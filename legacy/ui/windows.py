from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

SW_RESTORE = 9
SW_MINIMIZE = 6
SW_SHOW = 5
SW_MAXIMIZE = 3
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_A = 0x41
VK_V = 0x56
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def last_input_age_s() -> float:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 999.0
    return max(0.0, (kernel32.GetTickCount() - info.dwTime) / 1000.0)


def foreground_title() -> str:
    hwnd = int(user32.GetForegroundWindow() or 0)
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value or ""


_CS_COMPOSE_TITLES = ("接待中心", "咚咚工作站")


def human_is_busy(idle_s: float = 2.0, cs_idle_s: float = 2.0) -> bool:
    """True only when someone is typing in the CS compose window right now.

    Grok/terminal/browser activity must not freeze the queue.
    """
    age = last_input_age_s()
    if age >= idle_s:
        return False
    title = foreground_title()
    return any(k in title for k in _CS_COMPOSE_TITLES)


@dataclass(frozen=True)
class WinInfo:
    hwnd: int
    title: str
    class_name: str
    process: str
    visible: bool
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    def rel_to_abs(self, x_rel: float, y_rel: float) -> tuple[int, int]:
        return (
            int(self.left + self.width * x_rel),
            int(self.top + self.height * y_rel),
        )


def _text(fn, hwnd: int, size: int) -> str:
    buf = ctypes.create_unicode_buffer(size)
    fn(hwnd, buf, size)
    return buf.value


TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


_pid_name_cache: dict[int, str] = {}


def _pid_names() -> dict[int, str]:
    if _pid_name_cache:
        return _pid_name_cache
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1 or not snap:
        return {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            return {}
        while True:
            name = entry.szExeFile
            if name.lower().endswith(".exe"):
                name = name[:-4]
            _pid_name_cache[int(entry.th32ProcessID)] = name
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                break
        return _pid_name_cache
    finally:
        kernel32.CloseHandle(snap)


def _process_name(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    mapped = _pid_names().get(int(pid.value), "")
    if mapped:
        return mapped
    access = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
    handle = kernel32.OpenProcess(access, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(32768)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            name = buf.value.replace("/", "\\").rsplit("\\", 1)[-1]
        else:
            small = ctypes.create_unicode_buffer(260)
            psapi.GetModuleBaseNameW(handle, None, small, 260)
            name = small.value
        if name.lower().endswith(".exe"):
            name = name[:-4]
        return name
    finally:
        kernel32.CloseHandle(handle)


def _rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def list_windows() -> list[WinInfo]:
    _pid_name_cache.clear()
    found: list[WinInfo] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        title = _text(user32.GetWindowTextW, hwnd, 512)
        class_name = _text(user32.GetClassNameW, hwnd, 256)
        left, top, right, bottom = _rect(hwnd)
        found.append(
            WinInfo(
                hwnd=int(hwnd),
                title=title,
                class_name=class_name,
                process=_process_name(hwnd),
                visible=bool(user32.IsWindowVisible(hwnd)),
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )
        )
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return found


def find_window(
    process: str,
    title_contains: str,
    visible_only: bool = True,
    min_size: int = 200,
) -> WinInfo | None:
    process_l = process.lower()
    needle = title_contains.lower()
    windows = list_windows()
    matches = [
        w
        for w in windows
        if needle in w.title.lower()
        and (w.visible or not visible_only)
        and w.width >= min_size
        and w.height >= min_size
        and (not process_l or w.process.lower() == process_l or w.process == "")
    ]
    if not matches:
        return None
    matches.sort(key=lambda w: w.width * w.height, reverse=True)
    return matches[0]


def restore_if_needed(process: str, title_contains: str) -> WinInfo | None:
    win = find_window(process, title_contains, visible_only=True)
    if win is not None:
        return win
    hidden = find_window(process, title_contains, visible_only=False, min_size=0)
    if hidden is None:
        return None
    user32.ShowWindow(hidden.hwnd, SW_RESTORE)
    time.sleep(0.25)
    return find_window(process, title_contains, visible_only=True)


def find_notify(title_equals: str | None = None, title_startswith: str | None = None) -> WinInfo | None:
    for w in list_windows():
        if title_equals and w.title == title_equals:
            return w
        if title_startswith and w.title.startswith(title_startswith):
            return w
    return None


HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
VK_MENU = 0x12
VK_ESCAPE = 0x1B
VK_SHIFT = 0x10
VK_INSERT = 0x2D
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_SETFOCUS = 0x0007
MK_LBUTTON = 0x0001


def _escape(times: int = 2) -> None:
    for _ in range(times):
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)


def maximize(win: WinInfo) -> None:
    user32.ShowWindow(win.hwnd, SW_MAXIMIZE)


def win_from_hwnd(hwnd: int) -> WinInfo | None:
    for w in list_windows():
        if w.hwnd == hwnd:
            return w
    return None


def foreground(
    win: WinInfo,
    settle_s: float = 0.35,
    keep_topmost: bool = False,
    restore: bool = True,
) -> None:
    # SW_RESTORE un-maximizes; skip it when the window should stay maximized.
    user32.ShowWindow(win.hwnd, SW_RESTORE if restore else SW_SHOW)
    user32.BringWindowToTop(win.hwnd)
    # Unlock SetForegroundWindow via a brief Alt keystroke.
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.SetForegroundWindow(win.hwnd)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    # Qt treats leftover Alt as "menu focus" and then ignores clicks/keys.
    _escape(3)
    # Force z-order above the other fullscreen client.
    user32.SetWindowPos(win.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    time.sleep(0.05)
    if not keep_topmost:
        user32.SetWindowPos(win.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    fg = user32.GetForegroundWindow()
    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None)
    target_tid = user32.GetWindowThreadProcessId(win.hwnd, None)
    if fg_tid and fg_tid != cur_tid:
        user32.AttachThreadInput(cur_tid, fg_tid, True)
    if target_tid and target_tid != cur_tid:
        user32.AttachThreadInput(cur_tid, target_tid, True)
    user32.SetForegroundWindow(win.hwnd)
    if target_tid and target_tid != cur_tid:
        user32.AttachThreadInput(cur_tid, target_tid, False)
    if fg_tid and fg_tid != cur_tid:
        user32.AttachThreadInput(cur_tid, fg_tid, False)
    time.sleep(settle_s)


def click_abs(x: int, y: int, settle_s: float = 0.15) -> None:
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(settle_s)


def _key(vk: int, down: bool) -> None:
    flags = 0 if down else KEYEVENTF_KEYUP
    user32.keybd_event(vk, 0, flags, 0)


def hotkey(*vks: int) -> None:
    for vk in vks:
        _key(vk, True)
        time.sleep(0.02)
    for vk in reversed(vks):
        _key(vk, False)
        time.sleep(0.02)


def set_clipboard_text(text: str) -> None:
    import win32clipboard
    import win32con

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def paste_text(text: str, extra_shift_insert: bool = False) -> None:
    """Paste into the focused control. Never presses Enter."""
    import uiautomation as auto

    auto.SetClipboardText(text)
    time.sleep(0.1)
    # Do not Ctrl+A: that often selects the read-only chat history instead.
    auto.SendKeys("{Ctrl}v")
    time.sleep(0.2)
    if extra_shift_insert:
        # Jingmai's Qt pane often ignores Ctrl+V; Shift+Insert is a second native paste.
        hotkey(VK_SHIFT, VK_INSERT)
        time.sleep(0.25)
    else:
        time.sleep(0.1)


def _client_click(hwnd: int, screen_x: int, screen_y: int) -> None:
    pt = wintypes.POINT(int(screen_x), int(screen_y))
    user32.ScreenToClient(hwnd, ctypes.byref(pt))
    lp = (int(pt.y) << 16) | (int(pt.x) & 0xFFFF)
    user32.SendMessageW(hwnd, WM_SETFOCUS, 0, 0)
    user32.SendMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.03)
    user32.SendMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def screenshot_region(win: WinInfo, x_rel: float, y_rel: float, out_path: Path, pad: int = 180) -> Path:
    from PIL import ImageGrab

    # Capture the bottom third of the window so the compose box is visible.
    box = (
        win.left + int(win.width * 0.16),
        win.top + int(win.height * 0.58),
        win.left + int(win.width * 0.58),
        win.bottom - 4,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(bbox=box).save(out_path)
    return out_path


SIBLING_TITLES = ("接待中心", "咚咚融合工作台")


def _minimize_siblings(keep: WinInfo) -> list[int]:
    minimized: list[int] = []
    for w in list_windows():
        if w.hwnd == keep.hwnd or not w.visible:
            continue
        if any(s in w.title for s in SIBLING_TITLES):
            user32.ShowWindow(w.hwnd, SW_MINIMIZE)
            minimized.append(w.hwnd)
    return minimized


def click_send_button(win: WinInfo) -> bool:
    """Click a 发送 button in the lower part of the window. Never presses Enter."""
    import uiautomation as auto

    labels = ("发送", "發送", "Send")
    bottom = win.top + int(win.height * 0.60)

    def consider(ctrl) -> tuple[int, int] | None:
        try:
            name = (ctrl.Name or "").strip()
        except Exception:
            return None
        if name not in labels:
            return None
        try:
            r = ctrl.BoundingRectangle
            w = int(r.right) - int(r.left)
            h = int(r.bottom) - int(r.top)
            cx = (int(r.left) + int(r.right)) // 2
            cy = (int(r.top) + int(r.bottom)) // 2
        except Exception:
            return None
        if cy < bottom or w < 18 or h < 10 or w > 240 or h > 90:
            return None
        if not (win.left <= cx <= win.right and win.top <= cy <= win.bottom):
            return None
        return cx, cy

    try:
        root = auto.ControlFromHandle(win.hwnd)
        found = root.FindControl(lambda c, _d: consider(c) is not None, maxDepth=24)
    except Exception:
        found = None
    if found is None:
        return False
    pt = consider(found)
    if pt is None:
        return False
    click_abs(pt[0], pt[1], settle_s=0.45)
    return True


def fill_input(
    win: WinInfo,
    x_rel: float,
    y_rel: float,
    text: str,
    auto_send: bool,
    minimize_siblings: bool = True,
    restore_previous: bool = False,
) -> None:
    prev = int(user32.GetForegroundWindow() or 0)
    if minimize_siblings:
        _minimize_siblings(win)
        time.sleep(0.2)
    foreground(win, settle_s=0.45, keep_topmost=False, restore=False)
    x, y = win.rel_to_abs(x_rel, y_rel)
    pt = wintypes.POINT(int(x), int(y))
    hit = int(user32.WindowFromPoint(pt))
    if hit:
        _client_click(hit, x, y)
        time.sleep(0.12)
    click_abs(x, y, settle_s=0.25)
    click_abs(x, y, settle_s=0.2)
    paste_text(text, extra_shift_insert="咚咚" in win.title)
    if auto_send:
        if not click_send_button(win):
            raise RuntimeError("发送 button not found after fill")
        time.sleep(0.3)
    user32.SetWindowPos(
        win.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    )
    if restore_previous and prev and prev != win.hwnd:
        user32.SetForegroundWindow(prev)


def refuse_send() -> Callable[..., None]:
    def _send(*_a, **_k) -> None:
        raise RuntimeError("refusing to send: phase 1 only fills the input box")

    return _send

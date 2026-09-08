"""Count dark pixels after Jingmai paste attempts. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import ctypes
import time
from ctypes import wintypes

from PIL import ImageGrab

from legacy.ui.windows import (
    SW_RESTORE,
    VK_CONTROL,
    VK_V,
    _minimize_siblings,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_SETFOCUS = 0x0007
MK_LBUTTON = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


def dark_count(box=(346, 669, 1058, 1030), thresh=80) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.getdata():
        if px[0] < thresh and px[1] < thresh and px[2] < thresh:
            n += 1
    return n


def post_click(hwnd: int, cx: int, cy: int) -> None:
    lp = (cy << 16) | (cx & 0xFFFF)
    user32.PostMessageW(hwnd, WM_SETFOCUS, 0, 0)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.04)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)
    time.sleep(0.12)


def sendinput_click(x: int, y: int) -> None:
    extra = ctypes.c_ulonglong(0)
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]

    ax = int(x * 65535 / max(sw - 1, 1))
    ay = int(y * 65535 / max(sh - 1, 1))
    inp = INPUT()
    inp.type = 0
    inp.union.mi = MOUSEINPUT(ax, ay, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, extra)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    time.sleep(0.03)
    for flags in (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP):
        inp = INPUT()
        inp.type = 0
        inp.union.mi = MOUSEINPUT(0, 0, 0, flags, 0, extra)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.02)


def ctrl_v() -> None:
    extra = ctypes.c_ulonglong(0)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]

    def key(vk: int, flags: int) -> None:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki = KEYBDINPUT(vk, 0, flags, 0, extra)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    key(VK_CONTROL, 0)
    time.sleep(0.02)
    key(VK_V, 0)
    time.sleep(0.03)
    key(VK_V, KEYEVENTF_KEYUP)
    time.sleep(0.02)
    key(VK_CONTROL, KEYEVENTF_KEYUP)


def unicode_type(text: str) -> None:
    extra = ctypes.c_ulonglong(0)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]

    for ch in text:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.union.ki = KEYBDINPUT(0, ord(ch), flags, 0, extra)
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.006)


def main() -> int:
    artifacts = ROOT / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.4)

    hwnd_pane = 67506
    draft = "[草稿未发送] 咚咚填充1242"
    set_clipboard_text(draft)
    base = dark_count()
    print(f"base dark={base}")

    # Try several client clicks inside pane then Ctrl+V
    # pane is 712x408, client coords
    clients = [(40, 30), (80, 50), (200, 80), (100, 150), (300, 200), (50, 350)]
    for cx, cy in clients:
        post_click(hwnd_pane, cx, cy)
        ctrl_v()
        time.sleep(0.35)
        d = dark_count()
        print(f"postclick client({cx},{cy})+v dark={d} delta={d - base}")
        if d - base > 200:
            ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / f"jm-hit-client-{cx}-{cy}.png")
            print("HIT")
            print("not sent")
            return 0

    # Screen SendInput clicks
    screens = [(420, 700), (500, 740), (700, 800), (500, 1020), (900, 1020)]
    for x, y in screens:
        sendinput_click(x, y)
        time.sleep(0.08)
        sendinput_click(x, y)
        time.sleep(0.12)
        ctrl_v()
        time.sleep(0.35)
        d = dark_count()
        print(f"screen({x},{y})+v dark={d} delta={d - base}")
        if d - base > 200:
            ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / f"jm-hit-screen-{x}-{y}.png")
            print("HIT")
            print("not sent")
            return 0

    # Unicode type after best click
    sendinput_click(420, 700)
    time.sleep(0.15)
    unicode_type("DongdongFILL1242")
    time.sleep(0.35)
    d = dark_count()
    print(f"unicode type dark={d} delta={d - base}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-count-final.png")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Jingmai: PostMessage click + WM_CHAR/WM_PASTE into hwnd 67506. Never send."""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab, ImageStat

from ui.windows import (
    SW_RESTORE,
    _minimize_siblings,
    _text,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_CHAR = 0x0102
WM_PASTE = 0x0302
WM_SETFOCUS = 0x0007
MK_LBUTTON = 0x0001
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


def esc() -> None:
    user32.keybd_event(VK_ESCAPE, 0, 0, 0)
    user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)


def lparam_xy(x: int, y: int) -> int:
    return (y << 16) | (x & 0xFFFF)


def pane_sig() -> tuple:
    im = ImageGrab.grab(bbox=(346, 669, 1058, 1040))
    st = ImageStat.Stat(im)
    return (round(st.mean[0], 3), round(st.mean[1], 3), round(st.mean[2], 3), im.convert("L").getextrema())


def sendinput_click(x: int, y: int) -> None:
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    ax = int(x * 65535 / max(sw - 1, 1))
    ay = int(y * 65535 / max(sh - 1, 1))
    extra = ctypes.c_ulonglong(0) if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong(0)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]

    def fire(flags: int, dx: int = 0, dy: int = 0) -> None:
        inp = INPUT()
        inp.type = 0
        inp.union.mi = MOUSEINPUT(dx, dy, 0, flags, 0, extra)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    fire(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay)
    time.sleep(0.05)
    fire(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.03)
    fire(MOUSEEVENTF_LEFTUP)
    time.sleep(0.12)


def main() -> int:
    artifacts = Path(__file__).resolve().parent / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.4)
    esc()
    time.sleep(0.1)

    hwnd_pane = 67506
    if not user32.IsWindow(hwnd_pane):
        print("pane hwnd 67506 gone, searching...")
        return 1

    fg = user32.GetForegroundWindow()
    print(f"fg={fg} title={_text(user32.GetWindowTextW, fg, 80)!r}")
    pt = wintypes.POINT(420, 720)
    hit = int(user32.WindowFromPoint(pt))
    print(f"WindowFromPoint(420,720)={hit} class={_text(user32.GetClassNameW, hit, 80)!r}")

    left, top, right, bottom = ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd_pane, ctypes.byref(rect))
    print(f"pane 67506 rect=({rect.left},{rect.top})-({rect.right},{rect.bottom})")

    set_clipboard_text("[草稿未发送] 咚咚填充1240")
    base = pane_sig()
    print(f"base={base}")

    # 1) PostMessage click top-left of pane + WM_CHAR 'Z'
    cx, cy = 80, 40
    lp = lparam_xy(cx, cy)
    user32.PostMessageW(hwnd_pane, WM_SETFOCUS, 0, 0)
    user32.PostMessageW(hwnd_pane, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.05)
    user32.PostMessageW(hwnd_pane, WM_LBUTTONUP, 0, lp)
    time.sleep(0.1)
    user32.SendMessageW(hwnd_pane, WM_CHAR, ord("Z"), 0)
    time.sleep(0.2)
    s = pane_sig()
    print(f"after WM_CHAR Z to pane: {s} changed={s != base}")
    ImageGrab.grab(bbox=(346, 669, 1058, 900)).save(artifacts / "jm-wm-char.png")

    # 2) WM_PASTE to pane
    user32.SendMessageW(hwnd_pane, WM_PASTE, 0, 0)
    time.sleep(0.25)
    s2 = pane_sig()
    print(f"after WM_PASTE pane: {s2} changed={s2 != s}")

    # 3) same to toplevel
    user32.SendMessageW(win.hwnd, WM_CHAR, ord("Y"), 0)
    user32.SendMessageW(win.hwnd, WM_PASTE, 0, 0)
    time.sleep(0.2)
    s3 = pane_sig()
    print(f"after toplevel CHAR/PASTE: {s3} changed={s3 != s2}")

    # 4) SendInput absolute click + paste at (420,720) and (500,1040)
    import uiautomation as auto

    for x, y, tag in ((420, 720, "top"), (500, 1040, "sendleft"), (700, 780, "mid")):
        sendinput_click(x, y)
        sendinput_click(x, y)
        time.sleep(0.15)
        auto.SendKeys("{Ctrl}v", waitTime=0.05)
        time.sleep(0.35)
        s4 = pane_sig()
        print(f"SendInput click ({x},{y}) {tag}: {s4} changed={s4 != s3}")
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / f"jm-si-{tag}.png")
        if s4 != s3:
            s3 = s4
            print("HIT")
            break
        s3 = s4

    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-wm-final.png")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

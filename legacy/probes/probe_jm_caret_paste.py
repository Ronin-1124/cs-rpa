"""Focus Jingmai pane via PostMessage, then immediately Ctrl+V. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import ctypes
import time
from ctypes import wintypes

from PIL import ImageGrab, ImageStat

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
VK_ESCAPE = 0x1B

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004


def pane_sig() -> tuple:
    im = ImageGrab.grab(bbox=(346, 669, 1058, 1040))
    st = ImageStat.Stat(im)
    return (round(st.mean[0], 3), im.convert("L").getextrema())


def post_click_pane(hwnd: int, cx: int, cy: int) -> None:
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

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_ulonglong),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]

    ax = int(x * 65535 / max(sw - 1, 1))
    ay = int(y * 65535 / max(sh - 1, 1))
    inp = INPUT()
    inp.type = 0
    inp.union.mi = MOUSEINPUT(ax, ay, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, extra)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    time.sleep(0.04)
    for flags in (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP):
        inp = INPUT()
        inp.type = 0
        inp.union.mi = MOUSEINPUT(0, 0, 0, flags, 0, extra)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.03)


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
    time.sleep(0.02)
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
        time.sleep(0.008)


def close_ime(hwnd: int) -> None:
    try:
        imm32 = ctypes.windll.imm32
        himc = imm32.ImmGetContext(hwnd)
        if himc:
            imm32.ImmSetOpenStatus(himc, False)
            imm32.ImmReleaseContext(hwnd, himc)
    except Exception as e:
        print(f"ime err {e}")


def main() -> int:
    artifacts = ROOT / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.35)
    user32.keybd_event(VK_ESCAPE, 0, 0, 0)
    user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.1)

    hwnd_pane = 67506
    draft = "[草稿未发送] 咚咚填充1241"
    set_clipboard_text(draft)
    close_ime(win.hwnd)
    close_ime(hwnd_pane)

    base = pane_sig()
    print(f"base={base}")

    # A: PostMessage focus then immediate Ctrl+V
    post_click_pane(hwnd_pane, 80, 50)
    ImageGrab.grab(bbox=(346, 669, 900, 850)).save(artifacts / "jm-cp-caret.png")
    print(f"after post-click {pane_sig()}")
    ctrl_v()
    time.sleep(0.4)
    a = pane_sig()
    print(f"A postclick+ctrlv {a} changed={a != base}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-cp-A.png")
    if a != base:
        print("HIT A")
        print("not sent")
        return 0

    # B: SendInput click top of pane then Ctrl+V
    sendinput_click(430, 710)
    time.sleep(0.15)
    sendinput_click(430, 710)
    time.sleep(0.15)
    print(f"after si-click {pane_sig()}")
    ctrl_v()
    time.sleep(0.4)
    b = pane_sig()
    print(f"B sendinput+ctrlv {b} changed={b != a}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-cp-B.png")
    if b != a:
        print("HIT B")
        print("not sent")
        return 0

    # C: unicode type a short ASCII marker
    sendinput_click(430, 710)
    time.sleep(0.15)
    unicode_type("Dongdong1241")
    time.sleep(0.3)
    c = pane_sig()
    print(f"C unicode {c} changed={c != b}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-cp-C.png")

    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

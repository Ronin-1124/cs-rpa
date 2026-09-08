"""Try several Jingmai input methods. Never send / never Enter."""
from __future__ import annotations

from legacy.paths import ROOT

import ctypes
import time
from ctypes import wintypes

from PIL import ImageGrab

from legacy.ui.windows import _minimize_siblings, click_abs, foreground, restore_if_needed, set_clipboard_text, user32, VK_CONTROL, VK_V

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
WM_PASTE = 0x0302
WM_CHAR = 0x0102


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class INPUTUNION(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))


class INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("union", INPUTUNION))


def send_unicode(text: str) -> None:
    extra = ULONG_PTR(0)
    for ch in text:
        down = INPUT(type=INPUT_KEYBOARD)
        down.union.ki = KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE, 0, extra)
        up = INPUT(type=INPUT_KEYBOARD)
        up.union.ki = KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, extra)
        user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
        time.sleep(0.005)


def send_ctrl_v_input() -> None:
    extra = ULONG_PTR(0)
    for vk, flags in ((VK_CONTROL, 0), (VK_V, 0), (VK_V, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.union.ki = KEYBDINPUT(vk, 0, flags, 0, extra)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.02)


def main() -> int:
    artifacts = ROOT / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    time.sleep(0.2)
    foreground(win, settle_s=0.5)

    # Top-left of the compose pane, where the caret usually sits.
    x, y = 420, 730
    print(f"click compose ({x},{y})")
    click_abs(x, y, settle_s=0.2)
    click_abs(x, y, settle_s=0.3)
    user32.SetFocus(win.hwnd)

    print("method1 unicode type")
    send_unicode("咚咚直输A ")
    time.sleep(0.2)

    print("method2 clipboard + SendInput Ctrl+V")
    set_clipboard_text("咚咚粘贴B")
    time.sleep(0.1)
    send_ctrl_v_input()
    time.sleep(0.2)

    print("method3 uiautomation SendKeys")
    import uiautomation as auto

    auto.SendKeys("咚咚键入C", waitTime=0.05)
    time.sleep(0.3)

    out = artifacts / "jm-type-methods.png"
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(out)
    print(f"shot {out}")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

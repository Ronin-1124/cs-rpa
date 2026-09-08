"""Fine-scan top of Jingmai lower pane; click the text band and paste. Never send."""
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

KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
INPUT_KEYBOARD = 1


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


def dark_count(box, thresh=80) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.getdata():
        if px[0] < thresh and px[1] < thresh and px[2] < thresh:
            n += 1
    return n


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

    box = (346, 669, 1058, 780)
    ImageGrab.grab(bbox=box).save(artifacts / "jm-topband.png")
    im = ImageGrab.grab(bbox=box)
    pix = im.load()
    w, h = im.size
    print("fine rows of lower-top:")
    for y in range(h):
        nw = 0
        xs = []
        for x in range(w):
            r, g, b = pix[x, y][:3]
            if r < 240 or g < 240 or b < 240:
                nw += 1
                xs.append(x)
        if nw >= 8:
            print(
                f"  y={669+y:4} nw={nw:4} x={xs[0]}-{xs[-1]} "
                f"mid={346 + (xs[0]+xs[-1])//2}"
            )

    draft = "[草稿未发送] 咚咚填充1244"
    set_clipboard_text(draft)
    base = dark_count((346, 669, 1058, 1030))
    print(f"base dark={base}")

    # Click each nonwhite band's midpoint then paste.
    bands = []
    in_run = False
    start = 0
    for y in range(h):
        nw = 0
        for x in range(w):
            r, g, b = pix[x, y][:3]
            if r < 240 or g < 240 or b < 240:
                nw += 1
        if nw >= 8 and not in_run:
            in_run = True
            start = y
        elif nw < 8 and in_run:
            in_run = False
            bands.append((start, y))
    if in_run:
        bands.append((start, h))
    print(f"bands={[(669+a, 669+b) for a,b in bands]}")

    for a, b in bands:
        y = 669 + (a + b) // 2
        # find x midpoint of that row
        xs = []
        for x in range(w):
            r, g, bl = pix[x, a + (b - a) // 2][:3]
            if r < 240 or g < 240 or bl < 240:
                xs.append(x)
        if not xs:
            continue
        x = 346 + (xs[0] + xs[-1]) // 2
        print(f"click band ({x},{y})")
        sendinput_click(x, y)
        time.sleep(0.1)
        sendinput_click(x, y)
        time.sleep(0.15)
        ctrl_v()
        time.sleep(0.4)
        d = dark_count((346, 669, 1058, 1030))
        print(f"  dark={d} delta={d-base}")
        ImageGrab.grab(bbox=(346, 669, 1058, 1077)).save(artifacts / f"jm-band-{x}-{y}.png")
        if d - base > 200:
            print("HIT")
            print("not sent")
            return 0

    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Click each Jingmai toolbar icon, see which reveals a compose field. Never send."""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    SW_RESTORE,
    _minimize_siblings,
    restore_if_needed,
    user32,
)


def dark_count(box, thresh=80) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.getdata():
        if px[0] < thresh and px[1] < thresh and px[2] < thresh:
            n += 1
    return n


def nonwhite(box) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.getdata():
        if px[0] < 245 or px[1] < 245 or px[2] < 245:
            n += 1
    return n


def icon_centers(bar_box=(346, 631, 1058, 667)) -> list[tuple[int, int]]:
    im = ImageGrab.grab(bbox=bar_box)
    pix = im.load()
    w, h = im.size
    cols = []
    for x in range(w):
        ink = 0
        for y in range(h):
            r, g, b = pix[x, y][:3]
            if r < 230 or g < 230 or b < 230:
                ink += 1
        cols.append(ink)
    centers = []
    in_run = False
    start = 0
    for x, ink in enumerate(cols):
        if ink >= 3 and not in_run:
            in_run = True
            start = x
        elif ink < 3 and in_run:
            in_run = False
            width = x - start
            if 8 <= width <= 80:
                cx = bar_box[0] + (start + x) // 2
                cy = (bar_box[1] + bar_box[3]) // 2
                centers.append((cx, cy, width))
    if in_run:
        x = w
        width = x - start
        if 8 <= width <= 80:
            cx = bar_box[0] + (start + x) // 2
            cy = (bar_box[1] + bar_box[3]) // 2
            centers.append((cx, cy, width))
    return centers


def sendinput_click(x: int, y: int) -> None:
    import ctypes
    from ctypes import wintypes

    extra = ctypes.c_ulonglong(0)
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_ABSOLUTE = 0x8000

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

    ImageGrab.grab(bbox=(346, 620, 1058, 680)).save(artifacts / "jm-icons-bar.png")
    centers = icon_centers()
    print(f"found {len(centers)} toolbar icons: {centers}")

    lower = (346, 669, 1058, 1077)
    print(f"before lower nonwhite={nonwhite(lower)} dark={dark_count(lower)}")
    ImageGrab.grab(bbox=lower).save(artifacts / "jm-icons-lower-0.png")

    for i, (x, y, w) in enumerate(centers[:12]):
        print(f"click icon{i} ({x},{y}) width={w}")
        sendinput_click(x, y)
        time.sleep(0.55)
        nw = nonwhite(lower)
        dk = dark_count(lower)
        print(f"  after nonwhite={nw} dark={dk}")
        ImageGrab.grab(bbox=lower).save(artifacts / f"jm-icons-lower-{i+1}.png")
        ImageGrab.grab(bbox=(346, 620, 1058, 680)).save(artifacts / f"jm-icons-bar-{i+1}.png")

    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

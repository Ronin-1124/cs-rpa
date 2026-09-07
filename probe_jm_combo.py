"""Foreground Jingmai, PostMessage-click pane, immediately Ctrl+V. Never send."""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    VK_CONTROL,
    VK_V,
    _minimize_siblings,
    _text,
    foreground,
    hotkey,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_SETFOCUS = 0x0007
MK_LBUTTON = 0x0001
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002


def dark_count(box=(346, 669, 1058, 1030)) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.getdata():
        if px[0] < 80 and px[1] < 80 and px[2] < 80:
            n += 1
    return n


def post_click(hwnd: int, cx: int, cy: int) -> None:
    lp = (cy << 16) | (cx & 0xFFFF)
    user32.PostMessageW(hwnd, WM_SETFOCUS, 0, 0)
    user32.SendMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.03)
    user32.SendMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def main() -> int:
    artifacts = Path(__file__).resolve().parent / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    foreground(win, settle_s=0.45)
    for _ in range(3):
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)

    hwnd_pane = 67506
    draft = "[草稿未发送] 咚咚填充1250"
    set_clipboard_text(draft)
    base = dark_count()
    print(f"fg={int(user32.GetForegroundWindow())} base={base}")

    # client (74, 22) == screen (420, 691)
    post_click(hwnd_pane, 74, 22)
    time.sleep(0.15)
    print(f"after postclick dark={dark_count()} fg={int(user32.GetForegroundWindow())}")
    ImageGrab.grab(bbox=(346, 669, 1058, 780)).save(artifacts / "jm-combo-caret.png")
    hotkey(VK_CONTROL, VK_V)
    time.sleep(0.45)
    d = dark_count()
    print(f"after v dark={d} delta={d-base}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-combo-v.png")

    if d - base < 150:
        # also try second band client (125, 59) == (471, 728)
        post_click(hwnd_pane, 125, 59)
        time.sleep(0.12)
        hotkey(VK_CONTROL, VK_V)
        time.sleep(0.4)
        d2 = dark_count()
        print(f"band2 after v dark={d2} delta={d2-base}")
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-combo-v2.png")

        # WM_PASTE while focused
        user32.SendMessageW(hwnd_pane, 0x0302, 0, 0)
        time.sleep(0.3)
        d3 = dark_count()
        print(f"after WM_PASTE dark={d3}")

    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

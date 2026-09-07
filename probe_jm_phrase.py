"""Toggle 常用语 using band_nw metric, then paste. Never send."""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    VK_CONTROL,
    VK_V,
    _minimize_siblings,
    click_abs,
    foreground,
    hotkey,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002


def band_nw() -> int:
    im = ImageGrab.grab(bbox=(346, 675, 1058, 740))
    n = 0
    for px in im.getdata():
        if px[0] < 240 or px[1] < 240 or px[2] < 240:
            n += 1
    return n


def dark_count() -> int:
    im = ImageGrab.grab(bbox=(346, 669, 1058, 1030))
    n = 0
    for px in im.getdata():
        if px[0] < 80 and px[1] < 80 and px[2] < 80:
            n += 1
    return n


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

    print(f"start band_nw={band_nw()} dark={dark_count()}")
    ImageGrab.grab(bbox=(346, 620, 1058, 760)).save(artifacts / "jm-ph-0.png")

    for i, x in enumerate((370, 398, 426, 454, 482, 510, 538)):
        click_abs(x, 649, settle_s=0.5)
        b = band_nw()
        print(f"click toolbar x={x} band_nw={b}")
        ImageGrab.grab(bbox=(346, 620, 1058, 760)).save(artifacts / f"jm-ph-{i+1}.png")
        if b < 400:
            print("tabs/search gone — compose mode")
            break

    set_clipboard_text("[草稿未发送] 咚咚填充1251")
    base = dark_count()
    # click a few compose spots
    for x, y in ((420, 720), (500, 780), (420, 691), (700, 850)):
        click_abs(x, y, settle_s=0.2)
        click_abs(x, y, settle_s=0.2)
        hotkey(VK_CONTROL, VK_V)
        time.sleep(0.4)
        d = dark_count()
        print(f"paste ({x},{y}) dark={d} delta={d-base} band={band_nw()}")
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / f"jm-ph-p-{x}-{y}.png")
        if d - base > 200:
            print("HIT")
            break

    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

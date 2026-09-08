"""Use the production click+paste path at the placeholder band y=691. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import time

from PIL import ImageGrab

from legacy.ui.windows import _minimize_siblings, click_abs, fill_input, foreground, paste_text, restore_if_needed


def dark_count(box=(346, 669, 1058, 1030), thresh=80) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.getdata():
        if px[0] < thresh and px[1] < thresh and px[2] < thresh:
            n += 1
    return n


def nw_band() -> int:
    im = ImageGrab.grab(bbox=(346, 680, 1058, 705))
    n = 0
    for px in im.getdata():
        if px[0] < 240 or px[1] < 240 or px[2] < 240:
            n += 1
    return n


def main() -> int:
    artifacts = ROOT / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    print(f"win {win.width}x{win.height} hwnd={win.hwnd}")
    draft = "[草稿未发送] 咚咚填充1245"
    base = dark_count()
    print(f"base dark={base} band_nw={nw_band()}")

    # Production-like, but click the placeholder band.
    _minimize_siblings(win)
    time.sleep(0.2)
    foreground(win, settle_s=0.45)
    # y=691 / 1079 ≈ 0.640; x=420/1919 ≈ 0.219  (left of compose, where caret sits)
    x, y = 420, 691
    print(f"prod click ({x},{y}) rel=({x/win.width:.3f},{y/win.height:.3f})")
    click_abs(x, y, settle_s=0.25)
    click_abs(x, y, settle_s=0.2)
    paste_text(draft)
    time.sleep(0.4)
    d = dark_count()
    print(f"after prod-path dark={d} delta={d-base} band_nw={nw_band()}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-prod-691.png")
    ImageGrab.grab(bbox=(346, 669, 1058, 780)).save(artifacts / "jm-prod-691-top.png")

    if d - base < 200:
        # try left-of-band at x=380, and fill_input helper at 0.219, 0.640
        print("retry via fill_input rel 0.22, 0.640")
        fill_input(win, 0.22, 0.640, draft, auto_send=False)
        time.sleep(0.4)
        d2 = dark_count()
        print(f"after fill_input dark={d2} delta={d2-base}")
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-prod-fill.png")

    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

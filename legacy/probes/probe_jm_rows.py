"""Row histogram of Jingmai lower pane / toolbar. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import time

from PIL import ImageGrab

from legacy.ui.windows import SW_RESTORE, _minimize_siblings, restore_if_needed, user32


def row_hist(box, label: str) -> None:
    im = ImageGrab.grab(bbox=box)
    pix = im.load()
    w, h = im.size
    print(f"{label} {w}x{h}")
    for y in range(0, h, max(1, h // 20)):
        nw = 0
        dark = 0
        orange = 0
        blue = 0
        for x in range(w):
            r, g, b = pix[x, y][:3]
            if r < 245 or g < 245 or b < 245:
                nw += 1
            if r < 80 and g < 80 and b < 80:
                dark += 1
            if r > 200 and 70 < g < 180 and b < 90:
                orange += 1
            if b > r + 30 and b > g + 20 and b > 120:
                blue += 1
        if nw:
            print(f"  y={box[1]+y:4} nw={nw:4} dark={dark:3} orange={orange:3} blue={blue:3}")


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

    ImageGrab.grab(bbox=(346, 180, 1058, 1077)).save(artifacts / "jm-rows-col.png")
    row_hist((346, 180, 1058, 630), "chat")
    row_hist((346, 620, 1058, 680), "toolbar-wide")
    row_hist((346, 631, 1058, 667), "toolbar")
    row_hist((346, 669, 1058, 1077), "lower")
    row_hist((64, 74, 344, 400), "session-top")
    row_hist((1060, 134, 1289, 500), "mid-strip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

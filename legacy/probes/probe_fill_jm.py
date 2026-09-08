"""Fill Jingmai compose now that 常用语 is collapsed. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import time
from ctypes import wintypes

from PIL import ImageGrab

from legacy.ui.windows import (
    _minimize_siblings,
    click_abs,
    foreground,
    hotkey,
    restore_if_needed,
    set_clipboard_text,
    user32,
    VK_CONTROL,
    VK_V,
)

WM_PASTE = 0x0302


def main() -> int:
    artifacts = ROOT / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    time.sleep(0.25)
    foreground(win, settle_s=0.45)

    # Compose is the white area of the lower pane, above 发送.
    x, y = 700, 850
    print(f"click compose ({x},{y})")
    click_abs(x, y, settle_s=0.2)
    click_abs(x, y, settle_s=0.25)

    text = "[草稿未发送] 咚咚填充1231"
    set_clipboard_text(text)
    time.sleep(0.1)
    hotkey(VK_CONTROL, VK_V)
    time.sleep(0.15)
    pt = wintypes.POINT(x, y)
    hwnd = user32.WindowFromPoint(pt)
    user32.SendMessageW(int(hwnd), WM_PASTE, 0, 0)
    time.sleep(0.4)

    out = artifacts / "jm-fill-1231.png"
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(out)
    print(f"pasted: {text}")
    print(f"shot {out}")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

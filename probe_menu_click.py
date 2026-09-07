"""Jingmai compose: no-Alt focus, uiautomation right-click, scan for menu. Never send."""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    SW_RESTORE,
    _minimize_siblings,
    click_abs,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002


def esc() -> None:
    user32.keybd_event(VK_ESCAPE, 0, 0, 0)
    user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.08)


def dark_pixels(path: Path, thresh: int = 80) -> int:
    img = ImageGrab.grab() if False else None
    from PIL import Image

    im = Image.open(path)
    n = 0
    for px in im.getdata():
        r, g, b = px[:3]
        if r < thresh and g < thresh and b < thresh:
            n += 1
    return n


def shot(path: Path, box) -> int:
    ImageGrab.grab(bbox=box).save(path)
    n = dark_pixels(path)
    print(f"  {path.name} dark={n}")
    return n


def main() -> int:
    artifacts = Path(__file__).resolve().parent / "artifacts"
    artifacts.mkdir(exist_ok=True)

    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.4)
    for _ in range(3):
        esc()

    import uiautomation as auto

    x, y = 500, 820
    print(f"uia Click+RightClick ({x},{y})")
    auto.Click(x, y)
    time.sleep(0.2)
    set_clipboard_text("[草稿未发送] 咚咚填充1238")
    time.sleep(0.1)
    auto.RightClick(x, y)
    time.sleep(0.45)
    dark = shot(artifacts / "jm-uia-rclick.png", (300, 620, 950, 1050))

    pasted = False
    item = auto.MenuItemControl(searchDepth=25, Name="粘贴")
    if item.Exists(0.6, 0.08):
        print("UIA 粘贴 click")
        item.Click()
        pasted = True
    else:
        print("no UIA 粘贴")
        if dark > 40:
            click_abs(x + 50, y + 38, settle_s=0.35)
            pasted = True

    time.sleep(0.3)
    shot(artifacts / "jm-paste-1238.png", (346, 500, 1058, 1077))
    esc()
    esc()

    if not pasted:
        print("scanning compose pane for context menu...")
        best = (0, 0, 0)
        for sy in (690, 720, 760, 800, 850, 900, 960, 1020):
            for sx in (420, 700):
                auto.Click(sx, sy)
                time.sleep(0.08)
                auto.RightClick(sx, sy)
                time.sleep(0.28)
                name = artifacts / f"jm-scan-{sx}-{sy}.png"
                n = shot(name, (sx - 20, sy - 20, sx + 180, sy + 140))
                if n > best[0]:
                    best = (n, sx, sy)
                esc()
                time.sleep(0.08)
        print(f"best dark={best}")
        if best[0] > 40:
            sx, sy = best[1], best[2]
            auto.Click(sx, sy)
            time.sleep(0.1)
            set_clipboard_text("[草稿未发送] 咚咚填充1238")
            auto.RightClick(sx, sy)
            time.sleep(0.4)
            click_abs(sx + 50, sy + 38, settle_s=0.4)
            shot(artifacts / "jm-paste-1238b.png", (346, 500, 1058, 1077))

    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

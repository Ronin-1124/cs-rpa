"""Right-click -> 粘贴 into Jingmai compose. Never send chat."""
from __future__ import annotations

from legacy.paths import ROOT

import time

from PIL import ImageGrab

from legacy.ui.windows import (
    _minimize_siblings,
    click_abs,
    foreground,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
VK_DOWN = 0x28
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002


def right_click(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(0.03)
    user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    time.sleep(0.35)


def key(vk: int) -> None:
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.08)


def main() -> int:
    artifacts = ROOT / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    time.sleep(0.2)
    foreground(win, settle_s=0.45)

    x, y = 420, 760
    click_abs(x, y, settle_s=0.2)
    click_abs(x, y, settle_s=0.2)

    text = "[草稿未发送] 咚咚填充1232"
    set_clipboard_text(text)
    time.sleep(0.1)
    right_click(x, y)
    ImageGrab.grab(bbox=(346, 650, 800, 1000)).save(artifacts / "jm-menu-before-paste.png")
    # Context menu: 复制, 粘贴, 全选. Move to 粘贴 then activate.
    key(VK_DOWN)
    key(VK_DOWN)
    key(VK_RETURN)
    time.sleep(0.45)

    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-menu-paste.png")
    print(f"pasted via menu: {text}")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

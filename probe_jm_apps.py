"""After focusing Jingmai compose, press Apps/Shift+F10 for context menu paste. Never send."""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    SW_RESTORE,
    VK_CONTROL,
    VK_V,
    _minimize_siblings,
    click_abs,
    foreground,
    list_windows,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

KEYEVENTF_KEYUP = 0x0002
VK_APPS = 0x5D
VK_SHIFT = 0x10
VK_F10 = 0x79
VK_ESCAPE = 0x1B
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


def key(vk: int) -> None:
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def dump_popups(tag: str) -> None:
    print(f"--- popups {tag} ---")
    for w in list_windows():
        if not w.visible:
            continue
        if w.width < 8 or w.height < 8:
            continue
        if w.width > 900 and w.height > 700:
            continue
        if "咚咚" in w.title or "接待" in w.title:
            if w.width > 400:
                continue
        print(
            f"  {w.hwnd} {w.class_name:28} {w.width:4}x{w.height:<4} "
            f"({w.left},{w.top}) {w.title[:40]!r}"
        )


def dark_count(box=(346, 669, 1058, 1030)) -> int:
    im = ImageGrab.grab(bbox=box)
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
    time.sleep(0.2)
    foreground(win, settle_s=0.4)
    key(VK_ESCAPE)
    time.sleep(0.1)

    set_clipboard_text("[草稿未发送] 咚咚填充1247")
    x, y = 420, 691
    click_abs(x, y, settle_s=0.2)
    click_abs(x, y, settle_s=0.25)

    dump_popups("before")
    print("press VK_APPS")
    key(VK_APPS)
    time.sleep(0.45)
    dump_popups("after-apps")
    ImageGrab.grab(bbox=(x - 20, y - 20, x + 220, y + 180)).save(artifacts / "jm-apps-menu.png")

    import uiautomation as auto

    item = auto.MenuItemControl(searchDepth=20, Name="粘贴")
    if item.Exists(0.5, 0.08):
        print("UIA 粘贴 via Apps")
        item.Click()
        time.sleep(0.35)
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-apps-paste.png")
        print(f"dark={dark_count()}")
        print("not sent")
        return 0
    print("no UIA 粘贴 after Apps")
    key(VK_ESCAPE)

    print("Shift+F10")
    user32.keybd_event(VK_SHIFT, 0, 0, 0)
    key(VK_F10)
    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.45)
    dump_popups("after-s-f10")
    ImageGrab.grab(bbox=(x - 20, y - 20, x + 220, y + 180)).save(artifacts / "jm-sf10-menu.png")
    if item.Exists(0.4, 0.08):
        print("UIA 粘贴 via Shift+F10")
        item.Click()
        time.sleep(0.35)
        print(f"dark={dark_count()}")
        print("not sent")
        return 0
    key(VK_ESCAPE)

    print("mouse_event right-click")
    user32.SetCursorPos(x, y)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(0.12)
    user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    time.sleep(0.5)
    dump_popups("after-rclick")
    ImageGrab.grab(bbox=(x - 30, y - 30, x + 250, y + 200)).save(artifacts / "jm-rclick-691.png")
    if item.Exists(0.5, 0.08):
        print("UIA 粘贴 via rclick")
        item.Click()
        time.sleep(0.35)
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-rclick-paste.png")
        print(f"dark={dark_count()}")
        print("not sent")
        return 0

    # Pixel-click presumed 粘贴 offset (second item ~ 22px each)
    print("click offset 2nd menu item anyway")
    click_abs(x + 40, y + 44, settle_s=0.4)
    d = dark_count()
    print(f"dark after offset click={d}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-rclick-offset.png")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

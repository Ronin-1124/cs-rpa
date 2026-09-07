"""DPI check, right-click compose, and CEF-bottom paste. Never send."""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
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

MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010


def right_click(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    time.sleep(0.35)


def main() -> int:
    artifacts = Path(__file__).resolve().parent / "artifacts"
    try:
        dpi = user32.GetDpiForSystem()
    except Exception:
        dpi = -1
    aware = ctypes.windll.user32.IsProcessDPIAware()
    print(f"dpi={dpi} process_dpi_aware={aware}")

    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    try:
        wdpi = user32.GetDpiForWindow(win.hwnd)
    except Exception:
        wdpi = -1
    print(f"window dpi={wdpi} rect=({win.left},{win.top})-({win.right},{win.bottom}) {win.width}x{win.height}")

    _minimize_siblings(win)
    time.sleep(0.2)
    foreground(win, settle_s=0.45)

    # Right-click suspected compose.
    print("right-click pane (420,730)")
    click_abs(420, 730, settle_s=0.15)
    right_click(420, 730)
    ImageGrab.grab(bbox=(346, 650, 900, 1000)).save(artifacts / "jm-rclick-pane.png")
    print("shot jm-rclick-pane.png")
    time.sleep(0.2)
    # Dismiss menu with Escape
    user32.keybd_event(0x1B, 0, 0, 0)
    user32.keybd_event(0x1B, 0, 2, 0)
    time.sleep(0.2)

    # Right-click CEF bottom.
    print("right-click cef (700,610)")
    click_abs(700, 610, settle_s=0.15)
    right_click(700, 610)
    ImageGrab.grab(bbox=(500, 500, 1058, 780)).save(artifacts / "jm-rclick-cef.png")
    print("shot jm-rclick-cef.png")
    user32.keybd_event(0x1B, 0, 0, 0)
    user32.keybd_event(0x1B, 0, 2, 0)
    time.sleep(0.2)

    # Paste into CEF bottom.
    print("paste into cef bottom")
    click_abs(700, 600, settle_s=0.2)
    click_abs(700, 600, settle_s=0.2)
    set_clipboard_text("[草稿未发送] 咚咚CEF600")
    time.sleep(0.1)
    hotkey(VK_CONTROL, VK_V)
    time.sleep(0.4)
    ImageGrab.grab(bbox=(346, 188, 1058, 670)).save(artifacts / "jm-cef-paste.png")
    print("shot jm-cef-paste.png")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

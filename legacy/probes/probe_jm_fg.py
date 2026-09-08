"""Force Jingmai keyboard focus, Escape out of Alt, paste at y=691. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import time

from PIL import ImageGrab

from legacy.ui.windows import (
    VK_CONTROL,
    VK_V,
    _minimize_siblings,
    _text,
    click_abs,
    foreground,
    hotkey,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002


def dark_count(box=(346, 669, 1058, 1030)) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.getdata():
        if px[0] < 80 and px[1] < 80 and px[2] < 80:
            n += 1
    return n


def fg_info() -> str:
    h = int(user32.GetForegroundWindow())
    return f"{h} {_text(user32.GetWindowTextW, h, 60)!r} {_text(user32.GetClassNameW, h, 40)!r}"


def main() -> int:
    artifacts = ROOT / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    print(f"before fg {fg_info()}")
    foreground(win, settle_s=0.5)
    print(f"after foreground {fg_info()}")
    for _ in range(4):
        user32.keybd_event(VK_ESCAPE, 0, 0, 0)
        user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.06)
    print(f"after esc {fg_info()}")

    if int(user32.GetForegroundWindow()) != win.hwnd:
        print("retry foreground")
        foreground(win, settle_s=0.5)
        for _ in range(3):
            user32.keybd_event(VK_ESCAPE, 0, 0, 0)
            user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.06)
        print(f"after retry {fg_info()}")

    draft = "[草稿未发送] 咚咚填充1249"
    set_clipboard_text(draft)
    base = dark_count()
    print(f"base dark={base}")

    x, y = 420, 691
    click_abs(x, y, settle_s=0.25)
    print(f"after click1 {fg_info()}")
    click_abs(x, y, settle_s=0.25)
    print(f"after click2 {fg_info()}")
    hotkey(VK_CONTROL, VK_V)
    time.sleep(0.45)
    d = dark_count()
    print(f"after hotkey-v dark={d} delta={d-base} fg={fg_info()}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-fg-fill.png")
    ImageGrab.grab(bbox=(346, 669, 1058, 780)).save(artifacts / "jm-fg-top.png")

    if d - base < 150:
        print("second try paste_text")
        from legacy.ui.windows import paste_text

        click_abs(x, y, settle_s=0.2)
        paste_text(draft)
        time.sleep(0.4)
        d2 = dark_count()
        print(f"after paste_text dark={d2} delta={d2-base} fg={fg_info()}")
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-fg-fill2.png")

    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

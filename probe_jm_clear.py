"""Minimize everything covering Jingmai compose, TOPMOST, paste. Never send."""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    HWND_NOTOPMOST,
    HWND_TOPMOST,
    SW_MINIMIZE,
    SW_RESTORE,
    SWP_NOMOVE,
    SWP_NOSIZE,
    SWP_SHOWWINDOW,
    click_abs,
    list_windows,
    paste_text,
    restore_if_needed,
    set_clipboard_text,
    user32,
)


def dark_count(box=(346, 669, 1058, 1030)) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.getdata():
        if px[0] < 80 and px[1] < 80 and px[2] < 80:
            n += 1
    return n


def intersects(w, x: int, y: int) -> bool:
    return w.left <= x < w.right and w.top <= y < w.bottom


def main() -> int:
    artifacts = Path(__file__).resolve().parent / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1

    x, y = 420, 691
    minimized = []
    print("windows at click point:")
    for w in list_windows():
        if not w.visible or w.hwnd == win.hwnd:
            continue
        if w.width < 20 or w.height < 20:
            continue
        if intersects(w, x, y) or (w.left < 1058 and w.top < 1077 and w.right > 346 and w.bottom > 669):
            print(f"  overlap {w.hwnd} {w.class_name} {w.width}x{w.height} ({w.left},{w.top}) {w.title[:50]!r}")
            if w.class_name in ("Shell_TrayWnd",):
                continue
            user32.ShowWindow(w.hwnd, SW_MINIMIZE)
            minimized.append(w.hwnd)

    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetWindowPos(win.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.45)

    import ctypes
    from ctypes import wintypes

    pt = wintypes.POINT(x, y)
    hit = int(user32.WindowFromPoint(pt))
    fg = int(user32.GetForegroundWindow())
    print(f"fg={fg} hit={hit} jingmai={win.hwnd} pane=67506")

    draft = "[草稿未发送] 咚咚填充1248"
    set_clipboard_text(draft)
    base = dark_count()
    print(f"base dark={base}")
    click_abs(x, y, settle_s=0.25)
    click_abs(x, y, settle_s=0.2)
    paste_text(draft)
    time.sleep(0.45)
    d = dark_count()
    print(f"after paste dark={d} delta={d-base}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-clear-fill.png")
    ImageGrab.grab(bbox=(346, 669, 1058, 780)).save(artifacts / "jm-clear-top.png")

    # drop topmost
    user32.SetWindowPos(win.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""UIA from each Jingmai child HWND + session click then paste. Never send."""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

from ui.windows import (
    SW_RESTORE,
    WinInfo,
    _minimize_siblings,
    _process_name,
    _rect,
    _text,
    click_abs,
    fill_input,
    foreground,
    restore_if_needed,
    user32,
)

EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def children(parent: int) -> list[WinInfo]:
    found: list[WinInfo] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        title = _text(user32.GetWindowTextW, hwnd, 512)
        class_name = _text(user32.GetClassNameW, hwnd, 256)
        left, top, right, bottom = _rect(hwnd)
        found.append(
            WinInfo(
                hwnd=int(hwnd),
                title=title,
                class_name=class_name,
                process=_process_name(hwnd),
                visible=bool(user32.IsWindowVisible(hwnd)),
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )
        )
        return True

    user32.EnumChildWindows(parent, EnumChildProc(callback), 0)
    return found


def dump_ctrl(c, prefix: str) -> None:
    try:
        r = c.BoundingRectangle
        rect = f"({r.left},{r.top})-({r.right},{r.bottom})"
    except Exception:
        rect = "?"
    try:
        print(
            f"{prefix} type={c.ControlTypeName} name={c.Name!r:.70} "
            f"cls={c.ClassName!r} kids={len(c.GetChildren())} "
            f"focusable={c.IsKeyboardFocusable} hwnd={c.NativeWindowHandle} rect={rect}"
        )
    except Exception as e:
        print(f"{prefix} err {e}")


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
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.35)

    import uiautomation as auto

    print("=== ControlFromHandle per child ===")
    for k in children(win.hwnd):
        if not k.visible or k.width < 20 or k.height < 16:
            continue
        if k.top > 1100:
            continue
        try:
            c = auto.ControlFromHandle(k.hwnd)
        except Exception as e:
            print(f"hwnd {k.hwnd} ControlFromHandle err {e}")
            continue
        dump_ctrl(c, f"{k.hwnd} {k.class_name[:18]:18} {k.width}x{k.height}")
        try:
            for i, ch in enumerate(c.GetChildren()[:8]):
                dump_ctrl(ch, f"    kid{i}")
        except Exception:
            pass

    # Click a session then production fill at y=691
    print("=== click session (200,200) then fill ===")
    click_abs(200, 200, settle_s=0.35)
    click_abs(200, 250, settle_s=0.35)
    ImageGrab.grab(bbox=(64, 74, 344, 400)).save(artifacts / "jm-session.png")
    ImageGrab.grab(bbox=(346, 669, 1058, 780)).save(artifacts / "jm-after-session-top.png")
    base = dark_count()
    print(f"dark after session click={base}")
    fill_input(win, 0.22, 0.640, "[草稿未发送] 咚咚填充1246", auto_send=False)
    time.sleep(0.4)
    d = dark_count()
    print(f"dark after fill={d} delta={d-base}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-after-session-fill.png")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

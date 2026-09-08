"""Toggle Jingmai 常用语 panel, dump layout, try paste at candidate spots. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

from legacy.ui.windows import WinInfo, _minimize_siblings, _process_name, _rect, _text, click_abs, foreground, hotkey, restore_if_needed, user32, VK_CONTROL, VK_V

WM_PASTE = 0x0302
WM_CHAR = 0x0102
VK_SHIFT = 0x10
VK_INSERT = 0x2D


def child_windows(parent: int) -> list[WinInfo]:
    EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
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


def window_from_point(x: int, y: int) -> tuple[int, str, str]:
    pt = wintypes.POINT(int(x), int(y))
    hwnd = int(user32.WindowFromPoint(pt))
    return hwnd, _text(user32.GetWindowTextW, hwnd, 512), _text(user32.GetClassNameW, hwnd, 256)


def paste_wm(hwnd: int) -> None:
    user32.SendMessageW(hwnd, WM_PASTE, 0, 0)


def paste_ctrl_v() -> None:
    hotkey(VK_CONTROL, VK_V)


def paste_shift_insert() -> None:
    hotkey(VK_SHIFT, VK_INSERT)


def shot(path: Path, box) -> None:
    ImageGrab.grab(bbox=box).save(path)
    print(f"shot {path.name} {box}")


def dump_visible(win: WinInfo) -> None:
    kids = child_windows(win.hwnd)
    print(f"visible children of {win.hwnd}:")
    for k in sorted(kids, key=lambda w: (w.top, w.left)):
        if not k.visible or k.width < 8 or k.height < 8:
            continue
        print(
            f"  {k.hwnd} {k.class_name:28} {k.width:4}x{k.height:<4} "
            f"({k.left},{k.top})-({k.right},{k.bottom})"
        )


def main() -> int:
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)

    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    time.sleep(0.3)
    foreground(win, settle_s=0.4)

    print("=== before toggle ===")
    dump_visible(win)
    shot(artifacts / "jm2-before.png", (346, 500, 1058, 1077))

    # 常用语 icon is the left control on the 36px strip (346,631)-(1058,667).
    # Click near the left of that strip to collapse the phrases panel.
    print("clicking 常用语 toolbar at (396,649)")
    click_abs(396, 649, settle_s=0.6)
    time.sleep(0.4)
    print("=== after 常用语 click ===")
    dump_visible(win)
    shot(artifacts / "jm2-after-toggle.png", (346, 500, 1058, 1077))
    shot(artifacts / "jm2-full.png", (0, 0, 1919, 1079))

    print("point probes x=700 after toggle:")
    for y in range(500, 1070, 25):
        hwnd, title, cls = window_from_point(700, y)
        print(f"  y={y:4} hwnd={hwnd} class={cls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

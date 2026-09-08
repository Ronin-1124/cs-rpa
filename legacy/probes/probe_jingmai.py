"""Dump Jingmai child windows / UIA / gap screenshots. No send."""
from __future__ import annotations

from legacy.paths import ROOT

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

from legacy.ui.windows import WinInfo, _minimize_siblings, _process_name, _rect, _text, foreground, restore_if_needed, user32

kernel32 = ctypes.windll.user32
GA_ROOT = 2
GW_CHILD = 5
GW_HWNDNEXT = 2
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E

EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def child_windows(parent: int) -> list[WinInfo]:
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
    title = _text(user32.GetWindowTextW, hwnd, 512)
    class_name = _text(user32.GetClassNameW, hwnd, 256)
    return hwnd, title, class_name


def dump_uia(root_hwnd: int, out: Path) -> None:
    import uiautomation as auto

    ctrl = auto.ControlFromHandle(root_hwnd)
    lines: list[str] = []

    def walk(c, depth: int = 0) -> None:
        if depth > 8:
            return
        try:
            name = (c.Name or "")[:80]
            ctype = c.ControlTypeName
            r = c.BoundingRectangle
            lines.append(
                f"{'  '*depth}{ctype} name={name!r} rect=({r.left},{r.top},{r.right},{r.bottom})"
            )
        except Exception as e:
            lines.append(f"{'  '*depth}<err {e}>")
            return
        if ctype in ("EditControl", "DocumentControl", "ComboBoxControl"):
            try:
                vp = c.GetValuePattern()
                if vp:
                    lines.append(f"{'  '*depth}  VALUE={vp.Value!r}")
            except Exception:
                pass
        try:
            children = c.GetChildren()
        except Exception:
            return
        for ch in children[:40]:
            walk(ch, depth + 1)

    walk(ctrl)
    out.write_text("\n".join(lines), encoding="utf-8")


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
    print(f"win hwnd={win.hwnd} {win.left},{win.top} {win.width}x{win.height} {win.title}")

    kids = child_windows(win.hwnd)
    print(f"children={len(kids)}")
    for k in sorted(kids, key=lambda w: (w.top, w.left)):
        if k.width < 8 or k.height < 8:
            continue
        vis = "vis" if k.visible else "hid"
        print(
            f"  [{vis}] {k.hwnd} {k.class_name:28} {k.width:4}x{k.height:<4} "
            f"({k.left},{k.top})-({k.right},{k.bottom}) {k.title!r}"
        )

    dump_uia(win.hwnd, artifacts / "jm-uia.txt")
    print("wrote artifacts/jm-uia.txt")

    # Gap between CEF chat and 常用语 pane, plus bottom of chat.
    crops = {
        "jm-gap.png": (346, 600, 1058, 700),
        "jm-chat-bot.png": (346, 520, 1058, 670),
        "jm-send-bar.png": (346, 980, 1058, 1078),
        "jm-lower-top.png": (346, 650, 1058, 780),
    }
    for name, box in crops.items():
        ImageGrab.grab(bbox=box).save(artifacts / name)
        print(f"shot {name} {box}")

    # Probe WindowFromPoint along center-x of chat pane.
    cx = 700
    print("point probes x=700:")
    for y in range(560, 1070, 20):
        hwnd, title, cls = window_from_point(cx, y)
        print(f"  y={y:4} hwnd={hwnd} class={cls} title={title!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

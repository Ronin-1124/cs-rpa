"""Save small previews of Jingmai UI and dump children. Never send."""
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


def save_small(src_box, dest: Path, size) -> None:
    im = ImageGrab.grab(bbox=src_box)
    im.resize(size).save(dest)
    print(f"saved {dest.name} from {src_box} -> {size}")


def row_colors(box, rows=12, cols=16) -> None:
    im = ImageGrab.grab(bbox=box).resize((cols, rows))
    pix = im.load()
    print(f"colormap {box}:")
    for y in range(rows):
        cells = []
        for x in range(cols):
            r, g, b = pix[x, y][:3]
            if r > 220 and g > 220 and b > 220:
                cells.append("W")
            elif r > 200 and g < 140 and b < 80:
                cells.append("O")
            elif r < 50 and g < 50 and b < 50:
                cells.append("#")
            elif r > 180 and g > 180 and b < 120:
                cells.append("Y")
            elif b > r + 40 and b > g + 20:
                cells.append("B")
            elif g > r + 20 and g > b:
                cells.append("G")
            elif r > 160 and g > 160 and b > 160:
                cells.append(".")
            else:
                cells.append("*")
        print(" " + "".join(cells))


def main() -> int:
    artifacts = Path(__file__).resolve().parent / "artifacts"
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.4)

    print(f"hwnd={win.hwnd} {win.title}")
    print("=== children ===")
    for k in sorted(children(win.hwnd), key=lambda w: (w.top, w.left)):
        if k.width < 8 or k.height < 8:
            continue
        vis = "VIS" if k.visible else "hid"
        print(
            f"  {vis} {k.hwnd} {k.class_name:32} {k.width:4}x{k.height:<4} "
            f"({k.left},{k.top})-({k.right},{k.bottom}) {k.title[:40]!r}"
        )

    save_small((0, 0, 1919, 1079), artifacts / "jm-v-full.jpg", (480, 270))
    save_small((346, 500, 1058, 1077), artifacts / "jm-v-pane.jpg", (356, 288))
    save_small((346, 620, 1058, 680), artifacts / "jm-v-bar.jpg", (356, 30))
    save_small((346, 180, 1058, 670), artifacts / "jm-v-chat.jpg", (356, 240))
    save_small((346, 669, 1058, 1077), artifacts / "jm-v-lower.jpg", (356, 204))
    # also png originals of small crops
    ImageGrab.grab(bbox=(346, 620, 1058, 680)).save(artifacts / "jm-v-bar.png")
    ImageGrab.grab(bbox=(346, 669, 1058, 900)).save(artifacts / "jm-v-lower-top.png")
    ImageGrab.grab(bbox=(800, 980, 1058, 1077)).save(artifacts / "jm-v-send.png")

    print("chat")
    row_colors((346, 180, 1058, 630), 10, 20)
    print("toolbar")
    row_colors((346, 620, 1058, 680), 6, 24)
    print("lower")
    row_colors((346, 669, 1058, 1077), 12, 20)
    print("send area")
    row_colors((800, 980, 1058, 1077), 6, 16)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

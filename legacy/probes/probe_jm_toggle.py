"""Collapse Jingmai 常用语, then paste draft. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import time

from PIL import ImageGrab, ImageStat

from legacy.ui.windows import (
    SW_RESTORE,
    restore_if_needed,
    set_clipboard_text,
    user32,
    _minimize_siblings,
)

VK_ESCAPE = 0x1B
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


def esc() -> None:
    user32.keybd_event(VK_ESCAPE, 0, 0, 0)
    user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.06)


def paste_ctrl_v() -> None:
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.02)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def orange_bbox(box=(346, 620, 1058, 680), thresh=None) -> tuple[int, tuple[int, int, int, int] | None]:
    im = ImageGrab.grab(bbox=box)
    pix = im.load()
    w, h = im.size
    xs: list[int] = []
    ys: list[int] = []
    n = 0
    for y in range(h):
        for x in range(w):
            r, g, b = pix[x, y][:3]
            if r > 200 and 70 < g < 190 and b < 90:
                n += 1
                xs.append(x)
                ys.append(y)
    if not xs:
        return 0, None
    return n, (min(xs), min(ys), max(xs), max(ys))


def pane_hash(box=(346, 669, 1058, 1040)) -> tuple:
    im = ImageGrab.grab(bbox=box)
    st = ImageStat.Stat(im)
    ext = im.convert("L").getextrema()
    return (round(sum(st.mean), 2), int(ext[0]), int(ext[1]), im.size[0] * im.size[1])


def nonwhite(box) -> int:
    im = ImageGrab.grab(bbox=box)
    n = 0
    for px in im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata():
        r, g, b = px[:3]
        if r < 245 or g < 245 or b < 245:
            n += 1
    return n


def main() -> int:
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)

    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.45)
    for _ in range(2):
        esc()

    import uiautomation as auto

    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-tog-before.png")
    n, bb = orange_bbox()
    print(f"toolbar orange={n} bbox={bb}")
    print(f"pane hash={pane_hash()} nonwhite={nonwhite((346, 669, 1058, 1040))}")

    # If 常用语 is selected, click its orange icon (or left of toolbar).
    if n > 20 and bb is not None:
        ox = 346 + (bb[0] + bb[2]) // 2
        oy = 620 + (bb[1] + bb[3]) // 2
        print(f"click orange 常用语 icon ({ox},{oy})")
        auto.Click(ox, oy)
        time.sleep(0.55)
    else:
        print("no orange; click toolbar-left (396,649) anyway")
        auto.Click(396, 649)
        time.sleep(0.55)

    n2, bb2 = orange_bbox()
    print(f"after toggle orange={n2} bbox={bb2}")
    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-tog-after.png")
    ImageGrab.grab(bbox=(346, 620, 1058, 680)).save(artifacts / "jm-tog-toolbar.png")
    print(f"pane hash={pane_hash()} nonwhite={nonwhite((346, 669, 1058, 1040))}")

    if n2 > 20 and bb2 is not None:
        # Still selected: click again (toggle) at a few toolbar xs.
        for x in (370, 396, 430, 470, 520, 580):
            auto.Click(x, 649)
            time.sleep(0.4)
            n3, bb3 = orange_bbox()
            print(f"  click toolbar x={x} orange={n3} bbox={bb3}")
            if n3 < 20:
                n2, bb2 = n3, bb3
                break
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-tog-after2.png")

    draft = "[草稿未发送] 咚咚填充1239"
    set_clipboard_text(draft)
    time.sleep(0.1)

    before = pane_hash()
    spots = [(420, 720), (500, 780), (700, 820), (500, 900), (700, 960)]
    hit = None
    for x, y in spots:
        auto.Click(x, y)
        time.sleep(0.12)
        auto.Click(x, y)
        time.sleep(0.18)
        paste_ctrl_v()
        time.sleep(0.4)
        after = pane_hash()
        nw = nonwhite((346, 669, 1058, 1040))
        changed = after != before
        print(f"paste ({x},{y}) hash={after} nonwhite={nw} changed={changed}")
        ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / f"jm-tog-paste-{x}-{y}.png")
        if changed:
            hit = (x, y)
            break
        before = after

    ImageGrab.grab(bbox=(0, 0, 1919, 1079)).save(artifacts / "jm-tog-full.png")
    print(f"hit={hit} draft={draft}")
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

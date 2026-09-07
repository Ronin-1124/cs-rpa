"""Jingmai: dump UIA at compose points, pixel-diff paste. Never send."""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageGrab, ImageStat

from ui.windows import (
    SW_RESTORE,
    WinInfo,
    _minimize_siblings,
    _process_name,
    _rect,
    _text,
    click_abs,
    restore_if_needed,
    set_clipboard_text,
    user32,
)

VK_ESCAPE = 0x1B
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


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


def hash_box(box) -> tuple[int, int, int]:
    im = ImageGrab.grab(bbox=box)
    st = ImageStat.Stat(im)
    extrema = im.convert("L").getextrema()
    return (int(sum(st.mean)), int(extrema[0]), int(extrema[1]))


def describe_box(path: Path, box) -> None:
    im = ImageGrab.grab(bbox=box)
    im.save(path)
    w, h = im.size
    pix = im.load()
    orange = 0
    dark = 0
    nonwhite = 0
    for y in range(h):
        for x in range(w):
            r, g, b = pix[x, y][:3]
            if r > 200 and 80 < g < 180 and b < 80:
                orange += 1
            if r < 80 and g < 80 and b < 80:
                dark += 1
            if r < 245 or g < 245 or b < 245:
                nonwhite += 1
    print(f"  {path.name} {w}x{h} orange={orange} dark={dark} nonwhite={nonwhite}")


def dump_point_uia(x: int, y: int) -> None:
    import uiautomation as auto

    c = auto.ControlFromPoint(x, y)
    if c is None:
        print(f"  UIA ({x},{y}): None")
        return
    try:
        r = c.BoundingRectangle
        rect = f"({r.left},{r.top})-({r.right},{r.bottom})"
    except Exception:
        rect = "?"
    print(
        f"  UIA ({x},{y}): type={c.ControlTypeName} name={c.Name!r:.80} "
        f"cls={c.ClassName!r} auto={c.AutomationId!r} rect={rect} "
        f"focusable={c.IsKeyboardFocusable} hwnd={c.NativeWindowHandle}"
    )
    p = c.GetParentControl()
    depth = 0
    while p is not None and depth < 6:
        try:
            print(
                f"    parent{depth}: type={p.ControlTypeName} name={p.Name!r:.60} "
                f"cls={p.ClassName!r} hwnd={p.NativeWindowHandle}"
            )
        except Exception as e:
            print(f"    parent{depth}: err {e}")
            break
        p = p.GetParentControl()
        depth += 1
    try:
        kids = c.GetChildren()
        print(f"    children={len(kids)}")
        for k in kids[:12]:
            print(
                f"      {k.ControlTypeName} name={k.Name!r:.50} "
                f"cls={k.ClassName!r} hwnd={k.NativeWindowHandle}"
            )
    except Exception as e:
        print(f"    children err {e}")


def process_windows(pid: int) -> list[WinInfo]:
    found: list[WinInfo] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if int(wpid.value) != pid:
            return True
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

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return found


def main() -> int:
    artifacts = Path(__file__).resolve().parent / "artifacts"
    artifacts.mkdir(exist_ok=True)

    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    user32.ShowWindow(win.hwnd, SW_RESTORE)
    user32.SetForegroundWindow(win.hwnd)
    time.sleep(0.5)
    for _ in range(2):
        esc()

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(win.hwnd, ctypes.byref(pid))
    print(f"jingmai hwnd={win.hwnd} pid={pid.value} rect=({win.left},{win.top})-({win.right},{win.bottom})")

    print("=== process top-level windows ===")
    for w in sorted(process_windows(int(pid.value)), key=lambda x: (x.top, x.left)):
        if w.width < 4 or w.height < 4:
            continue
        vis = "VIS" if w.visible else "hid"
        print(
            f"  {vis} {w.hwnd} {w.class_name:28} {w.width:4}x{w.height:<4} "
            f"({w.left},{w.top})-({w.right},{w.bottom}) {w.title[:40]!r}"
        )

    describe_box(artifacts / "jm-diff-full.png", (0, 0, 1919, 1079))
    describe_box(artifacts / "jm-diff-pane.png", (346, 500, 1058, 1077))
    describe_box(artifacts / "jm-diff-toolbar.png", (346, 620, 1058, 680))

    points = [
        (396, 649, "toolbar-left"),
        (500, 650, "toolbar-mid"),
        (700, 610, "cef-bot"),
        (420, 700, "pane-top-l"),
        (700, 700, "pane-top-m"),
        (420, 760, "pane-y760"),
        (500, 820, "pane-y820"),
        (700, 850, "pane-y850"),
        (420, 920, "pane-y920"),
        (900, 1040, "near-send"),
        (500, 1040, "bot-left"),
    ]
    print("=== UIA ControlFromPoint ===")
    for x, y, name in points:
        print(f"-- {name}")
        dump_point_uia(x, y)

    import uiautomation as auto

    print("=== UIA search Edit/Document/ComboBox ===")
    root = auto.ControlFromHandle(win.hwnd)
    found_n = 0

    def walk(c, depth: int = 0) -> None:
        nonlocal found_n
        if depth > 12 or found_n > 40:
            return
        try:
            t = c.ControlTypeName
            name = c.Name or ""
            if t in (
                "EditControl",
                "DocumentControl",
                "ComboBoxControl",
                "TextControl",
            ) or "输入" in name or "粘贴" in name or "发送" in name:
                r = c.BoundingRectangle
                print(
                    f"  d{depth} {t} name={name!r:.60} cls={c.ClassName!r} "
                    f"rect=({r.left},{r.top})-({r.right},{r.bottom}) "
                    f"focusable={c.IsKeyboardFocusable} hwnd={c.NativeWindowHandle}"
                )
                found_n += 1
        except Exception:
            return
        try:
            for ch in c.GetChildren():
                walk(ch, depth + 1)
        except Exception:
            return

    walk(root)
    print(f"matched {found_n}")

    # Pixel-diff paste at a few spots. Never Enter.
    pane = (346, 669, 1058, 1040)  # exclude 发送 row
    draft = "[草稿未发送] 咚咚填充1239"
    set_clipboard_text(draft)
    time.sleep(0.1)

    spots = [
        (420, 700),
        (500, 760),
        (500, 820),
        (700, 850),
        (420, 900),
        (700, 610),
        (396, 649),
    ]
    print("=== pixel-diff paste ===")
    before = hash_box(pane)
    print(f"baseline pane hash={before}")
    for x, y in spots:
        auto.Click(x, y)
        time.sleep(0.15)
        auto.Click(x, y)
        time.sleep(0.15)
        paste_ctrl_v()
        time.sleep(0.35)
        after = hash_box(pane)
        changed = after != before
        print(f"  click ({x},{y}) hash={after} changed={changed}")
        if changed:
            ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / f"jm-hit-{x}-{y}.png")
            print("  HIT saved")
            describe_box(artifacts / "jm-diff-hit.png", (346, 500, 1058, 1077))
            break
        before = after

    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-diff-after.png")
    describe_box(artifacts / "jm-diff-after.png", (346, 500, 1058, 1077))
    print("not sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

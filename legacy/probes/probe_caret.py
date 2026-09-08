"""Dump GUI thread focus/caret after clicking Jingmai compose. No send."""
from __future__ import annotations

from legacy.paths import ROOT

import ctypes
import time
from ctypes import wintypes

from PIL import ImageGrab

from legacy.ui.windows import _minimize_siblings, _text, click_abs, foreground, restore_if_needed, user32


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


def dump_gti(label: str, hwnd: int) -> None:
    gti = GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(GUITHREADINFO)
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    ok = user32.GetGUIThreadInfo(tid, ctypes.byref(gti))
    focus = int(gti.hwndFocus) if gti.hwndFocus else 0
    caret = int(gti.hwndCaret) if gti.hwndCaret else 0
    fg = int(user32.GetForegroundWindow())
    print(
        f"{label} ok={ok} fg={fg}({_text(user32.GetWindowTextW, fg, 80)!r}) "
        f"active={int(gti.hwndActive) if gti.hwndActive else 0} "
        f"focus={focus}({_text(user32.GetClassNameW, focus, 80)!r}) "
        f"caret={caret} rc=({gti.rcCaret.left},{gti.rcCaret.top})-"
        f"({gti.rcCaret.right},{gti.rcCaret.bottom}) flags={gti.flags}"
    )


def main() -> int:
    win = restore_if_needed("jdm_dd_workbench", "咚咚融合工作台")
    if win is None:
        print("jingmai not found")
        return 1
    _minimize_siblings(win)
    time.sleep(0.2)
    foreground(win, settle_s=0.5)
    dump_gti("after-fg", win.hwnd)

    spots = [
        ("cef-bot", 700, 610),
        ("toolbar", 700, 649),
        ("pane-top", 420, 700),
        ("pane-mid", 700, 850),
        ("pane-low", 700, 980),
        ("send-left", 500, 1040),
    ]
    artifacts = ROOT / "artifacts"
    for name, x, y in spots:
        click_abs(x, y, settle_s=0.25)
        dump_gti(f"click {name} ({x},{y})", win.hwnd)
        pt = wintypes.POINT(x, y)
        h = int(user32.WindowFromPoint(pt))
        print(f"  WindowFromPoint hwnd={h} class={_text(user32.GetClassNameW, h, 80)!r}")

    ImageGrab.grab(bbox=(346, 500, 1058, 1077)).save(artifacts / "jm-caret.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Enumerate Qianniu child HWNDs + ControlFromPoint. Never send."""
from __future__ import annotations

import ctypes
from ctypes import wintypes


from legacy.ui.windows import find_window

user32 = ctypes.windll.user32
EnumChildProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def _text(fn, hwnd, size):
    buf = ctypes.create_unicode_buffer(size)
    fn(hwnd, buf, size)
    return buf.value


def children(parent: int) -> list[tuple]:
    found = []

    def cb(hwnd, _lp):
        title = _text(user32.GetWindowTextW, hwnd, 256)
        cls = _text(user32.GetClassNameW, hwnd, 256)
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        vis = bool(user32.IsWindowVisible(hwnd))
        found.append((int(hwnd), vis, r.right - r.left, r.bottom - r.top, r.left, r.top, cls, title))
        return True

    user32.EnumChildWindows(parent, EnumChildProc(cb), 0)
    return found


def main() -> None:
    chat = find_window("AliWorkbench", "接待中心", visible_only=False, min_size=0)
    print(f"chat={chat}")
    if chat is None:
        return
    kids = children(chat.hwnd)
    kids.sort(key=lambda k: -(k[2] * k[3]))
    print(f"children={len(kids)}")
    for k in kids[:40]:
        flag = "vis" if k[1] else "hid"
        print(f"  {flag} hwnd={k[0]} {k[2]}x{k[3]} ({k[4]},{k[5]}) cls={k[6]!r} title={k[7]!r}")

    import uiautomation as auto

    print("\n=== ControlFromPoint grid ===")
    seen = set()
    ys = list(range(chat.top + 80, chat.bottom - 40, 40))
    xs = list(range(chat.left + 40, chat.left + min(500, chat.width // 3), 50))
    xs += list(range(chat.left + chat.width // 3, chat.left + int(chat.width * 0.7), 80))
    for y in ys:
        for x in xs:
            try:
                c = auto.ControlFromPoint(x, y)
            except Exception:
                continue
            if c is None:
                continue
            key = (getattr(c, "ClassName", None), c.Name, c.ControlTypeName)
            if key in seen:
                continue
            seen.add(key)
            rect = c.BoundingRectangle
            print(
                f"  ({x},{y}) [{c.ControlTypeName}] cls={c.ClassName!r} name={(c.Name or '')[:80]!r} "
                f"{rect.left},{rect.top}-{rect.right},{rect.bottom}"
            )


if __name__ == "__main__":
    main()

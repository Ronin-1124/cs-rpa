"""Dump Qianniu 接待中心 after notify click. Read-only: never fill, never send."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ui.windows import find_notify, find_window, foreground, list_windows  # noqa: E402

ART = ROOT / "artifacts"


def main() -> None:
    import ctypes
    import uiautomation as auto
    from PIL import ImageGrab

    user32 = ctypes.windll.user32

    print("=== relevant windows ===")
    for w in list_windows():
        t = w.title or ""
        if any(k in t for k in ("消息", "接待", "千牛", "工作台")) or w.process in ("AliWorkbench",):
            if w.width < 40 and w.height < 40:
                continue
            flag = "vis" if w.visible else "hid"
            print(f"[{flag}] {w.process:16} hwnd={w.hwnd} {w.width}x{w.height} ({w.left},{w.top}) {t[:80]}")

    n = find_notify(title_equals="消息提醒")
    print("notify=", n)
    if n:
        print(f"notify vis={n.visible} {n.left},{n.top}-{n.right},{n.bottom} {n.width}x{n.height}")
        if n.visible and n.width > 20:
            ImageGrab.grab(bbox=(n.left, n.top, n.right, n.bottom)).save(ART / "qn-notify-small.png")
            print("saved qn-notify-small.png")

    chat = find_window("AliWorkbench", "接待中心", True, 200)
    print("chat=", chat)
    if chat is None:
        return

    # Bring 接待中心 to front without restore (keep maximize).
    foreground(chat, restore=False)

    # Child HWNDs
    wins = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def cb(hwnd, lp):
        if user32.IsWindowVisible(hwnd) or True:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buf, 256)
            tbuf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, tbuf, 256)
            r = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            vis = bool(user32.IsWindowVisible(hwnd))
            wins.append((hwnd, buf.value, tbuf.value, r.left, r.top, r.right, r.bottom, vis))
        return True

    user32.EnumChildWindows(chat.hwnd, cb, 0)
    print(f"\n=== child hwnds of 接待中心 ({len(wins)}) ===")
    for hwnd, cls, title, l, t, r, b, vis in wins[:40]:
        flag = "vis" if vis else "hid"
        print(f"  [{flag}] hwnd={hwnd} {r-l}x{b-t} ({l},{t}) cls={cls!r} title={title[:60]!r}")

    # UIA of 接待中心
    print("\n=== UIA walk 接待中心 ===")
    ctrl = auto.ControlFromHandle(chat.hwnd)
    print(f"root type={ctrl.ControlTypeName} cls={ctrl.ClassName!r} name={ctrl.Name!r}")

    def walk(c, d):
        if d > 5:
            return
        name = (c.Name or "").strip()
        val = ""
        try:
            vp = c.GetValuePattern()
            if vp:
                val = (vp.Value or "")[:80]
        except Exception:
            pass
        rect = c.BoundingRectangle
        print(
            f"{'  '*d}[{c.ControlTypeName}] cls={c.ClassName!r} name={name[:80]!r} val={val!r} "
            f"{rect.left},{rect.top}-{rect.right},{rect.bottom}"
        )
        for ch in c.GetChildren()[:25]:
            walk(ch, d + 1)

    walk(ctrl, 0)

    # Crops of left list / chat / compose
    left_box = (chat.left + 8, chat.top + 80, chat.left + min(380, chat.width // 4), chat.bottom - 20)
    chat_box = (
        chat.left + min(380, chat.width // 4),
        chat.top + 90,
        chat.right - 80,
        chat.bottom - 180,
    )
    compose_box = (
        chat.left + min(380, chat.width // 4),
        chat.bottom - 180,
        chat.right - 80,
        chat.bottom - 20,
    )
    ImageGrab.grab(bbox=left_box).save(ART / "qn-sess-left.png")
    ImageGrab.grab(bbox=chat_box).save(ART / "qn-sess-chat.png")
    ImageGrab.grab(bbox=compose_box).save(ART / "qn-sess-compose.png")
    ImageGrab.grab(bbox=(chat.left, chat.top, min(chat.left + 900, chat.right), min(chat.top + 200, chat.bottom))).save(
        ART / "qn-sess-top.png"
    )
    print("saved session crops")

    print("\n=== ControlFromPoint left panel ===")
    seen = set()
    for y in range(left_box[1], left_box[3], 28):
        for x in range(left_box[0] + 20, left_box[2], 60):
            try:
                c = auto.ControlFromPoint(x, y)
            except Exception:
                continue
            if c is None:
                continue
            key = (c.ControlTypeName, c.Name, getattr(c, "ClassName", None))
            if key in seen:
                continue
            seen.add(key)
            r = c.BoundingRectangle
            print(
                f"  ({x},{y}) [{c.ControlTypeName}] cls={c.ClassName!r} "
                f"name={(c.Name or '')[:100]!r} {r.left},{r.top}-{r.right},{r.bottom}"
            )

    print("\n=== ControlFromPoint chat ===")
    seen = set()
    for y in range(chat_box[1], chat_box[3], 40):
        for x in range(chat_box[0] + 40, chat_box[2], 120):
            try:
                c = auto.ControlFromPoint(x, y)
            except Exception:
                continue
            if c is None:
                continue
            key = (c.ControlTypeName, c.Name, getattr(c, "ClassName", None))
            if key in seen:
                continue
            seen.add(key)
            r = c.BoundingRectangle
            print(
                f"  ({x},{y}) [{c.ControlTypeName}] cls={c.ClassName!r} "
                f"name={(c.Name or '')[:100]!r} {r.left},{r.top}-{r.right},{r.bottom}"
            )


if __name__ == "__main__":
    main()

"""Dump Qianniu 消息提醒 UIA + screenshot. Click first item to open session. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import ctypes


from legacy.ui.windows import find_notify, find_window, foreground, list_windows  # noqa: E402

ART = ROOT / "artifacts"
user32 = ctypes.windll.user32


def main() -> None:
    import uiautomation as auto
    from PIL import ImageGrab

    print("=== windows ===")
    for w in list_windows():
        if w.title and ("消息" in w.title or "接待" in w.title or "千牛" in w.title or "Ali" in (w.process or "")):
            flag = "vis" if w.visible else "hid"
            print(f"[{flag}] {w.process:16} hwnd={w.hwnd} {w.width}x{w.height} ({w.left},{w.top}) {w.title}")

    n = find_notify(title_equals="消息提醒")
    print("notify=", n)
    if n is None:
        return
    print(f"vis={n.visible} {n.left},{n.top}-{n.right},{n.bottom}")
    ImageGrab.grab(bbox=(n.left, n.top, n.right, n.bottom)).save(ART / "qn-notify-now.png")

    ctrl = auto.ControlFromHandle(n.hwnd)
    print(f"root type={ctrl.ControlTypeName} cls={ctrl.ClassName!r} name={ctrl.Name!r}")

    def walk(c, d, path):
        if d > 8:
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
            f"{'  '*d}[{c.ControlTypeName}] cls={c.ClassName!r} name={name[:100]!r} val={val!r} "
            f"{rect.left},{rect.top}-{rect.right},{rect.bottom}"
        )
        for i, ch in enumerate(c.GetChildren()[:40]):
            walk(ch, d + 1, path + [i])

    walk(ctrl, 0, [])

    print("\n=== ControlFromPoint on notify ===")
    seen = set()
    for y in range(n.top + 8, n.bottom - 4, 12):
        for x in range(n.left + 8, n.right - 4, 20):
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
            print(f"  ({x},{y}) [{c.ControlTypeName}] cls={c.ClassName!r} name={(c.Name or '')[:120]!r} {r.left},{r.top}-{r.right},{r.bottom}")

    # Click the first message row (below title bar).
    cx = n.left + n.width // 2
    cy = n.top + 48
    print(f"click notify item at {cx},{cy}")
    user32.SetCursorPos(cx, cy)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)

    import time
    time.sleep(0.8)
    chat = find_window("AliWorkbench", "接待中心", True, 200)
    if chat:
        foreground(chat, restore=False)
        ImageGrab.grab(bbox=(chat.left, chat.top, chat.right, chat.bottom)).save(ART / "qn-after-notify-click-full.png")
        ImageGrab.grab(
            bbox=(chat.left, chat.top + 70, chat.left + min(420, chat.width // 3), chat.bottom)
        ).save(ART / "qn-after-notify-click-left.png")
        ImageGrab.grab(
            bbox=(
                chat.left + min(420, chat.width // 3),
                chat.top + 80,
                chat.right - 80,
                chat.bottom - 160,
            )
        ).save(ART / "qn-after-notify-click-chat.png")
        print("saved after-click shots")


if __name__ == "__main__":
    main()

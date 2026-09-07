"""Read-only probe of Qianniu 接待中心: windows, UIA, session list, chat. Never send."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ui.windows import (  # noqa: E402
    find_notify,
    find_window,
    foreground,
    list_windows,
    maximize,
    screenshot_region,
    win_from_hwnd,
)

ARTIFACTS = ROOT / "artifacts"


def dump_ctrl(ctrl, depth: int, lines: list[str], max_depth: int = 8, max_children: int = 40) -> None:
    try:
        name = (ctrl.Name or "")[:120]
        cls = (getattr(ctrl, "ClassName", None) or "")[:80]
        ctype = (getattr(ctrl, "ControlTypeName", None) or "")[:40]
        rect = ctrl.BoundingRectangle
        auto_id = (getattr(ctrl, "AutomationId", None) or "")[:60]
        value = ""
        try:
            vp = ctrl.GetValuePattern()
            if vp:
                value = (vp.Value or "")[:80]
        except Exception:
            pass
        loc = f"{rect.left},{rect.top}-{rect.right},{rect.bottom}" if rect else "?"
        extra = f" id={auto_id}" if auto_id else ""
        if value:
            extra += f" val={value!r}"
        lines.append(f"{'  '*depth}[{ctype}] cls={cls!r} name={name!r} {loc}{extra}")
        if depth >= max_depth:
            return
        children = ctrl.GetChildren()
        for i, child in enumerate(children[:max_children]):
            dump_ctrl(child, depth + 1, lines, max_depth, max_children)
        if len(children) > max_children:
            lines.append(f"{'  '*(depth+1)}... +{len(children)-max_children} more")
    except Exception as e:
        lines.append(f"{'  '*depth}ERR {e}")


def collect_text(ctrl, depth: int, acc: list[tuple], max_depth: int = 10) -> None:
    try:
        name = (ctrl.Name or "").strip()
        cls = (getattr(ctrl, "ClassName", None) or "")
        ctype = (getattr(ctrl, "ControlTypeName", None) or "")
        rect = ctrl.BoundingRectangle
        if name and rect and rect.width() > 0 and rect.height() > 0:
            acc.append((rect.left, rect.top, rect.right, rect.bottom, ctype, cls, name[:200]))
        if depth >= max_depth:
            return
        for child in ctrl.GetChildren()[:60]:
            collect_text(child, depth + 1, acc, max_depth)
    except Exception:
        return


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    print("=== AliWorkbench / 千牛 windows ===")
    wins = list_windows()
    qn = [
        w
        for w in wins
        if w.process.lower() in ("aliworkbench", "qianniu", "aliapp")
        or "接待" in w.title
        or "千牛" in w.title
        or "消息提醒" in w.title
        or "AliWorkbench" in (w.class_name or "")
        or "Qt5152" in (w.class_name or "")
    ]
    qn.sort(key=lambda w: (not w.visible, -(w.width * w.height)))
    for w in qn:
        vis = "vis" if w.visible else "hid"
        print(
            f"  {vis} hwnd={w.hwnd} {w.width}x{w.height} ({w.left},{w.top})-({w.right},{w.bottom}) "
            f"proc={w.process!r} cls={w.class_name!r} title={w.title!r}"
        )

    chat = find_window("AliWorkbench", "接待中心", visible_only=False, min_size=0)
    if chat is None:
        chat = find_window("AliWorkbench", "千牛", visible_only=False, min_size=0)
    print(f"\nchat window: {chat}")
    notify = find_notify(title_equals="消息提醒")
    print(f"notify window: {notify}")

    if chat is None:
        print("NO 接待中心 window")
        return

    maximize(chat)
    foreground(chat, settle_s=0.5, restore=False)
    chat = win_from_hwnd(chat.hwnd) or chat
    print(f"after max: {chat.width}x{chat.height} ({chat.left},{chat.top})-({chat.right},{chat.bottom})")

    from PIL import ImageGrab

    ImageGrab.grab(bbox=(chat.left, chat.top, chat.right, chat.bottom)).save(
        ARTIFACTS / "qn-full.png"
    )
    screenshot_region(chat, 0.394, 0.926, ARTIFACTS / "qn-compose.png")
    # left session list strip
    ImageGrab.grab(
        bbox=(chat.left, chat.top + 40, chat.left + min(420, chat.width // 3), chat.bottom)
    ).save(ARTIFACTS / "qn-left.png")
    # chat center
    ImageGrab.grab(
        bbox=(
            chat.left + min(420, chat.width // 3),
            chat.top + 80,
            chat.left + int(chat.width * 0.72),
            chat.bottom - 80,
        )
    ).save(ARTIFACTS / "qn-chat.png")
    print("screenshots: qn-full.png qn-left.png qn-chat.png qn-compose.png")

    import uiautomation as auto

    ctrl = auto.ControlFromHandle(chat.hwnd)
    print(f"root UIA: type={ctrl.ControlTypeName} name={ctrl.Name!r} cls={ctrl.ClassName!r}")
    lines: list[str] = []
    dump_ctrl(ctrl, 0, lines, max_depth=7, max_children=50)
    tree_path = ARTIFACTS / "qn-uia.txt"
    tree_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"UIA tree lines={len(lines)} -> {tree_path}")
    for line in lines[:80]:
        print(line)

    texts: list[tuple] = []
    collect_text(ctrl, 0, texts, max_depth=12)
    print(f"\n=== named visible nodes ({len(texts)}) ===")
    # left third likely sessions
    left_max = chat.left + int(chat.width * 0.28)
    sessions = [t for t in texts if t[0] < left_max and t[1] > chat.top + 40]
    print(f"left-column names: {len(sessions)}")
    for t in sessions[:40]:
        print(f"  L {t[0]},{t[1]} {t[4]} {t[5]!r} {t[6]!r}")

    mid_lo = chat.left + int(chat.width * 0.25)
    mid_hi = chat.left + int(chat.width * 0.75)
    chat_names = [t for t in texts if mid_lo <= t[0] <= mid_hi and t[1] > chat.top + 60]
    print(f"\nmid-column names: {len(chat_names)}")
    for t in chat_names[:50]:
        print(f"  C {t[0]},{t[1]} {t[4]} {t[5]!r} {t[6]!r}")

    if notify is not None:
        print(f"\n=== notify {notify.title} vis={notify.visible} {notify.width}x{notify.height} ===")
        nctrl = auto.ControlFromHandle(notify.hwnd)
        nlines: list[str] = []
        dump_ctrl(nctrl, 0, nlines, max_depth=8, max_children=30)
        (ARTIFACTS / "qn-notify-uia.txt").write_text("\n".join(nlines), encoding="utf-8")
        for line in nlines[:60]:
            print(line)
        if notify.visible and notify.width > 10:
            ImageGrab.grab(bbox=(notify.left, notify.top, notify.right, notify.bottom)).save(
                ARTIFACTS / "qn-notify.png"
            )


if __name__ == "__main__":
    main()

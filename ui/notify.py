from __future__ import annotations

from dataclasses import dataclass

from ui.windows import WinInfo, find_notify


@dataclass(frozen=True)
class NotifyMessage:
    platform: str
    buyer_id: str
    text: str
    raw_title: str
    visible: bool


def _uia_names(title: str) -> list[str]:
    try:
        import uiautomation as auto
    except Exception:
        return []
    win = auto.WindowControl(searchDepth=1, Name=title)
    if not win.Exists(0, 0):
        # startswith match for jingmai "新消息提醒 - ..."
        desktop = auto.GetRootControl()
        win = None
        for child in desktop.GetChildren():
            name = child.Name or ""
            if name == title or name.startswith(title):
                win = child
                break
        if win is None:
            return []
    names: list[str] = []

    def walk(ctrl, depth: int) -> None:
        if depth > 6:
            return
        name = (ctrl.Name or "").strip()
        if name and name not in names:
            names.append(name)
        try:
            children = ctrl.GetChildren()
        except Exception:
            return
        for child in children[:20]:
            walk(child, depth + 1)

    walk(win, 0)
    return names


def parse_notify(platform: str, notify_title: str, win: WinInfo | None) -> NotifyMessage | None:
    if win is None:
        win = find_notify(
            title_equals=notify_title if platform == "qianniu" else None,
            title_startswith=notify_title if platform == "jingmai" else None,
        )
    if win is None:
        return None
    names = _uia_names(win.title or notify_title)
    # Drop chrome titles, keep the first two informative strings.
    skip = {notify_title, win.title, "", "消息提醒", "新消息提醒"}
    info = [n for n in names if n not in skip and not n.startswith("新消息提醒")]
    buyer = info[0] if info else "unknown"
    text = info[1] if len(info) > 1 else (info[0] if info else "")
    if not text:
        return None
    return NotifyMessage(
        platform=platform,
        buyer_id=buyer[:80],
        text=text[:500],
        raw_title=win.title,
        visible=win.visible,
    )

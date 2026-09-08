"""Read-only watch: Qianniu 消息提醒 + session list. Never fill, never send.

Prints only DONE / FAILED (for the host monitor). Details go to artifacts/qn-watch.jsonl.
"""
from __future__ import annotations

from legacy.paths import ROOT

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path


from legacy.ui.notify import parse_notify  # noqa: E402
from legacy.ui.windows import find_notify, find_window

ARTIFACTS = ROOT / "artifacts"
LOG = ARTIFACTS / "qn-watch.jsonl"


def log(event: dict) -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def left_hash(chat) -> str | None:
    try:
        from PIL import ImageGrab

        box = (
            chat.left,
            chat.top + 70,
            chat.left + min(420, max(180, chat.width // 4)),
            chat.bottom - 20,
        )
        img = ImageGrab.grab(bbox=box)
        return hashlib.sha1(img.tobytes()).hexdigest()[:16]
    except Exception:
        return None


def dump_on_hit(chat, notify, reason: str) -> Path:
    from PIL import ImageGrab
    import uiautomation as auto

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    full = ARTIFACTS / f"qn-inbound-{stamp}-full.png"
    left = ARTIFACTS / f"qn-inbound-{stamp}-left.png"
    ImageGrab.grab(bbox=(chat.left, chat.top, chat.right, chat.bottom)).save(full)
    ImageGrab.grab(
        bbox=(chat.left, chat.top + 70, chat.left + min(420, chat.width // 3), chat.bottom)
    ).save(left)
    notice = parse_notify("qianniu", "消息提醒", notify)
    names = []
    if notify is not None:
        try:
            ctrl = auto.ControlFromHandle(notify.hwnd)
            nshot = ARTIFACTS / f"qn-inbound-{stamp}-notify.png"
            if notify.visible and notify.width > 20:
                ImageGrab.grab(bbox=(notify.left, notify.top, notify.right, notify.bottom)).save(nshot)

            def walk(c, d):
                if d > 7:
                    return
                n = (c.Name or "").strip()
                if n:
                    names.append(n)
                for ch in c.GetChildren()[:30]:
                    walk(ch, d + 1)

            walk(ctrl, 0)
        except Exception as e:
            names.append(f"ERR {e}")
    payload = {
        "event": "inbound",
        "reason": reason,
        "notify_title": notify.title if notify else None,
        "notify_visible": bool(notify and notify.visible),
        "notify_names": names,
        "parsed": None
        if notice is None
        else {"buyer": notice.buyer_id, "text": notice.text, "visible": notice.visible},
        "full": str(full),
        "left": str(left),
    }
    log(payload)
    return full


def main() -> int:
    deadline = time.time() + 3600
    last_hash = None
    while time.time() < deadline:
        chat = find_window("AliWorkbench", "接待中心", visible_only=False, min_size=0)
        notify = find_notify(title_equals="消息提醒")
        if chat is None:
            time.sleep(1.2)
            continue
        h = left_hash(chat)
        notify_vis = bool(notify and notify.visible and notify.width > 20 and notify.height > 20)
        if last_hash is None:
            last_hash = h
            log(
                {
                    "event": "armed",
                    "chat": chat.title,
                    "notify_visible": notify_vis,
                    "left_hash": h,
                }
            )
        # Hash of the left strip is noisy (工作台/接待中心 overlap). Only fire on the popup.
        if notify_vis:
            dump_on_hit(chat, notify, "notify_visible")
            print("DONE notify_visible", flush=True)
            return 0
        time.sleep(1.0)
    print("FAILED timeout_no_inbound", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

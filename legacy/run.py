"""Run Jingmai (web) + Qianniu watchers. Fill and send replies when auto_send."""
from __future__ import annotations

from legacy.paths import ROOT

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

if __name__ == "__main__" and ("--mock" in sys.argv or "--offline" in sys.argv or os.environ.get("CS_RPA_MOCK") == "1"):
    raise SystemExit("The old UIA mock runner is retired. Run: python -m mock_dongdong demo")

from legacy.config import load_config


from legacy.openclaw_client import OpenClawClient  # noqa: E402
from legacy.ui.windows import (  # noqa: E402
    SW_SHOW,
    click_abs,
    fill_input,
    find_window,
    foreground,
    list_windows,
    user32,
)

ART = ROOT / "artifacts"
LOG = ART / "events.jsonl"
EDGE_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def log(event: dict) -> None:
    ART.mkdir(exist_ok=True)
    event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(json.dumps(event, ensure_ascii=False), flush=True)


def ping_bridge(url: str) -> None:
    import urllib.request

    req = urllib.request.Request(
        url.rstrip("/") + "/jd/inbound",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=3)
    except Exception as exc:
        # 400 missing text means the server is up.
        if "400" not in str(exc) and "missing text" not in str(exc).lower():
            log(
                {
                    "event": "warn",
                    "bridge": url,
                    "error": str(exc),
                    "note": "OpenClaw unreachable; hang will see chats but cannot fill replies",
                }
            )


def open_dongdong() -> None:
    from legacy.ui.web_jingmai import (
        _find_live_dongdong_edge,
        dongdong_missing_hint,
        mock_mode,
        mock_workbench_url,
    )

    live = _find_live_dongdong_edge()
    if live is not None:
        log({"event": "ready", "platform": "jingmai", "hwnd": live.hwnd, "title": live.title, "mock": mock_mode()})
        return
    exe = next((p for p in EDGE_CANDIDATES if Path(p).is_file()), None)
    if exe is None:
        log({"event": "error", "platform": "jingmai", "error": "msedge.exe not found"})
        return
    url = mock_workbench_url() if mock_mode() else "https://dongdong.jd.com/"
    subprocess.Popen([exe, "--new-window", url])
    log({"event": "opening", "platform": "jingmai", "url": url, "mock": mock_mode()})
    deadline = time.time() + 25
    while time.time() < deadline:
        live = _find_live_dongdong_edge()
        if live is not None:
            log({"event": "ready", "platform": "jingmai", "hwnd": live.hwnd, "title": live.title, "mock": mock_mode()})
            return
        time.sleep(1.0)
    titles = [w.title for w in list_windows() if w.visible and w.process == "msedge"]
    log({"event": "warn", "platform": "jingmai", "error": dongdong_missing_hint(), "edge": titles, "mock": mock_mode()})


def _qn_chat() -> object | None:
    return find_window("AliWorkbench", "接待中心", visible_only=False, min_size=0)


def fill_qianniu_box(cfg: dict, text: str, screenshot_path: Path | None) -> None:
    from PIL import ImageGrab

    chat = _qn_chat()
    if chat is None:
        raise RuntimeError("接待中心 window not found")
    if not chat.visible:
        user32.ShowWindow(chat.hwnd, SW_SHOW)
        chat = _qn_chat() or chat
    rel = cfg["qianniu"]["input_rel"]
    fill_input(
        chat,
        float(rel["x"]),
        float(rel["y"]),
        text,
        auto_send=bool(cfg.get("auto_send")),
        minimize_siblings=False,
        restore_previous=True,
    )
    if screenshot_path is not None:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        box = (
            chat.left + int(chat.width * 0.22),
            chat.top + int(chat.height * 0.72),
            chat.right - 40,
            chat.bottom - 8,
        )
        ImageGrab.grab(bbox=box).save(screenshot_path)


def ocr_qianniu_notify(n) -> tuple[str, str, Path | None]:
    from PIL import ImageGrab
    from legacy.ui.ocr import ocr_lines, parse_qianniu_notify_lines

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shot = ART / f"qn-inbound-{stamp}-notify.png"
    img = ImageGrab.grab(bbox=(n.left, n.top, n.right, n.bottom))
    img.save(shot)
    buyer, text = parse_qianniu_notify_lines(ocr_lines(img))
    return buyer, text, shot


def ocr_qianniu_chat() -> tuple[str, str]:
    from PIL import ImageGrab
    from legacy.ui.ocr import compact_ocr, ocr_lines, parse_qianniu_notify_lines

    chat = _qn_chat()
    if chat is None:
        return "unknown", ""
    box = (
        chat.left + min(380, max(220, chat.width // 4)),
        chat.top + 90,
        chat.right - 80,
        chat.bottom - 160,
    )
    img = ImageGrab.grab(bbox=box)
    img.save(ART / "qn-chat-ocr.png")
    lines = ocr_lines(img)
    buyer, text = parse_qianniu_notify_lines(lines)
    if not text and lines:
        text = compact_ocr(" ".join(lines[-3:]))
    return buyer, text


def ask_and_fill_qianniu(cfg: dict, client: OpenClawClient, buyer: str, text: str) -> None:
    from legacy.ui.ocr import looks_like_customer_text

    if not looks_like_customer_text(text or ""):
        log({"event": "skip", "platform": "qianniu", "buyer": buyer, "reason": "ocr text not a customer question", "text": text})
        return
    log({"event": "ask", "platform": "qianniu", "buyer": buyer, "text": text})
    result = client.ask("qianniu", buyer or "unknown", text)
    if result.skip or not result.reply:
        log({"event": "skip", "platform": "qianniu", "buyer": buyer, "reason": "NO_REPLY"})
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fill_shot = ART / f"fill-qianniu-{stamp}.png"
    fill_qianniu_box(cfg, result.reply, fill_shot)
    log(
        {
            "event": "filled",
            "platform": "qianniu",
            "buyer": buyer,
            "reply": result.reply,
            "sent": bool(cfg.get("auto_send")),
            "screenshot": str(fill_shot),
        }
    )


class QianniuWalk:
    """Open 待回 once, then visit rows top-to-bottom. One click per session."""

    def __init__(self) -> None:
        self.slots: list[dict] = []
        self.i = 0
        self.daihui_done = False
        self.done = False

    def _left_shot(self, chat):
        from PIL import ImageGrab

        left0 = chat.left + 8
        top0 = chat.top + 78
        box = (left0, top0, chat.left + min(360, max(260, chat.width // 5)), chat.bottom - 40)
        img = ImageGrab.grab(bbox=box)
        img.save(ART / "qn-sess-left-now.png")
        return img, left0, top0

    def _show(self):
        chat = _qn_chat()
        if chat is None:
            return None
        user32.ShowWindow(chat.hwnd, SW_SHOW)
        foreground(chat, restore=False, keep_topmost=False)
        time.sleep(0.45)
        return _qn_chat() or chat

    def arm(self) -> None:
        from legacy.ui.ocr import find_daihui_click, parse_qianniu_session_rows

        chat = self._show()
        if chat is None:
            return
        img, left0, top0 = self._left_shot(chat)
        daihui = find_daihui_click(img, left0, top0)
        if daihui is not None and not self.daihui_done:
            click_abs(daihui[0], daihui[1], settle_s=0.7)
            self.daihui_done = True
            img, left0, top0 = self._left_shot(chat)
        raw = parse_qianniu_session_rows(img, left0, top0)
        raw.sort(key=lambda r: r["click_y"])
        slots: list[dict] = []
        for row in raw:
            if slots and abs(row["click_y"] - slots[-1]["click_y"]) < 28:
                continue
            slots.append(row)
        self.slots = slots
        self.i = 0
        log(
            {
                "event": "armed",
                "platform": "qianniu",
                "sessions": len(slots),
                "buyers": [s["buyer"] for s in slots[:20]],
            }
        )

    def step(self, cfg: dict, client: OpenClawClient) -> None:
        from legacy.ui.ocr import looks_like_customer_text

        if self.done:
            return
        if not self.slots:
            self.arm()
            if not self.slots:
                return
        if self.i >= len(self.slots):
            log({"event": "walk_done", "platform": "qianniu", "sessions": len(self.slots)})
            self.done = True
            return
        chat = self._show()
        if chat is None:
            return
        row = self.slots[self.i]
        idx = self.i
        self.i += 1
        log(
            {
                "event": "open_session",
                "platform": "qianniu",
                "index": idx,
                "of": len(self.slots),
                "buyer": row["buyer"],
            }
        )
        click_abs(row["click_x"], row["click_y"], settle_s=0.9)
        time.sleep(0.5)
        buyer, text = ocr_qianniu_chat()
        if not looks_like_customer_text(text):
            text = row.get("preview") or text
        if not buyer or buyer == "unknown":
            buyer = row["buyer"]
        log(
            {
                "event": "inbound",
                "platform": "qianniu",
                "buyer": buyer,
                "text": text,
                "source": "walk",
                "index": idx,
            }
        )
        ask_and_fill_qianniu(cfg, client, buyer, text)


_jm_missing_log = 0.0
_jm_empty_log = 0.0


class JingmaiWalk:
    """Process existing threads, then poll new inbound; sending follows config."""

    def __init__(self, pending_only: bool = False) -> None:
        self.pending_only = pending_only
        self.slots: list = []
        self.i = 0
        self.armed = False
        self.done = False
        self.source = "live"
        self.seen: set = set()

    def _list_rows(self, win, steal_focus: bool = False):
        from legacy.ui.web_jingmai import (
            ensure_live_inbox,
            list_live_sessions,
            open_recent_contacts,
        )

        ensure_live_inbox(win)
        try:
            rows = list_live_sessions(win, steal_focus=steal_focus)
        except RuntimeError:
            rows = []
        source = "live"
        if not rows:
            open_recent_contacts(win)
            try:
                rows = list_live_sessions(win, steal_focus=steal_focus)
            except RuntimeError:
                rows = []
            source = "recent"
        return rows, source

    def arm(self) -> None:
        from legacy.ui.web_jingmai import (
            _find_live_dongdong_edge,
            _prepare_live_edge,
            dongdong_missing_hint,
            mock_mode,
        )

        win = _find_live_dongdong_edge()
        if win is None:
            now = time.time()
            global _jm_missing_log
            if now - _jm_missing_log >= 60:
                log({"event": "wait", "platform": "jingmai", "error": dongdong_missing_hint(), "mock": mock_mode()})
                _jm_missing_log = now
            return
        win = _prepare_live_edge(steal_focus=True)
        rows, source = self._list_rows(win, steal_focus=True)
        if self.pending_only:
            rows = [row for row in rows if int(row.unread or 0) > 0]
        self.slots = list(rows)
        self.i = 0
        self.source = source
        self.armed = True
        log(
            {
                "event": "armed",
                "platform": "jingmai",
                "source": source,
                "sessions": len(self.slots),
                "buyers": [r.buyer_id for r in self.slots[:20]],
                "note": "walk existing threads then watch live inbox",
                "mock": mock_mode(),
            }
        )

    def _fill_one(self, cfg: dict, client: OpenClawClient, row, index: int, of: int, source: str) -> None:
        from legacy.ui.web_jingmai import (
            _fill_live_edge,
            _prepare_live_edge,
            _thread_turns,
            open_live_session,
            read_live_messages,
        )

        key = ("jm", row.buyer_id, row.preview)
        self.seen.add(key)
        log(
            {
                "event": "open_session",
                "platform": "jingmai",
                "source": source,
                "index": index,
                "of": of,
                "buyer": row.buyer_id,
            }
        )
        try:
            win = _prepare_live_edge(steal_focus=True)
            open_live_session(win, row.buyer_id, row)
        except Exception as exc:
            log({"event": "error", "platform": "jingmai", "buyer": row.buyer_id, "error": str(exc)})
            return
        time.sleep(0.5)
        msgs = read_live_messages(win) or read_live_messages(win)
        if not msgs:
            time.sleep(0.6)
            msgs = read_live_messages(win) or []
        turns = _thread_turns(msgs, row.preview)
        log(
            {
                "event": "inbound",
                "platform": "jingmai",
                "buyer": row.buyer_id,
                "text": row.preview,
                "unread": row.unread,
                "messages": len(msgs),
            }
        )
        if not any(t[0] == "customer" for t in turns):
            log({"event": "skip", "platform": "jingmai", "buyer": row.buyer_id, "reason": "no customer text"})
            return
        try:
            result = client.ask_thread("jingmai", row.buyer_id, turns)
        except Exception as exc:
            log({"event": "error", "platform": "jingmai", "buyer": row.buyer_id, "error": str(exc)})
            return
        if result.skip or not result.reply:
            log({"event": "skip", "platform": "jingmai", "buyer": row.buyer_id, "reason": "NO_REPLY"})
            return
        text = result.reply.strip()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shot = ART / f"fill-jingmai-{stamp}.png"
        send = bool(cfg.get("auto_send"))
        _fill_live_edge(win, text, shot, send=send)
        log(
            {
                "event": "filled",
                "platform": "jingmai",
                "buyer": row.buyer_id,
                "reply": text,
                "sent": send,
                "screenshot": str(shot),
            }
        )

    def watch_new(self, cfg: dict, client: OpenClawClient) -> None:
        from legacy.ui.web_jingmai import (
            _find_live_dongdong_edge,
            ensure_live_inbox,
            list_live_sessions,
            live_group_counts,
        )

        global _jm_empty_log
        win = _find_live_dongdong_edge()
        if win is None:
            return
        ensure_live_inbox(win)
        try:
            rows = list_live_sessions(win, steal_focus=False)
        except RuntimeError:
            return
        pending = []
        for row in rows:
            key = ("jm", row.buyer_id, row.preview)
            if int(row.unread or 0) <= 0:
                continue
            if key in self.seen:
                continue
            pending.append(row)
        if not pending:
            now = time.time()
            if now - _jm_empty_log >= 60:
                log(
                    {
                        "event": "idle",
                        "platform": "jingmai",
                        "sessions": len(rows),
                        "groups": live_group_counts(win),
                    }
                )
                _jm_empty_log = now
            return
        pending.sort(key=lambda r: (-int(r.unread or 0), r.buyer_id))
        self._fill_one(cfg, client, pending[0], 0, len(pending), "live")

    def step(self, cfg: dict, client: OpenClawClient) -> None:
        if not self.armed:
            self.arm()
            return
        if self.done:
            self.watch_new(cfg, client)
            return
        if self.i >= len(self.slots):
            log({"event": "walk_done", "platform": "jingmai", "sessions": len(self.slots), "source": self.source})
            self.done = True
            return
        row = self.slots[self.i]
        idx = self.i
        self.i += 1
        self._fill_one(cfg, client, row, idx, len(self.slots), self.source)


def handle_jingmai(cfg: dict, client: OpenClawClient, walk: JingmaiWalk) -> None:
    walk.step(cfg, client)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["jingmai", "qianniu", "all"], default="all")
    parser.add_argument(
        "--restore",
        action="store_true",
        help="bring 咚咚工作站 back to live inbox (tab 0); use after a person clicked the UI",
    )
    args = parser.parse_args()
    if args.restore:
        from legacy.ui.web_jingmai import restore_live_inbox

        return restore_live_inbox()
    platforms = ["jingmai", "qianniu"] if args.platform == "all" else [args.platform]

    cfg = load_config()
    ping_bridge(str(cfg.get("bridge_base") or "http://192.168.2.252:18080"))
    client = OpenClawClient(cfg["bridge_base"], int(cfg.get("bridge_timeout_sec") or 180))
    qn_walk = QianniuWalk()
    jm_walk = JingmaiWalk()
    from legacy.ui.web_jingmai import _find_live_dongdong_edge, dongdong_missing_hint, mock_mode

    if "jingmai" in platforms:
        live = _find_live_dongdong_edge()
        if live is None and not mock_mode():
            open_dongdong()
            live = _find_live_dongdong_edge()
        if live is not None:
            log(
                {
                    "event": "ready",
                    "platform": "jingmai",
                    "hwnd": live.hwnd,
                    "title": live.title,
                    "focus": False,
                    "mock": mock_mode(),
                }
            )
        else:
            log(
                {
                    "event": "ready",
                    "platform": "jingmai",
                    "note": dongdong_missing_hint() + "; watcher will pick it up",
                    "mock": mock_mode(),
                }
            )
    if "qianniu" in platforms:
        chat = find_window("AliWorkbench", "接待中心", visible_only=False, min_size=0)
        if chat is not None:
            log({"event": "ready", "platform": "qianniu", "hwnd": chat.hwnd, "title": chat.title, "focus": False})
    log(
        {
            "event": "watching",
            "auto_send": bool(cfg.get("auto_send")),
            "platforms": platforms,
            "mock": mock_mode(),
        }
    )
    print(
        f"watching {', '.join(platforms)}; walks existing threads then watches new; "
        f"auto_send={bool(cfg.get('auto_send'))}; if a person clicks 咚咚, run python -m legacy.ui.web_jingmai restore"
        + ("; mock window only" if mock_mode() else ""),
        flush=True,
    )
    tick = 0
    while True:
        if "qianniu" in platforms and tick % 4 == 1:
            try:
                qn_walk.step(cfg, client)
            except Exception as exc:
                log({"event": "error", "platform": "qianniu", "error": f"walk {exc}"})
        jm_every = 1 if platforms == ["jingmai"] else 6
        if "jingmai" in platforms and tick % jm_every == 0:
            try:
                handle_jingmai(cfg, client, jm_walk)
            except Exception as exc:
                log({"event": "error", "platform": "jingmai", "error": str(exc)})
        tick += 1
        time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())

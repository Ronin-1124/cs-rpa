"""Watch Qianniu / Jingmai notify popups, ask OpenClaw, fill input. Never send."""
from __future__ import annotations

from legacy.paths import ROOT

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from legacy.config import load_config

from legacy.adapters.base import PlatformAdapter
from legacy.adapters.jingmai import make_adapter as make_jingmai
from legacy.adapters.qianniu import make_adapter as make_qianniu
from legacy.openclaw_client import OpenClawClient
from legacy.ui.windows import list_windows


def log(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(json.dumps(event, ensure_ascii=False), flush=True)


def dump_windows() -> None:
    for w in list_windows():
        if w.title:
            flag = "vis" if w.visible else "hid"
            print(f"[{flag}] {w.process:20} {w.width:4}x{w.height:<4} {w.title}")


def handle_once(
    adapter: PlatformAdapter,
    client: OpenClawClient,
    cfg: dict,
    artifacts: Path,
    seen: set[tuple[str, str, str]],
    buyer: str | None,
    text: str | None,
) -> bool:
    if buyer and text:
        msg_platform, buyer_id, body = adapter.spec.key, buyer, text
        visible = True
    else:
        notice = adapter.read_notify()
        if notice is None or not notice.text:
            return False
        msg_platform, buyer_id, body = notice.platform, notice.buyer_id, notice.text
        visible = notice.visible
        if not visible:
            return False
    key = (msg_platform, buyer_id, body)
    if key in seen:
        return False
    seen.add(key)
    log_path = artifacts / "events.jsonl"
    log(log_path, {"event": "inbound", "platform": msg_platform, "buyer": buyer_id, "text": body})
    result = client.ask(msg_platform, buyer_id, body)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shot = artifacts / f"fill-{msg_platform}-{stamp}.png"
    adapter.fill_draft(result.reply, screenshot_path=shot)
    log(
        log_path,
        {
            "event": "filled",
            "platform": msg_platform,
            "buyer": buyer_id,
            "reply": result.reply,
            "sent": False,
            "screenshot": str(shot),
        },
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-windows", action="store_true")
    parser.add_argument("--once", action="store_true", help="process one inbound (or --ask) then exit")
    parser.add_argument("--platform", choices=["qianniu", "jingmai"], default=None)
    parser.add_argument("--buyer", default=None)
    parser.add_argument("--ask", default=None, help="skip notify, use this customer text")
    args = parser.parse_args()

    if args.dump_windows:
        dump_windows()
        return 0

    cfg = load_config()

    artifacts = ROOT / (cfg.get("log_dir") or "artifacts")
    client = OpenClawClient(cfg["bridge_base"], int(cfg.get("bridge_timeout_sec") or 180))
    adapters = {
        "qianniu": make_qianniu(cfg),
        "jingmai": make_jingmai(cfg),
    }
    if args.platform:
        adapters = {args.platform: adapters[args.platform]}

    seen: set[tuple[str, str, str]] = set()
    if args.once:
        if args.ask and not args.platform:
            print("--ask requires --platform", file=sys.stderr)
            return 2
        if args.ask:
            adapter = adapters[args.platform]
            handle_once(adapter, client, cfg, artifacts, seen, args.buyer or "manual", args.ask)
            return 0
        for adapter in adapters.values():
            if handle_once(adapter, client, cfg, artifacts, seen, None, None):
                return 0
        print("no visible notify message")
        return 1

    print(f"watching notify popups; auto_send={bool(cfg.get('auto_send'))}", flush=True)
    poll = max(200, int(cfg.get("poll_ms") or 800)) / 1000.0
    while True:
        for adapter in adapters.values():
            try:
                handle_once(adapter, client, cfg, artifacts, seen, None, None)
            except Exception as exc:
                log(artifacts / "events.jsonl", {"event": "error", "platform": adapter.spec.key, "error": str(exc)})
        time.sleep(poll)


if __name__ == "__main__":
    raise SystemExit(main())

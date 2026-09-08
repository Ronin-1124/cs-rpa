"""Fill a chat input box. Never sends.

  python -m legacy.fill_input jingmai
  python -m legacy.fill_input qianniu --text "自定义草稿"
  python -m legacy.fill_input jingmai --from-openclaw --buyer dry-run --ask "能开增值税专票吗？"
"""
from __future__ import annotations

from legacy.paths import ROOT

import argparse
import sys
from datetime import datetime

from legacy.config import load_config

from legacy.adapters.jingmai import make_adapter as make_jingmai
from legacy.adapters.qianniu import make_adapter as make_qianniu
from legacy.openclaw_client import OpenClawClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=["qianniu", "jingmai"])
    parser.add_argument("--text", default=None, help="draft to paste; default from config.dry_fill_text")
    parser.add_argument("--from-openclaw", action="store_true")
    parser.add_argument("--buyer", default="dry-run")
    parser.add_argument("--ask", default=None, help="customer message sent to OpenClaw")
    args = parser.parse_args()

    cfg = load_config()

    adapter = make_qianniu(cfg) if args.platform == "qianniu" else make_jingmai(cfg)
    text = args.text or cfg.get("dry_fill_text") or "[草稿·未发送]"
    if args.from_openclaw:
        if not args.ask:
            print("--from-openclaw requires --ask", file=sys.stderr)
            return 2
        client = OpenClawClient(cfg["bridge_base"], int(cfg.get("bridge_timeout_sec") or 180))
        result = client.ask(args.platform, args.buyer, args.ask)
        text = result.reply
        print(f"openclaw reply: {text}")

    artifacts = ROOT / (cfg.get("log_dir") or "artifacts")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shot = artifacts / f"fill-{args.platform}-{stamp}.png"
    try:
        win = adapter.fill_draft(text, screenshot_path=shot)
    except RuntimeError as exc:
        msg = str(exc)
        if "needs login" in msg:
            print(msg)
            print(f"screenshot: {shot}")
            print(f"sent={bool(cfg.get('auto_send'))}")
            return 3
        raise
    print(f"filled {args.platform} hwnd={win.hwnd} title={win.title}")
    print(f"draft: {text}")
    print(f"screenshot: {shot}")
    print(f"sent={bool(cfg.get('auto_send'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

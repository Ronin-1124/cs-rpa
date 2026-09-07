#!/usr/bin/env python3
"""Simulate JD/Taobao customer-service inbound -> OpenClaw -> reply.

This is a local proof-of-concept. Production would replace the /simulate
endpoint with official JD Dongdong / Taobao Qianniu API callbacks, then
call the matching send-message API with the returned reply.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OPENCLAW = os.environ.get(
    "OPENCLAW_BIN",
    str(Path.home() / ".nvm/versions/node/v24.18.0/bin/openclaw"),
)
HOST = os.environ.get("CS_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CS_BRIDGE_PORT", "18080"))

CS_PROMPT = """有一位{platform}顾客在店铺客服窗口咨询。
顾客ID: {buyer_id}
消息: {text}

按 SOUL.md、knowledge/style.md 的回复原则；guide.md 中待实现的功能不代表已经可用：
- 正常温和，一两句。不要过硬（「没货。」「转人工。」），也不要谄媚。
- 先看本对话已有客服回复，跟着那个语气。
- 库存和交期必须有当前依据，不能套用话术猜测。
- 技术问题只根据 knowledge/radxa-docs/docs；没有就「这个我这边看不了，转人工处理。」
- 常规问答和标准报价使用已确认、符合适用条件的话术；特殊价格、批量采购、优惠、复杂售后需要人工处理。
- 定制需求先询问缺失的必要信息，不重复询问已确认内容。没有工具成功结果，不声称已通知或转交人工。
- 已结束或无需再回：只输出 NO_REPLY
- 禁止：亲、宝子、建议您关注、设置到货通知、请稍等帮您转接

只输出发给顾客的正文。"""


def ask_openclaw(platform: str, buyer_id: str, text: str) -> str:
    session_key = f"agent:main:cs:{platform}:{buyer_id}"
    prompt = CS_PROMPT.format(platform=platform, buyer_id=buyer_id, text=text)
    proc = subprocess.run(
        [
            OPENCLAW,
            "agent",
            "--agent",
            "main",
            "--timeout",
            "120",
            "--session-key",
            session_key,
            "--json",
            "--message",
            prompt,
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": str(Path(OPENCLAW).parent) + ":" + os.environ.get("PATH", "")},
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
    data = json.loads(proc.stdout[proc.stdout.find("{") :])
    payloads = data.get("result", {}).get("payloads") or []
    if payloads and payloads[0].get("text"):
        return payloads[0]["text"]
    return data.get("result", {}).get("meta", {}).get("finalAssistantVisibleText") or ""


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, body: dict) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        platform = str(payload.get("platform") or "unknown")
        buyer_id = str(payload.get("buyerId") or payload.get("buyer_id") or "anonymous")
        text = str(payload.get("text") or payload.get("message") or "").strip()
        if self.path not in {"/simulate", "/jd/inbound", "/taobao/inbound"}:
            self._json(404, {"ok": False, "error": "unknown path"})
            return
        if self.path == "/jd/inbound":
            platform = "京东"
        elif self.path == "/taobao/inbound":
            platform = "淘宝"
        if not text:
            self._json(400, {"ok": False, "error": "missing text"})
            return
        try:
            reply = ask_openclaw(platform, buyer_id, text)
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"ok": False, "error": str(exc)})
            return
        self._json(200, {"ok": True, "platform": platform, "buyerId": buyer_id, "reply": reply})

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"mock CS bridge listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import mimetypes
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mock_dongdong import DEFAULT_HOST, DEFAULT_PORT
from mock_dongdong.store import Store

WEB = Path(__file__).resolve().parent / "web"


class Handler(BaseHTTPRequestHandler):
    store: Store

    def log_message(self, fmt, *args):
        if args and str(args[0]).startswith("POST"):
            super().log_message(fmt, *args)

    def _respond(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _json(self, status, payload):
        self._respond(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path
        try:
            if path == "/api/health":
                return self._json(200, {"ok": True, "version": 2, "offline": True})
            if path == "/api/state":
                return self._json(200, self.store.snapshot())
            if path == "/api/users":
                return self._json(200, {"users": self.store.list_users()})
            if path in ("/api/chat", "/api/messages"):
                token = (query.get("user") or query.get("buyer_id") or [""])[0]
                # Local latency fixture reproduces asynchronous conversation loading.
                time.sleep(0.25)
                return self._json(200, {"ok": True, **self.store.get_chat(token)})
            if path == "/api/templates":
                templates = WEB.parent.parent / "offline-templates.json"
                return self._json(200, {"cases": json.loads(templates.read_text(encoding="utf-8"))})
            name = {"/": "workbench.html", "/workbench": "workbench.html", "/control": "control.html"}.get(path, path.lstrip("/"))
            target = (WEB / name).resolve()
            if not target.is_relative_to(WEB.resolve()) or not target.is_file():
                return self._json(404, {"ok": False, "error": "not found"})
            mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._respond(200, target.read_bytes(), mime + "; charset=utf-8")
        except KeyError as exc:
            self._json(404, {"ok": False, "error": str(exc)})

    def do_POST(self):
        if self.headers.get("Origin") and self.headers["Origin"] != "http://" + self.headers.get("Host", ""):
            return self._json(403, {"ok": False, "error": "same-origin requests only"})
        try:
            size = int(self.headers.get("Content-Length") or 0)
            if size < 0 or size > 65536:
                raise ValueError("request too large")
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("JSON object required")
            token = str(body.get("buyer_id") or body.get("user") or "")
            path = urlparse(self.path).path
            if path == "/api/users":
                out = {"user": self.store.create_user(body.get("name"))}
            elif path == "/api/send":
                out = self.store.send_customer(token, str(body.get("text") or ""))
            elif path == "/api/read":
                self.store.mark_read(token, str(body.get("through") or ""))
                out = {}
            elif path == "/api/agent-send":
                out = self.store.agent_send(token, str(body.get("text") or ""), str(body.get("request_id") or ""))
            elif path == "/api/reset":
                self.store.reset()
                out = {}
            else:
                return self._json(404, {"ok": False, "error": "not found"})
            self._json(200, {"ok": True, **out})
        except KeyError as exc:
            self._json(404, {"ok": False, "error": str(exc)})
        except (ValueError, TypeError) as exc:
            self._json(400, {"ok": False, "error": str(exc)})


def serve(host=DEFAULT_HOST, port=DEFAULT_PORT, open_browser=False):
    Handler.store = Store()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dongdong replica v2: http://127.0.0.1:{port}/workbench", flush=True)
    print(f"Customer controls: http://127.0.0.1:{port}/control", flush=True)
    if open_browser:
        print("Open the workbench URL in Codex's in-app browser.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

from mock_dongdong import DEFAULT_PORT


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Local observation-based Dongdong replica v2")
    parser.add_argument("--url", default=f"http://127.0.0.1:{DEFAULT_PORT}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    create = sub.add_parser("create")
    create.add_argument("--name", default="")
    send = sub.add_parser("send")
    send.add_argument("user")
    send.add_argument("text", nargs="+")
    chat = sub.add_parser("chat")
    chat.add_argument("user")
    sub.add_parser("users")
    sub.add_parser("sessions")
    sub.add_parser("reset", help="replace v2 data with synthetic history fixtures")
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        from mock_dongdong.server import serve as start_server
        start_server(args.host, args.port)
        return 0
    body = None
    if args.cmd == "create":
        path, body = "/api/users", {"name":args.name}
    elif args.cmd == "send":
        path, body = "/api/send", {"user":args.user,"text":" ".join(args.text)}
    elif args.cmd == "reset":
        path, body = "/api/reset", {}
    elif args.cmd == "chat":
        path = "/api/chat?" + urllib.parse.urlencode({"user":args.user})
    else:
        path = "/api/users" if args.cmd == "users" else "/api/state"
    data = json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    request = urllib.request.Request(args.url.rstrip("/")+path,data=data,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=5) as response:
        print(json.dumps(json.load(response),ensure_ascii=False,indent=2))
    return 0

"""Isolated fixture store. Browser selection is deliberately not server state."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE_PATH = ROOT / "artifacts" / "dongdong-replica-v2.json"


def message(role: str, text: str, kind: str = "text") -> dict:
    return {"id": "s_" + uuid.uuid4().hex, "role": role, "text": text,
            "kind": kind, "ts": datetime.now().isoformat(timespec="seconds")}


class Store:
    def __init__(self, path: Path = STORE_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            self.reset()

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        data["rev"] += 1
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _session(self, data: dict, token: str) -> dict:
        for s in data["sessions"]:
            if token in (s["buyer_id"], s["user_id"]):
                return s
        raise KeyError("unknown customer")

    def snapshot(self) -> dict:
        with self._lock:
            data = self._read()
            recent = [{k: v for k, v in s.items() if k not in ("messages", "requests")}
                      for s in data["sessions"]]
            recent.sort(key=lambda s: s["updated_at"], reverse=True)
            consulting = [s for s in recent if s["in_consult"]]
            return {"version": 2, "rev": data["rev"], "users": self.list_users(),
                    "consulting": consulting, "recent": recent,
                    "groups": {"正在咨询": len(consulting), "留言": sum(not s["in_consult"] and s["unread"] > 0 for s in recent)}}

    def list_users(self) -> list[dict]:
        with self._lock:
            return [{"id": s["user_id"], "name": s["buyer_id"]} for s in self._read()["sessions"]]

    def create_user(self, name: str | None = None) -> dict:
        with self._lock:
            data = self._read()
            buyer = (name or "").strip() or "模拟顾客-" + uuid.uuid4().hex[:6]
            if any(s["buyer_id"] == buyer for s in data["sessions"]):
                raise ValueError("customer name already exists")
            if len(buyer) > 80:
                raise ValueError("customer name too long")
            user_id = "u_" + uuid.uuid4().hex[:12]
            data["sessions"].append({"buyer_id": buyer, "user_id": user_id, "unread": 0,
                "preview": "", "time": "", "updated_at": datetime.now().isoformat(),
                "in_consult": False, "messages": [], "requests": {}, "product": "测试开发板 Q8B"})
            self._write(data)
            return {"id": user_id, "name": buyer}

    def get_chat(self, token: str) -> dict:
        with self._lock:
            s = self._session(self._read(), token)
            return {k: v for k, v in s.items() if k != "requests"}

    def mark_read(self, token: str, through: str) -> None:
        with self._lock:
            data = self._read()
            s = self._session(data, token)
            ids = [m["id"] for m in s["messages"]]
            if through not in ids:
                return
            after = s["messages"][ids.index(through) + 1:]
            s["unread"] = sum(m["role"] == "customer" for m in after)
            self._write(data)

    def send_customer(self, token: str, text: str) -> dict:
        return self._send(token, text, "customer")

    def agent_send(self, token: str, text: str, request_id: str) -> dict:
        if not request_id or len(request_id) > 128:
            raise ValueError("request_id required")
        return self._send(token, text, "agent", request_id)

    def _send(self, token: str, text: str, role: str, request_id: str = "") -> dict:
        text = text.strip()
        if not text or len(text) > 10000:
            raise ValueError("message must contain 1-10000 characters")
        with self._lock:
            data = self._read()
            s = self._session(data, token)
            if request_id in s["requests"]:
                previous = s["requests"][request_id]
                if previous["text"] != text:
                    raise ValueError("request_id reused for different text")
                return previous
            msg = message(role, text)
            s["messages"].append(msg)
            s["preview"] = text
            s["time"] = datetime.now().strftime("%m月%d日 %H:%M")
            s["updated_at"] = datetime.now().isoformat()
            s["in_consult"] = True
            if role == "customer":
                s["unread"] += 1
            out = {"buyer_id": s["buyer_id"], "unread": s["unread"], **msg}
            if request_id:
                s["requests"][request_id] = out
            self._write(data)
            return out

    def reset(self) -> None:
        with self._lock:
            revision = self._read()["rev"] if self.path.exists() else 0
            self._write({"rev": revision, "sessions": []})
            names = ["模拟顾客-小林", "模拟顾客-小周", "模拟顾客-开发者", "模拟顾客-采购", "模拟顾客-售后"]
            for name in names:
                self.create_user(name)
            data = self._read()
            for i, s in enumerate(data["sessions"]):
                s["time"] = "09月07日 10:30"
                s["messages"] = [message("customer", "测试开发板 Q8B", "product"),
                    message("customer", "你好，请问这款开发板配套散热器吗？"),
                    message("agent", "您好，散热器需要单独选购。"),
                    message("agent", "商品资料请查看 https://example.invalid/product/q8b"),
                    message("system", "客服撤回了一条消息", "system"),
                    message("system", "上次聊到这里", "divider"),
                    message("customer", "好的，我再确认一下。")]
                if i == 2:
                    s["messages"][0]["kind"] = "product_error"
                s["preview"] = "好的，我再确认一下。"
            self._write(data)

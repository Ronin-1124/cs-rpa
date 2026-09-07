"""Deterministic replies for the explicitly enabled local RPA demonstration."""
from __future__ import annotations

import json
from pathlib import Path

from openclaw_client import CsReply, OpenClawClient


def demo_cases() -> list[dict]:
    return json.loads(Path(__file__).with_name("offline-templates.json").read_text(encoding="utf-8"))


class OfflineReplyClient(OpenClawClient):
    def __init__(self) -> None:
        self.replies = {case["question"]: case["reply"] for case in demo_cases()}

    def ask(self, platform: str, buyer_id: str, text: str) -> CsReply:
        if platform != "jingmai":
            raise ValueError("Offline replies are limited to the Jingmai mock demo")
        reply = self.replies.get(text.strip(), "")
        return CsReply(platform, buyer_id, reply, skip=not reply)

    def ask_thread(self, platform: str, buyer_id: str, turns: list[tuple[str, str]]) -> CsReply:
        conversational = [(role, text) for role, text in turns if role in ("customer", "agent") and text.strip()]
        if not conversational or conversational[-1][0] != "customer":
            return CsReply(platform, buyer_id, "", skip=True)
        return self.ask(platform, buyer_id, conversational[-1][1])

from __future__ import annotations

from dataclasses import dataclass

import requests

NO_REPLY_MARKERS = (
    "NO_REPLY",
    "NOREPLY",
    "无需回复",
    "不必回复",
    "不需要回复",
    "无需再回",
    "不用回复",
)
DRAFT_PREFIXES = ("[草稿未发送]", "[草稿·未发送]", "草稿：")


@dataclass(frozen=True)
class CsReply:
    platform: str
    buyer_id: str
    reply: str
    skip: bool = False


def clean_reply(text: str) -> str:
    """Drop leftover draft tags so the hang loop can send the body as-is."""
    body = (text or "").strip()
    looping = True
    while looping and body:
        looping = False
        for prefix in DRAFT_PREFIXES:
            if body.startswith(prefix):
                body = body[len(prefix) :].strip()
                looping = True
    return body


def is_no_reply(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    first = t.splitlines()[0].strip().upper().replace(" ", "")
    if first in {"NO_REPLY", "NOREPLY", "[NO_REPLY]"}:
        return True
    compact = t.replace(" ", "")
    return any(m in compact for m in NO_REPLY_MARKERS) and len(t) < 40


def format_thread_prompt(buyer_id: str, turns: list[tuple[str, str]]) -> str:
    lines = [
        "【客服回复】正常温和，一两句。不要过硬也不要谄媚。只输出将发给客户的正文或 NO_REPLY。不要加草稿/未发送标记。",
        f"买家：{buyer_id}",
        "规则：",
        "1) 先看下面对话里已有客服怎么回，跟着那个语气",
        "2) 只答店铺、产品、订单、售后相关问题；库存、交期必须有当前依据，不猜测",
        "3) 技术题按文档；没有就「这个我这边看不了，转人工处理。」",
        "4) 常规业务和标准报价使用已确认且适用的话术；特殊价格、批量采购、优惠、复杂售后需要人工处理。定制需求先询问缺失的必要信息",
        "5) 已说谢谢/结束，或客服已答完且没有新问题：NO_REPLY",
        "6) 禁止亲、宝子、建议您关注、设置到货通知、请稍等帮您转接",
        "7) 不重复询问已确认信息；没有工具成功结果，不声称已通知同事或转交人工",
        "",
        "对话（从上到下，当前窗口可见记录）：",
    ]
    role_map = {"customer": "客户", "agent": "客服", "system": "系统"}
    for role, text in turns:
        label = role_map.get(role, role)
        body = (text or "").strip().replace("\r", "")
        if not body:
            continue
        lines.append(f"{label}: {body}")
    return "\n".join(lines)


class OpenClawClient:
    def __init__(self, base_url: str, timeout_sec: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def ask(self, platform: str, buyer_id: str, text: str) -> CsReply:
        path = {
            "qianniu": "/taobao/inbound",
            "taobao": "/taobao/inbound",
            "淘宝": "/taobao/inbound",
            "jingmai": "/jd/inbound",
            "jd": "/jd/inbound",
            "京东": "/jd/inbound",
        }.get(platform)
        if not path:
            raise ValueError(f"unknown platform: {platform}")
        resp = requests.post(
            self.base_url + path,
            json={"buyerId": buyer_id, "text": text},
            timeout=self.timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("error") or data)
        reply = clean_reply((data.get("reply") or "").strip())
        skip = is_no_reply(reply)
        if not reply and not skip:
            raise RuntimeError("OpenClaw returned empty reply")
        return CsReply(
            platform=str(data.get("platform") or platform),
            buyer_id=str(data.get("buyerId") or buyer_id),
            reply="" if skip else reply,
            skip=skip,
        )

    def ask_thread(self, platform: str, buyer_id: str, turns: list[tuple[str, str]]) -> CsReply:
        return self.ask(platform, buyer_id, format_thread_prompt(buyer_id, turns))

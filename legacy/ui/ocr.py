"""Windows.Media.Ocr helper. Chinese first."""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

_CJK_SPACE = re.compile(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff0-9A-Za-z？?！!，,。])")
_SPACE_CJK = re.compile(r"(?<=[0-9A-Za-z])\s+(?=[\u4e00-\u9fff])")


def compact_ocr(text: str) -> str:
    t = (text or "").replace("\u3000", " ").strip()
    t = _CJK_SPACE.sub("", t)
    t = _SPACE_CJK.sub("", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def ocr_image(img: Image.Image, lang: str = "zh-Hans-CN") -> dict:
    import winocr

    if img.mode != "RGBA":
        img = img.convert("RGBA")
    last_err = None
    for tag in (lang, "zh-Hans", "zh-CN"):
        try:
            return winocr.recognize_pil_sync(img, tag) or {}
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"ocr failed: {last_err}")


def ocr_lines(img: Image.Image) -> list[str]:
    data = ocr_image(img)
    lines = []
    for line in data.get("lines") or []:
        raw = compact_ocr(line.get("text") or "")
        if raw:
            lines.append(raw)
    if not lines:
        blob = compact_ocr(data.get("text") or "")
        if blob:
            lines = [blob]
    return lines


def ocr_path(path: Path) -> list[str]:
    return ocr_lines(Image.open(path))


def ocr_line_boxes(img: Image.Image) -> list[dict]:
    data = ocr_image(img)
    out: list[dict] = []
    for line in data.get("lines") or []:
        text = compact_ocr(line.get("text") or "")
        words = line.get("words") or []
        if not text or not words:
            continue
        rects = [w.get("bounding_rect") or {} for w in words]
        xs = [float(r.get("x") or 0) for r in rects]
        ys = [float(r.get("y") or 0) for r in rects]
        hs = [float(r.get("height") or 12) for r in rects]
        out.append(
            {
                "text": text,
                "x": min(xs),
                "y": min(ys),
                "cy": min(ys) + max(hs) / 2,
            }
        )
    return out


_CHROME = (
    "消息提醒",
    "接待中心",
    "千牛",
    "正在接待",
    "正在接",
    "全部会话",
    "全部买家",
    "待回",
    "分组",
    "留言",
    "搜索",
    "发送",
    "联系人",
    "订单号",
    "聊天记录",
    "无法接",
    "其他消息",
    "服务助手转",
    "服助李转",
    "Thought",
    "Task",
    "grok",
    "Shift",
    "Ctrl",
    "Esc",
    "Tab",
)


def _chrome_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if any(k.lower() in t.lower() for k in _CHROME):
        return True
    if re.fullmatch(r"[\d:：\s.．-]+", t):
        return True
    return False


def find_daihui_click(img: Image.Image, origin_left: int, origin_top: int) -> tuple[int, int] | None:
    """Click point for 待回 tab if OCR sees it."""
    for b in ocr_line_boxes(img):
        t = b["text"].replace(" ", "")
        if "待回" in t:
            return origin_left + int(b["x"]) + 20, origin_top + int(b["cy"])
    return None


def parse_qianniu_session_rows(img: Image.Image, origin_left: int, origin_top: int) -> list[dict]:
    """Left-list rows: buyer + preview + click point in screen coords."""
    boxes = [b for b in ocr_line_boxes(img) if b["x"] >= 70 and b["y"] >= 220]
    rows: list[dict] = []
    i = 0
    while i < len(boxes):
        b = boxes[i]
        if _chrome_line(b["text"]):
            i += 1
            continue
        buyer = b["text"][:40]
        preview = ""
        if i + 1 < len(boxes) and not _chrome_line(boxes[i + 1]["text"]):
            nxt = boxes[i + 1]["text"]
            if looks_like_customer_text(nxt) or len(nxt) >= 4:
                preview = nxt
                i += 2
            else:
                i += 1
        else:
            i += 1
        rows.append(
            {
                "buyer": buyer,
                "preview": preview,
                "click_x": origin_left + int(b["x"]) + 48,
                "click_y": origin_top + int(b["cy"]),
            }
        )
    return rows


_SKIP = {
    "消息提醒",
    "新消息提醒",
    "接待中心",
    "发送",
    "千牛工作台",
    "超时",
    "当前没有会话",
}


def looks_like_customer_text(text: str) -> bool:
    t = compact_ocr(text)
    if len(t) < 4:
        return False
    if re.search(r"[吗？?货版镜像有无]", t):
        return True
    return len(re.findall(r"[\u4e00-\u9fff]", t)) >= 6


def parse_qianniu_notify_lines(lines: list[str]) -> tuple[str, str]:
    """Return (buyer, customer_text) from 消息提醒 OCR lines."""
    cleaned = []
    for line in lines:
        if line in _SKIP:
            continue
        if "账号" in line:
            continue
        if "ronin" in line.lower() and "开发" not in line:
            continue
        if line.startswith("由服务助手") or "转交" in line:
            continue
        if re.fullmatch(r"\d{1,4}", line):
            continue
        if re.search(r"\d{4}\s*[.．]\s*\d", line):
            continue
        if re.search(r"\d{1,2}\s*[：:]\s*\d{2}", line) and len(line) < 24:
            continue
        cleaned.append(line)
    buyer = "unknown"
    text = ""
    for line in cleaned:
        if re.search(r"[吗？?货版镜像系统]", line) or len(line) >= 6:
            if not text or len(line) > len(text):
                text = line
    names = [ln for ln in cleaned if ln != text and not re.search(r"[吗？?]", ln)]
    if names:
        buyer = names[0][:40]
    if not text and cleaned:
        text = cleaned[-1]
    return buyer, text

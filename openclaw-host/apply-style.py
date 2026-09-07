#!/usr/bin/env python3
from pathlib import Path

WS = Path("/home/radxa/.openclaw/workspace")
SRC = Path("/tmp/openclaw-style")

CS_SECTION = """## Customer Service Knowledge

Follow `SOUL.md` and `knowledge/style.md`. `guide.md` describes requirements, including features not yet implemented.

Style: normal, mild. Not blunt, not flattering. Copy existing 客服 wording in the thread and `knowledge/canned/`.

Answer using confirmed product information and applicable standard business replies. Do not invent stock, prices or policy.

Special pricing, bulk discounts and complex after-sales require human review. For customization, ask for missing requirements using the confirmed business template.
Never claim a notification or handoff succeeded without a tool result.

NO_REPLY when thanks/done or already answered.

Never: 亲, 宝子, 建议您关注, 设置到货通知, 请稍等帮您转接.
"""


def replace_section(text: str, heading: str, new_section: str) -> str:
    if heading not in text:
        return text.rstrip() + "\n\n" + new_section
    start = text.index(heading)
    rest = text[start + len(heading) :]
    nxt = rest.find("\n## ")
    if nxt == -1:
        return text[:start] + new_section
    return text[:start] + new_section + rest[nxt:]


def main() -> None:
    knowledge = WS / "knowledge"
    canned = knowledge / "canned"
    canned.mkdir(parents=True, exist_ok=True)
    mapping = {
        "style.md": knowledge / "style.md",
        "guide.md": WS / "guide.md",
        "SOUL.md": WS / "SOUL.md",
        "knowledge-README.md": knowledge / "README.md",
        "canned-README.md": canned / "README.md",
    }
    for name, dest in mapping.items():
        dest.write_text((SRC / name).read_text(encoding="utf-8"), encoding="utf-8")
    agents = WS / "AGENTS.md"
    agents.write_text(
        replace_section(agents.read_text(encoding="utf-8"), "## Customer Service Knowledge", CS_SECTION),
        encoding="utf-8",
    )
    print("style applied")


if __name__ == "__main__":
    main()

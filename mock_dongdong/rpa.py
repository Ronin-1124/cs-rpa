"""DOM-only local driver. No fixture API access and no OpenClaw dependency."""
from __future__ import annotations

from urllib.parse import urlparse

from playwright.sync_api import expect

ACTIVE_ROWS = ".c_tabs-tabpane:not(.c_tabs-tab_inactive) .alluser-item:visible"
EDITOR = ".EditorContent[contenteditable=true]"
MESSAGES = "#t-chat-scroll .message"


class ReplicaRpa:
    def __init__(self, page, templates: list[dict]):
        self.page = page
        self.templates = {c["question"]: c["reply"] for c in templates}
        self.handled = set()

    def guard_local(self):
        url = urlparse(self.page.url)
        if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError("This demo only operates on a local replica")

    def open_customer(self, buyer: str, question: str | None = None):
        self.guard_local()
        self.page.locator('.c_tabs-tab[title="历史咨询"]').click()
        row = self.page.locator(ACTIVE_ROWS).filter(has=self.page.get_by_text(buyer, exact=True))
        expect(row).to_have_count(1)
        row.click()
        expect(self.page.locator(".chat-head-name > span").first).to_have_text(buyer)
        expect(self.page.locator(EDITOR)).to_be_visible()
        if question is not None:
            expect(self.page.locator(".message_left .message__content").last).to_have_text(question)

    def read_turns(self):
        return self.page.locator(MESSAGES).evaluate_all("""nodes => nodes.flatMap(node => {
            const side = node.querySelector('.message_left, .message_right');
            const text = side?.querySelector('.message__content');
            return side && text ? [{id:side.id, role:side.classList.contains('message_left') ? 'customer' : 'agent', text:text.textContent}] : [];
        })""")

    def reply_current(self):
        self.guard_local()
        buyer = self.page.locator(".chat-head-name > span").first.inner_text()
        turns = self.read_turns()
        if not turns or turns[-1]["role"] != "customer":
            return None
        latest = turns[-1]
        key = (buyer, latest["id"])
        reply = self.templates.get(latest["text"].strip())
        if not reply or key in self.handled:
            return None
        editor = self.page.locator(EDITOR)
        editor.fill(reply)
        expect(editor).to_have_text(reply)
        expect(self.page.locator(".chat-head-name > span").first).to_have_text(buyer)
        # Recheck the last message immediately before sending.
        if self.read_turns()[-1]["id"] != latest["id"]:
            editor.fill("")
            return None
        before = self.page.locator(".message_right .message__content").count()
        self.page.locator(".SendButtonGroup > .send-button").click()
        expect(self.page.locator(".message_right .message__content")).to_have_count(before + 1)
        expect(self.page.locator(".message_right .message__content").last).to_have_text(reply)
        expect(editor).to_be_empty()
        self.handled.add(key)
        return {"buyer": buyer, "question": latest["text"], "reply": reply, "message_id": latest["id"]}

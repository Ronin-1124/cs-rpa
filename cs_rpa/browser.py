"""DOM-only transport. No fixture APIs are used to read or send messages."""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright
from playwright._impl._errors import TargetClosedError

ROWS = '.c_tabs-tabpane:not(.c_tabs-tab_inactive) .alluser-item:visible'
EDITOR = '.EditorContent[contenteditable=true]'
HEADER = '.chat-head-name > span'


def comparable_text(text):
    # Contenteditable may add blank lines when Chromium turns newlines into divs.
    return re.sub(r'\n{2,}', '\n', text.replace('\r\n', '\n')).strip()


class BrowserAdapter:
    def __init__(self, config, data_dir: Path):
        self.config, self.data_dir = config, data_dir
        self.playwright = self.context = self.page = None
        self.cursor = 0
        self.confirmed_message = None

    def start(self):
        self.playwright = sync_playwright().start()
        try:
            channel = self.config['channel']
            transport = self.config['transport']
            profile = self.data_dir / 'browser' / hashlib.sha256(f"{transport}:{self.config['shop']}".encode()).hexdigest()[:16]
            self.context = self.playwright.chromium.launch_persistent_context(
                str(profile), channel=channel, headless=transport == 'mock',
                viewport={'width': 1366, 'height': 960}, timeout=20000,
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.set_default_timeout(6000)
            self.page.goto(self.config['mock_url'] if transport == 'mock' else self.config['jd_url'], wait_until='domcontentloaded', timeout=20000)
        except Exception:
            self.close()
            raise

    def guard(self):
        url = urlparse(self.page.url)
        if self.config['transport'] == 'mock':
            if url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1'):
                raise RuntimeError('模拟适配器拒绝操作非本地页面')
        elif url.scheme != 'https' or url.hostname != 'dongdong.jd.com':
            raise RuntimeError('请先在打开的浏览器中完成京东登录')

    def customers(self):
        self.guard()
        if not self.page.locator('.c_tabs-tab[title="历史咨询"]').count():
            raise RuntimeError('等待登录或客服页面加载')
        self.page.locator('.c_tabs-tab[title="历史咨询"]').click()
        items = self.page.locator(ROWS).evaluate_all("""rows => rows.map(row => ({
            name: row.querySelector('.alluser-item-name')?.textContent?.trim() || '',
            customer_key: row.getAttribute('data-user-id') || '',
            preview: row.querySelector('.alluser-item-breifdesc')?.textContent || ''
        })).filter(row => row.name)""")
        unique = {}
        for item in items:
            name = item['name']
            if name in unique:
                unique[name] = None
            else:
                item['customer_key'] = item['customer_key'] or 'name:' + name
                unique[name] = item
        items = [item for item in unique.values() if item]
        if not items:
            return []
        start = self.cursor % len(items)
        ordered = items[start:] + items[:start]
        self.cursor = (start + self.config['max_sessions']) % len(items)
        return ordered[:self.config['max_sessions']]

    def open_customer(self, name):
        self.guard()
        self.page.locator('.c_tabs-tab[title="历史咨询"]').click()
        row = self.page.locator(ROWS).filter(has=self.page.get_by_text(name, exact=True))
        expect(row).to_have_count(1)
        current = self.page.locator(HEADER).first.inner_text() if self.page.locator(HEADER).count() else ''
        if current != name:
            row.click()
        expect(self.page.locator(HEADER).first).to_have_text(name)
        expect(self.page.locator(EDITOR)).to_be_visible()
        # Header and transcript update separately; require stable message IDs.
        previous = None
        stable_since = time.monotonic()
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            messages = self.read_messages()
            ids = [m['id'] for m in messages]
            if ids != previous:
                previous, stable_since = ids, time.monotonic()
            if time.monotonic() - stable_since >= .4:
                return messages
            self.page.wait_for_timeout(100)
        raise RuntimeError('聊天记录未稳定加载')

    def read_messages(self):
        return self.page.locator('#t-chat-scroll .message').evaluate_all("""nodes => nodes.flatMap(node => {
            const side = node.querySelector('.message_left, .message_right');
            const body = side?.querySelector('.message__content');
            if (!side?.id || !body) return [];
            return [{id: side.id, role: side.classList.contains('message_left') ? 'customer' : 'agent',
                text: body.textContent, timestamp: side.querySelector('.message__time_str')?.textContent || ''}];
        })""")

    def send(self, name, source_id, reply, before_click):
        self.confirmed_message = None
        messages = self.open_customer(name)
        if not messages or messages[-1]['id'] != source_id:
            return 'stale', '网页已有新消息，本条回复已取消'
        if self.config['transport'] != 'mock':
            return 'draft', '真实网页当前提供读取与草稿审核；真实发送需完成平台验证后启用'
        editor = self.page.locator(EDITOR)
        if editor.inner_text().strip():
            return 'draft', '输入框存在未发送内容，请先处理草稿'
        editor.fill(reply)
        if comparable_text(editor.inner_text()) != comparable_text(reply):
            editor.fill('')
            return 'draft', '输入框内容与审核回复不一致，请检查页面'
        latest = self.read_messages()
        if self.page.locator(HEADER).first.inner_text() != name or not latest or latest[-1]['id'] != source_id:
            editor.fill('')
            return 'stale', '发送前会话发生变化'
        if not before_click():
            editor.fill('')
            return 'draft', '运行已暂停或会话被同事接管'
        before = {m['id'] for m in latest}
        try:
            self.page.locator('.SendButtonGroup > .send-button').click(timeout=5000)
            deadline = time.monotonic() + 7
            while time.monotonic() < deadline:
                for message in self.read_messages():
                    if message['id'] not in before and message['role'] == 'agent' and comparable_text(message['text']) == comparable_text(reply):
                        self.confirmed_message = message
                        return 'sent', ''
                self.page.wait_for_timeout(150)
        except Exception:
            pass
        return 'uncertain', '发送结果未确认，请核对网页后处理；不会自动重发'

    def close(self):
        def release(callback):
            try:
                callback()
            except Exception as exc:
                # Ctrl+C may terminate either Chromium or its Playwright driver first.
                if not isinstance(exc, TargetClosedError) and not str(exc).endswith(
                    'Connection closed while reading from the driver'
                ):
                    raise

        context, playwright = self.context, self.playwright
        self.context = self.page = self.playwright = None
        try:
            if context:
                release(context.close)
        finally:
            if playwright:
                release(playwright.stop)

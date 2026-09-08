"""Rebuilt local replica regression: inject customers, reply exclusively through DOM."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from mock_dongdong.rpa import ReplicaRpa

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:18766"


def api(path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)


def ensure_server():
    try:
        health = api("/api/health")
    except OSError:
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        subprocess.Popen([sys.executable, "-X", "utf8", "-m", "mock_dongdong", "serve"],
                         cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
        deadline = time.monotonic() + 15
        while True:
            try:
                health = api("/api/health")
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Replica server failed to start")
                time.sleep(.3)
    if health.get("version") != 2:
        raise RuntimeError("Port 18766 is occupied by another server")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="explicitly open a separate test browser")
    parser.add_argument("--channel", default="msedge" if os.name == "nt" else "chromium")
    args = parser.parse_args(argv)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out = ROOT / "artifacts" / f"replica-v2-{stamp}"
    out.mkdir(parents=True)
    report = {"version": 2, "passed": False, "transport": "Playwright DOM", "cases": []}
    try:
        ensure_server()
        templates = json.loads((ROOT / "offline-templates.json").read_text(encoding="utf-8"))
        buyers = [f"离线验证-{stamp[-13:]}-{i}" for i in (1, 2)]
        for buyer in buyers:
            api("/api/users", {"name": buyer})
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.headed, channel=args.channel)
            try:
                context = browser.new_context(viewport={"width":1146,"height":958})
                external = []
                def route(request_route):
                    url = request_route.request.url
                    if url.startswith(BASE + "/"):
                        request_route.continue_()
                    else:
                        external.append(url)
                        request_route.abort()
                context.route("**/*", route)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(BASE + "/workbench")
                rpa = ReplicaRpa(page, templates)
                for i, buyer in enumerate([buyers[0], buyers[1], buyers[0]]):
                    case = templates[0 if i == 0 else 1]
                    api("/api/send", {"user":buyer,"text":case["question"]})
                    started = time.monotonic()
                    page.locator('.c_tabs-tab[title="历史咨询"]').click()
                    row = page.locator(".c_tabs-tabpane:not(.c_tabs-tab_inactive) .alluser-item").filter(has=page.get_by_text(buyer,exact=True))
                    expect(row.locator(".alluser-item-breifdesc")).to_have_text(case["question"])
                    rpa.open_customer(buyer, case["question"])
                    result = rpa.reply_current()
                    assert result is not None
                    result["seconds"] = round(time.monotonic()-started, 2)
                    assert rpa.reply_current() is None
                    chat = api("/api/chat?user="+urllib.parse.quote(buyer))
                    assert chat["messages"][-1]["text"] == case["reply"]
                    assert chat["unread"] == 0
                    report["cases"].append(result)
                # Independent windows retain their own selected customer and drafts.
                page.locator(".EditorContent").fill("未发送的草稿")
                rpa.open_customer(buyers[1])
                expect(page.locator(".EditorContent")).to_be_empty()
                rpa.open_customer(buyers[0])
                expect(page.locator(".EditorContent")).to_have_text("未发送的草稿")
                page.locator(".EditorContent").fill("")
                second = context.new_page()
                second.goto(BASE + "/workbench")
                other = ReplicaRpa(second, templates)
                other.open_customer(buyers[1])
                expect(page.locator(".chat-head-name > span").first).to_have_text(buyers[0])
                page.reload()
                expect(page.locator(".EditorContent[contenteditable=true]")).to_be_visible()
                assert ReplicaRpa(page, templates).reply_current() is None
                # Rapid switching must not display a previous customer's response.
                rows = page.locator(".c_tabs-tabpane:not(.c_tabs-tab_inactive) .alluser-item")
                rows.filter(has=page.get_by_text(buyers[1],exact=True)).click()
                rows.filter(has=page.get_by_text(buyers[0],exact=True)).click()
                expect(page.locator(".chat-head-name > span").first).to_have_text(buyers[0])
                expect(page.locator(".message_right .message__content")).to_have_count(2)
                for buyer, count in [(buyers[0],2),(buyers[1],1)]:
                    chat = api("/api/chat?user="+urllib.parse.quote(buyer))
                    assert sum(m["role"]=="agent" for m in chat["messages"]) == count
                # The server accepts the send, but its confirmation is lost.
                retry_buyer = buyers[0] + "-重试"
                api("/api/users", {"name":retry_buyer})
                api("/api/send", {"user":retry_buyer,"text":templates[0]["question"]})
                expect(page.locator(".c_tabs-tabpane:not(.c_tabs-tab_inactive) .alluser-item-name").filter(has_text=retry_buyer)).to_have_count(1)
                rpa.open_customer(retry_buyer,templates[0]["question"])
                def lose_confirmation(request_route):
                    request_route.fetch()
                    request_route.abort()
                page.route("**/api/agent-send", lose_confirmation, times=1)
                page.locator(".EditorContent").fill(templates[0]["reply"])
                page.locator(".send-button").click()
                expect(page.locator(".send-error")).to_contain_text("发送失败")
                expect(page.locator(".EditorContent")).to_have_text(templates[0]["reply"])
                page.locator(".send-button").click()
                expect(page.locator(".EditorContent")).to_be_empty()
                retry_chat = api("/api/chat?user="+urllib.parse.quote(retry_buyer))
                assert sum(m["role"]=="agent" for m in retry_chat["messages"]) == 1
                # Text is escaped, and plain Enter sends through the observed span's handler.
                literal = "<b>literal & text</b>"
                page.locator(".EditorContent").fill(literal)
                page.locator(".EditorContent").press("Enter")
                expect(page.locator(".message_right .message__content").last).to_have_text(literal)
                expect(page.locator(".message__content b")).to_have_count(0)
                rpa.open_customer("模拟顾客-开发者")
                expect(page.locator(".ProductCard .Error")).to_have_count(1)
                expect(page.locator(".message__system_wrap")).to_have_count(1)
                expect(page.locator(".last-chat-divider")).to_have_count(1)
                page.screenshot(path=str(out / "desktop.png"))
                page.set_viewport_size({"width":390,"height":844})
                page.screenshot(path=str(out / "narrow.png"), full_page=True)
                assert not errors, errors
                assert not external, external
                report.update(passed=True, checks=["two customers / three replies", "no duplicate after reload", "draft restoration", "independent windows", "rapid switching", "lost send confirmation / retry without duplicate", "Enter send / escaped text", "product error / system / divider fixtures", "no external requests", "no page errors"])
            finally:
                browser.close()
    except Exception as exc:
        report["error"] = str(exc)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    print(f"Report: {out / 'report.json'}", flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Opt-in browser integration: python -m tests.service_smoke [--live-model]."""
import argparse
import json
import tempfile
import threading
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from cs_rpa.database import ROOT
from cs_rpa.server import create_server


class FixtureModel:
    def __init__(self, profile):
        pass

    def plan(self, persona, context):
        last = next(m['text'] for m in reversed(context['history']) if m['role'] == 'customer')
        if context['colleague_result']:
            return {'intent': 'consult', 'reply': context['colleague_result'], 'fields': {}}
        if '定制' in last:
            return {'intent': 'custom', 'reply': '我先整理需求。', 'reason': '定制外壳需求',
                    'fields': {'product': 'TEST-1', 'requirements': '外壳', 'quantity': '100台',
                               'deadline': '下月', 'contact': '测试联系人'}}
        return {'intent': 'consult', 'reply': '这款 TEST-1 使用 5V 供电。',
                'evidence_ids': [k['id'] for k in context['knowledge']]}

    def test(self):
        return {'ok': True, 'model': 'fixture', 'seconds': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live-model', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'artifacts' / ('service-live-smoke' if args.live_model else 'service-smoke')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
        kwargs = {} if args.live_model else {'model_factory': FixtureModel, 'env_path': None}
        server, app = create_server(port=0, data_dir=Path(directory), import_root=None, **kwargs)
        base = f'http://127.0.0.1:{server.server_address[1]}'
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        errors = []
        try:
            with app.fixture._lock:
                app.fixture._write({'rev': 0, 'sessions': []})
            if not args.live_model:
                app.settings.save_profile({'name': '测试模型', 'protocol': 'anthropic', 'base_url': 'https://example.com',
                                           'api_key': 'fixture-key', 'model': 'fixture'})
            app.settings.save_runtime({'poll_seconds': 1, 'merge_seconds': 0})
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/manage')
                expect(page.locator('#runtime-title')).to_have_text('服务已就绪')
                page.locator('[data-view="knowledge"]').click()
                page.locator('#add-knowledge').click()
                page.locator('#knowledge-form [name=title]').fill('TEST-1供电电压是多少')
                page.locator('#knowledge-form [name=content]').fill('TEST-1是一款测试开发板，使用5V供电。')
                page.locator('#knowledge-form [name=product]').fill('TEST-1')
                page.locator('#knowledge-form button[type=submit]').click()
                expect(page.locator('#knowledge-dialog')).not_to_be_visible()
                control = browser.new_page()
                control.goto(base + '/control')
                control.locator('#create [name=name]').fill('测试客户甲')
                control.locator('#create button').click()
                expect(control.locator('#customer-title')).to_have_text('测试客户甲')
                control.locator('#inbound [name=text]').fill('请问TEST-1供电电压是多少？')
                control.locator('#inbound button[type=submit]').click()
                page.locator('[data-view="overview"]').click()
                page.locator('#start').click()
                expect(page.locator('#outbox textarea')).to_be_visible(timeout=120000)
                draft = page.locator('#outbox textarea')
                assert '5V' in draft.input_value(), draft.input_value()
                draft.fill(draft.input_value() + ' 请使用匹配的电源。')
                draft.focus()
                page.wait_for_timeout(2500)
                assert draft.evaluate('(el)=>document.activeElement===el'), 'Polling stole editor focus'
                draft.blur()
                page.locator('[data-outbox=approve]').click()
                expect(page.locator('#outbox .badge').first).to_have_text('已发送', timeout=30000)
                expect(control.locator('#history')).to_contain_text('匹配的电源', timeout=15000)
                page.locator('#pause').click()
                expect(page.locator('#runtime-title')).to_have_text('接待已暂停')
                control.locator('#create [name=name]').fill('测试客户乙')
                control.locator('#create button').click()
                expect(control.locator('#customer-title')).to_have_text('测试客户乙')
                control.locator('#inbound [name=text]').fill('我要定制TEST-1外壳，100台，下月交货，联系人是测试联系人。')
                control.locator('#inbound button[type=submit]').click()
                page.wait_for_timeout(1600)
                assert not app.db.rows('SELECT * FROM tasks'), 'Pause still processed new messages'
                page.locator('#start').click()
                page.locator('[data-view=tasks]').click()
                expect(page.locator('[data-result]')).to_be_visible(timeout=120000)
                page.screenshot(path=str(output / 'tasks.png'), full_page=True)
                page.locator('[data-result]').fill('同事已确认可以定制外壳。\n\n请您提供尺寸图纸。')
                page.locator('[data-resolve]').click()
                expect(page.locator('#task-list .badge').first).to_have_text('已完成', timeout=120000)
                page.locator('[data-view=overview]').click()
                expect(page.locator('#outbox textarea').first).to_contain_text('图纸', timeout=15000)
                page.screenshot(path=str(output / 'overview.png'), full_page=True)
                page.locator('[data-outbox=approve]').click()
                expect(page.locator('#outbox .badge').first).to_have_text('已发送', timeout=30000)
                page.locator('#stop').click()
                expect(page.locator('#runtime-title')).to_have_text('服务已就绪', timeout=30000)
                assert not app.runtime.status()['running']
                if not args.live_model:
                    app.settings.save_runtime({'mode': 'auto'})
                    control.locator('#inbound [name=text]').fill('TEST-1使用什么供电电压？')
                    control.locator('#inbound button[type=submit]').click()
                    page.locator('#start').click()
                    expect(page.locator('#stat-sent')).to_have_text('3', timeout=30000)
                    page.locator('#stop').click()
                    expect(page.locator('#runtime-title')).to_have_text('服务已就绪', timeout=30000)
                for name in ['conversations', 'knowledge', 'models', 'settings']:
                    page.locator(f'.nav-item[data-view={name}]').click()
                    page.wait_for_timeout(350)
                    page.screenshot(path=str(output / f'{name}.png'), full_page=True)
                page.set_viewport_size({'width': 390, 'height': 844})
                for name in ['overview', 'models', 'settings', 'conversations']:
                    page.locator(f'.nav-item[data-view={name}]').click()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{name} overflows mobile'
                page.locator('[data-view=overview]').click()
                page.screenshot(path=str(output / 'mobile.png'), full_page=True)
                control.set_viewport_size({'width': 1366, 'height': 900})
                control.screenshot(path=str(output / 'control.png'), full_page=True)
                control.goto(base + '/workbench')
                expect(control.locator('.c_tabs-tab_check')).to_have_attribute('title', '正在咨询')
                expect(control.locator('.message__content').first).to_be_visible()
                control.screenshot(path=str(output / 'workbench.png'), full_page=True)
                assert not errors, errors
                report = {'ok': True, 'live_model': args.live_model, 'counts': app.state()['counts'],
                          'browser_errors': errors, 'runtime': app.runtime.status()}
                (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                print(json.dumps(report, ensure_ascii=False), flush=True)
                browser.close()
        except Exception:
            (output / 'failure.json').write_text(json.dumps({'state': app.state(),
                'chats': [app.fixture.get_chat(u['id']) for u in app.fixture.list_users()]},
                ensure_ascii=False, indent=2), encoding='utf-8')
            raise
        finally:
            server.shutdown()
            thread.join()
            app.close()
            server.server_close()


if __name__ == '__main__':
    main()

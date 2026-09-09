import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from cs_rpa.browser import BrowserAdapter
from cs_rpa.runtime import Runtime
import test_service as fixtures


class RealBaselineCase(unittest.TestCase):
    setUp = fixtures.ServiceCase.setUp
    graph = fixtures.ServiceCase.graph
    value = fixtures.ServiceCase.value
    config = fixtures.ServiceCase.config
    def test_initial_history_marks_handled_without_reply_or_task(self):
        runtime = Runtime(self.db, self.settings, self.knowledge)
        self.assertTrue(runtime.baseline_history(self.cid, self.db.history(self.cid), time.time()))
        current = self.db.conversation(self.cid)
        self.assertEqual(current['latest_id'], current['handled_id'])
        self.assertFalse(self.db.rows('SELECT * FROM outbox'))
        self.assertFalse(self.db.rows('SELECT * FROM tasks'))

    def test_message_received_during_initial_scan_is_not_baselined(self):
        runtime = Runtime(self.db, self.settings, self.knowledge)
        started = time.time() - 2
        messages = [{'timestamp': datetime.now().strftime('%m-%d %H:%M:%S'), 'text': '新咨询'}]
        self.assertFalse(runtime.baseline_history(self.cid, messages, started))
        self.assertNotEqual(self.db.conversation(self.cid)['handled_id'], 'm1')

    def test_real_auto_mode_still_creates_only_drafts(self):
        self.settings.save_runtime({'transport': 'jingmai', 'mode': 'auto'})
        self.graph().invoke(self.value(), self.config)
        self.assertEqual(self.db.one('SELECT status FROM outbox')['status'], 'draft')

    def test_real_monitor_skips_old_history_then_processes_new_message(self):
        self.settings.save_runtime({'transport': 'jingmai', 'mode': 'auto', 'merge_seconds': 0, 'poll_seconds': 1})
        db, calls, reads = self.db, [], []
        runtime = None
        class Adapter(BrowserAdapter):
            def start(self):
                self.round = 0
            def customers(self):
                self.round += 1
                if db.one('SELECT id FROM outbox') or self.round > 8:
                    runtime.stop_event.set()
                return [{'name': '真实流程测试', 'customer_key': 'test-real', 'initial_history': True,
                         'preview': '历史问题' if self.round < 3 else '新的问题'}]
            def open_customer(self, name):
                reads.append(self.round)
                messages = [{'id': 'old', 'role': 'customer', 'text': '历史问题', 'timestamp': ''}]
                if self.round >= 3:
                    messages.append({'id': 'new', 'role': 'customer', 'text': '新的问题'})
                return messages
            def close(self):
                pass
            def send(self, *args):
                raise AssertionError('真实环境不应进入自动发送')
        class Model:
            def __init__(self, profile):
                pass
            def plan(self, persona, context):
                calls.append(context['history'][-1]['text'])
                return {'intent': 'greeting', 'reply': '测试回复', 'fields': {}}
        runtime = Runtime(db, self.settings, self.knowledge, adapter_factory=Adapter, model_factory=Model)
        runtime._run()
        self.assertEqual(calls, ['新的问题'])
        self.assertEqual(reads, [1, 3])
        self.assertEqual(runtime.baseline_count, 1)
        item = db.one('SELECT * FROM outbox')
        self.assertEqual((item['source_id'], item['status']), ('new', 'draft'))


class MonitorSelectionCase(unittest.TestCase):
    def test_first_customer_after_empty_start_is_new_not_history(self):
        adapter = BrowserAdapter({'transport': 'jingmai', 'max_sessions': 100}, Path('.'))
        adapter.select_workbench = Mock()
        adapter.guard = Mock()
        adapter.select_consulting = Mock()
        adapter.collect_contacts = Mock(side_effect=[[], [{'name': 'new', 'customer_key': 'name:new'}]])
        self.assertEqual(adapter.customers(), [])
        self.assertFalse(adapter.customers()[0]['initial_history'])

    def test_unchanged_preview_skips_open_but_periodic_audit_and_pending_work_read(self):
        adapter = BrowserAdapter({'transport': 'jingmai'}, Path('.'))
        customer = {'customer_key': 'name:test', 'preview': '你好', 'date': '今天'}
        self.assertTrue(adapter.should_read(customer))
        adapter.mark_read_snapshot(customer)
        self.assertFalse(adapter.should_read(customer))
        self.assertTrue(adapter.should_read({**customer, 'preview': '新的问题'}))
        self.assertTrue(adapter.should_read(customer, force=True))
        fingerprint, stamp = adapter.read_cache[customer['customer_key']]
        adapter.read_cache[customer['customer_key']] = (fingerprint, stamp - 61)
        self.assertTrue(adapter.should_read(customer))

    def test_virtualized_pages_are_merged_and_initial_customers_are_marked(self):
        adapter = BrowserAdapter({'transport': 'jingmai', 'max_sessions': 100}, Path('.'))
        adapter.page = Mock()
        adapter.page.locator.return_value.inner_text.return_value = '最近联系人(23)'
        def rows(start, end):
            return [{'name': str(i), 'customer_key': '', 'preview': '', 'date': ''} for i in range(start, end)]
        adapter.contact_rows = Mock(side_effect=[rows(0,22), rows(18,23), rows(18,23), rows(18,23)])
        adapter.scroll_contacts = Mock(side_effect=[{'moved': False, 'bottom': False},
            {'moved': True, 'bottom': True}, {'moved': False, 'bottom': True}, {'moved': False, 'bottom': True}, {'moved': False, 'bottom': True}])
        contacts = adapter.collect_contacts()
        self.assertEqual(len(contacts), 23)
        self.assertEqual(len({r['customer_key'] for r in contacts}), 23)
        self.assertIn('22', [r['name'] for r in contacts])


if __name__ == '__main__':
    unittest.main()

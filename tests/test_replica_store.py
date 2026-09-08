import tempfile
import unittest
from pathlib import Path

from mock_dongdong.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "state.json")
        self.store.create_user("customer-a")
        self.store.create_user("customer-b")

    def test_read_does_not_clear_later_inbound(self):
        first = self.store.send_customer("customer-a", "first")
        self.store.send_customer("customer-a", "second")
        self.store.mark_read("customer-a", first["id"])
        self.assertEqual(self.store.get_chat("customer-a")["unread"], 1)

    def test_retry_is_idempotent_and_bound_to_customer(self):
        first = self.store.agent_send("customer-a", "reply", "request-1")
        again = self.store.agent_send("customer-a", "reply", "request-1")
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(len(self.store.get_chat("customer-a")["messages"]), 1)
        self.assertEqual(len(self.store.get_chat("customer-b")["messages"]), 0)
        with self.assertRaises(ValueError):
            self.store.agent_send("customer-a", "different", "request-1")

    def test_reset_revision_increases(self):
        before = self.store.snapshot()["rev"]
        self.store.reset()
        self.assertGreater(self.store.snapshot()["rev"], before)


if __name__ == "__main__":
    unittest.main()

"""Configuration paths remain rooted at the project after moving legacy tools."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from legacy.config import load_config


@unittest.skipUnless(importlib.util.find_spec("yaml"), "optional legacy PyYAML dependency")
class ConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config.yaml").write_text(
            "auto_send: false\nbridge_base: http://127.0.0.1:18080\njingmai:\n  mode: web\n",
            encoding="utf-8",
        )
        patcher = patch("legacy.config.ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_base_config_without_overlay(self):
        config = load_config()
        self.assertFalse(config["auto_send"])
        self.assertEqual(config["jingmai"], {"mode": "web"})

    def test_local_config_preserves_shallow_override(self):
        (self.root / "config.local.yaml").write_text(
            "auto_send: true\njingmai:\n  process: custom\n", encoding="utf-8",
        )
        config = load_config()
        self.assertTrue(config["auto_send"])
        self.assertEqual(config["jingmai"], {"process": "custom"})
        self.assertEqual(config["bridge_base"], "http://127.0.0.1:18080")

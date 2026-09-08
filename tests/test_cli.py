"""The offline CLI must remain usable without Windows or browser dependencies."""
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_help_without_site_packages(self):
        for arguments in [[], ["serve"], ["demo"]]:
            with self.subTest(command=arguments):
                result = subprocess.run(
                    [sys.executable, "-S", "-m", "mock_dongdong", *arguments, "--help"],
                    cwd=ROOT, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_removed_mock_entry_explains_replacement(self):
        result = subprocess.run(
            [sys.executable, "-S", "-m", "legacy.run", "--mock"],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("python -m mock_dongdong demo", result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

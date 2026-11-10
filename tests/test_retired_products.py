"""Retired products are rejected before installation touches a target home."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RetiredProductTests(unittest.TestCase):
    def test_antigravity_is_rejected_without_target_changes(self):
        with tempfile.TemporaryDirectory(prefix="mainframe-retired-product-") as directory:
            home = Path(directory)
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "install.py"), "antigravity",
                 "uninstall", "--home", str(home)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("invalid choice: 'antigravity'", result.stderr)
            self.assertEqual(list(home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

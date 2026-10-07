"""Complete portable material, independently of native execution parity."""
import re
import tempfile
import tomllib
import unittest
from pathlib import Path

from installer.antigravity import Antigravity
from installer.cline import Cline
from installer.codex import Codex
from installer.minimax import MiniMax
from installer.shared import inventory, skill_resources
from installer.zcode import ZCode

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = (Codex, ZCode, Antigravity, MiniMax, Cline)


def normalized(text):
    return " ".join(text.split())


class DeliveryParityTests(unittest.TestCase):
    def test_every_skill_resource_and_role_and_command_body_is_delivered(self):
        source = inventory(ROOT)
        resources = skill_resources(ROOT, source)
        with tempfile.TemporaryDirectory(prefix="mainframe-delivery-parity-") as directory:
            for kind in ADAPTERS:
                adapter = kind(ROOT, Path(directory) / kind.__name__)
                artifacts = adapter.artifacts(source, {}) if kind is Codex else adapter.artifacts(source)
                for name, files in resources.items():
                    with self.subTest(adapter=kind.__name__, skill=name):
                        delivered = {p: row for p, row in artifacts.items() if row[2] == "skills." + name}
                        self.assertEqual(len(files), len(delivered))
                        base = ROOT / source["components"]["skills"][name]["source"]
                        for path in files:
                            relative = path.relative_to(base).as_posix()
                            matches = [row for p, row in delivered.items()
                                       if p.as_posix().endswith("/" + name + "/" + relative)]
                            self.assertEqual(len(matches), 1, relative)
                            expected = path.read_bytes().replace(b"{{MAINFRAME_ROOT}}", str(ROOT).encode()).replace(
                                b"{{CREDENTIALS_INDEX}}", str(adapter.index).encode())
                            self.assertEqual(matches[0][0], expected, relative)
                            self.assertEqual(matches[0][1], path.stat().st_mode & 0o777, relative)
                for category in ("agents", "commands"):
                    for name, row in source["components"][category].items():
                        with self.subTest(adapter=kind.__name__, component=name):
                            copies = [data for _, (data, _, component, _) in artifacts.items()
                                      if component == category + "." + name]
                            self.assertTrue(copies, name)
                            text = (ROOT / row["source"]).read_text()
                            if category == "agents":
                                method = re.search(r"^Required method: \[([^]]+)\]", text, re.M).group(1)
                                text = text[text.index("## Role"):]
                                if kind is Codex:
                                    copies = [tomllib.loads(data.decode())["developer_instructions"].encode()
                                              for data in copies]
                                self.assertTrue(any(method in data.decode() for data in copies))
                            else:
                                text = re.sub(r"<!-- MAINFRAME OPTIONAL BLOCK: native-primary-memory.*?<!-- END MAINFRAME OPTIONAL BLOCK: native-primary-memory -->\n?", "", text, flags=re.S)
                            # Metadata/indentation may change, but each canonical body paragraph stays.
                            joined = [normalized(data.decode()) for data in copies]
                            for paragraph in re.split(r"\n\s*\n", text.strip()):
                                self.assertTrue(any(normalized(paragraph) in value for value in joined),
                                                paragraph[:100])

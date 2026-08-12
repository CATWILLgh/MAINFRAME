#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = (
    ROOT
    / "adapters"
    / "claude-code"
    / "plugin"
    / "skills"
    / "shadcn"
    / "scripts"
    / "inspect-ui.mjs"
)


def run_inspector(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        package_root = Path(temp_dir)
        for relative, content in files.items():
            target = package_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        completed = subprocess.run(
            ["node", str(INSPECTOR), str(package_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)


class ShadcnInspectUiTests(unittest.TestCase):
    def test_stops_cleanly_when_package_is_not_shadcn(self):
        report = run_inspector({"package.json": '{"name":"plain-react"}'})

        self.assertFalse(report["shadcn"])
        self.assertEqual(report["reason"], "components.json not found")

    def test_lists_local_components_and_their_importing_files(self):
        report = run_inspector(
            {
                "components.json": json.dumps(
                    {
                        "style": "new-york",
                        "base": "radix",
                        "rsc": False,
                        "iconLibrary": "lucide",
                        "aliases": {"ui": "@/components/ui"},
                    }
                ),
                "src/components/ui/button.tsx": "export function Button() {}",
                "src/components/ui/dialog.tsx": "export function Dialog() {}",
                "src/pages/home.tsx": 'import { Button } from "@/components/ui/button";',
                "src/pages/settings.tsx": 'import { Button } from "@/components/ui/button";',
            }
        )

        self.assertTrue(report["shadcn"])
        self.assertEqual(report["uiDirectory"], "src/components/ui")
        self.assertEqual(report["config"]["base"], "radix")
        components = {item["name"]: item for item in report["components"]}
        self.assertEqual(
            components["button"]["importedBy"],
            ["src/pages/home.tsx", "src/pages/settings.tsx"],
        )
        self.assertEqual(components["dialog"]["importedBy"], [])


if __name__ == "__main__":
    unittest.main()

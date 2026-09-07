import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ADAPTATION.example.json"

EXPECTED_COMPONENTS = {
    "skills": {
        "mainframe-secrets",
        "mainframe-curl-requests",
        "mainframe-infrastructure",
        "mainframe-ops-app-server-safety",
        "mainframe-project-harness",
        "mainframe-peer-work",
        "mainframe-consequential-review",
        "mainframe-record-project-problem",
        "mainframe-harness-feedback",
        "mainframe-typescript-backend",
        "mainframe-python-backend",
        "mainframe-frontend",
        "mainframe-research",
        "mainframe-test-audit",
    },
    "agents": {
        "mainframe-typescript-backend-engineer",
        "mainframe-python-backend-engineer",
        "mainframe-react-frontend-engineer",
        "mainframe-consequential-reviewer",
        "mainframe-researcher",
        "mainframe-test-auditor",
    },
    "commands": {
        "mainframe-init",
        "project-skill",
        "tickets-find",
        "tickets-refine",
        "tickets-implement",
        "tickets-verify",
    },
    "hooks": {
        "destructive-operations",
        "secret-access",
        "rg-short-replace",
        "commit-secrets",
        "code-quality",
        "fallow-quality",
    },
}


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def markdown_files():
    roots = [
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
        ROOT / "ADAPT-MAINFRAME.md",
        ROOT / "hooks" / "README.md",
    ]
    for directory in ("docs", "skills", "agents", "commands"):
        roots.extend((ROOT / directory).rglob("*.md"))
    return sorted(set(roots))


def prose_without_fenced_code(text):
    lines = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return "\n".join(lines)


class RepositoryContractTests(unittest.TestCase):
    def test_manifest_uses_the_supported_state_model(self):
        manifest = load_manifest()
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(
            manifest["status_values"], ["pending", "installed", "unsupported"]
        )

        for group in manifest["components"].values():
            if not isinstance(group, dict):
                continue
            for component in group.values():
                if isinstance(component, dict) and "status" in component:
                    self.assertEqual(component["status"], "pending")

    def test_manifest_matches_the_delivered_component_inventory(self):
        components = load_manifest()["components"]
        for group, expected in EXPECTED_COMPONENTS.items():
            self.assertEqual(set(components[group]), expected, group)

        self.assertEqual(set(components["instructions"]), {"global"})
        self.assertEqual(
            components["shared"],
            {
                "credentials": {
                    "source": "shared/credentials/secret",
                    "status": "pending",
                }
            },
        )
        for group in ("mcp", "plugins", "runtime", "settings"):
            self.assertEqual(components[group], {}, group)

    def test_manifest_inventory_matches_files_on_disk(self):
        actual = {
            "skills": {
                path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")
            },
            "agents": {path.stem for path in (ROOT / "agents").glob("*.md")},
            "commands": {path.stem for path in (ROOT / "commands").glob("*.md")},
            "hooks": {
                path.stem for path in (ROOT / "hooks").glob("*.py")
            },
        }
        self.assertEqual(actual, EXPECTED_COMPONENTS)

    def test_every_manifest_source_exists_inside_the_repository(self):
        components = load_manifest()["components"]
        sources = []
        for group in components.values():
            for component in group.values():
                if isinstance(component, dict) and "source" in component:
                    sources.append(component["source"])

        forbidden = {
            "README.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "AGENTS.md",
            "CLAUDE.md",
            "ADAPT-MAINFRAME.md",
        }
        for source in sources:
            with self.subTest(source=source):
                path = (ROOT / source).resolve()
                self.assertTrue(path.is_relative_to(ROOT.resolve()))
                self.assertTrue(path.exists())
                self.assertNotIn(source, forbidden)
                self.assertFalse(source.startswith(("docs/", "tests/", ".github/")))

    def test_local_markdown_links_resolve(self):
        pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
        failures = []
        for document in markdown_files():
            text = prose_without_fenced_code(document.read_text(encoding="utf-8"))
            for raw_target in pattern.findall(text):
                target = raw_target.strip()
                if target.startswith("<") and ">" in target:
                    target = target[1 : target.index(">")]
                else:
                    target = target.split(maxsplit=1)[0]
                target = unquote(target.split("#", maxsplit=1)[0])
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.exists():
                    failures.append(f"{document.relative_to(ROOT)} -> {raw_target}")
        self.assertEqual(failures, [])

    def test_root_agent_files_are_product_entrypoints(self):
        self.assertEqual((ROOT / "CLAUDE.md").read_text(encoding="utf-8"), "@AGENTS.md\n")
        manifest_text = MANIFEST.read_text(encoding="utf-8")
        self.assertNotIn('"AGENTS.md"', manifest_text)
        self.assertNotIn('"CLAUDE.md"', manifest_text)
        self.assertNotIn('"docs/', manifest_text)


if __name__ == "__main__":
    unittest.main()

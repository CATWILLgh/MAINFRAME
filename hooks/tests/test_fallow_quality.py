from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "fallow-quality.py"
SPEC = importlib.util.spec_from_file_location("fallow_quality", SOURCE)
assert SPEC is not None and SPEC.loader is not None
FALLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FALLOW)


def report() -> dict[str, object]:
    return {
        "kind": "audit",
        "dead_code": {
            "unused_files": [
                {"path": "src/new.ts", "introduced": True},
                {"path": "src/other.ts", "introduced": True},
            ],
            "circular_dependencies": [
                {"files": ["src/new.ts", "src/cycle.ts"], "introduced": True},
                {"files": ["src/other.ts", "src/old.ts"], "introduced": True},
                {"files": ["src/new.ts", "src/inherited.ts"], "introduced": False},
            ],
            "boundary_violations": [
                {
                    "from_path": "src/new.ts",
                    "to_path": "src/private.ts",
                    "line": 4,
                    "introduced": True,
                }
            ],
            "boundary_call_violations": [],
        },
        "complexity": {
            "findings": [
                {
                    "path": "src/new.ts",
                    "line": 8,
                    "name": "work",
                    "cyclomatic": 19,
                    "introduced": True,
                }
            ]
        },
        "duplication": {
            "clone_groups": [
                {
                    "instances": [{"file": "src/new.ts", "start_line": 2}],
                    "line_count": 24,
                    "introduced": True,
                }
            ]
        },
    }


class FallowQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-fallow-")
        self.root = Path(self.temporary.name)
        (self.root / "src").mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_reports_only_introduced_current_scope_and_wholly_owned_unused(self) -> None:
        note = FALLOW.build_advisory(
            report(),
            self.root,
            ["src/new.ts"],
            wholly_owned_paths=["src/new.ts"],
        )
        self.assertIn("unused file: src/new.ts", note or "")
        self.assertIn("import cycle: src/new.ts -> src/cycle.ts", note or "")
        self.assertIn("boundary: src/new.ts:4 -> src/private.ts", note or "")
        self.assertIn("complexity: src/new.ts:8", note or "")
        self.assertIn("duplication: src/new.ts:2", note or "")
        self.assertNotIn("src/other.ts", note or "")
        self.assertNotIn("src/inherited.ts", note or "")

    def test_unused_file_requires_whole_file_ownership(self) -> None:
        isolated = {
            "kind": "audit",
            "dead_code": {
                "unused_files": [{"path": "src/new.ts", "introduced": True}]
            },
            "complexity": {},
            "duplication": {},
        }
        self.assertIsNone(
            FALLOW.build_advisory(isolated, self.root, ["src/new.ts"])
        )

    def test_non_javascript_scope_is_silent_without_invoking_fallow(self) -> None:
        with mock.patch.object(FALLOW.subprocess, "run") as run:
            result = FALLOW.analyze(self.root, ["src/module.py"], "diff")
        self.assertEqual(result, FALLOW.FallowResult())
        run.assert_not_called()

    def test_out_of_project_scope_is_unavailable_without_invoking_fallow(self) -> None:
        outside = self.root.parent / "outside.ts"
        with mock.patch.object(FALLOW.subprocess, "run") as run:
            result = FALLOW.analyze(self.root, [outside], "diff")
        self.assertIsNone(result.advisory)
        self.assertIn("unavailable", result.unavailable or "")
        run.assert_not_called()

    def test_invocation_is_bounded_new_only_and_disables_telemetry(self) -> None:
        process = mock.Mock(returncode=0, stdout=json.dumps(report()), stderr="")
        with (
            mock.patch.object(FALLOW.shutil, "which", return_value="/tools/fallow"),
            mock.patch.object(FALLOW.subprocess, "run", return_value=process) as run,
        ):
            result = FALLOW.analyze(
                self.root,
                ["src/new.ts"],
                "diff --git a/src/new.ts b/src/new.ts\n",
                wholly_owned_paths=["src/new.ts"],
            )
        self.assertIn("newly introduced", result.advisory or "")
        self.assertIsNone(result.unavailable)
        arguments, keywords = run.call_args
        self.assertEqual(arguments[0][0:2], ["/tools/fallow", "audit"])
        self.assertIn("--diff-stdin", arguments[0])
        self.assertIn("new-only", arguments[0])
        self.assertEqual(keywords["input"], "diff --git a/src/new.ts b/src/new.ts\n")
        self.assertEqual(keywords["env"]["FALLOW_TELEMETRY"], "off")
        self.assertEqual(keywords["env"]["FALLOW_TELEMETRY_DISABLED"], "1")
        self.assertEqual(keywords["env"]["FALLOW_UPDATE_CHECK"], "off")
        self.assertIn("--no-cache", arguments[0])
        self.assertFalse(keywords["check"])

    def test_missing_or_failed_analyzer_is_advisory_and_never_a_block(self) -> None:
        with mock.patch.object(FALLOW.shutil, "which", return_value=None):
            missing = FALLOW.analyze(self.root, ["src/new.ts"], "diff")
        self.assertIsNone(missing.advisory)
        self.assertIn("not blocked", missing.unavailable or "")

        process = mock.Mock(returncode=2, stdout='{"error":true}', stderr="secret")
        with (
            mock.patch.object(FALLOW.shutil, "which", return_value="/tools/fallow"),
            mock.patch.object(FALLOW.subprocess, "run", return_value=process),
        ):
            failed = FALLOW.analyze(self.root, ["src/new.ts"], "diff")
        self.assertEqual(failed, missing)
        self.assertNotIn("secret", failed.unavailable or "")

    def test_building_advice_is_stateless_under_parallel_calls(self) -> None:
        def build(_index: int) -> str | None:
            return FALLOW.build_advisory(
                report(),
                self.root,
                ["src/new.ts"],
                wholly_owned_paths=["src/new.ts"],
            )

        expected = build(0)
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(build, range(128)))
        self.assertEqual(results, [expected] * 128)


if __name__ == "__main__":
    unittest.main()

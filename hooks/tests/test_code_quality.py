from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "mainframe-code-quality.py"
SPEC = importlib.util.spec_from_file_location("code_quality", SOURCE)
assert SPEC is not None and SPEC.loader is not None
QUALITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALITY)
PYTHON_FINDINGS = QUALITY._python_findings
NODE_FINDINGS = QUALITY._node_findings
SEMGREP_SECURITY_FINDINGS = QUALITY._semgrep_security_findings


def source_lines(count: int) -> str:
    return "".join(f"value_{index} = {index}\n" for index in range(count))


class CodeQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-code-quality-")
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.state = self.root / "state"
        self.workspace.mkdir()
        self.scanner_patchers = [
            mock.patch.object(QUALITY, "_python_findings", return_value=[]),
            mock.patch.object(QUALITY, "_node_findings", return_value=[]),
            mock.patch.object(QUALITY, "_semgrep_security_findings", return_value=[]),
        ]
        self.scanners = [patcher.start() for patcher in self.scanner_patchers]

    def tearDown(self) -> None:
        for patcher in reversed(self.scanner_patchers):
            patcher.stop()
        self.temporary.cleanup()

    def test_compact_advice_keeps_each_subsection_and_diagnostic_suffix(self) -> None:
        long_path = self.workspace.joinpath(*(["directory" * 10] * 6), "worker.py")
        rows = [(long_path, QUALITY.Occurrence("TODO comment", line, str(line)))
                for line in range(1, 7)]
        quality = QUALITY._advisory(rows, self.workspace)
        growth = QUALITY._growth_advisory([
            QUALITY.GrowthFinding(long_path, "file", None, None, 399, 405),
        ], self.workspace)
        unavailable = QUALITY._issue_advisory([
            QUALITY.ScanIssue("ruff", "Ruff review was unavailable."),
        ])
        message = QUALITY._join_notes(quality, growth, unavailable)
        self.assertLessEqual(len(message), QUALITY.MAX_ADVISORY_CHARS)
        self.assertIn("Code quality", message)
        self.assertIn("TODO comment", message)
        self.assertIn("Code structure review", message)
        self.assertIn("crossed 400", message)
        self.assertIn("Ruff review was unavailable", message)
        self.assertIn("more findings", message)

        repeated_join = QUALITY._join_notes(message, QUALITY._unavailable("verification").advisory)
        self.assertLessEqual(len(repeated_join), QUALITY.MAX_ADVISORY_CHARS)
        for heading in ("Code quality", "Code structure review", "protection unavailable"):
            self.assertIn(heading, repeated_join)

    def capture(self, scope: str, operation: str, *paths: Path):
        return QUALITY.capture_before(
            scope,
            self.workspace,
            operation,
            paths,
            state_namespace="test-adapter",
            state_root=self.state,
        )

    def test_mixed_advice_preserves_decision_boundaries_within_context_budget(self) -> None:
        file = self.workspace / "worker.js"
        before = "const value = 1;\n" * 399
        file.write_text(before, encoding="utf-8")
        self.capture("mixed", "edit", file)
        self.scanners[1].side_effect = RuntimeError("unavailable")
        self.scanners[2].return_value = [QUALITY.Occurrence(
            "Review dynamic subprocess", 2, "review",
            channel=QUALITY._SEMGREP_SECURITY_CHANNEL, blocking=False,
        )]
        file.write_text("// TODO: finish\n" + before + "\n" * 5, encoding="utf-8")

        result = self.after("mixed", "edit")
        message = result.advisory or ""
        self.assertLessEqual(len(message), QUALITY.MAX_ADVISORY_CHARS)
        for evidence in ("worker.js:1", "TODO", "crossed 400", "unavailable"):
            self.assertIn(evidence, message)
        for boundary in ("non-blocking", "no forced split", "verify directly"):
            self.assertIn(boundary, message)
        self.assertIsNone(result.block_reason)
        self.assertEqual(self.after("mixed", "edit"), QUALITY.QualityResult())
        self.assertIn("Completion blocked", self.completion("mixed").block_reason or "")

        self.capture("mixed", "repair", file)
        file.write_text(before, encoding="utf-8")
        self.after("mixed", "repair")
        self.assertIsNone(self.completion("mixed").block_reason)

    def after(self, scope: str, operation: str, *, succeeded: bool = True):
        return QUALITY.record_after(
            scope,
            self.workspace,
            operation,
            succeeded=succeeded,
            state_namespace="test-adapter",
            state_root=self.state,
        )

    def completion(self, scope: str):
        return QUALITY.check_completion(
            scope,
            self.workspace,
            state_namespace="test-adapter",
            state_root=self.state,
        )

    def test_scans_high_signal_residue_and_omits_ordinary_output(self) -> None:
        python = QUALITY.scan_text(
            'text = "TODO and # noqa"\n'
            '# TODO: implement\n'
            'value = 1  # noqa\n'
            '@pytest.mark.skip\n'
            'def test_case():\n'
            '    breakpoint()\n'
            'print("operator output")\n',
            ".py",
        )
        labels = [row.label for row in python]
        self.assertEqual(labels.count("TODO/FIXME/HACK/XXX comment"), 1)
        self.assertEqual(labels.count("# noqa"), 1)
        self.assertIn("pytest/unittest skip", labels)
        self.assertIn("breakpoint()", labels)
        self.assertNotIn("print", " ".join(labels).lower())

        javascript = QUALITY.scan_text(
            'const text = "// TODO and debugger";\n'
            '// eslint-disable next-line\n'
            'test.only("focused", () => {});\n'
            'console.log("operator output");\n'
            'console.debug("temporary");\n'
            'debugger;\n',
            ".ts",
        )
        labels = [row.label for row in javascript]
        self.assertIn("eslint-disable", labels)
        self.assertIn("skipped/focused test (.skip/.only/xit/fit)", labels)
        self.assertIn("console.debug", labels)
        self.assertIn("debugger statement", labels)
        self.assertNotIn("TODO/FIXME/HACK/XXX comment", labels)
        self.assertNotIn("console.log", " ".join(labels))

    def test_code_markers_inside_strings_and_comments_do_not_trigger(self) -> None:
        python = QUALITY.scan_text(
            'example = """\n'
            'breakpoint()\n'
            '@pytest.mark.skip\n'
            '"""\n'
            '# Ordinary explanation mentioning breakpoint()\n',
            ".py",
        )
        self.assertEqual(python, [])

        javascript = QUALITY.scan_text(
            'const example = `\n'
            'debugger;\n'
            'test.only("example", () => {});\n'
            '`;\n'
            '/*\n'
            'console.debug("example");\n'
            'debugger;\n'
            '*/\n',
            ".ts",
        )
        self.assertEqual(javascript, [])

    def test_uncertain_parser_boundary_is_advisory_not_blocking(self) -> None:
        file = self.workspace / "module.ts"
        file.write_text("const value = 1;\n", encoding="utf-8")
        self.capture("scope", "edit", file)
        file.write_text("const text = `unterminated\n", encoding="utf-8")
        result = self.after("scope", "edit")
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertIsNone(result.block_reason)
        self.assertIsNone(self.completion("scope").block_reason)

    def test_python_security_finding_warns_and_blocks_until_removed(self) -> None:
        def scan(text: str, _path: Path, **_options):
            if "eval(" not in text:
                return []
            return [
                QUALITY._occurrence(
                    "Python security S307: dynamic eval()",
                    1,
                    "scanner",
                    "eval(value)",
                    channel=QUALITY._PYTHON_SECURITY_CHANNEL,
                )
            ]

        self.scanners[0].side_effect = scan
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "add-risk", file)
        file.write_text("eval(value)\n", encoding="utf-8")
        advisory = self.after("scope", "add-risk")
        self.assertIn("S307", advisory.advisory or "")
        self.assertIn("Completion blocked", self.completion("scope").block_reason or "")

        self.capture("scope", "remove-risk", file)
        file.write_text("value = 1\n", encoding="utf-8")
        self.after("scope", "remove-risk")
        self.assertIsNone(self.completion("scope").block_reason)

    def test_preexisting_security_finding_is_not_claimed(self) -> None:
        def scan(text: str, _path: Path, **_options):
            if "eval(" not in text:
                return []
            return [
                QUALITY._occurrence(
                    "Python security S307: dynamic eval()",
                    1,
                    "scanner",
                    "eval(value)",
                    channel=QUALITY._PYTHON_SECURITY_CHANNEL,
                )
            ]

        self.scanners[0].side_effect = scan
        file = self.workspace / "module.py"
        file.write_text("eval(value)\ncount = 1\n", encoding="utf-8")
        self.capture("scope", "unrelated", file)
        file.write_text("eval(value)\ncount = 2\n", encoding="utf-8")
        self.assertEqual(self.after("scope", "unrelated"), QUALITY.QualityResult())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_new_blocking_calls_in_async_code_are_advice_without_project_configuration(self) -> None:
        self.scanners[0].side_effect = PYTHON_FINDINGS
        file = self.workspace / "worker.py"
        base = (
            "import asyncio\nimport subprocess\nimport time\nimport urllib.request\nimport httpx\n\n"
            "def synchronous_worker():\n    time.sleep(1)\n\n"
            "async def existing_worker():\n    time.sleep(2)\n\n"
            "async def new_worker():\n    await asyncio.sleep(3)\n"
        )
        file.write_text(base, encoding="utf-8")
        self.assertEqual(self.capture("scope", "introduce", file), QUALITY.QualityResult())
        changed = base.replace("    await asyncio.sleep(3)", (
            "    urllib.request.urlopen('https://example.invalid')\n"
            "    client = httpx.Client()\n"
            "    client.get('https://example.invalid')\n"
            "    subprocess.run(['printf', 'fixture'], check=True)\n"
            "    open('fixture.txt')\n"
            "    time.sleep(3)"
        ))
        file.write_text(changed, encoding="utf-8")
        result = self.after("scope", "introduce")
        advisory = result.advisory or ""
        expected = {14: "ASYNC210", 16: "ASYNC212", 17: "ASYNC221", 18: "ASYNC230", 19: "ASYNC251"}
        for line, rule in expected.items():
            self.assertIn(f"worker.py:{line} — Python {rule}", advisory)
            self.assertEqual(advisory.count(rule), 1)
        self.assertIsNone(result.block_reason)
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

        self.assertEqual(self.capture("scope", "repair", file), QUALITY.QualityResult())
        file.write_text(base, encoding="utf-8")
        self.assertEqual(self.after("scope", "repair"), QUALITY.QualityResult())

    def test_python_swallowed_errors_are_advice_on_first_write(self) -> None:
        self.scanners[0].side_effect = PYTHON_FINDINGS
        file = self.workspace / "jobs" / "worker.py"
        source = (
            "try:\n    start_job()\nexcept Exception:\n    pass\n\n"
            "def finish_job():\n"
            "    try:\n        return run_job()\n"
            "    finally:\n        return None\n\n"
            "attempts = 1\n"
        )
        self.assertEqual(self.capture("scope", "create", file), QUALITY.QualityResult())
        file.parent.mkdir()
        file.write_text(source, encoding="utf-8")
        result = self.after("scope", "create")
        self.assertIn("jobs/worker.py:3 — Python S110", result.advisory or "")
        self.assertIn("jobs/worker.py:10 — Python B012", result.advisory or "")
        self.assertIsNone(result.block_reason)
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

        self.assertEqual(self.capture("scope", "unrelated", file), QUALITY.QualityResult())
        file.write_text(source.replace("attempts = 1", "attempts = 2"), encoding="utf-8")
        self.assertEqual(self.after("scope", "unrelated"), QUALITY.QualityResult())

    def test_javascript_error_handling_and_async_executor_are_advice_on_first_write(self) -> None:
        self.scanners[1].side_effect = NODE_FINDINGS
        file = self.workspace / "worker.ts"
        async_executor = "new Promise(async (resolve) => { resolve(await runJob()); })"
        source = (
            "export function finishJob() {\n"
            "  try { return runJob(); }\n"
            "  finally { return undefined; }\n"
            "}\n"
            f"export const job = {async_executor};\n"
        )
        self.assertEqual(self.capture("scope", "create", file), QUALITY.QualityResult())
        file.write_text(source, encoding="utf-8")
        result = self.after("scope", "create")
        self.assertIn("worker.ts:3 — JavaScript no-unsafe-finally", result.advisory or "")
        self.assertIn("worker.ts:5 — JavaScript no-async-promise-executor", result.advisory or "")
        self.assertIsNone(result.block_reason)
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

        self.assertEqual(self.capture("scope", "security-risk", file), QUALITY.QualityResult())
        file.write_text(source + "eval(input);\n", encoding="utf-8")
        result = self.after("scope", "security-risk")
        self.assertIn("worker.ts:6 — JavaScript security: eval()", result.advisory or "")
        self.assertNotIn("no-async-promise-executor", result.advisory or "")
        blocked = self.completion("scope").block_reason or ""
        self.assertIn("JavaScript security: eval()", blocked)
        self.assertNotIn("no-unsafe-finally", blocked)
        self.assertNotIn("no-async-promise-executor", blocked)

        self.assertEqual(self.capture("scope", "repair", file), QUALITY.QualityResult())
        repaired = source.replace("return undefined;", "cleanup();").replace(
            async_executor, "Promise.resolve().then(runJob)"
        )
        file.write_text(repaired, encoding="utf-8")
        self.assertEqual(self.after("scope", "repair"), QUALITY.QualityResult())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_python_reports_false_green_tests_and_unretained_tasks_from_first_write(self) -> None:
        self.scanners[0].side_effect = PYTHON_FINDINGS
        file = self.workspace / "jobs" / "test_worker.py"
        source = (
            "import asyncio\nimport pytest\n\n"
            "def test_worker():\n"
            "    assert (work_finished(), 'work must finish')\n"
            "    with pytest.raises(RuntimeError):\n"
            "        configure()\n"
            "        run_job()\n\n"
            "async def launch():\n"
            "    asyncio.create_task(run_async_job())\n"
            "    async with asyncio.TaskGroup() as group:\n"
            "        group.create_task(run_async_job())\n"
        )
        self.assertEqual(self.capture("scope", "create", file), QUALITY.QualityResult())
        file.parent.mkdir()
        file.write_text(source, encoding="utf-8")
        advice = self.after("scope", "create").advisory or ""
        for line, rule in ((5, "F631"), (6, "PT012"), (11, "RUF006")):
            self.assertIn(f"jobs/test_worker.py:{line} — Python {rule}", advice)
            self.assertEqual(advice.count(rule), 1)
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

        self.assertEqual(self.capture("scope", "unrelated", file), QUALITY.QualityResult())
        file.write_text(source + "\nmax_attempts = 2\n", encoding="utf-8")
        self.assertEqual(self.after("scope", "unrelated"), QUALITY.QualityResult())

    def test_async_assertions_report_only_discarded_results_in_jest_and_vitest_tests(self) -> None:
        self.scanners[1].side_effect = NODE_FINDINGS
        for name, imports in (
            ("worker.test.ts", "import { expect, test } from '@jest/globals';\n"),
            ("worker.spec.js", "import { expect, test } from 'vitest';\n"),
            ("__tests__/worker.ts", ""),
        ):
            with self.subTest(name=name):
                file = self.workspace / name
                file.parent.mkdir(exist_ok=True)
                source = imports + (
                    "test('ошибка', async () => { expect(runJob()).rejects.toThrow(); });\n"
                    "test('awaited', async () => { await (expect(runJob()).rejects.toThrow()); });\n"
                    "test('returned', () => expect(runJob()).rejects.toThrow());\n"
                    "test('held', async () => {\n"
                    "    const pending =\n"
                    "        expect(runJob()).rejects.toThrow();\n"
                    "    await pending;\n"
                    "});\n"
                )
                if "vitest" in imports:
                    source += (
                        "test('getter assertion', () => { expect(true).to.be.true; });\n"
                        "test('unawaited without semicolons', () => {\n"
                        "    prepare()\n"
                        "    expect(runJob()).resolves.toBe(true)\n"
                        "})\n"
                    )
                self.assertEqual(self.capture("scope", f"create-{name}", file), QUALITY.QualityResult())
                file.write_text(source, encoding="utf-8")
                advice = self.after("scope", f"create-{name}").advisory or ""
                self.assertIn(f"{name}:{2 if imports else 1} — JavaScript valid-expect", advice)
                if "vitest" in imports:
                    self.assertIn(f"{name}:13 — JavaScript valid-expect", advice)
                self.assertEqual(advice.count("valid-expect"), 2 if "vitest" in imports else 1)
                self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

                self.assertEqual(self.capture("scope", f"unrelated-{name}", file), QUALITY.QualityResult())
                file.write_text(source + "\nconst fixtureSize = 2;\n", encoding="utf-8")
                self.assertEqual(self.after("scope", f"unrelated-{name}"), QUALITY.QualityResult())

    def test_async_assertion_rule_ignores_non_test_files_and_jsx_expressions(self) -> None:
        self.scanners[1].side_effect = NODE_FINDINGS
        file = self.workspace / "worker.ts"
        self.assertEqual(self.capture("scope", "create", file), QUALITY.QualityResult())
        file.write_text("expect(runJob()).rejects.toThrow();\n", encoding="utf-8")
        self.assertEqual(self.after("scope", "create"), QUALITY.QualityResult())

        test_file = self.workspace / "worker.test.tsx"
        self.assertEqual(self.capture("scope", "jsx", test_file), QUALITY.QualityResult())
        test_file.write_text(
            "const child = <Result>{expect(runJob()).rejects.toThrow()}</Result>;\n",
            encoding="utf-8",
        )
        self.assertEqual(self.after("scope", "jsx"), QUALITY.QualityResult())

    def test_shellcheck_reports_masked_failures_only_for_applicable_shells(self) -> None:
        script = 'check() { local data="$(generate)"; }\n'
        file = self.workspace / "new" / "release.sh"
        self.assertEqual(self.capture("shell", "create", file), QUALITY.QualityResult())
        file.parent.mkdir()
        file.write_text("#!/usr/bin/env bash\n" + script, encoding="utf-8")
        with mock.patch.dict(os.environ, {"SHELLCHECK_OPTS": "--exclude=SC2155"}):
            advice = self.after("shell", "create").advisory or ""
        self.assertIn("new/release.sh:2 — ShellCheck SC2155", advice)
        self.assertEqual(self.completion("shell"), QUALITY.QualityResult())

        self.assertEqual(self.capture("shell", "unrelated", file), QUALITY.QualityResult())
        with file.open("a", encoding="utf-8") as stream:
            stream.write("printf 'release\n'\n")
        self.assertEqual(self.after("shell", "unrelated"), QUALITY.QualityResult())

        for name, shebang in (("release.zsh", "#!/bin/zsh\n"), ("other.sh", "#!/bin/zsh\n")):
            with self.subTest(name=name):
                file = self.workspace / name
                self.assertEqual(self.capture("shell", name, file), QUALITY.QualityResult())
                file.write_text(shebang + script, encoding="utf-8")
                self.assertEqual(self.after("shell", name), QUALITY.QualityResult())

        broken = self.workspace / "broken.bash"
        self.assertEqual(self.capture("shell", "malformed", broken), QUALITY.QualityResult())
        broken.write_text("if true; then\n", encoding="utf-8")
        self.assertIn("ShellCheck SC1073", self.after("shell", "malformed").advisory or "")

    def test_source_syntax_is_advisory_on_first_write(self) -> None:
        self.scanners[0].side_effect = PYTHON_FINDINGS
        self.scanners[1].side_effect = NODE_FINDINGS
        cases = {
            ".py": ("value = None\nresult = )\n", "Python"),
            ".pyi": ("def result( -> None: ...\n", "Python"),
            ".js": ("const result = ;\n", "JavaScript"),
            ".tsx": ("const result = <span>\n", "TypeScript"),
            ".mts": ("export const result: number = ;\n", "TypeScript"),
            ".cts": ("export const result: number = ;\n", "TypeScript"),
        }
        for extension, (source, language) in cases.items():
            with self.subTest(extension=extension):
                path = self.workspace / "new" / f"worker{extension}"
                self.assertEqual(self.capture(extension, "create", path), QUALITY.QualityResult())
                path.parent.mkdir(exist_ok=True)
                path.write_text(source, encoding="utf-8")
                result = self.after(extension, "create")
                self.assertIn(f"worker{extension}:", result.advisory or "")
                self.assertIn(f"{language} syntax error", result.advisory or "")
                self.assertIsNone(result.block_reason)
                self.assertEqual(self.completion(extension), QUALITY.QualityResult())

    def test_go_syntax_checks_a_complete_file_without_formatting(self) -> None:
        path = self.workspace / "worker.go"
        self.assertEqual(self.capture("go", "create", path), QUALITY.QualityResult())
        path.write_text("func run() {}\n", encoding="utf-8")
        self.assertIn("worker.go:1 — Go syntax error", self.after("go", "create").advisory or "")
        self.assertEqual(self.completion("go"), QUALITY.QualityResult())

        self.assertEqual(self.capture("go", "repair", path), QUALITY.QualityResult())
        valid = "package jobs\nfunc run(){println(1)}\n"
        path.write_text(valid, encoding="utf-8")
        self.assertEqual(self.after("go", "repair"), QUALITY.QualityResult())
        self.assertEqual(path.read_text(encoding="utf-8"), valid)

    def test_dart_syntax_is_reviewed_without_formatting(self) -> None:
        path = self.workspace / "worker.dart"
        self.assertEqual(self.capture("dart", "create", path), QUALITY.QualityResult())
        source = "void main() {\n  final result = ;\n}\n"
        path.write_text(source, encoding="utf-8")
        failed_parse = subprocess.CompletedProcess(
            ["dart", "format"], 65, "",
            "Could not format because the source could not be parsed:\n\n"
            "line 2, column 18 of source.dart: Expected an identifier.\n",
        )
        # The Dart SDK is optional. Keep the detector contract exercised in CI
        # even on a host without a Dart installation.
        with (
            mock.patch.object(QUALITY.shutil, "which", return_value="/usr/bin/dart"),
            mock.patch.object(QUALITY.subprocess, "run", return_value=failed_parse) as run,
        ):
            self.assertIn("worker.dart:2 — Dart syntax error", self.after("dart", "create").advisory or "")
        self.assertEqual(run.call_args.args[0][1:4], ["--suppress-analytics", "format", "--output=none"])
        self.assertEqual(path.read_text(encoding="utf-8"), source)
        self.assertEqual(self.completion("dart"), QUALITY.QualityResult())

    def test_rust_syntax_is_advisory_on_the_first_write_without_cargo(self) -> None:
        path = self.workspace / "new" / "worker.rs"
        source = "pub fn run() {\n    let count = 3\n}\n"
        self.assertEqual(self.capture("rust", "create", path), QUALITY.QualityResult())
        path.parent.mkdir()
        path.write_text(source, encoding="utf-8")
        advice = self.after("rust", "create").advisory or ""
        self.assertIn("new/worker.rs:2 — Rust syntax error", advice)
        self.assertNotIn("count", advice)
        self.assertEqual(path.read_text(encoding="utf-8"), source)
        self.assertEqual(self.completion("rust"), QUALITY.QualityResult())

        self.assertEqual(self.capture("rust", "unrelated", path), QUALITY.QualityResult())
        path.write_text("\n" + source, encoding="utf-8")
        self.assertEqual(self.after("rust", "unrelated"), QUALITY.QualityResult())

        self.assertEqual(self.capture("rust", "repair", path), QUALITY.QualityResult())
        valid = (
            '#[path = "missing.rs"] mod external;\n'
            'unsafe extern "C" { safe fn tick(); }\n'
            'fn work(){let _=1;}\n'
        )
        path.write_text(valid, encoding="utf-8")
        self.assertEqual(self.after("rust", "repair"), QUALITY.QualityResult())
        self.assertEqual(path.read_text(encoding="utf-8"), valid)

    def test_rust_syntax_uses_the_inherited_cargo_edition(self) -> None:
        root_manifest = self.workspace / "Cargo.toml"
        root_manifest.write_text(
            '[workspace]\nmembers = ["crates/worker"]\n[workspace.package]\nedition = "2021"\n',
            encoding="utf-8",
        )
        crate = self.workspace / "crates" / "worker"
        path = crate / "src" / "lib.rs"
        path.parent.mkdir(parents=True)
        (crate / "Cargo.toml").write_text(
            '[package]\nname = "worker"\nedition.workspace = true\n', encoding="utf-8",
        )
        self.assertEqual(self.capture("rust", "create", path), QUALITY.QualityResult())
        path.write_text("fn gen() {}\n", encoding="utf-8")
        self.assertEqual(self.after("rust", "create"), QUALITY.QualityResult())

        self.assertEqual(self.capture("rust", "replace", path), QUALITY.QualityResult())
        path.write_text("fn run() {\n    let count = ;\n}\n", encoding="utf-8")
        self.assertIn("lib.rs:2 — Rust syntax error", self.after("rust", "replace").advisory or "")

    def test_missing_rustfmt_warns_once_without_blocking(self) -> None:
        path = self.workspace / "worker.rs"
        with (
            mock.patch.object(QUALITY.shutil, "which", return_value=None),
            mock.patch.dict(os.environ, {"RUSTUP_HOME": str(self.root / "missing-rustup")}),
        ):
            self.assertEqual(self.capture("rust", "create", path), QUALITY.QualityResult())
            path.write_text("fn run() {}\n", encoding="utf-8")
            self.assertIn("rustfmt", self.after("rust", "create").advisory or "")
            self.assertEqual(self.capture("rust", "repeat", path), QUALITY.QualityResult())
            path.write_text("fn second() {}\n", encoding="utf-8")
            self.assertEqual(self.after("rust", "repeat"), QUALITY.QualityResult())
            self.assertEqual(self.completion("rust"), QUALITY.QualityResult())

    def test_node_module_extensions_keep_security_and_test_checks(self) -> None:
        self.scanners[1].side_effect = NODE_FINDINGS
        self.scanners[2].side_effect = SEMGREP_SECURITY_FINDINGS
        source = (
            'const agent = new https.Agent({ rejectUnauthorized: false });\n'
            'eval(input);\n'
            'test("rejects", () => {\n'
            '    expect(run()).rejects.toThrow();\n'
            '});\n'
        )
        for extension in (".mts", ".cts"):
            with self.subTest(extension=extension):
                path = self.workspace / f"worker.test{extension}"
                self.assertEqual(self.capture(extension, "create", path), QUALITY.QualityResult())
                path.write_text(source, encoding="utf-8")
                advice = self.after(extension, "create").advisory or ""
                self.assertIn("JavaScript security: eval()", advice)
                self.assertIn("TLS verification disabled", advice)
                self.assertIn("the test discards an async assertion", advice)
                self.assertIn("JavaScript security: eval()", self.completion(extension).block_reason or "")

    def test_syntax_error_does_not_clear_an_attributed_security_finding(self) -> None:
        self.scanners[0].side_effect = PYTHON_FINDINGS
        self.scanners[1].side_effect = NODE_FINDINGS
        for extension, risky, malformed, label in (
            (".py", "eval(user_input)\n", "result = )\n", "Python security S307"),
            (".mts", "eval(userInput);\n", "const result = ;\n", "JavaScript security: eval()"),
        ):
            with self.subTest(extension=extension):
                path = self.workspace / f"worker{extension}"
                self.assertEqual(self.capture(extension, "introduce", path), QUALITY.QualityResult())
                path.write_text(risky, encoding="utf-8")
                self.assertIn(label, self.after(extension, "introduce").advisory or "")

                self.assertEqual(self.capture(extension, "break", path), QUALITY.QualityResult())
                path.write_text(risky + malformed, encoding="utf-8")
                self.assertIn("syntax error", self.after(extension, "break").advisory or "")
                self.assertIsNone(self.completion(extension).block_reason)

                self.capture(extension, "repair", path)
                path.write_text(risky, encoding="utf-8")
                self.assertEqual(self.after(extension, "repair"), QUALITY.QualityResult())
                self.assertIn(label, self.completion(extension).block_reason or "")

                scope = extension + "-repair"
                self.assertEqual(self.capture(scope, "malformed", path), QUALITY.QualityResult())
                path.write_text(malformed, encoding="utf-8")
                self.after(scope, "malformed")
                self.assertEqual(self.capture(scope, "first-valid", path), QUALITY.QualityResult())
                path.write_text(risky, encoding="utf-8")
                self.assertIn(label, self.after(scope, "first-valid").advisory or "")
                self.assertIn(label, self.completion(scope).block_reason or "")

    def test_config_duplicate_keys_on_first_write_and_unrelated_edits(self) -> None:
        cases = {
            "config.json": ('{"limits": {"workers": 4, "workers": 400}, "keep": 1}\n', "JSON"),
            "config.yml": ("limits:\n  workers: 4\n  workers: 400\nkeep: 1\n", "YAML"),
            "config.yaml": (
                'limits: {workers: 4, "workers": 400}\n'
                '? "multi\\nline"\n: first\n? "multi\\nline"\n: second\nkeep: 1\n',
                "YAML",
            ),
            "config.toml": ("keep = 1\n[limits]\nworkers = 4\nworkers = 400\n", "TOML"),
        }
        for name, (source, language) in cases.items():
            with self.subTest(name=name):
                path = self.workspace / "config" / name
                self.assertEqual(self.capture(name, "create", path), QUALITY.QualityResult())
                path.parent.mkdir(exist_ok=True)
                path.write_text(source, encoding="utf-8")
                advice = self.after(name, "create").advisory or ""
                self.assertIn(f"config/{name}", advice)
                self.assertIn(f"{language} duplicate key", advice)
                if name == "config.yaml":
                    self.assertEqual(advice.count("YAML duplicate key"), 2)
                self.assertNotIn("workers", advice)
                self.assertEqual(self.completion(name), QUALITY.QualityResult())

                self.assertEqual(self.capture(name, "unrelated", path), QUALITY.QualityResult())
                path.write_text(source.replace("1", "2"), encoding="utf-8")
                self.assertEqual(self.after(name, "unrelated"), QUALITY.QualityResult())

    def test_json_with_comments_checks_duplicate_keys_without_style_warnings(self) -> None:
        path = self.workspace / "tsconfig.app.json"
        self.assertEqual(self.capture("tsconfig", "create", path), QUALITY.QualityResult())
        valid = '{ // build settings\n "include": ["src/**"], /* sources */\n}\n'
        path.write_text(valid, encoding="utf-8")
        self.assertEqual(self.after("tsconfig", "create"), QUALITY.QualityResult())

        self.assertEqual(self.capture("tsconfig", "duplicate", path), QUALITY.QualityResult())
        path.write_text(valid.replace(' "include"', ' "include": [],\n "include"'), encoding="utf-8")
        self.assertIn("JSON duplicate key", self.after("tsconfig", "duplicate").advisory or "")

    def test_config_scopes_and_yaml_document_boundaries(self) -> None:
        cases = {
            "config.json": '{"a": {"name": "a"}, "b": {"name": "b"}}\n',
            "config.yaml": (
                "on: &defaults {name: a}\n"
                "jobs: {<<: *defaults, name: b}\n"
                "child: !reference [job, script]\n"
                "---\non: {name: c}\n"
            ),
            "config.toml": '[[jobs]]\nname = "a"\n[[jobs]]\nname = "b"\n',
        }
        for name, source in cases.items():
            with self.subTest(name=name):
                path = self.workspace / name
                self.assertEqual(self.capture(name, "create", path), QUALITY.QualityResult())
                path.write_text(source, encoding="utf-8")
                self.assertEqual(self.after(name, "create"), QUALITY.QualityResult())

    def test_helm_template_is_not_mistaken_for_plain_yaml(self) -> None:
        chart = self.workspace / "chart"
        path = chart / "templates" / "deployment.yaml"
        path.parent.mkdir(parents=True)
        (chart / "Chart.yaml").write_text("name: sample\n", encoding="utf-8")
        self.assertEqual(self.capture("helm", "create", path), QUALITY.QualityResult())
        path.write_text("{{- if .Values.enabled }}\nkind: Deployment\n{{- end }}\n", encoding="utf-8")
        self.assertEqual(self.after("helm", "create"), QUALITY.QualityResult())

    def test_config_syntax_is_reported_from_first_write(self) -> None:
        for filename, text, label in (
            ("settings.json", "", "JSON syntax error"),
            ("settings.yml", "items: [1, 2\n", "YAML syntax error"),
            ("settings.toml", "items = [1, 2\n", "TOML syntax error"),
        ):
            with self.subTest(filename=filename):
                path = self.workspace / filename
                self.assertEqual(self.capture(filename, "create", path), QUALITY.QualityResult())
                path.write_text(text, encoding="utf-8")
                self.assertIn(label, self.after(filename, "create").advisory or "")
                self.assertEqual(self.completion(filename), QUALITY.QualityResult())

    def test_actionlint_checks_workflows_from_first_write(self) -> None:
        source = (
            "on: [push]\n"
            "jobs:\n"
            "  build:\n"
            "    runs-on: custom-self-hosted\n"
            "    needs: [absent]\n"
            "    steps:\n"
            "      - run: echo build\n"
        )
        file = self.workspace / ".github" / "workflows" / "release.yml"
        self.assertEqual(self.capture("workflow", "create", file), QUALITY.QualityResult())
        file.parent.mkdir(parents=True)
        file.write_text("on: [push]\n" + source, encoding="utf-8")
        advice = self.after("workflow", "create").advisory or ""
        self.assertIn(".github/workflows/release.yml:4 — actionlint", advice)
        self.assertIn(".github/workflows/release.yml:2 — YAML duplicate key", advice)
        self.assertIn("job dependency is missing or cyclic", advice)
        self.assertNotIn("custom-self-hosted", advice)
        self.assertEqual(self.completion("workflow"), QUALITY.QualityResult())

        other = self.workspace / "app.yml"
        self.assertEqual(self.capture("workflow", "other", other), QUALITY.QualityResult())
        other.write_text(source, encoding="utf-8")
        self.assertEqual(self.after("workflow", "other"), QUALITY.QualityResult())

    def test_unavailable_file_analyzer_is_reported_once_and_never_blocks(self) -> None:
        file = self.workspace / "release.bash"
        with mock.patch.object(QUALITY, "_run_review_tool", side_effect=RuntimeError("offline")):
            self.assertEqual(self.capture("shell", "first", file), QUALITY.QualityResult())
            file.write_text("cd target\n", encoding="utf-8")
            self.assertIn("shellcheck review was unavailable", self.after("shell", "first").advisory or "")
            self.assertEqual(self.capture("shell", "second", file), QUALITY.QualityResult())
            file.write_text("cd other\n", encoding="utf-8")
            self.assertEqual(self.after("shell", "second"), QUALITY.QualityResult())
            self.assertEqual(self.completion("shell"), QUALITY.QualityResult())

    def test_kubernetes_checks_plain_workloads_and_skips_overlay_patches(self) -> None:
        workload = (
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: worker\n"
            "spec:\n  selector:\n    matchLabels:\n      app: worker\n"
            "  template:\n    metadata:\n      labels:\n        app: worker\n"
            "    spec:\n      containers:\n        - name: worker\n          image: worker:1\n"
        )
        file = self.workspace / "deploy" / "worker.yaml"
        self.assertEqual(self.capture("kube", "create", file), QUALITY.QualityResult())
        file.parent.mkdir()
        file.write_text(workload, encoding="utf-8")
        advice = self.after("kube", "create").advisory or ""
        self.assertIn("deploy/worker.yaml — KubeLinter no-readiness-probe", advice)
        self.assertEqual(self.completion("kube"), QUALITY.QualityResult())

        self.assertEqual(self.capture("kube", "unrelated", file), QUALITY.QualityResult())
        file.write_text(workload.replace("worker:1", "worker:2"), encoding="utf-8")
        self.assertEqual(self.after("kube", "unrelated"), QUALITY.QualityResult())

        patch = self.workspace / "overlays" / "stage" / "worker.yaml"
        self.assertEqual(self.capture("kube", "patch", patch), QUALITY.QualityResult())
        patch.parent.mkdir(parents=True)
        patch.write_text(workload, encoding="utf-8")
        self.assertEqual(self.after("kube", "patch"), QUALITY.QualityResult())

        renamed_selector = workload.replace("app: worker", "app: another-worker", 1)
        self.assertEqual(self.capture("kube", "selector", file), QUALITY.QualityResult())
        file.write_text(renamed_selector, encoding="utf-8")
        advice = self.after("kube", "selector").advisory or ""
        self.assertIn("KubeLinter mismatching-selector", advice)
        self.assertNotIn("no-readiness-probe", advice)

        invalid = self.workspace / "values.yaml"
        config = "apiVersion: apps/v1\n---\nkind: Deployment\n  containers: []\n"
        self.assertEqual(self.capture("kube", "plain-yaml", invalid), QUALITY.QualityResult())
        invalid.write_text(config, encoding="utf-8")
        with mock.patch.object(QUALITY, "_run_review_tool", side_effect=AssertionError("unexpected tool")):
            self.assertIn("YAML syntax error", self.after("kube", "plain-yaml").advisory or "")

    def test_squawk_checks_recognized_postgresql_migrations_on_first_edit(self) -> None:
        root = self.workspace / "service" / "prisma" / "migrations"
        root.mkdir(parents=True)
        (root / "migration_lock.toml").write_text('provider = "postgresql"\n', encoding="utf-8")
        file = root / "20261113000000_drop_job_data" / "migration.sql"
        self.assertEqual(self.capture("sql", "first", file), QUALITY.QualityResult())
        file.parent.mkdir()
        file.write_text("DROP TABLE history;\n", encoding="utf-8")
        advice = self.after("sql", "first").advisory or ""
        self.assertIn("migration.sql:1 — Squawk ban-drop-table", advice)
        self.assertNotIn("ban-drop-table: DROP", advice)
        self.assertEqual(self.completion("sql"), QUALITY.QualityResult())

        self.assertEqual(self.capture("sql", "another", file), QUALITY.QualityResult())
        file.write_text("DROP TABLE history;\nCREATE INDEX idx_status ON jobs (status);\n", encoding="utf-8")
        advice = self.after("sql", "another").advisory or ""
        self.assertIn("Squawk require-concurrent-index-creation", advice)
        self.assertNotIn("Squawk ban-drop-table", advice)

        other = self.workspace / "clickhouse" / "migrations" / "0001_remove_table.sql"
        self.assertEqual(self.capture("sql", "other", other), QUALITY.QualityResult())
        other.parent.mkdir(parents=True)
        other.write_text("DROP TABLE history;\n", encoding="utf-8")
        self.assertEqual(self.after("sql", "other"), QUALITY.QualityResult())

    def test_postgresql_migration_detection_uses_existing_dialect_metadata(self) -> None:
        drizzle = self.workspace / "db" / "drizzle"
        (drizzle / "meta").mkdir(parents=True)
        (drizzle / "meta" / "_journal.json").write_text('{"dialect": "postgresql"}', encoding="utf-8")
        file = drizzle / "0000_truncate.sql"
        self.assertEqual(self.capture("sql", "drizzle", file), QUALITY.QualityResult())
        file.write_text("TRUNCATE TABLE events CASCADE;\n", encoding="utf-8")
        self.assertIn("Squawk ban-truncate-cascade", self.after("sql", "drizzle").advisory or "")

        css = self.workspace / "migrations"
        css.mkdir()
        (self.workspace / "go.mod").write_text(
            "module icover-vozvrat\n\nrequire (\n\tgithub.com/jackc/pgx/v5 v5.11.0\n)\n", encoding="utf-8",
        )
        (css / "migrations.go").write_text("package migrations\n\n//go:embed *.sql\n", encoding="utf-8")
        file = css / "0127_online_index.sql"
        self.assertEqual(self.capture("sql", "css", file), QUALITY.QualityResult())
        file.write_text("CREATE INDEX idx ON events (status);\n", encoding="utf-8")
        self.assertIn("Squawk require-concurrent-index-creation", self.after("sql", "css").advisory or "")
        self.assertEqual(self.capture("sql", "css-explicit-transaction", file), QUALITY.QualityResult())
        file.write_text("BEGIN;\nCREATE INDEX CONCURRENTLY idx ON events (status);\nCOMMIT;\n", encoding="utf-8")
        self.assertIn("Squawk ban-concurrent-index-creation-in-transaction",
                      self.after("sql", "css-explicit-transaction").advisory or "")
        self.assertEqual(self.capture("sql", "rewrite", file), QUALITY.QualityResult())
        file.write_text("ALTER TABLE events ALTER COLUMN status TYPE bigint USING status::bigint;\n",
                        encoding="utf-8")
        self.assertIn("Squawk changing-column-type", self.after("sql", "rewrite").advisory or "")

        raw = drizzle / "0001_invalid.sql"
        self.assertEqual(self.capture("sql", "invalid", raw), QUALITY.QualityResult())
        raw.write_text("CREATE INDEX broken\n", encoding="utf-8")
        advice = self.after("sql", "invalid").advisory or ""
        self.assertIn("0001_invalid.sql:1 — Squawk syntax-error", advice)
        self.assertEqual(advice.count("Squawk syntax-error"), 1)
        self.assertNotIn("more findings", advice)
        self.assertIn("parser", advice)
        self.assertNotIn("review was unavailable", advice)
        self.assertEqual(self.completion("sql"), QUALITY.QualityResult())

    def test_index_rebuild_and_name_advice_is_new_attributed_and_nonblocking(self) -> None:
        root = self.workspace / "prisma" / "migrations"
        root.mkdir(parents=True)
        (root / "migration_lock.toml").write_text('provider = "postgresql"\n')
        cases = (
            ("rebuild", "REINDEX INDEX events_status_idx;", "require-concurrent-reindex"),
            ("rebuild_table", "REINDEX TABLE events;", "require-concurrent-reindex"),
            ("long_name", "CREATE INDEX CONCURRENTLY " + "i" * 64 + " ON events (id);", "identifier-too-long"),
            ("unicode_name", 'CREATE INDEX CONCURRENTLY "' + "я" * 32 + '" ON events (id);', "identifier-too-long"),
            ("rebuild_transaction", "BEGIN; REINDEX INDEX CONCURRENTLY events_idx; COMMIT;", "ban-concurrent-index-creation-in-transaction"),
        )
        for name, statement, rule in cases:
            with self.subTest(case=name):
                file = root / f"20261116000000_{name}" / "migration.sql"
                file.parent.mkdir()
                self.capture(name, "create", file)
                file.write_text("SET lock_timeout = '1s';\n" + statement + "\n")
                result = self.after(name, "create")
                advice = result.advisory or ""
                self.assertIn(f"migration.sql:2 — Squawk {rule}", advice)
                self.assertLessEqual(len(advice), QUALITY.MAX_ADVISORY_CHARS)
                self.assertIsNone(result.block_reason)
                self.assertEqual(self.completion(name), QUALITY.QualityResult())
                if name == "rebuild_transaction":
                    self.assertIn("concurrent index operation", advice)
                    self.assertNotIn("CREATE INDEX CONCURRENTLY cannot", advice)
                self.capture(name, "unrelated", file)
                file.write_text(file.read_text() + "-- unrelated comment\n")
                self.assertEqual(self.after(name, "unrelated"), QUALITY.QualityResult())

    def test_index_safe_forms_byte_boundaries_and_ignores_stay_silent(self) -> None:
        root = self.workspace / "prisma" / "migrations"
        root.mkdir(parents=True)
        (root / "migration_lock.toml").write_text('provider = "postgresql"\n')
        statements = (
            "REINDEX INDEX CONCURRENTLY events_idx;",
            "REINDEX TABLE CONCURRENTLY events;",
            "REINDEX SYSTEM app;",
            "CREATE INDEX CONCURRENTLY " + "i" * 63 + " ON events (id);",
            'CREATE INDEX CONCURRENTLY "' + "я" * 31 + 'x" ON events (id);',
            "-- squawk-ignore require-concurrent-reindex\nREINDEX INDEX events_idx;",
            "-- squawk-ignore identifier-too-long\nCREATE INDEX CONCURRENTLY " + "i" * 64 + " ON events (id);",
            "SELECT 'REINDEX INDEX events_idx; " + "i" * 64 + "';",
            "-- REINDEX INDEX events_idx;\nSELECT 1;",
        )
        for index, statement in enumerate(statements):
            with self.subTest(case=index):
                file = root / f"20261116000000_safe_{index}" / "migration.sql"
                file.parent.mkdir()
                self.capture("safe-index", str(index), file)
                file.write_text("SET lock_timeout = '1s';\n" + statement + "\n")
                self.assertEqual(self.after("safe-index", str(index)), QUALITY.QualityResult())

    def test_sql_parse_advice_repeats_silently_and_clears_after_repair(self) -> None:
        root = self.workspace / "db" / "meta"
        root.mkdir(parents=True)
        (root / "_journal.json").write_text('{"dialect": "postgresql"}')
        file = root.parent / "0000_index.sql"
        self.capture("sql-parse", "create", file)
        file.write_text("CREATE INDEX CONCURRENTLY idx ON events (id,);\n")
        advice = self.after("sql-parse", "create").advisory or ""
        self.assertIn("0000_index.sql:1 — Squawk syntax-error", advice)
        self.assertIn("parser", advice)
        self.assertNotIn("review was unavailable", advice)
        self.assertEqual(self.completion("sql-parse"), QUALITY.QualityResult())
        self.capture("sql-parse", "unchanged", file)
        self.assertEqual(self.after("sql-parse", "unchanged"), QUALITY.QualityResult())
        self.capture("sql-parse", "repair", file)
        file.write_text("SET lock_timeout = '1s';\nCREATE INDEX CONCURRENTLY idx ON events (id);\n")
        self.assertEqual(self.after("sql-parse", "repair"), QUALITY.QualityResult())

    def test_index_checks_skip_unidentified_sql_and_preserve_scanner_failure(self) -> None:
        paths = (
            self.workspace / "clickhouse" / "0000_index.sql",
            self.workspace / "schema.sql",
            self.workspace / "prisma" / "migrations" / "20261116000000_index" / "migration.sql",
        )
        for index, file in enumerate(paths):
            file.parent.mkdir(parents=True, exist_ok=True)
            self.capture("other-dialect", str(index), file)
            file.write_text("REINDEX INDEX events_idx;\n")
            with mock.patch.object(QUALITY, "_run_review_tool", side_effect=AssertionError("wrong dialect")):
                self.assertEqual(self.after("other-dialect", str(index)), QUALITY.QualityResult())

        root = self.workspace / "db" / "meta"
        root.mkdir(parents=True)
        (root / "_journal.json").write_text('{"dialect": "postgresql"}')
        for index, error in enumerate((ValueError("bad JSON"), subprocess.TimeoutExpired("squawk", 1))):
            file = root.parent / f"000{index}_index.sql"
            self.capture(f"outage-{index}", "create", file)
            file.write_text("REINDEX INDEX events_idx;\n")
            with mock.patch.object(QUALITY, "_run_review_tool", side_effect=error):
                advice = self.after(f"outage-{index}", "create").advisory or ""
            self.assertIn("squawk review was unavailable", advice)
            self.assertNotIn("Squawk syntax-error", advice)
            self.assertEqual(self.completion(f"outage-{index}"), QUALITY.QualityResult())

    def test_online_postgresql_risks_are_advisory_on_the_first_edit(self) -> None:
        root = self.workspace / "prisma" / "migrations"
        root.mkdir(parents=True)
        (root / "migration_lock.toml").write_text('provider = "postgresql"\n')
        cases = (
            ("index", "CREATE INDEX idx ON events (status);", "require-concurrent-index-creation"),
            ("drop_index", "DROP INDEX idx;", "require-concurrent-index-deletion"),
            ("check", "ALTER TABLE events ADD CONSTRAINT valid CHECK (status IS NOT NULL);", "constraint-missing-not-valid"),
            ("foreign_key", "ALTER TABLE events ADD CONSTRAINT owner_fk FOREIGN KEY (owner_id) REFERENCES owners (id);", "constraint-missing-not-valid"),
            ("unique", "ALTER TABLE events ADD CONSTRAINT unique_status UNIQUE (status);", "disallowed-unique-constraint"),
            ("not_null", "ALTER TABLE events ALTER COLUMN status SET NOT NULL;", "adding-not-nullable-field"),
            ("required", "ALTER TABLE events ADD COLUMN status text NOT NULL;", "adding-required-field"),
            ("volatile_default", "ALTER TABLE events ADD COLUMN token uuid DEFAULT gen_random_uuid();", "adding-field-with-default"),
            ("rename_column", "ALTER TABLE events RENAME COLUMN status TO state;", "renaming-column"),
            ("rename_table", "ALTER TABLE events RENAME TO records;", "renaming-table"),
        )
        for name, statement, rule in cases:
            with self.subTest(rule=rule, name=name):
                file = root / f"20261115000000_{name}" / "migration.sql"
                file.parent.mkdir()
                self.capture(name, "create", file)
                file.write_text("SET lock_timeout = '1s';\n" + statement + "\n")
                advice = self.after(name, "create").advisory or ""
                self.assertIn(f"migration.sql:2 — Squawk {rule}", advice)
                self.assertEqual(self.completion(name), QUALITY.QualityResult())
                self.capture(name, "unchanged", file)
                self.assertEqual(self.after(name, "unchanged"), QUALITY.QualityResult())

    def test_postgresql_lock_timeout_and_safe_alternatives(self) -> None:
        root = self.workspace / "prisma" / "migrations"
        root.mkdir(parents=True)
        (root / "migration_lock.toml").write_text('provider = "postgresql"\n')
        for name, prefix in (("missing", ""), ("zero", "SET lock_timeout = '0ms';\n")):
            with self.subTest(timeout=name):
                file = root / f"20261115000000_{name}" / "migration.sql"
                file.parent.mkdir()
                self.capture(name, "create", file)
                file.write_text(prefix + "ALTER TABLE events ADD COLUMN status text;\n")
                advice = self.after(name, "create").advisory or ""
                self.assertIn("Squawk require-lock-timeout", advice)
                self.assertIn("runner", advice)
                self.assertEqual(self.completion(name), QUALITY.QualityResult())

        safe = (
            "CREATE INDEX CONCURRENTLY idx ON events (status);",
            "DROP INDEX CONCURRENTLY idx;",
            "ALTER TABLE events ADD CONSTRAINT valid CHECK (status IS NOT NULL) NOT VALID;",
            "ALTER TABLE events ADD CONSTRAINT unique_status UNIQUE USING INDEX idx;",
            "ALTER TABLE events ADD COLUMN status text NOT NULL DEFAULT 'active';",
            "ALTER TABLE events ADD COLUMN status text;",
            "UPDATE events SET status = 'active' WHERE id = 42;",
            "BEGIN; CREATE TABLE new_events (id bigint PRIMARY KEY, status text); CREATE INDEX idx ON new_events (status); COMMIT;",
        )
        for index, statement in enumerate(safe):
            with self.subTest(safe_statement=statement):
                name = f"safe-{index}"
                file = root / f"20261115000000_safe_{index}" / "migration.sql"
                file.parent.mkdir()
                self.capture(name, "create", file)
                file.write_text("SET lock_timeout = '1s';\n" + statement + "\n")
                self.assertEqual(self.after(name, "create"), QUALITY.QualityResult())

    def test_scanner_outage_does_not_hardlock_and_recovery_revalidates(self) -> None:
        finding = QUALITY._occurrence(
            "Python security S307: dynamic eval()",
            1,
            "scanner",
            "eval(value)",
            channel=QUALITY._PYTHON_SECURITY_CHANNEL,
        )
        self.scanners[0].side_effect = lambda text, _path, **_options: [finding] if "eval(" in text else []
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "risk", file)
        file.write_text("eval(value)\n", encoding="utf-8")
        self.after("scope", "risk")

        self.scanners[0].side_effect = RuntimeError("temporary outage")
        unavailable = self.completion("scope")
        self.assertIn("Ruff safety rules", unavailable.advisory or "")
        self.assertIsNone(unavailable.block_reason)
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

        self.scanners[0].side_effect = lambda text, _path, **_options: [finding] if "eval(" in text else []
        recovered = self.completion("scope")
        self.assertIn("Completion blocked", recovered.block_reason or "")

    def test_semgrep_finding_is_advisory_and_never_enters_stop_state(self) -> None:
        def scan(text: str, _extension: str):
            if "rejectUnauthorized" not in text:
                return []
            return [
                QUALITY._occurrence(
                    "JavaScript security review: TLS verification disabled",
                    1,
                    "scanner",
                    "rejectUnauthorized: false",
                    channel=QUALITY._SEMGREP_SECURITY_CHANNEL,
                    blocking=False,
                )
            ]

        self.scanners[2].side_effect = scan
        file = self.workspace / "module.ts"
        file.write_text("const value = 1;\n", encoding="utf-8")
        self.capture("scope", "add-review", file)
        file.write_text(
            "const agent = new https.Agent({ rejectUnauthorized: false });\n",
            encoding="utf-8",
        )
        advisory = self.after("scope", "add-review")
        self.assertIn("Security review advice", advisory.advisory or "")
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_pgxpool_advice_reports_new_discarded_resources_from_the_first_write(self) -> None:
        file = self.workspace / "db" / "worker.go"
        source = (
            "package sample\n"
            'import p "github.com/jackc/pgx/v5/pgxpool"\n'
            "type Store struct { pool *p.Pool }\n"
            "func (s *Store) discardQuery() error {\n"
            '    _, err := s.pool.Query(ctx, "SELECT 1")\n'
            "    return err\n"
            "}\n"
            "func discardAssigned(pool *p.Pool) error {\n"
            '    rows, err := pool.Query(ctx, "SELECT 1")\n'
            "    _ = rows\n"
            "    return err\n"
            "}\n"
            "func discardConnection(pool *p.Pool) error {\n"
            "    _, err := pool.Acquire(ctx)\n"
            "    return err\n"
            "}\n"
            "func useRows(pool *p.Pool) error {\n"
            '    rows, err := pool.Query(ctx, "SELECT 1")\n'
            "    if err != nil { return err }\n"
            "    defer rows.Close()\n"
            "    for rows.Next() {}\n"
            "    return rows.Err()\n"
            "}\n"
            "func giveRowsToCaller(pool *p.Pool) (any, error) {\n"
            '    return pool.Query(ctx, "SELECT 1")\n'
            "}\n"
            "func useConnection(pool *p.Pool) error {\n"
            "    conn, err := pool.Acquire(ctx)\n"
            "    if err != nil { return err }\n"
            "    defer conn.Release()\n"
            "    return nil\n"
            "}\n"
        )
        self.assertEqual(self.capture("go", "create", file), QUALITY.QualityResult())
        file.parent.mkdir()
        file.write_text(source, encoding="utf-8")
        advice = self.after("go", "create").advisory or ""
        self.assertIn("db/worker.go:5 — Go pgxpool.Query", advice)
        self.assertIn("db/worker.go:9 — Go pgxpool.Query", advice)
        self.assertIn("db/worker.go:14 — Go pgxpool.Acquire", advice)
        self.assertEqual(advice.count(" — Go pgxpool."), 3)
        self.assertNotIn("SELECT", advice)
        self.assertEqual(self.completion("go"), QUALITY.QualityResult())

        self.assertEqual(self.capture("go", "unrelated", file), QUALITY.QualityResult())
        file.write_text(source + "\nconst limit = 5\n", encoding="utf-8")
        self.assertEqual(self.after("go", "unrelated"), QUALITY.QualityResult())

    def test_pgxpool_advice_skips_other_go_clients_without_invoking_semgrep(self) -> None:
        file = self.workspace / "other.go"
        self.assertEqual(self.capture("go", "create", file), QUALITY.QualityResult())
        file.write_text(
            'package other\nimport "example.invalid/pgxpool"\n'
            "func use(pool *pgxpool.Pool) error {\n"
            '    _, err := pool.Query(ctx, "SELECT 1")\n'
            "    return err\n"
            "}\n",
            encoding="utf-8",
        )
        with mock.patch.object(QUALITY, "_semgrep_findings") as scan:
            self.assertEqual(self.after("go", "create"), QUALITY.QualityResult())
            scan.assert_not_called()

    def test_file_growth_crossing_is_advisory_and_never_blocks(self) -> None:
        file = self.workspace / "service.go"
        file.write_text(source_lines(399), encoding="utf-8")
        self.capture("scope", "grow", file)
        file.write_text(source_lines(402), encoding="utf-8")

        result = self.after("scope", "grow")
        self.assertIn("Code structure review", result.advisory or "")
        self.assertIn("service.go", result.advisory or "")
        self.assertIn("399 -> 402", result.advisory or "")
        self.assertIsNone(result.block_reason)
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_existing_large_file_and_later_edits_stay_silent(self) -> None:
        file = self.workspace / "legacy.rs"
        file.write_text(source_lines(405), encoding="utf-8")
        self.capture("scope", "existing", file)
        file.write_text(source_lines(450), encoding="utf-8")
        self.assertEqual(self.after("scope", "existing"), QUALITY.QualityResult())

        crossing = self.workspace / "crossing.rs"
        crossing.write_text(source_lines(399), encoding="utf-8")
        self.capture("scope", "first", crossing)
        crossing.write_text(source_lines(401), encoding="utf-8")
        self.assertIn("Code structure review", self.after("scope", "first").advisory or "")
        self.capture("scope", "second", crossing)
        crossing.write_text(source_lines(500), encoding="utf-8")
        self.assertEqual(self.after("scope", "second"), QUALITY.QualityResult())

    def test_new_large_file_is_measured_from_zero(self) -> None:
        file = self.workspace / "new.swift"
        self.capture("scope", "create", file)
        file.write_text(source_lines(405), encoding="utf-8")
        result = self.after("scope", "create")
        self.assertIn("0 -> 405", result.advisory or "")

    def test_python_function_growth_is_advisory_without_storing_its_name(self) -> None:
        file = self.workspace / "service.py"
        before = "def private_business_rule():\n" + "    value = 1\n" * 58
        after = "def private_business_rule():\n" + "    value = 1\n" * 61
        file.write_text(before, encoding="utf-8")
        self.capture("scope", "function", file)

        state_file = QUALITY._state_path(
            "scope", self.workspace, "test-adapter", self.state
        )
        self.assertNotIn(
            "private_business_rule",
            state_file.read_text(encoding="utf-8"),
        )

        file.write_text(after, encoding="utf-8")
        result = self.after("scope", "function")
        self.assertIn("Python function", result.advisory or "")
        self.assertIn("`private_business_rule`", result.advisory or "")
        self.assertIn("59 -> 62", result.advisory or "")
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_unparseable_python_baseline_does_not_guess_function_growth(self) -> None:
        file = self.workspace / "broken.py"
        file.write_text("def broken(:\n", encoding="utf-8")
        self.capture("scope", "repair", file)
        file.write_text(
            "def repaired():\n" + "    value = 1\n" * 61,
            encoding="utf-8",
        )
        self.assertEqual(self.after("scope", "repair"), QUALITY.QualityResult())

    def test_sql_growth_and_failed_edit_do_not_warn(self) -> None:
        sql = self.workspace / "migration.sql"
        sql.write_text(source_lines(399), encoding="utf-8")
        self.capture("scope", "sql", sql)
        sql.write_text(source_lines(450), encoding="utf-8")
        self.assertEqual(self.after("scope", "sql"), QUALITY.QualityResult())

        file = self.workspace / "failed.go"
        file.write_text(source_lines(399), encoding="utf-8")
        self.capture("scope", "failed-growth", file)
        file.write_text(source_lines(450), encoding="utf-8")
        self.assertEqual(
            self.after("scope", "failed-growth", succeeded=False),
            QUALITY.QualityResult(),
        )

    def test_growth_advisory_is_bounded_for_a_multi_file_edit(self) -> None:
        paths = []
        for index in range(12):
            file = self.workspace / f"large_{index}.go"
            file.write_text(source_lines(399), encoding="utf-8")
            paths.append(file)
        self.capture("scope", "batch-growth", *paths)
        for file in paths:
            file.write_text(source_lines(401), encoding="utf-8")

        result = self.after("scope", "batch-growth")
        self.assertIn("… 6 more", result.advisory or "")
        self.assertLess(len(result.advisory or ""), 1200)
        self.assertIsNone(result.block_reason)

    def test_missing_security_scanner_warns_once_without_blocking(self) -> None:
        self.scanners[0].side_effect = RuntimeError("missing")
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")

        first = self.capture("scope", "first", file)
        self.assertIn("Ruff safety rules", first.advisory or "")
        self.assertIsNone(first.block_reason)
        self.after("scope", "first")

        second = self.capture("scope", "second", file)
        self.assertEqual(second, QUALITY.QualityResult())
        self.after("scope", "second")
        self.assertIsNone(self.completion("scope").block_reason)

    def test_scanner_parsers_keep_only_curated_security_rules(self) -> None:
        ruff_output = json.dumps(
            [
                {
                    "code": "S307",
                    "message": "Use of possibly insecure function",
                    "location": {"row": 2},
                    "end_location": {"row": 2},
                },
                {
                    "code": "F401",
                    "message": "Unused import",
                    "location": {"row": 1},
                    "end_location": {"row": 1},
                },
            ]
        )
        with mock.patch.object(QUALITY.shutil, "which", return_value="ruff"), mock.patch.object(
            QUALITY.subprocess,
            "run",
            return_value=QUALITY.subprocess.CompletedProcess([], 1, ruff_output, ""),
        ) as run:
            rows = PYTHON_FINDINGS("import os\neval(value)\n", self.workspace / "a.py")
        self.assertEqual([row.label for row in rows], ["Python security S307: dynamic eval()"])
        command = run.call_args.args[0]
        self.assertIn("--isolated", command)
        self.assertIn("--ignore-noqa", command)
        self.assertIn("--no-cache", command)

        oxlint_output = json.dumps(
            {
                "diagnostics": [
                    {
                        "code": "eslint(no-implied-eval)",
                        "message": "String evaluation",
                        "labels": [{"span": {"line": 1, "line_end": 1}}],
                    },
                    {
                        "code": "eslint(no-alert)",
                        "message": "Alert",
                        "labels": [{"span": {"line": 2, "line_end": 2}}],
                    },
                ]
            }
        )
        def oxlint_completed(command, **_kwargs):
            config = Path(command[command.index("--config") + 1])
            self.assertEqual(
                json.loads(config.read_text()),
                {
                    "globals": {
                        "setInterval": "readonly",
                        "setTimeout": "readonly",
                        "window": "readonly",
                    }
                },
            )
            return QUALITY.subprocess.CompletedProcess(command, 1, oxlint_output, "")

        with mock.patch.object(QUALITY.shutil, "which", return_value="oxlint"), mock.patch.object(
            QUALITY.subprocess,
            "run",
            side_effect=oxlint_completed,
        ) as run:
            rows = NODE_FINDINGS('setTimeout("work()", 1);\nalert(1);\n', self.workspace / "a.ts")
        self.assertEqual(
            [row.label for row in rows],
            ["JavaScript security: implicit string evaluation"],
        )
        command = run.call_args.args[0]
        self.assertIn("--disable-nested-config", command)
        self.assertIn("--no-ignore", command)

    def test_semgrep_prefilter_and_scanner_are_bounded_and_telemetry_free(self) -> None:
        self.assertFalse(QUALITY._semgrep_candidate("const value = 1;"))
        self.assertTrue(
            QUALITY._semgrep_candidate("child_process.exec(`echo ${value}`);")
        )
        self.assertTrue(
            QUALITY._semgrep_candidate("new https.Agent({ rejectUnauthorized: false })")
        )

        output = json.dumps(
            {
                "results": [
                    {
                        "check_id": "mainframe.javascript.tls-verification-disabled",
                        "start": {"line": 1},
                        "end": {"line": 1},
                    }
                ],
                "errors": [],
            }
        )

        def completed(command, **_kwargs):
            config = Path(command[command.index("--config") + 1])
            rule_ids = {rule["id"] for rule in json.loads(config.read_text())["rules"]}
            self.assertEqual(rule_ids, set(QUALITY._SEMGREP_LABELS))
            return QUALITY.subprocess.CompletedProcess(command, 0, output, "")

        with mock.patch.object(QUALITY.shutil, "which", return_value="semgrep"), mock.patch.object(
            QUALITY.subprocess,
            "run",
            side_effect=completed,
        ) as run:
            rows = SEMGREP_SECURITY_FINDINGS(
                "new https.Agent({ rejectUnauthorized: false });\n",
                ".js",
            )
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].blocking)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--metrics") + 1], "off")
        self.assertIn("--disable-version-check", command)
        self.assertNotIn("--experimental", command)
        self.assertEqual(command[command.index("--jobs") + 1], "1")

    def test_process_comments_are_targeted_not_generic(self) -> None:
        rows = QUALITY.scan_text(
            '"""Phase 2 of the compiler is stable."""\n'
            '# Why: the provider retries this status.\n'
            '# Step 2: finish the plan\n'
            'def work():\n'
            '    """As discussed, use the temporary route."""\n'
            '    return 1\n',
            ".py",
        )
        process = [row for row in rows if row.label == "temporary process comment"]
        self.assertEqual([row.line for row in process], [3, 5])

    def test_preexisting_debt_is_not_owned(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("# TODO: old debt\nvalue = 1\n", encoding="utf-8")
        self.assertEqual(self.capture("scope", "op", file), QUALITY.QualityResult())
        file.write_text("# TODO: old debt\nvalue = 2\n", encoding="utf-8")
        self.assertEqual(self.after("scope", "op"), QUALITY.QualityResult())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_new_finding_warns_once_and_blocks_completion(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "first", file)
        file.write_text("# TODO: implement real behavior\nvalue = 1\n", encoding="utf-8")
        result = self.after("scope", "first")
        self.assertIn("module.py:1", result.advisory or "")
        self.assertIn("TODO/FIXME/HACK/XXX", result.advisory or "")
        self.assertIsNone(result.block_reason)

        self.capture("scope", "second", file)
        file.write_text("# TODO: implement real behavior\nvalue = 2\n", encoding="utf-8")
        self.assertEqual(self.after("scope", "second"), QUALITY.QualityResult())

        blocked = self.completion("scope")
        self.assertIn("Completion blocked", blocked.block_reason or "")
        self.assertIn("module.py:1", blocked.block_reason or "")
        self.assertNotIn("implement real behavior", blocked.block_reason or "")

    def test_removing_finding_clears_state_and_allows_completion(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "add", file)
        file.write_text("# TODO: finish\nvalue = 1\n", encoding="utf-8")
        self.after("scope", "add")

        self.capture("scope", "remove", file)
        file.write_text("value = 1\n", encoding="utf-8")
        self.assertEqual(self.after("scope", "remove"), QUALITY.QualityResult())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())
        states = [json.loads(path.read_text()) for path in self.state.glob("*.json")]
        self.assertTrue(all(not state["findings"] and not state["pending"] for state in states))

    def test_changed_marker_remains_owned_even_when_category_count_is_equal(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("# TODO: unrelated old debt\n", encoding="utf-8")
        self.capture("scope", "replace", file)
        file.write_text("# TODO: newly deferred implementation\n", encoding="utf-8")
        result = self.after("scope", "replace")
        self.assertIn("TODO/FIXME/HACK/XXX", result.advisory or "")
        self.assertIn("Completion blocked", self.completion("scope").block_reason or "")

    def test_editing_an_existing_skipped_test_does_not_claim_it_as_new(self) -> None:
        file = self.workspace / "module.ts"
        file.write_text('test.skip("old title", () => {});\n', encoding="utf-8")
        self.capture("scope", "rename", file)
        file.write_text('test.skip("clearer title", () => {});\n', encoding="utf-8")
        self.assertEqual(self.after("scope", "rename"), QUALITY.QualityResult())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_duplicate_occurrences_clear_one_at_a_time(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "add", file)
        file.write_text("# TODO: same\n# TODO: same\nvalue = 1\n", encoding="utf-8")
        self.after("scope", "add")
        self.assertIn("2 unfinished", self.completion("scope").block_reason or "")

        self.capture("scope", "remove-one", file)
        file.write_text("# TODO: same\nvalue = 1\n", encoding="utf-8")
        self.after("scope", "remove-one")
        self.assertIn("1 unfinished", self.completion("scope").block_reason or "")

    def test_failed_edit_consumes_snapshot_without_creating_a_finding(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "failed", file)
        self.assertEqual(self.after("scope", "failed", succeeded=False), QUALITY.QualityResult())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_conditional_test_decorators_do_not_block_completion(self) -> None:
        file = self.workspace / "test_runner.py"
        self.capture("scope", "create", file)
        file.write_text(
            '@unittest.skipUnless(True, "requirement met")\n'
            'def test_available():\n    pass\n'
            '@pytest.mark.skipif(False, reason="requirement met")\n'
            'def test_enabled():\n    pass\n',
            encoding="utf-8",
        )
        self.assertEqual(self.after("scope", "create"), QUALITY.QualityResult())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_debugger_object_key_is_silent_and_debugger_statement_is_reported(self) -> None:
        line = "  debugger" + " " * 6000 + ": false,"
        self.assertEqual(QUALITY.scan_text("const settings = {\n" + line + "\n};\n", ".js"), [])
        self.assertEqual(
            [row.label for row in QUALITY.scan_text("  debugger  ;  // development\n", ".js")],
            ["debugger statement"],
        )

    def test_duplicate_tool_event_preserves_the_first_snapshot_and_clean_replay_is_silent(self) -> None:
        file = self.workspace / "sample.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "edit", file)
        file.write_text("# TODO: finish work\n", encoding="utf-8")
        self.capture("scope", "edit", file)
        self.assertIn("TODO/FIXME/HACK/XXX", self.after("scope", "edit").advisory or "")
        self.assertEqual(self.after("scope", "edit"), QUALITY.QualityResult())

        self.capture("scope", "clean", file)
        file.write_text("value = 2\n", encoding="utf-8")
        self.assertEqual(self.after("scope", "clean"), QUALITY.QualityResult())
        self.assertEqual(self.after("scope", "clean"), QUALITY.QualityResult())

    def test_scanner_timeout_uses_the_remaining_shared_budget(self) -> None:
        executable = self.root / "ruff"
        executable.write_text("#!/bin/sh\nexec /bin/sleep 1\n")
        executable.chmod(0o755)
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.scanners[0].side_effect = PYTHON_FINDINGS
        started = time.monotonic()
        with (
            mock.patch.dict(os.environ, {"PATH": str(self.root)}),
            mock.patch.object(QUALITY, "SCAN_BUDGET_SECONDS", 0.1),
        ):
            result = self.capture("scope", "slow", file)
        self.assertIn("unavailable", result.advisory or "")
        self.assertLess(time.monotonic() - started, 0.6)
        self.assertIsNone(result.block_reason)

    def test_completed_event_retention_is_bounded(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        with mock.patch.object(QUALITY, "MAX_COMPLETED_OPERATIONS", 4):
            for number in range(10):
                self.capture("scope", str(number), file)
                self.after("scope", str(number))
        path = QUALITY._state_path("scope", self.workspace, "test-adapter", self.state)
        notices = json.loads(path.read_text())["notices"]
        self.assertLessEqual(len(notices), 5)

    def test_missing_snapshot_and_invalid_identity_fail_open(self) -> None:
        result = self.after("scope", "missing")
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertIsNone(result.block_reason)
        self.assertEqual(self.after("scope", "another-missing"), QUALITY.QualityResult())

        invalid = QUALITY.capture_before(
            "",
            self.workspace,
            "operation",
            [],
            state_root=self.state,
        )
        self.assertIn("protection unavailable", (invalid.advisory or "").lower())
        self.assertIsNone(invalid.block_reason)

    def test_corrupt_state_recovers_without_a_hard_lock(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        state_file = QUALITY._state_path("scope", self.workspace, "test-adapter", self.state)
        self.state.mkdir(mode=0o700)
        state_file.write_text("not json", encoding="utf-8")
        result = self.capture("scope", "operation", file)
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertIsNone(result.block_reason)
        self.assertEqual(json.loads(state_file.read_text(encoding="utf-8"))["version"], 1)

    def test_lock_contention_is_advisory_and_never_a_hard_lock(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        state_file = QUALITY._state_path("scope", self.workspace, "test-adapter", self.state)
        self.state.mkdir(mode=0o700)
        Path(f"{state_file}.lock").mkdir(mode=0o700)
        with mock.patch.object(QUALITY, "LOCK_RETRIES", 1):
            result = self.capture("scope", "operation", file)
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertIsNone(result.block_reason)

    def test_unreadable_boundary_is_advisory_not_blocking(self) -> None:
        file = self.workspace / "large.py"
        file.write_text("# TODO: hidden\n" + "x" * QUALITY.MAX_FILE_BYTES, encoding="utf-8")
        before = self.capture("scope", "large", file)
        self.assertIn("protection unavailable", (before.advisory or "").lower())
        after = self.after("scope", "large")
        self.assertIn("protection unavailable", (after.advisory or "").lower())
        self.assertIsNone(after.block_reason)
        self.assertNotIn("Completion blocked", self.completion("scope").block_reason or "")

    def test_fifo_source_is_unavailable_without_waiting_for_a_writer(self) -> None:
        workspace = self.workspace.resolve()
        fifo = workspace / "pipe.py"
        os.mkfifo(fifo)
        script = """import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location('quality', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module._read_source(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])) is None
path = pathlib.Path(sys.argv[2])
path.unlink()
path.write_text('regular')
real_open = module.os.open
def swap_then_open(name, flags, *args):
    path.unlink()
    module.os.mkfifo(path)
    return real_open(name, flags, *args)
module.os.open = swap_then_open
assert module._read_source(path, pathlib.Path(sys.argv[3])) is None
"""
        subprocess.run([sys.executable, "-c", script, str(SOURCE), str(fifo), str(workspace)],
                       check=True, timeout=3)

    def test_paths_outside_workspace_and_unsupported_files_are_ignored(self) -> None:
        outside = self.root / "outside.py"
        outside.write_text("# TODO: external\n", encoding="utf-8")
        markdown = self.workspace / "README.md"
        markdown.write_text("TODO\n", encoding="utf-8")
        self.assertEqual(self.capture("scope", "ignored", outside, markdown), QUALITY.QualityResult())
        self.assertEqual(self.after("scope", "ignored"), QUALITY.QualityResult())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

    def test_symlink_swap_cannot_escape_workspace(self) -> None:
        outside = self.root / "outside.py"
        outside.write_text("# TODO: external content\n", encoding="utf-8")
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "swap", file)
        file.unlink()
        file.symlink_to(outside)
        result = self.after("scope", "swap")
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertIsNone(result.block_reason)
        self.assertIsNone(self.completion("scope").block_reason)

    def test_excess_valid_paths_report_unavailable_boundary(self) -> None:
        paths = []
        for index in range(QUALITY.MAX_FILES_PER_EDIT + 1):
            file = self.workspace / f"bounded_{index}.py"
            file.write_text("value = 1\n", encoding="utf-8")
            paths.append(file)
        result = self.capture("scope", "batch", *paths)
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertIsNone(result.block_reason)

    def test_state_uses_hashes_private_permissions_and_no_source_text(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("very-secret-session-name", "operation-name", file)
        file.write_text("# TODO: sensitive description must not be stored\n", encoding="utf-8")
        self.after("very-secret-session-name", "operation-name")
        files = list(self.state.glob("*.json"))
        self.assertEqual(len(files), 1)
        stored = files[0].read_text(encoding="utf-8")
        self.assertNotIn("very-secret-session-name", files[0].name)
        self.assertNotIn("operation-name", stored)
        self.assertNotIn("sensitive description", stored)
        if os.name != "nt":
            self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)

    def test_stale_pending_snapshot_is_nonblocking_and_removed(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "stale", file)
        state_file = QUALITY._state_path("scope", self.workspace, "test-adapter", self.state)
        value = json.loads(state_file.read_text(encoding="utf-8"))
        next(iter(value["pending"].values()))["created"] = time.time() - QUALITY.PENDING_MAX_AGE_SECONDS - 1
        state_file.write_text(json.dumps(value), encoding="utf-8")
        result = self.completion("scope")
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertIsNone(result.block_reason)

    def test_completion_does_not_consume_an_inflight_edit_snapshot(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "inflight", file)
        first = self.completion("scope")
        self.assertIsNone(first.block_reason)
        self.assertIn("protection unavailable", (first.advisory or "").lower())
        self.assertEqual(self.completion("scope"), QUALITY.QualityResult())
        file.write_text("# TODO: finish\n", encoding="utf-8")
        self.assertIn("TODO/FIXME/HACK/XXX", self.after("scope", "inflight").advisory or "")
        self.assertIn("Completion blocked", self.completion("scope").block_reason or "")

    def test_missing_failed_post_does_not_own_a_later_edit_or_block_its_repair(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "failed-without-post", file)
        self.assertIsNone(self.completion("scope").block_reason)

        self.capture("scope", "successful-edit", file)
        file.write_text("# TODO: finish\n", encoding="utf-8")
        self.assertIn("TODO/FIXME/HACK/XXX", self.after("scope", "successful-edit").advisory or "")
        self.assertIn("Completion blocked", self.completion("scope").block_reason or "")

        self.capture("scope", "repair", file)
        file.write_text("value = 2\n", encoding="utf-8")
        self.after("scope", "repair")
        self.assertIsNone(self.completion("scope").block_reason)

        state_file = QUALITY._state_path("scope", self.workspace, "test-adapter", self.state)
        state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(set(state["pending"]), {QUALITY._operation_key("failed-without-post")})
        next(iter(state["pending"].values()))["created"] = (
            time.time() - QUALITY.PENDING_MAX_AGE_SECONDS - 1
        )
        state_file.write_text(json.dumps(state), encoding="utf-8")
        self.assertIsNone(self.completion("scope").block_reason)
        remaining = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
        self.assertFalse(remaining.get("pending"))
        self.assertFalse(remaining.get("findings"))

    def test_resuming_an_abandoned_scope_expires_its_own_state(self) -> None:
        file = self.workspace / "module.py"
        file.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "old", file)
        file.write_text("# TODO: old scope finding\n", encoding="utf-8")
        self.after("scope", "old")
        state_file = QUALITY._state_path("scope", self.workspace, "test-adapter", self.state)
        expired = time.time() - QUALITY.STATE_MAX_AGE_SECONDS - 1
        os.utime(state_file, (expired, expired))

        result = self.completion("scope")
        self.assertIsNone(result.block_reason)
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertFalse(state_file.exists())

    def test_message_output_is_bounded(self) -> None:
        paths = []
        for index in range(12):
            file = self.workspace / f"module_{index}.py"
            file.write_text("value = 1\n", encoding="utf-8")
            paths.append(file)
        self.capture("scope", "batch", *paths)
        for file in paths:
            file.write_text("# TODO: finish\n", encoding="utf-8")
        result = self.after("scope", "batch")
        self.assertIn("… 6 more", result.advisory or "")
        self.assertLess(len(result.advisory or ""), 1200)
        blocked = self.completion("scope")
        self.assertIn("… 6 more", blocked.block_reason or "")
        self.assertLess(len(blocked.block_reason or ""), 1200)

    def test_parallel_scopes_and_same_scope_updates_do_not_lose_findings(self) -> None:
        files = []
        for index in range(32):
            file = self.workspace / f"parallel_{index}.py"
            file.write_text("value = 1\n", encoding="utf-8")
            files.append(file)

        def update(index: int):
            scope = "shared" if index < 16 else f"scope-{index}"
            operation = f"operation-{index}"
            self.capture(scope, operation, files[index])
            files[index].write_text(f"# TODO: finish {index}\n", encoding="utf-8")
            return scope, self.after(scope, operation)

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(update, range(len(files))))
        self.assertTrue(all(result.advisory for _, result in results))
        shared = self.completion("shared")
        self.assertIn("16 unfinished", shared.block_reason or "")
        for index in range(16, 32):
            self.assertIn("1 unfinished", self.completion(f"scope-{index}").block_reason or "")

    def test_slow_scanner_does_not_hold_the_shared_state_lock(self) -> None:
        first = self.workspace / "first.py"
        second = self.workspace / "second.py"
        first.write_text("value = 1\n", encoding="utf-8")
        second.write_text("value = 1\n", encoding="utf-8")
        self.capture("scope", "first", first)

        entered = threading.Event()
        release = threading.Event()

        def scan(_text: str, path: Path, **_options):
            if path == first.resolve():
                entered.set()
                self.assertTrue(release.wait(timeout=2))
            return []

        self.scanners[0].side_effect = scan
        with ThreadPoolExecutor(max_workers=2) as executor:
            pending = executor.submit(self.after, "scope", "first")
            self.assertTrue(entered.wait(timeout=2))
            started = time.monotonic()
            competing = self.capture("scope", "second", second)
            elapsed = time.monotonic() - started
            release.set()
            result = pending.result(timeout=2)

        self.assertEqual(competing, QUALITY.QualityResult())
        self.assertEqual(result, QUALITY.QualityResult())
        self.assertLess(elapsed, 0.5)


if __name__ == "__main__":
    unittest.main()

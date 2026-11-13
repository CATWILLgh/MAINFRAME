from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
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

    def capture(self, scope: str, operation: str, *paths: Path):
        return QUALITY.capture_before(
            scope,
            self.workspace,
            operation,
            paths,
            state_namespace="test-adapter",
            state_root=self.state,
        )

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
                self.assertEqual(self.capture("scope", "create", file), QUALITY.QualityResult())
                file.write_text(source, encoding="utf-8")
                advice = self.after("scope", "create").advisory or ""
                self.assertIn(f"{name}:{2 if imports else 1} — JavaScript valid-expect", advice)
                if "vitest" in imports:
                    self.assertIn(f"{name}:13 — JavaScript valid-expect", advice)
                self.assertEqual(advice.count("valid-expect"), 2 if "vitest" in imports else 1)
                self.assertEqual(self.completion("scope"), QUALITY.QualityResult())

                self.assertEqual(self.capture("scope", "unrelated", file), QUALITY.QualityResult())
                file.write_text(source + "\nconst fixtureSize = 2;\n", encoding="utf-8")
                self.assertEqual(self.after("scope", "unrelated"), QUALITY.QualityResult())

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
        file.write_text(source, encoding="utf-8")
        advice = self.after("workflow", "create").advisory or ""
        self.assertIn(".github/workflows/release.yml:3 — actionlint", advice)
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
            self.assertEqual(self.after("kube", "plain-yaml"), QUALITY.QualityResult())

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
        self.assertEqual(self.after("sql", "another"), QUALITY.QualityResult())

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
        self.assertEqual(self.after("sql", "css"), QUALITY.QualityResult())
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
        self.assertIn("squawk review was unavailable", advice)
        self.assertEqual(self.completion("sql"), QUALITY.QualityResult())

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
        self.assertFalse(list(self.state.glob("*.json")))

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

    def test_missing_snapshot_and_invalid_identity_fail_open(self) -> None:
        result = self.after("scope", "missing")
        self.assertIn("protection unavailable", (result.advisory or "").lower())
        self.assertIsNone(result.block_reason)

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

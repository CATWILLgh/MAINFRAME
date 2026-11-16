from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "mainframe-code-quality.py"
SPEC = importlib.util.spec_from_file_location("web_code_quality", SOURCE)
QUALITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALITY)
NODE_FINDINGS = QUALITY._node_findings

ENTER = 'document.querySelector("textarea").addEventListener("keydown", event => { if (event.key === "Enter") sendMessage(); });\n'
INVALID = 'input:invalid { border-color: red; }\n'
CDN = '<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>\n'


class WebQualityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mainframe-web-quality-")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = (Path(self.temporary.name) / "workspace").resolve()
        self.workspace.mkdir()
        self.state = Path(self.temporary.name) / "state"
        for name in ("_node_findings", "_semgrep_security_findings"):
            patcher = mock.patch.object(QUALITY, name, return_value=[])
            patcher.start()
            self.addCleanup(patcher.stop)

    def capture(self, operation, path):
        return QUALITY.capture_before("web", self.workspace, operation, [path], state_root=self.state)

    def after(self, operation):
        return QUALITY.record_after("web", self.workspace, operation, state_root=self.state)

    @staticmethod
    def scanner_output(raw):
        def scan(command, **options):
            options["stdout"].write(json.dumps(raw).encode())
            return subprocess.CompletedProcess(command, 0)
        return scan

    def test_first_edit_reports_each_web_file_type_and_replay_is_silent(self):
        cases = (
            ("page.html", CDN, "secure-external-subresources"),
            ("page.htm", CDN, "secure-external-subresources"),
            ("form.css", INVALID, "validate-input-after-interaction"),
            ("form.tsx", 'export const Form = () => <textarea onKeyDown={event => { if (event.key === "Enter") sendMessage(); }} />;\n', "ime-safe-enter-submit"),
            ("form.vue", '<template><textarea /></template>\n<style>' + INVALID + '</style>\n', "validate-input-after-interaction"),
            ("form.svelte", '<textarea />\n<style>' + INVALID + '</style>\n', "validate-input-after-interaction"),
        )
        for name, text, rule in cases:
            with self.subTest(name=name):
                path = self.workspace / name
                self.assertEqual(self.capture(name, path), QUALITY.QualityResult())
                path.write_text(text)
                result = self.after(name)
                self.assertIn(rule, result.advisory or "")
                self.assertIn(name, result.advisory or "")
                self.assertIsNone(result.block_reason)
                self.assertEqual(self.after(name), QUALITY.QualityResult())
                self.capture(name + "-unchanged", path)
                self.assertEqual(self.after(name + "-unchanged"), QUALITY.QualityResult())
        self.assertEqual(QUALITY.check_completion("web", self.workspace, state_root=self.state), QUALITY.QualityResult())

    def test_all_javascript_and_typescript_extensions_keep_ime_checks(self):
        for extension in (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"):
            with self.subTest(extension=extension):
                path = self.workspace / ("form" + extension)
                self.capture(extension, path)
                path.write_text(ENTER)
                self.assertIn("ime-safe-enter-submit", self.after(extension).advisory or "")

    def assert_web_lines(self, name, text, rule, lines):
        rows = QUALITY._modern_web_findings(text, self.workspace / name, self.workspace)
        self.assertEqual([row.line for row in rows], lines)
        self.assertEqual(
            [row.label for row in rows],
            [f"Modern Web {rule}: {QUALITY._WEB_LABELS[rule]}"] * len(lines),
        )

    def test_new_cdn_occurrence_is_reported_once_and_repair_preserves_inherited_resource(self):
        path = self.workspace / "resources.html"
        inherited = CDN
        added = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">\n'
        path.write_text(inherited)
        self.assertEqual(self.capture("append-resource", path), QUALITY.QualityResult())
        path.write_text(inherited + added)
        result = self.after("append-resource")
        self.assertIn("resources.html:2", result.advisory or "")
        self.assertNotIn("resources.html:1", result.advisory or "")
        self.assertEqual((result.advisory or "").count("secure-external-subresources"), 1)
        self.assertIsNone(result.block_reason)
        self.assertEqual(self.after("append-resource"), QUALITY.QualityResult())
        self.capture("repair-resource", path)
        repaired = added.replace('href="', 'integrity="sha384-Zml4dHVyZQ==" crossorigin="anonymous" href="')
        path.write_text(inherited + repaired)
        self.assertEqual(self.after("repair-resource"), QUALITY.QualityResult())
        self.assert_web_lines("resources.html", path.read_text(), "secure-external-subresources", [1])
        self.assertEqual(QUALITY.check_completion("web", self.workspace, state_root=self.state), QUALITY.QualityResult())

    def test_every_static_external_resource_is_counted_and_nonstatic_resources_are_excluded(self):
        script = CDN.strip()
        stylesheet = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">'
        cases = (
            ("resources.html", "\n".join((script, stylesheet, script, stylesheet)), [1, 2, 3, 4]),
            ("uppercase.html", script.replace("https://", "HTTPS://"), [1]),
            ("attributes.svelte", '<svelte:head>' + script.replace('></script>', ' crossOrigin="anonymous"></script>') + '</svelte:head>', [1]),
            ("resources.tsx", 'const Page = () => <>\n' + script + '\n' + stylesheet.replace('>', ' />') + '\n</>;', [2, 3]),
            ("excluded.html", '\n'.join((
                '<script src="/assets/app.js"></script>',
                '<script src="https://cdn.jsdelivr.net/npm/jquery@latest/dist/jquery.min.js"></script>',
                '<link rel="preconnect" href="https://cdn.jsdelivr.net">',
                '<!-- ' + script + ' -->',
            )), []),
            ("excluded.tsx", 'const Page = () => <>\n' + '\n'.join((
                '<script src={cdnUrl} />',
                '<script {...props} src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js" />',
                '<link rel="stylesheet" href={cdnUrl} />',
                '<link {...props} rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" />',
            )) + '\n</>;', []),
        )
        for name, text, lines in cases:
            with self.subTest(name=name):
                self.assert_web_lines(name, text, "secure-external-subresources", lines)

    def test_ime_rule_targets_text_controls_and_excludes_native_actions_and_global_hotkeys(self):
        body = 'if (event.key === "Enter") sendMessage();'
        cases = (
            ("textarea.js", 'document.querySelector("textarea").addEventListener("keydown", event => {' + body + '});', [1]),
            ("input.js", 'document.querySelector("input").addEventListener("keydown", event => {' + body + '});', [1]),
            ("button-class.js", 'document.querySelector("textarea.button").addEventListener("keydown", event => {' + body + '});', [1]),
            ("ancestor-type.js", 'document.querySelector("input[type=button] + textarea").addEventListener("keydown", event => {' + body + '});', [1]),
            ("last-button.js", 'document.querySelector("textarea + button").addEventListener("keydown", event => {' + body + '});', []),
            ("mixed-targets.js", 'document.querySelector("button, textarea").addEventListener("keydown", event => {' + body + '});', []),
            ("text.tsx", 'const Form = () => <input type="text" onKeyDown={event => {' + body + '}} />;', [1]),
            ("native-button.tsx", 'const Form = () => <button onKeyDown={event => {' + body + '}}>Send</button>;', []),
            ("native-anchor.tsx", 'const Form = () => <a href="/send" onKeyDown={event => {' + body + '}}>Send</a>;', []),
            ("role-button.tsx", 'const Form = () => <div role="button" onKeyDown={event => {' + body + '}} />;', []),
            ("dynamic-type.tsx", 'const Form = () => <input type={kind} onKeyDown={event => {' + body + '}} />;', []),
            ("custom-component.tsx", 'const Form = ({ Input }) => <Input onKeyDown={event => {' + body + '}} />;', []),
            ("shadowed.tsx", 'const handle = event => {' + body + '}; const Form = (handle) => <input onKeyDown={handle} />;', []),
            ("global.js", 'document.addEventListener("keydown", event => {' + body + '});', []),
        )
        cases += tuple(
            (f"input-{kind}.tsx", 'const Form = () => <input type="' + kind + '" onKeyDown={event => {' + body + '}} />;', [])
            for kind in ("button", "submit", "checkbox")
        )
        for name, text, lines in cases:
            with self.subTest(name=name):
                self.assert_web_lines(name, text, "ime-safe-enter-submit", lines)

    def test_ime_guards_must_protect_the_same_event_before_the_submit(self):
        submit = 'if (event.key === "Enter") sendMessage();'
        cases = (
            ("comment", '/* event.isComposing */ ' + submit, [1]),
            ("logging", 'console.log(event.isComposing); ' + submit, [1]),
            ("late", submit + ' if (event.isComposing) return;', [1]),
            ("other-event", 'if (otherEvent.isComposing) return; ' + submit, [1]),
            ("early", 'if (event.isComposing) return; ' + submit, []),
            ("native", 'if (event.nativeEvent.isComposing) return; ' + submit, []),
            ("condition", 'if (event.key === "Enter" && !event.isComposing) sendMessage();', []),
        )
        for name, body, lines in cases:
            with self.subTest(name=name):
                text = 'const Form = () => <textarea onKeyDown={event => {' + body + '}} />;'
                self.assert_web_lines(name + ".tsx", text, "ime-safe-enter-submit", lines)

    def test_vue_and_svelte_text_handlers_support_named_inline_and_guarded_forms(self):
        submit = 'if (event.key === "Enter") sendMessage();'
        for extension, attributes in (
            ("vue", ("@keydown", "@keydown.enter")),
            ("svelte", ("on:keydown", "onkeydown")),
        ):
            for attribute in attributes:
                for named in (False, True):
                    for guarded in (False, True):
                        with self.subTest(extension=extension, attribute=attribute, named=named, guarded=guarded):
                            body = ('if (event.isComposing) return; ' if guarded else '') + submit
                            if extension == "vue":
                                script = '<script setup>function handle(event) {' + body + '}</script>\n' if named else ''
                                handler = 'handle' if named else 'event => {' + body + '}'
                                text = script + '<template><textarea ' + attribute + '="' + handler.replace('"', "'") + '" /></template>'
                            else:
                                script = '<script>function handle(event) {' + body + '}</script>\n' if named else ''
                                handler = 'handle' if named else '(event) => {' + body + '}'
                                text = script + '<textarea ' + attribute + '={' + handler + '} />'
                            self.assert_web_lines("form." + extension, text, "ime-safe-enter-submit", [] if guarded else [2 if named else 1])

    def test_vue_and_svelte_nontext_handlers_stay_silent(self):
        cases = (
            ("vue", '<template><button @keydown="event => { if (event.key === \'Enter\') sendMessage(); }">Send</button></template>'),
            ("vue", '<template><input type="checkbox" @keydown.enter="sendMessage()" /></template>'),
            ("svelte", '<button on:keydown={(event) => { if (event.key === "Enter") sendMessage(); }}>Send</button>'),
            ("svelte", '<input type="submit" onkeydown={(event) => { if (event.key === "Enter") sendMessage(); }} />'),
        )
        for extension, text in cases:
            with self.subTest(extension=extension, text=text):
                self.assert_web_lines("actions." + extension, text, "ime-safe-enter-submit", [])

    def test_css_invalid_suppression_is_local_and_deliberate_fallbacks_remain_safe(self):
        cases = (
            ("unrelated", 'textarea:user-invalid { color: red; }\n' + INVALID, [2]),
            ("comment", '/* Prefer :user-invalid here. */\n' + INVALID, [2]),
            ("supports", '@supports not selector(:user-invalid) {\n' + INVALID + '}\ninput:user-invalid { color: red; }', []),
            ("touched", '.touched input:invalid { border-color: red; }', []),
            ("validated", '.was-validated input:invalid { border-color: red; }', []),
            ("reset", 'input:invalid { box-shadow: none; outline: none; }', []),
            ("uppercase", 'INPUT:INVALID { border-color: red; }', [1]),
            ("required", 'input:required:invalid { border-color: red; }', [1]),
            ("required-touched", '.touched input[required]:invalid { border-color: red; }', []),
            ("shared-state-style", 'input:valid, input:invalid { color: var(--text); }', []),
            ("unrelated-valid", 'input:invalid, textarea:valid { color: red; }', [1]),
            ("same-field-states", 'input.field:invalid, input.field:valid { color: red; }', []),
        )
        for name, text, lines in cases:
            with self.subTest(name=name):
                self.assert_web_lines(name + ".css", text, "validate-input-after-interaction", lines)

    def test_changed_rule_semantics_do_not_claim_inherited_findings_from_old_snapshots(self):
        path = self.workspace / "upgrade.html"
        path.write_text(CDN + CDN.replace("jquery@3.7.1", "jquery@3.7.0"))
        modern = QUALITY._modern_web_findings
        with (
            mock.patch.object(QUALITY, "_WEB_CHANNEL", "modern-web"),
            mock.patch.object(QUALITY, "_modern_web_findings", side_effect=lambda *args: modern(*args)[:1]),
        ):
            self.capture("legacy-snapshot", path)
        self.assertEqual(self.after("legacy-snapshot"), QUALITY.QualityResult())
        self.capture("new-snapshot", path)
        path.write_text(path.read_text() + CDN.replace("jquery@3.7.1", "jquery@3.6.0"))
        self.assertIn("upgrade.html:3", self.after("new-snapshot").advisory or "")

    def test_unsupported_handler_paths_report_unavailable_once_and_keep_security(self):
        path = self.workspace / "uncertain.tsx"
        with mock.patch.object(QUALITY, "_node_findings", side_effect=NODE_FINDINGS):
            self.capture("unsupported", path)
            path.write_text('eval(value); const Form = () => <input onKeyDown={event => { if (event.key === "Enter") { try { send(); } finally {} } }} />;')
            result = self.after("unsupported")
            self.assertIn("Modern web review was unavailable", result.advisory or "")
            self.assertIn("JavaScript security: eval()", result.advisory or "")
            self.assertIn("JavaScript security: eval()", QUALITY.check_completion("web", self.workspace, state_root=self.state).block_reason or "")
            self.assertEqual(self.after("unsupported"), QUALITY.QualityResult())
            self.assertEqual(self.capture("unsupported-repeat", path), QUALITY.QualityResult())
            self.assertEqual(self.after("unsupported-repeat"), QUALITY.QualityResult())

    def test_tagged_css_templates_are_checked_without_reclassifying_plain_strings(self):
        for extension in (".ts", ".tsx", ".mts", ".cts", ".js"):
            path = self.workspace / ("styles" + extension)
            with self.subTest(extension=extension):
                rows = QUALITY._modern_web_findings('const styles = css`' + INVALID + '`;\n', path, self.workspace)
                self.assertTrue(any("validate-input-after-interaction" in row.label for row in rows))
                safe = 'const styles = css`input:user-invalid { border-color: red; }`;\n'
                self.assertEqual(QUALITY._modern_web_findings(safe, path, self.workspace), [])
                self.assertEqual(QUALITY._modern_web_findings('const example = ' + json.dumps(INVALID) + ';', path, self.workspace), [])

    def test_large_valid_scanner_output_is_complete_and_advice_stays_bounded(self):
        path = self.workspace / "forms.css"
        self.assertEqual(len(QUALITY._modern_web_findings(INVALID * 200, path, self.workspace)), 200)
        self.capture("large-output", path)
        path.write_text(INVALID * 200)
        result = self.after("large-output")
        self.assertIn("validate-input-after-interaction", result.advisory or "")
        self.assertNotIn("unavailable", result.advisory or "")
        self.assertLessEqual(len(result.advisory or ""), QUALITY.MAX_ADVISORY_CHARS)

    def test_web_budget_exhaustion_preserves_security_on_later_paths(self):
        paths = [self.workspace / f"form{i:02}.css" for i in range(23)]
        worker = self.workspace / "zz_worker.py"
        for path in paths:
            path.write_text(INVALID)
        worker.write_text("value = 1\n")
        paths.append(worker)
        clock = [0.0]
        calls = []
        python_scan = QUALITY._python_findings

        def scan_python(*args, **kwargs):
            calls.append("security")
            return python_scan(*args, **kwargs)

        def consume_web_budget(*args):
            calls.append("web")
            clock[0] += 0.3
            return []

        with (
            mock.patch.object(QUALITY.time, "monotonic", side_effect=lambda: clock[0]),
            mock.patch.object(QUALITY, "_modern_web_findings", side_effect=consume_web_budget),
            mock.patch.object(QUALITY, "_python_findings", side_effect=scan_python),
        ):
            QUALITY.capture_before("web", self.workspace, "budget", paths, state_root=self.state)
            self.assertEqual(calls[0], "security")
            calls.clear()
            worker.write_text("eval(value)\n")
            result = self.after("budget")
            self.assertEqual(calls[0], "security")
            self.assertIn("Python security S307", result.advisory or "")
            self.assertIn("Python security S307", QUALITY.check_completion("web", self.workspace, state_root=self.state).block_reason or "")

    def test_web_enrichment_rejects_a_revision_changed_after_core_scanning(self):
        path = self.workspace / "form.css"
        worker = self.workspace / "worker.py"
        path.write_text(INVALID)
        worker.write_text("value = 1\n")
        read_scan = QUALITY._read_scan

        def mutate_after_core(candidate, *args, **kwargs):
            scan = read_scan(candidate, *args, **kwargs)
            if candidate == worker:
                path.write_text(INVALID.replace(":invalid", ":user-invalid"))
            return scan

        with (
            mock.patch.object(QUALITY, "_read_scan", side_effect=mutate_after_core),
            mock.patch.object(QUALITY, "_modern_web_findings", side_effect=AssertionError("mixed revision")),
        ):
            scans = QUALITY._read_edit_scans([path, worker], self.workspace, time.monotonic() + 5)
        self.assertNotIn("modern-web", scans[path].channels)
        self.assertTrue(any(issue.key == "scanner:modern-web" for issue in scans[path].issues))
        self.assertIn(QUALITY._PYTHON_SECURITY_CHANNEL, scans[worker].channels)

    def test_safe_patterns_and_intentional_fallbacks_stay_silent(self):
        cases = (
            ("guard.js", ENTER.replace('if (event.key', 'if (event.isComposing) return; if (event.key')),
            ("guard.tsx", 'const Form = () => <input onKeyDown={event => { if (event.nativeEvent.isComposing) return; if (event.key === "Enter") sendMessage(); }} />;'),
            ("keyup.js", ENTER.replace('"keydown"', '"keyup"')),
            ("modifier.js", ENTER.replace('event.key === "Enter"', 'event.key === "Enter" && event.ctrlKey')),
            ("hotkey.js", 'document.addEventListener("keydown", event => { if (event.key === "Enter") sendMessage(); });'),
            ("quoted.js", 'const example = ' + json.dumps(ENTER) + ';'),
            ("fallback.css", '@supports not selector(:user-invalid) {' + INVALID + '}\ninput:user-invalid { border-color: red; }'),
            ("touched.css", '.was-validated input:invalid { border-color: red; }'),
            ("reset.css", 'input:invalid { box-shadow: none; outline: none; }'),
            ("comment.css", '/* ' + INVALID + ' */'),
            ("integrity.html", CDN.replace('></script>', ' integrity="sha384-Zml4dHVyZQ==" crossorigin="anonymous"></script>')),
            ("mutable.html", '<script src="https://cdn.jsdelivr.net/npm/jquery@latest/dist/jquery.min.js"></script>'),
            ("local.html", '<script src="/assets/app.js"></script>'),
        )
        for name, text in cases:
            with self.subTest(name=name):
                path = self.workspace / name
                self.capture(name, path)
                path.write_text(text)
                self.assertEqual(self.after(name), QUALITY.QualityResult())

    def test_repair_clears_web_advice_without_a_completion_block(self):
        path = self.workspace / "form.css"
        self.capture("introduce", path)
        path.write_text(INVALID)
        self.assertIn("validate-input-after-interaction", self.after("introduce").advisory or "")
        self.capture("repair", path)
        path.write_text(INVALID.replace(":invalid", ":user-invalid"))
        self.assertEqual(self.after("repair"), QUALITY.QualityResult())
        self.assertEqual(QUALITY.check_completion("web", self.workspace, state_root=self.state), QUALITY.QualityResult())

    def test_unrelated_and_generated_files_do_not_launch_the_scanner(self):
        paths = ("worker.py", "server.go", "app.min.js", "dist/app.js", "node_modules/app.js", "tests/form.test.tsx")
        with mock.patch.object(QUALITY, "_run_scanner", side_effect=AssertionError("unexpected scanner")):
            for name in paths:
                with self.subTest(name=name):
                    self.assertEqual(QUALITY._modern_web_findings(ENTER + CDN + INVALID, self.workspace / name, self.workspace), [])
            self.assertEqual(QUALITY._modern_web_findings("const value = 1;", self.workspace / "app.ts", self.workspace), [])

    def test_large_candidate_reports_unavailable_once_without_blocking(self):
        path = self.workspace / "form.css"
        text = INVALID + ("/* safe padding */\n" * 20_000)
        self.capture("large", path)
        path.write_text(text)
        with mock.patch.object(QUALITY, "_run_scanner", side_effect=AssertionError("oversized scan")):
            first = self.after("large")
            self.assertIn("web", (first.advisory or "").lower())
            self.assertIsNone(first.block_reason)
            self.capture("large-repeat", path)
            self.assertEqual(self.after("large-repeat"), QUALITY.QualityResult())

    def test_scanner_timeout_and_wire_validation_are_bounded(self):
        with mock.patch.object(QUALITY, "_run_scanner", side_effect=AssertionError("unbounded line scan")):
            with self.assertRaises(ValueError):
                QUALITY._modern_web_findings(INVALID + "/*" + "x" * 2_001 + "*/", self.workspace / "form.css", self.workspace)

        executable = self.workspace / "slow-scanner"
        marker = self.workspace / "scanner-temp-path"
        executable.write_text(
            "#!/usr/bin/env python3\nfrom pathlib import Path\nimport tempfile,time\n"
            "seed = tempfile.mkdtemp(prefix='mainframe-parser-seed-')\n"
            f"Path({str(marker)!r}).write_text(seed)\n"
            "time.sleep(10)\n"
        )
        executable.chmod(0o755)
        with mock.patch.object(QUALITY.shutil, "which", return_value=str(executable)):
            start = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                QUALITY._modern_web_findings(INVALID, self.workspace / "form.css", self.workspace)
            self.assertLess(time.monotonic() - start, 2)
            self.assertFalse(Path(marker.read_text()).parent.exists())

        for raw in ([], {"guides": []}, {"error": "synthetic failure", "guides": []}):
            with self.subTest(raw=raw), mock.patch.object(QUALITY, "_run_scanner", side_effect=self.scanner_output(raw)):
                with self.assertRaises(ValueError):
                    QUALITY._modern_web_findings(INVALID, self.workspace / "form.css", self.workspace)

    def test_findings_must_belong_to_the_addressed_snapshot(self):
        finding = {"file": "source.css", "line": 1}
        for replacement in ({"file": "unrelated.css"}, {"line": 99}, {"line": True}):
            raw = {"targetDir": "source.css", "activeRuleCount": 1, "guides": [{
                "guideId": "validate-input-after-interaction", "rules": [{
                    "ruleId": "validate-input-after-interaction", "findings": [{**finding, **replacement}],
                }],
            }]}
            with self.subTest(replacement=replacement), mock.patch.object(QUALITY, "_run_scanner", side_effect=self.scanner_output(raw)):
                with self.assertRaises(ValueError):
                    QUALITY._modern_web_findings(INVALID, self.workspace / "form.css", self.workspace)

    def test_scanner_output_read_has_a_size_bound(self):
        raw = {"targetDir": "source.css", "activeRuleCount": 1, "guides": [], "padding": "x" * QUALITY.MAX_FILE_BYTES}
        with mock.patch.object(QUALITY, "_run_scanner", side_effect=self.scanner_output(raw)):
            with self.assertRaisesRegex(ValueError, "output exceeds"):
                QUALITY._modern_web_findings(INVALID, self.workspace / "form.css", self.workspace)

    def test_unexpected_matcher_errors_cannot_be_swallowed_into_a_clean_result(self):
        module = self.workspace / "broken-parser.mjs"
        module.write_text(
            "export async function runAnalyzeCli(args, {rules}) {\n"
            " for (const rule of rules.filter(r => r.matcher.kind === 'js')) {\n"
            "  try { rule.matcher.matchFile({getDescendants(){throw new TypeError('synthetic parser API fault');}}, {}); } catch {}\n"
            " }\n"
            " return {exitCode:0,output:JSON.stringify({targetDir:args[0],activeRuleCount:rules.length,totalFindings:0,guides:[]})};\n"
            "}\n"
        )
        executable = self.workspace / "faulty-parser-launcher"
        executable.write_text(
            "#!/usr/bin/env python3\nimport os,sys\n"
            "os.execvp('node',['node','--input-type=module','--eval',sys.argv[2],'--','mainframe-web-check',"
            + repr(str(module)) + ", 'unused-compiler', *sys.argv[3:]])\n"
        )
        executable.chmod(0o755)
        with mock.patch.object(QUALITY.shutil, "which", return_value=str(executable)):
            with self.assertRaisesRegex(RuntimeError, "web scanner failed"):
                QUALITY._modern_web_findings(ENTER, self.workspace / "form.ts", self.workspace)

    def test_scanner_is_isolated_and_raw_diagnostics_stay_out_of_findings(self):
        snapshots = []

        def scan(command, **options):
            snapshot = options["cwd"] / command[3]
            snapshots.append(snapshot)
            self.assertEqual(snapshot.read_text(), INVALID)
            self.assertEqual(command[1], "--mainframe-rules")
            self.assertTrue(command[2])
            self.assertNotIn(INVALID, command[2])
            self.assertEqual(command[3:], ["source.css", "--json", "--guide", "validate-input-after-interaction"])
            self.assertEqual(options["env"]["DISABLE_TELEMETRY"], "1")
            self.assertEqual(options["env"]["ENABLE_FILE_LOGGING"], "false")
            self.assertEqual(options["env"]["TMPDIR"], str(options["cwd"]))
            self.assertNotIn("NODE_OPTIONS", options["env"])
            self.assertNotIn("NODE_PATH", options["env"])
            self.assertEqual(options["timeout"], 1)
            raw = {"targetDir": "source.css", "activeRuleCount": 1, "guides": [{
                "guideId": "validate-input-after-interaction", "rules": [{
                    "ruleId": "validate-input-after-interaction", "findings": [{
                        "file": "source.css", "line": 1, "message": "untrusted-diagnostic",
                        "lineContent": "private-source-value",
                    }],
                }],
            }]}
            options["stdout"].write(json.dumps(raw).encode())
            return subprocess.CompletedProcess(command, 0)

        with (
            mock.patch.dict(QUALITY.os.environ, {"NODE_OPTIONS": "--synthetic-probe", "NODE_PATH": "/synthetic"}),
            mock.patch.object(QUALITY, "_run_scanner", side_effect=scan),
        ):
            rows = QUALITY._modern_web_findings(INVALID, self.workspace / "form.css", self.workspace)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("untrusted-diagnostic", repr(rows))
        self.assertNotIn("private-source-value", repr(rows))
        self.assertTrue(all(not path.exists() for path in snapshots))

    def test_web_scanner_failure_preserves_existing_security_protection(self):
        path = self.workspace / "form.ts"
        finding = QUALITY._occurrence("JavaScript security: eval()", 1, "scanner", "eval(value)", channel=QUALITY._NODE_SECURITY_CHANNEL)

        def web_failure(text, *args):
            if text:
                raise RuntimeError("synthetic web scanner failure")
            return []

        with (
            mock.patch.object(QUALITY, "_node_findings", side_effect=lambda text, *args, **kwargs: [finding] if text else []),
            mock.patch.object(QUALITY, "_modern_web_findings", side_effect=web_failure),
        ):
            self.capture("security", path)
            path.write_text("eval(value);\n" + ENTER)
            result = self.after("security")
            self.assertIn("JavaScript security: eval()", result.advisory or "")
            self.assertIn("Modern web review was unavailable", result.advisory or "")
            self.assertIn("JavaScript security: eval()", QUALITY.check_completion("web", self.workspace, state_root=self.state).block_reason or "")


if __name__ == "__main__":
    unittest.main()

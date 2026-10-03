from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "mainframe-skill-reminder.py"
SPEC = importlib.util.spec_from_file_location("skill_reminder", SOURCE)
assert SPEC is not None and SPEC.loader is not None
DETECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DETECTOR)


class ReadIntentTests(unittest.TestCase):
    def test_actual_read_forms_preserve_literal_paths_and_order(self) -> None:
        self.assertEqual(
            DETECTOR.read_targets(
                "cat src/a.py 'src/space name.py'; sed -n '1,120p' src/b.go\n"
                "head -n 20 src/c.ts && tail -n10 src/a.py", "/workspace"
            ),
            ["/workspace/src/a.py", "/workspace/src/space name.py",
             "/workspace/src/b.go", "/workspace/src/c.ts"],
        )
        self.assertEqual(DETECTOR.read_targets("/bin/cat -- ./-n", "/workspace"), ["/workspace/-n"])
        self.assertEqual(DETECTOR.read_targets(r"cat src/a\ b.py", "/workspace"), ["/workspace/src/a b.py"])

    def test_rg_pattern_and_option_values_are_not_paths(self) -> None:
        for command in (
            "rg -n src/looks-like-file.py backend/a.py backend",
            "rg -n -g '*.py' -t py needle backend/a.py backend",
            "rg --glob='*.py' --max-count 2 -e needle backend/a.py backend",
            "rg -ne needle -- backend/a.py backend",
            "rg -- --pattern backend/a.py backend",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.read_targets(command, "/w"), ["/w/backend/a.py", "/w/backend"])
        self.assertEqual(DETECTOR.read_targets("rg file.py", "/w"), [])
        self.assertEqual(DETECTOR.read_targets("rg -f patterns.txt needle.py", "/w"), ["/w/patterns.txt", "/w/needle.py"])
        self.assertEqual(DETECTOR.read_targets("rg --ignore-file ignore.txt needle src", "/w"), ["/w/ignore.txt", "/w/src"])

    def test_option_operands_and_mutating_sed_are_never_read_targets(self) -> None:
        for command in (
            "head -n src/a.py", "tail --lines=src/a.py", "cat --output src/a.py",
            "rg --unknown src/a.py needle other.py", "rg --pre cat needle src/a.py",
            "sed -i '1p' src/a.py", "sed -n '1p;w output' src/a.py",
            "sed -n 's/x/y/' src/a.py", "sed -n -f script.sed src/a.py",
            "sed -n '1p' -i src/a.py", "sed -n '1p' -e 'd' src/a.py",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.read_targets(command, "/w"), [])

    def test_sequential_reads_and_read_only_pipelines(self) -> None:
        self.assertEqual(
            DETECTOR.read_targets("cat a.py | head -n 2; rg -n needle b.go | tail -n 3\ncat c.py", "/w"),
            ["/w/a.py", "/w/b.go", "/w/c.py"],
        )
        self.assertEqual(DETECTOR.read_targets("cat a.py | head -n 2 extra.py", "/w"), ["/w/a.py", "/w/extra.py"])
        self.assertEqual(DETECTOR.read_targets("cat a.py | cd /other && cat b.py", "/w"), [])
        self.assertEqual(DETECTOR.read_targets("cat a.py | bash -c 'echo example'", "/w"), [])

    def test_unknown_cwd_keeps_only_absolute_targets(self) -> None:
        for cwd in (None, "relative", "", 42):
            with self.subTest(cwd=cwd):
                self.assertEqual(DETECTOR.read_targets("cat a.py /absolute/b.py", cwd), ["/absolute/b.py"])

    def test_cd_success_branch_is_bounded_by_its_condition(self) -> None:
        self.assertEqual(DETECTOR.read_targets("cd /other && cat a.py && head b.go", None), ["/other/a.py", "/other/b.go"])
        self.assertEqual(DETECTOR.read_targets("cd /other &&\n cat a.py", None), ["/other/a.py"])
        self.assertEqual(DETECTOR.read_targets("cd /other && cat a.py; cat b.py /c.py", "/w"), ["/other/a.py", "/c.py"])
        for command in (
            "cd /other; cat a.py", "cd relative && cat a.py", "cd - && cat a.py",
            "cd /other\ncat a.py", "cd /other || cat a.py", "cd /other | cat a.py",
            "cat a.py | cd /other", "if cd /other; then cat a.py; fi",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.read_targets(command, "/w"), [])

    def test_quoted_examples_wrappers_and_unknown_executables_are_ignored(self) -> None:
        for command in (
            "echo 'cat /src/a.py'", "printf '%s' 'head /src/a.py'",
            "python -c 'print(\"cat /src/a.py\")'", "bash -c 'cat /src/a.py'",
            "env MODE=x cat /src/a.py", "command cat /src/a.py",
            "my-cat /src/a.py", "eval 'cat /src/a.py'",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.read_targets(command, "/w"), [])
        self.assertEqual(DETECTOR.read_targets("unknown; cat relative.py /absolute.py", "/w"), ["/absolute.py"])

    def test_unsafe_shell_syntax_and_malformed_input_fail_silently(self) -> None:
        for command in (
            "cat $(echo /src/a.py)", "cat `echo /src/a.py`", 'cat "$PATH/a.py"',
            "cat ${DIR}/a.py", "cat <(echo /src/a.py)", "cat <<'EOF'\n/src/a.py\nEOF",
            "cat /src/a.py > output", "cat /src/a.py < input", "cat /src/a.py &",
            "(cat /src/a.py)", "cat /src/*.py", "cat ~/src/a.py", "cat src/{a,b}.py",
            "cat 'unterminated", "cat /src/a.py &&", "cat /src/a.py |", "cat /src/a.py\x00",
            "cat /src/a.py ; ; cat /src/b.py", "cat /src/a.py || cat /src/b.py",
            "if true; cat /src/a.py; fi", "while true; cat /src/a.py; done",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.read_targets(command, "/w"), [])
        self.assertEqual(DETECTOR.read_targets(None, "/w"), [])
        self.assertEqual(DETECTOR.read_targets("cat '$literal.py'", "/w"), ["/w/$literal.py"])
        self.assertEqual(DETECTOR.read_targets(r'cat "\$literal.py"', "/w"), ["/w/$literal.py"])

    def test_limits_never_return_partial_targets(self) -> None:
        commands = (
            "cat /ok.py " + "x" * (DETECTOR.MAX_COMMAND_BYTES + 1),
            ";".join("cat /a.py" for _ in range(DETECTOR.MAX_SEGMENTS + 1)),
            "cat " + " ".join(f"/file{n}.py" for n in range(DETECTOR.MAX_TARGETS + 1)),
            "cat /ok.py /" + "x" * DETECTOR.MAX_PATH_BYTES,
            "cat " + " ".join("/same.py" for _ in range(DETECTOR.MAX_TOKENS + 1)),
        )
        for command in commands:
            with self.subTest(length=len(command)):
                self.assertEqual(DETECTOR.read_targets(command, "/w"), [])

    def test_calls_are_stateless_and_make_no_source_reads(self) -> None:
        # Intent is identical even when neither cwd nor file exists.
        command = "cat missing.py; rg -n needle missing_dir"
        expected = ["/does-not-exist/missing.py", "/does-not-exist/missing_dir"]
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: DETECTOR.read_targets(command, "/does-not-exist"), range(16)))
        self.assertEqual(results, [expected] * 16)
        with patch("builtins.open", side_effect=AssertionError("content read")), patch(
            "io.open", side_effect=AssertionError("content read")
        ), patch("os.stat", side_effect=AssertionError("filesystem inspection")):
            self.assertEqual(DETECTOR.read_targets(command, "/does-not-exist"), expected)


class CandidateSkillTests(unittest.TestCase):
    def test_testing_intent_overrides_language(self) -> None:
        for path in ("tests", "tests/a.py", "src/__tests__/A.tsx", "pkg/a_test.go", "src/a.spec.ts", "test_a.py", ".github/workflows/ci.yml"):
            with self.subTest(path=path):
                self.assertEqual(DETECTOR.candidate_skill(path), "mainframe-testing")

    def test_specific_language_candidates(self) -> None:
        expected = {
            "backend/a.py": "mainframe-python-backend",
            "server/a.go": "mainframe-go-backend",
            "server/routes/a.ts": "mainframe-typescript-backend",
            "src/A.tsx": "mainframe-frontend",
        }
        for path, candidate in expected.items():
            with self.subTest(path=path):
                self.assertEqual(DETECTOR.candidate_skill(path), candidate)

    def test_generic_and_outside_paths_are_not_guesses(self) -> None:
        for path in ("src", "src/a.ts", "file.py", "main.go", "scripts/check.py", "README.md", "src/config.json", "/backend/a.py", "../server/a.go", "", None):
            with self.subTest(path=path):
                self.assertIsNone(DETECTOR.candidate_skill(path))


if __name__ == "__main__":
    unittest.main()

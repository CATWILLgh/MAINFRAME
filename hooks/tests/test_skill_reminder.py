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


class OperationSkillTests(unittest.TestCase):
    def test_documented_codex_headless_peer_commands_without_authority_inference(self) -> None:
        session_id = "12345678-1234-4567-89ab-0123456789ab"
        for command in (
            "codex exec --json -C /workspace 'Review only backend/a.py'",
            "codex exec --sandbox read-only --json 'Review this change'",
            "codex exec -s workspace-write -C /workspace -- 'Run focused tests'",
            "codex exec --cd=/workspace --output-last-message result.txt 'Summarize the change'",
            "cat prompt.txt | codex exec --json -",
            "codex exec -",
            f"codex exec resume --json {session_id} 'Check the returned fix'",
            f"codex exec --json resume {session_id} 'Continue the same result'",
            f"codex exec resume {session_id}",
            f"cat correction.txt | codex exec resume --json {session_id} -",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), {"mainframe-peer-work"})
        for command in (
            "echo 'codex exec --json prompt'", "rg 'codex exec' README.md",
            "codex --version", "codex exec --help", "codex exec help",
            "codex install", "codex login", "codex auth status", "codex resume --last",
            "codex exec", "codex exec ''", "cat prompt.txt | codex exec", "codex exec --unknown prompt",
            "codex exec --sandbox unknown prompt", "codex exec --json=true prompt",
            "codex exec --dangerously-bypass-approvals-and-sandbox prompt",
            "codex exec resume --last correction", "codex exec resume named-session correction",
            "codex exec resume invalid-id correction", "codex exec resume",
            f"codex exec -- resume {session_id} correction",
            f"codex exec resume {session_id} correction extra",
            "codex exec --json \"$PROMPT\"", "bash -c 'codex exec prompt'",
            "claude -p prompt", "opencode run prompt", "pi -p prompt",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), set())

    def test_canonical_bounded_curl_options_remain_http_transfers(self) -> None:
        for command in (
            r"curl --disable -sS --fail --connect-timeout 3 --max-time 15 --proto '=https' --write-out '\nHTTP_CODE:%{http_code}\n' https://example.invalid/resource",
            "curl -q -sS --proto '=https' --proto-redir '=https' --max-redirs 3 -w '%{http_code}' https://example.invalid",
            "curl --disable --proto=https --write-out='%{http_code}' --url=https://example.invalid",
            "curl --disable --proto '-all,+https' --proto-redir '-all,+https' https://example.invalid",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), {"mainframe-curl-requests"})
        for command in (
            "curl --disable --proto '=https' --write-out https://example.invalid",
            "curl --disable --write-out https://example.invalid --proto '=https' local-file",
            "curl --disable --proto '=https' ftp://example.invalid/file",
            "curl -q --proto '=https' --config settings https://example.invalid",
            "curl --disable --proto --config https://example.invalid",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), set())

    def test_explicit_clickhouse_query_file_and_pipeline_input_operations(self) -> None:
        for command in (
            "clickhouse-client --host database.invalid --secure --query 'SELECT 1'",
            "clickhouse client -q 'SELECT 1; SELECT 2' --database app --format JSONEachRow",
            "clickhouse-client --queries-file queries.sql",
            "clickhouse-client --query='SELECT 1' --max_execution_time=5 --readonly=1",
            "cat queries.sql | clickhouse-client --host database.invalid",
            "cat rows.tsv | sudo -n clickhouse client --query 'INSERT INTO app.events FORMAT TSV'",
            "ssh server 'clickhouse-client --queries-file queries.sql'",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), {"mainframe-clickhouse"})
        self.assertEqual(DETECTOR.operation_skills(
            "mainframe-secret run CLICKHOUSE_PASSWORD -- clickhouse-client --query 'SELECT 1'"
        ), {"mainframe-secrets", "mainframe-clickhouse"})
        for command in (
            "echo 'clickhouse-client --query SELECT'", "rg clickhouse-client queries.sql",
            "clickhouse-client", "clickhouse client --host localhost --port 9000",
            "curl http://localhost:8123", "clickhouse local -q 'SELECT 1'",
            "clickhouse-client --query", "clickhouse-client --query=''",
            "clickhouse-client --config-file client.xml --query 'SELECT 1'",
            "clickhouse-client --unknown --query 'SELECT 1'",
            "clickhouse-client --version", "clickhouse client --help --query 'SELECT 1'",
            "clickhouse-client --query 'SELECT 1' --version-clean",
            "clickhouse-client --query \"$QUERY\"", "clickhouse-client < queries.sql",
        ):
            with self.subTest(command=command):
                expected = {"mainframe-curl-requests"} if command == "curl http://localhost:8123" else set()
                self.assertEqual(DETECTOR.operation_skills(command), expected)

    def test_literal_credential_and_http_operations(self) -> None:
        cases = {
            "mainframe-secret list": {"mainframe-secrets"},
            "mainframe-secret set API_TOKEN --clipboard": {"mainframe-secrets"},
            "mainframe-secret get API_TOKEN": {"mainframe-secrets"},
            "mainframe-secret run API_TOKEN OTHER_TOKEN -- curl -fsS --max-time 5 https://example.invalid/health":
                {"mainframe-secrets", "mainframe-curl-requests"},
            "/usr/bin/curl -X POST -H 'Content-Type: application/json' -d '{}' --url https://example.invalid":
                {"mainframe-curl-requests"},
            "curl -sSI 'https://example.invalid/path?q=one'": {"mainframe-curl-requests"},
            "curl --output https://example.invalid/output local-file": set(),
            "curl -H https://example.invalid": set(),
            "curl ftp://example.invalid/file": set(),
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), expected)

    def test_known_wrappers_preserve_remote_boundary_and_compound_operations(self) -> None:
        cases = {
            "ssh -T -o BatchMode=yes -p 22 operator@server 'sudo -n k3s kubectl get nodes -o wide'":
                {"mainframe-k3s"},
            "mainframe-secret run SSH_KEY -- ssh server 'curl -fsS https://example.invalid; docker compose ps'":
                {"mainframe-secrets", "mainframe-curl-requests", "mainframe-infrastructure"},
            "ssh server 'sudo -n docker compose restart api'": {"mainframe-infrastructure"},
            "sudo -n -- terraform plan && python3 -B -m unittest discover":
                {"mainframe-infrastructure", "mainframe-testing"},
            "cd /workspace && pytest -q; echo 'curl https://example.invalid'": {"mainframe-testing"},
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                result = DETECTOR.operation_skills(command)
                self.assertEqual(result, expected)
                self.assertNotIn("mainframe-ops-app-server-safety", result)

    def test_cluster_operations_require_k3s_identity_and_cluster_resource(self) -> None:
        for command in (
            "k3s server --cluster-init", "k3s agent --server https://cluster.invalid",
            "k3s etcd-snapshot save", "k3s kubectl describe node worker",
            "k3s kubectl drain worker --ignore-daemonsets", "k3s kubectl get storageclasses",
            "sudo -n systemctl restart k3s", "systemctl status k3s-agent",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), {"mainframe-k3s"})
        for command in (
            "kubectl get nodes", "kubectl get pods", "k3s kubectl get pods -A",
            "k3s kubectl logs api", "k3s kubectl exec api -- curl https://example.invalid",
            "k3s kubectl apply -f cluster.yaml", "k3s kubectl get nodes,pods",
            "k3s kubectl get nodes --unknown value", "k3s kubectl version",
            "k3s kubectl -n k3s get deployments", "systemctl restart application",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), set())

    def test_infrastructure_and_named_test_runners(self) -> None:
        for command in (
            "docker compose -f compose.yml up -d", "docker --context production ps",
            "docker -H tcp://remote.invalid:2376 inspect api", "docker exec api cat /etc/os-release",
            "docker container inspect api", "docker volume ls", "docker system df",
            "terraform plan", "terraform state list", "terraform -chdir=infra plan",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), {"mainframe-infrastructure"})
        for command in (
            "pytest", "python -m pytest tests", "python3 -m unittest discover -s tests",
            "go test ./...", "node --test test.js", "npm test -- --runInBand",
            "cargo test", "vitest run", "jest --runInBand",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), {"mainframe-testing"})

    def test_examples_help_versions_unknown_and_dynamic_forms_stay_silent(self) -> None:
        for command in (
            "echo 'mainframe-secret run API_TOKEN -- curl https://example.invalid'",
            "rg 'docker compose up|k3s|pytest' source.py", "cat terraform-plan.txt",
            "python -c 'print(\"pytest\")'", "bash -c 'curl https://example.invalid'",
            "env MODE=x pytest", "command curl https://example.invalid",
            "npm run verify", "npm run deploy", "docker mystery api", "terraform mystery",
            "docker container mystery", "docker context use", "terraform -chdir= plan",
            "mainframe-secret help", "mainframe-secret --version", "mainframe-secret run TOKEN --",
            "mainframe-secret run invalid-name -- pytest", "mainframe-secret list extra",
            "curl --help all", "curl --version", "curl --config settings https://example.invalid",
            "curl --unknown https://example.invalid", "k3s server --help",
            "docker compose --help", "terraform version", "pytest --version",
            "python3 -m unittest --help", "go help test", "node --version",
            "sudo pytest", "sudo -u root -n pytest", "ssh -V server 'pytest'",
            "ssh -o Unknown=yes server 'pytest'", "ssh server pytest -q",
            "ssh server 'curl \"$URL\"'", "curl \"$URL\"", "curl $(echo https://example.invalid)",
            "pytest; ssh server 'curl \"$URL\"'", "ssh server 'pytest || echo failed'",
            "curl https://example.invalid > out", "pytest || echo failed", "pytest &",
            "pytest; if true; then terraform plan; fi", "pytest 'unterminated",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), set())

    def test_shared_limits_wrapper_depth_and_purity(self) -> None:
        for command in (
            "pytest " + "x" * DETECTOR.MAX_COMMAND_BYTES,
            ";".join("pytest" for _ in range(DETECTOR.MAX_SEGMENTS + 1)),
            "pytest " + " ".join("x" for _ in range(DETECTOR.MAX_TOKENS + 1)),
            "sudo -n " * 10 + "pytest", None, "pytest\x00",
            "ssh server '" + ";".join("pytest" for _ in range(DETECTOR.MAX_SEGMENTS)) + "'",
        ):
            with self.subTest(command=command):
                self.assertEqual(DETECTOR.operation_skills(command), set())
        command = "mainframe-secret run API_TOKEN -- ssh server 'docker compose ps'"
        expected = {"mainframe-secrets", "mainframe-infrastructure"}
        with patch("builtins.open", side_effect=AssertionError("content read")), patch(
            "io.open", side_effect=AssertionError("content read")
        ), patch("os.stat", side_effect=AssertionError("filesystem inspection")):
            with ThreadPoolExecutor(max_workers=4) as executor:
                self.assertEqual(list(executor.map(DETECTOR.operation_skills, [command] * 16)), [expected] * 16)


if __name__ == "__main__":
    unittest.main()

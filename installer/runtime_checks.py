"""Exercise newer analyzers against small synthetic inputs before reuse."""

from difflib import unified_diff
import importlib.util
import os
from pathlib import Path
import sys


def _load(root: Path, name: str):
    source = root / "hooks" / f"mainframe-{name}.py"
    spec = importlib.util.spec_from_file_location(f"mainframe_probe_{name}", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fallow(root: Path, workspace: Path, executable: str) -> bool:
    fallow = _load(root, "fallow-quality")
    file = workspace / "worker.js"
    source = (
        "export function work(value) {\n"
        + "".join(f"    if (value === {i}) return {i};\n" for i in range(35))
        + "    return -1;\n}\n"
    )
    file.write_text(source, encoding="utf-8")
    diff = "".join(unified_diff([], source.splitlines(keepends=True),
                                fromfile="/dev/null", tofile="b/worker.js"))
    result = fallow.analyze(workspace, [file], diff, wholly_owned_paths=[file],
                            executable=executable, timeout_seconds=3)
    return result.unavailable is None and "complexity: worker.js:1" in (result.advisory or "")


def _analyzer(root: Path, workspace: Path, tool: str) -> bool:
    quality = _load(root, "code-quality")
    if tool == "ruff":
        scan = quality._python_findings
        path = workspace / "worker.py"
        checks = (
            (scan("eval(value)\n", path), "Python security S307", 1),
            (scan("value = )\n", path), "Python syntax error", 1),
        )
        if scan("value = 1\n", path):
            return False
    elif tool == "oxlint":
        scan = quality._node_findings
        path = workspace / "worker.mts"
        checks = (
            (scan("eval(value);\n", path), "JavaScript security: eval()", 1),
            (scan("const value: number = ;\n", path), "TypeScript syntax error", 1),
        )
        if scan("export const value: number = 1;\n", path):
            return False
    elif tool == "semgrep":
        tls = 'const agent = new https.Agent({ rejectUnauthorized: false });\n'
        go = (
            'package probe\nimport "github.com/jackc/pgx/v5/pgxpool"\n'
            'func work(pool *pgxpool.Pool) error {\n'
            '  _, err := pool.Query(ctx, "SELECT 1")\n  return err\n}\n'
        )
        checks = (
            (quality._semgrep_security_findings(tls, ".mts"), "JavaScript security review:", 1),
            (quality._pgxpool_findings(go), "Go pgxpool.Query", 4),
        )
    elif tool == "yamllint":
        checks = (
            (quality._yaml_findings("limit: 1\nlimit: 2\n"), "YAML duplicate key", 2),
            (quality._yaml_findings("limits: [1,\n"), "YAML syntax error", 2),
        )
    elif tool == "shellcheck":
        checks = ((quality._shellcheck_findings("#!/bin/bash\ncd target\n", ".bash"),
                   "ShellCheck SC2164", 2),)
    elif tool == "actionlint":
        workflow = "on: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    needs: absent\n    steps:\n      - run: echo build\n"
        checks = ((quality._actionlint_findings(workflow), "actionlint job-needs", 3),)
    elif tool == "kube-linter":
        workload = (
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: worker\n"
            "spec:\n  selector:\n    matchLabels:\n      app: worker\n"
            "  template:\n    metadata:\n      labels:\n        app: worker\n"
            "    spec:\n      containers:\n        - name: worker\n          image: worker:1\n"
        )
        checks = ((quality._kube_findings(workload), "KubeLinter no-readiness-probe", None),)
    elif tool == "squawk":
        checks = (
            (quality._squawk_findings("DROP TABLE history;\n"), "Squawk ban-drop-table", 1),
            (quality._squawk_findings("CREATE INDEX idx ON events (status);\n"), "Squawk require-concurrent-index-creation", 1),
            (quality._squawk_findings("ALTER TABLE events ADD CONSTRAINT c CHECK (id > 0);\n"), "Squawk constraint-missing-not-valid", 1),
            (quality._squawk_findings("ALTER TABLE events ADD COLUMN status text;\n"), "Squawk require-lock-timeout", 1),
        )
        safe = "SET lock_timeout = '1s';\nCREATE INDEX CONCURRENTLY idx ON events (status);\n"
        if quality._squawk_findings(safe):
            return False
    elif tool == "modern-web-guidance":
        scan = quality._modern_web_findings
        checks = (
            (scan('input:invalid { border-color: red; }\n', workspace / "form.css", workspace), "Modern Web validate-input-after-interaction", 1),
            (scan('<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>\n', workspace / "page.html", workspace), "Modern Web secure-external-subresources", 1),
            (scan('document.querySelector("input").addEventListener("keydown", e => { if (e.key === "Enter") submit(); });\n', workspace / "form.ts", workspace), "Modern Web ime-safe-enter-submit", 1),
        )
        safe = (
            ('@supports not selector(:user-invalid) { input:invalid { border-color: red; } }\ninput:user-invalid { border-color: red; }\n', "safe.css"),
            ('document.querySelector("input").addEventListener("keydown", e => { if (e.isComposing) return; if (e.key === "Enter") submit(); });\n', "safe.ts"),
            ('<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js" integrity="sha384-Zml4dHVyZQ==" crossorigin="anonymous"></script>\n', "safe.html"),
        )
        if any(scan(text, workspace / name, workspace) for text, name in safe):
            return False
    else:
        return False
    return all(any(row.label.startswith(prefix) and row.line == line for row in rows)
               for rows, prefix, line in checks)


def main() -> bool:
    tool, source_root, target = sys.argv[1:]
    target = str(Path(target).absolute())
    root = Path(source_root)
    workspace = Path.cwd()
    if tool == "fallow":
        return _fallow(root, workspace, target)
    (workspace / tool).symlink_to(target)
    os.environ["PATH"] = str(workspace) + os.pathsep + os.environ.get("PATH", os.defpath)
    return _analyzer(root, workspace, tool)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

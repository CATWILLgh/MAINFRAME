#!/usr/bin/env python3
"""Run the real Pi engineer release scenario in a disposable Git repository.

This is intentionally not part of the fast suite: it uses configured provider
subscriptions and can take several minutes. It never reads provider keys.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "adapters" / "pi" / "bin" / "mainframe-pi"


def run(argv: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def invoke(project: Path, env: dict[str, str], *arguments: str) -> dict:
    result = run([str(LAUNCHER), "engineer", *arguments], project, env)
    return json.loads(result.stdout)


def initialize_project(project: Path) -> Path:
    run(["git", "init", "-q"], project)
    run(["git", "config", "user.name", "MAINFRAME live test"], project)
    run(["git", "config", "user.email", "mainframe-live@example.invalid"], project)
    write(project / "package.json", '{"type":"module"}\n')
    write(project / "user-staged.txt", "initial staged owner data\n")
    write(project / "user-dirty.txt", "initial dirty owner data\n")
    write(project / "test/check.mjs", """import assert from "node:assert/strict";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { formatAmount } from "../src/amount.js";
const marker = ".agents/runtime/pi/live-first-check-seen";
if (!existsSync(marker)) {
  mkdirSync(".agents/runtime/pi", { recursive: true });
  writeFileSync(marker, "seen\\n");
  console.error("intentional first-pass failure for correction-loop validation");
  process.exit(1);
}
assert.equal(formatAmount(12.5), "12.50");
assert.equal(formatAmount(0), "0.00");
assert.throws(() => formatAmount(Number.NaN));
console.log("amount behavior passed");
""")
    write(project / "test/check-sum.mjs", """import assert from "node:assert/strict";
import { sum } from "../src/sum.js";
assert.equal(sum(2, 3), 5);
console.log("sum behavior passed");
""")
    run(["git", "add", "."], project)
    run(["git", "commit", "-q", "-m", "test: initialize live fixture"], project)
    write(project / "user-staged.txt", "user staged work must survive\n")
    run(["git", "add", "user-staged.txt"], project)
    write(project / "user-dirty.txt", "user dirty work must survive\n")
    return project / ".agents/runtime/pi/requests"


def write_request(request_dir: Path, name: str, *, goal: str, path: str, acceptance: list[str], check: str) -> None:
    write(request_dir / name, json.dumps({
        "schemaVersion": 1, "goal": goal, "writePaths": [path],
        "excludePaths": [], "invariants": ["Do not modify existing files."],
        "acceptance": acceptance,
        "forbiddenFutureStages": ["Do not add packaging or unrelated helpers."],
        "checks": [{"argv": ["node", check], "timeoutMs": 30000}],
    }, indent=2) + "\n")


def run_first_block(project: Path, request_dir: Path, environment: dict[str, str]) -> tuple[dict, dict]:
    write_request(request_dir, "block-1.json", goal="Implement a dependency-free amount formatter.",
                  path="src/amount.js", check="test/check.mjs", acceptance=[
                      "Export formatAmount(amount), returning two decimal places for finite numbers.",
                      "Reject non-number and non-finite values with a descriptive TypeError.",
                      "The exact allowed check passes.",
                  ])
    initial = invoke(project, environment, "--mode", "new", "--request",
                     ".agents/runtime/pi/requests/block-1.json", "--max-turns", "96")
    if initial["status"] != "ready-for-architect-review" or initial["rounds"] < 2:
        raise RuntimeError(f"internal correction loop was not proven: {initial}")
    write(request_dir / "feedback.json", json.dumps({
        "instructions": ["Use the exact TypeError message: amount must be a finite number"],
        "missingEvidence": ["External review requires a stable descriptive error message."],
        "failedCheckIds": [],
    }, indent=2) + "\n")
    resumed = invoke(project, environment, "--mode", "resume", "--feedback",
                     ".agents/runtime/pi/requests/feedback.json", "--max-turns", "96")
    if resumed["status"] != "ready-for-architect-review" or "amount must be a finite number" not in (
        project / "src/amount.js").read_text(encoding="utf-8"):
        raise RuntimeError(f"external correction was not accepted: {resumed}")
    return initial, resumed


def commit_and_run_second(project: Path, request_dir: Path, environment: dict[str, str]) -> tuple[dict, int]:
    run(["git", "add", "src/amount.js"], project)
    run(["git", "commit", "--only", "src/amount.js", "-m", "feat: add amount formatter"], project)
    status = run(["git", "status", "--porcelain=v1"], project).stdout
    if "M  user-staged.txt" not in status or " M user-dirty.txt" not in status:
        raise RuntimeError(f"unrelated owner state was not preserved:\n{status}")
    write_request(request_dir, "block-2.json", goal="Implement a tiny dependency-free sum helper.",
                  path="src/sum.js", check="test/check-sum.mjs",
                  acceptance=["Export sum(a, b) and pass the exact allowed check."])
    second = invoke(project, environment, "--mode", "new", "--request",
                    ".agents/runtime/pi/requests/block-2.json", "--max-turns", "96")
    receipts = list((project / ".agents/runtime/pi/engineer").glob("*/accepted-blocks/*.json"))
    if second["status"] != "ready-for-architect-review" or len(receipts) != 1:
        raise RuntimeError(f"second block or commit reconciliation failed: {second}")
    if second["metrics"]["executor"]["compactions"] < 1:
        raise RuntimeError("new-block compaction was not proven")
    return second, len(receipts)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mainframe-pi-engineer-live-") as temporary:
        project = Path(temporary)
        request_dir = initialize_project(project)
        environment = {**os.environ, "MAINFRAME_PI_TELEMETRY_DB": str(project / ".telemetry/telemetry.db")}
        initial, resumed = run_first_block(project, request_dir, environment)
        second, receipt_count = commit_and_run_second(project, request_dir, environment)
        print(json.dumps({
            "status": "passed", "internal_correction_rounds": initial["rounds"] - 1,
            "external_resume_status": resumed["status"], "accepted_receipts": receipt_count,
            "new_block_compactions": second["metrics"]["executor"]["compactions"],
            "owner_state_preserved": True, "telemetry_db": ".telemetry/telemetry.db",
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Turn one schema-2 harness report into a Spark regression-test candidate.

This worker is launched detached by the dev-only harness-feedback receiver. It
is deliberately best-effort: unavailable auth/quota/model, timeouts, malformed
output, or telemetry failures leave no result and never affect Claude Code.
"""

import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

MODEL = "gpt-5.3-codex-spark"
EFFORT = "medium"
TASK = "hook-regression-candidate"
OUTPUT_SCHEMA = 1
TIMEOUT_SECONDS = 180


def _repo_root():
    override = os.environ.get("MAINFRAME_PROJECT_ROOT")
    return pathlib.Path(override).resolve() if override else pathlib.Path(__file__).resolve().parents[4]


def _output_dir(root):
    override = os.environ.get("MAINFRAME_MODEL_LAB_ROOT")
    base = pathlib.Path(override).resolve() if override else root / "workspace" / "runtime" / "claude-code" / "model-lab"
    return base / "spark" / "hook-regression-candidates"


def _frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---", 2)
    if len(parts) != 3:
        return {}
    out = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def _eligible(meta):
    return (
        meta.get("schema") == "2"
        and meta.get("adapter") == "claude-code"
        and meta.get("model_lab_eligible") == "true"
    )


def _telemetry(root, status, session="", cwd="", elapsed=0):
    scripts = root / "adapters" / "claude-code" / "plugin" / "hooks" / "scripts"
    try:
        sys.path.insert(0, str(scripts))
        import _hooklib
        _hooklib.log_event(
            "model_lab",
            {
                "provider": "openai",
                "model": MODEL,
                "effort": EFFORT,
                "task": TASK,
                "status": status,
                "elapsed_bucket_s": min(300, int(elapsed // 10) * 10),
            },
            {"session_id": session, "cwd": cwd},
        )
    except Exception:
        pass


def _prompt(feedback_path):
    return f"""You are performing read-only quality analysis of MAINFRAME's Claude Code adapter.

Read the harness feedback report at:
{feedback_path}

Inspect only the smallest relevant hook, skill, installer, and test sources in this repository. Determine whether the report suggests a concrete regression test. Return exactly the JSON shape required by the supplied schema.

Rules:
- Do not edit files or propose broad architecture work.
- Treat the report as an observation, not as truth; ground evidence in inspected repository files.
- Recommend one narrow deterministic regression test that would fail for the reported behavior and pass after a correct fix.
- If evidence is incomplete, say so in limitations and lower confidence. Do not invent runtime behavior.
- Keep every field concise and use repository-relative locations where possible.
"""


def _valid_candidate(value):
    if not isinstance(value, dict):
        return False
    if set(value) != {"summary", "evidence", "recommended_test", "confidence", "limitations"}:
        return False
    test = value.get("recommended_test")
    return (
        isinstance(value.get("summary"), str) and bool(value["summary"].strip())
        and isinstance(value.get("evidence"), list)
        and isinstance(test, dict)
        and set(test) == {"name", "purpose", "setup", "action", "assertions"}
        and isinstance(test.get("assertions"), list) and bool(test["assertions"])
        and value.get("confidence") in {"low", "medium", "high"}
        and isinstance(value.get("limitations"), list)
    )


def _atomic_json(path, value):
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        return 0
    root = _repo_root()
    source = pathlib.Path(argv[0]).resolve()
    try:
        raw = source.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError):
        return 0
    meta = _frontmatter(text)
    if not _eligible(meta):
        return 0

    digest = hashlib.sha256(raw).hexdigest()
    output_dir = _output_dir(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{source.stem}-{digest[:12]}.json"
    if destination.exists():
        _telemetry(root, "deduplicated", meta.get("session", ""))
        return 0

    lock = output_dir / f".{digest}.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        try:
            if time.time() - lock.stat().st_mtime > 3600:
                lock.unlink()
        except OSError:
            pass
        return 0

    started = time.monotonic()
    status = "unavailable"
    try:
        schema = root / "adapters" / "claude-code" / "dev" / "model-lab" / "schemas" / "hook-regression-candidate.json"
        codex = os.environ.get("MAINFRAME_CODEX_BIN", "codex")
        fd, response_path = tempfile.mkstemp(prefix="mainframe-spark-", suffix=".json")
        os.close(fd)
        try:
            command = [
                codex, "exec", "--model", MODEL,
                "--config", f'model_reasoning_effort="{EFFORT}"',
                "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--sandbox", "read-only", "--cd", str(root),
                "--output-schema", str(schema),
                "--output-last-message", response_path, "-",
            ]
            proc = subprocess.run(
                command,
                input=_prompt(source),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
            if proc.returncode != 0:
                return 0
            try:
                candidate = json.loads(pathlib.Path(response_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                status = "invalid"
                return 0
            if not _valid_candidate(candidate):
                status = "invalid"
                return 0
            envelope = {
                "schema": OUTPUT_SCHEMA,
                "adapter": "claude-code",
                "producer": "spark-feedback-worker",
                "provider": "openai",
                "model": MODEL,
                "effort": EFFORT,
                "task": TASK,
                "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "source": {"name": source.name, "sha256": digest},
                "candidate": candidate,
            }
            _atomic_json(destination, envelope)
            status = "completed"
            return 0
        finally:
            try:
                os.unlink(response_path)
            except (OSError, UnboundLocalError):
                pass
    except (OSError, subprocess.SubprocessError):
        return 0
    finally:
        _telemetry(
            root, status, meta.get("session", ""),
            os.environ.get("PWD", ""), time.monotonic() - started,
        )
        try:
            lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())

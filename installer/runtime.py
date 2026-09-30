"""Provision shared analyzer executables required by installed MAINFRAME hooks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

from .core import Conflict, atomic_write, encode_json, installation_lock, regular_bytes


TOOL_SPECS = {
    "ruff": ("python", "ruff", "0.15.15"),
    "semgrep": ("python", "semgrep", "1.164.0"),
    "oxlint": ("node", "oxlint", "1.67.0"),
    "fallow": ("node", "fallow", "2.92.1"),
}
CODE_QUALITY_TOOLS = ("ruff", "oxlint", "semgrep")
FALLOW_TOOLS = ("fallow",)


def runtime_root(home: Path) -> Path:
    return home.resolve() / ".local/share/mainframe/runtime"


def runtime_bin(home: Path) -> Path:
    return runtime_root(home) / "bin"


def tools_for_hook(all_tools: tuple[str, ...], hook: str | None) -> tuple[str, ...]:
    if hook is None:
        return all_tools
    if hook == "mainframe-code-quality":
        return tuple(name for name in all_tools if name in CODE_QUALITY_TOOLS)
    if hook == "mainframe-fallow-quality":
        return tuple(name for name in all_tools if name in FALLOW_TOOLS)
    return ()


def _version(executable: Path) -> str | None:
    try:
        result = subprocess.run(
            [str(executable), "--version"], capture_output=True, text=True,
            timeout=20, check=False,
            env={**os.environ, "SEMGREP_SEND_METRICS": "off",
                 "FALLOW_TELEMETRY": "off", "FALLOW_TELEMETRY_DISABLED": "1",
                 "FALLOW_UPDATE_CHECK": "off"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    match = re.search(r"(?<!\d)(\d+\.\d+\.\d+)(?!\d)", result.stdout + "\n" + result.stderr)
    return match.group(1) if match else None


def _parts(value: str) -> tuple[int, int, int]:
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def _compatible(name: str, executable: Path) -> tuple[bool, str | None]:
    version = _version(executable)
    tested = TOOL_SPECS[name][2]
    return bool(version and _parts(version) == _parts(tested)), version


def _manifest(root: Path) -> dict:
    raw = regular_bytes(root / "installation.json")
    if raw is None:
        return {}
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) and value.get("schema") == 1 else {}


def status(home: Path, required: tuple[str, ...]) -> dict:
    required = tuple(dict.fromkeys(required))
    if not required:
        return {"ready": True, "required": [], "missing": []}
    root = runtime_root(home)
    record = _manifest(root)
    installed = record.get("tools", {}) if isinstance(record.get("tools"), dict) else {}
    missing: list[str] = []
    versions: dict[str, str] = {}
    for name in required:
        if name not in TOOL_SPECS:
            raise Conflict(f"Unknown MAINFRAME runtime dependency: {name}")
        shim = root / "bin" / name
        row = installed.get(name)
        if (not isinstance(row, dict) or not shim.is_file() or shim.is_symlink()
                or not os.access(shim, os.X_OK)):
            missing.append(name)
            continue
        compatible, version = _compatible(name, shim)
        if not compatible or version is None:
            missing.append(name)
            continue
        versions[name] = version
    return {
        "ready": not missing,
        "required": list(required),
        "missing": missing,
        "versions": versions,
        "bin": str(root / "bin"),
    }


def _run(command: list[str], *, timeout: int, env: dict[str, str] | None = None) -> None:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise Conflict("MAINFRAME runtime dependency installation could not start.") from error
    if result.returncode:
        raise Conflict("MAINFRAME runtime dependency installation failed; no hook files were changed.")


def _safe_rebuild(path: Path, root: Path) -> None:
    if path.exists():
        if path.is_symlink() or root not in path.parents:
            raise Conflict("Refusing to replace an unowned runtime dependency path.")
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)


def _managed_python(root: Path, names: list[str]) -> dict[str, Path]:
    target = root / "packages/python"
    _safe_rebuild(target, root)
    _run([sys.executable, "-m", "venv", str(target)], timeout=120)
    python = target / "bin/python"
    packages = [f"{TOOL_SPECS[name][1]}=={TOOL_SPECS[name][2]}" for name in names]
    environment = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1"}
    _run([str(python), "-m", "pip", "install", "--no-input", "--no-cache-dir", *packages],
         timeout=900, env=environment)
    return {name: (target / "bin" / name).resolve() for name in names}


def _managed_node(root: Path, names: list[str]) -> dict[str, Path]:
    npm = shutil.which("npm")
    if not npm:
        raise Conflict("npm is required to install Oxlint or Fallow for active MAINFRAME hooks.")
    target = root / "packages/node"
    _safe_rebuild(target, root)
    target.mkdir(parents=True, mode=0o700)
    packages = [f"{TOOL_SPECS[name][1]}@{TOOL_SPECS[name][2]}" for name in names]
    environment = {**os.environ, "NO_UPDATE_NOTIFIER": "1", "NPM_CONFIG_UPDATE_NOTIFIER": "false"}
    _run([npm, "install", "--prefix", str(target), "--no-audit", "--no-fund",
          "--save-exact", *packages], timeout=900, env=environment)
    return {name: (target / "node_modules/.bin" / name).resolve() for name in names}


def _candidates(root: Path, home: Path, wanted: list[str], existing: dict) -> tuple[dict[str, Path], dict[str, list[str]]]:
    resolved: dict[str, Path] = {}
    missing: dict[str, list[str]] = {"python": [], "node": []}
    for name in wanted:
        if name not in TOOL_SPECS:
            continue
        row = existing.get(name) if isinstance(existing, dict) else None
        recorded = row.get("executable") if isinstance(row, dict) else None
        executable = (Path(recorded).resolve()
                      if isinstance(recorded, str) and Path(recorded).is_absolute()
                      else None)
        compatible, _ = _compatible(name, executable) if executable else (False, None)
        if not compatible:
            located = shutil.which(name)
            executable = Path(located).resolve() if located else None
            if executable == (runtime_bin(home) / name).resolve():
                executable = None
        compatible, _ = _compatible(name, executable) if executable else (False, None)
        if compatible and executable:
            resolved[name] = executable
        else:
            missing[TOOL_SPECS[name][0]].append(name)
    managed_targets = {
        "python": root / "packages/python",
        "node": root / "packages/node",
    }
    for ecosystem, names in missing.items():
        if not names:
            continue
        target = managed_targets[ecosystem]
        for name, executable in list(resolved.items()):
            if TOOL_SPECS[name][0] == ecosystem and executable.is_relative_to(target):
                names.append(name)
                del resolved[name]
        names.sort()
    return resolved, missing


def ensure(home: Path, required: tuple[str, ...]) -> dict:
    """Provision required tools before any hook registration is changed."""
    required = tuple(dict.fromkeys(required))
    if not required:
        return status(home, required)
    root = runtime_root(home)
    with installation_lock(root / ".install.lock"):
        current = status(home, required)
        if current["ready"]:
            return current
        existing = _manifest(root).get("tools", {})
        retained = set(existing) if isinstance(existing, dict) else set()
        wanted = sorted(retained.union(required))
        candidates, missing = _candidates(root, home, wanted, existing)
        if missing["node"] and not shutil.which("npm"):
            raise Conflict("npm is required to install Oxlint or Fallow for active MAINFRAME hooks; no hook files were changed.")
        if missing["python"]:
            candidates.update(_managed_python(root, missing["python"]))
        if missing["node"]:
            candidates.update(_managed_node(root, missing["node"]))
        rows: dict[str, dict[str, str]] = {}
        for name in wanted:
            executable = candidates.get(name)
            if executable is None:
                raise Conflict(f"MAINFRAME runtime dependency {name} could not be resolved.")
            compatible, version = _compatible(name, executable)
            if not compatible or version is None:
                raise Conflict(f"MAINFRAME runtime dependency {name} failed its version probe.")
            shim = runtime_bin(home) / name
            body = "#!/bin/sh\nexec " + shlex.quote(str(executable)) + ' "$@"\n'
            atomic_write(shim, body.encode(), 0o755)
            rows[name] = {"version": version, "executable": str(executable)}
        atomic_write(root / "installation.json", encode_json({"schema": 1, "tools": rows}), 0o600)
    result = status(home, required)
    if not result["ready"]:
        raise Conflict("MAINFRAME runtime dependencies did not converge; no hook files were changed.")
    return result

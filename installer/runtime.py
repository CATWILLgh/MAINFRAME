"""Provision shared per-user executables for MAINFRAME hooks and workflows."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from .core import (
    Change, Conflict, atomic_write, encode_json, installation_lock, observed, regular_bytes,
    restore, transact,
)


TOOL_SPECS = {
    "ruff": ("python", "ruff", "0.15.15"),
    "semgrep": ("python", "semgrep", "1.164.0"),
    "oxlint": ("node", "oxlint", "1.67.0"),
    "fallow": ("node", "fallow", "2.92.1"),
}
CODE_QUALITY_TOOLS = ("ruff", "oxlint", "semgrep")
FALLOW_TOOLS = ("fallow",)
OPENSPEC_TOOLS = ("openspec",)
OPENSPEC_PACKAGE = "@fission-ai/openspec"
OPENSPEC_VERSION = "1.16.1"
OPENSPEC_NODE_MINIMUM = (22, 12, 0)
OPENSPEC_ENV = {"OPENSPEC_TELEMETRY": "0", "OPENSPEC_NO_UPDATE_CHECK": "1"}


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


def _version(executable: Path, *arguments: Path, path: str | None = None,
             exact: bool = False) -> str | None:
    environment = {
        **os.environ, "SEMGREP_SEND_METRICS": "off",
        "FALLOW_TELEMETRY": "off", "FALLOW_TELEMETRY_DISABLED": "1",
        "FALLOW_UPDATE_CHECK": "off", **OPENSPEC_ENV,
    }
    if path is not None:
        environment["PATH"] = path
    try:
        result = subprocess.run(
            [str(executable), *(str(argument) for argument in arguments), "--version"],
            capture_output=True, text=True, timeout=20, check=False, env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    if exact:
        output = result.stdout.strip() or result.stderr.strip()
        match = re.fullmatch(r"(?:openspec\s+)?v?(\d+\.\d+\.\d+)", output, re.IGNORECASE)
    else:
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


def _tool_rows(record: dict) -> dict:
    rows = record.get("tools")
    return rows if isinstance(rows, dict) else {}


def status(home: Path, required: tuple[str, ...]) -> dict:
    required = tuple(dict.fromkeys(required))
    if not required:
        return {"ready": True, "required": [], "missing": []}
    root = runtime_root(home)
    installed = _tool_rows(_manifest(root))
    missing: list[str] = []
    versions: dict[str, str] = {}
    for name in required:
        if name not in TOOL_SPECS and name not in OPENSPEC_TOOLS:
            raise Conflict(f"Unknown MAINFRAME runtime dependency: {name}")
        shim = root / "bin" / name
        row = installed.get(name)
        if (not isinstance(row, dict) or not shim.is_file() or shim.is_symlink()
                or not os.access(shim, os.X_OK)):
            missing.append(name)
            continue
        if name == "openspec":
            version = _openspec_status(shim, row)
        else:
            compatible, detected = _compatible(name, shim)
            version = detected if compatible else None
        if version is None:
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


def _run(command: list[str], *, timeout: int, env: dict[str, str] | None = None,
         cwd: Path | None = None) -> None:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False,
            env=env, cwd=cwd,
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


def _recorded_path(row: dict, key: str) -> Path | None:
    value = row.get(key)
    return Path(value) if isinstance(value, str) and Path(value).is_absolute() else None


def _openspec_command(row: dict, shim: Path) -> tuple[Path, ...] | None:
    executable = _recorded_path(row, "executable")
    if executable is None or executable == shim:
        return None
    if "node" not in row:
        return (executable,)
    node = _recorded_path(row, "node")
    return (node, executable) if node and node != shim else None


def _openspec_shim(command: tuple[Path, ...]) -> bytes:
    exports = "\n".join(f"export {key}={value}" for key, value in OPENSPEC_ENV.items())
    return f'#!/bin/sh\n{exports}\nexec {shlex.join(map(str, command))} "$@"\n'.encode()


def _supported_openspec_node(node: Path) -> bool:
    version = _version(node, exact=True)
    return bool(version and _parts(version) >= OPENSPEC_NODE_MINIMUM)


def _compatible_openspec(*command: Path) -> bool:
    return _version(*command, path=os.defpath, exact=True) == OPENSPEC_VERSION


def _openspec_status(shim: Path, row: dict) -> str | None:
    command = _openspec_command(row, shim)
    if (command is None or row.get("version") != OPENSPEC_VERSION
            or regular_bytes(shim) != _openspec_shim(command)
            or (len(command) == 2 and not _supported_openspec_node(command[0]))):
        return None
    return OPENSPEC_VERSION if _compatible_openspec(shim) else None


def _openspec_node(previous: tuple[Path, ...] | None) -> Path | None:
    if previous and len(previous) == 2 and _supported_openspec_node(previous[0]):
        return previous[0]
    located = shutil.which("node")
    node = Path(located).resolve() if located else None
    return node if node and _supported_openspec_node(node) else None


def _openspec_candidate(shim: Path, previous: tuple[Path, ...] | None,
                        node: Path | None) -> tuple[Path, ...] | None:
    if previous and len(previous) == 2:
        previous = (node, previous[-1]) if node else None
    if previous and previous[-1].resolve() != shim and _compatible_openspec(*previous):
        return previous
    for directory in os.get_exec_path():
        located = shutil.which("openspec", path=directory)
        if not located:
            continue
        executable = Path(located).resolve()
        if executable == shim:
            continue
        if executable.name == "openspec.js" and executable.parent.name == "bin":
            if node is None:
                continue
            command = (node, executable)
        else:
            command = (executable,)
        if _compatible_openspec(*command):
            return command
    return None


def _install_openspec(target: Path, npm: str, node: Path) -> tuple[Path, ...]:
    environment = {
        **os.environ, **OPENSPEC_ENV, "NO_UPDATE_NOTIFIER": "1",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "PATH": str(node.parent) + os.pathsep + os.environ.get("PATH", os.defpath),
    }
    _run([npm, "install", "--prefix", str(target), "--global=false", "--ignore-scripts",
          "--no-audit", "--no-fund", "--save-exact", f"{OPENSPEC_PACKAGE}@{OPENSPEC_VERSION}"],
         timeout=900, env=environment, cwd=target)
    entrypoint = target / "node_modules" / OPENSPEC_PACKAGE / "bin/openspec.js"
    if not _compatible_openspec(node, entrypoint):
        raise Conflict("MAINFRAME runtime dependency openspec failed its version probe.")
    return (node, entrypoint)


def _ensure_openspec(root: Path, shim: Path, journal: Path, allowed) -> None:
    manifest_path = root / "installation.json"
    manifest_snapshot = observed(manifest_path)
    manifest = _manifest(root)
    existing = _tool_rows(manifest)
    row = existing.get("openspec")
    previous = _openspec_command(row, shim) if isinstance(row, dict) else None
    snapshot = observed(shim)
    if snapshot[0] is not None and (previous is None or snapshot[0] != _openspec_shim(previous)):
        raise Conflict(f"Existing file has no installer ownership: {shim}")

    node = _openspec_node(previous)
    command = _openspec_candidate(shim, previous, node)
    staged = None
    try:
        if command is None:
            if node is None:
                minimum = ".".join(map(str, OPENSPEC_NODE_MINIMUM))
                raise Conflict(f"Node.js {minimum} or newer on PATH is required to install OpenSpec.")
            npm = shutil.which("npm")
            if npm is None:
                raise Conflict("npm is required to install OpenSpec.")
            packages = root / "packages"
            if packages.is_symlink() or (packages.exists() and not packages.is_dir()):
                raise Conflict(f"Refusing to replace an unowned runtime dependency path: {packages}")
            packages.mkdir(mode=0o700, exist_ok=True)
            # Keep this prefix separate from the analyzers and the active OpenSpec release.
            staged = Path(tempfile.mkdtemp(prefix="openspec-", dir=packages))
            command = _install_openspec(staged, str(Path(npm).absolute()), node)

        row = {"version": OPENSPEC_VERSION, "executable": str(command[-1])}
        if len(command) == 2:
            row["node"] = str(command[0])
        record = {**manifest, "schema": 1, "tools": {**existing, "openspec": row}}
        transact([
            Change.from_snapshot(shim, snapshot, _openspec_shim(command), 0o755),
            Change.from_snapshot(manifest_path, manifest_snapshot, encode_json(record)),
        ], journal, allowed)
    except BaseException:
        if staged is not None and not journal.exists():
            shutil.rmtree(staged)
        raise


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
    """Provision only the requested runtime capabilities in shared user storage."""
    required = tuple(dict.fromkeys(required))
    if not required:
        return status(home, required)
    root = runtime_root(home)
    shim = root / "bin/openspec"
    journal = root / ".openspec-recovery.json"

    def openspec_paths(path):
        return path in (shim, root / "installation.json")

    with installation_lock(root / ".install.lock"):
        restore(journal, openspec_paths)
        current = status(home, required)
        if current["ready"]:
            return current
        if "openspec" in current["missing"]:
            _ensure_openspec(root, shim, journal, openspec_paths)
        if any(name in TOOL_SPECS for name in current["missing"]):
            _ensure_analyzers(root, home, required)
    result = status(home, required)
    if not result["ready"]:
        raise Conflict("MAINFRAME runtime dependencies did not converge; no hook files were changed.")
    return result


def _ensure_analyzers(root: Path, home: Path, required: tuple[str, ...]) -> None:
    manifest = _manifest(root)
    existing = _tool_rows(manifest)
    wanted = sorted(set(TOOL_SPECS).intersection(set(existing).union(required)))
    candidates, missing = _candidates(root, home, wanted, existing)
    if missing["node"] and not shutil.which("npm"):
        raise Conflict("npm is required to install Oxlint or Fallow for active MAINFRAME hooks; no hook files were changed.")
    if missing["python"]:
        candidates.update(_managed_python(root, missing["python"]))
    if missing["node"]:
        candidates.update(_managed_node(root, missing["node"]))
    rows = dict(existing)
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
    atomic_write(root / "installation.json", encode_json({**manifest, "schema": 1, "tools": rows}), 0o600)

"""Provision shared per-user executables for MAINFRAME hooks and workflows."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from .core import (
    Change, Conflict, atomic_write, digest, encode_json, installation_lock, observed, regular_bytes,
    restore, transact,
)


TOOL_SPECS = {
    "ruff": ("python", "ruff", "0.15.15"),
    "semgrep": ("python", "semgrep", "1.164.0"),
    "yamllint": ("python", "yamllint", "1.38.0"),
    "oxlint": ("node", "oxlint", "1.67.0"),
    "fallow": ("node", "fallow", "2.92.1"),
    "shellcheck": ("release", "koalaman/shellcheck", "0.11.0"),
    "actionlint": ("release", "rhysd/actionlint", "1.7.12"),
    "kube-linter": ("release", "stackrox/kube-linter", "0.8.3"),
    "squawk": ("release", "sbdchd/squawk", "2.72.0"),
}
CODE_QUALITY_TOOLS = ("ruff", "oxlint", "semgrep", "yamllint", "shellcheck", "actionlint", "kube-linter", "squawk")
FALLOW_TOOLS = ("fallow",)
OPENSPEC_TOOLS = ("openspec",)
OPENSPEC_PACKAGE = "@fission-ai/openspec"
OPENSPEC_VERSION = "1.16.1"
OPENSPEC_NODE_MINIMUM = (22, 12, 0)
OPENSPEC_ENV = {"OPENSPEC_TELEMETRY": "0", "OPENSPEC_NO_UPDATE_CHECK": "1"}

# Upstream SHA256s from the pinned official GitHub release assets.
# Ordered by (darwin amd64, darwin arm64, linux amd64, linux arm64).
_RELEASE_SHA256 = {
    "shellcheck": (
        "3c89db4edcab7cf1c27bff178882e0f6f27f7afdf54e859fa041fca10febe4c6",
        "56affdd8de5527894dca6dc3d7e0a99a873b0f004d7aabc30ae407d3f48b0a79",
        "8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198",
        "12b331c1d2db6b9eb13cfca64306b1b157a86eb69db83023e261eaa7e7c14588",
    ),
    "actionlint": (
        "5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644",
        "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
        "325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6",
    ),
    "kube-linter": (
        "c62e8af3c9df2557c7a3922119ea1b35597794737d1ccad493f63a0d66e7b8fc",
        "6e3443a8ff8625a9fc31a38682c783988d7559018f7ff707a4f8c77c18c92f14",
        "1a6d8419b11971372971fdbc22682b684ebfb7cf1c39591662d1b6ca736c41df",
        "802e1b09eabd08f6f0a060a6b8ab2bf7bc7e6bf4f673bb2692303704c84b3e22",
    ),
    "squawk": (
        "ba255f16260663457e66e6888fcecebcfb64e9e35d7ef041e92834f8c9d2d849",
        "f2cced2d962a5642a089a90a0cf826c65786a59a0a2bd3cd96ddadff3583c2b4",
        "b4cda2069a3ca5b75b47f025b569df9e6a762262b9258bc4db3f43381f8544d8",
        "a6d0eb855ca69fa2a70e518c99b24bd4fd7d2f869a884e139de4730c0ca0be2c",
    ),
}
_RELEASE_PLATFORMS = (
    ("darwin", "amd64"), ("darwin", "arm64"), ("linux", "amd64"), ("linux", "arm64"),
)
_MAX_NATIVE_BYTES = 64_000_000


def _native_release(name: str) -> tuple[str, str, str, str | None, str]:
    _, repo, version = TOOL_SPECS[name]
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(machine, machine)
    try:
        index = _RELEASE_PLATFORMS.index((system, arch))
    except ValueError as error:
        raise Conflict(f"No pinned {name} release for {system}/{machine}.") from error
    if name == "shellcheck":
        archive_arch = "x86_64" if arch == "amd64" else "aarch64"
        asset = f"shellcheck-v{version}.{system}.{archive_arch}.tar.xz"
        member = f"shellcheck-v{version}/shellcheck"
    elif name == "actionlint":
        asset, member = f"actionlint_{version}_{system}_{arch}.tar.gz", "actionlint"
    elif name == "kube-linter":
        suffix = "_arm64" if arch == "arm64" else ""
        asset, member = f"kube-linter-{system}{suffix}.tar.gz", "kube-linter"
    elif name == "squawk":
        suffix = "x64" if arch == "amd64" else "arm64"
        prefix = "linux-musl" if system == "linux" else system
        asset, member = f"squawk-{prefix}-{suffix}", None
    else:
        raise Conflict(f"No pinned native release mapping for {name}.")
    return repo, f"v{version}", asset, member, _RELEASE_SHA256[name][index]


def _download_release(repo: str, tag: str, asset: str) -> bytes:
    url = f"https://github.com/{repo}/releases/download/{tag}/{asset}"
    with urlopen(Request(url, headers={"User-Agent": "MAINFRAME-installer"}), timeout=30) as response:
        target = urlsplit(response.geturl())
        if target.scheme != "https" or target.hostname not in {
            "github.com", "release-assets.githubusercontent.com",
        }:
            raise ValueError("unexpected release host")
        return response.read(_MAX_NATIVE_BYTES + 1)


def _managed_release(root: Path, name: str) -> Path:
    repo, tag, asset, member, checksum = _native_release(name)
    target = root / "packages/release" / name / tag / name
    try:
        data = _download_release(repo, tag, asset)
        if len(data) > _MAX_NATIVE_BYTES or digest(data) != checksum:
            raise Conflict(f"{name} release checksum did not match the pinned artifact.")
        if member is not None:
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                entry = archive.getmember(member)
                if not entry.isfile() or not 0 < entry.size <= _MAX_NATIVE_BYTES:
                    raise ValueError("invalid release member")
                stream = archive.extractfile(entry)
                if stream is None:
                    raise ValueError("missing executable")
                with stream:
                    data = stream.read()
        regular_bytes(target)
        atomic_write(target, data, 0o755)
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        raise Conflict(f"Could not prepare the pinned {name} release.") from error
    if not _compatible(name, target)[0]:
        raise Conflict(f"MAINFRAME runtime dependency {name} failed its version probe.")
    return target


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
             exact: bool = False, flag: str = "--version") -> str | None:
    environment = {
        **os.environ, "SEMGREP_SEND_METRICS": "off",
        "FALLOW_TELEMETRY": "off", "FALLOW_TELEMETRY_DISABLED": "1",
        "FALLOW_UPDATE_CHECK": "off", **OPENSPEC_ENV,
    }
    if path is not None:
        environment["PATH"] = path
    try:
        result = subprocess.run(
            [str(executable), *(str(argument) for argument in arguments), flag],
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
    version_flag = {"actionlint": "-version", "kube-linter": "version"}.get(name, "--version")
    version = _version(executable, flag=version_flag)
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
    missing: dict[str, list[str]] = {"python": [], "node": [], "release": []}
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
    for ecosystem, target in managed_targets.items():
        names = missing[ecosystem]
        if not names:
            continue
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
    for name in missing["release"]:
        candidates[name] = _managed_release(root, name)
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

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
import signal
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


# Each version is both the minimum and the tested distribution used for
# provisioning. Reuse above the minimum requires a compatibility sample.
TOOL_SPECS = {
    "ruff": ("python", "ruff", "0.15.15"),
    "semgrep": ("python", "semgrep", "1.164.0"),
    "yamllint": ("python", "yamllint", "1.38.0"),
    "oxlint": ("node", "oxlint", "1.67.0"),
    "fallow": ("node", "fallow", "2.92.1"),
    "modern-web-guidance": ("node", "modern-web-guidance", "1.0.0"),
    "shellcheck": ("release", "koalaman/shellcheck", "0.11.0"),
    "actionlint": ("release", "rhysd/actionlint", "1.7.12"),
    "kube-linter": ("release", "stackrox/kube-linter", "0.8.3"),
    "squawk": ("release", "sbdchd/squawk", "2.72.0"),
}
CODE_QUALITY_TOOLS = ("ruff", "oxlint", "semgrep", "yamllint", "shellcheck", "actionlint", "kube-linter", "squawk", "modern-web-guidance")
FALLOW_TOOLS = ("fallow",)
WEB_COMPILER_VERSION = "5.57.3"
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
    generation = _new_generation(root, "release")
    target = generation / name
    try:
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
            atomic_write(target, data, 0o755)
        except (OSError, ValueError, KeyError, tarfile.TarError) as error:
            raise Conflict(f"Could not prepare the pinned {name} release.") from error
        if _analyzer_release(name, target) != TOOL_SPECS[name][2]:
            raise Conflict(f"MAINFRAME runtime dependency {name} failed its version probe.")
        return target
    except BaseException:
        _discard_generation(generation, root)
        raise


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


def _probe_environment() -> dict[str, str]:
    return {
        **os.environ, "SEMGREP_SEND_METRICS": "off",
        "SEMGREP_ENABLE_VERSION_CHECK": "false",
        "FALLOW_TELEMETRY": "off", "FALLOW_TELEMETRY_DISABLED": "1",
        "FALLOW_UPDATE_CHECK": "off", **OPENSPEC_ENV,
        "DISABLE_TELEMETRY": "1", "ENABLE_FILE_LOGGING": "false",
    }


def _version(executable: Path, *arguments: Path, path: str | None = None,
             exact: bool = False, flag: str = "--version",
             env: dict[str, str] | None = None) -> str | None:
    environment = dict(_probe_environment() if env is None else env)
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
        match = re.fullmatch(r"(?:openspec\s+)?v?(\d+\.\d+\.\d+)(?:\+[\w.-]+)?", output, re.IGNORECASE)
    else:
        match = re.search(r"(?<![\d.])(\d+\.\d+\.\d+)([-.\w]*)",
                          result.stdout + "\n" + result.stderr)
        if match and match[2]:
            return None
    return match.group(1) if match else None


def _parts(value: str) -> tuple[int, int, int]:
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def _web_parser_modules(executable: Path) -> tuple[Path, Path, str]:
    entry = executable.resolve()
    scanner = entry.with_name("legacy-scan.mjs")
    if not scanner.is_file():
        raise Conflict("Modern Web Guidance's parser module is unavailable.")
    for parent in entry.parents:
        package = parent / "node_modules/svelte"
        compiler = package / "compiler/index.js"
        try:
            version = json.loads((package / "package.json").read_text())["version"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if (isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version)
                and _parts(version) >= _parts(WEB_COMPILER_VERSION) and compiler.is_file()):
            return scanner, compiler.resolve(), version
    raise Conflict("The prepared web runtime requires the tested Svelte compiler or a compatible newer release.")


def _analyzer_shim(name: str, executable: Path) -> bytes:
    body = "#!/bin/sh\n"
    if name == "modern-web-guidance":
        scanner, compiler, _ = _web_parser_modules(executable)
        body += ('if [ "${1-}" = "--mainframe-rules" ]; then\n'
                 '  shift\n  [ "$#" -ge 1 ] || exit 2\n'
                 '  mainframe_rules=$1\n  shift\n'
                 '  exec node --input-type=module --eval "$mainframe_rules" -- mainframe-web-check '
                 + shlex.quote(str(scanner)) + " " + shlex.quote(str(compiler)) + ' "$@"\nfi\n')
    return (body + "exec " + shlex.quote(str(executable)) + ' "$@"\n').encode()


def _analyzer_release(name: str, executable: Path) -> str | None:
    flag = {"actionlint": "-version", "kube-linter": "version"}.get(name, "--version")
    if name == "semgrep":
        with tempfile.TemporaryDirectory(prefix="mainframe-semgrep-version-") as directory:
            environment = _probe_environment()
            environment.pop("SEMGREP_APP_TOKEN", None)
            environment.update(SEMGREP_LOG_FILE=str(Path(directory) / "semgrep.log"),
                               SEMGREP_SETTINGS_FILE=str(Path(directory) / "settings.yml"))
            return _version(executable, flag=flag, env=environment)
    return _version(executable, flag=flag)


def _check_analyzer(name: str, executable: Path) -> bool:
    probe = Path(__file__).with_name("runtime_checks.py")
    try:
        with tempfile.TemporaryDirectory(prefix="mainframe-runtime-probe-") as directory:
            if name == "modern-web-guidance":
                prepared = Path(directory) / "prepared" / name
                prepared.parent.mkdir()
                prepared.write_bytes(_analyzer_shim(name, executable))
                prepared.chmod(0o755)
                executable = prepared
            with subprocess.Popen(
                [sys.executable, "-B", str(probe), name, str(probe.parent.parent), str(executable)],
                cwd=directory, env={**_probe_environment(), "TMPDIR": directory}, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            ) as process:
                try:
                    return process.wait(timeout=5) == 0
                except subprocess.TimeoutExpired:
                    # A timed-out probe can still have the analyzer as a child.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    return False
    except (OSError, Conflict, subprocess.SubprocessError):
        return False


def _analyzer_version(name: str, executable: Path) -> str | None:
    version = _analyzer_release(name, executable)
    minimum = TOOL_SPECS[name][2]
    compiler_tested = True
    if name == "modern-web-guidance":
        try:
            _, _, compiler_version = _web_parser_modules(executable)
            compiler_tested = compiler_version == WEB_COMPILER_VERSION
        except Conflict:
            return None
    if version == minimum and compiler_tested:
        return version
    if version is not None and _parts(version) >= _parts(minimum) and _check_analyzer(name, executable):
        return version
    return None


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
        elif name == "modern-web-guidance":
            executable = _recorded_path(row, "executable")
            try:
                expected = _analyzer_shim(name, executable) if executable else None
                version = (_analyzer_version(name, executable)
                           if executable and regular_bytes(shim) == expected else None)
            except (OSError, Conflict):
                version = None
        else:
            version = _analyzer_version(name, shim)
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
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=env, cwd=cwd, start_new_session=True,
        )
        try:
            process.communicate(timeout=timeout)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            finally:
                process.stdout.close()
                process.stderr.close()
    except (OSError, subprocess.SubprocessError) as error:
        raise Conflict("MAINFRAME runtime dependency installation could not start.") from error
    if process.returncode:
        raise Conflict("MAINFRAME runtime dependency installation failed; no hook files were changed.")


def _npm_install(command: list[str], environment: dict[str, str], *, cwd: Path | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="mainframe-npm-cache-") as directory:
        logs = str(Path(directory) / "_logs")
        scratch = Path(directory) / "tmp"
        scratch.mkdir(mode=0o700)
        environment = {
            **environment, "NPM_CONFIG_CACHE": directory, "npm_config_cache": directory,
            "NPM_CONFIG_LOGS_DIR": logs, "npm_config_logs_dir": logs,
            "TMPDIR": str(scratch), "TMP": str(scratch), "TEMP": str(scratch),
        }
        _run([*command, "--cache", directory, "--logs-dir", logs],
             timeout=900, env=environment, cwd=cwd)


def _runtime_directory(path: Path, root: Path) -> None:
    if root not in path.parents:
        raise Conflict("Refusing to replace an unowned runtime dependency path.")
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise Conflict(f"Refusing to change a symlink or its child: {path}")
        if candidate.exists() and not candidate.is_dir():
            raise Conflict(f"Expected a runtime dependency directory: {candidate}")


def _new_generation(root: Path, ecosystem: str) -> Path:
    parent = root / "packages" / ecosystem
    _runtime_directory(parent, root)
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return Path(tempfile.mkdtemp(prefix=f"mainframe-{ecosystem}-", dir=parent))


def _discard_generation(path: Path, root: Path) -> None:
    _runtime_directory(path, root)
    if path.exists():
        shutil.rmtree(path)


def _managed_python(root: Path, names: list[str]) -> dict[str, Path]:
    target = _new_generation(root, "python")
    python = target / "bin/python"
    packages = [f"{TOOL_SPECS[name][1]}=={TOOL_SPECS[name][2]}" for name in names]
    filesystem_root = target.resolve().anchor
    environment = {
        **os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1",
        "PIP_PREFIX": str(target), "PIP_ROOT": filesystem_root,
        "PIP_USER": "0", "PIP_LOG": os.devnull, "PIP_REPORT": os.devnull,
    }
    environment.pop("PIP_TARGET", None)
    try:
        with tempfile.TemporaryDirectory(prefix=".mainframe-work-", dir=target) as directory:
            environment.update(TMPDIR=directory, TMP=directory, TEMP=directory)
            _run([sys.executable, "-m", "venv", str(target)], timeout=120, env=environment)
            _run([str(python), "-m", "pip", "install", "--no-input", "--no-cache-dir",
                  "--target", "", "--prefix", str(target), "--root", filesystem_root, "--no-user",
                  "--log", os.devnull, "--report", os.devnull, *packages],
                 timeout=900, env=environment, cwd=target)
        executables = {name: (target / "bin" / name).resolve() for name in names}
        for name, executable in executables.items():
            if not executable.is_relative_to(target):
                raise Conflict(f"Prepared runtime dependency {name} is outside its allocated generation.")
            if _analyzer_release(name, executable) != TOOL_SPECS[name][2]:
                raise Conflict(f"MAINFRAME runtime dependency {name} failed its version probe.")
        return executables
    except BaseException:
        _discard_generation(target, root)
        raise


def _managed_node(root: Path, names: list[str]) -> dict[str, Path]:
    npm = shutil.which("npm")
    if not npm:
        raise Conflict("npm is required to install active MAINFRAME Node.js analyzers.")
    if "modern-web-guidance" in names:
        node = shutil.which("node")
        version = _version(Path(node), exact=True) if node else None
        if version is None or _parts(version) < (22, 0, 0):
            raise Conflict("Modern Web Guidance requires Node.js 22 or later before runtime preparation.")
    target = _new_generation(root, "node")
    packages = [f"{TOOL_SPECS[name][1]}@{TOOL_SPECS[name][2]}" for name in names]
    if "modern-web-guidance" in names:
        packages.append(f"svelte@{WEB_COMPILER_VERSION}")
    environment = {**os.environ, "NO_UPDATE_NOTIFIER": "1", "NPM_CONFIG_UPDATE_NOTIFIER": "false"}
    try:
        _npm_install([npm, "install", "--prefix", str(target), "--no-audit", "--no-fund",
                      "--save-exact", *packages], environment)
        executables = {name: (target / "node_modules/.bin" / name).resolve() for name in names}
        for name, executable in executables.items():
            if not executable.is_relative_to(target):
                raise Conflict(f"Prepared runtime dependency {name} is outside its allocated generation.")
            if _analyzer_release(name, executable) != TOOL_SPECS[name][2]:
                raise Conflict(f"MAINFRAME runtime dependency {name} failed its version probe.")
            if name == "modern-web-guidance" and _web_parser_modules(executable)[2] != WEB_COMPILER_VERSION:
                raise Conflict("The prepared Svelte parser failed its version probe.")
        return executables
    except BaseException:
        _discard_generation(target, root)
        raise


def _cleanup_generations(root: Path, previous: dict, rows: dict, ecosystem: str) -> None:
    parent = root / "packages" if ecosystem == "openspec" else root / "packages" / ecosystem
    candidates = {generation for name, row in previous.items()
                  if (generation := _owned_generation(root, name, row)) is not None
                  and generation.parent == parent}
    if not candidates:
        return
    _runtime_directory(parent, root)
    if not parent.is_dir():
        return
    for candidate in sorted(candidates):
        if candidate.is_symlink() or not candidate.is_dir() or _generation_referenced(candidate, rows):
            continue
        _discard_generation(candidate, root)


def _cleanup_node_generations(root: Path, previous: dict, rows: dict) -> None:
    _cleanup_generations(root, previous, rows, "node")


def _cleanup_python_generations(root: Path, previous: dict, rows: dict) -> None:
    # Legacy venv contents have no whole-directory receipt; preserve them.
    _cleanup_generations(root, previous, rows, "python")


def _recorded_path(row: dict, key: str) -> Path | None:
    value = row.get(key)
    return Path(value) if isinstance(value, str) and Path(value).is_absolute() else None


def _owned_generation(root: Path, name: str, row: object) -> Path | None:
    if not isinstance(row, dict):
        return None
    generation = _recorded_path(row, "managed_generation")
    executable = _recorded_path(row, "executable")
    ecosystem = "openspec" if name == "openspec" else TOOL_SPECS.get(name, (None,))[0]
    if generation is None or executable is None or ecosystem is None:
        return None
    parent = root / "packages" if ecosystem == "openspec" else root / "packages" / ecosystem
    prefix = "openspec" if ecosystem == "openspec" else f"mainframe-{ecosystem}"
    if generation.parent != parent or not re.fullmatch(rf"{prefix}-[a-z0-9_]{{8}}", generation.name):
        return None
    if ".." in executable.parts or executable == generation or not executable.is_relative_to(generation):
        return None
    if ecosystem == "release" and executable != generation / name:
        return None
    if ecosystem == "openspec" and executable != generation / "node_modules" / OPENSPEC_PACKAGE / "bin/openspec.js":
        return None
    return generation


def _tool_row(root: Path, name: str, executable: Path, *, version: str | None = None,
              previous: object = None, fresh: bool = False) -> dict:
    row = {"executable": str(executable)}
    if version is not None:
        row["version"] = version
    if fresh:
        # Only freshly allocated preparation results can acquire provenance.
        for candidate in executable.parents:
            proposed = {**row, "managed_generation": str(candidate)}
            if _owned_generation(root, name, proposed) == candidate:
                return proposed
    elif isinstance(previous, dict) and _recorded_path(previous, "executable") == executable:
        generation = _owned_generation(root, name, previous)
        if generation is not None:
            row["managed_generation"] = str(generation)
    return row


def _generation_referenced(generation: Path, rows: dict) -> bool:
    active = [_recorded_path(row, key) for row in rows.values() if isinstance(row, dict)
              for key in ("executable", "node")]
    try:
        return any(path is not None and (
            path.is_relative_to(generation) or path.resolve().is_relative_to(generation)
        ) for path in active)
    except (OSError, RuntimeError):
        return True  # An unresolved recorded path cannot establish safe removal.


def _retirement_records(root: Path, manifest: dict) -> dict[Path, dict]:
    records = manifest.get("pending_retirements", [])
    if not isinstance(records, list):
        raise Conflict("Unrecognized runtime retirement records; preserve installation.json.")
    pending = {}
    for record in records:
        name = record.get("tool") if isinstance(record, dict) else None
        generation = _owned_generation(root, name, record) if isinstance(name, str) else None
        if generation is None:
            raise Conflict("Unrecognized runtime retirement record; preserve installation.json.")
        pending.setdefault(generation, record)
    return pending


def _with_retirements(root: Path, manifest: dict, rows: dict) -> dict:
    pending = _retirement_records(root, manifest)
    active = {_owned_generation(root, name, row) for name, row in rows.items()}
    for name, row in _tool_rows(manifest).items():
        generation = _owned_generation(root, name, row)
        if generation is not None and generation not in active:
            pending.setdefault(generation, {"tool": name, "executable": row["executable"],
                                            "managed_generation": str(generation)})
    record = {**manifest, "schema": 1, "tools": rows}
    if pending:
        record["pending_retirements"] = [pending[path] for path in sorted(pending)]
    else:
        record.pop("pending_retirements", None)
    return record


def _reconcile_retirements(root: Path) -> None:
    path = root / "installation.json"
    snapshot = observed(path)
    manifest = _manifest(root)
    pending = _retirement_records(root, manifest)
    if not pending:
        return
    retained = []
    for generation, record in sorted(pending.items()):
        if _generation_referenced(generation, _tool_rows(manifest)) or generation.is_symlink():
            retained.append(record)
            continue
        if observed(path) != snapshot:
            raise Conflict("Runtime installation changed during retirement; preserve installation.json.")
        _discard_generation(generation, root)
    updated = dict(manifest)
    if retained:
        updated["pending_retirements"] = retained
    else:
        updated.pop("pending_retirements", None)
    if updated != manifest:
        if observed(path) != snapshot:
            raise Conflict("Runtime installation changed during retirement; preserve installation.json.")
        atomic_write(path, encode_json(updated), snapshot[1] if snapshot[1] is not None else 0o600)


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


def _openspec_version(*command: Path) -> str | None:
    version = _version(*command, path=os.defpath, exact=True)
    if version is None or _parts(version) < _parts(OPENSPEC_VERSION):
        return None
    if version == OPENSPEC_VERSION:
        return version
    try:
        with tempfile.TemporaryDirectory(prefix="mainframe-openspec-probe-") as directory:
            workspace = Path(directory)
            (workspace / "openspec/changes").mkdir(parents=True)
            result = subprocess.run(
                [*command, "list", "--json"], cwd=workspace,
                env={**_probe_environment(), "PATH": os.defpath},
                capture_output=True, text=True, timeout=5, check=False,
            )
            report = json.loads(result.stdout) if result.returncode == 0 else None
            if isinstance(report, dict) and report.get("changes") == []:
                return version
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _openspec_status(shim: Path, row: dict) -> str | None:
    command = _openspec_command(row, shim)
    if (command is None
            or regular_bytes(shim) != _openspec_shim(command)
            or (len(command) == 2 and not _supported_openspec_node(command[0]))):
        return None
    return _openspec_version(shim)


def _openspec_node(previous: tuple[Path, ...] | None) -> Path | None:
    if previous and len(previous) == 2 and _supported_openspec_node(previous[0]):
        return previous[0]
    located = shutil.which("node")
    node = Path(located).resolve() if located else None
    return node if node and _supported_openspec_node(node) else None


def _openspec_candidate(shim: Path, previous: tuple[Path, ...] | None,
                        node: Path | None) -> tuple[tuple[Path, ...], str] | None:
    if previous and len(previous) == 2:
        previous = (node, previous[-1]) if node else None
    if previous and previous[-1].resolve() != shim:
        version = _openspec_version(*previous)
        if version:
            return previous, version
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
        version = _openspec_version(*command)
        if version:
            return command, version
    return None


def _install_openspec(target: Path, npm: str, node: Path) -> tuple[Path, ...]:
    environment = {
        **os.environ, **OPENSPEC_ENV, "NO_UPDATE_NOTIFIER": "1",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "PATH": str(node.parent) + os.pathsep + os.environ.get("PATH", os.defpath),
    }
    _npm_install([npm, "install", "--prefix", str(target), "--global=false", "--ignore-scripts",
                  "--no-audit", "--no-fund", "--save-exact", f"{OPENSPEC_PACKAGE}@{OPENSPEC_VERSION}"],
                 environment, cwd=target)
    entrypoint = target / "node_modules" / OPENSPEC_PACKAGE / "bin/openspec.js"
    if _version(node, entrypoint, path=os.defpath, exact=True) != OPENSPEC_VERSION:
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
    candidate = _openspec_candidate(shim, previous, node)
    staged = None
    try:
        if candidate is None:
            if node is None:
                minimum = ".".join(map(str, OPENSPEC_NODE_MINIMUM))
                raise Conflict(f"Node.js {minimum} or newer on PATH is required to install OpenSpec.")
            npm = shutil.which("npm")
            if npm is None:
                raise Conflict("npm is required to install OpenSpec.")
            packages = root / "packages"
            _runtime_directory(packages, root)
            packages.mkdir(mode=0o700, exist_ok=True)
            # Keep this prefix separate from the analyzers and the active OpenSpec release.
            staged = Path(tempfile.mkdtemp(prefix="openspec-", dir=packages))
            command = _install_openspec(staged, str(Path(npm).absolute()), node)
            version = OPENSPEC_VERSION
        else:
            command, version = candidate
        row = _tool_row(root, "openspec", command[-1], version=version,
                        previous=existing.get("openspec"), fresh=staged is not None)
        if len(command) == 2:
            row["node"] = str(command[0])
        record = _with_retirements(root, manifest, {**existing, "openspec": row})
        transact([
            Change.from_snapshot(shim, snapshot, _openspec_shim(command), 0o755),
            Change.from_snapshot(manifest_path, manifest_snapshot, encode_json(record)),
        ], journal, allowed, after_restore=lambda changes: _cleanup_restored_stages(root, changes))
    except BaseException:
        if staged is not None and not journal.exists():
            _discard_generation(staged, root)
        raise
    _reconcile_retirements(root)


def _candidates(root: Path, home: Path, wanted: list[str], existing: dict) -> tuple[
    dict[str, tuple[Path, str]], dict[str, list[str]]
]:
    resolved: dict[str, tuple[Path, str]] = {}
    missing: dict[str, list[str]] = {"python": [], "node": [], "release": []}
    for name in wanted:
        if name not in TOOL_SPECS:
            continue
        row = existing.get(name) if isinstance(existing, dict) else None
        recorded = row.get("executable") if isinstance(row, dict) else None
        executable = (Path(recorded).resolve()
                      if isinstance(recorded, str) and Path(recorded).is_absolute()
                      else None)
        version = _analyzer_version(name, executable) if executable else None
        if version is None:
            seen = {executable, (runtime_bin(home) / name).resolve()}
            for directory in os.get_exec_path():
                located = shutil.which(name, path=directory)
                candidate = Path(located).resolve() if located else None
                if candidate in seen or candidate is None:
                    continue
                seen.add(candidate)
                version = _analyzer_version(name, candidate)
                if version is not None:
                    executable = candidate
                    break
        if executable and version is not None:
            resolved[name] = executable, version
        else:
            missing[TOOL_SPECS[name][0]].append(name)
    for ecosystem in ("python", "node"):
        names = missing[ecosystem]
        if not names:
            continue
        for name, (executable, _) in list(resolved.items()):
            row = existing.get(name)
            if (TOOL_SPECS[name][0] == ecosystem and _owned_generation(root, name, row) is not None
                    and _recorded_path(row, "executable") == executable):
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
        cleanup = lambda changes: _cleanup_restored_stages(root, changes)
        restore(journal, openspec_paths, after_restore=cleanup)
        restore(root / ".analyzers-recovery.json", lambda path: _analyzer_path(root, path),
                after_restore=cleanup)
        _reconcile_retirements(root)
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


def _analyzer_path(root: Path, path: Path) -> bool:
    return path == root / "installation.json" or (path.parent == root / "bin" and path.name in TOOL_SPECS)


def _cleanup_stages(root: Path, staged: dict, active: dict) -> None:
    for ecosystem in ("python", "node", "release", "openspec"):
        _cleanup_generations(root, staged, active, ecosystem)


def _cleanup_restored_stages(root: Path, changes: list[Change]) -> None:
    for change in changes:
        if change.path != root / "installation.json" or change.after is None:
            continue
        try:
            record = json.loads(change.after)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(record, dict) and record.get("schema") == 1:
            _cleanup_stages(root, _tool_rows(record), _tool_rows(_manifest(root)))


def _analyzer_snapshot(name: str, shim: Path, row: object):
    snapshot = observed(shim)
    if snapshot[0] is None:
        return snapshot
    executable = _recorded_path(row, "executable") if isinstance(row, dict) else None
    expected = set()
    if executable is not None:
        try:
            expected.add(_analyzer_shim(name, executable))
        except Conflict:
            expected = set()  # Missing parser metadata cannot prove the current wrapper.
        if name == "modern-web-guidance":
            expected.add(f'#!/bin/sh\nexec {shlex.quote(str(executable))} "$@"\n'.encode())
            expected.add(f'#!/bin/sh\nexec "{executable}" "$@"\n'.encode())
    if snapshot[0] not in expected:
        raise Conflict(f"Existing analyzer launcher was edited or has no installer ownership: {shim}")
    return snapshot


def _ensure_analyzers(root: Path, home: Path, required: tuple[str, ...]) -> None:
    manifest_path = root / "installation.json"
    manifest_snapshot = observed(manifest_path)
    manifest = _manifest(root)
    existing = _tool_rows(manifest)
    wanted = sorted(set(TOOL_SPECS).intersection(set(existing).union(required)))
    snapshots = {name: _analyzer_snapshot(name, runtime_bin(home) / name, existing.get(name))
                 for name in wanted}
    candidates, missing = _candidates(root, home, wanted, existing)
    if missing["node"] and not shutil.which("npm"):
        raise Conflict("npm is required to install active MAINFRAME Node.js analyzers; no hook files were changed.")
    staged = {}
    journal = root / ".analyzers-recovery.json"
    try:
        for name in missing["release"]:
            staged[name] = _managed_release(root, name)
        if missing["python"]:
            staged.update(_managed_python(root, missing["python"]))
        if missing["node"]:
            staged.update(_managed_node(root, missing["node"]))
        for name, executable in staged.items():
            version = _analyzer_release(name, executable)
            if version != TOOL_SPECS[name][2]:
                raise Conflict(f"MAINFRAME runtime dependency {name} failed its version probe.")
            candidates[name] = executable, version
        rows = dict(existing)
        changes = []
        for name in wanted:
            if name not in candidates:
                raise Conflict(f"MAINFRAME runtime dependency {name} could not be resolved.")
            executable, version = candidates[name]
            shim = runtime_bin(home) / name
            snapshot = snapshots[name]
            data = _analyzer_shim(name, executable)
            changes.append(Change.from_snapshot(shim, snapshot, data, 0o755))
            rows[name] = _tool_row(root, name, executable, version=version,
                                   previous=existing.get(name), fresh=name in staged)
        changes.append(Change.from_snapshot(manifest_path, manifest_snapshot,
                       encode_json(_with_retirements(root, manifest, rows))))
        transact(changes, journal, lambda path: _analyzer_path(root, path),
                 after_restore=lambda restored: _cleanup_restored_stages(root, restored))
    except BaseException:
        if not journal.exists():
            abandoned = {name: _tool_row(root, name, path, fresh=True) for name, path in staged.items()}
            _cleanup_stages(root, abandoned, _tool_rows(_manifest(root)))
        raise
    _reconcile_retirements(root)

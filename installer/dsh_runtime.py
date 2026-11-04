"""Build-time standalone Python/SQLCipher provisioning, never profile activation.

Only the package producer needs uv. End users get a runtime inside the Vault
package: no venv, Homebrew, install script, or runtime network download.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from .core import Conflict

PYTHON_VERSION = '3.12.12'
SQLCIPHER_PACKAGE_VERSION = '0.6.4'


def runtime_target(system=None, machine=None):
    system = system or platform.system()
    machine = machine or platform.machine()
    arch = {'arm64': 'aarch64', 'aarch64': 'aarch64', 'x86_64': 'x86_64', 'AMD64': 'x86_64'}.get(machine)
    suffix = {'Darwin': 'apple-darwin', 'Linux': 'unknown-linux-gnu'}.get(system)
    if not arch or not suffix:
        raise Conflict(f'Unsupported Vault runtime platform: {system}/{machine}; macOS or glibc Linux arm64/x64 required.')
    if system == 'Linux' and platform.libc_ver()[0] != 'glibc' and system == platform.system():
        raise Conflict('Unsupported Vault runtime: glibc Linux required, not musl/static Python.')
    return f'{arch}-{suffix}'


def validate_build_output(path: Path, source_root: Path | None = None) -> Path:
    """Read-only preflight shared by the CLI and standalone runtime producer.

    Reject original relative paths, aliases, existing targets and overlap with
    source or DSH-owned storage before any download, directory creation or spawn.
    Returns the canonical path without silently normalizing an unsafe spelling.
    """
    output = Path(path)
    if not output.is_absolute() or '..' in output.parts:
        raise Conflict('Build output must be an absolute path without traversal.')
    if output.is_symlink() or output.resolve() != output:
        raise Conflict('Build output must not use symlink components or filesystem aliases.')
    protected = [Path.home() / '.dsh']
    protected.extend(Path(value).expanduser() for key in ('DSH_HOME', 'DSH_PROFILE_DIR')
                     if (value := os.environ.get(key, '').strip()))
    if source_root is not None:
        protected.append(Path(source_root))
    for candidate in protected:
        candidate = candidate.resolve()
        if output == candidate or output in candidate.parents or candidate in output.parents:
            raise Conflict('Build output must not overlap source, DSH home, or profile directories.')
    if output.exists():
        raise Conflict('Build output must be a new directory.')
    if not output.parent.is_dir():
        raise Conflict('Build output parent must exist.')
    return output


def provision_runtime(output: Path) -> Path:
    """Provision a NEW private build tree, not an existing user Python or profile."""
    output = validate_build_output(output, source_root=Path(__file__).resolve().parents[1])
    target = runtime_target()
    uv = shutil.which('uv')
    if not uv:
        raise Conflict('Building Vault packages requires uv (end users do not need uv).')
    output.mkdir(mode=0o700)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('UV_', 'PYTHON', 'PIP_', 'LD_', 'DYLD_'))
           and k != 'SSLKEYLOGFILE'}
    common = dict(check=True, capture_output=True, text=True, env=env, cwd=output)
    try:
        subprocess.run([uv, 'python', 'install', PYTHON_VERSION,
                        '--install-dir', str(output / 'python'), '--no-bin',
                        '--no-config', '--no-cache'], **common)
        candidates = [p for p in (output / 'python').iterdir()
                      if p.name.startswith('cpython-') and p.is_dir() and not p.is_symlink()]
        if len(candidates) != 1:
            raise Conflict('Standalone Python provisioning produced an unexpected layout.')
        runtime = candidates[0]
        python = runtime / 'bin/python3.12'
        if not python.is_file() or python.is_symlink():
            raise Conflict('Standalone Python versioned executable is missing or linked.')
        subprocess.run([uv, 'pip', 'install', '--python', str(python),
                        '--target', str(runtime / 'lib/python3.12/site-packages'),
                        '--only-binary', ':all:', '--no-config', '--no-cache',
                        f'sqlcipher3=={SQLCIPHER_PACKAGE_VERSION}'], **common)
        # A synthetic in-memory database, never a credential database or worker.
        probe = ("import json,sys,importlib.metadata; from sqlcipher3 import dbapi2 as db; "
                 "c=db.connect(':memory:'); c.execute(\"PRAGMA key='synthetic-build-probe'\"); "
                 "print(json.dumps({'python':'.'.join(map(str,sys.version_info[:3])),"
                 "'sqlcipher3':importlib.metadata.version('sqlcipher3'),"
                 "'cipher':c.execute('PRAGMA cipher_version').fetchone()[0]}))")
        result = subprocess.run([str(python), '-I', '-B', '-c', probe], **common)
        observed = json.loads(result.stdout)
        if (observed.get('python') != PYTHON_VERSION or
                observed.get('sqlcipher3') != SQLCIPHER_PACKAGE_VERSION or
                not isinstance(observed.get('cipher'), str) or not observed['cipher'].startswith('4.')):
            raise Conflict('Standalone SQLCipher verification failed.')
        receipt = {'schema': 1, 'target': target, **observed,
                   'provider': 'uv/python-build-standalone', 'binary_wheel_only': True}
        (runtime / 'mainframe-runtime.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return runtime
    except (subprocess.CalledProcessError, ValueError, OSError) as error:
        # Leave the isolated failed build for diagnosis; do not delete computed paths.
        raise Conflict('Vault runtime build failed; isolated output retained. Check uv/platform binary wheel availability.') from error

"""Build checkout-independent native DSH tarballs; never inspect or write a profile.

The caller provisions a standalone Python/SQLCipher runtime separately. No code,
worker, package script, or interpreter from that runtime is executed here.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tarfile
import tempfile

from .core import Conflict, regular_bytes
from .dsh import DSH
from .shared import DSH_PLUGINS

_PRIVATE_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.pem', '.key', '.p12', '.pfx', '.kdbx'}
_PRIVATE_NAMES = {'pyvenv.cfg', '.env', 'credentials.json', 'credentials', 'secrets.json',
                  'vault.db-wal', 'vault.db-shm', '.npmrc', '.pypirc', '.netrc'}
_VERSION = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$')
_TARGETS = {'aarch64-apple-darwin': ('darwin', 'arm64'),
            'x86_64-apple-darwin': ('darwin', 'x64'),
            'aarch64-unknown-linux-gnu': ('linux', 'arm64'),
            'x86_64-unknown-linux-gnu': ('linux', 'x64')}


def _runtime_target(files):
    receipt_file = files.get('mainframe-runtime.json')
    if receipt_file is None:
        raise Conflict('Standalone runtime requires a mainframe-runtime.json provisioning receipt.')
    try:
        receipt = json.loads(regular_bytes(receipt_file[0]))
    except (ValueError, TypeError) as error:
        raise Conflict('Invalid standalone runtime provisioning receipt.') from error
    if (not isinstance(receipt, dict) or receipt.get('schema') != 1
            or receipt.get('python') != '3.12.12' or receipt.get('sqlcipher3') != '0.6.4'
            or receipt.get('binary_wheel_only') is not True
            or receipt.get('provider') != 'uv/python-build-standalone'
            or not isinstance(receipt.get('cipher'), str) or not receipt['cipher'].strip()
            or not isinstance(receipt.get('target'), str) or receipt['target'] not in _TARGETS):
        raise Conflict('Unsupported or unverified standalone runtime provisioning receipt.')
    return _TARGETS[receipt['target']]


def _path(value, label):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise Conflict(f'{label} must be an absolute, non-traversing path.')
    for parent in (*reversed(path.parents), path):
        if parent.is_symlink():
            raise Conflict(f'{label} must not use filesystem aliases or symlinks.')
    resolved = path.resolve()
    if resolved != path:
        raise Conflict(f'{label} must use its canonical absolute spelling.')
    return path


def _overlap(first, second):
    return first == second or first in second.parents or second in first.parents


def _private(path):
    name = path.name.lower()
    return name in _PRIVATE_NAMES or name.startswith('.env.') or path.suffix.lower() in _PRIVATE_SUFFIXES


def _runtime_files(runtime):
    """Resolve only internal links; emit regular file sources, retaining executable bits."""
    files = {}

    def visit(logical, candidate, ancestors):
        parts = logical.parts
        # Packaging tools are not runtime dependencies; omit their CA/test keys
        # rather than weakening the private-file boundary for arbitrary PEMs.
        if (len(parts) >= 3 and parts[:2] == ('lib', 'python3.12')
                and parts[2] in {'test', 'ensurepip', 'idlelib', 'tkinter', 'turtledemo'}):
            return
        if (len(parts) >= 4 and parts[:3] == ('lib', 'python3.12', 'site-packages')
                and (parts[3] in {'pip', 'setuptools', '_distutils_hack', 'wheel'}
                     or parts[3].startswith(('pip-', 'setuptools-', 'wheel-')))):
            return
        if len(parts) == 2 and parts[0] == 'bin' and parts[1].startswith(('pip', 'idle', '2to3')):
            return
        if _private(logical):
            raise Conflict('Standalone runtime contains private material or virtualenv configuration.')
        if logical.name == '__pycache__' or logical.suffix in {'.pyc', '.pyo'}:
            return
        try:
            physical = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise Conflict('Standalone runtime contains a broken or cyclic link.') from error
        if physical != runtime and runtime not in physical.parents:
            raise Conflict('Standalone runtime contains an external link.')
        mode = physical.stat().st_mode
        if stat.S_ISDIR(mode):
            if physical in ancestors:
                raise Conflict('Standalone runtime contains a directory link cycle.')
            for child in sorted(physical.iterdir()):
                visit(logical / child.name, child, ancestors | {physical})
        elif stat.S_ISREG(mode):
            files[logical.as_posix()] = (physical, 0o755 if mode & 0o111 else 0o644)
        else:
            raise Conflict('Standalone runtime may contain only regular files and internal links.')

    visit(Path('.'), runtime, set())
    python = files.get('bin/python3.12')
    if python is None or python[1] != 0o755:
        raise Conflict('Standalone runtime requires an executable bin/python3.12 matching the worker default.')
    if not any(Path(name).name.upper().startswith(('LICENSE', 'COPYING')) for name in files):
        raise Conflict('Standalone runtime must include its upstream licenses.')
    return files


def _archive(path, payload):
    """Write reproducible npm-compatible package/ entries; no links or special files."""
    with path.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as packed:
                for name, (source, mode) in sorted(payload.items()):
                    if name.startswith('/') or '..' in Path(name).parts or '\\' in name:
                        raise Conflict('Unsafe archive member name.')
                    info = tarfile.TarInfo('package/' + name)
                    info.mode = mode
                    info.mtime = info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    if isinstance(source, bytes):
                        import io
                        info.size = len(source)
                        packed.addfile(info, io.BytesIO(source))
                    else:
                        with source.open('rb') as stream:
                            info.size = os.fstat(stream.fileno()).st_size
                            packed.addfile(info, stream)


def build_packages(root, output, runtime_directory):
    """Return archive paths/hashes and native handoffs, without lifecycle changes.

    All inputs use canonical absolute paths. Output must be absent or empty,
    outside the source and runtime, with an existing parent. Artifacts remain at
    output: retain them for native package repair/reinstall after checkout deletion.
    The runtime is a provisioned standalone distribution, not a copied virtualenv.
    This validates packaging only, not ABI suitability or SQLCipher functionality.
    """
    root = _path(root, 'Source root')
    output = _path(output, 'Output')
    runtime = _path(runtime_directory, 'Standalone runtime')
    protected = [Path.home() / '.dsh']
    protected.extend(Path(value) for key in ('DSH_HOME', 'DSH_PROFILE_DIR')
                     if (value := os.environ.get(key, '').strip()))
    if any(_overlap(output, path.expanduser().resolve()) for path in protected):
        raise Conflict('Package output must not overlap DSH home or profile directories.')
    if not root.is_dir() or not runtime.is_dir():
        raise Conflict('Source root and standalone runtime must be existing directories.')
    if _overlap(root, output) or _overlap(runtime, output) or _overlap(root, runtime):
        raise Conflict('Source, runtime, and output must be separate directory trees.')
    if not output.parent.is_dir():
        raise Conflict('Output parent must already exist.')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise Conflict('Output must be absent or empty.')
    runtime_files = _runtime_files(runtime)
    runtime_os, runtime_cpu = _runtime_target(runtime_files)
    adapter = DSH(root, root / 'unused-profile-selection')
    bundles = {}
    payloads = {}
    for name, source in DSH_PLUGINS.items():
        checked = adapter._bundle(name, source)
        directory = root / source
        manifest = json.loads(regular_bytes(directory / 'package.json'))
        if not _VERSION.fullmatch(manifest['version']):
            raise Conflict('Package version must be a safe semantic version.')
        if manifest.get('scripts'):
            raise Conflict('Runtime packages must not execute installation scripts.')
        payload = {}
        for pattern in manifest['files']:
            for file in directory.glob(pattern):
                if not file.is_file() or file.is_symlink():
                    raise Conflict('Runtime manifest must select regular source files only.')
                relative = file.relative_to(directory).as_posix()
                payload[relative] = (file, 0o755 if file.stat().st_mode & 0o111 else 0o644)
        if name == 'secrets-vault':
            payload.update({'runtime/' + key: value for key, value in runtime_files.items()})
            manifest['files'] = [*manifest['files'], 'runtime']
            manifest['os'], manifest['cpu'] = [runtime_os], [runtime_cpu]
        payload['package.json'] = ((json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode(), 0o644)
        payloads[name] = payload
        platform = f'-{runtime_os}-{runtime_cpu}' if name == 'secrets-vault' else ''
        filename = f'mainframe-{name}-{checked["version"]}{platform}.tgz'
        archive = output / filename
        bundles[name] = {'package': checked['package'], 'version': checked['version'],
                         'archive': str(archive),
                         'handoff': {'tool': 'plugin_manager',
                                     'actions': ['list_bundles', 'install_bundle'],
                                     'target': str(archive)}}
    # Validate every input before publishing anything. Temporary staging is never
    # in the checkout, and an exception cleans only our own newly allocated tree.
    with tempfile.TemporaryDirectory(prefix='.mainframe-pack-', dir=output.parent) as temporary:
        stage = Path(temporary)
        for name, payload in payloads.items():
            staged = stage / Path(bundles[name]['archive']).name
            _archive(staged, payload)
            with staged.open('rb') as stream:
                bundles[name]['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        output.mkdir(exist_ok=True)
        for item in bundles.values():
            destination = Path(item['archive'])
            # Exclusive creation also guards a concurrently populated output.
            with (stage / destination.name).open('rb') as source, destination.open('xb') as target:
                shutil.copyfileobj(source, target)
    return {'product': 'dsh', 'mode': 'native-tarball-handoff', 'bundles': bundles,
            'profile_verified': False, 'composition_verified': False,
            'runtime_verified': False,
            'limitations': ['Packaging does not establish native installation, activation, ABI compatibility, or SQLCipher behavior.',
                            'Retain archives outside the checkout for native repair and subsequent reinstall.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--runtime-directory', required=True)
    args = parser.parse_args(argv)
    try:
        report = build_packages(args.root, args.output, args.runtime_directory)
    except (Conflict, OSError) as error:
        parser.exit(1, f'DSH package build failed: {error}\n')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

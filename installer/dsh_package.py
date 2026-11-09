"""Build checkout-independent native DSH tarballs; never inspect or write a profile.

Packages use the Host Node runtime. No runtime provisioning, package scripts,
profile reads, credential access, or plugin execution occurs here.
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
import tarfile
import tempfile

from .core import Conflict, regular_bytes
from .dsh import DSH
from .shared import DSH_PLUGINS

_VERSION = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$')


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


def build_packages(root, output):
    """Return archive paths/hashes and native handoffs, without lifecycle changes.

    All inputs use canonical absolute paths. Output must be absent or empty,
    outside the source, with an existing parent. Artifacts remain at
    output: retain them for native package repair/reinstall after checkout deletion.
    This validates packaging only, not native activation or encrypted persistence.
    """
    root = _path(root, 'Source root')
    output = _path(output, 'Output')
    protected = [Path.home() / '.dsh']
    protected.extend(Path(value) for key in ('DSH_HOME', 'DSH_PROFILE_DIR')
                     if (value := os.environ.get(key, '').strip()))
    if any(_overlap(output, path.expanduser().resolve()) for path in protected):
        raise Conflict('Package output must not overlap DSH home or profile directories.')
    if not root.is_dir():
        raise Conflict('Source root must be an existing directory.')
    if _overlap(root, output):
        raise Conflict('Source and output must be separate directory trees.')
    if not output.parent.is_dir():
        raise Conflict('Output parent must already exist.')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise Conflict('Output must be absent or empty.')
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
        payload['package.json'] = ((json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode(), 0o644)
        payloads[name] = payload
        filename = f'mainframe-{name}-{checked["version"]}.tgz'
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
            'limitations': ['Packaging does not establish native installation, activation, or encrypted persistence.',
                            'Retain archives outside the checkout for native repair and subsequent reinstall.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        report = build_packages(args.root, args.output)
    except (Conflict, OSError) as error:
        parser.exit(1, f'DSH package build failed: {error}\n')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

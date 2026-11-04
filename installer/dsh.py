"""DSH source adapter: validate bundles and hand off native lifecycle ownership.

No profile discovery, credential access, profile writes, or activation is performed.
Source verification is deliberately not adaptation delivery/verification evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

from .core import Conflict, digest, regular_bytes
from .shared import DSH_PLUGINS, inventory
from .state import component_keys, reconcile_state

# Explicit source boundary: linked-directory installs do not apply npm's files filter.
SOURCE_FILES = {
    'activity-analytics': {
        'README.md', 'build-client.mjs', 'client.js', 'client.template.js',
        'client.test.mjs', 'cordis.patch.yml', 'delivery.test.mjs', 'host.test.mjs',
        'icon.svg', 'index.js', 'outbox.js', 'outbox.test.mjs', 'package.json',
        'store.js', 'store.test.mjs', 'time.js', 'time.test.mjs',
        'locale/en.json', 'locale/ru.json',
    },
    'message-time': {
        'cordis.patch.yml', 'icon.svg', 'index.js', 'package.json', 'test.mjs',
        'locale/en.json', 'locale/ru.json',
    },
    'secrets-vault': {
        'README.md', 'backend.test.mjs', 'client.js', 'clipboard.js',
        'clipboard.test.mjs', 'cordis.patch.yml', 'host.test.mjs', 'icon.svg',
        'index.js', 'operations.js', 'operations.test.mjs', 'package.json',
        'recovery-host.test.mjs', 'recovery-store.js', 'recovery-ui.test.mjs',
        'recovery.test.mjs', 'ssh-askpass', 'ssh-askpass.cjs', 'ui-contract.test.mjs',
        'vault-store.js', 'vault.py', 'locale/en.json', 'locale/ru.json',
    },
}


class DSH:
    def __init__(self, root: Path, home: Path, *, surface: str | None = None):
        self.root = Path(root).resolve()
        self.home = Path(home)  # Selection metadata only; never read or written.
        self.surface = surface

    def _bundle(self, name: str, source: str) -> dict:
        directory = self.root / source
        expected = SOURCE_FILES[name]
        present = set()
        # Inspect metadata first: do not open unknown/private files or symlinks.
        for path in directory.rglob('*'):
            relative = path.relative_to(directory).as_posix()
            if path.is_symlink():
                raise Conflict(f'Unexpected DSH source symlink: {path}')
            if path.is_dir():
                if relative != 'locale':
                    raise Conflict(f'Unexpected DSH source directory: {path}')
            elif relative not in expected or not path.is_file():
                raise Conflict(f'Unexpected DSH source: {path}')
            else:
                present.add(relative)
        if missing := expected - present:
            raise Conflict(f'Missing DSH payload in {name}: {", ".join(sorted(missing))}')
        try:
            manifest = json.loads(regular_bytes(directory / 'package.json'))
        except (ValueError, TypeError) as error:
            raise Conflict(f'Invalid DSH package manifest: {name}') from error
        if (not isinstance(manifest, dict) or manifest.get('name') != f'@mainframe/{name}'
                or not isinstance(manifest.get('version'), str)):
            raise Conflict(f'Invalid DSH package identity: {name}')
        dsh = manifest.get('dsh')
        bundle = dsh.get('bundle') if isinstance(dsh, dict) else None
        if not isinstance(bundle, dict) or bundle.get('patch') != './cordis.patch.yml':
            raise Conflict(f'Invalid DSH bundle patch declaration: {name}')
        patterns = manifest.get('files')
        if not isinstance(patterns, list) or not patterns:
            raise Conflict(f'Missing DSH package files declaration: {name}')
        covered = set()
        for pattern in patterns:
            if not isinstance(pattern, str) or Path(pattern).is_absolute() or '..' in Path(pattern).parts:
                raise Conflict(f'Unsafe DSH payload declaration: {name}')
            matches = list(directory.glob(pattern))
            if not matches or any(p.relative_to(directory).as_posix() not in expected for p in matches):
                raise Conflict(f'Missing DSH payload declaration: {name}: {pattern}')
            covered.update(p.relative_to(directory).as_posix() for p in matches)
        development = {'package.json', 'build-client.mjs', 'client.template.js', 'time.js', 'outbox.js'}
        runtime = {item for item in expected if item not in development and not item.endswith('.test.mjs') and item != 'test.mjs'}
        if missing := runtime - covered:
            raise Conflict(f'Incomplete DSH runtime payload in {name}: {", ".join(sorted(missing))}')
        if name == 'secrets-vault' and not (directory / 'ssh-askpass').stat().st_mode & 0o111:
            raise Conflict('DSH vault ssh-askpass must remain executable.')
        requirements = ['Supply the selected DSH profile directory through native plugin configuration.'] if name != 'message-time' else []
        if name == 'activity-analytics':
            requirements.append('The DSH Host runtime must expose usable node:sqlite.')
        if name == 'secrets-vault':
            requirements.append('Configure an external Python with sqlcipher3/SQLCipher; no Python environment or vault data is included.')
        return {
            'source': source, 'package': manifest['name'], 'version': manifest['version'],
            'install_target': str(directory),
            'source_files': {item: digest(regular_bytes(directory / item)) for item in sorted(expected)},
            'requirements': requirements,
            'handoff': {'tool': 'plugin_manager', 'actions': ['list_bundles', 'install_bundle'],
                        'target': str(directory)},
        }

    def plan(self):
        source = inventory(self.root, 'dsh')
        bundles = {name: self._bundle(name, path) for name, path in DSH_PLUGINS.items()}
        pending = {
            component: ('Use plugin_manager after checking the selected profile and required configuration; '
                        'then verify native activation separately.' if component[0] == 'plugins' else
                        'No DSH mapping implemented by this source-plugin adapter; assign native adaptation separately.')
            for component in component_keys(source)
        }
        state = reconcile_state(source, {}, {'product': 'dsh', 'surface': self.surface},
                                unchanged=False, pending=pending)
        return [], {
            'product': 'dsh', 'mode': 'source-plugin-handoff',
            'verification_scope': 'repository-source-only',
            'source_verified': True, 'profile_verified': False,
            'source_checks': ['exact file boundary', 'package identity and manifest shape',
                              'declared runtime payload coverage', 'source hashes'],
            'composition_verified': False,
            'changes': [], 'bundles': bundles, 'state': state,
            'limitations': [
                'No profile inspected or changed; existing linked installations remain untouched.',
                'Patch syntax/semantics and target-local configuration require native review before activation.',
                'apply/enable/disable/uninstall/recover belong to the native plugin_manager, not this adapter.',
                'Package presence is not native discovery, activation, rendered UI, or credential-runtime verification.',
            ],
        }

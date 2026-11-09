"""Create a private config-only DSH bundle; never install it or inspect a profile.

Run from the repository root with ``python3 -B -m installer.dsh_local_bundle``.
Arguments are nonsecret absolute paths. The output parent must already exist.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


class LocalBundleError(ValueError):
    """A generation failure whose message does not disclose supplied paths."""


def _absolute(value, label):
    path = Path(value)
    if not path.is_absolute():
        raise LocalBundleError(f'{label} must be an absolute path.')
    # Check before resolving: resolution must not conceal a symlink argument.
    # Include components before ".." so an alias cannot be hidden by traversal.
    for index in range(1, len(path.parts) + 1):
        if Path(*path.parts[:index]).is_symlink():
            raise LocalBundleError(f'{label} must not use symlinks.')
    return path.resolve()


def _contains(parent, child):
    return parent == child or parent in child.parents


def _validate_output(output, boundaries):
    _absolute(output, 'Output')
    for boundary in boundaries:
        if _contains(boundary, output) or _contains(output, boundary):
            raise LocalBundleError('Output must be separate from the repository, profile and DSH home.')
    if not output.parent.is_dir():
        raise LocalBundleError('Output parent must be an existing directory.')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise LocalBundleError('Output must be absent or an empty directory.')


def _json(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def _payload(profile):
    manifest = {
        'name': '@mainframe/local-deployment', 'version': '1.0.0', 'private': True,
        'description': 'Private configuration for MAINFRAME Activity Analytics and Secrets Vault.',
        'type': 'module',
        'exports': {'./locale/*.json': './locale/*.json', './icon': './icon.svg'},
        'files': ['cordis.patch.yml', 'locale/*.json', 'icon.svg'],
        'dsh': {'bundle': {'patch': './cordis.patch.yml'}},
    }
    rows = [
        {'id': 'activity-analytics', 'name': '@mainframe/activity-analytics',
         'config': {'profileDirectory': str(profile)}},
        {'id': 'secrets-vault', 'name': '@mainframe/secrets-vault',
         'config': {'profileDirectory': str(profile)}},
    ]
    # JSON is a YAML subset; encoding paths this way prevents YAML interpolation
    # or accidental interpretation of punctuation in a local directory name.
    return {
        'package.json': _json(manifest),
        'cordis.patch.yml': _json([{'insert': rows}]),
        'locale/en.json': _json({'meta': {
            'title': 'MAINFRAME Local Deployment',
            'description': 'Activates Activity Analytics and Secrets Vault with private local paths.',
        }}),
        'locale/ru.json': _json({'meta': {
            'title': 'Локальная установка MAINFRAME',
            'description': 'Включает аналитику активности и хранилище секретов с локальными путями.',
        }}),
        # Original artwork: a deployment frame, activity trace and vault keyhole.
        'icon.svg': '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">\n'
                    '  <rect x="6" y="6" width="52" height="52" rx="12" fill="#173d58"/>\n'
                    '  <path d="M12 33h9l5-12 8 24 5-12h13" fill="none" stroke="#58d6c5" '
                    'stroke-width="4" stroke-linejoin="round"/>\n'
                    '  <circle cx="46" cy="20" r="5" fill="#fff0b5"/>\n'
                    '  <path d="M44 23h4v6h-4z" fill="#fff0b5"/>\n'
                    '</svg>\n',
    }


def generate_bundle(*, output, profile_directory):
    """Publish one bundle, returning its path; never read a profile.

    No profile files are opened. Path metadata is used only for boundaries and
    symlink rejection. Missing profile paths are permitted: configuration generation
    and native activation are separate operations. Existing nonempty outputs are
    never updated; choose a new private output for configuration changes.
    """
    stage = None
    stage_identity = None
    try:
        output = _absolute(output, 'Output')
        profile = _absolute(profile_directory, 'Profile directory')
        dsh_home = Path(os.environ.get('DSH_HOME') or Path.home() / '.dsh').expanduser().resolve()
        boundaries = (REPOSITORY_ROOT.resolve(), profile, dsh_home)
        _validate_output(output, boundaries)
        parent = output.parent
        stage = Path(tempfile.mkdtemp(prefix='.mainframe-deployment-', dir=parent))
        stage_identity = stage.stat()
        os.chmod(stage, 0o700)
        (stage / 'locale').mkdir(mode=0o700)
        os.chmod(stage / 'locale', 0o700)
        for relative, text in _payload(profile).items():
            # Exclusive creation and explicit chmod do not depend on umask.
            with (stage / relative).open('x', encoding='utf-8') as stream:
                os.chmod(stage / relative, 0o600)
                stream.write(text)
        # Recheck conflicts after staging. replace publishes the complete tree in
        # one same-filesystem rename (also replacing an existing empty directory).
        _validate_output(output, boundaries)
        os.replace(stage, output)
        stage = None
        return output
    except LocalBundleError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise LocalBundleError('Could not create the private deployment bundle.') from None
    finally:
        if stage is not None and stage_identity is not None:
            # Delete only the exact staging directory we created, never an
            # output path or a substituted symlink/directory. rmtree itself does
            # not follow symlinks inside the tree on supported platforms.
            try:
                current = stage.lstat()
                if (stat.S_ISDIR(current.st_mode)
                        and (current.st_dev, current.st_ino) == (stage_identity.st_dev, stage_identity.st_ino)
                        and stage.parent == parent and stage.resolve().parent == parent):
                    shutil.rmtree(stage)
            except OSError:
                pass  # Leave owner-only staging rather than touch an unknown tree.


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unknown arguments, which may contain paths.
        self.print_usage(sys.stderr)
        self.exit(2, 'Invalid arguments; supply all three absolute path options.\n')


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument('--output', required=True, help='New private bundle directory; parent must exist.')
    parser.add_argument('--profile-directory', required=True, help='Selected DSH profile directory (absolute).')
    args = parser.parse_args(argv)
    try:
        generate_bundle(output=args.output, profile_directory=args.profile_directory)
    except LocalBundleError as error:
        print(str(error), file=sys.stderr)
        return 1
    print('Created private config-only deployment bundle; native installation is still required.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

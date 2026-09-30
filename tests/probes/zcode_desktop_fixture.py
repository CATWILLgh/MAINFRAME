#!/usr/bin/env python3
"""Prepare harmless native-hook acceptance commands; never runs those commands."""
import json
from pathlib import Path
import shlex
import subprocess
import tempfile


def prepare():
    root = Path(tempfile.mkdtemp(prefix='mainframe-zcode-acceptance-')).resolve()
    root.chmod(0o700)
    for name in ('rm', 'mainframe-secret', 'rg'):
        shim = root / name
        shim.write_text('#!/bin/sh\nprintf "MAINFRAME_FIXTURE_EXECUTED_' + name + '\\n"\n')
        shim.chmod(0o700)
    repo = root / 'repo'
    repo.mkdir()
    def git(*args):
        subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, timeout=10)
    git('-c', 'init.templateDir=', 'init', '-q')
    git('config', 'commit.gpgSign', 'false')
    git('config', 'core.hooksPath', '/dev/null')
    git('config', 'user.name', 'MAINFRAME fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    # Deliberately synthetic and never sent to a credential service.
    (repo / 'fixture.txt').write_text('token=' + 'ghp_' + ('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' * 2)[:36] + '\n')
    quality = repo / 'quality.go'
    quality.write_text('package fixture\n')
    git('add', 'fixture.txt')
    quote = lambda path: shlex.quote(str(path))
    return {
        'fixture_root': str(root),
        'quality_file': str(quality),
        'commands': {
            'secret_deny': quote(root / 'mainframe-secret') + ' get MAINFRAME_SYNTHETIC',
            'destructive_deny': quote(root / 'rm') + ' -rf ' + quote(Path.cwd().resolve()),
            'rg_advice': quote(root / 'rg') + ' -r replacement pattern .',
            'commit_deny': 'git -C ' + quote(repo) + ' commit -qm mainframe-fixture',
            'clean_allow': quote(root / 'rm') + ' --help',
        },
        'safety': 'rm, mainframe-secret and rg commands address absolute inert shims. The commit can affect only this new disposable repository, even if a guard fails.',
    }


if __name__ == '__main__':
    print(json.dumps(prepare(), indent=2))

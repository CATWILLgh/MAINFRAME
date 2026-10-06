"""Opt-in Codex read reminder prototype; not part of the installable inventory."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import sys
import time

LIMIT = 262144
TTL = 7 * 86400
SKILLS = frozenset('mainframe-testing mainframe-python-backend mainframe-go-backend mainframe-typescript-backend mainframe-frontend'.split())
IGNORED = frozenset('.git .agents .codex node_modules vendor dist build generated __pycache__ .venv'.split())


def read_paths(command):
    if not isinstance(command, str) or len(command) > 8192 or any(c in command for c in '\n\r;|&<>$`*?{}()'):
        return []
    try:
        words = shlex.split(command)
    except ValueError:
        return []
    if not words:
        return []
    tool, *args = words
    if tool not in ('cat', 'head', 'tail', 'sed', '/bin/cat', '/usr/bin/head', '/usr/bin/tail', '/usr/bin/sed'):
        return []
    tool = Path(tool).name
    if tool == 'sed':
        if len(args) < 3 or args[0] != '-n' or not re.fullmatch(r'\d+(?:,\d+)?p', args[1]):
            return []
        args = args[2:]
    elif tool in ('head', 'tail') and args and args[0] == '-n':
        if len(args) < 3 or not re.fullmatch(r'[1-9]\d{0,4}', args[1]):
            return []
        args = args[2:]
    if args and args[0] == '--':
        args = args[1:]
    return args if 0 < len(args) <= 8 and all(p.startswith('/') for p in args) else []


def selection(path):
    """Path evidence only: no source reads, scans, shell or network."""
    parts = set(path.parts)
    if parts & IGNORED:
        return None
    if ('tests' in parts or '__tests__' in parts or path.name.startswith('test_')
            or path.name.endswith(('_test.go', '.test.ts', '.test.tsx', '.spec.ts', '.spec.tsx'))
            or path.name == '.gitlab-ci.yml' or path.parts[:2] == ('.github', 'workflows')):
        return 'mainframe-testing'
    backend = bool(parts & {'server', 'backend', 'handlers', 'controllers'})
    if backend:
        return {'.py': 'mainframe-python-backend', '.go': 'mainframe-go-backend',
                '.ts': 'mainframe-typescript-backend'}.get(path.suffix)
    # TSX alone does not identify React; require an established component path.
    if path.suffix == '.tsx' and parts & {'components', 'pages'}:
        return 'mainframe-frontend'
    return None


def succeeded(response):
    if isinstance(response, dict):
        return response.get('isError') is not True and type(response.get('exit_code')) is int and response['exit_code'] == 0
    # Codex model-facing exec envelope. Inspect metadata before Output only.
    if isinstance(response, str):
        header = response.split('Output:', 1)[0][:512]
        return bool(re.search(r'^Process exited with code 0\s*$', header, re.M))
    return False


def claim(state, scope, skill, seen=False):
    if state.is_symlink():
        return False
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    if state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        return False
    db = state / 'reminders.sqlite3'
    if db.is_symlink():
        return False
    fd = os.open(db, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    if db.stat().st_uid != os.getuid() or db.stat().st_mode & 0o077:
        return False
    with closing(sqlite3.connect(db, timeout=0.1)) as con, con:
        con.execute('CREATE TABLE IF NOT EXISTS reminders (scope TEXT, skill TEXT, sent INTEGER, expires REAL, PRIMARY KEY(scope,skill))')
        con.execute('BEGIN IMMEDIATE')
        now = time.time()
        con.execute('DELETE FROM reminders WHERE expires <= ?', (now,))
        if con.execute('SELECT 1 FROM reminders WHERE scope=? AND skill=?', (scope, skill)).fetchone():
            return False
        if con.execute('SELECT count(*) FROM reminders').fetchone()[0] >= 4096:
            return False
        if not seen and con.execute('SELECT coalesce(sum(sent),0) FROM reminders WHERE scope=?', (scope,)).fetchone()[0] >= 2:
            return False
        con.execute('INSERT INTO reminders VALUES (?,?,?,?)', (scope, skill, int(not seen), now + TTL))
        return not seen


def respond(data, config, state):
    try:
        return _respond(data, config, state)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, sqlite3.Error):
        return None


def _respond(data, config, state):
    if not isinstance(config, dict) or config.get('disabled') is True or not isinstance(data, dict):
        return None
    if data.get('hook_event_name') != 'PostToolUse' or data.get('tool_name') != 'Bash':
        return None
    if not succeeded(data.get('tool_response')):
        return None
    session, operation = data.get('session_id'), data.get('tool_use_id')
    if not all(isinstance(v, str) and 0 < len(v) <= 512 for v in (session, operation)):
        return None
    inputs = data.get('tool_input')
    paths = read_paths(inputs.get('command')) if isinstance(inputs, dict) else []
    if not paths:
        return None
    if 'profiles' in config:
        profiles = config['profiles']
        cwd = data.get('cwd')
        if not isinstance(profiles, list) or len(profiles) > 16 or not isinstance(cwd, str) or not Path(cwd).is_absolute():
            return None
        cwd = Path(cwd).resolve(strict=True)
        matches = [p for p in profiles if isinstance(p, dict) and isinstance(p.get('workspace'), str)
                   and Path(p['workspace']).is_absolute()
                   and cwd.is_relative_to(Path(p['workspace']).resolve(strict=True))]
        if not matches:
            return None
        config = max(matches, key=lambda p: len(Path(p['workspace']).resolve().parts))
        if config.get('disabled') is True:
            return None
    root = Path(config['workspace']).resolve(strict=True)
    skills = config.get('skills', {})
    if not root.is_dir() or not isinstance(skills, dict) or len(skills) > 16:
        return None
    available = {name: Path(value).resolve(strict=True) for name, value in skills.items()
                 if name in SKILLS and isinstance(value, str) and Path(value).is_absolute() and Path(value).is_file()}
    scope = hashlib.sha256((session + '\0' + str(root)).encode()).hexdigest()
    candidates = set()
    for raw in paths:
        path = Path(raw).resolve(strict=True)
        if not path.is_file():
            continue
        for name, skillpath in available.items():
            if path == skillpath:
                claim(state, scope, name, seen=True)
        if not path.is_relative_to(root):
            continue
        candidate = selection(path.relative_to(root))
        if candidate == 'mainframe-frontend' and config.get('react') is not True:
            continue
        if candidate in available:
            candidates.add(candidate)
    # Mixed domains are ambiguous; do not arbitrarily select one.
    if len(candidates) != 1:
        return None
    skill = candidates.pop()
    if not claim(state, scope, skill):
        return None
    message = (f'MAINFRAME: this read may relate to `{skill}`. If it matches the current task, '
               'use the available skill before the next substantive step; skip if already applied or irrelevant.')
    return {'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': message}}


def main():
    # Missing/deleted/disabled configuration is silent, including late callbacks.
    try:
        if len(sys.argv) != 3:
            return
        with Path(sys.argv[1]).open('rb') as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            return
        config = json.loads(raw)
        if config.get('disabled') is True:
            return
        payload = sys.stdin.buffer.read(LIMIT + 1)
        if len(payload) > LIMIT:
            return
        result = respond(json.loads(payload), config, Path(sys.argv[2]))
        if result:
            print(json.dumps(result))
    except Exception:
        return


if __name__ == '__main__':
    main()

"""Bounded Codex skill context and advisory state; no tool execution or source storage."""
from contextlib import closing
from datetime import datetime
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import tomllib

MAX_BYTES = 262144
TTL = 7 * 86400
NAMES = {'mainframe-python-backend', 'mainframe-go-backend', 'mainframe-typescript-backend',
         'mainframe-frontend', 'mainframe-testing', 'mainframe-infrastructure',
         'mainframe-secrets', 'mainframe-curl-requests', 'mainframe-clickhouse', 'mainframe-k3s',
         'mainframe-research', 'mainframe-test-audit', 'mainframe-consequential-review',
         'mainframe-peer-work'}
ROLE_SKILLS = {
    'mainframe-researcher': 'mainframe-research',
    'mainframe-test-auditor': 'mainframe-test-audit',
    'mainframe-consequential-reviewer': 'mainframe-consequential-review',
    'mainframe-go-backend-engineer': 'mainframe-go-backend',
    'mainframe-python-backend-engineer': 'mainframe-python-backend',
    'mainframe-typescript-backend-engineer': 'mainframe-typescript-backend',
    'mainframe-react-frontend-engineer': 'mainframe-frontend',
}
ROLE_MATCHER = '^(?:' + '|'.join(ROLE_SKILLS) + ')$'


def small_text(path, limit=65536):
    if not path.is_file() or path.is_symlink():
        return ''
    with path.open('rb') as f:
        data = f.read(limit + 1)
    return data.decode('utf-8') if len(data) <= limit else ''


def literal_calls(source):
    """Read scalar literal exec argument objects, never evaluate JavaScript."""
    results = []
    quoted = [m.span() for m in re.finditer(r'"(?:[^"\\]|\\.)*"|\x27(?:[^\x27\\]|\\.)*\x27|`[^`]*`|//[^\n]*|/\*.*?\*/', source, re.S)]
    starts = [m for m in re.finditer(r'\btools\.(?:exec_command|shell_command)\s*\(\s*', source)
              if not any(start <= m.start() < end for start, end in quoted)]
    if len(starts) > 32 or any(source[m.end():m.end()+1] != '{' for m in starts):
        return []
    for match in starts:
        pos = match.end() + 1; values = {}; valid = True
        for _ in range(16):
            key = re.match(r'\s*(?:"([a-z_]+)"|([a-z_]+))\s*:\s*', source[pos:])
            if not key:
                valid = False; break
            pos += key.end()
            value = re.match(r'("(?:[^"\\]|\\.)*"|\x27(?:[^\x27\\]|\\.)*\x27|true|false|\d+)\s*([,}])', source[pos:])
            if not value:
                valid = False; break
            raw = value[1]
            try:
                parsed = json.loads(raw) if not raw.startswith("'") else ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                valid = False; break
            k = key[1] or key[2]
            if k in values:
                valid = False; break
            values[k] = parsed; pos += value.end()
            if value[2] == '}':
                if re.match(r'\s*\)', source[pos:]):
                    results.append(values)
                break
        if not valid:
            return []
    return results


def workdir_hint(data, home):
    """Unique recent literal command/workdir hint, not exact nested-call attribution.

    Code-mode assigns random nested IDs and does not persist exec-begin events.
    Therefore missing/dynamic/conflicting contexts stay unknown. Default cwd is
    not substituted for an omitted workdir.
    """
    raw = data.get('transcript_path'); command = data.get('tool_input', {}).get('command')
    if not isinstance(raw, str) or not isinstance(command, str):
        return None
    path = Path(raw)
    if path.is_symlink() or not path.resolve().is_relative_to((home / 'sessions').resolve()):
        return None
    with path.open('rb') as f:
        f.seek(0, 2); size = f.tell(); offset = max(0, size - MAX_BYTES); f.seek(offset)
        lines = f.read(MAX_BYTES).splitlines()
    if offset:
        lines = lines[1:]
    hints = []
    for line in lines[-128:]:
        try:
            row = json.loads(line)
            stamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')).timestamp()
        except (ValueError, KeyError, TypeError):
            continue
        if not 0 <= time.time() - stamp < 120:
            continue
        body = row.get('payload', {})
        if row.get('type') != 'response_item' or body.get('type') not in ('function_call', 'custom_tool_call'):
            continue
        args = body.get('arguments', body.get('input'))
        if not isinstance(args, str):
            continue
        if body.get('name') in ('exec', 'functions.exec'):
            calls = literal_calls(args)
            if not calls and re.search(r'\btools\.(?:exec_command|shell_command)\s*\(', args):
                hints.append(None)
        elif body.get('call_id') == data.get('tool_use_id'):
            try: calls = [json.loads(args)]
            except ValueError: calls = []
        else:
            continue
        for call in calls:
            if not isinstance(call, dict) or call.get('cmd', call.get('command')) != command:
                continue
            workdir = call.get('workdir')
            hints.append(workdir if isinstance(workdir, str) and Path(workdir).is_absolute()
                         and not any(k in call for k in ('environment', 'environment_id', 'host')) else None)
    return hints[0] if hints and hints[0] and all(x == hints[0] for x in hints) else None


def project_root(cwd):
    path = Path(cwd).resolve(strict=True)
    if not path.is_dir():
        return None
    for parent in (path, *list(path.parents)[:8]):
        if (parent / '.git').exists():
            return parent
    return path


def catalog(home, project, cwd=None):
    """Readable local methods, respecting explicit native disable/user-only policy.

    Does not claim the native model's budgeted catalog exposed every entry.
    Suggestions contain a verified path so the method can be read directly.
    """
    layers = [home / 'config.toml', project / '.codex/config.toml']
    if cwd:
        directory = Path(cwd).resolve()
        for parent in (directory, *list(directory.parents)[:8]):
            if parent.is_relative_to(project):
                layers.append(parent / '.codex/config.toml')
    disabled = set()
    for layer in dict.fromkeys(layers):
        if layer.is_symlink():
            return {}, None
        text = small_text(layer)
        if layer.exists() and not text.strip():
            if layer.stat().st_size:
                return {}, None
        config = tomllib.loads(text or '')
        for row in config.get('skills', {}).get('config', []):
            if isinstance(row, dict) and row.get('enabled') is False:
                raw = row.get('path')
                if not isinstance(raw, str) or not Path(raw).expanduser().is_absolute():
                    return {}, None
                disabled.add(str(Path(raw).expanduser().resolve()))
    available = {}; project_methods = []
    binding = small_text(project / 'AGENTS.md')
    for root in (home / 'skills', project / '.agents/skills'):
        if not root.is_dir() or root.is_symlink():
            continue
        for directory in sorted(root.iterdir())[:64]:
            if directory.is_symlink() or not directory.is_dir():
                continue
            path = directory / 'SKILL.md'
            if str(path.resolve()) in disabled or str(directory.resolve()) in disabled:
                continue
            body = small_text(path, 32768)
            match = re.match(r'---\s*\nname:\s*([a-z][a-z0-9-]{0,79})\s*\n', body)
            if not match:
                continue
            name = match[1]
            policy_path = directory / 'agents/openai.yaml'
            if policy_path.exists() or policy_path.is_symlink():
                if policy_path.is_symlink() or policy_path.parent.is_symlink():
                    continue
                policy = small_text(policy_path, 4096)
                # Do not reinterpret unreadable/complex YAML as absent policy.
                # Accept the small explicit opt-in form; richer metadata needs
                # a native effective-policy source, not a permissive regex.
                simple = re.fullmatch(
                    r'''\s*(?P<outer>["']?)policy(?P=outer):[ \t]*\n[ \t]+(?P<inner>["']?)allow_implicit_invocation(?P=inner):[ \t]*true\s*''', policy)
                if not simple:
                    continue
            if root == home / 'skills' and name in NAMES:
                available[name] = path
            elif root != home / 'skills' and name.endswith('-engineering') and name in binding:
                project_methods.append((name, path))
    return available, project_methods[0] if len(project_methods) == 1 else None


def reserve(state, scope, skill, seen=False):
    if state.is_symlink():
        return False
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        return False
    db = state / 'skill-reminders.sqlite3'
    if db.is_symlink():
        return False
    fd = os.open(db, os.O_CREAT | os.O_WRONLY, 0o600); os.close(fd)
    if db.stat().st_uid != os.getuid() or db.stat().st_mode & 0o077:
        return False
    with closing(sqlite3.connect(db, timeout=0.1)) as con, con:
        con.execute('CREATE TABLE IF NOT EXISTS reminders (scope TEXT, skill TEXT, sent INTEGER, expires REAL, PRIMARY KEY(scope,skill))')
        con.execute('BEGIN IMMEDIATE')
        now = time.time(); con.execute('DELETE FROM reminders WHERE expires <= ?', (now,))
        if con.execute('SELECT 1 FROM reminders WHERE scope=? AND skill=?', (scope,skill)).fetchone():
            return False
        if con.execute('SELECT count(*) FROM reminders').fetchone()[0] >= 4096:
            return False
        if not seen and con.execute('SELECT coalesce(sum(sent),0) FROM reminders WHERE scope=?', (scope,)).fetchone()[0] >= 3:
            return False
        con.execute('INSERT INTO reminders VALUES (?,?,?,?)', (scope,skill,int(not seen),now+TTL))
        return not seen


def advisory(data, state, hooks, detector):
    try:
        return _advisory(data, state, hooks, detector)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, sqlite3.Error):
        return None


def _advisory(data, state, hooks, detector):
    event = data.get('hook_event_name', 'PostToolUse')
    if event not in {'PreToolUse', 'PostToolUse', 'SubagentStart'}:
        return None
    session, cwd = (data.get(k) for k in ('session_id', 'cwd'))
    if not all(isinstance(v, str) and 0 < len(v) <= 4096 for v in (session, cwd)) or not Path(cwd).is_absolute():
        return None
    agent = data.get('agent_id')
    if agent is not None and (not isinstance(agent, str) or not agent or len(agent) > 512):
        return None
    if event == 'SubagentStart':
        if not agent or data.get('agent_type') not in ROLE_SKILLS:
            return None
        role = ROLE_SKILLS[data['agent_type']]
        command = ''; paths = []; operations = set()
    else:
        operation = data.get('tool_use_id')
        if not isinstance(operation, str) or not 0 < len(operation) <= 4096:
            return None
        command = data.get('tool_input', {}).get('command')
        if not isinstance(command, str) or len(command) > 32768:
            return None
        if event == 'PostToolUse':
            response = data.get('tool_response')
            success = (isinstance(response, dict) and type(response.get('exit_code')) is int
                       and response['exit_code'] == 0 and response.get('isError') is not True)
            if not success and not isinstance(response, str):
                return None
        operations = detector.operation_skills(command) if event == 'PreToolUse' else set()
        if event == 'PreToolUse' and not operations:
            return None
        paths = []
        if event == 'PostToolUse' and re.search(r'\b(cat|sed|head|tail|rg)\b', command):
            try:
                hint = workdir_hint(data, hooks.parent.parent)
            except (OSError, ValueError, TypeError):
                hint = None
            paths = detector.read_targets(command, hint)
        if len(paths) > 8:
            return None
        if event == 'PostToolUse' and not paths:
            return None
        role = None
    project = project_root(cwd)
    if project is None:
        return None
    scope = hashlib.sha256((session+'\0'+(agent or 'root')+'\0'+str(project)).encode()).hexdigest()
    methods, project_method = catalog(hooks.parent.parent, project, cwd)
    candidates = set(operations) & methods.keys()
    if role:
        candidates = {role} & methods.keys()
    project_read = False
    all_methods = dict(methods)
    if project_method:
        all_methods[project_method[0]] = project_method[1]
    profile = None
    profile_path = Path(__file__).with_name('skill_profiles.py')
    if paths and profile_path.is_file() and not profile_path.is_symlink():
        spec = importlib.util.spec_from_file_location('mainframe_skill_profiles', profile_path)
        if spec and spec.loader:
            profile = importlib.util.module_from_spec(spec); spec.loader.exec_module(profile)
    for raw in paths:
        original = Path(raw)
        if original.is_symlink() or any(parent.is_symlink() and parent.resolve().is_relative_to(project) for parent in original.parents):
            continue
        path = original.resolve()
        # An explicit attempt already demonstrates method awareness; it does not
        # prove read success or application. Repeating advice cannot repair a read.
        for name, skillpath in all_methods.items():
            if path == skillpath.resolve():
                reserve(state, scope, name, seen=True)
        if not path.is_relative_to(project):
            continue
        rel = path.relative_to(project)
        if any(p.lower() in {'.git', '.agents', '.codex', 'node_modules', 'vendor', 'dist', 'build', '.venv', 'fixtures', '__fixtures__', 'examples', 'testdata'} for p in rel.parts):
            continue
        if not path.is_file() or Path(raw).is_symlink():
            continue
        project_read = True
        if detector.candidate_skill(str(rel)) == 'mainframe-testing':
            candidates.add('mainframe-testing')
        elif profile:
            candidates.update(profile.candidates(path, project))
    candidates &= methods.keys()
    if candidates & {'mainframe-k3s', 'mainframe-clickhouse'}:
        candidates.discard('mainframe-infrastructure')
    # Credential delivery is an independent operation; prefer it once before
    # the consumer method, while preserving the shared per-recipient budget.
    if 'mainframe-secrets' in candidates and reserve(state, scope, 'mainframe-secrets'):
        chosen = ('mainframe-secrets', methods['mainframe-secrets'])
    else:
        candidates.discard('mainframe-secrets')
        if len(candidates) == 1:
            name = candidates.pop()
            if not reserve(state, scope, name):
                return None
            chosen = (name, methods[name])
        elif not candidates and project_read and project_method and reserve(state, scope, project_method[0]):
            chosen = project_method
        else:
            return None
    name, path = chosen
    location = json.dumps(str(path), ensure_ascii=True)
    return (f'MAINFRAME skill reminder: consider `{name}` at {location} for this work. '
            'Read it if relevant and not already applied. This advisory does not change your task or authority.')

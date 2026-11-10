"""Validate only addressed task-index rows and note edits; adapters encode effects."""
from collections import Counter
from pathlib import Path
import re

MAX_BYTES = 1_000_000
GROUPS = ('Запланировано', 'На рассмотрении', 'Отложено', 'Отказались')
SECTIONS = ('Суть', 'Ожидаемый результат', 'Ограничения')
ROW = re.compile(r'- (.+?) \[Подробнее\]\((todos/[a-z0-9][a-z0-9-]*\.md)\)')


def _target(workspace, path):
    if not isinstance(workspace, str) or not isinstance(path, str):
        return None
    try:
        root = Path(workspace).resolve(strict=True)
        p = Path(path)
        p = p if p.is_absolute() else root / p
        relative = p.relative_to(root)
        if str(relative) != '.docs/todo' and not (
            len(relative.parts) == 3 and relative.parts[:2] == ('.docs', 'todos')
            and re.fullmatch(r'[a-z0-9][a-z0-9-]*\.md', relative.name)
        ):
            return None
        if any(part.is_symlink() for part in (p, *p.parents) if part.is_relative_to(root)):
            return None
        if '..' in relative.parts:
            return None
        return root, p, relative
    except (OSError, ValueError, RuntimeError):
        return None


def _read(path):
    try:
        if path.is_symlink():
            return None
        with path.open('rb') as f:
            raw = f.read(MAX_BYTES + 1)
        return raw.decode('utf-8') if len(raw) <= MAX_BYTES else None
    except FileNotFoundError:
        return ''
    except (OSError, UnicodeError):
        return None


def _section(text, title):
    match = re.search(r'(?m)^## ' + re.escape(title) + r'\s*\n', text)
    if not match:
        return ''
    return re.split(r'(?m)^#{1,2} ', text[match.end():], maxsplit=1)[0].strip()


def _note_problem(text):
    if len(text) > 5000:
        return 'note exceeds 5000 characters; consolidate its content without losing requirements'
    if not re.search(r'(?m)^# \S[^\n]*$', text):
        return 'note needs a self-contained title'
    if any(not _section(text, name) for name in SECTIONS):
        return 'note needs nonempty Суть, Ожидаемый результат and Ограничения sections'
    return None


def _rows(text):
    group = None
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith('## '):
            group = line[3:]
        elif line.strip() and line != '# TODO':
            yield group, line, number


def _check(root, path, relative, before, after, overlay):
    if str(relative) != '.docs/todo':
        problem = _note_problem(after)
        index = _read(root / '.docs/todo')
        if not problem and index:
            for group, line, _ in _rows(index):
                row = ROW.fullmatch(line)
                if (group == 'Отказались' and row and root / '.docs' / row.group(2) == path
                        and not _section(after, 'Решение')):
                    problem = 'declined idea needs its Решение section explaining the decision'
                    break
        return f'{relative}: {problem}' if problem else None
    old_headings = re.findall(r'(?m)^## (.+)$', before)
    headings = re.findall(r'(?m)^## (.+)$', after)
    if (not before or old_headings != headings) and headings != list(GROUPS):
        return '.docs/todo: retain the four agreed group headings in their established order'
    old = Counter((group, line) for group, line, _ in _rows(before))
    for group, line, number in _rows(after):
        key = group, line
        if old[key]:
            old[key] -= 1
            continue
        locus = f'.docs/todo:{number}'
        row = ROW.fullmatch(line)
        if group not in GROUPS or row is None:
            return locus + ': use one summary line followed by [Подробнее](todos/<name>.md) inside an agreed group'
        summary, link = row.groups()
        if not summary.strip() or len(summary) > 500:
            return locus + ': summary must contain 1–500 characters excluding the link'
        note_path = root / '.docs' / link
        target = _target(str(root), str(note_path))
        if target is None:
            return locus + ': note link must address a regular project note without symlink traversal'
        note = overlay.get(note_path) if note_path in overlay else _read(note_path)
        if not note:
            return locus + ': linked note is missing or unreadable; write the note before its index entry'
        problem = _note_problem(note)
        if problem:
            return locus + ': linked ' + problem
        if group == 'Отказались' and not _section(note, 'Решение'):
            return locus + ': declined idea needs a nonempty Решение section explaining the decision in its note'
    return None


def check_write(workspace, path, content):
    target = _target(workspace, path)
    if target is None or not isinstance(content, str):
        return None
    root, p, relative = target
    if str(relative) != '.docs/todo':
        return _check(root, p, relative, '', content, {})
    if len(content.encode('utf-8')) > MAX_BYTES:
        return None
    before = _read(p)
    if before is None:
        return None
    return _check(root, p, relative, before, content, {})


def check_edit(workspace, path, old, new, replace_all=False):
    target = _target(workspace, path)
    if target is None or not isinstance(old, str) or not isinstance(new, str) or not old:
        return None
    root, p, relative = target
    before = _read(p)
    if before is None or old not in before or (not replace_all and before.count(old) != 1):
        return None
    after = before.replace(old, new, -1 if replace_all else 1)
    if str(relative) == '.docs/todo' and len(after.encode('utf-8')) > MAX_BYTES:
        return None
    return _check(root, p, relative, before, after, {})


def _updated(before, lines):
    """Apply only unambiguous context hunks; malformed/unsupported patches stay neutral."""
    source = before.splitlines()
    cursor = 0
    i = 0
    while i < len(lines):
        header = lines[i]
        if not (header == '@@' or header.startswith('@@ ')):
            raise ValueError('unsupported hunk')
        i += 1
        old, new = [], []
        while i < len(lines) and not lines[i].startswith('@@'):
            line = lines[i]
            i += 1
            if line == '*** End of File':
                continue
            if not line or line[0] not in ' +-':
                raise ValueError('malformed hunk')
            if line[0] in ' -':
                old.append(line[1:])
            if line[0] in ' +':
                new.append(line[1:])
        matches = [n for n in range(cursor, len(source) - len(old) + 1) if source[n:n + len(old)] == old]
        if len(matches) != 1:
            raise ValueError('ambiguous hunk')
        start = matches[0]
        source[start:start + len(old)] = new
        cursor = start + len(new)
    return '\n'.join(source) + ('\n' if source else '')


def check_patch(workspace, patch):
    if not isinstance(patch, str) or len(patch.encode('utf-8')) > MAX_BYTES:
        return None
    lines = patch.splitlines()
    if not lines or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        return None
    changes, overlay = [], {}
    i = 1
    try:
        while i < len(lines) - 1:
            match = re.fullmatch(r'\*\*\* (Add|Update|Delete) File: (.+)', lines[i])
            if match is None:
                return None
            operation, name = match.groups()
            i += 1
            body = []
            while i < len(lines) - 1 and not re.match(r'\*\*\* (?:Add|Update|Delete) File:', lines[i]):
                body.append(lines[i])
                i += 1
            target = _target(workspace, name)
            if target is None:
                continue
            root, p, relative = target
            before = _read(p)
            if before is None:
                return None
            if operation == 'Delete':
                overlay[p] = None
                continue
            if operation == 'Add':
                if p.exists() or any(not line.startswith('+') for line in body):
                    return None
                after = '\n'.join(line[1:] for line in body) + '\n'
            else:
                after = _updated(before, body)
            overlay[p] = after
            changes.append((root, p, relative, before, after))
        for root, p, relative, before, after in changes:
            result = _check(root, p, relative, before, after, overlay)
            if result:
                return result
    except (OSError, ValueError, RuntimeError):
        return None
    return None

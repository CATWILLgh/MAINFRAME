#!/usr/bin/env python3
"""
Валидатор глобального CLAUDE.md хаба MAINFRAME.

Проверяет соответствие правилам Anthropic (R1-R5) и принципу агностичности (R6).
Полная спецификация — `docs/layers/claude-md.md`.

Режимы запуска:
  python3 tools/validate-claude-md.py <path>            # CLI: валидация конкретного файла
  python3 tools/validate-claude-md.py <path> --json     # CLI: вывод в JSON
  python3 tools/validate-claude-md.py --from-hook       # Hook: путь читается из stdin (PostToolUse)
  python3 tools/validate-claude-md.py --session-start   # Hook: сводка по всем целевым файлам в stdout

Exit code:
  0 — нет errors (warnings допустимы)
  1 — есть errors
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------- Конфигурация ----------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Файлы, которые валидируем. Любые правки за пределами этого множества
# хук пропускает мгновенно.
TARGET_FILES = {
    (PROJECT_ROOT / "export" / "CLAUDE.md").resolve(),
    (PROJECT_ROOT / "CLAUDE.md").resolve(),
}

BLACKLIST_FILE = PROJECT_ROOT / "tools" / "agnostic-blacklist.txt"

MAX_LINES = 200
MAX_IMPORT_DEPTH = 5
OLD_DOMAIN = "docs.anthropic.com/en/docs/claude-code"

# Извлечение @import-токенов из текста.
# Берём всё после @ до пробела/конца строки/запятой/скобки.
IMPORT_RE = re.compile(r"@([~/]?[\w][\w./\-~]*)")


# ---------- Утилиты для работы с графом импортов ----------

def strip_html_comments(text: str) -> str:
    """Удалить блок-уровневые HTML-комментарии — Claude Code их стрипает перед инжектом."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def count_non_empty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def resolve_import_path(token: str, base: Path) -> Path:
    """Резолв @path относительно файла с импортом. Поддержка ~ и абсолютных путей."""
    if token.startswith("~"):
        return Path(os.path.expanduser(token)).resolve()
    if token.startswith("/"):
        return Path(token).resolve()
    return (base.parent / token).resolve()


def iter_imports(content: str):
    """
    Пройти по строкам content, вернуть [(line_num, token), ...] для всех @import.
    Игнорирует @ внутри тройных бэктик-блоков (там это пример, не директива).
    """
    in_code = False
    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        # @ должно быть в начале токена (не часть email или middle-of-word)
        for m in IMPORT_RE.finditer(line):
            # Отсеять @ внутри слов: проверяем, что перед @ нет буквы/цифры
            start = m.start()
            if start > 0 and line[start - 1].isalnum():
                continue
            token = m.group(1)
            # Импорт обязан содержать "/" или "." или начинаться с ~/, иначе это не путь
            if "/" not in token and "." not in token and not token.startswith("~"):
                continue
            yield line_num, token


def build_import_graph(start: Path) -> tuple[list[tuple[Path, str, int]], list[dict]]:
    """
    Обойти граф импортов начиная со start.
    Возвращает:
      - graph: [(path, content, depth), ...] для всех существующих и читаемых файлов
      - issues: ошибки, найденные при обходе (превышение глубины, несуществующий импорт, не UTF-8)
    """
    graph: list[tuple[Path, str, int]] = []
    issues: list[dict] = []
    visited: set[Path] = set()

    def walk(path: Path, depth: int, origin: Path | None, origin_line: int | None):
        path = path.resolve()
        if path in visited:
            return
        visited.add(path)

        if not path.exists():
            if origin is not None:
                issues.append({
                    "rule": "R4",
                    "level": "error",
                    "file": str(origin),
                    "line": origin_line,
                    "message": f"импорт `@{path_token_from(origin, path)}` не существует (резолв: {path}).",
                })
            return

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append({
                "rule": "FORMAT",
                "level": "warning",
                "file": str(path),
                "line": None,
                "message": "файл не в UTF-8 — пропуск.",
            })
            return

        graph.append((path, content, depth))

        # Если глубина уже на пределе — следующих импортов не разворачиваем,
        # но факт превышения фиксируется только при попытке.
        for line_num, token in iter_imports(content):
            child_depth = depth + 1
            if child_depth > MAX_IMPORT_DEPTH:
                issues.append({
                    "rule": "R3",
                    "level": "error",
                    "file": str(path),
                    "line": line_num,
                    "message": f"глубина импорта `@{token}` превышает {MAX_IMPORT_DEPTH} хопов.",
                })
                continue
            child_path = resolve_import_path(token, path)
            walk(child_path, child_depth, origin=path, origin_line=line_num)

    walk(start, 0, origin=None, origin_line=None)
    return graph, issues


def path_token_from(origin: Path, resolved: Path) -> str:
    """Попытаться восстановить, как именно был записан токен (для красоты сообщения)."""
    try:
        return str(resolved.relative_to(origin.parent))
    except ValueError:
        return str(resolved)


# ---------- Правила ----------

def check_r1_size(graph: list) -> list[dict]:
    """≤ 200 строк после раскрытия импортов и стрипа HTML-комментариев (рекомендация Anthropic)."""
    total = 0
    for _, content, _ in graph:
        stripped = strip_html_comments(content)
        total += count_non_empty_lines(stripped)
    if total > MAX_LINES:
        return [{
            "rule": "R1",
            "level": "warning",
            "file": None,
            "line": None,
            "message": (
                f"суммарный размер после раскрытия импортов: {total} непустых строк "
                f"(рекомендация Anthropic: ≤ {MAX_LINES}; больше → ниже adherence и больше токенов)."
            ),
        }]
    return []


def check_r2_no_frontmatter(graph: list) -> list[dict]:
    """Корневой CLAUDE.md не должен начинаться с YAML-frontmatter (он только для .claude/rules/)."""
    if not graph:
        return []
    root_path, root_content, _ = graph[0]
    lines = root_content.splitlines()
    if lines and lines[0].strip() == "---":
        return [{
            "rule": "R2",
            "level": "warning",
            "file": str(root_path),
            "line": 1,
            "message": "YAML-frontmatter в начале файла не задокументирован для корневого CLAUDE.md.",
        }]
    return []


def check_r5_old_domain(graph: list) -> list[dict]:
    """Нет ссылок на старый домен docs.anthropic.com/en/docs/claude-code (отдаёт 301)."""
    issues = []
    for path, content, _ in graph:
        for line_num, line in enumerate(content.splitlines(), 1):
            if OLD_DOMAIN in line:
                issues.append({
                    "rule": "R5",
                    "level": "warning",
                    "file": str(path),
                    "line": line_num,
                    "message": f"ссылка на старый домен `{OLD_DOMAIN}` — замени на `code.claude.com/docs/en`.",
                })
    return issues


def load_blacklist() -> list[str]:
    if not BLACKLIST_FILE.exists():
        return []
    patterns = []
    for line in BLACKLIST_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def check_r6_agnostic(graph: list) -> list[dict]:
    """Принцип проектной агностичности: blacklist в tools/agnostic-blacklist.txt, case-insensitive substring."""
    patterns = load_blacklist()
    if not patterns:
        return []
    issues = []
    for path, content, _ in graph:
        # HTML-комментарии стрипаются Claude — наши проектные пометки в них допустимы.
        active = strip_html_comments(content)
        for line_num, line in enumerate(active.splitlines(), 1):
            line_lower = line.lower()
            for pat in patterns:
                if pat.lower() in line_lower:
                    issues.append({
                        "rule": "R6",
                        "level": "warning",
                        "file": str(path),
                        "line": line_num,
                        "message": f"найден паттерн `{pat}` — проектная специфика в глобальном файле (нарушает принцип agnostic, см. docs/layers/claude-md.md).",
                    })
    return issues


# ---------- Главная логика ----------

def validate_target(target: Path) -> list[dict]:
    """Прогнать все проверки для одного целевого файла."""
    if not target.exists():
        return [{
            "rule": "INFO",
            "level": "info",
            "file": str(target),
            "line": None,
            "message": "файл не существует — пропуск (это нормально, пока хаб не собран).",
        }]

    graph, graph_issues = build_import_graph(target)
    if not graph:
        return graph_issues or [{
            "rule": "INFO",
            "level": "info",
            "file": str(target),
            "line": None,
            "message": "не удалось прочитать файл.",
        }]

    issues = list(graph_issues)
    issues.extend(check_r1_size(graph))
    issues.extend(check_r2_no_frontmatter(graph))
    issues.extend(check_r5_old_domain(graph))
    issues.extend(check_r6_agnostic(graph))
    return issues


def format_human(target: Path, issues: list[dict]) -> str:
    rel = relpath(target)
    if not issues:
        return f"OK {rel}"

    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    infos = [i for i in issues if i["level"] == "info"]

    parts = [f"Валидатор CLAUDE.md — {rel}"]
    for label, bucket in (("errors", errors), ("warnings", warnings), ("info", infos)):
        if not bucket:
            continue
        parts.append(f"\n{label} ({len(bucket)}):")
        for i in bucket:
            loc = ""
            if i.get("file"):
                loc = relpath(Path(i["file"]))
                if i.get("line"):
                    loc += f":{i['line']}"
                loc = f" {loc} —"
            parts.append(f"  [{i['rule']}]{loc} {i['message']}")
    return "\n".join(parts)


def relpath(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def run_session_start() -> int:
    """SessionStart hook: краткая сводка в stdout (попадает в additionalContext)."""
    out = ["## Валидация глобальных файлов хаба MAINFRAME"]
    for target in sorted(TARGET_FILES):
        issues = validate_target(target)
        errors = [i for i in issues if i["level"] == "error"]
        warnings = [i for i in issues if i["level"] == "warning"]
        infos = [i for i in issues if i["level"] == "info"]
        rel = relpath(target)
        if infos and not errors and not warnings:
            out.append(f"- `{rel}` — пропущено: {infos[0]['message']}")
        elif not errors and not warnings:
            out.append(f"- `{rel}` — OK")
        else:
            out.append(f"- `{rel}` — errors={len(errors)}, warnings={len(warnings)}")
            for i in (errors + warnings)[:3]:
                line_part = f":{i['line']}" if i.get("line") else ""
                out.append(f"  - [{i['rule']}]{line_part} {i['message']}")
            if len(errors) + len(warnings) > 3:
                out.append(f"  - … ещё {len(errors) + len(warnings) - 3}. Запусти `python3 tools/validate-claude-md.py {rel}` для деталей.")
    print("\n".join(out))
    return 0


def run_from_hook() -> int:
    """PostToolUse hook: путь файла читается из stdin (формат Claude Code)."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # нет валидного входа — тихо выходим

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not file_path:
        return 0

    target = Path(file_path).resolve()

    # Раннее path-фильтрование — если правка не нашего файла, выходим за миллисекунду.
    if target not in TARGET_FILES:
        return 0

    issues = validate_target(target)
    if not issues:
        return 0

    # PostToolUse: stderr попадает в transcript для Claude.
    print(format_human(target, issues), file=sys.stderr)

    has_errors = any(i["level"] == "error" for i in issues)
    return 1 if has_errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Валидатор CLAUDE.md по правилам Anthropic + принципам MAINFRAME.")
    parser.add_argument("path", nargs="?", help="Путь к файлу для валидации (CLI-режим).")
    parser.add_argument("--json", action="store_true", help="Вывод в JSON (CLI-режим).")
    parser.add_argument("--from-hook", action="store_true", help="Режим PostToolUse: путь читается из stdin.")
    parser.add_argument("--session-start", action="store_true", help="Режим SessionStart: сводка по всем TARGET_FILES.")
    args = parser.parse_args()

    if args.session_start:
        return run_session_start()
    if args.from_hook:
        return run_from_hook()
    if not args.path:
        parser.print_help()
        return 2

    target = Path(args.path).resolve()
    issues = validate_target(target)

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print(format_human(target, issues))

    has_errors = any(i["level"] == "error" for i in issues)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())

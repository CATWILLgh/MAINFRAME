#!/usr/bin/env python3
"""Track newly introduced code residue and prevent incomplete completion.

This is the canonical, product-neutral implementation of one logical hook
component with fixed advisory and guard effects:

* after an edit, it reports newly introduced high-confidence unfinished-code,
  suppression, disabled-test, debug, or security findings;
* a completion guard blocks only while an attributed blocking finding remains
  after re-reading and re-scanning the file;
* context-dependent Semgrep findings are review advice and never enter the
  completion guard;
* a file or Python function that crosses a conservative size-review threshold
  produces one non-blocking cohesion advisory;
* unavailable protection is reported once per execution scope and never
  becomes a hard lock.

Adapters call :func:`capture_before` immediately before a successful file-edit
tool, :func:`record_after` immediately afterwards, and :func:`check_completion`
from a native continuation-capable completion event.  Product event names,
payloads, result encoding, and installation remain adapter-owned.

State is one private temporary JSON file per adapter namespace, native
session/conversation scope, and workspace.  It contains hashes, counts, and
notice keys, not source text or event history.  The operation identity is used
only to pair one short-lived pre/post snapshot.  Missing input, parser limits,
scanner failures, state failures, and hook exceptions return a bounded
non-blocking protection advisory and never create a hard lock.
"""

from __future__ import annotations

import ast
from collections import Counter
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import tokenize
from typing import Iterable, NamedTuple


MAX_FILE_BYTES = 2_000_000
MAX_FILES_PER_EDIT = 24
MAX_MESSAGE_ROWS = 6
PENDING_MAX_AGE_SECONDS = 60 * 60
STATE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
LOCK_MAX_AGE_SECONDS = 60
LOCK_RETRIES = 100
LOCK_RETRY_SECONDS = 0.005

CODE_EXTENSIONS = frozenset(
    {
        ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        ".dart", ".go", ".rb", ".rs", ".java", ".kt", ".kts", ".swift",
        ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".scala", ".php",
        ".lua", ".sh", ".bash", ".zsh", ".sql", ".vue", ".svelte",
    }
)


class QualityResult(NamedTuple):
    """A product-neutral result; at most one field is normally populated."""

    advisory: str | None = None
    block_reason: str | None = None


class Occurrence(NamedTuple):
    label: str
    line: int
    fingerprint: str
    channel: str = "markers"
    blocking: bool = True


class ScanIssue(NamedTuple):
    key: str
    message: str


class FunctionMetric(NamedTuple):
    name: str
    line: int
    lines: int


class GrowthMetrics(NamedTuple):
    lines: int
    python_functions: dict[str, FunctionMetric] | None


class ScanResult(NamedTuple):
    rows: list[Occurrence]
    channels: frozenset[str]
    issues: tuple[ScanIssue, ...]
    revision: str | None
    growth: GrowthMetrics | None = None


class GrowthFinding(NamedTuple):
    path: Path
    kind: str
    name: str | None
    line: int | None
    before: int
    after: int


def _profile(
    line: tuple[str, ...],
    block: tuple[str, str] | None = None,
    *,
    nests: bool = False,
    backtick: bool = False,
    strings: str = "\"'",
    char: bool = False,
    lifetime: bool = False,
    sql_double: bool = False,
    no_escape: str = "",
    heredoc: bool = False,
    exotic: str | None = None,
) -> dict[str, object]:
    return {
        "line": line,
        "block": block,
        "nests": nests,
        "backtick": backtick,
        "strings": set(strings),
        "char": char,
        "lifetime": lifetime,
        "sql_double": sql_double,
        "no_escape": set(no_escape),
        "heredoc": heredoc,
        "exotic": re.compile(exotic) if exotic else None,
    }


_C_BLOCK = ("/*", "*/")
_LANG_PROFILES = {
    ".c": _profile(("//",), _C_BLOCK, char=True),
    ".h": _profile(("//",), _C_BLOCK, char=True),
    ".cc": _profile(("//",), _C_BLOCK, char=True, exotic=r'R"'),
    ".cpp": _profile(("//",), _C_BLOCK, char=True, exotic=r'R"'),
    ".hpp": _profile(("//",), _C_BLOCK, char=True, exotic=r'R"'),
    ".cs": _profile(("//",), _C_BLOCK, char=True, exotic=r'@"|\$@"'),
    ".java": _profile(("//",), _C_BLOCK, char=True, exotic=r'"""'),
    ".kt": _profile(("//",), _C_BLOCK, nests=True, backtick=True, char=True, exotic=r'"""'),
    ".kts": _profile(("//",), _C_BLOCK, nests=True, backtick=True, char=True, exotic=r'"""'),
    ".swift": _profile(("//",), _C_BLOCK, nests=True, exotic=r'#"|"""'),
    ".scala": _profile(("//",), _C_BLOCK, char=True, exotic=r'"""'),
    ".dart": _profile(("//",), _C_BLOCK, exotic=r"r'|r\"|'''|\"\"\""),
    ".go": _profile(("//",), _C_BLOCK, backtick=True, char=True),
    ".rs": _profile(("//",), _C_BLOCK, nests=True, char=True, lifetime=True, exotic=r'r#*"|b"'),
    ".php": _profile(("//", "#"), _C_BLOCK, exotic=r"<<<"),
    ".js": _profile(("//",), _C_BLOCK, backtick=True),
    ".mjs": _profile(("//",), _C_BLOCK, backtick=True),
    ".cjs": _profile(("//",), _C_BLOCK, backtick=True),
    ".ts": _profile(("//",), _C_BLOCK, backtick=True),
    ".jsx": _profile(("//",), _C_BLOCK, backtick=True),
    ".tsx": _profile(("//",), _C_BLOCK, backtick=True),
    ".vue": _profile(("//",), _C_BLOCK, backtick=True),
    ".svelte": _profile(("//",), _C_BLOCK, backtick=True),
    ".sql": _profile(("--",), _C_BLOCK, strings="'", sql_double=True, no_escape="'"),
    ".sh": _profile(("#",), backtick=True, no_escape="'", heredoc=True),
    ".bash": _profile(("#",), backtick=True, no_escape="'", heredoc=True),
    ".zsh": _profile(("#",), backtick=True, no_escape="'", heredoc=True),
    ".lua": _profile(("--",), exotic=r"--\[\[|\[=*\[|\[\["),
}

_CHAR_LITERAL = re.compile(r"'(?:\\.|[^'\\\n])'")
_HEREDOC = re.compile(r"<<([-~]?)\s*\\?(['\"]?)([A-Za-z_]\w*)\2")


def _python_comments(text: str) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                rows.append((token.start[0], token.string, "comment"))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        pass
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                value = ast.get_docstring(node, clean=False)
                if value is not None:
                    rows.append((node.body[0].lineno, value, "docstring"))
    except (SyntaxError, ValueError):
        pass
    return rows


def _generic_comments(text: str, profile: dict[str, object]) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    size = len(text)
    index = 0
    line_number = 1
    line_delimiters = profile["line"]
    block = profile["block"]
    block_open, block_close = block if isinstance(block, tuple) else (None, None)
    nesting = bool(profile["nests"])
    strings = profile["strings"]
    no_escape = profile["no_escape"]
    pending_heredoc: tuple[str, str] | None = None

    def starts(value: str) -> bool:
        return text.startswith(value, index)

    while index < size:
        char = text[index]
        delimiter = next((value for value in line_delimiters if starts(value)), None)
        if delimiter is not None:
            end = text.find("\n", index)
            if end == -1:
                end = size
            rows.append((line_number, text[index:end].rstrip(), "comment"))
            index = end
            continue

        if profile["heredoc"] and char == "<" and starts("<<"):
            match = _HEREDOC.match(text, index)
            if match:
                pending_heredoc = (match.group(3), match.group(1))
                index = match.end()
                continue

        if block_open and starts(block_open):
            first_line = line_number
            buffer = [block_open]
            index += len(block_open)
            depth = 1
            while index < size and depth:
                if nesting and text.startswith(block_open, index):
                    depth += 1
                    buffer.append(block_open)
                    index += len(block_open)
                    continue
                if text.startswith(block_close, index):
                    depth -= 1
                    buffer.append(block_close)
                    index += len(block_close)
                    continue
                if text[index] == "\n":
                    line_number += 1
                buffer.append(text[index])
                index += 1
            rows.append((first_line, "".join(buffer), "comment"))
            continue

        if profile["backtick"] and char == "`":
            index += 1
            while index < size:
                current = text[index]
                if current == "\\":
                    index += 2
                    continue
                if current == "\n":
                    line_number += 1
                index += 1
                if current == "`":
                    break
            continue

        if profile["char"] and char == "'":
            match = _CHAR_LITERAL.match(text, index)
            if match:
                index = match.end()
                continue
            index += 1
            continue

        if char in strings:
            delimiter = char
            escaped = delimiter not in no_escape
            index += 1
            while index < size:
                current = text[index]
                if escaped and current == "\\":
                    index += 2
                    continue
                if profile["sql_double"] and current == delimiter and index + 1 < size and text[index + 1] == delimiter:
                    index += 2
                    continue
                if current == delimiter:
                    index += 1
                    break
                if current == "\n":
                    line_number += 1
                index += 1
            continue

        if char == "\\":
            if index + 1 < size and text[index + 1] == "\n":
                line_number += 1
            index += 2
            continue

        if char == "\n":
            line_number += 1
            index += 1
            if pending_heredoc:
                sentinel, mode = pending_heredoc
                pending_heredoc = None
                while index < size:
                    end = text.find("\n", index)
                    line_end = end if end != -1 else size
                    segment = text[index:line_end]
                    terminator = segment.lstrip("\t") if mode == "-" else segment.strip() if mode == "~" else segment
                    index = end + 1 if end != -1 else size
                    if end != -1:
                        line_number += 1
                    if terminator == sentinel:
                        break
            continue
        index += 1

    return rows


def _extract_comments(text: str, extension: str) -> list[tuple[int, str, str]]:
    try:
        if not text:
            return []
        if extension in {".py", ".pyi"}:
            return _python_comments(text)
        if extension == ".rb":
            return []
        profile = _LANG_PROFILES.get(extension)
        if profile is None:
            return []
        exotic = profile["exotic"]
        if isinstance(exotic, re.Pattern) and exotic.search(text):
            return []
        return _generic_comments(text, profile)
    except Exception:
        return []


def _blank(buffer: list[str], start: int, end: int) -> None:
    """Mask non-code while preserving offsets and line numbers."""
    for index in range(max(0, start), min(len(buffer), end)):
        if buffer[index] not in {"\n", "\r"}:
            buffer[index] = " "


def _line_offsets(text: str) -> list[int]:
    offsets = [0]
    for match in re.finditer("\n", text):
        offsets.append(match.end())
    return offsets


def _python_code_only(text: str) -> str | None:
    """Return Python with comments and strings masked, or None if uncertain."""
    buffer = list(text)
    offsets = _line_offsets(text)

    def absolute(position: tuple[int, int]) -> int:
        row, column = position
        if row < 1 or row > len(offsets):
            raise ValueError("token position outside input")
        return min(len(text), offsets[row - 1] + column)

    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type in {tokenize.COMMENT, tokenize.STRING}:
                _blank(buffer, absolute(token.start), absolute(token.end))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return None
    return "".join(buffer)


def _generic_code_only(text: str, profile: dict[str, object]) -> str | None:
    """Conservatively mask strings and comments for code-only detectors."""
    exotic = profile["exotic"]
    if isinstance(exotic, re.Pattern) and exotic.search(text):
        return None

    buffer = list(text)
    size = len(text)
    index = 0
    line_delimiters = profile["line"]
    block = profile["block"]
    block_open, block_close = block if isinstance(block, tuple) else (None, None)
    strings = profile["strings"]
    no_escape = profile["no_escape"]
    pending_heredoc: tuple[str, str] | None = None

    def starts(value: str) -> bool:
        return text.startswith(value, index)

    while index < size:
        char = text[index]
        delimiter = next((value for value in line_delimiters if starts(value)), None)
        if delimiter is not None:
            end = text.find("\n", index)
            end = size if end == -1 else end
            _blank(buffer, index, end)
            index = end
            continue

        if profile["heredoc"] and starts("<<"):
            match = _HEREDOC.match(text, index)
            if match:
                pending_heredoc = (match.group(3), match.group(1))
                index = match.end()
                continue

        if block_open and starts(block_open):
            start = index
            index += len(block_open)
            depth = 1
            while index < size and depth:
                if profile["nests"] and text.startswith(block_open, index):
                    depth += 1
                    index += len(block_open)
                    continue
                if text.startswith(block_close, index):
                    depth -= 1
                    index += len(block_close)
                    continue
                index += 1
            if depth:
                return None
            _blank(buffer, start, index)
            continue

        if profile["backtick"] and char == "`":
            start = index
            index += 1
            while index < size:
                current = text[index]
                if current == "\\":
                    index += 2
                    continue
                index += 1
                if current == "`":
                    break
            else:
                return None
            _blank(buffer, start, index)
            continue

        if profile["char"] and char == "'":
            match = _CHAR_LITERAL.match(text, index)
            if match:
                _blank(buffer, index, match.end())
                index = match.end()
                continue
            if profile["lifetime"] and index + 1 < size and (
                text[index + 1].isalpha() or text[index + 1] == "_"
            ):
                index += 1
                continue
            return None

        if char in strings:
            start = index
            delimiter = char
            escaped = delimiter not in no_escape
            index += 1
            while index < size:
                current = text[index]
                if escaped and current == "\\":
                    index += 2
                    continue
                if (
                    profile["sql_double"]
                    and current == delimiter
                    and index + 1 < size
                    and text[index + 1] == delimiter
                ):
                    index += 2
                    continue
                index += 1
                if current == delimiter:
                    break
            else:
                return None
            _blank(buffer, start, index)
            continue

        if char == "\n" and pending_heredoc:
            sentinel, mode = pending_heredoc
            pending_heredoc = None
            content_start = index + 1
            index = content_start
            found = False
            while index < size:
                end = text.find("\n", index)
                line_end = end if end != -1 else size
                segment = text[index:line_end]
                terminator = (
                    segment.lstrip("\t")
                    if mode == "-"
                    else segment.strip()
                    if mode == "~"
                    else segment
                )
                index = end + 1 if end != -1 else size
                if terminator == sentinel:
                    found = True
                    _blank(buffer, content_start, index)
                    break
            if not found:
                return None
            continue

        if char == "\\":
            index += 2
            continue
        index += 1

    return "".join(buffer)


def _code_only(text: str, extension: str) -> str | None:
    if extension in {".py", ".pyi"}:
        return _python_code_only(text)
    profile = _LANG_PROFILES.get(extension)
    if profile is None:
        return None
    try:
        return _generic_code_only(text, profile)
    except Exception:
        return None


_COMMENT_MARKERS = (
    ("TODO/FIXME/HACK/XXX comment", re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)),
    ("@ts-ignore / @ts-nocheck", re.compile(r"@ts-(?:ignore|nocheck)\b")),
    ("eslint-disable", re.compile(r"eslint-disable\b")),
    ("# type: ignore", re.compile(r"#\s*type:\s*ignore\b")),
    ("# noqa", re.compile(r"#\s*noqa\b")),
    ("pylint: disable", re.compile(r"pylint:\s*disable\b")),
)

_JS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}
_CODE_MARKERS = (
    (
        "skipped/focused test (.skip/.only/xit/fit)",
        re.compile(
            r"(?m)^[ \t]*(?:(?:it|test|describe|suite|context)\.(?:skip|only)"
            r"|(?:xit|fit|xdescribe|fdescribe))\s*\("
        ),
        _JS_EXTENSIONS,
    ),
    (
        "pytest/unittest skip",
        re.compile(r"(?m)^[ \t]*@(?:pytest\.mark\.skip|unittest\.skip)"),
        {".py", ".pyi"},
    ),
)

_DEBUG_MARKERS = (
    ("debugger statement", re.compile(r"(?m)^[ \t]*debugger\s*;?[ \t]*(?://.*)?$"), _JS_EXTENSIONS),
    ("console.debug", re.compile(r"(?m)^[ \t]*console\.debug\s*\("), _JS_EXTENSIONS),
    ("breakpoint()", re.compile(r"(?m)^[ \t]*breakpoint\s*\("), {".py", ".pyi"}),
    ("pdb.set_trace()", re.compile(r"(?m)^[ \t]*pdb\.set_trace\s*\("), {".py", ".pyi"}),
    ("var_dump()", re.compile(r"(?m)^[ \t]*var_dump\s*\("), {".php"}),
    ("dd()", re.compile(r"(?m)^[ \t]*(?:\$[A-Za-z_]\w*->)?dd\s*\("), {".php"}),
)

_PROCESS_ORDINAL = re.compile(
    r"\b(?i:phase|stage|step|part|iteration|milestone)"
    r"\s*[-#:]?\s*(?:\d+|(?!I\b)[A-Z]\b|[IVX]{2,4}\b)(?!\s*[=<>])"
)
_PROCESS_EPHEMERAL = re.compile(
    r"\bas (?:discussed|requested|agreed|we discussed|per our discussion)\b"
    r"|\b(?:per|from|see|in|follow) the (?:plan|to-?do(?: list)?|task list)\b",
    re.IGNORECASE,
)
_PROCESS_DIVIDER = re.compile(r"={4,}|-{4,}|\*{4,}|#{4,}|_{4,}")


def _line_for(text: str, start_line: int, offset: int) -> int:
    return start_line + text.count("\n", 0, offset)


def _fingerprint(label: str, kind: str, evidence: str) -> str:
    normalized = " ".join(evidence.strip().split())[:1000]
    raw = f"{label}\0{kind}\0{normalized}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()[:24]


def _occurrence(
    label: str,
    line: int,
    kind: str,
    evidence: str,
    *,
    channel: str = "markers",
    blocking: bool = True,
) -> Occurrence:
    fingerprint = _fingerprint(label, f"{channel}:{kind}", evidence)
    return Occurrence(label, max(1, line), fingerprint, channel, blocking)


FILE_LENGTH_THRESHOLD = 400
PYTHON_FUNCTION_LENGTH_THRESHOLD = 60
_FILE_GROWTH_EXTENSIONS = CODE_EXTENSIONS - {".sql"}
_PYTHON_SECURITY_CHANNEL = "python-security"
_NODE_SECURITY_CHANNEL = "node-security"
_SEMGREP_SECURITY_CHANNEL = "semgrep-security-advice"
_PYTHON_EXTENSIONS = {".py", ".pyi"}
_NODE_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
_RUFF_RULES = "S102,S307,S506,S602,S605,S501,S324"
_RUFF_LABELS = {
    "S102": "Python security S102: dynamic exec()",
    "S307": "Python security S307: dynamic eval()",
    "S506": "Python security S506: unsafe YAML loading",
    "S602": "Python security S602: subprocess shell execution",
    "S605": "Python security S605: shell process execution",
    "S501": "Python security S501: TLS verification disabled",
    "S324": "Python security S324: weak cryptographic hash",
}
_RUFF_SHELL_RULES = {"S602", "S605"}
_OXLINT_LABELS = {
    "no-eval": "JavaScript security: eval()",
    "no-new-func": "JavaScript security: dynamic Function()",
    "no-script-url": "JavaScript security: javascript URL",
    "no-implied-eval": "JavaScript security: implicit string evaluation",
}
_OXLINT_CONFIG = {
    "globals": {
        "setInterval": "readonly",
        "setTimeout": "readonly",
        "window": "readonly",
    }
}
_SEMGREP_LABELS = {
    "mainframe.javascript.dynamic-child-process-exec": (
        "JavaScript security review: dynamic child-process command"
    ),
    "mainframe.javascript.tls-verification-disabled": (
        "JavaScript security review: TLS verification disabled"
    ),
}
_SEMGREP_CONFIG = {
    "rules": [
        {
            "id": "mainframe.javascript.dynamic-child-process-exec",
            "languages": ["javascript", "typescript"],
            "message": "Review dynamically constructed child-process command.",
            "severity": "WARNING",
            "pattern-either": [
                {"pattern": "child_process.exec(`...${$VALUE}...`, ...)"},
                {"pattern": "child_process.execSync(`...${$VALUE}...`, ...)"},
                {"pattern": 'require("child_process").exec(`...${$VALUE}...`, ...)'},
                {"pattern": 'require("child_process").execSync(`...${$VALUE}...`, ...)'},
                {"pattern": 'require("node:child_process").exec(`...${$VALUE}...`, ...)'},
                {"pattern": 'require("node:child_process").execSync(`...${$VALUE}...`, ...)'},
            ],
        },
        {
            "id": "mainframe.javascript.tls-verification-disabled",
            "languages": ["javascript", "typescript"],
            "message": "Review an HTTPS agent with TLS verification disabled.",
            "severity": "WARNING",
            "pattern-either": [
                {"pattern": "new https.Agent({..., rejectUnauthorized: false, ...})"},
                {
                    "pattern": (
                        'new require("https").Agent('
                        "{..., rejectUnauthorized: false, ...})"
                    )
                },
                {
                    "pattern": (
                        'new require("node:https").Agent('
                        "{..., rejectUnauthorized: false, ...})"
                    )
                },
            ],
        },
    ]
}
_SEMGREP_EXEC_CANDIDATE = re.compile(
    r"\b(?:child_process|require\s*\(\s*['\"](?:node:)?child_process['\"]\s*\))"
    r"[\s\S]{0,400}?\.exec(?:Sync)?\s*\("
)
_SEMGREP_TLS_CANDIDATE = re.compile(r"\brejectUnauthorized\s*:\s*false\b")


def _growth_function_key(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8", errors="replace")).hexdigest()[:24]


class _FunctionMetricVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.functions: dict[str, FunctionMetric] = {}

    def _visit_scope(self, node: ast.AST, *, record: bool) -> None:
        name = getattr(node, "name", None)
        if not isinstance(name, str):
            return
        qualified = ".".join([*self.stack, name])
        if record:
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if isinstance(start, int) and isinstance(end, int) and end >= start:
                self.functions[_growth_function_key(qualified)] = FunctionMetric(
                    qualified,
                    start,
                    end - start + 1,
                )
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scope(node, record=False)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_scope(node, record=True)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scope(node, record=True)


def _growth_metrics(text: str, extension: str) -> GrowthMetrics | None:
    if extension not in _FILE_GROWTH_EXTENSIONS:
        return None
    functions: dict[str, FunctionMetric] | None = None
    if extension in _PYTHON_EXTENSIONS:
        try:
            tree = ast.parse(text)
            visitor = _FunctionMetricVisitor()
            visitor.visit(tree)
            functions = visitor.functions
        except (SyntaxError, ValueError, RecursionError):
            functions = None
    return GrowthMetrics(len(text.splitlines()), functions)


def _serialize_growth(metrics: GrowthMetrics | None) -> dict[str, object] | None:
    if metrics is None:
        return None
    functions = None
    if metrics.python_functions is not None:
        functions = {
            key: metric.lines
            for key, metric in metrics.python_functions.items()
        }
    return {"lines": metrics.lines, "python_functions": functions}


def _growth_findings(
    path: Path,
    before_value: object,
    current: GrowthMetrics | None,
) -> list[GrowthFinding]:
    if current is None or not isinstance(before_value, dict):
        return []
    before_lines = before_value.get("lines")
    if not isinstance(before_lines, int) or before_lines < 0:
        return []

    findings: list[GrowthFinding] = []
    if before_lines <= FILE_LENGTH_THRESHOLD < current.lines:
        findings.append(
            GrowthFinding(path, "file", None, None, before_lines, current.lines)
        )

    before_functions = before_value.get("python_functions")
    if current.python_functions is None or not isinstance(before_functions, dict):
        return findings
    for key, metric in current.python_functions.items():
        previous = before_functions.get(key, 0)
        if (
            isinstance(previous, int)
            and previous >= 0
            and previous <= PYTHON_FUNCTION_LENGTH_THRESHOLD < metric.lines
        ):
            findings.append(
                GrowthFinding(
                    path,
                    "Python function",
                    metric.name,
                    metric.line,
                    previous,
                    metric.lines,
                )
            )
    return findings


def _source_excerpt(text: str, row: int, end_row: int) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    start = max(0, row - 1)
    end = min(len(lines), max(start + 1, end_row))
    return "\n".join(line.strip() for line in lines[start:end])[:1000]


def _python_security_findings(text: str, path: Path) -> list[Occurrence]:
    executable = shutil.which("ruff")
    if executable is None:
        raise RuntimeError("ruff unavailable")
    completed = subprocess.run(
        [
            executable,
            "check",
            "--isolated",
            "--select",
            _RUFF_RULES,
            "--output-format",
            "json",
            "--no-cache",
            "--ignore-noqa",
            "--stdin-filename",
            str(path),
            "-",
        ],
        input=text,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=path.parent,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError("ruff scan failed")
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("invalid Ruff output") from error
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise RuntimeError("invalid Ruff result")

    rows: list[Occurrence] = []
    for item in raw:
        code = item.get("code")
        if code not in _RUFF_LABELS:
            continue
        message = str(item.get("message") or "")
        if code in _RUFF_SHELL_RULES and "seems safe" in message:
            continue
        row = int((item.get("location") or {}).get("row") or 0)
        end_row = int((item.get("end_location") or {}).get("row") or row)
        rows.append(
            _occurrence(
                _RUFF_LABELS[code],
                row,
                "scanner",
                _source_excerpt(text, row, end_row),
                channel=_PYTHON_SECURITY_CHANNEL,
            )
        )
    return rows


def _normalized_oxlint_code(value: object) -> str:
    code = str(value or "")
    if "(" in code and code.endswith(")"):
        code = code.split("(", 1)[1][:-1]
    return code


def _node_security_findings(text: str, extension: str) -> list[Occurrence]:
    executable = shutil.which("oxlint")
    if executable is None:
        raise RuntimeError("oxlint unavailable")
    with tempfile.TemporaryDirectory(prefix="mainframe-node-security-") as directory:
        root = Path(directory)
        config = root / "oxlint.json"
        source = root / f"source{extension}"
        config.write_text(json.dumps(_OXLINT_CONFIG), encoding="utf-8")
        source.write_text(text, encoding="utf-8")
        command = [
            executable,
            "--config",
            str(config),
            "-A",
            "all",
            "--disable-nested-config",
            "--no-ignore",
            "--format=json",
        ]
        for rule in _OXLINT_LABELS:
            command.extend(["-D", rule])
        command.append(str(source))
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=root,
            check=False,
        )
    if completed.returncode not in {0, 1}:
        raise RuntimeError("Oxlint scan failed")
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("invalid Oxlint output") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("diagnostics"), list):
        raise RuntimeError("invalid Oxlint result")
    if any(not isinstance(item, dict) for item in raw["diagnostics"]):
        raise RuntimeError("invalid Oxlint diagnostic")

    rows: list[Occurrence] = []
    for item in raw["diagnostics"]:
        code = _normalized_oxlint_code(item.get("code"))
        if code not in _OXLINT_LABELS:
            continue
        labels = item.get("labels") or []
        span = labels[0].get("span", {}) if labels and isinstance(labels[0], dict) else {}
        row = int(span.get("line") or 0)
        end_row = int(span.get("line_end") or row)
        rows.append(
            _occurrence(
                _OXLINT_LABELS[code],
                row,
                "scanner",
                _source_excerpt(text, row, end_row),
                channel=_NODE_SECURITY_CHANNEL,
            )
        )
    return rows


def _semgrep_candidate(text: str) -> bool:
    return bool(_SEMGREP_EXEC_CANDIDATE.search(text) or _SEMGREP_TLS_CANDIDATE.search(text))


def _semgrep_security_findings(
    text: str,
    extension: str,
) -> list[Occurrence]:
    if not _semgrep_candidate(text):
        return []
    executable = shutil.which("semgrep")
    if executable is None:
        raise RuntimeError("semgrep unavailable")
    with tempfile.TemporaryDirectory(prefix="mainframe-semgrep-security-") as directory:
        root = Path(directory)
        rules = root / "rules.json"
        source = root / f"source{extension}"
        rules.write_text(json.dumps(_SEMGREP_CONFIG), encoding="utf-8")
        source.write_text(text, encoding="utf-8")
        completed = subprocess.run(
            [
                executable,
                "scan",
                "--config",
                str(rules),
                "--oss-only",
                "--metrics",
                "off",
                "--disable-version-check",
                "--json",
                "--quiet",
                "--jobs",
                "1",
                "--timeout",
                "2",
                "--timeout-threshold",
                "1",
                "--max-memory",
                "256",
                "--max-target-bytes",
                str(MAX_FILE_BYTES),
                "--max-lines-per-finding",
                "1",
                "--max-chars-per-line",
                "120",
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=12,
            cwd=root,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError("Semgrep scan failed")
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("invalid Semgrep output") from error
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("results"), list)
        or raw.get("errors")
    ):
        raise RuntimeError("invalid Semgrep result")

    rows: list[Occurrence] = []
    for item in raw["results"]:
        if not isinstance(item, dict):
            raise RuntimeError("invalid Semgrep finding")
        raw_id = str(item.get("check_id") or "")
        marker = raw_id.find("mainframe.")
        rule_id = raw_id[marker:] if marker >= 0 else raw_id
        if rule_id not in _SEMGREP_LABELS:
            continue
        row = int((item.get("start") or {}).get("line") or 0)
        end_row = int((item.get("end") or {}).get("line") or row)
        rows.append(
            _occurrence(
                _SEMGREP_LABELS[rule_id],
                row,
                "scanner",
                _source_excerpt(text, row, end_row),
                channel=_SEMGREP_SECURITY_CHANNEL,
                blocking=False,
            )
        )
    return rows


def _scan_text(text: str, extension: str) -> list[Occurrence] | None:
    """Return findings, or None when code-only parsing is not trustworthy."""
    if not isinstance(text, str) or extension.lower() not in CODE_EXTENSIONS:
        return []
    extension = extension.lower()
    code = _code_only(text, extension)
    if code is None:
        return None
    findings: list[Occurrence] = []

    for start_line, value, kind in _extract_comments(text, extension):
        for label, pattern in _COMMENT_MARKERS:
            for match in pattern.finditer(value):
                line = _line_for(value, start_line, match.start())
                evidence = value.splitlines()[max(0, line - start_line)] if value.splitlines() else value
                findings.append(_occurrence(label, line, kind, evidence))

        process_match = _PROCESS_EPHEMERAL.search(value)
        if process_match is None and kind == "comment":
            process_match = _PROCESS_ORDINAL.search(value) or _PROCESS_DIVIDER.search(value)
        if process_match is not None:
            line = _line_for(value, start_line, process_match.start())
            evidence = value.splitlines()[max(0, line - start_line)] if value.splitlines() else value
            findings.append(_occurrence("temporary process comment", line, kind, evidence))

    for label, pattern, extensions in _CODE_MARKERS:
        if extension not in extensions:
            continue
        for match in pattern.finditer(code):
            line = 1 + text.count("\n", 0, match.start())
            evidence = match.group(0)
            findings.append(_occurrence(label, line, "code", evidence))

    for label, pattern, extensions in _DEBUG_MARKERS:
        if extension not in extensions:
            continue
        for match in pattern.finditer(code):
            line = 1 + text.count("\n", 0, match.start())
            evidence = match.group(0)
            findings.append(_occurrence(label, line, "code", evidence))

    return findings


def scan_text(text: str, extension: str) -> list[Occurrence]:
    """Return high-confidence findings without returning their source text."""
    return _scan_text(text, extension) or []


def _state_root(state_root: str | os.PathLike[str] | None) -> Path:
    return Path(state_root) if state_root is not None else Path(tempfile.gettempdir()) / "mainframe-code-quality"


def _require_identity(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _workspace(value: object) -> Path:
    if isinstance(value, os.PathLike):
        raw = os.fspath(value)
    else:
        raw = _require_identity(value, "workspace_root")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("workspace_root is required")
    path = Path(raw).expanduser().resolve()
    if not path.is_absolute():
        raise ValueError("workspace_root must be absolute")
    return path


def _state_path(
    scope_id: str,
    workspace_root: Path,
    state_namespace: str,
    state_root: str | os.PathLike[str] | None,
) -> Path:
    workspace_root = workspace_root.resolve()
    raw = f"{state_namespace}\0{scope_id}\0{workspace_root}".encode("utf-8", errors="replace")
    return _state_root(state_root) / f"{hashlib.sha256(raw).hexdigest()[:32]}.json"


def _empty_state() -> dict[str, object]:
    return {"version": 1, "pending": {}, "findings": {}, "notices": {}}


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        pass


@contextmanager
def _locked(path: Path):
    root = path.parent
    _ensure_private_directory(root)
    lock = Path(f"{path}.lock")
    for _ in range(LOCK_RETRIES):
        try:
            lock.mkdir(mode=0o700)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > LOCK_MAX_AGE_SECONDS:
                    lock.rmdir()
                    continue
            except FileNotFoundError:
                continue
            time.sleep(LOCK_RETRY_SECONDS)
    else:
        raise TimeoutError("temporary state lock is unavailable")
    try:
        yield
    finally:
        try:
            lock.rmdir()
        except FileNotFoundError:
            pass


def _load(path: Path) -> tuple[dict[str, object], bool]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ValueError("invalid state version")
        if not isinstance(value.get("pending"), dict) or not isinstance(value.get("findings"), dict):
            raise ValueError("invalid state shape")
        notices = value.setdefault("notices", {})
        if not isinstance(notices, dict):
            raise ValueError("invalid notice state")
        return value, False
    except FileNotFoundError:
        return _empty_state(), False
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return _empty_state(), True


def _save(path: Path, state: dict[str, object]) -> None:
    if not state.get("pending") and not state.get("findings") and not state.get("notices"):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    _ensure_private_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".quality-", dir=path.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, separators=(",", ":"), sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _cleanup_stale(root: Path) -> None:
    try:
        entries = list(root.iterdir())[:512]
    except FileNotFoundError:
        return
    now = time.time()
    for entry in entries:
        try:
            age = now - entry.stat().st_mtime
            if entry.is_dir() and entry.name.endswith(".lock") and age > LOCK_MAX_AGE_SECONDS:
                entry.rmdir()
            elif entry.is_file() and entry.suffix == ".json" and age > STATE_MAX_AGE_SECONDS:
                if Path(f"{entry}.lock").exists():
                    continue
                entry.unlink()
        except (FileNotFoundError, OSError):
            continue


def _operation_key(operation_id: str) -> str:
    return hashlib.sha256(operation_id.encode("utf-8", errors="replace")).hexdigest()[:24]


def _inside_workspace(path: Path, workspace: Path) -> bool:
    try:
        path.relative_to(workspace)
        return True
    except ValueError:
        return False


def _normalize_paths(
    paths: Iterable[str | os.PathLike[str]],
    workspace: Path,
) -> tuple[list[Path], bool]:
    result: list[Path] = []
    truncated = False
    for raw in paths:
        try:
            candidate = Path(raw).expanduser()
            candidate = (candidate if candidate.is_absolute() else workspace / candidate).resolve()
        except (OSError, TypeError, ValueError):
            continue
        if not _inside_workspace(candidate, workspace) or candidate.suffix.lower() not in CODE_EXTENSIONS:
            continue
        if candidate not in result:
            if len(result) >= MAX_FILES_PER_EDIT:
                truncated = True
                continue
            result.append(candidate)
    return result, truncated


def _read_source(path: Path, workspace: Path) -> str | None:
    try:
        resolved = path.resolve()
        if resolved != path or not _inside_workspace(resolved, workspace) or path.is_symlink():
            return None
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        text = ""
    except OSError:
        return None
    try:
        resolved_after = path.resolve()
        if (
            resolved_after != path
            or not _inside_workspace(resolved_after, workspace)
            or path.is_symlink()
        ):
            return None
    except OSError:
        return None
    return text


def _scan_source(
    text: str,
    extension: str,
    path: Path,
    *,
    include_advisory: bool,
) -> ScanResult:
    rows: list[Occurrence] = []
    channels: set[str] = set()
    issues: list[ScanIssue] = []

    marker_rows = _scan_text(text, extension)
    if marker_rows is None:
        issues.append(
            ScanIssue(
                f"parser:{extension}",
                f"Code marker parsing is unavailable for {extension} source.",
            )
        )
    else:
        rows.extend(marker_rows)
        channels.add("markers")

    if extension in _PYTHON_EXTENSIONS:
        try:
            rows.extend(_python_security_findings(text, path))
            channels.add(_PYTHON_SECURITY_CHANNEL)
        except Exception:
            issues.append(
                ScanIssue(
                    "scanner:python-security",
                    "Python security scanning is unavailable; Ruff safety rules were not checked.",
                )
            )

    if extension in _NODE_EXTENSIONS:
        try:
            rows.extend(_node_security_findings(text, extension))
            channels.add(_NODE_SECURITY_CHANNEL)
        except Exception:
            issues.append(
                ScanIssue(
                    "scanner:node-security",
                    "JavaScript security scanning is unavailable; Oxlint safety rules were not checked.",
                )
            )
        if include_advisory:
            try:
                rows.extend(_semgrep_security_findings(text, extension))
                channels.add(_SEMGREP_SECURITY_CHANNEL)
            except Exception:
                issues.append(
                    ScanIssue(
                        "scanner:semgrep-security",
                        "Semgrep security advice is unavailable for a candidate change.",
                    )
                )

    try:
        growth = _growth_metrics(text, extension)
    except Exception:
        growth = None
    revision = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return ScanResult(rows, frozenset(channels), tuple(issues), revision, growth)


def _read_scan(
    path: Path,
    workspace: Path,
    *,
    include_advisory: bool,
) -> ScanResult:
    text = _read_source(path, workspace)
    if text is None:
        return ScanResult(
            [],
            frozenset(),
            (
                ScanIssue(
                    "boundary:file-inspection",
                    "At least one changed file could not be inspected within the workspace boundary.",
                ),
            ),
            None,
        )
    return _scan_source(
        text,
        path.suffix.lower(),
        path,
        include_advisory=include_advisory,
    )


def _revision_matches(path: Path, workspace: Path, revision: str | None) -> bool:
    if revision is None:
        return False
    text = _read_source(path, workspace)
    if text is None:
        return False
    current = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return current == revision


def _serialize_counts(rows: list[Occurrence]) -> dict[str, dict[str, object]]:
    counts = Counter(row.fingerprint for row in rows)
    by_key = {row.fingerprint: row for row in rows}
    return {
        key: {
            "label": by_key[key].label,
            "count": count,
            "channel": by_key[key].channel,
            "blocking": by_key[key].blocking,
        }
        for key, count in counts.items()
    }


def _deserialize_counts(value: object) -> dict[str, tuple[str, int, str, bool]]:
    if not isinstance(value, dict):
        raise ValueError("invalid snapshot counts")
    result: dict[str, tuple[str, int, str, bool]] = {}
    for key, record in value.items():
        if not isinstance(key, str) or not isinstance(record, dict):
            raise ValueError("invalid snapshot finding")
        label = record.get("label")
        count = record.get("count")
        channel = record.get("channel", "markers")
        blocking = record.get("blocking", True)
        if (
            not isinstance(label, str)
            or not isinstance(count, int)
            or count < 0
            or not isinstance(channel, str)
            or not channel
            or not isinstance(blocking, bool)
        ):
            raise ValueError("invalid snapshot finding data")
        result[key] = (label, count, channel, blocking)
    return result


def _display_path(path: Path, workspace: Path) -> str:
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return path.name


def _unavailable(stage: str) -> QualityResult:
    return QualityResult(
        advisory=(
            f"Code-quality protection unavailable during {stage}; this is not "
            "evidence that the edit or completion is clean. Continue without a "
            "hook block and verify the changed code directly."
        )
    )


def _claim_issues(state: dict[str, object], issues: Iterable[ScanIssue]) -> list[str]:
    notices = state.get("notices")
    if not isinstance(notices, dict):
        raise ValueError("invalid notice state")
    claimed: list[str] = []
    for issue in issues:
        if issue.key in notices:
            continue
        notices[issue.key] = time.time()
        claimed.append(issue.message)
    return claimed


def _issue_advisory(messages: Iterable[str]) -> str | None:
    unique = list(dict.fromkeys(messages))
    if not unique:
        return None
    shown = unique[:MAX_MESSAGE_ROWS]
    body = "\n".join(f"  - {message}" for message in shown)
    if len(unique) > MAX_MESSAGE_ROWS:
        body += f"\n  - … {len(unique) - MAX_MESSAGE_ROWS} more unavailable checks"
    return (
        "Code-quality protection unavailable for part of this check:\n"
        + body
        + "\nThis is not evidence that the edit is clean. Continue without a "
        "hook block and verify the affected boundary directly."
    )


def _join_notes(*notes: str | None) -> str | None:
    return "\n".join(note for note in notes if note) or None


def _prune_pending(state: dict[str, object]) -> bool:
    pending = state.get("pending")
    if not isinstance(pending, dict):
        raise ValueError("invalid pending state")
    cutoff = time.time() - PENDING_MAX_AGE_SECONDS
    removed = False
    for key, value in list(pending.items()):
        created = value.get("created") if isinstance(value, dict) else None
        if not isinstance(created, (int, float)) or created < cutoff:
            del pending[key]
            removed = True
    return removed


def capture_before(
    scope_id: str,
    workspace_root: str | os.PathLike[str],
    operation_id: str,
    paths: Iterable[str | os.PathLike[str]],
    *,
    state_namespace: str = "mainframe",
    state_root: str | os.PathLike[str] | None = None,
) -> QualityResult:
    """Capture finding fingerprints immediately before one file-edit operation."""
    try:
        scope = _require_identity(scope_id, "scope_id")
        operation = _require_identity(operation_id, "operation_id")
        namespace = _require_identity(state_namespace, "state_namespace")
        workspace = _workspace(workspace_root)
        selected, truncated = _normalize_paths(paths, workspace)
        snapshots: dict[str, object] = {}
        issues: list[ScanIssue] = []
        if truncated:
            issues.append(
                ScanIssue(
                    "boundary:path-limit",
                    "The edit named more code paths than one bounded hook pass can inspect.",
                )
            )
        for selected_path in selected:
            scan = _read_scan(selected_path, workspace, include_advisory=True)
            issues.extend(scan.issues)
            snapshots[str(selected_path)] = {
                "available": scan.revision is not None,
                "channels": sorted(scan.channels),
                "counts": _serialize_counts(scan.rows),
                "growth": _serialize_growth(scan.growth),
            }

        path = _state_path(scope, workspace, namespace, state_root)
        with _locked(path):
            state, recovered = _load(path)
            _prune_pending(state)
            claimed = _claim_issues(state, issues)
            pending = state["pending"]
            assert isinstance(pending, dict)
            pending[_operation_key(operation)] = {
                "created": time.time(),
                "paths": snapshots,
            }
            _save(path, state)
        _cleanup_stale(path.parent)
        note = _issue_advisory(claimed)
        if recovered:
            note = _join_notes(note, _unavailable("before-edit capture").advisory)
        return QualityResult(advisory=note)
    except Exception:
        return _unavailable("before-edit capture")


def _active_records(state: dict[str, object]) -> dict[str, dict[str, dict[str, object]]]:
    findings = state.get("findings")
    if not isinstance(findings, dict):
        raise ValueError("invalid finding state")
    return findings


def _revalidate_path(
    active: dict[str, dict[str, dict[str, object]]],
    path: Path,
    scan: ScanResult,
) -> bool:
    records = active.get(str(path))
    if not records:
        return False
    counts = Counter(row.fingerprint for row in scan.rows)
    unavailable = False
    for fingerprint, record in list(records.items()):
        baseline = record.get("baseline") if isinstance(record, dict) else None
        channel = record.get("channel", "markers") if isinstance(record, dict) else None
        if not isinstance(channel, str) or channel not in scan.channels:
            unavailable = True
            continue
        if not isinstance(baseline, int) or counts.get(fingerprint, 0) <= baseline:
            del records[fingerprint]
    if not records:
        active.pop(str(path), None)
    return unavailable


def _advisory(rows: list[tuple[Path, Occurrence]], workspace: Path) -> str:
    locations = [f"{_display_path(path, workspace)}:{row.line} — {row.label}" for path, row in rows]
    body = "\n".join(f"  - {location}" for location in locations[:MAX_MESSAGE_ROWS])
    if len(locations) > MAX_MESSAGE_ROWS:
        body += f"\n  - … {len(locations) - MAX_MESSAGE_ROWS} more"
    return (
        "Code-quality check found newly introduced unfinished, suppressed, or "
        "high-confidence security-sensitive work:\n"
        + body
        + "\nResolve the underlying behavior and run relevant verification. Do "
        "not merely delete a marker or suppress a diagnostic that represents "
        "required work; route a truly unrelated observation through the "
        "project's issue workflow."
    )


def _review_advisory(rows: list[tuple[Path, Occurrence]], workspace: Path) -> str:
    locations = [f"{_display_path(path, workspace)}:{row.line} — {row.label}" for path, row in rows]
    body = "\n".join(f"  - {location}" for location in locations[:MAX_MESSAGE_ROWS])
    if len(locations) > MAX_MESSAGE_ROWS:
        body += f"\n  - … {len(locations) - MAX_MESSAGE_ROWS} more"
    return (
        "Security review advice for newly introduced code:\n"
        + body
        + "\nReview the affected trust boundary before continuing. These "
        "context-dependent findings are advisory and do not block completion."
    )


def _growth_advisory(rows: list[GrowthFinding], workspace: Path) -> str:
    locations: list[str] = []
    for row in rows:
        path = _display_path(row.path, workspace)
        if row.kind == "file":
            locations.append(
                f"file: {path} crossed {FILE_LENGTH_THRESHOLD} lines "
                f"({row.before} -> {row.after})"
            )
        else:
            locations.append(
                f"Python function: {path}:{row.line} `{row.name}` crossed "
                f"{PYTHON_FUNCTION_LENGTH_THRESHOLD} lines "
                f"({row.before} -> {row.after})"
            )
    body = "\n".join(f"  - {location}" for location in locations[:MAX_MESSAGE_ROWS])
    if len(locations) > MAX_MESSAGE_ROWS:
        body += f"\n  - … {len(locations) - MAX_MESSAGE_ROWS} more"
    return (
        "Code structure review for newly introduced growth:\n"
        + body
        + "\nCheck whether the affected responsibilities remain cohesive. A size "
        "threshold is review pressure, not a requirement to split coherent code."
    )


def record_after(
    scope_id: str,
    workspace_root: str | os.PathLike[str],
    operation_id: str,
    *,
    succeeded: bool = True,
    state_namespace: str = "mainframe",
    state_root: str | os.PathLike[str] | None = None,
) -> QualityResult:
    """Consume one pre-edit snapshot and record only newly introduced findings."""
    try:
        scope = _require_identity(scope_id, "scope_id")
        operation = _require_identity(operation_id, "operation_id")
        namespace = _require_identity(state_namespace, "state_namespace")
        workspace = _workspace(workspace_root)
        path = _state_path(scope, workspace, namespace, state_root)

        with _locked(path):
            state, recovered_before = _load(path)
            expired_before = _prune_pending(state)
            pending = state["pending"]
            assert isinstance(pending, dict)
            snapshot = pending.pop(_operation_key(operation), None)
            if not succeeded:
                _save(path, state)
                if recovered_before or expired_before:
                    return _unavailable("after-edit verification")
                return QualityResult()
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("paths"), dict):
                _save(path, state)
                return _unavailable("after-edit verification")
            _save(path, state)

        scanned: list[tuple[Path, dict[str, object], ScanResult]] = []
        issues: list[ScanIssue] = []
        for raw_path, before_record in snapshot["paths"].items():
            if not isinstance(raw_path, str) or not isinstance(before_record, dict):
                issues.append(
                    ScanIssue(
                        "boundary:snapshot",
                        "At least one before-edit snapshot had an invalid shape.",
                    )
                )
                continue
            file_path = Path(raw_path)
            if not _inside_workspace(file_path, workspace):
                issues.append(
                    ScanIssue(
                        "boundary:workspace",
                        "At least one changed path was outside the active workspace.",
                    )
                )
                continue
            scan = _read_scan(file_path, workspace, include_advisory=True)
            issues.extend(scan.issues)
            scanned.append((file_path, before_record, scan))

        new_rows: list[tuple[Path, Occurrence]] = []
        growth_rows: list[GrowthFinding] = []
        unavailable = False
        with _locked(path):
            state, recovered_after = _load(path)
            expired_after = _prune_pending(state)
            active = _active_records(state)
            for file_path, before_record, scan in scanned:
                if scan.revision is None or not _revision_matches(
                    file_path, workspace, scan.revision
                ):
                    issues.append(
                        ScanIssue(
                            "boundary:file-revision",
                            "A changed file moved again before its scan result could be attributed.",
                        )
                    )
                    unavailable = True
                    continue

                growth_rows.extend(
                    _growth_findings(file_path, before_record.get("growth"), scan.growth)
                )
                unavailable = _revalidate_path(active, file_path, scan) or unavailable
                raw_channels = before_record.get("channels", ["markers"])
                if not isinstance(raw_channels, list) or any(
                    not isinstance(channel, str) for channel in raw_channels
                ):
                    issues.append(
                        ScanIssue(
                            "boundary:snapshot-channels",
                            "At least one before-edit snapshot had invalid scanner metadata.",
                        )
                    )
                    unavailable = True
                    continue
                before_channels = set(raw_channels)
                common_channels = before_channels.intersection(scan.channels)
                if before_record.get("available") is not True:
                    common_channels.clear()

                before = _deserialize_counts(before_record.get("counts", {}))
                current_rows = [
                    row for row in scan.rows if row.channel in common_channels
                ]
                after_counts = Counter(row.fingerprint for row in current_rows)
                rows_by_fingerprint: dict[str, list[Occurrence]] = {}
                for row in current_rows:
                    rows_by_fingerprint.setdefault(row.fingerprint, []).append(row)
                records = active.setdefault(str(file_path), {})
                for fingerprint, current_count in after_counts.items():
                    representative = rows_by_fingerprint[fingerprint][0]
                    before_data = before.get(
                        fingerprint,
                        (
                            representative.label,
                            0,
                            representative.channel,
                            representative.blocking,
                        ),
                    )
                    label, before_count, before_channel, before_blocking = before_data
                    if before_channel != representative.channel:
                        before_count = 0
                    if current_count <= before_count or fingerprint in records:
                        continue
                    added_rows = rows_by_fingerprint[fingerprint][before_count:current_count]
                    new_rows.extend((file_path, row) for row in added_rows)
                    if representative.blocking and before_blocking:
                        records[fingerprint] = {
                            "label": label,
                            "baseline": before_count,
                            "channel": representative.channel,
                        }
                if not records:
                    active.pop(str(file_path), None)

            claimed = _claim_issues(state, issues)
            _save(path, state)

        _cleanup_stale(path.parent)
        blocking_rows = [item for item in new_rows if item[1].blocking]
        review_rows = [item for item in new_rows if not item[1].blocking]
        note = _join_notes(
            _advisory(blocking_rows, workspace) if blocking_rows else None,
            _review_advisory(review_rows, workspace) if review_rows else None,
            _growth_advisory(growth_rows, workspace) if growth_rows else None,
            _issue_advisory(claimed),
        )
        if recovered_before or recovered_after or expired_before or expired_after or unavailable:
            note = _join_notes(note, _unavailable("after-edit verification").advisory)
        return QualityResult(advisory=note)
    except Exception:
        return _unavailable("after-edit verification")


def _current_unresolved(
    active: dict[str, dict[str, dict[str, object]]],
    workspace: Path,
    scans: dict[str, ScanResult],
) -> tuple[list[tuple[Path, Occurrence]], list[ScanIssue]]:
    unresolved: list[tuple[Path, Occurrence]] = []
    issues: list[ScanIssue] = []
    for raw_path in list(active):
        path = Path(raw_path)
        if not _inside_workspace(path, workspace):
            active.pop(raw_path, None)
            issues.append(
                ScanIssue(
                    "boundary:stored-workspace",
                    "Stored finding state referenced a path outside the active workspace.",
                )
            )
            continue
        scan = scans.get(raw_path)
        if scan is None:
            issues.append(
                ScanIssue(
                    "boundary:late-finding",
                    "Finding state changed while completion verification was running.",
                )
            )
            continue
        if not _revision_matches(path, workspace, scan.revision):
            issues.append(
                ScanIssue(
                    "boundary:completion-revision",
                    "A tracked file changed while completion verification was running.",
                )
            )
            continue
        if _revalidate_path(active, path, scan):
            issues.append(
                ScanIssue(
                    "boundary:revalidation-channel",
                    "At least one attributed finding could not be revalidated by its scanner.",
                )
            )
        records = active.get(raw_path, {})
        counts = Counter(row.fingerprint for row in scan.rows)
        by_fingerprint: dict[str, list[Occurrence]] = {}
        for row in scan.rows:
            by_fingerprint.setdefault(row.fingerprint, []).append(row)
        for fingerprint, record in records.items():
            baseline = record.get("baseline") if isinstance(record, dict) else None
            channel = record.get("channel", "markers") if isinstance(record, dict) else None
            if not isinstance(channel, str) or channel not in scan.channels:
                continue
            if not isinstance(baseline, int) or baseline < 0:
                issues.append(
                    ScanIssue(
                        "boundary:finding-state",
                        "At least one attributed finding had invalid temporary state.",
                    )
                )
                continue
            unresolved.extend(
                (path, row)
                for row in by_fingerprint.get(fingerprint, [])[baseline:counts.get(fingerprint, 0)]
            )
    return unresolved, issues


def _block(rows: list[tuple[Path, Occurrence]], workspace: Path) -> str:
    locations = [f"{_display_path(path, workspace)}:{row.line} — {row.label}" for path, row in rows]
    body = "\n".join(f"  - {location}" for location in locations[:MAX_MESSAGE_ROWS])
    if len(locations) > MAX_MESSAGE_ROWS:
        body += f"\n  - … {len(locations) - MAX_MESSAGE_ROWS} more"
    count = len(rows)
    return (
        f"Completion blocked: {count} unfinished, suppressed, or security-sensitive code finding"
        f"{'s' if count != 1 else ''} introduced in this execution scope remain:\n"
        + body
        + "\nComplete or secure the underlying implementation and run relevant "
        "verification before stopping. Do not remove a marker or suppress a "
        "diagnostic when it represents required work."
    )


def check_completion(
    scope_id: str,
    workspace_root: str | os.PathLike[str],
    *,
    state_namespace: str = "mainframe",
    state_root: str | os.PathLike[str] | None = None,
) -> QualityResult:
    """Revalidate attributed findings and return a positive completion block."""
    try:
        scope = _require_identity(scope_id, "scope_id")
        namespace = _require_identity(state_namespace, "state_namespace")
        workspace = _workspace(workspace_root)
        path = _state_path(scope, workspace, namespace, state_root)
        with _locked(path):
            state, recovered_before = _load(path)
            expired_before = _prune_pending(state)
            pending = state.get("pending")
            incomplete_edits = bool(pending)
            if isinstance(pending, dict):
                pending.clear()
            active = _active_records(state)
            paths = list(active)
            _save(path, state)

        scans: dict[str, ScanResult] = {}
        issues: list[ScanIssue] = []
        for raw_path in paths:
            candidate = Path(raw_path)
            scan = _read_scan(candidate, workspace, include_advisory=False)
            scans[raw_path] = scan
            issues.extend(scan.issues)

        with _locked(path):
            state, recovered_after = _load(path)
            expired_after = _prune_pending(state)
            active = _active_records(state)
            rows, state_issues = _current_unresolved(active, workspace, scans)
            issues.extend(state_issues)
            claimed = _claim_issues(state, issues)
            _save(path, state)
        _cleanup_stale(path.parent)
        if rows:
            reason = _block(rows, workspace)
            issue_note = _issue_advisory(claimed)
            if issue_note:
                reason += "\n" + issue_note
            return QualityResult(block_reason=reason)
        note = _issue_advisory(claimed)
        if recovered_before or recovered_after or expired_before or expired_after or incomplete_edits:
            note = _join_notes(note, _unavailable("completion verification").advisory)
        return QualityResult(advisory=note)
    except Exception:
        return _unavailable("completion verification")


__all__ = [
    "CODE_EXTENSIONS",
    "Occurrence",
    "QualityResult",
    "capture_before",
    "check_completion",
    "record_after",
    "scan_text",
]

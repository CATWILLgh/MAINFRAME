#!/usr/bin/env python3
"""Track newly introduced code residue and prevent incomplete completion.

This is the canonical, product-neutral implementation of one logical hook
component with fixed advisory and guard effects:

* after an edit, it reports newly introduced high-confidence unfinished-code,
  suppression, disabled-test, debug, or security findings;
* a completion guard blocks only while an attributed blocking finding remains
  after re-reading and re-scanning the file;
* Ruff async and context-dependent Semgrep findings are review advice and
  never enter the completion guard;
* syntax errors and duplicate configuration keys are post-edit review advice;
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
from contextvars import ContextVar
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
import tokenize
import tomllib
from typing import Iterable, NamedTuple


MAX_FILE_BYTES = 2_000_000
MAX_FILES_PER_EDIT = 24
MAX_MESSAGE_ROWS = 6
MAX_ROW_CHARS = 240
MAX_ADVISORY_CHARS = 480
SCAN_BUDGET_SECONDS = 5
MAX_COMPLETED_OPERATIONS = 512
_SCAN_DEADLINE = ContextVar("mainframe_quality_deadline", default=None)
PENDING_MAX_AGE_SECONDS = 60 * 60
STATE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
LOCK_MAX_AGE_SECONDS = 60
LOCK_RETRIES = 100
LOCK_RETRY_SECONDS = 0.005

_TS_EXTENSIONS = frozenset({".ts", ".tsx", ".mts", ".cts"})
CODE_EXTENSIONS = _TS_EXTENSIONS | frozenset(
    {
        ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs",
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
    line: int | None
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

    @property
    def revalidation_channels(self) -> frozenset[str]:
        if any(row.channel == _SYNTAX_CHANNEL for row in self.rows):
            # Parser diagnostics can accompany a partial lint result. Keep the
            # before/after comparison, but require a complete parse to clear a
            # previously attributed security finding.
            return self.channels - {_PYTHON_SECURITY_CHANNEL, _NODE_SECURITY_CHANNEL}
        return self.channels


class SourceSnapshot(NamedTuple):
    text: str
    exists: bool

    @property
    def revision(self) -> str:
        if not self.exists:
            return "missing"
        return hashlib.sha256(self.text.encode("utf-8", errors="replace")).hexdigest()


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
    ".jsx": _profile(("//",), _C_BLOCK, backtick=True),
    **dict.fromkeys(_TS_EXTENSIONS, _profile(("//",), _C_BLOCK, backtick=True)),
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

_NODE_EXTENSIONS = _TS_EXTENSIONS | {".js", ".jsx", ".mjs", ".cjs"}
_JS_EXTENSIONS = _NODE_EXTENSIONS | {".vue", ".svelte"}
_WEB_EXTENSIONS = _JS_EXTENSIONS | {".css", ".html", ".htm"}
_WEB_MARKUP_EXTENSIONS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte"}
_WEB_STYLE_EXTENSIONS = {".css", ".html", ".htm", ".vue", ".svelte"}
_WEB_MAX_BYTES = 128_000
_WEB_MAX_LINE_CHARS = 2_000
_WEB_SCAN_BUDGET_SECONDS = 1
_WEB_CHANNEL = "modern-web-rules-v1"
_WEB_LABELS = {
    "ime-safe-enter-submit": "review text-entry composition guards; ignore buttons and links",
    "validate-input-after-interaction": "error styling can appear before interaction; preserve validation timing and browser support",
    "secure-external-subresources": "review integrity and CORS for external scripts or styles",
}
_WEB_IGNORED_DIRS = {"node_modules", "vendor", "third_party", "dist", "build", "coverage", ".next", "generated"}

# The adapted rule program is Apache-2.0; see LICENSES/Apache-2.0.txt.
_WEB_RULES_PROGRAM = r"""
// SPDX-License-Identifier: Apache-2.0
// Adapted from GoogleChrome modern-web-guidance 1.0.0 analyzing/rules (Apache-2.0):
// https://github.com/GoogleChrome/modern-web-guidance-src/tree/main/src/analyzing/rules
// MAINFRAME modifications: per-resource SRI, local same-event IME reachability,
// per-rule validation timing, and official-compiler Svelte template coverage.
// Evaluated by the managed launcher; all source parsing belongs to maintained parsers.
import { readFile, mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, join } from 'node:path';
import { pathToFileURL } from 'node:url';
const { runAnalyzeCli } = await import(pathToFileURL(process.argv[2]).href);
const args = process.argv.slice(4);
const guideIndex = args.indexOf('--guide');
const allows = id => guideIndex < 0 || args[guideIndex + 1] === id;
const kind = (n, name) => n?.getKindName() === name;
const unwrap = n => {
  while (n && ['ParenthesizedExpression', 'AsExpression', 'TypeAssertionExpression', 'NonNullExpression', 'SatisfiesExpression'].includes(n.getKindName())) n = n.getExpression();
  return n;
};
const descendants = (n, name) => n.getDescendants().filter(x => kind(x, name));
const literal = n => { n = unwrap(n); return n?.getLiteralValue?.(); };
function bindsName(pattern, name) {
  if (kind(pattern,'Identifier')) return pattern.getText() === name;
  return pattern?.getElements?.().some(e => bindsName(e.getNameNode?.(),name)) ?? false;
}
function resolve(n) {
  n = unwrap(n);
  if (!kind(n, 'Identifier')) return n;
  const name = n.getText();
  for (let p = n.getParent(); p; p = p.getParent()) {
    if (p.getParameters?.().some(param => bindsName(param.getNameNode(),name))) return null;
    if (!p.getStatements) continue;
    for (const stmt of p.getStatements()) {
      if (kind(stmt, 'FunctionDeclaration') && stmt.getName() === name) return stmt;
      for (const decl of stmt.getDeclarations?.() ?? []) if (decl.getName() === name) return unwrap(decl.getInitializer());
    }
  }
  return null;
}
const isFunction = n => n && ['ArrowFunction', 'FunctionExpression', 'FunctionDeclaration'].includes(n.getKindName());
const U = Symbol('unknown');
const canTrue = values => values.some(v => v === U || Boolean(v));
const canFalse = values => values.some(v => v === U || !v);
const pathOf = n => {
  n = unwrap(n);
  if (kind(n, 'Identifier')) return [n.getText()];
  if (kind(n, 'PropertyAccessExpression')) return [...pathOf(n.getExpression()), n.getName()];
  if (kind(n, 'ElementAccessExpression')) return [...pathOf(n.getExpression()), literal(n.getArgumentExpression())];
  return [];
};
let matcherUnavailable;
function unavailable(reason) {
  matcherUnavailable = new Error(`MAINFRAME web check unavailable: ${reason}`);
  throw matcherUnavailable;
}
// Only local if/return/short-circuit/switch paths are interpreted, never application code.
function reachableActions(fn, key) {
  const actions = new Map(), event = fn.getParameters?.()[0]?.getName();
  let budget = 4000;
  const spend = () => { if (--budget < 0) unavailable('handler exceeds 4000 AST evaluation steps'); };
  function expr(raw) {
    const n = unwrap(raw);
    if (!n) return [U];
    spend();
    if (kind(n, 'StringLiteral') || kind(n, 'NumericLiteral') || kind(n, 'NoSubstitutionTemplateLiteral')) return [literal(n)];
    if (kind(n, 'TrueKeyword')) return [true];
    if (kind(n, 'FalseKeyword')) return [false];
    if (kind(n, 'NullKeyword')) return [null];
    if (kind(n, 'PropertyAccessExpression') || kind(n, 'ElementAccessExpression')) {
      const p = pathOf(n);
      if (p[0] !== event || (p.length !== 2 && !(p.length === 3 && p[1] === 'nativeEvent'))) return [U];
      const field = p.at(-1);
      if (field === 'key' || field === 'code') return [key];
      if (field === 'isComposing') return [true];
      if (field === 'keyCode' || field === 'which') return [229];
      if (['ctrlKey', 'metaKey', 'altKey', 'shiftKey'].includes(field)) return [false];
      return [U];
    }
    if (kind(n, 'PrefixUnaryExpression') && n.getText().startsWith('!')) return expr(n.getOperand()).map(v => v === U ? U : !v);
    if (kind(n, 'BinaryExpression')) {
      const op = n.getOperatorToken().getText(), left = expr(n.getLeft());
      if (op === '&&') return [...(canFalse(left) ? [false] : []), ...(canTrue(left) ? expr(n.getRight()) : [])];
      if (op === '||') return [...(canTrue(left) ? [true] : []), ...(canFalse(left) ? expr(n.getRight()) : [])];
      const right = expr(n.getRight());
      if (['===', '==', '!==', '!='].includes(op)) return left.flatMap(a => right.map(b => a === U || b === U ? U : (op[0] === '!' ? a !== b : a === b)));
      return [U];
    }
    if (kind(n, 'ConditionalExpression')) {
      const c = expr(n.getCondition());
      return [...(canTrue(c) ? expr(n.getWhenTrue()) : []), ...(canFalse(c) ? expr(n.getWhenFalse()) : [])];
    }
    if (kind(n, 'CallExpression')) {
      for (const a of n.getArguments()) if (!isFunction(a)) expr(a);
      const p = pathOf(n.getExpression());
      if (!(p[0] === 'console' || (p[0] === event && ['preventDefault', 'stopPropagation', 'stopImmediatePropagation'].includes(p.at(-1))))) actions.set(n.getStart(), n);
      return [U];
    }
    if (kind(n, 'AwaitExpression') || kind(n, 'VoidExpression')) return expr(n.getExpression());
    return [U];
  }
  // Bit flags: 1 continues, 2 returns, 4 breaks out of a switch.
  function sequence(statements) {
    let state = 1;
    for (const s of statements) if (state & 1) state = (state & ~1) | stmt(s);
    return state;
  }
  function stmt(n) {
    if (!n) return 1;
    spend();
    if (kind(n, 'Block')) return sequence(n.getStatements());
    if (kind(n, 'ExpressionStatement')) { expr(n.getExpression()); return 1; }
    if (kind(n, 'ReturnStatement') || kind(n, 'ThrowStatement')) { expr(n.getExpression()); return 2; }
    if (kind(n, 'BreakStatement')) return 4;
    if (kind(n, 'IfStatement')) {
      const c = expr(n.getExpression());
      return (canTrue(c) ? stmt(n.getThenStatement()) : 0) | (canFalse(c) ? stmt(n.getElseStatement()) : 0);
    }
    if (kind(n, 'VariableStatement')) { for (const d of n.getDeclarations()) expr(d.getInitializer()); return 1; }
    if (kind(n, 'SwitchStatement')) {
      const values = expr(n.getExpression()), clauses = n.getCaseBlock().getClauses();
      let state = 0;
      for (const v of values) {
        const matched = clauses.findIndex(c => c.getExpression && literal(c.getExpression()) === v);
        const start = matched >= 0 ? matched : clauses.findIndex(c => kind(c, 'DefaultClause'));
        const indices = v === U ? clauses.map((_, i) => i) : [start];
        for (const i of indices) state |= i < 0 ? 1 : sequence(clauses.slice(i).flatMap(c => c.getStatements()));
      }
      return (state & 4 ? 1 : 0) | (state & ~4);
    }
    if (['ForStatement','ForInStatement','ForOfStatement','WhileStatement','DoStatement','TryStatement','WithStatement'].includes(n.getKindName()) && descendants(n,'CallExpression').some(c => c.getFirstAncestor(isFunction) === fn)) unavailable('executed loop/try control flow is outside local handler analysis');
    return 1;
  }
  const body = fn.getBody?.();
  if (kind(body, 'Block')) stmt(body); else expr(body);
  return actions;
}
function unsafeHandler(fn, enterOnly = false) {
  if (!isFunction(fn) || !fn.getBody?.()) return null;
  const event = fn.getParameters?.()[0]?.getName();
  const ownKey = n => { const p = pathOf(n); return p[0] === event && (p.length === 2 || (p.length === 3 && p[1] === 'nativeEvent')) && ['key','code'].includes(p.at(-1)); };
  function ownEnter(n) {
    return [n,...n.getDescendants()].some(x => {
      if (x.getFirstAncestor(isFunction) !== fn) return false;
      if (kind(x,'SwitchStatement')) return ownKey(x.getExpression()) && x.getCaseBlock().getClauses().some(c => c.getExpression && literal(c.getExpression()) === 'Enter');
      if (!kind(x,'BinaryExpression') || !['==','===','!=','!=='].includes(x.getOperatorToken().getText())) return false;
      return [[x.getLeft(),x.getRight()],[x.getRight(),x.getLeft()]].some(([a,b]) => ownKey(a) && literal(b) === 'Enter');
    });
  }
  if (!enterOnly && !ownEnter(fn.getBody())) return null;
  const enter = reachableActions(fn, 'Enter');
  const other = enterOnly ? new Map() : reachableActions(fn, '__mainframe_other_key__');
  function enterBranch(node) {
    for (let p = node.getParent(); p && p !== fn; p = p.getParent()) if (kind(p,'IfStatement') && ownEnter(p.getExpression())) return true;
    return false;
  }
  return [...enter].find(([site,node]) => !other.has(site) || enterBranch(node))?.[1] ?? null;
}
const nonTextRoles = /^(?:button|link|menuitem|tab|switch|checkbox|radio|option|listbox|treeitem)$/i;
function textElement(tag, attr) {
  if (['button', 'a', 'select', 'option'].includes(tag) || nonTextRoles.test(attr('role') ?? '')) return false;
  if (tag === 'textarea') return true;
  if (tag === 'input') return /^(?:text|search|email|url|tel|password|number)?$/i.test(attr('type') ?? '');
  return /^(?:true|plaintext-only)?$/i.test(attr('contenteditable') ?? '!') || attr('role') === 'textbox';
}
function textTarget(raw, seen = new Set()) {
  const n = unwrap(raw);
  if (!n || seen.has(n)) return false;
  seen.add(n);
  if (kind(n, 'Identifier')) return textTarget(resolve(n), seen);
  if (!kind(n, 'CallExpression')) return false;
  const p = pathOf(n.getExpression()), method = p.at(-1), value = literal(n.getArguments()[0]);
  if (typeof value !== 'string' || !['querySelector', 'createElement'].includes(method)) return false;
  if (method === 'createElement') return ['input', 'textarea'].includes(value.toLowerCase());
  if (value.includes(',')) return false;
  const subject = /(?:^|[\s>+~])((?:\[[^\]]*\]|[^\s>+~,])+)\s*$/.exec(value.trim())?.[1];
  if (!subject) return false;
  const tag = /^[a-z][\w-]*/i.exec(subject)?.[0].toLowerCase() ?? '';
  if (!['input','textarea'].includes(tag) && subject.includes('(')) return false;
  const attrs = new Map([...subject.matchAll(/\[\s*([\w-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\]\s]+)))?\s*\]/g)]
    .map(m => [m[1].toLowerCase(),m[2] ?? m[3] ?? m[4] ?? '']));
  if (['type','role'].some(name => new RegExp('\\[' + name + '\\b','i').test(subject) && !attrs.has(name))) return false;
  return textElement(tag, name => attrs.get(name) ?? null);
}
const imeMessage = 'Enter action on a text field can run during IME composition; guard the same event with isComposing before the action.';
function jsIme(sf) {
  const hits = [], record = (fn,site) => { if (unsafeHandler(resolve(fn))) hits.push({line:site.getStartLineNumber(), message:imeMessage}); };
  for (const call of descendants(sf, 'CallExpression')) {
    const access = unwrap(call.getExpression());
    if (!kind(access, 'PropertyAccessExpression') || access.getName() !== 'addEventListener' || literal(call.getArguments()[0]) !== 'keydown') continue;
    if (textTarget(access.getExpression())) record(call.getArguments()[1],call);
  }
  for (const attr of descendants(sf, 'JsxAttribute')) {
    if (!['onKeyDown', 'onkeydown'].includes(attr.getNameNode().getText())) continue;
    const el = attr.getFirstAncestor(n => kind(n,'JsxOpeningElement') || kind(n,'JsxSelfClosingElement')), attrs = el.getAttributes();
    const get = name => {
      const a = attrs.find(x => kind(x, 'JsxAttribute') && x.getNameNode().getText().toLowerCase() === name);
      const init = a?.getInitializer();
      return kind(init, 'JsxExpression') ? (literal(init.getExpression()) ?? (kind(init.getExpression(), 'TrueKeyword') ? 'true' : null)) : literal(init);
    };
    const dynamicType = attrs.some(a => kind(a,'JsxAttribute') && a.getNameNode().getText() === 'type') && get('type') === null;
    const tag = el.getTagNameNode().getText();
    if (tag === tag.toLowerCase() && !dynamicType && textElement(tag, get)) record(attr.getInitializer()?.getExpression?.(),attr);
  }
  for (const assignment of descendants(sf, 'BinaryExpression')) {
    const left = unwrap(assignment.getLeft());
    if (assignment.getOperatorToken().getText() === '=' && kind(left, 'PropertyAccessExpression') && left.getName() === 'onkeydown' && textTarget(left.getExpression())) record(assignment.getRight(),assignment);
  }
  return hits;
}
const meta = (id, hash, matcher) => {
  const guarded = {...matcher};
  for (const method of ['matchFile','matchElement','matchRule']) {
    const match = matcher[method];
    if (typeof match !== 'function') continue;
    guarded[method] = (...args) => {
      try { return match.apply(matcher,args); }
      catch (error) {
        matcherUnavailable ??= error instanceof Error ? error : new Error('web matcher failed');
        throw error;
      }
    };
  }
  return {id,guideId:id,guideHash:hash,summary:id,matcher:guarded,verifierRubric:{keepWhen:[],dropWhen:[]}};
};
const scripts = [];
let project, parsed = 0;
// Markup callbacks are synchronous. Reuse upstream script ASTs, acquiring its parser
// from one private seed only when a template has no script to supply a Project.
const target = args.find(a => !a.startsWith('-'));
const content = target ? await readFile(target, 'utf8') : '';
if (allows('ime-safe-enter-submit') && /\.(?:vue|svelte|html?)$/i.test(target ?? '') && /keydown/i.test(content)) {
  const collect = meta('mainframe-parser', '000000000000', {kind:'js',fastTokens:['function','const','let','var','=>'],matchFile(sf){project ??= sf.getProject();scripts.push(project.createSourceFile(`/__mainframe_script_${scripts.length}.ts`,sf.getFullText()));return [];}});
  await runAnalyzeCli([target, '--json'], {rules:[collect]});
  if (!project) {
    const dir = await mkdtemp(join(tmpdir(), 'mainframe-web-parser-'));
    try { const seed = join(dir,'seed.ts'); await writeFile(seed,'const seed = 0;',{mode:0o600}); await runAnalyzeCli([seed,'--json'],{rules:[collect]}); }
    finally { await rm(dir,{recursive:true,force:true}); }
  }
}
function templateHandler(raw, implicit) {
  const text = raw.trim().replace(/^\{([\s\S]*)\}$/, '$1').trim();
  const forwarding = /^([A-Za-z_$][\w$]*)\(\s*([A-Za-z_$][\w$]*)\s*\)$/.exec(text);
  const name = forwarding?.[2] === implicit ? forwarding[1] : text;
  if (/^[A-Za-z_$][\w$]*$/.test(name)) {
    for (const sf of scripts) {
      for (const n of sf.getStatements()) {
        if (kind(n,'FunctionDeclaration') && n.getName() === name) return n;
        const d = n.getDeclarations?.().find(d => d.getName() === name);
        if (d) return resolve(d.getInitializer());
      }
    }
    return null;
  }
  if (!project) return null;
  const sf = project.createSourceFile(`/__mainframe_handler_${parsed++}.ts`, `const handler = (${text});`);
  let fn = unwrap(sf.getStatements()[0]?.getDeclarations?.()[0]?.getInitializer());
  if (!isFunction(fn)) { project.removeSourceFile(sf); return project.createSourceFile(`/__mainframe_handler_${parsed++}.ts`, `const handler = (${implicit}) => {${text}\n};`).getStatements()[0].getDeclarations()[0].getInitializer(); }
  return fn;
}
const imeDom = meta('ime-safe-enter-submit','99e3b42fb16a',{kind:'dom',selector:'*',fastTokens:['<'],matchElement(el,ctx){
  if (/\.svelte$/i.test(ctx.filePath) || el.isJsx || el.hasDynamicAttribute?.('type') || !textElement(el.tagName, n => el.getAttribute(n))) return null;
  for (const [name, raw] of Object.entries(el.attributes)) {
    if (!/^(?:@keydown|v-on:keydown|on:keydown|onkeydown)(?:[.|]|$)/i.test(name) || /[.|](?:ctrl|meta|alt|shift)\b/i.test(name)) continue;
    const fn = templateHandler(raw, name.startsWith('@') || name.startsWith('v-on:') ? '$event' : 'event');
    if (unsafeHandler(fn, /\.enter\b/i.test(name))) return {message:imeMessage};
  }
  return null;
}});
function secureResource(el) {
  if (!['script','link'].includes(el.tagName) || (el.tagName === 'link' && el.getAttribute('rel')?.trim().toLowerCase() !== 'stylesheet')) return null;
  const url = el.getAttribute(el.tagName === 'script' ? 'src' : 'href')?.trim() ?? '';
  if (el.hasSpreadAttribute || el.hasAttribute('importance') || ['importance','integrity','crossorigin','crossOrigin','src','href'].some(a => el.hasDynamicAttribute?.(a))) return null;
  if (el.hasAttribute('integrity')) return !el.hasAttribute('crossorigin') && !el.hasAttribute('crossOrigin') && /\bsha(?:256|384|512)-[A-Za-z0-9+/=]+/.test(el.getAttribute('integrity') ?? '') && /^https:\/\//i.test(url) ? {message:'External integrity-protected resource needs crossorigin for browser SRI verification.'} : null;
  if (!/^https:\/\/(?:cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|unpkg\.com|code\.jquery\.com|maxcdn\.bootstrapcdn\.com|stackpath\.bootstrapcdn\.com|ajax\.googleapis\.com)\//i.test(url) || /\/combine\/|@(?:latest|next|main|master)\b|[?#{}<>]|<%|\$\{/i.test(url) || !/(?:\/|@|-)v?\d+\.\d+\.\d+(?:-[0-9a-zA-Z.-]+)?(?:\/|\.|-)/.test(url)) return null;
  return (el.tagName === 'script' ? /\.(?:js|mjs)$/i : /\.css$/i).test(url) ? {message:'Immutable public CDN resource needs Subresource Integrity and crossorigin.'} : null;
}
const sri = meta('secure-external-subresources','dfe6b556317c',{kind:'dom',selector:'script[src], link[rel="stylesheet"][href]',fastTokens:['<'],skipIfHasSpread:true,skipIfDynamicAttributes:['integrity','crossorigin','crossOrigin','src','href'],matchElement:(el,ctx) => /\.svelte$/i.test(ctx.filePath) ? null : secureResource(el)});
const visual = /^(?:border(?:-(?:color|top|right|bottom|left)(?:-color)?)?|background(?:-color|-image)?|color|(?:-(?:webkit|moz)-)?box-shadow|outline(?:-color)?)$/;
const reset = /^(?:none|0(?:px)?|transparent|currentcolor|inherit|initial|unset|revert|normal|auto)$/;
const css = meta('validate-input-after-interaction','039f2593da67',{kind:'css',fastTokens:[':'],matchRule(rule){
  if (/@supports\s+not\s+selector\(\s*:user-invalid\s*\)/i.test(rule.parentAtRule ?? '')) return null;
  const selectors = rule.selectorText.split(',');
  const stateBase = s => s.replace(/:(?:valid|invalid)\b/gi,'').trim().replace(/\s+/g,' ');
  const valid = new Set(selectors.filter(s => /:valid\b/i.test(s)).map(stateBase));
  for (const raw of selectors) {
    if (valid.has(stateBase(raw))) continue;
    if (/:user-invalid\b|(?:::|:-)(?:webkit-input-|moz-|ms-input-)?placeholder\b|\.(?:was-validated|is-validated|validated|touched|is-touched|ng-touched|dirty|is-dirty|ng-dirty|interacted|submitted|submission-attempted)\b|\bform\.invalid\b|\[data-(?:touched|dirty|interacted|validated)\b/i.test(raw)) continue;
    const s = raw.replace(/:not\([^)]*\)/gi,'');
    if (!/(?:^|[\s>+~])(?:input|textarea)(?:[.#][\w-]+|\[[^\]]*\]|:[\w-]+)*:invalid\b/i.test(s)) continue;
    if (!rule.declarations.some(d => (visual.test(d.property.toLowerCase()) || (/:invalid\b[^,]*[+~]/.test(s) && /^(?:display|visibility|opacity)$/.test(d.property))) && !reset.test(d.value.replace(/\s*!important\s*$/i,'').trim().toLowerCase()))) continue;
    return {message:'Apply text-field error styling after interaction using :user-invalid or an explicit touched/validated gate.'};
  }
  return null;
}});
const rules = [meta('ime-safe-enter-submit','99e3b42fb16a',{kind:'js',fastTokens:['keydown','onKeyDown'],matchFile:jsIme}),imeDom,sri,css];
const svelteHits = [];
if (/\.svelte$/i.test(target ?? '') && ((allows('ime-safe-enter-submit') && /keydown/i.test(content)) || (allows('secure-external-subresources') && /<(?:script|link)\b/i.test(content)))) {
  const imported = await import(pathToFileURL(process.argv[3]).href);
  const ast = (imported.default ?? imported).parse(content,{modern:true});
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'RegularElement' || node.type === 'Script') {
      const tag = node.type === 'Script' ? 'script' : node.name.toLowerCase();
      const attrs = node.attributes;
      const attribute = name => attrs.find(a => a.type === 'Attribute' && a.name.toLowerCase() === name.toLowerCase());
      const get = name => {
        const a = attribute(name);
        if (a?.value === true) return '';
        const values = Array.isArray(a?.value) ? a.value : a?.value ? [a.value] : [];
        if (values.length === 1 && values[0].type === 'ExpressionTag' && values[0].expression.type === 'Literal') return String(values[0].expression.value);
        return values.length && values.every(v => v.type === 'Text') ? values.map(v => v.data).join('') : null;
      };
      const dynamicType = Boolean(attribute('type')) && get('type') === null;
      const hit = (guideId, offset, message) => {
        const line = content.slice(0,offset).split('\n').length;
        svelteHits.push({guideId,finding:{file:basename(target),line,message,lineContent:content.split('\n')[line-1].trim()}});
      };
      if (allows('secure-external-subresources')) {
        const match = secureResource({tagName:tag,getAttribute:get,hasAttribute:name=>Boolean(attribute(name)),hasSpreadAttribute:attrs.some(a=>a.type === 'SpreadAttribute'),hasDynamicAttribute:name=>Boolean(attribute(name)) && get(name) === null});
        if (match) hit('secure-external-subresources',node.start,match.message);
      }
      if (allows('ime-safe-enter-submit') && !dynamicType && !attrs.some(a => a.type === 'SpreadAttribute') && textElement(tag,get)) {
        for (const a of attrs) {
          const expression = a.type === 'OnDirective' && a.name === 'keydown' ? a.expression : a.type === 'Attribute' && a.name === 'onkeydown' ? (Array.isArray(a.value) ? a.value[0]?.expression : a.value?.expression) : null;
          if (!expression || !['Identifier','ArrowFunctionExpression','FunctionExpression'].includes(expression.type)) continue;
          const fn = templateHandler(content.slice(expression.start,expression.end),'event');
          if (unsafeHandler(fn)) hit('ime-safe-enter-submit',a.start,imeMessage);
        }
      }
    }
    for (const [key,value] of Object.entries(node)) {
      if (['loc','expression','attributes','instance','module','css','content'].includes(key)) continue;
      if (Array.isArray(value)) value.forEach(visit); else if (value && typeof value === 'object') visit(value);
    }
  }
  visit(ast.fragment);
  visit(ast.instance);visit(ast.module);
}
const result = await runAnalyzeCli(args,{rules});
// Upstream catches matcher exceptions per file; preserve bounded-unavailable
// failures instead of allowing its empty result to appear successfully clean.
if (matcherUnavailable) throw matcherUnavailable;
// The upstream markup scanner drops brace-arrow Svelte attributes. Merge only
// official-compiler DOM matches into its unchanged public wire schema.
if (result.data && svelteHits.length) {
  for (const {guideId,finding} of svelteHits) {
    let guide = result.data.guides.find(g => g.guideId === guideId);
    if (!guide) { guide = {guideId,retrieveCommand:`npx modern-web-guidance retrieve ${guideId}`,count:0,rules:[]}; result.data.guides.push(guide); }
    let rule = guide.rules.find(r => r.ruleId === guideId);
    if (!rule) { rule = {ruleId:guideId,summary:guideId,verifierRubric:{keepWhen:[],dropWhen:[]},count:0,findings:[]};guide.rules.push(rule); }
    rule.findings.push(finding);rule.count = rule.findings.length;
    guide.count = guide.rules.reduce((n,r) => n + r.findings.length,0);
  }
  result.data.totalFindings = result.data.guides.reduce((n,g) => n + g.count,0);
  result.output = JSON.stringify(result.data,null,2) + '\n';
}
process.stdout.write(result.output);
process.exitCode = result.exitCode;
"""
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
        re.compile(r"(?m)^[ \t]*@(?:pytest\.mark\.skip|unittest\.skip)\b"),
        {".py", ".pyi"},
    ),
)

_DEBUG_MARKERS = (
    ("debugger statement", re.compile(r"(?m)^[ \t]*debugger[ \t]*(?:;[ \t]*)?$"), _JS_EXTENSIONS),
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
    line: int | None,
    kind: str,
    evidence: str,
    *,
    channel: str = "markers",
    blocking: bool = True,
) -> Occurrence:
    fingerprint = _fingerprint(label, f"{channel}:{kind}", evidence)
    return Occurrence(label, max(1, line) if line is not None else None, fingerprint, channel, blocking)


FILE_LENGTH_THRESHOLD = 400
PYTHON_FUNCTION_LENGTH_THRESHOLD = 60
_FILE_GROWTH_EXTENSIONS = CODE_EXTENSIONS - {".sql"}
_PYTHON_SECURITY_CHANNEL = "python-security"
_PYTHON_ASYNC_CHANNEL = "python-async-advice"
_PYTHON_ERROR_CHANNEL = "python-error-advice"
_PYTHON_CORRECTNESS_CHANNEL = "python-correctness-advice"
_NODE_SECURITY_CHANNEL = "node-security"
_NODE_CORRECTNESS_CHANNEL = "node-correctness-advice"
_NODE_TEST_CHANNEL = "node-test-advice"
_SEMGREP_SECURITY_CHANNEL = "semgrep-security-advice"
_SEMGREP_GO_CHANNEL = "semgrep-go-advice"
_SYNTAX_CHANNEL = "syntax"
_DUPLICATE_KEY_CHANNEL = "duplicate-key"
_WORKFLOW_DIRECTORY = (".github", "workflows")
_YAML_EXTENSIONS = {".yaml", ".yml"}
_JSON_EXTENSIONS = {".json", ".jsonc"}
_CONFIG_EXTENSIONS = _YAML_EXTENSIONS | _JSON_EXTENSIONS | {".toml"}
_EDIT_EXTENSIONS = CODE_EXTENSIONS | _CONFIG_EXTENSIONS | _WEB_EXTENSIONS
_SDK_SYNTAX_TOOLS = {
    ".go": ("Go", "gofmt"),
    ".dart": ("Dart", "dart"),
    ".rs": ("Rust", "rustfmt"),
}
_RUST_EDITIONS = ("2015", "2018", "2021", "2024")
_SHELL_EXTENSIONS = {".sh", ".bash"}
_SHELLCHECK_LABELS = {
    1072: "shell parser could not read this statement",
    1073: "shell parser could not read this construct",
    2155: "a declaration can mask the command's failed exit status",
    2164: "a failed cd can leave subsequent commands in the wrong directory",
    2094: "this pipeline reads and overwrites the same file",
}
# These diagnostics are intrinsic to the workflow and do not need repository
# metadata for local actions, reusable workflows, or self-hosted runners.
_ACTIONLINT_LABELS = {
    "syntax-check": "invalid workflow YAML or schema",
    "job-needs": "job dependency is missing or cyclic",
    "matrix": "invalid job matrix",
    "expression": "invalid workflow expression",
    "if-cond": "invalid condition",
    "id": "invalid or duplicate identifier",
}
_KUBE_LABELS = {
    "mismatching-selector": "workload selector does not match pod labels",
    "no-readiness-probe": "container has no readiness probe",
}
_KUBE_WORKLOAD = re.compile(
    r"(?m)^kind:[ \t]*['\"]?(?:Deployment|StatefulSet|DaemonSet)['\"]?[ \t]*(?:#.*)?$"
)
_KUBE_API = re.compile(r"(?m)^apiVersion:[ \t]*['\"]?apps/v1['\"]?[ \t]*(?:#.*)?$")
_KUBE_CONTAINER = re.compile(r"(?m)^[ \t]+containers[ \t]*:")
_SQUAWK_LABELS = {
    "ban-drop-table": "dropping a table can remove data and break existing clients",
    "ban-drop-column": "dropping a column can remove data and break existing clients",
    "ban-drop-schema": "dropping a schema can remove objects used by existing clients",
    "ban-drop-database": "dropping a database removes its data",
    "ban-truncate-cascade": "TRUNCATE CASCADE can erase related tables",
    "changing-column-type": "changing a column type can block access while rewriting the table",
    "ban-concurrent-index-creation-in-transaction": "a concurrent index operation cannot run inside an explicit transaction",
    "require-concurrent-index-creation": "ordinary index creation can block writes on a live table; review CONCURRENTLY and runner transaction mode",
    "require-concurrent-index-deletion": "ordinary index deletion can block table access; review online removal and constraint dependencies",
    "require-concurrent-reindex": "ordinary REINDEX can block table access; check target/version, constraints and runner before using CONCURRENTLY",
    "identifier-too-long": "SQL identifier exceeds the default 63-byte limit; truncation can cause name collisions",
    "syntax-error": "Squawk parser could not parse this statement; check syntax and analyzer/server version support",
    "constraint-missing-not-valid": "immediate constraint validation can block writes during a table scan; separate the short add from later validation",
    "disallowed-unique-constraint": "adding uniqueness can build an index while blocking writes; review concurrent index creation followed by constraint attachment",
    "adding-not-nullable-field": "SET NOT NULL can scan existing rows; verify prior constraint validation and bounded lock acquisition",
    "adding-required-field": "a required column without a default can reject existing rows; use a compatible staged addition and backfill",
    "adding-field-with-default": "this column default can rewrite existing rows; verify volatility, server version, and a staged backfill",
    "renaming-column": "renaming a column can break active readers and writers during a rolling deployment",
    "renaming-table": "renaming a table can break active readers and writers during a rolling deployment",
    "require-lock-timeout": "a finite lock_timeout is not declared before this DDL; verify the migration runner's connection setting or declare a scoped timeout",
}
_PYTHON_EXTENSIONS = {".py", ".pyi"}
_RUFF_SECURITY_LABELS = {
    "S102": "Python security S102: dynamic exec()",
    "S307": "Python security S307: dynamic eval()",
    "S506": "Python security S506: unsafe YAML loading",
    "S602": "Python security S602: subprocess shell execution",
    "S605": "Python security S605: shell process execution",
    "S501": "Python security S501: TLS verification disabled",
    "S324": "Python security S324: weak cryptographic hash",
}
_RUFF_ASYNC_LABELS = {
    "ASYNC210": "Python ASYNC210: blocking HTTP call in async function",
    "ASYNC212": "Python ASYNC212: synchronous HTTPX call in async function",
    "ASYNC221": "Python ASYNC221: blocking process call in async function",
    "ASYNC230": "Python ASYNC230: blocking open() in async function",
    "ASYNC251": "Python ASYNC251: blocking time.sleep() in async function",
}
_RUFF_ERROR_LABELS = {
    "S110": "Python S110: exception silently discarded by except ... pass",
    "B012": "Python B012: control flow in finally can suppress an exception",
}
_RUFF_CORRECTNESS_LABELS = {
    "F631": "Python F631: an assert on a non-empty tuple always passes",
    "PT012": "Python PT012: an earlier statement in pytest.raises can make the test pass",
    "RUF006": "Python RUF006: the background task may be collected before it finishes",
}
_RUFF_SHELL_RULES = {"S602", "S605"}
_OXLINT_SECURITY_LABELS = {
    "no-eval": "JavaScript security: eval()",
    "no-new-func": "JavaScript security: dynamic Function()",
    "no-script-url": "JavaScript security: javascript URL",
    "no-implied-eval": "JavaScript security: implicit string evaluation",
}
_OXLINT_CORRECTNESS_LABELS = {
    "no-unsafe-finally": (
        "JavaScript no-unsafe-finally: control flow in finally can suppress an exception"
    ),
    "no-async-promise-executor": (
        "JavaScript no-async-promise-executor: an async executor rejection can leave the Promise pending"
    ),
}
_OXLINT_ASYNC_ASSERTION_LABEL = (
    "JavaScript valid-expect: the test discards an async assertion; await or return it"
)
_JS_CALL_END = re.compile(rb"(?!(?:if|for|while|with|switch|catch)\()[\w.$]+\([^\r\n]*\)")
_JS_ASYNC_ASSERTION_END = re.compile(rb"\s*(?:[;}]|\Z)")
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
_PGXPOOL_IMPORT = '"github.com/jackc/pgx/v5/pgxpool"'
_PGXPOOL_DISCARD = re.compile(r"\b_\s*(?:,|=[^=])")
_PGXPOOL_CALL = re.compile(r"\.\s*(?:Query|Acquire)\s*\(")
_PGXPOOL_HINTS = {
    "Query": "discarded rows can hold a connection; close them or use Exec when no rows are needed",
    "Acquire": "discarded connection cannot be released; retain it and call Release",
}
_PGXPOOL_LABELS = {
    f"mainframe.go.pgxpool-{method.lower()}": f"Go pgxpool.{method}: {hint}"
    for method, hint in _PGXPOOL_HINTS.items()
}
_PGXPOOL_RULES = {
    "rules": [
        {
            "id": f"mainframe.go.pgxpool-{method.lower()}",
            "languages": ["go"],
            "message": hint,
            "severity": "WARNING",
            "patterns": [
                {"pattern-either": [
                    {"pattern": f"_, $ERR = $POOL.{method}(...)"},
                    {"pattern": f"$RESOURCE, $ERR := $POOL.{method}(...)\n_ = $RESOURCE\nreturn $ERR"},
                    {"pattern": (
                        f"$RESOURCE, $ERR := $POOL.{method}(...)\n"
                        "if $ERR != nil { return $ERR }\n_ = $RESOURCE\nreturn nil"
                    )},
                ]},
                {"metavariable-type": {"metavariable": "$POOL", "type": "*pgxpool.Pool"}},
            ],
        }
        for method, hint in _PGXPOOL_HINTS.items()
    ],
}


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


def _run_scanner(command, **options):
    deadline = _SCAN_DEADLINE.get()
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("code-quality scan budget exhausted")
        options["timeout"] = min(options["timeout"], remaining)
    return subprocess.run(command, **options)


def _syntax_finding(language: str, line: int, message: str, text: str) -> Occurrence:
    return _occurrence(
        f"{language} syntax error", line, "parser",
        message + "\n" + _source_excerpt(text, line, line),
        channel=_SYNTAX_CHANNEL, blocking=False,
    )


def _python_findings(text: str, path: Path, *, include_advisory: bool = True) -> list[Occurrence]:
    if not text:
        return []
    executable = shutil.which("ruff")
    if executable is None:
        raise RuntimeError("ruff unavailable")
    labels = _RUFF_SECURITY_LABELS
    if include_advisory:
        labels = labels | _RUFF_ASYNC_LABELS | _RUFF_ERROR_LABELS | _RUFF_CORRECTNESS_LABELS
    completed = _run_scanner(
        [
            executable,
            "check",
            "--isolated",
            "--select",
            ",".join(labels),
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
        if code == "invalid-syntax":
            line = int(item["location"]["row"])
            rows.append(_syntax_finding("Python", line, item["message"], text))
            continue
        if code not in labels:
            continue
        message = str(item.get("message") or "")
        if code in _RUFF_SHELL_RULES and "seems safe" in message:
            continue
        row = int((item.get("location") or {}).get("row") or 0)
        end_row = int((item.get("end_location") or {}).get("row") or row)
        security = code in _RUFF_SECURITY_LABELS
        if security:
            channel = _PYTHON_SECURITY_CHANNEL
        elif code in _RUFF_ASYNC_LABELS:
            channel = _PYTHON_ASYNC_CHANNEL
        elif code in _RUFF_ERROR_LABELS:
            channel = _PYTHON_ERROR_CHANNEL
        else:
            channel = _PYTHON_CORRECTNESS_CHANNEL
        rows.append(
            _occurrence(
                labels[code],
                row,
                "scanner",
                _source_excerpt(text, row, end_row),
                channel=channel,
                blocking=security,
            )
        )
    return rows


def _normalized_oxlint_code(value: object) -> str:
    code = str(value or "")
    if "(" in code and code.endswith(")"):
        code = code.split("(", 1)[1][:-1]
    return code


def _js_test_file(path: Path) -> bool:
    return path.stem.endswith((".test", ".spec")) or "__tests__" in path.parts


def _discarded_async_assertion(item: dict, span: dict, source: bytes) -> bool:
    if item.get("message") != "Async assertions must be awaited.":
        return False
    start, length = span.get("offset"), span.get("length")
    if not isinstance(start, int) or not isinstance(length, int):
        return False
    end = start + length
    if not 0 <= start < end <= len(source):
        return False
    # The pinned rule also flags valid awaits through parentheses or a variable.
    # Require an unambiguous statement boundary on both sides of its byte span.
    prefix = source[:start]
    before = prefix.rstrip()
    if before.endswith(b"{"):
        # JSX and template interpolations also start with a brace.
        at_boundary = before[:-1].rstrip().endswith((b")", b"=>"))
    elif before.endswith(b")") and b"\n" in prefix[len(before):]:
        # A completed call on the preceding line can omit its semicolon.
        previous_line = before.rsplit(b"\n", 1)[-1].strip()
        at_boundary = _JS_CALL_END.fullmatch(previous_line) is not None
    else:
        at_boundary = not before or before.endswith(b";")
    if not at_boundary:
        return False
    return _JS_ASYNC_ASSERTION_END.match(source, end) is not None


def _node_findings(text: str, path: Path, *, include_advisory: bool = True) -> list[Occurrence]:
    if not text:
        return []
    executable = shutil.which("oxlint")
    if executable is None:
        raise RuntimeError("oxlint unavailable")
    labels = _OXLINT_SECURITY_LABELS
    if include_advisory:
        labels = labels | _OXLINT_CORRECTNESS_LABELS
    check_tests = include_advisory and _js_test_file(path)
    with tempfile.TemporaryDirectory(prefix="mainframe-node-quality-") as directory:
        root = Path(directory)
        config = root / "oxlint.json"
        source = root / f"source{path.suffix.lower()}"
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
        for rule in labels:
            command.extend(["-D", rule])
        if check_tests:
            command.extend(["--vitest-plugin", "-D", "vitest/valid-expect"])
        command.append(str(source))
        completed = _run_scanner(
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
    source_bytes = text.encode("utf-8") if check_tests else b""
    for item in raw["diagnostics"]:
        code = _normalized_oxlint_code(item.get("code"))
        parser_error = not code and item.get("severity") == "error"
        if not (parser_error or code in labels or (check_tests and code == "valid-expect")):
            continue
        diagnostic_labels = item.get("labels") or []
        span = (
            diagnostic_labels[0].get("span", {})
            if diagnostic_labels and isinstance(diagnostic_labels[0], dict)
            else {}
        )
        row = int(span.get("line") or 0)
        if parser_error:
            language = "TypeScript" if path.suffix.lower() in _TS_EXTENSIONS else "JavaScript"
            rows.append(_syntax_finding(language, row, item["message"], text))
            continue
        end_row = int(span.get("line_end") or row)
        security = code in _OXLINT_SECURITY_LABELS
        if code == "valid-expect":
            if not _discarded_async_assertion(item, span, source_bytes):
                continue
            label = _OXLINT_ASYNC_ASSERTION_LABEL
            channel = _NODE_TEST_CHANNEL
        else:
            label = labels[code]
            channel = _NODE_SECURITY_CHANNEL if security else _NODE_CORRECTNESS_CHANNEL
        rows.append(
            _occurrence(
                label,
                row,
                "scanner",
                _source_excerpt(text, row, end_row),
                channel=channel,
                blocking=security,
            )
        )
    return rows


def _run_review_command(tool: str, args: list[str], text: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(tool)
    if executable is None:
        raise RuntimeError(f"{tool} unavailable")
    environment = {**os.environ}
    environment.pop("SHELLCHECK_OPTS", None)
    with tempfile.TemporaryDirectory(prefix=f"mainframe-{tool}-") as root:
        completed = _run_scanner(
            [executable, *args], input=text, capture_output=True, encoding="utf-8",
            cwd=root, env=environment, timeout=1, check=False,
        )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"{tool} execution failed")
    return completed


def _run_review_tool(tool: str, args: list[str], text: str) -> object:
    return json.loads(_run_review_command(tool, args, text).stdout)


def _modern_web_findings(text: str, path: Path, workspace: Path) -> list[Occurrence]:
    extension = path.suffix.lower()
    if extension not in _WEB_EXTENSIONS or not text:
        return []
    relative = path.relative_to(workspace)
    if (set(relative.parts[:-1]) & _WEB_IGNORED_DIRS
            or re.search(r"\.(?:min|bundle|generated)\.", path.name)
            or _js_test_file(path)):
        return []
    lower = text.lower()
    guides = []
    if (extension in _JS_EXTENSIONS | _WEB_MARKUP_EXTENSIONS
            and "keydown" in lower and ("Enter" in text or (
                extension == ".vue" and re.search(r"(?:@|v-on:)keydown(?:\.[\w-]+)*\.enter\b", lower)
            ))):
        guides.append("ime-safe-enter-submit")
    style_candidate = extension in _WEB_STYLE_EXTENSIONS or (
        extension in _NODE_EXTENSIONS and re.search(r"\bcss\s*`", text)
    )
    if style_candidate and ":invalid" in lower and ("input" in lower or "textarea" in lower):
        guides.append("validate-input-after-interaction")
    if extension in _WEB_MARKUP_EXTENSIONS and "https://" in lower and re.search(r"<(?:script|link)\b", lower):
        guides.append("secure-external-subresources")
    if not guides:
        return []
    if len(text.encode("utf-8")) > _WEB_MAX_BYTES or any(len(line) > _WEB_MAX_LINE_CHARS for line in text.splitlines()):
        raise ValueError("web snapshot exceeds the bounded parser input")
    executable = shutil.which("modern-web-guidance")
    if executable is None:
        raise RuntimeError("modern-web-guidance unavailable")
    suffix = ".ts" if extension in {".mts", ".cts"} else ".html" if extension == ".htm" else extension
    environment = {**os.environ, "DISABLE_TELEMETRY": "1", "ENABLE_FILE_LOGGING": "false"}
    environment.pop("NODE_OPTIONS", None)
    environment.pop("NODE_PATH", None)
    with tempfile.TemporaryDirectory(prefix="mainframe-web-review-") as directory:
        root = Path(directory)
        environment["TMPDIR"] = str(root)
        source = root / ("source" + suffix)
        source.write_text(text, encoding="utf-8")
        command = [executable, "--mainframe-rules", _WEB_RULES_PROGRAM, source.name, "--json"]
        if len(guides) == 1:
            command.extend(["--guide", guides[0]])
        # The upstream dispatcher calls process.exit before piped stdout drains.
        # Node writes stdout synchronously when it targets a regular file.
        with tempfile.TemporaryFile() as output:
            completed = _run_scanner(command, stdout=output, stderr=subprocess.DEVNULL,
                                     cwd=root, env=environment, timeout=1, check=False)
            output.seek(0)
            data = output.read(MAX_FILE_BYTES + 1)
    if completed.returncode != 0:
        raise RuntimeError("web scanner failed")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("web scanner output exceeds the bounded parser input")
    raw = json.loads(data)
    if (not isinstance(raw, dict) or raw.get("error") or raw.get("targetDir") != source.name
            or type(raw.get("activeRuleCount")) is not int or raw["activeRuleCount"] < 1
            or not isinstance(raw.get("guides"), list)):
        raise ValueError("invalid web scanner output")
    rows = []
    source_lines = text.splitlines()
    line_count = len(source_lines)
    for guide in raw["guides"]:
        if not isinstance(guide, dict) or not isinstance(guide.get("rules"), list):
            raise ValueError("invalid web guide output")
        if guide.get("guideId") not in guides:
            continue
        for rule in guide["rules"]:
            if not isinstance(rule, dict) or not isinstance(rule.get("findings"), list):
                raise ValueError("invalid web rule output")
            identity = rule.get("ruleId")
            if identity not in _WEB_LABELS or identity != guide["guideId"]:
                raise ValueError("unsupported web rule output")
            for finding in rule["findings"]:
                if (not isinstance(finding, dict) or finding.get("file") != source.name
                        or type(finding.get("line")) is not int or not 1 <= finding["line"] <= line_count):
                    raise ValueError("unattributed web finding")
                line = finding["line"]
                rows.append(_occurrence(
                    f"Modern Web {identity}: {_WEB_LABELS[identity]}", line, "scanner",
                    source_lines[line - 1].strip()[:1000], channel=_WEB_CHANNEL, blocking=False,
                ))
    return rows


def _duplicate_key_finding(language: str, line: int | None, key: str) -> Occurrence:
    return _occurrence(
        f"{language} duplicate key", line, "mapping",
        key, channel=_DUPLICATE_KEY_CHANNEL, blocking=False,
    )


_JSON_STRING = r'"(?:[^"\\]|\\.)*"'
_JSONC_COMMENTS = re.compile(_JSON_STRING + r"|//[^\r\n]*|/\*[\s\S]*?\*/")
_JSONC_TRAILING_COMMAS = re.compile(_JSON_STRING + r"|,(?=\s*[}\]])")


def _json_findings(text: str, path: Path) -> list[Occurrence]:
    def blank_comment_or_comma(match: re.Match[str]) -> str:
        value = match[0]
        return value if value.startswith('"') else re.sub(r"[^\r\n]", " ", value)

    def count_keys(pairs: list[tuple[str, object]]) -> None:
        # The stdlib gives the decoded key and its owning object, not a position.
        for key, count in Counter(key for key, _ in pairs).items():
            if count > 1:
                rows.extend(_duplicate_key_finding("JSON", None, key) for _ in range(count - 1))

    rows: list[Occurrence] = []
    text = text.removeprefix("\ufeff")
    if (
        path.suffix.lower() == ".jsonc"
        or re.fullmatch(r"(?:tsconfig|jsconfig)(?:\.[^.]+)*\.json", path.name)
        or path.name == "devcontainer.json"
        or path.parent.name == ".vscode"
    ):
        text = _JSONC_COMMENTS.sub(blank_comment_or_comma, text)
        text = _JSONC_TRAILING_COMMAS.sub(blank_comment_or_comma, text)

    def read_constant(value: str) -> None:
        constants.add(value)

    constants: set[str] = set()
    try:
        json.loads(text, object_pairs_hook=count_keys, parse_constant=read_constant,
                   parse_int=str, parse_float=str)
    except json.JSONDecodeError as error:
        return [_syntax_finding("JSON", error.lineno, error.msg, text)]
    if constants:
        return [_occurrence("JSON syntax error", None, "parser", value,
                            channel=_SYNTAX_CHANNEL, blocking=False) for value in sorted(constants)]
    return rows


def _toml_findings(text: str) -> list[Occurrence]:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        # Python 3.11 and 3.12 expose the location only in the exception message.
        message = str(error)
        location = re.search(r" \(at (?:(?:line (\d+), column \d+)|end of document)\)$", message)
        line = getattr(error, "lineno", None)
        if location and line is None:
            line = int(location[1]) if location[1] else 1 + text.count("\n")
        if location:
            message = message[:location.start()]
        if message.startswith(("Cannot overwrite a value", "Cannot declare ",
                               "Cannot redefine namespace", "Duplicate inline table key ")):
            evidence = message + "\n" + _source_excerpt(text, line or 1, line or 1).split("=", 1)[0]
            return [_duplicate_key_finding("TOML", line, evidence)]
        return [_syntax_finding("TOML", line or 1, message, text)]
    return []


_YAML_DIAGNOSTIC = re.compile(
    r"^stdin:(\d+):\d+: \[error\] (.*?) \((syntax|key-duplicates)\)(?:\n|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _yaml_findings(text: str) -> list[Occurrence]:
    result = _run_review_command(
        "yamllint", ["--format", "parsable", "--config-data",
                     '{"rules":{"key-duplicates":{"forbid-duplicated-merge-keys":true}}}', "-"],
        text,
    )
    rows = []
    offset = 0
    for match in _YAML_DIAGNOSTIC.finditer(result.stdout):
        if match.start() != offset:
            break
        offset = match.end()
        line, message, rule = int(match[1]), match[2], match[3]
        if rule == "key-duplicates":
            rows.append(_duplicate_key_finding("YAML", line, message))
        else:
            rows.append(_syntax_finding("YAML", line, message, text))
    if offset != len(result.stdout) or bool(result.returncode) != bool(rows):
        raise RuntimeError("invalid yamllint output")
    return rows


def _rustfmt_executable() -> str | None:
    executable = shutil.which("rustfmt")
    if executable:
        return executable
    # Desktop PATH may omit rustup's proxies even when an SDK is installed.
    root = Path(os.environ.get("RUSTUP_HOME") or Path.home() / ".rustup")
    installed = [path for path in root.glob("toolchains/*/bin/rustfmt")
                 if path.is_file() and os.access(path, os.X_OK)]
    stable = [path for path in installed if path.parent.parent.name.startswith("stable-")]
    candidates = stable or installed
    return str(candidates[0]) if len(candidates) == 1 else None


def _rust_edition(path: Path, workspace: Path) -> str:
    edition = _RUST_EDITIONS[-1]
    inherited = False
    for parent in path.parents:
        if not parent.is_relative_to(workspace):
            break
        manifest = _read_source(parent / "Cargo.toml", workspace)
        if manifest is None:
            raise RuntimeError("Cargo manifest is unavailable")
        if not manifest.exists:
            continue
        data = tomllib.loads(manifest.text)
        if not inherited:
            package = data.get("package")
            if not isinstance(package, dict):
                continue
            edition = package.get("edition", "2015")
            inherited = edition == {"workspace": True}
            if not inherited:
                break
            if "workspace" in package:
                root = (parent / package["workspace"]).resolve()
                referenced = _read_source(root / "Cargo.toml", workspace)
                if not referenced or not referenced.exists:
                    raise RuntimeError("Cargo workspace manifest is unavailable")
                data = tomllib.loads(referenced.text)
                edition = data["workspace"]["package"]["edition"]
                break
        if "workspace" in data:
            edition = data["workspace"]["package"]["edition"]
            break
    if edition not in _RUST_EDITIONS:
        raise RuntimeError("Cargo edition is unsupported or missing")
    return edition


def _sdk_syntax_findings(text: str, path: Path, workspace: Path) -> list[Occurrence]:
    extension = path.suffix.lower()
    language, tool = _SDK_SYNTAX_TOOLS[extension]
    executable = _rustfmt_executable() if tool == "rustfmt" else shutil.which(tool)
    if executable is None:
        raise RuntimeError(f"{tool} unavailable")
    with tempfile.TemporaryDirectory(prefix=f"mainframe-{tool}-") as directory:
        root = Path(directory)
        source = root / f"source{extension}"
        environment = {**os.environ}
        input_text = None
        if tool != "rustfmt":
            source.write_text(text, encoding="utf-8")
        if tool == "dart":
            # Take the already installed SDK behind Flutter's launcher, which
            # can otherwise initialize or update the Flutter cache.
            resolved = Path(executable).resolve()
            sdk = resolved.parent / "cache/dart-sdk/bin/dart"
            if (resolved.parent / "internal/shared.sh").is_file():
                executable = shutil.which(sdk)
                if executable is None:
                    raise RuntimeError("Flutter's Dart SDK is unavailable")
            args = ["--suppress-analytics", "format", "--output=none", source.name]
        elif tool == "gofmt":
            (root / "mode").write_text("off\n", encoding="utf-8")
            environment["TEST_TELEMETRY_DIR"] = directory
            args = ["-l", source.name]
        else:
            config = root / "rustfmt.toml"
            config.touch()
            args = ["--emit", "stdout", "--edition", _rust_edition(path, workspace),
                    "--color", "never", "--config-path", str(config)]
            environment["RUSTUP_AUTO_INSTALL"] = "0"
            input_text = text
        result = _run_scanner(
            [executable, *args], input=input_text, capture_output=True, encoding="utf-8",
            cwd=root, env=environment, timeout=1, check=False,
        )
    if not result.returncode:
        return []
    if tool == "dart" and result.returncode == 65:
        pattern = r"(?m)^line (?P<line>\d+), column \d+ of source\.dart: (?P<message>.+)$"
    elif tool == "gofmt" and result.returncode == 2:
        pattern = r"(?m)^source\.go:(?P<line>\d+):\d+: (?P<message>.+)$"
    elif tool == "rustfmt" and result.returncode == 1:
        pattern = r"(?m)^error: (?P<message>.+)\n *--> <stdin>:(?P<line>\d+):\d+$"
    else:
        pattern = None
    match = re.search(pattern, result.stderr) if pattern else None
    if match is None:
        raise RuntimeError(f"{tool} did not report a syntax diagnostic")
    return [_syntax_finding(language, int(match["line"]), match["message"], text)]


def _diagnostic_rows(raw: object) -> list[dict]:
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError("invalid analyzer diagnostics")
    return raw


def _shellcheck_findings(text: str, extension: str) -> list[Occurrence]:
    shebang = text.partition("\n")[0] if text.startswith("#!") else ""
    interpreter = re.match(
        r"^#![ \t]*(?:\S*/env[ \t]+(?:-S[ \t]+)?)?(?:\S*/)?(bash|sh|dash|ksh|busybox)(?=\s|$)",
        shebang,
    )
    if shebang and interpreter is None:
        return []
    args = ["--norc", "--format=json",
            "--include=" + ",".join(f"SC{code}" for code in _SHELLCHECK_LABELS), "-"]
    if interpreter:
        args.insert(0, f"--shell={interpreter.group(1)}")
    elif extension == ".bash":
        args.insert(0, "--shell=bash")
    raw = _run_review_tool("shellcheck", args, text)
    rows = []
    for item in _diagnostic_rows(raw):
        code = item.get("code")
        if code not in _SHELLCHECK_LABELS:
            continue
        line, end_line = int(item["line"]), int(item["endLine"])
        rows.append(_occurrence(
            f"ShellCheck SC{code}: {_SHELLCHECK_LABELS[code]}", line, "scanner",
            _source_excerpt(text, line, end_line), channel="shellcheck", blocking=False,
        ))
    return rows


def _github_workflow(path: Path, workspace: Path) -> bool:
    return path.suffix.lower() in _YAML_EXTENSIONS and path.parent.relative_to(workspace).parts == _WORKFLOW_DIRECTORY


def _actionlint_findings(text: str) -> list[Occurrence]:
    raw = _run_review_tool(
        "actionlint",
        ["-config-file", os.devnull, "-shellcheck=", "-pyflakes=",
         "-no-color", "-format", "{{json .}}", "-"],
        text,
    )
    rows = []
    for item in _diagnostic_rows(raw):
        kind = item.get("kind")
        if kind not in _ACTIONLINT_LABELS:
            continue
        line = int(item["line"])
        message = " ".join(str(item["message"]).split())
        # The analyzer may repeat input values. Put identity in the fingerprint
        # and send only the fixed rule description to the agent.
        rows.append(_occurrence(
            f"actionlint {kind}: {_ACTIONLINT_LABELS[kind]}", line, "scanner",
            message + "\n" + _source_excerpt(text, line, line),
            channel="actionlint", blocking=False,
        ))
    return rows


def _kube_candidate(text: str, path: Path, workspace: Path) -> bool:
    relative = path.relative_to(workspace)
    if (
        {"templates", "patches", "overlays"}.intersection(relative.parts[:-1])
        or path.stem.startswith(("patch-", "patch_")) or "{{" in text
    ):
        return False
    return any(
        _KUBE_API.search(document) and _KUBE_WORKLOAD.search(document) and _KUBE_CONTAINER.search(document)
        for document in re.split(r"(?m)^---[ \t]*(?:#.*)?$", text)
    )


def _kube_findings(text: str) -> list[Occurrence]:
    raw = _run_review_tool(
        "kube-linter", ["lint", "--with-color=false", "--format=json", "--fail-if-no-objects-found",
                       "--do-not-auto-add-defaults", "--include=" + ",".join(_KUBE_LABELS), "-"],
        text,
    )
    if not isinstance(raw, dict) or "Reports" not in raw:
        raise ValueError("invalid KubeLinter report")
    rows = []
    reports = [] if raw["Reports"] is None else raw["Reports"]
    for item in _diagnostic_rows(reports):
        check = item.get("Check")
        if check not in _KUBE_LABELS:
            continue
        diagnostic = item["Diagnostic"]["Message"]
        resource = item["Object"]["K8sObject"]
        kind, name = resource["GroupVersionKind"]["Kind"], resource["Name"]
        namespace = resource.get("Namespace") or "default"
        identity = f"{kind} {namespace}/{name}"
        safe_identity = all(
            isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", value)
            for value in (kind, name, namespace)
        )
        container = re.fullmatch(r'container "([A-Za-z0-9_.-]{1,63})" does not specify a readiness probe', diagnostic)
        if container and check == "no-readiness-probe":
            identity += f", container {container.group(1)}"
        label = f"{identity}: " if safe_identity else ""
        rows.append(_occurrence(
            f"KubeLinter {check}: {label}{_KUBE_LABELS[check]}", None, "scanner",
            identity, channel="kube-linter", blocking=False,
        ))
    return sorted(rows, key=lambda row: row.label)


def _migration_metadata(path: Path, workspace: Path) -> str:
    try:
        source = _read_source(path, workspace)
        return source.text if source else ""
    except RuntimeError:
        return ""


def _postgres_migration(path: Path, workspace: Path) -> bool:
    relative = path.relative_to(workspace)
    if (
        relative.parts[-4:-2] == ("prisma", "migrations")
        and path.name == "migration.sql"
        and re.fullmatch(r"\d{14}_.+", path.parent.name)
    ):
        try:
            lock = tomllib.loads(_migration_metadata(path.parent.parent / "migration_lock.toml", workspace))
        except ValueError:
            return False
        return lock.get("provider") == "postgresql"
    if not re.fullmatch(r"[0-9]{4}_.+\.sql", path.name):
        return False
    journal = _migration_metadata(path.parent / "meta/_journal.json", workspace)
    try:
        metadata = json.loads(journal or "null")
    except ValueError:
        return False
    if isinstance(metadata, dict):
        return metadata.get("dialect") == "postgresql"
    # The known CSS migration runner embeds its repository's SQL and uses pgx.
    # A numbered path or a Go dependency alone cannot identify its dialect.
    if len(relative.parts) != 2 or path.parent.name != "migrations":
        return False
    module = _migration_metadata(workspace / "go.mod", workspace)
    embedded = _migration_metadata(path.parent / "migrations.go", workspace)
    return (
        re.search(r"(?m)^module[ \t]+icover-vozvrat[ \t]*$", module) is not None
        and re.search(r"(?m)^[ \t]*github\.com/jackc/pgx/v5[ \t]", module) is not None
        and re.search(r"(?m)^//go:embed[ \t]+\*\.sql[ \t]*$", embedded) is not None
    )


def _squawk_findings(text: str) -> list[Occurrence]:
    raw = _run_review_tool(
        "squawk", ["--config", os.devnull, "--reporter=json", "--no-assume-in-transaction",
                   "--stdin-filepath=source.sql"], text,
    )
    diagnostics = _diagnostic_rows(raw)
    rows = []
    parse_reported = False
    # Keep the specific schema risk visible ahead of connection-setting advice.
    for item in sorted(diagnostics, key=lambda item: item.get("rule_name") == "require-lock-timeout"):
        rule = item.get("rule_name")
        if rule not in _SQUAWK_LABELS:
            continue
        if rule == "syntax-error":
            # Parser recovery can emit several follow-on errors for one typo.
            if parse_reported:
                continue
            parse_reported = True
        line = int(item["line"]) + 1
        end_line = int(item["line_end"]) + 1
        rows.append(_occurrence(
            f"Squawk {rule}: {_SQUAWK_LABELS[rule]}", line, "scanner",
            _source_excerpt(text, line, end_line), channel="squawk", blocking=False,
        ))
    return rows


def _scan_file_advice(
    text: str, extension: str, path: Path, workspace: Path,
) -> tuple[str | None, list[Occurrence], ScanIssue | None]:
    if extension in _SHELL_EXTENSIONS:
        tool, scan, args = "shellcheck", _shellcheck_findings, (text, extension)
    elif _github_workflow(path, workspace):
        tool, scan, args = "actionlint", _actionlint_findings, (text,)
    elif extension in _YAML_EXTENSIONS:
        if not _kube_candidate(text, path, workspace):
            # Plain YAML can become a manifest during this edit.
            return "kube-linter", [], None
        tool, scan, args = "kube-linter", _kube_findings, (text,)
    elif extension == ".sql":
        # A Prisma or Drizzle lock can be created alongside a new migration.
        if not text:
            return "squawk", [], None
        if not _postgres_migration(path, workspace):
            return None, [], None
        tool, scan, args = "squawk", _squawk_findings, (text,)
    else:
        return None, [], None
    if not text:
        return tool, [], None
    try:
        return tool, scan(*args), None
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        return None, [], ScanIssue(f"scanner:{tool}", f"{tool} review was unavailable for the edited file.")


def _semgrep_candidate(text: str) -> bool:
    return bool(_SEMGREP_EXEC_CANDIDATE.search(text) or _SEMGREP_TLS_CANDIDATE.search(text))


def _semgrep_security_findings(
    text: str,
    extension: str,
) -> list[Occurrence]:
    if not _semgrep_candidate(text):
        return []
    # The pinned Semgrep target selector skips the two Node TypeScript suffixes.
    # Only the disposable parser input needs the .ts name.
    if extension in {".mts", ".cts"}:
        extension = ".ts"
    return _semgrep_findings(text, extension, _SEMGREP_CONFIG, _SEMGREP_LABELS, _SEMGREP_SECURITY_CHANNEL)


def _pgxpool_findings(text: str) -> list[Occurrence]:
    if _PGXPOOL_IMPORT not in text or not _PGXPOOL_DISCARD.search(text) or not _PGXPOOL_CALL.search(text):
        return []
    return _semgrep_findings(
        text, ".go", _PGXPOOL_RULES, _PGXPOOL_LABELS, _SEMGREP_GO_CHANNEL, native=True,
    )


def _semgrep_findings(
    text: str, extension: str, config: dict, labels: dict[str, str], channel: str,
    *, native: bool = False,
) -> list[Occurrence]:
    executable = shutil.which("semgrep")
    if executable is None:
        raise RuntimeError("semgrep unavailable")
    # The pinned native CLI avoids Python startup for this narrow Go check.
    native_cli = ["--experimental"] if native else []
    with tempfile.TemporaryDirectory(prefix="mainframe-semgrep-") as directory:
        root = Path(directory)
        rules = root / "rules.json"
        source = root / f"source{extension}"
        rules.write_text(json.dumps(config), encoding="utf-8")
        source.write_text(text, encoding="utf-8")
        environment = {
            **os.environ,
            "XDG_CONFIG_HOME": str(root),
            "XDG_CACHE_HOME": str(root),
            "SEMGREP_LOG_FILE": str(root / "semgrep.log"),
            "SEMGREP_SETTINGS_FILE": str(root / "settings.yml"),
        }
        environment.pop("SEMGREP_APP_TOKEN", None)
        completed = _run_scanner(
            [
                executable,
                "scan",
                *native_cli,
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
            timeout=1 if native else 12,
            cwd=root,
            env=environment,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError("Semgrep scan failed")
    return _parse_semgrep_findings(completed.stdout, text, labels, channel)


def _parse_semgrep_findings(output: str, text: str, labels: dict[str, str], channel: str) -> list[Occurrence]:
    try:
        raw = json.loads(output)
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
        if rule_id not in labels:
            continue
        row = int((item.get("start") or {}).get("line") or 0)
        end_row = int((item.get("end") or {}).get("line") or row)
        rows.append(
            _occurrence(
                labels[rule_id],
                row,
                "scanner",
                _source_excerpt(text, row, end_row),
                channel=channel,
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
        if time.time() - path.stat().st_mtime > STATE_MAX_AGE_SECONDS:
            return _empty_state(), True
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
        if not _inside_workspace(candidate, workspace):
            continue
        if candidate.suffix.lower() not in _EDIT_EXTENSIONS:
            continue
        if candidate not in result:
            if len(result) >= MAX_FILES_PER_EDIT:
                truncated = True
                continue
            result.append(candidate)
    return result, truncated


def _read_source(path: Path, workspace: Path) -> SourceSnapshot | None:
    try:
        resolved = path.resolve()
        if resolved != path or not _inside_workspace(resolved, workspace) or path.is_symlink():
            return None
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                return None
            raw = handle.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            return None
        source = SourceSnapshot(raw.decode("utf-8", errors="replace"), True)
    except FileNotFoundError:
        source = SourceSnapshot("", False)
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
    return source


def _is_helm_template(text: str, path: Path, workspace: Path) -> bool:
    if "{{" not in text:
        return False
    for parent in path.parents:
        if parent == workspace:
            break
        if parent.name == "templates" and (parent.parent / "Chart.yaml").is_file():
            return True
    return False


def _scan_syntax_advice(
    source: SourceSnapshot, extension: str, path: Path, workspace: Path,
) -> tuple[list[Occurrence], tuple[str, ...], ScanIssue | None]:
    text = source.text
    channels = (_SYNTAX_CHANNEL,)
    if extension in _SDK_SYNTAX_TOOLS:
        _, tool = _SDK_SYNTAX_TOOLS[extension]
        scanner, args = _sdk_syntax_findings, (text, path, workspace)
    else:
        channels += (_DUPLICATE_KEY_CHANNEL,)
        if extension in _JSON_EXTENSIONS:
            tool, scanner, args = "JSON parser", _json_findings, (text, path)
        elif extension == ".toml":
            tool, scanner, args = "TOML parser", _toml_findings, (text,)
        elif _is_helm_template(text, path, workspace):
            # Rendered Helm output is YAML. The template source is not.
            return [], (), None
        else:
            tool, scanner, args = "yamllint", _yaml_findings, (text,)
    if not source.exists or (extension == ".rs" and not text.strip()):
        return [], channels, None
    try:
        return scanner(*args), channels, None
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        issue = ScanIssue(f"scanner:{tool}", f"{tool} syntax or key review was unavailable for the edited file.")
        return [], (), issue


def _scan_source(
    source: SourceSnapshot,
    extension: str,
    path: Path,
    workspace: Path,
    *,
    include_advisory: bool,
) -> ScanResult:
    text = source.text
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
            rows.extend(_python_findings(text, path, include_advisory=include_advisory))
            channels.add(_PYTHON_SECURITY_CHANNEL)
            if include_advisory:
                channels.update((_SYNTAX_CHANNEL, _PYTHON_ASYNC_CHANNEL, _PYTHON_ERROR_CHANNEL,
                                 _PYTHON_CORRECTNESS_CHANNEL))
        except Exception:
            message = "Python security scanning is unavailable; Ruff safety rules were not checked."
            if include_advisory:
                message += " Python syntax, async, error-handling, and test rules were also unavailable."
            issues.append(
                ScanIssue(
                    "scanner:python-security",
                    message,
                )
            )

    if extension in _NODE_EXTENSIONS:
        check_tests = include_advisory and _js_test_file(path)
        try:
            rows.extend(_node_findings(text, path, include_advisory=include_advisory))
            channels.add(_NODE_SECURITY_CHANNEL)
            if include_advisory:
                channels.update((_SYNTAX_CHANNEL, _NODE_CORRECTNESS_CHANNEL))
            if check_tests:
                channels.add(_NODE_TEST_CHANNEL)
        except Exception:
            message = "JavaScript security scanning is unavailable; Oxlint safety rules were not checked."
            if include_advisory:
                message += " JavaScript and TypeScript syntax, error-handling, and Promise rules were also unavailable."
            if check_tests:
                message += " Async test assertions were not checked."
            issues.append(
                ScanIssue(
                    "scanner:node-security",
                    message,
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

    if include_advisory:
        if extension in _CONFIG_EXTENSIONS or extension in _SDK_SYNTAX_TOOLS:
            findings, syntax_channels, issue = _scan_syntax_advice(source, extension, path, workspace)
            rows.extend(findings)
            channels.update(syntax_channels)
            if issue:
                issues.append(issue)
        if extension == ".go":
            try:
                rows.extend(_pgxpool_findings(text))
                channels.add(_SEMGREP_GO_CHANNEL)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                issues.append(ScanIssue(
                    "scanner:semgrep-go", "Semgrep pgxpool review was unavailable for a candidate Go edit.",
                ))
        channel, findings, issue = _scan_file_advice(text, extension, path, workspace)
        if channel:
            channels.add(channel)
            rows.extend(findings)
        if issue:
            issues.append(issue)

    try:
        growth = _growth_metrics(text, extension)
    except Exception:
        growth = None
    return ScanResult(rows, frozenset(channels), tuple(issues), source.revision, growth)


def _read_scan(
    path: Path,
    workspace: Path,
    *,
    include_advisory: bool,
    deadline: float | None = None,
) -> ScanResult:
    if deadline is not None and time.monotonic() >= deadline:
        return ScanResult([], frozenset(), (ScanIssue(
            "boundary:scan-budget", "The edit reached its code-quality scan time budget.",
        ),), None)
    source = _read_source(path, workspace)
    if source is None:
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
    token = _SCAN_DEADLINE.set(deadline)
    try:
        return _scan_source(
            source, path.suffix.lower(), path, workspace, include_advisory=include_advisory,
        )
    finally:
        _SCAN_DEADLINE.reset(token)


def _revision_matches(path: Path, workspace: Path, revision: str | None) -> bool:
    if revision is None:
        return False
    source = _read_source(path, workspace)
    return source is not None and source.revision == revision


def _read_edit_scans(paths: Iterable[Path], workspace: Path, deadline: float) -> dict[Path, ScanResult]:
    # Finish established checks for every path before spending time on new web advice.
    scans = {path: _read_scan(path, workspace, include_advisory=True, deadline=deadline) for path in paths}
    web_deadline = min(deadline, time.monotonic() + _WEB_SCAN_BUDGET_SECONDS)
    token = _SCAN_DEADLINE.set(web_deadline)
    try:
        for path, scan in scans.items():
            if path.suffix.lower() not in _WEB_EXTENSIONS or scan.revision is None:
                continue
            try:
                if time.monotonic() >= web_deadline:
                    raise TimeoutError("web review has no remaining edit budget")
                source = _read_source(path, workspace)
                if source is None or source.revision != scan.revision:
                    raise ValueError("web review snapshot changed after core scanning")
                rows = _modern_web_findings(source.text, path, workspace)
                scans[path] = scan._replace(rows=scan.rows + rows, channels=scan.channels | {_WEB_CHANNEL})
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
                issue = ScanIssue("scanner:modern-web", "Modern web review was unavailable for the edited file.")
                scans[path] = scan._replace(issues=scan.issues + (issue,))
    finally:
        _SCAN_DEADLINE.reset(token)
    return scans


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


def _bounded_row(value: str, limit: int = MAX_ROW_CHARS) -> str:
    value = "".join(char if char.isprintable() else "?" for char in value)
    if len(value) <= limit:
        return value
    # Preserve both the directory prefix and the file/line/diagnostic suffix.
    half = (limit - 3) // 2
    return value[:half] + " … " + value[-half:]


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
        "Code-quality protection unavailable; verify directly:\n"
        + body
        + "\nNo clean result or hook block is implied."
    )


def _join_notes(*notes: str | None) -> str | None:
    sections = [section for note in notes if note for section in note.split("\n\n") if section]
    if not sections:
        return None
    limit = (MAX_ADVISORY_CHARS - 2 * (len(sections) - 1)) // len(sections)
    compact = []
    for section in sections:
        if len(section) <= limit:
            compact.append(section)
            continue
        lines = section.splitlines()
        rows = [line for line in lines[1:] if line.startswith("  - ")]
        if not rows:
            compact.append(_bounded_row(section, limit))
            continue
        heading = lines[0]
        findings = heading + "\n" + "\n".join(rows)
        if len(findings) <= limit:
            compact.append(findings)
            continue
        marker = "\n  - … more findings" if len(rows) > 1 else ""
        row_limit = limit - len(heading) - len(marker) - 1
        first = _bounded_row(rows[0], row_limit)
        compact.append(heading + "\n" + first + marker)
    return "\n\n".join(compact)


def _prune_pending(state: dict[str, object]) -> bool:
    pending = state.get("pending")
    if not isinstance(pending, dict):
        raise ValueError("invalid pending state")
    cutoff = time.time() - PENDING_MAX_AGE_SECONDS
    notices = state["notices"]
    operations = [
        key for key, timestamp in notices.items()
        if key.startswith("operation:") and isinstance(timestamp, (int, float))
    ]
    for key in operations:
        if notices[key] < cutoff:
            del notices[key]
    operations = [key for key in operations if key in notices]
    for key in sorted(operations, key=notices.get)[:-MAX_COMPLETED_OPERATIONS]:
        del notices[key]
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
        deadline = time.monotonic() + SCAN_BUDGET_SECONDS
        snapshots: dict[str, object] = {}
        issues: list[ScanIssue] = []
        if truncated:
            issues.append(
                ScanIssue(
                    "boundary:path-limit",
                    "The edit named more code paths than one bounded hook pass can inspect.",
                )
            )
        for selected_path, scan in _read_edit_scans(selected, workspace, deadline).items():
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
            operation_key = _operation_key(operation)
            if "operation:" + operation_key not in state["notices"]:
                pending.setdefault(operation_key, {
                    "created": time.time(),
                    "paths": snapshots,
                })
            _save(path, state)
        _cleanup_stale(path.parent)
        note = _join_notes(_issue_advisory(claimed))
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
    revalidation_channels = scan.revalidation_channels
    unavailable = False
    for fingerprint, record in list(records.items()):
        baseline = record.get("baseline") if isinstance(record, dict) else None
        channel = record.get("channel", "markers") if isinstance(record, dict) else None
        if not isinstance(channel, str) or channel not in revalidation_channels:
            unavailable = True
            continue
        if not isinstance(baseline, int) or counts.get(fingerprint, 0) <= baseline:
            del records[fingerprint]
    if not records:
        active.pop(str(path), None)
    return unavailable


def _advisory(rows: list[tuple[Path, Occurrence]], workspace: Path) -> str:
    locations = [_bounded_row(f"{_display_path(path, workspace)}:{row.line} — {row.label}") for path, row in rows]
    body = "\n".join(f"  - {location}" for location in locations[:MAX_MESSAGE_ROWS])
    if len(locations) > MAX_MESSAGE_ROWS:
        body += f"\n  - … {len(locations) - MAX_MESSAGE_ROWS} more"
    return (
        "Code quality — new findings; fix behavior and verify:\n"
        + body
    )


def _review_advisory(rows: list[tuple[Path, Occurrence]], workspace: Path) -> str:
    locations = []
    for path, row in rows:
        location = _display_path(path, workspace)
        if row.line is not None:
            location += f":{row.line}"
        locations.append(_bounded_row(f"{location} — {row.label}"))
    body = "\n".join(f"  - {location}" for location in locations[:MAX_MESSAGE_ROWS])
    if len(locations) > MAX_MESSAGE_ROWS:
        body += f"\n  - … {len(locations) - MAX_MESSAGE_ROWS} more"
    if any(row.channel != _SEMGREP_SECURITY_CHANNEL for _, row in rows):
        return (
            "Code review advice (non-blocking):\n"
            + body
            + "\nReview the affected line or configuration."
        )
    return (
        "Security review advice (non-blocking):\n"
        + body
        + "\nReview the affected trust boundary in context."
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
    body = "\n".join(f"  - {_bounded_row(location)}" for location in locations[:MAX_MESSAGE_ROWS])
    if len(locations) > MAX_MESSAGE_ROWS:
        body += f"\n  - … {len(locations) - MAX_MESSAGE_ROWS} more"
    return (
        "Code structure review (no forced split):\n"
        + body
        + "\nReview the affected responsibilities for cohesion."
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
            operation_key = _operation_key(operation)
            notice_key = "operation:" + operation_key
            if notice_key in state["notices"]:
                return QualityResult()
            _claim_issues(state, [ScanIssue(notice_key, "")])
            snapshot = pending.pop(operation_key, None)
            if not succeeded:
                _save(path, state)
                if recovered_before or expired_before:
                    return _unavailable("after-edit verification")
                return QualityResult()
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("paths"), dict):
                claimed = _claim_issues(state, [ScanIssue(
                    "boundary:missing-snapshot",
                    "An edit could not be paired with its before snapshot.",
                )])
                _save(path, state)
                return QualityResult(advisory=_issue_advisory(claimed))
            _save(path, state)

        before_records: dict[Path, dict[str, object]] = {}
        issues: list[ScanIssue] = []
        deadline = time.monotonic() + SCAN_BUDGET_SECONDS
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
            before_records[file_path] = before_record
        scanned = _read_edit_scans(before_records, workspace, deadline)
        issues.extend(issue for scan in scanned.values() for issue in scan.issues)

        new_rows: list[tuple[Path, Occurrence]] = []
        growth_rows: list[GrowthFinding] = []
        unavailable = False
        with _locked(path):
            state, recovered_after = _load(path)
            expired_after = _prune_pending(state)
            active = _active_records(state)
            for file_path, scan in scanned.items():
                before_record = before_records[file_path]
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
        revalidation_channels = scan.revalidation_channels
        counts = Counter(row.fingerprint for row in scan.rows)
        by_fingerprint: dict[str, list[Occurrence]] = {}
        for row in scan.rows:
            by_fingerprint.setdefault(row.fingerprint, []).append(row)
        for fingerprint, record in records.items():
            baseline = record.get("baseline") if isinstance(record, dict) else None
            channel = record.get("channel", "markers") if isinstance(record, dict) else None
            if not isinstance(channel, str) or channel not in revalidation_channels:
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
    locations = [_bounded_row(f"{_display_path(path, workspace)}:{row.line} — {row.label}") for path, row in rows]
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
            # A completion callback can overlap another operation in the same
            # scope. Only its matching post event or expiry owns that snapshot.
            active = _active_records(state)
            paths = list(active)
            _save(path, state)

        scans: dict[str, ScanResult] = {}
        issues: list[ScanIssue] = []
        deadline = time.monotonic() + SCAN_BUDGET_SECONDS
        if incomplete_edits:
            issues.append(
                ScanIssue(
                    "boundary:incomplete-edit",
                    "An edit has no matching post event yet; its snapshot remains available for attribution.",
                )
            )
        for raw_path in paths:
            candidate = Path(raw_path)
            scan = _read_scan(candidate, workspace, include_advisory=False, deadline=deadline)
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
        note = _join_notes(_issue_advisory(claimed))
        if recovered_before or recovered_after or expired_before or expired_after:
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

"""Pure line-count / function-span detection for the length-gate hook.

Single source of truth for `length-quality-note.py`. Importable so the
counting and AST logic are unit-testable independent of the hook payload
plumbing (mirrors the `_markers.py` shared-detector-module pattern). Stdlib
only.

Design (decision-reviewer + advisor, 2026-07-06): no before/after size
comparison -- flag any over-threshold file/function on the current content
alone; ticket-discipline (`_hooklib.tickets_mentioning`), not a delta split,
is the noise-reduction mechanism. Qualnames are built via a recursive
NodeVisitor (push/pop per scope) -- `ast.walk` is breadth-first with no
ancestor context and cannot do this.
"""

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooklib import CODE_EXTENSIONS

# SQL migrations/schema dumps and Vue/Svelte SFCs (template+script+style
# bundled in one file) legitimately exceed 400 lines for reasons unrelated to
# hand-written imperative-logic bulk, which is the rule's intent. Carved out
# of the file-length check only; function-length stays Python-only regardless.
FILE_LENGTH_EXTENSIONS = CODE_EXTENSIONS - {".sql", ".vue", ".svelte"}

FILE_LENGTH_THRESHOLD = 400
FUNCTION_LENGTH_THRESHOLD = 60


def count_lines(text):
    """Line count matching editor display (`str.splitlines`), not `wc -l`
    (which undercounts a file lacking a trailing newline by one)."""
    return len(text.splitlines())


class _FunctionSpanVisitor(ast.NodeVisitor):
    def __init__(self):
        self.stack = []
        self.spans = []

    def _visit_scope(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node):
        self._visit_scope(node)

    def visit_FunctionDef(self, node):
        self.spans.append((".".join(self.stack + [node.name]),
                           node.lineno, node.end_lineno))
        self._visit_scope(node)

    def visit_AsyncFunctionDef(self, node):
        self.spans.append((".".join(self.stack + [node.name]),
                           node.lineno, node.end_lineno))
        self._visit_scope(node)


def python_function_spans(text):
    """(qualname, start_lineno, end_lineno) for every function/method in
    `text`, dotted by enclosing class/function nesting. Raises SyntaxError on
    malformed Python -- callers must catch it and skip the function-length
    check (file-length still applies, since it needs no parse)."""
    tree = ast.parse(text)
    visitor = _FunctionSpanVisitor()
    visitor.visit(tree)
    return visitor.spans


def over_threshold_functions(text, threshold=FUNCTION_LENGTH_THRESHOLD):
    """[(qualname, start, end, length), ...] for functions strictly over
    `threshold` lines. Raises SyntaxError on malformed Python (caller catches)."""
    result = []
    for qualname, start, end in python_function_spans(text):
        length = end - start + 1
        if length > threshold:
            result.append((qualname, start, end, length))
    return result

"""Pure line-count / function-span detection for the length-gate hook.

Single source of truth for `length-quality-note.py`. Importable so the
counting and AST logic are unit-testable independent of the hook payload
plumbing (mirrors the `_markers.py` shared-detector-module pattern). Stdlib
only.

The owning hook compares these pure measurements with a session baseline.
Qualnames are built via a recursive NodeVisitor (push/pop per scope) because
`ast.walk` is breadth-first and carries no ancestor context.
"""

import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooklib import CODE_EXTENSIONS

# Generated migrations and schema dumps legitimately exceed the generic file
# threshold. Vue/Svelte are now safe to include because only a session-owned
# crossing is reported; an inherited long SFC stays silent.
FILE_LENGTH_EXTENSIONS = CODE_EXTENSIONS - {".sql"}

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

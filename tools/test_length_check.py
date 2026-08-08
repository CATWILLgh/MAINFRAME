#!/usr/bin/env python3
"""Tests for _length_check.py: count_lines, python_function_spans,
over_threshold_functions, FILE_LENGTH_EXTENSIONS.

Design under test (decision-reviewer + advisor, 2026-07-06): no before/after
size comparison (the reviewer's counter-model, adopted) -- flag any
over-threshold file/function on the current content alone; ticket-discipline
(not a delta split) is the noise-reduction mechanism. Qualname must be built
via a recursive NodeVisitor (push/pop per scope), never `ast.walk` (breadth-
first, no ancestor context -- the reviewer's bug catch on the original plan).
"""

import importlib.util
import os

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "adapters/claude-code/plugin", "hooks", "scripts", "_length_check.py")
spec = importlib.util.spec_from_file_location("length_check", _SCRIPT)
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)


def test_count_lines_no_trailing_newline():
    assert lc.count_lines("a\nb\nc") == 3


def test_count_lines_trailing_newline_no_extra():
    assert lc.count_lines("a\nb\nc\n") == 3


def test_count_lines_empty_text():
    assert lc.count_lines("") == 0


def test_count_lines_single_line():
    assert lc.count_lines("just one line") == 1


def test_spans_top_level_function():
    src = "def foo():\n" + "    x = 1\n" * 5
    spans = lc.python_function_spans(src)
    assert spans == [("foo", 1, 6)]


def test_spans_method_in_class_qualname():
    src = (
        "class Widget:\n"
        "    def render(self):\n"
        "        return 1\n"
    )
    spans = lc.python_function_spans(src)
    assert spans == [("Widget.render", 2, 3)]


def test_spans_nested_closure_qualname():
    src = (
        "def outer():\n"
        "    def inner():\n"
        "        return 1\n"
        "    return inner\n"
    )
    spans = lc.python_function_spans(src)
    names = {n: (s, e) for n, s, e in spans}
    assert names["outer"] == (1, 4)
    assert names["outer.inner"] == (2, 3)


def test_spans_async_function():
    src = "async def fetch():\n    return 1\n"
    spans = lc.python_function_spans(src)
    assert spans == [("fetch", 1, 2)]


def test_spans_decorator_excluded_from_start_line():
    # Python 3.8+: FunctionDef.lineno is the `def` line, not the decorator.
    src = (
        "@staticmethod\n"
        "@another_decorator\n"
        "def handler():\n"
        "    return 1\n"
    )
    spans = lc.python_function_spans(src)
    assert spans == [("handler", 3, 4)]


def test_spans_class_nested_in_function():
    src = (
        "def factory():\n"
        "    class Local:\n"
        "        def method(self):\n"
        "            return 1\n"
        "    return Local\n"
    )
    spans = lc.python_function_spans(src)
    names = [n for n, _, _ in spans]
    assert names == ["factory", "factory.Local.method"]


def test_spans_malformed_python_raises_syntax_error():
    try:
        lc.python_function_spans("def broken(:\n    pass\n")
        raise AssertionError("expected SyntaxError")
    except SyntaxError:
        pass


def test_over_threshold_under_limit_not_reported():
    src = "def small():\n" + "    x = 1\n" * 10
    assert lc.over_threshold_functions(src, threshold=60) == []


def test_over_threshold_over_limit_reported_with_length():
    src = "def big():\n" + "    x = 1\n" * 65
    result = lc.over_threshold_functions(src, threshold=60)
    assert len(result) == 1
    name, start, end, length = result[0]
    assert name == "big"
    assert length == 66  # def line + 65 body lines
    assert length > 60


def test_over_threshold_custom_threshold_boundary():
    # Exactly at threshold is NOT a violation ("under N lines").
    src = "def edge():\n" + "    x = 1\n" * 4  # 5 lines total
    assert lc.over_threshold_functions(src, threshold=5) == []
    src2 = "def edge():\n" + "    x = 1\n" * 5  # 6 lines total
    assert len(lc.over_threshold_functions(src2, threshold=5)) == 1


def test_file_length_extensions_excludes_sql_vue_svelte():
    assert ".sql" not in lc.FILE_LENGTH_EXTENSIONS
    assert ".vue" not in lc.FILE_LENGTH_EXTENSIONS
    assert ".svelte" not in lc.FILE_LENGTH_EXTENSIONS


def test_file_length_extensions_includes_common_code():
    for e in (".py", ".ts", ".tsx", ".js", ".go", ".rs"):
        assert e in lc.FILE_LENGTH_EXTENSIONS


def _run_all():
    import sys
    failures = 0
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()

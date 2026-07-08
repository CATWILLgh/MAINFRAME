#!/usr/bin/env python3
"""Characterization tests for `comment_extract.py` (exact + lenient extractors).

Pins the documented contract before any refactor: fail to SILENCE, never to
EMIT — Python is exact (tokenize + ast), other languages run a string/char/
template-aware scanner, unmodelled string forms skip the whole file, and the
lenient layer counts line-START leaders only (its documented false positives
are pinned as such). Expected values were snapshotted by running the current
code and validating each output against the module contract.

Run: `python3 tools/test_comment_extract.py` (exit 0 = pass). Stdlib only.
"""

import importlib.util
import os

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "plugin-dist", "hooks", "scripts", "comment_extract.py")
spec = importlib.util.spec_from_file_location("comment_extract", _SCRIPT)
ce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ce)


def test_python_comments_and_docstrings():
    src = ('#!/usr/bin/env python3\n'
           '"""Module doc."""\n'
           '# top comment\n'
           'x = 1  # inline\n'
           's = "# not a comment"\n'
           '\n'
           'def f():\n'
           '    """Func doc."""\n'
           '    return 1\n'
           '\n'
           'class C:\n'
           '    """Class doc."""\n'
           '    y = "Phase 2"\n')
    got = ce.extract(src, ".py")
    assert (1, "#!/usr/bin/env python3", ce.COMMENT) in got
    assert (3, "# top comment", ce.COMMENT) in got
    assert (4, "# inline", ce.COMMENT) in got
    assert (2, "Module doc.", ce.DOCSTRING) in got
    assert (8, "Func doc.", ce.DOCSTRING) in got
    assert (12, "Class doc.", ce.DOCSTRING) in got
    texts = [t for _, t, _ in got]
    assert "# not a comment" not in texts       # string content is not a comment
    assert "Phase 2" not in texts               # data string is not a docstring
    assert len(got) == 6


def test_python_broken_source_keeps_partial_comments():
    got = ce.extract("# kept comment\ndef broken(:\n", ".py")
    assert got == [(1, "# kept comment", ce.COMMENT)]


def test_js_line_block_and_string_forms():
    src = ('const a = 1; // line comment\n'
           '/* block\n'
           '   comment */\n'
           'const s = "// not a comment";\n'
           'const t = `// not a comment either\n'
           '// still template`;\n'
           'const re = /https?:\\/\\//;\n'
           '// after regex\n')
    got = ce.extract(src, ".js")
    assert got == [
        (1, "// line comment", ce.COMMENT),
        (2, "/* block\n   comment */", ce.COMMENT),
        (8, "// after regex", ce.COMMENT),
    ]


def test_js_block_marker_inside_string_not_extracted():
    got = ce.extract('const s = "/* not a block */";\n// real\n', ".js")
    assert got == [(2, "// real", ce.COMMENT)]


def test_js_unterminated_string_fails_to_silence():
    got = ce.extract('const s = "unterminated\n// swallowed\n', ".js")
    assert got == []


def test_tsx_runs_js_machine():
    src = ('export function B() {\n'
           '  // jsx comment\n'
           '  return <div>Step 1 of 3</div>;\n'
           '}\n')
    assert ce.extract(src, ".tsx") == [(2, "// jsx comment", ce.COMMENT)]


def test_c_char_literals_do_not_open_strings():
    src = ("char q = '\"';\n"
           "char e = '\\'';\n"
           "// after chars\n"
           "int x = 1; /* trail */\n")
    got = ce.extract(src, ".c")
    assert got == [(3, "// after chars", ce.COMMENT),
                   (4, "/* trail */", ce.COMMENT)]


def test_rust_nested_block_and_lifetime():
    src = ("// line\n"
           "/* outer /* inner */ still outer */\n"
           "let lt: &'a str = s;\n"
           "// after lifetime\n")
    got = ce.extract(src, ".rs")
    assert got == [
        (1, "// line", ce.COMMENT),
        (2, "/* outer /* inner */ still outer */", ce.COMMENT),
        (4, "// after lifetime", ce.COMMENT),
    ]


def test_exotic_string_form_skips_whole_file():
    java = 'String s = """\n// looks like a comment\n""";\n// real comment\n'
    assert ce.extract(java, ".java") == []
    rust = 'let s = r#"// text"#;\n// real\n'
    assert ce.extract(rust, ".rs") == []


def test_go_raw_backtick_is_opaque():
    src = "// go comment\nvar s = `// not a comment`\n// after\n"
    got = ce.extract(src, ".go")
    assert got == [(1, "// go comment", ce.COMMENT),
                   (3, "// after", ce.COMMENT)]


def test_shell_heredoc_body_skipped():
    src = ("#!/bin/bash\n"
           "# real comment\n"
           "cat <<'EOF'\n"
           "# not a comment\n"
           "EOF\n"
           "echo done # trailing\n")
    got = ce.extract(src, ".sh")
    assert got == [(1, "#!/bin/bash", ce.COMMENT),
                   (2, "# real comment", ce.COMMENT),
                   (6, "# trailing", ce.COMMENT)]


def test_sql_doubled_quote_stays_in_string():
    src = ("-- top comment\n"
           "SELECT 'it''s -- not a comment' AS x;\n"
           "-- after\n")
    got = ce.extract(src, ".sql")
    assert got == [(1, "-- top comment", ce.COMMENT),
                   (3, "-- after", ce.COMMENT)]


def test_conservative_and_unknown_ext_extract_nothing():
    assert ce.extract("# ruby comment\nx = /a#b/\n", ".rb") == []
    assert ce.extract("// whatever\n", ".xyz") == []
    assert ce.extract("", ".js") == []


def test_lenient_line_start_only_and_shebang_skip():
    src = ('#!/usr/bin/env python3\n'
           '"""Module doc."""\n'
           '# top comment\n'
           'x = 1  # inline\n')
    got = ce.extract_lenient(src, ".py")
    assert got == [(3, "# top comment", ce.COMMENT)]


def test_lenient_counts_template_line_documented_fp():
    src = ('const t = `// not a comment either\n'
           '// still template`;\n'
           '// after\n')
    got = ce.extract_lenient(src, ".js")
    assert got == [(2, "// still template`;", ce.COMMENT),
                   (3, "// after", ce.COMMENT)]


def test_lenient_covers_conservative_and_unknown_ext():
    assert ce.extract_lenient("# ruby comment\n", ".rb") == \
        [(1, "# ruby comment", ce.COMMENT)]
    assert ce.extract_lenient("// whatever\n", ".xyz") == \
        [(1, "// whatever", ce.COMMENT)]


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

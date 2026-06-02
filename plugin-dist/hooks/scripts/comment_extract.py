#!/usr/bin/env python3
"""Zero-false-positive comment + docstring extraction for source linting.

Used by `comment-discipline-reminder.py` to find comments/docstrings reliably,
so a downstream marker check never fires on text that only LOOKS like a comment
(a URL inside a string, a `#` inside a regex, etc.).

Design contract — fail to SILENCE, never to EMIT:
- Python (.py/.pyi): exact, via stdlib `tokenize` (comments, incl. inline) and
  `ast` (docstrings — module/def/async def/class). A data string `x = "Phase 2"`
  is NOT a docstring; `ast.get_docstring` only returns a real docstring.
- Other languages: a string/char/template-aware state machine that emits a
  comment only when it is certain it is outside every string-like construct. If
  the file uses a string form this module does not model (heredocs, raw strings,
  Lua long brackets, C# verbatim, Java/Kotlin/Swift/Scala text blocks), the whole
  file is skipped — those bodies can span lines and hold comment-like text, so
  the safe move is to extract nothing. Incomplete coverage degrades to a missed
  comment (false negative), never to a misread one (false positive).
- Mixed-syntax / regex-heavy files where inline detection cannot be proven
  FP-free (JSX/TSX/Vue/Svelte HTML text, Ruby `#`-in-regex) are skipped for the
  same reason.

Return shape: `extract(text, ext)` -> list of (lineno, text, kind) where
kind is "comment" or "docstring"; lineno is 1-based. Returns [] on anything
unparseable. Never raises.
"""

import ast
import io
import re
import tokenize

# kinds
COMMENT = "comment"
DOCSTRING = "docstring"

PY_EXT = {".py", ".pyi"}

# Extensions that get LINE-START-only extraction (still zero-FP): inline/block
# detection here cannot be proven FP-free without a real parser.
#   jsx/tsx/vue/svelte: HTML/JSX text outside strings can contain `//` or `/* */`
#   rb: `#` can sit inside a `/regex/` or `%r{}` literal
CONSERVATIVE_EXT = {".jsx", ".tsx", ".vue", ".svelte", ".rb"}


def _profile(line, block=None, nests=False, backtick=None, strings="\"'",
             char=False, lifetime=False, sql_double=False, no_escape="",
             exotic=None):
    return {
        "line": tuple(line),
        "block": block,                 # (open, close) or None
        "nests": nests,                 # block comment nests (Rust/Swift/Kotlin)
        "backtick": backtick,           # 'opaque' to skip `...` (JS template / Go raw / Kotlin id)
        "strings": set(strings),        # delimiters that open a string
        "char": char,                   # ' is a char literal (C-family) — match '\\?.'
        "lifetime": lifetime,           # Rust: a lone ' may be a lifetime, not a char
        "sql_double": sql_double,       # '' inside a '-string is an escaped quote
        "no_escape": set(no_escape),    # delimiters where backslash is NOT an escape
        "exotic": re.compile(exotic) if exotic else None,  # presence -> line-start fallback
    }


# Per-extension language profiles for the generic scanner. Anything not listed
# and not Python and not conservative is treated with a safe default (// and
# /* */, double+single quoted strings) — but unknown extensions are simply not
# scanned by the caller, so this only applies to the set below.
_C_BLOCK = ("/*", "*/")
LANG_PROFILES = {
    # C family — ' is a char literal; C++ raw strings R"(...)" force fallback.
    ".c":   _profile(("//",), _C_BLOCK, char=True),
    ".h":   _profile(("//",), _C_BLOCK, char=True),
    ".cc":  _profile(("//",), _C_BLOCK, char=True, exotic=r'R"'),
    ".cpp": _profile(("//",), _C_BLOCK, char=True, exotic=r'R"'),
    ".hpp": _profile(("//",), _C_BLOCK, char=True, exotic=r'R"'),
    ".cs":  _profile(("//",), _C_BLOCK, char=True, exotic=r'@"|\$@"'),
    ".java": _profile(("//",), _C_BLOCK, char=True, exotic=r'"""'),
    ".kt":  _profile(("//",), _C_BLOCK, nests=True, backtick="opaque", char=True,
                     exotic=r'"""'),
    ".kts": _profile(("//",), _C_BLOCK, nests=True, backtick="opaque", char=True,
                     exotic=r'"""'),
    ".swift": _profile(("//",), _C_BLOCK, nests=True, exotic=r'#"|"""'),
    ".scala": _profile(("//",), _C_BLOCK, char=True, exotic=r'"""'),
    ".dart": _profile(("//",), _C_BLOCK, exotic=r"r'|r\"|'''|\"\"\""),
    ".go":  _profile(("//",), _C_BLOCK, backtick="opaque", char=True),
    ".rs":  _profile(("//",), _C_BLOCK, nests=True, char=True, lifetime=True,
                     exotic=r'r#*"|b"'),
    ".php": _profile(("//", "#"), _C_BLOCK, exotic=r"<<<"),
    # JS/TS — backtick is a template (opaque); empty-regex // is the one
    # documented theoretical residual (no practical occurrence in real code).
    ".js":  _profile(("//",), _C_BLOCK, backtick="opaque"),
    ".mjs": _profile(("//",), _C_BLOCK, backtick="opaque"),
    ".cjs": _profile(("//",), _C_BLOCK, backtick="opaque"),
    ".ts":  _profile(("//",), _C_BLOCK, backtick="opaque"),
    # SQL — '-string with '' doubling; no backslash escape.
    ".sql": _profile(("--",), _C_BLOCK, strings="'", sql_double=True, no_escape="'"),
    # Shell — # comments; '-string has no escape; backtick = command subst (opaque);
    # heredoc forces fallback.
    ".sh":   _profile(("#",), None, backtick="opaque", no_escape="'", exotic=r"<<[-~]?\s*\\?\w"),
    ".bash": _profile(("#",), None, backtick="opaque", no_escape="'", exotic=r"<<[-~]?\s*\\?\w"),
    ".zsh":  _profile(("#",), None, backtick="opaque", no_escape="'", exotic=r"<<[-~]?\s*\\?\w"),
    # Lua — -- comments; long-bracket [[...]] / --[[...]] forces fallback.
    ".lua": _profile(("--",), None, exotic=r"--\[\[|\[=*\[|\[\["),
}

_CHAR_LIT_RE = re.compile(r"'(?:\\.|[^'\\\n])'")


def extract(text, ext):
    """Return [(lineno, text, kind), ...]. Never raises."""
    try:
        if not text:
            return []
        if ext in PY_EXT:
            return _extract_python(text)
        if ext in CONSERVATIVE_EXT:
            # JSX/HTML text or a Ruby regex can hold comment-like text outside any
            # string; without a real parser that cannot be told from a comment, so
            # extract nothing rather than risk a false positive.
            return []
        prof = LANG_PROFILES.get(ext)
        if prof is None:
            return []
        if prof["exotic"] and prof["exotic"].search(text):
            # A string form we do not model (heredoc, raw string, text block) is
            # present; its body can span lines and contain comment-like text, so
            # fail to silence — extract nothing from this file.
            return []
        return _extract_generic(text, prof)
    except Exception:
        return []


def _line_leaders(ext):
    if ext in PY_EXT or ext == ".rb":
        return ("#",)
    prof = LANG_PROFILES.get(ext)
    if prof:
        return prof["line"]
    return ("//",)  # jsx/tsx/vue/svelte and any default


def extract_lenient(text, ext):
    """Line-START comments only — a low-stakes signal for the generic nudge.

    Not FP-free (a line inside a multi-line string that begins with a comment
    leader is counted), but the generic layer only says "you added comments,
    check them", never "this is leakage" — so a rare miscount is a harmless
    nudge, and this keeps coverage on files the airtight extractor skips
    (.tsx/.rb, heredoc files). Never feed this looser signal to the targeted
    detector.
    """
    try:
        leaders = _line_leaders(ext)
        out = []
        for n, line in enumerate(text.split("\n"), 1):
            s = line.lstrip()
            for d in leaders:
                if s.startswith(d) and not (d == "#" and s.startswith("#!")):
                    out.append((n, s, COMMENT))
                    break
        return out
    except Exception:
        return []


def _extract_python(src):
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                out.append((tok.start[0], tok.string, COMMENT))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        pass  # partial comments collected so far are still valid
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    out.append((node.body[0].lineno, doc, DOCSTRING))
    except (SyntaxError, ValueError):
        pass
    return out


def _extract_generic(src, p):
    out = []
    n = len(src)
    i = 0
    lineno = 1
    line_delims = p["line"]
    block = p["block"]
    bopen, bclose = (block if block else (None, None))
    nests = p["nests"]
    backtick = p["backtick"]
    strings = p["strings"]
    char = p["char"]
    lifetime = p["lifetime"]
    sql_double = p["sql_double"]
    no_escape = p["no_escape"]

    def starts(s):
        return src.startswith(s, i)

    while i < n:
        c = src[i]

        # line comment -> to end of line
        hit = None
        for d in line_delims:
            if starts(d):
                hit = d
                break
        if hit is not None:
            j = src.find("\n", i)
            if j == -1:
                j = n
            out.append((lineno, src[i:j].rstrip(), COMMENT))
            i = j
            continue

        # block comment
        if bopen and starts(bopen):
            start_line = lineno
            buf = [bopen]
            i += len(bopen)
            depth = 1
            while i < n and depth > 0:
                if nests and starts(bopen):
                    depth += 1
                    buf.append(bopen)
                    i += len(bopen)
                    continue
                if starts(bclose):
                    depth -= 1
                    buf.append(bclose)
                    i += len(bclose)
                    continue
                if src[i] == "\n":
                    lineno += 1
                buf.append(src[i])
                i += 1
            out.append((start_line, "".join(buf), COMMENT))
            continue

        # backtick: opaque skip (JS template / Go raw / Kotlin identifier)
        if backtick and c == "`":
            i += 1
            while i < n:
                ch = src[i]
                if ch == "\\":
                    i += 2
                    continue
                if ch == "\n":
                    lineno += 1
                if ch == "`":
                    i += 1
                    break
                i += 1
            continue

        # char literal (C-family) — and Rust lifetime disambiguation
        if char and c == "'":
            m = _CHAR_LIT_RE.match(src, i)
            if m:
                i = m.end()
                continue
            if lifetime:
                # a lone ' is a Rust lifetime, not a string — treat as ordinary
                i += 1
                continue
            # non-lifetime language: ' that is not a char literal — ordinary char
            i += 1
            continue

        # string
        if c in strings:
            delim = c
            esc = delim not in no_escape
            i += 1
            while i < n:
                ch = src[i]
                if esc and ch == "\\":
                    i += 2
                    continue
                if sql_double and ch == delim and i + 1 < n and src[i + 1] == delim:
                    i += 2
                    continue
                if ch == delim:
                    i += 1
                    break
                if ch == "\n":
                    lineno += 1
                i += 1
            continue

        # Backslash escapes the next char even in code: this keeps an escaped
        # slash in a JS/TS regex literal (`/https?:\/\//`) from forming a stray
        # `//`. Inside a regex every `/` is either escaped or closes it, so the
        # only residual is the empty regex `//`, which has no real-code use.
        if c == "\\":
            if i + 1 < n and src[i + 1] == "\n":
                lineno += 1
            i += 2
            continue

        if c == "\n":
            lineno += 1
        i += 1

    return out

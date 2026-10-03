#!/usr/bin/env python3
"""Extract bounded literal read intent; never execute or inspect source content.

Accepted shell grammar is a sequence of simple commands separated by ``;``,
newlines, or ``&&``, optionally with pipelines of supported readers. Readers
are cat, head/tail with bounded known option syntax, sed -n with one numeric
print expression, and rg with explicit operands and known options. Quoted and
escaped literal words are accepted. This is not a shell interpreter: variables,
substitutions, redirections, here-documents, unquoted glob/brace/tilde expansion,
background jobs, OR lists, groups, wrappers, and shell control flow are omitted.
Unsafe or malformed shell syntax makes the entire command silent. Unsupported
simple commands are ignored and make subsequent relative cwd attribution unknown.

An absolute literal ``cd PATH && reader`` sets cwd only on that success branch.
After its chain ends, cwd is unknown because cd may have failed. A cd in a pipe
makes that pipeline silent. Relative reads require an explicitly absolute cwd;
absolute reads remain useful when cwd is unknown. Paths are lexical intent,
not claims about file existence, symlink resolution, or actual command execution.

Calls have no IO, subprocess, network, state, environment, or content reads.
Commands over 32768 UTF-8 bytes, 512 tokens, 64 simple commands, 128 unique
targets, or paths over 4096 UTF-8 bytes return no targets (never a partial list).
"""

from __future__ import annotations

import posixpath
import re


MAX_COMMAND_BYTES = 32768
MAX_TOKENS = 512
MAX_SEGMENTS = 64
MAX_TARGETS = 128
MAX_PATH_BYTES = 4096
_SHELL_CONTROL = {"if", "then", "elif", "else", "fi", "for", "while", "until", "do", "done",
                  "case", "esac", "select", "function", "!", "time", "coproc"}


def _tokens(command: str) -> list[tuple[str, str]] | None:
    """Tokenize only a deliberately literal shell subset, preserving separators."""
    tokens: list[tuple[str, str]] = []
    word: list[str] = []
    started = False
    quote: str | None = None
    index = 0

    def flush() -> None:
        nonlocal started
        if started:
            tokens.append(("word", "".join(word)))
            word.clear()
            started = False

    while index < len(command):
        char = command[index]
        if char == "\x00" or (ord(char) < 32 and char not in "\n\t\r"):
            return None
        if quote == "'":
            if char == "'":
                quote = None
            else:
                word.append(char)
        elif char == "\\":
            index += 1
            if index == len(command) or command[index] in "\n\r":
                return None
            following = command[index]
            # Inside double quotes only these characters lose their backslash.
            if quote == '"' and following not in '$`"\\':
                word.append("\\")
            word.append(following)
            started = True
        elif quote == '"':
            if char == '"':
                quote = None
            elif char in "$`":
                return None
            else:
                word.append(char)
        elif char in "'\"":
            quote = char
            started = True
        elif char in "$`<>()[*?]{}~" or (char == "#" and not started):
            return None
        elif char in " \t\r":
            flush()
        elif char in ";\n|&":
            flush()
            if char == "&":
                if command[index : index + 2] != "&&":
                    return None
                index += 1
                char = "&&"
            elif char == "|" and command[index : index + 2] in {"||", "|&"}:
                return None
            tokens.append(("op", char))
        else:
            word.append(char)
            started = True
        if len(tokens) > MAX_TOKENS:
            return None
        index += 1
    if quote:
        return None
    flush()
    return tokens if len(tokens) <= MAX_TOKENS else None


def _absolute(path: str, cwd: str | None) -> str | None:
    if not path or path == "-":
        return None
    if len(path.encode("utf-8")) > MAX_PATH_BYTES:
        raise ValueError("path limit")
    if not posixpath.isabs(path):
        if cwd is None:
            return None
        path = posixpath.join(cwd, path)
    path = posixpath.normpath(path)
    if len(path.encode("utf-8")) > MAX_PATH_BYTES:
        raise ValueError("path limit")
    return path


def _plain_files(args: list[str], flags: set[str]) -> list[str] | None:
    files: list[str] = []
    options = True
    for arg in args:
        if options and arg == "--":
            options = False
        elif options and arg.startswith("-") and arg != "-":
            if arg not in flags and not (
                not arg.startswith("--")
                and all("-" + char in flags for char in arg[1:])
            ):
                return None
        else:
            files.append(arg)
    return files


def _head_tail_files(args: list[str]) -> list[str] | None:
    files: list[str] = []
    options = True
    index = 0
    while index < len(args):
        arg = args[index]
        if options and arg == "--":
            options = False
        elif options and arg in {"-n", "-c", "--lines", "--bytes"}:
            index += 1
            if index >= len(args) or not re.fullmatch(r"[+-]?\d+", args[index]):
                return None
        elif options and re.fullmatch(r"(?:-[nc]|--(?:lines|bytes)=)[+-]?\d+|-\d+", arg):
            pass
        elif options and arg in {"-q", "-v", "--quiet", "--silent", "--verbose"}:
            pass
        elif options and arg.startswith("-") and arg != "-":
            return None
        else:
            files.append(arg)
        index += 1
    return files


# Unknown rg options fail closed: their operands must never become read targets.
_RG_FLAGS = {
    "--hidden", "--no-ignore", "--no-ignore-vcs", "--no-ignore-parent",
    "--no-ignore-global", "--no-ignore-dot", "--ignore-case", "--case-sensitive",
    "--smart-case", "--fixed-strings", "--line-number", "--no-line-number",
    "--with-filename", "--no-filename", "--files-with-matches",
    "--files-without-match", "--count", "--count-matches", "--only-matching",
    "--invert-match", "--word-regexp", "--line-regexp", "--multiline",
    "--multiline-dotall", "--pcre2", "--text", "--binary", "--follow",
    "--quiet", "--no-messages", "--trim", "--stats", "--json", "--heading",
    "--no-heading", "--passthru", "--crlf", "--null", "--null-data",
    "--no-unicode", "--unicode", "--one-file-system", "--no-config",
}
_RG_VALUES = {
    "--glob", "--iglob", "--type", "--type-not", "--type-add", "--type-clear",
    "--max-count", "--max-depth", "--max-filesize", "--max-columns",
    "--threads", "--encoding", "--engine", "--color", "--colors", "--sort",
    "--sortr", "--after-context", "--before-context", "--context", "--replace",
    "--context-separator", "--field-context-separator", "--field-match-separator",
    "--path-separator", "--regex-size-limit", "--dfa-size-limit",
}
_RG_SHORT_FLAGS = frozenset("niIsSFHvwlLcoqxUaPz0Nu")
_RG_SHORT_VALUES = frozenset("gtdmMjABC r".replace(" ", ""))


def _rg_files(args: list[str]) -> list[str] | None:
    operands: list[str] = []
    extra_reads: list[str] = []
    explicit_pattern = False
    options = True
    index = 0
    while index < len(args):
        arg = args[index]
        value_option: str | None = None
        value: str | None = None
        if options and arg == "--":
            options = False
        elif options and arg.startswith("--"):
            option, equal, attached = arg.partition("=")
            if option in _RG_FLAGS and not equal:
                pass
            elif option in _RG_VALUES | {"--regexp", "--file", "--ignore-file"}:
                value_option = option
                value = attached if equal else None
            else:
                # --pre can execute arbitrary code; --files has no pattern.
                return None
        elif options and arg.startswith("-") and arg != "-":
            cluster = arg[1:]
            for offset, flag in enumerate(cluster):
                if flag in _RG_SHORT_FLAGS:
                    continue
                if flag in _RG_SHORT_VALUES | {"e", "f"}:
                    value_option = "-" + flag
                    value = cluster[offset + 1 :] or None
                    break
                return None
        else:
            operands.append(arg)
        if value_option:
            if value is None:
                index += 1
                if index >= len(args):
                    return None
                value = args[index]
            if value_option in {"-e", "--regexp", "-f", "--file"}:
                explicit_pattern = True
            if value_option in {"-f", "--file", "--ignore-file"}:
                extra_reads.append(value)
        index += 1
    if not explicit_pattern:
        if not operands:
            return None
        operands = operands[1:]  # First positional argument is always the pattern.
    return extra_reads + operands


def _reader_files(argv: list[str]) -> list[str] | None:
    executable = posixpath.basename(argv[0])
    args = argv[1:]
    if executable == "cat":
        return _plain_files(args, {"-n", "-b", "-s", "-v", "-E", "-T", "-A", "-e", "-t",
                                   "--number", "--number-nonblank", "--squeeze-blank",
                                   "--show-nonprinting", "--show-ends", "--show-tabs", "--show-all"})
    if executable in {"head", "tail"}:
        return _head_tail_files(args)
    if executable == "rg":
        return _rg_files(args)
    if executable == "sed":
        if not args or args[0] != "-n":
            return None
        args = args[1:]
        if args and args[0] == "-e":
            args = args[1:]
        if not args or not re.fullmatch(r"(?:(?:\d+|\$)(?:,(?:\d+|\$))?)?p", args[0]):
            return None
        return _plain_files(args[1:], set())
    return None


def _commands(tokens: list[tuple[str, str]]) -> list[tuple[list[str], str | None]]:
    commands: list[tuple[list[str], str | None]] = []
    current: list[str] = []
    for kind, value in tokens:
        if kind == "word":
            current.append(value)
        elif current:
            commands.append((current, value))
            current = []
        elif value != "\n":
            raise ValueError("empty command")
        # A newline after && or | is a continuation, otherwise a blank line.
    if current:
        commands.append((current, None))
    elif commands and commands[-1][1] in {"&&", "|"}:
        raise ValueError("missing continuation")
    if len(commands) > MAX_SEGMENTS:
        raise ValueError("command count limit")
    if any(argv[0] in _SHELL_CONTROL for argv, _ in commands):
        raise ValueError("shell control flow")
    return commands


def read_targets(command: str, cwd: str | None) -> list[str]:
    """Return deduplicated absolute literal targets, or [] on a grammar/size limit."""
    if not isinstance(command, str):
        return []
    try:
        if len(command.encode("utf-8")) > MAX_COMMAND_BYTES:
            return []
        tokens = _tokens(command)
        if not tokens:
            return []
        base = _absolute(cwd, None) if isinstance(cwd, str) else None
        commands = _commands(tokens)
        result: list[str] = []
        seen: set[str] = set()
        chain_cd = False
        index = 0
        while index < len(commands):
            end = index
            while commands[end][1] == "|":
                end += 1
            pipeline = commands[index : end + 1]
            has_cd = any(posixpath.basename(argv[0]) == "cd" for argv, _ in pipeline)
            if len(pipeline) > 1 and (has_cd or any(_reader_files(argv) is None for argv, _ in pipeline)):
                base = None
                chain_cd = True
            else:
                for argv, separator in pipeline:
                    if argv[0] == "cd":
                        target = argv[1] if len(argv) == 2 else None
                        base = (_absolute(target, None) if target and separator == "&&" else None)
                        chain_cd = True
                        continue
                    files = _reader_files(argv)
                    if files is None:
                        base = None
                        continue
                    for file in files:
                        path = _absolute(file, base)
                        if path is not None and path not in seen:
                            seen.add(path)
                            result.append(path)
                            if len(result) > MAX_TARGETS:
                                return []
            if commands[end][1] in {";", "\n", None} and chain_cd:
                base = None
                chain_cd = False
            index = end + 1
        return result
    except (UnicodeError, ValueError, TypeError):
        return []


def candidate_skill(relative_path: str) -> str | None:
    """Suggest a narrow skill; caller must verify React for frontend candidates.

    Testing paths take priority. Backend suggestions require both an explicit
    backend directory and a language suffix; generic paths have no guess.
    TSX/JSX only suggest frontend; they do not establish a React project.
    """
    if not isinstance(relative_path, str) or not relative_path:
        return None
    path = posixpath.normpath(relative_path.replace("\\", "/"))
    if path.startswith("/") or path == ".." or path.startswith("../"):
        return None
    parts = path.lower().split("/")
    filename = parts[-1]
    if any(part in {"test", "tests", "__tests__", "spec", "specs"} for part in parts) or (
        filename.startswith("test_") or filename.endswith(("_test.py", "_test.go"))
        or re.search(r"\.(?:test|spec)\.[cm]?[jt]sx?$", filename)
        or path.startswith(".github/workflows/") or filename == ".gitlab-ci.yml"
    ):
        return "mainframe-testing"
    if filename.endswith((".tsx", ".jsx")):
        return "mainframe-frontend"
    if not any(part in {"backend", "backends", "server", "servers", "api"} for part in parts[:-1]):
        return None
    if filename.endswith(".py"):
        return "mainframe-python-backend"
    if filename.endswith(".go"):
        return "mainframe-go-backend"
    if filename.endswith((".ts", ".mts", ".cts")):
        return "mainframe-typescript-backend"
    return None

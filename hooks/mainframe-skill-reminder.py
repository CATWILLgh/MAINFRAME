#!/usr/bin/env python3
"""Extract bounded literal read/operation intent without execution or source IO.

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

The separate ``operation_skills`` API reuses that literal grammar for narrow
credential, HTTP transfer, cluster, infrastructure and test-runner candidates.
Its documented wrapper subset does not expand the read-target grammar.
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


MAX_OPERATION_DEPTH = 6
_HELP_VERSION = {"--help", "-h", "--version", "-V"}


def _operation_operands(
    args: list[str], flags: set[str], values: set[str],
    option_values: dict[str, list[str]] | None = None,
) -> list[str] | None:
    """Separate known options from literal operands; unknown syntax is silent."""
    operands: list[str] = []
    index = 0
    options = True
    while index < len(args):
        arg = args[index]
        option: str | None = None
        value: str | None = None
        if options and arg == "--":
            options = False
        elif options and arg.startswith("--"):
            name, equal, attached = arg.partition("=")
            if name in flags and not equal:
                pass
            elif name in values:
                option, value = name, attached if equal else None
            else:
                return None
        elif options and arg.startswith("-") and arg != "-":
            for offset, letter in enumerate(arg[1:]):
                name = "-" + letter
                if name in flags:
                    continue
                if name in values:
                    option, value = name, arg[offset + 2 :] or None
                    break
                return None
        else:
            operands.append(arg)
        if option is not None:
            if value is None:
                index += 1
                if index == len(args):
                    return None
                value = args[index]
            protocol_mask = option in {"--proto", "--proto-redir"} and re.fullmatch(
                r"[=+-]?[A-Za-z0-9]+(?:,[=+-]?[A-Za-z0-9]+)*", value
            )
            if not value or (value.startswith("-") and not protocol_mask):
                return None
            if option_values is not None:
                option_values.setdefault(option, []).append(value)
            if option == "--url":
                operands.append(value)
        index += 1
    return operands


def _curl_transfer(args: list[str]) -> bool:
    operands = _operation_operands(
        args,
        {"-f", "-s", "-S", "-I", "-L", "-k", "-v", "-i", "-O", "-N", "-q", "--disable",
         "--fail", "--fail-with-body", "--silent", "--show-error", "--head",
         "--location", "--insecure", "--verbose", "--include", "--compressed",
         "--remote-name", "--no-buffer", "--http1.1", "--http2"},
        {"-X", "-H", "-d", "-o", "-u", "-A", "-m", "-T", "-F", "-b", "-c", "-w",
         "--request", "--header", "--data", "--data-raw", "--data-binary", "--data-urlencode",
         "--output", "--user", "--user-agent", "--max-time", "--connect-timeout",
         "--retry", "--retry-delay", "--upload-file", "--form", "--cookie",
         "--cookie-jar", "--cacert", "--cert", "--key", "--url", "--proto",
         "--proto-redir", "--write-out", "--max-redirs"},
    )
    # Every positional operand is a transfer URL, not a guessed default protocol.
    return bool(operands) and all(re.fullmatch(r"https?://[^/\s?#]+(?:[^\s]*)", url) for url in operands)


def _clickhouse_operation(args: list[str], piped_input: bool) -> bool:
    """Recognize explicit native-client input, without reading SQL or config."""
    option_values: dict[str, list[str]] = {}
    operands = _operation_operands(
        args,
        {"--secure", "--multiquery", "-n", "--multiline", "-m", "--time", "-t", "--vertical", "-E"},
        {"--query", "-q", "--queries-file", "--host", "--port", "--user", "-u", "--password",
         "--database", "-d", "--format", "-f", "--input-format", "--output-format", "--query_id",
         "--max_execution_time", "--max_result_rows", "--max_result_bytes", "--max_memory_usage", "--readonly"},
        option_values,
    )
    return operands == [] and (piped_input or bool(
        option_values.keys() & {"--query", "-q", "--queries-file"}
    ))


def _codex_peer_operation(args: list[str]) -> bool:
    """Match documented headless syntax; relevance never establishes authority."""
    if not args or args[0] != "exec":
        return False
    option_values: dict[str, list[str]] = {}
    operands = _operation_operands(
        args[1:], {"--json"},
        {"-C", "--cd", "-s", "--sandbox", "-o", "--output-last-message"},
        option_values,
    )
    if not operands or any(not operand for operand in operands):
        return False
    if any(value not in {"read-only", "workspace-write", "danger-full-access"}
           for option in {"-s", "--sandbox"} for value in option_values.get(option, [])):
        return False
    if operands[0] == "resume":
        if "--" in args:
            prefix = _operation_operands(
                args[1:args.index("--")], {"--json"},
                {"-C", "--cd", "-s", "--sandbox", "-o", "--output-last-message"},
            )
            if not prefix or prefix[0] != "resume":
                return False  # A word after -- is prompt data, not a subcommand.
        return len(operands) in {2, 3} and bool(re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", operands[1]
        ))
    # One literal prompt or explicit '-' input; implicit input and other native
    # subcommands are outside this route, as are most-recent/name-based resumes.
    return len(operands) == 1 and operands[0] not in {"help", "review"}


def _ssh_remote(args: list[str]) -> str | None:
    index = 0
    while index < len(args) and args[index].startswith("-"):
        arg = args[index]
        if arg == "--":
            index += 1
            break
        if arg in {"-T", "-t", "-n", "-q", "-v", "-vv", "-vvv", "-4", "-6"}:
            index += 1
            continue
        if arg not in {"-p", "-l", "-i", "-o"} or index + 1 == len(args):
            return None
        value = args[index + 1]
        if not value or value.startswith("-"):
            return None
        if arg == "-p" and not re.fullmatch(r"\d{1,5}", value):
            return None
        if arg == "-o" and value.partition("=")[0] not in {
            "BatchMode", "ConnectTimeout", "StrictHostKeyChecking", "UserKnownHostsFile",
            "LogLevel", "IdentitiesOnly", "ServerAliveInterval",
        }:
            return None
        if arg == "-o" and "=" not in value:
            return None
        index += 2
    # OpenSSH joins command operands, losing their original quoting. Only one
    # literal remote shell string can be reparsed without inventing that syntax.
    if len(args) - index != 2 or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]*", args[index]):
        return None
    return args[index + 1]


def _k3s_operation(args: list[str]) -> bool:
    if not args:
        return False
    if args[0] in {"server", "agent"}:
        return True
    if args[0] == "etcd-snapshot":
        return len(args) > 1 and args[1] in {"save", "list", "delete", "prune"}
    if args[0] != "kubectl":
        return False
    operands = _operation_operands(
        args[1:],
        {"-A", "--all-namespaces", "--all", "--no-headers", "--show-labels",
         "--ignore-daemonsets", "--delete-emptydir-data", "--force", "--watch", "-w"},
        {"-n", "--namespace", "-o", "--output", "-l", "--selector", "--context",
         "--kubeconfig", "--request-timeout", "--timeout", "--grace-period", "--field-selector"},
    )
    if not operands:
        return False
    if operands[0] in {"drain", "cordon", "uncordon"}:
        return len(operands) >= 2
    if operands[0] == "cluster-info":
        return len(operands) == 1
    resources = {"node", "nodes", "no", "namespace", "namespaces", "ns",
                 "persistentvolume", "persistentvolumes", "pv", "storageclass", "storageclasses", "sc",
                 "customresourcedefinition", "customresourcedefinitions", "crd", "crds",
                 "clusterrole", "clusterroles", "clusterrolebinding", "clusterrolebindings"}
    if operands[0] not in {"get", "describe", "delete", "taint", "label", "annotate"} or len(operands) < 2:
        return False
    return all(resource in resources for resource in operands[1].split(","))


def _infrastructure_operation(executable: str, args: list[str]) -> bool:
    if executable == "terraform":
        if args and args[0].startswith("-chdir="):
            if args[0] == "-chdir=":
                return False
            args = args[1:]
        return bool(args) and args[0] in {
            "init", "plan", "apply", "destroy", "validate", "fmt", "show", "output",
            "state", "workspace", "import", "refresh", "taint", "untaint", "providers",
        }
    if executable != "docker":
        return False
    index = 0
    while index < len(args) and args[index].startswith("-"):
        arg = args[index]
        if arg in {"--tls", "--tlsverify", "-D", "--debug"}:
            index += 1
        elif arg in {"--context", "-c", "--host", "-H", "--config", "--tlscacert", "--tlscert", "--tlskey"}:
            if index + 1 == len(args) or not args[index + 1] or args[index + 1].startswith("-"):
                return False
            index += 2
        elif any(arg.startswith(option + "=") and arg != option + "=" for option in {"--context", "--host", "--config"}):
            index += 1
        else:
            return False
    args = args[index:]
    if not args:
        return False
    if args[0] == "compose":
        # Only parse Compose global options before its subcommand. Operation
        # options belong to that subcommand and do not need to become operands.
        for offset, arg in enumerate(args[1:]):
            if arg in {"up", "down", "start", "stop", "restart", "ps", "logs", "build", "pull", "push", "config", "exec", "run"}:
                prefix = _operation_operands(args[1:offset + 1], {"--compatibility"},
                                              {"-f", "--file", "-p", "--project-name", "--profile", "--project-directory"})
                return prefix == []
        return False
    resource_operations = {
        "container": {"ls", "inspect", "logs", "run", "exec", "start", "stop", "restart", "kill", "rm", "prune"},
        "image": {"ls", "inspect", "build", "pull", "push", "rm", "prune", "tag"},
        "network": {"ls", "inspect", "create", "rm", "prune", "connect", "disconnect"},
        "volume": {"ls", "inspect", "create", "rm", "prune"},
        "system": {"df", "info", "prune"},
    }
    if args[0] in resource_operations:
        return len(args) >= 2 and args[1] in resource_operations[args[0]]
    return args[0] in {"ps", "inspect", "logs", "run", "exec", "start", "stop", "restart", "kill",
                       "build", "pull", "push", "info", "stats", "wait", "rm", "rmi", "images"}


def _operation_argv(
    argv: list[str], depth: int, remote: bool, budget: list[int], piped_input: bool = False,
) -> set[str]:
    if depth > MAX_OPERATION_DEPTH:
        raise ValueError("wrapper depth limit")
    if not argv or any(arg in _HELP_VERSION for arg in argv[1:]):
        return set()
    executable, args = posixpath.basename(argv[0]), argv[1:]
    if executable == "sudo":
        if not args or args[0] != "-n":
            return set()
        consumer = args[2:] if len(args) > 1 and args[1] == "--" else args[1:]
        return _operation_argv(consumer, depth + 1, remote, budget, piped_input)
    if executable == "ssh":
        command = _ssh_remote(args)
        return _operation_sequence(command, depth + 1, True, budget) if command else set()
    if executable == "mainframe-secret":
        if not args:
            return set()
        valid_name = lambda name: bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", name))
        if args[0] == "run" and "--" in args:
            boundary = args.index("--")
            if boundary < 2 or boundary + 1 == len(args) or not all(valid_name(name) for name in args[1:boundary]):
                return set()
            return {"mainframe-secrets"} | _operation_argv(args[boundary + 1:], depth + 1, remote, budget, piped_input)
        if (args[0] in {"list", "edit"} and len(args) == 1) or (
            args[0] in {"get", "copy", "del"} and len(args) == 2 and valid_name(args[1])
        ) or (args[0] == "set" and len(args) == 3 and valid_name(args[1]) and args[2] in {"--clipboard", "--prompt"}):
            return {"mainframe-secrets"}
        return set()
    if executable == "curl" and _curl_transfer(args):
        return {"mainframe-curl-requests"}
    if executable == "clickhouse-client" or (executable == "clickhouse" and args and args[0] == "client"):
        client_args = args[1:] if executable == "clickhouse" else args
        return {"mainframe-clickhouse"} if _clickhouse_operation(client_args, piped_input) else set()
    if executable == "codex" and _codex_peer_operation(args):
        return {"mainframe-peer-work"}
    if executable == "k3s" and _k3s_operation(args):
        return {"mainframe-k3s"}
    if executable == "systemctl" and len(args) == 2 and args[0] in {"start", "stop", "restart", "status", "show", "is-active"} and args[1] in {"k3s", "k3s.service", "k3s-agent", "k3s-agent.service"}:
        return {"mainframe-k3s"}
    if _infrastructure_operation(executable, args):
        return {"mainframe-infrastructure"}
    if executable in {"pytest", "py.test", "jest", "vitest"} or (
        executable in {"go", "cargo", "npm"} and args and args[0] == "test"
    ) or (executable == "node" and args and args[0] == "--test"):
        return {"mainframe-testing"}
    if re.fullmatch(r"python(?:3(?:\.\d+)?)?", executable):
        while args and args[0] in {"-B", "-I", "-E", "-s"}:
            args = args[1:]
        if len(args) >= 2 and args[0] == "-m" and args[1] in {"pytest", "unittest"}:
            return {"mainframe-testing"}
    return set()


def _operation_sequence(command: str, depth: int, remote: bool, budget: list[int]) -> set[str]:
    if depth > MAX_OPERATION_DEPTH or len(command.encode("utf-8")) > MAX_COMMAND_BYTES:
        raise ValueError("operation size/depth limit")
    tokens = _tokens(command)
    if tokens is None:
        raise ValueError("non-literal shell")
    commands = _commands(tokens)
    budget[0] += len(tokens)
    budget[1] += len(commands)
    if budget[0] > MAX_TOKENS or budget[1] > MAX_SEGMENTS:
        raise ValueError("aggregate operation limit")
    result: set[str] = set()
    for index, (argv, _) in enumerate(commands):
        piped_input = index > 0 and commands[index - 1][1] == "|"
        result.update(_operation_argv(argv, depth, remote, budget, piped_input))
    return result


def operation_skills(command: str) -> set[str]:
    """Return literal operation candidates, without IO, execution or authority.

    The read tokenizer's shell and size limits also apply here, including across
    nested SSH strings. Only ``sudo -n [--]``, the canonical credential helper,
    and SSH with known options and one literal remote command string unwrap.
    Remote identity remains explicit throughout recursion; no command, including
    a direct local-looking lifecycle command, establishes the independent local
    executor evidence needed for ``mainframe-ops-app-server-safety``.

    Known HTTP curl transfers, native ClickHouse clients with explicit query/file
    or pipeline input, K3s cluster operations, Docker/Terraform operations and
    named test runners and documented Codex exec/exact-ID resume forms are
    candidates. Peer relevance does not establish product-assignment authority.
    Bare kubectl, application-only K3s
    pod work, opaque shell wrappers, config-loaded/dynamic commands, arbitrary
    package scripts and help/version requests stay silent. A malformed nested
    string or exceeded limit silences the complete result, never a partial set.
    """
    if not isinstance(command, str):
        return set()
    try:
        return _operation_sequence(command, 0, False, [0, 0])
    except (UnicodeError, ValueError, TypeError):
        return set()


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

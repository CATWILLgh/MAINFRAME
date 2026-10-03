"""Maintained Codex packaging and reconciliation, with no duplicated content."""

from __future__ import annotations

from copy import deepcopy
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sqlite3
import sys
import tempfile
import tomllib

from .codex_skill_reminder import ROLE_MATCHER
from .core import (Change, Conflict, digest, encode_json, migrate_disabled_markers,
                   observed, reconcile_files, regular_bytes, retire_recorded_legacy_file)
from .shared import BEGIN, END, _instruction, inventory
from .state import component_keys, reconcile_state, set_component
from .runtime import CODE_QUALITY_TOOLS, runtime_bin

SHELL_HOOK_NAMES = (
    "mainframe-secret-access",
    "mainframe-rg-short-replace",
    "mainframe-destructive-operations",
    "mainframe-commit-secrets",
)
PRE_SHELL_TRANSPORT = "mainframe-pre-shell"
HOOK_NAMES = (*SHELL_HOOK_NAMES, "mainframe-code-quality", "mainframe-commit-checkpoint", "mainframe-skill-reminder")
RUNTIME_TOOLS = CODE_QUALITY_TOOLS
HOOK_RENAMES = {
    "secret-access": "mainframe-secret-access",
    "rg-short-replace": "mainframe-rg-short-replace",
    "code-quality": "mainframe-code-quality",
}
READ_ONLY_ROLES = {"mainframe-researcher", "mainframe-test-auditor", "mainframe-consequential-reviewer"}
READ_ONLY_ROLE_ACTION = "Verify parent permission overrides preserve the read-only role boundary."
KNOWN_RUNTIME = "0.153.4"
# Exact Desktop mapping revalidated against the tagged native schemas/sources.
# This is delivery compatibility, not observed lifecycle/role acceptance.
INSPECTED_DESKTOP_RUNTIMES = {"0.159.2", "0.159.0-alpha.12.1"}
# Current Desktop discovery exposes the same instruction/skill/role text formats.
# This permits only an existing installation's bounded update, including the
# exact Stop registration repair validated against the native schema.
CONTENT_UPDATE_RUNTIMES = {"0.154.0-alpha.6.2"}
LIMITATIONS = {
    "mainframe-destructive-operations": "The context-free command and root/home/Git guard subset is installed. Native shell hooks omit the actual tool workdir, so active-project-root and ordinary relative-target protection remain unsupported.",
    "mainframe-commit-secrets": "The context-free literal and absolute-file commit-metadata guard is installed. Native shell hooks omit the actual tool workdir needed to inspect staged and worktree content.",
    "mainframe-code-quality": "The core pre-edit, post-edit, and revalidating completion guard is installed. The full contract remains unsupported because Stop lacks non-blocking model context for completion-only unavailable-check advice.",
    "mainframe-fallow-quality": "No safe partial binding is installed: Codex lacks the exact attributed post-edit diff, dirty-worktree reconstruction can include unrelated changes, persisting source content violates the hook state boundary, and Stop would force a model continuation for an advisory.",
}


def mapping_supported(version: str | None, surface: str | None) -> bool:
    return version == KNOWN_RUNTIME or (
        surface == "desktop" and version in INSPECTED_DESKTOP_RUNTIMES
    )


def _validate_mapping(source: dict) -> None:
    components = source["components"]
    for category in ("mcp", "plugins", "runtime", "settings"):
        if components[category]:
            raise Conflict(f"The Codex adapter has no mapping for the new {category} inventory.")
    if set(components["hooks"]) != set(HOOK_NAMES) | set(LIMITATIONS):
        raise Conflict("A new hook requires a tested Codex event mapping.")
    expected_agents = READ_ONLY_ROLES | {
        "mainframe-typescript-backend-engineer",
        "mainframe-python-backend-engineer",
        "mainframe-go-backend-engineer",
        "mainframe-react-frontend-engineer",
    }
    if set(components["agents"]) != expected_agents:
        raise Conflict("A new role requires a Codex permission mapping.")


def desktop_version(config_home: Path, thread_id: str | None) -> str | None:
    """Read only this task's engine version, never a rollout or another task."""
    database = config_home / "state_5.sqlite"
    if not thread_id or not database.is_file():
        return None
    try:
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as connection:
            row = connection.execute("SELECT cli_version FROM threads WHERE id = ?", (thread_id,)).fetchone()
        return row[0] if row and isinstance(row[0], str) and re.fullmatch(
            r"\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?", row[0]
        ) else None
    except sqlite3.Error:
        return None


def native_version(executable: str | None) -> str | None:
    if not executable:
        return None
    result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10)
    match = re.fullmatch(r"codex-cli (\S+)\s*", result.stdout)
    return match.group(1) if result.returncode == 0 and match else None


def hook_command(base: Path, name: str, state: Path, analyzer_bin: Path | None = None) -> str:
    # This guard is in the registered command itself. It stays callable even
    # after Codex caches it and every MAINFRAME-owned file has been removed.
    script = ('[ -e "$1/.disabled-$3" ] && exit 0; '
              '[ -f "$1/bridge.py" ] || exit 0; '
              '[ -x "$2" ] || exit 0; '
              'PATH="${5:+$5:}$PATH" PYTHONDONTWRITEBYTECODE=1 "$2" -B "$1/bridge.py" "$3" "$4" 2>/dev/null || :')
    return shlex.join(["/bin/sh", "-c", script, "mainframe-hook", str(base),
                       str(Path(sys.executable).resolve()), name, str(state),
                       str(analyzer_bin) if analyzer_bin else ""])


def _legacy_hook_command(base: Path, name: str, state: Path) -> str:
    script = ('[ -e "$1/.disabled-$3" ] && exit 0; '
              '[ -f "$1/bridge.py" ] || exit 0; '
              '[ -x "$2" ] || exit 0; '
              'PYTHONDONTWRITEBYTECODE=1 "$2" -B "$1/bridge.py" "$3" "$4" 2>/dev/null || :')
    return shlex.join(["/bin/sh", "-c", script, "mainframe-hook", str(base),
                       str(Path(sys.executable).resolve()), name, str(state)])


def _commands(group: dict) -> set[str]:
    return {hook.get("command", "") for hook in group.get("hooks", []) if isinstance(hook, dict)}


def _is_validated_hook_registration_update(change: Change, previous: dict,
                                           base: Path, state: Path,
                                           analyzer_bin: Path) -> bool:
    """Accept exact owned runtime-path migration and Stop schema repair."""
    if change.before is None or change.after is None:
        return False
    try:
        before = json.loads(change.before)
        after = json.loads(change.after)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    expected = deepcopy(before)
    stop_groups = expected.get("hooks", {}).get("Stop", []) if isinstance(expected, dict) else []
    all_prior_groups = previous.get("hook_groups", {})
    owned_commands = {
        command for groups in all_prior_groups.values()
        for group in groups for command in _commands(group)
    }
    replacements = {
        _legacy_hook_command(base, transport, state):
        hook_command(base, transport, state, analyzer_bin)
        for transport in (PRE_SHELL_TRANSPORT, "mainframe-code-quality")
    }
    changed = 0
    if not isinstance(stop_groups, list):
        return False
    for event, groups in expected.get("hooks", {}).items():
        if not isinstance(groups, list):
            return False
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
                return False
            for handler in group.get("hooks", []):
                if not isinstance(handler, dict):
                    return False
                command = handler.get("command")
                if command in replacements and command in owned_commands:
                    handler["command"] = replacements[command]
                    changed += 1
    for group in stop_groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
            return False
        for handler in group.get("hooks", []):
            if (isinstance(handler, dict)
                    and handler.get("command") in {*owned_commands, *replacements.values()}
                    and handler.get("additionalContextLimit") == 6000):
                handler.pop("additionalContextLimit")
                changed += 1
    return changed > 0 and expected == after


def retire_reminder_pilot(raw: bytes | None, support: Path):
    """Retire only the exact receipted pilot; keep its backups and executable."""
    pilot = support / "experiments/skill-reminder"
    receipt_raw = regular_bytes(pilot / "receipt.json")
    if raw is None or receipt_raw is None:
        return raw, []
    record = json.loads(receipt_raw)
    registration = record.get("registration")
    document = json.loads(raw)
    groups = document.get("hooks", {}).get("PostToolUse", [])
    if registration not in groups:
        return raw, []
    commands = _commands(registration)
    if len(commands) != 1 or str(pilot / "codex.py") not in next(iter(commands)):
        raise Conflict("Pilot reminder receipt has an unexpected registration; preserve it for review.")
    config_path = pilot / "config.json"
    snapshot = observed(config_path)
    if snapshot[0] is None:
        raise Conflict("Pilot reminder configuration is missing; reconcile its registration first.")
    config = json.loads(snapshot[0])
    config["disabled"] = True
    changes = [Change.from_snapshot(config_path, snapshot, encode_json(config),
                                   mode=snapshot[1] or 0o600, component="retire reminder pilot")]
    document["hooks"]["PostToolUse"] = [g for g in groups if g != registration]
    return encode_json(document), changes


def merge_hooks(raw: bytes | None, desired: dict, prior: dict, base: Path):
    document = json.loads(raw) if raw is not None else {}
    if not isinstance(document, dict) or not isinstance(document.get("hooks", {}), dict):
        raise Conflict("hooks.json is not a native hooks object.")
    hooks = document.setdefault("hooks", {})
    owned = {}
    for event, groups in list(hooks.items()):
        if not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
            raise Conflict("A hooks.json event does not contain hook groups.")
        for previous in prior.get("hook_groups", {}).get(event, []):
            for current in groups:
                if _commands(previous) & _commands(current) and current != previous:
                    raise Conflict("An owned hook registration was edited; preserve it for review.")
            if previous in desired.get(event, []) and previous in groups:
                # Native trust identities can depend on registration position.
                # Keep an unchanged owned group where the user last saw it.
                first = groups.index(previous)
                groups = [g for index, g in enumerate(groups) if g != previous or index == first]
                owned.setdefault(event, []).append(previous)
            else:
                replacements = [g for g in desired.get(event, [])
                                if g.get("matcher") == previous.get("matcher")]
                if previous in groups and len(replacements) == 1:
                    replacement = replacements[0]
                    first = groups.index(previous)
                    groups = [replacement if index == first else g
                              for index, g in enumerate(groups) if g != previous or index == first]
                    owned.setdefault(event, []).append(replacement)
                else:
                    groups = [g for g in groups if g != previous]
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    for event, groups in desired.items():
        for group in groups:
            existing = hooks.setdefault(event, [])
            if group in existing:
                continue  # Existing identical registrations remain user-owned.
            for candidates in hooks.values():
                for candidate in candidates:
                    if any(str(base) in command for command in _commands(candidate)):
                        if candidate not in sum(desired.values(), []):
                            raise Conflict("An unowned MAINFRAME hook registration needs scoped migration.")
            existing.append(group)
            owned.setdefault(event, []).append(group)
    if document == {"hooks": {}} and prior.get("hook_file_created"):
        return None, owned
    if raw is None and document == {"hooks": {}}:
        return None, owned
    # Keep the user's formatting when the resulting native data is unchanged.
    result = raw if raw is not None and document == json.loads(raw) else encode_json(document)
    return result, owned


def merge_permission(raw: bytes | None, target: str | None, prior: dict):
    """Edit one simple native array; unusual syntax remains an explicit handoff."""
    text = (raw or b"").decode()
    parsed = tomllib.loads(text)
    section = parsed.get("sandbox_workspace_write", {})
    roots = section.get("writable_roots", [])
    if not isinstance(roots, list) or not all(isinstance(root, str) for root in roots):
        raise Conflict("sandbox_workspace_write.writable_roots must be a string array.")
    desired = [root for root in roots if not (prior.get("owned") and root == prior.get("root"))]
    owned = bool(target and target not in desired)
    if owned:
        desired.append(target)
    record = {"root": target, "owned": owned, "file_created": prior.get("file_created", raw is None),
              "key_created": prior.get("key_created", "writable_roots" not in section),
              "table_created": prior.get("table_created", "sandbox_workspace_write" not in parsed)}
    if roots == desired:
        return raw, record, None
    header = re.search(r"(?m)^\[sandbox_workspace_write\][ \t]*\n", text)
    if not header:
        if "sandbox_workspace_write" in parsed:
            return raw, prior, "Reconcile the feedback permission in the nonstandard TOML table syntax."
        result = text + ("\n" if text and not text.endswith("\n\n") else "")
        result += "[sandbox_workspace_write]\nwritable_roots = " + json.dumps(desired) + "\n"
    else:
        next_header = re.search(r"(?m)^\[", text[header.end():])
        end = header.end() + next_header.start() if next_header else len(text)
        segment = text[header.end():end]
        key = re.search(r"(?m)^writable_roots[ \t]*=[ \t]*", segment)
        if key:
            start = header.end() + key.start()
            stop = header.end() + key.end()
            while stop < end:
                stop = text.find("\n", stop, end)
                if stop == -1:
                    stop = end
                try:
                    value = tomllib.loads(text[start:stop])
                except tomllib.TOMLDecodeError:
                    stop += 1
                    continue
                if value == {"writable_roots": roots}:
                    break
                raise Conflict("Cannot isolate the writable_roots value.")
            else:
                raise Conflict("Cannot isolate the writable_roots value.")
            if "#" in text[start:stop]:
                return raw, prior, "Preserve array comments while reconciling the feedback writable_roots entry."
            replacement = "writable_roots = " + json.dumps(desired)
            if not desired and record["key_created"]:
                replacement = ""
            result = text[:start] + replacement + text[stop:]
        elif "writable_roots" in section:
            return raw, prior, "Reconcile the feedback permission in the quoted or dotted writable_roots key."
        else:
            result = text[:header.end()] + "writable_roots = " + json.dumps(desired) + "\n" + text[header.end():]
        if not target and record["table_created"]:
            result = re.sub(r"(?m)^\[sandbox_workspace_write\]\n(?=\s*(?:\[|\Z))", "", result)
    expected = deepcopy(parsed)
    expected.setdefault("sandbox_workspace_write", {})["writable_roots"] = desired
    actual = tomllib.loads(result)
    actual_roots = actual.get("sandbox_workspace_write", {}).get("writable_roots", [])
    for value in (expected, actual):
        value.get("sandbox_workspace_write", {}).pop("writable_roots", None)
        if value.get("sandbox_workspace_write") == {}:
            value.pop("sandbox_workspace_write")
    if expected != actual or actual_roots != desired:
        raise Conflict("Permission merge would change an unrelated TOML value.")
    return (None if not result.strip() and record["file_created"] else result.encode()), record, None


class Codex:
    def __init__(self, root: Path, home: Path, codex_home: Path | None = None, version: str | None = None, surface: str | None = None):
        self.root, self.home = root.resolve(), home.resolve()
        self.codex = (codex_home or self.home / ".codex").resolve()
        self.skills = self.codex / "skills"
        self.support = self.codex / "mainframe"
        self.hooks = self.support / "hooks"
        self.receipt_path = self.support / "installation.json"
        self.journal = self.support / "recovery.json"
        self.lock_path = self.codex / ".mainframe-install.lock"
        namespace = digest(str(self.codex).encode())[:24]
        self.event_state = Path(tempfile.gettempdir()).resolve() / ("mainframe-codex-rg-" + namespace)
        self.state_path = self.root / "ADAPTATION.codex.json"
        self.index = self.root / "shared/credentials/credentials-index.md"
        self.version = version
        self.surface = surface

    def allowed(self, path: Path) -> bool:
        if not path.is_absolute() or ".." in path.parts:
            return False
        exact = {self.codex / "AGENTS.md", self.codex / "AGENTS.override.md", self.codex / "hooks.json",
                 self.codex / "config.toml", self.receipt_path, self.state_path, self.index,
                 self.support / "experiments/skill-reminder/config.json",
                 self.home / ".local/bin/mainframe-secret", self.home / ".local/bin/secret"}
        if path in exact or path in (self.hooks, self.support) or path.is_relative_to(self.hooks):
            return True
        # Keep the former shared root readable by receipt reconciliation only:
        # unchanged owned files migrate; foreign or edited files are preserved.
        for skill_root in (self.skills, self.home / ".agents/skills"):
            if path.is_relative_to(skill_root):
                parts = path.relative_to(skill_root).parts
                return bool(parts and re.fullmatch(
                    r"mainframe-[a-z0-9-]+|project-skill|tickets-(?:find|refine|implement|verify)",
                    parts[0],
                ))
        return path.parent == self.codex / "agents" and bool(re.fullmatch(r"mainframe-[a-z0-9-]+\.toml", path.name))

    def receipt(self, snapshot=None) -> dict:
        raw = snapshot[0] if snapshot is not None else regular_bytes(self.receipt_path)
        if raw is None:
            return {}
        result = json.loads(raw)
        if result.get("version") != 1 or result.get("target") != str(self.codex):
            raise Conflict("Installation receipt belongs to another target or format.")
        old_source = Path(result.get("source", ""))
        if not old_source.is_absolute():
            raise Conflict("Receipt has no absolute source root.")
        for path, record in result.get("files", {}).items():
            old_index = (record.get("retain") is True and record.get("component") == "shared.credentials index"
                         and Path(path) == old_source / "shared/credentials/credentials-index.md")
            if not self.allowed(Path(path)) and not old_index:
                raise Conflict(f"Receipt contains an unexpected path: {path}")
        return result

    def artifacts(self, source: dict, previous: dict) -> dict:
        artifacts = {}
        def add(path, data, component, mode=0o600, retain=False):
            if path in artifacts:
                raise Conflict(f"Two components map to the same destination: {path}")
            artifacts[path] = (data, mode, component, retain)
        for name, entry in source["components"]["skills"].items():
            skill = self.root / entry["source"]
            for path in sorted(skill.rglob("*")):
                if path.is_symlink():
                    raise Conflict(f"Canonical skill resource is a symlink: {path}")
                if not path.is_file() or "__pycache__" in path.parts or path.name == ".DS_Store":
                    continue
                data = path.read_bytes()
                if path.suffix in {".md", ".py", ".sh", ".js", ".mjs", ".json", ".yaml", ".yml", ".txt"}:
                    data = data.replace(b"{{MAINFRAME_ROOT}}", str(self.root).encode())
                    data = data.replace(b"{{CREDENTIALS_INDEX}}", str(self.index).encode())
                add(self.skills / name / path.relative_to(skill), data, "skills." + name, path.stat().st_mode & 0o777)
        for name, entry in source["components"]["agents"].items():
            text = (self.root / entry["source"]).read_text()
            description = re.search(r"^Description: (.+)$", text, re.M).group(1)
            method = re.search(r"^Required method: \[([^]]+)\]", text, re.M).group(1)
            if method not in source["components"]["skills"]:
                raise Conflict(f"Unknown method for {name}: {method}")
            text = re.sub(r"^(?:Identifier|Description): .+\n\n", "", text, flags=re.M)
            text = re.sub(r"^Required method: .+$", lambda _: f"Required method: [{method}](<{self.skills / method / 'SKILL.md'}>)", text, flags=re.M)
            result = "name = " + json.dumps(name) + "\ndescription = " + json.dumps(description)
            result += "\ndeveloper_instructions = " + json.dumps(text) + "\n"
            if name in READ_ONLY_ROLES:
                result += 'sandbox_mode = "read-only"\n'
            tomllib.loads(result)
            add(self.codex / "agents" / (name + ".toml"), result.encode(), "agents." + name)
        for name, entry in source["components"]["commands"].items():
            body = (self.root / entry["source"]).read_text()
            if name == "mainframe-init":
                body = re.sub(r"<!-- MAINFRAME OPTIONAL BLOCK: native-primary-memory.*?<!-- END MAINFRAME OPTIONAL BLOCK: native-primary-memory -->\n?", "", body, flags=re.S)
            description = "Explicit user command: " + body.splitlines()[0].lstrip("# ") + ". User invocation only; takes no arguments."
            packaged = "---\nname: " + name + "\ndescription: " + json.dumps(description) + "\n---\n\n" + body
            add(self.skills / name / "SKILL.md", packaged.encode(), "commands." + name)
            add(self.skills / name / "agents/openai.yaml", b"policy:\n  allow_implicit_invocation: false\n", "commands." + name)
        for name in HOOK_NAMES:
            source_path = self.root / source["components"]["hooks"][name]["source"]
            add(self.hooks / "detectors" / source_path.name, source_path.read_bytes(), "hooks." + name)
        add(self.hooks / "bridge.py", Path(__file__).with_name("codex_hook.py").read_bytes(), "hook transport")
        add(self.hooks / "skill_profiles.py", Path(__file__).with_name("skill_profiles.py").read_bytes(), "hooks.mainframe-skill-reminder")
        add(self.hooks / "skill_reminder.py", Path(__file__).with_name("codex_skill_reminder.py").read_bytes(), "hooks.mainframe-skill-reminder")
        helper = self.home / ".local/bin/mainframe-secret"
        existing_helper = helper if helper.exists() else None
        if self.home == Path.home().resolve():
            located = shutil.which("mainframe-secret")
            existing_helper = Path(located) if located else existing_helper
        if existing_helper and str(existing_helper) not in previous.get("files", {}):
            probe = subprocess.run([str(existing_helper), "help"], capture_output=True, timeout=10)
            if probe.returncode or not all(token in probe.stdout for token in (b"mainframe-secret run NAME", b"mainframe-secret get NAME", b"mainframe-secret set NAME --clipboard", b"mainframe-secret copy NAME")):
                raise Conflict("An existing mainframe-secret command is incompatible; preserve it and reconcile that dependency.")
        else:
            add(helper, (self.root / source["components"]["shared"]["credentials"]["source"]).read_bytes(), "shared.credentials", 0o755)
        index_seed = (self.root / "shared/credentials/credentials-index.template.md").read_bytes()
        if previous and previous["source"] != str(self.root):
            old_index = Path(previous["source"]) / "shared/credentials/credentials-index.md"
            old_data, new_data = regular_bytes(old_index), regular_bytes(self.index)
            if old_data is None and new_data is None:
                raise Conflict("The prior credential index is unavailable; recover its non-secret metadata before switching source roots.")
            if old_data is not None:
                if new_data is not None and new_data != old_data:
                    raise Conflict("Reconcile the two existing non-secret credential indexes before switching source roots.")
                index_seed = old_data
        add(self.index, index_seed, "shared.credentials index", retain=True)
        return artifacts

    def plan(self, instructions_reviewed=False, remove=False):
        if regular_bytes(self.journal) is not None:
            raise Conflict(f"Interrupted transaction needs recovery: {self.journal}")
        receipt_snapshot = observed(self.receipt_path)
        source, previous = ({} if remove else inventory(self.root)), self.receipt(receipt_snapshot)
        if not remove:
            _validate_mapping(source)
        if remove and not previous:
            return [], {"changes": [], "note": "No installer-owned installation to remove."}
        artifacts = {} if remove else self.artifacts(source, previous)
        marker_changes = [] if remove else migrate_disabled_markers(
            previous, self.hooks, HOOK_RENAMES, "disabled hook marker"
        )
        changes, records = reconcile_files(artifacts, previous.get("files", {}), self.allowed)
        changes.extend(marker_changes)
        if not remove:
            changes.extend(retire_recorded_legacy_file(
                previous, self.home / ".local/bin/secret", "shared.credentials"
            ))
        instruction_path = Path(previous.get("instruction", {}).get("path", str(self.codex / "AGENTS.md")))
        if not previous.get("instruction") and (self.codex / "AGENTS.override.md").exists():
            instruction_path = self.codex / "AGENTS.override.md"
        if instruction_path not in {self.codex / "AGENTS.md", self.codex / "AGENTS.override.md"}:
            raise Conflict("Unexpected global instruction owner in receipt.")
        if previous.get("instruction") and instruction_path.name == "AGENTS.md" and (self.codex / "AGENTS.override.md").exists():
            raise Conflict("A new global override shadows the installed instruction; reconcile the owner first.")
        instruction_snapshot = observed(instruction_path)
        old_instruction = instruction_snapshot[0]
        prior_instruction = previous.get("instruction")
        outside, _ = _instruction(old_instruction, "", prior_instruction, remove=True)
        body = "" if remove else (self.root / "instructions/global.md").read_text()
        instruction, instruction_record = _instruction(old_instruction, body, prior_instruction, remove)
        user_digest = digest(outside or b"")
        review_needed = bool(not remove and outside and (
            not prior_instruction or prior_instruction.get("user_sha256") != user_digest
            or prior_instruction["sha256"] != instruction_record["sha256"]
        ))
        if review_needed and not instructions_reviewed:
            review_note = "Read the existing global instruction and canonical instructions/global.md; resolve semantic conflicts, then apply with --instructions-reviewed."
        else:
            review_note = None
        if instruction_record:
            instruction_record["path"] = str(instruction_path)
            instruction_record["user_sha256"] = user_digest
        changes.append(Change.from_snapshot(instruction_path, instruction_snapshot, instruction,
                       mode=instruction_snapshot[1] or 0o600, component="instructions.global"))
        desired_hooks = {} if remove else {"PreToolUse": [
            {"matcher": "^Bash$", "hooks": [{"type": "command", "command": hook_command(self.hooks, PRE_SHELL_TRANSPORT, self.event_state, runtime_bin(self.home)),
              "timeout": 5, "additionalContextLimit": 6000},
              {"type": "command", "command": hook_command(self.hooks, "mainframe-skill-reminder", self.event_state),
               "timeout": 2, "additionalContextLimit": 300}]},
            {"matcher": "^apply_patch$", "hooks": [{"type": "command",
              "command": hook_command(self.hooks, "mainframe-code-quality", self.event_state, runtime_bin(self.home)),
              "timeout": 180, "additionalContextLimit": 6000}]}],
        "SubagentStart": [{"matcher": ROLE_MATCHER, "hooks": [{"type": "command",
              "command": hook_command(self.hooks, "mainframe-skill-reminder", self.event_state),
              "timeout": 2, "additionalContextLimit": 300}]}],
        "PostToolUse": [{"matcher": "^apply_patch$", "hooks": [{"type": "command",
              "command": hook_command(self.hooks, "mainframe-code-quality", self.event_state, runtime_bin(self.home)),
              "timeout": 180, "additionalContextLimit": 6000},
              {"type": "command", "command": hook_command(self.hooks, "mainframe-commit-checkpoint", self.event_state),
               "timeout": 5, "additionalContextLimit": 1000}]},
            {"matcher": "^Bash$", "hooks": [{"type": "command",
              "command": hook_command(self.hooks, "mainframe-skill-reminder", self.event_state),
              "timeout": 2, "additionalContextLimit": 300}]}],
        "Stop": [{"hooks": [{"type": "command",
              "command": hook_command(self.hooks, "mainframe-code-quality", self.event_state, runtime_bin(self.home)),
              "timeout": 180}]}]}
        hook_path = self.codex / "hooks.json"
        hook_snapshot = observed(hook_path)
        old_hooks = hook_snapshot[0]
        if not remove:
            old_hooks, retirement = retire_reminder_pilot(old_hooks, self.support)
            changes.extend(retirement)
        hooks, hook_groups = merge_hooks(old_hooks, desired_hooks, previous, self.hooks)
        changes.append(Change.from_snapshot(hook_path, hook_snapshot, hooks,
                       mode=hook_snapshot[1] or 0o600, component="hook registration"))
        config_path = self.codex / "config.toml"
        target_permission = None if remove else str(self.root / "docs/tickets/open/observations")
        config_snapshot = observed(config_path)
        config, permission, permission_note = merge_permission(config_snapshot[0], target_permission, previous.get("permission", {}))
        if remove and permission_note:
            raise Conflict(permission_note + " Preserve the ownership receipt until removal is complete.")
        changes.append(Change.from_snapshot(config_path, config_snapshot, config,
                       mode=config_snapshot[1] or 0o600, component="feedback permission"))
        report = {"target": str(self.codex), "runtime_version": self.version, "surface": self.surface,
                  "instruction_review": review_note, "permission_handoff": permission_note}
        if remove:
            # Remove only the owned instruction/registrations/files. Credential
            # descriptions and stores, native trust caches and sessions survive.
            changes.append(Change.from_snapshot(self.receipt_path, receipt_snapshot, None, component="ownership receipt"))
            for name, owned in previous.get("disabled_markers", {}).items():
                if name not in {*HOOK_NAMES, *HOOK_RENAMES}:
                    raise Conflict("Unknown disabled hook in the receipt.")
                if owned:
                    changes.append(Change.to(self.hooks / (".disabled-" + name), None, component="disabled hook marker"))
            state_snapshot = observed(self.state_path)
            raw_state = state_snapshot[0]
            if raw_state is not None:
                prior_state = json.loads(raw_state)
                if prior_state.get("target", {}).get("config_home") == str(self.codex):
                    state_source = inventory(self.root)
                    state = reconcile_state(
                        state_source, prior_state, prior_state.get("target", {}),
                        unchanged=False,
                        pending={component: "Reinstall to restore the component."
                                 for component in component_keys(state_source)},
                        next_actions=("Installer-owned artifacts were removed; cached callbacks remain neutral.",),
                    )
                    changes.append(Change.from_snapshot(self.state_path, state_snapshot, encode_json(state), component="adaptation state"))
        else:
            receipt = {"version": 1, "target": str(self.codex), "source": str(self.root), "files": records,
                       "instruction": instruction_record, "hook_groups": hook_groups,
                       "hook_file_created": previous.get("hook_file_created", old_hooks is None), "permission": permission,
                       "disabled_markers": previous.get("disabled_markers", {})}
            directories = set(previous.get("directories", []))
            for path in artifacts:
                parent = path.parent
                while self.allowed(parent):
                    if not parent.exists():
                        directories.add(str(parent))
                    parent = parent.parent
            receipt["directories"] = sorted(directories)
            configuration = tomllib.loads((config or b"").decode())
            policy = {key: configuration.get(key) for key in ("sandbox_mode", "approval_policy", "permissions",
                      "permission_profile", "sandbox_workspace_write", "agents", "skills", "features")}
            fingerprint = digest(encode_json({"files": {p: r for p, r in records.items() if not r["retain"]},
                "instruction": digest(instruction or b""), "hooks": desired_hooks, "permission": permission,
                "policy": policy, "version": self.version, "adapter": digest(Path(__file__).read_bytes())}))
            receipt["fingerprint"] = fingerprint
            state_snapshot = observed(self.state_path)
            raw_state = state_snapshot[0]
            prior_state = json.loads(raw_state) if raw_state else {}
            target = {
                "product": "codex", "version": self.version, "surface": self.surface,
                "config_home": str(self.codex), "mainframe_root": str(self.root),
                "installer": "maintained Codex adapter",
            }
            unchanged = (
                prior_state.get("target", {}).get("config_home") == str(self.codex)
                and prior_state.get("target", {}).get("surface") == self.surface
                and prior_state.get("target", {}).get("version") == self.version
                and not any(change.needed for change in changes)
            )
            unsupported = {}
            pending = {}
            for name, limitation in LIMITATIONS.items():
                component = ("hooks", name)
                if mapping_supported(self.version, self.surface):
                    unsupported[component] = limitation + f" Confirmed mapping for Codex {self.version}."
                else:
                    pending[component] = "Recheck this hook limitation for the current runtime."
            if permission_note:
                pending[("skills", "mainframe-harness-feedback")] = permission_note
            delivered = set(component_keys(source)) - set(unsupported) - set(pending)
            if unchanged and prior_state.get("schema_version") == 2:
                next_actions = prior_state.get("next_actions", [])
                if not isinstance(next_actions, list):
                    next_actions = []
            else:
                next_actions = [
                    f"Confirm discovery in a fresh Codex {self.surface or 'current-surface'} task after any required activation or reload."
                ]
            state = reconcile_state(
                source, prior_state, target, unchanged=unchanged,
                delivered=delivered, unsupported=unsupported, pending=pending,
                next_actions=next_actions,
            )
            read_only_pending = False
            for name in READ_ONLY_ROLES:
                component = ("agents", name)
                row = state["components"]["agents"][name]
                if row.get("verification") == "pending":
                    read_only_pending = True
                    set_component(
                        state, component, delivery="installed", verification="pending",
                    )
            if read_only_pending:
                state.setdefault("next_actions", [])
                if READ_ONLY_ROLE_ACTION not in state["next_actions"]:
                    state["next_actions"].append(READ_ONLY_ROLE_ACTION)
            changes.append(Change.from_snapshot(self.state_path, state_snapshot, encode_json(state), component="adaptation state"))
            changes.append(Change.from_snapshot(self.receipt_path, receipt_snapshot, encode_json(receipt), component="ownership receipt"))
        # Dependencies precede their users; registrations follow implementations;
        # the global instruction is last, followed only by local bookkeeping.
        def order(change):
            for rank, prefix in enumerate(("shared.", "skills.", "agents.", "commands.", "hooks.",
                                            "hook transport", "feedback permission", "retire reminder pilot", "hook registration",
                                            "instructions.", "disabled hook marker", "adaptation state", "ownership receipt")):
                if change.component.startswith(prefix):
                    return rank
            raise Conflict("Unmapped installation change category.")
        changes.sort(key=order)
        report["changes"] = [change.summary() for change in changes if change.needed]
        if not remove:
            report["unsupported_full_contracts"] = (
                LIMITATIONS if mapping_supported(self.version, self.surface) else {}
            )
            report["retained_partial_bindings"] = {
                "mainframe-destructive-operations": LIMITATIONS["mainframe-destructive-operations"],
                "mainframe-commit-secrets": LIMITATIONS["mainframe-commit-secrets"],
                "mainframe-code-quality": LIMITATIONS["mainframe-code-quality"]
            }
        return changes, report

    def validate_content_update(self, changes, previous):
        """Permit text replacement and the one validated prerelease hook repair."""
        if (self.surface != "desktop" or self.version not in CONTENT_UPDATE_RUNTIMES
                or not previous or previous.get("source") != str(self.root)):
            raise Conflict("This runtime supports only content updates to an existing same-source installation invoked from Desktop; revalidate the native mapping for other changes.")
        for change in changes:
            if not change.needed or change.component in {"adaptation state", "ownership receipt"}:
                continue
            if (change.before is None or change.after is None
                    or change.before_mode != change.mode):
                raise Conflict("Content update cannot create, remove, or change file modes: " + str(change.path))
            component = change.component
            if (component == "hook registration"
                    and _is_validated_hook_registration_update(
                        change, previous, self.hooks, self.event_state,
                        runtime_bin(self.home),
                    )):
                continue
            if component == "instructions.global":
                if previous.get("instruction", {}).get("path") != str(change.path):
                    raise Conflict("Content update cannot change the global instruction owner.")
                continue
            if str(change.path) not in previous.get("files", {}):
                raise Conflict("Content update requires an existing receipt entry: " + str(change.path))
            if component.startswith("agents."):
                before = tomllib.loads(change.before.decode())
                after = tomllib.loads(change.after.decode())
                for field in ("description", "developer_instructions"):
                    before.pop(field, None)
                    after.pop(field, None)
                if before == after:
                    continue
            elif component.startswith(("skills.", "commands.")) and change.path.suffix == ".md":
                if change.path.name != "SKILL.md":
                    continue
                # Preserve native discovery and invocation metadata except description.
                def metadata(data):
                    parts = data.decode().split("---", 2)
                    if len(parts) != 3 or parts[0].strip():
                        raise Conflict("Content update requires the existing skill frontmatter shape.")
                    return re.sub(r"^description:.*$", "", parts[1], flags=re.M)
                if metadata(change.before) == metadata(change.after):
                    continue
            raise Conflict("Content update cannot change native packaging, executable support, or permissions: " + str(change.path))

    def control(self, enabled: bool, name: str | None):
        if name is not None and name not in HOOK_NAMES:
            raise Conflict("Unknown maintained Codex hook.")
        receipt_snapshot = observed(self.receipt_path)
        receipt = self.receipt(receipt_snapshot)
        if not receipt:
            raise Conflict("No installer-owned hooks; use the existing adapter's documented disable path.")
        markers = receipt.setdefault("disabled_markers", {})
        changes = []
        for hook in (name,) if name else HOOK_NAMES:
            path = self.hooks / (".disabled-" + hook)
            marker_snapshot = observed(path)
            before = marker_snapshot[0]
            if enabled:
                if before is not None and not markers.get(hook):
                    raise Conflict(f"Preserve the user-owned disable marker: {path}")
                changes.append(Change.from_snapshot(path, marker_snapshot, None, component="hook enable"))
                markers.pop(hook, None)
            else:
                markers.setdefault(hook, before is None)
                if before is None:
                    changes.append(Change.from_snapshot(path, marker_snapshot, b"", component="hook disable"))
        changes.append(Change.from_snapshot(self.receipt_path, receipt_snapshot, encode_json(receipt), component="ownership receipt"))
        state_snapshot = observed(self.state_path)
        raw_state = state_snapshot[0]
        if raw_state:
            state = json.loads(raw_state)
            if state.get("target", {}).get("config_home") == str(self.codex):
                for hook in (name,) if name else HOOK_NAMES:
                    if hook in LIMITATIONS:
                        continue
                    set_component(
                        state, ("hooks", hook), delivery="installed", verification="pending",
                        next_action=(
                            "Enable the hook before verifying its callback."
                            if not enabled else "Verify the enabled hook on the current surface."
                        ),
                    )
                changes.insert(-1, Change.from_snapshot(self.state_path, state_snapshot, encode_json(state), component="adaptation state"))
        return changes

    def clean_event_state(self):
        # Only this transport's exact database files, after callback quiescence.
        if self.event_state.is_symlink() or not self.event_state.exists():
            return
        if self.event_state.stat().st_uid != os.getuid():
            raise Conflict("Temporary hook state has unexpected ownership.")
        for name in ("skill-reminders.sqlite3", "skill-reminders.sqlite3-journal", "skill-reminders.sqlite3-wal", "skill-reminders.sqlite3-shm",
                     "events.sqlite3", "events.sqlite3-journal", "events.sqlite3-wal", "events.sqlite3-shm",
                     "commit-checkpoint.sqlite3", "commit-checkpoint.sqlite3-journal", "commit-checkpoint.sqlite3-wal", "commit-checkpoint.sqlite3-shm"):
            path = self.event_state / name
            if path.exists() and not path.is_symlink() and path.is_file():
                path.unlink()
        for path in self.event_state.iterdir():
            if re.fullmatch(r"[0-9a-f]{32}\.json", path.name) and path.is_file() and not path.is_symlink():
                path.unlink()
            elif re.fullmatch(r"[0-9a-f]{32}\.json\.lock", path.name) and path.is_dir() and not path.is_symlink():
                path.rmdir()
        try:
            self.event_state.rmdir()
        except OSError:
            pass

    def clean_directories(self, receipt: dict):
        for raw in sorted(receipt.get("directories", []), key=len, reverse=True):
            path = Path(raw)
            if self.allowed(path) and not path.is_symlink():
                try:
                    path.rmdir()
                except OSError:
                    pass

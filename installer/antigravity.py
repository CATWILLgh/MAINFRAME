"""Maintained Antigravity Desktop 2.0 mapping for release 2.13.0."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from .core import (Change, Conflict, digest, encode_json, migrate_disabled_markers,
                   observed, regular_bytes, reconcile_files, retire_recorded_legacy_file)
from .shared import inventory, _instruction
from .state import reconcile_state
from .runtime import CODE_QUALITY_TOOLS, FALLOW_TOOLS, runtime_bin


KNOWN_RUNTIME = "2.13.0"
HOOK_NAMES = (
    "mainframe-secret-access", "mainframe-rg-short-replace", "mainframe-destructive-operations", "mainframe-commit-secrets",
    "mainframe-code-quality", "mainframe-fallow-quality", "mainframe-commit-checkpoint",
)
RUNTIME_TOOLS = (*CODE_QUALITY_TOOLS, *FALLOW_TOOLS)
SKILL_REMINDER_ACTION = "Codex pilot first; native adaptation and acceptance are pending."
HOOK_RENAMES = {
    "secret-access": "mainframe-secret-access",
    "rg-short-replace": "mainframe-rg-short-replace",
    "destructive-operations": "mainframe-destructive-operations",
    "commit-secrets": "mainframe-commit-secrets",
    "code-quality": "mainframe-code-quality",
    "fallow-quality": "mainframe-fallow-quality",
}
READ_ONLY = {"mainframe-researcher", "mainframe-test-auditor", "mainframe-consequential-reviewer"}
COMMAND_REASON = (
    "Antigravity 2.13.0 exposes custom slash entries as ordinary skills that are also "
    "eligible for autonomous selection; it has no documented explicit-only command switch."
)
COMMAND_PARTIAL = (
    "Installed as a slash-capable skill whose discovery text and body require an explicit matching "
    "slash invocation; the host cannot enforce explicit-only selection."
)
PRE_TOOL_LIMIT = (
    "Antigravity 2.13.0 requires every PreToolUse handler to return allow, deny, ask, or force_ask. "
    "It has no neutral decision that preserves the native permission layer: allow authorizes the tool, "
    "while ask forces an extra permission decision and blocks unattended goals."
)
UNSUPPORTED = {
    "mainframe-secret-access": PRE_TOOL_LIMIT + " A positive match is delivered immediately after the tool call instead.",
    "mainframe-rg-short-replace": PRE_TOOL_LIMIT + " Its bounded advice is delivered immediately after the tool call instead.",
    "mainframe-destructive-operations": PRE_TOOL_LIMIT + " A positive match is delivered immediately after the tool call instead.",
    "mainframe-commit-secrets": PRE_TOOL_LIMIT + " The recorded commit is inspected immediately after the tool call instead.",
    "mainframe-code-quality": (
        PRE_TOOL_LIMIT + " Exact inserted-text findings are delivered after supported edit tools and revalidated "
        "at Stop, but pre-edit external diagnostics and growth attribution remain unavailable."
    ),
    "mainframe-fallow-quality": (
        "Antigravity Stop cannot deliver advisory-only output without continuing the model. Exact supported "
        "TS/JS edit diffs are therefore analyzed and delivered at PostInvocation instead of completion."
    ),
}
PARTIAL_HOOKS = {
    "mainframe-secret-access": (
        "A PostInvocation hook detects a matching completed command and injects bounded remediation context; "
        "pre-tool denial is unavailable."
    ),
    "mainframe-rg-short-replace": (
        "A PostInvocation hook applies the canonical command detector and injects its bounded advice before "
        "the next model decision; pre-tool timing is unavailable."
    ),
    "mainframe-destructive-operations": (
        "A PostInvocation hook detects a matching completed command and injects recovery context; deterministic "
        "pre-tool denial is unavailable."
    ),
    "mainframe-commit-secrets": (
        "A PostInvocation hook inspects a just-recorded HEAD and injects a redacted remediation finding; "
        "prospective staged-content denial is unavailable."
    ),
    "mainframe-code-quality": (
        "PostInvocation attributes high-confidence findings from exact supported edit payloads, and Stop "
        "continues only while those blocking findings remain; external pre-edit diagnostics and growth are unavailable."
    ),
    "mainframe-fallow-quality": (
        "PostInvocation runs the canonical Fallow detector over exact supported TS/JS edit diffs and injects "
        "advice without forcing a completion turn; completion-event timing is unavailable."
    ),
}
HOOK_SCOPE = (
    "One composite PostInvocation hook delivers positive command and edit findings; Stop revalidates only "
    "attributed blocking code findings. PreToolUse remains unregistered so native permissions stay authoritative."
)


def hook_command(event: str, bridge: Path, state: Path, analyzer_bin: Path | None = None) -> str:
    neutral = '{"decision":"stop"}' if event == "Stop" else "{}"
    command = " ".join(shlex.quote(value) for value in (
        str(Path(sys.executable).resolve()), "-B", str(bridge), event, str(state),
    ))
    environment = f"PATH={shlex.quote(str(analyzer_bin))}:\"$PATH\" " if analyzer_bin else ""
    return (
        f"[ -f {shlex.quote(str(bridge))} ] || {{ printf '%s\\n' {shlex.quote(neutral)}; exit 0; }}; "
        + environment
        + f"PYTHONDONTWRITEBYTECODE=1 {command} 2>/dev/null || printf '%s\\n' {shlex.quote(neutral)}"
    )


def desktop_version(app: Path) -> str:
    with (app / "Contents/Info.plist").open("rb") as stream:
        data = plistlib.load(stream)
    if data.get("CFBundleIdentifier") != "com.google.antigravity":
        raise Conflict("The selected application is not Antigravity Desktop 2.0.")
    version = data.get("CFBundleShortVersionString")
    if not isinstance(version, str) or not version:
        raise Conflict("Antigravity Desktop has no usable release version.")
    return version


def role_body(text: str, name: str) -> bytes:
    description_match = re.search(r"^Description: (.+)$", text, re.M)
    method_match = re.search(r"^Required method: \[([^]]+)\]", text, re.M)
    if not description_match or not method_match:
        raise Conflict("Canonical role metadata is incomplete: " + name)
    description, method = description_match.group(1), method_match.group(1)
    body = text[text.index("Required method:"):]
    body = re.sub(
        r"^Required method: .+$",
        "Required method: the native skill `" + method + "` — load it before substantive work.",
        body,
        flags=re.M,
    )
    tools = ["view_file", "list_dir", "find_by_name", "grep_search", "run_command", "send_message"]
    if name == "mainframe-researcher":
        tools.extend(["search_web", "read_url_content"])
    if name not in READ_ONLY:
        tools.extend(["write_to_file", "replace_file_content", "multi_replace_file_content", "manage_task"])
    header = [
        "---",
        "name: " + name,
        "description: " + json.dumps(description, ensure_ascii=False),
        "tools:",
        *("  - " + tool for tool in tools),
        "mainAgent: false",
        "subagent: true",
        "model: " + ("pro" if name in READ_ONLY else "inherit"),
        "commandExecutionPolicy: sandbox",
        "skills:",
        "  - skills/" + method,
        "---",
        "",
    ]
    return ("\n".join(header) + body.strip() + "\n").encode()


def command_body(text: str, name: str) -> bytes:
    text = re.sub(
        r"<!-- MAINFRAME OPTIONAL BLOCK: native-primary-memory.*?<!-- END MAINFRAME OPTIONAL BLOCK: native-primary-memory -->\n?",
        "", text, flags=re.S,
    )
    description = (
        f"User-invocable /{name} command. Use only when the current user explicitly "
        f"invokes /{name}; never select it autonomously."
    )
    return (
        "---\nname: " + name + "\ndescription: " + json.dumps(description) +
        "\n---\n\n" + text.strip() + "\n"
    ).encode()


class Antigravity:
    def __init__(self, root: Path, home: Path, gemini_home: Path | None = None,
                 version: str | None = None, surface: str = "desktop"):
        self.root, self.home = root.resolve(), home.resolve()
        self.gemini = (gemini_home or self.home / ".gemini").resolve()
        self.config = self.gemini / "config"
        self.skills, self.agents = self.config / "skills", self.config / "agents"
        self.hooks_config = self.config / "hooks.json"
        self.instruction = self.gemini / "GEMINI.md"
        self.support = self.gemini / "antigravity/mainframe"
        self.hooks = self.support / "hooks"
        self.receipt_path = self.support / "installation.json"
        self.journal = self.support / "recovery.json"
        self.lock_path = self.support / ".install.lock"
        self.state_path = self.root / "ADAPTATION.antigravity.json"
        self.index = self.root / "shared/credentials/credentials-index.md"
        self.event_state = Path(tempfile.gettempdir()).resolve() / (
            "mainframe-antigravity-" + digest(str(self.gemini).encode())[:24]
        )
        self.version, self.surface = version, surface

    def allowed(self, path: Path) -> bool:
        if not path.is_absolute() or ".." in path.parts:
            return False
        if path in {self.hooks_config, self.instruction, self.state_path, self.index,
                    self.home / ".local/bin/mainframe-secret", self.home / ".local/bin/secret",
                    self.receipt_path}:
            return True
        if path == self.support or path.is_relative_to(self.hooks):
            return True
        for base in (self.skills, self.agents):
            if path.is_relative_to(base):
                parts = path.relative_to(base).parts
                return bool(parts and re.fullmatch(
                    r"(?:mainframe-[a-z0-9-]+|project-skill|tickets-(?:find|refine|implement|verify))(?:\.md)?",
                    parts[0],
                ))
        return False

    def receipt(self, snapshot=None) -> dict:
        raw = snapshot[0] if snapshot is not None else regular_bytes(self.receipt_path)
        if raw is None:
            return {}
        result = json.loads(raw)
        if result.get("version") != 1 or result.get("target") != str(self.gemini):
            raise Conflict("Antigravity receipt has a different target or unsupported format.")
        for raw_path in result.get("files", {}):
            if not self.allowed(Path(raw_path)):
                raise Conflict("Unexpected owned Antigravity file: " + raw_path)
        return result

    def artifacts(self, source: dict) -> dict:
        result = {}

        def add(path, data, component, mode=0o600, retain=False):
            if path in result:
                raise Conflict("Duplicate Antigravity destination: " + str(path))
            result[path] = data, mode, component, retain

        for name, entry in source["components"]["skills"].items():
            base = self.root / entry["source"]
            for path in sorted(base.rglob("*")):
                if path.is_symlink():
                    raise Conflict("Canonical skill resources cannot be symlinks.")
                if not path.is_file() or "__pycache__" in path.parts or path.name == ".DS_Store":
                    continue
                data = path.read_bytes()
                if path.suffix in {".md", ".txt", ".py", ".sh", ".js", ".mjs", ".json", ".yaml", ".yml"}:
                    data = data.replace(b"{{MAINFRAME_ROOT}}", str(self.root).encode()).replace(
                        b"{{CREDENTIALS_INDEX}}", str(self.index).encode()
                    )
                add(self.skills / name / path.relative_to(base), data, "skills." + name, path.stat().st_mode & 0o777)
        for name, entry in source["components"]["agents"].items():
            add(self.agents / (name + ".md"), role_body((self.root / entry["source"]).read_text(), name), "agents." + name)
        for name, entry in source["components"]["commands"].items():
            add(self.skills / name / "SKILL.md", command_body((self.root / entry["source"]).read_text(), name),
                "commands." + name)
        for name in HOOK_NAMES:
            add(self.hooks / "detectors" / (name + ".py"),
                (self.root / "hooks" / (name + ".py")).read_bytes(), "hooks." + name)
        add(self.hooks / "bridge.py", Path(__file__).with_name("antigravity_hook.py").read_bytes(),
            "hook transport")
        add(self.hooks / "antigravity_hook_state.py",
            Path(__file__).with_name("antigravity_hook_state.py").read_bytes(),
            "hook transport")
        helper = self.home / ".local/bin/mainframe-secret"
        located = shutil.which("mainframe-secret") if self.home == Path.home().resolve() else None
        if located and Path(located).resolve() != helper:
            probe = subprocess.run([located, "help"], capture_output=True, timeout=10)
            tokens = (b"mainframe-secret run NAME", b"mainframe-secret get NAME", b"mainframe-secret copy NAME", b"mainframe-secret set NAME --clipboard")
            if probe.returncode or not all(token in probe.stdout for token in tokens):
                raise Conflict("Existing mainframe-secret helper needs compatibility review; no credential stores were read.")
        else:
            add(helper, (self.root / "shared/credentials/mainframe-secret").read_bytes(), "shared.credentials", 0o755)
        add(self.index, (self.root / "shared/credentials/credentials-index.template.md").read_bytes(),
            "shared.credentials index", retain=True)
        return result

    def desired_hooks(self) -> dict:
        bridge = self.hooks / "bridge.py"
        return {
            "mainframe-adaptation": {
                "PostInvocation": [{
                    "type": "command",
                    "command": hook_command("PostInvocation", bridge, self.event_state, runtime_bin(self.home)),
                    "timeout": 30,
                }],
                "Stop": [{
                    "type": "command",
                    "command": hook_command("Stop", bridge, self.event_state, runtime_bin(self.home)),
                    "timeout": 10,
                }],
            }
        }

    def merge_hooks(self, raw: bytes | None, previous: dict, remove: bool):
        config = json.loads(raw) if raw else {}
        if not isinstance(config, dict) or any(not isinstance(key, str) or not isinstance(value, dict)
                                               for key, value in config.items()):
            raise Conflict("Antigravity hooks.json must map hook names to objects.")
        for key, old in previous.get("hook_specs", {}).items():
            if config.get(key) != old:
                raise Conflict("An owned Antigravity hook registration was edited: " + key)
            del config[key]
        owned = {}
        if not remove:
            for key, value in self.desired_hooks().items():
                if key in config:
                    raise Conflict("Existing Antigravity hook name has no installer ownership: " + key)
                config[key] = value
                owned[key] = deepcopy(value)
        return (None if not config and previous.get("hooks_created", raw is None) else encode_json(config)), owned

    def plan(self, instructions_reviewed=False, remove=False):
        if regular_bytes(self.journal) is not None:
            raise Conflict("Recover the interrupted Antigravity transaction first.")
        source = inventory(self.root, "antigravity")
        receipt_snapshot = observed(self.receipt_path)
        previous = self.receipt(receipt_snapshot)
        if remove and not previous:
            return [], {"changes": [], "note": "No maintained Antigravity installation to remove."}
        if previous and previous.get("source") != str(self.root):
            raise Conflict("Antigravity source root changed; reconcile the non-secret index before relocation.")
        artifacts = {} if remove else self.artifacts(source)
        if remove:
            helper = self.home / ".local/bin/mainframe-secret"
            raw_helper = regular_bytes(helper)
            if str(helper) in previous.get("files", {}) and raw_helper is not None:
                artifacts[helper] = raw_helper, helper.stat().st_mode & 0o777, "shared.credentials", True
        marker_changes = [] if remove else migrate_disabled_markers(
            previous, self.hooks, HOOK_RENAMES, "hook control"
        )
        changes, records = reconcile_files(artifacts, previous.get("files", {}), self.allowed)
        changes.extend(marker_changes)
        if not remove:
            changes.extend(retire_recorded_legacy_file(
                previous, self.home / ".local/bin/secret", "shared.credentials"
            ))

        instruction_snapshot = observed(self.instruction)
        body = "" if remove else (self.root / "instructions/global.md").read_text()
        outside, _ = _instruction(instruction_snapshot[0], "", previous.get("instruction"), remove=True)
        instruction, instruction_record = _instruction(
            instruction_snapshot[0], body, previous.get("instruction"), remove
        )
        review = None
        if instruction is not None and len(instruction.decode("utf-8")) > 12_000:
            raise Conflict("Merged Antigravity GEMINI.md exceeds the documented 12,000-character limit.")
        if not remove and outside and (
            not previous.get("instruction")
            or previous["instruction"].get("user_sha256") != digest(outside)
            or previous["instruction"].get("sha256") != instruction_record["sha256"]
        ) and not instructions_reviewed:
            review = "Read the existing GEMINI.md and canonical global instruction; resolve conflicts, then use --instructions-reviewed."
        if instruction_record:
            instruction_record["user_sha256"] = digest(outside or b"")
        changes.append(Change.from_snapshot(self.instruction, instruction_snapshot, instruction,
                                            instruction_snapshot[1] or 0o600, "instructions.global"))

        hooks_snapshot = observed(self.hooks_config)
        hooks, hook_specs = self.merge_hooks(hooks_snapshot[0], previous, remove)
        changes.append(Change.from_snapshot(self.hooks_config, hooks_snapshot, hooks,
                                            hooks_snapshot[1] or 0o600, "native registrations"))
        if remove or (previous.get("hook_specs") and not hook_specs):
            for name, owned in previous.get("disabled_markers", {}).items():
                if name not in {*HOOK_NAMES, *HOOK_RENAMES, "advisories"}:
                    raise Conflict("Unknown disabled hook in Antigravity receipt.")
                if owned:
                    marker = self.hooks / (".disabled-" + name)
                    marker_snapshot = observed(marker)
                    if marker_snapshot[0] is not None and marker_snapshot != (b"", 0o600):
                        raise Conflict("Owned Antigravity disable marker was edited; preserve it for review.")
                    changes.append(Change.from_snapshot(marker, marker_snapshot, None,
                                                        component="hook control"))

        state_snapshot = observed(self.state_path)
        prior_state = json.loads(state_snapshot[0]) if state_snapshot[0] else {}
        if remove:
            new_receipt = None
            target = prior_state.get("target", {})
        else:
            new_receipt = {
                "version": 1, "target": str(self.gemini), "source": str(self.root), "files": records,
                "instruction": instruction_record, "hook_specs": hook_specs,
                "hooks_created": previous.get("hooks_created", hooks_snapshot[0] is None),
                "disabled_markers": previous.get("disabled_markers", {}) if hook_specs else {},
            }
            directories = set(previous.get("directories", []))
            for path in artifacts:
                for parent in path.parents:
                    if self.allowed(parent) and not parent.exists():
                        directories.add(str(parent))
            new_receipt["directories"] = sorted(directories)
            new_receipt["fingerprint"] = digest(encode_json({
                "files": records, "instruction": digest(instruction or b""), "hooks": digest(hooks or b""),
                "version": self.version, "adapter": digest(Path(__file__).read_bytes()),
            }))
            target = {
                "product": "antigravity", "surface": self.surface, "version": self.version,
                "config_home": str(self.gemini), "mainframe_root": str(self.root),
                "installer": "maintained Antigravity Desktop adapter", "hook_scope": HOOK_SCOPE,
            }

        if state_snapshot[0] or not remove:
            unchanged = bool(not remove and prior_state.get("target", {}).get("config_home") == str(self.gemini)
                             and prior_state.get("target", {}).get("version") == self.version
                             and not any(change.needed for change in changes))
            unsupported = {("commands", name): COMMAND_REASON for name in source["components"]["commands"]}
            unsupported.update({("hooks", name): reason for name, reason in UNSUPPORTED.items()})
            pending = {("hooks", n): SKILL_REMINDER_ACTION
                       for n in source["components"]["hooks"]
                       if n == "mainframe-skill-reminder"}
            delivered = [
                (category, name) for category, group in source["components"].items() for name in group
                if (category, name) not in unsupported and (category, name) not in pending
                and category != "commands"
                and (category != "hooks" or name == "mainframe-commit-checkpoint")
            ]
            actions = [] if remove else [
                "Open a new Antigravity Desktop 2.0 conversation to load global skills, agents, and instructions."
            ]
            state = reconcile_state(source, prior_state, target, unchanged=unchanged, delivered=delivered,
                                    unsupported=unsupported if not remove else {},
                                    pending=pending if not remove else {}, next_actions=actions)
            changes.append(Change.from_snapshot(self.state_path, state_snapshot, encode_json(state),
                                                component="adaptation state"))
        changes.append(Change.from_snapshot(self.receipt_path, receipt_snapshot,
                                            encode_json(new_receipt) if new_receipt else None,
                                            component="ownership receipt"))
        order = ("shared.", "skills.", "agents.", "commands.", "hooks.", "hook transport", "native registrations",
                 "instructions.", "hook control", "adaptation state", "ownership receipt")
        changes.sort(key=lambda change: next((i for i, prefix in enumerate(order)
                                              if change.component.startswith(prefix)), len(order)))
        changes = [change for change in changes if change.needed]
        planned = {"installed": 0, "pending": 0, "unsupported": 0}
        verified = {"passed": 0, "pending": 0}
        if state_snapshot[0] or not remove:
            for group in state["components"].values():
                for row in group.values():
                    planned[row["delivery"]] += 1
                    if row.get("verification") in verified:
                        verified[row["verification"]] += 1
        return changes, {
            "planned_delivery": planned, "planned_verification": verified,
            "unsupported_full_contracts": {**{name: COMMAND_REASON for name in source["components"]["commands"]},
                                           **UNSUPPORTED} if not remove else {},
            "retained_partial_bindings": ({
                **{name: COMMAND_PARTIAL for name in source["components"]["commands"]},
                **PARTIAL_HOOKS,
            } if not remove else {}),
            "hook_scope": HOOK_SCOPE, "next_actions": state.get("next_actions", []) if state_snapshot[0] or not remove else [],
            "target": str(self.gemini), "runtime_version": self.version, "surface": self.surface,
            "instruction_review": review, "changes": [change.summary() for change in changes],
            "handoff": "Delivery checks only; no agent, browser, credential, CLI, or model probes are run.",
            "retiring_hooks": bool(previous.get("hook_specs")) and previous.get("hook_specs") != hook_specs,
        }

    def control(self, enabled: bool, name: str | None = None):
        snapshot = observed(self.receipt_path)
        receipt = self.receipt(snapshot)
        if not receipt:
            raise Conflict("No maintained Antigravity hook installation.")
        if not receipt.get("hook_specs"):
            raise Conflict("Antigravity 2.13.0 has no maintained MAINFRAME hook bindings.")
        changes, markers = [], receipt.setdefault("disabled_markers", {})
        selected = (name,) if name else (*HOOK_NAMES, "advisories")
        for hook in selected:
            if hook not in {*HOOK_NAMES, "advisories"}:
                raise Conflict("Unknown maintained Antigravity hook.")
            path = self.hooks / (".disabled-" + hook)
            old = observed(path)
            if markers.get(hook) and old[0] is not None and old != (b"", 0o600):
                raise Conflict("Owned Antigravity disable marker was edited; preserve it for review.")
            if enabled and old[0] is not None and not markers.get(hook):
                raise Conflict("Preserve the user-owned hook disable marker.")
            if enabled:
                markers.pop(hook, None)
            else:
                markers.setdefault(hook, old[0] is None)
            if enabled or old[0] is None:
                changes.append(Change.from_snapshot(path, old, None if enabled else b"", component="hook control"))
        changes.append(Change.from_snapshot(self.receipt_path, snapshot, encode_json(receipt), component="ownership receipt"))
        return changes

    def clean_directories(self, receipt: dict):
        for raw in sorted(receipt.get("directories", []), key=len, reverse=True):
            path = Path(raw)
            if self.allowed(path) and not path.is_symlink():
                try:
                    path.rmdir()
                except OSError:
                    pass

    def clean_event_state(self):
        if self.event_state.is_symlink() or not self.event_state.exists():
            return
        metadata = self.event_state.stat()
        if not self.event_state.is_dir() or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            raise Conflict("Temporary Antigravity hook state is not a private directory owned by this user.")
        for path in self.event_state.iterdir():
            if path.is_file() and not path.is_symlink() and (
                path.name in {"events.sqlite3", "events.sqlite3-journal", "events.sqlite3-wal", "events.sqlite3-shm",
                              "commit-checkpoint.sqlite3", "commit-checkpoint.sqlite3-journal", "commit-checkpoint.sqlite3-wal", "commit-checkpoint.sqlite3-shm"} or re.fullmatch(r"[0-9a-f]{64}\.json", path.name)
            ):
                path.unlink()
            elif path.is_dir() and not path.is_symlink() and re.fullmatch(r"[0-9a-f]{64}\.json\.lock", path.name):
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            self.event_state.rmdir()
        except OSError:
            pass

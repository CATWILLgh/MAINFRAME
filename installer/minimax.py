"""Maintained MiniMax Code Desktop Plugin V1 mapping."""

from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys

from .core import Change, Conflict, digest, encode_json, observed, regular_bytes, reconcile_files
from .shared import inventory, plan_skill_delivery, skill_resources, unsupported_dsh_plugins
from .state import reconcile_state
from .runtime import CODE_QUALITY_TOOLS, FALLOW_TOOLS, runtime_bin


HOOK_NAMES = (
    "mainframe-subagent-selection", "mainframe-todo-limits",
    "mainframe-secret-access", "mainframe-rg-short-replace",
    "mainframe-destructive-operations", "mainframe-commit-secrets",
    "mainframe-code-quality", "mainframe-fallow-quality", "mainframe-commit-checkpoint", "mainframe-skill-reminder",
)
RUNTIME_TOOLS = (*CODE_QUALITY_TOOLS, *FALLOW_TOOLS)
COMMAND_REASON = (
    "MiniMax Code exposes Plugin Skills to both autonomous selection and explicit invocation; "
    "Plugin V1 has no explicit-only command capability."
)
COMMAND_PARTIAL = (
    "Installed as a Plugin Skill whose discovery text and body require explicit matching invocation; "
    "the host cannot enforce explicit-only selection."
)
SELECTION_REASON = (
    "MiniMax task supports model/effort overrides only for explicit user choices; its native tool "
    "instructions forbid autonomous inference. Requiring both fields would block valid inherited/default calls."
)
SELECTION_PARTIAL = (
    "PreToolUse task advice preserves native defaults and explains the explicit-user-choice boundary "
    "when complete selections are absent; autonomous preventive selection parity is unavailable."
)
READ_ONLY_ROLES = frozenset({
    "mainframe-consequential-reviewer", "mainframe-researcher", "mainframe-test-auditor",
})
READ_ONLY_TOOLS = ("read", "glob", "grep", "skill", "web_fetch", "web_search", "ask_user")
HOOK_SCOPE = (
    "SessionStart and SubagentStart inject the canonical global instruction for their exact "
    "recipients. One composite PreToolUse handler covers bash, native task selection advice, addressed TODO writes/edits, and exact edit capture; PostToolUse "
    "delivers exact edit findings; Stop and SubagentStop revalidate only blocking findings and "
    "use native loop guards."
)


def desktop_version(app: Path) -> str:
    with (app / "Contents/Info.plist").open("rb") as stream:
        data = plistlib.load(stream)
    if data.get("CFBundleIdentifier") != "com.minimax.agent":
        raise Conflict("The selected application is not MiniMax Code Desktop.")
    version = data.get("CFBundleShortVersionString")
    if not isinstance(version, str) or not version:
        raise Conflict("MiniMax Code Desktop has no usable release version.")
    return version


def command_body(text: str, name: str) -> bytes:
    text = re.sub(
        r"<!-- MAINFRAME OPTIONAL BLOCK: native-primary-memory.*?<!-- END MAINFRAME OPTIONAL BLOCK: native-primary-memory -->\n?",
        "", text, flags=re.S,
    )
    description = (
        f"Run the user-invocable /{name} MAINFRAME workflow only when the current user explicitly "
        f"invokes /{name}. Never select this Skill autonomously."
    )
    return (
        "---\nname: " + name + "\ndescription: " + json.dumps(description, ensure_ascii=False)
        + "\n---\n\n" + text.strip() + "\n"
    ).encode()


def agent_body(text: str, name: str, plugin: Path) -> bytes:
    description = re.search(r"^Description: (.+)$", text, re.M).group(1)
    text = re.sub(r"\(\.\./skills/([^/]+)/SKILL\.md\)",
                  lambda match: "(" + str(plugin / "skills" / match.group(1) / "SKILL.md") + ")", text)
    metadata = "---\nname: " + name + "\ndescription: " + json.dumps(description)
    if name in READ_ONLY_ROLES:
        metadata += "\ntools: " + json.dumps(READ_ONLY_TOOLS)
    return (metadata + "\n---\n\n" + text.strip() + "\n").encode()


def hook_command(python: Path, analyzer_bin: Path | None = None) -> str:
    values = ["/usr/bin/env"]
    if analyzer_bin:
        values.append("MAINFRAME_RUNTIME_BIN=" + str(analyzer_bin))
    values.extend((str(python.resolve()), "-B"))
    command = " ".join(shlex.quote(value) for value in values)
    return command + ' "${PLUGIN_ROOT}/scripts/mainframe_hook.py" "${PLUGIN_DATA}"'


class MiniMax:
    def __init__(self, root: Path, home: Path, minimax_home: Path | None = None,
                 version: str | None = None, surface: str = "desktop",
                 python: Path | None = None):
        self.root, self.home = root.resolve(), home.resolve()
        self.minimax = (minimax_home or self.home / ".minimax").resolve()
        self.plugin = self.minimax / "plugins/mainframe"
        self.support = self.minimax / "mainframe"
        self.receipt_path = self.support / "installation.json"
        self.journal = self.support / "recovery.json"
        self.lock_path = self.support / ".install.lock"
        self.state_path = self.root / "ADAPTATION.minimax.json"
        self.agent_names = frozenset(json.loads((self.root / "ADAPTATION.example.json").read_text())["components"]["agents"])
        self.index = self.root / "shared/credentials/credentials-index.md"
        self.python = (python or Path(sys.executable)).resolve()
        self.version, self.surface = version, surface

    def allowed(self, path: Path) -> bool:
        if not path.is_absolute() or ".." in path.parts:
            return False
        if path in {
            self.state_path, self.index, self.receipt_path,
            self.home / ".local/bin/mainframe-secret", self.home / ".local/bin/secret",
        }:
            return True
        if any(path in {self.minimax / "agents" / name, self.minimax / "agents" / name / "agent.md"}
               for name in self.agent_names):
            return True
        if path == self.support or path.is_relative_to(self.plugin):
            return True
        return False

    def receipt(self, snapshot=None) -> dict:
        raw = snapshot[0] if snapshot is not None else regular_bytes(self.receipt_path)
        if raw is None:
            return {}
        result = json.loads(raw)
        if result.get("version") != 1 or result.get("target") != str(self.minimax):
            raise Conflict("MiniMax receipt has a different target or unsupported format.")
        for raw_path in result.get("files", {}):
            if not self.allowed(Path(raw_path)):
                raise Conflict("Unexpected owned MiniMax file: " + raw_path)
        return result

    def _skill_files(self, source: dict, add) -> list[str]:
        manifest_skills = []
        resources = skill_resources(self.root, source)
        for name, entry in source["components"]["skills"].items():
            base = self.root / entry["source"]
            for path in resources[name]:
                data = path.read_bytes()
                if path.suffix in {".md", ".txt", ".py", ".sh", ".js", ".mjs", ".json", ".yaml", ".yml"}:
                    data = data.replace(b"{{MAINFRAME_ROOT}}", str(self.root).encode()).replace(
                        b"{{CREDENTIALS_INDEX}}", str(self.index).encode()
                    )
                destination = self.plugin / "skills" / name / path.relative_to(base)
                add(destination, data, "skills." + name, path.stat().st_mode & 0o777)
            manifest_skills.append(f"skills/{name}/SKILL.md")
        for name, entry in source["components"]["commands"].items():
            add(self.plugin / "skills" / name / "SKILL.md",
                command_body((self.root / entry["source"]).read_text(), name),
                "commands." + name)
            manifest_skills.append(f"skills/{name}/SKILL.md")
        return manifest_skills

    def _skill_artifacts(self, source: dict) -> dict:
        artifacts = {}

        def add(path, data, component, mode):
            artifacts[path] = data, mode, component, False

        self._skill_files(source, add)
        return artifacts

    def _skill_registration(self, name: str, previous: dict, source: dict) -> dict:
        path = self.plugin / ".minimax-plugin/plugin.json"
        record = previous.get("files", {}).get(str(path), {})
        if record.get("owned") is not True or record.get("retain") or record.get("component") != "plugin package":
            raise Conflict("Skill-only delivery requires the installer-owned MiniMax Plugin manifest.")
        data, mode = observed(path)
        if data is None or digest(data) != record.get("sha256") or mode != record.get("mode"):
            raise Conflict("The installed MiniMax Plugin manifest is missing or was edited.")
        manifest = json.loads(data)
        if (not isinstance(manifest, dict) or manifest.get("schemaVersion") != 1
                or manifest.get("name") != "mainframe" or not isinstance(manifest.get("skills"), list)
                or any(not isinstance(entry, str) for entry in manifest["skills"])):
            raise Conflict("Expected the receipted MAINFRAME MiniMax Plugin V1 manifest.")
        entries = manifest["skills"]
        selected = f"skills/{name}/SKILL.md"
        if entries.count(selected) > 1:
            raise Conflict("The MiniMax Plugin manifest registers the selected skill more than once.")
        if selected not in entries:
            components = source["components"]
            canonical = {
                f"skills/{skill}/SKILL.md": index
                for index, skill in enumerate((*components["skills"], *components["commands"]))
            }
            position = next((i for i, entry in enumerate(entries)
                             if canonical.get(entry, -1) > canonical[selected]), len(entries))
            entries.insert(position, selected)
            data = encode_json(manifest)
        return {path: (data, mode, "plugin package", False)}

    def plan_skill(self, name: str):
        if self.surface != "desktop" or self.version != "3.0.73":
            raise Conflict("MiniMax skill-only delivery requires the inspected Desktop release 3.0.73.")
        return plan_skill_delivery(self, name, "minimax", self.plugin / "skills" / name,
                                   self._skill_artifacts, self._skill_registration)

    def artifacts(self, source: dict) -> dict:
        result = {}
        def add(path, data, component, mode=0o600, retain=False):
            if path in result:
                raise Conflict("Duplicate MiniMax destination: " + str(path))
            result[path] = data, mode, component, retain

        skills = self._skill_files(source, add)
        for name, entry in source["components"]["agents"].items():
            add(self.minimax / "agents" / name / "agent.md",
                agent_body((self.root / entry["source"]).read_text(), name, self.plugin),
                "agents." + name)
        for name in HOOK_NAMES:
            add(self.plugin / "hooks/detectors" / (name + ".py"),
                (self.root / "hooks" / (name + ".py")).read_bytes(), "hooks." + name)
        add(self.plugin / "scripts/mainframe_hook.py",
            Path(__file__).with_name("minimax_hook.py").read_bytes(), "hook transport")
        for filename, sourcefile in (("skill_reminder.py", "codex_skill_reminder.py"),
                                     ("native_skill_reminder.py", "native_skill_reminder.py")):
            add(self.plugin / "scripts" / filename, Path(__file__).with_name(sourcefile).read_bytes(), "hooks.mainframe-skill-reminder")
        add(self.plugin / "scripts" / "skill_profiles.py", Path(__file__).with_name("skill_profiles.py").read_bytes(), "hooks.mainframe-skill-reminder")
        add(self.plugin / "instructions/global.md",
            (self.root / "instructions/global.md").read_bytes(), "instructions.global")
        add(self.plugin / "hooks/hooks.json", encode_json({"hooks": {
            "SessionStart": [{"hooks": [{
                "type": "command", "command": hook_command(self.python, runtime_bin(self.home)), "timeout": 5,
            }]}],
            "SubagentStart": [{"hooks": [{
                "type": "command", "command": hook_command(self.python, runtime_bin(self.home)), "timeout": 5,
            }]}],
            "PreToolUse": [{"matcher": "bash|write|edit|task", "hooks": [{
                "type": "command", "command": hook_command(self.python, runtime_bin(self.home)), "timeout": 10,
            }]}],
            "PostToolUse": [{"matcher": "bash|read|write|edit", "hooks": [{
                "type": "command", "command": hook_command(self.python, runtime_bin(self.home)), "timeout": 10,
            }]}],
            "Stop": [{"hooks": [{
                "type": "command", "command": hook_command(self.python, runtime_bin(self.home)), "timeout": 10,
            }]}],
            "SubagentStop": [{"hooks": [{
                "type": "command", "command": hook_command(self.python, runtime_bin(self.home)), "timeout": 10,
            }]}],
        }}), "native registrations")
        add(self.plugin / "icon.png", Path(__file__).with_name("assets").joinpath("mainframe-icon.png").read_bytes(),
            "plugin package")
        manifest = {
            "schemaVersion": 1,
            "name": "mainframe",
            "displayName": "MAINFRAME",
            "version": "1.1.0",
            "description": "Installs MAINFRAME workflows, operating policy, and bounded safety hooks.",
            "author": "MAINFRAME",
            "icon": "icon.png",
            "category": "Code",
            "exampleQueries": [
                "Use the relevant MAINFRAME skill for this engineering task.",
                "Run /mainframe-project-skill for this repository.",
            ],
            "apps": [], "mcpServers": [], "skills": skills, "hooks": ["hooks/hooks.json"],
        }
        add(self.plugin / ".minimax-plugin/plugin.json", encode_json(manifest), "plugin package")

        helper = self.home / ".local/bin/mainframe-secret"
        located = shutil.which("mainframe-secret") if self.home == Path.home().resolve() else None
        if located and Path(located).resolve() != helper:
            probe = subprocess.run([located, "help"], capture_output=True, timeout=10)
            tokens = (b"mainframe-secret run NAME", b"mainframe-secret get NAME",
                      b"mainframe-secret copy NAME", b"mainframe-secret set NAME --clipboard")
            if probe.returncode or not all(token in probe.stdout for token in tokens):
                raise Conflict("Existing mainframe-secret helper needs compatibility review; no credential stores were read.")
        else:
            add(helper, (self.root / "shared/credentials/mainframe-secret").read_bytes(),
                "shared.credentials", 0o755)
        add(self.index, (self.root / "shared/credentials/credentials-index.template.md").read_bytes(),
            "shared.credentials index", retain=True)
        return result

    def validate_plugin_entries(self, artifacts: dict, previous: dict) -> None:
        if not self.plugin.exists():
            return
        if self.plugin.is_symlink() or not self.plugin.is_dir():
            raise Conflict("The MiniMax MAINFRAME Plugin root is not a regular directory.")
        expected = {path for path in artifacts if path.is_relative_to(self.plugin)}
        # Receipted retired entries are reconciled below, including former role Skills.
        expected.update(Path(path) for path in previous.get("files", {})
                        if Path(path).is_relative_to(self.plugin))
        for path in tuple(expected):
            expected.update(parent for parent in path.parents if parent != self.plugin
                            and parent.is_relative_to(self.plugin))
        for name in previous.get("disabled_markers", {}):
            if name not in HOOK_NAMES:
                raise Conflict("Unknown disabled MiniMax hook in the receipt.")
            expected.add(self.plugin / "hooks" / (".disabled-" + name))
        for path in self.plugin.rglob("*"):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise Conflict("Unsupported entry in the MiniMax MAINFRAME Plugin: " + str(path))
            if path.is_file() and path.stat().st_nlink != 1:
                raise Conflict("Hard-linked entry in the MiniMax MAINFRAME Plugin: " + str(path))
            if path not in expected:
                raise Conflict("Unexpected entry in the MiniMax MAINFRAME Plugin: " + str(path))

    def plan(self, instructions_reviewed=False, remove=False):
        if regular_bytes(self.journal) is not None:
            raise Conflict("Recover the interrupted MiniMax transaction first.")
        source = inventory(self.root, "minimax")
        receipt_snapshot = observed(self.receipt_path)
        previous = self.receipt(receipt_snapshot)
        if remove and not previous:
            return [], {"changes": [], "note": "No maintained MiniMax installation to remove."}
        if previous and previous.get("source") != str(self.root):
            raise Conflict("MiniMax source root changed; reconcile the non-secret index before relocation.")
        if not remove:
            release = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", self.version or "")
            if release is None or tuple(map(int, release.groups())) < (3, 0, 73):
                raise Conflict("The full MiniMax Desktop mapping requires release 3.0.73 or newer; older Plugin-only mappings remain removable.")
            if not self.python.is_file():
                raise Conflict("The Python interpreter running the installer is unavailable for MiniMax Hooks.")
            probe = subprocess.run([str(self.python), "-c", "import sys; assert sys.version_info >= (3, 11)"],
                                   capture_output=True, timeout=5)
            if probe.returncode:
                raise Conflict("MiniMax Hooks require the installer's Python 3.11 or newer interpreter.")
        artifacts = {} if remove else self.artifacts(source)
        if not remove:
            self.validate_plugin_entries(artifacts, previous)
        if remove:
            helper = self.home / ".local/bin/mainframe-secret"
            raw = regular_bytes(helper)
            if str(helper) in previous.get("files", {}) and raw is not None:
                artifacts[helper] = raw, helper.stat().st_mode & 0o777, "shared.credentials", True
        changes, records = reconcile_files(artifacts, previous.get("files", {}), self.allowed)

        state_snapshot = observed(self.state_path)
        prior_state = json.loads(state_snapshot[0]) if state_snapshot[0] else {}
        if remove:
            new_receipt = None
            target = prior_state.get("target", {})
        else:
            new_receipt = {
                "version": 1, "target": str(self.minimax), "source": str(self.root), "files": records,
                "disabled_markers": previous.get("disabled_markers", {}),
            }
            directories = set(previous.get("directories", []))
            for path in artifacts:
                for parent in path.parents:
                    if self.allowed(parent) and not parent.exists(): directories.add(str(parent))
            new_receipt["directories"] = sorted(directories)
            new_receipt["fingerprint"] = digest(encode_json({
                "files": records, "version": self.version,
                "adapter": digest(Path(__file__).read_bytes()),
                "bridge": digest(Path(__file__).with_name("minimax_hook.py").read_bytes()),
            }))
            target = {
                "product": "minimax", "surface": self.surface, "version": self.version,
                "config_home": str(self.minimax), "mainframe_root": str(self.root),
                "installer": "maintained MiniMax Code Desktop adapter", "hook_scope": HOOK_SCOPE,
                "plugin_root": str(self.plugin),
            }

        if state_snapshot[0] or not remove:
            unchanged = bool(not remove and prior_state.get("target", {}).get("config_home") == str(self.minimax)
                             and prior_state.get("target", {}).get("version") == self.version
                             and not any(change.needed for change in changes))
            unsupported = {
                **unsupported_dsh_plugins(source),
                **{("commands", name): COMMAND_REASON for name in source["components"]["commands"]},
            }
            unsupported[("hooks", "mainframe-subagent-selection")] = SELECTION_REASON
            pending = {}
            delivered = [
                (category, name) for category, group in source["components"].items() for name in group
                if (category, name) not in unsupported and (category, name) not in pending
            ]
            actions = [] if remove else [
                "Wait for the automatic local Plugin rescan; confirm MAINFRAME and its seven custom Agents in Desktop, then open a fresh conversation. Restart Desktop only if its Agent roster needs startup reconciliation."
            ]
            state = reconcile_state(source, prior_state, target, unchanged=unchanged,
                                    delivered=delivered, unsupported=unsupported if not remove else {},
                                    pending=pending if not remove else {}, next_actions=actions)
            changes.append(Change.from_snapshot(self.state_path, state_snapshot, encode_json(state),
                                                component="adaptation state"))
        if remove:
            for name, owned in previous.get("disabled_markers", {}).items():
                if name not in HOOK_NAMES:
                    raise Conflict("Unknown disabled MiniMax hook in the receipt.")
                if not owned:
                    continue
                marker = self.plugin / "hooks" / (".disabled-" + name)
                marker_snapshot = observed(marker)
                if marker_snapshot[0] is not None and marker_snapshot != (b"", 0o600):
                    raise Conflict("Owned MiniMax disable marker was edited; preserve it for review.")
                changes.append(Change.from_snapshot(marker, marker_snapshot, None,
                                                    component="hook control"))
        changes.append(Change.from_snapshot(self.receipt_path, receipt_snapshot,
                                            encode_json(new_receipt) if new_receipt else None,
                                            component="ownership receipt"))
        order = ("shared.", "skills.", "commands.", "agents.", "hooks.", "hook transport", "native registrations",
                 "instructions.", "plugin package", "hook control", "adaptation state", "ownership receipt")
        changes.sort(key=lambda change: next((i for i, prefix in enumerate(order)
                                              if change.component.startswith(prefix)), len(order)))
        changes = [change for change in changes if change.needed]
        planned = {"installed": 0, "pending": 0, "unsupported": 0}
        verified = {"passed": 0, "pending": 0}
        if state_snapshot[0] or not remove:
            for group in state["components"].values():
                for row in group.values():
                    planned[row["delivery"]] += 1
                    if row.get("verification") in verified: verified[row["verification"]] += 1
        return changes, {
            "planned_delivery": planned, "planned_verification": verified,
            "unsupported_full_contracts": ({
                **{name: reason for (_, name), reason in unsupported_dsh_plugins(source).items()},
                **{name: COMMAND_REASON for name in source["components"]["commands"]},
                "mainframe-subagent-selection": SELECTION_REASON,
            } if not remove else {}),
            "retained_partial_bindings": ({
                **{name: COMMAND_PARTIAL for name in source["components"]["commands"]},
                "mainframe-subagent-selection": SELECTION_PARTIAL,
            } if not remove else {}),
            "hook_scope": HOOK_SCOPE,
            "next_actions": state.get("next_actions", []) if state_snapshot[0] or not remove else [],
            "target": str(self.minimax), "runtime_version": self.version, "surface": self.surface,
            "instruction_review": None, "changes": [change.summary() for change in changes],
            "handoff": "Delivery checks only; no agent, browser, credential, CLI, or model probes are run.",
        }

    def control(self, enabled: bool, name: str | None = None):
        snapshot = observed(self.receipt_path)
        receipt = self.receipt(snapshot)
        if not receipt: raise Conflict("No maintained MiniMax hook installation.")
        changes, markers = [], receipt.setdefault("disabled_markers", {})
        selected = (name,) if name else HOOK_NAMES
        for hook in selected:
            if hook not in HOOK_NAMES: raise Conflict("Unknown maintained MiniMax hook.")
            path = self.plugin / "hooks" / (".disabled-" + hook)
            old = observed(path)
            if markers.get(hook) and old[0] is not None and old != (b"", 0o600):
                raise Conflict("Owned MiniMax disable marker was edited; preserve it for review.")
            if enabled and old[0] is not None and not markers.get(hook):
                raise Conflict("Preserve the user-owned MiniMax hook disable marker.")
            if enabled: markers.pop(hook, None)
            else: markers.setdefault(hook, old[0] is None)
            if enabled or old[0] is None:
                changes.append(Change.from_snapshot(path, old, None if enabled else b"",
                                                    component="hook control"))
        changes.append(Change.from_snapshot(self.receipt_path, snapshot, encode_json(receipt),
                                            component="ownership receipt"))
        return changes

    def clean_directories(self, receipt: dict):
        for raw in sorted(receipt.get("directories", []), key=len, reverse=True):
            path = Path(raw)
            if self.allowed(path) and not path.is_symlink():
                try: path.rmdir()
                except OSError: pass

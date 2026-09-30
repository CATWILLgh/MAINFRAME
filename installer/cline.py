"""Maintained Cline (Desktop and CLI) global component mapping."""

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
from .shared import _instruction, inventory
from .state import reconcile_state


HOOK_NAMES = (
    "mainframe-secret-access", "mainframe-rg-short-replace",
    "mainframe-destructive-operations", "mainframe-commit-secrets",
    "mainframe-code-quality", "mainframe-fallow-quality",
)
HOOK_FILES = {"PreToolUse": "tool_call", "PostToolUse": "tool_result"}
TRANSPORT = "mainframe-cline-hook"
# Cline file hooks have one synchronous pre-action event and one post-action
# event. Lifecycle events are detached, so they cannot inject context, continue a
# model, or block, and no recoverable per-tool denial exists outside the
# in-process plugin API.
COMPLETION_REASON = (
    "Cline dispatches its lifecycle hook files detached: the runtime ignores their "
    "result, so no completion event can revalidate findings or continue the model."
)
CODE_QUALITY_PARTIAL = (
    "Per-edit advisories are delivered on PostToolUse; the attributed-finding "
    "completion guard has no blocking completion event in Cline."
)
FALLOW_PARTIAL = (
    "Fallow's exact-scope structural analysis is delivered as a per-edit advisory on "
    "PostToolUse; Cline has no continuation-capable completion event for the canonical timing."
)
HOOK_SCOPE = (
    "One pre-action guard file covers recognized catastrophic shell and secret patterns; "
    "one post-action file delivers exact-edit quality and Fallow advisories. Lifecycle hook "
    "files are unused because Cline ignores their result. Guards hard-block through the "
    "native cancel result, which stops the affected run with the reason; Cline offers no "
    "recoverable per-tool denial for file hooks."
)
READ_ONLY_AGENTS = {
    "mainframe-consequential-reviewer": "mainframe-consequential-review",
    "mainframe-researcher": "mainframe-research",
    "mainframe-test-auditor": "mainframe-test-audit",
}
AGENT_SKILLS = {
    "mainframe-typescript-backend-engineer": "mainframe-typescript-backend",
    "mainframe-python-backend-engineer": "mainframe-python-backend",
    "mainframe-go-backend-engineer": "mainframe-go-backend",
    "mainframe-react-frontend-engineer": "mainframe-frontend",
    **READ_ONLY_AGENTS,
}
READ_ONLY_TOOLS = "read_files, search_codebase"


def desktop_version(app: Path) -> str:
    with (app / "Contents/Info.plist").open("rb") as stream:
        data = plistlib.load(stream)
    if data.get("CFBundleIdentifier") != "bot.cline.app":
        raise Conflict("The selected application is not Cline Desktop.")
    version = data.get("CFBundleShortVersionString")
    if not isinstance(version, str) or not version:
        raise Conflict("Cline Desktop has no usable release version.")
    return version


def cli_version(executable: str = "cline") -> str:
    located = shutil.which(executable)
    if not located:
        raise Conflict("No Cline CLI executable is available for version evidence.")
    try:
        probe = subprocess.run([located, "--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as error:
        raise Conflict("The Cline CLI version probe failed.") from error
    version = probe.stdout.strip()
    if probe.returncode or not version:
        raise Conflict("The Cline CLI did not report a usable version.")
    return version


def launcher(event: str, transport: str) -> bytes:
    """Return a fail-open launcher that never imports a missing implementation."""
    return (
        "#!/bin/sh\n"
        "# MAINFRAME Cline hook launcher. It fails open: an unavailable interpreter\n"
        "# or transport produces no hook result instead of a finding.\n"
        f'event={shlex.quote(event)}\n'
        'base=$(dirname "$0") || exit 0\n'
        f'transport="$base/{transport}"\n'
        '[ -f "$transport" ] || exit 0\n'
        'command -v python3 >/dev/null 2>&1 || exit 0\n'
        'exec python3 -B "$transport" "$event" "$base/../data/mainframe/hook-state"\n'
    ).encode()


def workflow_body(text: str, name: str) -> bytes:
    text = re.sub(
        r"<!-- MAINFRAME OPTIONAL BLOCK: native-primary-memory.*?"
        r"<!-- END MAINFRAME OPTIONAL BLOCK: native-primary-memory -->\n?",
        "", text, flags=re.S,
    )
    return ("---\nname: " + name + "\n---\n\n" + text.strip() + "\n").encode()


def agent_body(text: str, identity: str) -> tuple[str, bytes]:
    """Split one canonical role file into native description and role body."""
    description = ""
    for line in text.splitlines():
        if line.startswith("Description: "):
            description = line[len("Description: "):].strip()
            break
    if not description:
        raise Conflict(f"Canonical role lacks a description: {identity}")
    tail = text.split("\n## Role\n", 1)
    if len(tail) != 2:
        raise Conflict(f"Canonical role lacks its Role section: {identity}")
    skill = AGENT_SKILLS[identity]
    body = (
        f"Required method (attached skill): `{skill}`\n\n## Role\n" + tail[1].strip() + "\n"
    )
    frontmatter = [
        "---",
        f"name: {identity}",
        "description: " + json.dumps(description, ensure_ascii=False),
        f"skills: {skill}",
    ]
    if identity in READ_ONLY_AGENTS:
        frontmatter.append(f"tools: {READ_ONLY_TOOLS}")
    frontmatter.append("---")
    return identity, ("\n".join(frontmatter) + "\n\n" + body).encode()


class Cline:
    def __init__(self, root: Path, home: Path, cline_home: Path | None = None,
                 version: str | None = None, surface: str = "desktop",
                 python: Path | None = None):
        self.root, self.home = root.resolve(), home.resolve()
        self.cline = (cline_home or self.home / ".cline").resolve()
        self.hooks = self.cline / "hooks"
        self.detectors = self.hooks / "detectors"
        self.skills = self.cline / "skills"
        self.agents = self.cline / "agents"
        self.workflows = self.cline / "workflows"
        self.rules = self.cline / "rules/mainframe.md"
        self.support = self.cline / "data/mainframe"
        self.receipt_path = self.support / "installation.json"
        self.journal = self.support / "recovery.json"
        self.lock_path = self.support / ".install.lock"
        self.state_path = self.root / "ADAPTATION.cline.json"
        self.index = self.root / "shared/credentials/credentials-index.md"
        self.python = (python or Path(sys.executable)).resolve()
        self.version, self.surface = version, surface
        self._sources: dict[str, dict] | None = None

    def sources(self) -> dict[str, dict]:
        """Read names and sources from the inventory without extra validation."""
        if self._sources is None:
            raw = json.loads((self.root / "ADAPTATION.example.json").read_bytes())
            self._sources = raw.get("components", {})
        return self._sources

    def names(self, category: str) -> tuple[str, ...]:
        return tuple(self.sources().get(category, {}))

    def allowed(self, path: Path) -> bool:
        if not path.is_absolute() or ".." in path.parts:
            return False
        if path in {
            self.state_path, self.index, self.receipt_path, self.journal, self.lock_path,
            self.rules, self.home / ".local/bin/mainframe-secret",
            self.home / ".local/bin/secret",
            self.hooks / "PreToolUse", self.hooks / "PostToolUse", self.hooks / TRANSPORT,
        }:
            return True
        if path.parent == self.detectors and path.suffix == ".py" and path.stem in HOOK_NAMES:
            return True
        if path.parent == self.hooks and path.name.startswith(".disabled-"):
            return path.name[len(".disabled-"):] in HOOK_NAMES
        if path.parent == self.agents and path.stem in AGENT_SKILLS and path.suffix == ".yml":
            return True
        if path.parent == self.workflows and path.name.endswith(".md"):
            return path.stem in self.names("commands")
        if path in {self.skills, self.agents, self.workflows, self.hooks,
                    self.detectors, self.rules.parent, self.support}:
            return True
        if path.is_relative_to(self.support):
            return True
        for name in self.names("skills"):
            if path.is_relative_to(self.skills / name):
                return True
        return False

    def receipt(self, snapshot=None) -> dict:
        raw = snapshot[0] if snapshot is not None else regular_bytes(self.receipt_path)
        if raw is None:
            return {}
        result = json.loads(raw)
        if result.get("version") != 1 or result.get("target") != str(self.cline):
            raise Conflict("Cline receipt has a different target or unsupported format.")
        for raw_path in result.get("files", {}):
            if not self.allowed(Path(raw_path)):
                raise Conflict("Unexpected owned Cline file: " + raw_path)
        return result


    def _skill_files(self, source: dict, add) -> None:
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
                add(self.skills / name / path.relative_to(base), data, "skills." + name,
                    path.stat().st_mode & 0o777)

    def artifacts(self, source: dict) -> dict:
        result = {}

        def add(path: Path, data: bytes, component: str, mode: int = 0o600, retain=False):
            if path in result:
                raise Conflict("Duplicate Cline destination: " + str(path))
            result[path] = data, mode, component, retain

        self._skill_files(source, add)
        for name, entry in source["components"]["commands"].items():
            text = (self.root / entry["source"]).read_text()
            add(self.workflows / (name + ".md"), workflow_body(text, name), "commands." + name)
        for name, entry in source["components"]["agents"].items():
            text = (self.root / entry["source"]).read_text()
            identity, body = agent_body(text, name)
            add(self.agents / (identity + ".yml"), body, "agents." + name)
        for name in HOOK_NAMES:
            add(self.detectors / (name + ".py"),
                (self.root / "hooks" / (name + ".py")).read_bytes(), "hooks." + name)
        add(self.hooks / TRANSPORT, Path(__file__).with_name("cline_hook.py").read_bytes(),
            "hook transport", 0o700)
        for file_name, event_key in HOOK_FILES.items():
            add(self.hooks / file_name, launcher(event_key, TRANSPORT), "hook transport", 0o755)
        add(self.index, (self.root / "shared/credentials/credentials-index.template.md").read_bytes(),
            "shared.credentials index", 0o600, True)

        helper = self.home / ".local/bin/mainframe-secret"
        located = shutil.which("mainframe-secret") if self.home == Path.home().resolve() else None
        if located and Path(located).resolve() != helper:
            probe = subprocess.run([located, "help"], capture_output=True, timeout=10)
            tokens = (b"mainframe-secret run NAME", b"mainframe-secret get NAME",
                      b"mainframe-secret copy NAME", b"mainframe-secret set NAME --clipboard")
            if probe.returncode or not all(token in probe.stdout for token in tokens):
                raise Conflict("Existing mainframe-secret helper needs compatibility review; "
                               "no credential stores were read.")
        else:
            add(helper, (self.root / "shared/credentials/mainframe-secret").read_bytes(),
                "shared.credentials", 0o755)
        return result

    def validate_destinations(self, artifacts: dict, previous: dict) -> None:
        """Refuse to adopt an unowned hook disable marker; identical foreign
        files are reused without ownership by the file reconciliation."""
        for name in HOOK_NAMES:
            marker = self.hooks / (".disabled-" + name)
            if marker.exists() and name not in previous.get("disabled_markers", {}):
                raise Conflict(f"An unowned hook disable marker exists: {marker}")


    def plan(self, instructions_reviewed=False, remove=False):
        if regular_bytes(self.journal) is not None:
            raise Conflict("Recover the interrupted Cline transaction first.")
        source = inventory(self.root, "cline")
        receipt_snapshot = observed(self.receipt_path)
        previous = self.receipt(receipt_snapshot)
        if remove and not previous:
            return [], {"changes": [], "note": "No maintained Cline installation to remove."}
        if previous and previous.get("source") != str(self.root):
            raise Conflict("Cline source root changed; reconcile the non-secret index before relocation.")
        if not remove:
            if not self.python.is_file():
                raise Conflict("The Python interpreter running the installer is unavailable for Cline hooks.")
            probe = subprocess.run(
                [str(self.python), "-c", "import sys; assert sys.version_info >= (3, 11)"],
                capture_output=True, timeout=5,
            )
            if probe.returncode:
                raise Conflict("Cline hooks require the installer's Python 3.11 or newer interpreter.")
        artifacts = {} if remove else self.artifacts(source)
        if not remove:
            self.validate_destinations(artifacts, previous)
        if remove:
            helper = self.home / ".local/bin/mainframe-secret"
            raw = regular_bytes(helper)
            if str(helper) in previous.get("files", {}) and raw is not None:
                artifacts[helper] = raw, helper.stat().st_mode & 0o777, "shared.credentials", True
        changes, records = reconcile_files(artifacts, previous.get("files", {}), self.allowed)

        rules_snapshot = observed(self.rules)
        prior_instruction = previous.get("instruction")
        outside, _ = _instruction(rules_snapshot[0], "", prior_instruction, remove=True)
        body = "" if remove else (self.root / "instructions/global.md").read_text()
        instruction, instruction_record = _instruction(rules_snapshot[0], body, prior_instruction, remove)
        user_digest = digest(outside or b"")
        review_needed = bool(not remove and outside and (
            not prior_instruction or prior_instruction.get("user_sha256") != user_digest
            or prior_instruction["sha256"] != instruction_record["sha256"]
        ))
        if review_needed and not instructions_reviewed:
            raise Conflict(
                "The Cline rules file holds user content outside the MAINFRAME block; "
                "read it and instructions/global.md, resolve semantic conflicts, then apply "
                "with --instructions-reviewed."
            )
        if instruction_record:
            instruction_record["path"] = str(self.rules)
            instruction_record["user_sha256"] = user_digest
        changes.append(Change.from_snapshot(self.rules, rules_snapshot, instruction,
                                            component="instructions.global"))

        state_snapshot = observed(self.state_path)
        prior_state = json.loads(state_snapshot[0]) if state_snapshot[0] else {}
        if remove:
            new_receipt = None
            target = prior_state.get("target", {})
        else:
            new_receipt = {
                "version": 1, "target": str(self.cline), "source": str(self.root), "files": records,
                "disabled_markers": previous.get("disabled_markers", {}),
                "instruction": instruction_record,
            }
            directories = set(previous.get("directories", []))
            for path in (*artifacts, self.rules):
                for parent in path.parents:
                    if self.allowed(parent) and not parent.exists():
                        directories.add(str(parent))
            new_receipt["directories"] = sorted(directories)
            new_receipt["fingerprint"] = digest(encode_json({
                "files": records, "version": self.version,
                "adapter": digest(Path(__file__).read_bytes()),
                "bridge": digest(Path(__file__).with_name("cline_hook.py").read_bytes()),
            }))
            target = {
                "product": "cline", "surface": self.surface, "version": self.version,
                "config_home": str(self.cline), "mainframe_root": str(self.root),
                "installer": "maintained Cline adapter", "hook_scope": HOOK_SCOPE,
                "rules": str(self.rules), "hooks": str(self.hooks),
            }


        if state_snapshot[0] or not remove:
            unchanged = bool(not remove and prior_state.get("target", {}).get("config_home") == str(self.cline)
                             and prior_state.get("target", {}).get("version") == self.version
                             and not any(change.needed for change in changes))
            unsupported = {
                ("hooks", "mainframe-fallow-quality"): COMPLETION_REASON + " " + FALLOW_PARTIAL,
                ("hooks", "mainframe-code-quality"): COMPLETION_REASON + " " + CODE_QUALITY_PARTIAL,
            }
            delivered = [
                (category, name) for category, group in source["components"].items() for name in group
                if (category, name) not in unsupported
            ]
            if remove:
                from .state import component_keys
                state = reconcile_state(
                    source, prior_state, target, unchanged=False,
                    pending={component: "Reinstall to restore the component."
                             for component in component_keys(source)},
                    next_actions=("Installer-owned Cline artifacts were removed.",),
                )
            else:
                actions = [
                    "Open one new Cline conversation and confirm MAINFRAME skills, workflows, and rules appear without diagnostics.",
                    "Exercise one harmless Cline hook and one configured role in the selected surface; file delivery alone does not prove loading.",
                ]
                state = reconcile_state(source, prior_state, target, unchanged=unchanged,
                                        delivered=delivered, unsupported=unsupported,
                                        next_actions=actions)
            changes.append(Change.from_snapshot(self.state_path, state_snapshot, encode_json(state),
                                                component="adaptation state"))
        if remove:
            for name, owned in previous.get("disabled_markers", {}).items():
                if name not in HOOK_NAMES:
                    raise Conflict("Unknown disabled Cline hook in the receipt.")
                if not owned:
                    continue
                marker = self.hooks / (".disabled-" + name)
                marker_snapshot = observed(marker)
                if marker_snapshot[0] is not None and marker_snapshot != (b"", 0o600):
                    raise Conflict("Owned Cline disable marker was edited; preserve it for review.")
                changes.append(Change.from_snapshot(marker, marker_snapshot, None,
                                                    component="hook control"))
        changes.append(Change.from_snapshot(self.receipt_path, receipt_snapshot,
                                            encode_json(new_receipt) if new_receipt else None,
                                            component="ownership receipt"))
        order = ("shared.", "skills.", "commands.", "agents.", "hooks.", "hook transport",
                 "instructions.", "hook control", "adaptation state", "ownership receipt")
        changes.sort(key=lambda change: next((index for index, prefix in enumerate(order)
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
            "unsupported_full_contracts": ({
                "mainframe-code-quality": COMPLETION_REASON,
                "mainframe-fallow-quality": COMPLETION_REASON,
            } if not remove else {}),
            "retained_partial_bindings": ({
                "mainframe-code-quality": CODE_QUALITY_PARTIAL,
                "mainframe-fallow-quality": FALLOW_PARTIAL,
            } if not remove else {}),
            "hook_scope": HOOK_SCOPE,
            "next_actions": state.get("next_actions", []) if state_snapshot[0] or not remove else [],
            "target": str(self.cline), "runtime_version": self.version, "surface": self.surface,
            "instruction_review": None, "changes": [change.summary() for change in changes],
            "handoff": "Delivery checks only; no Cline session, model, browser, credential, or role probe is run.",
        }


    def control(self, enabled: bool, name: str | None = None):
        snapshot = observed(self.receipt_path)
        receipt = self.receipt(snapshot)
        if not receipt:
            raise Conflict("No maintained Cline hook installation.")
        changes, markers = [], receipt.setdefault("disabled_markers", {})
        selected = (name,) if name else HOOK_NAMES
        for hook in selected:
            if hook not in HOOK_NAMES:
                raise Conflict("Unknown maintained Cline hook.")
            path = self.hooks / (".disabled-" + hook)
            old = observed(path)
            if markers.get(hook) and old[0] is not None and old != (b"", 0o600):
                raise Conflict("Owned Cline disable marker was edited; preserve it for review.")
            if enabled and old[0] is not None and not markers.get(hook):
                raise Conflict("Preserve the user-owned Cline hook disable marker.")
            if enabled:
                markers.pop(hook, None)
            else:
                markers.setdefault(hook, old[0] is None)
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
                try:
                    path.rmdir()
                except OSError:
                    pass

    def clean_event_state(self):
        # Only this transport's exact database files, after callback quiescence.
        state = self.support / "hook-state"
        if state.is_symlink() or not state.exists():
            return
        if state.stat().st_uid != os.getuid():
            raise Conflict("Temporary hook state has unexpected ownership.")
        for name in ("events.sqlite3", "events.sqlite3-journal", "events.sqlite3-wal", "events.sqlite3-shm"):
            path = state / name
            if path.exists() and not path.is_symlink() and path.is_file():
                path.unlink()
        for path in state.iterdir():
            if re.fullmatch(r"[0-9a-f]{32}\.json", path.name) and path.is_file() and not path.is_symlink():
                path.unlink()

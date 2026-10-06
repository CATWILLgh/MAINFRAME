"""Maintained ZCode Desktop mapping; no model calls or native acceptance campaign."""
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
from .runtime import CODE_QUALITY_TOOLS, runtime_bin
from .shared import inventory, _instruction, skill_resources
from .state import reconcile_state, set_component

KNOWN_RUNTIME = "3.11.2.6792"
FULL_MAPPING_RUNTIMES = {KNOWN_RUNTIME, "3.14.4.7912"}
CONTENT_UPDATE_RUNTIMES = {"3.14.3.7762"}
SHELL_HOOK_NAMES = ("mainframe-secret-access", "mainframe-rg-short-replace", "mainframe-destructive-operations", "mainframe-commit-secrets")
PRE_SHELL_TRANSPORT = "mainframe-pre-shell"
HOOK_NAMES = (*SHELL_HOOK_NAMES, "mainframe-code-quality", "mainframe-commit-checkpoint", "mainframe-skill-reminder")
RUNTIME_TOOLS = CODE_QUALITY_TOOLS
HOOK_RENAMES = {
    "secret-access": "mainframe-secret-access",
    "rg-short-replace": "mainframe-rg-short-replace",
    "destructive-operations": "mainframe-destructive-operations",
    "commit-secrets": "mainframe-commit-secrets",
    "code-quality": "mainframe-code-quality",
}
READ_ONLY = {"mainframe-researcher", "mainframe-test-auditor", "mainframe-consequential-reviewer"}
LEGACY_HOOKS = tuple(n for n in HOOK_NAMES if n != "mainframe-skill-reminder")
LEGACY_BRIDGE_SHA256 = "5761f656b9ead923dd48b91adb02935bcba3d922155464a19ae0205a520e75d8"
COMPATIBLE_UPDATE_BRIDGE_SHA256 = {
    # Split four-process transport delivered before the bounded consolidation.
    "7f106b9fd50bf03f11dcbad11c83a24ffb9b94a1f2a9fa06422abcc03e9736fe",
    # First consolidated transport, before current clear/compact root capture.
    "bf1ed8e64b9cbcb94baaefc23f15efefdef33583d80856d0250cf2ea4321e7c5",
}
UNSUPPORTED = {
    "mainframe-code-quality": "The core edit lifecycle and revalidating completion guard are installed. The full contract remains unsupported because Stop drops advisory-only output unless it forces another model turn.",
    "mainframe-fallow-quality": "ZCode Stop delivers completion advice only by continuing the model; the canonical non-blocking completion advisory is unsupported in this build.",
}
HOOK_SCOPE = "Primary runtime only: the inspected ZCode default subagent path does not inherit hook runners."
AUTOMATION_SKILL_COMMANDS = {"mainframe-tickets-find"}
NATIVE_AGENT_SETTING_KEYS = ("color", "model", "thoughtLevel", "injectAgentsMd")
OPEN_SESSION_ACTION = "Open a new ZCode Desktop session to load the delivered registrations."
REFRESH_SKILLS_ACTION = "In ZCode Settings, refresh Skills once, then open a new Desktop session to load the delivered registrations."



def desktop_version(app: Path) -> str:
    info = app / "Contents/Info.plist"
    with info.open("rb") as stream:
        data = plistlib.load(stream)
    if data.get("CFBundleIdentifier") != "dev.zcode.app":
        raise Conflict("The selected application is not ZCode Desktop.")
    version = data.get("CFBundleVersion")
    if not isinstance(version, str):
        raise Conflict("ZCode Desktop has no usable build version.")
    return version


def hook_registration(base: Path, name: str, state: Path, timeout_ms: int = 5000,
                      analyzer_bin: Path | None = None) -> dict:
    # The system-shell guard is stored in native config, not in a removable file.
    script = ('[ -e "$1/.disabled-$4" ] && exit 0; '
              '[ -f "$1/bridge.py" ] || exit 0; [ -x "$2" ] || exit 0; '
              'PATH="$3:$PATH" PYTHONDONTWRITEBYTECODE=1 '
              '"$2" -B "$1/bridge.py" "$4" "$5" 2>/dev/null || :')
    return {"type": "process", "command": "/bin/sh", "args": ["-c", script, "mainframe-hook",
            str(base), str(Path(sys.executable).resolve()), str(analyzer_bin or ""), name, str(state)],
            "enabled": True, "timeoutMs": timeout_ms}


def _legacy_hook_registration(base: Path, name: str, state: Path,
                              timeout_ms: int = 5000) -> dict:
    """Return the exact pre-runtime-path callback for bounded upgrades."""
    script = ('[ -e "$1/.disabled-$3" ] && exit 0; '
              '[ -f "$1/bridge.py" ] || exit 0; [ -x "$2" ] || exit 0; '
              'PYTHONDONTWRITEBYTECODE=1 "$2" -B "$1/bridge.py" "$3" "$4" 2>/dev/null || :')
    return {"type": "process", "command": "/bin/sh", "args": ["-c", script, "mainframe-hook",
            str(base), str(Path(sys.executable).resolve()), name, str(state)],
            "enabled": True, "timeoutMs": timeout_ms}


def _is_validated_hook_config_update(before: bytes, after: bytes, base: Path, state: Path,
                                     analyzer_bin: Path) -> bool:
    try:
        old = json.loads(before)
        new = json.loads(after)
        old_group = old["hooks"]["events"]["PreToolUse"][0]
        new_group = new["hooks"]["events"]["PreToolUse"][0]
        old_start = old["hooks"]["events"]["SessionStart"][0]
        new_start = new["hooks"]["events"]["SessionStart"][0]
        old_names = [hook["args"][-2] for hook in old_group["hooks"]]
        new_names = [hook["args"][-2] for hook in new_group["hooks"]]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return False
    if old_group.get("matcher") != "Bash" or new_group.get("matcher") != "Bash":
        return False
    expected = deepcopy(old)
    changed = False
    if old_names != new_names:
        if old_names != list(SHELL_HOOK_NAMES) or new_names != [PRE_SHELL_TRANSPORT]:
            return False
        expected["hooks"]["events"]["PreToolUse"][0]["hooks"] = new_group["hooks"]
        changed = True
    if old_start.get("matcher") != new_start.get("matcher"):
        if (
            old_start.get("matcher") != "startup|resume"
            or new_start.get("matcher") != "startup|clear|compact|resume"
            or set(old_start) != {"matcher", "hooks"}
            or set(new_start) != {"matcher", "hooks"}
        ):
            return False
        expected["hooks"]["events"]["SessionStart"][0]["matcher"] = new_start["matcher"]
        changed = True
    variants = {
        ("PreToolUse", "Bash"): [(PRE_SHELL_TRANSPORT, 5000), ("mainframe-skill-reminder", 2000)],
        ("PostToolUse", "Bash|Read"): [("mainframe-skill-reminder", 2000)],
        ("PreToolUse", "Write|Edit"): [("mainframe-code-quality", 30000)],
        ("PostToolUse", "Write|Edit"): [("mainframe-code-quality", 60000), ("mainframe-commit-checkpoint", 5000)],
        ("PostToolUseFailure", "Write|Edit"): [("mainframe-code-quality", 30000)],
        ("Stop", None): [("mainframe-code-quality", 60000)],
        ("SessionStart", "startup|resume"): [("mainframe-destructive-operations", 5000)],
        ("SessionStart", "startup|clear|compact|resume"): [("mainframe-destructive-operations", 5000)],
    }
    for event, groups in expected.get("hooks", {}).get("events", {}).items():
        for group in groups:
            for name, timeout in variants.get((event, group.get("matcher")), []):
                old_callback = _legacy_hook_registration(base, name, state, timeout)
                new_callback = hook_registration(base, name, state, timeout, analyzer_bin)
                for index, callback in enumerate(group.get("hooks", [])):
                    if callback == old_callback:
                        group["hooks"][index] = new_callback
                        changed = True
    return changed and expected == new


def command_body(text: str, legacy=False) -> bytes:
    if legacy:
        text = re.sub(r"<!-- (?:END )?MAINFRAME OPTIONAL BLOCK: [^\n]*\n?", "", text)
    else:
        text = re.sub(r"<!-- MAINFRAME OPTIONAL BLOCK: native-primary-memory.*?<!-- END MAINFRAME OPTIONAL BLOCK: native-primary-memory -->\n?", "", text, flags=re.S)
    title = text.splitlines()[0].lstrip("# ")
    # A plain scalar exactly matches the inspected legacy format for these titles.
    if any(token in title for token in (": ", "\n", "#")):
        title = json.dumps(title)
    return ("---\ndescription: " + title + "\n---\n\n" + text.strip() + "\n").encode()


def command_skill_body(text: str, name: str) -> bytes:
    description = (
        "Load this workflow only when the current user or automation instructions "
        f"explicitly request /{name} or ${name}."
    )
    return (
        "---\nname: " + name + "\ndescription: " + json.dumps(description) +
        "\n---\n\n" + text.strip() + "\n"
    ).encode()


def _yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def _frontmatter(data: bytes) -> tuple[dict, str] | None:
    try:
        lines = data.decode().splitlines()
    except UnicodeDecodeError:
        return None
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    fields = {}
    index = 1
    while index < end:
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*):(?: (.*))?", lines[index])
        if not match:
            return None
        key, raw = match.groups()
        if raw not in (None, ""):
            try:
                fields[key] = json.loads(raw)
            except json.JSONDecodeError:
                fields[key] = raw
            index += 1
            continue
        values = []
        index += 1
        while index < end and lines[index].startswith("  - "):
            item = lines[index][4:]
            try:
                values.append(json.loads(item))
            except json.JSONDecodeError:
                values.append(item)
            index += 1
        fields[key] = values
    return fields, "\n".join(lines[end + 1:]).strip()


def _agent_settings(data: bytes) -> dict | None:
    parsed = _frontmatter(data)
    if parsed is None:
        return None
    fields, _ = parsed
    return {key: fields[key] for key in NATIVE_AGENT_SETTING_KEYS if key in fields}


def _agent_core_digest(data: bytes) -> str | None:
    parsed = _frontmatter(data)
    if parsed is None:
        return None
    fields, body = parsed
    core = {key: value for key, value in fields.items()
            if key not in NATIVE_AGENT_SETTING_KEYS}
    return digest(encode_json({"fields": core, "body": body}))


def _compatible_agent_settings(current: bytes, expected: bytes) -> dict | None:
    current_parsed, expected_parsed = _frontmatter(current), _frontmatter(expected)
    if current_parsed is None or expected_parsed is None:
        return None
    current_fields, current_body = current_parsed
    expected_fields, expected_body = expected_parsed
    current_core = {key: value for key, value in current_fields.items()
                    if key not in NATIVE_AGENT_SETTING_KEYS}
    if current_core != expected_fields or current_body != expected_body:
        return None
    return {key: current_fields[key] for key in NATIVE_AGENT_SETTING_KEYS
            if key in current_fields}


def role_body(text: str, name: str, native_settings: dict | None = None) -> bytes:
    description = re.search(r"^Description: (.+)$", text, re.M).group(1)
    method = re.search(r"^Required method: \[([^]]+)\]", text, re.M).group(1)
    body = text[text.index("Required method:"):]
    body = re.sub(r"^Required method: .+$", lambda _: "Required method: the native skill `" + method +
                  "` — load it through the skill mechanism before substantive work.", body, flags=re.M)
    native_settings = native_settings or {}
    quoted = bool(native_settings)
    header = "---\nname: " + (json.dumps(name) if quoted else name) + "\ndescription: " + (
        json.dumps(description) if quoted else description
    ) + "\n"
    for key in ("color", "model", "thoughtLevel"):
        if key in native_settings:
            value = native_settings[key]
            rendered = (str(value) if key in {"color", "thoughtLevel"}
                        and isinstance(value, str)
                        and re.fullmatch(r"[A-Za-z0-9_.:-]+", value)
                        else _yaml_scalar(value))
            header += key + ": " + rendered + "\n"
    if name in READ_ONLY:
        header += "disallowedTools:\n  - Edit\n  - Write\n"
    if "injectAgentsMd" in native_settings:
        header += "injectAgentsMd: " + _yaml_scalar(native_settings["injectAgentsMd"]) + "\n"
    return (header + "---\n\n" + body.strip() + "\n").encode()


class ZCode:
    def __init__(self, root: Path, home: Path, zcode_home: Path | None = None,
                 version: str | None = None, surface="desktop", adopt_existing=False):
        self.root, self.home = root.resolve(), home.resolve()
        self.zcode = (zcode_home or self.home / ".zcode").resolve()
        self.skills, self.agents, self.commands = [self.zcode / n for n in ("skills", "agents", "commands")]
        self.support = self.zcode / "mainframe"
        self.hooks = self.support / "hooks"
        self.legacy = self.zcode / "hooks/mainframe"
        self.receipt_path = self.support / "installation.json"
        self.journal = self.support / "recovery.json"
        self.lock_path = self.zcode / ".mainframe-install.lock"
        self.config = self.zcode / "cli/config.json"
        self.state_path = self.root / "ADAPTATION.zcode.json"
        self.index = self.root / "shared/credentials/credentials-index.md"
        self.event_state = Path(tempfile.gettempdir()).resolve() / ("mainframe-zcode-rg-" + digest(str(self.zcode).encode())[:24])
        self.version, self.surface, self.adopt_existing = version, surface, adopt_existing

    def allowed(self, path: Path) -> bool:
        if not path.is_absolute() or ".." in path.parts:
            return False
        if path in {self.config, self.zcode / "AGENTS.md", self.state_path, self.index,
                    self.home / ".local/bin/mainframe-secret", self.home / ".local/bin/secret",
                    self.receipt_path}:
            return True
        if path == self.support or path.is_relative_to(self.hooks) or path == self.legacy or path.is_relative_to(self.legacy):
            return True
        for base in (self.skills, self.agents, self.commands):
            if path.is_relative_to(base):
                parts = path.relative_to(base).parts
                return bool(parts and re.fullmatch(
                    r"(?:mainframe-[a-z0-9-]+|project-skill|tickets-(?:find|refine|implement|verify))(?:\.md)?",
                    parts[0],
                ))
        return False

    def receipt(self, snapshot=None):
        raw = snapshot[0] if snapshot is not None else regular_bytes(self.receipt_path)
        if raw is None:
            return {}
        record = json.loads(raw)
        if record.get("version") != 1 or record.get("target") != str(self.zcode):
            raise Conflict("ZCode receipt has a different target or unsupported format.")
        for path in record.get("files", {}):
            if not self.allowed(Path(path)):
                raise Conflict("Unexpected owned ZCode file: " + path)
        return record

    def artifacts(self, source):
        result = {}
        def add(path, data, component, mode=0o600, retain=False):
            if path in result:
                raise Conflict("Duplicate ZCode destination: " + str(path))
            result[path] = (data, mode, component, retain)
        resources = skill_resources(self.root, source)
        for name, entry in source["components"]["skills"].items():
            base = self.root / entry["source"]
            for p in resources[name]:
                data = p.read_bytes()
                if p.suffix in {".md", ".txt", ".py", ".sh", ".js", ".mjs", ".json", ".yaml", ".yml"}:
                    data = data.replace(b"{{MAINFRAME_ROOT}}", str(self.root).encode()).replace(b"{{CREDENTIALS_INDEX}}", str(self.index).encode())
                add(self.skills / name / p.relative_to(base), data, "skills." + name, p.stat().st_mode & 0o777)
        for name, entry in source["components"]["agents"].items():
            add(self.agents / (name + ".md"), role_body((self.root / entry["source"]).read_text(), name), "agents." + name)
        for name, entry in source["components"]["commands"].items():
            text = (self.root / entry["source"]).read_text()
            add(self.commands / (name + ".md"), command_body(text), "commands." + name)
            if name in AUTOMATION_SKILL_COMMANDS:
                add(self.skills / name / "SKILL.md", command_skill_body(text, name), "commands." + name)
        for name in HOOK_NAMES:
            add(self.hooks / "detectors" / (name + ".py"), (self.root / "hooks" / (name + ".py")).read_bytes(), "hooks." + name)
        add(self.hooks / "bridge.py", Path(__file__).with_name("zcode_hook.py").read_bytes(), "hook transport")
        for filename, sourcefile in (("skill_reminder.py", "codex_skill_reminder.py"),
                                     ("native_skill_reminder.py", "native_skill_reminder.py")):
            add(self.hooks / filename, Path(__file__).with_name(sourcefile).read_bytes(), "hooks.mainframe-skill-reminder")
        add(self.hooks / "skill_profiles.py", Path(__file__).with_name("skill_profiles.py").read_bytes(), "hooks.mainframe-skill-reminder")
        helper = self.home / ".local/bin/mainframe-secret"
        located = shutil.which("mainframe-secret") if self.home == Path.home().resolve() else None
        if located and Path(located) != helper:
            probe = subprocess.run([located, "help"], capture_output=True, timeout=10)
            if probe.returncode or not all(t in probe.stdout for t in (b"mainframe-secret run NAME", b"mainframe-secret get NAME", b"mainframe-secret copy NAME", b"mainframe-secret set NAME --clipboard")):
                raise Conflict("Existing mainframe-secret helper needs compatibility review; no credential stores were read.")
        else:
            add(helper, (self.root / "shared/credentials/mainframe-secret").read_bytes(), "shared.credentials", 0o755)
        add(self.index, (self.root / "shared/credentials/credentials-index.template.md").read_bytes(), "shared.credentials index", retain=True)
        return result

    def adopt(self, source, artifacts, state, config):
        if state.get("target", {}).get("product_id") != "zcode":
            raise Conflict("--adopt-existing requires the inspected manual ZCode state; it does not claim arbitrary files.")
        previous = {"version": 1, "target": str(self.zcode), "source": str(self.root), "files": {},
                    "hook_groups": {}, "adopted_legacy": True}
        for path, (data, mode, component, retain) in artifacts.items():
            raw = regular_bytes(path)
            if raw is None or component in ("shared.credentials", "shared.credentials index"):
                continue
            compatible = [data]
            if path == self.commands / "mainframe-init.md":
                compatible.append(command_body((self.root / "commands/mainframe-init.md").read_text(), legacy=True))
            if raw not in compatible:
                raise Conflict("Manual ZCode file differs from the known adaptation; preserve and review: " + str(path))
            previous["files"][str(path)] = {"sha256": digest(raw), "mode": path.stat().st_mode & 0o777,
                                           "owned": True, "retain": retain, "component": component}
        bridge = regular_bytes(self.legacy / "zcode_hook.py")
        if bridge is not None:
            if digest(bridge) != LEGACY_BRIDGE_SHA256:
                raise Conflict("Manual ZCode hook wrapper changed; use scoped retirement before adoption.")
            # Retain old callable files for cached sessions. Disable markers are
            # created before config switches; old callbacks then remain neutral.
            for p in (self.legacy / "zcode_hook.py", *(self.legacy / "detectors" / (n + ".py") for n in LEGACY_HOOKS)):
                raw = regular_bytes(p)
                if raw is None or (p.name != "zcode_hook.py" and raw != (self.root / "hooks" / p.name).read_bytes()):
                    raise Conflict("Manual detector changed or missing: " + str(p))
                artifacts[p] = (raw, p.stat().st_mode & 0o777, "retained legacy callback", True)
            for n in LEGACY_HOOKS:
                artifacts[self.legacy / (".disabled-" + n)] = (b"", 0o600, "legacy hook disable", True)
            for event, groups in config.get("hooks", {}).get("events", {}).items():
                owned = []
                for group in groups:
                    callbacks = group.get("hooks", [])
                    matches = [h for h in callbacks if str(self.legacy / "zcode_hook.py") in h.get("args", [])]
                    if matches:
                        expected_matcher = None if event == "Stop" else "Bash" if group.get("matcher") == "Bash" and event == "PreToolUse" else "Write|Edit"
                        expected_keys = {"hooks"} if event == "Stop" else {"hooks", "matcher"}
                        if (event not in {"PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop"}
                                or set(group) != expected_keys or group.get("matcher") != expected_matcher
                                or len(matches) != len(callbacks)):
                            raise Conflict("Mixed or edited manual hook group needs scoped retirement.")
                        seen = set()
                        for h in matches:
                            name = h["args"][-1]
                            allowed_names = set(LEGACY_HOOKS) - {"mainframe-code-quality"} if expected_matcher == "Bash" else {"mainframe-code-quality"}
                            timeout = 10000 if expected_matcher == "Bash" else 60000 if event == "Stop" else 30000
                            expected = {"type": "process", "command": "/usr/local/bin/python3",
                                        "args": [str(self.legacy / "zcode_hook.py"), name],
                                        "enabled": True, "timeoutMs": timeout}
                            if name not in allowed_names or name in seen or h != expected:
                                raise Conflict("Edited manual hook callback needs scoped retirement.")
                            seen.add(name)
                        owned.append(deepcopy(group))
                if owned:
                    previous["hook_groups"][event] = owned
        return previous

    def merge_config(self, raw, previous, remove):
        cfg = json.loads(raw) if raw else {}
        if not isinstance(cfg, dict):
            raise Conflict("ZCode config must be a JSON object.")
        hooks = cfg.setdefault("hooks", {})
        if not isinstance(hooks, dict) or not isinstance(hooks.get("events", {}), dict):
            raise Conflict("ZCode hooks configuration has an unsupported shape.")
        events = hooks.setdefault("events", {})
        for event, groups in events.items():
            if not isinstance(event, str) or not isinstance(groups, list) or any(
                not isinstance(group, dict) or not isinstance(group.get("hooks"), list)
                or any(not isinstance(hook, dict) for hook in group["hooks"]) for group in groups
            ):
                raise Conflict("ZCode hook groups have an unsupported shape; preserve the configuration.")
        if "skills" in cfg and not isinstance(cfg["skills"], dict):
            raise Conflict("ZCode skill overrides must be an object.")
        for event, groups in previous.get("hook_groups", {}).items():
            current = events.get(event, [])
            for group in groups:
                if current.count(group) != 1:
                    raise Conflict("An owned ZCode hook registration was edited or duplicated; preserve it for review.")
                current.remove(group)
            if not current:
                events.pop(event, None)
        owned = {}
        if not remove:
            quality = lambda timeout: hook_registration(
                self.hooks, "mainframe-code-quality", self.event_state, timeout,
                runtime_bin(self.home),
            )
            desired_groups = {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [hook_registration(
                        self.hooks, PRE_SHELL_TRANSPORT, self.event_state,
                        analyzer_bin=runtime_bin(self.home),
                    )]},
                    {"matcher": "Write|Edit", "hooks": [quality(30000)]},
                ],
                "PostToolUse": [{"matcher": "Write|Edit", "hooks": [quality(60000), hook_registration(self.hooks, "mainframe-commit-checkpoint", self.event_state, 5000, runtime_bin(self.home))]}],
                "PostToolUseFailure": [{"matcher": "Write|Edit", "hooks": [quality(30000)]}],
                "Stop": [{"hooks": [quality(60000)]}],
                "SessionStart": [{"matcher": "startup|clear|compact|resume", "hooks": [hook_registration(
                    self.hooks, "mainframe-destructive-operations", self.event_state,
                    analyzer_bin=runtime_bin(self.home),
                )]}],
            }
            desired_groups["PreToolUse"].append({"matcher": "Bash", "hooks": [hook_registration(self.hooks, "mainframe-skill-reminder", self.event_state, 2000, runtime_bin(self.home))]})
            desired_groups["PostToolUse"].append({"matcher": "Bash|Read", "hooks": [hook_registration(self.hooks, "mainframe-skill-reminder", self.event_state, 2000, runtime_bin(self.home))]})
            expected_callbacks = [h for groups in desired_groups.values() for group in groups for h in group["hooks"]]
            for event, candidates in events.items():
                for candidate in candidates:
                    if candidate in desired_groups.get(event, []):
                        continue
                    callbacks = candidate.get("hooks", [])
                    has_split_pre_shell = any(
                        str(self.hooks) in hook.get("args", [])
                        and len(hook.get("args", [])) >= 2
                        and hook["args"][-2] in {*SHELL_HOOK_NAMES, PRE_SHELL_TRANSPORT}
                        for hook in callbacks
                    )
                    if has_split_pre_shell or any(h in expected_callbacks for h in callbacks):
                        raise Conflict("A split or duplicated maintained ZCode hook registration needs scoped reconciliation.")
            for event, desired in desired_groups.items():
                current = events.setdefault(event, [])
                for group in desired:
                    if current.count(group) > 1:
                        raise Conflict("Duplicate maintained ZCode hook registrations need scoped reconciliation.")
                    if group not in current:
                        current.append(group)
                        owned.setdefault(event, []).append(group)
                    elif group in previous.get("hook_groups", {}).get(event, []):
                        owned.setdefault(event, []).append(group)
        enabled_added = previous.get("enabled_added", "enabled" not in hooks)
        if remove:
            if enabled_added and hooks.get("enabled") is True:
                hooks.pop("enabled")
        else:
            hooks.setdefault("enabled", True)  # Preserve a deliberate global disable.
        overrides = deepcopy(previous.get("skill_overrides", {}))
        for path, record in list(overrides.items()):
            if cfg.get("skills", {}).get(path) != record["after"]:
                raise Conflict("An owned ZCode skill override changed; preserve it for review.")
            if remove or not Path(path).exists():
                if record["before"] is None:
                    cfg["skills"].pop(path)
                else:
                    cfg["skills"][path] = record["before"]
                del overrides[path]
        if not remove:
            for name in inventory(self.root, "zcode")["components"]["commands"]:
                p = self.home / ".agents/skills" / name / "SKILL.md"
                if p.exists() and str(p) not in overrides:
                    skills = cfg.setdefault("skills", {})
                    before = deepcopy(skills.get(str(p)))
                    if before != {"enable": False}:
                        after = {**(before or {}), "enable": False}
                        skills[str(p)] = after
                        overrides[str(p)] = {"before": before, "after": after}
        if not hooks.get("events"):
            hooks.pop("events", None)
        if not hooks:
            cfg.pop("hooks", None)
        if cfg.get("skills") == {} and (raw is None or "skills" not in json.loads(raw)):
            cfg.pop("skills")
        return (None if not cfg and previous.get("config_created", raw is None) else encode_json(cfg)), owned, enabled_added, overrides

    def plan(self, instructions_reviewed=False, remove=False):
        if regular_bytes(self.journal) is not None:
            raise Conflict("Recover the interrupted ZCode transaction first.")
        source = {} if remove else inventory(self.root, "zcode")
        receipt_snapshot = observed(self.receipt_path); previous = self.receipt(receipt_snapshot)
        if remove and not previous:
            return [], {"changes": [], "note": "No maintained ZCode installation to remove."}
        config_snapshot = observed(self.config); old_config = config_snapshot[0]
        old_state = observed(self.state_path); prior_state = json.loads(old_state[0]) if old_state[0] else {}
        artifacts = {} if remove else self.artifacts(source)
        if remove:
            helper = self.home / ".local/bin/mainframe-secret"
            raw_helper = regular_bytes(helper)
            if str(helper) in previous.get("files", {}) and raw_helper is not None:
                # Shared consumers may still need it. Retain on removal only;
                # normal updates must deliver canonical fixes to owned helpers.
                artifacts[helper] = (raw_helper, helper.stat().st_mode & 0o777, "shared.credentials", True)
        if self.adopt_existing and not previous and not remove:
            previous = self.adopt(source, artifacts, prior_state, json.loads(old_config or b"{}"))
        elif not previous and regular_bytes(self.legacy / "zcode_hook.py") is not None:
            raise Conflict("Existing manual ZCode hooks need adoption. Review plan with --adopt-existing; no native probes are required.")
        if previous and previous.get("source") != str(self.root):
            raise Conflict("ZCode source root changed; reconcile the non-secret index before relocation.")
        if not remove:
            for raw_path, record in previous.get("files", {}).items():
                path = Path(raw_path)
                if record.get("retain") and path.is_relative_to(self.legacy):
                    data = regular_bytes(path)
                    if data is None and record.get("owned") and record["component"] == "legacy hook disable":
                        artifacts[path] = (b"", 0o600, record["component"], True)
                    elif data is not None:
                        artifacts[path] = (data, path.stat().st_mode & 0o777, record["component"], True)
        if not remove and previous:
            for name in source["components"]["agents"]:
                path = self.agents / (name + ".md")
                prior_file = previous.get("files", {}).get(str(path))
                current = regular_bytes(path)
                if not prior_file or not prior_file.get("owned") or current is None:
                    continue
                expected = artifacts[path][0]
                if digest(current) == prior_file["sha256"]:
                    settings = _agent_settings(current)
                else:
                    settings = (_agent_settings(current)
                                if prior_file.get("native_core_sha256")
                                and _agent_core_digest(current) == prior_file["native_core_sha256"]
                                else _compatible_agent_settings(current, expected))
                    if settings is not None:
                        prior_file["sha256"] = digest(current)
                        prior_file["mode"] = path.stat().st_mode & 0o777
                if settings is not None:
                    source_text = (self.root / source["components"]["agents"][name]["source"]).read_text()
                    _, mode, component, retain = artifacts[path]
                    artifacts[path] = (role_body(source_text, name, settings), mode, component, retain)
            for name in source["components"]["commands"]:
                path = self.commands / (name + ".md")
                prior_file = previous.get("files", {}).get(str(path))
                current = regular_bytes(path)
                if not prior_file or not prior_file.get("owned") or current is None:
                    continue
                expected, mode, component, retain = artifacts[path]
                if current.rstrip(b"\n") == expected.rstrip(b"\n"):
                    artifacts[path] = (current, mode, component, retain)
                    if digest(current) != prior_file["sha256"]:
                        prior_file["sha256"] = digest(current)
                        prior_file["mode"] = path.stat().st_mode & 0o777
        marker_changes = [] if remove else migrate_disabled_markers(
            previous, self.hooks, HOOK_RENAMES, "disabled hook marker"
        )
        changes, records = reconcile_files(artifacts, previous.get("files", {}), self.allowed)
        changes.extend(marker_changes)
        if not remove:
            changes.extend(retire_recorded_legacy_file(
                previous, self.home / ".local/bin/secret", "shared.credentials"
            ))
        ipath = self.zcode / "AGENTS.md"; ins_snapshot = observed(ipath); raw = ins_snapshot[0]
        body = "" if remove else (self.root / "instructions/global.md").read_text()
        prior = previous.get("instruction")
        reused = not prior and raw is not None and not remove and raw == body.encode() and not self.adopt_existing
        if prior and prior.get("reused"):
            if raw is None or digest(raw) != prior["sha256"]:
                raise Conflict("Reused global instruction changed; review its ownership.")
            if not remove and raw != body.encode():
                raise Conflict("Canonical instruction changed; adopt the existing compatible installation before updating this owner.")
            reused = True
        if reused:
            instruction, irecord = raw, {"reused": True, "sha256": digest(raw)}
            review = None
        else:
            base = raw
            if self.adopt_existing and not prior and raw == body.encode():
                base = None
            outside, _ = _instruction(base, "", prior, remove=True)
            instruction, irecord = _instruction(base, body, prior, remove)
            review = None
            if not remove and outside and (not prior or prior.get("user_sha256") != digest(outside) or prior.get("sha256") != irecord["sha256"]) and not instructions_reviewed:
                review = "Read the existing ZCode AGENTS.md and canonical global instruction; resolve conflicts, then use --instructions-reviewed."
            if irecord: irecord["user_sha256"] = digest(outside or b"")
        changes.append(Change.from_snapshot(ipath, ins_snapshot, instruction, ins_snapshot[1] or 0o600, "instructions.global"))
        config, groups, enabled_added, overrides = self.merge_config(old_config, previous, remove)
        changes.append(Change.from_snapshot(self.config, config_snapshot, config, config_snapshot[1] or 0o600, "native registrations"))
        if remove:
            for name, owned in previous.get("disabled_markers", {}).items():
                if name not in {*HOOK_NAMES, *HOOK_RENAMES}:
                    raise Conflict("Unknown disabled hook in ZCode receipt.")
                if owned:
                    marker = self.hooks / (".disabled-" + name)
                    snapshot = observed(marker)
                    if snapshot[0] is not None and snapshot != (b"", 0o600):
                        raise Conflict("Owned ZCode disable marker was edited; preserve it for review.")
                    changes.append(Change.from_snapshot(marker, snapshot, None, component="disabled hook marker"))
            new_receipt = None
            target = prior_state.get("target", {})
        else:
            for path, artifact in artifacts.items():
                if artifact[2].startswith("agents.") and str(path) in records:
                    records[str(path)]["native_core_sha256"] = _agent_core_digest(artifact[0])
            new_receipt = {"version": 1, "target": str(self.zcode), "source": str(self.root), "files": records,
                           "instruction": irecord, "hook_groups": groups, "enabled_added": enabled_added,
                           "config_created": previous.get("config_created", old_config is None), "skill_overrides": overrides,
                           "disabled_markers": previous.get("disabled_markers", {}),
                           "adopted_legacy": previous.get("adopted_legacy", False)}
            directories = set(previous.get("directories", []))
            for p in artifacts:
                for parent in p.parents:
                    if self.allowed(parent) and not parent.exists(): directories.add(str(parent))
            new_receipt["directories"] = sorted(directories)
            fingerprint = digest(encode_json({"files": records, "instruction": digest(instruction or b""),
                                             "config": digest(config or b""), "version": self.version,
                                             "adapter": digest(Path(__file__).read_bytes())}))
            new_receipt["fingerprint"] = fingerprint
            target = {"product": "zcode", "surface": self.surface, "version": self.version,
                      "config_home": str(self.zcode), "mainframe_root": str(self.root), "installer": "maintained ZCode adapter",
                      "hook_scope": HOOK_SCOPE}
        if old_state[0] or not remove:
            unchanged = bool(
                not remove
                and prior_state.get("target", {}).get("config_home") == str(self.zcode)
                and prior_state.get("target", {}).get("surface") == self.surface
                and prior_state.get("target", {}).get("version") == self.version
                and not any(change.needed for change in changes)
            )
            state_source = source if not remove else inventory(self.root, "zcode")
            unsupported = {("hooks", n): why for n, why in UNSUPPORTED.items()} if not remove else {}
            pending = {}
            delivered = [(cat, n) for cat, group in state_source["components"].items() for n in group
                         if not remove and (cat != "hooks" or n in HOOK_NAMES)
                         and (cat, n) not in unsupported and (cat, n) not in pending]
            hooks_loaded = bool(
                unchanged
                and all(
                    prior_state.get("components", {}).get("hooks", {}).get(name, {}).get("verification") == "passed"
                    for name in SHELL_HOOK_NAMES
                )
            )
            skill_refresh_pending = bool(
                not remove
                and (
                    any(change.needed and change.path.is_relative_to(self.skills) for change in changes)
                    or REFRESH_SKILLS_ACTION in prior_state.get("next_actions", [])
                )
            )
            actions = []
            if skill_refresh_pending:
                actions.append(REFRESH_SKILLS_ACTION)
            elif not remove and not hooks_loaded:
                actions.append(OPEN_SESSION_ACTION)
            if not remove and json.loads(config or b"{}").get("hooks", {}).get("enabled") is False:
                actions.append("ZCode hooks are deliberately disabled globally; enable them in the app only when the user requests activation.")
            if not remove and new_receipt["adopted_legacy"]:
                actions.append("Legacy callable files remain inert for old sessions; retire them only after those sessions stop using their callbacks.")
            state = reconcile_state(state_source, prior_state, target, unchanged=unchanged,
                                    delivered=delivered, unsupported=unsupported,
                                    pending=pending if not remove else {}, next_actions=actions)
            if not remove:
                for n in HOOK_NAMES:
                    if n in UNSUPPORTED:
                        continue
                    if regular_bytes(self.hooks / (".disabled-" + n)) is not None:
                        set_component(state, ("hooks", n), delivery="installed", verification="pending",
                                      next_action="Explicitly disabled; enable before native verification.")
            changes.append(Change.from_snapshot(self.state_path, old_state, encode_json(state), component="adaptation state"))
        changes.append(Change.from_snapshot(self.receipt_path, receipt_snapshot, encode_json(new_receipt) if new_receipt else None, component="ownership receipt"))
        # Retire old callbacks first; keep all dependencies for in-flight legacy calls.
        def order(change):
            prefixes = ("legacy hook disable", "shared.", "skills.", "agents.", "commands.",
                        "hooks.", "hook transport", "retained legacy callback", "native registrations",
                        "instructions.", "disabled hook marker", "adaptation state", "ownership receipt")
            for rank, prefix in enumerate(prefixes):
                if change.component.startswith(prefix): return rank
            raise Conflict("Unmapped ZCode change category.")
        changes.sort(key=order)
        changes = [c for c in changes if c.needed]
        planned = {"installed": 0, "pending": 0, "unsupported": 0}
        verified = {"passed": 0, "pending": 0}
        if old_state[0] or not remove:
            for group in state["components"].values():
                for row in group.values():
                    planned[row["delivery"]] += 1
                    if row.get("verification") in verified:
                        verified[row["verification"]] += 1
        return changes, {"planned_delivery": planned,
                         "planned_verification": verified,
                         "unsupported_full_contracts": UNSUPPORTED if not remove else {},
                         "retained_partial_bindings": ({"mainframe-code-quality": UNSUPPORTED["mainframe-code-quality"]}
                                                       if not remove else {}),
                         "hook_scope": HOOK_SCOPE,
                         "hooks_globally_enabled": json.loads(config or b"{}").get("hooks", {}).get("enabled", False),
                         "next_actions": state.get("next_actions", []) if old_state[0] or not remove else [],
                         "target": str(self.zcode), "runtime_version": self.version, "surface": self.surface,
                         "instruction_review": review, "changes": [{"path": str(c.path), "component": c.component,
                            "action": "remove" if c.after is None else "create" if c.before is None else "update"} for c in changes],
                         "handoff": "Delivery checks only; no agent, browser, credential, or native-hook probes are run."}

    def validate_content_update(self, changes, previous):
        """Allow bounded skill updates and exact validated hook migrations."""
        if (self.surface != "desktop" or self.version not in CONTENT_UPDATE_RUNTIMES
                or not previous or previous.get("source") != str(self.root)):
            raise Conflict("This ZCode build supports only bounded skill updates to an existing same-source installation; revalidate the native mapping for other changes.")
        automation_skill = self.skills / "mainframe-tickets-find/SKILL.md"
        for change in changes:
            if not change.needed or change.component in {"adaptation state", "ownership receipt"}:
                continue
            if change.path == automation_skill and change.component == "commands.mainframe-tickets-find":
                if change.before is None and change.after is not None and change.mode == 0o600:
                    continue
                raise Conflict("The automation skill projection has an unexpected existing shape: " + str(change.path))
            record = previous.get("files", {}).get(str(change.path))
            if (change.component == "hook transport"
                    and change.path == self.hooks / "bridge.py"
                    and record and record.get("sha256") in COMPATIBLE_UPDATE_BRIDGE_SHA256
                    and digest(change.before or b"") in COMPATIBLE_UPDATE_BRIDGE_SHA256
                    and change.after is not None and change.before_mode == change.mode):
                continue
            if (change.component == "native registrations" and change.before is not None
                    and change.after is not None and change.before_mode == change.mode
                    and _is_validated_hook_config_update(
                        change.before, change.after, self.hooks, self.event_state,
                        runtime_bin(self.home),
                    )):
                continue
            if (not change.component.startswith("skills.") or not record
                    or change.before is None or change.after is None
                    or change.before_mode != change.mode):
                raise Conflict("Bounded ZCode update cannot change native packaging, hooks, roles, commands, or permissions: " + str(change.path))

    def control(self, enabled, name=None):
        snapshot = observed(self.receipt_path); receipt = self.receipt(snapshot)
        if not receipt: raise Conflict("No maintained ZCode hook installation.")
        changes = []; markers = receipt.setdefault("disabled_markers", {})
        for hook in (name,) if name else HOOK_NAMES:
            if hook not in HOOK_NAMES: raise Conflict("Unknown maintained ZCode hook.")
            path = self.hooks / (".disabled-" + hook); old = observed(path)
            if markers.get(hook) and old[0] is not None and old != (b"", 0o600):
                raise Conflict("Owned ZCode disable marker was edited; preserve it for review.")
            if enabled and old[0] is not None and not markers.get(hook):
                raise Conflict("Preserve the user-owned hook disable marker.")
            if enabled: markers.pop(hook, None)
            else: markers.setdefault(hook, old[0] is None)
            if enabled or old[0] is None:
                changes.append(Change.from_snapshot(path, old, None if enabled else b"", component="hook control"))
        state_snapshot = observed(self.state_path)
        if state_snapshot[0]:
            state = json.loads(state_snapshot[0])
            if state.get("target", {}).get("config_home") == str(self.zcode):
                if state.get("schema_version") != 2:
                    raise Conflict("Reconcile the ZCode delivery state before controlling hooks.")
                for hook in (name,) if name else HOOK_NAMES:
                    if hook in UNSUPPORTED:
                        continue
                    set_component(state, ("hooks", hook), delivery="installed", verification="pending",
                                  next_action=("Open a new session to capture the project root, then verify on a native event." if hook == "mainframe-destructive-operations" else "Verify the enabled hook on a native event.") if enabled else
                                              "Explicitly disabled; enable before native verification.")
                changes.append(Change.from_snapshot(self.state_path, state_snapshot, encode_json(state), component="adaptation state"))
        changes.append(Change.from_snapshot(self.receipt_path, snapshot, encode_json(receipt), component="ownership receipt"))
        return changes

    def clean_directories(self, receipt):
        for raw in sorted(receipt.get("directories", []), key=len, reverse=True):
            p = Path(raw)
            if self.allowed(p) and not p.is_symlink():
                try: p.rmdir()
                except OSError: pass

    def clean_event_state(self):
        if self.event_state.is_symlink() or not self.event_state.exists(): return
        metadata = self.event_state.stat()
        if not self.event_state.is_dir() or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
            raise Conflict("Temporary ZCode hook state is not a private directory owned by this user.")
        for name in ("events.sqlite3", "events.sqlite3-journal", "events.sqlite3-wal", "events.sqlite3-shm",
                     "commit-checkpoint.sqlite3", "commit-checkpoint.sqlite3-journal", "commit-checkpoint.sqlite3-wal", "commit-checkpoint.sqlite3-shm"):
            p = self.event_state / name
            if p.is_file() and not p.is_symlink(): p.unlink()
        for p in self.event_state.iterdir():
            if re.fullmatch(r"[0-9a-f]{32}\.json", p.name) and p.is_file() and not p.is_symlink(): p.unlink()
            elif re.fullmatch(r"[0-9a-f]{32}\.json\.lock", p.name) and p.is_dir() and not p.is_symlink(): p.rmdir()
        try: self.event_state.rmdir()
        except OSError: pass

"""Product-neutral inventory and managed-instruction helpers."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile

from .core import Change, Conflict, digest, encode_json, observed, reconcile_files, regular_bytes
from .state import set_component


DSH_PLUGINS = {
    name: f"plugins/dsh/{name}"
    for name in ("activity-analytics", "message-time", "secrets-vault", "session-collaboration")
}


def unsupported_dsh_plugins(source: dict) -> dict[tuple[str, str], str]:
    """DSH runtime plugins have no native binding in the existing products."""
    return {
        ("plugins", name): "DSH-only runtime plugin; not installed in this product."
        for name in DSH_PLUGINS if name in source["components"]["plugins"]
    }


def _skill_resource_names(root: Path, bases: dict[str, Path]) -> set[str]:
    """Apply source ownership and ignore rules using filename-only Git output."""
    command = ["git", "-C", str(root), "-c", "core.excludesFile=/dev/null"]
    owner = subprocess.run(command + ["rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    checkout = owner.returncode == 0 and Path(owner.stdout.strip()).resolve() == root
    if not checkout and (root / ".git").exists():
        raise Conflict("Cannot establish Git source ownership for skill resources.")
    with tempfile.TemporaryDirectory(prefix="mainframe-resources-") as temporary:
        if not checkout:
            subprocess.run(["git", "init", "--bare", "--template=", "-q", temporary],
                           check=True, capture_output=True)
            command += ["--git-dir=" + temporary, "--work-tree=" + str(root)]
        paths = [base.relative_to(root).as_posix() for base in bases.values()]

        def listed(*options):
            process = subprocess.run(command + ["ls-files", "-z", *options, "--", *paths],
                                     capture_output=True)
            if process.returncode:
                raise Conflict("Cannot enumerate canonical skill resources.")
            return {value.decode("utf-8") for value in process.stdout.split(b"\0") if value}

        tracked = listed("--cached") if checkout else set()
        candidates = tracked | listed("--others", "--exclude-standard")
        # --no-index also detects forcibly tracked private files. Never read them.
        ignored = subprocess.run(command + ["check-ignore", "--no-index", "-z", "--stdin"],
                                 input=b"".join(value.encode() + b"\0" for value in sorted(candidates)),
                                 capture_output=True)
        if ignored.returncode not in (0, 1):
            raise Conflict("Cannot validate skill resource ignore rules.")
        excluded = {value.decode("utf-8") for value in ignored.stdout.split(b"\0") if value}
        if tracked & excluded:
            raise Conflict("Ignored local material is tracked as a canonical skill resource.")
        if checkout and candidates - tracked - excluded:
            raise Conflict("Untracked canonical skill resource: add intended source files to Git "
                           "or move local material outside the skill package.")
        return candidates - excluded


def skill_resources(root: Path, source: dict) -> dict[str, list[Path]]:
    """Select approved skill files without reading ignored/private contents.

    Git checkouts use the index as source ownership. Source archives use their
    distributed ignore rules through disposable metadata, never an in-place
    git init. Both preserve binary resources and reject symlinks.
    """
    root = root.resolve()
    bases = {name: root / row["source"]
             for name, row in source["components"]["skills"].items()}
    for base in bases.values():
        if base.is_symlink():
            raise Conflict("Canonical skill resources cannot be symlinks.")
    selected = _skill_resource_names(root, bases)
    result = {}
    for name, base in bases.items():
        files = []
        for relative in sorted(selected):
            path = root / relative
            if not path.is_relative_to(base):
                continue
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents
                                        if parent.is_relative_to(base)):
                raise Conflict("Canonical skill resources cannot be symlinks.")
            if not path.is_file() or not path.resolve().is_relative_to(base):
                raise Conflict("Canonical skill resource is missing or not a regular file.")
            if path.name not in {".gitignore", ".gitattributes", ".gitkeep"}:
                files.append(path)
        if base / "SKILL.md" not in files:
            raise Conflict("Canonical SKILL.md must be an approved skill resource.")
        result[name] = files
    return result


def render_skill_artifacts(root: Path, skills: Path, index: Path, source: dict) -> dict:
    artifacts = {}
    resources = skill_resources(root, source)
    for name, entry in source["components"]["skills"].items():
        base = root / entry["source"]
        for path in resources[name]:
            data = path.read_bytes()
            if path.suffix in {".md", ".txt", ".py", ".sh", ".js", ".mjs", ".json", ".yaml", ".yml"}:
                data = data.replace(b"{{MAINFRAME_ROOT}}", str(root).encode())
                data = data.replace(b"{{CREDENTIALS_INDEX}}", str(index).encode())
            artifacts[skills / name / path.relative_to(base)] = (
                data, path.stat().st_mode & 0o777, "skills." + name, False,
            )
    return artifacts


def plan_skill_delivery(adapter, name, product, destination, render, registration=None):
    """Reconcile the selected package and any required native catalog entry."""
    if regular_bytes(adapter.journal) is not None:
        raise Conflict(f"Interrupted transaction needs recovery: {adapter.journal}")
    source = inventory(adapter.root, product)
    entry = source["components"]["skills"].get(name)
    if entry is None:
        raise Conflict("Unknown canonical skill: " + name)
    receipt_snapshot = observed(adapter.receipt_path)
    receipt = adapter.receipt(receipt_snapshot)
    if not receipt or receipt.get("source") != str(adapter.root):
        raise Conflict("Skill-only delivery requires an existing same-source installation.")
    state_snapshot = observed(adapter.state_path)
    state = json.loads(state_snapshot[0]) if state_snapshot[0] else {}
    target = state.get("target", {})
    skills = state.get("components", {}).get("skills")
    if (state.get("schema_version") != 2 or target.get("product") != product
            or target.get("config_home") != receipt["target"]
            or target.get("mainframe_root") != str(adapter.root) or not isinstance(skills, dict)):
        raise Conflict("Skill-only delivery requires matching existing adaptation state.")

    component = "skills." + name
    files = receipt["files"]
    old_records = {path: record for path, record in files.items() if record.get("component") == component}
    if any(Path(path).is_relative_to(destination) and record.get("component") != component
           for path, record in files.items()):
        raise Conflict("Skill destination belongs to another receipted component.")
    if any(not Path(path).is_relative_to(destination) for path in old_records):
        raise Conflict("Skill-only delivery cannot migrate a previous skill destination.")
    artifacts = render({"components": {"skills": {name: entry}, "commands": {}}})
    if not artifacts or any(not path.is_relative_to(destination) or row[2] != component
                            for path, row in artifacts.items()):
        raise Conflict("The rendered skill package is outside its selected destination.")
    if registration is not None:
        for path, artifact in registration(name, receipt, source).items():
            prior = files.get(str(path))
            if path in artifacts or not prior or not prior["owned"] or prior.get("retain") or prior["component"] != artifact[2]:
                raise Conflict("The skill's native registration is not owned by this installation.")
            artifacts[path] = artifact
            old_records[str(path)] = prior
    if any(not adapter.allowed(path) for path in artifacts):
        raise Conflict("Skill-only delivery contains an unexpected destination.")

    changes, records = reconcile_files(artifacts, old_records, adapter.allowed)
    if any(not change.path.is_relative_to(destination) and change.before is None for change in changes):
        raise Conflict("The skill's existing native registration disappeared during planning.")
    for path in old_records.keys() - records.keys():
        del files[path]
    files.update(records)
    directories = set(receipt.get("directories", []))
    for path in artifacts:
        parent = path.parent
        while adapter.allowed(parent):
            if not parent.exists():
                directories.add(str(parent))
            parent = parent.parent
    receipt["directories"] = sorted(directories)
    row = skills.get(name, {})
    if (any(change.needed for change in changes) or row.get("source") != entry["source"]
            or row.get("delivery") != "installed"):
        skills[name] = entry.copy()
        set_component(state, ("skills", name), delivery="installed", verification="pending",
                      next_action=f"Confirm {name} discovery in a fresh {product} Desktop session after reload.")
    changes.extend((
        Change.from_snapshot(adapter.state_path, state_snapshot, encode_json(state), component="adaptation state"),
        Change.from_snapshot(adapter.receipt_path, receipt_snapshot, encode_json(receipt), component="ownership receipt"),
    ))
    return changes, {
        "target": receipt["target"], "runtime_version": adapter.version, "surface": adapter.surface,
        "skill": name, "delivery_mode": "existing-installation skill-only delivery",
        "changes": [change.summary() for change in changes if change.needed],
        "native_acceptance": "Skill discovery remains pending; use a fresh Desktop session after reload.",
    }


BEGIN = "<!-- MAINFRAME managed instructions: begin -->"
END = "<!-- MAINFRAME managed instructions: end -->"
EXPECTED_GROUPS = {
    "shared", "instructions", "skills", "agents", "commands", "hooks",
    "mcp", "plugins", "runtime", "settings",
}


def inventory(root: Path, product: str = "codex") -> dict:
    """Load and validate the exact canonical inventory and local state path."""
    result = json.loads((root / "ADAPTATION.example.json").read_bytes())
    components = result.get("components", {})
    if (
        result.get("schema_version") != 2
        or result.get("delivery_values") != ["pending", "installed", "unsupported"]
        or result.get("verification_values") != ["pending", "passed"]
        or set(components) != EXPECTED_GROUPS
    ):
        raise Conflict("The source inventory requires an installer update.")
    for category, suffix in (
        ("skills", None), ("instructions", ".md"), ("agents", ".md"),
        ("commands", ".md"), ("hooks", ".py"),
    ):
        paths = (
            [path for path in (root / category).iterdir()
             if path.is_dir() and not path.name.startswith(".")]
            if suffix is None else list((root / category).glob("*" + suffix))
        )
        expected = {
            path.name if suffix is None else path.stem: path.relative_to(root).as_posix()
            for path in paths
        }
        if {name: row.get("source") for name, row in components[category].items()} != expected:
            raise Conflict(f"Inventory and canonical {category} differ.")
    expected_shared = {
        "credentials": {
            "source": "shared/credentials/mainframe-secret",
            "delivery": "pending",
            "verification": "pending",
        }
    }
    if components["shared"] != expected_shared:
        raise Conflict("The shared-support inventory requires an installer update.")
    if {name: row.get("source") for name, row in components["plugins"].items()} != DSH_PLUGINS:
        raise Conflict("The DSH plugin inventory requires an installer update.")
    sources = []
    for group in components.values():
        for name, row in group.items():
            path = root / row.get("source", "")
            if (
                not re.fullmatch(r"[a-z][a-z0-9-]*", name)
                or row.get("delivery") != "pending"
                or row.get("verification") != "pending"
                or set(row) != {"source", "delivery", "verification"}
                or not path.exists()
                or not path.resolve().is_relative_to(root)
            ):
                raise Conflict(f"Invalid canonical source: {name}")
            sources.append(row["source"])
    if len(sources) != 55 or len(sources) != len(set(sources)):
        raise Conflict("The source inventory identities require an installer update.")
    for relative in (f"ADAPTATION.{product}.json", "shared/credentials/credentials-index.md"):
        owner = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        with tempfile.TemporaryDirectory(prefix="mainframe-ignore-") as temporary:
            command = ["git", "-C", str(root)]
            if owner.returncode or Path(owner.stdout.strip()).resolve() != root:
                subprocess.run(
                    ["git", "init", "--bare", "--template=", "-q", temporary],
                    check=True,
                )
                command += [
                    "--git-dir=" + temporary,
                    "--work-tree=" + str(root),
                    "-c", "core.excludesFile=/dev/null",
                ]
            if subprocess.run(command + ["check-ignore", "-q", relative]).returncode:
                raise Conflict(f"Installation-local file must be ignored: {relative}")
    return result


def _instruction(current: bytes | None, body: str, prior: dict | None, remove=False):
    text = (current or b"").decode("utf-8")
    if prior:
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            raise Conflict(
                "The managed global instruction boundary changed; preserve the current "
                "global file and reconcile its ownership before applying. Do not append "
                "another managed block."
            )
        start, end = text.index(BEGIN), text.index(END) + len(END)
        if text[end:end + 1] == "\n":
            end += 1
        if digest(text[start:end].encode()) != prior["sha256"]:
            raise Conflict("The managed global instruction was edited; reconcile its semantics first.")
        prefix, suffix = text[:start], text[end:]
        if remove:
            separator = prior.get("separator", "")
            if separator and prefix.endswith(separator):
                prefix = prefix[:-len(separator)]
            result = (prefix + suffix).encode()
            return None if not result and prior["created"] else result, None
    else:
        if remove:
            return current, None
        if BEGIN in text or END in text or "MAINFRAME managed supplement" in text:
            raise Conflict("An older or unowned MAINFRAME instruction block needs scoped migration.")
        separator = "" if not text or text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n"
        prior = {"created": current is None, "separator": separator}
        prefix, suffix = text + separator, ""
    block = BEGIN + "\n" + body.rstrip() + "\n" + END + "\n"
    return (prefix + block + suffix).encode(), {**prior, "sha256": digest(block.encode())}

"""Product-neutral inventory and managed-instruction helpers."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile

from .core import Conflict, digest


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
    if len(sources) != 38 or len(sources) != len(set(sources)):
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

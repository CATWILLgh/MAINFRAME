"""Explicit, auth-free catalog probe for an already inspected Desktop engine.

Run only for assigned adapter acceptance. It uses disposable source/home trees,
starts no model turn, and does not exercise or trust the discovered hooks.
"""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from installer.codex import CURRENT_DESKTOP_RUNTIME, Codex
from installer.codex_native import Native, summarize
from installer.core import transact
from installer.shared import inventory


def probe(engine: Path, expected_version: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="mainframe-codex-contract-") as temporary:
        base = Path(temporary).resolve()
        source, home, workspace = (base / name for name in ("source", "home", "workspace"))
        source.mkdir()
        (workspace / ".git").mkdir(parents=True)
        for directory in ("instructions", "skills", "agents", "commands", "hooks", "plugins"):
            shutil.copytree(ROOT / directory, source / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("ADAPTATION.example.json", ".gitignore", "install.py"):
            shutil.copyfile(ROOT / name, source / name)
        credentials = source / "shared/credentials"
        credentials.mkdir(parents=True)
        for name in ("mainframe-secret", "credentials-index.template.md"):
            shutil.copyfile(ROOT / "shared/credentials" / name, credentials / name)
        adapter = Codex(source, home, version=expected_version, surface="desktop")
        changes, _ = adapter.plan(instructions_reviewed=True)
        transact(changes, adapter.journal, adapter.allowed)
        config = adapter.codex / "config.toml"
        config.write_text('cli_auth_credentials_store = "file"\n' + config.read_text()
                          + '\n[analytics]\nenabled = false\n')
        environment = {"PATH": os.defpath, "HOME": str(home), "CODEX_HOME": str(adapter.codex),
                       "RUST_LOG": "error"}
        version = subprocess.run([str(engine), "--version"], env=environment, cwd=workspace,
                                 capture_output=True, text=True, timeout=10, check=True)
        if version.stdout.strip() != f"codex-cli {expected_version}":
            raise AssertionError("The supplied engine differs from the assigned version.")
        with patch.dict(os.environ, environment, clear=True):
            with Native(str(engine)) as native:
                skill_result = native.rpc("skills/list", {"cwds": [str(workspace)], "forceReload": True})
                hook_result = native.rpc("hooks/list", {"cwds": [str(workspace)]})
                native.rpc("config/read", {"cwd": str(workspace), "includeLayers": False})
        result = summarize(adapter, inventory(source), skill_result, hook_result, workspace)
        for category in ("skills", "commands", "hooks"):
            missing = [name for name, row in result[category].items() if not row["discovered"]]
            if missing:
                raise AssertionError(f"Native {category} discovery mismatch: {missing}")
        diagnostics = [entry for group in (*skill_result["data"], *hook_result["data"])
                       for entry in group.get("errors", group.get("diagnostics", []))]
        if diagnostics:
            raise AssertionError("Native discovery returned diagnostics.")
        return {
            "version": expected_version,
            "binary_sha256": sha256(engine.read_bytes()).hexdigest(),
            "discovered": {category: len(result[category]) for category in ("skills", "commands", "hooks")},
            "diagnostics": len(diagnostics),
            "hook_trust": sorted({row.get("trustStatus", "unreported")
                                  for group in hook_result["data"] for row in group["hooks"]}),
            "scope": "disposable app-server catalog/config parsing; no model turns, hook execution, trust or live-profile acceptance",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--expected-version", default=CURRENT_DESKTOP_RUNTIME)
    arguments = parser.parse_args()
    print(json.dumps(probe(arguments.engine.resolve(), arguments.expected_version), indent=2))

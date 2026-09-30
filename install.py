#!/usr/bin/env python3
"""One MAINFRAME installation entrypoint. Run from the source repository root."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
if sys.version_info < (3, 11):
    print('{"error": "The MAINFRAME installer needs Python 3.11 or newer."}', file=sys.stderr)
    raise SystemExit(2)

if os.name != "posix":
    print('{"error": "This installer currently targets macOS and Linux."}', file=sys.stderr)
    raise SystemExit(2)

from installer.codex import Codex, HOOK_NAMES, KNOWN_RUNTIME, CONTENT_UPDATE_RUNTIMES, desktop_version, native_version
from installer.core import Conflict, installation_lock, restore, transact


def show(report, details=False):
    report = dict(report)
    if not details and "changes" in report:
        changes = report.pop("changes")
        grouped = {}
        for change in changes:
            group = grouped.setdefault(change["component"], {"files": 0, "actions": set(), "paths": []})
            group["files"] += 1
            group["actions"].add(change["action"])
            group["paths"].append(change["path"])
        report["file_change_count"] = len(changes)
        report["components_changed"] = {name: {"files": group["files"], "actions": sorted(group["actions"]),
            "destination": os.path.commonpath(group["paths"])} for name, group in grouped.items()}
    print(json.dumps(report, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", choices=["antigravity", "cline", "codex", "minimax", "zcode"])
    parser.add_argument("action", choices=["plan", "apply", "verify", "disable", "enable", "uninstall", "recover"])
    parser.add_argument("--home", type=Path, default=Path.home(), help="Explicit target home; isolated fixture roots never imply native proof")
    parser.add_argument("--zcode-home", type=Path, help="Explicit ZCode configuration root")
    parser.add_argument("--zcode-app", type=Path, help="ZCode Desktop application whose plist provides the build")
    parser.add_argument("--gemini-home", type=Path, help="Explicit Antigravity shared configuration root")
    parser.add_argument("--antigravity-app", type=Path, help="Antigravity Desktop application whose plist provides the release")
    parser.add_argument("--minimax-home", type=Path, help="Explicit MiniMax Code data directory")
    parser.add_argument("--minimax-app", type=Path, help="MiniMax Code Desktop application whose plist provides the release")
    parser.add_argument("--cline-home", type=Path, help="Explicit Cline configuration root")
    parser.add_argument("--cline-app", type=Path, help="Cline Desktop application whose plist provides the release")
    parser.add_argument("--adopt-existing", action="store_true", help="Adopt only the recognized manual ZCode adaptation after a read-only plan")
    parser.add_argument("--codex-home", type=Path, help="Actual Codex config home; defaults to CODEX_HOME for the current user")
    parser.add_argument("--surface", choices=["desktop", "cli"], help="Current installation surface; required for plan, apply, and verify")
    parser.add_argument("--runtime-version", help="Fallback observed Desktop engine version when current-task metadata is unavailable")
    parser.add_argument("--executable", help="Codex executable for version and optional native discovery; never upgraded automatically")
    parser.add_argument("--native", action="store_true", help="Include read-only app-server discovery in verify; no model turns")
    parser.add_argument("--details", action="store_true", help="Include every changed path; default output groups files by component")
    parser.add_argument("--instructions-reviewed", action="store_true", help="The invoking agent has checked the existing and canonical instruction semantics")
    parser.add_argument("--hook", help="One maintained hook for enable/disable; default is all hooks for the selected product")
    args = parser.parse_args(argv)
    if args.hook and args.action not in ("enable", "disable"):
        parser.error("--hook applies only to enable or disable")
    if args.native and args.action != "verify":
        parser.error("--native applies only to verify")
    if args.action in ("plan", "apply", "verify") and not args.surface:
        parser.error("--surface desktop or --surface cli is required; use the surface running this installation")
    if args.surface == "desktop" and (args.executable or args.native):
        parser.error("Desktop installation does not launch the Codex CLI or app-server; inspect the current app surface")
    if args.runtime_version and args.surface != "desktop":
        parser.error("--runtime-version applies only to Desktop; CLI reads its own version")
    root = Path(__file__).resolve().parent
    if Path.cwd().resolve() != root:
        raise Conflict("Open the MAINFRAME repository and run its installer from that root.")
    if args.product == "zcode":
        return zcode_main(args, root, parser)
    if args.product == "antigravity":
        return antigravity_main(args, root, parser)
    if args.product == "minimax":
        return minimax_main(args, root, parser)
    if args.product == "cline":
        return cline_main(args, root, parser)
    if (args.adopt_existing or args.zcode_home or args.zcode_app or args.gemini_home
            or args.antigravity_app or args.minimax_home or args.minimax_app
            or args.cline_home or args.cline_app):
        parser.error("Options for another product cannot modify a Codex installation")
    if args.hook and args.hook not in HOOK_NAMES:
        parser.error("Unknown maintained Codex hook")
    codex_home = args.codex_home
    if codex_home is None and args.home.resolve() == Path.home().resolve() and os.environ.get("CODEX_HOME"):
        codex_home = Path(os.environ["CODEX_HOME"])
    executable, version = None, None
    if args.action in ("plan", "apply", "verify"):
        if args.surface == "desktop":
            version = desktop_version(codex_home or args.home / ".codex", os.environ.get("CODEX_THREAD_ID"))
            if version and args.runtime_version and version != args.runtime_version:
                raise Conflict("--runtime-version conflicts with the current Desktop task's engine metadata.")
            version = version or args.runtime_version
            if not version:
                raise Conflict("Current-task Desktop engine metadata is unavailable; supply --runtime-version from app engine metadata, never from CLI or the app release number.")
        else:
            executable = args.executable or shutil.which("codex")
            version = native_version(executable) if executable else None
    adapter = Codex(root, args.home, codex_home, version, surface=args.surface)
    if args.action in ("plan", "verify"):
        changes, report = adapter.plan(args.instructions_reviewed)
        if version in CONTENT_UPDATE_RUNTIMES:
            adapter.validate_content_update(changes, adapter.receipt())
            report["delivery_mode"] = "existing-installation bounded update; content changes and validated Stop schema repair only"
        if args.action == "verify":
            report["structure_matches"] = not report["changes"]
            if args.native:
                if not executable:
                    raise Conflict("Specify the installed Codex executable for native discovery.")
                from installer.codex_native import discover
                report["native"] = discover(adapter, executable)
                native = report["native"]
                report["native_discovery_passed"] = not native["diagnostic_errors"] and all(
                    row["discovered"] and (category != "hooks" or row["trusted"] and not row["disabled"])
                    for category in ("skills", "commands", "hooks") for row in native[category].values()
                )
        show(report, args.details)
        return 0 if args.action == "plan" or (report["structure_matches"] and report.get("native_discovery_passed", True)) else 1
    if args.action == "apply" and version not in {KNOWN_RUNTIME, *CONTENT_UPDATE_RUNTIMES}:
        raise Conflict("This installer targets the inspected Codex mapping for runtime " + KNOWN_RUNTIME +
                       "; revalidate the native mapping for the detected runtime before activation. No runtime is upgraded automatically.")
    with installation_lock(adapter.lock_path):
        if args.action == "recover":
            restore(adapter.journal, adapter.allowed)
            report = {"recovered": True, "note": "Prior file state restored; recheck native behavior before continuing."}
        elif args.action in ("disable", "enable"):
            transact(adapter.control(args.action == "enable", args.hook), adapter.journal, adapter.allowed)
            if args.action == "disable":
                time.sleep(6)  # Registered synchronous hooks have a five-second native timeout.
            report = {"hook_control": args.action, "hooks": [args.hook] if args.hook else list(HOOK_NAMES)}
        else:
            remove = args.action == "uninstall"
            changes, report = adapter.plan(args.instructions_reviewed, remove)
            if report.get("instruction_review"):
                raise Conflict(report["instruction_review"])
            old_receipt = adapter.receipt()
            if not remove and version in CONTENT_UPDATE_RUNTIMES:
                adapter.validate_content_update(changes, old_receipt)
                report["delivery_mode"] = "existing-installation bounded update; content changes and validated Stop schema repair only"
            if remove and old_receipt:
                transact(adapter.control(False, None), adapter.journal, adapter.allowed)
                time.sleep(6)
                changes, report = adapter.plan(args.instructions_reviewed, remove=True)
            transact(changes, adapter.journal, adapter.allowed)
            if remove:
                adapter.clean_event_state()
                adapter.clean_directories(old_receipt)
            else:
                # A destination migration can retire every file from an old
                # installer-created component tree. Prune only receipt-owned
                # directories that are now empty; rmdir preserves any user or
                # foreign material without another discovery pass.
                adapter.clean_directories(adapter.receipt())
            report["applied"] = True
            report["native_acceptance"] = "Record current-surface discovery and any user activation/reload handoff; do not start model probes. See docs/installation/codex-installer.md." if not remove else "Cached inline commands remain neutral without implementation."
        show(report, args.details)
    return 0


def zcode_main(args, root, parser):
    from installer.zcode import (ZCode, KNOWN_RUNTIME as ZCODE_RUNTIME,
        CONTENT_UPDATE_RUNTIMES as ZCODE_CONTENT_UPDATE_RUNTIMES,
        desktop_version as zcode_version)
    if (args.codex_home or args.gemini_home or args.antigravity_app or args.minimax_home
            or args.minimax_app or args.cline_home or args.cline_app
            or args.native or args.executable or args.surface == "cli"):
        parser.error("The maintained ZCode route targets Desktop only and never starts a CLI agent")
    if args.adopt_existing and args.action not in ("plan", "apply", "verify"):
        parser.error("--adopt-existing applies only to a ZCode delivery plan, apply, or verify")
    version = None
    if args.action in ("plan", "apply", "verify"):
        # Isolated fixtures may supply their explicitly simulated runtime.
        version = args.runtime_version
        if args.home.resolve() == Path.home().resolve() or not version:
            observed_version = zcode_version(args.zcode_app or Path("/Applications/ZCode.app"))
            if version and version != observed_version:
                raise Conflict("Supplied ZCode build conflicts with the selected Desktop application")
            version = observed_version
        if version not in {ZCODE_RUNTIME, *ZCODE_CONTENT_UPDATE_RUNTIMES}:
            raise Conflict("Revalidate the maintained ZCode mapping for this build; supported full mapping is " + ZCODE_RUNTIME)
    from installer.zcode import HOOK_NAMES as ZCODE_HOOK_NAMES
    if args.hook and args.hook not in ZCODE_HOOK_NAMES:
        parser.error("Unknown maintained ZCode hook")
    adapter = ZCode(root, args.home, args.zcode_home, version, args.surface, args.adopt_existing)
    if args.action in ("plan", "verify"):
        changes, report = adapter.plan(args.instructions_reviewed)
        if version in ZCODE_CONTENT_UPDATE_RUNTIMES:
            adapter.validate_content_update(changes, adapter.receipt())
            report["delivery_mode"] = "existing-installation bounded update; skills and validated hook transport/lifecycle updates only"
        if args.action == "verify": report["structure_matches"] = not report["changes"]
        show(report, args.details)
        return 0 if args.action == "plan" or report["structure_matches"] else 1
    with installation_lock(adapter.lock_path):
        if args.action == "recover":
            restore(adapter.journal, adapter.allowed)
            report = {"recovered": True}
        elif args.action in ("disable", "enable"):
            transact(adapter.control(args.action == "enable", args.hook), adapter.journal, adapter.allowed)
            if args.action == "disable": time.sleep(6)
            report = {"hook_control": args.action, "hooks": [args.hook] if args.hook else list(ZCODE_HOOK_NAMES)}
        else:
            remove = args.action == "uninstall"
            changes, report = adapter.plan(args.instructions_reviewed, remove)
            if report.get("instruction_review"): raise Conflict(report["instruction_review"])
            previous = adapter.receipt()
            if not remove and version in ZCODE_CONTENT_UPDATE_RUNTIMES:
                adapter.validate_content_update(changes, previous)
                report["delivery_mode"] = "existing-installation bounded update; skills and validated hook transport/lifecycle updates only"
            if remove and previous:
                transact(adapter.control(False), adapter.journal, adapter.allowed)
                time.sleep(6)
                changes, report = adapter.plan(args.instructions_reviewed, remove=True)
            transact(changes, adapter.journal, adapter.allowed)
            if remove:
                adapter.clean_event_state()
                adapter.clean_directories(previous)
            else:
                adapter.clean_directories(adapter.receipt())
            report["applied"] = True
            report["native_acceptance"] = "This apply command did not run native probes; existing evidence is preserved only for unchanged artifacts."
        show(report, args.details)
    return 0


def antigravity_runtime(args, version_reader):
    if args.action not in ("plan", "apply", "verify"):
        return None
    version = args.runtime_version
    if args.home.resolve() == Path.home().resolve() or not version:
        observed = version_reader(args.antigravity_app or Path("/Applications/Antigravity.app"))
        if version and version != observed:
            raise Conflict("Supplied Antigravity release conflicts with the selected Desktop application")
        version = observed
    return version


def antigravity_main(args, root, parser):
    from installer.antigravity import (
        Antigravity, HOOK_NAMES as ANTIGRAVITY_HOOK_NAMES,
        KNOWN_RUNTIME as ANTIGRAVITY_RUNTIME, desktop_version as antigravity_version,
    )
    if (args.codex_home or args.zcode_home or args.zcode_app or args.adopt_existing
            or args.minimax_home or args.minimax_app or args.cline_home or args.cline_app
            or args.native or args.executable or args.surface == "cli"):
        parser.error("The maintained Antigravity route targets Desktop 2.0 only and never starts a CLI or IDE agent")
    if args.hook and args.hook not in ANTIGRAVITY_HOOK_NAMES:
        parser.error("Unknown maintained Antigravity hook")
    version = antigravity_runtime(args, antigravity_version)
    adapter = Antigravity(root, args.home, args.gemini_home, version, args.surface)
    if args.action in ("plan", "verify"):
        _, report = adapter.plan(args.instructions_reviewed)
        if args.action == "verify":
            report["structure_matches"] = not report["changes"]
        show(report, args.details)
        return 0 if args.action == "plan" or report["structure_matches"] else 1
    if args.action == "apply" and version != ANTIGRAVITY_RUNTIME:
        raise Conflict("Revalidate the maintained Antigravity mapping for this release; supported release is " + ANTIGRAVITY_RUNTIME)
    with installation_lock(adapter.lock_path):
        if args.action == "recover":
            restore(adapter.journal, adapter.allowed)
            report = {"recovered": True}
        elif args.action in ("disable", "enable"):
            transact(adapter.control(args.action == "enable", args.hook), adapter.journal, adapter.allowed)
            if args.action == "disable":
                time.sleep(6)
            report = {"hook_control": args.action,
                      "hooks": [args.hook] if args.hook else list(ANTIGRAVITY_HOOK_NAMES)}
        else:
            remove = args.action == "uninstall"
            changes, report = adapter.plan(args.instructions_reviewed, remove)
            if report.get("instruction_review"):
                raise Conflict(report["instruction_review"])
            previous = adapter.receipt()
            if not remove and report.get("retiring_hooks"):
                transact(adapter.control(False), adapter.journal, adapter.allowed)
                time.sleep(6)
                changes, report = adapter.plan(args.instructions_reviewed, remove=False)
            if remove and previous:
                if previous.get("hook_specs"):
                    transact(adapter.control(False), adapter.journal, adapter.allowed)
                    time.sleep(6)
                changes, report = adapter.plan(args.instructions_reviewed, remove=True)
            transact(changes, adapter.journal, adapter.allowed)
            if remove:
                adapter.clean_event_state()
                adapter.clean_directories(previous)
            else:
                adapter.clean_directories(adapter.receipt())
            report["applied"] = True
            report["native_acceptance"] = (
                "Open one new Antigravity Desktop 2.0 conversation and check native discovery; "
                "the installer did not start a model or the Antigravity CLI."
                if not remove else "Owned Antigravity configuration was removed."
            )
        show(report, args.details)
    return 0


def minimax_main(args, root, parser):
    from installer.minimax import (
        MiniMax, HOOK_NAMES as MINIMAX_HOOK_NAMES,
        desktop_version as minimax_version,
    )
    if (args.codex_home or args.zcode_home or args.zcode_app or args.gemini_home
            or args.antigravity_app or args.adopt_existing or args.cline_home or args.cline_app
            or args.native or args.executable or args.surface == "cli"):
        parser.error("The maintained MiniMax route targets Desktop only and never starts a CLI agent")
    if args.hook and args.hook not in MINIMAX_HOOK_NAMES:
        parser.error("Unknown maintained MiniMax hook")
    version = args.runtime_version
    if args.action in ("plan", "apply", "verify"):
        if args.home.resolve() == Path.home().resolve() or not version:
            observed_version = minimax_version(args.minimax_app or Path("/Applications/MiniMax Code.app"))
            if version and version != observed_version:
                raise Conflict("Supplied MiniMax release conflicts with the selected Desktop application")
            version = observed_version
    adapter = MiniMax(root, args.home, args.minimax_home, version, args.surface)
    if args.action in ("plan", "verify"):
        _, report = adapter.plan(args.instructions_reviewed)
        if args.action == "verify": report["structure_matches"] = not report["changes"]
        show(report, args.details)
        return 0 if args.action == "plan" or report["structure_matches"] else 1
    with installation_lock(adapter.lock_path):
        if args.action == "recover":
            restore(adapter.journal, adapter.allowed)
            report = {"recovered": True}
        elif args.action in ("disable", "enable"):
            transact(adapter.control(args.action == "enable", args.hook), adapter.journal, adapter.allowed)
            if args.action == "disable": time.sleep(11)
            report = {"hook_control": args.action,
                      "hooks": [args.hook] if args.hook else list(MINIMAX_HOOK_NAMES)}
        else:
            remove = args.action == "uninstall"
            changes, report = adapter.plan(args.instructions_reviewed, remove)
            previous = adapter.receipt()
            if remove and previous:
                transact(adapter.control(False), adapter.journal, adapter.allowed)
                time.sleep(11)
                changes, report = adapter.plan(args.instructions_reviewed, remove=True)
            transact(changes, adapter.journal, adapter.allowed)
            adapter.clean_directories(previous if remove else adapter.receipt())
            report["applied"] = True
            report["native_acceptance"] = (
                "MiniMax automatically rescans local Plugins. Open one new conversation and confirm "
                "MAINFRAME appears without scan diagnostics; no model probe was started."
                if not remove else "Owned MiniMax Plugin files were removed."
            )
        show(report, args.details)
    return 0


def cline_main(args, root, parser):
    from installer.cline import (
        Cline, HOOK_NAMES as CLINE_HOOK_NAMES,
        cli_version as cline_cli_version, desktop_version as cline_desktop_version,
    )
    if (args.codex_home or args.zcode_home or args.zcode_app or args.gemini_home
            or args.antigravity_app or args.minimax_home or args.minimax_app
            or args.adopt_existing or args.native or args.executable):
        parser.error("Options for another product cannot modify a Cline installation")
    if args.hook and args.hook not in CLINE_HOOK_NAMES:
        parser.error("Unknown maintained Cline hook")
    version = args.runtime_version
    if args.action in ("plan", "apply", "verify"):
        observed = (cline_desktop_version(args.cline_app or Path("/Applications/Cline.app"))
                    if args.surface == "desktop" else cline_cli_version())
        if version and version != observed:
            raise Conflict("Supplied Cline release conflicts with the observed " + args.surface + " version")
        version = observed
    adapter = Cline(root, args.home, args.cline_home, version, args.surface)
    if args.action in ("plan", "verify"):
        _, report = adapter.plan(args.instructions_reviewed)
        if args.action == "verify":
            report["structure_matches"] = not report["changes"]
        show(report, args.details)
        return 0 if args.action == "plan" or report["structure_matches"] else 1
    with installation_lock(adapter.lock_path):
        if args.action == "recover":
            restore(adapter.journal, adapter.allowed)
            report = {"recovered": True}
        elif args.action in ("disable", "enable"):
            transact(adapter.control(args.action == "enable", args.hook), adapter.journal, adapter.allowed)
            report = {"hook_control": args.action,
                      "hooks": [args.hook] if args.hook else list(CLINE_HOOK_NAMES)}
        else:
            remove = args.action == "uninstall"
            changes, report = adapter.plan(args.instructions_reviewed, remove)
            previous = adapter.receipt()
            if remove and previous:
                transact(adapter.control(False), adapter.journal, adapter.allowed)
                changes, report = adapter.plan(args.instructions_reviewed, remove=True)
            transact(changes, adapter.journal, adapter.allowed)
            if remove:
                adapter.clean_event_state()
            adapter.clean_directories(previous if remove else adapter.receipt())
            report["applied"] = True
            report["native_acceptance"] = (
                "Open one new Cline conversation in the selected surface and confirm MAINFRAME "
                "discovery without diagnostics; no session, model, or role probe was started."
                if not remove else "Owned Cline files were removed."
            )
        show(report, args.details)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Conflict, OSError, ValueError, subprocess.SubprocessError) as error:
        # Errors identify the boundary, never dump configuration or recovery data.
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        raise SystemExit(2)

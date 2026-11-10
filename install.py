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

from installer.codex import (Codex, HOOK_NAMES, KNOWN_RUNTIME, CONTENT_UPDATE_RUNTIMES,
                             INSPECTED_DESKTOP_RUNTIMES, DETECTOR_UPDATE_RUNTIMES, SELECTION_UPDATE_RUNTIMES, TEXT_UPDATE_RUNTIMES,
                             desktop_version, native_version, mapping_supported, runtime_tools)
from installer.core import Conflict, installation_lock, restore, transact
from installer.runtime import OPENSPEC_TOOLS, ensure as ensure_runtime, status as runtime_status, tools_for_hook


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


def add_runtime_status(report, adapter, tools):
    support = runtime_status(adapter.home, tools)
    report["runtime_support"] = support
    return support


def provision_runtime(report, adapter, tools, hook=None):
    selected = tools_for_hook(tools, hook)
    support = ensure_runtime(adapter.home, selected)
    report["runtime_support"] = support
    return support


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", choices=["codex", "dsh", "zcode"])
    parser.add_argument("action", choices=["plan", "apply", "verify", "disable", "enable", "uninstall", "recover", "package"])
    parser.add_argument("--home", type=Path, default=Path.home(), help="Explicit target home; isolated fixture roots never imply native proof")
    parser.add_argument("--zcode-home", type=Path, help="Explicit ZCode configuration root")
    parser.add_argument("--zcode-app", type=Path, help="ZCode Desktop application whose plist provides the build")
    parser.add_argument("--adopt-existing", action="store_true", help="Adopt only the recognized manual ZCode adaptation after a read-only plan")
    parser.add_argument("--codex-home", type=Path, help="Actual Codex config home; defaults to CODEX_HOME for the current user")
    parser.add_argument("--surface", choices=["desktop", "cli"], help="Current installation surface; required for plan, apply, and verify")
    parser.add_argument("--runtime-version", help="Fallback observed Desktop engine version when current-task metadata is unavailable")
    parser.add_argument("--executable", help="Codex executable for version and optional native discovery; never upgraded automatically")
    parser.add_argument("--native", action="store_true", help="Include read-only app-server discovery in verify; no model turns")
    parser.add_argument("--details", action="store_true", help="Include every changed path; default output groups files by component")
    parser.add_argument("--instructions-reviewed", action="store_true", help="The invoking agent has checked the existing and canonical instruction semantics")
    parser.add_argument("--hook", help="One maintained hook for enable/disable; default is all hooks for the selected product")
    parser.add_argument("--skill", help="Deliver only this exact canonical skill into an existing Desktop installation")
    parser.add_argument("--todo", action="store_true", help="Deliver only the project idea command and its addressed guard into an existing Codex or ZCode Desktop installation")
    parser.add_argument("--output", type=Path, help="DSH package output directory outside the checkout; must not exist")
    args = parser.parse_args(argv)
    if args.product != "dsh" and (args.action == "package" or args.output):
        parser.error("package/--output are DSH-only")
    if args.product == "dsh":
        root = Path(__file__).resolve().parent
        if Path.cwd().resolve() != root:
            raise Conflict("Open the MAINFRAME repository and run its installer from that root.")
        if args.action not in ("plan", "verify", "package"):
            parser.error("DSH adapter supports plan/verify/package; use native plugin_manager for profile lifecycle actions")
        if args.action != "package" and (args.output):
            parser.error("DSH --output require package")
        if not args.surface:
            parser.error("DSH requires --surface desktop or --surface cli as selection metadata, not native proof")
        if (args.zcode_home or args.zcode_app or args.codex_home or args.adopt_existing
                or args.runtime_version or args.executable or args.native or args.instructions_reviewed
                or args.hook or args.skill is not None or args.todo):
            parser.error("DSH source adapter does not accept other-product, instruction, runtime, native, or component options")
        from installer.dsh import DSH
        if args.action == "package":
            if not args.output:
                parser.error("DSH package requires --output outside the checkout")
            from installer.dsh_package import build_packages
            show(build_packages(root, args.output), args.details)
            return 0
        _, report = DSH(root, args.home, surface=args.surface).plan()
        show(report, args.details)
        return 0  # Source validation only; report explicitly denies profile verification.
    if args.todo and (args.product not in ("codex", "zcode")
                      or args.action not in ("plan", "apply", "verify")
                      or args.surface != "desktop" or args.skill or args.hook or args.native
                      or args.adopt_existing):
        parser.error("--todo requires Codex or ZCode Desktop plan/apply/verify without other component selectors")
    if args.skill is not None and (args.action not in ("plan", "apply", "verify")
                                   or args.surface != "desktop" or args.native
                                   or args.adopt_existing or args.hook):
        parser.error("--skill requires Desktop plan/apply/verify without native probes or other selectors")
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
    if args.adopt_existing or args.zcode_home or args.zcode_app:
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
            # Stored thread metadata identifies the creation engine, not necessarily
            # the live engine after an app upgrade. Explicit observed evidence wins.
            version = args.runtime_version or version
            if not version:
                raise Conflict("Current-task Desktop engine metadata is unavailable; supply --runtime-version from app engine metadata, never from CLI or the app release number.")
        else:
            executable = args.executable or shutil.which("codex")
            version = native_version(executable) if executable else None
    adapter = Codex(root, args.home, codex_home, version, surface=args.surface)
    codex_tools = runtime_tools(version, args.surface)
    if args.action == "enable" and any(
            row.get("component") == "hooks.mainframe-fallow-quality"
            for row in adapter.receipt().get("files", {}).values()):
        codex_tools = tuple(dict.fromkeys((*codex_tools, "fallow")))
    if args.todo or args.skill is not None:
        return scoped_delivery(args, adapter)
    package_tools = codex_tools + OPENSPEC_TOOLS if mapping_supported(version, args.surface) else codex_tools
    if args.action in ("plan", "verify"):
        changes, report = adapter.plan(args.instructions_reviewed)
        support = add_runtime_status(report, adapter, package_tools)
        if version in CONTENT_UPDATE_RUNTIMES:
            adapter.validate_content_update(changes, adapter.receipt())
            report["delivery_mode"] = adapter.bounded_update_mode()
        if args.action == "verify":
            if version in DETECTOR_UPDATE_RUNTIMES | SELECTION_UPDATE_RUNTIMES | TEXT_UPDATE_RUNTIMES:
                report["scoped_update_matches"] = not report["changes"]
            report["structure_matches"] = not report["changes"] and support["ready"]
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
    if args.action == "apply" and not mapping_supported(version, args.surface) and version not in CONTENT_UPDATE_RUNTIMES:
        raise Conflict("This installer targets the inspected Codex mapping for runtime " + KNOWN_RUNTIME +
                       " and Desktop " + ", ".join(sorted(INSPECTED_DESKTOP_RUNTIMES)) +
                       "; revalidate the native mapping for the detected runtime before activation. No runtime is upgraded automatically.")
    with installation_lock(adapter.lock_path):
        if args.action == "recover":
            restore(adapter.journal, adapter.allowed)
            report = {"recovered": True, "note": "Prior file state restored; recheck native behavior before continuing."}
        elif args.action in ("disable", "enable"):
            report = {}
            if args.action == "enable":
                provision_runtime(report, adapter, codex_tools, args.hook)
            transact(adapter.control(args.action == "enable", args.hook), adapter.journal, adapter.allowed)
            if args.action == "disable":
                time.sleep(6)  # Registered synchronous hooks have a five-second native timeout.
            report.update({"hook_control": args.action, "hooks": [args.hook] if args.hook else list(HOOK_NAMES)})
        else:
            remove = args.action == "uninstall"
            changes, report = adapter.plan(args.instructions_reviewed, remove)
            if report.get("instruction_review"):
                raise Conflict(report["instruction_review"])
            old_receipt = adapter.receipt()
            if not remove and version in CONTENT_UPDATE_RUNTIMES:
                adapter.validate_content_update(changes, old_receipt)
                report["delivery_mode"] = adapter.bounded_update_mode()
            if not remove:
                if version in DETECTOR_UPDATE_RUNTIMES | SELECTION_UPDATE_RUNTIMES | TEXT_UPDATE_RUNTIMES:
                    # These bounded updates need no new analyzer provisioning.
                    # Keep unrelated hook dependency readiness visible without
                    # provisioning or modifying those existing dependencies.
                    add_runtime_status(report, adapter, codex_tools)
                else:
                    provision_runtime(report, adapter, package_tools)
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


def scoped_delivery(args, adapter):
    def plan():
        return adapter.plan_todo() if args.todo else adapter.plan_skill(args.skill)

    tools = OPENSPEC_TOOLS if args.skill == "mainframe-openspec" else ()
    if args.action == "apply":
        with installation_lock(adapter.lock_path):
            changes, report = plan()
            if tools:
                provision_runtime(report, adapter, tools)
            transact(changes, adapter.journal, adapter.allowed)
            report["applied"] = True
    else:
        _, report = plan()
        if tools:
            add_runtime_status(report, adapter, tools)
        if args.action == "verify":
            report["scoped_update_matches"] = not report["changes"]
    show(report, args.details)
    return 0 if args.action != "verify" or (
        report["scoped_update_matches"] and report.get("runtime_support", {}).get("ready", True)
    ) else 1


def zcode_main(args, root, parser):
    from installer.zcode import (ZCode, KNOWN_RUNTIME as ZCODE_RUNTIME,
        FULL_MAPPING_RUNTIMES as ZCODE_FULL_MAPPING_RUNTIMES,
        CONTENT_UPDATE_RUNTIMES as ZCODE_CONTENT_UPDATE_RUNTIMES,
        SKILL_DELIVERY_RUNTIMES as ZCODE_SKILL_DELIVERY_RUNTIMES,
        SINGLE_SKILL_RUNTIMES as ZCODE_SINGLE_SKILL_RUNTIMES,
        TODO_DELIVERY_RUNTIMES as ZCODE_TODO_DELIVERY_RUNTIMES,
        runtime_tools as zcode_runtime_tools,
        desktop_version as zcode_version)
    if (args.codex_home
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
        permitted = (ZCODE_TODO_DELIVERY_RUNTIMES if args.todo else
                     ZCODE_FULL_MAPPING_RUNTIMES | ZCODE_CONTENT_UPDATE_RUNTIMES | ZCODE_SKILL_DELIVERY_RUNTIMES)
        if args.skill is not None:
            permitted = ZCODE_SINGLE_SKILL_RUNTIMES
        if version not in permitted:
            raise Conflict("Revalidate the maintained ZCode mapping for this build; supported full mapping is " + ZCODE_RUNTIME)
    from installer.zcode import HOOK_NAMES as ZCODE_HOOK_NAMES
    if args.hook and args.hook not in ZCODE_HOOK_NAMES:
        parser.error("Unknown maintained ZCode hook")
    adapter = ZCode(root, args.home, args.zcode_home, version, args.surface, args.adopt_existing)
    zcode_tools = zcode_runtime_tools(version, args.surface)
    if args.action == "enable" and any(
            row.get("component") == "hooks.mainframe-fallow-quality"
            for row in adapter.receipt().get("files", {}).values()):
        zcode_tools = tuple(dict.fromkeys((*zcode_tools, "fallow")))
    if args.todo or args.skill is not None:
        return scoped_delivery(args, adapter)
    package_tools = zcode_tools + OPENSPEC_TOOLS if version in ZCODE_FULL_MAPPING_RUNTIMES else zcode_tools
    if args.action in ("plan", "verify"):
        changes, report = adapter.plan(args.instructions_reviewed)
        support = add_runtime_status(report, adapter, package_tools)
        if version in ZCODE_CONTENT_UPDATE_RUNTIMES:
            adapter.validate_content_update(changes, adapter.receipt())
            report["delivery_mode"] = "existing-installation bounded update; skills and validated hook transport/lifecycle updates only"
        if version in ZCODE_SKILL_DELIVERY_RUNTIMES:
            adapter.validate_skill_delivery(changes, adapter.receipt())
            report["delivery_mode"] = "existing-installation bounded content delivery; Markdown skills, existing global instruction and destructive detector only"
        if args.action == "verify": report["structure_matches"] = not report["changes"] and support["ready"]
        show(report, args.details)
        return 0 if args.action == "plan" or report["structure_matches"] else 1
    with installation_lock(adapter.lock_path):
        if args.action == "recover":
            restore(adapter.journal, adapter.allowed)
            report = {"recovered": True}
        elif args.action in ("disable", "enable"):
            report = {}
            if args.action == "enable":
                provision_runtime(report, adapter, zcode_tools, args.hook)
            transact(adapter.control(args.action == "enable", args.hook), adapter.journal, adapter.allowed)
            if args.action == "disable": time.sleep(6)
            report.update({"hook_control": args.action, "hooks": [args.hook] if args.hook else list(ZCODE_HOOK_NAMES)})
        else:
            remove = args.action == "uninstall"
            changes, report = adapter.plan(args.instructions_reviewed, remove)
            if report.get("instruction_review"): raise Conflict(report["instruction_review"])
            previous = adapter.receipt()
            if not remove and version in ZCODE_CONTENT_UPDATE_RUNTIMES:
                adapter.validate_content_update(changes, previous)
                report["delivery_mode"] = "existing-installation bounded update; skills and validated hook transport/lifecycle updates only"
            if not remove and version in ZCODE_SKILL_DELIVERY_RUNTIMES:
                adapter.validate_skill_delivery(changes, previous)
                report["delivery_mode"] = "existing-installation bounded content delivery; Markdown skills, existing global instruction and destructive detector only"
            if not remove:
                provision_runtime(report, adapter, package_tools)
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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Conflict, OSError, ValueError, subprocess.SubprocessError) as error:
        # Errors identify the boundary, never dump configuration or recovery data.
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        raise SystemExit(2)

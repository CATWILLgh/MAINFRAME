"""Project neutral MAINFRAME skills into Antigravity Desktop 2.x."""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Callable


PLAN_ROOT_TOKEN = "{{mainframe.plans_root}}"
ANTIGRAVITY_PLAN_ROOT = "~/.gemini/antigravity/mainframe-plans"
ANTIGRAVITY_CREDENTIALS_INDEX = "~/.gemini/antigravity/credentials-index.md"


class ProjectionMode(str, Enum):
    BINDINGS_ONLY = "bindings-only"
    OVERLAY = "overlay"


SKILL_PROJECTION_POLICIES = {
    "code-audit": ProjectionMode.BINDINGS_ONLY,
    "curl-requests": ProjectionMode.OVERLAY,
    "decision-review": ProjectionMode.BINDINGS_ONLY,
    "frontend-design": ProjectionMode.BINDINGS_ONLY,
    "git-conventional-commits": ProjectionMode.BINDINGS_ONLY,
    "nestjs-backend-patterns": ProjectionMode.BINDINGS_ONLY,
    "nextjs-backend-patterns": ProjectionMode.BINDINGS_ONLY,
    "no-suppression-markers": ProjectionMode.BINDINGS_ONLY,
    "python-backend-patterns": ProjectionMode.BINDINGS_ONLY,
    "react-frontend-patterns": ProjectionMode.BINDINGS_ONLY,
    "secrets-handling": ProjectionMode.OVERLAY,
    "shadcn": ProjectionMode.BINDINGS_ONLY,
    "surface-ticket": ProjectionMode.BINDINGS_ONLY,
    "task-workflow": ProjectionMode.OVERLAY,
    "testing-strategy": ProjectionMode.BINDINGS_ONLY,
}

_RUNTIME_MARKERS = (
    PLAN_ROOT_TOKEN,
    "Claude Code",
    "~/.claude/",
    "CLAUDE.md",
    "settings.json",
    "permissions.deny",
    "~/.zshenv",
    "`EnterPlanMode`",
    "`ExitPlanMode`",
    "`AskUserQuestion`",
    "`TodoWrite`",
    "the `Agent` tool",
    "`run_in_background: true`",
    "`Explore`",
    "`WebSearch`",
    "`WebFetch`",
    "preloaded",
    "`skills:` frontmatter",
    "PostToolUse",
    "PreToolUse",
    "`advisor()`",
    "allowedPrompts",
)

_RUNTIME_REWRITES = (
    (PLAN_ROOT_TOKEN, ANTIGRAVITY_PLAN_ROOT),
    (
        "one parallel `Explore` subagent (the built-in read-only\nsearch agent)",
        "one parallel read-only search subagent",
    ),
    ("a project `CLAUDE.md`", "project instructions"),
    ("umbrella CLAUDE.md rules", "umbrella MAINFRAME plugin rules"),
    ("CLAUDE.md verification rules", "MAINFRAME plugin verification rules"),
    ("CLAUDE.md rule", "MAINFRAME plugin rule"),
    ("~/.claude/skills/mainframe/skills/", "~/.gemini/config/plugins/mainframe/skills/"),
    ("~/.claude/credentials-index.md", ANTIGRAVITY_CREDENTIALS_INDEX),
    ("~/.claude/plans", ANTIGRAVITY_PLAN_ROOT),
    ("`AskUserQuestion`", "ask the user directly in chat"),
    ("`TodoWrite`", "a persistent checklist"),
    ("`EnterPlanMode`", "interactive planning"),
    ("`ExitPlanMode`", "explicit plan approval"),
    ("the `Agent` tool", "`define_subagent` followed by `invoke_subagent`"),
    ("`run_in_background: true`", "background subagent execution"),
    ("`Explore`", "a read-only search subagent"),
    ("`WebSearch`", "web research tools"),
    ("`WebFetch`", "web research tools"),
)


def runtime_sensitive_skills(
    skill_texts: Mapping[str, Mapping[str, str]],
) -> set[str]:
    """Return source skills containing a runtime-specific contract marker."""
    sensitive = set()
    markers = tuple(marker.casefold() for marker in _RUNTIME_MARKERS)
    for skill, files in skill_texts.items():
        if any(
            marker in text.casefold()
            for text in files.values()
            for marker in markers
        ):
            sensitive.add(skill)
    return sensitive


def validate_skill_projection_inventory(
    skill_texts: Mapping[str, Mapping[str, str]],
) -> None:
    sensitive = runtime_sensitive_skills(skill_texts)
    unknown = sorted(sensitive - SKILL_PROJECTION_POLICIES.keys())
    if unknown:
        names = ", ".join(unknown)
        raise ValueError(f"runtime-sensitive skills lack projection policy: {names}")
    present = set(skill_texts)
    overlay_skills = {skill for skill, _ in _OVERLAYS}
    for skill in sorted(present & SKILL_PROJECTION_POLICIES.keys()):
        mode = SKILL_PROJECTION_POLICIES[skill]
        has_overlay = skill in overlay_skills
        if (mode is ProjectionMode.OVERLAY) != has_overlay:
            raise ValueError(f"Antigravity skill projection policy mismatch: {skill}")
        if mode is ProjectionMode.OVERLAY:
            required = {relative for name, relative in _OVERLAYS if name == skill}
            missing = sorted(required - skill_texts[skill].keys())
            if missing:
                targets = ", ".join(missing)
                raise ValueError(
                    f"Antigravity skill projection targets missing: {skill}: {targets}"
                )


def _replace_once(text: str, source: str, replacement: str, label: str) -> str:
    if text.count(source) != 1:
        raise ValueError(f"Antigravity skill projection anchor drift: {label}")
    return text.replace(source, replacement)


def _rewrite_secrets(text: str, label: str) -> str:
    replacements = (
        (
            "Direct reads of the credentials store are denied by `settings.json` patterns.",
            "Direct reads of the credentials store are forbidden by this policy. "
            "Antigravity permission settings are user-owned and are not installed by this plugin.",
        ),
        (
            "Direct read of `~/.ssh/id_*` / `~/.netrc` is denied.",
            "Direct read of `~/.ssh/id_*` / `~/.netrc` is forbidden by this policy.",
        ),
        (
            "| 2 | Generic API tokens, passwords, anything that maps to a shell env-var | `~/.config/credentials/secrets.env` (0600); auto-sourced from `~/.zshenv` | Direct read denied. Access only through `secret get NAME` or as env-var (already in scope when called from a shell that sourced the file). |",
            "| 2 | Generic API tokens, passwords, anything that maps to a shell env-var | `~/.config/credentials/secrets.env` (0600) | Direct read is forbidden by this policy. Access only through `secret get NAME`, or as an env-var already present in the command environment. |",
        ),
        (
            "These are enforced by `permissions.deny` in `settings.json` and by `path-validation.py` (PreToolUse hook). The skill is the policy; the hook is the safety net.",
            "This skill is the policy. The plugin does not install Antigravity permissions; configure user-owned global or project `Deny` rules when a mechanical boundary is required.",
        ),
        (
            "**Pattern A — secret is already in the shell environment** (because `~/.zshenv` sourced the store at session start):",
            "**Pattern A — secret is already present in the command environment:**",
        ),
        (
            "**Pattern B — secret is in the store but not in env** (rare — for example, a token you just `secret set` and want to use without restarting the shell):",
            "**Pattern B — secret is in the store but not in the command environment:**",
        ),
        ("# denied by hook", "# forbidden: exposes the credential store"),
        (
            "the auto-mode classifier evaluates each tool call in isolation, cannot see conversational authorization, and hard-denies cross-project credential reads (witnessed 2026-06-15); and ",
            "direct reads bypass the managed credential flow; ",
        ),
        (
            "## Auto-mode caveat\n\nThe store is sourced by `~/.zshenv` at shell start. Claude Code's Bash subprocess always reads `~/.zshenv` (not `.zshrc`), so the secrets are present in env for all commands you run, including unattended auto-runs.\n\nIf a secret is missing from env (recently added via `secret set` but the current shell predates the change, or sourcing failed) — use Pattern B (`$(secret get NAME)`) explicitly. Do not try to `source ~/.zshenv` to reload — it may have side effects on the current Bash subprocess state.",
            "## Shell environment caveat\n\nAntigravity does not document which shell startup files commands read. Never assume a stored secret is present in the command environment.\n\nIf a secret is missing from the environment, use Pattern B (`$(secret get NAME)`) explicitly. Do not load shell startup files to recover it; they may have unrelated side effects.",
        ),
        (
            "- `path-validation.py` (PreToolUse hook) — enforces denial of direct reads on `~/.config/credentials/`; this skill is the policy, hook is the safety net.",
            "- `path-validation.py` (PreToolUse hook) — guards destructive path operations; it does not enforce this credential policy.",
        ),
        (
            "- `secret` helper script (`~/.local/bin/secret`) — installed by `install.sh`; the only sanctioned read/write interface to the tier-2 store.",
            "- `secret` helper script (`~/.local/bin/secret`) — supplied by MAINFRAME's separate profile installation; when available, it is the only sanctioned read/write interface to the tier-2 store.",
        ),
    )
    for source, replacement in replacements:
        text = _replace_once(text, source, replacement, label)
    return text


def _rewrite_curl(text: str, label: str) -> str:
    source = "**Where tokens come from.** If [`secrets-handling`](../secrets-handling/SKILL.md) is active on this machine, generic API tokens live in `~/.config/credentials/secrets.env` and are loaded into the shell environment by `~/.zshenv`. The patterns below assume this — `$API_TOKEN` resolves because the store was sourced at shell start. If the token is in the store but not in the current shell env (e.g. just added via `secret set`), substitute inline: `$(secret get API_TOKEN)`. If `secrets-handling` is not active, treat the env-var examples as \"replace with whatever your project's credential source is\" (vault CLI, project `.env`, etc.) — the curl patterns themselves are agnostic."
    replacement = "**Where tokens come from.** If [`secrets-handling`](../secrets-handling/SKILL.md) is active on this machine, generic API tokens live in `~/.config/credentials/secrets.env`. Use `$API_TOKEN` only when it is already present in the command environment; otherwise substitute inline with `$(secret get API_TOKEN)`. If `secrets-handling` is not active, treat the env-var examples as \"replace with whatever your project's credential source is\" (vault CLI, project `.env`, etc.) — the curl patterns themselves are agnostic."
    return _replace_once(text, source, replacement, label)


def _rewrite_workflow_skill(text: str, label: str) -> str:
    replacements = (
        (f"Plan files land in `{PLAN_ROOT_TOKEN}/<basename(cwd)>/<YYYY-MM-DD>-<topic>.md`", f"Plan audit copies land in `{ANTIGRAVITY_PLAN_ROOT}/audit/<basename(cwd)>/<YYYY-MM-DD>-<topic>.md`"),
        ("uses `EnterPlanMode` / `ExitPlanMode` when present", "`/goal` auto-approves the plan; otherwise written plans await an explicit go"),
        ("before a `/goal`, an `ExitPlanMode` approval, or an explicit \"go\"", "before a `/goal`, an approved plan, or an explicit \"go\""),
        ("ask **decision-level** questions through `AskUserQuestion`", "ask **decision-level** questions directly in chat"),
        ("plan approved via `ExitPlanMode`", "plan presented and approved with an explicit go"),
        ("structured questions and plan mode are appropriate here", "direct questions and an explicit plan-approval exchange are appropriate here"),
        ("headless `claude -p`, a scheduled run", "a headless or scheduled run"),
        ("  - User present: surface the fork through `AskUserQuestion`, not a free-text chat question. Phrase the question and every option in plain, concrete language a non-technical reader answers at a glance; lean on the built-in Other for the free-form path. It is non-blocking — the user can pick Other or just type in chat — so prefer it whenever a real decision-fork needs the user, and skip it when there is no fork.", "  - User present: ask the user about the fork directly in chat. Phrase the question and every option in plain, concrete language a non-technical reader can answer at a glance. Prefer a direct question whenever a real decision-fork needs the user, and skip it when there is no fork."),
        ("a read-only search sub-agent digest (Claude Code: `Explore`)", "a read-only search sub-agent digest"),
        ("persistent todo checklist (Claude Code: `TodoWrite`)", "persistent checklist"),
        ("multiple sub-agent calls (Claude Code: the `Agent` tool)", "multiple dynamic subagent calls"),
        ("background fan-out where offered (Claude Code: `run_in_background: true`)", "background fan-out where supported"),
        ("the two plan-file paths (interactive tool file vs the always-written hub audit copy), and the interactive-vs-auto workflow", "the Antigravity plan/audit workflow and its interactive-vs-auto approval path"),
        ("the same way `decision-reviewer` does", "with the same stakes-based scaling as `decision-review`"),
        ("dispatch `decision-reviewer` FIRST", "invoke `delegate-decision-reviewer` FIRST"),
        ("dispatch the `decision-reviewer` agent", "follow [`delegate-decision-reviewer`](../delegate-decision-reviewer/SKILL.md) to define and invoke a fresh specialist reviewer"),
        ("**before** the advisor call", "**before** the Step 6b reviewer"),
        ("fold this into the advisor call", "fold this into the Step 6b review"),
        ("(advisor: holistic, sees your framing; decision-reviewer: adversarial, artifact-only)", "(Step 6b: holistic and sees your framing; decision review: adversarial and artifact-only)"),
        ("[`web-search`](../../agents/web-search.md)", "[`web-search`](../delegate-web-search/SKILL.md)"),
        ("[`decision-reviewer`](../../agents/decision-reviewer.md)", "[`delegate-decision-reviewer`](../delegate-decision-reviewer/SKILL.md)"),
        ("If the project has a `CLAUDE.md` listing specialised agents (e.g. `backend-python-developer`, `enterprise-react-developer`), use those.", "If the project instructions list specialised agents (e.g. `backend-python-developer`, `enterprise-react-developer`), use those."),
        ("It resolves the description language from the repo (explicit `CLAUDE.md` directive → existing commit history → English default)", "It resolves the description language from the repo (explicit commit-language directive → existing commit history → English default)"),
        ("- **Interactive + plan file exists:** wait for the plan-approval gate (Claude Code: `ExitPlanMode`, whose `allowedPrompts` captures the granted permissions); without such a gate, present the plan and await an explicit go. The approval is the execution authorization — no extra \"when to start?\" turn.", "- **Interactive + plan file exists:** if `/goal` is set, treat the plan as approved and continue without another confirmation. Otherwise, present the plan and await an explicit go. The approval is the execution authorization — no extra \"when to start?\" turn."),
        ("A casual \"ok / sounds good\" in regular chat is not a substitute for the plan-approval gate on a non-trivial change with a written plan. If a plan file exists in interactive mode, route through the gate.", "For a non-trivial change with a written plan, `/goal` carries automatic plan approval; otherwise present that plan and await an explicit go before execution."),
        ("**6b. Then `advisor()` as the final checkpoint — conditional on stakes, mirroring 6a.** Call `advisor()` after synthesis **and after any decision-review** — so the advisor sees the reviewer's verdict in the transcript and makes the last call before substantive work: proceed, or turn back to further investigation / redesign. **Skip this before-writing call only on a recon-confirmed trivial change** — low blast radius (not shared / contract / auth / security, no dependents to break), reversible, obvious approach. This is Step 6, so recon (Step 2) has already established the blast radius — the skip is evidence-based, not a guess; **record it** (one line in the plan / report) so an auto-mode mis-call is auditable. Any doubt, or anything above trivial → call it. advisor #2 (Step 12) runs regardless.", "**6b. Then invoke a fresh dynamic reviewer as the final checkpoint — conditional on stakes, mirroring 6a.** After synthesis and any decision review, define and invoke a fresh reviewer with the synthesis and the earlier verdict so it can decide whether to proceed or turn back. **Skip this before-writing review only on a recon-confirmed trivial change** — low blast radius (not shared / contract / auth / security, no dependents to break), reversible, obvious approach. This is Step 6, so recon (Step 2) has already established the blast radius; record the skip in the plan or report. Any doubt, or anything above trivial → invoke the reviewer. Dynamic reviewer #2 (Step 12) runs regardless."),
        ("- A critical advisor finding → revise plan / approach, re-call.", "- A critical reviewer finding → revise the plan or approach and repeat the checkpoint."),
        ("- A passed advisor → proceed.", "- A passed review checkpoint → proceed."),
        ("**Advisor unavailable** (absent tool, pairing failure, runtime without it) — substitute and record it: checkpoint #1 → a **fork subagent** as stand-in advisor where forking exists (inherits the conversation, parent model, cost), else `decision-reviewer` with a self-contained prompt (approach, alternatives, assumptions, files — it sees only the prompt); checkpoint #2 → a **fresh reviewer** on the diff (independence is the point, no fork).", "**Independent review implementation:** keep both checkpoints and record the reviewer used. At checkpoint #1, define and invoke a fresh dynamic reviewer with the synthesis and any Step 6a verdict. At checkpoint #2, define and invoke another fresh reviewer on the finished diff; independence is the point."),
        ("Before declaring the task complete — `advisor()` once more on the finished result. One round; this is validation, not re-design. **This call is unconditional, with one guarded exception: a pure-mechanical edit** — typo, rename, comment, or formatting with zero logic — **may skip advisor entirely, but only when both guards hold:** the change touches no exported / public identifier (nothing external can consume it), **and** no instruction-bearing text (`CLAUDE.md`, a skill, or an agent definition — those change agent behaviour, so they are never \"mechanical\"). Fail either guard → advisor #2 runs.", "Before declaring the task complete, define and invoke a fresh dynamic reviewer on the finished result. One round; this is validation, not re-design. **This review is unconditional, with one guarded exception: a pure-mechanical edit** — typo, rename, comment, or formatting with zero logic — **may skip it only when both guards hold:** the change touches no exported or public identifier, **and** no instruction-bearing text (`CLAUDE.md`, a skill, or an agent definition). Fail either guard → dynamic reviewer #2 runs."),
        ("If the advisor surfaces a new issue at this stage — verify it against the actual change. A finding the advisor missed during #1 but caught at #2 is worth fixing; a conflict between advisor and primary-source evidence is worth one reconcile call.", "If the fresh reviewer surfaces a new issue at this stage, verify it against the actual change. A finding missed during checkpoint #1 but caught at #2 is worth fixing; reconcile a conflict between the reviewer and primary-source evidence once."),
    )
    for source, replacement in replacements:
        text = _replace_once(text, source, replacement, label)
    return _rewrite_review_terms(text, label)


def _rewrite_workflow_flow(text: str, label: str) -> str:
    replacements = (
        ("  HS -->|yes| RV[6a decision-reviewer]", "  HS -->|yes| RV[6a decision-review]"),
        ("  RV --> AV[6b advisor #1]", "  RV --> AV[6b dynamic reviewer #1]"),
        ("  ED --> A2[12 advisor #2<br/>unconditional bar guarded mechanical skip]", "  ED --> A2[12 dynamic reviewer #2<br/>unconditional bar guarded mechanical skip]"),
        ("**Turn-backs (the redirects that matter):** advisor #1 loops to Synthesis (revise the approach) or Recon (re-investigate) before any writing, and is itself conditional — skipped (and the skip recorded) on a recon-confirmed trivial, low-blast-radius change; Verify loops to Execution on a mismatch (cap 2); advisor #2 loops to Execution if it surfaces a new issue.", "**Turn-backs (the redirects that matter):** dynamic reviewer #1 loops to Synthesis (revise the approach) or Recon (re-investigate) before any writing, and is itself conditional — skipped (and the skip recorded) on a recon-confirmed trivial, low-blast-radius change; Verify loops to Execution on a mismatch (cap 2); dynamic reviewer #2 loops to Execution if it surfaces a new issue."),
    )
    for source, replacement in replacements:
        text = _replace_once(text, source, replacement, label)
    return text


def _rewrite_workflow_plan(text: str, label: str) -> str:
    replacements = (
        (f"| Tool plan file (interactive `EnterPlanMode` only) | `{PLAN_ROOT_TOKEN}/<random-kebab-slug>.md` — flat, no date | Claude Code tool (path injected via plan-mode system message) | Single session; tool may reuse / replace |", "| Interactive plan approval | `/goal` auto-approves; otherwise present the plan in chat and await an explicit go | Antigravity conversation | Current session |"),
        ("Verified against Claude Code plan mode (2026-05-30): the tool path is flat with a random slug; the hub audit copy lives under `audit/` so it never collides. `<basename(cwd)>` from `basename \"$(pwd)\"` (no per-project config); `<topic>` is a ≤ 6-word kebab slug. `mkdir -p` the dir; the audit copy is never tracked by git.", "Antigravity has no documented native plan-mode tool or injected plan-file path. The hub audit copy remains skill-owned, outside the repository, and never tracked by git."),
        ("- **Interactive** — tool plan mode's 5 phases: `EnterPlanMode` → Explore agents (1-3) → Plan agents (1-3) → Review (read critical files, `AskUserQuestion`) → Write (into **both** the tool plan file and the hub audit copy) → `ExitPlanMode` for approval.", "- **Interactive** — run the same five phases with ordinary reasoning and subagents: Explore → Plan → Review (read critical files and ask the user directly in chat) → Write the hub audit copy. If `/goal` is set, continue under its automatic plan approval; otherwise present the plan and await an explicit go."),
        ("- **Auto** — same Phase 1-4 without the tool: skip `EnterPlanMode`; Explore + Plan still run; Review is internal reasoning; Write only the hub audit copy; then proceed (no `ExitPlanMode`).", "- **Auto** — run the same phases; Review is internal reasoning, write only the hub audit copy, then proceed without a blocking gate."),
        (f"## Runtime note\n\nThe five-phase interactive flow above and the audit-copy home\n(`{PLAN_ROOT_TOKEN}/<project>/`) are Claude Code conventions. On a runtime\nwithout the plan-mode tools, run the same phases as ordinary reasoning +\nsub-agent dispatches, treat an explicit user \"go\" as the approval gate, and\nkeep the plan (and its final \"what actually happened\" retro) inside the\nreport instead of the audit copy.", "## Runtime note\n\nAntigravity has no documented native plan-mode tools. Run the same phases as ordinary reasoning and subagent dispatches and write the hub audit copy. If `/goal` is set, its automatic plan approval is the gate; otherwise present the plan and treat an explicit user \"go\" as the approval gate. The report does not replace the persistent audit copy."),
    )
    for source, replacement in replacements:
        text = _replace_once(text, source, replacement, label)
    return text


def _rewrite_review_terms(text: str, label: str) -> str:
    replacements = (
        ("synthesis → advisor → execution → verification → out-of-scope tickets → edge-case sweep → advisor → git safety", "synthesis → independent review checkpoint → execution → verification → out-of-scope tickets → edge-case sweep → independent review checkpoint → git safety"),
        ("verification stays unconditional and advisor scales to stakes (advisor #1 skipped only on a recon-confirmed trivial low-blast-radius change; advisor #2 stays bar a guarded pure-mechanical edit)", "verification stays unconditional and independent review scales to stakes (checkpoint #1 is skipped only on a recon-confirmed trivial low-blast-radius change; checkpoint #2 stays bar a guarded pure-mechanical edit)"),
        ("Advisor scales to stakes with the same stakes-based scaling as `decision-review` (6a): advisor #1", "Independent review scales to stakes alongside `decision-review` (6a): checkpoint #1"),
        ("advisor #2 (before-done)", "checkpoint #2 (before-done)"),
        ("an advisor turn-back", "an independent-review turn-back"),
        ("recon, advisor #1, TDD, verify, edge-case sweep, advisor #2", "recon, independent review checkpoint #1, TDD, verify, edge-case sweep, independent review checkpoint #2"),
        ("### 6. Decision review → Advisor #1", "### 6. Decision review → Independent review checkpoint #1"),
        ("the deep review first, the advisor last", "the deep review first, the independent review checkpoint last"),
        ("### 12. Advisor #2", "### 12. Independent review checkpoint #2"),
        ("| \"It's a small change, advisor isn't needed\" | advisor #2 stays (bar a guarded pure-mechanical edit, Step 12); advisor #1", "| \"It's a small change, independent review isn't needed\" | checkpoint #2 stays (bar a guarded pure-mechanical edit, Step 12); checkpoint #1"),
        ("| Advisor #1 (on approach) |", "| Independent review checkpoint #1 (on approach) |"),
        ("| Advisor #2 (final) |", "| Independent review checkpoint #2 (final) |"),
        ("used in advisor responses and reports", "used in reviewer responses and reports"),
        ("before the advisor checkpoint", "before the independent review checkpoint"),
        ("**Boundary** = `/goal` set, plan presented and approved with an explicit go, or an explicit \"go / run it\"", "**Boundary** = `/goal` set, an approved plan, or an explicit \"go / run it\""),
    )
    for source, replacement in replacements:
        text = _replace_once(text, source, replacement, label)
    return text


_OVERLAYS: dict[tuple[str, str], Callable[[str, str], str]] = {
    ("curl-requests", "SKILL.md"): _rewrite_curl,
    ("secrets-handling", "SKILL.md"): _rewrite_secrets,
    ("task-workflow", "SKILL.md"): _rewrite_workflow_skill,
    ("task-workflow", "flow.md"): _rewrite_workflow_flow,
    ("task-workflow", "plan-file.md"): _rewrite_workflow_plan,
}

_FORBIDDEN_PROJECTED_MARKERS = (
    PLAN_ROOT_TOKEN,
    "allowedprompts",
    "advisor()",
    "enterplanmode",
    "exitplanmode",
    "settings.json",
    "permissions.deny",
    "~/.zshenv",
    "claude code's bash subprocess",
    "claude code tool",
    "verified against claude code plan mode",
    "built-in other",
    "denied by hook",
    "auto-mode classifier",
    "enforces denial of direct reads",
    "~/.claude/",
)


def adapt_runtime_markdown(text: str) -> str:
    text = re.sub(r"\bpreloaded into\b", "Available to", text, flags=re.IGNORECASE)
    for source, replacement in _RUNTIME_REWRITES:
        text = text.replace(source, replacement)
    text = text.replace(
        "uses `EnterPlanMode` / `ExitPlanMode` when present",
        "uses an explicit interactive planning and approval exchange",
    )
    text = text.replace("](../skills/", "](~/.gemini/config/plugins/mainframe/skills/")
    text = text.replace("preloaded skill", "referenced skill")
    text = text.replace("preloaded `", "referenced `")
    text = text.replace("is preloaded", "is available")
    text = re.sub(r"\bpreloaded\b", "available", text, flags=re.IGNORECASE)
    text = text.replace("`skills:` frontmatter", "delegation contract")
    text = re.sub(
        r"\[CLAUDE\.md\]\(\.\./\.\./dist/claude-code/CLAUDE\.md\)(?:\s+rules)?",
        "`MAINFRAME plugin rules`",
        text,
    )
    return text.replace("CLAUDE.md", "MAINFRAME plugin rules")


def adapt_skill_markdown(skill: str, relative: Path, text: str) -> str:
    label = f"core/skills/{skill}/{relative.as_posix()}"
    projector = _OVERLAYS.get((skill, relative.as_posix()))
    if projector is not None:
        text = projector(text, label)
    projected = adapt_runtime_markdown(text)
    validate_projected_skill_markdown(label, projected)
    return projected


def validate_projected_skill_markdown(label: str, text: str) -> None:
    folded = text.casefold()
    for marker in _FORBIDDEN_PROJECTED_MARKERS:
        if marker in folded:
            raise ValueError(f"forbidden Antigravity skill guarantee: {label}")
    if re.search(r"\badvisor\b", folded):
        raise ValueError(f"forbidden Antigravity skill guarantee: {label}")

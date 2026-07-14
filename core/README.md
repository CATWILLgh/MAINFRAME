# core/ — the tool-agnostic source of truth

Per ADR 0085: hub sources live here, neutral to any specific AI coding tool.
Per-tool refinements live in `adapters/<tool>/`, whose directory structure
MIRRORS this one. Delivered artifacts (`dist/claude-code/plugin/`, `dist/`) are committed
RENDER OUTPUTS — never edit them by hand.

## Editing rule

1. Edit files under `core/` (or the owning `adapters/<tool>/`).
2. Render: `python3 tools/render_core.py --write`.
3. Commit sources and render outputs together.

CI runs `python3 tools/render_core.py --check` on every push. That check is
the sole mechanical drift guard: the test suites exercise the rendered output
and stay green on an un-rendered core edit, so only `--check` catches a
source↔render divergence, orphan render files, and naked render-path
self-references in core sources.

## Sections

- `gates/` — gate detectors (Python) + their data; wire contract in
  [gates/CONTRACT.md](gates/CONTRACT.md). Landed (wave 1).
- `agents/` — neutral agent definitions: capability-contract frontmatter
  (`needs-repo-read` / `needs-write` / `needs-web` / `needs-docs-lookup`,
  `reasoning-tier` deep|standard|light, `turn-budget`, `background`,
  `method-skills`) + role prose passed through verbatim. The renderer derives
  the Claude Code frontmatter deterministically; `review-only` is folded into
  `!needs-write` (tracks `permissionMode: plan` on every current agent); rare
  divergence goes into a per-agent override
  `adapters/claude-code/agents/<name>.yml` (key-merge over derived values).
  Landed (wave 1).
- `skills/` — SKILL.md-standard skills; foreign parsers tolerate the hub's
  extra frontmatter keys (verified on OpenCode), so skills render as pure
  byte-copies — no frontmatter split, bodies verbatim. `validate-skill.py`
  treats this directory as the source of truth. Landed (wave 1).

- `instructions/` — the umbrella behavioral rules as ordered section
  fragments (numeric prefixes = the shared compose order). Rendered by
  concatenation: + `adapters/claude-code/instructions/` → `dist/claude-code/CLAUDE.md`
  (byte-identical to the pre-split file); + `adapters/opencode/instructions/`
  → `dist/opencode/AGENTS.md` (delivered to `~/.config/opencode/AGENTS.md` by
  `install.sh --opencode`, superseding OpenCode's CLAUDE.md fallback).
  Landed (wave 1).

- `permissions/rules.json` — the hub-owned allow/deny/ask rules. Rendered by
  KEY-MERGE, not byte-copy: `settings.json` is both hub policy and a live
  user-editable config surface (model, language, `permissions.defaultMode`),
  so the render splices ONLY the three rule lists into `dist/claude-code/settings.json`
  in place and `--check` compares only those lists — user keys are never
  touched or checked. The OpenCode generator reads this file directly.
  Landed.

- `adapters/claude-code/files/` — hand-authored Claude Code delivery files:
  `output-styles/`, `scripts/`, and `templates/`. `render_core.py` copies them
  into the corresponding `dist/claude-code/` paths.

Deferred: layer-6 (the non-permission `settings.json` keys — model, language,
etc.) stays user-owned in `dist/claude-code/settings.json`, by design.

## Assembly rules (mirror overlay)

An adapter overlay refines, never duplicates:

- **Prose** — whole-block append (core file + adapter module file); no
  conditional markup inside paragraphs.
- **Structures** (frontmatter, permission tables, configs) — key-merge; the
  adapter adds or overrides keys.
- **Code** — core detectors are untouchable; an adapter contributes wiring
  only (e.g. `adapters/claude-code/gates/run-hook.sh`, `hooks.json`).
- **Thin-layer discipline** — copied core content inside an overlay is a
  defect (it re-creates version drift); overlays carry only deltas.

## Language

Everything under `core/` and `adapters/` is English (hub principles §3):
these files are delivered to models, not to the user.

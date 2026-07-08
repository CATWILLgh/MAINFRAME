# core/ — the tool-agnostic source of truth

Per ADR 0085: hub sources live here, neutral to any specific AI coding tool.
Per-tool refinements live in `adapters/<tool>/`, whose directory structure
MIRRORS this one. Delivered artifacts (`plugin-dist/`, `export/`) are committed
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
- `agents/` — neutral agent definitions (role prose + capability contract).
  Pending (wave 1).
- `skills/` — SKILL.md-standard skills; probes confirmed foreign parsers
  tolerate the hub's extra frontmatter keys, so skills migrate as-is and the
  render only injects tool bindings. Pending (wave 1).

Deferred until needed: `instructions/`, `permissions/`.

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

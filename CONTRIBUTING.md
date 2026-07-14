# Contributing to MAINFRAME

This is primarily a personal hub. Forks under [MIT](LICENSE) are encouraged — adapt to your own workflow. PRs against the canonical repo are accepted but reviewed selectively: the hub is shaped to one engineer's preferences and existing principles.

---

## Forking (the easy path)

```bash
# 1. Fork on GitHub, then:
git clone https://github.com/<your-username>/MAINFRAME ~/Documents/projects/MAINFRAME-fork
cd ~/Documents/projects/MAINFRAME-fork
./install.sh
```

You now have an independent hub. Shape it freely. Pull from upstream selectively when you want specific changes.

The default command installs Claude Code. Add `--opencode` or `--codex` to install that projection alongside the Claude Code baseline.

---

## Principles

Every artifact the hub ships to Claude Code, OpenCode, or Codex must hold these:

### 1. Project-agnostic
No hardcoded project names, stacks, paths, or domains in any artifact. Stack-specific patterns live in stack-specific skills (e.g. `react-frontend-patterns`), NOT in the umbrella `CLAUDE.md`.

**Check before contributing**: would this be useful, neutral, or harmful in a random project that doesn't use the named stack? Useful or neutral — ship. Harmful or noise — cut, or move into a stack-specific skill.

### 2. Evidence-based
New rules need proof — real experience, authoritative source (Anthropic / project maintainer docs / RFCs / security references), or measured experiment. "Sounds reasonable" or "everyone does it" doesn't qualify.

Each rule costs tokens and adherence. The Anthropic spec explicitly warns: longer files reduce adherence to all rules.

### 3. English in artifacts
- Skills, agents, commands, hooks — **English**
- Comments in Python hooks — **English**
- Docs written for humans (this file, `docs/layers/*.md`) — any language

Reason: LLMs are tuned on English, follow English instructions more precisely, spend fewer tokens for the same content (~30-40% savings on typical instructions).

### 4. Single source of truth
Each artifact has one authored source. Generated runtime projections and committed golden fixtures are derived evidence, not competing sources.

### 5. Sub-agent economy
Pick the model per task:
- **Haiku** — trivial lookups, simple listings, basic extractions
- **Sonnet** — most research, multi-step analysis, code audit, source-check via Context7/WebFetch
- **Opus** — complex reasoning over incomplete data, creative synthesis, multi-step planning with open branching, design trade-offs without obvious right answer

For shared agents, set `reasoning-tier` and capability fields in `core/agents/<name>.md`; each adapter derives the runtime-specific model, effort, tools, and sandbox restrictions.

---

## Adding a new artifact

1. **Decide the layer** using [`docs/layers/decision-tree.md`](docs/layers/decision-tree.md). It walks 4 axes (activation, context isolation, kind, cross-layer triggering) plus the bloat-prevention toolkit (`when_to_use`, `disable-model-invocation`, `context: fork`, narrow `tools:`).
2. **Read the layer spec** at [`docs/layers/<layer>.md`](docs/layers/) — every layer has its own contract.
3. **Place the artifact** in the correct location:
   - Shared skills and agent contracts → `core/skills/` and `core/agents/`
   - Shared gate detectors and their data → `core/gates/`
   - Shared umbrella instructions → the appropriate numbered file in `core/instructions/`
   - Per-tool refinements → `adapters/<tool>/`
   - Hand-authored Claude Code files (output-styles, scripts, templates) → `adapters/claude-code/files/<layer>/`
   - Permission rules → `core/permissions/rules.json`
   - Path-scoped Claude Code rules are the direct-authored exception → `dist/claude-code/rules/<name>.md`; there is no `core/rules/`
   - The Commands layer is empty and has no source/render mapping yet; decide and add that mapping before adding its first artifact
   - Render owned outputs with `python3 tools/render_core.py --write`. Do not hand-edit generated files in `dist/`; non-permission fields in `dist/claude-code/settings.json` remain user-owned there
4. **Validate**:
   ```bash
   # CLAUDE.md changes
   python3 tools/validate-claude-md.py dist/claude-code/CLAUDE.md
   
   # New / changed skills
   .venv/bin/python3 tools/validate-skill.py core/skills/<your-skill>/

   # Source/render drift
   python3 tools/render_core.py --check
   ```
5. **Test in a fresh target session** — use `./install.sh` for Claude Code, add `--opencode` for OpenCode, or add `--codex` for Codex. Verify the artifact through that runtime's delivery path; only Claude Code plugin artifacts use the `mainframe:` namespace prefix.
6. **Commit** with conventional format (see below).

---

## Validators

Two Python validators ship with the repo. In this repository they are also wired into the project-local Claude Code hooks.

### `tools/validate-claude-md.py`
Anthropic `CLAUDE.md` spec + project-agnosticism check across the import graph. Targets `CLAUDE.md` (project) and `dist/claude-code/CLAUDE.md` (umbrella). Uses system `python3`, no dependencies.

```bash
python3 tools/validate-claude-md.py dist/claude-code/CLAUDE.md
python3 tools/validate-claude-md.py --session-start
```

### `tools/validate-skill.py`
Skill format rules:
- 5K tokens / 500 lines for `SKILL.md` body
- 5K tokens / 60 lines for supporting files
- Depth = 1 (no nested subdirectories under skill folder)
- `description` ≤ 1024 chars
- `description + when_to_use` ≤ 1536 chars
- Frontmatter completeness
- No dead supporting files

```bash
.venv/bin/python3 tools/validate-skill.py core/skills/<your-skill>/
.venv/bin/python3 tools/validate-skill.py --all
```

**Bootstrap the venv once**:
```bash
python3 -m venv .venv && .venv/bin/pip install tiktoken pyyaml
```

If a validator hook complains while working in this repository, the signal is "fix the file", not "disable the hook".

---

## Commit conventions

Conventional Commits v1.0.0.

```
<type>(<scope>)[!]: <description>

<body — why, what to verify, trade-offs>

<footer tokens — optional>
```

- `type` and `scope` — **English**, lowercase
- Breaking marker `!` — only when a downstream consumer must adapt
- Description and body — **English** (this repo is public, international audience reads the log)
- Body — bullet list focused on **why** (not what), what to verify, trade-offs accepted
- No `Co-Authored-By: Claude ...` or `Generated with Claude Code` trailers

**Types**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `build`, `style`, `ci`.

**Splitting**: mixed changes get split into atomic commits by type and independent scope. A `feat` change should not be bundled with a `refactor` change in unrelated code.

**Multi-line messages**: use `git commit -F /dev/stdin <<'EOF' ... EOF` (heredoc). The `-m "..."` form breaks on newlines and backticks (and on non-ASCII characters in shells with the wrong locale).

---

## Code style

- **Python hooks**: PEP-8 compliant, no comments unless the *why* is non-obvious
- **Markdown**: clean ATX headers, short sentences, tables for comparisons
- **Skill names**: `lowercase-kebab-case`
- **File limits**: 400 lines per file, 60 per function (per Clean Code)
- **No suppression markers** in committed artifacts: no `TODO`/`FIXME`/`HACK`/`XXX`, no `# noqa` / `# type: ignore` / `@ts-ignore` without explicit reasoning in the commit body
- **No debug residue**: no `print()` / `console.log` / `debugger` left over from diagnosis

---

## ADR for non-trivial decisions

Architecture-level decisions (new layer, principle change, install model change) go through an ADR (Architecture Decision Record) — short markdown documenting context, decision, alternatives considered, consequences.

ADRs in the canonical repo are private and gitignored under `docs/decisions/`. For fork contributions, feel free to maintain your own ADR set; if proposing a change to the canonical hub, include the reasoning inline in the PR body and the commit message.

---

## License of contributions

By submitting a PR, you agree your contribution is licensed under the same [MIT license](LICENSE).

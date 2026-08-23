---
name: project-instructions-init
description: Establish or repair a project's native Claude Code instruction hierarchy after the user explicitly asks to initialize project guidance.
argument-hint: "[optional scope]"
disable-model-invocation: true
---

# Initialize project instructions

Build a small, coherent Claude Code instruction system for the current
repository. Preserve established project knowledge and do not replace a working
structure merely to impose MAINFRAME filenames.

## Inspect before editing

1. Resolve the repository root and the directories in which Claude actually
   works.
2. Read inherited user instructions only to identify conflicts. Never modify
   global user configuration in this project run.
3. Inspect root and nested `CLAUDE.md`, `.claude/CLAUDE.md`,
   `CLAUDE.local.md`, `.claude/rules/`, project skills, project agents, and their
   direct instruction references.
4. Model Claude's native loading behavior: ancestor and root instructions load
   at session start, while nested instructions load when Claude works in those
   subtrees.
5. Measure every instruction file in lines and bytes. Treat documented product
   limits as ceilings, not content targets.

Distinguish verified behavior, project facts, proposed conventions, and unknowns.
When two instructions disagree in meaning, show the exact conflict and its
practical consequence to the user before editing either side. Do not infer a
product, business, infrastructure, authority, or ownership decision.

## Build the smallest useful hierarchy

Use these responsibilities unless the repository already has an equally clear
native structure:

- root `CLAUDE.md` or `.claude/CLAUDE.md`: short invariants for every task and
  an exact link to the project skill;
- `.claude/skills/<project-skill>/SKILL.md`: project architecture, durable
  workflows, navigation, and a compact list of only the MAINFRAME skills or
  agents relevant to this repository;
- nested `CLAUDE.md`: only rules that differ for that subtree;
- `.claude/rules/`: scoped rules only when path-based loading is clearer than a
  nested instruction file.

The project skill may route to discovered MAINFRAME skills and agents, but must
not copy their descriptions or methods. The plugin catalogue remains the full
capability inventory; the project skill is only the repository's curated map.
Do not create a second source of truth for the same rule.

Keep the skill progressively readable and move durable detail into linked
references only when that reduces the entrypoint without hiding required
behavior. Before writing, present the proposed owner of each file and every
unresolved semantic conflict. After the user resolves those choices, make the
smallest coherent edit and preserve unrelated content.

## Verify

Reconstruct startup and subtree instruction sets from the final files. Confirm
that each durable rule has one owner, nested files contain only local deltas,
all referenced paths exist, and no later-loaded rule silently reverses a broader
one. Report the measured footprint and every remaining uncertainty.

Static inspection does not prove model routing quality. Development telemetry
can prove that this explicit command ran and correlate later events in the same
session; actual behavior still needs runtime evidence.

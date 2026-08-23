---
name: mainframe-project-instructions-init
description: Establish or repair a project's native Codex instruction hierarchy after the user explicitly asks to initialize project guidance. Use only for the deliberate project setup run, not for ordinary implementation or incidental instruction edits.
---

# Initialize project instructions

Build a small, coherent Codex-native instruction system for the current
repository. Preserve existing project knowledge. Do not replace an established
system merely to impose MAINFRAME's preferred filenames.

## Inspect before editing

1. Resolve the repository root and the directories in which agents actually
   work.
2. Read the effective global instruction file only to identify inherited
   constraints. Never modify global user configuration in this project run.
3. Inspect every project `AGENTS.md`, `AGENTS.override.md`, configured fallback
   instruction file, project skill, custom agent, and directly referenced
   instruction document that can affect those working directories.
4. Build the effective Codex chain for each materially different working
   directory: one instruction file per directory from the repository root to
   that directory, with closer files taking precedence.
5. Measure every always-loaded file in lines and bytes and estimate the combined
   instruction footprint. Treat Codex's configured project-instruction limit as
   a ceiling, not a content target.

Distinguish verified behavior, project facts, proposed conventions, and unknowns.
When two instructions disagree in meaning, show the exact conflict and its
practical consequence to the user before editing either side. Do not choose a
product, business, infrastructure, authority, or ownership rule by inference.

## Build the smallest useful hierarchy

Use these responsibilities unless the repository already has an equally clear
native structure:

- root `AGENTS.md`: short invariants that apply to every task and an exact link
  to the project skill;
- `.agents/skills/<project-skill>/SKILL.md`: project architecture, durable
  workflows, navigation, and a compact list of only the MAINFRAME skills or
  agents relevant to this repository;
- nested `AGENTS.md`: only rules that differ for that subtree.

The project skill may route to discovered MAINFRAME skills and agents, but must
not copy their descriptions or methods. The harness catalogue remains the full
capability inventory; the project skill is only the repository's smaller,
curated map. Do not create a second source of truth for the same rule.

Keep the project skill progressively readable. Put durable detail in linked
references only when it would otherwise bloat the entrypoint. Use native paths
and names that another Codex installation in the repository can discover.

Before writing, present the proposed ownership of each file and every unresolved
semantic conflict. After the user resolves those choices, make the smallest
coherent edit. Preserve unrelated content and do not silently delete a rule
whose owner or purpose is unclear.

## Verify

Rebuild every affected effective chain from the final files. Confirm that:

- each durable rule has one owner;
- root guidance and the project skill complement rather than repeat each other;
- nested files contain only local deltas;
- all referenced files, skills, and agents exist at the recorded paths;
- no closer instruction silently reverses a broader rule;
- the measured footprint is reported, with any remaining risk or unresolved
  decision stated plainly.

Do not claim that model routing quality was proven by static inspection. The
development telemetry can prove that this explicit run occurred and correlate
later session events; actual long-session behavior remains runtime evidence.

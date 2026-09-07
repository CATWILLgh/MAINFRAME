# Initialize or evolve the current project's skill

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments and operates only on the current project.

Converge the project's evolving engineering skill to one useful current state. Initialize it when absent, update stale or incomplete content when present, and add supporting structure only when durable evidence requires it. Do not create a second baseline merely because an existing one uses a different name or structure.

## Resolve the project and native harness

Resolve the exact current project root from the active workspace and version-control boundary. Consult current official documentation for the installed agent product's project skill discovery, metadata, precedence, project instructions, reload, and validation behavior. Inspect only the global sources that actually affect this project and preserve them as a read-only baseline.

Within the current project, reconstruct the effective root and relevant nested instruction chain, native project skill roots, declared project skills, includes, and generated ownership. Do not scan the home directory, other repositories, archives, backups, caches, Trash, or another product's configuration.

Find an existing evolving baseline by responsibility rather than filename: it supplies the project's recurring engineering method and maintains verified project knowledge across substantive tasks. Distinguish it from focused skills that own one domain such as interface design, external evidence, infrastructure, or release operations.

## Preserve project ownership

Preserve the existing Git and harness ownership of every discovered skill:

- keep a tracked shared skill tracked;
- keep a locally ignored skill ignored;
- keep focused skills separate when their triggers and knowledge owners are distinct;
- update the canonical project source rather than a generated or installed copy.

When no evolving baseline exists, determine the policy for agent-owned project files from the current project's effective instructions, tracked files, ignore rules, and established native skill root. Follow a clear tracked or ignored policy. If the project has no policy and choosing would decide whether the skill is shared through Git or remains local to this checkout, stop on that one ownership decision instead of changing `.gitignore`, `.git/info/exclude`, project instructions, or global configuration by guesswork.

Use a stable native-compatible identifier derived from the project's established identity, normally `<project-id>-engineering`. Do not rename an existing compatible skill merely to match this default.

## Use the deterministic minimum

Every newly initialized baseline starts with exactly:

```text
<native-project-skill-root>/<project-skill-id>/
|-- SKILL.md
`-- references/
    `-- project-knowledge.md
```

Create no empty `scripts/`, `assets/`, component catalog, source map, examples, or UI metadata. Add native-required metadata only when the installed product requires it for project discovery.

Use this `SKILL.md` template and replace every angle-bracket token with verified project-specific content. Remove instructions that the project already owns elsewhere instead of duplicating them.

```markdown
---
name: <project-skill-id>
description: Apply and maintain verified <project-name> project knowledge during every substantive task whose target belongs to this repository. Use for planning, research, implementation, review, testing, cleanup, or maintenance so durable decisions, boundaries, workflows, and recurring traps are reused and corrected. Do not use outside <project-name>.
---

# Use and maintain <project-name> project knowledge

Before substantive work in this repository, read the effective project instructions and [references/project-knowledge.md](references/project-knowledge.md). Apply relevant durable knowledge without reciting unrelated entries or treating it as stronger authority than the current request and current evidence.

Work from the current project state. Separate user decisions, implemented behavior, verified runtime evidence, and unknowns. Preserve unrelated work and keep global configuration unchanged unless the current request separately authorizes a global change.

## Keep the knowledge useful

Proactively update this skill when the current work establishes knowledge that will materially improve a future task through an explicit durable user decision, direct inspection of the current project, current authoritative documentation, or a reproducible check. Update stale entries in place and merge duplicates.

Keep stable working procedure in this `SKILL.md` and decision-changing project facts, contracts, source routes, verification evidence, and recurring traps in `references/project-knowledge.md`. Add a focused reference or deterministic read-only script only when repeated use proves that it has a distinct owner and saves recurring investigation.

Do not record guesses, proposals awaiting approval, session chronology, temporary status, task notes, raw output, secrets, credentials, prompts, responses, telemetry, personal data, or copied project documentation. Link to an existing source of truth instead of duplicating it.

After changing the skill, validate its native structure, links, and any executable resources. Confirm that the project still discovers the same effective skill and that the edit did not change its tracked or ignored ownership.
```

Create `references/project-knowledge.md` with the title `# Verified <project-name> project knowledge` and only directly supported entries. Each entry states the durable fact or decision, the evidence or source needed to judge it, and its practical consequence. Use headings only for areas that already contain real knowledge; do not leave placeholders or empty taxonomy. If the bounded initialization finds no decision-changing project fact beyond identity and source ownership, say that no additional durable knowledge has yet been established rather than inventing content.

## Update and extend deliberately

Use the current invocation, effective project instructions, current canonical project files, and reproducible observations as evidence. Do not import another repository's skill, native memory, transcript, archive, or historical agent index as current project truth.

Keep these states distinct in maintained knowledge:

- a user decision defines accepted direction but does not prove implementation;
- implemented behavior requires current source inspection;
- verified behavior names the smallest observed check and its boundary;
- an unknown records a consequential gap without guessing.

Put shared project method in the baseline `SKILL.md`; stable cross-task knowledge in its project knowledge reference; genuinely domain-specific method and knowledge in an existing focused skill; and a repeated deterministic read-only orientation check in a script. Create `references/components/` or a source map only after multiple real entries make direct routing materially clearer. Do not grow structure to mirror a generic template.

When several project skills already evolve, update the narrowest existing owner. Do not merge focused skills into the baseline or copy the same rule into several descriptions. When a durable fact conflicts with the effective harness or another maintained entry, surface the exact conflict and correct only the established owner after any material user decision.

## Bind, validate, and report

Locate the current product's effective project-root instruction owner inside the resolved project. Add or reconcile one minimal reference from that owner to the evolving project skill so a new session can discover the durable project knowledge before substantive work. Reference the stable skill identity and native project path; do not paste the skill body into the root instruction.

Reuse an existing shared cross-agent root instruction when it is natively effective. Add a thin product-specific bridge only when the installed product cannot consume that owner directly. Do not create every product's conventional root file, add a global binding, or duplicate the reference across several instruction layers.

If no effective root instruction exists, create the current product's smallest native project instruction only after resolving whether that project-owned file is tracked, ignored, or split. If the project's evidence does not decide that ownership and the choice would determine whether the instruction is shared through Git, stop on that one decision instead of guessing. Repeated invocation must update the same managed reference without adding duplicate lines or generated sections.

Validate frontmatter or native metadata, every relative link, executable resource, project confinement, and Git ownership. Reload or start a fresh project session through the documented native mechanism and verify discovery; file presence or a syntax check alone is insufficient. If the product cannot expose a project skill reliably, return the exact limitation instead of installing a global copy as a substitute.

Repeated invocation against unchanged project evidence must produce no semantic or structural churn. Return the project root, skill identity and path, tracked or ignored ownership, whether it was initialized or reconciled, durable knowledge added or corrected, discovery evidence, and any exact unresolved ownership or capability decision.

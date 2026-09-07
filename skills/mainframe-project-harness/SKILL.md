---
name: mainframe-project-harness
description: Detect and surface conflicts in a project's effective agent harness, including conflicts between applicable global and project instructions, and establish or repair project-owned configuration when authorized. Use proactively whenever instructions, skills, agents, hooks, commands, permissions, or MCP configuration appear contradictory, duplicated, shadowed, stale, misplaced, unsupported by available capabilities, or inconsistent with observed behavior; also use when inspection, initialization, cleanup, or repair of them is requested. Do not use for ordinary application defects or unrequested global configuration changes.
---

# Maintain the project harness

Use this skill as soon as you notice credible evidence that the harness affecting your project work may be inconsistent. Do not wait for the skill to be named or for a full audit to be requested.

Work from the project root. Consult the current official documentation for your installed product version and interface before relying on paths, discovery, precedence, nesting, imports, permissions, or reload behavior. Do not apply another product's filenames or mechanics to your environment.

## Establish the effective harness

Read only the global configuration that can affect the project. Treat it as a preserved baseline and record its exact source and effect without changing it.

Inspect every project-owned component your product can discover from the repository root and relevant working directories, including applicable:

- root and nested instructions, overrides, and imports;
- project settings and permissions;
- skills and agent definitions;
- hooks, commands, and workflows;
- MCP declarations and tool policies, without reading secret values;
- references, includes, symlinks, generated copies, and their canonical sources.

Reconstruct the actual chain from the global baseline through the project root to relevant subtrees. Distinguish always-loaded instructions from components loaded only when selected or invoked. Identify which source wins, where each rule applies, and which material is not discoverable.

Treat archives, backups, Trash, fixtures, caches, dependencies, and vendor trees as inactive unless documented discovery rules actually include them.

## Surface conflicts proactively

Verify a suspected conflict against actual scope and precedence before reporting it. Do not manufacture a problem from harmless inheritance, intentional specialization, or wording that has the same effect.

When a real conflict or harness defect is found, report it proactively to the current recipient or your immediate caller. State:

- the exact sources involved;
- the effective behavior and why it wins;
- the practical consequence for the current task or project;
- the owner and correct edit location;
- whether work can safely continue.

Continue the assigned task when the issue does not invalidate or endanger the result. Stop only when proceeding would produce a materially wrong, unsafe, or unauthorized outcome that requires a decision from the current recipient or your immediate caller.

Keep investigation proportional to the signal. Do not turn one local inconsistency into an unrestricted audit of global files, other products, histories, authentication data, secret values, telemetry, or unrelated projects.

## Maintain project-owned configuration

Respect the authority in the assigned request. A request to inspect or explain does not authorize edits. A request to initialize, clean up, or repair the project harness authorizes only the corresponding project-owned changes.

Give every durable rule or component one owner:

- global configuration for behavior intended everywhere;
- root project configuration for shared project invariants;
- nested configuration for subtree-specific exceptions;
- skills for reusable methods;
- agents for bounded roles and task responsibility;
- hooks for automatic event reactions;
- canonical sources for generated adapter or runtime copies.

Place a correction at its owner. Do not edit generated material directly when a canonical source or documented rebuild route exists. Keep global configuration unchanged unless a global change is separately and explicitly included in your authority.

Resolve clear mechanical defects within the authorized project work. Discuss changes that alter the meaning of a unique rule, remove user-owned knowledge, change ownership, or require choosing between valid behaviors. Preserve unrelated and pre-existing work.

## Verify and report

After a change, reconstruct every affected instruction chain and validate references, symlinks, discovery paths, metadata, and native parsing. Use the product's native reload, new-session, discovery, or safe representative invocation when available and authorized.

Do not treat file presence or structural validation as proof that the product loaded or followed the harness.

Tell the current recipient or your immediate caller exactly where future changes belong:

- “To change behavior everywhere, edit `<global path>`.”
- “To change only this project, edit `<project path>`.”
- “To change only this subtree, edit `<nested path>`.”
- “Do not edit this generated file; edit `<canonical path>` and rebuild it through `<route>`.”

Separate the preserved global baseline, project-owned configuration, effective combined behavior, generated material, completed repairs, and unresolved decisions. Claim only the verification level you actually observed.

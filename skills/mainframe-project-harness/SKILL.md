---
name: mainframe-project-harness
description: Audit or repair project agent configuration when instructions conflict, skills are missing, or hooks, permissions, and tool policies misbehave. Not a routine setup check.
---

# Maintain the project harness

Start with the configuration implicated by the request or observed fault. Use
current native tool contracts and established project evidence; consult official
documentation when discovery, precedence, permissions, or reload behavior is
uncertain or version-sensitive. Reuse current evidence already available.

## Establish the effective harness

Read only the global configuration that can affect the project. Treat it as a preserved baseline and record its exact source and effect without changing it.

For a local repair, trace only the affected instruction chain and its owners.
For an explicit project-wide harness audit, inventory discoverable components
and inspect the relevant bodies, including:

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

For a shell-command policy, classify execution from parsed shell boundaries
rather than matching dangerous words in the raw command string. A remote-command
exception applies only after identifying the actual launcher, its exact allowed
destination, and the quoted remote payload. Local commands composed before or
after it, local command or process substitutions, executable launcher options,
shell wrappers, and other destinations retain their own policy. Cover the exact
reported compound command plus genuine local, mixed local/remote, and local
expansion controls; the mere presence of `ssh` or an allowed host name is never
an exception.

Complete authorized repairs, including semantic corrections supported by the
request and evidence. Ask only when a material ownership, policy, or behavior
choice remains unresolved; several valid implementations alone are not a reason
to stop. Preserve unrelated rules, user-owned knowledge, and pre-existing work.

## Verify and report

Validate the changed contract: wording needs an instruction-chain review and
link checks; changed packaging or registration also needs native parsing and
discovery evidence. Use a new-session or behavioral probe only when changed
behavior or unresolved risk requires it and the assignment permits it. Do not
repeat unchanged discovery or launch another product surface for a text edit.

Do not treat file presence or structural validation as proof that the product loaded or followed the harness.

Report the corrected behavior, canonical edit location, verification, and any
remaining decision or activation step. Identify a generated copy's rebuild route
when relevant. Claim only the verification level actually observed.

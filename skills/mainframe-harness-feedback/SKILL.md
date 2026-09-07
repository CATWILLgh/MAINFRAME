---
name: mainframe-harness-feedback
description: Preserve an observed fault in MAINFRAME or its effective agent harness in MAINFRAME's central feedback queue. Use proactively for instruction conflicts, faulty or noisy hooks, lost context, incorrect adaptation, duplicate registration, unsupported claimed behavior, or inconsistent agent, subagent, Desktop, and CLI behavior; do not use for application defects or routine successful checks.
---

# Report a MAINFRAME harness fault

Use this skill when available evidence indicates that MAINFRAME, an adapted MAINFRAME component, or the effective agent harness behaved incorrectly. Keep this feedback separate from the receiving project's issue queue.

First distinguish the owner of the problem:

- Use the receiving project's issue route for an application, data, infrastructure, or project-documentation defect.
- Repair a local project-harness configuration defect when that repair belongs to the assigned work and is authorized.
- Use this route when the evidence concerns MAINFRAME semantics, adaptation, discovery, precedence, registration, hooks, skills, agents, commands, permissions, or behavior across supported invocation trajectories.

Do not require a proven root cause before preserving a useful observation. State separately what was observed, what was reproduced, and what remains an inference.

## Use the resolved MAINFRAME destination

The installed copy of this skill must contain the normalized absolute MAINFRAME source root supplied during adaptation in place of `{{MAINFRAME_ROOT}}`. Its only feedback destination is:

`{{MAINFRAME_ROOT}}/docs/tickets/open/observations/`

Treat an unresolved placeholder as an installation defect. Do not scan the home directory, other repositories, mounted volumes, application data, archives, backups, recovery directories, or Trash to guess the root. If the resolved root or the narrow feedback permission is unavailable, return feedback-ready content and the exact missing path, capability, or authorization to your immediate caller; do not write the report into the receiving project's queue or claim it was filed.

Use only the access needed to list open observations and create or update a matching record. Do not use the feedback permission to inspect or modify unrelated MAINFRAME content.

The destination may be absent before the first report. Create only the exact destination directory when writing the first real observation and the configured authority permits it; do not initialize empty ticket states during installation.

## Preserve useful evidence

Record:

- a concise factual title;
- the affected canonical or adapted component;
- the receiving agent product, version, and interface when known;
- the execution trajectory relevant to the fault, such as primary agent, subagent, reviewer, direct request, delegated task, Desktop, or CLI;
- the triggering action or condition;
- observed behavior and expected behavior when a source defines it;
- the practical consequence for the active work;
- minimal redacted evidence and reproduction status;
- remaining uncertainty.

Keep evidence collection proportional to the observed fault. Do not include secrets, protected stores, telemetry payloads, full transcripts, unrelated project data, or speculative severity and cause. A hook message is evidence, not proof that a ticket was written.

## Reconcile repeated reports

Search only MAINFRAME's open feedback observations for the same component, trigger, behavior, and evidence. Do not search archives by default.

- Update a clear open match only with material evidence not already present.
- Create one new observation when no clear open match exists.
- Keep uncertain matches separate and record only the possible relationship.

Preserve the existing record identity and history. Repeating the same report with the same evidence must converge on one effective open observation without duplicate text. Do not reopen or mutate archived records.

After a successful write, return the record path or identity and whether it was created or reconciled. If you cannot write, return the complete feedback-ready record and the exact handoff required. Continue the assigned task when the fault does not make its result invalid or unsafe. Fix MAINFRAME only when that work is separately assigned and authorized; never disable a safety guard merely to avoid its refusal.

Test this reporting route only with a clearly synthetic observation in an isolated temporary destination. Do not create a real MAINFRAME defect ticket merely to prove that the skill can write one.

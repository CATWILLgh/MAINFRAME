# Audit old MAINFRAME traces in this agent environment

Execute this file as a standalone read-only audit, including when invoked as a
native goal. Identify the current hosting product, surface, and version from
native evidence. That is the target; adjacent CLIs and archive directories do
not expand it. Use only this surface's own current official loading contract.

The result is an evidence-backed inspection of installed MAINFRAME traces,
not a repository health check or a search for old project names. Nothing may
be installed, removed, disabled, or stopped. Do not run discovery or cleanup
scripts. Read [the procedure](support/legacy-audit.md), then follow these steps:

1. Set up one coverage table with the layers listed below. Establish documented
   package/plugin discovery first, since packages can supply other layers.
2. Work through one layer at a time: retrieve its current official contract,
   derive exact loading locations, inspect them, and write that row's bounded
   conclusion or gap before starting the next layer. Follow the detailed loop
   in the procedure. Do not collect a broad inventory first and reconstruct
   evidence for the table at the end. Reuse already retrieved sources and
   observations when they directly cover another layer; do not repeat reads.
3. For each candidate, establish ownership, referenced target, and consumers
   separately. An inaccessible target is unknown, not absent. Unproven objects
   are not cleanup candidates.
4. Reconcile the existing rows and findings. The final summary must not expand
   their coverage or replace an unresolved gap with a claim of cleanliness.

The final report must account for instructions/rules, skills, commands,
hooks, profiles/subagents, packages/plugins, MCP integrations, and background
services/shared helpers. Keep a row even when its contract is unknown. For each,
state its documented location, what was inspected, and what remains unknown.
Where a layer is unsupported, cite the source; where support is unknown, say so.
A list of MCP servers does not replace a check of hook registrations.

Use these completion boundaries:

- Every layer has a retrieved official contract and all its applicable loading
  locations were inspected, or documented non-support: report findings for that
  scope. Reconcile this against the table, not against the number of findings.
- A needed source or location is unavailable: finish independent inspection and
  return a partial audit with the exact gap. Do not call the environment clean
  or the audit fully verified. Do not loop on the unchanged access blocker.
- No removable object proven: report that result; do not manufacture candidates.

Conclude with confirmed findings, retained uncertain objects, and limitations.
Every claim of absence, broken linkage, inactivity, or MAINFRAME ownership must
have a matching observation. A native report artifact may hold the result;
leave repository files, user settings, and runtime state unchanged. Do not
start cleanup, a briefing, or another goal unless separately requested.

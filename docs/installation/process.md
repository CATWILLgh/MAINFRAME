# Installation process

Use this process from the MAINFRAME repository root. It is target-neutral; pair
it with the page for the installed product and the guide for the active
component type.

## 1. Resolve the only source root

Use the active workspace or Git boundary. The resolved root must contain the
bootstrap, state example, this guide, and every canonical category named there.
Do not search outside that root for a preferred checkout.

Normalize the absolute root once. Use that value for installed placeholders,
permissions, and local state. A symlinked launch path is not enough: record the
resolved source and the path the native product will actually use.

## 2. Validate the inventory

Treat [ADAPTATION.example.json](../../ADAPTATION.example.json) as exhaustive.
Before global writes:

1. parse the JSON;
2. verify every listed source exists inside the resolved root;
3. verify every direct canonical instruction, skill directory, agent file,
   command file, and hook source is represented exactly once;
4. verify no state, test, documentation, installer, template, archive, cache, or
   local development file is listed;
5. stop on mismatch instead of discovering extra payload from directories.

A listed skill owns its complete relative resource tree. Those nested files are
not separate inventory entries. Shared credentials are narrower: only the exact
listed helper file is payload.

## 3. Create or reconcile local state

Choose one stable product ID. Verify `ADAPTATION.<product-id>.json` is ignored,
then copy the example only when the file is absent.

On resume, compare schema, identities, and sources to the current example. Add,
reset, retain, and remove entries exactly as the bootstrap specifies. Do not
preserve `installed` after the canonical source or target mechanism changed
without re-verification.

The state file answers only:

- what target and native destinations were resolved;
- whether each exact component is `pending`, `installed`, or `unsupported`;
- the short blocker or limitation when needed.

It is not a journal. Do not accumulate attempts, timestamps, raw diagnostics,
transcripts, telemetry, secrets, or backup locations.

## 4. Reconstruct the effective target

Use three evidence sources together:

1. current official documentation;
2. installed version and command help or application information;
3. harmless runtime observation.

Determine the effective owners and precedence for global instructions, skills,
agents, commands, hooks, integrations, permissions, and settings. Include
environment overrides, managed layers, wrappers, symlinks, and Desktop-versus-
CLI boundaries only when they actually affect this target.

Do not inspect another product's configuration or treat an old MAINFRAME
adapter as evidence of current behavior. Historical material can explain an
intentional behavior only after the current canonical source confirms it.

## 5. Preserve the baseline

Inventory only the target's known relevant global roots. Classify existing
material as:

- native or application-generated;
- user-owned and unrelated;
- current MAINFRAME-owned;
- positively identified obsolete MAINFRAME-owned;
- unknown ownership.

Only current and obsolete MAINFRAME-owned identities are adaptation targets.
Unknown ownership is preserved until resolved. Take a narrow rollback copy just
before changing a concrete file or registration, not a profile-wide archive.

Never read protected credential values. Preserve authentication, session and
history stores, memories, projects, caches, and built-in data even when they are
near a configuration file being changed.

## 6. Adapt one component

For the next `pending` entry:

1. read the component guide and native page;
2. inspect the canonical source and directly required resources;
3. resolve the exact native stable identity, destination, metadata, and reload;
4. inspect an existing identity before writing;
5. create an installed copy in temporary staging when transformation is needed;
6. add only target-required metadata, paths, wrappers, and registrations;
7. validate the staged result;
8. replace or merge only the owned target atomically where practical;
9. reload and run the smallest native probe;
10. update the state before opening the next entry.

Prefer pure canonical sources behind thin native wrappers. Never edit canonical
sources to add target frontmatter, event names, permissions, absolute paths, or
configuration syntax.

Repeated installation must converge to one equivalent effective component.
Use stable identities and semantic merge rules. Do not create aliases,
compatibility duplicates, repeated permission rows, or parallel registrations
as a substitute for understanding precedence.

## 7. Stop or continue correctly

Continue past one `unsupported` entry when remaining components are independent.
Leave an entry `pending` when the capability could still be completed but a
specific dependency, authority, or decision is missing.

Stop before the affected action when:

- a user-owned semantic conflict requires choosing which behavior wins;
- ownership is ambiguous and replacement could destroy unrelated state;
- secret storage or protected access needs a user decision;
- a destructive or externally mutating step lacks authority;
- canonical source or required evidence is unavailable.

Do not stop for routine successful components or ask the user to approve the
documented sequence again.

## 8. Finish and clean up

Run the final evidence matrix. Only after a replacement is verified, remove its
positively identified obsolete MAINFRAME-owned predecessor and stale
registration. Remove temporary staging and targeted rollback copies. Preserve
the state file and native caches.

Final success requires no `pending` inventory rows. Report installed proof,
unsupported limitations, preserved data, cleanup, and exact remaining blockers
without secret values or verbose command logs.

# Verification

Verification is layered. A lower layer never proves a higher one.

| Layer | Proves | Does not prove |
| --- | --- | --- |
| Inventory | The expected canonical sources are listed exactly once | Any target installation |
| Source | Canonical syntax, links, tests, and deterministic behavior covered by tests | Native discovery or events |
| Installed structure | The target copy parses and references valid paths | That the product loaded it |
| Native discovery | The current product exposes the installed identity | Correct behavior or enforcement |
| Representative behavior | One safe trigger produced the required effect | Unprobed products or interfaces |
| Preservation | Owned changes avoided unrelated state and secrets | Future product upgrades |

## Per-component evidence

Before setting `installed`, record a concise evidence pointer in working notes or
the final report; keep the state JSON itself small.

- **Credentials:** command identity resolves to the intended executable;
  clipboard or protected prompt registration and protected retrieval work
  without printing a value; the centralized non-secret index remains ignored.
- **Instruction:** a fresh native session demonstrates that the effective global
  layer contains the MAINFRAME semantics alongside preserved user content.
- **Skill:** native listing or routing exposes the stable name, and a harmless
  invocation loads its body and relative resources.
- **Agent:** native discovery exposes the role; a harmless allowed action works;
  a harmless prohibited action is denied when enforcement is part of the role.
- **Command:** the user-visible command identity exists, loads only on explicit
  invocation when supported, preserves the no-argument contract, and does not
  silently invoke a different agent or mode.
- **Hook:** the native event reaches the wrapper; the detector is silent on a
  clean payload; a safe synthetic finding has the required advisory or blocking
  effect; operational failure follows the canonical fail behavior.
- **Integration or permission:** native effective configuration exposes the
  stable registration; a harmless capability probe works; unrelated entries and
  secret boundaries remain unchanged.

## Desktop and CLI

Do not infer one surface from another. Prove them separately when they have
different processes, configuration roots, reload behavior, sandboxes, event
dispatch, or bundled versions. When they are proven to share one effective
configuration, record that evidence once and still test any distinct runtime
behavior.

For a UI-only surface, use visible native discovery and one harmless user-like
interaction. For a CLI surface, use its listing, diagnostic, or execution path.
A successful CLI parse does not prove Desktop reloaded a hook.

## Negative checks

Final verification also confirms:

- every state entry is `installed` or precisely `unsupported`;
- all target placeholders are resolved only in installed copies;
- no broken MAINFRAME-owned symlink or duplicate registration remains;
- no repository documentation, tests, local state, archive, or development
  configuration was installed globally;
- no secret value appears in ordinary configuration, state, diagnostics, logs,
  patches, or the final report;
- authentication, histories, sessions, memories, projects, user instructions,
  unrelated components, and native caches remain present;
- no MAINFRAME telemetry collector or permanent activity log was added;
- the repository's tracked content was not modified by the installation run.

## Safe hook probes

Never test a destructive guard against a real protected path or repository.
Call canonical detectors directly with synthetic payloads, then exercise the
native bridge with an isolated harmless fake action whose expected block cannot
damage state. Use temporary repositories and files for Git and edit-event
checks. Ensure all temporary processes and files are removed afterward.

## Unsupported is evidence, not failure concealment

Use `unsupported` only when the installed product cannot represent a required
semantic after documentation and a harmless probe. Name the missing event,
enforcement, visibility, attribution, or continuation capability. A partial
advisory does not prove a guard, and a prompt does not prove a native permission.

Use `pending` when installation is still possible but unfinished.

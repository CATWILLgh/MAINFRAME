# Adapt commands

Use this guide for every entry under `components.commands`.

## Preserve explicit user invocation

Every MAINFRAME command is a user-facing explicit operation. Prefer the native
global slash command or prompt-template mechanism that:

- exposes the stable command name to the user;
- keeps the full body out of routine context until invocation;
- prevents autonomous model invocation when supported;
- preserves the source's no-argument contract;
- runs in the user's current project rather than the MAINFRAME source project
  unless the command itself says otherwise.

Reinstall by stable identity. Do not create aliases or turn a command into an
always-on instruction. If slash syntax, delayed loading, user-only invocation,
or command identity cannot be represented, record that exact degradation.

## `mainframe-init`

Preserve the primary-session boundary. The command applies outcome ownership to
the user-facing coordinating session that was explicitly invoked. A bounded
subagent does not become the primary owner merely because it can see inherited
text.

Background delegation is an optional working agreement, not a default duty.
Keep or prefer it only when the user or receiving project has established that
agreement and the product can preserve ownership and handoff.

The source contains a block delimited by `MAINFRAME OPTIONAL BLOCK:
native-primary-memory`. These comments are adaptation metadata. Keep and
natively adapt the block only when current documentation and a harmless probe
prove persistent memory for the user-facing primary session. Otherwise remove
the whole block from the installed copy. Remove delimiter comments either way.
Do not simulate missing memory with a global file or transcript scan.

## `project-skill`

Install this command globally but do not execute it during MAINFRAME
installation. Later, when the user invokes it from a receiving project, it must
stay inside that project, preserve tracked/ignored/split ownership, reconcile
one deterministic evolving skill, and bind it through one minimal effective
root-instruction reference. It must not create every product's root file or scan
other projects.

## Ticket commands

Keep the no-argument, one-item-at-a-time, repeat-until-exhausted behavior. Do not
replace project queue discovery with a global path or turn project tickets into
MAINFRAME harness feedback.

## Verify

Use native command listing or UI discovery. Invoke each command harmlessly in a
disposable or read-only project context and prove the correct full body loads at
that moment. Verify that a repeated install updates one identity and that no
default agent, model, subtask mode, or arguments were introduced accidentally.

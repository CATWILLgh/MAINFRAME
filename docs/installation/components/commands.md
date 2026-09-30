# Adapt commands

Use this guide for every entry under `components.commands`.

## Preserve explicit user invocation

Every MAINFRAME command is a user-facing explicit operation. Require a native
global representation that:

- exposes the stable command name to the user;
- keeps the full body out of routine context until invocation;
- preserves explicit user activation rather than autonomous execution;
- preserves the source's no-argument contract;
- runs in the user's current project rather than the MAINFRAME source project
  unless the command itself says otherwise.

Prefer native slash syntax and suppress model invocation through native controls
where available. Alternate invocation syntax and unavoidable catalog metadata
are packaging degradations: report them, but they do not make a representation
unsupported when the required behavior above is preserved and proven. An
established missing required behavior makes delivery `unsupported` with its
limitation in `reason`; missing proof leaves verification `pending`.

Reinstall by stable identity. Do not create aliases or turn a command into an
always-on instruction.

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

## `mainframe-project-skill`

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

Run these native checks during adapter development or explicitly requested
acceptance, not as an ordinary maintained-installation tail.

Use native command listing or UI discovery for every exact identity. Prefer a
native template preview or request inspection that shows its full body loads
only on explicit invocation. If execution is the only available loading path,
use a disposable context and an explicit probe boundary that prevents the
workflow from performing project or external mutations. Keep that probe
boundary in the test task; do not add arguments to a no-argument command. Do not
execute `mainframe-project-skill`, ticket campaigns, or actual initialization as an installation
side effect. If the target cannot expose loading safely, keep that proof at
`verification: pending`; file contents alone do not prove invocation.

For optional native-memory adaptation, check actual persistent primary-session
recall through the documented mechanism without real user content. Lack of a
probe leaves memory unverified, so omit the optional block as its source directs.

Verify that a repeated reconciliation updates one identity and that no default
agent, model, subtask mode, or arguments were introduced accidentally.

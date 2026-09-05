# Workflow entry points

Purpose: provide convenient native invocations for existing methods without
duplicating their implementation or assigning the invoker a new role.

`{{COMMAND_BINDING}}`: bind the work method (`mainframe-init`), project
instruction initialization and audit, and the four ticket methods (find,
refine, implement, verify) to the product's documented command or skill
invocation mechanism. Pass the operator's exact task or scope to the owning
skill. Do not start a queue-wide action from an incidental mention of a ticket.

The installation and update entry points load the corresponding prompt from
`goals/` in this source checkout using a resolved absolute path. They start a
native goal only when the operator requested that run and the native surface
permits it. A preparation-only request returns the ready-to-use objective and
stops before execution.

If there is no native command surface, expose copyable prompts referring to
the installed workflows. Do not create a shell dispatcher or custom lifecycle.

Verification: invoke one entry with a bounded harmless scope and check that it
reaches the intended method without duplicate instructions, role reassignment,
scope expansion, or an extra goal. Check that a preparation-only invocation
does not execute the prepared work.

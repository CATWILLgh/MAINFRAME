# Workflow entry points

Purpose: provide convenient native invocations for existing methods without
duplicating their implementation or assigning the invoker a new role.

`{{COMMAND_BINDING}}`: bind one-ticket decision preparation (`mainframe-ticket-decision`), project
instruction initialization and audit, and the four ticket methods (find,
refine, implement, verify) to the product's documented command or skill
invocation mechanism. Pass the operator's exact task or scope to the owning
skill. Do not start a queue-wide action from an incidental mention of a ticket.

The one-ticket decision command takes an exact ticket id and runs preparation
as a conversation. It records the decision and returns the appropriate
implementation or resumed-verification objective for separate operator
submission; it does not execute that next stage.
If there is no native command surface, expose copyable prompts referring to
the installed workflows.

## Goal plus ticket skill

Find, refine, implement, and verify are separate operator-started goals, not
an automatically chained pipeline. Complete only the explicitly selected
workflow. Moving a ticket into the next queue does not authorize starting its
next stage, creating another goal, or delegating that stage to a subagent.
Verify runs later in its own fresh task against implemented tickets awaiting
verification; implementation's own checks do not replace it. Subagents may
assist within the currently selected workflow and its authority.

No fixed age, priority, or easiest-first ordering is required. Before acting on
each ticket, recheck its current queue eligibility, relevance, evidence, and
authority against the present tree, including any freshness observations from
find. An earlier find/refine pass does not authorize acting on stale premises.
Choose a workable order while respecting actual dependencies and process the
selected scope; do not leave a ticket unexamined merely because it is difficult.

Support an operator starting a native goal whose objective invokes a ticket
skill, or invoking that skill after starting the goal. Load the actual installed
skill and its references before execution; its name alone is not its content.
Use the existing goal, preserve the supplied scope, and follow that method's
completion rule. No preliminary decision briefing for an autonomous ticket, second goal, or remembered
generic ticket workflow is required. An empty native `/goal` may show status
rather than start work: verify the actual product syntax.

Use only documented native invocation. If nested skill mentions do not expand
inside a goal, explicitly load the installed method by path. These ticket
methods require native Goal support; do not invent a replacement lifecycle.

# A bounded role for this task

Purpose: let an agent assign useful temporary roles without maintaining a
catalog of mandatory specialist profiles.

Adapt `{{SUBAGENT_ROLE}}` to include the concrete result, relevant evidence,
owned files or read-only scope, permitted side effects, verification required,
and the recipient of the result. Link only skills relevant to the assignment;
all installed skills remain available when the task needs them.

Use `{{TOOL_SCOPE}}` and `{{MODEL_CHOICE}}` only through documented native
capabilities and within the operator's preferences. Do not require every role
to have its own configuration file or model.

Useful assignments include a bounded implementation, current-source research,
a test-suite audit, a decision challenge, and a final readiness check. These are
examples, not a mandatory pipeline. Separate review from mutation when the
assignment is review-only. A direct executor can use the same method without
spawning a subagent or pretending that self-review is independent.

Check that the recipient understands its output and authority, can access the
relevant skills, and returns evidence rather than taking over unrelated work.
If a native permission restriction is claimed, verify it actually holds.

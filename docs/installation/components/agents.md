# Adapt agents and subagents

Use this guide for every entry under `components.agents`.

## Translate the role, not only its prose

Preserve the canonical role body and stable identity. Add target metadata only
to the installed copy. Attach required skills through native skill references;
do not paste their bodies into the role.

For each role, derive a small capability matrix before writing:

| Concern | Resolve from canonical role |
| --- | --- |
| Recipient | Who receives the result or handoff |
| Boundary | Exact task type and exclusions |
| Method | Required MAINFRAME skill |
| Read/write | Allowed path and mutation scope |
| Tools | Required and prohibited action classes |
| External effects | Network and externally mutating boundary |
| Delegation | Whether this role may create or direct another worker |

Map each enforceable row to the narrowest documented native control: role mode,
tool or permission rules, sandbox, path scope, or per-role setting. Prompt text
is guidance, not enforcement. Never broaden a role because the product cannot
express a narrow rule.

Preserve the user's model default unless a demonstrated capability requirement
cannot be met. Do not bake a preferred model, reasoning level, background mode,
memory, or tool name into the canonical role.

All messages between a primary agent and subagents, between subagents, and back
to their coordinating recipient are in English. User-facing communication
follows the user's applicable language.

## Unsupported roles

If the target has no native custom-agent or subagent mechanism, mark the role
`unsupported`; an ordinary prompt file is not equivalent. If a defining safety
boundary cannot be enforced, record whether the role is wholly unsupported or
whether a narrower read-only representation still preserves its canonical
result. Do not claim enforcement from wording alone.

## Verify

Prove native discovery and explicit or automatic routing as defined by the
product. In an isolated harmless scope, test one permitted action and one
prohibited action whenever the role relies on native enforcement. Record what
the product enforced, what remains instruction-only, and what cannot be
represented.

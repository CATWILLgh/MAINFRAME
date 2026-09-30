# Adapt agents and subagents

Use this guide for every entry under `components.agents`.

## Translate the role, not only its prose

Preserve the canonical role body and stable identity. Add target metadata only
to the installed copy. Attach required skills through native skill references;
do not paste their bodies into the role. If native attachment is unavailable,
use an equivalent reference only after a role invocation proves it can load the
method under its actual permissions, and report the native limitation. Loading
assigned instructions or method resources does not authorize broad repository
inspection. Strip installer directions and adaptation metadata from the runtime
role body; keep the role's duties addressed to the agent that executes it.

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

Preserve the delegation and task-specific model selection policy in the
[global instruction](../../../instructions/global.md#agents). A role's routing
description identifies when it is useful; its availability does not require a
spawn. Do not bake a preferred model, reasoning level, background mode, memory,
or tool name into the canonical role.

In the adapted copy, honor explicit user or project selections and keep native
per-task selection available. Do not pin every role to the installing agent's
model or reasoning effort. Resolve supported values and precedence from the
current native interface; use the configured default when selection is
unavailable. Record that limitation without inventing a substitute mechanism.

All messages between a primary agent and subagents, between subagents, and back
to their coordinating recipient are in English. User-facing communication
follows the user's applicable language.

## Unsupported roles

If the target has no native custom-agent or subagent mechanism, set its delivery
to `unsupported` with the exact limitation in `reason`; an ordinary prompt file
is not equivalent. If a defining safety
boundary cannot be enforced, record whether the role is wholly unsupported or
whether a narrower representation still preserves its complete canonical
contract. A role that must implement changes cannot be called supported merely
because a read-only role is possible. Do not claim enforcement from wording
alone. A delivered role with untested discovery, routing, or permissions keeps
`verification: pending` and a compact `next_action` under the
[verification criteria](../verification.md).

## Verify

Run these native checks during adapter development or explicitly requested
acceptance, not as an ordinary maintained-installation tail.

Prove native discovery of each exact role identity and explicit or automatic
routing as defined by the product. Prove the actual spawned role loads its
method, not only that the coordinating session can read it. In an isolated
harmless scope, test one permitted action and one prohibited action whenever the
role relies on native enforcement. Record what
the product enforced, what remains instruction-only, and what cannot be
represented.

A model declining a prohibited action proves instruction following, not native
enforcement. Use a harmless action that reaches the relevant native control and
inspect its denial. Keep successful role loading separate from missing or
unsupported restrictions; a future routing check cannot repair a permission gap.

When model or reasoning selection is claimed, check the effective settings of
the spawned agent through available native metadata. A requested value alone
does not prove it took effect. Reuse the role probe for this check instead of
starting a separate agent only to inspect settings.

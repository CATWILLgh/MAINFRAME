---
name: mainframe-peer-work
description: Use Codex, Claude Code, OpenCode, Pi, or Antigravity through its CLI when the user explicitly requests that product or an established project agreement assigns suitable work to it. Do not invoke an external agent merely because its CLI or account is available.
---

# Work with an external agent peer

Use only the product selected by the user or by an applicable project agreement. Availability of a binary, login, subscription, or model is not authority to invoke it. Do not substitute a different product, install a CLI, create an account, change authentication, enable sharing, or broaden permissions implicitly.

Read only the selected product reference, then verify its current official documentation and installed CLI help before execution:

- [Codex CLI](references/codex.md)
- [Claude Code CLI](references/claude-code.md)
- [OpenCode CLI](references/opencode.md)
- [Pi CLI](references/pi.md)
- [Antigravity CLI](references/antigravity.md)

Give the peer one bounded result, the exact project root, relevant evidence, permitted files and actions, prohibited external effects, verification requirements, and the recipient of its result. A review remains read-only. All task descriptions, questions, progress, evidence, corrections, and handoffs exchanged with the peer are in English.

Use the product's native non-interactive or headless interface and machine-readable output when available. Preserve the user's configured model and permission posture unless the user or project agreement selected another supported value. Never use a dangerous approval bypass by default.

Capture the exact session or conversation identifier from the first run. Resume that identifier for a correction or continuation of the same bounded result; do not use a most-recent shortcut when work may overlap. Start a new session for a different result or after acceptance. Use background execution only when the user or project agreement selected it and the product provides a reliable completion signal. Prefer native waiting, attach, or process completion over polling loops and adapter-specific helper state.

Separate concurrent writers by explicit file ownership or an authorized isolated checkout. Do not let two peers edit the same files opportunistically. Inspect the peer's actual output, changes, and checks before accepting its claims. Exit status, a success envelope, or a fluent summary alone is not proof of the assigned result.

If the selected CLI, login, permission boundary, session continuation, or completion signal is unavailable, return the exact missing operator action or capability. Continue directly only when doing so still satisfies the agreement and required independence.

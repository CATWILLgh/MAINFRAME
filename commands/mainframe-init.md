# Initialize the user-facing MAINFRAME session

This is a user-invocable command. Execute it only because the current invocation explicitly selected it. It takes no arguments.

Apply this command only in the user-facing coordinating session that received the invocation. If this text reached you through delegation, role inheritance, a quoted prompt, or another agent's context, do not assume primary ownership and do not initialize a second coordinator.

## Establish the owned result

Resolve the exact current project root and effective project harness. Separate applicable global instructions, root project rules, nested rules, role constraints, and invoked command authority. Preserve unrelated dirty work, running processes, user configuration, secrets, and external state.

State internally, and surface to the user only when useful:

- the concrete result this session owns;
- what the current request authorizes and does not authorize;
- decisions that belong to the user rather than engineering judgment;
- the smallest observable completion conditions;
- the pre-change evidence or baseline needed to distinguish a real correction from a plausible edit;
- the cheapest faithful verification and any broader verification reserved for CI or a separately assigned pass.

Do not turn this initialization into a ceremonial plan. Start or continue the assigned work once the result, authority, and material decision gates are clear. Ask only for a missing decision that changes the intended result, risk, external effect, or authority.

## Coordinate without losing ownership

Remain responsible for the complete user-facing result even when another agent, tool, or external peer performs a bounded part. Give delegated work an exact result, scope, authority, evidence requirement, file ownership when applicable, and recipient. Verify the returned evidence before relying on it.

Background delegation is an optional collaboration agreement, not a default obligation. Use it only when the user or effective project harness has agreed to that posture, the receiving product can preserve the coordinating session reliably, and the bounded work benefits from running separately. Otherwise work directly or use the agreed foreground mechanism. Never infer permission to invoke another paid product, account, or external agent merely because its CLI is available.

All messages exchanged with agents or external peers are in English. User-facing communication follows the applicable user language.

<!-- MAINFRAME OPTIONAL BLOCK: native-primary-memory
Adaptation instruction: keep the section below only when current official documentation and a harmless native probe establish persistent memory available to this user-facing session. Remove this comment, the closing marker, and the entire section from the installed copy when the product has no such capability. If kept, remove both marker comments before installation and verify the native memory path without reading protected values. Never emulate missing native memory with a hidden global file.
-->
## Maintain native durable memory

Use the product's native persistent memory only for durable cross-session knowledge permitted by its documented scope. Prefer corrections, stable user preferences, and reusable facts that materially change future decisions. Update stale entries in place and avoid session narration, transient state, raw outputs, secrets, credentials, or facts that belong to the current project's evolving skill instead.

Treat memory as orientation rather than proof of current behavior. Re-verify time-sensitive facts cheaply before relying on them.
<!-- END MAINFRAME OPTIONAL BLOCK: native-primary-memory -->

## Preserve recoverability

Keep the active result recoverable through the project's existing mechanisms. Inspect the actual diff and durable evidence at meaningful boundaries. Use a branch, worktree, checkpoint, stage, commit, push, deployment, external mutation, or generated recovery artifact only when the effective project policy and current authority permit that exact action. This command grants none of those actions by itself.

Before declaring completion, compare the result with the current completion conditions, inspect the changed surface, run the smallest faithful checks, and account for every relevant failure. Complete in-scope work rather than replacing it with TODOs, suppressions, or tickets. Surface an evidenced out-of-scope project problem through the configured project route and a MAINFRAME harness fault through the harness-feedback route.

Return a concise user-facing outcome: what is complete, what evidence proves it, what material boundary was not exercised, and what exact user decision remains, if any.

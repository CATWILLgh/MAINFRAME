---
id: 7e88d75a
title: Subagent-only skills leak into the OpenCode and Codex main-agent registries
status: open
priority: medium
component: adapter-contracts
discovered: 2026-07-15
discovered-from: ["#553bad8e"]
tags: ["skills", "visibility", "subagents", "opencode", "codex", "adapter-parity"]
---

# 7e88d75a: Subagent-only skills leak into the OpenCode and Codex main-agent registries

## What was observed

MAINFRAME defines a designated-subagent-only scope as `user-invocable: false` plus `disable-model-invocation: true`, with the skill delivered through the target agent's `skills:` preload. Eight current skills use that contract: `decision-review`, `dokploy-api`, `frontend-design`, `nestjs-backend-patterns`, `nextjs-backend-patterns`, `python-backend-patterns`, `react-frontend-patterns`, and `shadcn`.

Claude Code preserves both fields and supports the intended boundary. The OpenCode and Codex adapters do not:

- OpenCode installs all 18 skills globally. OpenCode ignores the Claude-specific visibility keys, and `opencode debug skill` confirms that all eight restricted skills are registered for the main runtime. The default main agent can therefore discover and invoke methods intended only for designated subagents.
- Codex renders all 18 skills into the global `~/.codex/skills/` registry while dropping both visibility fields. The current Codex session advertises the eight restricted skills to the main agent. Agent TOMLs ask their worker to load the same globally available `$skill`, rather than receiving an agent-private preload.

This is a semantic adapter failure, not merely different syntax: the neutral contract says the main agent must never see these skills, while two delivered targets expose them.

## Why it is a problem

The boundary exists to keep large stack-specific methods out of unrelated main-agent work and to preserve ownership by the specialized worker. Exposing them globally adds discovery/context cost, allows the main agent to bypass delegation, and makes an adapter appear functionally equivalent when it is weaker than the documented architecture.

Changing the source flags or exposing every skill intentionally would solve the adapter mismatch by deleting the desired contract, which is not acceptable.

## Why it is not a duplicate

- [#d189a02a](d189a02a-adapter-metadata-parser-drift.md) covers missing shared parser contracts and originally recorded no production regression. This ticket records an active cross-adapter behavioral regression with a distinct visibility boundary.
- [#553bad8e](553bad8e-actionable-skills-hidden-from-slash-menu.md) resolves user-menu visibility for `surface-ticket`; it does not cover agent-private skills leaking to other runtimes.
- [#c4b061ba](c4b061ba-reconcile-subagent-skill-preload-docs.md) concerns Claude Code preload semantics, not OpenCode or Codex delivery.

## What probably needs to be done

- Define a target-neutral visibility contract with three explicit scopes: user plus main agent, main agent only, and designated subagent only.
- Keep Claude Code's existing `disable-model-invocation` plus `skills:` projection.
- For OpenCode, either deny restricted skill names to main agents and allow them only on designated agents, or stop globally installing those skills and inject/package their content with the agent.
- For Codex, project `disable-model-invocation: true` at minimum to `agents/openai.yaml` as `policy.allow_implicit_invocation: false`. This prevents automatic main-agent invocation but still permits explicit `$skill`, so full user-plus-main isolation still requires an agent-private resource or embedding the required method into generated agent instructions while excluding it from global skill installation.
- If a runtime cannot enforce isolation, fail or emit a visible degraded-capability diagnostic rather than silently claiming parity.
- Add an installed-runtime contract test that probes both negative access from the main agent and positive access from the designated agent.

## Acceptance criteria

- The eight designated-subagent-only skills are absent from the main-agent discovery and invocation surface in Claude Code, OpenCode, and Codex.
- Each designated agent still receives its required method and can demonstrate a marker from the skill body.
- Main-agent-only skills remain model-invocable while staying out of the user command menu where that distinction exists.
- Adapter build summaries report any target that cannot preserve a visibility scope.
- Cross-adapter tests fail when a new skill's expected scope is not projected deliberately by every target.

## Sources

- `docs/layers/skills.md:93-103,109-115,134-139` — documented access, preload, and subagent-only contract.
- `docs/layers/decision-tree.md:25-33,65-73` — “only in a dedicated subagent” placement and bloat prevention.
- `core/skills/*/SKILL.md` — eight current `disable-model-invocation: true` declarations.
- `install.sh:628-631,663-668` — OpenCode global skill delivery.
- `adapters/codex/build_codex.py:396-449,465-471,694-727` — Codex global skill projection and agent load instruction.
- Live probe, 2026-07-15: OpenCode 1.17.15 registers all 18 MAINFRAME skills; the current Codex session exposes all 18 available skills to the main agent.
- [Build skills — Codex documentation](https://developers.openai.com/codex/skills) — `policy.allow_implicit_invocation: false` disables implicit model invocation but preserves explicit `$skill` invocation.

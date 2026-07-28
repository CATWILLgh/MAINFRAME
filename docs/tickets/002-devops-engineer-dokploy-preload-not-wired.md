---
id: 002
title: devops-engineer does not receive its dokploy-api skill preload (new plugin agent preload not wired mid-session)
status: closed
priority: medium
component: agents
discovered: 2026-06-02
discovered-from: []
tags: ["agents", "skills", "preload", "plugin", "dokploy"]
---

# 002: devops-engineer does not receive its dokploy-api skill preload

## What was observed
Clean (uncontaminated) `claude -p` probes show the `devops-engineer` sub-agent answers `UNKNOWN` to **top-of-skill** `dokploy-api` facts that are plainly in `dokploy-api/SKILL.md`:
- the `/api` URL prefix every endpoint lives under (`SKILL.md:16`),
- responses are bare JSON / no `{result:{data:{json}}}` wrapper (`SKILL.md:29`),
- the full-spec endpoint `GET /api/settings.getOpenApiDocument` (`SKILL.md:83`).

Total non-delivery, not truncation. Control: `nestjs-backend-engineer` in the same harness correctly returned its preloaded `nestjs-backend-patterns` recon-script path — so the `skills:` + `disable-model-invocation: true` mechanism works in general. Both agents use the identical frontmatter pattern. The only material difference: `devops-engineer` was created mid-session; `nestjs-backend-engineer` pre-existed (present at the last `install.sh` registration).

An earlier "verified, preload works" conclusion was wrong — it rested on a **contaminated** probe (the prompt fed the agent the distinctive skill framing, so its answer was echo, not recall). The clean blind probe reversed it.

## Why it is a problem
`devops-engineer`'s primary deploy capability is the `dokploy-api` skill. With `dokploy-api` set to `disable-model-invocation: true` AND the preload not delivering, the skill is currently reachable by **no one** (hidden from main, absent in the agent). Worse, the knowledge-less agent defaults to wrong assumptions — in probes it stated `Authorization: Bearer` for auth, the exact anti-pattern the skill exists to correct (real auth is `x-api-key`).

## Why it is not a duplicate
First ticket about agent skill-preload wiring. #001 is about `agents.md` doc staleness — unrelated.

## What probably needs to be done
1. Run `install.sh` (or fully restart Claude) to re-register the plugin, then re-probe with a **blind** probe (facts the prompt does not supply). Expected if the hypothesis holds: `/api`, `x-api-key`, bare JSON all answered correctly. — requires verification.
2. If the preload activates → root cause is "new plugin agent needs re-registration to wire `skills:` preload"; document it and close.
3. If it still returns `UNKNOWN` → real bug. Inspect: `devops-engineer.md` frontmatter parsing (long quoted `description` before `skills:`?), whether `dokploy-api` resolves by name in the plugin manifest, the plugin agent→skill preload binding for plugin sub-agents.
4. Interim option if dokploy reachability is needed before the fix: drop `disable-model-invocation: true` from `dokploy-api/SKILL.md` so the main context can load it again; re-add once the agent preload is confirmed.

## Acceptance criteria
- `devops-engineer` returns the correct `dokploy-api` facts (`/api` prefix, `x-api-key` auth header, bare-JSON responses, `settings.getOpenApiDocument`) under a blind `claude -p` probe.
- `docs/layers/agents.md` gray-zone #4 updated from "PARTIALLY RESOLVED" to resolved with the confirmed root cause.

## Sources
- `plugin-dist/agents/devops-engineer.md` — `skills: [dokploy-api, surface-ticket]`
- `plugin-dist/skills/dokploy-api/SKILL.md:16,29,83` — the in-skill facts probed
- `docs/layers/agents.md` gray-zone #4 — current status + methodology note
- Probe transcripts (session 2026-06-02): devops UNKNOWN vs nestjs recon-path correct

## Resolution (2026-06-02) — invalid premise (probe-methodology artifact)

**Closed: not a bug.** A realistic probe (dispatch `devops-engineer`, ask a Dokploy question, let it work normally — no `no-fetching` constraint) showed the agent **locates and reads** its `dokploy-api` skill files and answers correctly: `x-api-key` (not `Authorization: Bearer`, with the `trpc-to-openapi`-artifact explanation), the `/api` prefix, bare-JSON responses. The `disable-model-invocation: true` + `skills:` design works as intended — hidden from main, used by the agent.

The `UNKNOWN` results that prompted this ticket were a **probe artifact**: the probe forbade fetching ("from preloaded knowledge only"), which blocked the actual access path. `skills:` makes a skill *available to read on demand*, it does not pre-inject the body. No reinstall was needed; `install.sh` would not have changed anything (the plugin symlink was already correct).

**Lesson recorded** in `docs/layers/agents.md` gray-zone #4 and memory: probe agents the way they operate (give a task, let them read); don't feed the distinctive answer into the prompt; don't force `no-fetching`.

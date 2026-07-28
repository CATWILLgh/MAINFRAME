---
id: 35b82ec7
title: devops-engineer agent has no founding ADR; recent Docker doctrine decision also unrecorded
status: open
priority: low
component: docs
discovered: 2026-06-03
discovered-from: []
tags: ["docs", "adr", "devops-engineer", "decision-record"]
---

# 35b82ec7: devops-engineer agent has no founding ADR; recent Docker doctrine decision also unrecorded

## What was observed

The peer engineer agents have founding ADRs that record creation rationale, scope, and model/effort calibration: ADR 0055 (`python-backend-engineer`), ADR 0057 (`nestjs-backend-engineer`), with calibration in 0062/0063. The `devops-engineer` agent has **none**. The closest records are ADR 0066 (the `dokploy-api` skill it preloads) and ADR 0028 (the `ops-app-server-safety` skill it cross-refs) — neither establishes the agent itself: its scope boundaries vs the backend/frontend roles, the `model: sonnet` / `effort: medium` / `background: true` choice, or the data-store escalation layer (Phase E).

Additionally, on 2026-06-03 a Docker operational doctrine was added **inline** to the agent (Phase D: hardening defaults + debug playbook, both source-cited). That was a deliberate skill-vs-inline decision (see below) with no durable decision record — it currently lives only in conversation.

## Why it is a problem

No audit trail for why the agent is configured and scoped as it is. Future sessions / post-compact may re-litigate settled decisions ("why no `docker-ops` skill?", "why `sonnet/medium`?", "where is the devops/backend boundary?"). `decision-tree.md` §D values an ADR precisely as this trail: "in two weeks no one will remember why … and a week later someone will move it back." There is a documentation asymmetry with the backend agents.

## Why it is not a duplicate

- [#001](001-agents-md-stale-plugin-migration.md) — `docs/layers/agents.md` staleness (doc-sync after plugin migration), not a decision record for the agent.
- [#002](002-devops-engineer-dokploy-preload-not-wired.md) — a specific dokploy-preload wiring bug (closed), not the missing founding rationale.

This ticket is about the absent decision record for the agent itself.

## What probably needs to be done

Write a founding ADR for `devops-engineer` covering:
1. Creation rationale + scope boundaries (deploy/CI/containers/data-store-ops vs backend-engineer app code vs react-frontend-engineer).
2. Config: `model: opus` / `effort: high` / `background: true` (see the "Provenance migrated from the agent body" section below for the current values and rationale) — record the choice in the ADR, and whether to run an `agent-tournament` calibration (as 0062/0063 did for peers) or why it is deferred.
3. **Retroactively record the 2026-06-03 Docker inline-vs-skill decision:** inline chosen because Context7 covers Dockerfile *syntax*, `settings.json` ask-tier already gates *destructive* docker ops, and only the operational *debug playbook* was genuinely skill-worthy. Promote to a `docker-ops` skill via `decision-tree.md` Recipe M1/M2 on an observable growth signal (the inline Docker section grows to 2+ topics / gains conditional logic / exceeds comfortable agent-file size). Docker doctrine sources: [Docker build best-practices](https://docs.docker.com/build/building/best-practices/), [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html), [docker inspect](https://docs.docker.com/reference/cli/docker/container/inspect/) / [docker logs](https://docs.docker.com/reference/cli/docker/container/logs/) CLI refs.

## Acceptance criteria

- An ADR `docs/decisions/00NN-devops-engineer-agent.md` exists covering items 1-3.
- The Docker inline-vs-skill rationale + the promote-on-signal trigger are recorded in it.
- References reconciled (this ticket closed with the ADR number).

## Provenance migrated from the agent body (2026-07-13)

The model/effort rationale used to live only in the delivered agent body
(`core/agents/devops-engineer.md`), which shipped verbatim into the OpenCode
projection where it is false (that agent runs `openai/gpt-5.6-sol`, not
`opus`). It was removed from the body as part of ticket `5fae0bfa`
(OpenCode-delivered prose must not carry CC-dialect provenance). Captured here
so nothing is lost until the founding ADR (items 1-3 above) is written:

- **Current CC config (supersedes item 2's stale `sonnet/medium`):** `model: opus`
  / `effort: high`, from the contract's `reasoning-tier: deep`.
- **Rationale (verbatim from the removed body bullet):** set for the deeper
  infra-reasoning profile of this role — heavier than the `sonnet`/`medium`
  peer engineers. NOT yet tournament-calibrated (peers were, via ADR
  0062/0063); revisit via the `agent-tournament` method. Re-tournament after a
  notable prompt-body change.
- **OpenCode assignment (separate, not tournament-derived):** `gpt-5.6-sol` /
  `high`, chosen by fleet strength in the machine-local enrich file.

## Sources

- `plugin-dist/agents/devops-engineer.md` (the agent; Phase D Docker block added 2026-06-03).
- `docs/decisions/0055-*`, `0057-*` (peer founding ADRs), `0062/0063` (peer calibration), `0066-dokploy-api-skill.md`, `0028-ops-app-server-safety-skill.md`.
- `docs/layers/decision-tree.md` §B (Recipe M1/M2), §D (ADR mandatory).

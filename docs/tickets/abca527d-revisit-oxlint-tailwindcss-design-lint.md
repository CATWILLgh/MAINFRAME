---
id: abca527d
title: Revisit oxlint-tailwindcss as a zero-config design-lint hook once it matures
status: open
priority: low
component: hooks
discovered: 2026-06-04
discovered-from: []
tags: ["hooks", "frontend", "tailwind", "lint", "design", "tech-debt"]
---

# abca527d: Revisit oxlint-tailwindcss as a zero-config design-lint hook once it matures

## What was observed

ADR 0072 evaluated a design-hygiene check hook (option E). Conclusion: do NOT ship one this round. The reliably-scriptable rules (`eslint-plugin-tailwindcss`: `no-contradicting-classname`, `classnames-order`, `enforces-shorthand`) are mostly cosmetic and require a project-side eslint + tailwind config, which a global hub hook cannot assume. The high-value check (raw-colour → semantic-token enforcement) is a false-positive firehose (charts, SVG, third-party props) — the hub's `react-perf` lesson applies.

A promising alternative surfaced in research: **`oxlint-tailwindcss`** — a third-party oxlint plugin, zero-config, designed for Tailwind v4 (22 rules with autofix). Zero-config + oxlint speed would fit the per-edit hook model the way `eslint-plugin-tailwindcss` does not. But it is young (published ~2026-03) with no release track record, so shipping it into the hub now is unproven risk.

## Why it is a problem

Not a bug — a deferred opportunity. The hub currently has no automated design-hygiene gate; the doctrine in `frontend-design` is enforced only by the agent reading it. A low-FP, zero-config Tailwind v4 linter in a PostToolUse hook would add a cheap regression net for the deterministic class-hygiene rules (contradicting / order / shorthand) without the integration friction of `eslint-plugin-tailwindcss`.

## Why it is not a duplicate

The current `frontend-design` and `shadcn` skills provide agent guidance:
visual decisions, accessibility constraints and component-composition rules.
They do not run a deterministic class linter or enforce findings after a file
edit. This ticket is only an optional evaluation of whether
`oxlint-tailwindcss` has matured enough to add that automated, low-false-positive
check; it neither replaces nor expands the two existing skills.

## What probably needs to be done

- Re-evaluate `oxlint-tailwindcss` once it has a stable release track record (semver ≥ a few minor versions, issue-tracker health, Tailwind v4 coverage confirmed).
- If solid: prototype a PostToolUse hook on `.tsx`/`.jsx`/`.css` running only the deterministic, low-FP rules (no `no-unknown-classes` until config-stability is proven). Fail-safe (exit 0) when the binary or a project tailwind config is absent — mirror the nodejs-security hook pattern.
- Measure FP rate on a real shadcn project before enabling globally (the `react-perf` firehose lesson is the bar to clear).

## Acceptance criteria

- A decision recorded (ship / keep deferred) with the FP measurement that backs it.
- If shipped: hook fail-safe verified (silent without binary/config), low-FP confirmed on a real project, registered in `plugin-dist/hooks/hooks.json`.

## Sources

- ADR 0072 — `docs/decisions/0072-frontend-design-craft-upgrade.md` (option E evaluation).
- oxlint-tailwindcss — https://sergioazocar.com/en/blog/oxlint-tailwindcss-the-linting-plugin-tailwind-v4-needed/
- eslint-plugin-tailwindcss — https://github.com/francoismassart/eslint-plugin-tailwindcss

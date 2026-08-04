<!-- Generated from MAINFRAME hub (core/skills/surface-ticket/template.md) — do not edit. -->

# Ticket template

Copy this skeleton when creating a ticket. Do not reconstruct it from memory — stale keys and the old sequential-id habit creep back in that way.

## Filename and id

`<id>-<short-slug>.md`:

- `<id>` — random 8-char hex token, generated fresh. It is branch-collision-free: two branches never allocate the same id, so there is no renumber-on-merge. Generate:
  ```sh
  openssl rand -hex 4                                # e.g. 3f9a2c01
  head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n'  # fallback, no openssl
  ```
- `<short-slug>` — 3-7 kebab-case words summarising the issue.
- The filename id and the frontmatter `id:` must match.

## Frontmatter (required schema)

```yaml
---
id: <hex>
title: <one line, human description>
status: open                  # open | needs-refinement | in-progress | closed | approved
priority: medium              # critical | high | medium | low
component: <free tag>         # e.g. "server", "client", "infra", "docs"
discovered: <YYYY-MM-DD>
discovered-from: []           # cross-refs: ["#3f9a2c01"] or empty
tags: []                      # for grep: ["validation", "security", "perf"]
---
```

Never omit a key. Empty values are `[]` for lists, `null` / empty string otherwise.

## Body — fixed sections

Use these headers verbatim. Skip a section only if it genuinely does not apply.

```markdown
# <id>: <title>

## What was observed
<facts only: where, what, expected vs actual, output / behaviour>

## Why it is a problem
<impact: correctness / security / business invariant / UX. Cite standards if applicable (OWASP, CWE, RFC)>

## Why it is not a duplicate
<cross-refs to related tickets, with the distinction>
- [#3f9a2c01](3f9a2c01-slug.md) — covers X; this ticket is about Y.

## What probably needs to be done
<actionable steps. Mark "requires verification" where uncertain>

## Acceptance criteria
<measurable: tests pass, lint clean, behaviour verified by ...>

## Sources
<code references using `path:line`, docs links, related commits>
```

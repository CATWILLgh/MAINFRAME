# Ticket format and lifecycle

The ticket path is its lifecycle state. Do not duplicate that state in
frontmatter. Create only the needed destination directory, never empty states in advance.

```text
docs/tickets/
├── open/
│   ├── observations/
│   ├── needs-scope-review/
│   ├── needs-decision/
│   ├── ready/
│   └── needs-verification/
└── archive/
    ├── resolved/
    └── rejected/
```

- `observations`: plausible findings not deliberately confirmed.
- `needs-scope-review`: confirmed problems whose locations, consequences, and
  blast radius still need profile review.
- `needs-decision`: reviewed problems needing a product, infrastructure, or
  authority decision from the user.
- `ready`: reviewed technical work needing no new user decision.
- `needs-verification`: completed implementations awaiting an independent check.
- `archive/resolved` contains independently verified fixes.
- `archive/rejected` contains tickets later disproved, superseded, or duplicated.

There is no `in-progress` ticket state. A ticket remains in `ready` while work
is attempted and moves only after an implementation produces evidence ready
for independent verification. An interrupted run therefore cannot strand it.

Only the independent verification stage moves a ticket to
`archive/resolved`. A failed verification returns the same ticket to:

- `ready` when the implementation is incomplete or incorrect;
- `needs-scope-review` when affected locations or blast radius were missed;
- `needs-decision` when a user-owned choice has emerged.

Archive files are immutable. Do not reopen, edit, move, or rename them. A later
occurrence gets a new id and may link to a known archived ticket without
searching the archive by default.

A legacy project may keep tickets directly in `docs/tickets/`. Do not classify
or move them during intake: migrate them separately after reviewing each state.

## Identity and filename

Use `docs/tickets/<state>/<id>-<short-slug>.md`.

- Generate a random four-character lowercase hexadecimal id with
  `openssl rand -hex 2`; check open and archived directories and retry on collision.
- Use a concise descriptive kebab-case slug that identifies the problem without
  opening the file.
- Preserve the id for the ticket's full lifetime.
- An open ticket may receive a clearer slug as understanding changes; update
  links to its old path. Never rename an archived ticket.

## Common frontmatter

```markdown
---
id: <four lowercase hex characters>
title: "<plain description of the problem or observation>"
component: "<observed component or unknown>"
created: <YYYY-MM-DD>
created-from: "<current task, audit, or investigation>"
---
```

Do not add `status`; the directory is authoritative. Keep evidence in the
ticket body and preserve earlier observations and verification results as
history. Add only concise facts needed by the next stage, not raw logs or a
session transcript.

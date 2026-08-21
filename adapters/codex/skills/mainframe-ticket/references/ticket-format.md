# Ticket format and lifecycle

The ticket path is its lifecycle state. Do not duplicate that state in
frontmatter. Create only the needed destination directory, never empty states
in advance.

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
- `ready`: reviewed work whose execution route is recorded explicitly.
- `needs-verification`: completed implementations awaiting an independent check.
- `archive/resolved`: independently verified fixes.
- `archive/rejected`: tickets later disproved, superseded, or duplicated.

There is no `in-progress` state. A ticket remains in `ready` while work is
attempted and moves only after an implementation produces evidence ready for
independent verification. An interrupted run therefore cannot strand it.

Every ticket in `ready` or `needs-verification` carries one execution route in
frontmatter:

- `execution: autonomous` means the expected behavior is fixed by cited current
  project evidence and no product, business-logic, material infrastructure,
  destructive-action, data, authority, or irreducible preference choice remains.
- `execution: user-approved` means the user resolved the recorded choice through
  `mainframe-init` for that ticket. It may be implemented only by that route's
  exact one-ticket Goal, never by the queue-wide autonomous implementation run.

Before assigning `execution: autonomous`, add an `## Autonomous implementation
boundary` section naming the fixed expected behavior, the repository or owning
external evidence that fixes it, and the material decisions excluded from the
implementation. Agent confidence, a proposed solution, or location in `ready`
is not evidence. Code in a business path may be changed autonomously only to
restore that already-fixed behavior; choosing new business behavior is never
autonomous.

Only independent verification moves a ticket to `archive/resolved`. A failed
verification returns the same ticket to:

- `ready` when the implementation is incomplete or incorrect;
- `needs-scope-review` when affected locations or blast radius were missed;
- `needs-decision` when a user-owned choice emerged.

Archive files are immutable. Do not reopen, edit, move, or rename them. A later
occurrence gets a new id and may link to a known archived ticket without
searching the archive by default.

## Normalize legacy open tickets during discovery

At the start of `mainframe-tickets-find`, bring current open ticket records
under the canonical tree without asking the user. Make the migration a separate
coherent change before discovering new problems.

- Preserve every ticket body, history, existing id, and meaningful title. Do
  not shorten a legacy id merely because new ids use four hex characters.
- Add missing common frontmatter only from facts already present in the file;
  use `unknown` where the component or origin cannot be recovered safely.
- Give an unclear filename a concise kebab-case slug and update repository-local
  links to the moved path.
- Keep an explicitly recognizable open state when it maps directly to the
  canonical tree. Put an ambiguous legacy open record in `observations`.
- A legacy `ready` record without the autonomous boundary and
  `execution: autonomous` is not eligible autonomous work: move it to
  `needs-scope-review`. Never invent the missing eligibility evidence.
- Leave archived records and non-ticket documentation unchanged. Do not
  consolidate duplicates or verify ticket claims during normalization; those
  belong to `mainframe-tickets-refine`.

The normalization must be idempotent: a second discovery run over an already
canonical queue produces no structural changes.

## Identity and filename

Use `docs/tickets/<state>/<id>-<short-slug>.md`.

- Generate a random four-character lowercase hexadecimal id with
  `openssl rand -hex 2`; search open and archived directories and retry on
  collision.
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
# Added only after refinement or an explicit user decision:
# execution: autonomous | user-approved
---
```

Do not add `status`; the directory is authoritative. Keep evidence in the
ticket body and preserve earlier observations and verification results as
history. Add only concise facts needed by the next stage, not raw logs or a
session transcript.

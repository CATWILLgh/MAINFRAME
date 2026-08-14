# Record an intentionally confirmed problem

Use this path only when the immediate caller explicitly assigned focused
investigation or confirmation of a concrete hypothesis, including an audit
whose contract requires confirmed findings. Evidence must establish that the
problem exists; model memory or a plausible explanation is not evidence.

## Confirm the claim

State a falsifiable claim, then use the source that directly defines or
demonstrates it:

- repository structure or behavior: exact code, configuration, call chain, or
  repeated local pattern;
- runtime failure: a reproducible command, red test, trace, or observed output;
- product requirement: the current definition of done, project decision, or
  explicit user requirement;
- framework, library, database, protocol, or external API behavior: current
  official documentation or Context7 for the exact installed version together
  with the local usage that makes it relevant;
- security issue: an official advisory and the affected installed version;
- missing regression coverage: the existing test inventory and a concrete
  behavior that can change without a failing test.

Check the most plausible alternative explanation. For numbers, dates,
versions, amounts, units, and calculated differences, compare exact values with
their source. Separate confirmed facts from remaining uncertainty. Do not turn
an unconfirmed hypothesis into a ticket.

## Search open tickets

Search `docs/tickets/open/` recursively for a clear match.

- When a matching observation exists, append the evidence and move that ticket
  to `open/needs-scope-review/`.
- When a matching open ticket is already further along, append only materially
  new evidence. Return it to `needs-scope-review` only when that evidence proves
  its present scope or blast radius incomplete.
- When the match is uncertain, keep the findings separate.
- Do not search or modify the archive by default.

## Create only a confirmed problem

When no clear open match exists, follow [ticket-format.md](ticket-format.md) and
create:

`docs/tickets/open/needs-scope-review/<id>-<short-slug>.md`

After the common frontmatter, use:

```markdown
# <title>

## Confirmed problem

- Actual behavior: <what happens>
- Required or safe behavior: <what should happen and who defines it>
- Known locations: <repository links or components>

## Evidence

### <YYYY-MM-DD>

- Claim: <falsifiable statement>
- Confirmation: <reproduction, code path, test, or exact comparison>
- Sources: <repository links and current authoritative URLs>
- Limits: <what the evidence does not yet establish>
```

Do not move the ticket directly to `ready` or `needs-decision`. A separate
profile review must establish every affected location, blast radius, and next
lifecycle state.

If the investigation disproves a hypothesis for which no ticket existed, do
not create a rejected ticket. Return the negative result through the owning
audit or investigation. `archive/rejected` is only for an existing ticket that
a later stage disproves, supersedes, or confirms as a duplicate.

# Record an incidental observation

Use this path for a concrete, plausible problem noticed outside the active
task's assigned result or found by an explicitly broad discovery run. Locate
and describe the observation, but do not investigate its cause, actual impact,
priority, or blast radius.

## 1. Search open tickets

Search `docs/tickets/open/` recursively using the most distinctive available
behavior, location, component, identifier, or error text. Vary the query when
one term is too broad or naming may have changed. Read only plausible matches
far enough to decide whether they clearly describe the same observation.

- When a match is clear, append only the materially different location,
  condition, symptom, or observed output.
- When a match is uncertain, create a separate observation. Do not merge two
  potentially different problems to save a file.
- Do not search the archive by default. If a relevant archived ticket is
  already known, link to it from the new observation without changing the
  archived file.

## 2. Create an observation when no clear match exists

Follow [ticket-format.md](ticket-format.md) and create:

`docs/tickets/open/observations/<id>-<short-slug>.md`

After the common frontmatter, use this minimal body:

```markdown
# <title>

## Observations

### <YYYY-MM-DD>

- Where: <repository link, command, or component>
- Observed: <concrete behavior or output>
```

Do not add a probable cause, impact claim, priority, proposed solution,
acceptance criteria, or source research. Those belong to deliberate profile
review.

## 3. Continue the owning route

During ordinary work, resume the active task immediately after the write.
During a discovery run, continue with the next unchecked part of its coverage
map. Do not fix or confirm the observation inline, even when the apparent
change looks small. If it blocks the assigned result or agreed definition of
done, stop treating it as an observation and return it to the active workflow.

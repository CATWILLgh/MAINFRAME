# Record an incidental observation

Use this path for a concrete, plausible problem noticed outside the active
task or found by an explicitly broad discovery run. Locate and describe the
observation without investigating its cause, actual impact, priority, or blast
radius.

## Search open tickets

Search `docs/tickets/open/` recursively using the most distinctive available
behavior, location, component, identifier, or error text. Vary the query when
one term is too broad or naming may have changed. Read only plausible matches
far enough to decide whether they clearly describe the same observation.

- For a clear match, append only a materially different location, condition,
  symptom, or observed output.
- For an uncertain match, create a separate observation. Do not merge possibly
  different problems merely to reduce file count.
- Do not search the archive by default. If a relevant archived ticket is
  already known, link it from the new observation without changing the archive.

## Create an observation

When no clear match exists, follow [ticket-format.md](ticket-format.md) and
create:

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
acceptance criteria, or external source research. Those belong to deliberate
profile review.

## Continue the owning route

During ordinary work, resume the active task immediately after writing. During
a discovery run, continue with the next unchecked part of its coverage map. Do
not fix or confirm the observation inline, even when the apparent change looks
small. If it blocks the active result or definition of done, return it to the
active workflow.

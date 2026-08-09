# Intake ticket template

Create `docs/tickets/<id>-<short-slug>.md`, where `<id>` is the output of
`openssl rand -hex 4`. Keep the same id in frontmatter.

```markdown
---
id: <eight hex characters>
title: <plain description of the observation>
status: needs-refinement
component: <observed component or unknown>
discovered: <YYYY-MM-DD>
discovered-from: <current task or goal>
---

# <title>

## Observations

### <YYYY-MM-DD>

- Where: `<path:line, command, or component>`
- Observed: <concrete behavior or output>
```

For a later occurrence, append another dated observation with only materially
different facts. Do not normalize older tickets to this template during intake.

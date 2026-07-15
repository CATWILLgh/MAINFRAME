# Tickets

File-based ticket queue for this project. Convention is managed by the hub `surface-ticket` skill.

- Filename: `<id>-short-slug.md`, where `<id>` is a random 8-hex token (branch-collision-free).
- Status / priority / component live in each ticket's YAML frontmatter, not here.
- List open: `rg -l '^status: open' docs/tickets/`
- High priority: `rg -l '^priority: (critical|high)' docs/tickets/`
- Search body: `rg -l 'keyword' docs/tickets/`

# Capture or update a project idea

Run only on explicit user invocation. Accept the user's text following the command
as the idea or requested update. If no text was supplied, ask what to record;
do not convert unrelated conversation, operating instructions or the command's
own setup into a task. Recording an idea does not authorize its implementation.

## Resolve and preserve the receiving project

Use the active project's root, including its actual Git worktree boundary. Write
only that worktree's `.docs/todo` index and `.docs/todos/` notes. Create missing
directories/files as needed. Keep both in version control; do not add ignore
rules or silently force-add through an existing exclusion. Surface a conflicting
project policy when it prevents tracked storage. Preserve unrelated changes and
partial staging. Separate worktrees keep their own Git versions of these files;
do not write into another checkout or invent a shared external store.

## Decide what to capture

Read the index and only candidate notes relevant to the user's idea. Update an
existing semantic match when the new text concerns the same work; create a new
entry for independently useful work. Do not merge ideas merely because they
share keywords. Consolidate repeated information and preserve the user's meaning.

Choose the group from the user's expressed intent:

| Index heading | Meaning |
| --- | --- |
| `## Запланировано` | The user decided this should be done; this is not implementation authorization |
| `## На рассмотрении` | The idea is being evaluated and no commitment has been made |
| `## Отложено` | Retained for later, with no current commitment to work on it |
| `## Отказались` | The user decided against it; explain the actual reason in the note |

If the intended meaning or group cannot be inferred without guessing, ask the
smallest useful clarification before writing that record. Missing implementation
detail alone need not prevent capture: label consequential unknowns explicitly.
Never invent requirements, agreement, a rejection reason or completed work.

## Write a compact, self-contained record

Use UTF-8 Markdown even though the index has no extension. Its fixed structure is
`# TODO`, then the four headings above in that order. Entries are one physical
line each, under their group:

```text
- Сохранять выбранные фильтры списка заказов между посещениями. [Подробнее](todos/saved-order-filters.md)
```

The summary alone has 1–500 Unicode characters; the leading `- `, separating
space and final link are excluded. It must identify the requested work without
depending on the chat. Use a unique descriptive lowercase ASCII kebab-case
filename ending in `.md`; preserve existing filenames and links on ordinary updates.

Each note has at most **5000 Unicode characters in total**, including whitespace,
headings, links and the final newline. Write a self-contained title and these
nonempty sections, adapting the content rather than inventing detail:

```markdown
# Сохранение фильтров списка заказов

## Суть
Что нужно изменить и зачем это пользователю.

## Ожидаемый результат
Наблюдаемый результат, по которому понятно, что идея реализована.

## Ограничения
Существенные границы и неизвестные. Если пользователь не задал ограничений,
так и укажи; не придумывай их.
```

Keep the group in the index only. A declined idea also requires a nonempty
`## Решение` section explaining why the user decided against it. Preserve useful
rationale when a decision changes without turning the note into a chat log.
When explicitly recording an evidenced completion, remove the entry from the
active index, retain its note, and add a short `## Результат` with the observed
result and completion date. Do not treat disappearance from the index as proof
of completion. Do not delete a note merely because the task was completed.

Maintain one current description. Rewrite and consolidate on updates instead of
appending every message. If the content will not fit, shorten it without losing
requirements; if distinct work genuinely needs separate records, make the split
explicit. Do not truncate text or create continuation notes to evade the limit.

## Verify the addressed change

Write or update the note before adding or moving its index entry, so that links
and rejection rationale are present when the index is checked. Re-read the
latest files immediately before applying an edit and preserve other writers'
changes. Verify only changed rows, their links and changed notes: summary length,
whole-note length, required structure, correct group and self-contained meaning.
Use the available native file-edit path protected by `mainframe-todo-limits`;
shell writes may not be intercepted. The hook checks formal invariants, not
semantic clarity. Do not treat a silent or unavailable hook as proof of a valid
record, and do not scan every note to verify one edit.

Return the captured summary, group and a link to the note. For a completed item,
link its retained result note. Local checkpoints follow the receiving project's
existing rules; this command does not authorize push or publication.

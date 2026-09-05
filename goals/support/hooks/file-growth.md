# Notice substantial new file growth

Source: [length-quality-note.py](../../../templates/hooks/scripts/length-quality-note.py), [_length_check.py](../../../templates/hooks/scripts/_length_check.py).

Call `note_for_changes(cwd, changes)` with exact `path`, `before`, `after` values. The source thresholds are heuristics to review for the target; the result is advisory.

Purpose: prompt a useful structure check when current edits materially enlarge
a file, without treating a fixed line count as proof of poor design.

`{{HOOK_BINDING}}`: compare the pre-edit baseline with current task-attributable
growth at a documented edit or completion boundary. Use a modest bounded
advisory message when the growth merits reviewing responsibilities and cohesion.
Choose any heuristic threshold from actual file types and project conventions;
do not split coherent files just to satisfy a universal size limit.

Check in isolation: materially new growth produces one useful notice; an
untouched large file stays quiet; repeated edits do not repeat the same notice;
generated data and fixtures are handled appropriately; the hook does not block
completion because of size alone.

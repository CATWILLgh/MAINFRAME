# Hook source guide

Start with the working source, then adapt its binding using the target product's
current official documentation. The short documents beside this guide describe
intent and limitations. These are source templates, not an installed adapter:
there is no native manifest, dispatcher, installer, or telemetry service here.

The scripts were recovered from archive commit `53ad1e5`. Detection logic and
supporting state were retained; telemetry calls, event storage, peer/session
machinery, and the subagent-only staging/commit ban were removed. Execution and
dependency failures now exit nonzero instead of silently succeeding.

## Bindings to adapt

The reference JSON shape uses `tool_name`, `tool_input`, `cwd`, `session_id`,
`agent_id`, and, for paired snapshots, `turn_id` and `tool_use_id`. Shell
operations use `Bash` with `tool_input.command`; file operations use `Edit`,
`Write`, or `MultiEdit` with paths and before/after text. These names are source
conventions, not evidence that a target supports them.

[Shared IO](scripts/_hooklib.py) reads one JSON object from stdin and emits the
retained `hookSpecificOutput` or completion `decision` shapes. Replace these
with documented native inputs, outputs, error handling, and timeouts. Empty
stdout means no finding; a nonzero exit means an unavailable check, not a clean
result. A native binding must distinguish advisory failure from required-guard
failure and use [bounded failure handling](failure-feedback.md).

For modules exposing functions rather than `main()`, use the entry point named
in the corresponding short document. Do not execute a library file and assume
silence proves its check ran. Run only the selected checks, not every script on
every event.

## Shared source

| Files | Keep for |
| --- | --- |
| [_hooklib.py](scripts/_hooklib.py) | Payload/output binding, file types and Git baseline reads. |
| [_notice_state.py](scripts/_notice_state.py) | Atomic expiring notice deduplication by session and writer. |
| [_marker_state.py](scripts/_marker_state.py), [_markers.py](scripts/_markers.py) | Active finding ownership, revalidation and suppression/residue detection. |
| [comment_extract.py](scripts/comment_extract.py), [_comment_findings.py](scripts/_comment_findings.py) | Comment extraction and stable changed-comment identities. |
| [_python_findings.py](scripts/_python_findings.py), [_node_findings.py](scripts/_node_findings.py) | Ruff/Oxlint invocation and content-based security findings. |
| [_edit_snapshot.py](scripts/_edit_snapshot.py) | Paired tool-call snapshots and before/after edit reconstruction. |
| [_length_check.py](scripts/_length_check.py) | Line counts and Python function spans. |

Snapshot integration must capture permitted source files before an edit and
consume the same call's snapshot after success. Feed reconstructed deltas to
the checks; do not substitute another task's changes or claim exact attribution
from the fallback Git HEAD baseline. Exclude protected files before capture;
snapshots may contain source text. Snapshot files are private, consumed once,
and expire; finding/notice state expires too. Adapt the `MAINFRAME_*_DIR`
locations per installation and preserve concurrency isolation. This temporary
correctness state is not an event history.

The scanners need existing Ruff, Oxlint, or Semgrep executables as appropriate.
Inspect their invocations and the [Semgrep rules](rules/semgrep-informational.yml)
and [fixtures](rules/semgrep-informational.js). Missing tools are check limits;
the hook does not install them. The safety detectors cover specific patterns,
not all security defects. Constants, suppression policies, and completion
gates must be reconciled with the target and project before activation.

Each hook's progress row includes its linked source and dependencies. Validate
the adapted result with its positive, negative, malformed-input and repetition
cases. Local source regression tests run with
`python3 -m unittest discover -s scripts -p 'test_hook_sources.py'`;
native event delivery still needs a separate check in the installing product.

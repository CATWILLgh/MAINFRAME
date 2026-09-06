# Hook source guide

Start with the working source, then adapt its binding using the target product's
current official documentation. The short documents beside this guide describe
intent and limitations.

## Responsibility boundary

MAINFRAME supplies the detection logic, policies, dependencies, and regression
cases. Their quality is a source-maintenance responsibility, not something an
installing agent is expected to invent. The target harness determines which
events and enforcement mechanisms actually exist.

Adapt registration, event matching, payload conversion, result encoding,
paths, supported timeout handling, and state identifiers as needed. Preserve
what constitutes a finding, the advisory or blocking contract, deduplication,
and attribution guarantees. Do not add detectors, rewrite rules from prose,
or alter thresholds to make installation pass. A necessary semantic change is
a source problem to report, not an implicit installation decision.

If a required event, payload, or enforcement capability is absent, identify
the precise incompatibility during the briefing. Do not invent events, add a
polling loop, or substitute an unrelated event with different guarantees. A
documented native equivalent is usable only if the supplied behavior and
acceptance checks remain satisfied. First make a bounded, documentation-backed
attempt to find a faithful mapping or native equivalent. If neither can satisfy
the contract, skip that hook and continue installing the supported set. State
the missing capability, attempted mapping, and resulting coverage gap. This
fallback is already authorized; do not ask again for each unsupported hook.
Never activate a broken approximation or claim the skipped check is enforced.

## Bindings to adapt

The reference JSON shape uses `tool_name`, `tool_input`, `cwd`, `session_id`,
`agent_id`, and, for paired snapshots, `turn_id` and `tool_use_id`. Shell
operations use `Bash` with `tool_input.command`; file operations use `Edit`,
`Write`, or `MultiEdit` with paths and before/after text. These names are source
conventions, not evidence that a target supports them.

[Shared IO](../../../templates/hooks/scripts/_hooklib.py) reads one JSON object from stdin and emits the
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
| [_hooklib.py](../../../templates/hooks/scripts/_hooklib.py) | Payload/output binding, file types and Git baseline reads. |
| [_notice_state.py](../../../templates/hooks/scripts/_notice_state.py) | Atomic expiring notice deduplication by session and writer. |
| [_marker_state.py](../../../templates/hooks/scripts/_marker_state.py), [_markers.py](../../../templates/hooks/scripts/_markers.py) | Active finding ownership, revalidation and suppression/residue detection. |
| [comment_extract.py](../../../templates/hooks/scripts/comment_extract.py), [_comment_findings.py](../../../templates/hooks/scripts/_comment_findings.py) | Comment extraction and stable changed-comment identities. |
| [_python_findings.py](../../../templates/hooks/scripts/_python_findings.py), [_node_findings.py](../../../templates/hooks/scripts/_node_findings.py) | Ruff/Oxlint invocation and content-based security findings. |
| [_edit_snapshot.py](../../../templates/hooks/scripts/_edit_snapshot.py) | Paired tool-call snapshots and before/after edit reconstruction. |
| [_length_check.py](../../../templates/hooks/scripts/_length_check.py) | Line counts and Python function spans. |

Snapshot integration must capture permitted source files before an edit and
consume the same call's snapshot after success. Feed reconstructed deltas to
the checks; do not substitute another task's changes or claim exact attribution
from the fallback Git HEAD baseline. Exclude protected files before capture;
snapshots may contain source text. Snapshot files are private, consumed once,
and expire; finding/notice state expires too. Adapt the `MAINFRAME_*_DIR`
locations per installation and preserve concurrency isolation. This temporary
correctness state is not an event history.

The scanners need Ruff, Oxlint, or Semgrep executables as appropriate. The
pre-goal briefing explains missing tools and proposes a concrete installation
list. The installation goal installs only the dependencies agreed there and
verifies them before activating hooks; reuse compatible existing tools.
Inspect their invocations and the [Semgrep rules](../../../templates/hooks/rules/semgrep-informational.yml)
and [fixtures](../../../templates/hooks/rules/semgrep-informational.js). Missing tools are check limits;
the hook does not install them. The safety detectors cover specific patterns,
not all security defects. Verify that the supplied constants, suppression
policies, and completion gates can retain their meaning on the target before
activation; incompatibility does not authorize changing their semantics.

Each hook's progress row includes its linked source and dependencies. Validate
the adapted result with its positive, negative, malformed-input and repetition
cases. Local source regression tests run with
`python3 -m unittest discover -s scripts -p 'test_hook_sources.py'`;
native event delivery still needs a separate check in the installing product.

# Canonical hooks

Hooks are deterministic event reactions that cannot be represented reliably by
instructions alone. This file owns their exact semantic catalog, trigger and
failure contracts, attribution, dependencies, and representative cases. The
cross-product installation method lives in the
[hook component guide](../docs/installation/components/hooks.md).

The files in this directory define product-agnostic behavior; globally installed
adapter copies supply native event names, payload and output encoding, paths,
timeouts, registration, and permissions.

Install only hooks listed in `ADAPTATION.<product-id>.json`. Preserve their
trigger timing, filtering, blocking or advisory effect, failure behavior,
attribution, deduplication, and bounded context. Do not add telemetry or claim
equivalence when the product lacks a required event or enforcement mechanism.

Every rule has one fixed semantic class:

- A `guard` returns either silence or a hard block. Use it only before the
  protected side effect and only for an exact dangerous condition or hard
  invariant. It never requests permission, infers authority, or substitutes a
  warning for a required block.
- An `advisory` returns either silence or a bounded warning to the recipient
  responsible for the next action. Use it only for new, evidence-backed,
  actionable information. It never blocks, grants permission, or records
  generic status.

There is no hook-level `ask` result. Native product permission prompts remain
separate from MAINFRAME hooks. A rule must not change between blocking and
advisory behavior based on a guessed role, authority, conversation, or
execution topology. If two distinct conditions require different effects,
represent and verify them as distinct detector rules with fixed effects.

Both classes stay silent when there is no finding. Do not emit success notices,
repeat global instructions, or retain input as logs. Deduplicate repeated
advisories, omit secrets and unnecessary raw input, and bound each message to
the finding, its exact locus when available, and the decision-useful next
action. An advisory failure does not block the original action; report an
unavailable advisory check only when that fact can change the next decision.
A guard blocks only a positively recognized dangerous condition. Missing input,
timeouts, unavailable dependencies, parser limits, and detector exceptions are
not dangerous findings and must not create a hard lock. Represent a
decision-relevant protection failure as a distinct non-blocking advisory rule;
otherwise fail silently. Test both semantic findings and operational failures
during adaptation.

| Hook | Class | Trigger and result | State |
| --- | --- | --- | --- |
| `destructive-operations` | `guard` | Before a shell action, hard-block a recognized catastrophic filesystem deletion or a narrow Git operation that bypasses recovery and safety mechanisms | Stateless |
| `secret-access` | `guard` | Before a shell action, hard-block direct credential output or value-bearing registration through the `secret` helper and point to its protected route | Stateless |
| `rg-short-replace` | `advisory` | Before a shell action, warn when an actual ripgrep invocation uses short `-r`, which selects output replacement rather than recursion | Stateless; adapter deduplicates duplicate delivery of one native event |
| `commit-secrets` | `guard` plus unavailable-check `advisory` | Before an agent-initiated `git commit`, block newly introduced high-confidence secret material; warn without blocking when the prospective commit cannot be inspected | Stateless |
| `code-quality` | Post-edit quality, security, and structure advisories plus an attributed-finding completion guard | Around a successful file edit, report new high-confidence residue, security findings, or a size-review threshold crossing; before completion, revalidate and block only attributed blocking findings | One private temporary JSON file per adapter namespace, native execution scope, and workspace |
| `fallow-quality` | `advisory` | At a continuation-capable completion event after exact-scope TS/JS edits, report newly introduced structural findings or a decision-relevant unavailable check without blocking | Canonical detector is stateless; adapter may retain only bounded short-lived attribution state |

## Adapt `destructive-operations`

Copy `destructive-operations.py` unchanged when the product can call a Python
detector from its native hook. Keep any required payload/output wrapper in the
installed adapter, not in the canonical file. Pass the exact shell command,
tool working directory, active project root, and current user's home root to
`decision_reason`.

A returned reason must become a documented native hard denial for the action.
`None` means no decision: emit nothing and leave the product's native permission
layer authoritative. Never convert `None` into an allow decision. If the
product cannot intercept and deny a shell action before execution, mark the
component `unsupported`; an instruction, reminder, or after-action message is
not equivalent.

The filesystem check blocks recursive deletion of the filesystem root, current
user's home root, or active project root. It also blocks a relative recursive
deletion after an earlier directory-changing command when the effective target
cannot be determined without emulating the shell.

The Git check is a hallucination circuit breaker, not an authorization system.
It blocks force or mirror push, verification and low-level delivery bypasses,
hard reset, non-dry-run clean, deletion of reflog or unreachable-object recovery
data, immediate garbage-collection pruning, mass history rewriting, forced
branch or worktree deletion, clearing every stash, and direct low-level ref
mutation. Ordinary commits, pushes, merges, rebases, branch and tag work,
configuration, remote management, narrower cleanup, and all unclassified Git
operations remain governed by the global instruction and native permissions.
An intentionally required blocked operation is performed manually outside the
agent or enabled through a deliberate installed-policy change.

Keep the successful path silent. Do not create state, logs, history, telemetry,
permission prompts, transcript inspection, or inferred approval. Missing
required payload fields and detector exceptions are non-blocking unavailable
protection, not reasons to deny the action. Emit a bounded advisory only when
the failure can change the next decision. An intentionally unrecognized shell
expression remains under the native permission boundary and must not be
reported as checked.

## Adapt `secret-access`

Call `decision_reason` immediately before a shell action with the exact command.
A returned reason must become a documented native hard denial. `None` emits
nothing and leaves the product's native permission layer authoritative. A
missing or malformed command and detector failure are unavailable protection,
not reasons to deny the action.

The detector blocks only two direct helper mistakes: standalone `secret get
NAME`, which would print the value into agent context, and `secret set NAME
VALUE`, which would place the value in command arguments. It allows `secret set
NAME --clipboard`, the protected `--prompt` fallback, `secret copy NAME`,
`secret run NAME -- COMMAND`, and a nested `secret get` used only inside its
consumer invocation. Its denial never quotes the credential name or value.

Keep the detector stateless and silent on allowed actions. It is deliberately
not a shell parser, authorization mechanism, or credential sandbox. Protect
direct reads and searches of the installed store through the product's native
filesystem permissions when available, and report the exact enforcement gap
when no such boundary exists. If the product cannot deny a recognized command
before execution, mark this hook `unsupported` instead of replacing it with a
warning.

## Adapt `rg-short-replace`

Before registration, inspect the installed ripgrep help and confirm that short
`-r` takes replacement text while recursion is already the default. If the
installed executable has different semantics or cannot be identified, mark the
component `unsupported` rather than guessing from another search tool.

Call `advisory_message` immediately before a shell action with the exact
command. A returned message is non-blocking context for the recipient
responsible for the next command; `None` emits nothing. Malformed input and
detector failure stay silent and never block the shell action.

Preserve the detector's parsing of executable position, shell segments, quoted
values, options that consume values, `--`, supported wrappers, and bounded
nested shell commands. Warn for short `-r` even when replacement may be
intentional, because the message points intentional use to explicit
`--replace=...`; do not warn for that long form, option values, quoted examples,
or other executables.

Keep the advisory fixed and bounded rather than echoing the raw command. The
canonical detector creates no state. Suppress only duplicate delivery of the
same native event identity in the adapter; do not suppress a later, separately
executed mistaken command merely because an earlier event warned about it.

## Adapt `commit-secrets`

Call `check_command` immediately before a shell action with the exact command
and native working directory. A non-empty `block_reason` is a hard denial. A
non-empty `advisory` is non-blocking context for the recipient responsible for
the next action. An empty result emits nothing. Never turn an advisory or a
detector exception into a denial.

The detector activates only for an agent-initiated `git commit`. It examines
new high-confidence credential shapes in the effective index, supported
auto-staged or path-selected worktree content, literal commit metadata, and
binary blobs. It compares prospective content with the base tree so removed
values, pre-existing values, and unchanged renames do not create a finding.
Partial staging remains isolated from unrelated dirty worktree content.

The detector does not scan repository history, unrelated files, credential
stores, commands outside the receiving agent, or generic password and entropy
patterns. An encrypted staged blob passes naturally; the mere presence of SOPS
or git-crypt configuration never disables checks for other repository content.
When a worktree filter makes the exact prospective blob unavailable without
executing project code, emit the unavailable-check advisory instead of scanning
plaintext that Git may transform.

Keep the detector stateless and read-only. Never print a matched value. Bound a
denial to finding class, sanitized repository-relative path or metadata locus,
and line when available. The adapter must allow the original action when Git is
unavailable, a timeout occurs, input is malformed, or a supported boundary
cannot be established; deliver the canonical advisory when the product has a
documented non-blocking context channel.

## Adapt `code-quality`

Treat `code-quality.py` as one component. It has five fixed effects:

- a post-edit advisory for newly introduced high-confidence quality residue;
- a post-edit advisory for newly introduced high-confidence Ruff or Oxlint
  security findings;
- context-dependent Semgrep review advice that never blocks completion;
- a `new-growth-pressure` structure advisory for a file or Python function that
  crosses a conservative size-review threshold in the current edit;
- a completion guard for attributed blocking findings that remain after a
  fresh scan.

Operational failure is a separate bounded advisory, emitted once per execution
scope for each unavailable check. It never blocks. Do not turn the completion
guard into a warning, infer completion from a transcript, or claim parity when
the product cannot prevent completion. Record the guard as unsupported for that
product while preserving separately supported advisories only when their native
delivery can be proven.

The inventory intentionally keeps one row for this canonical component. If the
advisory is proven but the guard is unavailable, leave that row `unsupported`
and add one concise note such as `new-residue advisory installed;
unresolved-residue guard unavailable: <documented reason>`. Do not mark the
component `installed`, add sub-status machinery, or hide the useful advisory.

Use the smallest native identities the product actually provides. Pass a stable
adapter-owned namespace, the native session or conversation identifier as
`scope_id`, the normalized current workspace root, and the native tool-call or
step identifier as `operation_id`. The namespace is an installation constant,
not a field the product must supply. Do not require a universal task or agent
identifier. Aggregate subagent edits only when the product demonstrably shares
the same scope identifier or exposes reliable lineage; otherwise record that
limitation instead of scanning unrelated sessions or the whole machine.

Immediately before a file-edit tool, resolve only its explicit code paths inside
the current workspace and call `capture_before`. Immediately after the same
successful operation, call `record_after` with the same identifiers; pass
`succeeded=False` after a failed edit so its snapshot is consumed without
creating a finding. Deliver a returned advisory once to the recipient
responsible for the edit. Do not call the component for unrelated tools,
unsupported extensions, paths outside the current workspace, or changes not
made through the bound native event.

From a documented continuation-capable completion event, call
`check_completion`. Map a returned `block_reason` to native continuation of that
same execution scope and feed the bounded reason back to the responsible agent.
An empty result permits completion silently. A returned `advisory` means the
check was operationally unavailable; it never blocks and must be delivered only
through a documented non-blocking channel. Do not stop repeated guard calls
merely because the native event says a stop hook is already active: the current
files, not a retry counter, determine whether the positive finding remains.

The detector owns one private state file below the system temporary directory
for each adapter namespace, scope, and workspace. It stores only hashes,
counts, paths, line metrics, hashed function identities, notice keys, and
short-lived operation metadata, never source text, function names, transcripts,
prompts, or telemetry. Preserve its atomic replacement,
bounded lock recovery, one-hour pending-operation expiry, seven-day
abandoned-state expiry, workspace confinement, source-size bounds, successful
cleanup, and revalidation before blocking. Scanners run outside the state lock;
unique temporary scanner directories are removed after each call. Do not
replace this with a repository-wide scan or persist it in the receiving project.

Preserve the high-signal detector set: TODO/FIXME/HACK/XXX comments, diagnostic
suppressions, skipped or focused tests, explicit debugger residue, and comments
that depend on temporary phase, plan, step, or discussion context. It must not
warn merely because a normal comment, docstring, `print`, `console.log`, or
structured log was added. Keep comment extraction string-aware and conservative;
an unsupported syntax or unreadable boundary is unavailable protection, not a
finding.

Keep `new-growth-pressure` inside this component because it consumes the same
explicit path and before/after snapshot. Emit it immediately after the
successful edit, never from the completion guard. A hand-authored code file
crosses the review threshold only when it moves from at most 400 lines to more
than 400; a Python function crosses only when it moves from at most 60 lines to
more than 60. Count a new file or function from zero. Exclude SQL, skip function
comparison when either Python snapshot cannot be parsed, and keep already-large
files and functions silent. Bound the advisory and tell the recipient to review
cohesion rather than mechanically split code to satisfy a number. These defaults
are review pressure, not project policy; project-specific generated-file,
complexity, and structural rules remain with the receiving project's own
configuration and tooling.

For Python files, run Ruff in isolated, no-cache, ignore-noqa mode and keep only
`S102`, `S307`, `S506`, `S602`, `S605`, `S501`, and `S324`. Discard Ruff's
explicitly safe shell-call variants. For JavaScript and TypeScript, run Oxlint
with nested configuration and ignores disabled, all unrelated rules allowed,
and only `no-eval`, `no-new-func`, `no-script-url`, and `no-implied-eval`
denied. Supply the canonical read-only `setTimeout`, `setInterval`, and `window`
globals so `no-implied-eval` works without consuming project lint settings.
These findings use the same before/after attribution and completion
revalidation as quality residue; pre-existing findings are not claimed.

Run Semgrep only when a cheap source prefilter finds a candidate for dynamically
constructed child-process execution or disabled HTTPS certificate verification.
Use only the two embedded canonical rules, one job, bounded file, memory, and
time limits, version checks disabled, and metrics off. Semgrep findings are
review advice only and are never persisted as completion blockers.

`ruff`, `oxlint`, and `semgrep` are direct runtime support for this one hook,
not separate hook components. During adaptation, reuse compatible resolved
executables or install their current official distributions through the
target's supported global method. Prove each with a harmless representative
sample and record a precise pending blocker or unsupported limitation when a
required scanner cannot be supplied. A missing, timed-out, malformed, or failed
scanner must leave the action and completion unblocked and emit only its
deduplicated unavailable-check advisory.

## Adapt `fallow-quality`

Keep [fallow-quality.py](fallow-quality.py) as a separate stateless advisory
detector. It complements the per-edit `code-quality` checks with Fallow's
cross-file structural view; it does not share the completion guard, create a
second blocking gate, or own project architecture policy.

Reuse or install a compatible current official Fallow distribution and verify
that its `audit` command supports `--diff-stdin`, `--gate new-only`, JSON output,
an explicit project root, and `--no-cache`. Set `FALLOW_TELEMETRY=off`, the
stronger `FALLOW_TELEMETRY_DISABLED=1` kill switch, and
`FALLOW_UPDATE_CHECK=off` for every invocation. Do not install or invoke
Fallow's own product-hook registration as the MAINFRAME integration, because
its event scope and delivery contract are not equivalent to this component.

At a documented continuation-capable completion event, call `analyze` only
when the current native execution scope changed one of the supported TS/JS
extensions. Supply:

- the normalized current project root;
- only paths positively attributed to that execution scope;
- an in-memory unified diff reconstructed from those exact edits; and
- the subset of paths wholly created or replaced by that scope.

Do not infer scope from the whole dirty worktree, recent timestamps, a process
list, or unrelated session history. Include subagent edits only when the native
product exposes reliable lineage to the same result. If short-lived attribution
state is required, keep it outside the receiving repository, key it by a fixed
adapter namespace plus native session and workspace identities, use atomic
replacement and locking, expire abandoned state, and never retain source or
diff text. Reuse the proven state mechanics of `code-quality` when practical;
do not merge the semantic components or inventory rows.

The detector runs Fallow with the diff on standard input and reports only
findings marked newly introduced that intersect the supplied paths. It reports
an unused file only when the adapter also supplied whole-file ownership. Output
is bounded and asks the recipient to verify findings rather than treating the
analyzer as authoritative.

A normal clean result is silent. Missing Fallow, invalid input, oversized
scope, timeout, nonzero analyzer failure, or unsupported output returns at most
one bounded unavailable-check advisory and never prevents completion. Deliver
advice only through a documented non-blocking channel and deduplicate duplicate
delivery of one native completion event. If exact attribution or non-blocking
completion delivery is unavailable, record this component as `unsupported`;
do not substitute a whole-repository scan or an always-on instruction.

Run the canonical regressions without executing any destructive command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s hooks/tests -p 'test_*.py'
```

After installation, separately verify native event delivery, hard denial, and
any non-blocking advisory with a synthetic command payload or an isolated fake
runner. Never test a destructive guard by targeting a real filesystem, home,
or project root.

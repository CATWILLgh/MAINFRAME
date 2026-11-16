# Canonical hooks

Hooks are deterministic event reactions that cannot be represented reliably by
instructions alone. This file owns their exact semantic catalog, trigger and
failure contracts, attribution, dependencies, and representative cases. The
cross-product installation method lives in the
[hook component guide](../docs/installation/components/hooks.md).

The files in this directory define product-agnostic behavior; globally installed
adapter copies supply native event names, payload and output encoding, paths,
timeouts, registration, and permissions.

Automatic project checks must work after supported adapter installation and
native activation, without additional consumer-project setup or agent invocation.
Select applicable checks from the native event, addressed files and unambiguous
existing metadata. Do not require project-specific configuration, custom test/CI
integration, database endpoints or new services. Prepare required tool dependencies
through the maintained installer, not in the consuming project or on each event.
Keep inapplicable checks silent. Where the available evidence cannot establish a
runtime guarantee, state the coverage limit rather than presenting a project
integration proposal as an automatic MAINFRAME capability. Skills may guide
project engineering; that method is distinct from an installed automatic check.

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
A guard blocks only a positively recognized dangerous condition or explicitly
documented forbidden command form. Missing input,
timeouts, unavailable dependencies, parser limits, and detector exceptions are
not dangerous findings and must not create a hard lock. Represent a
decision-relevant protection failure as a distinct non-blocking advisory rule;
otherwise fail silently. Test both semantic findings and operational failures
during adaptation.

An explicitly disabled hook produces no finding, state, injected context, or
completion continuation. Its adapter must tolerate late callbacks and launch
failures under the [hook component guide](../docs/installation/components/hooks.md#preserve-failure-behavior);
removing a registered executable is not a disable mechanism.

| Hook | Class | Trigger and result | State |
| --- | --- | --- | --- |
| `mainframe-todo-limits` | `guard` | Before a supported addressed file edit, reject a changed idea-index row over 500 characters, a note over 5000 characters, malformed record structure/link, or missing rejection reason | Stateless; only addressed content and its index/link dependencies |
| `mainframe-destructive-operations` | `guard` | Before a shell action, hard-block a recognized catastrophic filesystem deletion or a narrow Git operation that bypasses recovery and safety mechanisms | Stateless |
| `mainframe-secret-access` | `guard` | Before a shell action, hard-block direct credential output or value-bearing registration through the `mainframe-secret` helper and point to its protected route | Stateless |
| `mainframe-rg-short-replace` | `advisory` | Before a shell action, warn when an actual ripgrep invocation uses short `-r`, which selects output replacement rather than recursion | Stateless; adapter deduplicates duplicate delivery of one native event |
| `mainframe-commit-secrets` | `guard` plus unavailable-check `advisory` | Before an agent-initiated `git commit`, block newly introduced high-confidence secret material; warn without blocking when the prospective commit cannot be inspected | Stateless |
| `mainframe-commit-checkpoint` | `advisory` | After a successful native edit, remind the responsible agent to checkpoint a coherent verified part when editing has accumulated | Expiring hashes, counters and timestamps only |
| `mainframe-code-quality` | Post-edit quality, security, and structure advisories plus an attributed-finding completion guard | Around a successful file edit, report new high-confidence residue, security findings, or a size-review threshold crossing; before completion, revalidate and block only attributed blocking findings | One private temporary JSON file per adapter namespace, native execution scope, and workspace |
| `mainframe-fallow-quality` | `advisory` | At a continuation-capable completion event after exact-scope TS/JS edits, report newly introduced structural findings or a decision-relevant unavailable check without blocking | Canonical detector is stateless; adapter may retain only bounded short-lived attribution state |
| `mainframe-skill-reminder` | `advisory` | At a recognized operation, read or specialized role start, suggest one relevant readable skill without changing task authority | Expiring recipient/workspace hashes and skill identities; bounded suggestion count |
| `mainframe-subagent-selection` | `guard` | Before native subagent creation with selectable model and reasoning effort, reject omitted or implicit choices | Stateless |

## Adapt `mainframe-todo-limits`

The command [todo](../commands/todo.md) owns the record format. Normalize a
supported native edit into `check_write(workspace, path, content)`,
`check_edit(workspace, path, old, new, replace_all=False)`, or
`check_patch(workspace, patch)`. A returned string is a preventive denial;
`None` is neutral. No raw record content is returned, written or retained.
If native Edit uses an empty old string to create or fill a blank file, pass
the verified native `blank_characters` set to `check_edit`.

Validate only the root `.docs/todo` index's changed entries (including a group
move) and changed `.docs/todos/<name>.md` notes. Inspect their direct link/index
dependencies as needed; never walk all notes. Count Python/Unicode characters,
including whitespace and newlines in the note. The summary excludes its list
prefix and final link. Meaning, factual completion and semantic duplicates
remain agent judgments. This check does not authorize execution of an idea.

Reject only positively reconstructed violations. Unresolved workspace, unsafe
path/symlink, unreadable or oversized input, ambiguous replacement or unsupported
patch syntax is unavailable evidence and stays neutral. Supported patch forms
are Add/Update/Delete with unambiguous context hunks; moves and shell writes are
outside this preventive binding. A complete supplied note over the limit is a
known violation even when it exceeds the bounded file-read size. A clean call
has no state or output. Native adapters preserve deliberate disables and use
their ordinary safe launcher lifecycle. Other products retain this hook pending
adaptation rather than claiming protection from command delivery alone.

## Adapt `mainframe-subagent-selection`

This stateless `guard` requires explicit model and reasoning-effort choices
before creating a subagent when the native interface supports both controls.
Missing, blank, non-string or implicit `inherit`/`default`/`auto` selections are
denied with a short instruction to choose according to complexity, importance,
error cost and budget. Valid explicit choices are silent. Native model catalogs
and validation own availability and supported combinations; the hook does not
judge whether a selected model is sufficiently capable.

The adapter must positively identify subagent creation and normalize its actual
argument fields. A recognized empty argument object is a violation; an absent
or unreadable event is unavailable evidence, not a violation. Keep unsupported
selection interfaces pending adaptation; do not block all delegation merely
because a product cannot expose these fields. Disable and uninstall must stay
silent, including late callbacks. No state, logs, network or external tools are
needed. Product-specific history-fork constraints belong to the adapter.

Codex Desktop 0.163.0-alpha.11 has a verified preventive binding. Other product
bindings await separately scoped validation; this is not proof they cannot
support the hook. See [Codex evidence](../docs/installation/native/codex.md#explicit-subagent-selection).

## Adapt `mainframe-destructive-operations`

Copy `mainframe-destructive-operations.py` unchanged when the product can call a Python
detector from its native hook. Keep any required payload/output wrapper in the
installed adapter, not in the canonical file. Pass the exact shell command,
tool working directory, active project root, and current user's home root to
`decision_reason`.

When a product exposes the exact command and a pre-action denial but does not
expose the shell tool's actual working directory, call
`context_free_decision_reason` as an explicit degraded binding. It preserves
only command-structural Git decisions, filesystem/home-root targets, and the
fixed directory-change plus relative-recursive-delete form. Keep the inventory
row unsupported for the missing project-root and ordinary-relative-target
guarantees; never pass a session or workspace cwd as if it were the tool cwd.

A returned reason must become a documented native hard denial for the action.
`None` means no decision: emit nothing and leave the product's native permission
layer authoritative. Never convert `None` into an allow decision. If the
product cannot intercept and deny a shell action before execution, mark the
component `unsupported`; an instruction, reminder, or after-action message is
not equivalent.

The filesystem check blocks recursive deletion of the filesystem root, current
user's home root, or active project root. It also blocks a relative recursive
deletion after an earlier directory-changing command when the effective target
cannot be determined without emulating the shell. That combination is a fixed
forbidden command form; it does not assert that an unknown target is a root.
Carry that directory
uncertainty into supported nested shells, but inspect the actual command and
target: nonrecursive deletion, quoted examples, and absolute narrower targets
do not become catastrophic merely because a prior command changed directory.

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

## Adapt `mainframe-secret-access`

Call `decision_reason` immediately before a shell action with the exact command.
A returned reason must become a documented native hard denial. `None` emits
nothing and leaves the product's native permission layer authoritative. A
missing or malformed command and detector failure are unavailable protection,
not reasons to deny the action.

The detector blocks only two direct helper mistakes: standalone `mainframe-secret get
NAME`, which would print the value into agent context, and `mainframe-secret set NAME
VALUE`, which would place the value in command arguments. It allows `mainframe-secret set
NAME --clipboard`, the protected `--prompt` fallback, `mainframe-secret copy NAME`,
`mainframe-secret run NAME -- COMMAND`, and a nested `mainframe-secret get` used only inside its
consumer invocation. Its denial never quotes the credential name or value.
For a direct `set`, a following unquoted shell control operator ends that
invocation; the next command is not a positional credential value. Quoted or
escaped operator literals remain arguments, and an actual extra value still
causes a denial. Keep the standalone `get` boundary unchanged.

Keep the detector stateless and silent on allowed actions. It is deliberately
not a shell parser, authorization mechanism, or credential sandbox. Protect
direct reads and searches of the installed store through the product's native
filesystem permissions when available, and report the exact enforcement gap
when no such boundary exists. If the product cannot deny a recognized command
before execution, mark this hook `unsupported` instead of replacing it with a
warning.

## Adapt `mainframe-rg-short-replace`

Before registration, inspect the installed ripgrep help and confirm that short
`-r` takes replacement text while recursion is already the default. If the
installed executable has demonstrably different semantics, mark the component
`unsupported`. If the executable or its semantics cannot yet be identified,
leave it `pending` with the missing evidence rather than guessing from another
search tool.

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

## Adapt `mainframe-commit-secrets`

Call `check_command` immediately before a shell action with the exact command
and native working directory. A non-empty `block_reason` is a hard denial. A
non-empty `advisory` is non-blocking context for the recipient responsible for
the next action. An empty result emits nothing. Never turn an advisory or a
detector exception into a denial.

When the same pre-action event omits the shell tool's actual working directory,
`check_context_free_metadata` is the safe degraded binding. It inspects literal
commit metadata and absolute commit-message files only. It deliberately emits
no unavailable advisory and does not claim staged, worktree, or relative-file
coverage. Keep the full inventory row unsupported and name those missing
guarantees.

The detector activates only for an agent-initiated `git commit`. It examines
new high-confidence credential shapes in the effective index, supported
auto-staged or path-selected worktree content, literal commit metadata, and
binary blobs. It compares prospective content with the base tree so removed
values, pre-existing values, and unchanged renames do not create a finding.
Partial staging remains isolated from unrelated dirty worktree content.
Preserve option-value boundaries: `-mupdate` supplies a message, `-Fmessage.txt`
supplies a metadata file, and `-amupdate` additionally selects auto-staging.
Letters inside an attached value must never change the prospective commit scope.

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

## Adapt `mainframe-code-quality`

Treat `mainframe-code-quality.py` as one component with these fixed effects:

- a post-edit advisory for newly introduced high-confidence quality residue;
- a post-edit advisory for newly introduced high-confidence Ruff or Oxlint
  security findings;
- a post-edit advisory for newly introduced blocking calls in Python async code;
- a post-edit advisory for newly introduced swallowed exceptions, unsafe control
  flow in `finally`, and async Promise executors;
- a post-edit advisory for newly introduced assertions that can pass without
  testing their intended behavior, and Python background tasks without a
  retained reference;
- a post-edit advisory for new syntax errors or duplicate configuration keys
  in the supported formats, starting with file creation;
- a post-edit advisory for new composition-unsafe Enter actions, premature form
  error styling, and missing integrity/CORS on supported external resources;
- a post-edit advisory for newly introduced errors in shell scripts, GitHub
  Actions workflows, Kubernetes workloads, or recognized PostgreSQL migrations;
- a post-edit advisory for Go code that discards rows or a connection from
  `pgxpool` in a recognized pattern;
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
`succeeded=False` when a native failed-edit callback is available so its snapshot
is consumed without creating a finding. When the product emits no failed-edit
callback, retain the unmatched snapshot until its bounded expiry. Never invent
success or failure, consume it for another operation, or discard it at completion.
Prove that a later successful edit is still attributed independently and that
the unmatched snapshot alone cannot block completion. Deliver a returned
advisory once to the recipient responsible for the edit. Do not call the component for unrelated tools,
unsupported extensions, paths outside the current workspace, or changes not
made through the bound native event.

Deduplicate native pre/post event redelivery. Preserve the first
before snapshot for an operation and consume it through its matching success or
failure event only once; a missing snapshot is unavailable attribution, not
proof of a clean edit. A completion callback must not discard another in-flight
operation's snapshot in the same scope. It can report unavailable attribution
without blocking, while the matching post event or bounded expiry retains
ownership of that snapshot.

From a documented continuation-capable completion event, call
`check_completion`. Map a returned `block_reason` to native continuation of that
same execution scope and feed the bounded reason back to the responsible agent.
An empty result permits completion silently. A returned `advisory` means the
check was operationally unavailable; it never blocks and must be delivered only
through a documented non-blocking channel. Bound automatic repair to one
continuation per completion attempt. On an already-active Stop callback,
preserve unresolved findings without requesting another continuation. Use a
non-blocking unresolved message only where the native event supports it. A later
ordinary completion attempt revalidates the current files before blocking.

The detector owns one private state file below the system temporary directory
for each adapter namespace, scope, and workspace. It stores only hashes,
counts, paths, line metrics, hashed function identities, notice keys, and
short-lived operation metadata, never source text, function names, transcripts,
prompts, or telemetry. Preserve its atomic replacement,
bounded lock recovery, one-hour pending-operation expiry, at most 512 recent
completed-operation receipts plus the current receipt, seven-day
abandoned-state expiry, workspace confinement, source-size bounds, successful
cleanup, and revalidation before blocking. Scanners run outside the state lock;
unique temporary scanner directories are removed after each call. Do not
replace this with a repository-wide scan or persist it in the receiving project.
Expiry must also apply when the abandoned scope itself resumes; cleanup by
another scope is not a prerequisite.

Share a five-second external-scanner budget across the addressed files in each
capture, post-edit check, or completion check. Exhaustion produces deduplicated
unavailable-check advice. Bound regular-file reads before scanning and reject
nonregular inputs without waiting for a writer. Bound each finding row to 240
characters, preserving its path prefix and diagnostic suffix. Compact combined
quality advice to 480 characters, reserving evidence for each subsection before
omitting extra rows and explanatory footers. Native adapters own the combined
event-message and serialized-output limits.

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

For Python files, run Ruff in isolated, no-cache, ignore-noqa mode. Keep security
rules `S102`, `S307`, `S506`, `S602`, `S605`, `S501`, and `S324`. Discard Ruff's
explicitly safe shell-call variants. The same before/after invocation also checks
`ASYNC210`, `ASYNC212`, `ASYNC221`, `ASYNC230`, and `ASYNC251` for blocking
calls, and `S110` and `B012` for suppressed exceptions.
Also select `F631` for truthy tuple assertions, `PT012` for multi-statement
`pytest.raises` blocks, and `RUF006` for discarded `asyncio` task references.

For JavaScript and TypeScript, run Oxlint with nested configuration and ignores
disabled. Apply the TypeScript checks to `.ts`, `.tsx`, `.mts`, and `.cts`.
Select `no-eval`, `no-new-func`, `no-script-url`, and `no-implied-eval`
for security and `no-unsafe-finally` and `no-async-promise-executor` for review.
Supply the canonical read-only `setTimeout`, `setInterval`, and `window` globals
so `no-implied-eval` works without consuming project lint settings.
In `*.test.*`, `*.spec.*`, and `__tests__/` sources, use Oxlint's
`vitest/valid-expect` rule for the async assertion syntax shared by Jest
and Vitest. Report only unawaited assertions whose result is clearly
discarded. The pinned analyzer also flags some valid code, such as an
assertion that is saved and awaited later.

Report Python and JavaScript/TypeScript parser diagnostics from the existing
Ruff and Oxlint invocations. A failed parse cannot confirm that an existing
security finding was removed. Keep its attribution until a successful scan
can revalidate it.

Both scanners include the review rules on the first supported edit, including
new files, without project configuration. Report only newly introduced
findings. Completion revalidation keeps the security rules and leaves the
correctness rules advisory.

Run Semgrep only on candidate files. JavaScript and TypeScript retain their
embedded checks for dynamic child-process execution and disabled TLS
verification. For an edited `.go` file containing the pgx v5 pool import and a
candidate discard, check explicit discarded results from `Query` or
`Acquire` on a recognizable pool. The Go scan uses Semgrep's native
CLI, a one-second deadline, and the before/after file snapshots. Its scope is
the explicit discard patterns in that file. It does not trace a result through
other files or prove that every exit from a function closes it.

Semgrep runs the selected embedded rules locally with one job, bounded file
and memory limits, disposable settings, version checks disabled, and metrics
off. Findings are review advice and stay outside completion revalidation.

Run the file-specific analyzers against the exact before and after source text
in an isolated temporary directory. Bound each invocation to one second.
Use static diagnostic descriptions and compare only new findings. See
[the tested runtime versions](../installer/runtime.py) and
[the executable tests](tests/test_code_quality.py).

| Tool | Automatic scope | Reported findings |
| --- | --- | --- |
| `gofmt` and `dart format` | `.go` and `.dart` with the corresponding local SDK executable on `PATH`. Use the existing Dart SDK bundled with Flutter when present. | Syntax errors. Invoke the parser on the snapshot without formatting the project file or fetching dependencies. |
| `rustfmt` | `.rs` with the formatter on `PATH` or in a local rustup toolchain. | Syntax errors from stdin using the owning Cargo edition, including workspace inheritance. Standalone files use Edition 2024. The hook does not run Cargo, expand macros, or apply formatting. |
| Python standard library | `.json`, `.jsonc`, and `.toml`. Accept JSON comments and trailing commas in `.jsonc`, TypeScript and JavaScript config names, `devcontainer.json`, and files in `.vscode/`. | Syntax errors and duplicate keys. JSON reports the file when a duplicate has no parser position. TOML reports the first parser diagnostic using the hook's Python version. |
| yamllint | `.yml` and `.yaml`. Skip Helm template sources and honor yamllint's inline directives. | YAML syntax errors and repeated keys in the same mapping. YAML syntax and key review runs alongside workflow and Kubernetes checks. |
| ShellCheck | `.sh` and `.bash` with a supported interpreter or no shebang. | Shell parse errors, masked command failure, unchecked `cd`, and a pipeline that reads and writes the same file. |
| actionlint | `.github/workflows/*.yml` and `.github/workflows/*.yaml` at the repository root. | Workflow YAML or schema errors, missing or cyclic job dependencies, and invalid identifiers, expressions, conditions, or matrices. |
| KubeLinter | Plain Kubernetes deployment, stateful set, and daemon set YAML with a container specification. Skip Helm templates and recognized Kustomize overlays and patches. | A workload selector that does not match its pod template, or a container without a readiness probe. Check service selectors and routes against the rendered manifest set. |
| Squawk | Versioned `.sql` migrations under a PostgreSQL Prisma lock, PostgreSQL Drizzle journal, or the embedded CSS migration layout. | Destructive drops, cascading truncation, type changes, ordinary index creation/removal/rebuilding, overlong SQL identifiers, SQL parser diagnostics, immediate constraint validation, required columns, rewrite-prone defaults, rolling-deployment renames, missing lock timeouts, and concurrent index operations inside an explicit SQL transaction. |
| Modern web rules | `.html`, `.htm`, `.css`, JS/TS module extensions, JSX/TSX, Vue and Svelte. Use isolated snapshots, Modern Web Guidance's AST/DOM/CSS parser APIs, and the official Svelte compiler for Svelte templates. | Maintained `ime-safe-enter-submit`, `validate-input-after-interaction`, and `secure-external-subresources` rules. |

These migration findings are advisory, attributed to the current edit, and
deduplicated against its before snapshot. Connection-setting advice follows
specific schema risks so a truncated message retains the actionable operation.
Squawk recognizes file-level timeout declarations. Actual connection settings,
runner-owned transactions, server/version restrictions, data volume, and progress
under contention require the normal-runner engine checks in the shared
[migration method](../skills/mainframe-testing/references/migrations.md).

Index rebuild advice requires review of the actual target/version, constraints
and runner before choosing `CONCURRENTLY`; it is not an automatic rewrite.
Identifier advice concerns SQL names generally, including index names, and the
default 63-byte PostgreSQL limit. Preserve upstream inline ignores. SQL parse
diagnostics identify the first parser error only: a parser/server syntax mismatch
is possible, so do not claim the live database rejected the statement. Actual
analyzer failure remains a distinct unavailable check. These rules share the
existing Squawk invocation per snapshot, attribution, combined message and limits.
They do not connect to a database or prove index readiness, application use or
performance.
The existing [quality tests](tests/test_code_quality.py) cover first-edit advice,
safe forms, byte boundaries, repetition/repair, dialect exclusion and failures;
the [runtime probes](../installer/runtime_checks.py) require the new diagnostics
and clean counterparts before reusing a newer analyzer. Run the quality tests
locally with the prepared runtime; CI prepares dependencies and runs the full
hook suite. Native delivery and live database behavior remain separate evidence.

Modern Web Guidance runs only for candidate syntax in an addressed web file.
Skip generated/vendor/build paths, minified bundles, and recognized JS test
files. The scanner receives one temporary snapshot, with telemetry and file
logging disabled and no project configuration. Limit its input to 128 KB and
2000 characters per line, and read at most 2 MB of JSON from a private temporary
stdout file. Keep all child temporary files inside the snapshot directory so
the parent removes them after failure or timeout.
Finish established checks for every path before adding web advice from the
same source revision. All web subprocesses together have at most one second
within the unchanged shared scan budget. Include upstream-supported tagged
`css` templates in JS/TS files. Keep output in the ordinary combined advisory. A reached
bound or unavailable scanner emits one deduplicated availability notice.
Preserve relevant exclusions for composition guards, modifier shortcuts,
post-interaction styles, intentional support fallbacks, and mutable CDN URLs.
Return only fixed rule labels and validated source locations. Keep these
findings advisory and preserve existing completion guards if web review fails.
The hook supplies its own narrow rules through the prepared parser API. Check
every supported static external resource, require a same-event composition
guard before a reachable Enter action, exclude non-text controls, and evaluate
validation timing per CSS rule. Resolve local callbacks, simple selectors and
framework bindings; leave imported callbacks, complex/dynamic targets and cross-function data flow outside
static coverage. Reached unsupported control flow or an exhausted AST budget
reports unavailable. Version the web channel when semantics change so old
snapshots cannot attribute inherited findings to a new edit. A clean static
result does not replace affected browser interaction checks.
Broader modernization uses the [frontend method](../skills/mainframe-frontend/references/modern-web.md).

The code-quality hook uses its existing edit events and configured analyzer
runtime paths. Use the shared runtime's
[compatibility and provisioning policy](../docs/installation/components/hooks.md#runtime-support).
A missing, timed-out, malformed, or failed scanner must leave the action and
completion unblocked and emit only its deduplicated unavailable-check advisory.

## Adapt `mainframe-fallow-quality`

Keep [mainframe-fallow-quality.py](mainframe-fallow-quality.py) as a separate stateless advisory
detector. It complements the per-edit `mainframe-code-quality` checks with Fallow's
cross-file structural view; it does not share the completion guard, create a
second blocking gate, or own project architecture policy.

Reuse Fallow under the shared runtime compatibility policy and verify
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
diff text. Reuse the proven state mechanics of `mainframe-code-quality` when practical;
do not merge the semantic components or inventory rows.

The detector runs Fallow with the diff on standard input and reports
newly introduced findings that intersect the supplied paths. It reports
an unused file only when the adapter also supplied whole-file ownership. Mark
verified file creation with a `/dev/null` before path. If Fallow cannot resolve
`HEAD`, use `health --complexity` for a single verified new file within the
same timeout. This mode reports measured complexity. Import graphs and clone
comparisons use the ordinary audit once a Git baseline exists. Output
is limited to six rows of at most 240 displayed characters plus a truncation
suffix per row, with control characters neutralized, and asks the recipient to
verify findings rather than treating the analyzer as authoritative. Validate
the audit envelope, finding-list shapes, and Boolean `introduced` attribution;
an unsupported analyzer shape is an unavailable check, not a clean result.

A normal clean result is silent. Missing Fallow, invalid input, oversized
scope, timeout, nonzero analyzer failure, or unsupported output returns at most
one bounded unavailable-check advisory and never prevents completion. Deliver
advice only through a documented non-blocking channel. Deduplicate native event
redelivery and repeated generic unavailable-check advice within the same
recipient/workspace scope. A recovery can make a later failure actionable
again. Newly introduced findings in a separate edit remain independently
reportable. If exact attribution or non-blocking
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

## Adapt `mainframe-commit-checkpoint`

Call `observe(scope, workspace, event_id, changed_lines, state_root=...)` only
after a successful native edit with a stable recipient/session identity, a
stable native operation ID, and an unambiguous Git workspace. Never substitute
completion, elapsed time alone, transcript volume, or guessed shell side effects
for edit evidence. Estimate touched text volume from supported edit payloads;
this counts editing effort, not unique net lines or completed logical units.
`text_lines` counts text without retaining it. Do not read protected stores,
untracked file bodies or bulk source diffs to fill gaps in native input.

The default thresholds are 25 successful edit operations or 2000 estimated
touched lines since the observed HEAD or previous reminder. Emit a short native
advisory only after crossing a threshold and confirming uncommitted Git changes
through bounded metadata-only status. A clean worktree resets accumulation. Reset counters when Git HEAD changes,
including the first commit; deduplicate callbacks atomically, isolate scopes and
repositories, and allow another reminder only after fresh threshold crossing
and at least 10 minutes. Counters saturate; state has a six-hour TTL and bounded
scope/event capacity; expired rows are pruned on a subsequent observation,
without a background process. Retain no raw IDs, paths, commands or source text.

The reminder cannot establish that work is finished or that a diff belongs to
the agent. It directs the agent to select and verify a coherent owned part,
follow existing local-commit authority, preserve unrelated staging and avoid
pushing. Canonical local-commit authority belongs to
[instructions/global.md](../instructions/global.md), not to this detector.
Do not turn a reminder into a quota, automatic `git add`, commit-message lint,
permission denial or a mandatory new approval step.

Codex and ZCode deliver the advice through `PostToolUse` model context.
Unsupported or ambiguous edit forms remain silent.
Keep this hook independent of code-quality disablement. Never force a Stop continuation for checkpoint
advice. Missing Git, missing IDs, unavailable/unsafe state, unknown outcomes,
failed edits, non-Git workspaces and runtime exceptions fail silently.

Coverage is limited to supported native edit events. Changes made by arbitrary
shell commands, external editors, or unexposed subagent tools are not counted;
this hook does not claim to intercept all ways a repository can change. The
agent's semantic checkpoint rule still applies to those workflows. Installation
copies the canonical detector and native binding; source/fixture tests do not
prove a live app has trusted or activated it.

## Adapt `mainframe-skill-reminder`

This advisory suggests a readable relevant method at a recognized work boundary. The canonical
parser extracts bounded literal file/directory targets and conservative skill
candidates without IO or execution. The adapter owns workspace context, catalog
and policy, native events and recipient-scoped state. It must never execute shell
text, infer permissions, block a tool, force a continuation or inject file content
or skill descriptions as instructions.

On Codex use `PreToolUse` Bash for explicit operation advice, `PostToolUse`
Bash for read-related advice, and `SubagentStart` for exact specialized native
roles. Only the role event supplies advice before the child starts work. A
pre-tool callback does not prove that the model reconsidered its first submitted
operation. Reject a known failed read outcome; raw output may leave success unknown.
Require a session identity and tool-operation identity for tool events, and a
child identity for role-start events; distinguish child `agent_id` from root. Literal absolute targets remain useful without a workdir. For relative
reads, a unique explicit literal workdir from bounded recent native transcript
arguments can supply an advisory hint, not exact operation attribution. Unknown,
dynamic, conflicting or nonlocal execution contexts stay silent. Never treat
session cwd as shell cwd by default. The bounded hint parser reads only the native
transcript tail in memory, retains no source/commands/output and fails silently
on format changes. This approximation must not be reused for blocking guards.

Use readable native skills and explicit invocation policy; an on-disk skill is
not proof that the budgeted native catalog displayed it. Include its canonical
path so the recipient can read it. Respect disabled skills and user-only commands. Existing unreadable or complex
invocation-policy metadata stays silent; the bounded fallback accepts only a
simple explicit opt-in mapping, rather than guessing YAML semantics.
A uniquely identified project engineering skill must be bound by project guidance.
Testing routes to the implementation method, not automatically to test audit.
React candidates need package and application-entry evidence; standalone
component libraries and React Native stay silent. Source profiles use bounded
reads of relevant non-secret source and nearest package metadata. At most eight
targets are profiled; symlinks, fixtures, generated files and obvious credential
files stay silent. Do not infer a backend from a language extension alone. Unknown domains remain governed by ordinary proactive selection.

Send one brief conditional suggestion. Deduplicate by session, recipient,
workspace and skill or operation, with at most three suggestions per scope and
seven-day expiry. Explicit PostgreSQL or K3s backup commands get one lifecycle
note. Named Argo CD release commands and explicit scaling of a workload to zero
share one continuity note per scope. A named OpenSpec apply instruction request
gets one note on challenging material risks, acceptance evidence, and live-operation authority. These fixed notes point to a readable
method and remain useful after an explicit skill read. An explicit read attempt
suppresses the generic skill suggestion and establishes awareness only. Raw
output cannot prove read success; never parse content as a status envelope. Bounded private state contains hashes and skill identities,
fixed operation keys, and expiry, never source or raw native IDs. Disable/missing identity/state failures are silent;
a cached launcher must remain harmless after files are retired. Native receipt
and useful application require separate observations from a successful callback.

The maintained adapters deliver this advisory in Codex and ZCode. Native
timing, identity and missing role-start advice are
listed in the [native binding table](skill-reminder-routing.md#native-bindings).
File delivery is not proof of native activation or useful skill application.

Implemented routes, deferred candidates and per-skill counterexamples are
documented in [the routing design](skill-reminder-routing.md). Its status table
distinguishes delivered bindings from ideas that still lack sufficient evidence.

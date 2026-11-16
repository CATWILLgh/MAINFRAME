# Agent-facing content review — 2026-11-16

Reviewed against source revision `5d25568`, in separate batches. This is
repository maintenance evidence, excluded from installed payload by the
[inventory](../ADAPTATION.example.json).

## Coverage and ownership

Read the global instruction, seven roles, nine commands, all 27 skill
entrypoints and all 111 supporting Markdown references, including nested
Dokploy references. Reviewed hook messages, their owning contracts, Codex and
ZCode output/deduplication boundaries, the three reconnaissance scripts,
the infrastructure template, and the credential helper's output contract.
DSH review covered agent-facing clock text, tool schemas, prompt fragments
and read/wait/output limits; it was not an audit of every plugin algorithm.

Commands are independently packaged. Shared repository-only references cannot
replace their runtime safeguards. Sibling testing/logging/HTTP skill resources
remain delivered dependencies. Queue-template duplication is intentional and
checked for equality. No component was merged, removed or renamed; the 59
inventory identities and native registrations remain unchanged.

Global rules and roles were left intact. Their authority, independence and
language specializations do not establish contradictions. Domain references
retain their distinct transaction, recovery, recipient, privacy and local/CI
boundaries. Large plugin implementations and executable hook code are not
automatically model-visible instruction text.

## Size evidence

Counts are Unicode characters in canonical Markdown, including metadata and
links, before native wrappers/path substitutions. They are not token counts
or the amount loaded in every task. Skill bodies and references are conditional.

| Source | Before | After |
| --- | ---: | ---: |
| Global instruction | 8,362 | 8,362 |
| Seven roles | 7,183 | 7,183 |
| 27 skill entrypoints | 114,930 | 114,443 |
| Nine commands | 90,143 | 88,688 |
| 111 references | 339,263 | 340,633 |
| Total | 559,881 | 559,309 |

The three backend entrypoints shrink from 16,362 to 15,384 characters.
References grow to correct concrete safety/accuracy gaps; the net Markdown
reduction is 572 characters. Reduction was not used as a reason to discard
useful domain knowledge or introduce shared loading machinery.

| Synthetic emitted-context case | Before | After |
| --- | ---: | ---: |
| One quality finding | 121 | 84 |
| Mixed quality/security/growth/unavailable advice | 351 | 349, retaining three previously lost decision boundaries |
| Five-row Fallow audit | 517 | 445 |
| Fallow creation advice | 116 | 271, adding missing interpretation guidance |
| Large TypeScript metadata fixture | 34,824 | About 2,800, with explicit omissions |

The recon fixture uses 10,000-character declarations, 200 script names and
invalid config objects. Absolute temporary-path lengths affect its exact totals.

Quality post-edit advice retains its 480-character limit. Native combined
messages retain 1,600-character and 8,192-byte wire limits. Required repair,
verification and non-blocking/no-forced-split guidance precedes findings;
middle elision preserves diagnostic suffixes. Clean/repeated events remain
silent under the existing attribution and deduplication rules.

## Corrections and controlling evidence

- [Quality](../hooks/mainframe-code-quality.py) and
  [Fallow](../hooks/mainframe-fallow-quality.py): preserve interpretation and
  repair instructions through message clipping, including creation fallback
  and long paths. Detectors, finding thresholds and authority are unchanged.
- [Ticket commands](../commands/mainframe-tickets-find.md): remove repeated
  intra-command prose and reconcile campaign storage. Preserve distinct stage
  authority, one-ticket sequencing, independent verification, immutable history,
  persistence and the exact random-duplicate stopping condition.
- [Curl](../skills/mainframe-curl-requests/SKILL.md): separate HTTP failure
  detection from body suppression; the [official manual](https://curl.se/docs/manpage.html#--fail)
  documents the failure limitations and [output controls](https://curl.se/docs/manpage.html#--output).
  LeanREA website inspection now reuses this bounded method.
- [Go discovery](../skills/mainframe-go-backend/references/recon.md): avoid
  implicit toolchain downloads during inspection, following the
  [selection contract](https://go.dev/doc/toolchain#select). LeanREA also
  distinguishes available build/runtime metadata from stripped symbol tables;
  the [linker contract](https://pkg.go.dev/cmd/link) defines `-s`.
- [SQLite inspection](../skills/mainframe-leanrea/references/bundles-and-data.md):
  require a consistent snapshot and preserve required WAL/journals, following
  [SQLite's corruption guidance](https://www.sqlite.org/howtocorrupt.html#_backup_or_restore_while_a_transaction_is_active).
- [TypeScript reconnaissance](../skills/mainframe-typescript-backend/scripts/recon.mjs):
  omit parser excerpts, reject oversized/nonregular input, project typed bounded
  metadata and report omissions. Preserve JSONC and unfamiliar module strings
  as declarations; do not invent compiler validation or execute project code.

Current primary-source checks targeted material uncertainties. For example,
ClickHouse's unusual readonly/backup/restore warning was
[confirmed](https://clickhouse.com/docs/concepts/features/configuration/settings/permissions-for-queries)
and preserved. Every external link/release fact was not freshly revalidated.

## Verification and limits

Focused red/green was observed for mixed quality advice, clipped completion
guidance, Fallow interpretation/locations and TypeScript output. The
[native context tests](../tests/test_hook_context.py) exercise actual detector
text through both maintained encoders; the
[recon tests](../tests/test_typescript_recon.py) run the script through Node
with synthetic files and verify that project files/code remain untouched.
Existing reminder, event-deduplication, output-budget and lifecycle checks pass.

Reproduce the source/delivery checks with:

```sh
python3 -B -m unittest discover -s tests -p test_repository.py
PYTHONPATH=tests python3 -B -m unittest test_delivery_parity test_hook_context test_typescript_recon
git diff --check
```

The complete quality owner now passes locally: **81 tests, zero failures** in
7.893 seconds with the pinned analyzers prepared in a task-owned temporary home.
No assertions, expected findings, or test membership were changed. The earlier
39 failures were prerequisite failures, broken down as follows:

| Cause | Failed subcases |
| --- | ---: |
| Squawk absent | 29 |
| yamllint absent | 4 |
| actionlint absent | 1 |
| KubeLinter absent | 1 |
| ShellCheck absent | 1 |
| Semgrep CA-store startup failure | 3 |

Semgrep's existing trusted CA bundle was passed through process-scoped
`SSL_CERT_FILE`; TLS verification remained enabled. The contributor
[setup/preflight route](../CONTRIBUTING.md#run-the-quality-analyzer-contracts)
now distinguishes unavailable prerequisites from failed behavior assertions.
The complete shell route was checked with missing analyzers, missing SDK tools,
and a reused prepared home; refusals occurred before assertions and the prepared
route passed all 81 tests.
Fallow's real-analyzer creation case and the other analyzer suites remain
separate checks. Hosted CI for these commits was not run.

The Python skill validator lacked PyYAML. Existing Ruby safely parsed the four
changed entrypoint frontmatters and checked name/description constraints;
repository links/inventory and complete Codex/ZCode delivery parity passed.
Test dependencies were prepared only in the isolated test home; no global
installation, product-native acceptance probes, publication or live-system
actions were performed. Source and synthetic checks do not establish native
activation or equal task performance across models.

## Ordinary installation follow-up — 2026-11-17

Full Codex and ZCode `apply` already prepares required analyzers and OpenSpec
before changing product files or registrations. Four normal-entrypoint tests
cover dependency selection and refusal before activation when preparation fails.
The [runtime support contract](installation/components/hooks.md#runtime-support)
now also defines staged preparation, explicit allocation ownership, preservation
of edited launchers, and retryable pending retirement in the existing receipt.
Dependency code and this report add no agent-facing prompt material.

All **77 runtime lifecycle tests** passed locally through `python3 -B -m unittest
discover -s tests -p 'test_runtime*.py'`. They cover native/Python/Node/OpenSpec preparation, failed and
interrupted activation, alias/symlink/concurrent-edit preservation, retirement
retry and real pip wheel/source-build cases. Synthetic destination settings
exposed pip writes outside its stage; a timed-out source build exposed ambient
temporary files. Both are now contained. Independent review also found lost
retirement provenance after a deletion error; durable pending receipts repaired
that case. The separate reviewer reran five decisive/neighbor checks and found
no remaining material objection in the changed paths.

Real public yamllint 1.38.0 and Oxlint 1.67.0 preparation succeeded in a disposable
home. Repeat `ensure` left bindings and metadata unchanged. A final Oxlint run
also preserved ambient cache, log, temporary and configuration paths. All smoke
homes and the approximately 138 MiB analyzer-test home were removed. The 81 quality tests passed
again with no assertion or membership changes. Semgrep also started normally
outside the test sandbox without a CA override; no persistent certificate
setting was added to adapter installation.

Shared runtime and unproven legacy directories remain intentionally preserved.
A hard stop before a stage is recorded may leave an unregistered directory;
there is no automatic name-based sweep. Native application/authenticated-index
acceptance and hosted CI were not run; the user's global installation was not
updated.

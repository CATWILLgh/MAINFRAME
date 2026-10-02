# GitHub Actions verification

Read the existing workflow, scripts, supported runner/toolchain versions, branch rulesets and required check names before editing. Inspect the applicable GitHub.com or GHES documentation for features that may differ by installation. Do not change protection settings, publish, deploy or start paid/external runs without authority.

## Event and gate behavior

Use PR checks for change validation and the project's intended default-branch/tag/schedule routes for their actual purposes. Add `merge_group` when a GitHub merge queue needs these checks; a PR-only workflow does not establish queue acceptance. Determine which head or merge revision was tested rather than treating all green runs for a branch as equivalent.

A workflow skipped by branch/path filters can leave a required check pending, while a job skipped by its own condition can appear successful. A failed prerequisite can also prevent dependent jobs from running. A stable required gate must run despite failed dependencies, inspect each required job's actual result, and distinguish justified non-applicability from missing, failed or canceled coverage. Verify its `needs`/condition behavior and configured check identity; do not use unconditional green steps as an aggregate verdict.

Keep required names stable and unambiguous across workflows. Confirm the exact latest revision/event with the repository's active ruleset; a manual run is not a substitute for proving all required PR or workflow rules. Observe the server-side settings when available and report the limit when they cannot be inspected.

Sources: [Required-check behavior](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks), [merge queues](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).

## Trust and reproducibility

Use minimal `permissions` and separate privileged publication from untrusted change tests. Fork PR contexts and private-repository settings differ. Never check out and execute untrusted PR code with privileged `pull_request_target` or `workflow_run` credentials. Treat artifacts from untrusted producers as untrusted even when retrieved by a trusted workflow. Persistent self-hosted runners require an established isolation boundary before accepting untrusted jobs.

Resolve action and reusable-workflow references from their owning repositories. Prefer verified full commit SHAs with a human-readable version annotation and an update mechanism, not invented pins or forgotten frozen dependencies. Put untrusted event values into quoted environment variables or structured arguments rather than shell source. Scope OIDC and environment permissions to the intended job and identity; neither capability authorizes deployment on its own.

Source: [Secure use](https://docs.github.com/en/actions/reference/security/secure-use).

## Cost and failure diagnostics

Scope concurrency by workflow and the actual branch/PR purpose; cancel obsolete validation safely without canceling unrelated or irreversible work. A matrix multiplies job setup and runner cost. Set bounded parallelism and choose fail-fast according to the evidence needed; avoid `continue-on-error` on required combinations.

Cache only regenerable dependencies with suitable OS/toolchain/lockfile and trust boundaries. A cache miss must succeed; a cache hit must not skip tests. Pass build outputs and reports through named artifacts associated with their producer/revision. Retain bounded failure logs and reports when jobs fail, without secrets. Artifacts from a successful different revision are not acceptance evidence.

Validate YAML and action expressions with available tooling, inspect referenced scripts, and verify the event/job graph. Only an authorized hosted run establishes actual runner behavior, result reporting and artifacts. Preserve failed-attempt evidence when retrying a transient failure.

Sources: [Concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency), [matrix strategy](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstrategy), [caching](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching), [reruns](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).

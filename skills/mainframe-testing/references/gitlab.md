# GitLab CI verification

Inspect the project's GitLab version/edition, runner executor, included configurations, current `workflow`/job `rules`, protected resources and merge checks before changing the pipeline. Resolve the merged configuration and preserve version-compatible syntax. GitLab.com documentation does not establish feature availability on an older self-managed instance.

## Choose the pipeline that proves the claim

Design `workflow: rules` and job rules together so merge requests receive their required checks without duplicate equivalent branch pipelines. An ordinary MR pipeline checks source-branch content; merged-results pipelines and merge trains establish different integration claims. Verify required feature settings and edition availability before relying on them. Ensure MR-enabling rules exist at the documented root configuration boundary, rather than assuming a conditional include enables everything.

Inspect which pipeline GitLab uses for merge acceptance. Do not assume a newer branch failure necessarily overrides an older successful MR pipeline. Check `Pipelines must succeed` and skipped-pipeline settings; pipeline absence, skipped work, and passing required tests are distinct. Manual jobs and `allow_failure` have context-dependent defaults, including differences inside `rules`; required verification must not become optional by accident.

Sources: [MR pipelines and fork behavior](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/), [merge trains](https://docs.gitlab.com/ci/pipelines/merge_trains/), [merge checks](https://docs.gitlab.com/user/project/merge_requests/auto_merge/#require-a-successful-pipeline-for-merge), [allow_failure](https://docs.gitlab.com/ci/yaml/#allow_failure).

## Graph, artifacts and resource use

Use `needs` for actual dependencies and earlier starts, with explicit artifact transfer. If a producer is conditionally absent, determine whether the consumer can legitimately run without it before using `optional: true`; never turn a required test into an optional edge just to make pipeline creation pass. Keep expected test membership visible for parallel shards and isolate services/data per job.

Cache regenerable dependencies, using lockfile/toolchain and trust boundaries. Preserve protected/nonprotected separation unless a deliberate trust decision permits otherwise. Use artifacts for reports and generated outputs with bounded retention and explicit producer selection. Avoid overlapping cache and artifact paths whose restoration can overwrite one another. Confirm that tests actually ran; report upload is not an execution check.

Mark only safe-to-cancel jobs `interruptible`; understand `workflow:auto_cancel` for the installed version. Use `resource_group` or the project's established serialization for shared mutations, and do not automatically cancel deployment or data migration halfway through. Configure bounded `retry` only for identified infrastructure failures; a broad retry can hide assertion failures and flaky behavior.

Sources: [needs](https://docs.gitlab.com/ci/yaml/needs/), [caching](https://docs.gitlab.com/ci/caching/), [interruptible](https://docs.gitlab.com/ci/yaml/#interruptible), [retry](https://docs.gitlab.com/ci/yaml/#retry), [resource_group](https://docs.gitlab.com/ci/yaml/#resource_group), [pipeline efficiency](https://docs.gitlab.com/ci/pipelines/pipeline_efficiency/).

## Trust and validation

A fork MR run in the parent project can combine contributor-controlled CI content with parent runners and variables. Review that boundary before triggering it; do not rely on the UI warning existing in every API or command path. Protected variables/runners are not automatically safe merely because a job is an MR job. Verify the installed version's access requirements and actual settings. Keep test credentials disposable and publication/deployment authority separate; limit job-token scope and use protected environments where the project requires them.

Pin includes/images to verified immutable references where supported and maintain an update path. Do not copy newest syntax into an older GitLab or relax protected-resource rules to get a test passing.

CI Lint can validate includes and simulate parts of pipeline creation. Its default UI simulation is a push to the default branch; that does not prove MR, fork, scheduled or train behavior. Validate those routes against the applicable rules and, when authorized, actual pipeline evidence for the exact revision/event. Inspect runner behavior, service readiness, collected tests and artifacts separately from configuration validity.

Sources: [Fork MR resources](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/#use-with-forked-projects), [CI Lint](https://docs.gitlab.com/ci/yaml/lint/), [YAML reference](https://docs.gitlab.com/ci/yaml/).

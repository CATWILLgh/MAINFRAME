# A repeatable project testing strategy

Use this reference when establishing a project's verification approach, choosing a test boundary for a change, or auditing whether existing checks protect the intended guarantees. The selection method is shared across projects; the applicable levels and tools follow each project's actual risks. This is not a mandatory five-stage pipeline, a test-count quota, or a prescribed framework.

## Select from the same sequence

Start with the observable guarantee and choose the smallest boundary that can faithfully prove it. Add a higher level only for a guarantee the lower level cannot establish; keep existing required coverage. Several levels can protect different risks in the same feature.

| Level | What it proves | Typical evidence and execution |
| --- | --- | --- |
| Business rules | Calculations, validation, permissions decisions and state transitions | Deterministic pure/in-process tests in the fast local loop |
| Components and contracts | Actual handler/module behavior, serialization, error mapping and collaborator protocols | In-process component tests; consumer/provider contract checks at their real boundary. A fake alone does not establish provider compatibility |
| Real integrations | Database constraints, transactions, migrations, queue delivery and external-service semantics | Correct-engine tests: isolated verified local PostgreSQL where appropriate; other service-backed checks in CI by default |
| Critical journeys | Essential user or system outcomes across the assembled application | A small selected set of end-to-end checks in CI; passing component tests do not establish the assembled journey |
| Specialized risks | Relevant concurrency, performance, security, recovery, upgrade or compatibility guarantees | Focused evidence at the affected boundary; expensive environments and campaigns in CI. Cheap concurrency or security checks can still be local |

Specialized risks apply across the other levels; they are not a final optional bucket or automatically a costly suite. Do not defer required security, migration or recovery evidence to an optional scheduled job. A library need not have a browser journey, and a service without a database need not set up PostgreSQL. An infrastructure or documentation repository still needs the relevant contract, configuration or artifact checks, not invented business logic.

Use [local boundaries](local.md) for infrastructure authority and [the CI contract](ci.md) for required events, result interpretation and cost. Test-level names vary between frameworks; judge the exercised boundary rather than renaming the project's established suites.

## Keep one project verification map

Reuse the existing project test documentation, project-skill reference, or equivalent maintained owner. Link it from project knowledge; do not create another file when one already serves this purpose. Group guarantees that share the same proof and execution route rather than listing every test case. Start with the current task's affected guarantees and expand during relevant work; an ordinary change does not authorize a repository-wide inventory.

Use this compact schema, adapted to the existing document's format:

| Guarantee / concrete failure | Level and real boundary | Owning tests and runnable command | Local / CI job and event | Acceptance and evidence gap |
| --- | --- | --- | --- | --- |
| A project-specific invariant and the regression to detect | What is actually exercised, including engine or collaborator | Links to the existing test owner and verified command | Required environment; actual CI job/configuration and trigger | Observable pass condition; unimplemented coverage, unrun proof or justified non-applicability |

The row above describes the fields; do not copy it as project evidence. Record supported facts, not invented commands, job names or successful runs. When a command starts services or selects a broad suite, expose that consequence rather than presenting it as a fast local check. Distinguish an absent test/job, a present but unrun check, and a level that does not apply. Link detailed evidence for the tested revision when needed; keep volatile run history out of the durable map.

For a new software project, establish a minimal map from its accepted requirements and available checks before calling its verification setup complete. Mark missing checks explicitly. For an existing project, reconcile affected entries against source and CI configuration; do not rewrite unrelated entries or bootstrap a new documentation system. If the existing project skill owns verification knowledge, maintain that owner under its existing tracked/ignored policy. Read-only work returns proposed corrections instead of writing the map.

## Use the map during implementation

1. Match the changed behavior and plausible regression to the relevant row, or identify the missing guarantee. Reuse known current commands and boundary evidence.
2. Select the cheapest faithful test and follow [red, green, refactor](tdd.md). Include material rejection and side-effect risks rather than mechanically adding every test level.
3. Run the focused proof and nearest affected fast regressions. Connect required higher-level proof to an actual CI job and trigger; merely promising “CI will test it” is insufficient.
4. Update the owning map only when guarantees, test ownership, commands, environment, required gates or a durable gap changed. Return actual results and pending evidence separately; no per-task map churn.

## Evaluate the same map during audit

Apply `mainframe-test-audit` for the read-only assessment. Trace material guarantees to executable tests, then inspect assertions and the actual local/CI selection path. A documented row is not proof that its test executes or detects the failure. Check that mocks preserve the claimed boundary, fixtures isolate data, required jobs run for the right revision/event, and skipped/allowed-failure results cannot masquerade as successful required coverage.

Look for unprotected guarantees, unjustified duplication or expensive setup, and unsupported non-applicability claims. Require concrete evidence before reporting a defect; absence of a particular level or document format is not itself a test-quality failure. Name the affected guarantee, mechanism, evidence and acceptance condition. Return corrections to an inaccurate map without editing it during the audit. Authorizing repair permits a separate implementation phase, not a retroactive claim that the audit was independent.

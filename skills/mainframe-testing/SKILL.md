---
name: mainframe-testing
description: Design, write, run, or repair tests and GitHub/GitLab CI during development. Use for TDD, fixtures, local/CI boundaries, and verification evidence. Use mainframe-test-audit to assess an existing test system.
---

# Own the behavior and its verification

Apply this method as the primary agent or a delegated engineer within the same task authority. Use the stack-specific engineering skill for native tools and contracts. This method does not authorize implementation during read-only investigation or verification, global installation, remote access, publication, or deployment.

For a behavior change, use test-driven development: demonstrate the relevant failing behavior before the fix, implement the smallest complete correction, then refactor while the focused checks remain green. A compiler, import, setup, credential, or network failure is not the intended red result. Reuse an existing test that already demonstrates the defect; do not add a duplicate solely to claim TDD.

State what observable behavior must change, what must remain true, and which boundary can prove it. Test user-visible results and protected side effects rather than private implementation details. Include meaningful rejection, boundary, failure, retry, concurrency, and cleanup cases when the contract contains them; do not generate an indiscriminate test matrix.

## Choose the operation

Use this method proactively when implementation requires tests, test changes, or CI work; an explicit request to “use TDD” is unnecessary. It owns how verification is built and run, including ordinary regression checks after a change. Its result is the authorized change with meaningful tests and accurately bounded evidence.

Use `mainframe-test-audit` when the task is to assess the quality of an existing test system, or concrete escaped regressions, flakiness, misleading green results, or measured cost warrant investigation within scope. That method evaluates the same criteria without changing the audited system. Do not start an audit for every test run or load both full methods by default.

For an assignment that includes both audit and repair, keep findings and implementation as explicit phases and reuse the caller's existing repair authority. A delegated read-only auditor returns findings to its caller; it does not become an implementer. An author may review their own work but must not claim an independent audit.

## Load the method needed now

| Decision | Reference |
| --- | --- |
| Red/green/refactor, regression design, or an inherited implementation | [Behavior and TDD](references/tdd.md) |
| Local scope, fixtures, PostgreSQL identity, or an unavailable real dependency | [Local test boundary](references/local.md) |
| Required CI checks, triggers, cost, caching, failures, or evidence ownership | [CI contract](references/ci.md) |
| GitHub workflow authoring or troubleshooting | [GitHub Actions](references/github.md) |
| GitLab pipeline authoring or troubleshooting | [GitLab CI](references/gitlab.md) |

Keep the normal local loop lightweight: pure or in-process checks first, isolated verified local PostgreSQL when its semantics are needed. Other service-backed, expensive, compatibility, and end-to-end suites run in CI by default. Do not start a local service fleet or replace an engine with PostgreSQL merely to fit this policy. A more permissive local pass requires explicit caller/project authority for that pass; cheap tests are not proof of a dependency's untested semantics.

A prose-only or reversible low-impact change needs the smallest meaningful validation, not an artificial failing test. For a behavior change that cannot be faithfully observed locally, demonstrate the local portion, provide the CI test at its real boundary, and record the missing red/green evidence honestly. Never weaken the requirement just to obtain a green local result.

## Finish with evidence

Run the focused proof and nearest relevant fast checks. Inspect failures and fix in-scope problems; do not weaken assertions, accept snapshots blindly, hide failures, rerun flakes until green, or equate coverage percentage with correctness. Avoid broad reruns unless new changes or evidence require them.

When delegating, supply the behavior, test boundary, local/CI split, permitted infrastructure, and completion evidence. The implementer returns observed red and green outcomes (or the exact exception), changed tests, and remaining required CI jobs. The coordinator verifies the integrated result and relevant cross-component checks after integration; per-agent green checks do not establish combined correctness.

Distinguish local validation, CI configuration validation, a run for the exact revision and event, and live acceptance. If CI has not run or cannot be observed, report that limitation and the exact pending job; do not claim full verification or silently mark required evidence unnecessary. Run or inspect CI only within existing authority. Preserve the project's useful test map and commands through its existing project skill when authorized; do not add task logs or a new progress system.

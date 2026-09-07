---
name: mainframe-test-audit
description: Audit an existing test system for meaningful regression coverage, reliability, and execution cost. Use when a test audit is requested or when observed flakiness, false confidence, hidden cost, or a material coverage gap makes test-system quality the actual problem. Do not use for routine implementation, writing or fixing tests, final product acceptance, or general code review.
---

# Test-system audit

Apply this method when the active work matches the description, whether you are the primary auditor or a delegated specialist. Follow the scope and authority supplied through the current execution path; this skill does not expand either.

Audit the existing test system rather than redesigning it from preference. Tests protect observable guarantees, not a target count, coverage percentage, framework fashion, or universal ratio of test levels.

## Establish the audit boundary

Identify the exact package, component, journey, test layer, suite, or execution contour under review. State the observable product guarantees inside that boundary and the concrete regressions the tests are expected to detect.

Inspect the effective project instructions, relevant product decisions and contracts, owning code paths, test configuration, existing tests, fixtures and lifecycle setup, native commands, and applicable CI configuration. Do not broaden a bounded audit into a repository-wide review.

Map how the project obtains each kind of evidence:

- focused checks used while changing one behavior;
- the nearest fast local regression suite;
- checks whose correctness depends on a real local dependency;
- broad, compatibility, deployed, or full-system checks reserved for CI or a deliberately prepared environment.

The absence of one universal test command is not a defect. Judge whether the applicable checks can be discovered, understood, and rerun without unrelated infrastructure or hidden side effects.

## Test the quality of the evidence

For every material guarantee, identify the cheapest observation that would faithfully fail for the real regression. Inspect whether the current evidence:

- reaches the behavior through the boundary where the defect can occur;
- asserts an observable contract strongly enough to detect the failure;
- uses a mock, stub, emulator, database substitute, or fixture that preserves the relevant semantics;
- avoids coupling to private implementation details that can change without changing behavior;
- covers only branches that actually exist, without duplicating the same guarantee for ceremony;
- isolates time, randomness, ordering, process state, shared data, network access, and concurrency sufficiently to be repeatable;
- makes setup, infrastructure, runtime, and maintenance cost visible and proportional to the risk.

Check the strongest plausible alternative explanation before confirming a defect. Repository behavior and repeatable observed output are authoritative for local claims. Verify an external contract or version-sensitive runner, framework, library, protocol, or database claim against current primary documentation when it is load-bearing.

Use strict evidence thresholds:

- A coverage gap requires a concrete observable regression that no current test would detect.
- A weak or misleading test requires a demonstrated path to green evidence while its claimed contract is broken.
- A reliability defect requires reproducible nondeterminism, order dependence, state leakage, or an equivalent evidenced instability.
- An execution-cost defect requires measured or directly observable cost and its actual source.

Do not report style preferences, preferred test ratios, raw coverage percentages, duplicated assertion counts, or hypothetical improvements as confirmed defects.

## Keep the audit read-only

Do not author, rewrite, weaken, suppress, or repair tests, source, fixtures, snapshots, or configuration during the audit. When ordinary implementation work merely exposes a possible test-system issue outside its assigned result, do not expand into an audit; route the bounded observation through the applicable project problem mechanism or return it to the current recipient.

Run an existing focused or fast check only when it supplies evidence needed by the audit. Inspect the exact command, lifecycle scripts, configuration, setup, fixtures, destinations, and external effects first. Do not install dependencies, start services or containers, update snapshots, use a fix mode, or invoke a deployed environment unless that action is explicitly included in the supplied authority and the required environment is deliberately prepared.

Run a broad or expensive suite only when measuring or evaluating that suite is part of the audit. Use the project's recorded infrastructure boundary; do not assume that a service is disposable or permitted from its technology or location alone. Never retry until green and call that reliability evidence.

## Return actionable findings

Lead with the audited boundary and technical conclusion. For each confirmed problem, identify the affected guarantee, the current evidence path, the demonstrated failure or false-confidence mechanism, its consequence, and the smallest acceptance condition for a later correction. Keep one finding around one independently actionable underlying problem.

Record or reconcile a project problem only when the current assignment authorizes durable recording and the configured project problem route is available. Otherwise return the evidence and required recording action to the current recipient. A clean audit with no confirmed problem is a valid result.

Report the commands and durations actually observed, disproved hypotheses, external sources used for load-bearing claims, and material limits on confirmation. Do not prescribe implementation, paste raw logs, claim product acceptance, or force a rigid report template when concise prose is clearer.

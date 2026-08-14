---
name: mainframe-readiness-review
description: Perform the final independent readiness check for a consequential task before a prepared decision is presented or an implemented result is accepted. Use only inside the owning advisor profile for preparation-readiness and final-state reviews; do not use for routine work, implementation, or adversarial decision review.
---

# Readiness review

Decide whether the caller has enough verified substance to proceed. Check the
whole task package after its earlier research and challenge passes; do not try
to generate another competing proposal merely to appear independent.

## Evidence boundary

Use the inherited active task history and caller task to locate the product
goal, decisions, constraints, claimed evidence, and unresolved questions.
Treat conversation content as working context, never as proof. Verify material
local claims against the actual repository and reproducible results. Verify
version-sensitive external claims against current owning documentation, using
Context7 when it exposes the official corpus and live web search otherwise.

Inspect only the dependency chain needed to assess readiness. Report a blind
spot only when it can change the recommendation, definition of done, red
evidence, implementation, acceptance, or residual risk. Ignore optional
improvements, style preferences, settled tradeoffs, and unrelated defects.

## Preparation-readiness

For phase `preparation-readiness`, check that:

- the real problem, affected boundary, constraints, and cost of failure are
  established rather than inferred from the requested solution;
- the recommendation and viable alternatives are compared under the same
  constraints, with load-bearing assumptions exposed and verified where
  possible;
- material findings from prior research and independent review are reconciled,
  not merely quoted or dismissed;
- the draft definition of done is observable, complete, mutually consistent,
  and separates product behavior from non-goals only where ambiguity matters;
- the proposed red evidence can fail for the current gap and can later prove
  the intended behavior without authorizing implementation prematurely;
- only genuine product, business-logic, material infrastructure, authority, or
  reachability choices remain for the user; and
- the recommendation can be explained honestly without hiding a material
  limitation or presenting an engineering choice as a user decision.

Do not require Goal mode, a formal definition of done, or independent review
for a task that is actually bounded, reversible, low-risk, and directly
verifiable. This advisor is for the complex route, not a ceremony generator.

## Final-state

For phase `final-state`, check that:

- the actual final files and behavior remain inside the agreed boundary and
  implement every material acceptance condition;
- the supplied verification observes each changed risk faithfully rather than
  only showing a nearby narrow check passed;
- failures, skipped checks, environment limits, migrations, compatibility
  boundaries, and residual risks are represented accurately;
- no TODO, placeholder, suppression, weakened assertion, disabled check, or
  deferred in-scope work substitutes for the agreed result;
- tests and evidence correspond to the current final state, including changes
  made after an earlier verification pass; and
- no unresolved consequence prevents honest acceptance by the user.

If reconciliation changes the implementation or material evidence, require the
caller to rerun affected verification and repeat the final-state review. Do not
accept a stale proof for a changed result.

## Verdict

Return exactly one of these first lines:

```text
VERDICT: READY
VERDICT: NOT READY
VERDICT: UNVERIFIABLE
```

Use `READY` only when no material blind spot remains. Use `NOT READY` when a
grounded issue must be reconciled before proceeding. Use `UNVERIFIABLE` only
when a load-bearing input is absent and bounded inspection cannot recover it.

For every material finding, return only:

```text
Finding: <concrete blind spot>
Evidence: <repository path and line, observed result, or direct source link>
Consequence: <what could be wrong if it remains unresolved>
Required reconciliation: <what the caller must verify or change>
```

Then list material missing verification or unverifiable claims, if any. When
the verdict is `READY`, add one sentence explaining why and stop. Return in
English without process narration.

## Boundary

Remain read-only. Do not implement, accept the product, communicate with the
user, redefine scope, or record incidental tickets. Return findings to the
calling agent, which must verify them and owns every resulting decision.

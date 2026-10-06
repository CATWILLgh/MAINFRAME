---
name: mainframe-consequential-review
description: Assess a consequential decision or readiness claim when mistaken acceptance could cause material harm, such as a production rollout, migration, or recovery. Not routine code review.
---

# Review consequential decisions and results

Apply this skill before accepting a decision or completion claim when being wrong would have a material product, operational, security, financial, legal, or recovery cost. Do not wait for an explicit review request when the trigger is already evident.

Do not turn ordinary reversible work into a review ceremony. Keep the review limited to the decision or result whose acceptance matters.

## Establish the acceptance claim

State neutrally what is about to be accepted, its boundary, the consequence of failure, its load-bearing assumptions, and the evidence already offered. Ignore confidence, enthusiasm, status, and claims that the answer is obvious.

Treat conversation and prior conclusions as context, not proof. Inspect the affected repository, configuration, contracts, dependency chain, or produced artifact. Verify version-sensitive external claims against current primary documentation. Use a bounded experiment when it is the cheapest faithful way to settle a material uncertainty.

Mark each material statement as observed, source-backed, inferred, or unknown. Do not upgrade an inference into evidence because it is plausible.

## Try to disprove it

Identify the strongest realistic way the decision or result could fail. Work backward to concrete causes, then discard any cause already prevented by the actual system or unsupported by evidence.

Test the assumptions that must hold for acceptance. State what observation would make each assumption false and whether that observation is present, absent, or unavailable.

For a proposed decision, compare another approach only when there is a genuine decision fork. Evaluate it under the same constraints and explain where it is better or worse. Do not invent an alternative merely to appear critical.

For a completion claim, map each material acceptance condition to evidence that directly observes it. A successful build, nearby test, file presence, or structural check does not prove behavior outside what it actually measured. Evidence produced before later changes is stale for risks affected by those changes.

Keep only objections that could change acceptance, mitigation, or residual risk. A review with no grounded objection is a useful result.

## Respect ownership and authority

This review does not broaden authority. A recipient assigned only to review remains read-only and returns findings to the decision owner.

If you are already implementing the authorized task, you may correct an in-scope issue discovered by this review under the authority you already have. Do not expand into unrelated defects or describe your own review as independent.

Use a separate reviewer only when independence materially improves confidence and the environment and assignment support it. A different label or role does not make self-review independent.

## Return the assessment

Lead with one clear verdict using the recipient's language and requested format:

- Use `proceed` when no material grounded objection remains.
- Use `proceed-with-mitigations` when acceptance is reasonable with explicit bounded safeguards.
- Use `reconsider` when a grounded issue invalidates a load-bearing assumption or makes the proposed acceptance materially unsafe or unreliable.
- Use `unverifiable` only when essential evidence is unavailable and bounded inspection cannot recover it.

Use exact `ASSESSMENT: <verdict>` tokens only when the caller or consuming
integration requires that machine-readable contract. Otherwise translate the
verdict naturally. Report only material assumptions, evidence, objections,
mitigations, and missing observations; omit empty categories. When proceeding,
briefly explain why the evidence is sufficient and finish the assessment.

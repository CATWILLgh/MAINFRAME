---
name: mainframe-decision-review
description: Independently challenge a consequential proposed decision, design, architecture, or approach before acceptance. Use for non-obvious tradeoffs or a high cost of being wrong; do not use for routine low-risk choices, implementation, or general defect discovery in existing code.
---

# Decision review

Test the proposed decision against its strongest grounded failure modes. The
goal is a more reliable decision, not disagreement for its own sake.

## Grounding rule

Ground every material objection in repository evidence, current primary
documentation, a bounded experiment, or explicit reasoning. Mark reasoning-only
claims as the weakest evidence. If an objection cannot be grounded, discard it
and name the limit instead of manufacturing doubt.

Treat a clean review as useful evidence. `proceed` is the correct verdict when
no serious grounded objection survives inspection.

## Review method

1. Reduce the brief to a neutral proposal, its boundary, constraints, viable
   alternatives, load-bearing assumptions, evidence, and cost of failure.
   Ignore confidence, enthusiasm, status, and claims that the answer is obvious.
2. Inspect the affected code, configuration, contracts, and dependency chain
   before objecting. A failure already prevented by the real system is not a
   finding. Stay inside the supplied decision boundary.
3. Verify every version-sensitive framework, library, protocol, API, security,
   or operational claim against current owning documentation. Use Context7
   when it exposes the official corpus; otherwise use live web search to reach
   the primary source. Add an independent source only when the claim is
   disputed, interpretive, plausibly stale, or expensive to get wrong.
4. Run a pre-mortem at a realistic failure horizon: assume the decision failed
   materially, work backwards to specific causes, then keep only causes that
   survive grounding.
5. Try to falsify each load-bearing assumption. State what observation would
   make it false and whether that observation is present, absent, or still
   unavailable.
6. Build the strongest alternative only for a genuine decision fork. Compare
   it under the same constraints and state where it wins and loses. Do not
   invent an alternative to fill the report.
7. Rank surviving objections by consequence and evidence confidence. Stop when
   the load-bearing assumptions and strongest grounded objections are resolved;
   more searching is not automatically more confidence.

## Severity

- **Critical**: confirmed or immediately reachable catastrophic harm, such as
  broad production loss, material compromise, irreversible corruption, or
  comparable safety, legal, or financial impact.
- **High**: a major product or security guarantee fails for meaningful scope,
  with serious impact and no safe practical workaround.
- **Medium**: a real bounded defect or material maintainability or performance
  problem with recoverable impact, limited scope, or a practical workaround.
- **Low**: localized friction or quality debt without demonstrated material
  product impact. Preference and speculative improvement are not findings.

Severity describes consequence; confidence describes evidence. Take borderline
severity at the lower level and state what evidence would raise it. Do not bury
a serious finding under low-value observations.

## Verdict

Return exactly this English structure, with no preamble:

```text
ASSESSMENT: <proceed | proceed-with-mitigations | reconsider | unverifiable> — <one-line reason>

LOAD-BEARING ASSUMPTIONS:
- <assumption> — <holds | unverified | false> — <grounding>

GROUNDED OBJECTIONS:
- [SEVERITY] <falsifiable failure scenario> — <code:path:line | source:url | reasoning> — <cheap mitigation when one exists>

COUNTER-MODEL:
- <strongest real alternative and where it wins or loses; omit when there is no genuine fork>

HONEST LIMITS:
- <material evidence unavailable, objections discarded as ungrounded, or checks needed for greater confidence>
```

Use `unverifiable` only when load-bearing input is unavailable and bounded
inspection cannot recover it. Name exactly what would establish the missing
fact. If there are no grounded objections, say so directly in that section.

## Boundary

Review the proposal; do not implement it, audit unrelated existing defects,
rewrite requirements, communicate with the user, or take ownership of the
caller's decision. The calling agent must verify consequential findings before
changing the proposal.

## Method sources

- [Gary Klein, "Performing a Project Premortem" (HBR, 2007)](https://hbr.org/2007/09/performing-a-project-premortem)
- [Richards J. Heuer Jr., *Psychology of Intelligence Analysis*](https://www.cia.gov/resources/csi/books-monographs/psychology-of-intelligence-analysis-2/)
- [Sharma et al., "Towards Understanding Sycophancy in Language Models"](https://www.anthropic.com/research/towards-understanding-sycophancy-in-language-models)
- [Huang et al., "Large Language Models Cannot Self-Correct Reasoning Yet"](https://arxiv.org/abs/2310.01798)
- [Gou et al., "CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing"](https://arxiv.org/abs/2305.11738)

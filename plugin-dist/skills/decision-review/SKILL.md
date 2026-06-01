---
name: decision-review
user-invocable: false
disable-model-invocation: true
description: "Methodology for rigorous, evidence-grounded validation of a proposed decision, design, or approach. Covers pre-mortem failure-scenario generation, disconfirmation testing, counter-model construction, evidence-grounding of every objection, and honest severity ranking — with the hard discipline that an objection which cannot be grounded is reported as ungrounded, never manufactured or inflated. Loaded by the `decision-reviewer` agent only; closed to main-context auto-invocation."
when_to_use: "A decision/design/approach review is in flight inside the `decision-reviewer` sub-agent — validating an architecture choice, a design fork, or a plan before it is committed to. Triggered via agent frontmatter `skills:` preload, not by direct user invocation."
---

# Decision review — method

Preloaded into the `decision-reviewer` sub-agent. The job is to find the strongest **grounded** reasons a proposed decision will fail, so the decision is hardened before it is committed to.

## Prime directive — grounding, not posture

The value here is not that you disagree. An assigned contrarian who manufactures objections to fill the role makes the decision *worse*, not better: the proposer refutes the weak objections and walks away more confident (Nemeth, *EJSP* 2001 — assigned devil's advocacy fosters "cognitive bolstering of the initial viewpoint" rather than genuine reconsideration). The value is **specific, falsifiable, evidence-backed failure modes**.

Therefore the one rule that overrides every other:

> **If you cannot ground an objection in evidence, say so — do not invent one.**

State the truth about your own findings: *"The strongest objection I can ground is X, severity Medium; beyond that I would be speculating."* A reviewer that fabricates plausible-but-false objections trains the reader to ignore it — the false-positive firehose is this method's failure mode, exactly as ritualized dissent is the human one. Honesty about the *strength* of what you found preserves the signal. Concluding "I found no high-severity grounded objection" is a valid, valuable outcome — not a failure to do your job.

## Step 1 — Strip the framing (defeat sycophancy)

LLMs drift toward agreeing with the framing they are handed. Evaluate the **artifact**, not the author's confidence in it. Ignore "I think this is a great plan", "obviously the right call", enthusiasm, and seniority cues. If the input carries the author's opinion, discard the opinion and keep the neutral proposal. Judge what is actually proposed, against reality — not against how it was sold.

## Step 2 — Ground yourself in the real system

An objection you can check, you must check. Pure reasoning inherits the same blind spots as the proposal (Huang et al., arXiv:2310.01798 — models cannot reliably self-correct "without external feedback"; tool-grounded critique breaks the loop, Gou et al. CRITIC, arXiv:2305.11738).

- Read the actual code, configs, and constraints the decision touches (`Read`/`Grep`/`Glob`) before forming objections. A failure mode that the code already prevents is not a failure mode.
- When the decision rests on a library / framework / protocol / API claim, verify it against authoritative sources (Context7 first, then web) — do not object from memory.
- Tag each objection with its grounding: `[code: path:line]`, `[source: url]`, or `[reasoning]`. Reasoning-only objections are the weakest and must be flagged as such.

## Step 3 — Pre-mortem (prospective hindsight)

Do not ask "what could go wrong?" — that invites vague worry. Ask the stronger question (Klein, HBR 2007 — prospective hindsight lifts correct cause-identification by ~30%):

> **"It is six months later. This decision failed badly. What caused it?"**

Work backwards from the assumed failure to concrete, traceable causes. Each cause becomes a candidate objection — then ground it per Step 2.

## Step 4 — Disconfirmation, not confirmation

Per Heuer's Analysis of Competing Hypotheses (CIA, 1999): seek evidence that would **falsify** the approach, not evidence that supports it. For each load-bearing assumption the decision rests on, ask: *what observation would prove this assumption false, and is that observation present?* List the assumptions explicitly — an unexamined assumption is where decisions die.

## Step 5 — Build the counter-model when it is warranted

A list of objections is easy to wave away; a complete alternative is not (Cosier, *SMJ* 1980 — dialectical inquiry outperforms simple devil's advocacy on complex decisions). When the decision is a genuine fork with high cost-of-wrong, construct the **strongest alternative approach** you can, on the same constraints, and state plainly where it beats the proposal and where it loses. If the proposal survives a steelmanned alternative, that is real evidence *for* it — say so.

## Step 6 — Rank honestly by severity

Use the `severity-calibration` rubric. Do not drown a Critical in nitpicks, and do not inflate a Low to look productive. A review of ten Low objections and zero grounded High is a *green light with cosmetics*, and must read as one. Borderline → pick the lower level and state what would raise it.

## Step 7 — Verdict and output

End with an honest, decision-useful verdict. Structure:

```
ASSESSMENT: <proceed | proceed-with-mitigations | reconsider> — one line, why.

LOAD-BEARING ASSUMPTIONS:
- <assumption> — [holds | unverified | false] — <grounding>

GROUNDED OBJECTIONS (strongest first):
- [SEVERITY] <falsifiable failure scenario: under condition X this breaks because Y> — <grounding: code:line | source | reasoning> — <mitigation if cheap>

COUNTER-MODEL (only if a genuine fork):
- <strongest alternative, where it wins / loses>

HONEST LIMITS:
- <what you could not ground; the strongest objection you had to drop for lack of evidence; what a deeper check would need>
```

If the proposal is sound and you could not ground a serious objection, the verdict is `proceed` and the GROUNDED OBJECTIONS section says so — do not pad it.

## Anti-patterns

- **Manufacturing objections to fill the adversarial role.** This is the prime-directive violation; it inverts the method's value.
- **Objecting from memory** on a library/API/protocol claim instead of verifying it.
- **A failure mode the code already handles** — you skipped Step 2.
- **Inflating severity** to look rigorous — destroys the signal `severity-calibration` exists to protect.
- **Generic worry** ("this might not scale", "edge cases exist") with no specific, falsifiable scenario attached.
- **Refusing to bless a sound decision** — a forced "but actually…" when the honest answer is `proceed` is theater.

## Cross-refs

- [`severity-calibration`](../severity-calibration/SKILL.md) — the rubric for Step 6; reused, not duplicated.
- [`code-audit`](../code-audit/SKILL.md) — for finding defects in *existing code*; this skill reviews *decisions*, not implementations.

## Sources

- Klein, "Performing a Project Premortem," *HBR* Sept 2007 — prospective hindsight (~30% lift in cause identification). https://hbr.org/2007/09/performing-a-project-premortem
- Nemeth et al., "Devil's advocate versus authentic dissent," *European Journal of Social Psychology* 2001 — assigned dissent can bolster the majority view. https://onlinelibrary.wiley.com/doi/abs/10.1002/ejsp.58
- Heuer, *Psychology of Intelligence Analysis* (CIA, 1999) — Analysis of Competing Hypotheses; disconfirmation over confirmation.
- Huang et al., "Large Language Models Cannot Self-Correct Reasoning Yet," arXiv:2310.01798 — self-correction needs an external signal.
- Gou et al., "CRITIC: LLMs Can Self-Correct with Tool-Interactive Critiquing," arXiv:2305.11738 — tool-grounding breaks the hallucination loop.
- Cosier, "A critical view of dialectical inquiry as a tool in strategic planning," *Strategic Management Journal* 1980 — full counter-model beats a list of objections.

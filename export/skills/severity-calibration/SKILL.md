---
name: severity-calibration
user-invocable: false
description: Assign a calibrated severity level (Critical/High/Medium/Low) to a finding, risk, bug, or audit result by real impact rather than drama. Provides the rubric for each level and the discipline against severity inflation, which devalues genuinely critical findings.
when_to_use: Trigger when rating or reporting the severity or urgency of a finding. Common triggers — producing a review or audit report, risk or security assessment, bug triage, or any output that labels how serious something is.
---

# Severity calibration

A rubric and discipline for assigning severity honestly. Reinforces the global rule
"calibrate severity honestly" by turning it into a concrete, shared scale.

## Why it matters

Severity tells the reader where to spend attention first. Inflating it — labeling
everything Critical or High — trains the reader to discount the label, so a genuinely
critical issue gets the same shrug as the noise. Calibrated severity keeps the signal
trustworthy.

## The rubric

Assign by real impact, not by how dramatic the finding feels:

- **Critical** — breaks functionality, creates a security vulnerability, or loses data.
- **High** — violates a business invariant, significantly degrades UX, or risks data loss.
- **Medium** — violates a standard, adds technical debt, or degrades performance without breaking.
- **Low** — style, recommendation, nice-to-have.

## Discipline

- **Reserve the top level for real impact.** "Could this take down production, leak data, or corrupt state?" If not, it is not Critical.
- **Borderline → pick the lower level and explain why.** State the assumption that would raise it. Do not round up "to be safe" — that rounding is the inflation that erodes the scale.
- **Verify before labeling Critical/High.** A high-severity claim that proves wrong costs more trust than a missed Medium. Re-read the code or data to confirm before stamping it.
- **Be consistent.** The same kind of issue gets the same level throughout — two findings at equal real impact must not land at different levels.

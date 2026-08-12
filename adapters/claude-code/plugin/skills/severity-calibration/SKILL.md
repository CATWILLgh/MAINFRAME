---
name: severity-calibration
user-invocable: false
description: Assign a calibrated severity level (Critical/High/Medium/Low) to a finding, risk, bug, or audit result by real impact rather than drama. Provides the rubric for each level and the discipline against severity inflation, which devalues genuinely critical findings.
when_to_use: Trigger when rating or reporting the severity or urgency of a finding. Common triggers — producing a review or audit report, risk or security assessment, bug triage, or any output that labels how serious something is.
---

# Severity calibration

A compact MAINFRAME triage scale for findings that actually need a severity
label. It is not a substitute for a project's own incident levels, support
priority, regulatory classification, or a security-specific score such as
CVSS. Use the project's established scale when one exists.

## Why it matters

Severity tells the reader where to spend attention first. Inflating it — labeling
everything Critical or High — trains the reader to discount the label, so a genuinely
critical issue gets the same shrug as the noise. Calibrated severity keeps the signal
trustworthy.

## The rubric

Assign by demonstrated or well-grounded impact, reach, recoverability, and
available workaround. Severity describes the problem's consequence; confidence
describes the strength of the evidence. Do not raise severity to compensate for
uncertainty.

- **Critical** — confirmed or immediately reachable catastrophic harm: broad
  production unavailability, material compromise, irreversible corruption or
  loss, or comparable safety, legal, or financial impact. Ordinary broken
  functionality is not Critical.
- **High** — a major product or security guarantee fails for a meaningful
  scope, with serious user or business impact and no safe practical workaround;
  recovery remains possible or the blast radius is below Critical.
- **Medium** — a real, bounded defect or material maintainability/performance
  problem with recoverable impact, limited scope, or a practical workaround.
- **Low** — localized friction or quality debt with no demonstrated material
  product impact. Pure preference and speculative improvement are not findings.

## Discipline

- Establish the affected guarantee, reachable condition, scope, consequence,
  recoverability, and workaround before assigning Critical or High.
- A hypothetical worst case is not the observed severity. State the assumption
  that would make it reachable and lower the current label when that assumption
  is unverified.
- Borderline cases take the lower level. State what evidence would raise it.
- A standards violation, missing abstraction, long file, or low coverage is not
  Medium by itself. Tie it to a concrete failure or leave it as an unlabeled
  observation.
- Apply the same level to equal impact. If the project already defines a
  different scale, translate explicitly instead of silently mixing meanings.

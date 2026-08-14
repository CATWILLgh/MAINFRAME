# Review and evidence

Review the user journey, not only visual novelty.

## Evidence order

1. Reproduce the affected path with representative content and state.
2. Inspect visible output at realistic narrow and wide widths.
3. Check keyboard, focus, reflow, motion preference, and failure recovery when relevant.
4. Use automated accessibility, runtime, and performance checks for the defects they can actually detect.
5. Compare against the project's product and design contracts, then against current external standards where applicable.

Absence of automated findings is not proof of usability or accessibility. A screenshot can prove visible hierarchy or clipping, but not interaction correctness. A visual reviewer without browser access cannot verify focus, keyboard behavior, runtime errors, or state transitions.

## Findings

Record each material finding with:

- the affected place and user path;
- the observed mismatch;
- the likely user consequence;
- reproducible evidence;
- the governing project contract or primary external source when one exists.

Do not assign a universal quality score or call subjective preference a standards violation. Separate confirmed defects from optional directions. Route a confirmed out-of-scope problem through the project's ticket mechanism without interrupting the assigned work.

## Independent review

For a high-impact new direction, redesign, or uncertain visual result, use a fresh review perspective when available. Give it representative screenshots and the agreed product/design contract, not the builder's defense of the solution. Keep the reviewer read-only and its remit explicit: visual review is not full functional verification.

Run a bounded loop: one representative review packet, one coherent correction batch, then one confirmation pass. Continue only when the new evidence reveals a materially different problem.

## Sources

- WCAG 2.2 conformance — https://www.w3.org/WAI/WCAG22/Understanding/conformance.html
- GOV.UK Design System: teams still test adapted patterns in their own service — https://design-system.service.gov.uk/get-started/
- Core Web Vitals: field and lab evidence serve different purposes — https://web.dev/articles/vitals

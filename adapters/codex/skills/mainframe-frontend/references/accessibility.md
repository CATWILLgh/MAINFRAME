# Accessibility

Accessibility constrains structure and interaction from the start. A component library can provide a sound primitive, but the assembled interface still owns its labels, state, focus, content, contrast, responsive behavior, and correct use. Target WCAG 2.2 AA unless the project has a stronger contract.

## You still own

- **Contrast** — measure the actual rendered foreground/background pairs and visual state indicators that users need to perceive. Use [color](color.md).
- **Target size** — WCAG 2.2 AA SC 2.5.8 sets a 24×24 CSS px minimum with documented exceptions. Touch-first platform guidance commonly uses larger targets, including 44pt in Apple guidance and 48dp in Material. Grow the hit area without unnecessarily enlarging the glyph.
- **Visible labels and instructions** — provide the label or instruction a user needs; a placeholder is not a durable label. Use native `<label>` association when the control supports it and set `autocomplete` for applicable user-data fields.
- **Error identification** — identify the affected field and problem in text, place the message where the relationship is clear, and expose that relationship programmatically, commonly with `aria-describedby`. Color alone never carries the error.
- **Focus and reading order** — visual order must remain consistent with a meaningful DOM and keyboard order. Focus must be visible and not fully hidden by authored content such as sticky headers (SC 2.4.11).
- **Custom widgets** — anything built from `div` / `span` needs full keyboard + ARIA name / role / value (SC 2.1.1 / 4.1.2). First reach for a native element or a Radix primitive instead — the First Rule of ARIA: use a native HTML element with built-in semantics before re-purposing one with an ARIA role.
- **Reflow and zoom** — preserve content and operation at 400% zoom / 320 CSS px equivalent where SC 1.4.10 applies; avoid controls or overlays that permanently consume the usable viewport.
- **Motion preference** — remove or replace non-essential movement when `prefers-reduced-motion` is active. Use [motion](motion.md).

## WCAG 2.2 additions worth a check

- **2.4.11 Focus Not Obscured** — sticky headers / toasts must not bury the focused control.
- **2.5.8 Target Size** — 24 CSS px minimum, subject to the criterion's spacing and exception rules.
- **3.3.7 Redundant Entry** — don't re-ask for data already given earlier in a flow.
- **3.3.8 Accessible Authentication** — no puzzle / memory test as the only auth path.

## Verify

Use a keyboard-only pass for the affected journey; check focus visibility, order, overlays, zoom/reflow, labels, errors, and motion preference where relevant. Run axe or an equivalent automated check as additional evidence. Automation does not prove full WCAG conformance.

## Sources

- WCAG 2.2 — https://www.w3.org/TR/WCAG22/
- WCAG target size minimum — https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- Using ARIA, Rule 1 (native first) — https://www.w3.org/TR/using-aria/#rule1

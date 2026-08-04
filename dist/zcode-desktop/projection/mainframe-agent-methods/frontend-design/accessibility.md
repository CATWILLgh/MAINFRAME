# Accessibility — what Radix doesn't cover

shadcn / Radix primitives handle ARIA roles, keyboard, and focus-trap **for their own widgets**. This file is what the engineer still owns. WCAG 2.2 AA is the floor.

## You still own

- **Contrast** — token pairs + the focus ring (see [color.md](color.md)). Radix's ring inherits `--ring`; verify it clears 3:1.
- **Target size** — custom icon buttons / links ≥ **24×24 CSS px** (SC 2.5.8). Touch-first surfaces: 44pt (HIG) / 48dp (Material). Grow the hit area with padding, not a bigger glyph.
- **Visible labels** — every input has a real `<label>` (SC 3.3.2); a placeholder is not a label. Set `autocomplete` for user-data fields (SC 1.3.5).
- **Error text** — identify the field in text, adjacent, wired via `aria-describedby` (SC 3.3.1 / 4.1.2). Colour alone never carries the error.
- **Focus order** — visual reorder (flex / grid `order`, absolute) must still match DOM / tab order (SC 2.1.1). The focused element must not sit fully hidden under a sticky bar (SC 2.4.11).
- **Custom widgets** — anything built from `div` / `span` needs full keyboard + ARIA name / role / value (SC 2.1.1 / 4.1.2). First reach for a native element or a Radix primitive instead — the First Rule of ARIA: use a native HTML element with built-in semantics before re-purposing one with an ARIA role.
- **Reduced motion** — gate decorative transitions on `prefers-reduced-motion` (see [motion.md](motion.md)).

## WCAG 2.2 additions worth a check

- **2.4.11 Focus Not Obscured** — sticky headers / toasts must not bury the focused control.
- **2.5.8 Target Size** — 24px minimum.
- **3.3.7 Redundant Entry** — don't re-ask for data already given earlier in a flow.
- **3.3.8 Accessible Authentication** — no puzzle / memory test as the only auth path.

## Verify

Keyboard-only pass (Tab / Shift-Tab / Enter / Esc reach and operate everything); check focus visibility; run an axe / Lighthouse a11y pass. Absence of automated findings is not full coverage — the keyboard pass is the floor.

## Sources

- WCAG 2.2 (SC 2.1.1 / 2.1.2 / 2.4.7 / 2.4.11 / 2.5.8 / 1.3.1 / 1.3.5 / 3.3.1 / 3.3.2 / 3.3.7 / 3.3.8 / 4.1.2) — https://www.w3.org/TR/WCAG22/
- Using ARIA, Rule 1 (native first) — https://www.w3.org/TR/using-aria/#rule1

# Unslop visual direction

Start here for web UI design. Work from the audience, the task, and what the
product actually does. A screen needs a clear first read and a character that
fits its purpose.

## Read the screen before changing it

Look at the rendered surface or the supplied screenshot when available. Find the
first thing the eye lands on, the primary action, and the information needed to
act. Name the location and consequence of each issue you intend to address.
For example, equal emphasis on three summary cards can hide the failed import
that needs attention. A weak hierarchy can justify a redesign even when every
control works. For a new screen, use real content and its intended reading
order to anticipate the same problems.

Match the size of the change to the evidence. Polish a sound screen where it
breaks. When the hierarchy or composition is the problem, rethink the grouping
and reading order within the assigned scope. A discussion or review can stop
at a concrete recommendation.

## Give the design a reason to look that way

Before choosing styles, decide who the screen serves, what they should see or
do first, and which product-specific detail can carry the character. Draw the
tone from the product, its content, and its established visual language. Keep
navigation and secondary controls quiet enough for the focal content or action
to lead. Give color, texture, imagery, or motion a job where it appears.

For example, on an import monitor, show the latest failed run and its recovery
action together, with a distinctive stage-by-stage trace as the visual focus.
On a scheduling page, the timeline and its next open slot can supply the
character. The exact colors, typography, and density follow the product and
its users. Reuse existing brand and semantic roles.

## Refine the visible result

Choose the checks that change the result. Use the project's tokens and real
content as constraints.

- **Composition and spacing.** Give related content shared edges and tighter
  internal spacing. Use scale, placement, and density to separate primary and
  supporting information. Check for nested cards or repeated equal boxes that
  flatten the hierarchy.
- **Color and depth.** Make action, selection, and status distinct. Check
  contrast on the actual background and keep their meaning available without
  color alone. Question decorative gradients, glows, and borders where they
  compete with the content. Keep intentional brand expression.
- **Copy, type, and icons.** Use product-specific language, meaningful action
  verbs, units, and comparison periods. Remove filler and verify claims. Set
  distinct type roles, align icon boxes and comparable figures, and check
  wrapping with representative labels and data. At the rendered size, make
  sure display tracking keeps letter and word boundaries legible.
- **Imagery, detail, and motion.** Prefer a meaningful product view, an
  existing local asset, or a visual made in code. Keep one detail that belongs
  to this product when it helps the task. Make motion explain cause, continuity,
  or feedback, and respect reduced motion. Keep keyboard focus visible.

Read [layout, type, and motion](layout-type-and-motion.md) for those decisions
and [flows and accessibility](flows-and-accessibility.md) where the design
affects access or interaction. Preserve meaningful labels and controls at
narrow widths and in dense, empty, or other affected states.

For an implemented redesign, compare the rendered baseline and candidate
using the same task, representative content, viewport, and theme. Look for an
easier first read, a clearer next action, and fewer distractions. Revise or
discard a candidate that fares worse. Use [browser verification](browser-verification.md)
and describe gains you observed without claiming measured user performance.

Adapted from [Unslop by Damir Sokolovsky](https://github.com/heydamir/unslop/tree/a6f121eee5f29c2f74976b75456feae8b66afb3a)
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). MAINFRAME
condensed and rewrote the visual method, kept project design systems and
accessibility constraints, and replaced service-dependent options with local
materials and verification.

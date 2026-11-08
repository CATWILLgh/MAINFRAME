# Product illustrations and short demos

Use the Stageshow method when an illustration or short demo needs to show how
one product action leads to a visible result. Build the scene in React with the
project's existing UI primitives, local assets, styles, and browser tooling.
The method requires no upstream kit, install, CDN, or service.

## Compose the scene

- Name the action and the visible result in one sentence. Use a still if the
  result explains the idea on its own. Use motion if the order, transition, or
  feedback is what the viewer needs to understand.
- Keep the action target and its result in the same crop. Use the smallest
  recognizable slice of the product, with type and status labels readable at the
  actual placement size. Give the meaningful detail more space than surrounding
  chrome. Recompose for narrow placements rather than scaling down a full screen.
  Cut unrelated records before shrinking text and keep the context that explains
  what changed.
- Author the beats with fixed sample data. Render simulated controls as visual
  elements outside the tab order, without wiring app actions, requests, or live
  data. Give the scene a caption or text equivalent that conveys the same action
  and result. Keep any real play or pause control outside the simulated UI.
- Make the meaningful result visible in the poster or initial static render.
  For an animated version, keep that still available when motion is disabled or
  playback fails. Respect `prefers-reduced-motion` by showing the still and
  skipping autoplay. Play once by default. If repeating adds value, provide a
  real pause control and inspect the reset at normal speed.

## Worked scene

**Reserve stock.** Reserving three units moves them from available to reserved.
Crop to one order line and its two counts. Keep the line identifier and count
labels visible throughout, and omit navigation and other orders.
Open the [standalone example](../assets/stock-reservation.html) in a browser to
see the result and replay the three beats. Its dependency-free HTML, CSS, and
JavaScript demonstrate the composition and timing. Recreate those decisions
with the receiving project's React components when building its demo.

| Beat | What the viewer sees |
| --- | --- |
| Start | `Order 104 · Canvas bag` with `8 available · 0 reserved`. |
| Action | Briefly highlight the simulated `Reserve 3` affordance beside the counts. |
| Result and poster | The same line shows `5 available · 3 reserved` with a `Reserved` label. Hold this frame so the change can be read. |

Use the result row as the still and caption it “Reserving three units moves them
from available to reserved.” If the placement only needs to explain the result,
ship that frame alone. For a motion version, keep the counts in fixed positions
and change both in the same beat so the scene never appears to create stock.

## Verify locally

Open the result at its real placement size, including the narrowest supported
layout. Inspect the poster and the start, action, and result frames. Check that
the changed value, its label, and its context remain legible, and that the static
result is visible with reduced motion enabled. If the animation loops, watch the
last frame cross into the first at normal speed. A reset that looks like an
unexplained reverse action is a reason to end on the result and replay on demand.
Use [browser verification](browser-verification.md) for the local preview.

## Provenance

This guidance and example are original adaptations of ideas from Benji Taylor's
[Stageshow announcement](https://benji.org/stageshow) and the
[MIT-licensed source](https://github.com/benjitaylor/skills/tree/802057409787133703c56001080169e347305572/stageshow).

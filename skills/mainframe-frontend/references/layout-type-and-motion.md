# Layout, type, and motion

Build layout from content hierarchy and user priority. Reuse the project's spacing, breakpoint, container, and type systems. Choose responsive changes where content or interaction stops working rather than copying a framework breakpoint as product policy.

Give flex and grid children containing long content room to shrink. Keep meaningful content available through wrapping or bounded local scrolling. Avoid page-level horizontal overflow except for explicitly two-dimensional content. Fixed and sticky regions must not cover focused controls or final actions.

Treat mobile as an edited priority order, not compressed desktop. Move or remove lower-priority regions before shrinking readable text. Preserve navigation, primary action, drafts, selection, and a clear way back.

Create hierarchy through content order, spacing, scale, weight, contrast, alignment, and color. Keep long-form measure readable and inspect actual language and glyphs. Use tabular numerals where changing or aligned numbers benefit from them; use monospaced type for content that needs it, not as generic decoration.

Use motion for cause, continuity, feedback, or deliberate expression. Reuse project tokens, keep operational transitions interruptible, avoid `transition: all`, and honor reduced motion. Measure layout-affecting animation on representative devices instead of assuming it is harmless.

Inspect shared edges, baselines, icon boxes, wrapping, overflow, and vertical reachability in a normal, narrow, wide, and reduced-height view. Source values alone do not prove optical alignment.

---
id: 1d04acea
title: Add scrolling for long TUI plans
status: open
priority: medium
component: installer-tui
discovered: 2026-07-16
discovered-from: []
tags: ["tui", "accessibility", "preview"]
---

# 1d04acea: Add scrolling for long TUI plans

## What was observed

The preview screen renders the complete filesystem and configuration plans as
one string. It has no viewport, scroll position, or navigation keys. When the
combined plan is taller than the terminal, rows outside the visible area
cannot be inspected.

## Why it is a problem

The preview is the user's safety boundary before future application. A plan
that cannot be read in full prevents informed confirmation and will become
more likely as configuration resources and supported environments increase.

## Why it is not a duplicate

No existing ticket covers terminal-height overflow or preview navigation.
Configuration lifecycle tickets define what must be planned; this ticket is
about making every planned row reachable in the terminal.

## What probably needs to be done

- Render the preview through a Bubble Tea viewport sized from window messages.
- Add visible scroll position and keyboard hints.
- Preserve the current back and quit keys.
- Keep selection state and the generated preview stable while scrolling.

## Acceptance criteria

- A preview taller than the terminal can be read from first row to last row.
- Resize events update the viewport without losing the current position.
- Short previews retain the current compact layout.
- Tests cover scrolling, boundaries, resize, back, and quit behavior.

## Sources

- `internal/tui/model.go:102`
- `internal/tui/model.go:147`
- `internal/tui/configuration_view.go:36`

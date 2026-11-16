# Flows and accessibility

Map the changed journey from entry and prerequisites through the states a real person can reach: loading or pending, useful empty state, validation or recoverable error, unavailable or forbidden state, offline state when relevant, success, cancellation, retry, undo, and destructive confirmation.

Keep feedback near the responsible action and specific enough to guide recovery. Preserve entered data and context after recoverable failure. Do not use a toast as the only evidence of a durable change when the surface can show the authoritative result.

Show the product state in language the user can act on. Keep provider errors,
stack traces and internal workflow diagnostics in redacted developer telemetry.
Give the user a choice only when each offered action is available and changes
the outcome. Recover automatically when the system can do so safely. While
delivery is uncertain, show the known state, preserve the user's work and offer
retry only after the system establishes that it is safe. Exercise a representative
failure through the rendered UI and assert the message and available actions.

Use semantic HTML first. Preserve meaningful landmarks and headings, visible labels, DOM and reading order, keyboard operation, target size, visible focus, focus restoration, error association, non-color state cues, text alternatives, zoom and reflow, and reduced-motion behavior.

Measure contrast on the rendered foreground/background and essential component-state pairs. A component library does not prove that the assembled interface is accessible.

Exercise the changed path with keyboard-only interaction and the supported narrow layout. Automated accessibility checks add evidence but do not establish full conformance or usability.

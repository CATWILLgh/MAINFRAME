# Components and interaction

Start with required behavior and semantics, not a library name. Prefer a native element when it already provides the correct interaction. Reuse an established project primitive when it supplies valuable behavior, accessibility, or consistency; inspect its installed API and call sites first.

Before adding a component, search for the same semantic role, variants, styles, and consumers. Extend the canonical primitive or add a named variant when the role already exists. Do not create a near-duplicate that differs only by spacing, radius, color, icon placement, or a few props.

Avoid the opposite error: do not force unrelated roles into one abstraction or promote a one-off composition without a real shared contract. Keep page composition near its owning feature and shared behavior in the narrowest stable primitive.

Maintain one interaction vocabulary for primary, secondary, quiet, selected, and destructive actions. Icon-only controls still need an accessible name and full hit area. Preserve visible hover, pressed, focus, open, disabled, loading, success, and error states where they apply.

Use the installed component system, whether native, project-owned, shadcn, Radix, Base UI, Material UI, Ant Design, or another system. No library is mandatory. Do not initialize, replace, or broadly update a component system merely to implement a local change.

For overlays, menus, tabs, comboboxes, dialogs, drag-and-drop, and other composite widgets, preserve focus management, keyboard semantics, dismissal, layering, scroll ownership, and accessible names. Do not recreate complex behavior with clickable `div` elements.

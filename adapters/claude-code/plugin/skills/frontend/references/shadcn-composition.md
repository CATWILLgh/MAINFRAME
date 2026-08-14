# Composition

## Reuse and variants

- Search the local inventory and existing call sites before creating a component.
- One semantic role should have one canonical primitive. Add a named variant when repeated behavior or appearance belongs to that primitive.
- Keep one-off page composition near the page; do not promote it to a shared primitive without actual reuse.
- Use semantic tokens for colors and typography. `className` may handle local layout; avoid silently restyling a primitive's contract at every call site.
- Use `cn()` for conditional classes, `gap-*` for stacks, and `size-*` when width equals height.

## Structure

- Keep items inside their group: select, menu, command, and tabs items belong to their matching containers.
- Use the trigger mechanism required by `config.base`: Radix commonly uses `asChild`; other bases may use `render`. Verify current docs.
- Dialog, Sheet, and Drawer need an accessible title, visually hidden when necessary.
- Compose Card through its semantic sections instead of placing everything in CardContent.
- Avatar needs a fallback. Pending buttons compose a Spinner and disabled state; do not assume an `isLoading` prop.

## Existing components over custom markup

Use the installed Alert, Empty, Badge, Separator, Skeleton, Spinner, and toast implementation when they match the role. Do not recreate them as styled `div` or `span` elements.

## Icons and status

- Use `config.iconLibrary`; do not assume Lucide.
- Pass icon components, not string keys. Let the component's CSS size icons unless current source says otherwise.
- Icons inside buttons follow the primitive's current placement API.
- Status meaning needs text or an accessible name, not color alone. Use semantic variants instead of raw palette classes.

Review current component source and documentation when an API detail is version-sensitive.

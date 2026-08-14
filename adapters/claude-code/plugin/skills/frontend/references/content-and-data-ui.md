# Rich content and data-heavy UI

- Preserve the active editor, Markdown pipeline, table, chart, barcode, QR, or file library and its installed major. These libraries carry non-trivial serialization and accessibility contracts.
- Rich-text editors need an explicit stored format, schema evolution, paste rules, upload ownership, and sanitization boundary. Do not treat editor HTML as trusted because the editor produced it.
- Markdown and HTML pipelines must keep parsing, transformation, sanitization, and rendering in a deliberate order. Verify plugin compatibility before changing the pipeline.
- Tables should preserve stable row identity, sorting and filtering ownership, keyboard behavior, empty/loading states, and virtualization when measured volume requires it.
- Virtualized lists and grids need persistent item keys, realistic size estimates or measurements, stable scroll behavior across data changes, and an intentional focus or navigation path for items outside the mounted range.
- Drag-and-drop must not make a business action pointer-only. Preserve focus, an equivalent keyboard path, cancellation, and contextual screen-reader instructions or announcements supported by the active library.
- Node-and-edge editors need stable domain identifiers, explicit ownership of graph data and viewport state, validated connections, and accessible names plus keyboard behavior for actionable elements.
- Charts communicate data rather than decorate it. Preserve units, scales, labels, legends, keyboard or textual alternatives, and meaningful empty/error states.
- Barcode, QR, image, spreadsheet, and archive generation must preserve encoding, dimensions, filenames, memory limits, and failure feedback required by the real workflow.
- Test transformations without rendering when possible; use component or browser tests for interaction, layout-dependent behavior, download behavior, or browser APIs.

Sources:
- Tiptap documentation — https://tiptap.dev/docs/editor/getting-started/overview
- React Markdown security — https://github.com/remarkjs/react-markdown#security
- TanStack Table — https://tanstack.com/table/latest
- TanStack Virtual — https://tanstack.com/virtual/latest/docs/api/virtualizer
- dnd kit accessibility — https://dndkit.com/legacy/guides/accessibility/
- React Flow accessibility — https://reactflow.dev/learn/advanced-use/accessibility
- Recharts — https://recharts.org/en-US/guide

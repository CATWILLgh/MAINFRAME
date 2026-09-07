# Complex UI and browser capabilities

Preserve the active editor, Markdown pipeline, table, chart, graph, virtualization, drag-and-drop, barcode, QR, file, PWA, storage, and realtime libraries. They carry serialization, performance, compatibility, and accessibility contracts beyond their visible markup.

Keep rich content parsing, transformation, sanitization, storage format, paste rules, uploads, and rendering boundaries explicit. Treat editor output and Markdown plugins as untrusted until the owning pipeline establishes otherwise.

Tables, grids, lists, and graphs need stable domain identity, meaningful empty and error states, predictable sorting and filtering, keyboard access, and measured virtualization. Charts require units, labels, scales, legends, and a textual or tabular alternative where users need the data.

For IndexedDB, offline queues, and service workers, define schema and upgrade behavior, source of truth, sync state, conflict handling, retry termination, and recovery. Never imply server success before synchronization is confirmed.

For realtime state, handle disconnect, reconnect, duplicate and out-of-order events, and canonical resynchronization. Events should reconcile the existing authority rather than create a second one.

Check permissions, availability, fallback, cancellation, size, memory, and failure behavior for cameras, scanners, notifications, clipboard, downloads, uploads, storage, and other browser APIs. Verify the actual browser semantics when they are part of the risk.

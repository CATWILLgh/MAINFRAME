# Modern web platform work

Use this method when introducing a browser API, changing browser-dependent HTML/CSS behavior,
diagnosing frontend performance, or modernizing an existing implementation.
Reuse the current framework, component owner, and product contracts.

## Establish support and choose the implementation

- Resolve browser targets from the project's existing Browserslist, build
  targets, support policy, tests, and known clients. Include embedded browsers
  and mobile environments when relevant. Name a material unknown before a
  choice that could remove working behavior.
- Check the exact feature and subfeature against current Baseline/MDN data.
  Reuse verified support evidence while the feature and browser targets stay current.
  Baseline describes interoperability across its browser set. The actual
  product's versions, permissions, secure context, and embedding can differ.
  When targets are unknown, favor widely available features while preserving
  the existing usable path and stating the assumption.
- Prefer a native feature when it meets the contract and reduces maintained
  code, dependencies, or browser work. Evaluate actual benefit before replacing
  a component library or adding a polyfill. A feature's age alone does not
  establish a defect or justify a rewrite.
- Use feature detection and progressive enhancement where support differs.
  Keep the base experience usable. Add a fallback for an identified supported
  environment and give it one clear owner and an exit condition.

## Load the relevant guidance

Search the official Modern Web Guidance catalog for the specific capability,
such as dialog dismissal, container layout, input validation, or input latency.
If results are empty or unrelated, rephrase once with the concrete UI or platform
term; continue without unrelated guides if there is still no match.
Read the matching guide and its compatibility constraints. Preserve intentional
fallbacks and project behavior while applying its relevant recommendations.

Set `mwg_cli` to the prepared executable at
`~/.local/share/mainframe/runtime/bin/modern-web-guidance`, then check
`modern-web-guidance` on `PATH` if the prepared executable is absent. Reuse that
path for search, retrieve, and legacy scans without installing tools or skills,
changing persistent `PATH`, or setting up the project. Disable telemetry and
optional file logging on every call:

```sh
DISABLE_TELEMETRY=1 ENABLE_FILE_LOGGING=false "$mwg_cli" search "dialog light dismiss"
```

Use `retrieve <guide-id>` for the matching result; if output points to a temporary
file, read that guide before removing the lookup file. When the CLI is unavailable,
use official documentation for decision evidence and report any missing scan.

## Preserve the interaction contract

- For dialogs and popovers, preserve focus placement/restoration, keyboard and
  Escape handling, dismissal, nested overlays, scrolling, and accessible naming.
  Check React lifecycle and server/client ownership when using imperative DOM
  methods. Confirm platform support before using newer dismissal attributes.
- For forms, preserve pristine/touched/submitted feedback timing, labels,
  server validation, autofill, and keyboard submission. An Enter keydown action
  must account for active IME composition. Verify the framework's native event
  boundary and relevant browser behavior. Intentional compatibility styles can
  coexist with `:user-invalid` through a supported enhancement path.
- For layout and animation, choose native layout, containment, and scheduling
  only where they preserve sizing, reachability, focus, reduced motion, and
  observable order. Measure before retaining repeated layout reads/writes or
  replacing established virtualization and animation mechanisms.
- For external resources, review immutable CDN asset integrity and CORS at the
  actual loading boundary. Keep secrets and internal URLs out of diagnostics.
  Use the existing [browser safety method](browser-safety.md) for trust changes.

## Modernize within the assigned scope

For an assigned broad legacy-pattern or modernization review, run
`"$mwg_cli" legacy-scan <addressed-file-or-folder> --json` with the same telemetry
controls. A focused feature or component review uses its relevant guide and
interaction checks. Keep scan paths within the assigned scope and use
`--guide <guide-id>` when one capability owns the question.
Review each matching rule's `keepWhen`/`dropWhen` rubric against surrounding code.
The scanner's opportunity list is input to that review.

Prioritize a demonstrated correctness, accessibility, compatibility, performance,
or maintenance improvement. Preserve old behavior where it remains part of the
contract. Apply a coherent change, then verify the affected interaction and
neighboring existing path. A reduced finding count alone cannot prove success.

The edit hook independently checks a curated subset of new IME, validation,
and external-resource findings. Broader modernization and actual browser support
need the checks selected by [frontend testing](testing.md).
The scanner can miss additional resources, framework-bound handlers, or unsafe
code masked by unrelated composition/validation markers. It can also flag
non-text Enter handlers: preserve buttons and links. Use findings as review
candidates; an empty result cannot replace the affected interaction checks.

## Primary references

Adapted using GoogleChrome Modern Web Guidance; the externally installed CLI
retains its [Apache-2.0 license](https://github.com/GoogleChrome/modern-web-guidance/blob/main/LICENSE)
and bundled third-party notices.

- [Modern Web Guidance](https://developer.chrome.com/docs/modern-web-guidance)
  and its [modernization workflow](https://developer.chrome.com/docs/modern-web-guidance/modernization-workflow).
- [Browser Baseline](https://web.dev/baseline) and the target feature's MDN page.
- [Keyboard composition state](https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/isComposing).

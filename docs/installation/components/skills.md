# Adapt skills

Use this guide for every entry under `components.skills`.

## Preserve the complete skill

Copy the complete listed skill directory, including directly referenced
scripts, references, examples, and assets. Preserve stable identity, proactive
trigger semantics, exclusions, relative links, and progressive disclosure.
Nested resources belong to the skill; they are not separate components.

Add only native-required metadata or packaging to the installed copy. Do not
edit the canonical skill to add one product's frontmatter, UI metadata,
permissions, absolute destination, or discovery path.

Resolve these installation markers only in installed copies:

- `{{MAINFRAME_ROOT}}`: the validated absolute repository root;
- `{{CREDENTIALS_INDEX}}`: the absolute centralized non-secret index.

Never leave a marker unresolved or obtain either path through broad filesystem
search.

## Map discovery and permissions

Confirm native global discovery, name constraints, description parsing,
resource loading, permissions, enable/disable state, precedence, and reload.
Reconcile by the canonical skill name. Remove an obsolete owned alias only after
the stable identity is proven.

Do not copy a skill body into agents, root instructions, or commands. Attach or
reference it through the product's native mechanism. If the product exposes only
always-on prompt text, decide whether that preserves the skill's trigger and
progressive-loading contract; otherwise record the limitation.

## Browser route for frontend work

For `mainframe-frontend`, establish an interactive browser verification route.
Prefer a documented native browser that can open the real surface, interact as a
user, observe navigation, and inspect console failures. If the product has no
adequate route, ask the user to choose an already available substitute such as a
project browser harness, Playwright, Browser Use, or agent-browser. Do not
silently install or authorize one.

The receiving project later owns its exact browser command, contour, URL,
permissions, and credential boundary. Until a harmless real interaction and
console observation are possible, report that part of the skill as a capability
gap rather than replacing it with a build or screenshot.

## Verify

Validate native metadata and every relative resource. Prove that native listing
or routing exposes the stable identity and that a harmless invocation loads the
body and a referenced resource. Restart or reindex when current documentation
requires it.

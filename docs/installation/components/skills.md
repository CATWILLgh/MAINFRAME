# Adapt skills

Use this guide for every entry under `components.skills`.

## Preserve the complete skill

Copy the approved resource tree of the listed skill, including directly referenced
scripts, references, examples, and assets. Preserve stable identity, proactive
trigger semantics, exclusions, relative links, and progressive disclosure.
Nested resources belong to the skill; they are not separate components.

Use the maintained shared resource selector. Ignore rules exclude local state
before contents are read, and Git control files stay in the source. For a Git
checkout, reject untracked non-ignored resources until their ownership is
resolved; do not blindly copy them or silently omit a required new resource.
For a downloaded source archive, use its distributed ignore rules without
initializing the source. Reject symlinks and missing tracked resources.

Add only native-required metadata or packaging to the installed copy. Do not
edit the canonical skill to add one product's frontmatter, UI metadata,
permissions, absolute destination, or discovery path.

Resolve these installation markers only in installed copies:

- `{{MAINFRAME_ROOT}}`: the validated absolute repository root;
- `{{CREDENTIALS_INDEX}}`: the absolute centralized non-secret index.

Never leave a marker unresolved or obtain either path through broad filesystem
search. Remove installer-only directions from the delivered runtime body;
retain only duties and failure behavior for the agent loading the skill.

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

During adapter development or explicitly requested acceptance for
`mainframe-frontend`, establish an available global interactive browser
capability without configuring a receiving project.
Prefer a documented native browser that can open the real surface, interact as a
user, observe navigation, and inspect console failures. If the product has no
adequate route, reuse an available substitute within the acceptance task's
authority. Ask only when a new installation, permission, or material configuration
choice is required. Do not silently install or authorize a substitute.

The receiving project later owns its exact browser command, contour, URL,
permissions, and credential boundary. Prove the global capability on a harmless
disposable page with real interaction and console observation. A routine
maintained installation does not open or operate a browser; it leaves this
verification pending. During acceptance, distinguish an unverified route from a
confirmed unsupported capability under [verification.md](../verification.md);
a build or screenshot does not replace the missing behavior.

This establishes adapter capability, not a mandatory matrix for every frontend
edit. At task time the canonical browser-verification method selects observations
for the changed contract: static appearance and interaction have different needs.

## Feedback destination

For `mainframe-harness-feedback`, resolve the canonical destination in the
installed copy and prepare the narrow permission described by the
[integration guide](integrations.md#permissions). Validate report rendering with
a synthetic observation in an isolated temporary directory; never write a fake
report into the real feedback queue or create that queue as installation
residue. A synthetic write validates rendering, not the real destination's
effective permission. Use native permission inspection and a harmless denied
action where appropriate to verify that boundary.

## Verify

Run these discovery and loading checks during adapter development or explicitly
requested acceptance, not as an ordinary maintained-installation tail.

Validate native metadata and every relative resource. Prove that native listing
or routing exposes the stable identity and that a harmless invocation loads the
body and a referenced resource. Restart or reindex when current documentation
requires it.

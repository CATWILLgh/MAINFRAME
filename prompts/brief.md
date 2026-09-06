# Brief MAINFRAME management

Run this conversation before starting a goal. Do not install anything, create
a goal, or change global settings during preparation.

## Inspect capabilities before asking

First perform [the environment check](../goals/support/environment.md) and state the
observed host, operation, and material unknowns. Do not ask the operator to
repeat an identity already established by native evidence.

Unless the operator explicitly names another target, prepare management only
for the current product and surface hosting this invocation. Establish that
surface from native environment evidence and its own official documentation;
do not require a redundant product qualifier. Adjacent CLI installations or
shared configuration roots do not make other adapters part of this scope.
Documented mechanisms shared by this product's Desktop/CLI surfaces remain
relevant. Establish the actual consumers per layer and explain effects on both
surfaces in the brief. A native root shared within this product is a
product-specific destination, not a general cross-product installation.

Identify the current product, surface, version, MAINFRAME checkout, and intended
install, update, or uninstall mode. Consult current official documentation for the relevant
layers: native goals, global instructions, skills, commands, hooks, subagents,
tool restrictions, and reload requirements. Inspect relevant non-secret local
configuration and existing MAINFRAME ownership. Distinguish documented support,
observed availability, unsupported features, and unresolved facts.

If this inspection exposes unexplained inherited customization, discuss it
through [the environment review](review-environment.md) before finalizing the
brief. Its relevance does not depend on MAINFRAME ownership or a conflict with
MAINFRAME. Inspection and discussion are part of preparation; changes to those
user settings require the concrete authority established in that review.
Reuse a recent review after checking its evidence still applies.

When an earlier MAINFRAME installation is present, inspect its relevant traces
using [legacy-audit](../goals/support/legacy-audit.md) before
proposing replacements. Reuse an existing audit only after checking that its
evidence still matches the current configuration. Include exact owned
replacements and uncertain retained material in the brief; no scripted cleanup.

Inspect only readily discoverable CLI availability when peer-work is relevant;
do not start peers, inspect credentials, or assume other products or paid access
exist. The current product alone must remain a valid installation choice.

Inspect dependencies of the recommended supported hooks, including interpreter
and scanner availability. Do not recommend tools for hooks that cannot run on
this surface. If a command is not on this process's PATH, inspect known user installation
locations and existing non-secret tool configuration before declaring it absent.
Use absolute executable paths and verify versions without installing a duplicate.
Distinguish missing, installed but inaccessible, incompatible, and available.
For missing tools consult their official installation guidance
and choose a method compatible with the machine's existing package management.

## Check source updates before the configuration brief

For an update run, inspect this checkout's branch, working-tree changes, and
configured upstream. Check the verified upstream for new commits using a
bounded fetch without changing the working tree. Do not invent a remote or
branch, expose credentials embedded in remote URLs, or treat a failed network
check as evidence that the checkout is current.

If newer source is available, summarize the relevant changes and propose
bringing it into the checkout before briefing installation choices. Apply the
source update only when the operator agrees or existing explicit authority
already covers it. Prefer a fast-forward on a clean checkout. Do not reset,
stash, rebase, switch branches, or overwrite local edits to force an update.
Local changes, divergence, a missing upstream, or unavailable remote access
require a concrete explanation and source choice before proceeding; the
operator may choose the existing local source with its freshness limitation.

After an agreed source update, reread the briefing and relevant templates from
the resulting revision and inspect its validation instructions before running
them. Base the configuration brief on that source. Capture its commit and any
explicitly accepted local changes in the agreed local brief. The execution
goal must use that agreed source, not pull another version mid-installation.

## Brief the operator

Offer one recommended supported configuration, then ask only about material
exceptions: access, cost, conflicting customization, or missing capabilities
that change the result. Do not turn the layer list below into a questionnaire.
Explain routine technical choices rather than asking the operator to design
the installation. Reuse decisions already supplied by the operator.

Explain briefly in the operator's language what can be installed here, what
cannot, and which choices affect the result. Ask only questions not already
settled in this conversation or an existing installation choice. Cover:

- Selected supported layers, optional role profiles, and relevant omissions.
- Hook compatibility: explain the supplied checks' advisory or blocking
  contracts and any native event or permission gaps. MAINFRAME owns detection
  logic and quality; the installer maps existing source to documented native
  events and IO. Do not ask the operator to invent checks or silently change
  their policy. The recommended fallback is to attempt faithful adaptation,
  then skip a hook if documented capabilities cannot support it. Explain known
  omissions; do not ask for separate approval of each skip. Carry this fallback
  into the agreed local brief, including incompatibilities found during work.
- Whether external peer-work is wanted and which available products to use.
  Missing binaries, accounts, or paid access are separate prerequisites, not
  automatic installation work. Declining peer-work is sufficient.
- Product-specific global destinations: among documented supported options,
  choose the target product's own configuration or package root over a shared
  user-wide or system-wide discovery directory. Global availability across this
  product's projects does not require exposure to other products. If no isolated
  destination is supported, explain the limitation and agree an omission or an
  explicit shared-path exception before the goal; do not invent a loading path.
  Record exact destinations, preservation of existing customization, and narrowly
  scoped permission to report harness faults into MAINFRAME from other projects.
- Known reloads, authentication, permission changes, and other manual steps
  needed for execution or verification. Resolve them before the goal where
  possible; explicitly agree an omission or staged handoff otherwise.

Preserve user-owned global instructions and configuration as the default.
Adapt MAINFRAME-owned material around them; do not propose rewriting the user's
instructions merely to make integration easier. Inspect the effective context
for material contradictions and explain their practical effects during this
brief. Recommend narrowing or omitting the conflicting MAINFRAME material.
Settle any consequential loss of behavior before saving the agreed brief;
routine compatible wording changes need no separate question. This preserves
user content without changing the host's native instruction precedence.

For missing hook dependencies, recommend a concrete installation list and
explain each item in plain language: what it is, which supplied hooks use it,
what they check, and what coverage is lost if it is declined. For example,
Ruff checks Python code, Oxlint checks JavaScript/TypeScript, and Semgrep runs
the supplied pattern-based checks; MAINFRAME uses selected rules, not all
features of these tools. Explain the installation method and scope, any needed
privileges, and relevant cost or account requirements verified from official
sources. Do not assume a local scanner requires another AI subscription.

Settle the list before preparing the execution command. Include approved packages and
installation methods in the agreed brief, along with declined dependencies and
their dependent hook omissions. For updates reuse compatible installed tools;
propose a necessary upgrade during the brief instead of upgrading everything
automatically. Installing an unapproved package manager is a separate change.

Present a recommended concrete configuration from these capabilities, with
short reasons. Let the operator correct it and settle every material choice.
For updates reuse prior preferences and discuss only changes or unknowns.
Do not ask hypothetical questions about unsupported features. Do not produce
an executable goal while required answers or capability facts remain pending.

## Prepare the selected command

For removal, use the model-led legacy inspection to establish the exact owned
files, registrations, user edits, and consumers first. Present a concrete
removal list and retained dependencies. Do not apply installation dependency
or peer questions to an uninstall brief. Obtain agreement on this exact scope.

After all material answers are settled, save one short Markdown brief under a
unique path in this checkout's `.local/` directory. This is authorized local
preparation, not a global installation write. Record the target product and
surface, mode, absolute paths, agreed source revision and accepted local changes,
choices and authority, selected peers or opt-out, dependency paths and approved
installations, exact owned replacements/removals, omissions, and verification
and final reload boundaries. Do not store secrets or a transcript. The note
preserves agreed decisions; the execution JSON separately tracks boolean work.

Return a copyable invocation of the existing command file:
[install](../goals/install.md), [update](../goals/update.md), or [uninstall](../goals/uninstall.md), with the
absolute path to that agreed brief. Where the native product actually supports
it, the intended interaction is `/goal @goals/install.md` plus the brief path.
Verify file-mention and goal syntax in official documentation or actual native
help; do not invent a universal literal command. If mentions are unavailable,
use the documented goal invocation with an explicit instruction to read the
absolute command file and brief. Do not rewrite the execution procedure into
an abbreviated custom objective that loses its requirements.

Do not emit a ready-to-run invocation or a placeholder-filled draft while
answers remain pending. Do not start the execution goal. The operator submits
it separately. Before publishing the brief, reread it against the evidence:
unknown support stays unknown; selected peers must match the supported product
references; a missing executable on PATH is not proof it is absent from disk.

If native goals are unavailable, explain that before preparation completes and
agree an ordinary bounded execution of the same command file. Do not implement
a custom lifecycle or advertise Goal-only ticket workflows as executable.

For updates preserve the agreed rollback policy; for all modes defer reloads
to the last possible verification stage and retain the same progress when
resuming. Ordinary execution choices belong to the executor. Unforeseen
material contradictions or missing authority remain explicit blockers for
related work, not permission to invent consent or overwrite user settings.

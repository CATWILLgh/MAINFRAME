# Installation process

Use this process from the MAINFRAME repository root. It is target-neutral; pair
it with the page for the installed product and the guide for the active
component type.

The maintained [Codex procedure](codex-installer.md),
[ZCode procedure](zcode-installer.md), [Antigravity procedure](antigravity-installer.md),
the [MiniMax procedure](minimax-installer.md), and the
[Cline procedure](cline-installer.md) execute the mechanical parts of this
contract. For those routes, run their finite `plan`, `apply`, and `verify`
sequence instead of recreating this manual adapter-development loop. Their
protected ownership receipts record owned files and registrations; the ignored
adaptation state records delivery separately from native verification.

## 1. Resolve the only source root

Use the active workspace or Git boundary. The resolved root must contain the
bootstrap, state example, this guide, and every canonical category named there.
Do not search outside that root for a preferred checkout.

Normalize the absolute root once. Use that value for installed placeholders,
permissions, and local state. A symlinked launch path is not enough: record the
resolved source and the path the native product will actually use.

## 2. Validate the inventory

Treat [ADAPTATION.example.json](../../ADAPTATION.example.json) as exhaustive.
Before global writes:

1. parse the JSON;
2. verify every listed source exists inside the resolved root;
3. verify every direct canonical instruction, skill directory, agent file,
   command file, and hook source is represented exactly once;
4. verify no state, test, documentation, installer, template, archive, cache, or
   local development file is listed;
5. stop on mismatch instead of discovering extra payload from directories.

The repository structural check runs these inventory assertions without global
writes:

```sh
python3 -B -m unittest discover -s tests -p 'test_repository.py'
```

A listed skill owns its approved relative resource tree under the
[skill resource boundary](components/skills.md#preserve-the-complete-skill).
Those nested files are not separate inventory entries. Local ignored files and
Git control files are excluded; an untracked non-ignored resource in a Git
checkout stops planning. Shared credentials are narrower: only the exact listed
helper file is payload.

## 3. Create or reconcile local state

Choose one stable product ID. Verify `ADAPTATION.<product-id>.json` is ignored,
then copy the example only when the file is absent. In a Git worktree, check
the exact path with Git's ignore rules. For a downloaded archive, evaluate the
source's distributed ignore files using private temporary Git metadata with the
source as its work tree; do not initialize or alter the source checkout. Remove
that temporary metadata after the check. The same rule applies to the local
credential index. A file being untracked does not prove it is ignored.

Compare schema, identities, and sources to the current example. Reconcile
entries and reset prior outcomes exactly as the bootstrap specifies. Compare
actual source contents and required resources, not only names, paths, or Git
revision: a source may have changed in place or the checkout may be dirty.
Recheck the effective target after source, dependency, product version,
configuration, or adapter changes; prior `unsupported` outcomes also need this
recheck.

When migrating schema 1, an old `status: installed` is prior verification
evidence only; it never proves that the current installer delivered the current
source to the current target. Re-establish delivery from the current plan and
target transaction. Carry forward an old unsupported outcome only when its
precise limitation still applies.

The schema 2 state file answers only:

- what target and native destinations were resolved;
- whether each exact component's delivery is `pending`, `installed`, or
  `unsupported`;
- whether each non-unsupported component's verification is `pending` or
  `passed`;
- the compact missing step in `next_action`, or a shared step in the top-level
  `next_actions` list;
- an actual product limitation in `reason`, including the affected surface.

Delivery is evaluated against the exact canonical component contract. An
`unsupported` full contract can still have useful behavior represented through a
different native primitive. For hooks, evaluate the alternatives in the
[hook guide](components/hooks.md#keep-native-integration-thin), keeping advice
at a relevant decision point rather than moving it into generic instructions.
Adapters must expose that
separately as `retained_partial_bindings`; they must not relabel partial behavior as
full delivery or discard it because one enforcement guarantee is unavailable.

It is not a journal. Do not accumulate attempts, timestamps, raw diagnostics,
transcripts, telemetry, or secrets. A pending recovery may keep the one essential
non-secret rollback location as its `next_action`; remove that pointer after
recovery.

## 4. Reconstruct the effective target for adapter work

Use three evidence sources together:

1. current official documentation;
2. installed version and command help or application information;
3. harmless runtime observation.

Default to the surface running the request under the
[surface rule](verification.md#desktop-and-cli). Name only explicitly requested
additional surfaces. Record each actual version and
configuration root; do not silently add another product or claim an untested
interface. A declared surface can retain `verification: pending` when a fresh
native probe is unavailable.

Check runtime compatibility with the selected model before starting model-driven
probes. A second executable path is not automatically a second runtime or UI
surface. Plan evidence reuse under the
[smallest proof plan](verification.md#plan-the-smallest-complete-proof) before
spending model calls; keep separate checks for actual differences.

Determine the effective owners and precedence for global instructions, skills,
agents, commands, hooks, integrations, permissions, and settings. Include
environment overrides, managed layers, wrappers, symlinks, and Desktop-versus-
CLI boundaries only when they actually affect this target.

Do not inspect another product's configuration or treat an old MAINFRAME
adapter as evidence of current behavior. Historical material can explain an
intentional behavior only after the current canonical source confirms it.

## 5. Preserve the baseline

Inventory only the target's known relevant global roots. Classify existing
material as:

- native or application-generated;
- user-owned and unrelated;
- current MAINFRAME-owned;
- positively identified obsolete MAINFRAME-owned;
- unknown ownership.

Only current and obsolete MAINFRAME-owned identities are adaptation targets.
Unknown ownership is preserved until resolved. Take a narrow rollback copy just
before changing a concrete file or registration, not a profile-wide archive.
Save the narrow baseline and a short list of operation-owned probe artifacts in
temporary protected files before writes. Tool output and conversational memory
are not durable rollback copies. Keep only what comparison or recovery needs;
use the [recovery guide](problems/rollback-and-recovery.md) to retire these files.

Never read protected credential values. Preserve authentication, session and
history stores, memories, projects, caches, and built-in data even when they are
near a configuration file being changed.

## 6. Adapt one component manually

Use this per-component loop for product-adapter development, explicit native
acceptance, or a target without a maintained installer. It is not an extra tail
for an ordinary maintained installation.

For the next component whose delivery is `pending`:

1. read the component guide and native page;
2. inspect the canonical source and directly required resources;
3. resolve the exact native stable identity, destination, metadata, reload, and
   required dependencies;
4. inspect an existing identity before writing;
5. create an installed copy in temporary staging when transformation is needed;
6. add only target-required metadata, paths, wrappers, and registrations;
7. validate the staged result;
8. prepare its required runtime, permissions, native settings, and any listed
   dependency before activation and proof; an empty support category does not
   prohibit a dependency required by an inventoried component;
9. replace or merge only the owned target atomically where practical;
10. set delivery to `installed` after deterministic target checks pass;
11. during explicit acceptance, reload and run its required checks from
    [verification.md](verification.md), including positive and negative probes
    where the contract requires them, then set verification to `passed`;
12. update the state before opening the next entry.

Identify dependencies during planning and prepare them before activation. Do
not invoke a real workflow or grant broader access just to prove discovery. Read
the component guide for a harmless loading or behavior probe. If proof depends
on a later component, keep its verification `pending` with a compact
`next_action` and revisit it once that dependency is verified.

Prefer pure canonical sources behind thin native wrappers. Never edit canonical
sources to add target frontmatter, event names, permissions, absolute paths, or
configuration syntax.

Repeated installation must converge to one equivalent effective component.
Use stable identities and semantic merge rules. Do not create aliases,
compatibility duplicates, repeated permission rows, or parallel registrations
as a substitute for understanding precedence. Demonstrate convergence by
reconciling the same source and target a second time: the candidate MAINFRAME
content and effective registrations must remain equivalent, with no additional
write needed. Use a bounded dry run or staged comparison where possible. This
checks adaptation, not repeated execution of mutating user workflows.

## 7. Stop or continue correctly

Continue past one `delivery: unsupported` entry when remaining components are
independent. Leave delivery `pending` when installation itself still needs a
specific dependency, authority, or decision. Leave verification `pending` when
delivery completed but required native proof is missing.
Use [verification.md](verification.md#unsupported-is-evidence-not-failure-concealment)
for the evidence threshold; an unavailable probe is not an unsupported product.

Stop before the affected action when:

- a user-owned semantic conflict requires choosing which behavior wins;
- ownership is ambiguous and replacement could destroy unrelated state;
- secret storage or protected access needs a user decision;
- a destructive or externally mutating step lacks authority;
- canonical source or required evidence is unavailable.

Do not stop for routine successful components or ask the user to approve the
documented sequence again.

## 8. Finish and clean up

Run the final evidence matrix and follow
[rollback-and-recovery.md](problems/rollback-and-recovery.md) for cleanup. Only
after a replacement is verified, retire its positively identified obsolete
MAINFRAME-owned predecessor through that sequence, then confirm the current
identity remains discoverable. Hook files remain callable until obsolete
callbacks unload. Preserve the state file and application-owned caches.

Full native acceptance requires every supported row to be delivered and have
`verification: passed`, with no unresolved recovery, plus verified convergence,
preservation, and cleanup. Report delivery, verification, unsupported
limitations, preserved data, cleanup, and exact remaining actions without secret
values or verbose command logs.

A maintained installation pass may finish with a user handoff or missing adapter
proof under [verification.md](verification.md#routine-installation-and-adapter-validation).

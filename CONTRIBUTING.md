# Contributing

Keep changes small, evidence-based, and inside the agreed scope. Preserve
unrelated work, private data, and local agent configuration.

## Canonical design

- Keep one canonical owner for every rule or capability.
- Keep canonical components independent of a particular agent product,
  consumer project, role, subagent topology, or invocation path.
- Put product-specific paths, frontmatter, permissions, registrations, event
  schemas, and wrappers in the maintained product installer and its generated
  target copies. Keep them out of canonical component bodies.
- Make repeated adaptation and installation update the same components without
  duplicate files, registrations, permissions, hooks, or index entries.
- Keep reusable methods in skills, bounded execution roles in agents, explicit
  user workflows in commands, and deterministic event reactions in hooks.
- Write agent-facing canonical material in clear English. Use direct
  instructions and state observable triggers, boundaries, and failure behavior.
- Do not add telemetry, permission-audit storage, committed generated exports, bundled
  product copies, transcripts, or permanent execution logs.

## Agent-facing content

Keep always-loaded instructions small and limited to rules that affect most
work. Put reusable workflow method in a skill, explicit user workflows in
commands, and product-specific representation in the maintained adapter.

- Give each skill a short description that names its actual trigger. Avoid
  broad neighboring keywords and repeated urgency that can route unrelated
  work into the skill.
- Use a skill entrypoint as a small router when it covers several workflows.
  Link only the relevant supporting references, scripts, and assets instead of
  loading the full domain for every invocation.
- State outcomes, decision boundaries, completion evidence, and material
  failure behavior. Require a fixed itinerary only when ordering is necessary
  for correctness or current runtime evidence shows that a looser method fails.
- Make permission specific to the workflow and reuse authority already supplied
  by the caller. Do not add precautionary approval stops for ordinary safe work.
- Keep verification proportionate to the changed risk. Reserve broad suites and
  behavioral campaigns for the risks they can actually prove.
- Review skill descriptions, root instructions, roles, and task prompts together
  for duplication and conflict. Preserve instructions required by supported
  lighter models; do not optimize the repository for one model by name.

These rules follow OpenAI's current guidance for
[skills and prompts](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra).
Apply them when changing agent-facing content; do not add the article or this
maintainer guidance to the installed runtime payload.

## Maintained installation code

[install.py](install.py) is the single entrypoint. Keep shared file ownership and
transaction mechanics in [installer/core.py](installer/core.py), shared inventory, instruction merging, and delivery state in [installer/shared.py](installer/shared.py)
and [installer/state.py](installer/state.py), and native decisions in [installer/codex.py](installer/codex.py)
and native modules such as [installer/zcode.py](installer/zcode.py),
[installer/antigravity.py](installer/antigravity.py), and
[installer/minimax.py](installer/minimax.py). Extract more shared code only when
another implemented product actually uses it. Canonical texts and
detectors remain single sources; never copy their bodies into the installer.

Changes to native packaging, configuration, or lifecycle behavior require tests
against disposable homes, including update, convergence, foreign-file
preservation, interrupted writes, and removal. Use actual native probes for
discovery and event claims. An installer ownership receipt is bounded recovery
and reconciliation metadata, not a component status or activity log.

## Delivery boundary

[ADAPTATION.example.json](ADAPTATION.example.json) is the complete product
inventory. Update it whenever an installable component is added, renamed,
moved, or removed.

Only listed sources are product payload. A listed skill includes its required
relative resources. A listed hook includes only its canonical source file, not
`hooks/README.md` or `hooks/tests/`. The shared credential component installs
only `shared/credentials/mainframe-secret`; its installer, template, local
index, and tests remain repository support.

A listed hook may require the maintained native transport accompanying its
binding. Install only that support file and the binding's canonical detector;
this does not make the rest of the installer directory product payload.

Do not make root documentation, development checks, `.agents/`, archives,
tickets, examples, caches, or ignored state installable. Do not recover a
component from an archive merely because it existed before.

Root `AGENTS.md`, `CLAUDE.md`, and `docs/installation/` are tracked repository
control-plane support. Keep them useful to an installer opening this repository,
but never list or copy them as global product payload. `CLAUDE.md` should remain
a thin native bridge to the shared root guidance rather than a second body of
instructions.

## Installation documentation

[docs/installation/README.md](docs/installation/README.md) is the canonical
guide entry. Keep documentation ownership narrow:

- change `ADAPT-MAINFRAME.md` only for the fixed trajectory, state loop,
  component order, stop conditions, or completion boundary;
- change a component guide for cross-product adaptation mechanics;
- change a dated native page when current official product behavior changes;
- change the maintained product module and its procedure together when its
  supported native mapping or executable installation behavior changes;
- change a problem note for a repeatable bounded recovery case;
- change canonical component source and tests for behavior itself.

When an inventory, component contract, native mechanism, or verification
requirement changes, update its documentation owner in the same change. Recheck
native pages against current official sources and the installed product; do not
turn them into generated adapters or copy volatile product syntax into the
bootstrap.

## Security and data

- Never commit secret values, credential stores, private keys, session data, or
  protected user content.
- Keep the credential index limited to non-secret descriptions and references.
- Treat hooks as defense in depth, not as authority or a complete sandbox.
- Keep guards deterministic and block only positively recognized dangerous
  conditions or command forms explicitly forbidden by the canonical contract.
  Operational failures must not hard-lock unrelated work.
- Report a security problem through [SECURITY.md](SECURITY.md).

## Validate the change

Select checks for the changed surface. Documentation and instruction-only edits
need link/inventory checks and review of the affected decision boundaries, not
unrelated executable suites. The source-structure check is:

```sh
python3 -B -m unittest discover -s tests -p 'test_repository.py'
git diff --check
```

For executable changes, run the affected tests from `tests/` (installer and
adapter contracts), `hooks/tests/` (detectors), or `shared/credentials/tests/`
(credential helper). Broaden to the relevant suite for a shared contract change;
reserve all suites together for CI or assigned full verification. One-shot tests
using disposable fixtures are authorized; inspect an unknown command's side
effects before running it. Fix failures caused by the change and rerun affected checks without
requesting approval at each step.

Validate changed skills with an appropriate skill validator. Review their
triggers and realistic decision boundaries; use an independent behavioral probe
only when complexity or risk justifies it. Run a harmless representative probe
for changed executable behavior. The source-structure check above covers relative
links, exact inventory ownership, and exclusion of repository-only payload.

Structural checks prove only source structure. Native discovery, permissions,
event delivery, blocking behavior, Desktop behavior, and CLI behavior require
separate adapter tests on the requested surface. These are development and
acceptance checks; an ordinary installation follows the bounded product
procedure without replaying this development suite or starting model probes.

When handing off a change, state what changed, what was tested, what the tests
prove, and what remains unverified. Do not commit, push, publish, or change
external systems unless the current task authorizes that action.

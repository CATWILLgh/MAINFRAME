# Contributing

Keep changes small, evidence-based, and inside the agreed scope. Preserve
unrelated work, private data, and local agent configuration.

## Canonical design

- Keep one canonical owner for every rule or capability.
- Keep canonical components independent of a particular agent product,
  consumer project, role, subagent topology, or invocation path.
- Put product-specific paths, frontmatter, permissions, registrations, event
  schemas, and wrappers only in installed adapter copies.
- Make repeated adaptation and installation update the same components without
  duplicate files, registrations, permissions, hooks, or index entries.
- Keep reusable methods in skills, bounded execution roles in agents, explicit
  user workflows in commands, and deterministic event reactions in hooks.
- Write agent-facing canonical material in clear English. Use direct
  instructions and state observable triggers, boundaries, and failure behavior.
- Do not add telemetry, permission-audit storage, generated adapters, bundled
  product copies, transcripts, or permanent execution logs.

## Delivery boundary

[ADAPTATION.example.json](ADAPTATION.example.json) is the complete product
inventory. Update it whenever an installable component is added, renamed,
moved, or removed.

Only listed sources are product payload. A listed skill includes its required
relative resources. A listed hook includes only its canonical source file, not
`hooks/README.md` or `hooks/tests/`. The shared credential component installs
only `shared/credentials/secret`; its installer, template, local index, and
tests remain repository support.

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
- Keep guards deterministic and fail only on positively recognized dangerous
  conditions. Operational failures must not hard-lock unrelated work.
- Report a security problem through [SECURITY.md](SECURITY.md).

## Validate the change

Use the smallest checks that cover the changed risk. At minimum:

```sh
python3 -m json.tool ADAPTATION.example.json >/dev/null
PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s hooks/tests -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s shared/credentials/tests -p 'test_*.py'
git diff --check
```

Also validate every changed skill with an appropriate skill validator, check
relative documentation and component links, and run a harmless representative
probe for changed executable behavior. Verify that every inventory source
exists, every direct skill, agent, command, instruction, and hook is represented
exactly once, and no repository-only file entered the product inventory.

Structural checks prove only source structure. Native discovery, permissions,
event delivery, blocking behavior, Desktop behavior, and CLI behavior require
separate adapter tests.

When handing off a change, state what changed, what was tested, what the tests
prove, and what remains unverified. Do not commit, push, publish, or change
external systems unless the current task authorizes that action.

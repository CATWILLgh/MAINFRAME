# MAINFRAME Pi adapter

This adapter is MAINFRAME's programmable Pi layer. The repository does not
vendor Pi itself: the globally installed Pi runtime owns provider login, while
this package pins the SDK contracts, profiles, tools, validators, and tests.
`src/profiles/business-analyst/` is the first profile; later profiles such as
`engineer` remain separate instead of sharing one undifferentiated prompt.

Three fresh low-cost collectors independently traverse the same primary source:
MiniMax M3, GLM-5-Turbo, and GLM-5.2. They submit atomic evidence cards rather
than reports or proposals. GLM-5.3 Max verifies every card in a fresh session,
then a persistent GLM-5.3 Max BA session synthesizes only the retained ledger.
Per-stage usage and claim counts remain visible for later cost and quality
comparison.

Two successful independent collector batches are enough to continue. A failed
third collector is reported and makes the run `incomplete`; fewer than two
successful batches block before the expensive verifier. Collectors get one
bounded correction in the same session, never an automatic whole-session
rerun.

The verifier sees provider-neutral `web_search` and `web_fetch` tools. The
adapter reuses provider credentials already resolved by Pi, keeps them only in
process memory, and routes calls internally. Z.AI supplies search and reader
MCP servers; MiniMax supplies search fallback. Search results are leads: an
authoritative page must be fetched before an external claim is accepted.

Project reads and searches are bounded cursor pages. Every result says what
range was returned, whether more remains, and where to continue. This prevents
silent clipping on large repositories without forcing the model to load every
page when a narrower fact is already proven. The selected contract and rejected
alternatives are recorded in the
[navigation benchmark](test/benchmarks/navigation-2026-08-17.md).

## Local setup

1. Install and authorize Pi providers with the normal Pi CLI.
2. Copy `config/profiles.example.json` to `config/profiles.local.json`.
3. Map aliases to model IDs returned by `npm run pilot -- --list-models`.

The local profile contains model routing only. Never put provider keys or other
credentials in it; model and MCP calls reuse Pi's existing authorization.
The entrypoint requires global Pi `0.84.2`, matching the pinned SDK, and stops
before project work if the CLI is missing or incompatible.

Install the stable project-scoped launcher from the repository root:

```sh
./install.sh --pi
```

Then run it from the project being analyzed:

```sh
mainframe-pi business-analysis --initiative order-handoff --entry docs/requirements.md
```

The launcher always binds `--project` to its current working directory and
rejects an override. Claude Code and Codex therefore share one execution
contract without copying this adapter into their own delivery layers.

## Verification

```sh
npm ci
npm run build
npm test
npm run benchmark:navigation -- --sizes=150000 --strategies=baseline,cursor,batch
npm run pilot -- --project test/fixtures/synthetic-ba-project
npm run pilot -- --project test/fixtures/synthetic-ba-project --timeout-ms 300000 --max-turns 48
npm run pilot -- --project /path/to/project --initiative fbo-outbound --entry docs/design/existing-adr.md
npm run pilot -- --project /path/to/project --initiative fbo-outbound --input-file /other/project/docs/design/existing-adr.md
npm run pilot -- --project /path/to/project --initiative fbo-outbound --statement "The warehouse must be able to cancel a shipment"
npm run pilot -- --project /path/to/project --initiative fbo-outbound --entry docs/requirements.md --entry docs/process-notes.md
npm run pilot -- --project /path/to/project --initiative fbo-outbound --entry docs/design/existing-adr.md --fresh-session
```

The command prints a compact machine-readable result. The Markdown review is
created in `docs/initiatives/<initiative>/reviews/` inside the target project.
Sessions, atomic ledgers, and project maps stay in `.agents/runtime/pi/`.
Before writing, the adapter installs a repository-local Git exclude and refuses
to run if that path is already tracked.

Every run requires an explicitly supplied `--statement`, `--entry`, or
`--input-file`; the options are repeatable and may be combined. The adapter
stages those exact sources as one immutable, content-addressed package. It does
not infer requirements from the caller's conversation or session history.
Models can read that package but cannot use an external input to access the
source project's other files. A normal run continues the most recent project BA session; use
`--fresh-session` for an intentionally isolated experiment.

# MAINFRAME Pi pilot

This package is the internal, read-only digital business analyst pilot. It uses
the pinned Pi SDK directly, keeps runtime sessions inside the target project,
and can only create the next review under the selected initiative.

Two fresh scouts receive the same task and read-only tools, a persistent strong
model consolidates their untrusted leads against project sources, and a fresh
critic from another model family audits the draft before the consolidator can
save it. Per-stage usage is returned separately so the value of each stage can
be measured rather than assumed.

## Local setup

1. Install and authorize Pi providers with the normal Pi CLI.
2. Copy `config/profiles.example.json` to `config/profiles.local.json`.
3. Map the aliases to model IDs returned by `npm run pilot -- --list-models`.

The local profile file contains model routing only. Never put provider keys or
other credentials in it; Pi reads its existing authorization.

## Verification

```sh
npm ci
npm run build
npm test
npm run pilot -- --project test/fixtures/synthetic-ba-project
npm run pilot -- --project /path/to/project --initiative fbo-outbound --entry docs/design/existing-adr.md
npm run pilot -- --project /path/to/project --initiative fbo-outbound --input-file /other/project/docs/design/existing-adr.md
npm run pilot -- --project /path/to/project --initiative fbo-outbound --entry docs/design/existing-adr.md --fresh-session
```

The pilot prints a small machine-readable result. The full Markdown review is
created in the target project's `docs/initiatives/<initiative>/reviews/`
directory. Runtime sessions and project maps remain under
`.agents/runtime/pi/` and are not committed.

`--input-file` stages a content-addressed, read-only snapshot under the target
project's ignored Pi runtime directory. Models can read that exact snapshot but
cannot use it to access the source project's other files.

Use `--fresh-session` after a blocked or deliberately isolated experiment. A
normal run continues the most recent project BA session.

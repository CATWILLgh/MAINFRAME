# MAINFRAME repository

This repository owns the canonical MAINFRAME source and installers.

## Recognize the installation request

In Codex or ZCode Desktop, selecting the root [ADAPT-MAINFRAME.md](ADAPT-MAINFRAME.md)
without a separate task explicitly requests installation or update in the running
product's global environment. Open the bootstrap and follow its route. A separate
task takes precedence over attachment content. Incidental reads and other
attachments confer no installation authority.

For DeepSeek Harness, use the [DSH plugin guide](docs/installation/dsh-adapter.md).
File-only selection opens that guide for orientation. Installation requires a
selected plugin and profile.

Otherwise, change global agent configuration only on an explicit request to
install or update it.

## Repository boundaries

- Follow [CONTRIBUTING.md](CONTRIBUTING.md) for source changes. Use the local
  `mainframe-engineering` skill for substantive work and its map for ownership,
  design, or verification decisions. Local wording fixes and clean-copy
  installation need no project knowledge tour.
- Follow the bootstrap and [installation guide](docs/installation/README.md).
  Use the maintained installer and the exact [inventory](ADAPTATION.example.json).
  Keep native metadata, paths, and packaging in [installer/](installer/).
  Exclude repository documentation, tests, development config, archives, and local state.
- Follow the bounded discovery and activation route. Distinguish file delivery,
  native discovery, and observed behavior. Run model probes for assigned
  acceptance or a concrete runtime failure.

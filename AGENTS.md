# MAINFRAME repository

This repository is the canonical MAINFRAME source and installation workspace.

- Do not install or change global agent configuration unless the current user
  request explicitly asks to install or update MAINFRAME.
- For installation or update, follow [ADAPT-MAINFRAME.md](ADAPT-MAINFRAME.md)
  and the canonical [installation guide](docs/installation/README.md).
- Treat [ADAPTATION.example.json](ADAPTATION.example.json) as the exact
  installable inventory.
- Adapt installed copies to the current product. Do not add product-specific
  metadata or paths to canonical sources.
- Do not install repository documentation, tests, development configuration,
  archives, or local state.
- Verify native discovery and behavior. Copying files is not completion.
- For changes to MAINFRAME itself, follow
  [CONTRIBUTING.md](CONTRIBUTING.md).

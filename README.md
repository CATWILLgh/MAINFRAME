# MAINFRAME

MAINFRAME is a product-neutral set of instructions, skills, agents, commands,
and hooks for coding agents. The repository stores one canonical version of
each component. The agent installing MAINFRAME adapts copies to the current
native format of its own product.

MAINFRAME does not ship prebuilt adapters. Product paths, metadata,
permissions, registrations, and compatibility code belong only to installed
copies.

## Verified baselines

Each badge shows the lowest version that has actually run the relevant
MAINFRAME checks in this rebuild as of 2026-09-07. It is verification evidence,
not a claim that older releases are incompatible or that every newer release is
automatically supported.

Core runtimes used by the canonical sources and repository checks:

![Python: minimum tested 3.9.6](https://img.shields.io/badge/Python-min%20tested%203.9.6-3776AB?logo=python&logoColor=white)
![Bash: minimum tested 3.2.57](https://img.shields.io/badge/Bash-min%20tested%203.2.57-4EAA25?logo=gnubash&logoColor=white)
![Git: minimum tested 2.39.5](https://img.shields.io/badge/Git-min%20tested%202.39.5-F05032?logo=git&logoColor=white)
![Node.js: minimum tested 25.9.0](https://img.shields.io/badge/Node.js-min%20tested%2025.9.0-5FA04E?logo=nodedotjs&logoColor=white)

Optional runtime support used by specific hook capabilities:

![ripgrep: minimum tested 15.2.0](https://img.shields.io/badge/ripgrep-min%20tested%2015.2.0-CC342D)
![Ruff: minimum tested 0.15.15](https://img.shields.io/badge/Ruff-min%20tested%200.15.15-D7FF64)
![Oxlint: minimum tested 1.67.0](https://img.shields.io/badge/Oxlint-min%20tested%201.67.0-7C3AED)
![Semgrep: minimum tested 1.164.0](https://img.shields.io/badge/Semgrep-min%20tested%201.164.0-00A9A5)
![Fallow: minimum tested 2.92.1](https://img.shields.io/badge/Fallow-min%20tested%202.92.1-6B7280)

Python runs the canonical hooks and Python reconnaissance; Bash runs the
credential helper; Git supports repository-aware safety; Node.js runs the
TypeScript and React reconnaissance scripts. The second group is not required
for every installation: an adapter installs or reuses each analyzer only when
its corresponding hook is supported.

### Adapter acceptance

No adapter is marked verified yet. Add an adapter badge only after installation
from a clean repository copy proves native discovery and behavior. Each badge
must identify the agent product version, tested interface (`CLI`, `Desktop`, or
both), and model. Different verified combinations receive separate badges; a
source validation or successful installation alone is not enough.

## Install or update

MAINFRAME has one supported installation path:

1. Clone or update this repository.
2. Open this repository itself as the current project in the agent product you
   want to configure.
3. Give the agent [ADAPT-MAINFRAME.md](ADAPT-MAINFRAME.md) and ask it to
   complete the installation.

The agent checks its current official documentation, installs every applicable
component into its own global environment, and verifies native discovery or
behavior. It records progress in an ignored
`ADAPTATION.<product-id>.json` copied from
[ADAPTATION.example.json](ADAPTATION.example.json). Repeating the same process
updates one effective installation instead of creating duplicates.

The tracked root [AGENTS.md](AGENTS.md) tells compatible agents how to treat this
repository as the product and installation workspace. [CLAUDE.md](CLAUDE.md) is
a minimal Claude Code bridge to the same guidance. The complete maintained
installation route starts at
[docs/installation/README.md](docs/installation/README.md). These files ship
with the repository so a zero-context installer can orient itself, but they are
repository control-plane support rather than globally installed payload.

Do not run the installation from another project. MAINFRAME is installed
globally; project-specific configuration is created later through installed
capabilities such as `project-skill`.

## Product payload

[ADAPTATION.example.json](ADAPTATION.example.json) is the complete list of
installable component identities and canonical sources.

| Source | Installed result |
| --- | --- |
| [instructions/global.md](instructions/global.md) | One MAINFRAME-owned section in the product's global instruction |
| Listed directories under [skills/](skills/) | Native global skills, including their required references, scripts, and assets |
| Listed files under [agents/](agents/) | Native global agent or subagent roles |
| Listed files under [commands/](commands/) | Explicit user commands or the closest supported native equivalent |
| Listed Python files under [hooks/](hooks/) | Native event bindings around the canonical hook behavior |
| [shared/credentials/secret](shared/credentials/secret) | The global `secret` helper when a compatible command is not already present |

Hook analyzers such as Ruff, Oxlint, Semgrep, or Fallow are direct runtime
support for listed hooks, not separate MAINFRAME components. An adapter reuses
or installs them only when the hook requires them and the target product can
support the behavior.

Nothing else is product payload. In particular, the following stay in this
repository and are never installed globally:

- root `AGENTS.md` and `CLAUDE.md`, this README,
  [ADAPT-MAINFRAME.md](ADAPT-MAINFRAME.md), the adaptation JSON, the canonical
  [installation guide](docs/installation/README.md),
  [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
  [LICENSE](LICENSE);
- hook documentation and tests;
- `shared/credentials/install.sh`, the credential-index template, the ignored
  local credential index, and credential-helper tests;
- local development agent state under `.agents/`, archives, project tickets,
  caches, generated files, and Git history.

The installer must stop on an inventory mismatch. It must not discover extra
payload from directory contents, archives, older adapters, or ignored files.

## User commands

The installed product exposes these stable command identities through its
closest explicit user-command mechanism:

| Command | Purpose |
| --- | --- |
| [mainframe-init](commands/mainframe-init.md) | Establish ownership and verification for one user-facing coordinating session |
| [project-skill](commands/project-skill.md) | Initialize, update, or extend the current project's evolving skill |
| [tickets-find](commands/tickets-find.md) | Find and record current project problems from scratch |
| [tickets-refine](commands/tickets-refine.md) | Expand the project's existing ticket queue |
| [tickets-implement](commands/tickets-implement.md) | Implement every ready project ticket one at a time |
| [tickets-verify](commands/tickets-verify.md) | Independently verify every eligible implemented ticket |

Exact slash syntax and delayed loading depend on the installed product. The
adapter records any unsupported or degraded capability instead of claiming
equivalence.

## Safety and privacy

Installation preserves unrelated global configuration, authentication,
history, sessions, memories, projects, and user-owned instructions. Secret
values are never part of this repository or its adaptation state. MAINFRAME
does not include telemetry collectors or a permanent activity log.

Canonical source validation does not prove that a product discovered or ran an
installed component. Each adapter must verify Desktop and CLI separately when
their configuration or runtime differs.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and security
boundaries, [CONTRIBUTING.md](CONTRIBUTING.md) for change rules, and
[LICENSE](LICENSE) for the MIT license.

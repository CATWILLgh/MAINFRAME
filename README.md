# MAINFRAME

MAINFRAME is a product-neutral set of instructions, skills, agents, commands,
and hooks for coding agents. The repository stores one canonical version of
each component. A maintained installer generates native copies from these sources
and a small product-specific mapping. Maintained implementations target Codex,
ZCode Desktop, Antigravity Desktop 2.0, and MiniMax Code Desktop. Other products
require separately assigned adapter development.

Canonical content stays product-neutral. Native packaging, registration,
lifecycle handling, and installation checks live under [installer/](installer/).
Generated product copies are not maintained as separate source trees.

## Verified baselines

Each badge shows the lowest version that has actually run the relevant
MAINFRAME checks in this rebuild as of 2026-09-07. It is verification evidence,
not a claim that older releases are incompatible or that every newer release is
automatically supported.

Runtimes verified for the canonical components:

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

The maintained installer requires Python 3.11 or newer and is tested locally on
Python 3.13.0. CI is configured to run its repository tests on Python 3.12; that
run must pass before publication. The older Python badge above applies to
the separately tested canonical components, not the new installer.

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

The [Codex](docs/installation/codex-installer.md),
[ZCode Desktop](docs/installation/zcode-installer.md),
[Antigravity Desktop 2.0](docs/installation/antigravity-installer.md), and
[MiniMax Code Desktop](docs/installation/minimax-installer.md) installers
implement packaging, ownership, updates, recovery, and safe hook removal for
their documented versions. The installation-procedure trials below do not
establish full native acceptance; each adapter records its own exact limitations.

### Installer model trials

Codex **Desktop 0.153.4**, **2026-09-08**. One fresh task per tested combination,
using the same source and file-only request after removing the previous
MAINFRAME installation. Models are ordered from lightest to strongest;
reasoning levels with the same observed outcome are grouped.

| Model | Reasoning | Result |
| --- | --- | --- |
| `gpt-5.3-codex-spark` | low, medium, xhigh | Partial: correct files; instruction review skipped |
| `gpt-5.3-codex-spark` | high | Failed: installation never started |
| `gpt-5.6-luna` | low | Passed |
| `gpt-5.6-terra` | low, medium, high, xhigh | Passed |
| `gpt-5.6-sol` | — | Not tested; expected to pass |
| `gpt-6-astra` | — | Not tested; expected to pass |

Passed covers file delivery, preservation, convergence, and required instruction
review. Full adapter acceptance is tracked separately. These are single-run
results; the Sol/Astra expectations are untested assumptions.

## Install or update

MAINFRAME has one supported installation path:

1. Clone or update this repository.
2. Open this repository itself as the current project in the agent product you
   want to configure.
3. Send [ADAPT-MAINFRAME.md](ADAPT-MAINFRAME.md) to the agent on its own, as an
   attachment or file reference. No additional prompt is needed.

For Codex, ZCode Desktop, Antigravity Desktop 2.0, and MiniMax Code Desktop, the agent runs [install.py](install.py), reviews existing instruction
semantics when required by the plan, verifies the delivered structure, and checks
available discovery evidence on the current surface. If activation or reload
requires user action, it leaves a short handoff and records the remaining gaps.
It does not regenerate installation scripts or start a model session for each
file. The installer does not change product versions or choose a model.

The agent checks the applicable native contract, installs every applicable
component into its own global environment, and records which discovery and
behavior requirements are proven on the requested surface. Delivery and native verification are recorded separately. Missing native evidence
keeps verification pending; ordinary installation does not run a full adapter acceptance
campaign. It records progress in an ignored
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
capabilities such as `mainframe-project-skill`.

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
| [shared/credentials/mainframe-secret](shared/credentials/mainframe-secret) | The global `mainframe-secret` helper when a compatible command is not already present |

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
- [install.py](install.py) and installer development modules; only the small
  native hook transport required by a listed hook enters its installed binding;
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
| [mainframe-project-skill](commands/mainframe-project-skill.md) | Initialize, update, or extend the current project's evolving skill |
| [mainframe-tickets-find](commands/mainframe-tickets-find.md) | Find and record current project problems from scratch |
| [mainframe-tickets-refine](commands/mainframe-tickets-refine.md) | Expand the project's existing ticket queue |
| [mainframe-tickets-implement](commands/mainframe-tickets-implement.md) | Implement every ready project ticket one at a time |
| [mainframe-tickets-verify](commands/mainframe-tickets-verify.md) | Independently verify every eligible implemented ticket |

Exact slash syntax and delayed loading depend on the installed product. The
adapter records any unsupported or degraded capability instead of claiming
equivalence. In ZCode, send `/mainframe-project-skill` as its own command. `$mainframe-project-skill`
would select a skill, while `/goal /mainframe-project-skill` passes the latter text to the
built-in goal command instead of invoking it.

## Safety and privacy

Installation preserves unrelated global configuration, authentication,
history, sessions, memories, projects, and user-owned instructions. Secret
values are never part of this repository or its adaptation state. MAINFRAME
does not include telemetry collectors or a permanent activity log.

Canonical source validation does not prove that a product discovered or ran an
installed component. Installation targets the surface running the request.
Desktop and CLI need separate evidence only when the user requests both;
ordinary installation does not start the other interface or repeat adapter
acceptance tests.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and security
boundaries, [CONTRIBUTING.md](CONTRIBUTING.md) for change rules, and
[LICENSE](LICENSE) for the MIT license.

# MAINFRAME

MAINFRAME provides reusable instructions, skills, agents, commands, and hooks
for coding agents. Each component has one product-neutral source. Maintained
adapters translate that source into the native layouts of **Codex** and
**ZCode Desktop**.

This repository also develops four separate **DeepSeek Harness (DSH)** plugins.
Each is built as its own package and installed into a DSH profile through DSH's
native manager. [DSH plugin guide](docs/installation/dsh-adapter.md)

[![GitHub Actions on main](https://github.com/CATWILLgh/MAINFRAME/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/CATWILLgh/MAINFRAME/actions/workflows/ci.yml?query=branch%3Amain)
![Installer Python 3.11 or newer](https://img.shields.io/badge/installer%20Python-3.11%2B-3776AB?logo=python&logoColor=white)
![GitHub CI Python 3.12](https://img.shields.io/badge/GitHub%20CI%20Python-3.12-3776AB?logo=python&logoColor=white)

## Where MAINFRAME installs

The versions below identify the latest full delivery mapping maintained here
for each surface. The native guides record earlier and scoped-update versions.
Delivery checks establish file and configuration convergence. Native discovery,
permissions, event execution, and model behavior require separate evidence on
the requested surface.

| Product | Full delivery mapping | Other maintained paths |
| --- | --- | --- |
| [Codex Desktop](docs/installation/codex-installer.md) | Engine `0.165.0-alpha.1.2` | `0.166.0-alpha.5.1` and `0.167.0-alpha.3.2` support skill-only updates of an existing installation. |
| [Codex CLI](docs/installation/codex-installer.md) | Engine `0.153.4` | Read-only native discovery is available on the inspected CLI. |
| [ZCode Desktop](docs/installation/zcode-installer.md) | Build `3.17.1.9553` | Build `3.17.2.9661` supports skill-only updates of an existing installation. |

Some hooks have narrower native bindings. Codex retains partial shell guards
where the host omits the actual tool working directory, and both adapters
retain useful code-quality and Fallow behavior within their event limits.
ZCode's installed hook bindings cover the primary runtime. The installer reports
unsupported full contracts and retained partial bindings. [Codex mapping](docs/installation/native/codex.md) · [ZCode mapping](docs/installation/native/zcode.md)

## Install or update MAINFRAME

Use the checked-out repository as the open project in the product you want to
configure. Run the maintained installer on macOS or Linux with Python 3.11 or
newer and Git.

1. Clone or update this repository.
2. Open this repository in Codex or ZCode Desktop.
3. Send [ADAPT-MAINFRAME.md](ADAPT-MAINFRAME.md) by itself as an attachment or
   file reference. The project's [AGENTS.md](AGENTS.md) defines this invocation.
4. Follow the returned activation handoff. Codex may require reviewing and
   trusting new hooks. ZCode asks you to refresh Skills when skill files changed.
   Use a new chat for discovery on the same surface.

The agent uses the maintained [installer](install.py) to plan, apply, and
verify. It resolves actual instruction conflicts before applying and records
delivery separately from native behavior in an ignored
`ADAPTATION.<product-id>.json`. Use the same route to update an existing
installation on a supported runtime. The per-product procedures also cover
scoped Desktop updates, hook controls, removal, and recovery. [Installation guide](docs/installation/README.md)

The installer prepares the analyzers needed by supported hook bindings and
the shared OpenSpec CLI when delivering its skill. It reuses compatible tools
or provisions their pinned distributions before activation. Some provisioning
paths need Node.js and npm. [Shared runtime and provisioning](docs/installation/components/integrations.md)

## What MAINFRAME delivers

The [inventory](ADAPTATION.example.json) lists 52 MAINFRAME components and
four DSH packages. Each global adapter delivers the MAINFRAME components its
native mapping supports.

| Canonical source | Native result |
| --- | --- |
| [Global instruction](instructions/global.md) | One owned section of the product's user-level instructions |
| [25 skills](skills/) | Global skill packages with their approved references, scripts, and assets |
| [7 roles](agents/) | Native agent or subagent profiles |
| [8 commands](commands/) | Explicit workflows projected into the product's command mechanism |
| [10 hooks](hooks/) | Canonical detectors bound to supported native events |
| [Credential helper](shared/credentials/mainframe-secret) | A compatible `mainframe-secret` command and integration with the non-secret index |

Root project instructions, source docs, installer modules, tests, local state,
and archives stay in the repository. The adapter delivers only the small
native transport required by a supported hook. [Payload boundary](docs/installation/README.md#repository-and-payload-boundary)

## Use MAINFRAME in a project

Open the project where you want the work done. Describe the task to select a
relevant skill, such as [testing](skills/mainframe-testing/SKILL.md),
[React frontend work](skills/mainframe-frontend/SKILL.md), or
[shipped-software analysis](skills/mainframe-leanrea/SKILL.md). The native role
profiles are available through the host's delegation mechanism on supported
surfaces. Hook behavior follows the host's supported events and activation state.

Invoke explicit workflows using the product's command mechanism. Codex
projects them as explicit-only skills. ZCode exposes slash commands and uses
a separate ticket-finder skill projection for noninteractive automations.
For example, invoke `$mainframe-project-skill` explicitly in Codex or send
`/mainframe-project-skill` as its own ZCode command to create or update the
current project's reusable skill. [Codex commands](docs/installation/native/codex.md#explicit-commands) · [ZCode commands](docs/installation/native/zcode.md#skills-and-explicit-commands)

| Command | Purpose |
| --- | --- |
| [todo](commands/todo.md) | Capture or update an idea in the current project's tracked queue |
| [mainframe-init](commands/mainframe-init.md) | Establish ownership and verification for one user-facing coordinating session |
| [mainframe-project-skill](commands/mainframe-project-skill.md) | Initialize, update, or extend the current project's evolving skill |
| [mainframe-tickets-init](commands/mainframe-tickets-init.md) | Initialize or migrate project ticket directories, format and root instructions |
| [mainframe-tickets-find](commands/mainframe-tickets-find.md) | Investigate random project areas and record or enrich deduplicated problem tickets |
| [mainframe-tickets-refine](commands/mainframe-tickets-refine.md) | Deeply investigate ticket execution paths, blast radius, and duplicates; route each outcome |
| [mainframe-tickets-implement](commands/mainframe-tickets-implement.md) | Implement, validate, and locally commit each ready engineering ticket sequentially |
| [mainframe-tickets-verify](commands/mainframe-tickets-verify.md) | Independently verify implemented tickets; edit only ticket records |

## DeepSeek Harness plugins

The four packages target DSH `0.2.2-rc.1`. Choose the ones you want for a
profile.

| Plugin | Capability |
| --- | --- |
| [Activity Analytics](plugins/dsh/activity-analytics/README.md) | Profile-local activity and agent-time summaries |
| [Message Time](plugins/dsh/message-time/README.md) | Timestamps for human messages and complete agent turns |
| [Secrets Vault](plugins/dsh/secrets-vault/README.md) | Encrypted profile-local credential storage |
| [Session Collaboration](plugins/dsh/session-collaboration/README.md) | Session discovery, messaging, waits, and lifecycle controls across projects |

Build versioned `.tgz` archives from the checkout, retain them in persistent
storage, and install or replace bundles with DSH's native `plugin_manager`.
Repository and archive checks cover package source and contents. Native profile
activation and visible behavior are verified separately. [Package, install, or update DSH plugins](docs/installation/dsh-adapter.md)

[Workspace Transfer Safe](plugins/dsh/workspace-transfer-safe/README.md) remains
a paused prototype excluded from the package build and supported installation.

## Verification and security

The GitHub badge tracks the workflow for branch `main`. For another revision,
use that revision's Actions result. The workflow
runs the repository, hook, and credential-helper tests, shell syntax, and
whitespace checks. Analyzer pins are maintained in the runtime installer and
the workflow. [Validation commands](CONTRIBUTING.md#validate-the-change) · [GitHub workflow](.github/workflows/ci.yml)

Installation preserves unrelated user configuration, authentication, histories,
sessions, memories, and projects. MAINFRAME sends no telemetry. The optional DSH
Activity Analytics plugin stores timing data within its profile. [Analytics storage](plugins/dsh/activity-analytics/README.md#storage-and-deployment) · [Security reporting](SECURITY.md)

[Contributing](CONTRIBUTING.md) · [Repository sharing](docs/repository-sharing.md) · [MIT license](LICENSE)

# MiniMax Code Desktop installer

This maintained route targets MiniMax Code Desktop's native **Plugin V1**
contract on macOS. The full mapping requires release **3.0.73 or newer**; its native Agent and
Task contracts were inspected in installed build **3.0.73.170**. It records the
actual release in delivery state. A newer release still needs native recognition
and behavior checks; version comparison alone does not prove compatibility. It installs one user-owned local Plugin at
`~/.minimax/plugins/mainframe/`; it does not edit MiniMax's internal SQLite
state, launch another agent, or use a CLI surface.

Run from the MAINFRAME repository root:

```sh
python3 -B install.py minimax plan --surface desktop
python3 -B install.py minimax apply --surface desktop
python3 -B install.py minimax verify --surface desktop
```

`plan` is read-only. `apply` writes the reviewed plan through the common
transaction and ownership receipt. `verify` checks that the same plan has no
remaining structural changes. `--minimax-app` selects another application bundle
for version evidence; `--minimax-home` selects an explicit data directory.
Neither option changes the other adapters.

## Deliver one skill

An existing same-source MAINFRAME installation can deliver one canonical skill
on Desktop release **3.0.73**, inspected in build **3.0.73.170**. Use the exact
inventory name, for example `mainframe-k3s`.

```sh
python3 -B install.py minimax plan --surface desktop --skill mainframe-k3s
python3 -B install.py minimax apply --surface desktop --skill mainframe-k3s
python3 -B install.py minimax verify --surface desktop --skill mainframe-k3s
```

The installer writes the skill and its approved resources inside
`~/.minimax/plugins/mainframe/skills/<name>/`. It adds one entry to the
existing installer-owned `.minimax-plugin/plugin.json` when needed and updates
the matching ownership and adaptation records. A missing or edited manifest
requires reconciliation. `verify` reports `scoped_update_matches` when the
scoped plan converges. Wait for the Plugin rescan and confirm skill discovery
in a fresh Desktop conversation.

## Delivered shape

The Plugin manifest declares all canonical MAINFRAME Skills in the
[inventory](../../ADAPTATION.example.json), eight command workflows rendered as
Skills, and one Hook document. Seven native custom Agents are delivered separately
at `~/.minimax/agents/<mainframe-name>/agent.md`. The nine unsupported full
contracts (eight commands plus autonomous model/effort enforcement) all retain
partial bindings. The Hook document starts
one composite command for each relevant event rather than one process per
canonical detector:

| Event | MAINFRAME behavior |
| --- | --- |
| `SessionStart` | Inject the complete canonical global instruction into the root Agent |
| `SubagentStart` | Inject the same global instruction into the starting Subagent |
| `PreToolUse` on `bash` | Run secret, destructive-operation, commit-secret, and ripgrep detectors |
| `PreToolUse` on `task` | Advise on native user-only model/effort overrides when complete choices are absent; preserve legal defaults |
| `PreToolUse` on `write` or `edit` | Validate addressed TODO index/note content, then capture the exact edit scope for code-quality and Fallow comparison |
| `PostToolUse` on `write` or `edit` | Deliver bounded findings from the completed edit |
| `Stop` or `SubagentStop` | Revalidate blocking code-quality findings for the stopping recipient and continue it at most once for the same native stop identity |

Clean events write no stdout. Operational failure fails open. Hook state lives
under MiniMax's host-owned `PLUGIN_DATA`, and disable markers affect only the
selected canonical Hook. The Plugin package itself remains immutable at runtime.

MiniMax exposes Plugin Skills to autonomous selection as well as explicit
invocation. The eight commands remain useful partial bindings: discovery text
and bodies require explicit invocation, while the current native reader/runtime
projection has no explicit-only flag. Unsupported frontmatter would not enforce it.

Custom Agents now use the current Desktop's file-backed native route. The host
scans valid direct `agents/<name>/agent.md` files for its roster and repairs its
own runtime index at startup. The installer writes no internal database records
and starts no Agent or greeting. The three review/research roles use native tool
allowlists retaining file reads, Skills and web access while excluding shell,
write/edit, delegation, computer use and unrelated MCP tools. The host may
further restrict tools in child sessions. Required method links resolve to the
MAINFRAME Plugin's skill files. No model/effort defaults are installed.

The current native `task` schema supports both selection controls, but its tool
description says to set them only when the user specifies them and forbids
inferred or guessed selections. Autonomous preventive selection parity is
therefore unsupported. A retained `PreToolUse` advisory explains that boundary
and preserves inherited/default calls when choices are absent. It never denies
such calls or requires the user to disable the guard. Both supplied selections
produce no advisory; native validation owns model/effort compatibility.

Updates retire only receipted former role-Skill files. An edited Agent file,
including user changes to model or effort, stops reconciliation for review and
is never overwritten. Native settings, authentication, history, unrelated Agents,
host-created Agent metadata, Plugin enable state and per-hook disable markers
are preserved.

## Activation and evidence boundary

MiniMax automatically rescans local Plugins and enables a newly discovered
local directory by default. A prior user-disabled state for the same directory
is preserved by the host. After `apply`, wait for that rescan and open one new
conversation to confirm that `MAINFRAME` appears without scan diagnostics. Confirm the seven custom Agents in the Desktop roster too; restart Desktop
only if its roster needs startup reconciliation. This is the routine handoff; the installer does not spend a model turn probing
every Skill or Hook.

`ADAPTATION.minimax.json` records delivery separately from native behavior.
A converged `verify` proves files, manifest references, modes, ownership, and
registration shape and native Agent file delivery. It does not prove Desktop discovery, a model's Skill choice,
or a real event lifecycle.

A changed release returns native verification to pending where appropriate.
Older releases are rejected before the full mapping is written; disable,
removal and recovery remain available. A host scan or wire-contract failure
requires a focused adapter update against that concrete failure.

Hook controls and removal use the same entrypoint:

```sh
python3 -B install.py minimax disable
python3 -B install.py minimax enable --hook mainframe-fallow-quality
python3 -B install.py minimax uninstall
python3 -B install.py minimax recover
```

The mapping and its limitations are documented in
[native/minimax.md](native/minimax.md). Adapter code lives in
[installer/minimax.py](../../installer/minimax.py), and the small installed Hook
transport comes from [installer/minimax_hook.py](../../installer/minimax_hook.py).


## Skill reminders

The installer delivers the shared positive-only reminder method and this
product's [native binding](../../hooks/skill-reminder-routing.md#native-bindings).
An already considered skill stays quiet; reminders neither block nor continue
a model. Existing disable choices are preserved. Start a fresh Desktop
conversation after updating registrations; file convergence does not establish
native receipt or skill application.

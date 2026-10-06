# MiniMax Code Desktop installer

This maintained route targets MiniMax Code Desktop's native **Plugin V1**
contract on macOS. It reads the installed application's actual version for
state and evidence but does not reject a release merely because its number
changed. It installs one user-owned local Plugin at
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

## Delivered shape

The Plugin manifest declares every canonical MAINFRAME Skill in the
[inventory](../../ADAPTATION.example.json), seven command
workflows rendered as Skills, and one Hook document. The Hook document starts
one composite command for each relevant event rather than one process per
canonical detector:

| Event | MAINFRAME behavior |
| --- | --- |
| `SessionStart` | Inject the complete canonical global instruction into the root Agent |
| `SubagentStart` | Inject the same global instruction into the starting Subagent |
| `PreToolUse` on `bash` | Run secret, destructive-operation, commit-secret, and ripgrep detectors |
| `PreToolUse` on `write` or `edit` | Capture the exact edit scope for code-quality and Fallow comparison |
| `PostToolUse` on `write` or `edit` | Deliver bounded findings from the completed edit |
| `Stop` or `SubagentStop` | Revalidate blocking code-quality findings for the stopping recipient and continue it at most once for the same native stop identity |

Clean events write no stdout. Operational failure fails open. Hook state lives
under MiniMax's host-owned `PLUGIN_DATA`, and disable markers affect only the
selected canonical Hook. The Plugin package itself remains immutable at runtime.

MiniMax exposes Plugin Skills to autonomous selection as well as explicit
invocation. The seven commands are therefore useful partial bindings, but their
explicit-only contract cannot be enforced. MiniMax custom Agents are managed by
the native `mavis` service and are not representable in local Plugin V1, so the
seven role components remain unsupported rather than being written into private
runtime state.

## Activation and evidence boundary

MiniMax automatically rescans local Plugins and enables a newly discovered
local directory by default. A prior user-disabled state for the same directory
is preserved by the host. After `apply`, wait for that rescan and open one new
conversation to confirm that `MAINFRAME` appears without scan diagnostics. This
is the only routine handoff; the installer does not spend a model turn probing
every Skill or Hook.

`ADAPTATION.minimax.json` records delivery separately from native behavior.
A converged `verify` proves files, manifest references, modes, ownership, and
registration shape. It does not prove Desktop discovery, a model's Skill choice,
or a real event lifecycle.

A new MiniMax release changes the recorded target version and returns native
verification to pending where appropriate. Compatibility follows the declared
Plugin V1 shape and the host's scan result rather than a hard-coded application
version allowlist. If the host rejects the package or changes the wire contract,
the adapter needs a focused mapping update against that concrete failure.

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

# Cline installer

This maintained route targets Cline's shared global configuration root on
macOS. Cline Desktop and the Cline CLI read the same `~/.cline/` tree, so one
installation serves both surfaces; select the surface that will prove native
behavior. The installer never launches a Cline session, the hub, or a model.

Run from the MAINFRAME repository root:

```sh
python3 -B install.py cline plan --surface desktop
python3 -B install.py cline apply --surface desktop
python3 -B install.py cline verify --surface desktop
```

`plan` is read-only. `apply` writes the reviewed plan through the common
transaction and ownership receipt. `verify` checks that the same plan has no
remaining structural changes. `--cline-app` selects another Desktop bundle for
release evidence, `--cline-home` selects an explicit configuration root, and
`--surface cli` reads the installed CLI's own version instead.

## Delivered shape

| Destination | Content |
| --- | --- |
| `~/.cline/rules/mainframe.md` | The canonical global instruction inside one MAINFRAME-managed block |
| `~/.cline/skills/mainframe-*/` | The 15 canonical skills, complete with references, scripts, and assets; markers resolved only in the copies |
| `~/.cline/agents/mainframe-*.yml` | The seven roles as YAML profiles; read-only roles are restricted to `read_files, search_codebase` and every profile binds its required method through the native `skills:` field |
| `~/.cline/workflows/<command>.md` | The seven commands as explicit user-invoked slash workflows |
| `~/.cline/hooks/PreToolUse`, `PostToolUse` | Two fail-open launchers that call one Python transport |
| `~/.cline/hooks/mainframe-cline-hook` and `hooks/detectors/` | The unchanged canonical detectors behind the transport |
| `~/.local/bin/mainframe-secret` | The credential helper, installed only when absent |

`PreToolUse` receives every tool call, filters to the exact shell and edit tools,
evaluates the secret, destructive-operations, commit-secrets, and
ripgrep-replacement detectors, and answers only on a positively recognized
finding: a hard `cancel` for a guard, a `contextModification` advisory
otherwise. `PostToolUse` delivers exact-scope code-quality advisories plus
Fallow's structural analysis of TS/JS edits, with per-operation
deduplication and bounded per-file snapshots. For `apply_patch`, the transport
extracts the complete affected scope from canonical patch headers; multi-file
patches remain one attributed operation. Clean calls, unknown tools, malformed
payloads, unavailable interpreters, and detector failures all stay silent.
Hook state lives under `~/.cline/data/mainframe/hook-state/` with bounded
expiry.

Two hook components are `unsupported` with an exact reason: Cline dispatches
lifecycle hook files detached, so no completion event can revalidate findings
or continue the model, which removes the completion guard of
`mainframe-code-quality` and the continuation-capable completion timing of
`mainframe-fallow-quality`. Both remain useful as reported partial bindings:
per-edit quality advisories and per-edit Fallow analysis are delivered
informatively on `PostToolUse` and never block. Guards block through the native `cancel` result, which stops
the affected run with the reason; Cline file hooks offer no recoverable
per-tool denial, and a batched `run_commands` call is evaluated command by
command.

Commands are workflows, Cline's explicit-only invocation surface; skills remain
the autonomous surface. Agent profiles load as `subagent_<name>` tools when the
runtime spawns configured agents.

## Activation and evidence boundary

`ADAPTATION.cline.json` records delivery separately from native behavior. A
converged `verify` proves files, modes, ownership, markers, and placeholders.
It does not prove Desktop or CLI discovery, a model's skill choice, workflow
invocation, role loading, or a hook lifecycle. Open one new conversation in the
selected surface and confirm MAINFRAME appears without diagnostics; that is the
only routine handoff. File hooks are read when a session starts, so a new
conversation also adopts hook changes.

A new Cline release changes the recorded target version and returns native
verification to pending where appropriate. If Cline changes hook event names,
payload shape, or the output contract, the adapter needs a focused mapping
update against that concrete failure.

Hook controls and removal use the same entrypoint:

```sh
python3 -B install.py cline disable
python3 -B install.py cline enable --hook mainframe-secret-access
python3 -B install.py cline uninstall
python3 -B install.py cline recover
```

The mapping and its limitations are documented in
[native/cline.md](native/cline.md). Adapter code lives in
[installer/cline.py](../../installer/cline.py), and the installed hook
transport comes from [installer/cline_hook.py](../../installer/cline_hook.py).

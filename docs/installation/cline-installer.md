# Cline Desktop installer

This maintained route targets installed Cline Desktop **0.0.46** on macOS and
its product-private `~/.cline/` directory. It never launches a conversation,
hub, model or application service.

Run from the MAINFRAME repository root:

```sh
python3 -B install.py cline plan --surface desktop
python3 -B install.py cline apply --surface desktop
python3 -B install.py cline verify --surface desktop
```

`plan` is read-only. `apply` uses the common transaction and ownership receipt;
`verify` checks convergence. Full Desktop plans require release 0.0.46 or newer;
controls and removal remain available for older recorded installations. `--cline-app` selects the Desktop bundle for version
evidence, and `--cline-home` selects another configuration root. The legacy
`--surface cli` implementation remains available, with no claim of current CLI
compatibility from this Desktop qualification.

For one canonical skill on the inspected **0.0.46** Desktop release, add
`--skill <name>` to the three commands above. This requires an existing
same-source installation with matching receipt and adaptation state. The
selected package goes under `~/.cline/skills/`; only its package, receipt
records and adaptation row are reconciled. Analyzers and other bindings
are outside this route. `scoped_update_matches` reports package convergence.

The installer delivers one managed instruction block under `rules/`, all skills
in the [canonical inventory](../../ADAPTATION.example.json) with their approved
resources under `skills/`, seven YAML role profiles
under `agents/`, eight explicit slash workflows under `workflows/`, and unchanged
canonical detectors behind `hooks/PreToolUse` and `PostToolUse`. Profiles bind
required methods through `skills:`; the three read-only roles expose only native
read/search tools and their attached skill executor.

The additional native `plugins/mainframe.js` module revalidates attributed
quality findings before `submit_and_exit`. A positive finding recoverably skips
that completion tool; the agent can repair and retry. The plugin needs only
Node builtins and the installer's Python interpreter. Its child process is
bounded below the native three-second plugin-hook timeout and fails open.
It writes no product settings or database registration.

File hooks retain established protection when the plugin is disabled or fails
to load. `PreToolUse` applies shell secret, destructive-operation and commit
checks, ripgrep advice, TODO guards and edit capture. Its positive guard
`cancel` aborts the run. `PostToolUse` supplies exact-edit quality, Fallow,
checkpoint and skill advice. The plugin does not duplicate these guards or
advisories. Multi-file patches retain their complete bounded scope; native
structured failed edits stay neutral. Private state and the ownership receipt
live under `~/.cline/data/mainframe/`.

The adapter accounts for every inventoried component. The three unsupported
full contracts are detailed below. Quality retains per-edit advice plus the new
completion-tool check; Fallow retains per-edit structural advice. Neither has a
universal continuation-capable completion event, because natural delegated
completion can bypass `submit_and_exit` and `afterRun` ignores return values.
Subagent model-plus-effort selection has no binding: native call schemas do not
offer both controls. No guard blocks valid inherited native defaults. There are
no stale pending rows reserved for another product.

The current shipped loader accepts the generated plugin in a disposable worker;
source inspection proves its global discovery path and control effects. A
converged installation proves files, modes, ownership and markers. It does not
prove live Desktop discovery or recipient behavior. Open one new Desktop
conversation and confirm skills, workflows, profiles and rules appear without
diagnostics; observe a harmless relevant event when native acceptance is needed.
A product version change invalidates prior native verification where appropriate.

Existing histories, sessions, authentication, global settings, foreign plugins
and user files are preserved. Only receipted owned files are updated or removed.
The credential helper is installed when needed; its metadata index is retained.
Existing per-hook disable choices are preserved. Controls use the same entrypoint:

```sh
python3 -B install.py cline disable
python3 -B install.py cline enable --hook mainframe-todo-limits
python3 -B install.py cline uninstall
python3 -B install.py cline recover
```

The [native evidence](native/cline.md) owns current schemas, loading paths,
hook ordering, read-only filtering and acceptance limits. The maintained code is
[installer/cline.py](../../installer/cline.py) with the thin transport in
[installer/cline_hook.py](../../installer/cline_hook.py).

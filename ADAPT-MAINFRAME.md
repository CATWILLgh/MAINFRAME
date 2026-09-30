# Install MAINFRAME into the running product

This is the installation entrypoint. The file-selection rule in
[AGENTS.md](AGENTS.md) defines sending this file alone as the request to install
or update MAINFRAME. Start the route below without asking for another launch
phrase. An explicit request to review, explain, or edit this file means that
separate task; incidental reading does not invoke installation.

## Establish the source and target

The user opens this MAINFRAME repository in the product to be configured.
Resolve the current workspace root and require this file,
[ADAPTATION.example.json](ADAPTATION.example.json), `install.py`, `installer/`,
`docs/installation/`, and every listed canonical source to be present there.
Do not search other checkouts, archives, backups, or the home directory for a
replacement source. Run the installer from this root.

Target only the surface running the request. Desktop does not launch a CLI
agent or a separate app-server; CLI does not operate Desktop. Shared files do
not expand authority. An installer shell command is permitted: it runs the
file-delivery program, not another agent product.

Preserve authentication, credentials, protected stores, sessions, history,
projects, worktrees, user instructions, unrelated configuration, and dirty
repository work. Do not change canonical source during installation. Repository
writes are limited to ignored adaptation state, the non-secret credential index,
and explicitly authorized feedback. Only the exact inventory is payload;
repository documentation, tests, development skills, and local state are not.

## Select the maintained installer

Read exactly the matching procedure:

- **Codex:** [codex-installer.md](docs/installation/codex-installer.md).
- **ZCode Desktop:** [zcode-installer.md](docs/installation/zcode-installer.md).
- **Antigravity Desktop 2.0:** [antigravity-installer.md](docs/installation/antigravity-installer.md).
- **MiniMax Code Desktop:** [minimax-installer.md](docs/installation/minimax-installer.md).
- **Cline Desktop or CLI:** [cline-installer.md](docs/installation/cline-installer.md).

Follow that procedure's `plan`, `apply`, and `verify` commands. Reuse the
maintained mapping; do not write another installer, copy components manually,
run the generic adaptation loop, or ask another model to adapt the inventory.
The agent resolves actual instruction conflicts and unexpected environments;
the program owns deterministic rendering, file ownership, writes, and recovery.

For a product or version without a maintained supported mapping, report the
exact missing adapter or compatibility work. Do not silently turn an ordinary
installation into adapter development. Native orientation documents are research
inputs for separately assigned development, not executable installers.

## Complete the bounded delivery pass

1. Run the product's read-only plan. Resolve only the concrete conflicts it
   reports. A required instruction review means read the existing owner and
   canonical body; it does not mean asking the user to approve compatible text.
2. Apply the reviewed plan. Use the product's explicit legacy-adoption route
   only when its evidence checks recognize the existing installation.
3. Run its deterministic verification once. Investigate a failure at its exact
   owner; do not repeat a failed check unchanged or overwrite user edits.
4. Report delivery, precise limitations, and the one necessary user activation
   or new-session handoff. Finish independent delivery even when one native
   capability remains unresolved.

The installer checks delivered files, required resources, substitutions,
configuration, preservation, and convergence. It does not start model turns,
invoke operational commands, test credentials, launch a browser, or trigger
native hook lifecycles to fill the state file. Those belong to a separately
requested adapter validation run. Follow the
[verification boundary](docs/installation/verification.md#routine-installation-and-adapter-validation).

## Keep state small and truthful

[ADAPTATION.example.json](ADAPTATION.example.json) owns schema and exact component
identity. The maintained installer creates or migrates the ignored product state.
Do not rewrite its structure into a session report.

- `delivery: pending`: files or a representable binding have not been delivered.
- `delivery: installed`: the intended files and registrations passed delivery
  checks. This does not claim the host has loaded or exercised them.
- `delivery: unsupported`: the target cannot represent the required capability;
  `reason` names the established limitation.
- `verification: pending` or `passed`: native behavior evidence is independent
  of delivery. Unsupported rows omit verification.
- `next_action` names only the remaining component-specific action. Shared
  activation or reload belongs once in the state's `next_actions` list.

Existing schema-1 statuses do not prove present delivery. The installer reconciles
actual files and conservatively retains applicable verification evidence. Do not
mark verification passed from file presence, successful parsing, or an agent's
unsupported claim. Do not treat an untested capability as unsupported.

## Recovery and final report

Use only the procedure's maintained recovery, disable, and removal operations.
Never remove a hook's callable entrypoint while an old session may still invoke
it. Follow [safe retirement](docs/installation/problems/rollback-and-recovery.md#retire-hooks-safely);
keep a necessary inert legacy callback and its exact cleanup handoff until old
scopes are known to have unloaded it. Preserve scoped rollback material while
recovery remains pending, without creating a full-profile archive or logs.

Return a concise report: product/surface, whether delivery verification passed,
components not delivered or unsupported, necessary activation, and any recovery
blocker. Do not list every successful file or repeat the same target metadata per
component. A completed delivery pass with pending native verification is a valid
bounded result; full native acceptance is a separate claim requiring its evidence.

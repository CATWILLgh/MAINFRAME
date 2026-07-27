---
id: d0251020
title: Add a plaintext-safe secret input path for the installer TUI
status: open
priority: medium
component: installer
discovered: 2026-07-17
discovered-from: []
tags: ["tui", "credentials", "security", "mcp"]
---

# d0251020: Add a plaintext-safe secret input path for the installer TUI

## What was observed

The current credential helper accepts `secret set NAME VALUE`. The secret value
is therefore present in the child process argument vector. The first MCP
onboarding milestone can describe an API-key profile, but deliberately does not
collect or persist the key through this interface.

## Why it is a problem

Process arguments can be exposed through process inspection, diagnostics, or
crash reporting. Passing a Context7 API key this way would violate the installer
strategy requirement that credentials never enter previews, logs, journals, or
other observable command metadata. Keyed MCP onboarding cannot become
executable until a safer channel exists.

## Why it is not a duplicate

- [#7ac048e7](7ac048e7-encode-configuration-permission-contracts.md) defines
  destination file and directory modes; it does not cover secret transport into
  the credential helper.
- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) defines
  adapter-owned MCP publication and removal; it assumes credential material can
  already be stored without exposure.

## What probably needs to be done

- Add a credential-helper operation that reads the value from standard input or
  another non-argument channel while keeping the name as the only public
  argument.
- Add masked terminal input in the TUI and pass the bytes directly to that
  operation without putting them in arguments, environment variables, preview
  structures, logs, or executor journals.
- Preserve the helper's existing validation, locking, file mode, backup, and
  atomic replacement behavior.
- Clear transient byte buffers where practical and make failure messages name
  only the credential identifier, never its value.
- Enable keyed MCP profiles only after each selected adapter proves either a
  plaintext-free reference or an explicitly approved adapter-local standard
  storage contract.

## Acceptance criteria

- Process arguments and environment contain no secret value during storage.
- Terminal input is masked and cancellation leaves the credential store
  unchanged.
- Tests cover empty input, invalid names, newline policy, interrupted writes,
  concurrent storage, and absence of secret bytes from errors and previews.
- Context7 keyed onboarding stores the key once in the neutral credential store
  and publishes adapter-local references where the host supports them.
- Standalone Antigravity keyed activation resolves the selected reference only
  during confirmed Apply and writes the value only to Antigravity's standard
  MCP configuration. The value is absent from previews, ownership metadata,
  journals, logs, errors, and all other adapter roots.

## Sources

- `core/resources/credential-tools/secret:102-115`
- `docs/installer-strategy.md`
- `internal/mcpcatalog/catalog.json`
- <https://cwe.mitre.org/data/definitions/214.html>

## Re-occurrence noted (2026-07-27)

**Noticed during:** the proposed Context7 credential-instance projection for
standalone Antigravity 2.x

**Where:** `com.google.antigravity` version `2.2.1`

**Additional details:** Antigravity's MCP documentation shows direct string
values for remote `headers`, provides no environment-reference syntax for
them, and documents `env` only for stdio servers. In an isolated temporary
home, a synthetic local MCP endpoint received
`${MAINFRAME_ANTIGRAVITY_PROBE}` literally even though that variable was
present in the standalone language-server environment. The process was launched
with isolated configuration roots and did not receive or change live user
configuration. This established that a reference-only projection cannot work
for this host.

The product decision was superseded on 2026-07-27. Standalone Antigravity keyed
Context7 now uses its standard configuration storage through MAINFRAME's common
confirmed-Apply transaction. The TUI never collects or displays the value; the
executor resolves the already selected user-owned reference at Apply time.
This does not close the ticket's original masked-input scope for storing a new
secret without putting it in process arguments.

**Source:** <https://antigravity.google/docs/mcp>, accessed 2026-07-27.

### Reproduction record

The probe used only the synthetic value `reference-expanded`. Create an
isolated root and place this MCP configuration at
`$PROBE_ROOT/gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "mainframe-env-reference-probe": {
      "serverUrl": "http://127.0.0.1:49321/mcp",
      "headers": {
        "X-Mainframe-Probe": "${MAINFRAME_ANTIGRAVITY_PROBE}"
      }
    }
  }
}
```

Create the root and start the repository's loopback-only synthetic MCP server:

```sh
export PROBE_ROOT="$(mktemp -d /tmp/mainframe-antigravity-probe.XXXXXX)"
echo "$PROBE_ROOT"
mkdir -p "$PROBE_ROOT/gemini/config"
python3 tools/probe_antigravity_mcp_headers.py --port 49321
```

The server records `X-Mainframe-Probe`, answers `initialize` and `tools/list`,
and accepts notifications. In a second terminal, export the printed
`PROBE_ROOT` path and launch the exact installed binary:

```sh
export PROBE_ROOT=/tmp/mainframe-antigravity-probe.<printed-suffix>
HOME="$PROBE_ROOT" \
MAINFRAME_ANTIGRAVITY_PROBE=reference-expanded \
/Applications/Antigravity.app/Contents/Resources/bin/language_server \
  -gemini_dir="$PROBE_ROOT/gemini" \
  -config_dir=config \
  -app_data_dir=antigravity \
  -standalone \
  -headless \
  -disable_telemetry \
  -use_mocked_data \
  -use_ls_chrome_devtools_mcp=false
```

When the isolated mocked-data process asks for a redirect URL, enter
`http://localhost/invalid`; no real account authorization is used. The process
then initializes the configured MCP connection.

The isolated `2.2.1` run sent two requests. The exact captured lines were:

```text
REQUEST_1_X-Mainframe-Probe=${MAINFRAME_ANTIGRAVITY_PROBE}
REQUEST_2_X-Mainframe-Probe=${MAINFRAME_ANTIGRAVITY_PROBE}
```

Stop both processes normally after capture and verify that port `49321` has no
listener. The observed filesystem writes stayed under `$PROBE_ROOT`; live
Claude Code and Codex configuration was neither supplied to the process nor
changed. A later host version must be rechecked rather than assumed to behave
identically.

## Progress (2026-07-27)

- The TUI now provides masked, paste-capable input with a separate
  value-free confirmation.
- The release-bundled helper exposes `create-stdin NAME`; the value is sent
  only through standard input and existing names cannot be overwritten.
- Invalid, empty, multiline, NUL-containing, and oversized input is rejected
  without reflecting content. Publication retains the existing lock, private
  modes, same-filesystem atomic replacement, and unrelated entries.
- Rotation and deletion remain deliberately separate because changing a shared
  name affects every consumer. Their future confirmation must include a
  refreshed impact view rather than reusing create-only behavior.

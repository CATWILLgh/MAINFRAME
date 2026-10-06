# Install MAINFRAME into Antigravity Desktop 2.0

Use this maintained route when the file-only installation request runs in
Antigravity Desktop from the open MAINFRAME repository. The supported mapping
targets macOS Antigravity **2.16.0**. Version detection reads the application
plist and never starts a model, the Antigravity CLI, IDE, or browser.

## Plan, apply, verify

From the repository root run:

```sh
python3 -B install.py antigravity plan --surface desktop
python3 -B install.py antigravity apply --surface desktop --instructions-reviewed
python3 -B install.py antigravity verify --surface desktop
```

Read the existing `~/.gemini/GEMINI.md` and canonical global instruction only
when the plan requests semantic review. Resolve actual contradictions and pass
`--instructions-reviewed`; do not ask the user to approve compatible overlap.
The installer preserves outside content and rejects a merged rule file above the
documented 24,000-byte per-file limit.

`--gemini-home` selects an explicitly resolved shared customization root and
`--antigravity-app` selects the Desktop application used for version evidence.
`--home` and `--runtime-version` support disposable fixtures. A simulated home
or version is not native acceptance evidence.

The adapter installs complete global skills, seven native subagent definitions,
the compatible credential helper, and the global instruction. It preserves
foreign `hooks.json` entries and installs one composite MAINFRAME binding on 2.16.0.
Antigravity requires every `PreToolUse` handler to decide `allow`, `deny`,
`ask`, `force_ask`, or `deny_unless_prior_grant`: it provides no neutral result that can leave the native
permission layer authoritative. `allow` authorizes an otherwise clean tool,
while `ask` adds a prompt and blocks unattended goals. The installer therefore
records each full native hook contract as unsupported instead of silently replacing
the user's permission policy. Instead, one `PostInvocation` handler inspects only
the latest completed native tool-call row and injects an ephemeral message only for
a positive detector finding. One `Stop` handler continues only while an exact
inserted-text code finding remains, at most once for the same finding set and
native `executionNum`. Clean events emit no context and never force a
model continuation. The report's `retained_partial_bindings` describes this degraded
event timing and the exact missing guarantee for each component. The adapter
does not install deprecated workflows. The seven
commands use Antigravity's current slash-capable skill package with an explicit
invocation guard in both discovery metadata and the body. This preserves useful
`/mainframe-project-skill` behavior, but cannot enforce explicit-only selection at the
host level, so the full command contracts remain unsupported. The resulting
`ADAPTATION.antigravity.json` records exact component delivery, while the installer
report separates retained partial behavior from the missing full contracts.

`verify` proves exact files, registrations, preservation, and convergence. It
does not invoke skills, roles, credentials, hooks, models, CLI, browser, or UI.
After it passes, open one new Antigravity Desktop conversation for discovery.
Do not repeat installation checks to fill native verification fields.

## Update and recovery

```sh
python3 -B install.py antigravity uninstall
python3 -B install.py antigravity recover
```

An update from the earlier 2.13.0 mapping first disables its owned callbacks,
waits for their bounded timeout, then replaces only the old bridge, detectors,
and named registrations. `disable` and `enable` control individual policy markers
without rewriting foreign hook configuration. Uninstall removes
only receipt-owned artifacts. Credential descriptions, user rules, unrelated Gemini
configuration, authentication, histories, conversations, CLI data, and browser
profiles remain untouched.

Native decisions and evidence live in
[native/antigravity.md](native/antigravity.md). Adapter logic lives in
[installer/antigravity.py](../../installer/antigravity.py), with shared
transactions in [installer/core.py](../../installer/core.py).


## Skill reminders

The installer delivers the shared positive-only reminder method and this
product's [native binding](../../hooks/skill-reminder-routing.md#native-bindings).
An already considered skill stays quiet; reminders neither block nor continue
a model. Existing disable choices are preserved. Start a fresh Desktop
conversation after updating registrations; file convergence does not establish
native receipt or skill application.

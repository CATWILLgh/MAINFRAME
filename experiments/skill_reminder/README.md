# Codex skill reminder prototype

This experiment is not installed by `install.py` and is not part of the canonical
inventory. It tests a narrow read-time advisory before committing to a new
cross-product component. Normal installation does not change global settings for this experiment; explicit experimental registration is separate.

The maintained successor is [mainframe-skill-reminder](../../hooks/README.md#adapt-mainframe-skill-reminder), delivered through the Codex installer. A matching receipted experimental registration is retired during that update; its configuration is disabled and its executable retained for cached callbacks. This directory remains historical experiment evidence, not the current installation route.

## Contract

Codex [hooks documentation](https://learn.chatgpt.com/docs/hooks) inspected
2026-10-03 documents shell/exec hooks as `Bash`, and `PostToolUse` JSON
`hookSpecificOutput.additionalContext` as model-visible context. Shell input
contains the command, but does not reliably identify its actual workdir.
This prototype therefore accepts only literal absolute paths in simple
`cat`, `head`, `tail` and print-only `sed -n` commands. It skips pipelines,
compound commands, substitutions, relative paths, unsupported tool outputs
and failed commands. It never evaluates shell text or reads source content.

The owning workspace and available skill paths are explicit experiment inputs.
Verify these skills are actually exposed in the receiving Codex catalog before
registering the experiment. File existence alone does not prove availability.
The prototype does not discover or register skills, run models, spawn processes,
install dependencies or send telemetry. Its Python standard-library entrypoint
is [codex.py](codex.py).

Routes: test and CI paths -> testing; backend paths plus Python/Go/TypeScript
extension -> the corresponding backend skill; component/page TSX -> frontend
only with an explicitly verified React profile. These are conservative signals,
not proof of task intent. Mixed domains, generic scripts, vendor/generated
paths and other languages stay silent. Project-skill discovery, infrastructure
routing, MCP reads, search commands and edit reminders are deferred; arbitrary
skill names are not inferred from files.

One short conditional recommendation, never a block or Stop continuation.
At most two recommendations per native session/workspace, once per skill.
An observed successful read of a configured SKILL.md suppresses that skill's
reminder; it does not assert that its instructions were applied. No transcript
search or source retention. Private bounded SQLite state keeps hashed scope,
skill IDs, sent flags and seven-day expiry; expired sessions can be reminded
again. Unknown identity, state failure or disable returns silence. Native
session IDs must distinguish recipients for independent subagent accounting;
that guarantee still needs actual Desktop acceptance.

## Explicit local acceptance setup

Only register after reviewing this prototype and confirming the intended
workspace and currently exposed skill paths. Use an absolute configuration
path outside the product's automatically discovered skill roots. Example shape
(replace paths with verified ones, omit unavailable skills):

```json
{
  "workspace": "/absolute/project",
  "skills": {
    "mainframe-python-backend": "/absolute/skills/mainframe-python-backend/SKILL.md",
    "mainframe-testing": "/absolute/skills/mainframe-testing/SKILL.md"
  },
  "react": false,
  "disabled": false
}
```

In the intended Codex hook configuration, preserve every existing registration
and append a `PostToolUse` group with matcher `^Bash$`. Its command handler runs:

```text
<absolute-python> -B <absolute-repo>/experiments/skill_reminder/codex.py <absolute-config.json> <absolute-private-state-directory>
```

For a global experimental registration covering several approved workspaces, use a top-level `profiles` array of the objects above (maximum 16). The callback selects the most specific workspace containing its native `cwd`; unmatched workspaces stay silent. A top-level `disabled: true` silences all profiles.

Shell-quote each argument when rendering the actual registration. Use an outer launcher guard that silently exits when the script, configuration or interpreter is absent; preserve the executable during normal disable/removal. Set `timeout`
to 2 seconds and `additionalContextLimit` to 150. Do not add `Stop`, a permission
decision, or forced continuation. Native trust remains a user UI action.
The experiment currently has no automated installer/uninstaller; this recipe
is not a claim of delivered or accepted behavior.

Set `disabled` to true first to silence even late callbacks. Preserve the
executable until its hook registration has been removed; deleting a registered
command would cause launcher errors. Missing configuration is also silent.
Remove only this experiment's registration and positively owned state.

## Evidence and promotion boundary

`python3 -B -m unittest discover -s tests -p test_skill_reminder.py` covers routes,
nonblocking output, no-state negative cases, ambiguity, missing skills, React
profile, errors, shell parsing, path escape, disable, budget, concurrent claims,
expiry and the executable stdin/stdout protocol. These are synthetic events;
they establish neither actual Desktop callback delivery nor improved model
skill use. The red stub produced missing-recommendation and parser assertion
failures before implementation; initial missing-module errors were setup only.

Before promotion, in an authorized fresh Desktop session observe one supported
absolute file read, the delivered model context, repeated reads remaining quiet,
a failed/irrelevant read staying quiet, and disable behavior. Check subagent
identity separately. Record useful versus irrelevant reminders on ordinary
work before widening recognition. Only then add a canonical hook contract,
inventory row and maintained delivery/cleanup support; do not silently include
this experimental source in normal installations.

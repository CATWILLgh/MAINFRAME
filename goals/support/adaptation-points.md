# Native adaptation points

These markers are authoring slots for the installing agent. They do not name
required native configuration fields. Resolve each marker from official
documentation and the actual environment, then remove authoring notes from
delivered instructions. Add a native option only when it serves the source's
purpose; the table is not a list of features to enable everywhere.

| Marker | Meaning | If unavailable |
| --- | --- | --- |
| `{{MAINFRAME_ROOT}}` | Verified absolute path of this checkout, used only for harness issue routing and source ownership. | Ask for the missing location; do not guess another project. |
| `{{CREDENTIALS_INDEX}}` | Existing authorized non-secret credential catalog path. | Report the missing catalog when a credential is needed; do not search protected stores. |
| `{{SUBAGENT_ROLE}}` | Role, bounded task, allowed files, expected evidence, and acceptance boundary for one useful delegation. | Execute directly within the same authority; disclose lack of independence when it matters. |
| `{{TOOL_SCOPE}}` | Documented native tool or permission restriction for that task. | Preserve the instruction boundary but do not claim technical enforcement. |
| `{{MODEL_CHOICE}}` | Available model and effort suited to the bounded job and operator preferences. | Keep the environment's supported defaults. |
| `{{HOOK_BINDING}}` | Native event, matcher, payload, output, timeout, and activation form implementing a hook's purpose. | Attempt a faithful documented mapping or native equivalent; if unavailable, skip the hook and report missing coverage. |
| `{{COMMAND_BINDING}}` | Native invocation for the named workflow or goal. | Provide an ordinary copyable prompt; do not invent a slash command. |

Example delegation block to adapt where useful:

```text
Role and assignment: {{SUBAGENT_ROLE}}
Native tool scope: {{TOOL_SCOPE}}
Model selection: {{MODEL_CHOICE}}
```

No skill requires a fixed specialist name. The same method can be used by the
current agent or by a bounded delegate. Independence is a property of the
actual review arrangement, not a title assigned to the same reasoning pass.

# Native settings

Purpose: use the environment's capabilities without imposing one product's
configuration on another.

Adapt these choices only after reading the owning current official settings,
permissions, model, and subagent documentation:

- `{{TOOL_SCOPE}}`: enforce the actual task boundary for a bounded delegate or
  skill where the native product supports it. A read-only reviewer should not
  receive implementation permissions merely because another role needs them.
- `{{MODEL_CHOICE}}`: select from supported models and effort settings based on
  the job and operator preferences; preserve user choices when no change is
  needed.
- Skill discovery: expose all applicable skills to both direct and delegated
  work. Keep descriptions concise and resources progressively loaded; universal
  availability does not mean preloading all skill bodies into every session.
- Context and memory: use the native lifecycle and the operator's retention
  and write preferences.

Preserve unrelated native settings.

Verification: inspect the effective configuration and actual skill visibility,
exercise a permitted and a denied operation for any claimed tool restriction,
and check that unrelated settings and model choices were preserved.

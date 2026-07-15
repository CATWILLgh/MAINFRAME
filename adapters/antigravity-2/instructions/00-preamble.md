# MAINFRAME on Antigravity Desktop 2.x

These rules apply to the standalone Antigravity Desktop agent center. Runtime
hooks deliberately no-op for transcripts under `~/.gemini/antigravity-cli` and
for other Gemini surfaces.

MAINFRAME source agents are exposed as `delegate-*` skills. When one matches a
task, read its `SKILL.md`, define the described dynamic subagent for the current
conversation, and invoke it. Capability restrictions in that skill are part of
the delegation contract.

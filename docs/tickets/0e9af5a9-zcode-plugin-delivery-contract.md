---
id: 0e9af5a9
title: Prove ZCode plugin delivery and agent activation before adopting it
status: open
priority: medium
component: zcode-desktop
discovered: 2026-08-05
discovered-from: []
tags: ["zcode", "plugins", "delivery"]
---

# 0e9af5a9: Prove ZCode plugin delivery and agent activation before adopting it

## What was observed
ZCode documents plugins as a packaging surface, but the installed ZCode guide says plugin-manifest agents are recorded without being executed. Installing and enabling a custom plugin also requires marketplace or plugin configuration that is not part of the stable direct-file discovery contract.

The v1 adapter therefore installs documented user files directly and does not write plugin caches or marketplace state.

## Why it is a problem
Plugin packaging could eventually provide a cleaner single activation boundary. Using it before agent execution and uninstall ownership are proven would silently omit specialized agents or leave unmanaged configuration.

## Why it is not a duplicate
No existing ticket covers ZCode plugin-packaged agent execution or plugin lifecycle ownership.

## What probably needs to be done
Re-test a minimal custom plugin against a future supported ZCode version, including install, enable, agent discovery and execution, hooks, upgrade, disable, and uninstall. Compare the result with direct-file delivery before changing the adapter.

## Acceptance criteria
- Official documentation and installed behavior agree on plugin-packaged agents.
- A temporary-home test proves install, update, disable, and uninstall without foreign-state loss.
- Plugin delivery preserves the same public/restricted skill boundary as direct files.
- Migration from direct files has an explicit preview and rollback path.

## Sources
- `adapters/zcode-desktop/capabilities.json`
- `adapters/zcode-desktop/build_zcode.py`
- `/Applications/ZCode.app/Contents/Resources/glm/packages/zcode-guide-plugin/skills/diagnosing-plugins/SKILL.md`
- https://zcode.z.ai/en/docs/plugin

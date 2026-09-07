# Pi orientation

Last reviewed: 2026-09-07.

Pi is intentionally extensible and may rely on skills, prompt templates, and
extensions rather than dedicated first-class surfaces for every MAINFRAME
component. Verify the installed package/version and current upstream
documentation before mapping anything.

## Official upstream sources

- [Coding agent README](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md)
- [Skills](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/skills.md)
- [Extensions](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md)

If these links redirect to a successor upstream, verify that the installed Pi
package belongs to that lineage before using the redirected documentation.

## Current orientation

| MAINFRAME concern | Native direction to verify |
| --- | --- |
| Global instruction | Pi's effective user instruction/context mechanism; do not globally copy this repository's project bootstrap |
| Skills | Global skill discovery with complete relative resources |
| Commands | Prompt templates or extension commands only when they remain explicit user operations and can preserve the no-argument contract |
| Hooks | Extension lifecycle/tool events only when they reproduce canonical timing and effect |
| Agents | A real native or extension-provided custom-agent mechanism; otherwise roles remain unsupported |
| Settings and permissions | Pi configuration and extension controls actually present in the installed version |

Do not treat a general extension API as proof of a capability. A MAINFRAME guard
requires pre-effect denial; a completion guard requires continuation in the same
scope; an agent requires native routing and a meaningful permission boundary.

## Adaptation decisions

1. Resolve the actual Pi executable, package version, resource directories, and
   configuration precedence.
2. Install each skill once in the current global discovery owner and verify
   progressive loading.
3. Choose prompt templates or extension commands only after proving user-visible
   discovery and explicit-only invocation. Keep target code outside canonical
   command files.
4. Implement thin extension wrappers for hooks only when the event contract can
   extract the exact fields and return the required advisory or block.
5. Mark custom roles unsupported unless a current documented mechanism can
   discover, invoke, and constrain them. Do not relabel a prompt template as a
   subagent.
6. Verify any CLI and embedded surface independently when they host different
   extension runtimes.

## Useful probes

- Use Pi's native resource listing or diagnostic commands to locate the
  effective skill, prompt, extension, and instruction sources.
- Explicitly invoke one command representation and one skill.
- Load one extension in isolation and exercise a synthetic event.
- Test repeated installation for duplicate commands and event handlers.
- Confirm extension failure follows the canonical hook failure behavior.

Prefer a precise unsupported entry over an elaborate compatibility layer that
cannot be verified against Pi's real execution model.

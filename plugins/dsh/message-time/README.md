# Message timestamps

Version **1.2.1** targets **DSH 0.2.2-rc.1** only. Wider compatibility is not claimed.
The package uses the real `@deepseek-ai/schemastery` dependency (`~3.19.0`) and
exports a named native `Config` alongside `name` and `apply`.

## Configuration

| Field | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Enable the plugin. |
| `includeUser` | `true` | Add a compact human-input receipt timestamp. |
| `includeAssistant` | `true` | Add a timestamp only when a full agent turn completes; **not** per assistant message or tool call. |
| `includeTurnStart` | `true` | Add a timestamp on the first accepted step of a full agent turn. |
| `timeZone` | omitted | Optional IANA fallback time zone. |

A valid `source.clientTimeZone` on human input takes precedence and becomes the
session's remembered zone after admission. With no known session zone, a valid
configured zone is used; an omitted, empty, or invalid configured zone falls back
to the host's time zone. Invalid client zones do not erase a known session zone.
The bundled patch explicitly sets `Europe/Moscow`: it is a fallback choice,
**not browser autodetection**. Remove that setting to use the host fallback.
The plugin does not query the browser itself.

All five fields have English/Russian descriptions passed through native
Schemastery `.i18n()`. Booleans have explicit schema defaults; `timeZone` remains
optional and accepts strings so invalid zone names can retain runtime fallback
behavior. Wrong non-null types are rejected by native Schemastery validation.

## Receipt lifecycle and history

The derived per-Session state folds durable inbox splices in order. All pending
IDs (including synthetic input) preserve native splice positions. Removed IDs
with `outcome: "canceled"` lose their receipts. Removal without an outcome is a
native claim: its timestamp survives queue draining, asynchronous assembly, and
pre-step admission. Committed human messages consume their receipt; every
terminal turn releases uncommitted claims while preserving queued future work.

Receipt retention is bounded by pending human inputs plus uncommitted claims,
not all past canceled/settled input. Pending IDs are bounded by current queues.
Already-observed sessions fold events even when no subsequent step runs; other
sessions replay lazily. Reload/fork derives state from the durable prefix, and
unload drops derived state and prevents queued or in-flight clock writes.
Settled messages are never edited; only newly proposed built-in clocks are
replaced. No tool/step clocks or system-prompt changes are introduced.

## Verification scope

Run with Node 24 (or a compatible Node supporting `module.registerHooks`):

```sh
node --test plugins/dsh/message-time/test.mjs
```

The tests exercise receipt lifetime, cancellation/replacement, pre-step claims,
terminal cleanup, replay/fork, 1,000 canceled inputs, 100 settled turns, timezone
fallbacks, all switches, and unload. The test-only schema fixture records actual
constructor calls and localization inputs; it is deliberately **not a validator
or native graph**. Neither tests nor fixture are included in the package payload.

Native source inspected in the installed DSH 0.2.2-rc.1 archive:

- `@deepseek-ai/dsh-agent-loop/lib/index.js`: durable inbox projection and normalized
  splices (25–62, 173–201); claim before asynchronous pre-step assembly (666–713).
- `@deepseek-ai/cordis/src/fiber.ts`: synchronous `Config['~standard'].validate`
  contract (50–61).
- `@deepseek-ai/dsh-app-boot/lib/index.js`: native Schemastery identity check
  (3197–3200) and native graph projection (3374 onward).
- `@deepseek-ai/schemastery/src/index.ts`: localized description merging and object
  propagation (334–382), optional/default handling (533–543), and string type
  validation (668–675).

This is bounded source/fixture verification, **not** native activation, native
Config validation/projection execution, or observed settings-UI acceptance.
No installation, profile changes, or model probe was performed.

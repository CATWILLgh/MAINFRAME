# Security

## Report a vulnerability

Report security problems privately. Use GitHub private vulnerability reporting
when it is available, or another private channel already shared with the
maintainer. If no private channel is available, open a minimal public issue
asking how to make contact and include no security details.

Do not publish an exploit, secret value, key, token, credential-store path,
session content, or protected user data. A useful report includes:

- the MAINFRAME version or commit;
- the affected agent product and version, including Desktop or CLI;
- the affected component, event, or action;
- sanitized steps, observed behavior, expected behavior, and likely impact;
- whether a real credential or external system may have been exposed.

Rotate a real credential if it may have been exposed. Do not send the
credential with the report.

## Security scope

Report behavior with any of these effects.

- Overwrites unrelated global configuration or native product state.
- Adapts permissions, sandboxing, tools, hooks, or roles unsafely.
- Exposes a value handled by the `mainframe-secret` helper.
- Lets a positively recognized protected operation pass, or blocks unrelated
  work only because a guard had an operational failure.
- Mixes attribution across projects, sessions, agents, or concurrent work.
- Installs payload outside the [documented MAINFRAME delivery boundary](docs/installation/README.md#repository-and-payload-boundary)
  or a DSH package's declared files.
- Adds telemetry or unexpected network traffic, or stores activity outside
  the applicable documented plugin data boundary.
- Claims native enforcement or runtime verification without supporting
  evidence.

MAINFRAME hooks are defense in depth. They do not replace native permissions,
sandboxing, or authority checks. A capability that the current product cannot
support is not by itself a vulnerability, but claiming unsupported enforcement
as effective can be one.

## Supported code

Security fixes target the maintained [MAINFRAME adapters](README.md#where-mainframe-installs)
and [DSH packages](docs/installation/dsh-adapter.md). The maintainer will assess
the supplied evidence and avoid public disclosure until a correction or safe
migration path is understood.

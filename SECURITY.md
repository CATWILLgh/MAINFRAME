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

Security problems include behavior that:

- overwrites unrelated global configuration or native product state;
- adapts permissions, sandboxing, tools, hooks, or roles unsafely;
- exposes a value handled by the `secret` helper;
- lets a positively recognized protected operation pass, or blocks unrelated
  work only because a guard had an operational failure;
- mixes attribution across projects, sessions, agents, or concurrent work;
- installs repository files not listed in `ADAPTATION.example.json`;
- adds telemetry, a permanent activity log, or unexpected network traffic;
- claims native enforcement or runtime verification without supporting
  evidence.

MAINFRAME hooks are defense in depth. They do not replace native permissions,
sandboxing, or authority checks. A capability that the current product cannot
support is not by itself a vulnerability, but claiming unsupported enforcement
as effective can be one.

## Supported code

Security fixes target the current maintained repository state. Archived
adapters and historical material are references, not supported installation
sources. The maintainer will assess the supplied evidence and avoid public
disclosure until a correction or safe migration path is understood.

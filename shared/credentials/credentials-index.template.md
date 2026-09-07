# Credentials index

This is the centralized local credential catalog for MAINFRAME. The working
copy is `shared/credentials/credentials-index.md` and must remain ignored by
Git.

This file contains service metadata and credential references only. Never put
passwords, tokens, private keys, cookies, recovery codes, or other secret values
here. Actual values live outside the repository and are delivered through the
`secret` command or a native credential mechanism.

Credential names used with `secret` must match `[A-Z_][A-Z0-9_]*`.

## Servers

<!--
### <service name>

- Purpose:
- Environment:
- Address:
- Access:
- Credentials:
  - `SERVICE_NAME_PASSWORD`
- Notes:
-->

## APIs and external services

<!--
### <service name>

- Purpose:
- Dashboard:
- Credentials:
  - `SERVICE_NAME_API_KEY`
- Notes:
-->

## Git and package registries

<!--
### <provider>

- Account:
- Native authentication:
- Credentials:
  - `PROVIDER_TOKEN`
- Notes:
-->

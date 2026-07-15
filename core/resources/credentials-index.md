# Credentials index

> Personal directory of servers / services / credentials. Lives at `{{mainframe.config_root}}/credentials-index.md`.
>
> **This file does NOT contain secret values.** Only descriptions and pointers ("get the password via `secret get foo`").
> The actual secret values live in `~/.config/credentials/secrets.env` and are accessed through the `secret` helper.
>
> Format: free-form Markdown. Edit by hand. The structure below is a suggestion — adapt to your scale.

---

## VPS / servers

<!--
Template for a single server. Copy and fill in. Delete this comment when adding real entries.

### <short-name> (<public hostname or IP>)
- **Purpose:** what runs on it / why you have it.
- **SSH:** `ssh <alias from ~/.ssh/config>` (key: `~/.ssh/id_<name>`).
- **Root password** (if applicable): `secret get <short-name>-root-pass`.
- **Service tokens** (one line per service):
  - `<service>` token — `secret get <short-name>-<service>-token`.
- **Admin URLs / panels** (no creds): `https://...`.
- **Notes:** anything you want to remember (provider, region, backup policy, monitoring dashboard).
-->

---

## APIs / external services

<!--
Template for an external service / API. Copy and fill in.

### <service name>
- **Purpose:** what you use it for.
- **Token / key:** `secret get <service>-api`.
- **Org / account ID** (if applicable): `secret get <service>-org`.
- **Dashboard:** https://...
- **Notes:** rate limits, quota, billing reminders.
-->

---

## Git providers / package registries

<!--
Template for git / package providers.

### GitHub
- **CLI auth:** `gh auth status` (uses `gh auth login`, stored in macOS Keychain / Linux secret-service).
- **Personal access token** (if needed outside `gh`): `secret get github-pat`.
- **Username:** ...
-->

---

## Reminders

- Add a server / service here when you add its secret via `secret set NAME value`. The index is your only map — if it is not here, you will forget what `NAME` was for.
- Remove the section when you delete the secret. Use `secret list` to find orphans (names in the store that are no longer in this index).
- This file is read by the active coding environment when you reference a service by name. Keep service short-names stable so it can find them.

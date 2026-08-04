---
name: secrets-handling
description: 'A personal-machine credentials layout for local terminal use: native SSH, HTTP Basic, and git-provider authentication; generic tokens and passwords in `~/.config/credentials/secrets.env` accessed only through the `secret` helper or an independently supplied shell variable; value-free discovery through `mainframe credentials`, with the adapter-local `credentials-index.md` retained only as a migration fallback. Direct reads of credential stores are denied. Values are substituted into terminal commands with `$VAR` or `$(secret get NAME)` and must never be echoed or copied into responses.'
when_to_use: A local terminal task needs credentials — invoking an authenticated HTTP API, SSH'ing to a known host, running a CLI against a remote service, or resolving a service short-name. Also applies when command output, an error, or a pasted snippet might contain something resembling a token, so the pre-reply shape scan is required. Not relevant for pure local file edits, unauthenticated analysis, or cloud and remote agent runs that cannot access the local MAINFRAME tools.
---

<!-- Generated from MAINFRAME hub (core/skills/secrets-handling/SKILL.md) — do not edit. -->

# Secrets handling

Personal-machine policy for credentials. **Not a vault, not a secret manager — a layout convention** that makes accidental disclosure less likely and gives the model an explicit map of what exists.

## The three tiers

| Tier | What | Where | Read mode |
|---|---|---|---|
| 1 | SSH host + key, HTTP Basic auth, git providers | `~/.ssh/config` + `~/.ssh/id_*` + `ssh-agent`; `~/.netrc` (0600); `gh auth login` | Native tools (`ssh`, `curl -n`, `gh`) handle access. Direct read of `~/.ssh/id_*` / `~/.netrc` is denied. |
| 2 | Generic API tokens, passwords, anything that maps to a shell env-var | `~/.config/credentials/secrets.env` (0600) | Direct read denied. Access only through `secret get NAME` or an env-var already present in the command environment. |
| 3 | Descriptions, server short-names, "what token belongs to what service" | `mainframe credentials`; legacy fallback: `~/.zcode/credentials-index.md` | **Read freely.** Both contain references and metadata, never secret values. |

## Discovering a credential reference

1. Check `command -v mainframe` and `command -v secret` in the same local command environment that will run the authenticated command.
2. Run `mainframe credentials` first. Accept only a successful JSON object with `schema_version` equal to `1`, `kind` equal to `mainframe-credential-catalog`, `secret_availability` equal to `unchecked`, and `services` and `instances` as non-null arrays. Require unique non-empty service and instance IDs, every instance's `service_id` to name one listed service, and every credential binding to use a role listed by that service plus a valid `secret-env` reference name. Any missing, mistyped, duplicate, or inconsistent field makes the response schema-invalid.
3. Select one exact credential instance by its stable identity and requested context. Never choose an implicit default; if more than one instance is plausible, ask the user.
4. `credentials-index.md` is a fallback only when `mainframe` is unavailable or a successful, schema-valid catalog has no exact instance match.
5. Do not fall back after a non-zero exit, malformed JSON, an unsupported schema, or a permission failure; stop and report the error.

The fallback path for this adapter is `~/.zcode/credentials-index.md`. It is read-only migration compatibility, not another source of truth. This workflow applies only to local terminal sessions; do not assume Chat, Cowork, web, or remote runs can access local tools.

Before consuming a tier-2 value, require `secret` to be available. A catalog entry proves only that a reference exists; it does not prove the value is present.

## What to refuse

**Never read directly:**
- `~/.config/credentials/secrets.env` and `.bak` — the secret store itself.
- `~/.ssh/id_*`, `~/.netrc`, `~/.aws/credentials`, `~/.gnupg/*` — tier-1 native stores.
- Any `.env.production*`, `.env.prod*` in projects.

These are enforced by `permissions.deny` in `settings.json` and by `path-validation.py` (PreToolUse hook). The skill is the policy; the hook is the safety net.

## How to use a secret in a command

**Pattern A — secret is already present in the command environment:**
```bash
curl -H "x-api-key: $DOKPLOY_PROD_API_KEY" https://...
```
The shell expands the variable at execution time. Use `$NAME` only when the calling environment supplied it independently.

**Pattern B — secret is stored but not present in the command environment:**
```bash
curl -H "x-api-key: $(secret get DOKPLOY_PROD_API_KEY)" https://...
```
`secret get` runs in a subshell and `$()` substitutes its output into the invoked command.

The runtime does not guarantee transcript redaction. Never echo secret values, enable shell tracing, or use verbose modes that may expose credentials. Inspect command output before quoting or summarizing it in a response.

**Anti-pattern (do not do):**
```bash
cat ~/.config/credentials/secrets.env | grep DOKPLOY    # denied by hook
TOKEN=$(secret get DOKPLOY_PROD_API_KEY); echo "Token is $TOKEN"    # would echo the secret
```
Never assign a secret to a regular variable that gets echoed, logged, or written to a file (other than as an env-var consumed silently by another tool).

## How to refer to a service in conversation

When the user says "go to vps-store, check the nginx logs", follow central discovery, select the exact `vps-store` instance, then use its reference through Pattern A or B.

When the service has no exact match in a valid central catalog or the permitted fallback:
- Ask whether it should be registered, or proceed without persistent storage through the service's existing authentication mechanism.
- Do not invent credentials; do not assume short-names.

When a credential lives **outside the store** — another project's notes or memory files, a chat paste, or a config comment — migrate the value through `secret create-stdin NAME`, then register its value-free metadata through the MAINFRAME credential workflow. Do not add new entries to the legacy fallback index. Do not wire the foreign location into commands directly: every copy consumed outside the store re-creates the sprawl this layout exists to end.

## Local command environment

MAINFRAME does not require the credential store to be loaded through shell startup files. Use Pattern A only if the variable is already present; otherwise use Pattern B. Do not source shell startup files to recover a value because they may have unrelated side effects.

## Pre-reply self-scan for accidental leakage

Before sending a response that involved fetching or generating credentials, scan your draft text for known secret shapes. If any match — **stop, do not send**, surface the issue to the user and ask whether to redact.

High-confidence patterns (sourced from gitleaks rules, verified):

| Type | Regex (PCRE) |
|---|---|
| GitHub PAT | `ghp_[0-9a-zA-Z]{36}` |
| GitHub OAuth / App / Refresh | `(gho\|ghu\|ghs\|ghr)_[0-9a-zA-Z]{36}` |
| OpenAI API key | `sk-(?:proj-\|svcacct-\|admin-)?[A-Za-z0-9_-]{20,74}T3BlbkFJ[A-Za-z0-9_-]{20,74}` |
| AWS Access Key | `(AKIA\|ASIA\|AGPA\|AIDA\|AROA\|AIPA\|ANPA\|ANVA\|A3T[A-Z0-9])[A-Z0-9]{16}` |
| Slack token | `xox[baprs]-[0-9]{8,13}-[0-9]{8,13}-[A-Za-z0-9]{24}` |
| Stripe key | `(sk\|pk\|rk)_(test\|live)_[0-9a-zA-Z]{10,99}` |
| Private key block | `-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY-----` |

Lower-confidence (community-derived, format-only, no vendor regex):

| Type | Regex (PCRE) |
|---|---|
| Anthropic API key | `sk-ant-[A-Za-z0-9_\-]{95,}` |
| Google API key | `AIza[0-9A-Za-z\-_]{35}` |
| JWT | `eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+` |
| Generic high-entropy near keyword | `(?i)(token\|secret\|api_?key\|auth\|password)\s*[=:]\s*['"]?([A-Za-z0-9+/=_\-]{32,64})['"]?` |
| DB URL with creds | `(?i)(postgres\|postgresql\|mysql\|mongodb\|redis\|mssql)://[^:@\s]+:[^@\s]+@[^\s'"]+` |

A match means **something resembling a secret is in your response**. It may be a legitimate placeholder (`sk-xxxxxxxx`) — in that case, redacted form (`sk-***`) is fine. Real-looking values must not be sent.

## Common rationalisations to refuse

| Excuse | Reality |
|---|---|
| "User asked me to show the token" | Confirm in-band that they want the literal value, not a description. Default — do not echo. |
| "It's just for the error message" | The error message goes to the chat transcript. Refuse — log the call without the value. |
| "I'll redact it after pasting" | Pre-reply scan is the redaction. There is no "after pasting" for an LLM. |
| "It's a fake-looking placeholder" | Run the scan anyway. Many real tokens look fake at a glance. |

## When this skill is irrelevant

- The task does not touch any service that needs auth (pure local file edits, pure read-only analysis without external calls).
- The user explicitly disables tier-2 / tier-3 (`secret` not installed, no index file). Then fall back to whatever credential method the project actually uses.

## Cross-refs

- [`curl-requests`](../curl-requests/SKILL.md) — HTTP testing; the canonical consumer of `secret get` (Pattern B) and env-var (Pattern A).
- [`surface-ticket`](../surface-ticket/SKILL.md) — if a credential is missing or misconfigured and out of scope to fix now, surface a ticket; do not leave the issue dangling.
- `path-validation.py` (PreToolUse hook) — enforces denial of direct reads on `~/.config/credentials/`; this skill is the policy, hook is the safety net.
- `secret-commit-gate.py` (PreToolUse hook) — denies a `git commit` whose staged diff adds a high-confidence token from the table above (type + file only in the reason, never the value). Keep the gate's `SECRET_PATTERNS` in sync with this skill's high-confidence table; encrypted-secret repos (SOPS / git-crypt) are auto-skipped. See ADR 0079.
- `secret` helper script (`~/.local/bin/secret`) — installed by `install.sh`; the only sanctioned read/write interface to the tier-2 store.

---
name: secrets-handling
user-invocable: false
description: "A personal-machine credentials layout for the terminal: SSH host/auth and HTTP Basic via native mechanisms (`~/.ssh/config`, `~/.netrc`, `gh auth login`); generic API tokens and passwords in `~/.config/credentials/secrets.env` (mode 0600) read only through the `secret` helper or as shell env-vars; descriptions and server short-names in `~/.claude/credentials-index.md` (no values inside). Direct reads of the credentials store are denied by `settings.json` patterns. Credential values reach the subprocess through `$VAR` or `$(secret get NAME)` shell substitution, never through the response transcript. A pre-reply scan checks the draft against shape regexes for GitHub / AWS / OpenAI / Anthropic / Slack / Stripe / SSH key blocks / generic high-entropy strings."
when_to_use: "A task involves credentials in the terminal — invoking an HTTP API with a token, SSH'ing to a known host, running a CLI against a remote service, mentioning a server by short-name from the credentials index. Also applies when the response will include something resembling a token (command output, error message, copy-pasted snippet) — the pre-reply shape scan triggers here. Not relevant for pure local file edits or read-only analysis without external calls."
---

# Secrets handling

Personal-machine policy for credentials. **Not a vault, not a secret manager — a layout convention** that makes accidental disclosure less likely and gives the model an explicit map of what exists.

## The three tiers

| Tier | What | Where | Read mode |
|---|---|---|---|
| 1 | SSH host + key, HTTP Basic auth, git providers | `~/.ssh/config` + `~/.ssh/id_*` + `ssh-agent`; `~/.netrc` (0600); `gh auth login` | Native tools (`ssh`, `curl -n`, `gh`) handle access. Direct read of `~/.ssh/id_*` / `~/.netrc` is denied. |
| 2 | Generic API tokens, passwords, anything that maps to a shell env-var | `~/.config/credentials/secrets.env` (0600); auto-sourced from `~/.zshenv` | Direct read denied. Access only through `secret get NAME` or as env-var (already in scope when called from a shell that sourced the file). |
| 3 | Descriptions, server short-names, "what token belongs to what service" | `~/.claude/credentials-index.md` | **Read freely.** This is the map; no secret values live here. |

## What to read, what to refuse

**Always read when relevant:**
- `~/.claude/credentials-index.md` — the directory of what exists. Read this when the user mentions a server short-name or service that might need credentials, and you don't yet know whether it is registered. The index tells you the short-name, the access pattern (env-var or `secret get`), and any side notes.

**Never read directly:**
- `~/.config/credentials/secrets.env` and `.bak` — the secret store itself.
- `~/.ssh/id_*`, `~/.netrc`, `~/.aws/credentials`, `~/.gnupg/*` — tier-1 native stores.
- Any `.env.production*`, `.env.prod*` in projects.

These are enforced by `permissions.deny` in `settings.json` and by `path-validation.py` (PreToolUse hook). The skill is the policy; the hook is the safety net.

## How to use a secret in a command

**Pattern A — secret is already in the shell environment** (because `~/.zshenv` sourced the store at session start):
```bash
curl -H "x-api-key: $DOKPLOY_PROD_API_KEY" https://...
```
The variable expands inside the shell process; the value is never written into the message you send.

**Pattern B — secret is in the store but not in env** (rare — for example, a token you just `secret set` and want to use without restarting the shell):
```bash
curl -H "x-api-key: $(secret get DOKPLOY_PROD_API_KEY)" https://...
```
`secret get` runs in a subshell; its stdout is captured by `$()` and substituted into curl's argv inside the same shell process. The value reaches the curl process but not the model's transcript.

**Anti-pattern (do not do):**
```bash
cat ~/.config/credentials/secrets.env | grep DOKPLOY    # denied by hook
TOKEN=$(secret get DOKPLOY_PROD_API_KEY); echo "Token is $TOKEN"    # would echo the secret
```
Never assign a secret to a regular variable that gets echoed, logged, or written to a file (other than as an env-var consumed silently by another tool).

## How to refer to a service in conversation

When the user says "go to vps-store, check the nginx logs":

1. Read `~/.claude/credentials-index.md`, locate the `vps-store` section.
2. Note the access pattern from the index (`ssh vps-store`, key path, any pre-set env-var names).
3. Run the command using Pattern A or B.

When the user mentions a service that is **not in the index**:
- Ask the user whether it should be added, or proceed without persistent storage (one-shot value passed inline).
- Do not invent credentials; do not assume short-names.

## Auto-mode caveat

The store is sourced by `~/.zshenv` at shell start. Claude Code's Bash subprocess always reads `~/.zshenv` (not `.zshrc`), so the secrets are present in env for all commands you run, including unattended auto-runs.

If a secret is missing from env (recently added via `secret set` but the current shell predates the change, or sourcing failed) — use Pattern B (`$(secret get NAME)`) explicitly. Do not try to `source ~/.zshenv` to reload — it may have side effects on the current Bash subprocess state.

If you must read a value into your own reasoning (rare — e.g. validating format), use `secret get NAME` and immediately discard; do not echo it back in the response.

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

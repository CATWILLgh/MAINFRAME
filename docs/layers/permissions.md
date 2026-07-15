# Layer: Permissions

> **Architecture note (three-tool hub, 2026-07-14):** MAINFRAME targets Claude Code, OpenCode, and Codex. Shared sources live in `core/`, tool-specific sources in `adapters/<tool>/`, and `render_core.py` plus the OpenCode/Codex builders populate `dist/<tool>/`. Do not hand-edit generated outputs. The path-scoped Rules layer is authored directly in `dist/claude-code/rules/`; non-permission fields in `dist/claude-code/settings.json` are also user-owned there.


> Shared allow/deny/ask policy authored in `core/permissions/rules.json`, then rendered or conservatively projected into the controls each of the three runtimes can express.

> Last updated: 2026-07-14 (three-tool projection and current policy summary).

---

## Where it lives / How to install

- Source of truth: `core/permissions/rules.json` — hub-owned `allow`, `deny`, and `ask` rules.
- Claude Code target: `dist/claude-code/settings.json` — the permission lists are rendered by key-merge; `permissions.defaultMode` remains in the target settings.
- OpenCode target: `adapters/opencode/build_opencode.py` projects representable entries and merges the `permission` block into `~/.config/opencode/opencode.json`. This is best-effort and is not a safety boundary.
- Codex target: `adapters/codex/build_codex.py` emits only exact safe shell-prefix projections to `dist/codex/rules/mainframe.rules`, installed at `${CODEX_HOME:-~/.codex}/rules/mainframe.rules`; unrepresentable rules are omitted and reported.
- Claude Code runtime: `~/.claude/settings.json` (symlink to the hub file).
- In any project: `<repo>/.claude/settings.json` (project-scope) and `<repo>/.claude/settings.local.json` (gitignored, local).
- Run `python3 tools/render_core.py --write` for the Claude projection; the OpenCode and Codex builders run during `install.sh --opencode` and `install.sh --codex`.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Rule syntax (Bash, the primary case)

Format: `"Tool"` or `"Tool(specifier)"`. Source: `code.claude.com/docs/en/permissions`.

> "Bash permission rules support wildcard matching with `*`. Wildcards can appear at any position in the command, including at the beginning, middle, or end."

| Pattern | What it matches | Example commands |
|---|---|---|
| `Bash(npm run build)` | exactly this command with no extra args | `npm run build` |
| `Bash(npm run test *)` | starts with `npm run test ` + anything | `npm run test unit`, not `npm run testfoo` |
| `Bash(npm *)` | starts with `npm ` (with a space) | `npm install`, not `npmx` |
| `Bash(npm*)` | starts with `npm` (no space) | `npm install` AND `npmx run` |
| `Bash(* install)` | ends with ` install` | `pnpm install`, `apt install` |
| `Bash(git * main)` | `git <whatever> main` | `git checkout main`, `git push origin main` |
| `Bash(* --version)` | ends with ` --version` | `node --version` |
| `Bash(* --help *)` | contains ` --help ` | `npm --help install` |

**Word-boundary rule (critical):**

> "When `*` appears at the end with a space before it (like `Bash(ls *)`), it enforces a word boundary, requiring the prefix to be followed by a space or end-of-string. For example, `Bash(ls *)` matches `ls -la` but not `lsof`. In contrast, `Bash(ls*)` without a space matches both `ls -la` and `lsof`."

**`:*` suffix:**

> "The `:*` form is only recognized at the end of a pattern." — equivalent to `<prefix> *` (with a space + word boundary). `Bash(ls:*)` == `Bash(ls *)`.

**A single `*` matches any sequence, including spaces** — so one wildcard can span multiple arguments.

### 1.2. Evaluation order

> "Rules are evaluated in order: **deny rules first, then ask, then allow.** The first matching rule wins."

```
1. deny — match → BLOCKED (even in bypassPermissions mode)
2. ask  — match → prompt (or deny in dontAsk/headless)
3. allow — match → permitted without a prompt
4. no match → default behavior (prompt in interactive, deny in dontAsk)
```

**`bypassPermissions` exception:** deny rules are applied always, even in this mode. Quote: "If a deny rule matches, the tool is blocked, even if `bypassPermissions` mode is active."

### 1.3. Cross-scope: permission rules **merge**, not override

> "Permission rules behave differently because they merge across scopes rather than override."
> "If user settings allow a permission and project settings deny it, the deny rule blocks it. The reverse is also true: a user-level deny blocks a project-level allow, because deny rules from any scope are evaluated before allow rules."

Collection order:
1. All `deny` from ALL scopes (managed, user, project, local) → evaluated first.
2. All `ask` from all scopes → evaluated second.
3. All `allow` from all scopes → evaluated third.

**Consequence:** adding a `deny` in any layer (e.g. in the hub via symlink) is a hard guard that cannot be bypassed by an `allow` in another layer.

### 1.4. Composite Bash commands — official decomposition

> "Claude Code is aware of shell operators, so a rule like `Bash(safe-cmd *)` won't give it permission to run the command `safe-cmd && other-cmd`. The recognized command separators are `&&`, `||`, `;`, `|`, `|&`, `&`, and newlines. **A rule must match each subcommand independently.**"

That is, the command is decomposed into an AST by separators, and the pattern check is applied to each subcommand.

**Hardening 2026-w15:** prior to this update, compound commands were a bypass route (backslash flags, env var prefixes, `/dev/tcp` redirects, compound operators). Now closed. Source: `code.claude.com/docs/en/whats-new/2026-w15`.

### 1.5. Mode-dependent behavior of `ask`

| Mode | What an `ask` rule does |
|---|---|
| `default` (interactive) | Shows a prompt to the user |
| `dontAsk` | "ask rules are denied rather than prompting" (source: permission-modes) |
| `bypassPermissions` | `ask` rules are ignored entirely; `deny` still blocks |
| Headless `-p` | Not explicitly documented; by analogy with `dontAsk` — likely deny |

**`acceptEdits` mode auto-approves only filesystem commands:** `mkdir`, `touch`, `rm`, `rmdir`, `mv`, `cp`, `sed`, plus those with safe env-prefixes (`LANG=C`, `NO_COLOR=1`) and process wrappers (`timeout`, `nice`, `nohup`). Standard rules apply to all other commands.

### 1.6. Special cases

- **`eval`** — always requires approval, regardless of rules. Source: `agent-sdk/secure-deployment`.
- **`Bash`** without a specifier (bare-name rule) — matches ALL Bash commands and removes the tool from the permission pipeline early. Anti-pattern.
- **`allowManagedPermissionRulesOnly: true`** (managed scope) — ignores user/project rules for permissions, managed only. Corporate lockdown.

### 1.7. Auto-mode classifier (2026-05-28)

Auto-mode (`defaultMode: "auto"`) adds a 4-step classification algorithm between the rules and the model:

1. Actions matching `permissions.allow` or `permissions.deny` — resolved immediately.
2. Read-only operations and file edits within the working directory — auto-approved (except protected paths).
3. Everything else → the classifier.
4. If the classifier blocks, Claude receives the reason and tries an alternative.

**Critical consequence for `ask`:** the rule does not reach step 1, does not reach step 2 → falls through to the classifier. The classifier blocks destructive actions **silently**, without an interactive prompt. This changes the semantics of `ask` in auto-mode: a rule that in default-mode yields a prompt will yield a silent block in auto-mode.

**Default block categories (examples from docs):** "destroying data through force-pushes or mass deletions", "deleting remote git branches from vague instructions", "degrading security by disabling logging", "retrying failed deployment commands with safety-check flags removed", "irreversibly destroying files that existed before the session". The full list is available via the `claude auto-mode defaults` command; it is not published in full in the docs.

### 1.8. Hub 3-tier model (2026-05-28)

Categorization of rules in `core/permissions/rules.json` into 3 tiers with explicit criteria. Sources: OWASP LLM06 (Excessive Agency), NIST SP 800-53 AC-6/CM-7 (least privilege/functionality), Anthropic Auto Mode docs, real-world incidents (Replit 2025-07, PocketOS 2026-04, nx supply chain 2025-08).

**Tier 1 — `deny`** (hard block, no override): irreversible + out-of-scope + undermines security + catastrophic scale. Any single criterion is sufficient.

**Tier 2 — `ask`** (prompt in default-mode, classifier-block in auto-mode): potentially destructive with limited scope + non-standard for the current task + crosses trust boundaries + ambiguous request + destructive action.

**Tier 3 — `allow`** (audited without prompt): isolated within the working directory + reversible + explicitly requested. Read-only commands do NOT require explicit `allow` rules — Claude Code auto-allows them.

### 1.9. Path-scoped control — via hook only

Matcher-based path control (e.g. `Bash(rm -rf ./private-dir/*)`) is **unreliable**: Claude may write absolute or relative paths, there is no normalization before comparison, and glob/tilde/variable expansion is not resolved before matching. The only reliable approach is a `PreToolUse` hook with a script that parses the command via `shlex`, resolves paths with `os.path.abspath`/`expanduser`/`expandvars`, and checks membership against `$CLAUDE_PROJECT_DIR`.

Caveat: a hook `permissionDecision: "ask"` in auto-mode transitions to `"defer"` — it does not show a UI prompt but instead holds the call for the Agent SDK wrapper. That is, the hook provides path-precision but does not restore interactivity in auto-mode.

---

## 2. Hub usage & ADRs

### 2.1. Current authored policy

As verified from `core/permissions/rules.json` on 2026-07-14, the policy contains 100 `allow`, 88 `deny`, and 46 `ask` entries. Claude Code's `permissions.defaultMode` is separately user-owned in `dist/claude-code/settings.json` and is currently `auto`. Do not duplicate the full lists here: inspect the authored JSON for the current policy, then use the runtime-specific builder report to see which entries were projectable.

The current Codex projection contains 101 `prefix_rule` entries: 76 `allow`, 3 `forbidden`, and 22 `prompt`. A lower count than the authored policy is expected because Codex rules express shell argv prefixes only; omission is safer than broadening an untranslatable source rule. The builder validates the three decision classes with the installed `codex execpolicy` parser during `./install.sh --codex` before publishing any generated output.

### 2.2. Canonical claim vs hub empirical — discrepancies

Empirical tables from tests in this same session (2026-05-27 and 2026-05-28). Anthropic docs describe **a single matching engine** for all three lists — no documented differences between forms. The observed behavior is the opposite:

| Pattern | Layer | Docs claim | Hub empirical | Date |
|---|---|---|---|---|
| `Bash(*pat*)` anywhere | `deny` | Should work (universal) | **Works** | 2026-05-27 |
| `Bash(prefix:*)` | `deny` | Should work | **Does NOT block** | 2026-05-27 |
| `Bash(prefix*)` | `deny` | Should work | **Does NOT work** | 2026-05-27 |
| `Bash(*pat*)` anywhere | `ask` | Should work | **Does NOT fire** (silent pass) | 2026-05-28 |
| `Bash(* pat *)` anywhere with spaces | `ask` | Should work | **Does NOT fire** | 2026-05-28 |
| `Bash(* pat)` ends-with | `ask` | Should work | **Does NOT fire** | 2026-05-28 |
| `Bash(rm -rf *)` prefix+space | `ask` | Should work | **Works** (direct + composite via `cd && rm`) | 2026-05-28 |
| `Bash(git commit --no-verify*)` prefix | `ask` for composite `cd /dir && git commit --no-verify ...` | Should work (sub-decomposition) | **Does NOT fire** — unresolved discrepancy | 2026-05-28 |
| Composite decomposition via `&&`/`;`/`\|` | all | Works (hardened 2026-w15) | **Works for `rm -rf`**, **does not work for `git commit --no-verify`** | 2026-05-28 |

**What this means for us:**
- Docs assert a single matcher → our runtime quirks cannot be derived from theory, **empirical testing only**.
- The anywhere-form is reliable only in `deny`. In `ask` — it does not work at all.
- The prefix-form works in `ask` for some commands and not others — the reason is unknown (see gray zones).

---

## 3. Gray zones / open questions

1. **Why does `Bash(prefix:*)` in `deny` not block, while in `allow` it does block?** Docs describe a single matching engine; the difference is an undocumented runtime quirk.
2. **Why does `Bash(git commit --no-verify*)` not fire in `ask` on composite commands, while `Bash(rm -rf *)` does?** Hypotheses: quoting (`-m "..."`), trailing flag combinations, specific handling of `--no-verify`. Requires further experimentation.
3. **`acceptEdits` mode + `ask` rules** — behavior is undocumented. Empirical: `rm -rf` fires (denied); `git commit --no-verify` does not fire. Inconsistent.
4. **`ask` rules in headless `-p` mode (without `--dontAsk`)** — by analogy with dontAsk it should be deny, but this is not stated explicitly.
5. **Symlinks on settings paths** — not mentioned in docs. Empirically: they work (the hub uses them), the file watcher picks them up.
6. **The size of the file watcher "brief delay"** — not documented; empirical observation — milliseconds to seconds.
7. **`--force-with-lease` under the general pattern `*--force*`** — the anywhere-form `Bash(*--force*)` will also catch `--force-with-lease` (undesirable: it is the safer push variant). A precise technical block is not implemented; the behavioral guard in CLAUDE.md covers misuse.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7 `/websites/code_claude`):**
- `code.claude.com/docs/en/permissions` — wildcards, compound commands, settings precedence.
- `code.claude.com/docs/en/settings` — scopes, priority, file watcher.
- `code.claude.com/docs/en/agent-sdk/permissions` — deny in bypassPermissions, dontAsk semantics, eval order.
- `code.claude.com/docs/en/permission-modes` — `acceptEdits` filesystem command list, `dontAsk` semantics.
- `code.claude.com/docs/en/agent-sdk/secure-deployment` — AST parsing, `eval` always requires approval.
- `code.claude.com/docs/en/whats-new/2026-w15` — compound command hardening.
- `code.claude.com/docs/en/server-managed-settings` — `allowManagedPermissionRulesOnly`.

**Internal:**
- Hub empirical data 2026-05-27 (deny: prefix vs anywhere) and 2026-05-28 (ask: prefix vs anywhere, composite, runtime quirks) — table §2.2.

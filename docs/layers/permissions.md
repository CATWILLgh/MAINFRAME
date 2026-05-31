# Layer: Permissions

> Слой Claude Code, контролирующий, какие tool-вызовы разрешены, запрещены или требуют подтверждения у пользователя. В хабе: `export/settings.json` блок `permissions.{allow, deny, ask}` → симлинк в `~/.claude/settings.json` → действует во всех проектах.

> Последнее обновление: 2026-05-28 (3-секционный rewrite).

---

## Где живёт / Как install

- В хабе: `export/settings.json` — поля `permissions.allow`, `permissions.deny`, `permissions.ask`, плюс `permissions.defaultMode`.
- На машине: `~/.claude/settings.json` (симлинк на хабовый файл).
- В любом проекте: `<repo>/.claude/settings.json` (project-scope) и `<repo>/.claude/settings.local.json` (gitignored, local).
- Активация: одновременно со всем `export/settings.json` через симлинк. Отдельной активации только для permissions нет. File watcher Claude Code подхватывает правки «with brief delay» без рестарта.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Синтаксис правил (Bash, основной случай)

Формат: `"Tool"` или `"Tool(specifier)"`. Источник: `code.claude.com/docs/en/permissions`.

> «Bash permission rules support wildcard matching with `*`. Wildcards can appear at any position in the command, including at the beginning, middle, or end.»

| Pattern | Что match'ит | Пример команд |
|---|---|---|
| `Bash(npm run build)` | строго эту команду без extra args | `npm run build` |
| `Bash(npm run test *)` | starts with `npm run test ` + что угодно | `npm run test unit`, не `npm run testfoo` |
| `Bash(npm *)` | starts with `npm ` (с пробелом) | `npm install`, не `npmx` |
| `Bash(npm*)` | starts with `npm` (без пробела) | `npm install` И `npmx run` |
| `Bash(* install)` | заканчивается ` install` | `pnpm install`, `apt install` |
| `Bash(git * main)` | `git <whatever> main` | `git checkout main`, `git push origin main` |
| `Bash(* --version)` | заканчивается ` --version` | `node --version` |
| `Bash(* --help *)` | содержит ` --help ` | `npm --help install` |

**Word-boundary правило (критическое):**

> «When `*` appears at the end with a space before it (like `Bash(ls *)`), it enforces a word boundary, requiring the prefix to be followed by a space or end-of-string. For example, `Bash(ls *)` matches `ls -la` but not `lsof`. In contrast, `Bash(ls*)` without a space matches both `ls -la` and `lsof`.»

**`:*` суффикс:**

> «The `:*` form is only recognized at the end of a pattern.» — эквивалентен `<prefix> *` (с пробелом + word boundary). `Bash(ls:*)` == `Bash(ls *)`.

**Один `*` matches любую sequence, включая пробелы** — поэтому один wildcard может span несколько аргументов.

### 1.2. Evaluation order

> «Rules are evaluated in order: **deny rules first, then ask, then allow.** The first matching rule wins.»

```
1. deny — match → BLOCKED (даже в bypassPermissions mode)
2. ask  — match → prompt (или deny в dontAsk/headless)
3. allow — match → разрешено без prompt'а
4. no match → default behavior (prompt в interactive, deny в dontAsk)
```

**`bypassPermissions` exception:** deny rules применяются всегда, даже в этом mode. Цитата: «If a deny rule matches, the tool is blocked, even if `bypassPermissions` mode is active.»

### 1.3. Cross-scope: permission rules **merge**, не override

> «Permission rules behave differently because they merge across scopes rather than override.»
> «If user settings allow a permission and project settings deny it, the deny rule blocks it. The reverse is also true: a user-level deny blocks a project-level allow, because deny rules from any scope are evaluated before allow rules.»

Порядок сбора:
1. Все `deny` от ВСЕХ scopes (managed, user, project, local) → проверяются первыми.
2. Все `ask` от всех scopes → вторыми.
3. Все `allow` от всех scopes → третьими.

**Следствие:** добавление `deny` в любом слое (например, в хабе через симлинк) — жёсткая защита, которую нельзя обойти `allow` в другом слое.

### 1.4. Composite Bash commands — официальная декомпозиция

> «Claude Code is aware of shell operators, so a rule like `Bash(safe-cmd *)` won't give it permission to run the command `safe-cmd && other-cmd`. The recognized command separators are `&&`, `||`, `;`, `|`, `|&`, `&`, and newlines. **A rule must match each subcommand independently.**»

То есть команда декомпозируется в AST по разделителям, и pattern check применяется к каждой sub-команде.

**Hardening 2026-w15:** до этого update'а compound commands были bypass route (backslash flags, env var prefixes, `/dev/tcp` redirects, compound operators). Сейчас закрыто. Источник: `code.claude.com/docs/en/whats-new/2026-w15`.

### 1.5. Mode-зависимое поведение `ask`

| Mode | Что делает `ask` rule |
|---|---|
| `default` (interactive) | Показывает prompt пользователю |
| `dontAsk` | «ask rules are denied rather than prompting» (источник: permission-modes) |
| `bypassPermissions` | `ask` rules игнорируются полностью; `deny` всё ещё блокирует |
| Headless `-p` | Не документировано явно; по аналогии с `dontAsk` — likely deny |

**`acceptEdits` mode auto-approves только filesystem команды:** `mkdir`, `touch`, `rm`, `rmdir`, `mv`, `cp`, `sed`, плюс с safe env-prefixes (`LANG=C`, `NO_COLOR=1`) и process wrappers (`timeout`, `nice`, `nohup`). На прочие команды стандартные правила работают.

### 1.6. Особые случаи

- **`eval`** — всегда требует одобрения, независимо от rules. Источник: `agent-sdk/secure-deployment`.
- **`Bash`** без specifier (bare-name rule) — matches ВСЕ Bash-команды и убирает tool из permission pipeline early. Антипаттерн.
- **`allowManagedPermissionRulesOnly: true`** (managed scope) — игнорирует user/project rules для permissions, только managed. Корпоративная блокировка.

### 1.7. Auto-mode classifier (2026-05-28)

Auto-mode (`defaultMode: "auto"`) добавляет 4-шаговый алгоритм классификации между правилами и моделью:

1. Действия matching `permissions.allow` или `permissions.deny` — resolve немедленно.
2. Read-only операции и file edits в working directory — auto-approve (кроме protected paths).
3. Всё остальное → классификатор.
4. Если классификатор блокирует, Claude получает причину и пробует альтернативу.

**Критическое следствие для `ask`:** правило не попадает в шаг 1, не попадает в шаг 2 → falls through to classifier. Классификатор блокирует destructive действия **молча**, без интерактивного prompt'а. Это меняет семантику `ask` в auto-mode: rule, который в default-mode даёт prompt, в auto-mode даёт silent block.

**Категории default block (примеры из docs):** «destroying data through force-pushes or mass deletions», «deleting remote git branches from vague instructions», «degrading security by disabling logging», «retrying failed deployment commands with safety-check flags removed», «irreversibly destroying files that existed before the session». Полный список — через `claude auto-mode defaults` команду; в docs не опубликован полностью.

Подробнее: [[permissions-auto-mode-classifier memory]].

### 1.8. 3-tier модель хаба (2026-05-28, ADR 0031)

Категоризация правил в `export/settings.json` по 3 уровням с явными критериями. Источники: OWASP LLM06 (Excessive Agency), NIST SP 800-53 AC-6/CM-7 (least privilege/functionality), Anthropic Auto Mode docs, real-world incidents (Replit 2025-07, PocketOS 2026-04, nx supply chain 2025-08).

**Tier 1 — `deny`** (hard block, no override): необратимое + выход за scope + подрыв безопасности + катастрофический масштаб. Любой один критерий достаточен.

**Tier 2 — `ask`** (prompt в default-mode, classifier-block в auto-mode): потенциально разрушительное с ограниченной областью + нестандартное для текущей задачи + пересечение границ доверия + ambiguous request + destructive action.

**Tier 3 — `allow`** (audit без prompt): изолировано в working dir + обратимо + явно запрошено. Read-only команды НЕ требуют явных `allow` правил — Claude Code auto-allows их.

Полные критерии с примерами: [[permissions-tier-model memory]].

### 1.9. Path-scoped control — только через hook

Matcher-based path control (например, `Bash(rm -rf ./inbox/*)`) **ненадёжен**: Claude может писать абсолютные или относительные пути, нормализации перед сравнением нет, glob/tilde/variable expansion не разрешается перед matching. Единственный надёжный способ — `PreToolUse` hook со скриптом, который парсит команду через `shlex`, разрешает пути через `os.path.abspath`/`expanduser`/`expandvars`, проверяет принадлежность к `$CLAUDE_PROJECT_DIR`.

Caveat: hook `permissionDecision: "ask"` в auto-mode переходит в `"defer"` — не даёт UI prompt, а сохраняет вызов для Agent SDK wrapper. То есть hook даёт path-precision, но не возвращает интерактивность в auto-mode.

---

## 2. Hub usage & ADRs

### 2.1. Текущие настройки в `export/settings.json`

```json
"permissions": {
  "defaultMode": "acceptEdits",
  "deny": [
    "Bash(rm -rf /)", "Bash(rm -rf /*)", "Bash(rm -rf ~)", "Bash(rm -rf ~/)", "Bash(rm -rf ~/*)",
    "Bash(*git push --force*)", "Bash(*git push -f *)",
    "Bash(*mkfs*)", "Bash(*dd if=*)"
  ],
  "ask": [
    "Bash(rm -rf *)",
    "Bash(git commit --no-verify*)", "Bash(git push --no-verify*)", "Bash(git rebase --no-verify*)",
    "Bash(npm install --no-verify*)", "Bash(pnpm install --no-verify*)"
  ],
  "allow": [ /* ~80 prefix-form rules, в основном `Bash(cmd:*)` */ ]
}
```

### 2.2. Canonical claim vs hub empirical — расхождения

Эмпирические таблицы из тестов в этой же сессии (2026-05-27 и 2026-05-28). Anthropic docs описывают **единый matching engine** для всех трёх списков — никаких documented различий между формами. Наблюдается обратное:

| Pattern | Слой | Docs claim | Hub empirical | Дата |
|---|---|---|---|---|
| `Bash(*pat*)` anywhere | `deny` | Должно работать (универсальный) | **Работает** | 2026-05-27 |
| `Bash(prefix:*)` | `deny` | Должно работать | **НЕ блокирует** | 2026-05-27 |
| `Bash(prefix*)` | `deny` | Должно работать | **НЕ работает** | 2026-05-27 |
| `Bash(*pat*)` anywhere | `ask` | Должно работать | **НЕ fires** (silent pass) | 2026-05-28 |
| `Bash(* pat *)` anywhere with spaces | `ask` | Должно работать | **НЕ fires** | 2026-05-28 |
| `Bash(* pat)` ends-with | `ask` | Должно работать | **НЕ fires** | 2026-05-28 |
| `Bash(rm -rf *)` prefix+space | `ask` | Должно работать | **Работает** (direct + composite через `cd && rm`) | 2026-05-28 |
| `Bash(git commit --no-verify*)` prefix | `ask` для composite `cd /dir && git commit --no-verify ...` | Должно работать (sub-decomposition) | **НЕ fires** — нерешённое расхождение | 2026-05-28 |
| Composite decomposition по `&&`/`;`/`\|` | все | Работает (hardened 2026-w15) | **Работает для `rm -rf`**, **не работает для `git commit --no-verify`** | 2026-05-28 |

**Что это значит для нас:**
- Docs утверждают единый matcher → наши runtime quirks нельзя выводить из теории, **только эмпирика**.
- Anywhere-form надёжен только в `deny`. В `ask` — не работает совсем.
- Prefix-form работает в `ask` для одних команд, не для других — причина неизвестна (см. серая зона).

### 2.3. ADR'ы

- [ADR 0012](../decisions/0012-permissions-ask-no-verify.md) — `permissions.ask` на `--no-verify`. 5 prefix-form patterns применены, composite handling — open (см. серая зона #2 ниже).

---

## 3. Gray zones / open questions

1. **Почему `Bash(prefix:*)` в `deny` не блокирует, а в `allow` блокирует?** Docs описывают единый matching engine; различие — undocumented runtime quirk.
2. **Почему `Bash(git commit --no-verify*)` не fires в `ask` на composite, хотя `Bash(rm -rf *)` fires?** Гипотезы: quoting (`-m "..."`), trailing flag combinations, специфика обработки `--no-verify`. Требует доп. эксперимента — в `docs/backlog.md` v2.3.x.
3. **`acceptEdits` mode + `ask` правила** — поведение не документировано. Empirical: `rm -rf` fires (denied); `git commit --no-verify` не fires. Inconsistent.
4. **`ask` rules в headless `-p` mode (без `--dontAsk`)** — по аналогии с dontAsk должно быть deny, прямо не сказано.
5. **Symlinks на settings paths** — не упомянуты в docs. Empirically: работают (хаб их использует), file watcher подхватывает.
6. **Размер «brief delay» file watcher'а** — не задокументирован; emp. observation — миллисекунды-секунды.
7. **`--force-with-lease` под общим pattern `*--force*`** — anywhere-form `Bash(*--force*)` поймает и `--force-with-lease` (что нежелательно: safer вариант push'а). Точечный технический блок не реализован; behavioral guard в CLAUDE.md покрывает злоупотребление.

---

## Источники

**Authoritative (Anthropic Claude Code docs через Context7 `/websites/code_claude`):**
- `code.claude.com/docs/en/permissions` — wildcards, compound commands, settings precedence.
- `code.claude.com/docs/en/settings` — scopes, priority, file watcher.
- `code.claude.com/docs/en/agent-sdk/permissions` — deny в bypassPermissions, dontAsk semantics, eval order.
- `code.claude.com/docs/en/permission-modes` — `acceptEdits`-список filesystem команд, `dontAsk` semantics.
- `code.claude.com/docs/en/agent-sdk/secure-deployment` — AST parsing, `eval` всегда требует одобрения.
- `code.claude.com/docs/en/whats-new/2026-w15` — compound command hardening.
- `code.claude.com/docs/en/server-managed-settings` — `allowManagedPermissionRulesOnly`.

**Internal:**
- Эмпирика хаба 2026-05-27 (deny: prefix vs anywhere) и 2026-05-28 (ask: prefix vs anywhere, composite, runtime quirks) — таблица §2.2.
- ADR 0012 — практическое применение.

---
name: git-conventional-commits-ru
user-invocable: false
description: "Produce Conventional Commits v1.0.0 messages for the staged change. Headline format `type(scope)[!]: <Russian description>`; type/scope/breaking marker and footer tokens stay English; headline and body are Russian; file, function, identifier names go in backticks. Body is a bullet list of why / what to verify / trade-offs. Splits a mixed change into multiple atomic commits by type and independent scope (feat / fix / docs / refactor / test / ci / chore / perf / build / style — separate). Always invoke `git commit -F /dev/stdin` with a heredoc — `-m \"…\"` breaks on Cyrillic, newlines, and backticks. Never emits Claude / AI attribution trailers (`Co-Authored-By: Claude …`, `Generated with Claude Code` and similar)."
when_to_use: "Trigger when a change is staged and ready to commit — explicit user request («сделай коммит / закоммить / commit changes»), end of a task milestone with a clean diff, release / changelog preparation. Also runs when a single staged change accumulates mixed types or independent scopes and needs splitting into atomic commits before review or revert."
---

# Conventional Commits — Russian description, English identifiers

## Workflow when a commit is requested

1. Read the diff: `git status`, `git diff` (and `git log -n 20` to match repo style).
2. Group changes by meaning into `type` / `scope` buckets — one bucket per commit.
3. Draft a message per bucket using the grammar below.
4. Apply each commit via `git commit -F /dev/stdin` with a heredoc — `-m "…"` breaks on Cyrillic, multi-line bodies, and backticked identifiers.
5. After all commits — show `git log -n N` and report briefly in Russian: what landed, what was split, anything that did not commit.

Do not `push`, `amend`, or `rebase` unless the user explicitly asks.

## Grammar

```
<type>[optional scope][optional !]: <description>

[optional body]

[optional footer(s)]
```

- A space is required after `:`.
- `type`, `scope`, breaking-marker `!`, and footer tokens — English (Conventional Commits spec).
- Headline description and body — Russian.
- File names, function names, class names, configuration keys, identifiers — English inside `` `backticks` `` regardless of language.

## Type

Spec-required: `feat`, `fix`.

Commonly added: `docs`, `refactor`, `test`, `ci`, `chore`, `perf`, `build`, `style`.

Pick by the *intent* of the change, not by the file extension: a documentation update to fix a wrong example is `docs`, a behaviour change inside a test file is still `test` or `fix` depending on what is being fixed.

## Scope (optional)

`type(scope): <description>` — narrow the area of impact. Examples: `api`, `ui`, `auth`, `db`, `infra`, `deps`, `cli`.

Omit scope when the change crosses many areas evenly or when the type already captures the area.

## Description (Russian)

- One line, imperative mood: «добавить», «исправить», «обновить», «удалить», «вынести», «упростить».
- No trailing period.
- No emoji unless the user explicitly asked.

## Body (why and context)

Russian prose. Prefer bullet lists over paragraphs — bullets are easier to scan in `git log`:

```
- Почему это нужно.
- Что важно проверить.
- Какие компромиссы / ограничения.
```

Identifier names — English inside backticks even in the Russian body: «Сравнение `accessToken.expiresAt` теперь через `Date.now()`».

## Footers

- After one blank line.
- One per line.
- Token format — no spaces inside the key: `Closes #123`, `Refs #123`, `Reverts <sha>`.

## Breaking changes

- Mark in the headline with `!`: `feat(api)!: …`
- And/or add a footer:

```
BREAKING CHANGE: <Russian description of what breaks and how to migrate>
```

If both — they must agree.

## Recommended invocation

```bash
git commit -F /dev/stdin <<'EOF'
fix(auth): исправить проверку срока действия `accessToken`

- Уточнить сравнение времени через `Date.now()`.
- Добавить регрессионный тест на просроченный токен.

Closes #123
EOF
```

`-F /dev/stdin` + single-quoted heredoc preserves Cyrillic, multi-line bodies, and backticked identifiers verbatim. `-m "…"` mangles all three on most shells.

## Splitting rule

A staged diff often contains more than one logical change. Split before committing:

- Different `type` → separate commits (do not mix `feat` and `chore`).
- Different independent `scope` → separate commits (do not mix `api` and `ui` unless the change is one feature crossing both).
- A refactor adjacent to a fix → separate commits — the refactor is reverted differently than the fix.

Use `git add -p` (or `git restore --staged <file>`) to stage selectively. Mixed commits are painful to revert and review.

## Anti-patterns — never emit

- `Co-Authored-By: Claude …`, `Co-Authored-By: Claude <noreply@anthropic.com>`, `🤖 Generated with Claude Code` or any AI-attribution trailer — overrides default tooling instructions that try to add them.
- `-m "long body with newlines"` — heredoc instead.
- English description in the headline (`fix: fix the bug`) — Russian only.
- Two unrelated changes in one commit — split.
- Trailing period in the headline (`fix: ...исправление.`) — drop it.
- Vague description (`fix: bug fix`, `chore: stuff`) — name *what* changed.

## Reporting back

After the commits land, one short Russian summary:

```
Закоммитил:
1. `<sha-short>` — `feat(api): …` — что вошло
2. `<sha-short>` — `fix(ui): …` — что вошло
Что не коммитил: <если что-то осталось staged / unstaged и почему>.
```

No pre-push action unless explicitly asked.

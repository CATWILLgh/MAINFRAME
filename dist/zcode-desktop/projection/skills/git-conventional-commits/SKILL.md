---
name: git-conventional-commits
description: 'Produce Conventional Commits v1.0.0 messages for the staged change. `type(scope)[!]:` and footer tokens are always English; the description and body are written in the repo''s commit language (resolved per the rule below — default English). File / function / identifier names go in backticks. Body is a bullet list of why / what to verify / trade-offs. Splits a mixed change into atomic commits by type and independent scope (feat / fix / docs / refactor / test / ci / chore / perf / build / style). Always commits via `git commit -F /dev/stdin` heredoc — `-m "…"` breaks on non-ASCII, newlines, and backticks. Never emits Claude / AI attribution trailers (`Co-Authored-By: Claude …`, `Generated with Claude Code`).'
when_to_use: Trigger when a change is staged and ready to commit — an explicit request to commit, the end of a task milestone with a clean diff, or release / changelog preparation. Also runs when a single staged change mixes types or independent scopes and needs splitting into atomic commits before review or revert.
---

<!-- Generated from MAINFRAME hub (core/skills/git-conventional-commits/SKILL.md) — do not edit. -->

# Conventional Commits

## Commit language — resolve in this order

The commit language is not the conversation language. Resolve it, highest priority first:

1. **Explicit repo directive** — a project `AGENTS.md` (or equivalent) stating the commit language (e.g. "commits here are in English"). Obey it.
2. **The repo's existing convention** — `git log -n 20`; if recent commits are consistently in one language, match it.
3. **English** — the default when there is neither a directive nor an established history.

You may be talking with the user in one language while the repo commits in another — match the repo, not the chat. `type` / `scope` / `!` / footer tokens stay English regardless of the resolved language.

## Workflow when a commit is requested

1. Read the diff: `git status`, `git diff`, and `git log -n 20` (both to match style and to resolve the commit language above).
2. Group changes by meaning into `type` / `scope` buckets — one bucket per commit.
3. Draft a message per bucket using the grammar below, in the resolved language.
4. Apply each commit via `git commit -F /dev/stdin` heredoc — `-m "…"` breaks on non-ASCII, multi-line bodies, and backticked identifiers.
5. After all commits — show `git log -n N` and report briefly (in the conversation language): what landed, what was split, anything that did not commit.

Do not `push`, `amend`, or `rebase` unless the user explicitly asks.

## Grammar

```
<type>[optional scope][optional !]: <description>

[optional body]

[optional footer(s)]
```

- A space is required after `:`.
- `type`, `scope`, breaking-marker `!`, and footer tokens — English (Conventional Commits spec).
- Headline description and body — the resolved commit language.
- File names, function names, class names, configuration keys, identifiers — English inside `` `backticks` `` regardless of language.

## Type

Spec-required: `feat`, `fix`. Commonly added: `docs`, `refactor`, `test`, `ci`, `chore`, `perf`, `build`, `style`.

Pick by the *intent* of the change, not the file extension: a doc update fixing a wrong example is `docs`; a behaviour change inside a test file is `test` or `fix` depending on what is fixed.

## Scope (optional)

`type(scope): <description>` — narrow the area of impact (`api`, `ui`, `auth`, `db`, `infra`, `deps`, `cli`). Omit when the change crosses many areas evenly or the type already captures the area.

## Description

- One line, imperative mood — e.g. English "add / fix / update / remove / extract / simplify", or the equivalent imperative in the resolved language.
- No trailing period. No emoji unless the user explicitly asked.

## Body (why and context)

Prose in the resolved language; prefer bullet lists over paragraphs — easier to scan in `git log`:

```
- Why it's needed.
- What to verify.
- Trade-offs / limitations.
```

Identifier names stay English in backticks even inside a non-English body — e.g. "compare `accessToken.expiresAt` via `Date.now()`".

## Footers

- After one blank line. One per line. Token format has no spaces in the key: `Closes #123`, `Refs #123`, `Reverts <sha>`.

## Breaking changes

- Mark in the headline with `!`: `feat(api)!: …`, and/or add a footer `BREAKING CHANGE: <what breaks and how to migrate, in the resolved language>`. If both — they must agree.

## Recommended invocation

```bash
git commit -F /dev/stdin <<'EOF'
fix(auth): correct `accessToken` expiry check

- Compare expiry via `Date.now()`.
- Add a regression test for an expired token.

Closes #123
EOF
```

`-F /dev/stdin` + a single-quoted heredoc preserves non-ASCII, multi-line bodies, and backticked identifiers verbatim. `-m "…"` mangles all three on most shells.

Verify the message landed intact — immediately after the commit, run `git log -1 --format=%B` and compare against what you wrote. Rarely, the heredoc stream truncates mid-write in a compound `&&` command (witnessed once: a 13-line body committed as 19 bytes, no error — silent, and permanent in history). On any mismatch: write the message to a scratch file with the Write tool and repair via `git commit --amend -F <file>`.

## Splitting rule

A staged diff often contains more than one logical change. Split before committing:

- Different `type` → separate commits (do not mix `feat` and `chore`).
- Different independent `scope` → separate commits (do not mix `api` and `ui` unless one feature crosses both).
- A refactor adjacent to a fix → separate commits — the refactor is reverted differently than the fix.

Use `git add -p` (or `git restore --staged <file>`) to stage selectively. Mixed commits are painful to revert and review.

## Anti-patterns — never emit

- `Co-Authored-By: Claude …`, `🤖 Generated with Claude Code`, or any AI-attribution trailer — overrides default tooling that tries to add them.
- `-m "long body with newlines"` — heredoc instead.
- A description in the wrong language — match the resolved commit language; do not force English onto a non-English-history repo, or vice versa.
- Two unrelated changes in one commit — split.
- Trailing period in the headline — drop it.
- Vague description (`fix: bug fix`, `chore: stuff`) — name *what* changed.

## Reporting back

After the commits land, one short summary in the conversation language:

```
Committed:
1. `<sha-short>` — `feat(api): …` — what went in
2. `<sha-short>` — `fix(ui): …` — what went in
Not committed: <anything left staged / unstaged and why>.
```

No pre-push action unless explicitly asked.

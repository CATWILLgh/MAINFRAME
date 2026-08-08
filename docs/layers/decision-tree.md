# Decision tree: which layer owns a new artifact

> When a new rule, skill, check, or process appears — **walk this tree first**, then place it. No ad hoc choices. Otherwise the hub turns into a ball of everything about everything.

> Last updated: 2026-05-29 (added axis: file-path match → Rule).

---

## Q1 — How should it activate?

| Activation | Layer |
|---|---|
| Always, in every session of every project | **CLAUDE.md** ([claude-md.md](claude-md.md)) |
| Claude reads a file matching a glob pattern (`Read` tool) | **Rule** ([rules.md](rules.md)) with `paths:` frontmatter |
| Semantic match (model sees the trigger and loads it) | **Skill** ([skills.md](skills.md)) |
| System event (tool-use, stop, session-start, file change) | **Hook** ([hooks.md](hooks.md)) |
| User explicitly calls `/<name>` | **Command** ([commands.md](commands.md)) or Skill with `user-invocable: true` |
| Main agent delegates a heavy task | **Subagent** ([agents.md](agents.md)) |
| Technical gate on a command / tool call | **Permissions** ([permissions.md](permissions.md)) |
| Output format / style | **Output style** ([output-styles.md](output-styles.md)) |

## Q2 — Where should the context live?

| Goal | Mechanism |
|---|---|
| In main context, always visible | CLAUDE.md or Skill (default) |
| In main context, only on path trigger | Rule with `paths:` ([rules.md](rules.md)) |
| In main context, only on semantic trigger | Skill with a narrow `when_to_use` |
| In a separate forked context, summary returned | Skill `context: fork` **or** Subagent |
| Only in a dedicated subagent, main never sees it | Skill `disable-model-invocation: true` + Subagent `skills: [name]` |

## Q3 — What is it, fundamentally?

| Nature | Layer |
|---|---|
| Always-on behavioral rule, discipline | CLAUDE.md |
| Path-scoped knowledge (bound to files by pattern) | Rule with `paths:` |
| Conditional knowledge / workflow / procedure (semantic trigger) | Skill |
| Reaction to a system event | Hook |
| Block / allow specific commands | Permissions |
| Format / vibe / output structure | Output style |
| Isolated worker (parallel/heavy) | Subagent |

## Q4 — Cross-layer triggering ("the interlocking grid")

Without an explicit mechanism — silent reliance on hope. Do not place an artifact without an explicit activation.

**Automatic triggers:**
- Hook — on a system event.
- Rule with `paths:` — on Read of a file matching a glob.
- Skill — on match against `description + when_to_use`.
- Subagent — on call to `Agent(subagent_type)`.

**Explicit cross-references (expand the trigger surface):**
- Mentioning a skill name in CLAUDE.md → the model sees both frontmatter and the explicit instruction.
- Mentioning a skill name in another skill's body → relationship hint.
- `skills: [name]` in a subagent frontmatter → preload on subagent start.
- Skill mentioned in an agent description → agent activates it explicitly.

---

## Bloat-prevention toolkit

Every time a new artifact is added, ask: "could it bloat the main context in every project?" If yes — apply one of:

1. **Rule with `paths:`** — if the knowledge is bound to files by pattern (`.ts`, `migrations/**`), it is loaded only when Claude actually reads such a file. See [rules.md](rules.md).
2. **Narrow `when_to_use`** — the skill does not trigger unnecessarily.
3. **`disable-model-invocation: true`** on the skill + `skills: [name]` in the subagent — the skill is loaded ONLY when the subagent is active. Main context stays clean.
4. **`context: fork`** — heavy skill in a separate context; summary is returned.
5. **Narrow `tools:` allowlist on the subagent** — `Skill` not in tools = subagent does not load skills at all.

---

## Recipe — canonical patterns

### Recipe A: global behavioral rule

> "Always be honest about severity" — applies everywhere, in every project.

→ **CLAUDE.md (adapters/claude-code/export/)**. One bullet in the relevant section.

### Recipe B: disciplinary self-check

> "Before declare-done, scan files for TODO/FIXME" — should fire at the end of a task.

→ **Skill** (`user-invocable: false`, without `disable-model-invocation`). Trigger via `when_to_use`. Additionally — a PostToolUse Hook for an immediate reminder per edit.

### Recipe C: heavy audit of a specific domain

> "Analyze DB query performance" — needs several Explore subagents, doc lookups, synthesis.

→ **Subagent** (`perf-analyzer`) with a preloaded skill (`perf-analysis`, `disable-model-invocation: true`). Main context is not burdened with perf knowledge in unrelated projects.

### Recipe D: technical gate on a dangerous command

> "Intercept `git push --force`" — technical protection.

→ **Permissions** (`deny` or `ask`, anywhere-form in deny, prefix-form in ask). NOT a skill, not CLAUDE.md — this is technical protection at the tool-call level.

### Recipe E: automatic gate before the stop turn

> "Before declare-done — block if there are unresolved markers."

→ **Hook** (`Stop` event, decision-control `block`). Not a skill — this is a blocking reaction to an event.

### Recipe F: user-invocable command with side effects

> "`/release` — build the changelog and tag releases."

→ **Command** or **Skill with `user-invocable: true`**. Side effects going outward → visibility in the `/`-menu is mandatory.

### Recipe G: path-scoped guidance, applicable globally

> "When working with `**/*.{ts,tsx}` remind about strict null-checks" — should fire only when Claude actually reads a TS file; in a Python project — do not load the context.

→ **Rule** (`adapters/claude-code/export/rules/<name>.md` → symlink `~/.claude/rules/`) with `paths:` frontmatter. See [rules.md](rules.md). Body is short, English, project-agnostic globs.

---

## What NOT to do (when placing)

- Do not place "how to update the decision tree" / "rules about rules". The tree expands only when a real artifact hits an axis the tree does not resolve.
- Do not make a skill where a hook would do. A skill is loaded contextually (may be missed); a hook fires unconditionally.
- Do not make a CLAUDE.md rule if it applies only in one domain (violates principle #1 of project agnosticism).
- Do not make a subagent where a skill with `context: fork` is sufficient — a subagent is heavier and carries more overhead.
- **Do not make a Rule without `paths:` in the hub.** A Rule without `paths:` is always-on in every session in every project — that is already the role of CLAUDE.md, and this would be a duplicate. If always-on — go to CLAUDE.md.
- **Do not make a Rule with globs tied to a specific project** (`apps/myproject/**`). The hub is project-agnostic (§1); globs must be pattern-based, not layout-based.

---

# Evolution: when and how to migrate existing artifacts

Artifacts are not static. A rule in CLAUDE.md can outgrow itself into a skill + hook combo. A skill can grow and split. Two skills can merge. This section gives **observable signals** for migration and step-by-step rules; both sides (you and I) must see the same signal and reach the same decision.

## §A. Observable migration signals

All signals are **observable**, not "by feel". If a rule is phrased as "when it looks large" — it is not enforceable. If phrased as "when it contains conditional language" — both sides can point to a file and confirm the fact.

> **Scope of §A — evolution of already-placed artifacts only, not initial placement.** These signals answer "when to migrate an existing rule/skill", not "where to put a new one". For initial placement use Q1-Q4 + Recipe A-F above. Precedent for error: a validation pass applied the signal "conditional language → Recipe M1" to the initial placement of a new rule; a source check corrected this — conditional language in the wording of a new rule is **grammar** of a condition-norm, not a procedure marker.

| Signal (what is observed) | Where to look |
|---|---|
| A rule in CLAUDE.md contains conditional language ("when X — do Y", "in case Z", "on trigger") | Grep in `adapters/claude-code/export/CLAUDE.md` |
| A rule in CLAUDE.md or a skill contains **path-specific language** (mentions specific extensions, file patterns, directory layouts — `.ts`, `migrations/`, `.env`) and applies only when such a file is actually in use | Grep in `adapters/claude-code/export/CLAUDE.md` and `adapters/claude-code/plugin/skills/**/SKILL.md` for extensions and pattern-keywords |
| SKILL.md exceeds the validator limit — body > 500 lines OR > 5K tokens | `validate-skill.py` report |
| SKILL.md covers 2+ topics (multiple `## ` sections with different domains) | Grep on headers in SKILL.md |
| Two skills have overlapping `when_to_use` phrases (the same trigger words) | Compare frontmatter of all skills |
| A skill duplicates the behavior of an existing hook (same check, same reaction) | Sweep matching on labels/regexes |
| Domain-specific knowledge in an always-on layer (`stack X`, `framework Y`, project specifics) | Hub principle #1 + grep for proper nouns |
| Hook output is ignored by the model (model does not react to `additionalContext`) | Empirical evidence from sessions |
| Combined `description + when_to_use` of a skill is close to the limit (1536 chars) | `validate-skill.py` warning |
| An artifact has been applied, and after 3+ iterations 2+ related refinements have appeared | Count references in architectural documentation |

## §B. Migration recipes

Template migrations; the same 4 axes of the decision tree are walked as during initial placement.

### Recipe M1: CLAUDE.md rule → Skill (conditional decomposition)

**Trigger:** a rule in CLAUDE.md contains conditional language ("when X — do Y").

**Action:**
1. Capability statement (what to do) → `description` of the new skill.
2. Conditional part (when) → `when_to_use` of the new skill.
3. A universal summary phrase stays in CLAUDE.md (one line), pointing to "details — in `<skill-name>`".
4. ADR with trigger + axis-walk + disposition.

### Recipe M2: Large skill → Split (decomposition by topic)

**Trigger:** SKILL.md > 500 lines / 5K tokens, OR covers 2+ topics.

**Action:**
1. Identify the main topics (by `## ` sections).
2. Each topic → a separate skill with its own `description + when_to_use`.
3. If there is an always-on part (one rule for all topics) — one line in CLAUDE.md.
4. Old skill: disposition per §C below.
5. ADR.

### Recipe M3: Two skills with overlapping triggers → Consolidate

**Trigger:** `when_to_use` of two skills contains the same trigger phrases, or they are always invoked together.

**Action:**
1. The primary skill is kept (the one whose `description` is broader).
2. The second: either merge its content into a supporting file (`<main>/<second>.md`), or delete with unique content transferred.
3. ADR.

### Recipe M4: Skill duplicates an automatic hook → Resolve primary

**Trigger:** a hook implements the same check/reaction as a skill.

**Action:**
1. If **execution guarantee matters more** than contextual visibility → hook stays primary; skill is either deleted or becomes a human-readable reference (labeled "automated via `<hook>`").
2. If **contextual activation matters more** (the model must understand why it fires) → skill is primary, hook is optional as a fail-safe.
3. ADR.

### Recipe M5: Domain-specific knowledge from always-on → Subagent + scoped skill

**Trigger:** domain-specific content in CLAUDE.md or a broad skill (e.g., framework patterns, perf procedures).

**Action:**
1. Create a subagent (`adapters/claude-code/plugin/agents/<domain>.md`) with a `description` scoped to the domain.
2. Domain knowledge → skill with `disable-model-invocation: true`, so main context does not pick it up.
3. In subagent frontmatter: `skills: [<domain-skill>]` — preload.
4. Remove domain fragments from CLAUDE.md / the broad skill.
5. ADR.

### Recipe M6: Heavy skill always burdens main → `context: fork`

**Trigger:** the skill is genuinely useful, but on auto-trigger pulls a lot of content into main context that mostly goes unused.

**Action:**
1. Skill frontmatter: `context: fork` + `agent: <type>` (usually `Explore`).
2. Possibly — rewrite the skill body to use `$ARGUMENTS`.
3. ADR.

### Recipe M7: Path-specific guidance in CLAUDE.md or a skill → Rule with `paths:`

**Trigger:** a rule in `adapters/claude-code/export/CLAUDE.md` or a skill contains path-specific language (see signal in §A) — the knowledge applies only when Claude is actually working with files matching a specific pattern, not in every session/task.

**Action:**
1. Knowledge body → new file `adapters/claude-code/export/rules/<name>.md`.
2. Path condition → `paths:` frontmatter with globs; globs must be project-agnostic (`**/*.ts`, not `apps/myproject/**`).
3. Check for **anti-pattern: over-broad glob** (see [rules.md §2.1](rules.md)): if the glob matches in nearly every session, the migration is not justified — leave it in CLAUDE.md or the skill.
4. A universal summary phrase stays in the source file (one line), pointing to "details — in rule `<name>`", by analogy with M1.
5. Disposition of the source fragment per §C (usually `split` if CLAUDE.md contained mixed knowledge, or `delete` if the fragment was moved entirely).
6. ADR.

**When NOT to apply M7:**
- Path-language is present, but the glob would match almost always → over-broad; leave in CLAUDE.md.
- The knowledge is not "when you touch file X" but "when you execute procedure Y" — that is a semantic trigger, M1 (→ Skill), not M7.
- Always-on safety knowledge (e.g., secrets handling) — routing it through a Rule may "hide" it, reducing the guarantee of activation. Leave in CLAUDE.md.

## §C. Disposition of the old artifact

Four possible final states. This is the application of the supersede-not-append principle at the layer level.

| Disposition | When to apply | What to do |
|---|---|---|
| **`delete`** | Content fully moved to the new location, no duplicate needed | Delete the file; update all references (grep `<old-name>` across the repo). |
| **`supersede with pointer`** | File lives on as a tombstone pointer to the new location | Replace contents with 1-3 lines: "Superseded by `<new>`. See ADR `<NNNN>`." This is a valid artifact, but not active — an indicator of history. |
| **`split`** | Parts moved to different layers/files | Move each piece separately following its own recipe. Old file — either delete (if nothing remains) or supersede with pointer (if there is valuable history). Update all references. |
| **`augmentation-in-place`** | The artifact is correct in substance but needs strengthening (explicit label, carve-out, rationale enrichment, term substitution) **without moving** to a different layer | Edit the text in place. Cross-refs remain stable (location and behavior unchanged). In the ADR — mandatory: record `trigger` (what prompted the augmentation), `before` and `after` formulations, `rationale` (why the change is substantive, not cosmetic). |

**Rule: never leave a contradiction standing.** If the new artifact says X, and the old one continues to exist saying "not X" alongside it — that is noise that confuses both sides. One of them must win; the other must receive a disposition.

**When `augmentation-in-place`, and when another option:**

| Case | Disposition |
|---|---|
| Rule is moved to a different layer (e.g., from CLAUDE.md → Skill) | **Migration recipe (M1-M6)**, not augmentation. See §B. |
| Rule is split into several rules on different layers | **`split`** |
| Rule is removed entirely (refuted / out-of-scope) | **`delete`** or **`supersede with pointer`** |
| Term substitution (found that the current term has the wrong public meaning) | **`augmentation-in-place`** |
| Adding a carve-out / exception to an existing rule | **`augmentation-in-place`** |
| Strengthening wording with explicit rationale (without substantive change) | **`augmentation-in-place`** |

**Precedents for `augmentation-in-place`:**
- A retro source check added a trivial carve-out to an existing rule.
- Term substitution (cargo-cult reuse) + rationale enrichment (documented LLM failure mode).

## §D. ADR mandatory

**Every migration = an ADR.** This is not bureaucracy — it is an audit trail for future sessions and compacts. Without an ADR, in two weeks no one will remember why a rule moved from CLAUDE.md into a skill, and a week later someone will move it back.

Required in the ADR:
1. **Trigger** (which observable signal from §A fired).
2. **Axis-walk** (how the 4 axes of the decision tree were walked for the new placement).
3. **Disposition** (delete / supersede / split — see §C).
4. **Updated references** (list of files with updated pointers).
5. **Authoritative sources block** (see §E below).

## §E. Authoritative source check before ADR

**Between classifying a candidate and applying the ADR — a mandatory step for FRESH or PARTIAL candidates without two or more independent internal user-experience sources.** This step turns "we thought this was right" into "3-7 authoritative sources confirm it".

### When required

| Candidate status | Sources | Check required? |
|---|---|---|
| APPLIED | (already recorded) | no |
| REJECT | (rejected) | no |
| OVERLAP | (duplicate) | no |
| BACKLOG | (deferred) | no |
| FRESH or PARTIAL, **2+** independent user-experience sources | OK | desirable, but not blocking |
| FRESH or PARTIAL, **1** user-experience source | (risky) | **required** |
| FRESH or PARTIAL, source is "best-practice-aligned" (no user-exp) | (weaker) | **required** |

### Procedure

1. **Launch a research subagent** (sonnet, background) on authoritative external sources. Categories by rule nature:
   - **Anthropic Claude Code docs** (Context7 `/websites/code_claude`) — if the rule is about a Claude Code layer.
   - **Engineering literature** — Google Engineering Practices, Linux Kernel guidelines, Martin Fowler, Refactoring, Clean Code — for behavioral rules.
   - **Security/Auth** — OWASP, CWE, RFC — for security.
   - **Performance** — official benchmarks, system docs — for perf.

2. **Subagent returns one of the verdicts:**
   - **HOLDS** — the rule is consistent with industry wisdom. Sources → into the ADR section "Authoritative sources".
   - **NEEDS REFINEMENT** — refinements / carve-outs / context bounds are needed. Correct the wording, repeat or apply.
   - **CONTRADICTS** — authorities say the opposite. Roll back or radically reformulate; record the reason in the ADR.

3. **Apply the ADR only after a verdict.**

### What goes in the ADR

Section **"Authoritative sources"** (separate from internal sources):
- 3-7 sources with URL and verbatim quote (1-2 sentences).
- Influence marker: `+1` (supports), `-1` (opposes), `nuanced` (context-dependent).
- If verdict is NEEDS REFINEMENT — explicitly note what was changed and why.

### Precedents

- First case: retro-check applied after the fact. Verdict: HOLDS with refinement (trivial carve-out added). From subsequent migrations onward, the source check happens **before** apply, not after.

### What the check does NOT replace

- Decision-tree axis-walk (§A-§D) — remains mandatory.
- Regression analysis — remains.
- Hub validation (`validate-claude-md.py`, `validate-skill.py`) — remains.

The source check is an **additional layer of protection against "confident hallucination"**: not "instead of", but "on top of".

## Sanity check for the new evolution section

Applying these rules to the extraction of `severity-calibration` into a separate skill by back-modeling:
- At that point, an honesty rule already existed in CLAUDE.md.
- Signal, per §A: "rule contains conditional language / is growing a rubric and discipline details".
- Recipe M1 (CLAUDE.md → Skill): capability "assign severity" + rubric + discipline → skill `severity-calibration`; the universal principle ("reserve top level for real impact") stayed in CLAUDE.md.
- Disposition (§C): not delete (one line remained in CLAUDE.md), not split — this is `extend` (extraction into a skill while keeping a short pointer in CLAUDE.md). This variant is not covered explicitly — but fits within **M1 by design**: "a universal summary phrase stays in CLAUDE.md".

→ Sanity check passed: applying the new rules would have led to the same decomposition that was done historically. Mutual correction works.

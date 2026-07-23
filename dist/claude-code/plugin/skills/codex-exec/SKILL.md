---
name: codex-exec
user-invocable: false
description: "Delegate substantial work to the OpenAI Codex CLI as an external agent via background `codex exec` runs: canonical invocation (prompt inline + `< /dev/null`, absolute `-C`, explicit model + effort, `-o` for the final answer), the battle-tested model × effort routing matrix (implementation on contract, final review, design review, triage, mechanical work), briefing discipline (outcome contract with stop-conditions, never step-by-step implementation), sandbox limits (no network / localhost DB / sockets — host verification mandatory), failure modes and rescue (stdin hang, capacity errors, resume, hung-wait vs dead process), fresh-vs-persistent session modes, parallelism caps."
when_to_use: "A task is worth offloading to an independent external coding agent — implementation against a written contract, a broad audit or recon sweep, an adversarial design or code review needing a second frontier model with different blind spots, triage of a large queue, or bulk mechanical edits — especially when the orchestrator's own quota is the bottleneck and the Codex CLI is installed and authenticated. Also applies when a running `codex exec` misbehaves (hang, capacity error, dead thread) and needs diagnosis or rescue."
---

# Delegating work to Codex via `codex exec`

Codex CLI is an independent frontier coding agent with its own quota pool and its own
blind spots — both are the point. The orchestrator keeps decisions, briefs, and all
verification; Codex does bounded work in a sandbox. Treat it exactly like a sub-agent:
its "done" is a claim to verify, never a result to relay.

Good delegation targets: implementation against a tight written contract (both backend
and frontend), broad read-only audits and recon sweeps, adversarial design/code review,
edge-case sweeps, triage/classification of large queues, mechanical bulk edits from a
template. Keep for yourself: anything needing the live conversation context, architecture
decisions under active discussion, tasks you cannot write acceptance criteria for, and
web research (the sandbox has no network by default — runs hang or come back empty).

## Canonical invocation

Preconditions, checked once per session: `codex login status` prints `Logged in using
ChatGPT` (credentials persist in `~/.codex/auth.json`; if not logged in, runs fail
early — that failure is auth, not any of the failure modes below), and `SCRATCH` points
at a real scratch directory for briefs/answers/logs (any temp dir outside the repo).
The whole recipe below is verified end-to-end against codex-cli 0.144.1 — after a CLI
upgrade, re-check the flag surface with `codex exec --help` before trusting it.

```bash
SCRATCH=/abs/path/to/scratch-dir
codex exec --skip-git-repo-check -C /abs/path/to/repo -s read-only \
  -c model='"gpt-5.6-sol"' -c model_reasoning_effort='"high"' \
  -c approval_policy='"never"' \
  -o "$SCRATCH/answer.md" \
  "$(cat "$SCRATCH/brief.md")" < /dev/null > "$SCRATCH/stdout.log" 2>&1
```

Run it as a background shell task (Claude Code: the Bash tool's background-run flag) —
a substantial agentic run takes minutes; a foreground timeout kills it mid-edit.

Non-negotiable pieces of that command:

- **Prompt inline via `"$(cat brief.md)"` plus `< /dev/null`.** Piped stdin in a
  background run hangs nondeterministically — both a bare inline prompt and the
  `- < brief.md` redirect form have hung waiting on stdin. `< /dev/null` gives instant
  EOF; there is no ambiguity. Diagnosis of a hung run is below.
- **`-C` with an absolute path, always.** With `-s workspace-write` the writable root is
  the caller's cwd at spawn time; a drifted shell cwd makes Codex stop with a polite
  "workspace not writable" report instead of doing the work. Same rule for every path in
  any wrapper around the call: absolute only.
- **Model and effort explicit on every call.** The `~/.codex/config.toml` default drifts
  (observed drifting to a cheap low-effort model); a run launched on defaults wastes the
  whole grind. Confirm right after launch:
  `grep -E "^(model|sandbox|reasoning effort):" stdout.log` — those exact labels open
  every run's stdout banner, which also prints `session id:` (keep it; it is the resume
  handle).
- **`-o` file is the final answer; stdout is a huge event trace.** Read the answer file.
  Bound every inspection of the stdout log (`tail -c 2000`, `head`) — careless dumps of a
  multi-hundred-KB trace flood the calling context.
- **Sandbox by task:** `-s read-only` for recon/review/audit (safe default),
  `-s workspace-write` for edits. `danger-full-access` — never by default; it removes the
  sandbox entirely.

Useful extras (same 0.144.1 verification): `--add-dir <dir>` grants additional
writable roots (monorepo side-packages); `--output-schema <file.json>` forces the final
message into a JSON Schema shape; `--ephemeral` skips session persistence; `-i <img>`
attaches images; `codex exec review` runs a built-in repo review. `--ignore-user-config`
skips only `$CODEX_HOME/config.toml`, NOT a project-level `.codex/config.toml` (see
failure modes for the project-config workaround).

The first `workspace-write` + `approval_policy=never` run in a session may be blocked by
the harness permission gate as "write without confirmation". That gate is legitimate:
general task approval is not approval to write unattended — surface it and get the
explicit yes.

## Model × effort routing (verify the fleet first)

Model slugs are account-bound and drift. Before a long grind: list current slugs from
`~/.codex/models_cache.json`, and sanity-ping an unfamiliar slug with a trivial read-only
prompt — a bad id fails only after real work would have started. Fleet as verified
2026-07-23: `gpt-5.6-sol` (flagship judgment), `gpt-5.6-terra` (deep/adversarial),
`gpt-5.6-luna` (fast, cheap), plus `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`,
`gpt-5.3-codex-spark` (real-time distillate — never for deep multi-file reasoning).
Effort scale observed: `low / medium / high / xhigh / max` (`ultra` exists only on some
models — check per model in `models_cache.json`, do not assume a universal enum).

Battle-tested routing (distilled from ~40 logged production calls):

| Task class | Model / effort | Sandbox |
|---|---|---|
| Recon, summaries, simple lookups | luna / low-medium | read-only |
| Mechanical work from an explicit template; triage of mechanical clusters | luna / high | per task |
| Triage / classification of large queues (~20 items per call) | sol / medium | read-only |
| Implementation against a tight contract (any stack side) | sol / medium | workspace-write |
| Complex or delicate implementation | sol / high | workspace-write |
| Investigations, domain forensics, edge-case sweeps | sol / high | read-only |
| Final review of ordinary diffs (catches what tests mask) | sol / high | read-only |
| Design review AND final review of money / concurrency / temporal invariants | terra / high | read-only |
| The most expensive error classes (merge seams, money joints) — reserve | terra / xhigh | read-only |

Stable observations behind the table:

- sol/medium (write) implements faithfully when the contract is airtight — and stops
  correctly on contract contradictions instead of improvising, which repeatedly exposed
  real bugs and stale premises. Contract quality = result quality.
- terra/high review rounds on concurrency do NOT converge in one pass — plan 3-4
  FAIL→PASS rounds; each FAIL has historically been a real finding. Terra accepts
  counter-evidence (acceptance criteria, recorded product decisions), not only code.
- Two independent terra runs on one adversarial brief converging on the same finding is
  a strong signal — use that pattern to check the orchestrator's own confident claims.
- Escalate one tier after 2 consecutive misses ("not enough context", wrong output);
  de-escalate next time when a task finishes trivially fast.
- `Selected model is at capacity` → retry the same model immediately once; on repeat,
  fall back sol↔terra.

## Briefing discipline

Write the brief as an **outcome contract, not an implementation script**: what must
exist, style/format, acceptance criteria, workflow fences. Never dictate APIs, SDKs, or
command-by-command steps — and never hand it a pre-digested fix-list that suppresses its
own recon: over-constrained briefs produce transcribed fixes plus hallucinated details,
while "work thoroughly, investigate the repo yourself, verify every path against the
real tree" produces self-verified output. You still verify the output; that is not a
constraint on the input.

The brief is one self-contained English markdown file containing:

- Facts already verified by the orchestrator (so it does not redo recon) and a starting
  point (`file:line`), with "keep recon tight: targeted slices only".
- Explicit scope paths and the do-not-touch list.
- Exact commands it may run (test/lint invocations), and the expected output format.
- Hard constraints, stated every time: "do NOT commit" (the sandbox does not reliably
  fence `git` — in some environments commits succeed; the caller owns git), plus any
  style passport (docstring language, naming) — otherwise it silently rewrites to its
  own defaults.
- Domain payload shapes for any tests it must write — without them its test scenarios
  drift toward invented fields.
- The stop-condition, verbatim: "on any contradiction between this contract and the
  code, or a missing decision — STOP and report; do not improvise." In test-only briefs
  add: "if hardening a test exposes a product bug — do not fix it; report."
- One brief = one ticket/fix. Its context window is finite; merged briefs die with
  "ran out of room in the model's context window" during recon (tree is usually
  untouched — check `git status`, relaunch is cheap).

Secrets: `codex exec` inherits the shell environment, so a run can see real env secrets.
Never paste secret values into a brief, and never quote its raw stdout into a reply
without scanning — treat its logs like any command output that may embed credentials.

## Sandbox limits → host verification is mandatory

Under `workspace-write` the sandbox blocks: outbound network (default; can be enabled
with `-c sandbox_workspace_write.network_access=true` when genuinely needed), TCP/Unix
sockets to localhost (backend tests against a local DB fail with "Operation not
permitted" — those failures are connectivity, not code), and socket/IPC binding (no dev
servers, no runner smokes that open pipes). Read-only runs additionally cannot write
temp files, so test suites cannot run at all — it reviews by inspection; never cite
"Codex ran the tests" for a read-only run.

Consequences, all observed in production:

- Codex writes code + tests (the main value) but often **cannot run** DB-backed suites,
  network smokes, or env-dependent asserts. Its "green" may mean collect-only, a silent
  DB fallback, or types-only — the full suite runs on the host, by the orchestrator.
- It runs `ruff check` but not `ruff format --check` — freshly written files can fail a
  CI format gate. Run the formatter check yourself.
- Host verification checklist for a write run: lint + format check, typecheck, the full
  targeted suite on real infrastructure, boundary arithmetic in its tests recomputed by
  hand (observed: an overflow test seeded below the threshold — a false-red waiting to
  happen), fixture-vs-schema sync for tests it wrote, and a diff grep for duplicated
  logic before "finishing" any stub it left (observed: a retry loop added by the caller
  on top of Codex's own deeper retry → double retries).
- Tests it could not execute (EPERM smokes) may carry self-contradictory asserts it
  never saw red. When fixing on the host, fix the test to the brief's spec first, then
  look at the code.
- Every review finding it reports is re-verified against the code before relaying or
  ticketing — its hit rate is high, which is exactly why an unverified miss slips
  through.

## Failure modes and rescue

- **Hang diagnosis.** `tail` the stdout log. "Reading additional input from stdin..."
  opens every stdin-attached run and is harmless by itself; it signals a hang only when
  it stays the LAST line with no banner following → stdin hang, kill and relaunch with
  the canonical form. No such line, CPU
  time not growing (`ps -o time`), and no fresh rollout file in
  `~/.codex/sessions/YYYY/MM/DD/` matching the start time → the session never started;
  kill immediately, waiting is pointless.
- **A broken wait is not a dead process.** After a caller-side timeout or an interrupted
  wait, Codex frequently keeps working and lands all files afterwards. Before ANY
  relaunch: check `git status` and the rollout file's mtime — or you will start a second
  instance on top of a live one.
- **Kill precisely:** `pkill -f "codex exec"` — never touch `codex app-server` (an IDE's
  live bridge).
- **Capacity error mid-run:** files already written stay on disk; no answer file is
  produced. Do not blindly re-run — snapshot/commit the current tree as a baseline,
  inventory what landed (runs have died at ~95% done), then finish the remainder
  yourself or with a targeted continuation brief.
- **Resume a session:** `codex exec resume <session-id>` (or `--last`). The id comes
  from the run's stdout banner (`session id:`) or from the rollout filename
  `~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<session-id>.jsonl`. The `resume`
  subcommand does NOT accept `-s` — pass `-c sandbox_mode='"workspace-write"'`; `-c`
  values parse as TOML, so strings need double quotes inside single quotes. The working
  root comes from the thread header, so `-C` is unnecessary when unchanged. Sub-agent
  rollouts (Codex spawns internal sub-agents that write their own rollout files) are NOT
  resumable — picking "the newest rollout" can hit one and fail; when in doubt, a fresh
  self-contained brief (current `git status`, decisions made, remaining work) is cheaper
  than session archaeology.
- **Project `.codex/config.toml` parse errors:** the project file is parsed before any
  `-c` override and independently of `CODEX_HOME`, so an incompatible stanza kills the
  run at thread start. Workaround: move the project config OUT of the repository (into a
  scratch dir — an in-repo `.tmpbak` shows up in `git status` and parallel agents delete
  it as junk) around the call, restore after; serialize any parallel runs sharing that
  file, since the move/restore pair races.

## Session modes and adversarial use

- **Fresh run per task (default):** full independence, no anchoring on your framing —
  the right mode for adversarial checks and second opinions.
- **Persistent team-member:** resume one long-lived session across turns so it
  accumulates project context; close loops with it (show it the results of experiments
  it demanded). Choose the mode deliberately per task — independence and accumulated
  context are opposites.
- Brief adversarial runs to refute, not to praise. Verify every claim against evidence;
  agreement is signal, disagreement means dig — never silently adopt either. Stop on an
  explicit verdict, not on the finding count: demand a go/no-go on the final round,
  because a strong reviewer returns ~10 findings per round indefinitely if allowed. Cap
  open-ended review loops at 3 rounds; the concurrency/money final reviews above are the
  sanctioned exception (their extra FAIL rounds have historically been real findings —
  plan for them, still verdict-gated).

## Parallelism, quota, evolution

- 2-3 concurrent `codex exec` processes maximum, starts staggered — aggressive fan-out
  draws provider rate-limits; serialize anything sharing a project-config workaround.
- The Codex quota is a separate pool from the orchestrator's — that separation is the
  economic reason this skill exists. The default failure is under-use, not over-use:
  when queues are long and the orchestrator's quota is the bottleneck, reach for it
  sooner than feels natural.
- Keep a living model × effort map in project memory: log each call (model, effort,
  sandbox, task class, verdict) after it completes. Three or more homogeneous lessons on
  one cell → propose an update to the routing table above; single observations change
  nothing.

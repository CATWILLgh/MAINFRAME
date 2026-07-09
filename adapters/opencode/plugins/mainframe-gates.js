/**
 * MAINFRAME gates for OpenCode — table-driven dispatcher plugin.
 *
 * Bridges OpenCode tool events to the hub's existing Python hooks, keeping
 * every rule set single-source in Python. Two modes, partitioned by event:
 *
 * - `tool.execute.before` rows BLOCK: a parsed permissionDecision deny/ask
 *   becomes a thrown Error (blocks the call; the message reaches the model
 *   verbatim — verified on OpenCode 1.17.15). `ask` maps to block because
 *   plugins have no working ask flow; the throw text asks the model to relay
 *   the reason to the user.
 * - `tool.execute.after` rows are ADVISORY: a parsed additionalContext is
 *   appended to the tool output as a `[mainframe] ...` note (the model reads
 *   it — verified for bash and edit). The after handler must NEVER throw:
 *   the side effect already landed, and a thrown after-hook marks an executed
 *   call as failed, which can push the model into re-running a commit or
 *   delete. Everything, including the append, stays inside try/catch.
 *
 * Fail-open contract: only a parsed decision/note acts. python3 missing,
 * nonzero exit, empty or unparseable stdout, timeouts, and internal errors
 * all defer with a console.error. Row filters only gate whether-to-spawn
 * (over-approximation is fine — the Python scripts remain the deciders).
 *
 * Known divergences from Claude Code, accepted by design: bash reminder
 * notes arrive after execution, not before (teaches the next call); notes
 * share the tool-output channel instead of a separate context channel, so a
 * parsed-by-the-agent stdout may carry a trailing note on hinted commands.
 */

const SCRIPTS_DIR = `${process.env.HOME}/.claude/skills/mainframe/hooks/scripts`

const CODE_HINT = () => true
const ROW_TIMEOUT_MS = 8000
const MAX_SEEN_NOTES = 500

const hasExt = (exts) => (cc) => {
  const p = String(cc.tool_input.file_path || "")
  return exts.some((e) => p.endsWith(e))
}
const baseIn = (names) => (cc) => {
  const p = String(cc.tool_input.file_path || "")
  const base = p.split("/").pop() || ""
  return names.some((n) => base === n || base.startsWith(n))
}
const cmdHas = (needle) => (cc) =>
  String(cc.tool_input.command || "").includes(needle)

// Spawn filters over-approximate on purpose; each script re-filters exactly.
const ROWS = [
  { script: "secret-commit-gate.py", event: "before", tools: ["bash"], filter: cmdHas("commit") },
  { script: "path-validation.py", event: "before", tools: ["bash"], filter: cmdHas("rm") },
  { script: "bash-pattern-reminder.py", event: "after", tools: ["bash"], filter: CODE_HINT },
  { script: "commit-conventional-reminder.py", event: "after", tools: ["bash"], filter: cmdHas("commit") },
  { script: "scan-suppression-markers.py", event: "after", tools: ["edit", "write"], filter: CODE_HINT },
  { script: "comment-discipline-reminder.py", event: "after", tools: ["edit", "write"], filter: CODE_HINT },
  { script: "ticket-id-format-reminder.py", event: "after", tools: ["write"], filter: (cc) => String(cc.tool_input.file_path || "").includes("ticket") },
  { script: "python-security-scan.py", event: "after", tools: ["edit", "write"], filter: hasExt([".py", ".pyi"]) },
  { script: "python-deps-audit.py", event: "after", tools: ["edit", "write"], filter: baseIn(["requirements", "pyproject.toml", "poetry.lock", "Pipfile", "uv.lock"]) },
  { script: "nodejs-deps-audit.py", event: "after", tools: ["edit", "write"], filter: baseIn(["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb"]) },
  { script: "nodejs-security-scan.py", event: "after", tools: ["edit", "write"], filter: hasExt([".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"]) },
  // Passive telemetry sink: emits nothing to stdout, so the advisory-note
  // parsing sees null; rows tagged source=opencode via ccPayload.
  { script: "telemetry.py", event: "after", tools: ["bash", "edit", "write"], filter: CODE_HINT },
]

const ASK_SUFFIX =
  " [mainframe-gates: this action needs the user's explicit go-ahead;" +
  " relay the reason above and wait for their answer in chat.]"

function ccPayload(tool, args, directory, sessionID) {
  const a = args || {}
  // source/session_id feed the telemetry sink's harness dimension; the gate
  // detectors ignore them.
  const common = { cwd: directory, project_dir: directory,
                   session_id: String(sessionID ?? ""), source: "opencode" }
  if (tool === "bash") {
    return { tool_name: "Bash", tool_input: { command: String(a.command ?? "") },
             ...common }
  }
  if (tool === "edit") {
    return { tool_name: "Edit",
             tool_input: { file_path: String(a.filePath ?? ""),
                           old_string: String(a.oldString ?? ""),
                           new_string: String(a.newString ?? "") },
             ...common }
  }
  if (tool === "write") {
    return { tool_name: "Write",
             tool_input: { file_path: String(a.filePath ?? ""),
                           content: String(a.content ?? "") },
             ...common }
  }
  return null
}

export const MainframeGates = async ({ $, directory }) => {
  let ready = false
  try {
    const probe =
      await $`python3 -c "import sys; print(sys.version_info[0])"`.quiet().nothrow()
    const scripts =
      await $`test -f ${SCRIPTS_DIR}/secret-commit-gate.py && test -f ${SCRIPTS_DIR}/path-validation.py`.nothrow()
    ready = probe.exitCode === 0 && scripts.exitCode === 0
  } catch (e) {
    ready = false
  }
  console.error(ready
    ? `[mainframe-gates] active: ${ROWS.length} hook rows`
    : "[mainframe-gates] DISABLED — python3 or hub scripts not found " +
      `(${SCRIPTS_DIR}). Hub gates are NOT active in this session.`)

  const seenNotes = new Set()

  // The race caps how long an ADVISORY row is waited for (a late note is
  // worthless; the spawned python is internally bounded, not killed here).
  // Block rows wait it out: converting a slow-but-correct deny into a silent
  // pass would trade the security guarantee for latency.
  const runRow = async (row, payload, { capped }) => {
    const json = JSON.stringify(payload)
    // Shell arg length is capped (~1 MB on macOS); a Write of a large file
    // would fail the spawn anyway — skip loudly instead.
    if (json.length > 200_000) {
      console.error(`[mainframe-gates] ${row.script} skipped: payload too large`)
      return null
    }
    const spawn =
      $`echo ${json} | CLAUDE_PROJECT_DIR=${payload.project_dir} python3 ${SCRIPTS_DIR}/${row.script}`
        .cwd(payload.cwd).quiet().nothrow()
    const res = capped
      ? await Promise.race([
          spawn,
          new Promise((resolve) => setTimeout(resolve, ROW_TIMEOUT_MS, null)),
        ])
      : await spawn
    if (!res || res.exitCode !== 0) return null
    const text = res.stdout.toString().trim()
    if (!text) return null
    return JSON.parse(text)?.hookSpecificOutput ?? null
  }

  const matching = (event, tool, payload) =>
    ROWS.filter((r) => r.event === event && r.tools.includes(tool) &&
                       r.filter(payload))

  return {
    "tool.execute.before": async (input, output) => {
      let block = null
      try {
        if (!ready) return
        const payload = ccPayload(input.tool, output?.args, directory,
                                  input?.sessionID)
        if (!payload || input.tool !== "bash") return
        payload.hook_event_name = "PreToolUse"
        for (const row of matching("before", input.tool, payload)) {
          const out = await runRow(row, payload, { capped: false })
          const verdict = out?.permissionDecision
          if (verdict === "deny" || verdict === "ask") {
            block = { verdict,
                      reason: String(out.permissionDecisionReason || row.script) }
            break
          }
        }
      } catch (e) {
        console.error("[mainframe-gates] internal error, failing open: " + e)
        return
      }
      if (block) {
        throw new Error(block.reason + (block.verdict === "ask" ? ASK_SUFFIX : ""))
      }
    },

    "tool.execute.after": async (input, output) => {
      try {
        if (!ready) return
        const payload = ccPayload(input.tool, input?.args, directory,
                                  input?.sessionID)
        if (!payload) return
        payload.hook_event_name = "PostToolUse"
        const rows = matching("after", input.tool, payload)
        if (!rows.length) return
        const notes = (await Promise.all(rows.map(async (row) => {
          try {
            const out = await runRow(row, payload, { capped: true })
            const note = out?.additionalContext
            return typeof note === "string" && note.trim() ? note.trim() : null
          } catch (e) {
            console.error(`[mainframe-gates] ${row.script} failed, skipping: ${e}`)
            return null
          }
        }))).filter(Boolean).filter((n) => {
          if (seenNotes.has(n)) return false
          if (seenNotes.size < MAX_SEEN_NOTES) seenNotes.add(n)
          return true
        })
        if (!notes.length) return
        output.output = String(output.output ?? "") +
          notes.map((n) => `\n[mainframe] ${n}`).join("")
      } catch (e) {
        console.error("[mainframe-gates] advisory error, skipping notes: " + e)
      }
    },
  }
}

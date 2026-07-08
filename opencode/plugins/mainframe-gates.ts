/**
 * MAINFRAME security gates for OpenCode — adapter plugin.
 *
 * Bridges OpenCode's `tool.execute.before` to the hub's existing Python
 * PreToolUse gates (secret-commit-gate, path-validation), keeping the tuned
 * rule sets single-source in Python. Blocking works by throwing (the message
 * reaches the model verbatim; verified empirically on OpenCode 1.17.15).
 *
 * Fail-open contract: only a PARSED permissionDecision of deny/ask may throw.
 * Any internal failure (python3 missing, script crash, nonzero exit, empty or
 * unparseable stdout) is logged and lets the call pass — an accidental
 * exception in a plugin hook blocks the tool call on this platform, so every
 * code path here is wrapped. `ask` maps to block: plugins have no working ask
 * flow (permission.ask hook does not fire; user chose block over pass-through).
 */

const SCRIPTS_DIR = `${process.env.HOME}/.claude/skills/mainframe/hooks/scripts`
const GATES = ["secret-commit-gate.py", "path-validation.py"]
// Over-approximating spawn filter only — never decides anything itself.
const SPAWN_HINTS = ["commit", "rm"]

const ASK_SUFFIX =
  " [mainframe-gates: this action needs the user's explicit go-ahead;" +
  " relay the reason above and wait for their answer in chat.]"

type Decision = { verdict: "deny" | "ask"; reason: string } | null

export const MainframeGates = async ({ $, directory }: any) => {
  let ready = false
  try {
    const probe =
      await $`python3 -c "import sys; print(sys.version_info[0])"`.quiet().nothrow()
    const scripts =
      await $`test -f ${SCRIPTS_DIR}/${GATES[0]} && test -f ${SCRIPTS_DIR}/${GATES[1]}`.nothrow()
    ready = probe.exitCode === 0 && scripts.exitCode === 0
  } catch (e) {
    ready = false
  }
  if (!ready) {
    console.error(
      "[mainframe-gates] DISABLED — python3 or hub gate scripts not found " +
      `(${SCRIPTS_DIR}). Bash security gates are NOT active in this session.`,
    )
  } else {
    console.error("[mainframe-gates] active: " + GATES.join(", "))
  }

  const runGate = async (script: string, command: string): Promise<Decision> => {
    const payload = JSON.stringify({
      tool_name: "Bash",
      tool_input: { command },
      cwd: directory,
      project_dir: directory,
    })
    const res =
      await $`echo ${payload} | CLAUDE_PROJECT_DIR=${directory} python3 ${SCRIPTS_DIR}/${script}`
        .cwd(directory).quiet().nothrow()
    if (res.exitCode !== 0) return null
    const text = res.stdout.toString().trim()
    if (!text) return null
    const out = JSON.parse(text)?.hookSpecificOutput
    const verdict = out?.permissionDecision
    if (verdict === "deny" || verdict === "ask") {
      return { verdict, reason: String(out.permissionDecisionReason || script) }
    }
    return null
  }

  return {
    "tool.execute.before": async (input: any, output: any) => {
      let block: Decision = null
      try {
        if (!ready || input.tool !== "bash") return
        const command = String(output?.args?.command ?? "")
        if (!SPAWN_HINTS.some((h) => command.includes(h))) return
        for (const script of GATES) {
          block = await runGate(script, command)
          if (block) break
        }
      } catch (e) {
        console.error("[mainframe-gates] internal error, failing open: " + e)
        return
      }
      if (block) {
        throw new Error(
          block.reason + (block.verdict === "ask" ? ASK_SUFFIX : ""),
        )
      }
    },
  }
}

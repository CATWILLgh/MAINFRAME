import { execFile } from "node:child_process"
import { createHash } from "node:crypto"
import path from "node:path"
import { fileURLToPath } from "node:url"

const HOME = process.env.HOME || ""
const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url))
const HELPER_PATH = path.resolve(MODULE_DIR, "../memory/store.py")
const REMINDER_PATH = path.resolve(MODULE_DIR, "../memory/memory-reminder.py")
const DATA_HOME = process.env.XDG_DATA_HOME || path.join(HOME, ".local", "share")
const STORE_ROOT = path.join(DATA_HOME, "opencode", "mainframe-memory")
const HELPER_TIMEOUT_MS = 8000
const HELPER_MAX_STDOUT_BYTES = 128 * 1024
const MEMORY_SENTINEL = "<!-- mainframe-memory:v1:"
const MAX_SESSIONS = 200
const OPENCODE_MEMORY_NOTE =
  "[mainframe automated harness reminder, not the user] Memory check " +
  "(skip if nothing applies): did a durable, reusable project " +
  "fact surface this session that a future OpenCode session would want? If " +
  "so, save it with the OpenCode project-memory workflow now: keep " +
  "`MEMORY.md` as a concise index, move detail to topic files, deduplicate, " +
  "and supersede stale entries. Never store credentials, current plans, " +
  "active task progress, temporary debugging detail, or guesses. Nothing to " +
  "save is a fine answer."

const runtime = {
  execFile,
  storeRoot: STORE_ROOT,
  loadMemory: async (root, directory) => {
    const stdout = await new Promise((resolve, reject) => {
      runtime.execFile(
        "python3",
        [HELPER_PATH, "load", "--runtime", "opencode", "--store-root", root,
         "--workspace", directory],
        { timeout: HELPER_TIMEOUT_MS, maxBuffer: HELPER_MAX_STDOUT_BYTES },
        (error, value) => error ? reject(error) : resolve(value),
      )
    })
    const payload = JSON.parse(String(stdout))
    return typeof payload.prompt === "string" ? payload.prompt : ""
  },
  runReminder: async (payload) => {
    const stdout = await new Promise((resolve, reject) => {
      const child = runtime.execFile(
        "python3", [REMINDER_PATH],
        { timeout: HELPER_TIMEOUT_MS, maxBuffer: HELPER_MAX_STDOUT_BYTES },
        (error, value) => error ? reject(error) : resolve(value),
      )
      child.stdin?.on("error", () => {})
      child.stdin?.end(JSON.stringify(payload))
    })
    const result = JSON.parse(String(stdout || "{}"))
    const note = result?.hookSpecificOutput?.additionalContext
    return typeof note === "string" && note.trim() ? note.trim() : ""
  },
}

const memoryBlock = (prompt) => {
  const text = String(prompt || "").trim()
  if (!text) return ""
  const hash = createHash("sha256").update(text).digest("hex").slice(0, 16)
  return `${MEMORY_SENTINEL}${hash} -->\n${text}`
}

const appendMemory = async (directory, target) => {
  if (!Array.isArray(target)) return
  try {
    const block = memoryBlock(await runtime.loadMemory(STORE_ROOT, directory))
    if (!block || target.some((item) =>
      String(item).includes(MEMORY_SENTINEL))) return
    target.push(block)
  } catch (error) {
    console.error(`[mainframe-memory] helper unavailable, failing open: ${error}`)
  }
}

const sessionFor = (sessions, sessionID) => {
  let state = sessions.get(sessionID)
  if (state) return state
  if (sessions.size >= MAX_SESSIONS) {
    sessions.delete(sessions.keys().next().value)
  }
  state = { bytes: 0, lastAttemptBytes: 0, lastReminderBytes: 0,
            partBytes: new Map() }
  sessions.set(sessionID, state)
  return state
}

const countTextUpdate = (sessions, properties) => {
  const part = properties?.part
  if (!part || part.type !== "text" || part.ignored) return
  const sessionID = part.sessionID || properties.sessionID
  if (!sessionID) return
  const state = sessionFor(sessions, sessionID)
  const partID = part.id || `${part.messageID || "message"}:text`
  const previous = state.partBytes.get(partID) || 0
  let current
  let growth
  if (typeof properties.delta === "string" && properties.delta) {
    growth = Buffer.byteLength(properties.delta)
    current = previous + growth
  } else {
    current = Buffer.byteLength(String(part.text || ""))
    growth = Math.max(0, current - previous)
  }
  state.partBytes.set(partID, current)
  state.bytes += growth
}

const sendReminder = async (client, sessions, sessionID, directory) => {
  const state = sessions.get(sessionID)
  if (!state) return
  if (state.bytes <= state.lastAttemptBytes) return

  state.lastAttemptBytes = state.bytes
  try {
    const note = await runtime.runReminder({
      cwd: directory,
      project_dir: directory,
      source: "opencode",
      hook_event_name: "Stop",
      transcript_bytes: state.bytes - state.lastReminderBytes,
      memory_note: OPENCODE_MEMORY_NOTE,
      memory_backend: "opencode",
    })
    if (!note) return
    state.lastReminderBytes = state.bytes
    await client.session.prompt({
      path: { id: sessionID },
      body: { parts: [{ type: "text", text: note }] },
    })
  } catch (error) {
    console.error(`[mainframe-memory] reminder bridge failed open: ${error}`)
  }
}

export const MainframeMemory = async ({ client, directory }) => {
  const sessions = new Map()
  return {
    "experimental.chat.system.transform": async (_input, output) => {
      await appendMemory(directory, output?.system)
    },

    "experimental.session.compacting": async (_input, output) => {
      await appendMemory(directory, output?.context)
    },

    event: async ({ event }) => {
      try {
        if (!event) return
        if (event.type === "message.part.updated") {
          countTextUpdate(sessions, event.properties)
          return
        }
        const sessionID = event.properties?.sessionID
        if (!sessionID) return
        if (event.type === "session.deleted") {
          sessions.delete(sessionID)
          return
        }
        if (event.type === "session.idle") {
          await sendReminder(client, sessions, sessionID, directory)
        }
      } catch (error) {
        console.error(`[mainframe-memory] event handler failed open: ${error}`)
      }
    },
  }
}

MainframeMemory.runtime = runtime

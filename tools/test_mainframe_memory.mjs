#!/usr/bin/env node

import * as pluginModule from "../adapters/opencode/plugins/mainframe-memory.js"

const { MainframeMemory } = pluginModule
const runtime = MainframeMemory.runtime
const real = { ...runtime }
const failures = []

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

async function test(name, fn) {
  try {
    await fn()
    console.log(`  ok   ${name}`)
  } catch (error) {
    failures.push(name)
    console.log(`  FAIL ${name}: ${error.message}`)
  }
}

function fakeRuntime(content = "# Project memory\n\n- Durable fact",
                     detectorNote = "Detector memory note") {
  const calls = []
  const reminderCalls = []
  runtime.loadMemory = async (root, directory) => {
    calls.push({ root, directory })
    return content
  }
  runtime.runReminder = async (payload) => {
    reminderCalls.push(payload)
    return detectorNote
  }
  return { calls, reminderCalls }
}

function fakeClient() {
  const prompts = []
  return {
    prompts,
    client: {
      session: {
        prompt: async (request) => { prompts.push(request) },
      },
    },
  }
}

async function makePlugin(content, detectorNote) {
  const fake = fakeRuntime(content, detectorNote)
  const client = fakeClient()
  const hooks = await MainframeMemory({
    client: client.client,
    directory: "/tmp/project",
  })
  return { hooks, fake, prompts: client.prompts }
}

await test("every module export is a function (legacy loader contract)", async () => {
  for (const [name, value] of Object.entries(pluginModule)) {
    assert(typeof value === "function", `export ${name} is ${typeof value}`)
  }
})

await test("default loader invokes the neutral helper with runtime and workspace", async () => {
  let call
  runtime.execFile = (command, args, options, callback) => {
    call = { command, args, options }
    callback(null, JSON.stringify({ prompt: "bounded memory" }))
  }
  runtime.loadMemory = real.loadMemory
  const prompt = await runtime.loadMemory("/memory-root", "/workspace")
  assert(prompt === "bounded memory", `unexpected prompt: ${prompt}`)
  assert(call.command === "python3", `unexpected command: ${call.command}`)
  assert(call.args.includes("load"), "load command missing")
  assert(call.args.includes("opencode"), "runtime missing")
  assert(call.args.includes("/memory-root"), "store root missing")
  assert(call.args.includes("/workspace"), "workspace missing")
})

await test("default reminder bridge sends JSON to the installed detector", async () => {
  let call
  runtime.execFile = (command, args, options, callback) => {
    call = { command, args, options, stdin: "" }
    setImmediate(() => callback(null, JSON.stringify({
      hookSpecificOutput: { additionalContext: "detector result" },
    })))
    return {
      stdin: {
        on: () => {},
        end: (value) => { call.stdin = String(value) },
      },
    }
  }
  runtime.runReminder = real.runReminder
  const payload = { cwd: "/workspace", transcript_bytes: 123 }
  const note = await runtime.runReminder(payload)
  assert(note === "detector result", `unexpected note: ${note}`)
  assert(call.command === "python3", `unexpected command: ${call.command}`)
  assert(call.args[0].endsWith("/memory/memory-reminder.py"),
         `wrong detector: ${call.args[0]}`)
  assert(call.stdin === JSON.stringify(payload), `wrong stdin: ${call.stdin}`)
})

await test("system transform appends bounded memory with a stable hash sentinel", async () => {
  const { hooks, fake } = await makePlugin()
  const first = { system: ["base system"] }
  const second = { system: ["base system"] }

  await hooks["experimental.chat.system.transform"]({}, first)
  await hooks["experimental.chat.system.transform"]({}, second)

  assert(first.system.length === 2, `unexpected system length: ${first.system.length}`)
  assert(first.system[1].includes("<!-- mainframe-memory:v1:"), "sentinel missing")
  assert(first.system[1].includes("Durable fact"), "memory content missing")
  assert(first.system[1] === second.system[1], "same content produced a different block")
  assert(fake.calls[0].root.endsWith("/.local/share/opencode/mainframe-memory"),
         `wrong root: ${fake.calls[0].root}`)
  assert(fake.calls[0].directory === "/tmp/project", "wrong project directory")
})

await test("system transform does not duplicate an existing memory block", async () => {
  const { hooks } = await makePlugin()
  const output = { system: [] }
  await hooks["experimental.chat.system.transform"]({}, output)
  await hooks["experimental.chat.system.transform"]({}, output)
  assert(output.system.length === 1, `memory duplicated: ${output.system.length}`)
})

await test("compaction receives the same bounded memory context once", async () => {
  const { hooks } = await makePlugin()
  const output = { context: [] }
  await hooks["experimental.session.compacting"]({ sessionID: "s1" }, output)
  await hooks["experimental.session.compacting"]({ sessionID: "s1" }, output)
  assert(output.context.length === 1, `memory duplicated: ${output.context.length}`)
  assert(output.context[0].includes("Durable fact"), "memory content missing")
})

await test("empty memory and helper failures fail open", async () => {
  for (const behavior of ["", new Error("helper unavailable")]) {
    runtime.loadMemory = async () => {
      if (behavior instanceof Error) throw behavior
      return behavior
    }
    runtime.runReminder = async () => ""
    const hooks = await MainframeMemory({ client: fakeClient().client,
                                          directory: "/tmp/project" })
    const system = { system: ["base"] }
    const compact = { context: ["base"] }
    await hooks["experimental.chat.system.transform"]({}, system)
    await hooks["experimental.session.compacting"]({ sessionID: "s1" }, compact)
    assert(system.system.length === 1, "system changed on helper failure")
    assert(compact.context.length === 1, "compaction changed on helper failure")
  }
})

await test("idle delegates new activity to the detector and injects its note", async () => {
  const { hooks, prompts, fake } = await makePlugin()
  const event = hooks.event
  const text = "small activity"
  await event({ event: { type: "message.part.updated", properties: {
    part: { id: "p1", sessionID: "s1", type: "text", text },
  } } })
  await event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })

  assert(prompts.length === 1, `expected one prompt, got ${prompts.length}`)
  assert(fake.reminderCalls.length === 1, "detector was not called")
  const payload = fake.reminderCalls[0]
  assert(payload.cwd === "/tmp/project", `wrong cwd: ${payload.cwd}`)
  assert(payload.project_dir === "/tmp/project", "wrong project_dir")
  assert(payload.source === "opencode", `wrong source: ${payload.source}`)
  assert(payload.hook_event_name === "Stop", "wrong event name")
  assert(payload.memory_backend === "opencode", "wrong memory backend")
  assert(payload.transcript_bytes === Buffer.byteLength(text),
         `wrong byte count: ${payload.transcript_bytes}`)
  assert(payload.memory_note.includes("OpenCode"), "runtime memory note missing")
  assert(/automated harness reminder/i.test(payload.memory_note),
         "harness origin missing")
  assert(prompts[0].path.id === "s1", "wrong target session")
  const reminder = prompts[0].body.parts[0].text
  assert(reminder === "Detector memory note", `detector note changed: ${reminder}`)
})

await test("repeated full-part updates count only their byte growth", async () => {
  const { hooks, prompts } = await makePlugin()
  const update = async (text) => hooks.event({ event: {
    type: "message.part.updated",
    properties: { part: { id: "p1", sessionID: "s1", type: "text", text } },
  } })
  await update("x".repeat(30))
  await update("x".repeat(30))
  await hooks.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  assert(prompts.length === 1, "first activity was not delegated")

  await update("x".repeat(50))
  await hooks.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  assert(prompts.length === 2, "real text growth was not delegated")
})

await test("detector silence is respected and unchanged activity is not retried", async () => {
  const { hooks, prompts, fake } = await makePlugin(undefined, "")
  const addDelta = async (delta) => hooks.event({ event: {
    type: "message.part.updated",
    properties: {
      part: { id: "p1", sessionID: "s1", type: "text", text: "" }, delta,
    },
  } })
  const idle = () => hooks.event({ event: {
    type: "session.idle", properties: { sessionID: "s1" },
  } })

  await addDelta("first")
  await idle()
  await idle()
  assert(prompts.length === 0, "detector silence still injected a prompt")
  assert(fake.reminderCalls.length === 1, "unchanged activity was retried")

  await addDelta("second")
  await idle()
  assert(fake.reminderCalls.length === 2, "new activity did not re-run detector")
  assert(fake.reminderCalls[1].transcript_bytes ===
         Buffer.byteLength("firstsecond"), "silent activity was not accumulated")
})

await test("successful note resets the new-activity byte baseline", async () => {
  const { hooks, fake } = await makePlugin()
  const send = async (delta) => {
    await hooks.event({ event: { type: "message.part.updated", properties: {
      part: { id: "p1", sessionID: "s1", type: "text", text: "" }, delta,
    } } })
    await hooks.event({ event: {
      type: "session.idle", properties: { sessionID: "s1" },
    } })
  }
  await send("first")
  await send("next")
  assert(fake.reminderCalls[0].transcript_bytes === Buffer.byteLength("first"),
         "first activity count is wrong")
  assert(fake.reminderCalls[1].transcript_bytes === Buffer.byteLength("next"),
         "baseline was not reset after injected note")
})

await test("detector failure fails open without retrying unchanged activity", async () => {
  const { hooks, prompts, fake } = await makePlugin()
  runtime.runReminder = async (payload) => {
    fake.reminderCalls.push(payload)
    throw new Error("detector unavailable")
  }
  await hooks.event({ event: { type: "message.part.updated", properties: {
    part: { id: "p1", sessionID: "s1", type: "text", text: "activity" },
  } } })
  const idle = { event: { type: "session.idle", properties: { sessionID: "s1" } } }
  await hooks.event(idle)
  await hooks.event(idle)
  assert(prompts.length === 0, "detector failure injected a prompt")
  assert(fake.reminderCalls.length === 1, "unchanged failure was retried")
})

await test("non-text and ignored parts do not count as substantive activity", async () => {
  const { hooks, prompts } = await makePlugin()
  for (const part of [
    { id: "p1", sessionID: "s1", type: "tool", text: "x".repeat(60 * 1024) },
    { id: "p2", sessionID: "s1", type: "text", text: "x".repeat(60 * 1024), ignored: true },
  ]) {
    await hooks.event({ event: { type: "message.part.updated", properties: { part } } })
  }
  await hooks.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } })
  assert(prompts.length === 0, "non-substantive activity triggered a reminder")
})

Object.assign(runtime, real)

if (failures.length) {
  console.error(`\n${failures.length} failure(s): ${failures.join(", ")}`)
  process.exit(1)
}

console.log("\nAll OpenCode memory plugin tests passed.")

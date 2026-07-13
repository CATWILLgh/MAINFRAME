#!/usr/bin/env node
// Tests for the OpenCode dispatcher plugin (adapters/opencode/plugins/mainframe-gates.js).
// Run: `node tools/test_mainframe_gates.mjs` (exit 0 = pass). No deps: the
// plugin's `runtime` seam (execFile/existsSync) is faked, so tests pin the
// dispatcher's contract without OpenCode or python3.
//
// Pinned block contract: deny -> throw with reason; ask -> throw with the
// relay suffix; nonzero exit / empty / unparseable stdout -> pass (fail-open).
// Invariant: the `after` handler must NEVER throw — the side effect has
// already landed, and on OpenCode a thrown after-hook marks an executed call
// as failed (the model may then retry a commit or delete).
// Invariant: the plugin must not depend on the host-provided Bun `$` — the
// desktop app runs the engine on Node, where plugins receive `$ = undefined`.

import { mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import * as pluginModule from "../adapters/opencode/plugins/mainframe-gates.js"

const { MainframeGates } = pluginModule
// The seam hangs off the factory, not the module: OpenCode's legacy loader
// throws on any non-function module export.
const runtime = MainframeGates.runtime

// Real bindings, captured before any fake mutates the seam — the integration
// tests at the bottom put them back to exercise a real python3 child.
const real = { ...runtime }

// Fake process runner: responses are looked up by a substring of the spawned
// command line. Each call records the command line and the stdin payload.
function fakeRuntime(responses) {
  const calls = []
  runtime.existsSync = () => true
  runtime.spawn = (cmd, args, opts) => {
    const cmdline = [cmd, ...(args || [])].join(" ")
    const call = { cmdline, stdin: "", cwd: opts?.cwd, env: opts?.env }
    calls.push(call)
    let resp = { exitCode: 0, stdout: "" }
    for (const [needle, r] of Object.entries(responses)) {
      if (cmdline.includes(needle)) { resp = r; break }
    }
    if (resp instanceof Error) throw resp
    const listeners = {}
    setImmediate(() => {
      // Real spawn failures (python3 absent) emit an async `error` with NO
      // `close` — the fake must mirror that, not a synchronous throw.
      if (resp.asyncError) { listeners.error?.(new Error("spawn ENOENT")); return }
      if (resp.stdout) listeners.data?.(resp.stdout)
      listeners.close?.(resp.exitCode)
    })
    return {
      on: (ev, fn) => { listeners[ev] = fn },
      stdout: { on: (ev, fn) => { if (ev === "data") listeners.data = fn } },
      stdin: { on: () => {}, end: (data) => { call.stdin = String(data ?? "") } },
    }
  }
  return { calls }
}

function decision(verdict, reason) {
  return JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: verdict,
      permissionDecisionReason: reason,
    },
  })
}

function note(text) {
  return JSON.stringify({
    hookSpecificOutput: { hookEventName: "PostToolUse", additionalContext: text },
  })
}

async function plugin(responses) {
  const fake = fakeRuntime({ ...responses })
  const hooks = await MainframeGates({ directory: "/tmp/proj" })
  return { hooks, calls: fake.calls }
}

async function expectThrow(fn) {
  try { await fn() } catch (e) { return String(e.message ?? e) }
  return null
}

const failures = []
async function test(name, fn) {
  try { await fn(); console.log(`  ok   ${name}`) }
  catch (e) { failures.push(name); console.log(`  FAIL ${name}: ${e.message}`) }
}
const assert = (cond, msg) => { if (!cond) throw new Error(msg) }

await test("every module export is a function (legacy loader contract)", async () => {
  for (const [name, value] of Object.entries(pluginModule)) {
    assert(typeof value === "function",
           `export "${name}" is ${typeof value} — OpenCode's legacy loader throws on it`)
  }
})

await test("no Bun $ (desktop Node runtime): plugin stays active and blocks", async () => {
  const fake = fakeRuntime({
    "secret-commit-gate.py": { exitCode: 0, stdout: decision("deny", "Commit blocked — secret") },
  })
  // The desktop app passes `$ = undefined` to plugins; the factory must not touch it.
  const hooks = await MainframeGates({ $: undefined, directory: "/tmp/proj" })
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "git commit -m x" } }))
  assert(msg && msg.includes("Commit blocked — secret"), `got: ${msg}`)
  assert(fake.calls.some((c) => c.cmdline.includes("secret-commit-gate.py")), "gate not spawned")
})

await test("deny from secret gate throws with the script reason", async () => {
  const { hooks } = await plugin({
    "secret-commit-gate.py": { exitCode: 0, stdout: decision("deny", "Commit blocked — secret") },
  })
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "git commit -m x" } }))
  assert(msg && msg.includes("Commit blocked — secret"), `got: ${msg}`)
})

await test("ask from path gate throws with the relay-to-user suffix", async () => {
  const { hooks } = await plugin({
    "path-validation.py": { exitCode: 0, stdout: decision("ask", "rm -rf target outside project") },
  })
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "rm -rf /elsewhere" } }))
  assert(msg && msg.includes("outside project"), `got: ${msg}`)
  assert(msg.includes("mainframe-gates:"), `suffix missing: ${msg}`)
})

await test("async spawn error without close (python3 absent) passes (fail-open)", async () => {
  const { hooks } = await plugin({
    "path-validation.py": { asyncError: true },
  })
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "rm -rf x" } }))
  assert(msg === null, `unexpected throw: ${msg}`)
})

await test("nonzero exit from a gate passes (fail-open)", async () => {
  const { hooks } = await plugin({
    "path-validation.py": { exitCode: 1, stdout: decision("ask", "boom") },
  })
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "rm -rf x" } }))
  assert(msg === null, `unexpected throw: ${msg}`)
})

await test("empty and unparseable stdout pass (fail-open)", async () => {
  for (const stdout of ["", "not json {"]) {
    const { hooks } = await plugin({ "path-validation.py": { exitCode: 0, stdout } })
    const msg = await expectThrow(() =>
      hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "rm -rf x" } }))
    assert(msg === null, `unexpected throw for ${JSON.stringify(stdout)}: ${msg}`)
  }
})

await test("allow decision from a gate passes", async () => {
  const { hooks } = await plugin({
    "path-validation.py": { exitCode: 0, stdout: decision("allow", "inside project") },
  })
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "rm -rf sub" } }))
  assert(msg === null, `unexpected throw: ${msg}`)
})

await test("non-bash tool and unhinted command spawn nothing in before", async () => {
  const { hooks, calls } = await plugin({})
  const baseline = calls.length
  await hooks["tool.execute.before"]({ tool: "edit" }, { args: {} })
  await hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "ls -la" } })
  assert(calls.length === baseline, "unexpected spawn")
})

await test("advisory note from a bash reminder is appended to output", async () => {
  const { hooks } = await plugin({
    "bash-pattern-reminder.py": { exitCode: 0, stdout: note("prefer rg over grep") },
  })
  const output = { args: { command: "git commit -m x" }, output: "done" }
  await hooks["tool.execute.after"]({ tool: "bash", args: { command: "git commit -m x" } }, output)
  assert(output.output.includes("done"), "original output lost")
  assert(output.output.includes("[mainframe] prefer rg over grep"), `note missing: ${output.output}`)
})

await test("edit args translate to CC shape in the stdin payload", async () => {
  const { hooks, calls } = await plugin({
    "scan-suppression-markers.py": { exitCode: 0, stdout: note("marker found") },
  })
  const output = { output: "Edit applied" }
  await hooks["tool.execute.after"](
    { tool: "edit", args: { filePath: "/tmp/proj/a.py", oldString: "x", newString: "y" } },
    output)
  const spawn = calls.find((c) => c.cmdline.includes("scan-suppression-markers.py"))
  assert(spawn, "file script not spawned")
  assert(spawn.stdin.includes('"tool_name":"Edit"'), spawn.stdin.slice(0, 200))
  assert(spawn.stdin.includes("file_path"), "file_path missing in payload")
  assert(spawn.stdin.includes("old_string"), "old_string missing in payload")
  assert(spawn.env?.CLAUDE_PROJECT_DIR === "/tmp/proj", "CLAUDE_PROJECT_DIR not in env")
  assert(output.output.includes("[mainframe] marker found"), output.output)
})

await test("after handler NEVER throws: exploding spawn leaves output intact", async () => {
  const { hooks } = await plugin({
    "scan-suppression-markers.py": new Error("spawn exploded"),
  })
  const output = { output: "Edit applied" }
  const msg = await expectThrow(() =>
    hooks["tool.execute.after"](
      { tool: "edit", args: { filePath: "/tmp/proj/a.py" } }, output))
  assert(msg === null, `after threw: ${msg}`)
  assert(output.output === "Edit applied", "output mutated on failure")
})

await test("after handler survives a broken output object", async () => {
  const { hooks } = await plugin({
    "bash-pattern-reminder.py": { exitCode: 0, stdout: note("n") },
  })
  const frozen = Object.freeze({ args: { command: "git commit" }, output: "x" })
  const msg = await expectThrow(() =>
    hooks["tool.execute.after"]({ tool: "bash", args: { command: "git commit" } }, frozen))
  assert(msg === null, `after threw on frozen output: ${msg}`)
})

await test("duplicate notes are suppressed within a session", async () => {
  const { hooks } = await plugin({
    "python-security-scan.py": { exitCode: 0, stdout: note("S307 eval at a.py:10") },
  })
  const mk = () => ({ output: "Edit applied" })
  const input = { tool: "edit", args: { filePath: "/tmp/proj/a.py" } }
  const first = mk(); await hooks["tool.execute.after"](input, first)
  const second = mk(); await hooks["tool.execute.after"](input, second)
  assert(first.output.includes("S307"), "first note missing")
  assert(!second.output.includes("S307"), `duplicate not suppressed: ${second.output}`)
})

await test("deny decision on an after row cannot block (mode partition)", async () => {
  const { hooks } = await plugin({
    "bash-pattern-reminder.py": { exitCode: 0, stdout: decision("deny", "evil") },
  })
  const output = { args: { command: "git commit" }, output: "x" }
  const msg = await expectThrow(() =>
    hooks["tool.execute.after"]({ tool: "bash", args: { command: "git commit" } }, output))
  assert(msg === null, `after threw on decision output: ${msg}`)
  assert(!output.output.includes("evil"), "decision text leaked into notes")
})

await test("not-ready plugin no-ops both handlers", async () => {
  fakeRuntime({ "python3 -c": { exitCode: 1, stdout: "" } })
  const hooks = await MainframeGates({ directory: "/tmp/proj" })
  const output = { args: { command: "git commit" }, output: "x" }
  const msg1 = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "git commit" } }))
  const msg2 = await expectThrow(() =>
    hooks["tool.execute.after"]({ tool: "bash", args: { command: "git commit" } }, output))
  assert(msg1 === null && msg2 === null && output.output === "x", "not-ready leaked behavior")
})

await test("missing hub scripts disable the plugin (not-ready)", async () => {
  const fake = fakeRuntime({})
  runtime.existsSync = () => false
  const hooks = await MainframeGates({ directory: "/tmp/proj" })
  const baseline = fake.calls.length
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "git commit" } }))
  assert(msg === null, `not-ready threw: ${msg}`)
  assert(fake.calls.length === baseline, "row spawned while not ready")
})

await test("telemetry row spawns tagged with source/session/event", async () => {
  const { hooks, calls } = await plugin({})
  await hooks["tool.execute.after"](
    { tool: "bash", args: { command: "ls" }, sessionID: "ses_123" },
    { output: "x" })
  const spawn = calls.find((c) => c.cmdline.includes("telemetry.py"))
  assert(spawn, "telemetry.py was not spawned on an after event")
  for (const marker of ['"source":"opencode"', '"session_id":"ses_123"',
                        '"hook_event_name":"PostToolUse"']) {
    assert(spawn.stdin.includes(marker), `payload missing ${marker}`)
  }
})

// The two tests below spawn a real python3 child: a stubbed spawn can verify
// dispatch but not that the payload actually crosses the process boundary.

const ROUNDTRIP_PY = [
  "import json, sys",
  "p = json.load(sys.stdin)",
  'out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",',
  '       "permissionDecision": "deny",',
  '       "permissionDecisionReason": "roundtrip:" + p["tool_input"]["command"]}}',
  "print(json.dumps(out))",
].join("\n")

const EARLY_EXIT_PY = "import sys\nsys.exit(0)\n"

function fixtureDir(gates) {
  const dir = mkdtempSync(join(tmpdir(), "mfgates-"))
  for (const [name, body] of Object.entries(gates)) writeFileSync(join(dir, name), body)
  Object.assign(runtime, real, { scriptsDir: dir })
  return dir
}

await test("integration: payload round-trips through a real python3 child", async () => {
  // The fixture dir doubles as the session directory: spawn cwd must exist.
  const dir = fixtureDir({ "secret-commit-gate.py": ROUNDTRIP_PY, "path-validation.py": EARLY_EXIT_PY })
  const hooks = await MainframeGates({ $: undefined, directory: dir })
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "git commit -m stdintest" } }))
  assert(msg && msg.includes("roundtrip:git commit -m stdintest"), `got: ${msg}`)
})

await test("integration: script exiting before reading stdin fails open, host survives", async () => {
  const dir = fixtureDir({ "secret-commit-gate.py": ROUNDTRIP_PY, "path-validation.py": EARLY_EXIT_PY })
  const hooks = await MainframeGates({ $: undefined, directory: dir })
  // ~1 MB command overflows the pipe buffer so the early-exiting child forces
  // an EPIPE on the stdin write — the exact stream error that must not escape.
  const big = "rm -rf " + "x".repeat(1_000_000)
  const msg = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: big } }))
  assert(msg === null, `expected fail-open, got: ${msg}`)
})

console.log(failures.length ? `${failures.length} FAILED` : "all passed")
process.exit(failures.length ? 1 : 0)

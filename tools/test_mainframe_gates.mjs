#!/usr/bin/env node
// Tests for the OpenCode dispatcher plugin (opencode/plugins/mainframe-gates.js).
// Run: `node tools/test_mainframe_gates.mjs` (exit 0 = pass). No deps: the Bun
// `$` shell is faked, so tests pin the dispatcher's contract without OpenCode.
//
// Pinned block contract: deny -> throw with reason; ask -> throw with the
// relay suffix; nonzero exit / empty / unparseable stdout -> pass (fail-open).
// Invariant: the `after` handler must NEVER throw — the side effect has
// already landed, and on OpenCode a thrown after-hook marks an executed call
// as failed (the model may then retry a commit or delete).

import { MainframeGates } from "../opencode/plugins/mainframe-gates.js"

// Fake Bun-shell: a tagged template returning a chainable promise whose
// response is looked up from `responses` by a substring of the command.
function fakeShell(responses) {
  const calls = []
  const $ = (strings, ...values) => {
    const cmd = strings.reduce((acc, s, i) => acc + s + (i < values.length ? String(values[i]) : ""), "")
    calls.push(cmd)
    let resp = { exitCode: 0, stdout: "" }
    for (const [needle, r] of Object.entries(responses)) {
      if (cmd.includes(needle)) { resp = r; break }
    }
    const promise = Promise.resolve(
      resp instanceof Error ? Promise.reject(resp) : {
        exitCode: resp.exitCode,
        stdout: { toString: () => resp.stdout },
      },
    )
    const chain = resp instanceof Error ? Promise.reject(resp) : promise
    chain.cwd = () => chain
    chain.quiet = () => chain
    chain.nothrow = () => chain
    chain.catch(() => {})
    return chain
  }
  $.calls = calls
  return $
}

const READY = {
  "python3 -c": { exitCode: 0, stdout: "3" },
  "test -f": { exitCode: 0, stdout: "" },
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
  const $ = fakeShell({ ...READY, ...responses })
  const hooks = await MainframeGates({ $, directory: "/tmp/proj" })
  return { hooks, $ }
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
  const { hooks, $ } = await plugin({})
  const baseline = $.calls.length
  await hooks["tool.execute.before"]({ tool: "edit" }, { args: {} })
  await hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "ls -la" } })
  assert($.calls.length === baseline, "unexpected spawn")
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

await test("edit args translate to CC shape for file scripts", async () => {
  const { hooks, $ } = await plugin({
    "scan-suppression-markers.py": { exitCode: 0, stdout: note("marker found") },
  })
  const output = { output: "Edit applied" }
  await hooks["tool.execute.after"](
    { tool: "edit", args: { filePath: "/tmp/proj/a.py", oldString: "x", newString: "y" } },
    output)
  const spawn = $.calls.find((c) => c.includes("scan-suppression-markers.py"))
  assert(spawn, "file script not spawned")
  assert(spawn.includes('"tool_name": "Edit"') || spawn.includes('"tool_name":"Edit"'), spawn.slice(0, 200))
  assert(spawn.includes("file_path"), "file_path missing in payload")
  assert(spawn.includes("old_string"), "old_string missing in payload")
  assert(output.output.includes("[mainframe] marker found"), output.output)
})

await test("after handler NEVER throws: rejecting row leaves output intact", async () => {
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
  const $ = fakeShell({ "python3 -c": { exitCode: 1, stdout: "" } })
  const hooks = await MainframeGates({ $, directory: "/tmp/proj" })
  const output = { args: { command: "git commit" }, output: "x" }
  const msg1 = await expectThrow(() =>
    hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "git commit" } }))
  const msg2 = await expectThrow(() =>
    hooks["tool.execute.after"]({ tool: "bash", args: { command: "git commit" } }, output))
  assert(msg1 === null && msg2 === null && output.output === "x", "not-ready leaked behavior")
})

console.log(failures.length ? `${failures.length} FAILED` : "all passed")
process.exit(failures.length ? 1 : 0)

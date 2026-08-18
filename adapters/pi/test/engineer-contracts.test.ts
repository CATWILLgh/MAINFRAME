import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import test from "node:test";

import {
  parseEngineerBlockManifest,
  parseEngineerCheckResult,
  parseEngineerCompletionManifest,
  parseEngineerVerifierVerdict,
} from "../src/profiles/engineer/contracts.js";
import { acquireEngineerWriterLock, inspectEngineerGit } from "../src/profiles/engineer/preflight.js";
import { EngineerWorkspace } from "../src/profiles/engineer/workspace.js";

const execFileAsync = promisify(execFile);

function block(overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: 1,
    blockId: "BLOCK-001",
    sessionMode: "new",
    goal: "Implement one bounded behavior",
    expectedHead: "a".repeat(40),
    scope: { include: ["src/**"], exclude: ["src/generated/**"] },
    invariants: ["Do not change public behavior outside the block"],
    acceptance: [
      { id: "A-001", requirement: "The behavior is implemented" },
      { id: "A-002", requirement: "The focused test passes" },
    ],
    forbiddenFutureStages: ["Do not implement BLOCK-002"],
    allowedChecks: [{ id: "CHECK-TEST", argv: ["npm", "test", "--", "focused"], timeoutMs: 60_000 }],
    ...overrides,
  };
}

test("block manifest accepts explicit new and resume session modes", () => {
  assert.equal(parseEngineerBlockManifest(block()).sessionMode, "new");
  assert.equal(parseEngineerBlockManifest(block({ sessionMode: "resume" })).sessionMode, "resume");
  assert.throws(() => parseEngineerBlockManifest(block({ sessionMode: "automatic" })), /new or resume/);
});

test("block manifest requires full Git id, unique acceptance, and argv checks", () => {
  assert.throws(() => parseEngineerBlockManifest(block({ expectedHead: "abc1234" })), /full Git object id/);
  assert.throws(() => parseEngineerBlockManifest(block({
    acceptance: [
      { id: "A-001", requirement: "One" },
      { id: "A-001", requirement: "Two" },
    ],
  })), /acceptance ids must be unique/);
  assert.throws(() => parseEngineerBlockManifest(block({
    allowedChecks: [{ id: "CHECK", command: "npm test", timeoutMs: 60_000 }],
  })), /unsupported field 'command'/);
});

test("candidate completion must cover every acceptance item with evidence", () => {
  const manifest = parseEngineerBlockManifest(block());
  assert.throws(() => parseEngineerCompletionManifest({
    schemaVersion: 1,
    blockId: "BLOCK-001",
    status: "candidate",
    summary: "Implemented the behavior",
    changedPaths: ["src/example.ts"],
    acceptanceClaims: [{ acceptanceId: "A-001", claim: "Implemented", evidence: ["src/example.ts:10"] }],
    blockers: [],
  }, manifest), /must claim every acceptance item/);
});

test("check result must match the exact approved argv and status semantics", () => {
  const manifest = parseEngineerBlockManifest(block());
  const result = parseEngineerCheckResult({
    schemaVersion: 1,
    checkId: "CHECK-TEST",
    argv: ["npm", "test", "--", "focused"],
    status: "passed",
    exitCode: 0,
    durationMs: 1234,
    output: { inline: "ok", truncated: false },
  }, manifest);
  assert.equal(result.status, "passed");
  assert.throws(() => parseEngineerCheckResult({
    ...result,
    argv: ["npm", "test"],
  }, manifest), /does not match allowed check/);
  assert.throws(() => parseEngineerCheckResult({
    ...result,
    status: "passed",
    exitCode: 1,
  }, manifest), /must have exitCode 0/);
  assert.throws(() => parseEngineerCheckResult({
    ...result,
    output: { inline: "partial", truncated: true },
  }, manifest), /must have one retainedPath/);
});

test("ready verdict requires exact coverage and verified results", () => {
  const manifest = parseEngineerBlockManifest(block());
  assert.throws(() => parseEngineerVerifierVerdict({
    schemaVersion: 1,
    blockId: "BLOCK-001",
    status: "ready-for-architect-review",
    items: [
      { acceptanceId: "A-001", verdict: "verified", reason: "Diff proves it", evidence: ["src/example.ts:10"] },
      { acceptanceId: "A-002", verdict: "unproven", reason: "No check result", evidence: [] },
    ],
  }, manifest), /requires every acceptance item to be verified/);
});

test("correction verdict requires a bounded packet and known check ids", () => {
  const manifest = parseEngineerBlockManifest(block());
  const verdict = parseEngineerVerifierVerdict({
    schemaVersion: 1,
    blockId: "BLOCK-001",
    status: "correction-required",
    items: [
      { acceptanceId: "A-001", verdict: "verified", reason: "Diff proves it", evidence: ["src/example.ts:10"] },
      { acceptanceId: "A-002", verdict: "missing", reason: "Focused test was not run", evidence: [] },
    ],
    correctionPacket: {
      instructions: ["Run the manifest-approved focused check and return its result"],
      missingEvidence: ["A-002 has no successful check result"],
      failedCheckIds: ["CHECK-TEST"],
    },
  }, manifest);
  assert.equal(verdict.status, "correction-required");
  assert.throws(() => parseEngineerVerifierVerdict({
    ...verdict,
    correctionPacket: { ...verdict.correctionPacket, failedCheckIds: ["UNKNOWN"] },
  }, manifest), /unknown check 'UNKNOWN'/);
});

test("closed contracts reject fields that could silently expand the run", () => {
  assert.throws(() => parseEngineerBlockManifest(block({ networkAccess: true })), /unsupported field 'networkAccess'/);
});

test("Git preflight binds the run to exact HEAD and records dirty paths", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-engineer-git-"));
  await execFileAsync("git", ["init", "-q", root]);
  await execFileAsync("git", ["-C", root, "config", "user.name", "MAINFRAME Test"]);
  await execFileAsync("git", ["-C", root, "config", "user.email", "mainframe-test@example.invalid"]);
  await writeFile(path.join(root, "tracked.txt"), "initial\n");
  await execFileAsync("git", ["-C", root, "add", "tracked.txt"]);
  await execFileAsync("git", ["-C", root, "commit", "-qm", "test: initial"]);
  const head = (await execFileAsync("git", ["-C", root, "rev-parse", "HEAD"], { encoding: "utf8" })).stdout.trim();
  await writeFile(path.join(root, "tracked.txt"), "changed\n");
  await writeFile(path.join(root, "untracked.txt"), "new\n");
  const manifest = parseEngineerBlockManifest(block({ expectedHead: head }));
  const facts = await inspectEngineerGit(root, manifest);
  assert.equal(facts.startingHead, head);
  assert.deepEqual(facts.initialDirtyPaths, ["tracked.txt", "untracked.txt"]);
  await assert.rejects(inspectEngineerGit(root, parseEngineerBlockManifest(block({ expectedHead: "b".repeat(40) }))), /HEAD changed/);
});

test("writer lock permits only one Pi engineer in a worktree", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-engineer-lock-"));
  await execFileAsync("git", ["init", "-q", root]);
  await execFileAsync("git", ["-C", root, "config", "user.name", "MAINFRAME Test"]);
  await execFileAsync("git", ["-C", root, "config", "user.email", "mainframe-test@example.invalid"]);
  await writeFile(path.join(root, "tracked.txt"), "initial\n");
  await execFileAsync("git", ["-C", root, "add", "tracked.txt"]);
  await execFileAsync("git", ["-C", root, "commit", "-qm", "test: initial"]);
  const head = (await execFileAsync("git", ["-C", root, "rev-parse", "HEAD"], { encoding: "utf8" })).stdout.trim();
  const facts = await inspectEngineerGit(root, parseEngineerBlockManifest(block({ expectedHead: head })));
  const first = await acquireEngineerWriterLock(facts, "BLOCK-001");
  await assert.rejects(acquireEngineerWriterLock(facts, "BLOCK-002"), /already has a Pi engineer writer/);
  await first.release();
  const second = await acquireEngineerWriterLock(facts, "BLOCK-002");
  await second.release();
});

test("engineer workspace requires an observed version for exact edits", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-engineer-workspace-"));
  await writeFile(path.join(root, "source.ts"), "const first = 1;\nconst second = 2;\n");
  const manifest = parseEngineerBlockManifest(block({
    scope: { include: ["*.ts", "src/**"], exclude: ["src/generated/**"] },
  }));
  const workspace = await EngineerWorkspace.create(root, manifest);
  const observed = await workspace.observe("source.ts");
  const edited = await workspace.edit("source.ts", observed.version, [
    { oldText: "first = 1", newText: "first = 10" },
    { oldText: "second = 2", newText: "second = 20" },
  ]);
  assert.match(edited.content, /first = 10/);
  assert.match(await readFile(path.join(root, "source.ts"), "utf8"), /second = 20/);
  await assert.rejects(
    workspace.edit("source.ts", observed.version, [{ oldText: "first = 10", newText: "first = 100" }]),
    /Re-read before editing/,
  );
});

test("engineer workspace detects external changes and refuses ambiguous edits", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-engineer-stale-"));
  const target = path.join(root, "source.ts");
  await writeFile(target, "same\nsame\n");
  const workspace = await EngineerWorkspace.create(root, parseEngineerBlockManifest(block({
    scope: { include: ["*.ts"], exclude: [] },
  })));
  const observed = await workspace.observe("source.ts");
  await assert.rejects(
    workspace.edit("source.ts", observed.version, [{ oldText: "same", newText: "changed" }]),
    /must occur exactly once/,
  );
  await writeFile(target, "external\n");
  await assert.rejects(
    workspace.edit("source.ts", observed.version, [{ oldText: "same", newText: "changed" }]),
    /changed after it was read/,
  );
});

test("engineer workspace creates only new in-scope text files", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-engineer-create-"));
  const workspace = await EngineerWorkspace.create(root, parseEngineerBlockManifest(block({
    scope: { include: ["src/**"], exclude: ["src/generated/**"] },
  })));
  await workspace.createFile("src/new.ts", "export const value = 1;\n");
  assert.equal(await readFile(path.join(root, "src/new.ts"), "utf8"), "export const value = 1;\n");
  await assert.rejects(workspace.createFile("src/new.ts", "overwrite\n"), /already exists/);
  await assert.rejects(workspace.createFile("src/generated/no.ts", "no\n"), /outside the block scope/);
  await assert.rejects(workspace.createFile("../escape.ts", "no\n"), /outside the project/);
});

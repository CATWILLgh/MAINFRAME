import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import test from "node:test";

import {
  compileEngineerBlockManifest,
  parseEngineerBlockRequest,
} from "../src/profiles/engineer/block-request.js";
import { inspectEngineerGit, inspectEngineerGitState } from "../src/profiles/engineer/preflight.js";
import {
  engineerRuntimeDirectory,
  loadActiveEngineerManifest,
  markEngineerBlockReadyForArchitectReview,
  reconcileAcceptedEngineerBlock,
  recordActiveEngineerBlock,
} from "../src/profiles/engineer/session-state.js";

const execFileAsync = promisify(execFile);

test("short block request compiles mechanical manifest fields", () => {
  const request = parseEngineerBlockRequest({
    schemaVersion: 1,
    goal: "Implement one bounded behavior",
    writePaths: ["src/orders/**", "test/orders/**"],
    acceptance: ["The behavior is implemented", "The focused test passes"],
    checks: [{ argv: ["npm", "test", "--", "orders"] }],
  });
  const manifest = compileEngineerBlockManifest(request, "a".repeat(40), "new");
  assert.match(manifest.blockId, /^BLOCK-[0-9A-F]{12}$/);
  assert.equal(manifest.expectedHead, "a".repeat(40));
  assert.equal(manifest.sessionMode, "new");
  assert.deepEqual(manifest.scope, { include: ["src/orders/**", "test/orders/**"], exclude: [] });
  assert.deepEqual(manifest.invariants, []);
  assert.deepEqual(manifest.acceptance.map(({ id }) => id), ["A-001", "A-002"]);
  assert.deepEqual(manifest.allowedChecks, [{
    id: "CHECK-001",
    argv: ["npm", "test", "--", "orders"],
    timeoutMs: 60_000,
  }]);
  assert.equal(compileEngineerBlockManifest(request, "a".repeat(40), "new").blockId, manifest.blockId);
});

test("short block request rejects ambiguous or expanding fields", () => {
  assert.throws(() => parseEngineerBlockRequest({
    schemaVersion: 1,
    goal: "Implement",
    writePaths: [],
    acceptance: ["Done"],
  }), /writePaths must be a non-empty array/);
  assert.throws(() => parseEngineerBlockRequest({
    schemaVersion: 1,
    goal: "Implement",
    writePaths: ["src/**"],
    acceptance: ["Done"],
    networkAccess: true,
  }), /unsupported field 'networkAccess'/);
  assert.throws(() => parseEngineerBlockRequest({
    schemaVersion: 1,
    goal: "Implement",
    writePaths: ["src/**"],
    acceptance: ["Done"],
    checks: "npm test",
  }), /checks must be an array/);
  assert.throws(() => parseEngineerBlockRequest({
    schemaVersion: 1,
    goal: "Implement",
    writePaths: ["src/**"],
    acceptance: ["Done"],
    checks: [{ argv: ["git", "reset", "--hard"] }],
  }), /cannot invoke Git/);
  assert.throws(() => parseEngineerBlockRequest({
    schemaVersion: 1,
    goal: "Implement",
    writePaths: ["src/**"],
    acceptance: ["Done"],
    checks: [{ argv: ["bash", "-lc", "git status"] }],
  }), /cannot use an inline shell/);
});

test("resume rejects a runtime-owned path that leaves the project", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-request-state-"));
  await execFileAsync("git", ["init", "-q", root]);
  await execFileAsync("git", ["-C", root, "config", "user.name", "MAINFRAME Test"]);
  await execFileAsync("git", ["-C", root, "config", "user.email", "mainframe-test@example.invalid"]);
  await writeFile(path.join(root, "source.ts"), "initial\n");
  await execFileAsync("git", ["-C", root, "add", "source.ts"]);
  await execFileAsync("git", ["-C", root, "commit", "-qm", "test: initial"]);
  const head = (await execFileAsync("git", ["-C", root, "rev-parse", "HEAD"], { encoding: "utf8" })).stdout.trim();
  const request = parseEngineerBlockRequest({
    schemaVersion: 1,
    goal: "Implement",
    writePaths: ["*.ts"],
    acceptance: ["Done"],
  });
  const manifest = compileEngineerBlockManifest(request, head, "new");
  const facts = await inspectEngineerGit(root, manifest);
  await recordActiveEngineerBlock(facts, manifest);
  const statePath = path.join(engineerRuntimeDirectory(facts), "active-block.json");
  const state = JSON.parse(await readFile(statePath, "utf8")) as Record<string, unknown>;
  state.ownedPaths = [{ path: "../escape", sha256: "a".repeat(64) }];
  await writeFile(statePath, `${JSON.stringify(state)}\n`);
  await assert.rejects(loadActiveEngineerManifest(facts), /path leaves the project/);
});

test("new reconciles only a reviewed block committed by the primary agent", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-request-accepted-"));
  await execFileAsync("git", ["init", "-q", root]);
  await execFileAsync("git", ["-C", root, "config", "user.name", "MAINFRAME Test"]);
  await execFileAsync("git", ["-C", root, "config", "user.email", "mainframe-test@example.invalid"]);
  await writeFile(path.join(root, "source.ts"), "initial\n");
  await execFileAsync("git", ["-C", root, "add", "source.ts"]);
  await execFileAsync("git", ["-C", root, "commit", "-qm", "test: initial"]);
  const head = (await execFileAsync("git", ["-C", root, "rev-parse", "HEAD"], { encoding: "utf8" })).stdout.trim();
  const request = parseEngineerBlockRequest({
    schemaVersion: 1,
    goal: "Implement",
    writePaths: ["*.ts"],
    acceptance: ["Done"],
  });
  const manifest = compileEngineerBlockManifest(request, head, "new");
  let facts = await inspectEngineerGit(root, manifest);
  await writeFile(path.join(root, "source.ts"), "implemented\n");
  await recordActiveEngineerBlock(facts, manifest, ["source.ts"]);
  await assert.rejects(reconcileAcceptedEngineerBlock(facts), /still needs architect review/);
  await markEngineerBlockReadyForArchitectReview(facts);
  await assert.rejects(reconcileAcceptedEngineerBlock(facts), /before the primary agent commits/);
  await execFileAsync("git", ["-C", root, "add", "source.ts"]);
  await execFileAsync("git", ["-C", root, "commit", "-qm", "feat(test): implement block"]);
  facts = await inspectEngineerGitState(root);
  const receipt = await reconcileAcceptedEngineerBlock(facts);
  assert.equal(receipt?.blockId, manifest.blockId);
  assert.deepEqual(receipt?.paths, ["source.ts"]);
  assert.equal(receipt?.previousHead, head);
  assert.equal(receipt?.acceptedHead, facts.startingHead);
  await assert.rejects(loadActiveEngineerManifest(facts), /no recorded Pi engineer block/);
});

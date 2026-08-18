import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import test from "node:test";

import { parseEngineerBlockManifest } from "../src/profiles/engineer/contracts.js";
import { inspectEngineerGitState } from "../src/profiles/engineer/preflight.js";
import {
  commitAcceptedEngineerBlock,
  loadActiveEngineerManifest,
  markEngineerBlockReadyForArchitectReview,
  recordActiveEngineerBlock,
} from "../src/profiles/engineer/session-state.js";

const execFileAsync = promisify(execFile);

test("architect acceptance commits only Pi-owned paths and preserves unrelated staged work", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-engineer-commit-"));
  await execFileAsync("git", ["init", "-q", root]);
  await execFileAsync("git", ["-C", root, "config", "user.name", "MAINFRAME Test"]);
  await execFileAsync("git", ["-C", root, "config", "user.email", "mainframe-test@example.invalid"]);
  await writeFile(path.join(root, "owned.txt"), "initial\n");
  await writeFile(path.join(root, "unrelated.txt"), "initial\n");
  await execFileAsync("git", ["-C", root, "add", "owned.txt", "unrelated.txt"]);
  await execFileAsync("git", ["-C", root, "commit", "-qm", "test: initial"]);
  const head = (await execFileAsync("git", ["-C", root, "rev-parse", "HEAD"], { encoding: "utf8" })).stdout.trim();
  await writeFile(path.join(root, "owned.txt"), "implemented\n");
  await writeFile(path.join(root, "created.txt"), "created\n");
  await writeFile(path.join(root, "unrelated.txt"), "user staged\n");
  await execFileAsync("git", ["-C", root, "add", "unrelated.txt"]);
  const manifest = parseEngineerBlockManifest({
    schemaVersion: 1,
    blockId: "BLOCK-COMMIT",
    sessionMode: "new",
    goal: "Implement one block",
    expectedHead: head,
    scope: { include: ["*.txt"], exclude: [] },
    invariants: [],
    acceptance: [{ id: "A-001", requirement: "Done" }],
    forbiddenFutureStages: [],
    allowedChecks: [],
  });
  const facts = await inspectEngineerGitState(root);
  await recordActiveEngineerBlock(facts, manifest, ["owned.txt", "created.txt"]);
  await assert.rejects(commitAcceptedEngineerBlock(facts, "feat(test): implement block"), /has not reached architect review/);
  await markEngineerBlockReadyForArchitectReview(facts);
  await assert.rejects(commitAcceptedEngineerBlock(facts, "not conventional"), /Conventional Commits/);
  const receipt = await commitAcceptedEngineerBlock(facts, "feat(test): implement block");
  assert.deepEqual(receipt.paths, ["created.txt", "owned.txt"]);
  const committed = (await execFileAsync("git", ["-C", root, "show", "--format=", "--name-only", "HEAD"], { encoding: "utf8" })).stdout.trim().split("\n").sort();
  assert.deepEqual(committed, ["created.txt", "owned.txt"]);
  const staged = (await execFileAsync("git", ["-C", root, "diff", "--cached", "--name-only"], { encoding: "utf8" })).stdout.trim();
  assert.equal(staged, "unrelated.txt");
  await assert.rejects(loadActiveEngineerManifest(await inspectEngineerGitState(root)), /no recorded Pi engineer block/);
});

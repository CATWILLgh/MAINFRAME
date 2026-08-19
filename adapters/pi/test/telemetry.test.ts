import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { DatabaseSync } from "node:sqlite";

import { writeEngineerTelemetry } from "../src/telemetry.js";

test("engineer telemetry records privacy-safe run, usage, and tool summaries", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "mainframe-pi-telemetry-"));
  const databasePath = path.join(root, "telemetry.db");
  const previous = process.env.MAINFRAME_PI_TELEMETRY_DB;
  process.env.MAINFRAME_PI_TELEMETRY_DB = databasePath;
  try {
    const status = writeEngineerTelemetry({
      facts: {
        projectRoot: "/private/project-name",
        gitDirectory: "/private/project-name/.git",
        worktreeId: "worktree-secret",
        startingHead: "a".repeat(40),
        initialDirtyPaths: ["private-file.txt"],
      },
      mode: "new",
      profile: {
        executor: { provider: "provider", model: "executor", thinking: "low" },
        verifier: { provider: "provider", model: "verifier", thinking: "high" },
      },
      result: {
        status: "ready-for-architect-review",
        rounds: 2,
        checks: [{ status: "passed" }],
        verdict: { status: "ready-for-architect-review" },
        usage: {
          executor: { requests: 2, input: 100, output: 20, cacheRead: 50, cacheWrite: 5, cost: 0.01 },
          verifier: { requests: 1, input: 30, output: 10, cacheRead: 0, cacheWrite: 0, cost: 0.002 },
        },
        metrics: {
          executor: { toolCalls: 4, repeatedToolCalls: 1, callsByTool: { read: 2, edit: 2 }, failedToolCalls: 0, compactions: 1, retries: 0 },
          verifier: { toolCalls: 2, repeatedToolCalls: 0, callsByTool: { read: 2 }, failedToolCalls: 0, compactions: 0, retries: 1 },
        },
      } as never,
      durationMs: 3210,
    });
    assert.equal(status, "written");
    const database = new DatabaseSync(databasePath, { readOnly: true });
    const rows = database.prepare("SELECT event, payload, project, session_id FROM events ORDER BY id").all() as Array<{
      event: string; payload: string; project: string; session_id: string;
    }>;
    database.close();
    assert.equal(rows.filter(({ event }) => event === "model_usage").length, 2);
    assert.equal(rows.filter(({ event }) => event === "engineer_tool_summary").length, 3);
    const run = JSON.parse(rows.find(({ event }) => event === "engineer_run")!.payload);
    assert.equal(run.correction_rounds, 1);
    assert.equal(run.tool_calls, 6);
    assert.equal(run.compactions, 1);
    const stored = await readFile(databasePath);
    assert.equal(stored.includes(Buffer.from("/private/project-name")), false);
    assert.equal(stored.includes(Buffer.from("private-file.txt")), false);
    assert.equal(rows[0]!.project.length, 20);
    assert.equal(rows[0]!.session_id.length, 24);
  } finally {
    if (previous === undefined) delete process.env.MAINFRAME_PI_TELEMETRY_DB;
    else process.env.MAINFRAME_PI_TELEMETRY_DB = previous;
  }
});

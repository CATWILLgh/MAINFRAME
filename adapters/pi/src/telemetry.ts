import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";

import type { ModelSelection } from "./model-types.js";
import type { EngineerPipelineResult } from "./profiles/engineer/runtime.js";
import type { EngineerSessionMode } from "./profiles/engineer/contracts.js";
import type { EngineerGitFacts } from "./profiles/engineer/preflight.js";

const ADAPTER_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_DIRECTORY = path.resolve(ADAPTER_ROOT, "../../workspace/runtime/pi/telemetry");

const SCHEMA = `
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  agent_type TEXT NOT NULL,
  tool_use_id TEXT NOT NULL,
  project TEXT NOT NULL,
  hook_event TEXT NOT NULL,
  model TEXT NOT NULL,
  origin TEXT NOT NULL,
  event TEXT NOT NULL,
  payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_event_ts ON events(event, ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_sample
ON events(json_extract(payload, '$.sample_id'))
WHERE json_extract(payload, '$.sample_id') IS NOT NULL;
`;

function sha(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function telemetryPath(): string | undefined {
  const explicit = process.env.MAINFRAME_PI_TELEMETRY_DB;
  if (explicit) return path.resolve(explicit);
  if (!existsSync(path.join(DEFAULT_DIRECTORY, "enabled"))) return undefined;
  return path.join(DEFAULT_DIRECTORY, "telemetry.db");
}

function insert(
  database: DatabaseSync,
  envelope: {
    runId: string;
    project: string;
    session: string;
    agentType: string;
    model: string;
  },
  event: string,
  payload: Record<string, string | number | boolean>,
): void {
  database.prepare(`
    INSERT INTO events(
      ts, schema_version, session_id, turn_id, agent_id, agent_type,
      tool_use_id, project, hook_event, model, origin, event, payload
    ) VALUES (?, 1, ?, ?, ?, ?, '', ?, 'engineer', ?, 'runtime', ?, ?)
  `).run(
    new Date().toISOString(), envelope.session, envelope.runId,
    `${envelope.session}:${envelope.agentType}`, envelope.agentType,
    envelope.project, envelope.model, event, JSON.stringify(payload),
  );
}

function writeUsage(
  database: DatabaseSync,
  envelope: Parameters<typeof insert>[1],
  sampleId: string,
  usage: EngineerPipelineResult["usage"]["executor"],
): void {
  if (usage.requests <= 0) return;
  insert(database, envelope, "model_usage", {
    sample_id: sampleId,
    source: "pi-sdk",
    input_tokens: usage.input,
    cached_input_tokens: usage.cacheRead,
    cache_write_tokens: usage.cacheWrite,
    output_tokens: usage.output,
    reasoning_output_tokens: 0,
    total_tokens: usage.input + usage.output,
    request_count: usage.requests,
    cost_micro_usd: Math.max(0, Math.round(usage.cost * 1_000_000)),
  });
}

export function writeEngineerTelemetry(options: {
  facts: EngineerGitFacts;
  mode: EngineerSessionMode;
  profile: { executor: ModelSelection; verifier: ModelSelection };
  result: EngineerPipelineResult;
  durationMs: number;
}): "written" | "disabled" | "error" {
  const databasePath = telemetryPath();
  if (!databasePath) return "disabled";
  try {
    mkdirSync(path.dirname(databasePath), { recursive: true, mode: 0o700 });
    const database = new DatabaseSync(databasePath);
    try {
      database.exec(
        "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000;",
      );
      database.exec(SCHEMA);
      const runId = randomUUID();
      const base = {
        runId,
        project: sha(options.facts.projectRoot).slice(0, 20),
        session: sha(`${options.facts.projectRoot}\0${options.facts.worktreeId}`).slice(0, 24),
      };
      const executorModel = `${options.profile.executor.provider}/${options.profile.executor.model}`;
      const verifierModel = `${options.profile.verifier.provider}/${options.profile.verifier.model}`;
      database.exec("BEGIN IMMEDIATE");
      writeUsage(database, { ...base, agentType: "engineer-executor", model: executorModel }, `${runId}:executor`, options.result.usage.executor);
      writeUsage(database, { ...base, agentType: "engineer-verifier", model: verifierModel }, `${runId}:verifier`, options.result.usage.verifier);
      for (const [stage, metrics, model] of [
        ["executor", options.result.metrics.executor, executorModel],
        ["verifier", options.result.metrics.verifier, verifierModel],
      ] as const) {
        for (const [toolName, calls] of Object.entries(metrics.callsByTool)) {
          insert(database, { ...base, agentType: `engineer-${stage}`, model }, "engineer_tool_summary", {
            sample_id: `${runId}:${stage}:tool:${toolName}`,
            stage,
            tool_name: toolName,
            calls,
          });
        }
      }
      const checksPassed = options.result.checks.filter(({ status }) => status === "passed").length;
      insert(database, { ...base, agentType: "engineer-pipeline", model: executorModel }, "engineer_run", {
        sample_id: `${runId}:run`,
        mode: options.mode,
        status: options.result.status,
        rounds: options.result.rounds,
        correction_rounds: Math.max(0, options.result.rounds - 1),
        checks_total: options.result.checks.length,
        checks_passed: checksPassed,
        verifier_status: options.result.verdict?.status ?? "unavailable",
        duration_ms: Math.max(0, Math.round(options.durationMs)),
        tool_calls: options.result.metrics.executor.toolCalls + options.result.metrics.verifier.toolCalls,
        repeated_tool_calls: options.result.metrics.executor.repeatedToolCalls + options.result.metrics.verifier.repeatedToolCalls,
        failed_tool_calls: options.result.metrics.executor.failedToolCalls + options.result.metrics.verifier.failedToolCalls,
        compactions: options.result.metrics.executor.compactions + options.result.metrics.verifier.compactions,
        retries: options.result.metrics.executor.retries + options.result.metrics.verifier.retries,
        executor_effort: options.profile.executor.thinking,
        verifier_effort: options.profile.verifier.thinking,
      });
      database.exec("COMMIT");
    } catch (error) {
      try { database.exec("ROLLBACK"); } catch { /* no active transaction */ }
      throw error;
    } finally {
      database.close();
    }
    return "written";
  } catch {
    return "error";
  }
}

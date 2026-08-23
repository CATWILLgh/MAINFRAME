import { randomUUID } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

import type { EngineerPipelineResult } from "./runtime.js";
import type { EngineerBlockManifest } from "./contracts.js";
import type { EngineerGitFacts } from "./preflight.js";
import { engineerRuntimeDirectory } from "./session-state.js";

export interface EngineerRunHandle {
  runId: string;
  directory: string;
  statePath: string;
  resultPath: string;
  startedAt: string;
  mode: "new" | "resume";
  blockId: string;
  facts: EngineerGitFacts;
}

interface LatestEngineerRun {
  schemaVersion: 1;
  worktreeId: string;
  blockId: string;
  phase: "running" | "finished";
  status: string;
}

async function latestEngineerRun(facts: EngineerGitFacts): Promise<LatestEngineerRun | undefined> {
  const statePath = path.join(engineerRuntimeDirectory(facts), "latest-run.json");
  let raw: unknown;
  try {
    raw = JSON.parse(await readFile(statePath, "utf8"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw new Error("The latest Pi engineer run state is unreadable");
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("The latest Pi engineer run state is malformed");
  }
  const candidate = raw as Record<string, unknown>;
  if (
    candidate.schemaVersion !== 1 ||
    candidate.worktreeId !== facts.worktreeId ||
    typeof candidate.blockId !== "string" ||
    (candidate.phase !== "running" && candidate.phase !== "finished") ||
    typeof candidate.status !== "string"
  ) {
    throw new Error("The latest Pi engineer run state does not match this worktree");
  }
  return candidate as unknown as LatestEngineerRun;
}

export async function validateEngineerResumeDisposition(
  facts: EngineerGitFacts,
  blockId: string,
  hasFeedback: boolean,
): Promise<void> {
  const latest = await latestEngineerRun(facts);
  if (!latest) return;
  if (latest.blockId !== blockId) {
    throw new Error("The latest Pi engineer run belongs to a different active block");
  }
  if (latest.phase === "running") {
    throw new Error("The active Pi engineer run is still running");
  }
  if (latest.status === "ready-for-architect-review") {
    throw new Error("The active Pi engineer block already awaits architect review and commit; resume would repeat completed work");
  }
  if (latest.status === "plan-conflict" && !hasFeedback) {
    throw new Error(
      "The previous run ended in plan-conflict; resume requires corrective --feedback, or the primary agent must accept and commit the block before starting new work",
    );
  }
}

export async function latestEngineerDisposition(
  facts: EngineerGitFacts,
  blockId: string,
): Promise<string | undefined> {
  const latest = await latestEngineerRun(facts);
  if (!latest) return undefined;
  if (latest.blockId !== blockId) throw new Error("The latest Pi engineer run belongs to a different active block");
  return latest.phase === "finished" ? latest.status : "running";
}

async function writeJsonAtomic(destination: string, value: object): Promise<void> {
  const temporary = `${destination}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
  await rename(temporary, destination);
}

export async function beginEngineerRun(
  facts: EngineerGitFacts,
  manifest: EngineerBlockManifest,
  mode: "new" | "resume",
): Promise<EngineerRunHandle> {
  const runId = randomUUID();
  const runtimeDirectory = engineerRuntimeDirectory(facts);
  const directory = path.join(runtimeDirectory, "runs", runId);
  const statePath = path.join(runtimeDirectory, "latest-run.json");
  const resultPath = path.join(directory, "result.json");
  const startedAt = new Date().toISOString();
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const handle = {
    runId,
    directory,
    statePath,
    resultPath,
    startedAt,
    mode,
    blockId: manifest.blockId,
    facts,
  } satisfies EngineerRunHandle;
  await writeJsonAtomic(statePath, {
    schemaVersion: 1,
    runId,
    worktreeId: facts.worktreeId,
    blockId: manifest.blockId,
    mode,
    pid: process.pid,
    phase: "running",
    status: "running",
    startedAt,
    updatedAt: startedAt,
    resultPath: null,
    exitCode: null,
  });
  return handle;
}

export async function finishEngineerRun(
  handle: EngineerRunHandle,
  result: EngineerPipelineResult,
): Promise<void> {
  await writeJsonAtomic(handle.resultPath, result);
  const relativeResult = path.relative(handle.facts.projectRoot, handle.resultPath);
  await writeJsonAtomic(handle.statePath, {
    schemaVersion: 1,
    runId: handle.runId,
    worktreeId: handle.facts.worktreeId,
    blockId: handle.blockId,
    mode: handle.mode,
    pid: process.pid,
    phase: "finished",
    status: result.status,
    startedAt: handle.startedAt,
    updatedAt: new Date().toISOString(),
    resultPath: relativeResult,
    exitCode: result.status === "ready-for-architect-review" ? 0 : 1,
  });
}

export async function failEngineerRun(
  handle: EngineerRunHandle,
  error: unknown,
): Promise<void> {
  const reason = error instanceof Error ? error.message : String(error);
  const result = { status: "failed", reason };
  await writeJsonAtomic(handle.resultPath, result);
  const relativeResult = path.relative(handle.facts.projectRoot, handle.resultPath);
  await writeJsonAtomic(handle.statePath, {
    schemaVersion: 1,
    runId: handle.runId,
    worktreeId: handle.facts.worktreeId,
    blockId: handle.blockId,
    mode: handle.mode,
    pid: process.pid,
    phase: "finished",
    status: "failed",
    startedAt: handle.startedAt,
    updatedAt: new Date().toISOString(),
    resultPath: relativeResult,
    exitCode: 1,
  });
}

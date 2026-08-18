import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

import type { EngineerBlockManifest } from "./contracts.js";
import type { EngineerGitFacts } from "./preflight.js";

interface ActiveEngineerBlock {
  schemaVersion: 1;
  worktreeId: string;
  manifest: EngineerBlockManifest;
  recordedAt: string;
}

export function engineerRuntimeDirectory(facts: EngineerGitFacts): string {
  return path.join(facts.projectRoot, ".agents/runtime/pi/engineer", facts.worktreeId);
}

export function engineerSessionDirectory(facts: EngineerGitFacts): string {
  return path.join(engineerRuntimeDirectory(facts), "sessions");
}

function comparableManifest(manifest: EngineerBlockManifest): string {
  return JSON.stringify({ ...manifest, sessionMode: "resume" });
}

export async function validateEngineerSessionIntent(
  facts: EngineerGitFacts,
  manifest: EngineerBlockManifest,
): Promise<void> {
  if (manifest.sessionMode === "new") return;
  const statePath = path.join(engineerRuntimeDirectory(facts), "active-block.json");
  let active: ActiveEngineerBlock;
  try {
    active = JSON.parse(await readFile(statePath, "utf8")) as ActiveEngineerBlock;
  } catch {
    throw new Error("Cannot resume: this worktree has no recorded Pi engineer block; start it with sessionMode new");
  }
  if (active.schemaVersion !== 1 || active.worktreeId !== facts.worktreeId) {
    throw new Error("Cannot resume: the recorded Pi engineer session belongs to a different or unsupported worktree state");
  }
  if (comparableManifest(active.manifest) !== comparableManifest(manifest)) {
    throw new Error("Cannot resume: the supplied block manifest differs from the active Pi engineer block; use sessionMode new for a new block");
  }
}

export async function recordActiveEngineerBlock(
  facts: EngineerGitFacts,
  manifest: EngineerBlockManifest,
): Promise<void> {
  const directory = engineerRuntimeDirectory(facts);
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const statePath = path.join(directory, "active-block.json");
  const temporary = path.join(directory, `active-block.${process.pid}.${Date.now()}.tmp`);
  const active: ActiveEngineerBlock = {
    schemaVersion: 1,
    worktreeId: facts.worktreeId,
    manifest: { ...manifest, sessionMode: "resume" },
    recordedAt: new Date().toISOString(),
  };
  await writeFile(temporary, `${JSON.stringify(active, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await rename(temporary, statePath);
}

export function newBlockCompactionInstructions(manifest: EngineerBlockManifest): string {
  return `Prepare this worktree's persistent engineer session for a new block. Preserve only durable context: the overall goal, invariant architectural decisions, externally accepted blocks and commits, current HEAD, open risks, and facts needed to understand the next block. Discard detailed logs, copied file bodies, rejected hypotheses, and implementation detail from accepted work. The next block is ${manifest.blockId}: ${manifest.goal}`;
}

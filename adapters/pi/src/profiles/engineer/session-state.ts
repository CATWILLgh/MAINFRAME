import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import { isInside } from "../../paths.js";
import { parseEngineerBlockManifest, type EngineerBlockManifest } from "./contracts.js";
import type { EngineerGitFacts } from "./preflight.js";

interface ActiveEngineerBlock {
  schemaVersion: 1;
  worktreeId: string;
  manifest: EngineerBlockManifest;
  ownedPaths: Array<{ path: string; sha256: string }>;
  reviewReady: boolean;
  recordedAt: string;
}

const execFileAsync = promisify(execFile);

export function engineerRuntimeDirectory(facts: EngineerGitFacts): string {
  return path.join(facts.projectRoot, ".agents/runtime/pi/engineer", facts.worktreeId);
}

export function engineerSessionDirectory(facts: EngineerGitFacts): string {
  return path.join(engineerRuntimeDirectory(facts), "sessions");
}

function comparableManifest(manifest: EngineerBlockManifest): string {
  return JSON.stringify({ ...manifest, sessionMode: "resume" });
}

async function readActiveEngineerBlock(facts: EngineerGitFacts): Promise<ActiveEngineerBlock> {
  const statePath = path.join(engineerRuntimeDirectory(facts), "active-block.json");
  let raw: unknown;
  try {
    raw = JSON.parse(await readFile(statePath, "utf8"));
  } catch {
    throw new Error("Cannot resume: this worktree has no recorded Pi engineer block; start it with --mode new");
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("Cannot resume: the recorded Pi engineer block is malformed");
  }
  const candidate = raw as Record<string, unknown>;
  const expectedFields = ["schemaVersion", "worktreeId", "manifest", "ownedPaths", "reviewReady", "recordedAt"];
  const requiredFields = expectedFields.filter((field) => field !== "reviewReady");
  if (Object.keys(candidate).some((key) => !expectedFields.includes(key)) || requiredFields.some((key) => !(key in candidate))) {
    throw new Error("Cannot resume: the recorded Pi engineer block has unsupported or missing fields");
  }
  if (candidate.schemaVersion !== 1 || candidate.worktreeId !== facts.worktreeId) {
    throw new Error("Cannot resume: the recorded Pi engineer session belongs to a different or unsupported worktree state");
  }
  if (!Array.isArray(candidate.ownedPaths)) {
    throw new Error("Cannot resume: the recorded Pi engineer block predates file-ownership tracking");
  }
  const ownedPaths = candidate.ownedPaths.map((rawOwned, index) => {
    if (!rawOwned || typeof rawOwned !== "object" || Array.isArray(rawOwned)) {
      throw new Error(`Cannot resume: ownedPaths[${index}] is malformed`);
    }
    const owned = rawOwned as Record<string, unknown>;
    if (Object.keys(owned).length !== 2 || !("path" in owned) || !("sha256" in owned)) {
      throw new Error(`Cannot resume: ownedPaths[${index}] has unsupported or missing fields`);
    }
    if (typeof owned.path !== "string" || !owned.path || path.isAbsolute(owned.path)) {
      throw new Error(`Cannot resume: ownedPaths[${index}].path is invalid`);
    }
    const absolute = path.resolve(facts.projectRoot, owned.path);
    if (!isInside(facts.projectRoot, absolute)) {
      throw new Error(`Cannot resume: ownedPaths[${index}].path leaves the project`);
    }
    if (typeof owned.sha256 !== "string" || !/^[0-9a-f]{64}$/i.test(owned.sha256)) {
      throw new Error(`Cannot resume: ownedPaths[${index}].sha256 is invalid`);
    }
    return { path: owned.path, sha256: owned.sha256 };
  });
  if (new Set(ownedPaths.map(({ path: ownedPath }) => ownedPath)).size !== ownedPaths.length) {
    throw new Error("Cannot resume: ownedPaths contains duplicates");
  }
  if (typeof candidate.recordedAt !== "string" || !candidate.recordedAt) {
    throw new Error("Cannot resume: the recorded Pi engineer timestamp is invalid");
  }
  if (candidate.reviewReady !== undefined && typeof candidate.reviewReady !== "boolean") {
    throw new Error("Cannot resume: the recorded Pi engineer review state is invalid");
  }
  const manifest = parseEngineerBlockManifest(candidate.manifest);
  if (manifest.sessionMode !== "resume") {
    throw new Error("Cannot resume: the recorded Pi engineer manifest is not resumable");
  }
  return {
    schemaVersion: 1,
    worktreeId: facts.worktreeId,
    manifest,
    ownedPaths,
    reviewReady: candidate.reviewReady === true,
    recordedAt: candidate.recordedAt,
  };
}

export async function loadActiveEngineerManifest(facts: EngineerGitFacts): Promise<EngineerBlockManifest> {
  return (await readActiveEngineerBlock(facts)).manifest;
}

export async function validateEngineerSessionIntent(
  facts: EngineerGitFacts,
  manifest: EngineerBlockManifest,
): Promise<string[]> {
  if (manifest.sessionMode === "new") return [];
  const active = await readActiveEngineerBlock(facts);
  if (comparableManifest(active.manifest) !== comparableManifest(manifest)) {
    throw new Error("Cannot resume: the supplied block manifest differs from the active Pi engineer block; use sessionMode new for a new block");
  }
  for (const owned of active.ownedPaths) {
    const content = await readFile(path.join(facts.projectRoot, owned.path));
    const current = createHash("sha256").update(content).digest("hex");
    if (current !== owned.sha256) {
      throw new Error(`Cannot resume: a previously Pi-owned file changed outside the recorded session: ${owned.path}`);
    }
  }
  return active.ownedPaths.map(({ path: ownedPath }) => ownedPath);
}

export async function recordActiveEngineerBlock(
  facts: EngineerGitFacts,
  manifest: EngineerBlockManifest,
  ownedPaths: string[] = [],
): Promise<void> {
  const directory = engineerRuntimeDirectory(facts);
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const statePath = path.join(directory, "active-block.json");
  const temporary = path.join(directory, `active-block.${process.pid}.${Date.now()}.tmp`);
  const active: ActiveEngineerBlock = {
    schemaVersion: 1,
    worktreeId: facts.worktreeId,
    manifest: { ...manifest, sessionMode: "resume" },
    ownedPaths: await Promise.all([...new Set(ownedPaths)].sort().map(async (ownedPath) => ({
      path: ownedPath,
      sha256: createHash("sha256").update(await readFile(path.join(facts.projectRoot, ownedPath))).digest("hex"),
    }))),
    reviewReady: false,
    recordedAt: new Date().toISOString(),
  };
  await writeFile(temporary, `${JSON.stringify(active, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await rename(temporary, statePath);
}

async function writeActiveEngineerBlock(facts: EngineerGitFacts, active: ActiveEngineerBlock): Promise<void> {
  const directory = engineerRuntimeDirectory(facts);
  const temporary = path.join(directory, `active-block.${process.pid}.${Date.now()}.tmp`);
  await writeFile(temporary, `${JSON.stringify(active, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await rename(temporary, path.join(directory, "active-block.json"));
}

async function verifyOwnedHashes(facts: EngineerGitFacts, active: ActiveEngineerBlock): Promise<void> {
  for (const owned of active.ownedPaths) {
    const current = createHash("sha256").update(await readFile(path.join(facts.projectRoot, owned.path))).digest("hex");
    if (current !== owned.sha256) throw new Error(`Pi-owned file changed after verification: ${owned.path}`);
  }
}

export async function markEngineerBlockReadyForArchitectReview(facts: EngineerGitFacts): Promise<void> {
  const active = await readActiveEngineerBlock(facts);
  if (active.ownedPaths.length === 0) throw new Error("Cannot mark an engineer block ready without owned changes");
  await verifyOwnedHashes(facts, active);
  await writeActiveEngineerBlock(facts, { ...active, reviewReady: true, recordedAt: new Date().toISOString() });
}

function conventionalCommitMessage(message: string): string {
  const trimmed = message.trim();
  if (!/^(feat|fix|refactor|perf|test|docs|build|ci|chore)(\([a-z0-9][a-z0-9._/-]*\))?!?: [^\n]+$/.test(trimmed)) {
    throw new Error("Commit message must use Conventional Commits: type(optional-scope): description");
  }
  return trimmed;
}

export async function commitAcceptedEngineerBlock(facts: EngineerGitFacts, message: string) {
  const active = await readActiveEngineerBlock(facts);
  if (!active.reviewReady) throw new Error("Cannot commit: the active block has not reached architect review");
  if (facts.startingHead.toLowerCase() !== active.manifest.expectedHead.toLowerCase()) {
    throw new Error(`Cannot commit: Git HEAD changed after the block started (expected ${active.manifest.expectedHead}, found ${facts.startingHead})`);
  }
  if (active.ownedPaths.length === 0) throw new Error("Cannot commit: the active block owns no changed paths");
  await verifyOwnedHashes(facts, active);
  const commitMessage = conventionalCommitMessage(message);
  const ownedPaths = active.ownedPaths.map(({ path: ownedPath }) => ownedPath);
  const directory = engineerRuntimeDirectory(facts);
  await mkdir(path.join(directory, "commits"), { recursive: true, mode: 0o700 });
  const temporaryIndex = path.join(directory, `commit-index.${process.pid}.${Date.now()}`);
  const gitEnvironment = { ...process.env, GIT_INDEX_FILE: temporaryIndex };
  try {
    await execFileAsync("git", ["-C", facts.projectRoot, "read-tree", "HEAD"], { env: gitEnvironment });
    await execFileAsync("git", ["-C", facts.projectRoot, "add", "--", ...ownedPaths], { env: gitEnvironment });
    const staged = (await execFileAsync("git", ["-C", facts.projectRoot, "diff", "--cached", "--name-only", "-z", "HEAD"], { env: gitEnvironment, encoding: "utf8" })).stdout.split("\0").filter(Boolean).sort();
    if (JSON.stringify(staged) !== JSON.stringify([...ownedPaths].sort())) throw new Error(`Cannot commit: isolated index paths differ from Pi ownership (${JSON.stringify(staged)})`);
    const headBeforeCommit = (await execFileAsync("git", ["-C", facts.projectRoot, "rev-parse", "HEAD"], { encoding: "utf8" })).stdout.trim();
    if (headBeforeCommit.toLowerCase() !== active.manifest.expectedHead.toLowerCase()) {
      throw new Error(`Cannot commit: Git HEAD changed while preparing the isolated commit (found ${headBeforeCommit})`);
    }
    await execFileAsync("git", ["-C", facts.projectRoot, "commit", "-m", commitMessage], { env: gitEnvironment, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 });
  } finally {
    await rm(temporaryIndex, { force: true });
  }
  const commit = (await execFileAsync("git", ["-C", facts.projectRoot, "rev-parse", "HEAD"], { encoding: "utf8" })).stdout.trim();
  const parent = (await execFileAsync("git", ["-C", facts.projectRoot, "rev-parse", `${commit}^`], { encoding: "utf8" })).stdout.trim();
  if (parent.toLowerCase() !== active.manifest.expectedHead.toLowerCase()) throw new Error("Committed block does not descend from its expected HEAD");
  const committedPaths = (await execFileAsync("git", ["-C", facts.projectRoot, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", commit], { encoding: "utf8" })).stdout.split("\0").filter(Boolean).sort();
  if (JSON.stringify(committedPaths) !== JSON.stringify([...ownedPaths].sort())) throw new Error(`Committed paths differ from Pi ownership: ${JSON.stringify(committedPaths)}`);
  await execFileAsync("git", ["-C", facts.projectRoot, "add", "--", ...ownedPaths]);
  const receipt = { schemaVersion: 1 as const, blockId: active.manifest.blockId, commit, message: commitMessage, paths: [...ownedPaths].sort() };
  await writeFile(path.join(directory, "commits", `${active.manifest.blockId}-${commit.slice(0, 12)}.json`), `${JSON.stringify(receipt, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await rm(path.join(directory, "active-block.json"));
  return receipt;
}

export function newBlockCompactionInstructions(manifest: EngineerBlockManifest): string {
  return `Prepare this worktree's persistent engineer session for a new block. Preserve only durable context: the overall goal, invariant architectural decisions, externally accepted blocks and commits, current HEAD, open risks, and facts needed to understand the next block. Discard detailed logs, copied file bodies, rejected hypotheses, and implementation detail from accepted work. The next block is ${manifest.blockId}: ${manifest.goal}`;
}

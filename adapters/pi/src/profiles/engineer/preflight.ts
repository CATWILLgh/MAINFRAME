import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, open, readFile, realpath, rm } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import { resolveProjectRoot } from "../../paths.js";
import { protectProjectRuntime } from "../../runtime-storage.js";
import type { EngineerBlockManifest } from "./contracts.js";

const execFileAsync = promisify(execFile);

export interface EngineerGitFacts {
  projectRoot: string;
  gitDirectory: string;
  worktreeId: string;
  startingHead: string;
  initialDirtyPaths: string[];
}

export interface EngineerWriterLock {
  lockPath: string;
  release(): Promise<void>;
}

async function git(projectRoot: string, args: string[]): Promise<string> {
  const result = await execFileAsync("git", ["-C", projectRoot, ...args], {
    encoding: "utf8",
    maxBuffer: 4 * 1024 * 1024,
  });
  return result.stdout;
}

function parsePorcelainPaths(output: string): string[] {
  const entries = output.split("\0");
  if (entries.at(-1) === "") entries.pop();
  const paths: string[] = [];
  for (let index = 0; index < entries.length; index += 1) {
    const entry = entries[index] ?? "";
    if (entry.length < 4 || entry[2] !== " ") throw new Error("Git returned an unsupported porcelain status entry");
    paths.push(entry.slice(3));
    if (/[RC]/.test(entry.slice(0, 2))) {
      const previousPath = entries[index + 1];
      if (!previousPath) throw new Error("Git returned an incomplete rename or copy status entry");
      paths.push(previousPath);
      index += 1;
    }
  }
  return [...new Set(paths)].sort();
}

export async function inspectEngineerGit(
  projectRoot: string,
  manifest: EngineerBlockManifest,
): Promise<EngineerGitFacts> {
  const facts = await inspectEngineerGitState(projectRoot);
  if (facts.startingHead.toLowerCase() !== manifest.expectedHead.toLowerCase()) {
    throw new Error(`Git HEAD changed before the run: expected ${manifest.expectedHead}, found ${facts.startingHead}`);
  }
  return facts;
}

export async function inspectEngineerGitState(projectRoot: string): Promise<EngineerGitFacts> {
  const root = await resolveProjectRoot(projectRoot);
  const topLevel = await realpath((await git(root, ["rev-parse", "--show-toplevel"])).trim());
  if (topLevel !== root) {
    throw new Error(`Pi engineer must run from the Git worktree root: ${topLevel}`);
  }
  const startingHead = (await git(root, ["rev-parse", "HEAD"])).trim();
  const gitDirectoryRaw = (await git(root, ["rev-parse", "--absolute-git-dir"])).trim();
  const gitDirectory = await realpath(gitDirectoryRaw);
  const worktreeId = createHash("sha256").update(`${root}\0${gitDirectory}`).digest("hex").slice(0, 20);
  const initialDirtyPaths = parsePorcelainPaths(await git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]));
  return { projectRoot: root, gitDirectory, worktreeId, startingHead, initialDirtyPaths };
}

export async function acquireEngineerWriterLock(
  facts: EngineerGitFacts,
  blockId: string,
): Promise<EngineerWriterLock> {
  await protectProjectRuntime(facts.projectRoot);
  const directory = path.join(facts.projectRoot, ".agents/runtime/pi/engineer", facts.worktreeId);
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const lockPath = path.join(directory, "writer.lock");
  let handle;
  try {
    handle = await open(lockPath, "wx", 0o600);
  } catch (error) {
    const existing = await readFile(lockPath, "utf8").catch(() => "unreadable lock owner");
    if ((error as NodeJS.ErrnoException).code === "EEXIST") {
      throw new Error(`This worktree already has a Pi engineer writer: ${existing.trim()}`);
    }
    throw error;
  }
  const owner = JSON.stringify({ pid: process.pid, blockId, acquiredAt: new Date().toISOString() });
  await handle.writeFile(`${owner}\n`);
  await handle.close();
  let released = false;
  return {
    lockPath,
    async release(): Promise<void> {
      if (released) return;
      released = true;
      await rm(lockPath, { force: true });
    },
  };
}

import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { protectProjectRuntime } from "../../runtime-storage.js";
import {
  parseEngineerCheckResult,
  type EngineerAllowedCheck,
  type EngineerBlockManifest,
  type EngineerCheckResult,
} from "./contracts.js";
import type { EngineerGitFacts } from "./preflight.js";

const INLINE_OUTPUT_LIMIT = 20_000;
const TERMINATION_GRACE_MS = 2_000;

function boundedOutput(output: string): { inline: string; truncated: boolean } {
  if (output.length <= INLINE_OUTPUT_LIMIT) return { inline: output, truncated: false };
  const half = Math.floor((INLINE_OUTPUT_LIMIT - 80) / 2);
  return {
    inline: `${output.slice(0, half)}\n… output truncated by MAINFRAME …\n${output.slice(-half)}`,
    truncated: true,
  };
}

function terminateProcessTree(pid: number | undefined, signal: NodeJS.Signals): void {
  if (!pid) return;
  try {
    if (process.platform === "win32") process.kill(pid, signal);
    else process.kill(-pid, signal);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ESRCH") throw error;
  }
}

async function retainFullOutput(facts: EngineerGitFacts, checkId: string, output: string): Promise<string> {
  await protectProjectRuntime(facts.projectRoot);
  const relative = path.posix.join(
    ".agents/runtime/pi/engineer",
    facts.worktreeId,
    "check-output",
    `${checkId}-${Date.now()}-${randomUUID()}.log`,
  );
  const absolute = path.join(facts.projectRoot, relative);
  await mkdir(path.dirname(absolute), { recursive: true, mode: 0o700 });
  await writeFile(absolute, output, { encoding: "utf8", mode: 0o600 });
  return relative;
}

export async function runEngineerCheck(
  facts: EngineerGitFacts,
  manifest: EngineerBlockManifest,
  checkId: string,
): Promise<EngineerCheckResult> {
  const check = manifest.allowedChecks.find(({ id }) => id === checkId);
  if (!check) throw new Error(`Unknown manifest-approved check: ${checkId}`);
  const started = Date.now();
  const chunks: string[] = [];
  let timedOut = false;
  let spawnError: Error | undefined;

  const exitCode = await new Promise<number | null>((resolve) => {
    const child = spawn(check.argv[0]!, check.argv.slice(1), {
      cwd: facts.projectRoot,
      env: process.env,
      shell: false,
      detached: process.platform !== "win32",
      stdio: ["ignore", "pipe", "pipe"],
    });
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => chunks.push(chunk));
    child.stderr.on("data", (chunk: string) => chunks.push(chunk));
    let forceTimer: NodeJS.Timeout | undefined;
    const timeout = setTimeout(() => {
      timedOut = true;
      terminateProcessTree(child.pid, "SIGTERM");
      forceTimer = setTimeout(() => terminateProcessTree(child.pid, "SIGKILL"), TERMINATION_GRACE_MS);
      forceTimer.unref();
    }, check.timeoutMs);
    timeout.unref();
    child.once("error", (error) => {
      spawnError = error;
    });
    child.once("close", (code) => {
      clearTimeout(timeout);
      if (forceTimer) clearTimeout(forceTimer);
      resolve(code);
    });
  });

  const fullOutput = chunks.join("");
  const bounded = boundedOutput(fullOutput);
  const output = bounded.truncated
    ? { ...bounded, retainedPath: await retainFullOutput(facts, check.id, fullOutput) }
    : bounded;
  const status: EngineerCheckResult["status"] = timedOut
    ? "timed-out"
    : spawnError
      ? "spawn-error"
      : exitCode === 0
        ? "passed"
        : "failed";
  return parseEngineerCheckResult({
    schemaVersion: 1,
    checkId: check.id,
    argv: check.argv,
    status,
    exitCode: timedOut || spawnError ? null : exitCode,
    durationMs: Date.now() - started,
    output,
  }, manifest);
}

export async function runEngineerChecks(
  facts: EngineerGitFacts,
  manifest: EngineerBlockManifest,
): Promise<EngineerCheckResult[]> {
  const results: EngineerCheckResult[] = [];
  for (const check of manifest.allowedChecks) results.push(await runEngineerCheck(facts, manifest, check.id));
  return results;
}

export function approvedCheck(manifest: EngineerBlockManifest, checkId: string): EngineerAllowedCheck | undefined {
  return manifest.allowedChecks.find(({ id }) => id === checkId);
}

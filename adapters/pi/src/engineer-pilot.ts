import { readFile, realpath } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ModelRuntime } from "@earendil-works/pi-coding-agent";

import { loadEngineerProfile } from "./config.js";
import { isInside, resolveProjectRoot } from "./paths.js";
import { verifyPiCli } from "./preflight.js";
import { parseEngineerBlockManifest } from "./profiles/engineer/contracts.js";
import { resolveModel } from "./profiles/business-analyst/runtime.js";
import { runEngineerPipeline } from "./profiles/engineer/runtime.js";

const ADAPTER_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name);
  return index < 0 ? undefined : process.argv[index + 1];
}

function positiveIntegerArgument(name: string): number | undefined {
  const raw = argument(name);
  if (raw === undefined) return undefined;
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error(`${name} must be a positive integer`);
  return parsed;
}

async function main(): Promise<void> {
  await verifyPiCli();
  const projectRoot = await resolveProjectRoot(argument("--project") ?? process.cwd());
  const mode = argument("--mode");
  if (mode !== "new" && mode !== "resume") throw new Error("--mode must be exactly new or resume");
  const manifestArgument = argument("--manifest");
  if (!manifestArgument) throw new Error("--manifest is required");
  const manifestPath = await realpath(path.resolve(projectRoot, manifestArgument));
  if (!isInside(projectRoot, manifestPath)) throw new Error("Engineer manifest must be inside the current project");
  const raw = JSON.parse(await readFile(manifestPath, "utf8")) as Record<string, unknown>;
  if (raw.sessionMode !== undefined && raw.sessionMode !== mode) {
    throw new Error("Manifest sessionMode conflicts with the explicit --mode argument");
  }
  const manifest = parseEngineerBlockManifest({ ...raw, sessionMode: mode });
  const configPath = path.resolve(argument("--config") ?? path.join(ADAPTER_ROOT, "config", "profiles.local.json"));
  const profile = await loadEngineerProfile(configPath, argument("--profile") ?? "engineer-pilot");
  const modelRuntime = await ModelRuntime.create({ signal: AbortSignal.timeout(15_000) });
  const [executorModel, verifierModel] = await Promise.all([
    resolveModel(modelRuntime, profile.executor),
    resolveModel(modelRuntime, profile.verifier),
  ]);
  const timeoutMs = positiveIntegerArgument("--timeout-ms");
  const verifierTimeoutMs = positiveIntegerArgument("--verifier-timeout-ms");
  const maxTurns = positiveIntegerArgument("--max-turns");
  const result = await runEngineerPipeline({
    projectRoot,
    manifest,
    modelRuntime,
    executorModel,
    executorThinking: profile.executor.thinking,
    verifierModel,
    verifierThinking: profile.verifier.thinking,
    ...(timeoutMs === undefined ? {} : { executorTimeoutMs: timeoutMs }),
    ...(verifierTimeoutMs === undefined ? {} : { verifierTimeoutMs }),
    ...(maxTurns === undefined ? {} : { maxTurns }),
  });
  console.log(JSON.stringify(result, null, 2));
  if (result.status !== "ready-for-architect-review") process.exitCode = 1;
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

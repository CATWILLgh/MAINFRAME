import { readFile, realpath } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ModelRuntime } from "@earendil-works/pi-coding-agent";

import { loadEngineerProfile } from "./config.js";
import { isInside, resolveProjectRoot } from "./paths.js";
import { verifyPiCli } from "./preflight.js";
import { compileEngineerBlockManifest, parseEngineerBlockRequest } from "./profiles/engineer/block-request.js";
import { parseEngineerBlockManifest, parseEngineerCorrectionPacket } from "./profiles/engineer/contracts.js";
import { inspectEngineerGitState } from "./profiles/engineer/preflight.js";
import { resolveModel } from "./profiles/business-analyst/runtime.js";
import { runEngineerPipeline } from "./profiles/engineer/runtime.js";
import {
  archiveActiveEngineerBlockForNew,
  loadActiveEngineerManifest,
} from "./profiles/engineer/session-state.js";
import {
  beginEngineerRun,
  failEngineerRun,
  finishEngineerRun,
  type EngineerRunHandle,
  validateEngineerResumeDisposition,
} from "./profiles/engineer/run-state.js";
import { writeEngineerTelemetry } from "./telemetry.js";
import { createWebRouter } from "./web-tools.js";

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
  const started = Date.now();
  let run: EngineerRunHandle | undefined;
  try {
    await verifyPiCli();
    const projectRoot = await resolveProjectRoot(argument("--project") ?? process.cwd());
    const mode = argument("--mode");
    if (mode !== "new" && mode !== "resume") throw new Error("--mode must be exactly new or resume");
    const requestArgument = argument("--request");
    if (mode === "new" && !requestArgument) throw new Error("--request is required with --mode new");
    if (mode === "resume" && requestArgument) throw new Error("--request is not accepted with --mode resume");
    const gitFacts = await inspectEngineerGitState(projectRoot);
    const runMode = mode === "new" ? "new" : "resume";
    let manifest;
    if (runMode === "new") {
      const requestPath = await realpath(path.resolve(projectRoot, requestArgument!));
      if (!isInside(projectRoot, requestPath)) throw new Error("Engineer block request must be inside the current project");
      const request = parseEngineerBlockRequest(JSON.parse(await readFile(requestPath, "utf8")));
      manifest = compileEngineerBlockManifest(request, gitFacts.startingHead, runMode);
    } else {
      const active = await loadActiveEngineerManifest(gitFacts);
      manifest = parseEngineerBlockManifest({ ...active, sessionMode: runMode });
    }
    const feedbackArgument = argument("--feedback");
    let initialCorrection;
    if (feedbackArgument) {
      if (runMode !== "resume") throw new Error("--feedback is valid only with --mode resume");
      const feedbackPath = await realpath(path.resolve(projectRoot, feedbackArgument));
      if (!isInside(projectRoot, feedbackPath)) throw new Error("Engineer feedback must be inside the current project");
      initialCorrection = parseEngineerCorrectionPacket(JSON.parse(await readFile(feedbackPath, "utf8")), manifest);
    }
    if (runMode === "resume") {
      await validateEngineerResumeDisposition(gitFacts, manifest.blockId, initialCorrection !== undefined);
    }
    const configPath = path.resolve(argument("--config") ?? path.join(ADAPTER_ROOT, "config", "profiles.local.json"));
    const profile = await loadEngineerProfile(configPath, argument("--profile") ?? "engineer-pilot");
    const modelRuntime = await ModelRuntime.create({ signal: AbortSignal.timeout(15_000) });
    const [executorModel, verifierModel] = await Promise.all([
      resolveModel(modelRuntime, profile.executor),
      resolveModel(modelRuntime, profile.verifier),
    ]);
    const webRouter = await createWebRouter(modelRuntime, "zai");
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
      webRouter,
      onStarted: async (facts) => {
        if (runMode === "new") await archiveActiveEngineerBlockForNew(facts);
        run = await beginEngineerRun(facts, manifest, runMode);
      },
      ...(timeoutMs === undefined ? {} : { executorTimeoutMs: timeoutMs }),
      ...(verifierTimeoutMs === undefined ? {} : { verifierTimeoutMs }),
      ...(maxTurns === undefined ? {} : { maxTurns }),
      ...(initialCorrection === undefined ? {} : { initialCorrection }),
    });
    const telemetryStatus = writeEngineerTelemetry({
      facts: gitFacts,
      mode: runMode,
      profile,
      result,
      durationMs: Date.now() - started,
    });
    if (telemetryStatus === "error") {
      console.error(
        "MAINFRAME Pi dev telemetry is unavailable; the engineering result below remains valid.",
      );
    }
    if (run) await finishEngineerRun(run, result);
    console.log(JSON.stringify(result, null, 2));
    if (result.status !== "ready-for-architect-review") process.exitCode = 1;
  } catch (error) {
    if (run) await failEngineerRun(run, error).catch(() => undefined);
    throw error;
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  createAgentSession,
  defineTool,
  ModelRuntime,
  SessionManager,
  SettingsManager,
  type AgentSession,
} from "@earendil-works/pi-coding-agent";
import type { Model } from "@earendil-works/pi-ai/compat";
import { Type } from "typebox";

import type { CollectorSelection, ModelSelection } from "../../model-types.js";
import { buildProjectMap } from "../../project-map.js";
import { createProjectTools, readProjectFile } from "../../project-tools.js";
import { stageExplicitInputPackage } from "../../external-input.js";
import { protectProjectRuntime } from "../../runtime-storage.js";
import {
  addUsage,
  boundedPrompt,
  collectUsage,
  createIsolatedLoader,
  emptyUsage,
  isBenignCompactionNoop,
  type UsageSummary,
} from "../../session-utils.js";
import { CollectorRunError, runCollector, type CollectorResult } from "./collector-runner.js";
import { segmentEntryArtifact, writeJsonLines, type AtomicClaim } from "./facts.js";
import {
  BUSINESS_ANALYST_SYSTEM_PROMPT,
  COMPACTION_INSTRUCTIONS,
  repairPrompt,
  synthesisPrompt,
} from "./prompts.js";
import { saveNextReview } from "./review-store.js";
import { validateReview, type Readiness } from "./review-validator.js";
import { runVerifier } from "./verifier-runner.js";

export { createIsolatedLoader, isBenignCompactionNoop } from "../../session-utils.js";
export type { UsageSummary } from "../../session-utils.js";

export interface RunOptions {
  projectRoot: string;
  initiative: string;
  statements?: string[];
  entryPaths?: string[];
  externalInputPaths?: string[];
  freshSession?: boolean;
  collectors: CollectorSelection[];
  verifier: ModelSelection;
  synthesizer: ModelSelection;
  timeoutMs?: number;
  maxTurns?: number;
}

export interface RunResult {
  run_status: "complete" | "incomplete" | "blocked";
  readiness?: Readiness;
  review_path?: string;
  compaction_status?: "compacted" | "not-needed";
  error?: string;
  duration_ms: number;
  collectors: CollectorSelection[];
  verifier: ModelSelection;
  synthesizer: ModelSelection;
  claim_count?: number;
  verified_claim_count?: number;
  collector_failures?: Array<{ role: CollectorSelection["role"]; error: string }>;
  usage: UsageSummary;
  stage_usage: {
    collectors: Array<{ role: CollectorSelection["role"]; usage: UsageSummary }>;
    verifier: UsageSummary;
    synthesizer: UsageSummary;
  };
}

export async function resolveModel(runtime: ModelRuntime, selection: ModelSelection): Promise<Model<any>> {
  const available = await runtime.getAvailable(selection.provider, { signal: AbortSignal.timeout(15_000) });
  const selected = available.find((model) => model.id === selection.model);
  if (!selected) {
    throw new Error(`Model is unavailable through configured Pi authentication: ${selection.provider}/${selection.model}`);
  }
  return applyVerifiedThinkingContract(selected, selection);
}

export function applyVerifiedThinkingContract(model: Model<any>, selection: ModelSelection): Model<any> {
  if (selection.provider !== "zai" || selection.model !== "glm-5.3") return model;
  return {
    ...model,
    compat: { ...model.compat, supportsReasoningEffort: true },
    thinkingLevelMap: {
      ...model.thinkingLevelMap,
      off: null,
      minimal: null,
      low: "low",
      medium: null,
      high: "high",
      xhigh: null,
      max: "max",
    },
  };
}

export async function listAvailableModels(): Promise<Array<{ provider: string; id: string; name: string }>> {
  const runtime = await ModelRuntime.create({ signal: AbortSignal.timeout(15_000) });
  const models = await runtime.getAvailable(undefined, { signal: AbortSignal.timeout(15_000) });
  return models.map((model) => ({ provider: model.provider, id: model.id, name: model.name }));
}

export async function runBusinessAnalysis(options: RunOptions): Promise<RunResult> {
  const started = Date.now();
  const usage = emptyUsage();
  const collectorUsage: Array<{ role: CollectorSelection["role"]; usage: UsageSummary }> = [];
  let verifierUsage = emptyUsage();
  let synthesizerUsage = emptyUsage();
  const timeoutMs = options.timeoutMs ?? 900_000;
  const maxTurns = options.maxTurns ?? 96;
  let synthesizerSession: AgentSession | undefined;
  let synthesizerUsageCollected = false;
  let claimCount: number | undefined;
  let verifiedClaimCount: number | undefined;
  const collectorFailures: Array<{ role: CollectorSelection["role"]; error: string }> = [];

  try {
    if (options.collectors.length !== 3) throw new Error("Business-analysis profile requires exactly three collectors");
    if (new Set(options.collectors.map(({ role }) => role)).size !== options.collectors.length) {
      throw new Error("Collector roles must be unique");
    }
    const projectRoot = path.resolve(options.projectRoot);
    await protectProjectRuntime(projectRoot);
    const entryPath = await stageExplicitInputPackage(projectRoot, {
      statements: options.statements ?? [],
      projectPaths: options.entryPaths ?? [],
      externalPaths: options.externalInputPaths ?? [],
    });
    const allowedRuntimeInput = entryPath;
    await readProjectFile(projectRoot, entryPath, 1, undefined, allowedRuntimeInput);

    const runtimeDirectory = path.join(projectRoot, ".agents/runtime/pi");
    const runDirectory = path.join(runtimeDirectory, "runs", `${Date.now()}-${process.pid}`);
    const sessionDirectory = path.join(runtimeDirectory, "sessions/business-analyst");
    await mkdir(runDirectory, { recursive: true });
    await mkdir(sessionDirectory, { recursive: true });
    const projectMap = await buildProjectMap(projectRoot, options.initiative, entryPath);
    await writeFile(path.join(runtimeDirectory, "project-map.json"), `${JSON.stringify(projectMap, null, 2)}\n`, { mode: 0o600 });
    const segments = await segmentEntryArtifact(projectRoot, entryPath, allowedRuntimeInput);
    await writeFile(path.join(runDirectory, "segments.json"), `${JSON.stringify(segments, null, 2)}\n`, { mode: 0o600 });

    const modelRuntime = await ModelRuntime.create({ signal: AbortSignal.timeout(15_000) });
    const [collectorModels, verifierModel, synthesizerModel] = await Promise.all([
      Promise.all(options.collectors.map(({ model }) => resolveModel(modelRuntime, model))),
      resolveModel(modelRuntime, options.verifier),
      resolveModel(modelRuntime, options.synthesizer),
    ]);

    const collectorMaxTurns = Math.min(maxTurns, 48);
    const settled = await Promise.allSettled(options.collectors.map((collector, index) =>
      runCollector(
        projectRoot,
        options.initiative,
        entryPath,
        collector,
        segments,
        modelRuntime,
        collectorModels[index]!,
        timeoutMs,
        collectorMaxTurns,
        allowedRuntimeInput,
      ),
    ));
    const results: CollectorResult[] = [];
    const errors: string[] = [];
    for (const [index, result] of settled.entries()) {
      if (result.status === "fulfilled") {
        results.push(result.value);
        collectorUsage.push({ role: result.value.role, usage: result.value.usage });
        addUsage(usage, result.value.usage);
        await writeJsonLines(path.join(runDirectory, `claims-${result.value.role}.jsonl`), result.value.claims);
      } else {
        if (result.reason instanceof CollectorRunError) {
          collectorUsage.push({ role: options.collectors[index]!.role, usage: result.reason.usage });
          addUsage(usage, result.reason.usage);
        }
        const failure = { role: options.collectors[index]!.role, error: String(result.reason) };
        collectorFailures.push(failure);
        errors.push(`${failure.role}: ${failure.error}`);
      }
    }
    if (results.length < 2) {
      throw new Error(`Collector stage produced fewer than two independent results: ${errors.join("; ")}`);
    }
    const candidates: AtomicClaim[] = results.flatMap(({ claims }) => claims);
    claimCount = candidates.length;
    const verification = await runVerifier(projectRoot, options.initiative, candidates, modelRuntime, verifierModel, options.verifier.thinking, timeoutMs, maxTurns, allowedRuntimeInput);
    verifierUsage = verification.usage;
    addUsage(usage, verifierUsage);
    verifiedClaimCount = verification.claims.filter(({ verdict }) => verdict === "verified" || verdict === "partially-verified").length;
    await writeJsonLines(path.join(runDirectory, "verified-claims.jsonl"), verification.claims);

    let draft: string | undefined;
    let savedPath: string | undefined;
    let phase: "draft" | "final" = "draft";
    const submitDraft = defineTool({
      name: "submit_draft",
      label: "Submit analysis draft",
      description: "Submit the complete Markdown review for deterministic validation.",
      parameters: Type.Object({ markdown: Type.String({ minLength: 1 }) }),
      execute: async (_id, params) => {
        if (phase !== "draft" || draft) return { content: [{ type: "text", text: "Draft submission is closed." }], details: {}, terminate: true };
        draft = params.markdown;
        return { content: [{ type: "text", text: "Draft received." }], details: {}, terminate: true };
      },
    });
    const saveReview = defineTool({
      name: "save_review",
      label: "Save validated review",
      description: "Validate and atomically create the next review file.",
      parameters: Type.Object({ markdown: Type.String({ minLength: 1 }) }),
      execute: async (_id, params) => {
        if (phase !== "final") return { content: [{ type: "text", text: "Saving is unavailable before validation." }], details: {} };
        const validation = await validateReview(projectRoot, params.markdown);
        if (validation.errors.length) return { content: [{ type: "text", text: `Review rejected:\n${validation.errors.map((error) => `- ${error}`).join("\n")}` }], details: {} };
        savedPath = (await saveNextReview(projectRoot, options.initiative, params.markdown)).relativePath;
        return { content: [{ type: "text", text: `Review saved: ${savedPath}` }], details: {}, terminate: true };
      },
    });
    const settings = SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: true, maxRetries: 2 } });
    const loader = await createIsolatedLoader(projectRoot, BUSINESS_ANALYST_SYSTEM_PROMPT, settings);
    synthesizerSession = (await createAgentSession({
      cwd: projectRoot,
      modelRuntime,
      model: synthesizerModel,
      thinkingLevel: options.synthesizer.thinking,
      tools: ["project_read", "project_find", "project_grep", "project_list", "submit_draft", "save_review"],
      customTools: [...createProjectTools(projectRoot, allowedRuntimeInput), submitDraft, saveReview],
      resourceLoader: loader,
      sessionManager: options.freshSession ? SessionManager.create(projectRoot, sessionDirectory) : SessionManager.continueRecent(projectRoot, sessionDirectory),
      settingsManager: settings,
    })).session;
    await boundedPrompt(synthesizerSession, synthesisPrompt(options.initiative, entryPath, candidates, verification.claims), timeoutMs, maxTurns, () => draft !== undefined, "submit_draft");
    if (!draft) throw new Error("Synthesizer ended without a draft");
    phase = "final";
    await boundedPrompt(synthesizerSession, repairPrompt((await validateReview(projectRoot, draft)).errors), timeoutMs, maxTurns, () => savedPath !== undefined, "save_review");
    if (!savedPath) throw new Error("Synthesizer ended without saving a validated review");
    const finalMarkdown = await readFile(path.join(projectRoot, savedPath), "utf8");
    const finalValidation = await validateReview(projectRoot, finalMarkdown);
    if (finalValidation.errors.length || !finalValidation.readiness) throw new Error(`Saved review failed validation: ${finalValidation.errors.join("; ")}`);

    let compactionStatus: "compacted" | "not-needed" = "compacted";
    try { await synthesizerSession.compact(COMPACTION_INSTRUCTIONS); }
    catch (error) { if (!isBenignCompactionNoop(error)) throw error; compactionStatus = "not-needed"; }
    synthesizerUsage = collectUsage(synthesizerSession);
    synthesizerUsageCollected = true;
    addUsage(usage, synthesizerUsage);
    return {
      run_status: collectorFailures.length ? "incomplete" : "complete",
      readiness: finalValidation.readiness,
      review_path: savedPath,
      compaction_status: compactionStatus, duration_ms: Date.now() - started,
      collectors: options.collectors, verifier: options.verifier, synthesizer: options.synthesizer,
      ...(claimCount === undefined ? {} : { claim_count: claimCount }),
      ...(verifiedClaimCount === undefined ? {} : { verified_claim_count: verifiedClaimCount }),
      ...(collectorFailures.length ? { collector_failures: collectorFailures } : {}),
      usage,
      stage_usage: { collectors: collectorUsage, verifier: verifierUsage, synthesizer: synthesizerUsage },
    };
  } catch (error) {
    if (synthesizerSession && !synthesizerUsageCollected) {
      synthesizerUsage = collectUsage(synthesizerSession);
      addUsage(usage, synthesizerUsage);
    }
    return {
      run_status: "blocked", error: error instanceof Error ? error.message : String(error),
      duration_ms: Date.now() - started, collectors: options.collectors,
      verifier: options.verifier, synthesizer: options.synthesizer,
      ...(claimCount === undefined ? {} : { claim_count: claimCount }),
      ...(verifiedClaimCount === undefined ? {} : { verified_claim_count: verifiedClaimCount }),
      ...(collectorFailures.length ? { collector_failures: collectorFailures } : {}),
      usage,
      stage_usage: { collectors: collectorUsage, verifier: verifierUsage, synthesizer: synthesizerUsage },
    };
  } finally {
    synthesizerSession?.dispose();
  }
}

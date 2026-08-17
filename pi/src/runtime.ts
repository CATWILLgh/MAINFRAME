import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  createAgentSession,
  defineTool,
  ModelRuntime,
  SessionManager,
  SettingsManager,
  type AgentSession,
} from "@earendil-works/pi-coding-agent";
import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Model } from "@earendil-works/pi-ai/compat";
import { Type } from "typebox";

import {
  BUSINESS_ANALYST_SYSTEM_PROMPT,
  COMPACTION_INSTRUCTIONS,
  initialPrompt,
  repairPrompt,
} from "./prompts.js";
import { buildProjectMap } from "./project-map.js";
import { createProjectTools, readProjectFile } from "./project-tools.js";
import { stageExternalInput } from "./external-input.js";
import { runCritic } from "./critic-runner.js";
import { saveNextReview } from "./review-store.js";
import { validateReview, type Readiness } from "./review-validator.js";
import { runScout, type ScoutResult } from "./scout-runner.js";
import {
  addUsage,
  boundedPrompt,
  collectUsage,
  createIsolatedLoader,
  emptyUsage,
  isBenignCompactionNoop,
  type UsageSummary,
} from "./session-utils.js";

export { createIsolatedLoader, isBenignCompactionNoop } from "./session-utils.js";
export type { UsageSummary } from "./session-utils.js";

export interface ModelSelection {
  provider: string;
  model: string;
  thinking: ThinkingLevel;
}

export type ScoutRole = "independent-a" | "independent-b";

export interface ScoutSelection {
  role: ScoutRole;
  model: ModelSelection;
}

export interface RunOptions {
  projectRoot: string;
  initiative: string;
  entryPath?: string;
  externalInputPath?: string;
  freshSession?: boolean;
  scouts: ScoutSelection[];
  critic: ModelSelection;
  consolidator: ModelSelection;
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
  scouts: ScoutSelection[];
  critic: ModelSelection;
  consolidator: ModelSelection;
  usage: UsageSummary;
  stage_usage: {
    scouts: Array<{ role: ScoutRole; usage: UsageSummary }>;
    critic: UsageSummary;
    consolidator: UsageSummary;
  };
}

async function resolveModel(runtime: ModelRuntime, selection: ModelSelection): Promise<Model<any>> {
  const available = await runtime.getAvailable(selection.provider, { signal: AbortSignal.timeout(15_000) });
  const selected = available.find((model) => model.id === selection.model);
  if (!selected) {
    throw new Error(
      `Model is not available through configured Pi authentication: ${selection.provider}/${selection.model}`,
    );
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
  const scoutStageUsage: Array<{ role: ScoutRole; usage: UsageSummary }> = [];
  let criticUsage = emptyUsage();
  let consolidatorUsage = emptyUsage();
  const timeoutMs = options.timeoutMs ?? 600_000;
  const maxTurns = options.maxTurns ?? 64;
  let consolidatorSession: AgentSession | undefined;
  let consolidatorUsageCollected = false;

  try {
    if (options.scouts.length === 0) throw new Error("At least one scout is required");
    if (new Set(options.scouts.map((scout) => scout.role)).size !== options.scouts.length) {
      throw new Error("Scout roles must be unique");
    }

    const projectRoot = path.resolve(options.projectRoot);
    if (options.entryPath && options.externalInputPath) {
      throw new Error("Use either entryPath or externalInputPath, not both");
    }
    const entryPath = options.externalInputPath
      ? await stageExternalInput(projectRoot, options.externalInputPath)
      : options.entryPath ?? `docs/initiatives/${options.initiative}/requirements.md`;
    const allowedRuntimeInput = options.externalInputPath ? entryPath : undefined;
    await readProjectFile(projectRoot, entryPath, 1, undefined, allowedRuntimeInput);
    const runtimeDirectory = path.join(projectRoot, ".agents/runtime/pi");
    const sessionDirectory = path.join(runtimeDirectory, "sessions/business-analyst");
    await mkdir(sessionDirectory, { recursive: true });
    const projectMap = await buildProjectMap(projectRoot, options.initiative, entryPath);
    await writeFile(path.join(runtimeDirectory, "project-map.json"), `${JSON.stringify(projectMap, null, 2)}\n`);

    const modelRuntime = await ModelRuntime.create({ signal: AbortSignal.timeout(15_000) });
    const [scoutModels, criticModel, consolidatorModel] = await Promise.all([
      Promise.all(options.scouts.map((scout) => resolveModel(modelRuntime, scout.model))),
      resolveModel(modelRuntime, options.critic),
      resolveModel(modelRuntime, options.consolidator),
    ]);

    const settledScouts = await Promise.allSettled(
      options.scouts.map((scout, index) =>
        runScout(
          projectRoot,
          options.initiative,
          entryPath,
          scout,
          modelRuntime,
          scoutModels[index]!,
          timeoutMs,
          maxTurns,
        ),
      ),
    );
    const scoutResults: ScoutResult[] = [];
    const scoutErrors: string[] = [];
    for (const [index, result] of settledScouts.entries()) {
      if (result.status === "fulfilled") {
        scoutResults.push(result.value);
        scoutStageUsage.push({ role: result.value.role, usage: result.value.usage });
        addUsage(usage, result.value.usage);
      } else {
        scoutErrors.push(`${options.scouts[index]!.role}: ${String(result.reason)}`);
      }
    }
    if (scoutErrors.length) throw new Error(`Scout stage failed: ${scoutErrors.join("; ")}`);

    let draft: string | undefined;
    let savedPath: string | undefined;
    let phase: "draft" | "final" = "draft";
    const submitDraft = defineTool({
      name: "submit_draft",
      label: "Submit consolidated analysis draft",
      description: "Submit the verified complete Markdown report for deterministic validation.",
      parameters: Type.Object({ markdown: Type.String({ minLength: 1 }) }),
      execute: async (_id, params) => {
        if (phase !== "draft" || draft) {
          return { content: [{ type: "text", text: "Draft submission is closed." }], details: {}, terminate: true };
        }
        draft = params.markdown;
        return {
          content: [{ type: "text", text: "Draft received for deterministic validation." }],
          details: {},
          terminate: true,
        };
      },
    });
    const saveReview = defineTool({
      name: "save_review",
      label: "Save validated review",
      description: "Validate and atomically create the next review file inside the assigned initiative.",
      parameters: Type.Object({ markdown: Type.String({ minLength: 1 }) }),
      execute: async (_id, params) => {
        if (phase !== "final") {
          return { content: [{ type: "text", text: "Saving is unavailable before validation." }], details: {} };
        }
        const validation = await validateReview(projectRoot, params.markdown);
        if (validation.errors.length) {
          return {
            content: [{ type: "text", text: `Review rejected:\n${validation.errors.map((error) => `- ${error}`).join("\n")}` }],
            details: {},
          };
        }
        const saved = await saveNextReview(projectRoot, options.initiative, params.markdown);
        savedPath = saved.relativePath;
        return { content: [{ type: "text", text: `Review saved: ${saved.relativePath}` }], details: {}, terminate: true };
      },
    });

    const settings = SettingsManager.inMemory({
      compaction: { enabled: false },
      retry: { enabled: true, maxRetries: 2 },
    });
    const loader = await createIsolatedLoader(projectRoot, BUSINESS_ANALYST_SYSTEM_PROMPT, settings);
    const created = await createAgentSession({
      cwd: projectRoot,
      modelRuntime,
      model: consolidatorModel,
      thinkingLevel: options.consolidator.thinking,
      tools: ["project_read", "project_find", "project_grep", "project_list", "submit_draft", "save_review"],
      customTools: [...createProjectTools(projectRoot, allowedRuntimeInput), submitDraft, saveReview],
      resourceLoader: loader,
      sessionManager: options.freshSession
        ? SessionManager.create(projectRoot, sessionDirectory)
        : SessionManager.continueRecent(projectRoot, sessionDirectory),
      settingsManager: settings,
    });
    consolidatorSession = created.session;
    await boundedPrompt(
      consolidatorSession,
      initialPrompt(
        options.initiative,
        entryPath,
        scoutResults.map(({ role, observations }) => ({ role, observations })),
      ),
      timeoutMs,
      maxTurns,
      () => draft !== undefined,
      "submit_draft",
    );
    if (!draft) throw new Error("Consolidator ended without submitting a draft");

    const deterministic = await validateReview(projectRoot, draft);
    const critic = await runCritic(
      projectRoot,
      options.initiative,
      draft,
      modelRuntime,
      criticModel,
      options.critic.thinking,
      timeoutMs,
      maxTurns,
      allowedRuntimeInput,
    );
    criticUsage = critic.usage;
    addUsage(usage, criticUsage);
    phase = "final";
    await boundedPrompt(
      consolidatorSession,
      repairPrompt(deterministic.errors, critic.critique),
      timeoutMs,
      maxTurns,
      () => savedPath !== undefined,
      "save_review",
    );
    if (!savedPath) throw new Error("Consolidator ended without saving a validated review");
    const confirmedSavedPath: string = savedPath;

    const finalMarkdown = await import("node:fs/promises").then(({ readFile }) =>
      readFile(path.join(projectRoot, confirmedSavedPath), "utf8"),
    );
    const finalValidation = await validateReview(projectRoot, finalMarkdown);
    if (finalValidation.errors.length || !finalValidation.readiness) {
      throw new Error(`Saved review failed final validation: ${finalValidation.errors.join("; ")}`);
    }

    let compactionStatus: "compacted" | "not-needed" = "compacted";
    try {
      await consolidatorSession.compact(COMPACTION_INSTRUCTIONS);
    } catch (error) {
      if (!isBenignCompactionNoop(error)) throw error;
      compactionStatus = "not-needed";
    }
    consolidatorUsage = collectUsage(consolidatorSession);
    consolidatorUsageCollected = true;
    addUsage(usage, consolidatorUsage);
    return {
      run_status: "complete",
      readiness: finalValidation.readiness,
      review_path: confirmedSavedPath,
      compaction_status: compactionStatus,
      duration_ms: Date.now() - started,
      scouts: options.scouts,
      critic: options.critic,
      consolidator: options.consolidator,
      usage,
      stage_usage: { scouts: scoutStageUsage, critic: criticUsage, consolidator: consolidatorUsage },
    };
  } catch (error) {
    if (consolidatorSession && !consolidatorUsageCollected) {
      consolidatorUsage = collectUsage(consolidatorSession);
      addUsage(usage, consolidatorUsage);
    }
    return {
      run_status: "blocked",
      error: error instanceof Error ? error.message : String(error),
      duration_ms: Date.now() - started,
      scouts: options.scouts,
      critic: options.critic,
      consolidator: options.consolidator,
      usage,
      stage_usage: { scouts: scoutStageUsage, critic: criticUsage, consolidator: consolidatorUsage },
    };
  } finally {
    consolidatorSession?.dispose();
  }
}

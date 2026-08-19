import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";

import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Model } from "@earendil-works/pi-ai/compat";
import type { ModelRuntime } from "@earendil-works/pi-coding-agent";

import {
  addUsage,
  emptyUsage,
  type SessionMetricsSummary,
  type UsageSummary,
} from "../../session-utils.js";
import { runEngineerChecks } from "./check-runner.js";
import type {
  EngineerBlockManifest,
  EngineerCheckResult,
  EngineerCompletionManifest,
  EngineerCorrectionPacket,
  EngineerVerifierVerdict,
} from "./contracts.js";
import { EngineerExecutor } from "./executor-runner.js";
import { runEngineerVerifier } from "./verifier-runner.js";
import { markEngineerBlockReadyForArchitectReview } from "./session-state.js";
import type { WebRouter } from "../../web-tools.js";

export interface EngineerPipelineOptions {
  projectRoot: string;
  manifest: EngineerBlockManifest;
  modelRuntime: ModelRuntime;
  executorModel: Model<any>;
  executorThinking: ThinkingLevel;
  verifierModel: Model<any>;
  verifierThinking: ThinkingLevel;
  executorTimeoutMs?: number;
  verifierTimeoutMs?: number;
  maxTurns?: number;
  initialCorrection?: EngineerCorrectionPacket;
  webRouter: WebRouter;
}

export interface EngineerPipelineResult {
  status: "ready-for-architect-review" | "blocked" | "plan-conflict" | "incomplete";
  reason?: string;
  rounds: number;
  completion?: EngineerCompletionManifest;
  checks: EngineerCheckResult[];
  verdict?: EngineerVerifierVerdict;
  usage: {
    executor: UsageSummary;
    verifier: UsageSummary;
    total: UsageSummary;
  };
  metrics: {
    executor: SessionMetricsSummary;
    verifier: SessionMetricsSummary;
  };
}

const EMPTY_METRICS: SessionMetricsSummary = {
  toolCalls: 0,
  repeatedToolCalls: 0,
  callsByTool: {},
  failedToolCalls: 0,
  compactions: 0,
  retries: 0,
};

function addMetrics(
  target: SessionMetricsSummary,
  source: SessionMetricsSummary,
): SessionMetricsSummary {
  const callsByTool = { ...target.callsByTool };
  for (const [name, calls] of Object.entries(source.callsByTool)) {
    callsByTool[name] = (callsByTool[name] ?? 0) + calls;
  }
  return {
    toolCalls: target.toolCalls + source.toolCalls,
    repeatedToolCalls: target.repeatedToolCalls + source.repeatedToolCalls,
    callsByTool,
    failedToolCalls: target.failedToolCalls + source.failedToolCalls,
    compactions: target.compactions + source.compactions,
    retries: target.retries + source.retries,
  };
}

async function progressFingerprint(
  projectRoot: string,
  completion: EngineerCompletionManifest,
  checks: EngineerCheckResult[],
  verdict: EngineerVerifierVerdict,
): Promise<string> {
  const hash = createHash("sha256");
  hash.update(JSON.stringify({ completion, checks, verdict }));
  for (const relative of [...completion.changedPaths].sort()) {
    hash.update(`\0${relative}\0`);
    try {
      hash.update(await readFile(path.join(projectRoot, relative)));
    } catch (error) {
      hash.update(`unreadable:${error instanceof Error ? error.message : String(error)}`);
    }
  }
  return hash.digest("hex");
}

export async function runEngineerPipeline(options: EngineerPipelineOptions): Promise<EngineerPipelineResult> {
  const verifierUsage = emptyUsage();
  const totalUsage = emptyUsage();
  let executor: EngineerExecutor | undefined;
  let completion: EngineerCompletionManifest | undefined;
  let checks: EngineerCheckResult[] = [];
  let verdict: EngineerVerifierVerdict | undefined;
  let verifierMetrics = { ...EMPTY_METRICS, callsByTool: {} };
  let rounds = 0;
  const rejectedFingerprints = new Set<string>();
  try {
    executor = await EngineerExecutor.create({
      projectRoot: options.projectRoot,
      manifest: options.manifest,
      modelRuntime: options.modelRuntime,
      model: options.executorModel,
      thinking: options.executorThinking,
      ...(options.executorTimeoutMs === undefined ? {} : { timeoutMs: options.executorTimeoutMs }),
      ...(options.maxTurns === undefined ? {} : { maxTurns: options.maxTurns }),
      webRouter: options.webRouter,
    });
    let correction = options.initialCorrection;
    while (true) {
      rounds += 1;
      const executorRound = correction
        ? await executor.runCorrection(correction)
        : await executor.runInitial();
      completion = executorRound.completion;
      checks = await runEngineerChecks(executor.facts, options.manifest);
      const verification = await runEngineerVerifier(
        executor.facts,
        options.manifest,
        completion,
        checks,
        options.modelRuntime,
        options.verifierModel,
        options.verifierThinking,
        options.webRouter,
        options.verifierTimeoutMs ?? 900_000,
        options.maxTurns ?? 96,
      );
      verdict = verification.verdict;
      addUsage(verifierUsage, verification.usage);
      verifierMetrics = addMetrics(verifierMetrics, verification.metrics);
      if (verdict.status === "ready-for-architect-review") {
        await markEngineerBlockReadyForArchitectReview(executor.facts);
        const executorUsage = executor.usage();
        addUsage(totalUsage, executorUsage);
        addUsage(totalUsage, verifierUsage);
        return {
          status: "ready-for-architect-review", rounds, completion, checks, verdict,
          usage: { executor: executorUsage, verifier: verifierUsage, total: totalUsage },
          metrics: { executor: executor.sessionMetrics(), verifier: verifierMetrics },
        };
      }
      if (verdict.status === "blocked" || verdict.status === "plan-conflict") {
        const executorUsage = executor.usage();
        addUsage(totalUsage, executorUsage);
        addUsage(totalUsage, verifierUsage);
        return {
          status: verdict.status, rounds, completion, checks, verdict,
          usage: { executor: executorUsage, verifier: verifierUsage, total: totalUsage },
          metrics: { executor: executor.sessionMetrics(), verifier: verifierMetrics },
        };
      }
      const fingerprint = await progressFingerprint(executor.facts.projectRoot, completion, checks, verdict);
      if (rejectedFingerprints.has(fingerprint)) {
        const executorUsage = executor.usage();
        addUsage(totalUsage, executorUsage);
        addUsage(totalUsage, verifierUsage);
        return {
          status: "incomplete",
          reason: "The correction cycle repeated without new repository state, check evidence, or verifier findings",
          rounds,
          completion,
          checks,
          verdict,
          usage: { executor: executorUsage, verifier: verifierUsage, total: totalUsage },
          metrics: { executor: executor.sessionMetrics(), verifier: verifierMetrics },
        };
      }
      rejectedFingerprints.add(fingerprint);
      correction = verdict.correctionPacket;
      if (!correction) throw new Error("Correction-required verdict has no correction packet");
    }
  } catch (error) {
    const executorUsage = executor?.usage() ?? emptyUsage();
    addUsage(totalUsage, executorUsage);
    addUsage(totalUsage, verifierUsage);
    return {
      status: "blocked",
      reason: error instanceof Error ? error.message : String(error),
      rounds,
      ...(completion ? { completion } : {}),
      checks,
      ...(verdict ? { verdict } : {}),
      usage: { executor: executorUsage, verifier: verifierUsage, total: totalUsage },
      metrics: {
        executor: executor?.sessionMetrics() ?? { ...EMPTY_METRICS, callsByTool: {} },
        verifier: verifierMetrics,
      },
    };
  } finally {
    await executor?.dispose();
  }
}

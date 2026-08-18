import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";

import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Model } from "@earendil-works/pi-ai/compat";
import type { ModelRuntime } from "@earendil-works/pi-coding-agent";

import { addUsage, emptyUsage, type UsageSummary } from "../../session-utils.js";
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
        options.verifierTimeoutMs ?? 900_000,
        options.maxTurns ?? 96,
      );
      verdict = verification.verdict;
      addUsage(verifierUsage, verification.usage);
      if (verdict.status === "ready-for-architect-review") {
        const executorUsage = executor.usage();
        addUsage(totalUsage, executorUsage);
        addUsage(totalUsage, verifierUsage);
        return {
          status: "ready-for-architect-review", rounds, completion, checks, verdict,
          usage: { executor: executorUsage, verifier: verifierUsage, total: totalUsage },
        };
      }
      if (verdict.status === "blocked" || verdict.status === "plan-conflict") {
        const executorUsage = executor.usage();
        addUsage(totalUsage, executorUsage);
        addUsage(totalUsage, verifierUsage);
        return {
          status: verdict.status, rounds, completion, checks, verdict,
          usage: { executor: executorUsage, verifier: verifierUsage, total: totalUsage },
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
    };
  } finally {
    await executor?.dispose();
  }
}

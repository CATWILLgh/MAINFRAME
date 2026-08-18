import { execFile } from "node:child_process";
import { promisify } from "node:util";

import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Model } from "@earendil-works/pi-ai/compat";
import {
  createAgentSession,
  defineTool,
  SessionManager,
  SettingsManager,
  type ModelRuntime,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { createProjectTools } from "../../project-tools.js";
import {
  boundedPrompt,
  collectUsage,
  createIsolatedLoader,
  type UsageSummary,
} from "../../session-utils.js";
import {
  parseEngineerVerifierVerdict,
  type EngineerBlockManifest,
  type EngineerCheckResult,
  type EngineerCompletionManifest,
  type EngineerVerifierVerdict,
} from "./contracts.js";
import type { EngineerGitFacts } from "./preflight.js";

const execFileAsync = promisify(execFile);
const MAX_INLINE_DIFF = 120_000;

const VERIFIER_SYSTEM_PROMPT = `You are MAINFRAME's fresh read-only completion verifier.

The executor report is a claim, not evidence. Compare every acceptance item with the actual Git state, changed files, focused check results, and direct project reads. Do not edit files, propose unrelated improvements, or widen the block. A passing check proves only what that check covers. Missing evidence is unproven, not verified.

Classify every acceptance item exactly once. Return ready-for-architect-review only when every item is verified and all supplied deterministic checks passed. For correctable omissions return one exact correction packet for the same executor session. Use plan-conflict only when the agreed manifest itself prevents a correct implementation. Use blocked only for a demonstrated external blocker.`;

export interface EngineerVerificationResult {
  verdict: EngineerVerifierVerdict;
  usage: UsageSummary;
}

export function validateVerdictAgainstRunEvidence(
  verdict: EngineerVerifierVerdict,
  completion: EngineerCompletionManifest,
  checks: EngineerCheckResult[],
): void {
  if (verdict.status === "ready-for-architect-review" && completion.status !== "candidate") {
    throw new Error("A blocked or plan-conflict executor claim cannot be ready for architect review");
  }
  if (verdict.status === "ready-for-architect-review") {
    const failed = checks.filter(({ status }) => status !== "passed").map(({ checkId }) => checkId);
    if (failed.length) throw new Error(`Ready verdict is impossible because checks did not pass: ${failed.join(", ")}`);
  }
  if (verdict.status === "correction-required" && !verdict.correctionPacket) {
    throw new Error("Correction verdict has no correction packet");
  }
}

async function gitEvidence(
  facts: EngineerGitFacts,
  changedPaths: string[],
): Promise<{ currentHead: string; status: string; diff: string; diffTruncated: boolean }> {
  const currentHead = (await execFileAsync("git", ["-C", facts.projectRoot, "rev-parse", "HEAD"], { encoding: "utf8" })).stdout.trim();
  if (currentHead !== facts.startingHead) {
    throw new Error(`Git HEAD changed during the Pi engineer run: expected ${facts.startingHead}, found ${currentHead}`);
  }
  const pathArgs = changedPaths.length ? ["--", ...changedPaths] : ["--"];
  const [statusResult, diffResult] = await Promise.all([
    execFileAsync("git", ["-C", facts.projectRoot, "status", "--porcelain=v1", ...pathArgs], {
      encoding: "utf8",
      maxBuffer: 4 * 1024 * 1024,
    }),
    execFileAsync("git", ["-C", facts.projectRoot, "diff", "--no-ext-diff", "--unified=30", facts.startingHead, ...pathArgs], {
      encoding: "utf8",
      maxBuffer: 8 * 1024 * 1024,
    }),
  ]);
  const fullDiff = diffResult.stdout;
  return {
    currentHead,
    status: statusResult.stdout,
    diff: fullDiff.slice(0, MAX_INLINE_DIFF),
    diffTruncated: fullDiff.length > MAX_INLINE_DIFF,
  };
}

export async function runEngineerVerifier(
  facts: EngineerGitFacts,
  manifest: EngineerBlockManifest,
  completion: EngineerCompletionManifest,
  checks: EngineerCheckResult[],
  modelRuntime: ModelRuntime,
  model: Model<any>,
  thinking: ThinkingLevel,
  timeoutMs = 900_000,
  maxTurns = 96,
): Promise<EngineerVerificationResult> {
  const evidence = await gitEvidence(facts, completion.changedPaths);
  let verdict: EngineerVerifierVerdict | undefined;
  const submit = defineTool({
    name: "submit_engineer_verdict",
    label: "Submit independent block verdict",
    description: "Classify every acceptance item and either approve internal completeness or return one bounded correction packet.",
    parameters: Type.Object({
      schemaVersion: Type.Literal(1),
      blockId: Type.String({ minLength: 1, maxLength: 64 }),
      status: Type.Union([
        Type.Literal("ready-for-architect-review"), Type.Literal("correction-required"),
        Type.Literal("blocked"), Type.Literal("plan-conflict"),
      ]),
      items: Type.Array(Type.Object({
        acceptanceId: Type.String({ minLength: 1, maxLength: 64 }),
        verdict: Type.Union([
          Type.Literal("verified"), Type.Literal("partial"), Type.Literal("missing"),
          Type.Literal("contradicted"), Type.Literal("unproven"), Type.Literal("plan-conflict"),
        ]),
        reason: Type.String({ minLength: 1, maxLength: 1_500 }),
        evidence: Type.Array(Type.String({ minLength: 1 }), { maxItems: 20 }),
      }), { minItems: 1, maxItems: 400 }),
      correctionPacket: Type.Optional(Type.Object({
        instructions: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 40 }),
        missingEvidence: Type.Array(Type.String({ minLength: 1 }), { maxItems: 40 }),
        failedCheckIds: Type.Array(Type.String({ minLength: 1 }), { maxItems: 40 }),
      })),
    }),
    execute: async (_id, params) => {
      try {
        const candidate = parseEngineerVerifierVerdict(params, manifest);
        validateVerdictAgainstRunEvidence(candidate, completion, checks);
        verdict = candidate;
      } catch (error) {
        return {
          content: [{ type: "text" as const, text: `Verdict rejected: ${error instanceof Error ? error.message : String(error)}` }],
          details: {},
        };
      }
      return { content: [{ type: "text" as const, text: "Independent verdict accepted." }], details: {}, terminate: true };
    },
  });
  const settings = SettingsManager.inMemory({
    compaction: { enabled: false },
    retry: { enabled: true, maxRetries: 2 },
  });
  const loader = await createIsolatedLoader(facts.projectRoot, VERIFIER_SYSTEM_PROMPT, settings);
  const session = (await createAgentSession({
    cwd: facts.projectRoot,
    modelRuntime,
    model,
    thinkingLevel: thinking,
    tools: ["project_read", "project_find", "project_grep", "project_list", "submit_engineer_verdict"],
    customTools: [...createProjectTools(facts.projectRoot), submit],
    resourceLoader: loader,
    sessionManager: SessionManager.inMemory(facts.projectRoot),
    settingsManager: settings,
  })).session;
  try {
    const prompt = `Verify this implementation block. The Git diff may omit untracked file contents; inspect every changed path directly when needed. If diffTruncated is true, use focused reads and searches instead of assuming the omitted tail.\n\n${JSON.stringify({ manifest, executorClaim: completion, deterministicChecks: checks, git: evidence }, null, 2)}`;
    await boundedPrompt(session, prompt, timeoutMs, maxTurns, () => verdict !== undefined, "submit_engineer_verdict");
    if (!verdict) throw new Error("Pi engineer verifier ended without a valid verdict");
    return { verdict, usage: collectUsage(session) };
  } finally {
    session.dispose();
  }
}

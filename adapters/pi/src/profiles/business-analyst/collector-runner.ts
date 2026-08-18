import {
  createAgentSession,
  defineTool,
  SessionManager,
  SettingsManager,
  type ModelRuntime,
} from "@earendil-works/pi-coding-agent";
import type { Model } from "@earendil-works/pi-ai/compat";
import { Type } from "typebox";

import type { CollectorSelection } from "../../model-types.js";
import { createProjectTools } from "../../project-tools.js";
import { boundedPrompt, collectUsage, createIsolatedLoader, type UsageSummary } from "../../session-utils.js";
import {
  assignClaimIds,
  type AtomicClaim,
  type SourceSegment,
  type SubmittedClaim,
  validateClaimSubmission,
} from "./facts.js";
import { BUSINESS_ANALYSIS_COLLECTOR_SYSTEM_PROMPT, collectorPrompt } from "./prompts.js";

export interface CollectorResult {
  role: CollectorSelection["role"];
  claims: AtomicClaim[];
  usage: UsageSummary;
}

export class CollectorRunError extends Error {
  constructor(message: string, readonly usage: UsageSummary, options?: ErrorOptions) {
    super(message, options);
    this.name = "CollectorRunError";
  }
}

const claimSchema = Type.Object({
  statement: Type.String({ minLength: 1, maxLength: 1_200 }),
  kind: Type.Union([
    Type.Literal("source-rule"),
    Type.Literal("implementation-fact"),
    Type.Literal("candidate-gap"),
    Type.Literal("candidate-conflict"),
    Type.Literal("external-fact"),
  ]),
  basis: Type.Union([Type.Literal("direct"), Type.Literal("inference")]),
  sourceSegmentIds: Type.Array(Type.String(), { maxItems: 20 }),
  evidence: Type.Array(Type.String(), { minItems: 1, maxItems: 12 }),
  uncertainty: Type.String({ maxLength: 800 }),
  verificationQuestion: Type.String({ minLength: 1, maxLength: 800 }),
});

export async function runCollector(
  projectRoot: string,
  initiative: string,
  entryPath: string,
  collector: CollectorSelection,
  segments: SourceSegment[],
  modelRuntime: ModelRuntime,
  model: Model<any>,
  timeoutMs: number,
  maxTurns: number,
  allowedRuntimeInput?: string,
): Promise<CollectorResult> {
  const deadline = Date.now() + timeoutMs;
  let claims: AtomicClaim[] | undefined;
  let submissionAttempts = 0;
  let lastSubmissionErrors: string[] = [];
  const submitFacts = defineTool({
    name: "submit_fact_batch",
    label: "Submit atomic fact batch",
    description: "Submit one falsifiable claim per item and account for every primary-source segment.",
    parameters: Type.Object({
      claims: Type.Array(claimSchema, { maxItems: 120 }),
      noClaimSegmentIds: Type.Array(Type.String(), { maxItems: 300 }),
    }),
    execute: async (_id, params) => {
      submissionAttempts += 1;
      if (claims) {
        return { content: [{ type: "text", text: "Fact submission is closed." }], details: {}, terminate: true };
      }
      const errors = await validateClaimSubmission(
        projectRoot,
        params.claims as SubmittedClaim[],
        params.noClaimSegmentIds,
        segments,
      );
      lastSubmissionErrors = errors;
      if (errors.length) {
        return {
          content: [{ type: "text", text: `Fact batch rejected:\n${errors.map((error) => `- ${error}`).join("\n")}` }],
          details: {},
        };
      }
      claims = assignClaimIds(collector.role, params.claims as SubmittedClaim[]);
      return { content: [{ type: "text", text: "Fact batch accepted." }], details: {}, terminate: true };
    },
  });
  const settings = SettingsManager.inMemory({
    compaction: { enabled: false },
    retry: { enabled: true, maxRetries: 2 },
  });
  const loader = await createIsolatedLoader(projectRoot, BUSINESS_ANALYSIS_COLLECTOR_SYSTEM_PROMPT, settings);
  const created = await createAgentSession({
    cwd: projectRoot,
    modelRuntime,
    model,
    thinkingLevel: collector.model.thinking,
    tools: ["project_read", "project_find", "project_grep", "project_list", "submit_fact_batch"],
    customTools: [...createProjectTools(projectRoot, allowedRuntimeInput), submitFacts],
    resourceLoader: loader,
    sessionManager: SessionManager.inMemory(projectRoot),
    settingsManager: settings,
  });
  try {
    await boundedPrompt(
      created.session,
      collectorPrompt(initiative, entryPath, segments),
      timeoutMs,
      maxTurns,
      () => claims !== undefined,
      "submit_fact_batch",
    );
    if (!claims) {
      const remainingMs = deadline - Date.now();
      if (remainingMs <= 0) throw new Error(`${collector.role} collector exhausted its time without a valid fact batch`);
      await boundedPrompt(
        created.session,
        "Your previous turn ended without calling submit_fact_batch. Do not continue research or explain the omission. Submit the complete atomic fact batch now, accounting for every source segment.",
        remainingMs,
        maxTurns,
        () => claims !== undefined,
        "submit_fact_batch",
      );
    }
    if (!claims) {
      const rejection = lastSubmissionErrors.length
        ? `; last rejection: ${lastSubmissionErrors.join(" | ")}`
        : "";
      throw new Error(
        `${collector.role} collector ended without a valid fact batch after ${submissionAttempts} submission attempt(s)${rejection}`,
      );
    }
    return { role: collector.role, claims, usage: collectUsage(created.session) };
  } catch (error) {
    if (error instanceof CollectorRunError) throw error;
    throw new CollectorRunError(
      error instanceof Error ? error.message : String(error),
      collectUsage(created.session),
      { cause: error },
    );
  } finally {
    created.session.dispose();
  }
}

import {
  createAgentSession,
  defineTool,
  SessionManager,
  SettingsManager,
  type ModelRuntime,
} from "@earendil-works/pi-coding-agent";
import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Model } from "@earendil-works/pi-ai/compat";
import { Type } from "typebox";

import { createProjectTools } from "../../project-tools.js";
import { boundedPrompt, collectUsage, createIsolatedLoader, type UsageSummary } from "../../session-utils.js";
import { createWebRouter, createWebTools } from "../../web-tools.js";
import type { AtomicClaim, VerifiedClaim } from "./facts.js";
import { BUSINESS_ANALYSIS_VERIFIER_SYSTEM_PROMPT, verifierPrompt } from "./prompts.js";
import { validateEvidenceReferences } from "./review-validator.js";

export interface VerifierResult {
  claims: VerifiedClaim[];
  usage: UsageSummary;
}

export async function runVerifier(
  projectRoot: string,
  initiative: string,
  candidates: AtomicClaim[],
  modelRuntime: ModelRuntime,
  model: Model<any>,
  thinking: ThinkingLevel,
  timeoutMs: number,
  maxTurns: number,
  allowedRuntimeInput?: string,
): Promise<VerifierResult> {
  let verified: VerifiedClaim[] | undefined;
  const submitVerification = defineTool({
    name: "submit_verification_ledger",
    label: "Submit verified claim ledger",
    description: "Return exactly one evidence verdict for every supplied candidate claim.",
    parameters: Type.Object({
      claims: Type.Array(Type.Object({
        claimId: Type.String(),
        verdict: Type.Union([
          Type.Literal("verified"), Type.Literal("partially-verified"), Type.Literal("unsupported"),
          Type.Literal("contradicted"), Type.Literal("duplicate"),
        ]),
        normalizedStatement: Type.String({ minLength: 1, maxLength: 1_200 }),
        evidence: Type.Array(Type.String(), { maxItems: 12 }),
        reason: Type.String({ minLength: 1, maxLength: 1_200 }),
        duplicateOf: Type.Optional(Type.String()),
      }), { maxItems: 360 }),
    }),
    execute: async (_id, params) => {
      const rows = params.claims as VerifiedClaim[];
      const expected = new Set(candidates.map(({ id }) => id));
      const errors: string[] = [];
      const seen = new Set<string>();
      for (const row of rows) {
        if (!expected.has(row.claimId)) errors.push(`Unknown claim id: ${row.claimId}`);
        if (seen.has(row.claimId)) errors.push(`Duplicate verdict: ${row.claimId}`);
        seen.add(row.claimId);
        if (["verified", "partially-verified", "contradicted"].includes(row.verdict) && !row.evidence.length) {
          errors.push(`${row.claimId} verdict ${row.verdict} requires evidence`);
        }
        if (row.verdict === "duplicate" && (!row.duplicateOf || !expected.has(row.duplicateOf))) {
          errors.push(`${row.claimId} duplicate verdict requires a known duplicateOf id`);
        }
        errors.push(...(await validateEvidenceReferences(projectRoot, row.evidence, row.claimId)));
      }
      for (const id of expected) if (!seen.has(id)) errors.push(`Missing verdict: ${id}`);
      if (errors.length) {
        return { content: [{ type: "text", text: `Ledger rejected:\n${errors.map((error) => `- ${error}`).join("\n")}` }], details: {} };
      }
      verified = rows;
      return { content: [{ type: "text", text: "Verification ledger accepted." }], details: {}, terminate: true };
    },
  });
  const settings = SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: true, maxRetries: 2 } });
  const loader = await createIsolatedLoader(projectRoot, BUSINESS_ANALYSIS_VERIFIER_SYSTEM_PROMPT, settings);
  const webTools = createWebTools(await createWebRouter(modelRuntime, "zai"));
  const created = await createAgentSession({
    cwd: projectRoot,
    modelRuntime,
    model,
    thinkingLevel: thinking,
    tools: ["project_read", "project_find", "project_grep", "project_list", "web_search", "web_fetch", "submit_verification_ledger"],
    customTools: [...createProjectTools(projectRoot, allowedRuntimeInput), ...webTools, submitVerification],
    resourceLoader: loader,
    sessionManager: SessionManager.inMemory(projectRoot),
    settingsManager: settings,
  });
  try {
    await boundedPrompt(created.session, verifierPrompt(initiative, candidates), timeoutMs, maxTurns, () => verified !== undefined, "submit_verification_ledger");
    if (!verified) throw new Error("Verifier ended without a valid claim ledger");
    return { claims: verified, usage: collectUsage(created.session) };
  } finally {
    created.session.dispose();
  }
}

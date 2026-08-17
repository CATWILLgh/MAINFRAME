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

import { BUSINESS_ANALYSIS_CRITIC_SYSTEM_PROMPT, criticPrompt } from "./prompts.js";
import { createProjectTools } from "./project-tools.js";
import { boundedPrompt, collectUsage, createIsolatedLoader, type UsageSummary } from "./session-utils.js";

export interface CriticResult {
  critique: string;
  usage: UsageSummary;
}

export async function runCritic(
  projectRoot: string,
  initiative: string,
  draft: string,
  modelRuntime: ModelRuntime,
  model: Model<any>,
  thinking: ThinkingLevel,
  timeoutMs: number,
  maxTurns: number,
  allowedRuntimeInput?: string,
): Promise<CriticResult> {
  let critique: string | undefined;
  const submitCritique = defineTool({
    name: "submit_critique",
    label: "Submit evidence critique",
    description: "Return concise evidence-linked corrections for the consolidating analyst.",
    parameters: Type.Object({ markdown: Type.String({ minLength: 1 }) }),
    execute: async (_id, params) => {
      if (critique) {
        return { content: [{ type: "text", text: "Critique submission is closed." }], details: {}, terminate: true };
      }
      critique = params.markdown;
      return { content: [{ type: "text", text: "Critique received." }], details: {}, terminate: true };
    },
  });
  const settings = SettingsManager.inMemory({
    compaction: { enabled: false },
    retry: { enabled: true, maxRetries: 2 },
  });
  const loader = await createIsolatedLoader(projectRoot, BUSINESS_ANALYSIS_CRITIC_SYSTEM_PROMPT, settings);
  const created = await createAgentSession({
    cwd: projectRoot,
    modelRuntime,
    model,
    thinkingLevel: thinking,
    tools: ["project_read", "project_find", "project_grep", "project_list", "submit_critique"],
    customTools: [...createProjectTools(projectRoot, allowedRuntimeInput), submitCritique],
    resourceLoader: loader,
    sessionManager: SessionManager.inMemory(projectRoot),
    settingsManager: settings,
  });
  try {
    await boundedPrompt(
      created.session,
      criticPrompt(initiative, draft),
      timeoutMs,
      maxTurns,
      () => critique !== undefined,
      "submit_critique",
    );
    if (!critique) throw new Error("Critic ended without submitting observations");
    return { critique, usage: collectUsage(created.session) };
  } finally {
    created.session.dispose();
  }
}

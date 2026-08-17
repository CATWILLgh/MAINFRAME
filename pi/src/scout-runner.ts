import {
  createAgentSession,
  defineTool,
  SessionManager,
  SettingsManager,
  type ModelRuntime,
} from "@earendil-works/pi-coding-agent";
import type { Model } from "@earendil-works/pi-ai/compat";
import { Type } from "typebox";

import {
  BUSINESS_ANALYSIS_SCOUT_SYSTEM_PROMPT,
  scoutPrompt,
} from "./prompts.js";
import { createProjectTools } from "./project-tools.js";
import { boundedPrompt, collectUsage, createIsolatedLoader, type UsageSummary } from "./session-utils.js";
import type { ScoutRole, ScoutSelection } from "./runtime.js";

export interface ScoutResult {
  role: ScoutRole;
  observations: string;
  usage: UsageSummary;
}

export async function runScout(
  projectRoot: string,
  initiative: string,
  entryPath: string,
  scout: ScoutSelection,
  modelRuntime: ModelRuntime,
  model: Model<any>,
  timeoutMs: number,
  maxTurns: number,
): Promise<ScoutResult> {
  let observations: string | undefined;
  const submitObservations = defineTool({
    name: "submit_observations",
    label: "Submit candidate observations",
    description: "Return concise evidence-linked leads for the consolidating analyst.",
    parameters: Type.Object({ markdown: Type.String({ minLength: 1, maxLength: 12_000 }) }),
    execute: async (_id, params) => {
      if (observations) {
        return {
          content: [{ type: "text", text: "Observation submission is closed." }],
          details: {},
          terminate: true,
        };
      }
      observations = params.markdown;
      return { content: [{ type: "text", text: "Observations received." }], details: {}, terminate: true };
    },
  });
  const settings = SettingsManager.inMemory({
    compaction: { enabled: false },
    retry: { enabled: true, maxRetries: 2 },
  });
  const loader = await createIsolatedLoader(projectRoot, BUSINESS_ANALYSIS_SCOUT_SYSTEM_PROMPT, settings);
  const created = await createAgentSession({
    cwd: projectRoot,
    modelRuntime,
    model,
    thinkingLevel: scout.model.thinking,
    tools: ["project_read", "project_find", "project_grep", "project_list", "submit_observations"],
    customTools: [...createProjectTools(projectRoot, entryPath), submitObservations],
    resourceLoader: loader,
    sessionManager: SessionManager.inMemory(projectRoot),
    settingsManager: settings,
  });
  try {
    await boundedPrompt(
      created.session,
      scoutPrompt(initiative, entryPath),
      timeoutMs,
      maxTurns,
      () => observations !== undefined,
      "submit_observations",
    );
    if (!observations) throw new Error(`${scout.role} scout ended without submitting observations`);
    return { role: scout.role, observations, usage: collectUsage(created.session) };
  } finally {
    created.session.dispose();
  }
}

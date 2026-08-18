import { readFile } from "node:fs/promises";
import path from "node:path";

import type { ThinkingLevel } from "@earendil-works/pi-agent-core";

import type { CollectorRole, CollectorSelection, ModelSelection } from "./model-types.js";

const THINKING_LEVELS = new Set<ThinkingLevel>([
  "off",
  "minimal",
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
]);

interface ModelAlias {
  provider: string;
  model: string;
}

interface ProfileStage {
  model: string;
  thinking: ThinkingLevel;
}

interface RawProfileConfig {
  schemaVersion: number;
  models: Record<string, ModelAlias>;
  profiles: Record<
    string,
    {
      collectors: Record<CollectorRole, ProfileStage>;
      verifier: ProfileStage;
      synthesizer: ProfileStage;
    }
  >;
  engineerProfiles: Record<string, { executor: ProfileStage; verifier: ProfileStage }>;
}

export interface ResolvedProfile {
  collectors: CollectorSelection[];
  verifier: ModelSelection;
  synthesizer: ModelSelection;
}

export interface ResolvedEngineerProfile {
  executor: ModelSelection;
  verifier: ModelSelection;
}

const COLLECTOR_ROLES: CollectorRole[] = ["minimax", "glm-turbo", "glm-5.2"];

function object(value: unknown, owner: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${owner} must be an object`);
  }
  return value as Record<string, unknown>;
}

function parseConfig(value: unknown): RawProfileConfig {
  const root = object(value, "Profile config");
  if (root.schemaVersion !== 4) throw new Error("Profile config schemaVersion must be 4");
  const rawModels = object(root.models, "models");
  const models: Record<string, ModelAlias> = {};
  for (const [alias, rawModel] of Object.entries(rawModels)) {
    const model = object(rawModel, `models.${alias}`);
    if (typeof model.provider !== "string" || !model.provider) {
      throw new Error(`models.${alias}.provider must be a non-empty string`);
    }
    if (typeof model.model !== "string" || !model.model) {
      throw new Error(`models.${alias}.model must be a non-empty string`);
    }
    models[alias] = { provider: model.provider, model: model.model };
  }

  const rawProfiles = object(root.profiles, "profiles");
  const profiles: RawProfileConfig["profiles"] = {};
  for (const [name, rawProfile] of Object.entries(rawProfiles)) {
    const profile = object(rawProfile, `profiles.${name}`);
    const rawCollectors = object(profile.collectors, `profiles.${name}.collectors`);
    const collectors = {} as Record<CollectorRole, ProfileStage>;
    for (const role of COLLECTOR_ROLES) {
      const stage = object(rawCollectors[role], `profiles.${name}.collectors.${role}`);
      if (typeof stage.model !== "string" || !models[stage.model]) {
        throw new Error(`profiles.${name}.collectors.${role}.model must reference a configured model alias`);
      }
      if (typeof stage.thinking !== "string" || !THINKING_LEVELS.has(stage.thinking as ThinkingLevel)) {
        throw new Error(`profiles.${name}.collectors.${role}.thinking is unsupported`);
      }
      collectors[role] = { model: stage.model, thinking: stage.thinking as ThinkingLevel };
    }
    const rawSynthesizer = object(profile.synthesizer, `profiles.${name}.synthesizer`);
    if (typeof rawSynthesizer.model !== "string" || !models[rawSynthesizer.model]) {
      throw new Error(`profiles.${name}.synthesizer.model must reference a configured model alias`);
    }
    if (
      typeof rawSynthesizer.thinking !== "string" ||
      !THINKING_LEVELS.has(rawSynthesizer.thinking as ThinkingLevel)
    ) {
      throw new Error(`profiles.${name}.synthesizer.thinking is unsupported`);
    }
    const rawVerifier = object(profile.verifier, `profiles.${name}.verifier`);
    if (typeof rawVerifier.model !== "string" || !models[rawVerifier.model]) {
      throw new Error(`profiles.${name}.verifier.model must reference a configured model alias`);
    }
    if (typeof rawVerifier.thinking !== "string" || !THINKING_LEVELS.has(rawVerifier.thinking as ThinkingLevel)) {
      throw new Error(`profiles.${name}.verifier.thinking is unsupported`);
    }
    profiles[name] = {
      collectors,
      verifier: {
        model: rawVerifier.model,
        thinking: rawVerifier.thinking as ThinkingLevel,
      },
      synthesizer: {
        model: rawSynthesizer.model,
        thinking: rawSynthesizer.thinking as ThinkingLevel,
      },
    };
  }
  const rawEngineerProfiles = root.engineerProfiles === undefined
    ? {}
    : object(root.engineerProfiles, "engineerProfiles");
  const engineerProfiles: RawProfileConfig["engineerProfiles"] = {};
  for (const [name, rawEngineerProfile] of Object.entries(rawEngineerProfiles)) {
    const profile = object(rawEngineerProfile, `engineerProfiles.${name}`);
    const parsed = {} as { executor: ProfileStage; verifier: ProfileStage };
    for (const role of ["executor", "verifier"] as const) {
      const stage = object(profile[role], `engineerProfiles.${name}.${role}`);
      if (typeof stage.model !== "string" || !models[stage.model]) {
        throw new Error(`engineerProfiles.${name}.${role}.model must reference a configured model alias`);
      }
      if (typeof stage.thinking !== "string" || !THINKING_LEVELS.has(stage.thinking as ThinkingLevel)) {
        throw new Error(`engineerProfiles.${name}.${role}.thinking is unsupported`);
      }
      parsed[role] = { model: stage.model, thinking: stage.thinking as ThinkingLevel };
    }
    engineerProfiles[name] = parsed;
  }
  return { schemaVersion: 4, models, profiles, engineerProfiles };
}

export async function loadEngineerProfile(
  configPath: string,
  profileName: string,
): Promise<ResolvedEngineerProfile> {
  const absolute = path.resolve(configPath);
  const parsed = parseConfig(JSON.parse(await readFile(absolute, "utf8")) as unknown);
  const profile = parsed.engineerProfiles[profileName];
  if (!profile) throw new Error(`Unknown Pi engineer profile: ${profileName}`);
  const resolveStage = (stage: ProfileStage): ModelSelection => {
    const alias = parsed.models[stage.model];
    if (!alias) throw new Error(`Unknown model alias: ${stage.model}`);
    return { provider: alias.provider, model: alias.model, thinking: stage.thinking };
  };
  return { executor: resolveStage(profile.executor), verifier: resolveStage(profile.verifier) };
}

export async function loadProfile(
  configPath: string,
  profileName: string,
): Promise<ResolvedProfile> {
  const absolute = path.resolve(configPath);
  const parsed = parseConfig(JSON.parse(await readFile(absolute, "utf8")) as unknown);
  const profile = parsed.profiles[profileName];
  if (!profile) throw new Error(`Unknown Pi profile: ${profileName}`);

  const resolveStage = (stage: ProfileStage): ModelSelection => {
    const alias = parsed.models[stage.model];
    if (!alias) throw new Error(`Unknown model alias: ${stage.model}`);
    return { provider: alias.provider, model: alias.model, thinking: stage.thinking };
  };
  return {
    collectors: COLLECTOR_ROLES.map((role) => ({ role, model: resolveStage(profile.collectors[role]) })),
    verifier: resolveStage(profile.verifier),
    synthesizer: resolveStage(profile.synthesizer),
  };
}

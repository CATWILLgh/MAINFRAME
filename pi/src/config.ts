import { readFile } from "node:fs/promises";
import path from "node:path";

import type { ThinkingLevel } from "@earendil-works/pi-agent-core";

import type { ModelSelection, ScoutRole, ScoutSelection } from "./runtime.js";

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
    { scouts: Record<ScoutRole, ProfileStage>; critic: ProfileStage; consolidator: ProfileStage }
  >;
}

export interface ResolvedProfile {
  scouts: ScoutSelection[];
  critic: ModelSelection;
  consolidator: ModelSelection;
}

const SCOUT_ROLES: ScoutRole[] = ["independent-a", "independent-b"];

function object(value: unknown, owner: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${owner} must be an object`);
  }
  return value as Record<string, unknown>;
}

function parseConfig(value: unknown): RawProfileConfig {
  const root = object(value, "Profile config");
  if (root.schemaVersion !== 3) throw new Error("Profile config schemaVersion must be 3");
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
    const rawScouts = object(profile.scouts, `profiles.${name}.scouts`);
    const scouts = {} as Record<ScoutRole, ProfileStage>;
    for (const role of SCOUT_ROLES) {
      const stage = object(rawScouts[role], `profiles.${name}.scouts.${role}`);
      if (typeof stage.model !== "string" || !models[stage.model]) {
        throw new Error(`profiles.${name}.scouts.${role}.model must reference a configured model alias`);
      }
      if (typeof stage.thinking !== "string" || !THINKING_LEVELS.has(stage.thinking as ThinkingLevel)) {
        throw new Error(`profiles.${name}.scouts.${role}.thinking is unsupported`);
      }
      scouts[role] = { model: stage.model, thinking: stage.thinking as ThinkingLevel };
    }
    const rawConsolidator = object(profile.consolidator, `profiles.${name}.consolidator`);
    if (typeof rawConsolidator.model !== "string" || !models[rawConsolidator.model]) {
      throw new Error(`profiles.${name}.consolidator.model must reference a configured model alias`);
    }
    if (
      typeof rawConsolidator.thinking !== "string" ||
      !THINKING_LEVELS.has(rawConsolidator.thinking as ThinkingLevel)
    ) {
      throw new Error(`profiles.${name}.consolidator.thinking is unsupported`);
    }
    const rawCritic = object(profile.critic, `profiles.${name}.critic`);
    if (typeof rawCritic.model !== "string" || !models[rawCritic.model]) {
      throw new Error(`profiles.${name}.critic.model must reference a configured model alias`);
    }
    if (typeof rawCritic.thinking !== "string" || !THINKING_LEVELS.has(rawCritic.thinking as ThinkingLevel)) {
      throw new Error(`profiles.${name}.critic.thinking is unsupported`);
    }
    profiles[name] = {
      scouts,
      critic: {
        model: rawCritic.model,
        thinking: rawCritic.thinking as ThinkingLevel,
      },
      consolidator: {
        model: rawConsolidator.model,
        thinking: rawConsolidator.thinking as ThinkingLevel,
      },
    };
  }
  return { schemaVersion: 3, models, profiles };
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
    scouts: SCOUT_ROLES.map((role) => ({ role, model: resolveStage(profile.scouts[role]) })),
    critic: resolveStage(profile.critic),
    consolidator: resolveStage(profile.consolidator),
  };
}

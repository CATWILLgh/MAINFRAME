import { createHash } from "node:crypto";

import {
  parseEngineerBlockManifest,
  type EngineerBlockManifest,
  type EngineerSessionMode,
} from "./contracts.js";

export interface EngineerBlockRequest {
  schemaVersion: 1;
  goal: string;
  writePaths: string[];
  excludePaths: string[];
  invariants: string[];
  acceptance: string[];
  forbiddenFutureStages: string[];
  checks: Array<{ argv: string[]; timeoutMs: number }>;
}

type UnknownObject = Record<string, unknown>;

function object(value: unknown, owner: string): UnknownObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${owner} must be an object`);
  return value as UnknownObject;
}

function fields(value: UnknownObject, required: string[], optional: string[], owner: string): void {
  const allowed = new Set([...required, ...optional]);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) throw new Error(`${owner} contains unsupported field '${key}'`);
  }
  for (const key of required) if (!(key in value)) throw new Error(`${owner} is missing '${key}'`);
}

function text(value: unknown, owner: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${owner} must be a non-empty string`);
  return value;
}

function texts(value: unknown, owner: string, required = false): string[] {
  if (!Array.isArray(value) || (required && value.length === 0)) {
    throw new Error(`${owner} must be ${required ? "a non-empty" : "an"} array`);
  }
  const result = value.map((item, index) => text(item, `${owner}[${index}]`));
  if (new Set(result).size !== result.length) throw new Error(`${owner} must not contain duplicates`);
  return result;
}

export function parseEngineerBlockRequest(value: unknown): EngineerBlockRequest {
  const root = object(value, "Engineer block request");
  fields(root, ["schemaVersion", "goal", "writePaths", "acceptance"], [
    "excludePaths", "invariants", "forbiddenFutureStages", "checks",
  ], "Engineer block request");
  if (root.schemaVersion !== 1) throw new Error("Engineer block request schemaVersion must be 1");
  if (root.checks !== undefined && !Array.isArray(root.checks)) throw new Error("checks must be an array");
  const checks = root.checks === undefined ? [] : root.checks.map((raw, index) => {
    const check = object(raw, `checks[${index}]`);
    fields(check, ["argv"], ["timeoutMs"], `checks[${index}]`);
    const timeoutMs = check.timeoutMs ?? 60_000;
    if (typeof timeoutMs !== "number" || !Number.isInteger(timeoutMs) || timeoutMs < 1_000 || timeoutMs > 3_600_000) {
      throw new Error(`checks[${index}].timeoutMs must be an integer from 1000 to 3600000`);
    }
    return { argv: texts(check.argv, `checks[${index}].argv`, true), timeoutMs };
  });
  return {
    schemaVersion: 1,
    goal: text(root.goal, "goal"),
    writePaths: texts(root.writePaths, "writePaths", true),
    excludePaths: root.excludePaths === undefined ? [] : texts(root.excludePaths, "excludePaths"),
    invariants: root.invariants === undefined ? [] : texts(root.invariants, "invariants"),
    acceptance: texts(root.acceptance, "acceptance", true),
    forbiddenFutureStages: root.forbiddenFutureStages === undefined
      ? []
      : texts(root.forbiddenFutureStages, "forbiddenFutureStages"),
    checks,
  };
}

export function compileEngineerBlockManifest(
  request: EngineerBlockRequest,
  expectedHead: string,
  sessionMode: EngineerSessionMode,
): EngineerBlockManifest {
  const digest = createHash("sha256")
    .update(`${expectedHead}\0${JSON.stringify(request)}`)
    .digest("hex")
    .slice(0, 12)
    .toUpperCase();
  return parseEngineerBlockManifest({
    schemaVersion: 1,
    blockId: `BLOCK-${digest}`,
    sessionMode,
    goal: request.goal,
    expectedHead,
    scope: { include: request.writePaths, exclude: request.excludePaths },
    invariants: request.invariants,
    acceptance: request.acceptance.map((requirement, index) => ({
      id: `A-${String(index + 1).padStart(3, "0")}`,
      requirement,
    })),
    forbiddenFutureStages: request.forbiddenFutureStages,
    allowedChecks: request.checks.map((check, index) => ({
      id: `CHECK-${String(index + 1).padStart(3, "0")}`,
      ...check,
    })),
  });
}

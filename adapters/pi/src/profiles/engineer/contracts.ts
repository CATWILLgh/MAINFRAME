export type EngineerSessionMode = "new" | "resume";

export type AcceptanceVerdict =
  | "verified"
  | "partial"
  | "missing"
  | "contradicted"
  | "unproven"
  | "plan-conflict";

export interface EngineerAcceptanceItem {
  id: string;
  requirement: string;
}

export interface EngineerAllowedCheck {
  id: string;
  argv: string[];
  timeoutMs: number;
}

export interface EngineerBlockManifest {
  schemaVersion: 1;
  blockId: string;
  sessionMode: EngineerSessionMode;
  goal: string;
  expectedHead: string;
  scope: {
    include: string[];
    exclude: string[];
  };
  invariants: string[];
  acceptance: EngineerAcceptanceItem[];
  forbiddenFutureStages: string[];
  allowedChecks: EngineerAllowedCheck[];
}

export interface EngineerCompletionManifest {
  schemaVersion: 1;
  blockId: string;
  status: "candidate" | "blocked" | "plan-conflict";
  summary: string;
  changedPaths: string[];
  acceptanceClaims: Array<{
    acceptanceId: string;
    claim: string;
    evidence: string[];
  }>;
  blockers: string[];
}

export interface EngineerCheckResult {
  schemaVersion: 1;
  checkId: string;
  argv: string[];
  status: "passed" | "failed" | "timed-out" | "spawn-error";
  exitCode: number | null;
  durationMs: number;
  output: {
    inline: string;
    truncated: boolean;
    retainedPath?: string;
  };
}

export interface EngineerCorrectionPacket {
  instructions: string[];
  missingEvidence: string[];
  failedCheckIds: string[];
}

export interface EngineerVerifierVerdict {
  schemaVersion: 1;
  blockId: string;
  status: "ready-for-architect-review" | "correction-required" | "blocked" | "plan-conflict";
  items: Array<{
    acceptanceId: string;
    verdict: AcceptanceVerdict;
    reason: string;
    evidence: string[];
  }>;
  correctionPacket?: EngineerCorrectionPacket;
}

type UnknownObject = Record<string, unknown>;

function object(value: unknown, owner: string): UnknownObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${owner} must be an object`);
  }
  return value as UnknownObject;
}

function exactKeys(value: UnknownObject, keys: string[], owner: string): void {
  const allowed = new Set(keys);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) throw new Error(`${owner} contains unsupported field '${key}'`);
  }
  for (const key of keys) {
    if (!(key in value)) throw new Error(`${owner} is missing '${key}'`);
  }
}

function nonEmptyString(value: unknown, owner: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${owner} must be a non-empty string`);
  return value;
}

function identifier(value: unknown, owner: string): string {
  const parsed = nonEmptyString(value, owner);
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(parsed)) {
    throw new Error(`${owner} must be a safe identifier no longer than 64 characters`);
  }
  return parsed;
}

function stringArray(value: unknown, owner: string, allowEmpty = true): string[] {
  if (!Array.isArray(value) || (!allowEmpty && value.length === 0)) {
    throw new Error(`${owner} must be ${allowEmpty ? "an" : "a non-empty"} array`);
  }
  const parsed = value.map((item, index) => nonEmptyString(item, `${owner}[${index}]`));
  if (new Set(parsed).size !== parsed.length) throw new Error(`${owner} must not contain duplicates`);
  return parsed;
}

function objectArray(value: unknown, owner: string): UnknownObject[] {
  if (!Array.isArray(value)) throw new Error(`${owner} must be an array`);
  return value.map((item, index) => object(item, `${owner}[${index}]`));
}

function uniqueIds(items: Array<{ id: string }>, owner: string): void {
  if (new Set(items.map(({ id }) => id)).size !== items.length) throw new Error(`${owner} ids must be unique`);
}

export function parseEngineerBlockManifest(value: unknown): EngineerBlockManifest {
  const root = object(value, "Engineer block manifest");
  exactKeys(root, [
    "schemaVersion", "blockId", "sessionMode", "goal", "expectedHead", "scope", "invariants",
    "acceptance", "forbiddenFutureStages", "allowedChecks",
  ], "Engineer block manifest");
  if (root.schemaVersion !== 1) throw new Error("Engineer block manifest schemaVersion must be 1");
  if (root.sessionMode !== "new" && root.sessionMode !== "resume") {
    throw new Error("Engineer block manifest sessionMode must be new or resume");
  }
  const expectedHead = nonEmptyString(root.expectedHead, "expectedHead");
  if (!/^[0-9a-f]{40,64}$/i.test(expectedHead)) throw new Error("expectedHead must be a full Git object id");
  const scope = object(root.scope, "scope");
  exactKeys(scope, ["include", "exclude"], "scope");
  const acceptance = objectArray(root.acceptance, "acceptance").map((item, index) => {
    exactKeys(item, ["id", "requirement"], `acceptance[${index}]`);
    return {
      id: identifier(item.id, `acceptance[${index}].id`),
      requirement: nonEmptyString(item.requirement, `acceptance[${index}].requirement`),
    };
  });
  if (acceptance.length === 0) throw new Error("acceptance must contain at least one item");
  uniqueIds(acceptance, "acceptance");
  const allowedChecks = objectArray(root.allowedChecks, "allowedChecks").map((item, index) => {
    exactKeys(item, ["id", "argv", "timeoutMs"], `allowedChecks[${index}]`);
    const argv = stringArray(item.argv, `allowedChecks[${index}].argv`, false);
    if (typeof item.timeoutMs !== "number" || !Number.isInteger(item.timeoutMs) || item.timeoutMs < 1_000 || item.timeoutMs > 3_600_000) {
      throw new Error(`allowedChecks[${index}].timeoutMs must be an integer from 1000 to 3600000`);
    }
    return { id: identifier(item.id, `allowedChecks[${index}].id`), argv, timeoutMs: item.timeoutMs };
  });
  uniqueIds(allowedChecks, "allowedChecks");
  return {
    schemaVersion: 1,
    blockId: identifier(root.blockId, "blockId"),
    sessionMode: root.sessionMode,
    goal: nonEmptyString(root.goal, "goal"),
    expectedHead,
    scope: {
      include: stringArray(scope.include, "scope.include", false),
      exclude: stringArray(scope.exclude, "scope.exclude"),
    },
    invariants: stringArray(root.invariants, "invariants", false),
    acceptance,
    forbiddenFutureStages: stringArray(root.forbiddenFutureStages, "forbiddenFutureStages"),
    allowedChecks,
  };
}

export function parseEngineerCompletionManifest(
  value: unknown,
  manifest: EngineerBlockManifest,
): EngineerCompletionManifest {
  const root = object(value, "Engineer completion manifest");
  exactKeys(root, [
    "schemaVersion", "blockId", "status", "summary", "changedPaths", "acceptanceClaims", "blockers",
  ], "Engineer completion manifest");
  if (root.schemaVersion !== 1) throw new Error("Engineer completion manifest schemaVersion must be 1");
  if (root.blockId !== manifest.blockId) throw new Error("Engineer completion manifest blockId does not match the run");
  if (root.status !== "candidate" && root.status !== "blocked" && root.status !== "plan-conflict") {
    throw new Error("Engineer completion manifest status is unsupported");
  }
  const known = new Set(manifest.acceptance.map(({ id }) => id));
  const claims = objectArray(root.acceptanceClaims, "acceptanceClaims").map((item, index) => {
    exactKeys(item, ["acceptanceId", "claim", "evidence"], `acceptanceClaims[${index}]`);
    const acceptanceId = nonEmptyString(item.acceptanceId, `acceptanceClaims[${index}].acceptanceId`);
    if (!known.has(acceptanceId)) throw new Error(`acceptanceClaims references unknown item '${acceptanceId}'`);
    return {
      acceptanceId,
      claim: nonEmptyString(item.claim, `acceptanceClaims[${index}].claim`),
      evidence: stringArray(item.evidence, `acceptanceClaims[${index}].evidence`, false),
    };
  });
  if (new Set(claims.map(({ acceptanceId }) => acceptanceId)).size !== claims.length) {
    throw new Error("acceptanceClaims must contain each acceptance id only once");
  }
  if (root.status === "candidate" && claims.length !== known.size) {
    throw new Error("candidate completion must claim every acceptance item");
  }
  const blockers = stringArray(root.blockers, "blockers");
  if (root.status !== "candidate" && blockers.length === 0) {
    throw new Error("blocked or plan-conflict completion must describe a blocker");
  }
  return {
    schemaVersion: 1,
    blockId: manifest.blockId,
    status: root.status,
    summary: nonEmptyString(root.summary, "summary"),
    changedPaths: stringArray(root.changedPaths, "changedPaths"),
    acceptanceClaims: claims,
    blockers,
  };
}

export function parseEngineerCheckResult(
  value: unknown,
  manifest: EngineerBlockManifest,
): EngineerCheckResult {
  const root = object(value, "Engineer check result");
  exactKeys(root, ["schemaVersion", "checkId", "argv", "status", "exitCode", "durationMs", "output"], "Engineer check result");
  if (root.schemaVersion !== 1) throw new Error("Engineer check result schemaVersion must be 1");
  const checkId = nonEmptyString(root.checkId, "checkId");
  const allowed = manifest.allowedChecks.find(({ id }) => id === checkId);
  if (!allowed) throw new Error(`Engineer check result references unknown check '${checkId}'`);
  const argv = stringArray(root.argv, "argv", false);
  if (argv.length !== allowed.argv.length || argv.some((part, index) => part !== allowed.argv[index])) {
    throw new Error(`Engineer check result argv does not match allowed check '${checkId}'`);
  }
  const statuses = new Set(["passed", "failed", "timed-out", "spawn-error"]);
  if (typeof root.status !== "string" || !statuses.has(root.status)) {
    throw new Error("Engineer check result status is unsupported");
  }
  if (root.exitCode !== null && (typeof root.exitCode !== "number" || !Number.isInteger(root.exitCode))) {
    throw new Error("Engineer check result exitCode must be an integer or null");
  }
  if (root.status === "passed" && root.exitCode !== 0) {
    throw new Error("A passed check must have exitCode 0");
  }
  if ((root.status === "timed-out" || root.status === "spawn-error") && root.exitCode !== null) {
    throw new Error(`${root.status} check must have a null exitCode`);
  }
  if (typeof root.durationMs !== "number" || !Number.isInteger(root.durationMs) || root.durationMs < 0) {
    throw new Error("Engineer check result durationMs must be a non-negative integer");
  }
  const output = object(root.output, "output");
  const hasRetainedPath = "retainedPath" in output;
  exactKeys(output, hasRetainedPath ? ["inline", "truncated", "retainedPath"] : ["inline", "truncated"], "output");
  if (typeof output.inline !== "string" || output.inline.length > 20_000) {
    throw new Error("output.inline must be a string no longer than 20000 characters");
  }
  if (typeof output.truncated !== "boolean") throw new Error("output.truncated must be a boolean");
  if (output.truncated !== hasRetainedPath) {
    throw new Error("truncated output must have one retainedPath and complete output must not have one");
  }
  const parsedOutput = {
    inline: output.inline,
    truncated: output.truncated,
    ...(hasRetainedPath ? { retainedPath: nonEmptyString(output.retainedPath, "output.retainedPath") } : {}),
  };
  return {
    schemaVersion: 1,
    checkId,
    argv,
    status: root.status as EngineerCheckResult["status"],
    exitCode: root.exitCode as number | null,
    durationMs: root.durationMs,
    output: parsedOutput,
  };
}

export function parseEngineerVerifierVerdict(
  value: unknown,
  manifest: EngineerBlockManifest,
): EngineerVerifierVerdict {
  const root = object(value, "Engineer verifier verdict");
  const baseKeys = ["schemaVersion", "blockId", "status", "items"];
  const hasCorrection = "correctionPacket" in root;
  exactKeys(root, hasCorrection ? [...baseKeys, "correctionPacket"] : baseKeys, "Engineer verifier verdict");
  if (root.schemaVersion !== 1) throw new Error("Engineer verifier verdict schemaVersion must be 1");
  if (root.blockId !== manifest.blockId) throw new Error("Engineer verifier verdict blockId does not match the run");
  const statuses = new Set(["ready-for-architect-review", "correction-required", "blocked", "plan-conflict"]);
  if (typeof root.status !== "string" || !statuses.has(root.status)) {
    throw new Error("Engineer verifier verdict status is unsupported");
  }
  const known = new Set(manifest.acceptance.map(({ id }) => id));
  const verdicts = new Set<AcceptanceVerdict>([
    "verified", "partial", "missing", "contradicted", "unproven", "plan-conflict",
  ]);
  const items = objectArray(root.items, "items").map((item, index) => {
    exactKeys(item, ["acceptanceId", "verdict", "reason", "evidence"], `items[${index}]`);
    const acceptanceId = nonEmptyString(item.acceptanceId, `items[${index}].acceptanceId`);
    if (!known.has(acceptanceId)) throw new Error(`items references unknown acceptance '${acceptanceId}'`);
    if (typeof item.verdict !== "string" || !verdicts.has(item.verdict as AcceptanceVerdict)) {
      throw new Error(`items[${index}].verdict is unsupported`);
    }
    return {
      acceptanceId,
      verdict: item.verdict as AcceptanceVerdict,
      reason: nonEmptyString(item.reason, `items[${index}].reason`),
      evidence: stringArray(item.evidence, `items[${index}].evidence`),
    };
  });
  if (items.length !== known.size || new Set(items.map(({ acceptanceId }) => acceptanceId)).size !== known.size) {
    throw new Error("verifier must classify every acceptance item exactly once");
  }
  if (root.status === "ready-for-architect-review" && items.some(({ verdict }) => verdict !== "verified")) {
    throw new Error("ready-for-architect-review requires every acceptance item to be verified");
  }
  if (root.status === "plan-conflict" && !items.some(({ verdict }) => verdict === "plan-conflict")) {
    throw new Error("plan-conflict status requires a plan-conflict item");
  }
  if ((root.status === "correction-required") !== hasCorrection) {
    throw new Error("correctionPacket is required only for correction-required status");
  }
  let correctionPacket: EngineerCorrectionPacket | undefined;
  if (hasCorrection) {
    const packet = object(root.correctionPacket, "correctionPacket");
    exactKeys(packet, ["instructions", "missingEvidence", "failedCheckIds"], "correctionPacket");
    const knownChecks = new Set(manifest.allowedChecks.map(({ id }) => id));
    const failedCheckIds = stringArray(packet.failedCheckIds, "correctionPacket.failedCheckIds");
    for (const id of failedCheckIds) {
      if (!knownChecks.has(id)) throw new Error(`correctionPacket references unknown check '${id}'`);
    }
    correctionPacket = {
      instructions: stringArray(packet.instructions, "correctionPacket.instructions", false),
      missingEvidence: stringArray(packet.missingEvidence, "correctionPacket.missingEvidence"),
      failedCheckIds,
    };
  }
  return {
    schemaVersion: 1,
    blockId: manifest.blockId,
    status: root.status as EngineerVerifierVerdict["status"],
    items,
    ...(correctionPacket ? { correctionPacket } : {}),
  };
}

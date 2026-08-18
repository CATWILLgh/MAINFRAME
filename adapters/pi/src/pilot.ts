import path from "node:path";
import { fileURLToPath } from "node:url";

import { loadProfile } from "./config.js";
import { verifyPiCli } from "./preflight.js";
import { listAvailableModels, runBusinessAnalysis } from "./profiles/business-analyst/runtime.js";

const ADAPTER_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name);
  return index < 0 ? undefined : process.argv[index + 1];
}

function argumentsFor(name: string): string[] {
  return process.argv.flatMap((argument, index) => argument === name && process.argv[index + 1]
    ? [process.argv[index + 1]!]
    : []);
}

function positiveIntegerArgument(name: string): number | undefined {
  const raw = argument(name);
  if (raw === undefined) return undefined;
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error(`${name} must be a positive integer`);
  return parsed;
}

async function main(): Promise<void> {
  await verifyPiCli();
  if (process.argv.includes("--list-models")) {
    console.log(JSON.stringify(await listAvailableModels(), null, 2));
    return;
  }

  const configPath = path.resolve(
    argument("--config") ?? path.join(ADAPTER_ROOT, "config", "profiles.local.json"),
  );
  const configured = await loadProfile(configPath, argument("--profile") ?? "business-analysis");
  const projectRoot = path.resolve(argument("--project") ?? "test/fixtures/synthetic-ba-project");
  const initiative = argument("--initiative") ?? "order-handoff";
  const statements = argumentsFor("--statement");
  const entryPaths = argumentsFor("--entry");
  const externalInputPaths = argumentsFor("--input-file").map((inputPath) => path.resolve(inputPath));
  const freshSession = process.argv.includes("--fresh-session");
  const timeoutMs = positiveIntegerArgument("--timeout-ms");
  const maxTurns = positiveIntegerArgument("--max-turns");
  const result = await runBusinessAnalysis({
    projectRoot,
    initiative,
    ...(statements.length ? { statements } : {}),
    ...(entryPaths.length ? { entryPaths } : {}),
    ...(externalInputPaths.length ? { externalInputPaths } : {}),
    ...(freshSession ? { freshSession: true } : {}),
    ...(timeoutMs ? { timeoutMs } : {}),
    ...(maxTurns ? { maxTurns } : {}),
    ...configured,
  });
  console.log(JSON.stringify(result, null, 2));
  if (result.run_status !== "complete") process.exitCode = 1;
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

import path from "node:path";

import { loadProfile } from "./config.js";
import { listAvailableModels, runBusinessAnalysis } from "./runtime.js";

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name);
  return index < 0 ? undefined : process.argv[index + 1];
}

async function main(): Promise<void> {
  if (process.argv.includes("--list-models")) {
    console.log(JSON.stringify(await listAvailableModels(), null, 2));
    return;
  }

  const configPath = path.resolve(argument("--config") ?? "config/profiles.local.json");
  const configured = await loadProfile(configPath, argument("--profile") ?? "business-analysis");
  const projectRoot = path.resolve(argument("--project") ?? "test/fixtures/synthetic-ba-project");
  const initiative = argument("--initiative") ?? "order-handoff";
  const entryPath = argument("--entry");
  const externalInputPath = argument("--input-file");
  const freshSession = process.argv.includes("--fresh-session");
  const result = await runBusinessAnalysis({
    projectRoot,
    initiative,
    ...(entryPath ? { entryPath } : {}),
    ...(externalInputPath ? { externalInputPath: path.resolve(externalInputPath) } : {}),
    ...(freshSession ? { freshSession: true } : {}),
    ...configured,
  });
  console.log(JSON.stringify(result, null, 2));
  if (result.run_status !== "complete") process.exitCode = 1;
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

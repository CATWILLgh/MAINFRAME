import { resolveProjectRoot } from "./paths.js";
import { acquireEngineerWriterLock, inspectEngineerGitState } from "./profiles/engineer/preflight.js";
import { commitAcceptedEngineerBlock, loadActiveEngineerManifest } from "./profiles/engineer/session-state.js";

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name);
  return index < 0 ? undefined : process.argv[index + 1];
}

async function main(): Promise<void> {
  const projectRoot = await resolveProjectRoot(argument("--project") ?? process.cwd());
  const message = argument("--message");
  if (!message) throw new Error("--message is required");
  const facts = await inspectEngineerGitState(projectRoot);
  const manifest = await loadActiveEngineerManifest(facts);
  const lock = await acquireEngineerWriterLock(facts, manifest.blockId);
  try {
    console.log(JSON.stringify(await commitAcceptedEngineerBlock(facts, message), null, 2));
  } finally {
    await lock.release();
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

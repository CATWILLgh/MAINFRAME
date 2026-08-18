import { execFile } from "node:child_process";
import { appendFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const RUNTIME_PATTERN = ".agents/runtime/pi/";

async function git(projectRoot: string, args: string[]): Promise<string> {
  const result = await execFileAsync("git", ["-C", projectRoot, ...args], { encoding: "utf8" });
  return result.stdout.trim();
}

export async function protectProjectRuntime(projectRoot: string): Promise<void> {
  try {
    if ((await git(projectRoot, ["rev-parse", "--is-inside-work-tree"])) !== "true") return;
  } catch {
    return;
  }
  const tracked = await git(projectRoot, ["ls-files", "--", RUNTIME_PATTERN]);
  if (tracked) {
    throw new Error(`Pi runtime path is already tracked by Git; remove it from the index before running:\n${tracked}`);
  }
  try {
    await git(projectRoot, ["check-ignore", "-q", `${RUNTIME_PATTERN}.mainframe-probe`]);
    return;
  } catch {
    // Install a repository-local ignore. This does not modify tracked project files.
  }
  const excludePath = await git(projectRoot, ["rev-parse", "--git-path", "info/exclude"]);
  const absolute = path.isAbsolute(excludePath) ? excludePath : path.join(projectRoot, excludePath);
  await mkdir(path.dirname(absolute), { recursive: true });
  const current = await readFile(absolute, "utf8").catch(() => "");
  if (!current.split("\n").includes(RUNTIME_PATTERN)) {
    await appendFile(absolute, `${current && !current.endsWith("\n") ? "\n" : ""}${RUNTIME_PATTERN}\n`);
  }
  try {
    await git(projectRoot, ["check-ignore", "-q", `${RUNTIME_PATTERN}.mainframe-probe`]);
  } catch {
    throw new Error("Could not protect the Pi runtime path with the repository-local Git exclude");
  }
}

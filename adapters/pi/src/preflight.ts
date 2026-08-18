import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
export const EXPECTED_PI_VERSION = "0.84.2";

export function parsePiVersion(output: string): string {
  const match = /(?:^|\s)(\d+\.\d+\.\d+)(?:\s|$)/.exec(output.trim());
  if (!match?.[1]) throw new Error(`Could not parse Pi version from: ${output.trim() || "empty output"}`);
  return match[1];
}

export async function verifyPiCli(): Promise<void> {
  let stdout: string;
  try {
    stdout = (await execFileAsync("pi", ["--version"], { encoding: "utf8", timeout: 10_000 })).stdout;
  } catch (error) {
    throw new Error(`Global Pi CLI is unavailable: ${error instanceof Error ? error.message : String(error)}`);
  }
  const actual = parsePiVersion(stdout);
  if (actual !== EXPECTED_PI_VERSION) {
    throw new Error(`Pi CLI ${actual} is incompatible with the pinned adapter SDK ${EXPECTED_PI_VERSION}`);
  }
}

import { createHash } from "node:crypto";
import { mkdir, readFile, realpath, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import { isInside, resolveProjectRoot } from "./paths.js";

const MAX_INPUT_BYTES = 512_000;

export async function stageExternalInput(projectRoot: string, sourcePath: string): Promise<string> {
  const root = await resolveProjectRoot(projectRoot);
  const source = await realpath(sourcePath);
  const details = await stat(source);
  if (!details.isFile()) throw new Error("External input is not a file");
  if (details.size > MAX_INPUT_BYTES) throw new Error(`External input exceeds ${MAX_INPUT_BYTES} bytes`);

  const content = await readFile(source);
  if (content.includes(0)) throw new Error("External input must be a text file");

  const inputsDirectory = path.join(root, ".agents", "runtime", "pi", "inputs");
  await mkdir(inputsDirectory, { recursive: true });
  const resolvedInputs = await realpath(inputsDirectory);
  if (!isInside(root, resolvedInputs)) throw new Error("Pi input directory resolves outside the project");

  const digest = createHash("sha256").update(content).digest("hex");
  const destination = path.join(resolvedInputs, `${digest}.md`);
  try {
    await writeFile(destination, content, { flag: "wx", mode: 0o600 });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
    const existing = await readFile(destination);
    if (!existing.equals(content)) throw new Error("Existing staged input does not match its content hash");
  }
  return path.relative(root, destination).split(path.sep).join("/");
}

import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

import { resolveProjectRoot } from "./paths.js";
import { EXCLUDED_DIRECTORY_NAMES, isExcludedRelativePath, normalizeRelative } from "./project-policy.js";

export interface ProjectMapFile {
  path: string;
  bytes: number;
  sha256: string;
}

export interface ProjectMap {
  schemaVersion: 2;
  initiative: string;
  entryPath: string;
  generatedAt: string;
  files: ProjectMapFile[];
  excludedDirectories: string[];
}

async function walk(root: string, directory: string, files: ProjectMapFile[]): Promise<void> {
  const entries = await readdir(directory, { withFileTypes: true });
  entries.sort((left, right) => left.name.localeCompare(right.name));

  for (const entry of entries) {
    if (entry.isSymbolicLink()) continue;

    const absolute = path.join(directory, entry.name);
    const relative = normalizeRelative(path.relative(root, absolute));
    if (isExcludedRelativePath(relative)) continue;
    if (entry.isDirectory() && EXCLUDED_DIRECTORY_NAMES.has(entry.name)) continue;
    if (entry.isDirectory()) {
      await walk(root, absolute, files);
      continue;
    }
    if (!entry.isFile()) continue;

    const details = await stat(absolute);
    const content = await readFile(absolute);
    files.push({
      path: relative,
      bytes: details.size,
      sha256: createHash("sha256").update(content).digest("hex"),
    });
  }
}

export async function buildProjectMap(
  projectRoot: string,
  initiative: string,
  entryPath = `docs/initiatives/${initiative}/requirements.md`,
): Promise<ProjectMap> {
  const root = await resolveProjectRoot(projectRoot);
  const files: ProjectMapFile[] = [];
  await walk(root, root, files);
  return {
    schemaVersion: 2,
    initiative,
    entryPath,
    generatedAt: new Date().toISOString(),
    files,
    excludedDirectories: [...EXCLUDED_DIRECTORY_NAMES].sort(),
  };
}

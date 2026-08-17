import { readdir, readFile, realpath, stat } from "node:fs/promises";
import path from "node:path";

import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { isInside, resolveProjectRoot } from "./paths.js";
import {
  EXCLUDED_DIRECTORY_NAMES,
  isExcludedRelativePath,
  isModelExcludedRelativePath,
  normalizeRelative,
} from "./project-policy.js";

const MAX_FILE_BYTES = 512_000;
const MAX_RESULTS = 40;
const MAX_DIRECTORY_ENTRIES = 80;
async function resolveInside(
  projectRoot: string,
  requestedPath: string,
  allowedRuntimeInput?: string,
): Promise<string> {
  const root = await resolveProjectRoot(projectRoot);
  const candidate = path.resolve(root, requestedPath || ".");
  if (!isInside(root, candidate)) throw new Error("Requested path is outside the project");
  if (isModelExcludedRelativePath(normalizeRelative(path.relative(root, candidate)), allowedRuntimeInput)) {
    throw new Error("Requested path is excluded from the business-analysis profile");
  }
  const resolved = await realpath(candidate);
  if (!isInside(root, resolved)) throw new Error("Requested path resolves outside the project");
  if (isModelExcludedRelativePath(normalizeRelative(path.relative(root, resolved)), allowedRuntimeInput)) {
    throw new Error("Requested path is excluded from the business-analysis profile");
  }
  return resolved;
}

export async function readProjectFile(
  projectRoot: string,
  requestedPath: string,
  startLine = 1,
  endLine?: number,
  allowedRuntimeInput?: string,
): Promise<string> {
  const resolved = await resolveInside(projectRoot, requestedPath, allowedRuntimeInput);
  const details = await stat(resolved);
  if (!details.isFile()) throw new Error("Requested path is not a file");
  if (details.size > MAX_FILE_BYTES) throw new Error(`File exceeds ${MAX_FILE_BYTES} bytes`);
  const content = await readFile(resolved, "utf8");
  if (content.includes("\0")) throw new Error("Binary files are not readable by this profile");
  const lines = content.split("\n");
  const first = Math.max(1, startLine);
  const last = Math.min(lines.length, endLine ?? first + 239);
  return lines
    .slice(first - 1, last)
    .map((line, index) => `${first + index}: ${line}`)
    .join("\n");
}

async function collectFiles(root: string, directory: string, output: string[]): Promise<void> {
  const entries = await readdir(directory, { withFileTypes: true });
  entries.sort((left, right) => left.name.localeCompare(right.name));
  for (const entry of entries) {
    if (entry.isSymbolicLink()) continue;
    const absolute = path.join(directory, entry.name);
    const relative = normalizeRelative(path.relative(root, absolute));
    if (isExcludedRelativePath(relative)) continue;
    if (entry.isDirectory() && EXCLUDED_DIRECTORY_NAMES.has(entry.name)) continue;
    if (entry.isDirectory()) {
      await collectFiles(root, absolute, output);
    } else if (entry.isFile()) {
      output.push(relative);
    }
  }
}

export async function findProjectFiles(projectRoot: string, query: string): Promise<string[]> {
  const root = await resolveProjectRoot(projectRoot);
  const files: string[] = [];
  await collectFiles(root, root, files);
  const normalized = query.toLowerCase();
  return files.filter((file) => file.toLowerCase().includes(normalized)).slice(0, MAX_RESULTS);
}

export async function grepProject(
  projectRoot: string,
  query: string,
  requestedPath = ".",
  allowedRuntimeInput?: string,
): Promise<string[]> {
  if (!query) throw new Error("Search query must not be empty");
  const root = await resolveProjectRoot(projectRoot);
  const searchRoot = await resolveInside(root, requestedPath, allowedRuntimeInput);
  const details = await stat(searchRoot);
  const files: string[] = [];
  if (details.isFile()) {
    files.push(path.relative(root, searchRoot).split(path.sep).join("/"));
  } else {
    await collectFiles(root, searchRoot, files);
  }

  const needle = query.toLowerCase();
  const matches: string[] = [];
  for (const relativePath of files) {
    const absolute = path.join(root, relativePath);
    const fileDetails = await stat(absolute);
    if (fileDetails.size > MAX_FILE_BYTES) continue;
    const content = await readFile(absolute, "utf8");
    if (content.includes("\0")) continue;
    for (const [index, line] of content.split("\n").entries()) {
      if (line.toLowerCase().includes(needle)) {
        matches.push(`${relativePath}:${index + 1}: ${line}`);
        if (matches.length >= MAX_RESULTS) return matches;
      }
    }
  }
  return matches;
}

export async function listProjectDirectory(projectRoot: string, requestedPath = "."): Promise<string[]> {
  const root = await resolveProjectRoot(projectRoot);
  const directory = await resolveInside(root, requestedPath);
  if (!(await stat(directory)).isDirectory()) throw new Error("Requested path is not a directory");
  const entries = await readdir(directory, { withFileTypes: true });
  return entries
    .filter((entry) => {
      if (entry.isSymbolicLink()) return false;
      const relative = normalizeRelative(path.relative(root, path.join(directory, entry.name)));
      return !isExcludedRelativePath(relative) && !EXCLUDED_DIRECTORY_NAMES.has(entry.name);
    })
    .sort((left, right) => left.name.localeCompare(right.name))
    .slice(0, MAX_DIRECTORY_ENTRIES)
    .map((entry) => `${entry.isDirectory() ? "directory" : "file"}\t${entry.name}`)
    .concat(entries.length > MAX_DIRECTORY_ENTRIES ? [`… ${entries.length - MAX_DIRECTORY_ENTRIES} more entries omitted`] : []);
}

function textResult(text: string) {
  return { content: [{ type: "text" as const, text }], details: {} };
}

export function createProjectTools(projectRoot: string, allowedRuntimeInput?: string) {
  return [
    defineTool({
      name: "project_read",
      label: "Read project file",
      description: "Read a bounded line range from a text file inside the assigned project.",
      parameters: Type.Object({
        path: Type.String(),
        startLine: Type.Optional(Type.Integer({ minimum: 1 })),
        endLine: Type.Optional(Type.Integer({ minimum: 1 })),
      }),
      execute: async (_id, params) =>
        textResult(
          await readProjectFile(
            projectRoot,
            params.path,
            params.startLine,
            params.endLine,
            allowedRuntimeInput,
          ),
        ),
    }),
    defineTool({
      name: "project_find",
      label: "Find project files",
      description: "Find up to 40 project-relative file paths containing a targeted literal case-insensitive fragment.",
      parameters: Type.Object({ query: Type.String() }),
      execute: async (_id, params) => textResult((await findProjectFiles(projectRoot, params.query)).join("\n")),
    }),
    defineTool({
      name: "project_grep",
      label: "Search project text",
      description: "Return up to 40 targeted literal case-insensitive text matches. Narrow path when possible.",
      parameters: Type.Object({
        query: Type.String(),
        path: Type.Optional(Type.String()),
      }),
      execute: async (_id, params) =>
        textResult(
          (await grepProject(projectRoot, params.query, params.path, allowedRuntimeInput)).join("\n"),
        ),
    }),
    defineTool({
      name: "project_list",
      label: "List project directory",
      description: "List at most 80 direct children of a directory. Prefer project_find for large trees.",
      parameters: Type.Object({ path: Type.Optional(Type.String()) }),
      execute: async (_id, params) =>
        textResult((await listProjectDirectory(projectRoot, params.path)).join("\n")),
    }),
  ];
}

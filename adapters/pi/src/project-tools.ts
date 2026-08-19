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

export interface OffsetPage<T> {
  total: number;
  offset: number;
  returned: T[];
  nextOffset: number | null;
  truncated: boolean;
}

export interface LinePage {
  totalLines: number;
  startLine: number;
  endLine: number;
  returned: string[];
  nextStartLine: number | null;
  truncated: boolean;
}

function offsetPage<T>(items: T[], offset: number, limit: number): OffsetPage<T> {
  const boundedOffset = Math.max(0, offset);
  const returned = items.slice(boundedOffset, boundedOffset + limit);
  const nextOffset = boundedOffset + returned.length < items.length
    ? boundedOffset + returned.length
    : null;
  return {
    total: items.length,
    offset: boundedOffset,
    returned,
    nextOffset,
    truncated: nextOffset !== null,
  };
}

async function resolveInside(
  projectRoot: string,
  requestedPath: string,
  allowedRuntimeInput?: string,
): Promise<string> {
  const root = await resolveProjectRoot(projectRoot);
  const candidate = path.resolve(root, requestedPath || ".");
  if (!isInside(root, candidate)) throw new Error("Requested path is outside the project");
  if (isModelExcludedRelativePath(normalizeRelative(path.relative(root, candidate)), allowedRuntimeInput)) {
    throw new Error("Requested path is excluded from project navigation");
  }
  const resolved = await realpath(candidate);
  if (!isInside(root, resolved)) throw new Error("Requested path resolves outside the project");
  if (isModelExcludedRelativePath(normalizeRelative(path.relative(root, resolved)), allowedRuntimeInput)) {
    throw new Error("Requested path is excluded from project navigation");
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

export async function readProjectFilePage(
  projectRoot: string,
  requestedPath: string,
  startLine = 1,
  endLine?: number,
  allowedRuntimeInput?: string,
): Promise<LinePage> {
  if (endLine !== undefined && endLine < startLine) {
    throw new Error("endLine must be greater than or equal to startLine");
  }
  const resolved = await resolveInside(projectRoot, requestedPath, allowedRuntimeInput);
  const details = await stat(resolved);
  if (!details.isFile()) throw new Error("Requested path is not a file");
  if (details.size > MAX_FILE_BYTES) throw new Error(`File exceeds ${MAX_FILE_BYTES} bytes`);
  const content = await readFile(resolved, "utf8");
  if (content.includes("\0")) throw new Error("Binary files are not readable by this profile");
  const lines = content.split("\n");
  const first = Math.max(1, startLine);
  const requestedLast = endLine ?? first + 239;
  const last = Math.min(lines.length, requestedLast, first + 239);
  const returned = first > lines.length
    ? []
    : lines.slice(first - 1, last).map((line, index) => `${first + index}: ${line}`);
  const actualEnd = returned.length ? first + returned.length - 1 : Math.min(first - 1, lines.length);
  const nextStartLine = actualEnd < lines.length ? actualEnd + 1 : null;
  return {
    totalLines: lines.length,
    startLine: first,
    endLine: actualEnd,
    returned,
    nextStartLine,
    truncated: nextStartLine !== null,
  };
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
  return (await findProjectFilesPage(projectRoot, query)).returned;
}

export async function findProjectFilesPage(
  projectRoot: string,
  query: string,
  offset = 0,
): Promise<OffsetPage<string>> {
  const root = await resolveProjectRoot(projectRoot);
  const files: string[] = [];
  await collectFiles(root, root, files);
  const normalized = query.toLowerCase();
  return offsetPage(files.filter((file) => file.toLowerCase().includes(normalized)), offset, MAX_RESULTS);
}

export async function grepProject(
  projectRoot: string,
  query: string,
  requestedPath = ".",
  allowedRuntimeInput?: string,
): Promise<string[]> {
  return (await grepProjectPage(projectRoot, query, requestedPath, 0, allowedRuntimeInput)).returned;
}

export async function grepProjectPage(
  projectRoot: string,
  query: string,
  requestedPath = ".",
  offset = 0,
  allowedRuntimeInput?: string,
): Promise<OffsetPage<string>> {
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
      }
    }
  }
  return offsetPage(matches, offset, MAX_RESULTS);
}

export async function listProjectDirectory(projectRoot: string, requestedPath = "."): Promise<string[]> {
  const page = await listProjectDirectoryPage(projectRoot, requestedPath);
  return page.returned.concat(page.truncated ? [`… ${page.total - page.returned.length} more entries omitted`] : []);
}

export async function listProjectDirectoryPage(
  projectRoot: string,
  requestedPath = ".",
  offset = 0,
): Promise<OffsetPage<string>> {
  const root = await resolveProjectRoot(projectRoot);
  const directory = await resolveInside(root, requestedPath);
  if (!(await stat(directory)).isDirectory()) throw new Error("Requested path is not a directory");
  const entries = await readdir(directory, { withFileTypes: true });
  const visible = entries
    .filter((entry) => {
      if (entry.isSymbolicLink()) return false;
      const relative = normalizeRelative(path.relative(root, path.join(directory, entry.name)));
      return !isExcludedRelativePath(relative) && !EXCLUDED_DIRECTORY_NAMES.has(entry.name);
    })
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((entry) => `${entry.isDirectory() ? "directory" : "file"}\t${entry.name}`);
  return offsetPage(visible, offset, MAX_DIRECTORY_ENTRIES);
}

function textResult(value: unknown) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return { content: [{ type: "text" as const, text }], details: {} };
}

export function createProjectTools(projectRoot: string, allowedRuntimeInput?: string) {
  return [
    defineTool({
      name: "project_read",
      label: "Read project file",
      description: "Read at most 240 lines. The result reports totalLines, truncation, and nextStartLine; continue when complete coverage matters.",
      parameters: Type.Object({
        path: Type.String(),
        startLine: Type.Optional(Type.Integer({ minimum: 1 })),
        endLine: Type.Optional(Type.Integer({ minimum: 1 })),
      }),
      execute: async (_id, params) =>
        textResult(
          await readProjectFilePage(
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
      description: "Find a bounded page of project-relative paths. The result reports total, truncation, and nextOffset.",
      parameters: Type.Object({
        query: Type.String(),
        offset: Type.Optional(Type.Integer({ minimum: 0 })),
      }),
      execute: async (_id, params) =>
        textResult(await findProjectFilesPage(projectRoot, params.query, params.offset)),
    }),
    defineTool({
      name: "project_grep",
      label: "Search project text",
      description: "Return a bounded page of literal case-insensitive matches. Narrow path when possible and follow nextOffset when completeness matters.",
      parameters: Type.Object({
        query: Type.String(),
        path: Type.Optional(Type.String()),
        offset: Type.Optional(Type.Integer({ minimum: 0 })),
      }),
      execute: async (_id, params) =>
        textResult(
          await grepProjectPage(
            projectRoot,
            params.query,
            params.path,
            params.offset,
            allowedRuntimeInput,
          ),
        ),
    }),
    defineTool({
      name: "project_list",
      label: "List project directory",
      description: "List a bounded page of direct children with total, truncation, and nextOffset. Prefer project_find for large trees.",
      parameters: Type.Object({
        path: Type.Optional(Type.String()),
        offset: Type.Optional(Type.Integer({ minimum: 0 })),
      }),
      execute: async (_id, params) =>
        textResult(await listProjectDirectoryPage(projectRoot, params.path, params.offset)),
    }),
  ];
}

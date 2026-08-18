import { createHash } from "node:crypto";
import { lstat, mkdir, open, readFile, realpath, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import { withFileMutationQueue } from "@earendil-works/pi-coding-agent";

import { isInside, resolveProjectRoot } from "../../paths.js";
import { isModelExcludedRelativePath, normalizeRelative } from "../../project-policy.js";
import type { EngineerBlockManifest } from "./contracts.js";

const MAX_ENGINEER_FILE_BYTES = 2_000_000;

export interface EngineerObservedFile {
  path: string;
  version: string;
  content: string;
}

export interface EngineerExactEdit {
  oldText: string;
  newText: string;
}

function version(content: Buffer | string): string {
  return createHash("sha256").update(content).digest("hex");
}

function requireText(content: Buffer, owner: string): string {
  if (content.length > MAX_ENGINEER_FILE_BYTES) throw new Error(`${owner} exceeds ${MAX_ENGINEER_FILE_BYTES} bytes`);
  if (content.includes(0)) throw new Error(`${owner} is binary`);
  return content.toString("utf8");
}

function countOccurrences(content: string, needle: string): number {
  let count = 0;
  let offset = 0;
  while (true) {
    const index = content.indexOf(needle, offset);
    if (index < 0) return count;
    count += 1;
    offset = index + Math.max(needle.length, 1);
  }
}

export class EngineerWorkspace {
  private readonly observations = new Map<string, string>();

  private constructor(
    readonly projectRoot: string,
    private readonly manifest: EngineerBlockManifest,
  ) {}

  static async create(projectRoot: string, manifest: EngineerBlockManifest): Promise<EngineerWorkspace> {
    return new EngineerWorkspace(await resolveProjectRoot(projectRoot), manifest);
  }

  private relative(requestedPath: string): string {
    if (!requestedPath || path.isAbsolute(requestedPath)) throw new Error("File path must be project-relative");
    const candidate = path.resolve(this.projectRoot, requestedPath);
    if (!isInside(this.projectRoot, candidate)) throw new Error("File path is outside the project");
    const relative = normalizeRelative(path.relative(this.projectRoot, candidate));
    if (!relative || isModelExcludedRelativePath(relative)) throw new Error(`File path is excluded: ${relative || "."}`);
    const included = this.manifest.scope.include.some((pattern) => path.matchesGlob(relative, normalizeRelative(pattern)));
    const excluded = this.manifest.scope.exclude.some((pattern) => path.matchesGlob(relative, normalizeRelative(pattern)));
    if (!included || excluded) throw new Error(`File path is outside the block scope: ${relative}`);
    return relative;
  }

  private async existingFile(requestedPath: string): Promise<{ relative: string; absolute: string }> {
    const relative = this.relative(requestedPath);
    const candidate = path.join(this.projectRoot, relative);
    if ((await lstat(candidate)).isSymbolicLink()) throw new Error(`Symbolic-link files are not writable: ${relative}`);
    const absolute = await realpath(candidate);
    if (!isInside(this.projectRoot, absolute) || !(await stat(absolute)).isFile()) {
      throw new Error(`Path is outside the project or not a file: ${relative}`);
    }
    return { relative, absolute };
  }

  async observe(requestedPath: string): Promise<EngineerObservedFile> {
    const { relative, absolute } = await this.existingFile(requestedPath);
    const raw = await readFile(absolute);
    const content = requireText(raw, relative);
    const observedVersion = version(raw);
    this.observations.set(relative, observedVersion);
    return { path: relative, version: observedVersion, content };
  }

  async edit(requestedPath: string, observedVersion: string, edits: EngineerExactEdit[]): Promise<EngineerObservedFile> {
    const { relative, absolute } = await this.existingFile(requestedPath);
    return withFileMutationQueue(absolute, async () => {
      const recorded = this.observations.get(relative);
      if (!recorded || recorded !== observedVersion) throw new Error(`Re-read before editing ${relative}`);
      const raw = await readFile(absolute);
      const currentVersion = version(raw);
      if (currentVersion !== recorded) {
        this.observations.delete(relative);
        throw new Error(`File changed after it was read: ${relative}`);
      }
      if (!edits.length) throw new Error("At least one exact edit is required");
      const content = requireText(raw, relative);
      const replacements = edits.map((edit, index) => {
        if (!edit.oldText) throw new Error(`edits[${index}].oldText must not be empty`);
        const occurrences = countOccurrences(content, edit.oldText);
        if (occurrences !== 1) {
          throw new Error(`edits[${index}].oldText must occur exactly once in ${relative}; found ${occurrences}`);
        }
        const start = content.indexOf(edit.oldText);
        return { start, end: start + edit.oldText.length, newText: edit.newText };
      });
      const ordered = [...replacements].sort((left, right) => left.start - right.start);
      for (let index = 1; index < ordered.length; index += 1) {
        if (ordered[index]!.start < ordered[index - 1]!.end) throw new Error("Exact edits must not overlap");
      }
      let next = content;
      for (const replacement of ordered.reverse()) {
        next = `${next.slice(0, replacement.start)}${replacement.newText}${next.slice(replacement.end)}`;
      }
      await writeFile(absolute, next, { encoding: "utf8" });
      const nextVersion = version(next);
      this.observations.set(relative, nextVersion);
      return { path: relative, version: nextVersion, content: next };
    });
  }

  async createFile(requestedPath: string, content: string): Promise<EngineerObservedFile> {
    const relative = this.relative(requestedPath);
    const absolute = path.join(this.projectRoot, relative);
    return withFileMutationQueue(absolute, async () => {
      try {
        await lstat(absolute);
        throw new Error(`File already exists; use exact edit: ${relative}`);
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      }
      if (Buffer.byteLength(content) > MAX_ENGINEER_FILE_BYTES || content.includes("\0")) {
        throw new Error(`New file must be UTF-8 text no larger than ${MAX_ENGINEER_FILE_BYTES} bytes`);
      }
      const parent = path.dirname(absolute);
      await mkdir(parent, { recursive: true, mode: 0o755 });
      const resolvedParent = await realpath(parent);
      if (!isInside(this.projectRoot, resolvedParent)) throw new Error(`New file parent resolves outside the project: ${relative}`);
      const handle = await open(absolute, "wx", 0o644);
      try {
        await handle.writeFile(content, { encoding: "utf8" });
      } finally {
        await handle.close();
      }
      const observedVersion = version(content);
      this.observations.set(relative, observedVersion);
      return { path: relative, version: observedVersion, content };
    });
  }
}

import { constants } from "node:fs";
import { open, readdir } from "node:fs/promises";
import path from "node:path";

import { ensureInitiativeDirectory, ensureReviewsDirectory } from "./paths.js";

export interface SavedReview {
  absolutePath: string;
  relativePath: string;
}

export async function saveNextReview(
  projectRoot: string,
  initiative: string,
  markdown: string,
): Promise<SavedReview> {
  const resolved = await ensureInitiativeDirectory(projectRoot, initiative);
  const reviews = await ensureReviewsDirectory(resolved.initiativeDirectory);
  const existing = await readdir(reviews);
  const numbers = existing
    .map((name) => /^(\d{3})\.md$/.exec(name)?.[1])
    .filter((value): value is string => value !== undefined)
    .map(Number);
  let candidateNumber = Math.max(0, ...numbers) + 1;

  while (candidateNumber <= 999) {
    const filename = `${String(candidateNumber).padStart(3, "0")}.md`;
    const absolutePath = path.join(reviews, filename);
    try {
      const handle = await open(
        absolutePath,
        constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | constants.O_NOFOLLOW,
        0o644,
      );
      try {
        await handle.writeFile(markdown.endsWith("\n") ? markdown : `${markdown}\n`, "utf8");
        await handle.sync();
      } finally {
        await handle.close();
      }
      return {
        absolutePath,
        relativePath: path.relative(resolved.projectRoot, absolutePath).split(path.sep).join("/"),
      };
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
      candidateNumber += 1;
    }
  }
  throw new Error("Review sequence is exhausted");
}

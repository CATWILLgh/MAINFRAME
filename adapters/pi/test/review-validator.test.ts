import assert from "node:assert/strict";
import { mkdtemp, mkdir, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { validateEvidenceReferences } from "../src/profiles/business-analyst/review-validator.js";

test("evidence validation accepts project paths through a symlinked project root", async () => {
  const parent = await mkdtemp(path.join(tmpdir(), "mainframe-pi-evidence-root-"));
  const project = path.join(parent, "project");
  const alias = path.join(parent, "project-alias");
  await mkdir(project);
  await writeFile(path.join(project, "evidence.md"), "first\nsecond\n");
  await symlink(project, alias);
  assert.deepEqual(
    await validateEvidenceReferences(alias, ["evidence.md:1-2"], "probe"),
    [],
  );
});

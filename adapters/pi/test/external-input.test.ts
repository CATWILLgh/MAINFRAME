import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { stageExplicitInputPackage, stageExternalInput } from "../src/external-input.js";
import { readProjectFile } from "../src/project-tools.js";

test("an external input is staged immutably and only that runtime file becomes readable", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-target-"));
  const sourceRoot = await mkdtemp(path.join(tmpdir(), "mainframe-pi-source-"));
  const source = path.join(sourceRoot, "requirements.md");
  await writeFile(source, "# External requirements\n\nOriginal source stays separate.\n");

  const staged = await stageExternalInput(root, source);
  assert.match(staged, /^\.agents\/runtime\/pi\/inputs\/[a-f0-9]{64}\.md$/);
  assert.match(await readProjectFile(root, staged, 1, undefined, staged), /External requirements/);
  assert.equal(await readFile(source, "utf8"), "# External requirements\n\nOriginal source stays separate.\n");

  const sibling = path.join(root, ".agents/runtime/pi/inputs/unrelated.md");
  await writeFile(sibling, "must remain private\n");
  await assert.rejects(
    readProjectFile(root, ".agents/runtime/pi/inputs/unrelated.md", 1, undefined, staged),
    /excluded from project navigation/,
  );
});

test("an explicit requirements package preserves only named statements and files", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-package-"));
  const sourceRoot = await mkdtemp(path.join(tmpdir(), "mainframe-pi-package-source-"));
  await mkdir(path.join(root, "docs"), { recursive: true });
  await writeFile(path.join(root, "docs/requirements.md"), "# Project requirements\n\nCancel a shipment.\n");
  const external = path.join(sourceRoot, "pm-notes.md");
  await writeFile(external, "# PM notes\n\nRetry a failed handoff.\n");

  const staged = await stageExplicitInputPackage(root, {
    statements: ["A manager wants manual review."],
    projectPaths: ["docs/requirements.md"],
    externalPaths: [external],
  });
  const content = await readFile(path.join(root, staged), "utf8");
  assert.match(content, /supplied statement/);
  assert.match(content, /A manager wants manual review/);
  assert.match(content, /project file `docs\/requirements\.md`/);
  assert.match(content, /Cancel a shipment/);
  assert.match(content, /supplied external file `pm-notes\.md`/);
  assert.match(content, /Retry a failed handoff/);
  await assert.rejects(stageExplicitInputPackage(root, {}), /requires an explicit requirements statement/);
});

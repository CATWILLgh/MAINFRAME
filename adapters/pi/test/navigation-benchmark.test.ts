import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import {
  buildCorpusIndex,
  generateSyntheticCorpus,
  searchIndex,
} from "../src/navigation-corpus.js";
import {
  findProjectFilesPage,
  grepProject,
  grepProjectPage,
  listProjectDirectoryPage,
  readProjectFilePage,
} from "../src/project-tools.js";

test("project navigation pages expose totals and deterministic continuation", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-cursors-"));
  try {
    for (let index = 0; index < 100; index += 1) {
      await writeFile(path.join(root, `matching-${String(index).padStart(3, "0")}.md`), `line one\nshared needle ${index}\nline three`);
    }

    const foundFirst = await findProjectFilesPage(root, "matching");
    assert.deepEqual(
      { total: foundFirst.total, count: foundFirst.returned.length, next: foundFirst.nextOffset, truncated: foundFirst.truncated },
      { total: 100, count: 40, next: 40, truncated: true },
    );
    const foundLast = await findProjectFilesPage(root, "matching", 80);
    assert.deepEqual(
      { total: foundLast.total, count: foundLast.returned.length, next: foundLast.nextOffset, truncated: foundLast.truncated },
      { total: 100, count: 20, next: null, truncated: false },
    );

    const grepLast = await grepProjectPage(root, "shared needle", ".", 80);
    assert.deepEqual(
      { total: grepLast.total, count: grepLast.returned.length, next: grepLast.nextOffset, truncated: grepLast.truncated },
      { total: 100, count: 20, next: null, truncated: false },
    );

    const listedLast = await listProjectDirectoryPage(root, ".", 80);
    assert.deepEqual(
      { total: listedLast.total, count: listedLast.returned.length, next: listedLast.nextOffset, truncated: listedLast.truncated },
      { total: 100, count: 20, next: null, truncated: false },
    );

    const readLast = await readProjectFilePage(root, "matching-000.md", 3);
    assert.deepEqual(
      { total: readLast.totalLines, start: readLast.startLine, end: readLast.endLine, next: readLast.nextStartLine, truncated: readLast.truncated },
      { total: 3, start: 3, end: 3, next: null, truncated: false },
    );
    assert.deepEqual(readLast.returned, ["3: line three"]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("navigation benchmark exposes the current silent-clipping failure", async () => {
  const corpus = await generateSyntheticCorpus(150_000);
  try {
    const baseline = await grepProject(corpus.root, "classification=binding");
    assert.equal(baseline.length, 40);
    assert(corpus.gold.some(({ id }) => !baseline.some((line) => line.includes(id))));
  } finally {
    await rm(corpus.root, { recursive: true, force: true });
  }
});

test("intersection query recovers every planted fact with exact evidence", async () => {
  const corpus = await generateSyntheticCorpus(150_000);
  try {
    const index = await buildCorpusIndex(corpus.root);
    const matches = searchIndex(index, ["state=active", "classification=binding"]);
    assert.equal(matches.length, corpus.gold.length);
    assert.deepEqual(
      new Set(matches.map(({ text }) => /CONTROL (CTL-\d+)/u.exec(text)?.[1])),
      new Set(corpus.gold.map(({ id }) => id)),
    );
    assert.deepEqual(
      new Set(matches.map(({ path, line }) => `${path}:${line}`)),
      new Set(corpus.gold.map(({ evidence }) => evidence)),
    );
  } finally {
    await rm(corpus.root, { recursive: true, force: true });
  }
});

test("split records require continuation or cross-line correlation", async () => {
  const corpus = await generateSyntheticCorpus(150_000, "split-record");
  try {
    const index = await buildCorpusIndex(corpus.root);
    assert.equal(searchIndex(index, ["state=active", "classification=binding"]).length, 0);
    const states = searchIndex(index, ["state=active"]);
    const classifications = searchIndex(index, ["classification=binding"]);
    assert(states.length > 40);
    assert(classifications.length > 40);
    for (const { id } of corpus.gold) {
      assert(states.some(({ text }) => text.includes(id)));
      assert(classifications.some(({ text }) => text.includes(id)));
    }
  } finally {
    await rm(corpus.root, { recursive: true, force: true });
  }
});

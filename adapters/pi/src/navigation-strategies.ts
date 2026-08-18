import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { searchIndex, type CorpusIndex, type IndexedLine } from "./navigation-corpus.js";
import {
  findProjectFiles,
  grepProject,
  listProjectDirectory,
  readProjectFile,
} from "./project-tools.js";

export type NavigationStrategy = "baseline" | "cursor" | "spill" | "batch" | "hybrid";

const PAGE_SIZE = 40;

function textResult(value: unknown) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return { content: [{ type: "text" as const, text }], details: {} };
}

function page<T>(items: T[], offset: number, limit = PAGE_SIZE) {
  const returned = items.slice(offset, offset + limit);
  const nextOffset = offset + returned.length < items.length ? offset + returned.length : null;
  return { total: items.length, offset, returned, nextOffset, truncated: nextOffset !== null };
}

function formatLine(item: IndexedLine): string {
  return `${item.path}:${item.line}: ${item.text}`;
}

function createBaselineTools(root: string) {
  return [
    defineTool({
      name: "project_read",
      label: "Legacy read",
      description: "Read a bounded range without continuation metadata.",
      parameters: Type.Object({
        path: Type.String(),
        startLine: Type.Optional(Type.Integer({ minimum: 1 })),
        endLine: Type.Optional(Type.Integer({ minimum: 1 })),
      }),
      execute: async (_id, params) =>
        textResult(await readProjectFile(root, params.path, params.startLine, params.endLine)),
    }),
    defineTool({
      name: "project_find",
      label: "Legacy find",
      description: "Return the first forty matching paths without continuation metadata.",
      parameters: Type.Object({ query: Type.String() }),
      execute: async (_id, params) => textResult((await findProjectFiles(root, params.query)).join("\n")),
    }),
    defineTool({
      name: "project_grep",
      label: "Legacy grep",
      description: "Return the first forty matches without continuation metadata.",
      parameters: Type.Object({ query: Type.String(), path: Type.Optional(Type.String()) }),
      execute: async (_id, params) =>
        textResult((await grepProject(root, params.query, params.path)).join("\n")),
    }),
    defineTool({
      name: "project_list",
      label: "Legacy list",
      description: "Return a bounded directory listing without a continuation cursor.",
      parameters: Type.Object({ path: Type.Optional(Type.String()) }),
      execute: async (_id, params) =>
        textResult((await listProjectDirectory(root, params.path)).join("\n")),
    }),
  ];
}

function createCursorTools(index: CorpusIndex) {
  return [
    defineTool({
      name: "nav_grep",
      label: "Paginated text search",
      description: "Search literal text with explicit total and nextOffset. Continue until nextOffset is null when coverage matters.",
      parameters: Type.Object({ query: Type.String(), offset: Type.Optional(Type.Integer({ minimum: 0 })) }),
      execute: async (_id, params) =>
        textResult(page(searchIndex(index, [params.query]).map(formatLine), params.offset ?? 0)),
    }),
    defineTool({
      name: "nav_find",
      label: "Paginated file search",
      description: "Find file names with explicit total and nextOffset.",
      parameters: Type.Object({ query: Type.String(), offset: Type.Optional(Type.Integer({ minimum: 0 })) }),
      execute: async (_id, params) => {
        const query = params.query.toLowerCase();
        return textResult(page(index.files.filter((file) => file.toLowerCase().includes(query)), params.offset ?? 0));
      },
    }),
    defineTool({
      name: "nav_read",
      label: "Paginated file read",
      description: "Read a bounded line range with totalLines and nextStartLine.",
      parameters: Type.Object({
        path: Type.String(),
        startLine: Type.Optional(Type.Integer({ minimum: 1 })),
        endLine: Type.Optional(Type.Integer({ minimum: 1 })),
      }),
      execute: async (_id, params) => {
        const fileLines = index.lines.filter((line) => line.path === params.path);
        const start = params.startLine ?? 1;
        const end = Math.min(params.endLine ?? start + 79, fileLines.length);
        const returned = fileLines.slice(start - 1, end).map(formatLine);
        return textResult({
          totalLines: fileLines.length,
          startLine: start,
          endLine: end,
          returned,
          nextStartLine: end < fileLines.length ? end + 1 : null,
        });
      },
    }),
  ];
}

function createSpillTools(index: CorpusIndex) {
  const spills = new Map<string, string[]>();
  let sequence = 0;
  return [
    defineTool({
      name: "spill_grep",
      label: "Search with retained overflow",
      description: "Search text. Large results return a bounded preview and a locator whose pages can be read with spill_page.",
      parameters: Type.Object({ query: Type.String() }),
      execute: async (_id, params) => {
        const results = searchIndex(index, [params.query]).map(formatLine);
        if (results.length <= PAGE_SIZE) return textResult({ total: results.length, results, locator: null });
        const locator = `spill-${++sequence}`;
        spills.set(locator, results);
        return textResult({
          total: results.length,
          preview: [...results.slice(0, 10), ...results.slice(-10)],
          locator,
          instruction: "Read retained results with spill_page until nextOffset is null.",
        });
      },
    }),
    defineTool({
      name: "spill_page",
      label: "Read retained search page",
      description: "Read a bounded page from a retained search result.",
      parameters: Type.Object({ locator: Type.String(), offset: Type.Optional(Type.Integer({ minimum: 0 })) }),
      execute: async (_id, params) => {
        const results = spills.get(params.locator);
        if (!results) throw new Error("Unknown spill locator");
        return textResult(page(results, params.offset ?? 0));
      },
    }),
  ];
}

function createBatchTools(index: CorpusIndex) {
  return [
    defineTool({
      name: "batch_query",
      label: "Batch project query",
      description: "Run up to eight intersection searches. Every returned line contains all terms in its query.",
      parameters: Type.Object({
        queries: Type.Array(
          Type.Object({ terms: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 6 }) }),
          { minItems: 1, maxItems: 8 },
        ),
      }),
      execute: async (_id, params) => textResult({
        results: params.queries.map(({ terms }) => {
          const matches = searchIndex(index, terms).map(formatLine);
          return { terms, total: matches.length, matches: matches.slice(0, 120), truncated: matches.length > 120 };
        }),
      }),
    }),
  ];
}

export function createStrategyTools(strategy: NavigationStrategy, root: string, index: CorpusIndex) {
  if (strategy === "baseline") return createBaselineTools(root);
  if (strategy === "cursor") return createCursorTools(index);
  if (strategy === "spill") return createSpillTools(index);
  if (strategy === "batch") return createBatchTools(index);
  return [...createBatchTools(index), ...createCursorTools(index)];
}

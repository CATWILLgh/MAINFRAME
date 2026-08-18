import {
  defineTool,
  type ToolDefinition,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import {
  findProjectFilesPage,
  grepProjectPage,
  listProjectDirectoryPage,
} from "../../project-tools.js";
import {
  parseEngineerCompletionManifest,
  type EngineerBlockManifest,
  type EngineerCompletionManifest,
} from "./contracts.js";
import { EngineerWorkspace } from "./workspace.js";

function textResult(value: unknown, terminate = false) {
  return {
    content: [{ type: "text" as const, text: typeof value === "string" ? value : JSON.stringify(value) }],
    details: {},
    ...(terminate ? { terminate: true as const } : {}),
  };
}

export interface EngineerToolSet {
  tools: ToolDefinition[];
  completion(): EngineerCompletionManifest | undefined;
}

export function createEngineerTools(
  projectRoot: string,
  manifest: EngineerBlockManifest,
  workspace: EngineerWorkspace,
): EngineerToolSet {
  let completed: EngineerCompletionManifest | undefined;

  const read = defineTool({
    name: "engineer_read",
    label: "Read an in-scope project file",
    description: "Read up to 240 lines and receive the exact file version required by engineer_edit. Follow nextStartLine when full coverage matters.",
    parameters: Type.Object({
      path: Type.String({ minLength: 1 }),
      startLine: Type.Optional(Type.Integer({ minimum: 1 })),
    }),
    execute: async (_id, params) => {
      const observed = await workspace.observe(params.path);
      const lines = observed.content.split("\n");
      const first = params.startLine ?? 1;
      const returned = first > lines.length ? [] : lines.slice(first - 1, first + 239);
      const endLine = returned.length ? first + returned.length - 1 : Math.min(first - 1, lines.length);
      return textResult({
        path: observed.path,
        version: observed.version,
        totalLines: lines.length,
        startLine: first,
        endLine,
        nextStartLine: endLine < lines.length ? endLine + 1 : null,
        truncated: endLine < lines.length,
        lines: returned.map((line, index) => `${first + index}: ${line}`),
      });
    },
  });
  const find = defineTool({
    name: "engineer_find",
    label: "Find project files",
    description: "Find a bounded page of project-relative paths; follow nextOffset when complete coverage matters.",
    parameters: Type.Object({
      query: Type.String(),
      offset: Type.Optional(Type.Integer({ minimum: 0 })),
    }),
    execute: async (_id, params) => textResult(await findProjectFilesPage(projectRoot, params.query, params.offset)),
  });
  const grep = defineTool({
    name: "engineer_grep",
    label: "Search project text",
    description: "Return a bounded page of literal case-insensitive matches; narrow the path and follow nextOffset when completeness matters.",
    parameters: Type.Object({
      query: Type.String({ minLength: 1 }),
      path: Type.Optional(Type.String()),
      offset: Type.Optional(Type.Integer({ minimum: 0 })),
    }),
    execute: async (_id, params) => textResult(await grepProjectPage(projectRoot, params.query, params.path, params.offset)),
  });
  const list = defineTool({
    name: "engineer_list",
    label: "List project directory",
    description: "List one bounded directory page; follow nextOffset when complete coverage matters.",
    parameters: Type.Object({
      path: Type.Optional(Type.String()),
      offset: Type.Optional(Type.Integer({ minimum: 0 })),
    }),
    execute: async (_id, params) => textResult(await listProjectDirectoryPage(projectRoot, params.path, params.offset)),
  });
  const edit = defineTool({
    name: "engineer_edit",
    label: "Apply exact in-scope edits",
    description: "Edit one previously read file. Supply its latest version and non-overlapping exact replacements against that version.",
    parameters: Type.Object({
      path: Type.String({ minLength: 1 }),
      version: Type.String({ pattern: "^[0-9a-f]{64}$" }),
      edits: Type.Array(Type.Object({
        oldText: Type.String({ minLength: 1 }),
        newText: Type.String(),
      }), { minItems: 1, maxItems: 40 }),
    }),
    execute: async (_id, params) => {
      const result = await workspace.edit(params.path, params.version, params.edits);
      return textResult({ path: result.path, version: result.version, changed: true });
    },
  });
  const create = defineTool({
    name: "engineer_create",
    label: "Create one in-scope text file",
    description: "Create a new text file. This refuses every existing path; use engineer_read and engineer_edit for existing files.",
    parameters: Type.Object({
      path: Type.String({ minLength: 1 }),
      content: Type.String(),
    }),
    execute: async (_id, params) => {
      const result = await workspace.createFile(params.path, params.content);
      return textResult({ path: result.path, version: result.version, created: true });
    },
  });
  const finish = defineTool({
    name: "engineer_finish",
    label: "Submit the block completion claim",
    description: "End the executor stage with one closed completion manifest. This is a claim that the independent verifier will check.",
    parameters: Type.Object({
      schemaVersion: Type.Literal(1),
      blockId: Type.String({ minLength: 1, maxLength: 64 }),
      status: Type.Union([Type.Literal("candidate"), Type.Literal("blocked"), Type.Literal("plan-conflict")]),
      summary: Type.String({ minLength: 1, maxLength: 2_000 }),
      changedPaths: Type.Array(Type.String({ minLength: 1 }), { maxItems: 400 }),
      acceptanceClaims: Type.Array(Type.Object({
        acceptanceId: Type.String({ minLength: 1, maxLength: 64 }),
        claim: Type.String({ minLength: 1, maxLength: 1_200 }),
        evidence: Type.Array(Type.String({ minLength: 1 }), { minItems: 1, maxItems: 20 }),
      }), { maxItems: 400 }),
      blockers: Type.Array(Type.String({ minLength: 1 }), { maxItems: 40 }),
    }),
    execute: async (_id, params) => {
      if (completed) return textResult("Completion submission is already closed.", true);
      try {
        completed = parseEngineerCompletionManifest(params, manifest);
      } catch (error) {
        return textResult(`Completion rejected: ${error instanceof Error ? error.message : String(error)}`);
      }
      return textResult("Completion claim accepted for independent verification.", true);
    },
  });

  return {
    tools: [read, find, grep, list, edit, create, finish],
    completion: () => completed,
  };
}

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport, getDefaultEnvironment } from "@modelcontextprotocol/sdk/client/stdio.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { defineTool, type ModelRuntime } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const SEARCH_LIMIT = 24_000;
const FETCH_LIMIT = 80_000;
const REQUEST_TIMEOUT_MS = 35_000;

export interface WebBackend {
  id: string;
  search?(query: string): Promise<string>;
  fetch?(url: string): Promise<string>;
}

export class WebRouter {
  constructor(private readonly backends: WebBackend[]) {}

  async search(query: string): Promise<{ backend: string; text: string }> {
    return this.route("search", query);
  }

  async fetch(url: string): Promise<{ backend: string; text: string }> {
    assertPublicHttpUrl(url);
    return this.route("fetch", url);
  }

  private async route(operation: "search" | "fetch", input: string): Promise<{ backend: string; text: string }> {
    const failures: string[] = [];
    for (const backend of this.backends) {
      const method = backend[operation];
      if (!method) continue;
      try {
        const text = await method.call(backend, input);
        if (text.trim()) return { backend: backend.id, text };
        failures.push(`${backend.id}: empty result`);
      } catch (error) {
        failures.push(`${backend.id}: ${error instanceof Error ? error.message : String(error)}`);
      }
    }
    throw new Error(`No ${operation} backend succeeded (${failures.join("; ") || "none configured"})`);
  }
}

function assertPublicHttpUrl(raw: string): void {
  const url = new URL(raw);
  if (url.protocol !== "https:" && url.protocol !== "http:") throw new Error("Only HTTP(S) URLs are supported");
  const host = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (host === "localhost" || host.endsWith(".local") || host === "::1" || host === "0.0.0.0") {
    throw new Error("Local URLs are not supported");
  }
  const octets = host.split(".").map(Number);
  if (octets.length === 4 && octets.every((part) => Number.isInteger(part) && part >= 0 && part <= 255)) {
    if (octets[0] === 10 || octets[0] === 127 || (octets[0] === 169 && octets[1] === 254) ||
      (octets[0] === 172 && (octets[1] ?? 0) >= 16 && (octets[1] ?? 0) <= 31) ||
      (octets[0] === 192 && octets[1] === 168)) {
      throw new Error("Private-network URLs are not supported");
    }
  }
}

function resultText(raw: unknown, limit: number): string {
  const result = (raw && typeof raw === "object" ? raw : {}) as { content?: unknown; structuredContent?: unknown };
  const blocks: string[] = [];
  for (const item of Array.isArray(result.content) ? result.content as Array<Record<string, any>> : []) {
    if (item.type === "text") blocks.push(item.text);
    else if (item.type === "resource" && "text" in item.resource) blocks.push(item.resource.text);
  }
  if (result.structuredContent) blocks.push(JSON.stringify(result.structuredContent));
  return blocks.join("\n").slice(0, limit);
}

async function zaiBackend(runtime: ModelRuntime): Promise<WebBackend | undefined> {
  const resolved = await runtime.getAuth("zai");
  const apiKey = resolved?.auth.apiKey;
  if (!apiKey) return undefined;
  const call = async (url: string, tool: string, args: Record<string, unknown>, limit: number) => {
    const client = new Client({ name: "mainframe-pi", version: "0.1.0" });
    const transport = new StreamableHTTPClientTransport(new URL(url), {
      requestInit: { headers: { Authorization: `Bearer ${apiKey}` } },
      reconnectionOptions: { maxReconnectionDelay: 2_000, initialReconnectionDelay: 250, reconnectionDelayGrowFactor: 2, maxRetries: 1 },
    });
    try {
      await client.connect(transport as never, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
      return resultText(await client.callTool({ name: tool, arguments: args }, undefined, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) }), limit);
    } finally {
      await client.close().catch(() => undefined);
    }
  };
  return {
    id: "zai",
    search: (query) => call("https://api.z.ai/api/mcp/web_search_prime/mcp", "web_search_prime", {
      search_query: query.slice(0, 280), content_size: "medium", location: "us",
    }, SEARCH_LIMIT),
    fetch: (url) => call("https://api.z.ai/api/mcp/web_reader/mcp", "webReader", {
      url, timeout: 25, return_format: "markdown", retain_images: false, with_links_summary: false,
    }, FETCH_LIMIT),
  };
}

async function minimaxBackend(runtime: ModelRuntime): Promise<WebBackend | undefined> {
  const resolved = await runtime.getAuth("minimax");
  const apiKey = resolved?.auth.apiKey;
  if (!apiKey) return undefined;
  return {
    id: "minimax",
    search: async (query) => {
      const client = new Client({ name: "mainframe-pi", version: "0.1.0" });
      const transport = new StdioClientTransport({
        command: "uvx",
        // The published MiniMax package currently omits its MCP runtime dependency.
        args: ["--with", "mcp==1.29.0", "minimax-coding-plan-mcp@0.0.4", "-y"],
        env: {
          ...getDefaultEnvironment(),
          MINIMAX_API_KEY: apiKey,
          MINIMAX_API_HOST: "https://api.minimax.io",
        },
        stderr: "pipe",
      });
      try {
        await client.connect(transport, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
        return resultText(await client.callTool({ name: "web_search", arguments: { query } }, undefined, { signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) }), SEARCH_LIMIT);
      } finally {
        await client.close().catch(() => undefined);
      }
    },
  };
}

export async function createWebRouter(runtime: ModelRuntime, preferred: "zai" | "minimax" = "zai"): Promise<WebRouter> {
  const resolved = await Promise.all([zaiBackend(runtime), minimaxBackend(runtime)]);
  const available = resolved.filter((backend): backend is WebBackend => backend !== undefined);
  available.sort((left, right) => Number(right.id === preferred) - Number(left.id === preferred));
  return new WebRouter(available);
}

export function createWebTools(router: WebRouter) {
  const textResult = (value: { backend: string; text: string }) => ({
    content: [{ type: "text" as const, text: value.text }],
    details: { backend: value.backend },
  });
  return [
    defineTool({
      name: "web_search",
      label: "Search the public web",
      description: "Search current public sources. Results are leads; fetch the authoritative page before treating a claim as evidence.",
      parameters: Type.Object({ query: Type.String({ minLength: 1, maxLength: 280 }) }),
      execute: async (_id, params) => textResult(await router.search(params.query)),
    }),
    defineTool({
      name: "web_fetch",
      label: "Read a public webpage",
      description: "Fetch one public HTTP(S) page for evidence. Local and private-network URLs are rejected.",
      parameters: Type.Object({ url: Type.String({ minLength: 1, maxLength: 2_048 }) }),
      execute: async (_id, params) => textResult(await router.fetch(params.url)),
    }),
  ];
}

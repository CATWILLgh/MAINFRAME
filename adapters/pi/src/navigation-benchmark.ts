import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";

import {
  createAgentSession,
  defineTool,
  ModelRuntime,
  SessionManager,
  SettingsManager,
  type AgentSession,
} from "@earendil-works/pi-coding-agent";
import type { Model } from "@earendil-works/pi-ai/compat";
import { Type } from "typebox";

import { loadProfile } from "./config.js";
import type { CollectorSelection } from "./model-types.js";
import {
  buildCorpusIndex,
  generateSyntheticCorpus,
  type CorpusIndex,
  type GoldControl,
  type NavigationScenario,
  type SyntheticCorpus,
} from "./navigation-corpus.js";
import { createStrategyTools, type NavigationStrategy } from "./navigation-strategies.js";
import { boundedPrompt, collectUsage, createIsolatedLoader, type UsageSummary } from "./session-utils.js";
export type { NavigationStrategy } from "./navigation-strategies.js";

interface SubmittedControl {
  id: string;
  evidence: string;
}

interface NavigationMetrics {
  toolCalls: number;
  repeatedToolCalls: number;
  bytesReturned: number;
  callsByTool: Record<string, number>;
}

export interface BenchmarkRunResult {
  strategy: NavigationStrategy;
  model: { provider: string; id: string; thinking: string };
  approximateWords: number;
  scenario: NavigationScenario;
  status: "complete" | "blocked";
  recall: number;
  precision: number;
  evidenceAccuracy: number;
  found: number;
  expected: number;
  falsePositives: string[];
  missing: string[];
  durationMs: number;
  usage: UsageSummary;
  navigation: NavigationMetrics;
  submitted?: SubmittedControl[];
  error?: string;
}

const SYSTEM_PROMPT = `You are a read-only retrieval worker in a controlled benchmark. Find evidence; do not invent it.
Use only the supplied project tools. Return every project control that is simultaneously state=active and classification=binding. Other active or binding controls are distractors. Cite the exact project-relative path:line containing each returned control. Submit exactly once through submit_controls.`;

function textResult(value: unknown) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return { content: [{ type: "text" as const, text }], details: {} };
}

function strategyPrompt(strategy: NavigationStrategy, corpus: SyntheticCorpus): string {
  const method = strategy === "baseline"
    ? "Use project_grep/project_find/project_read/project_list. Their result bounds may be silent; work with what the tools expose."
    : strategy === "cursor"
      ? "Use nav_grep/nav_find. Follow nextOffset until null whenever a result set can contain qualifying controls."
      : strategy === "spill"
        ? "Use spill_grep. If it returns a locator, inspect retained pages with spill_page rather than repeating the same search."
        : strategy === "batch"
          ? "Use batch_query with multiple terms to perform server-side intersections instead of loading unrelated matches."
          : "Use batch_query for cheap narrowing, then nav_grep/nav_read with continuation whenever batching reports truncation or a record spans lines.";
  const scenario = corpus.scenario === "split-record"
    ? "A control's state and classification can be on adjacent lines; both lines must carry the same control id."
    : "Each control is represented on one line.";
  return `Inspect the synthetic project of ${corpus.files} documents. There are exactly 12 controls that are both active and binding. Return all 12 and no distractors. ${scenario} ${method}`;
}

async function resolveModel(runtime: ModelRuntime, collector: CollectorSelection): Promise<Model<any>> {
  const available = await runtime.getAvailable(collector.model.provider, { signal: AbortSignal.timeout(15_000) });
  const model = available.find(({ id }) => id === collector.model.model);
  if (!model) throw new Error(`Unavailable model ${collector.model.provider}/${collector.model.model}`);
  return model;
}

function evaluate(submitted: SubmittedControl[], gold: GoldControl[]) {
  const expected = new Map(gold.map((item) => [item.id, item.evidence]));
  const unique = new Map(submitted.map((item) => [
    item.id,
    /^([^:\n]+:\d+)/u.exec(item.evidence.trim())?.[1] ?? item.evidence.trim(),
  ]));
  const found = [...unique.keys()].filter((id) => expected.has(id));
  const falsePositives = [...unique.keys()].filter((id) => !expected.has(id));
  const missing = [...expected.keys()].filter((id) => !unique.has(id));
  const evidenceCorrect = found.filter((id) => unique.get(id) === expected.get(id)).length;
  return {
    recall: found.length / expected.size,
    precision: unique.size ? found.length / unique.size : 0,
    evidenceAccuracy: found.length ? evidenceCorrect / found.length : 0,
    found: found.length,
    falsePositives,
    missing,
  };
}

async function runOne(
  corpus: SyntheticCorpus,
  index: CorpusIndex,
  strategy: NavigationStrategy,
  collector: CollectorSelection,
  timeoutMs: number,
): Promise<BenchmarkRunResult> {
  const started = Date.now();
  const metrics: NavigationMetrics = { toolCalls: 0, repeatedToolCalls: 0, bytesReturned: 0, callsByTool: {} };
  const seenCalls = new Set<string>();
  let submitted: SubmittedControl[] | undefined;
  let session: AgentSession | undefined;
  try {
    const runtime = await ModelRuntime.create({ signal: AbortSignal.timeout(15_000) });
    const model = await resolveModel(runtime, collector);
    const submit = defineTool({
      name: "submit_controls",
      label: "Submit qualifying controls",
      description: "Submit every active binding control with exact path:line evidence.",
      parameters: Type.Object({ controls: Type.Array(Type.Object({ id: Type.String(), evidence: Type.String() }), { maxItems: 40 }) }),
      execute: async (_id, params) => {
        submitted = params.controls;
        return { ...textResult("Controls accepted."), terminate: true };
      },
    });
    const tools = [...createStrategyTools(strategy, corpus.root, index), submit];
    const settings = SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: true, maxRetries: 1 } });
    const loader = await createIsolatedLoader(corpus.root, SYSTEM_PROMPT, settings);
    session = (await createAgentSession({
      cwd: corpus.root,
      modelRuntime: runtime,
      model,
      thinkingLevel: collector.model.thinking,
      tools: tools.map(({ name }) => name),
      customTools: tools,
      resourceLoader: loader,
      sessionManager: SessionManager.inMemory(corpus.root),
      settingsManager: settings,
    })).session;
    const unsubscribe = session.subscribe((event) => {
      if (event.type === "tool_execution_start") {
        metrics.toolCalls += 1;
        metrics.callsByTool[event.toolName] = (metrics.callsByTool[event.toolName] ?? 0) + 1;
        const key = `${event.toolName}:${JSON.stringify(event.args)}`;
        if (seenCalls.has(key)) metrics.repeatedToolCalls += 1;
        seenCalls.add(key);
      }
      if (event.type === "tool_execution_end") metrics.bytesReturned += JSON.stringify(event.result).length;
    });
    try {
      await boundedPrompt(session, strategyPrompt(strategy, corpus), timeoutMs, 64, () => submitted !== undefined, "submit_controls");
    } finally {
      unsubscribe();
    }
    if (!submitted) throw new Error("Model ended without submit_controls");
    const scored = evaluate(submitted, corpus.gold);
    return {
      strategy,
      model: { provider: collector.model.provider, id: collector.model.model, thinking: collector.model.thinking },
      approximateWords: corpus.approximateWords,
      scenario: corpus.scenario,
      status: "complete",
      ...scored,
      expected: corpus.gold.length,
      durationMs: Date.now() - started,
      usage: collectUsage(session),
      navigation: metrics,
      submitted,
    };
  } catch (error) {
    return {
      strategy,
      model: { provider: collector.model.provider, id: collector.model.model, thinking: collector.model.thinking },
      approximateWords: corpus.approximateWords,
      scenario: corpus.scenario,
      status: "blocked",
      recall: 0,
      precision: 0,
      evidenceAccuracy: 0,
      found: 0,
      expected: corpus.gold.length,
      falsePositives: [],
      missing: corpus.gold.map(({ id }) => id),
      durationMs: Date.now() - started,
      usage: session ? collectUsage(session) : { requests: 0, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: 0 },
      navigation: metrics,
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    session?.dispose();
  }
}

function argument(name: string, fallback: string): string {
  const prefix = `--${name}=`;
  return process.argv.find((value) => value.startsWith(prefix))?.slice(prefix.length) ?? fallback;
}

async function main(): Promise<void> {
  const sizes = argument("sizes", "150000").split(",").map(Number);
  const scenario = argument("scenario", "single-line") as NavigationScenario;
  const requestedStrategies = argument("strategies", "baseline,cursor,spill,batch").split(",") as NavigationStrategy[];
  const requestedModels = new Set(argument("models", "all").split(","));
  const timeoutMs = Number(argument("timeout-ms", "900000"));
  const concurrency = Math.max(1, Number(argument("concurrency", "1")));
  const outputPath = argument("output", path.resolve("test/benchmarks/navigation-results.json"));
  const profilePath = argument("config", path.resolve("config/profiles.local.json"));
  const profile = await loadProfile(profilePath, "business-analysis");
  const collectors = requestedModels.has("all")
    ? profile.collectors
    : profile.collectors.filter(({ role }) => requestedModels.has(role));
  if (!collectors.length) throw new Error("No benchmark models selected");
  const results: BenchmarkRunResult[] = [];

  for (const requestedSize of sizes) {
    const corpus = await generateSyntheticCorpus(requestedSize, scenario);
    try {
      const index = await buildCorpusIndex(corpus.root);
      const jobs = requestedStrategies.flatMap((strategy) => collectors.map((collector) => ({ strategy, collector })));
      for (let offset = 0; offset < jobs.length; offset += concurrency) {
        const batch = jobs.slice(offset, offset + concurrency);
        const batchResults = await Promise.all(batch.map(({ strategy, collector }) =>
          runOne(corpus, index, strategy, collector, timeoutMs),
        ));
        results.push(...batchResults);
        for (const result of batchResults) process.stdout.write(`${JSON.stringify(result)}\n`);
      }
    } finally {
      await rm(corpus.root, { recursive: true, force: true });
    }
  }
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify({ generatedAt: new Date().toISOString(), results }, null, 2)}\n`);
  process.stdout.write(`Saved ${results.length} benchmark results to ${outputPath}\n`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exitCode = 1;
  });
}

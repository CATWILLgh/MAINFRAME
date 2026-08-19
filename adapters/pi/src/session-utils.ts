import {
  DefaultResourceLoader,
  getAgentDir,
  SettingsManager,
  type AgentSession,
} from "@earendil-works/pi-coding-agent";
import type { AgentMessage } from "@earendil-works/pi-agent-core";

export interface UsageSummary {
  requests: number;
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  totalTokens: number;
  cost: number;
}

export function emptyUsage(): UsageSummary {
  return { requests: 0, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: 0 };
}

export function collectUsage(session: AgentSession): UsageSummary {
  const total = emptyUsage();
  for (const message of session.messages) {
    if (message.role !== "assistant") continue;
    total.requests += 1;
    total.input += message.usage.input;
    total.output += message.usage.output;
    total.cacheRead += message.usage.cacheRead;
    total.cacheWrite += message.usage.cacheWrite;
    total.totalTokens += message.usage.totalTokens;
    total.cost += message.usage.cost.total;
  }
  return total;
}

export function addUsage(target: UsageSummary, source: UsageSummary): void {
  target.requests += source.requests;
  target.input += source.input;
  target.output += source.output;
  target.cacheRead += source.cacheRead;
  target.cacheWrite += source.cacheWrite;
  target.totalTokens += source.totalTokens;
  target.cost += source.cost;
}

export interface SessionMetricsSummary {
  toolCalls: number;
  repeatedToolCalls: number;
  callsByTool: Record<string, number>;
  failedToolCalls: number;
  compactions: number;
  retries: number;
}

export interface SessionMetricsCollector {
  summary(): SessionMetricsSummary;
  dispose(): void;
}

export function collectSessionMetrics(session: AgentSession): SessionMetricsCollector {
  const callsByTool: Record<string, number> = {};
  const seen = new Set<string>();
  let toolCalls = 0;
  let repeatedToolCalls = 0;
  let failedToolCalls = 0;
  let compactions = 0;
  let retries = 0;
  const unsubscribe = session.subscribe((event) => {
    if (event.type === "tool_execution_start") {
      toolCalls += 1;
      callsByTool[event.toolName] = (callsByTool[event.toolName] ?? 0) + 1;
      const fingerprint = `${event.toolName}:${JSON.stringify(event.args)}`;
      if (seen.has(fingerprint)) repeatedToolCalls += 1;
      seen.add(fingerprint);
    } else if (event.type === "tool_execution_end" && event.isError) {
      failedToolCalls += 1;
    } else if (event.type === "compaction_end" && !event.aborted) {
      compactions += 1;
    } else if (event.type === "auto_retry_start") {
      retries += 1;
    }
  });
  return {
    summary: () => ({
      toolCalls,
      repeatedToolCalls,
      callsByTool: { ...callsByTool },
      failedToolCalls,
      compactions,
      retries,
    }),
    dispose: unsubscribe,
  };
}

export function requestsCompletionTool(message: AgentMessage, toolName?: string): boolean {
  if (!toolName || message.role !== "assistant") return false;
  return message.content.some((part) => part.type === "toolCall" && part.name === toolName);
}

export async function createIsolatedLoader(
  projectRoot: string,
  systemPrompt: string,
  settings = SettingsManager.inMemory(),
) {
  const loader = new DefaultResourceLoader({
    cwd: projectRoot,
    agentDir: getAgentDir(),
    settingsManager: settings,
    noExtensions: true,
    noSkills: true,
    noPromptTemplates: true,
    noThemes: true,
    noContextFiles: true,
    systemPrompt,
  });
  await loader.reload();
  return loader;
}

export async function boundedPrompt(
  session: AgentSession,
  prompt: string,
  timeoutMs: number,
  maxTurns: number,
  isComplete: () => boolean = () => false,
  completionToolName?: string,
): Promise<void> {
  let turns = 0;
  let limitExceeded = false;
  const unsubscribe = session.subscribe((event) => {
    if (event.type !== "turn_end") return;
    turns += 1;
    if (
      turns > maxTurns &&
      !isComplete() &&
      !requestsCompletionTool(event.message, completionToolName)
    ) {
      limitExceeded = true;
      void session.abort();
    }
  });
  let timedOut = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      timedOut = true;
      void session.abort();
      reject(new Error(`Model exceeded the ${timeoutMs}-millisecond stage timeout`));
    }, timeoutMs);
  });
  try {
    await Promise.race([session.prompt(prompt), timeout]);
  } finally {
    if (timer) clearTimeout(timer);
    unsubscribe();
  }
  if (timedOut && !isComplete()) throw new Error(`Model exceeded the ${timeoutMs}-millisecond stage timeout`);
  if (limitExceeded && !isComplete()) throw new Error(`Model exceeded the ${maxTurns}-turn pilot limit`);
  if (session.agent.state.errorMessage) throw new Error(session.agent.state.errorMessage);
}

export function isBenignCompactionNoop(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return error.message === "Nothing to compact (session too small)" || error.message === "Already compacted";
}

import { mkdir } from "node:fs/promises";

import type { ThinkingLevel } from "@earendil-works/pi-agent-core";
import type { Model } from "@earendil-works/pi-ai/compat";
import {
  createAgentSession,
  SessionManager,
  SettingsManager,
  type AgentSession,
  type ModelRuntime,
} from "@earendil-works/pi-coding-agent";

import {
  boundedPrompt,
  collectUsage,
  createIsolatedLoader,
  isBenignCompactionNoop,
  type UsageSummary,
} from "../../session-utils.js";
import type {
  EngineerBlockManifest,
  EngineerCompletionManifest,
  EngineerCorrectionPacket,
} from "./contracts.js";
import {
  acquireEngineerWriterLock,
  inspectEngineerGit,
  type EngineerGitFacts,
  type EngineerWriterLock,
} from "./preflight.js";
import {
  ENGINEER_SYSTEM_PROMPT,
  engineerBlockPrompt,
  engineerCorrectionPrompt,
} from "./prompts.js";
import {
  engineerSessionDirectory,
  newBlockCompactionInstructions,
  recordActiveEngineerBlock,
  validateEngineerSessionIntent,
} from "./session-state.js";
import { createEngineerTools, type EngineerToolSet } from "./tools.js";
import { EngineerWorkspace } from "./workspace.js";

export interface EngineerExecutorOptions {
  projectRoot: string;
  manifest: EngineerBlockManifest;
  modelRuntime: ModelRuntime;
  model: Model<any>;
  thinking: ThinkingLevel;
  timeoutMs?: number;
  maxTurns?: number;
}

export interface EngineerExecutorRound {
  completion: EngineerCompletionManifest;
  usage: UsageSummary;
}

export class EngineerExecutor {
  private constructor(
    readonly facts: EngineerGitFacts,
    private readonly manifest: EngineerBlockManifest,
    private readonly session: AgentSession,
    private readonly toolSet: EngineerToolSet,
    private readonly writerLock: EngineerWriterLock,
    private readonly timeoutMs: number,
    private readonly maxTurns: number,
  ) {}

  static async create(options: EngineerExecutorOptions): Promise<EngineerExecutor> {
    const facts = await inspectEngineerGit(options.projectRoot, options.manifest);
    await validateEngineerSessionIntent(facts, options.manifest);
    const writerLock = await acquireEngineerWriterLock(facts, options.manifest.blockId);
    let session: AgentSession | undefined;
    try {
      const workspace = await EngineerWorkspace.create(facts.projectRoot, options.manifest, facts.initialDirtyPaths);
      const toolSet = createEngineerTools(facts.projectRoot, options.manifest, workspace);
      const settings = SettingsManager.inMemory({
        compaction: { enabled: true },
        retry: { enabled: true, maxRetries: 2 },
      });
      const loader = await createIsolatedLoader(facts.projectRoot, ENGINEER_SYSTEM_PROMPT, settings);
      const sessionDirectory = engineerSessionDirectory(facts);
      await mkdir(sessionDirectory, { recursive: true, mode: 0o700 });
      session = (await createAgentSession({
        cwd: facts.projectRoot,
        modelRuntime: options.modelRuntime,
        model: options.model,
        thinkingLevel: options.thinking,
        tools: [
          "engineer_read", "engineer_find", "engineer_grep", "engineer_list",
          "engineer_edit", "engineer_create", "engineer_finish",
        ],
        customTools: toolSet.tools,
        resourceLoader: loader,
        sessionManager: SessionManager.continueRecent(facts.projectRoot, sessionDirectory),
        settingsManager: settings,
      })).session;
      if (options.manifest.sessionMode === "new") {
        try {
          await session.compact(newBlockCompactionInstructions(options.manifest));
        } catch (error) {
          if (!isBenignCompactionNoop(error)) throw error;
        }
        await recordActiveEngineerBlock(facts, options.manifest);
      }
      return new EngineerExecutor(
        facts,
        options.manifest,
        session,
        toolSet,
        writerLock,
        options.timeoutMs ?? 1_800_000,
        options.maxTurns ?? 160,
      );
    } catch (error) {
      session?.dispose();
      await writerLock.release();
      throw error;
    }
  }

  async runInitial(): Promise<EngineerExecutorRound> {
    return this.runRound(engineerBlockPrompt(this.manifest));
  }

  async runCorrection(packet: EngineerCorrectionPacket): Promise<EngineerExecutorRound> {
    return this.runRound(engineerCorrectionPrompt(packet));
  }

  usage(): UsageSummary {
    return collectUsage(this.session);
  }

  private async runRound(prompt: string): Promise<EngineerExecutorRound> {
    this.toolSet.beginRound();
    const started = Date.now();
    await boundedPrompt(
      this.session,
      prompt,
      this.timeoutMs,
      this.maxTurns,
      () => this.toolSet.completion() !== undefined,
      "engineer_finish",
    );
    if (!this.toolSet.completion()) {
      const remaining = this.timeoutMs - (Date.now() - started);
      if (remaining <= 0) throw new Error("Pi engineer exhausted the stage timeout without engineer_finish");
      await boundedPrompt(
        this.session,
        "Your previous turn ended without engineer_finish. Do not start new work or explain the omission. Submit the complete block claim now, or report the concrete blocker or plan conflict.",
        remaining,
        this.maxTurns,
        () => this.toolSet.completion() !== undefined,
        "engineer_finish",
      );
    }
    const completion = this.toolSet.completion();
    if (!completion) throw new Error("Pi engineer ended without a valid completion manifest");
    return { completion, usage: collectUsage(this.session) };
  }

  async dispose(): Promise<void> {
    this.session.dispose();
    await this.writerLock.release();
  }
}

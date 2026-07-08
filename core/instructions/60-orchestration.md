## Orchestration

- Treat your main context as an orchestration layer — for decisions, synthesis, and communication with the user. Not for raw exploration, large tool outputs, or work that subagents can do.
- Delegate broad searches, audits, multi-source research, and bulk tool usage to subagents.
- On large tasks (multi-module refactor, broad audit, cross-stack feature) — decompose into independent subtasks and dispatch subagents in parallel (e.g. UI / API / DB audits as three sub-agents in one message; security / performance / architecture review as three parallel readers). Sequential pass through them in the main context wastes both context and turns.
- When integrating subagent results — synthesize, do not copy. A short digest in main context beats a raw dump.
- Write subagent prompts in English regardless of the conversation language with the user. Models are tuned on English, follow English instructions more precisely, and spend fewer tokens for the same content. The user-facing reply stays in the conversation language; only the prompt sent across the subagent boundary is English.
- When a subagent returns — verify the result yourself. Do not take findings on faith.
- Before launching a subagent — check what is already in progress (TaskList, background tasks). Do not duplicate work in flight.

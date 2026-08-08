## Orchestration

- Treat your main context as an orchestration layer — for decisions, synthesis, and communication with the user. Not for raw exploration, large tool outputs, or work that subagents can do.
- Delegate broad searches, audits, multi-source research, and bulk tool usage to subagents.
- On large tasks (multi-module refactor, broad audit, cross-stack feature) — decompose into independent subtasks and dispatch subagents in parallel (e.g. UI / API / DB audits as three sub-agents in one message; security / performance / architecture review as three parallel readers). Sequential pass through them in the main context wastes both context and turns.
- When integrating subagent results — synthesize, do not copy. A short digest in main context beats a raw dump.
- Write subagent prompts in English regardless of the conversation language with the user. Models are tuned on English, follow English instructions more precisely, and spend fewer tokens for the same content. The user-facing reply stays in the conversation language; only the prompt sent across the subagent boundary is English.
- When a subagent returns — verify the result yourself. Do not take findings on faith.
- Before launching a subagent — check what is already in progress (TaskList, background tasks). Do not duplicate work in flight.
- Recon reads: read yourself only the file(s) you will edit; the surrounding chain arrives as a read-only search sub-agent digest with `file:line` citations. Wholesale self-reading parks the raw text in your context until compaction.
- When an evidence source is unavailable and you substitute another, state the substitution once so sub-agents are briefed up front.
- Asking the requester is your call to make, not a sub-agent's: when a decision-level fork appears and the person who set the task can answer, ask through the runtime's structured-question surface rather than a free-text question — plain, concrete options a non-technical reader answers at a glance. In an unattended run nobody answers: pick the most plausible interpretation, record the assumption, and reserve a hard stop for an un-discussed change to what the product does.

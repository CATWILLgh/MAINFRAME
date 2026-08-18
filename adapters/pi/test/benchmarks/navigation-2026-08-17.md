# Pi context-navigation benchmark — 2026-08-17

## Decision

Use **explicit cursor pagination** as the required base contract for Pi project
navigation. Every bounded search, file listing, and read must report the total,
the returned range, whether output was truncated, and the next cursor or line.

Keep multi-term batch queries as an optional accelerator for narrow questions.
Do not replace cursor navigation with batching, retained spill output, or an
undifferentiated tool bundle.

For the tested read-only retrieval role, `zai/glm-5.2` with thinking disabled
was the most stable and economical model. This is not evidence that it is the
best BA reasoner or synthesizer.

## Guarantee

The worker must recover all twelve planted controls, reject distractors, and
cite the exact source line. Correctness and evidence quality are gates; tokens,
tool calls, and duration are compared only after those gates pass.

The generated projects contained approximately 150k, 350k, and 800k words.
Controls were distributed from the beginning to the end. The harder scenario
split the two qualifying properties across adjacent lines and filled the corpus
with hundreds of one-property distractors.

## Live results

Forty-eight fresh Pi SDK runs used the locally authorized Pi 0.84.2 models:
MiniMax M3, GLM-5-Turbo, and GLM-5.2, all with thinking disabled.

| Strategy and scenario | Runs | Perfect | Median tokens | Mean tool calls | Result |
|---|---:|---:|---:|---:|---|
| baseline / one line | 3 | 3 | 27,990 | 18.7 | Correct here, but silently bounded and expensive |
| spill / one line | 3 | 2 | 22,252 | 8.3 | Rejected: one run found only 10/12 |
| batch / one line | 9 | 9 | 3,716 | 2.0 | Best accelerator for an exact intersection |
| cursor / one line | 9 | 9 | 10,364 | 7.2 | Correct and bounded |
| batch / split record | 6 | 5 | 26,470 | 5.0 | Rejected as the base: one run cited only half the condition |
| hybrid / split record | 6 | 6 | 41,540 | 11.2 | Correct, but extra tools increased cost and variance |
| cursor / split record | 12 | 12 | 18,660 | 16.8 | Winner: only universally correct base contract |

The hardest 800k split-record cursor case was repeated three times per model.
All nine runs were perfect. Model-level cursor results across the 350k run and
the repeated 800k runs were:

| Model | Runs | Perfect | Median tokens | Mean tokens | Maximum |
|---|---:|---:|---:|---:|---:|
| GLM-5.2 off | 4 | 4 | 13,348 | 13,445 | 18,660 |
| MiniMax M3 off | 4 | 4 | 39,357 | 38,008 | 41,381 |
| GLM-5-Turbo off | 4 | 4 | 16,547 | 69,131 | 230,467 |

GLM-5-Turbo had one 230k-token outlier despite returning the right answer. That
variance matters for unattended work.

## What the result does not prove

- The corpus measures navigation and evidence recovery, not full business
  analysis, architecture, or coding quality.
- Word count is a reproducible source-size approximation, not a provider's
  private tokenizer count.
- Batch query remains useful when the question is naturally expressible as a
  small intersection. It should sit behind the cursor-safe base rather than be
  exposed beside every primitive by default.
- A model family or provider can change. Re-run the benchmark after material
  model, Pi runtime, prompt, or tool-contract changes.

## Reproduction

From `adapters/pi/` with configured local Pi authentication:

```sh
npm test
npm run build
npm run benchmark:navigation -- --sizes=150000 --strategies=baseline,cursor,spill,batch --models=all
npm run benchmark:navigation -- --sizes=350000,800000 --strategies=cursor,batch --models=all
npm run benchmark:navigation -- --sizes=350000,800000 --scenario=split-record --strategies=cursor,batch,hybrid --models=all
```

Raw per-run results intentionally stay outside the repository unless a future
telemetry contract adopts them. The committed report retains the decision and
the aggregate evidence without model transcripts.

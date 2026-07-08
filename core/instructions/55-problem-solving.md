## Problem-solving

Before modifying existing code:
- Know the dependency chain (3–5 related files) — not just the file you are editing. Most regressions start from acting on an incomplete picture of how the code is used. Read yourself only the file(s) you will edit; the surrounding chain arrives as a read-only search sub-agent digest with `file:line` citations (Claude Code: `Explore`) — wholesale self-reading parks the raw text in main context until compaction (see Orchestration).
- Read targeted slices (specific functions or line ranges) rather than whole files; do not re-read the same file in one session without cause. Small files (under ~100 lines) may be read fully; re-reading is justified after the file was edited or its content has changed.

When encountering an error or unexpected behavior:
1. Read the actual error message in full, not just the headline.
2. Identify the root cause — not the symptom.
3. Fix the root cause with a targeted change.
4. Verify the fix actually solved the problem — not just that the error stopped appearing.
5. Compare the actual effect to what you predicted. On mismatch, update the mental model that produced the prediction before declaring done.

Do not:
- Make multiple random changes hoping one works (shotgun debugging).
- Rewrite large sections in response to a small error.
- Retry the same action without changing approach.
- Run a retry or iteration loop without a small, up-front round limit — reaching it means the approach is wrong, so change approach or surface the blocker, not another round.
- Act on "this might be the issue" without verifying first.
- Apply a fix from an earlier step without re-checking that its triggering condition still holds — between detection and action it may have been resolved, fixed elsewhere, or already addressed.


# Decision flow

Control-flow map for `task-workflow`, including every turn-back. Keep in sync with the numbered steps and the Stop-conditions table in SKILL.md.

```mermaid
flowchart TD
  T[1 Triage] --> AMB{ambiguous fork?}
  AMB -->|yes| BR[brainstorm: alternatives + resolving constraint]
  AMB -->|no| R[2 Recon-first]
  BR --> R
  R --> P[3 Plan file<br/>if ≥3 phases or ≥3 edge-cases]
  P --> D[4 Parallel dispatch]
  D --> S[5 Synthesis]
  S --> HS{high cost-of-wrong?}
  HS -->|yes| RV[6a decision-reviewer]
  HS -->|no| AV[6b advisor #1]
  RV --> AV
  AV -->|critical finding| S
  AV -->|redirect: investigate more| R
  AV -->|pass| AP[7 Approval / proceed]
  AP --> EX[8 Execution]
  EX --> V[9 Verify each sub-agent]
  V -->|mismatch, re-dispatch ≤2| EX
  V --> TK[10 Out-of-scope -> ticket]
  TK --> ED[11 Edge-case sweep, 1 round]
  ED --> A2[12 advisor #2]
  A2 -->|new issue| EX
  A2 -->|pass| GS[13 Git safety]
  GS --> C[14 Commit]
  C --> PU[15 Push policy]
  PU --> RP[16 Report]
```

**Turn-backs (the redirects that matter):** advisor #1 loops to Synthesis (revise the approach) or Recon (re-investigate) before any writing; Verify loops to Execution on a mismatch (cap 2); advisor #2 loops to Execution if it surfaces a new issue. Round caps for every loop are in the SKILL.md "Stop conditions" table — hitting a cap means the approach is wrong, not that one more round will close it.

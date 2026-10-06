# Skill reminder route candidates

This matrix records both implemented and deferred routes. See the current
[hook contract](README.md#adapt-mainframe-skill-reminder) for delivery behavior.
Rows below retain candidate reasoning; the implementation status table is
authoritative for which subsets are active. Do not turn the matrix into keyword
matching or claim every row is available in the Codex Bash event.

A bounded local investigation of real receiving-project sessions found literal
commands, credential wrappers, remote command strings, inline programs, project
source reads and explicit method reads. The investigation also found source
rewrites and searches containing domain words without executing domain tools.
Private session locations and sampling limits remain in the maintainer's local
evidence; consumer project names and transcripts do not belong in delivery.

## Rules shared by every route

- Parse executable/operation boundaries, not words in command arguments, echoed
  documentation, search patterns, comments or generated source text. Known
  wrappers may reveal a nested operation without executing any input. Preserve
  the distinction between local and remote execution throughout the chain.
- Domain-specific integration source may warrant its engineering method without
  a live operation. Identify actual syntax and project role; never claim a
  generated client or SQL file establishes a connection, environment or authority.
- Resolve only bounded, non-secret project metadata needed for the route. A
  target map is orientation, not proof of live target state or permission.
- Choose one most useful method at a decision point. Prefer a verified specialist
  to a generic infrastructure method. Keep the shared reminder budget, recipient
  isolation, expiry, disable policy and readable-skill checks.
- A PostToolUse advisory cannot ensure the skill was applied before the first
  operation. A pre-action event also does not necessarily allow the model to
  reconsider an already-submitted operation; verify native semantics. Neither
  kind of reminder replaces a guard or grants authority.
- Existing file heuristics are conditional recommendations, not zero-error
  classification. Additional fixtures, vendored examples and role counterexamples
  must be considered when strengthening them. No observed case is not proof of
  impossibility, and a bounded sample cannot establish a zero false-positive rate.

## Per-skill candidates

| Skill | Narrow candidate and required evidence | Rejection / negative case | Evidence and placement |
| --- | --- | --- | --- |
| `mainframe-secrets` | Parsed installed `mainframe-secret` credential operation, including `run` before a known consumer; or the explicitly configured metadata index | Help/version, quoted helper examples, arbitrary `.env` reads; never inspect a secret store to classify | Credential wrappers were frequent in the sample. Bash operation advice is feasible; combine wrapper and consumer without flooding |
| `mainframe-curl-requests` | Parsed curl HTTP(S) transfer, including a literal SSH remote command; distinguish transfer arguments from help/version | A curl example in a file, `curl --version`, non-HTTP transport, unparsed shell interpolation | Direct and SSH-wrapped curl were observed; bounded operation advice is feasible |
| `mainframe-clickhouse` | Identified ClickHouse client/MCP operation, or actual ClickHouse integration/schema syntax in a known project owner | A domain word in `rg`, source rewrite strings, a generic SQL file, HTTP port alone, PostgreSQL sizing work | Integration-related reads occurred, but no direct-first client invocation in the initial sample. Client, source and target routes need separate fixtures; do not infer a live database from integration work |
| `mainframe-self-monitoring` | Explicit embedded diagnostics page or operator-console implementation | A Dockerfile, health endpoint or metric read alone does not establish a UI integration task | Ordinary proactive selection; no automatic hook route without attributable task evidence |
| `mainframe-notifications` | Explicit application notification delivery/settings or channel repair assignment | Reading SMTP, bot or service-worker configuration alone does not establish this workflow | Ordinary proactive selection; no automatic hook binding without attributable task evidence |
| `mainframe-keycloak-sso` | Explicit application SSO integration or repair assignment | Reading auth settings, a Keycloak deployment manifest or login theme alone does not establish application integration | New method: ordinary proactive skill selection; no automatic hook binding until attributable task evidence distinguishes integration from deployment/theming |
| `mainframe-k3s` | Parsed K3s cluster operation, including literal SSH/sudo wrappers; or exact non-secret K3s configuration ownership | Bare kubectl, arbitrary directory named k3s, application-only pod work, help/version; do not read kubeconfig credentials to classify | SSH/sudo K3s chains were observed. Inspect the subcommand and resource: K3s executable identity alone does not establish cluster-level work |
| `mainframe-infrastructure` | Recognized Dockerfile/Compose/IaC owner, configured infrastructure map, or identified deployment/runtime management operation | Fixture/example/vendor config, broad `infra` directory, ordinary CI test execution, more specific verified K3s/ClickHouse route | Dockerfile reads and remote Docker operations were observed. Conditional file/operation route is feasible |
| `mainframe-ops-app-server-safety` | Parsed service lifecycle operation with independently established local executor and target, or a resolved project script that starts that local service | Remote SSH, remote Docker context/endpoint, `ps`/version, one-shot scripts, guessing local from localhost or workdir | Actual method reads were observed. Current Bash payload lacks enough executor evidence for blanket local-lifecycle classification; use a verified local binding or retain infrastructure advice |
| `mainframe-testing` | Existing test/CI file route; extend to identified test runners and configured verification scripts | Help/version, printing a command example, arbitrary `npm run` name, a deployment job misclassified as ordinary tests | Test method reads and test-runner operations were observed. Known script body and test purpose strengthen routing |
| `mainframe-test-audit` | Explicit native test-auditor assignment or project-declared test-quality audit workflow | Ordinary tests, coverage collection alone, running CI, current investigation's own audit probe | No historical receiving-project invocation found in bounded search. Role/workflow route is viable if an adapter exposes it; Bash file paths alone do not distinguish the purpose |
| `mainframe-go-backend` | Go service/module profile plus attributable source owner; include `internal/` only with service evidence | Go CLI/library, generated files, language extension alone | Many `internal/` reads bypass the existing backend-folder heuristic. A module/service profile needs positive service and negative CLI fixtures |
| `mainframe-python-backend` | Python service/worker profile plus attributable source or operation | Data science, maintenance script, generic Python heredoc, fixture-only dependency imports | Method reads and many inline Python programs were observed; interpreter identity is insufficient |
| `mainframe-typescript-backend` | Node service/Next.js server owner plus source or operation, not just `src/` | React client, browser library, build tooling, generic Node inline script | Method reads and `src/` reads were observed. Resolve the package/workspace boundary, not only the repository root |
| `mainframe-frontend` | React web package plus client interface owner; retain package evidence | React Native, Next.js server-only owner, standalone design system, unrelated TSX examples | React method reads occurred. A React dependency alone does not resolve client/server ownership |
| `mainframe-record-project-problem` | Access to the project's configured recording contract/template and observation-queue workflow | Generic ticket read, implementing the assigned ticket, an unfinished assigned result, arbitrary `tickets/` folder | Actual recording workflows read queue instructions and search observations. Conditional recording-method advice is viable; it must not assert the problem is out of scope |
| `mainframe-harness-feedback` | Access to the configured MAINFRAME feedback contract/destination, or an attributable structured harness fault | Ordinary application failure, correct permission denial, intentional hook disablement | Actual fault reports used the feedback destination. Queue/workflow advice is viable; a denial string alone does not establish a fault |
| `mainframe-project-harness` | Explicit harness audit/repair assignment or a structured configuration/discovery conflict | Routine reading of AGENTS.md, initial setup, any edit to settings without a fault or audit assignment | No genuine receiving-project invocation found in bounded search. Configuration paths identify a domain, not the skill's full trigger; use an exposed assignment/finding |
| `mainframe-research` | Explicit researcher assignment or project-declared comparison/research workflow; external-source activity is supporting evidence | Single-fact lookup, routine official-doc retrieval, number of searches alone | Actual comparative research used multiple sources. Role/task events could route precisely; current Bash event does not expose web operations or research purpose |
| `mainframe-consequential-review` | Explicit consequential-reviewer assignment or declared readiness/acceptance decision needing independent challenge | Routine code review, merely reading migrations/financial code, any production word | Actual assignments concerned financial correctness and migration/recovery. The same source paths occur in routine implementation; use the decision/role boundary |
| `mainframe-peer-work` | Parsed verified external coding-agent executable and its actual headless/continuation operation | Help/version/install, executable-name collision, quoted invocation, ordinary agent APIs | No actual invocation found in bounded search. Candidate needs product-specific fixtures and native timing; remind about existing assigned-product authority, never infer it |

## Implementation order

1. Add one canonical operation recognizer with bounded wrapper handling. Start
   with demonstrated credential/curl/remote infrastructure chains; retain remote
   identity instead of rewriting them as local commands.
2. Strengthen bounded project/package ownership for existing engineering routes,
   and add explicit infrastructure/integration owners. Do not scan the entire
   repository or follow instructions embedded in configuration/content.
3. Add configured queue workflows without inferring issue ownership or defect
   existence from a filename. Reuse existing queue contracts, not a second index.
4. Adapt role/finding events when the product exposes them. Explicit semantic
   assignments can supply deterministic anchors even when file reads cannot.
   Do not infer missing task semantics by scanning the entire conversation on
   every hook invocation.

For each activated route retain an observed positive shape, a realistic near
miss, ambiguity/disable/duplicate cases, and a bounded native receipt check.
Corpus search hits are candidates; manual interpretation is not a trained or
validated production classifier. Keep emitted-message counts separate from
actual relevance and subsequent method application.

## Implementation status

| Subset | Event / outcome | Explicit remaining boundary |
| --- | --- | --- |
| Credential helper, HTTP curl, ClickHouse client, K3s cluster operation, Docker/Terraform, named test runners, explicit Codex headless peer work | Codex `PreToolUse` Bash | Only bounded literal supported syntax; no command rewrite or guard; no proof the first operation used the method |
| Backend module, React web application, ClickHouse integration, infrastructure configuration | Codex `PostToolUse` Bash reads with bounded source/package evidence | Eight read targets maximum; fixtures, generated files, secret/key files, unsafe paths and ambiguous ownership stay silent |
| Researcher, test auditor, consequential reviewer and four engineering roles | Codex `SubagentStart` exact native MAINFRAME role | Generic/default/explorer roles do not establish the specialized task |
| Project engineering method | Project-guidance-bound unique method after an otherwise unclassified project read | Does not displace a recognized specialist or repeat after the specialist was already suggested |
| Local application-server safety | Not automatically selected; identifiable Docker/runtime work can receive infrastructure advice | Current Bash payload and outer-call workdir hint do not prove local executor/target identity. Remote and tunneled endpoints remain possible |
| Project-problem and harness-feedback recording | Deferred, existing explicit skill selection remains | Queue reads also occur in triage/implementation; native payload does not establish an unresolved out-of-scope issue or an actual harness defect. Permission refusal alone is not such evidence |
| Project-harness audit/repair | Deferred, existing explicit skill selection remains | Ordinary configuration reads/edits do not establish the required fault/audit purpose; no stable structured finding is available to this adapter |
| External-agent peer work | Narrow documented `codex exec` / exact-ID resume syntax uses `PreToolUse`; other products remain unclassified | No actual invocation in the bounded corpus: positive cases are documented-syntax fixtures, not historical use. Invocation syntax identifies method relevance, never assigned-product authority. No CLI is launched merely to invent a test |

Deferred does not mean intrinsically impossible. Revisit a route when a native
role, attributable structured finding or established project workflow supplies
the missing distinction. Do not use UserPromptSubmit/Stop to guess intent from
keywords or force extra model turns, and do not scan full conversations in the
hook. The current native tool inventory exposed no ClickHouse/K3s MCP tool with
a verified identity to bind; unknown MCP tool names remain unclassified.

Explicit initial literal `cat .../SKILL.md` attempts suppress later advice even
when a complex suffix prevents full read-command parsing. This suppression-only
fallback does not classify source files, inspect later branches, or prove that
the method was read successfully or applied.


## Native bindings

All five maintained adapters reuse one detector, source profiles and recipient
budget through a small native normalizer. No callback executes the inspected
command, reads the complete skill body into the model, changes permission or
forces a model turn. One readable path is suggested conditionally; explicit
skill-read awareness suppresses further advice for that method. State stores
only expiring scope hashes and skill identities, at most three sent suggestions
per recipient/workspace and one per skill. Unknown or conflicting identity,
context, invocation policy and state failures stay silent.

| Adapter | Operation advice | Read advice | Attribution and limits |
| --- | --- | --- | --- |
| Codex | PreToolUse Bash | PostToolUse Bash | Root/child identity; exact specialized roles also use SubagentStart; bounded native transcript workdir hints |
| ZCode | PreToolUse Bash | PostToolUse Bash/Read | Primary runtime only; native default children omit hook runners; shell relative reads require an explicit literal directory |
| Antigravity | PostInvocation run_command | PostInvocation run_command/view_file | Native conversation and bounded latest-call identity; post-invocation advice before the next model decision, no prospective prevention or role-start advice |
| MiniMax | PreToolUse bash | PostToolUse bash/read | Native session and optional recipient identity; known structured failed reads stay silent; no canonical specialized Agent package/start mapping |
| Cline | PreToolUse run_commands | PostToolUse run_commands/read_files | Native task, tool ID and optional agent identity; multi-command arrays and unattributed lifecycle events stay silent; no role-start advisory |

Native file read tools are normalized only from literal supported path
fields (Cline accepts up to eight `files[].path` requests). Absolute targets work without a shell workdir; do not substitute a
workspace directory for an unknown shell tool cwd. The helpers consider only
readable MAINFRAME methods in each adapter's installed skill root plus the
uniquely bound project engineering method. These paths are usable directly;
the helper does not claim native catalog visibility. Native package/global
hook enablement and per-component disable markers remain authoritative.

Verification: `PYTHONPATH=tests python3 -B -m unittest test_native_skill_reminder`
checks wire formats, recipient dedup, explicit-read suppression, known failure
and disable behavior in disposable homes. Product installer suites separately
check ownership, packaging, registration, convergence and removal. The pinned
[ZCode source probe](../tests/probes/zcode_reminder_contract.cjs) establishes the
reviewed current parser/consumer boundary without starting a model. Live
recognition, model receipt and useful application still need native-session
evidence; the existing Codex observations do not establish acceptance elsewhere.

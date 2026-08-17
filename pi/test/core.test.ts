import assert from "node:assert/strict";
import { cp, mkdtemp, mkdir, readFile, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { buildProjectMap } from "../src/project-map.js";
import { loadProfile } from "../src/config.js";
import { stageExternalInput } from "../src/external-input.js";
import {
  findProjectFiles,
  grepProject,
  listProjectDirectory,
  readProjectFile,
} from "../src/project-tools.js";
import { saveNextReview } from "../src/review-store.js";
import { validateReview } from "../src/review-validator.js";
import {
  applyVerifiedThinkingContract,
  createIsolatedLoader,
  isBenignCompactionNoop,
} from "../src/runtime.js";
import { requestsCompletionTool } from "../src/session-utils.js";

const fixture = path.resolve("test/fixtures/synthetic-ba-project");

function validReview(evidence = "docs/initiatives/order-handoff/requirements.md:3"): string {
  return `# Business Analysis Review

## Process understanding

The application hands an approved shipment to ERP and waits for acknowledgement.

## Findings

### F-001 — [process-blocker] Completion is not defined

- Scenario: ERP does not acknowledge the request.
- Gap or contradiction: The terminal business state is not defined.
- Consequence: Warehouse staff cannot complete or safely retry the shipment.
- Evidence: ${evidence}
- Question: Q-001

## Questions

### Q-001

- Question: What state and owner apply after delivery attempts are exhausted?
- Proposal: Keep the shipment recoverable by warehouse staff.

## Confirmed business scenarios

### S-001 — Successful handoff

- Initial state: A warehouse manager approved the shipment.
- Event or action: ERP acknowledges the request with an order id.
- Expected business result: The shipment becomes ready and shows the ERP id.
- Forbidden side effect: A duplicate ERP order is not created.

## Readiness

needs-answers
`;
}

test("project map includes useful sources and excludes generated directories", async () => {
  const map = await buildProjectMap(fixture, "order-handoff");
  assert.equal(map.initiative, "order-handoff");
  assert.equal(map.entryPath, "docs/initiatives/order-handoff/requirements.md");
  assert(map.files.some((file) => file.path === "docs/initiatives/order-handoff/requirements.md"));
  assert(map.files.some((file) => file.path === "src/order-handoff.ts"));
  assert(!map.files.some((file) => file.path.includes("node_modules")));
});

test("project map records an explicit existing entry artifact", async () => {
  const map = await buildProjectMap(fixture, "order-handoff", "docs/integrations/erp.md");
  assert.equal(map.entryPath, "docs/integrations/erp.md");
  assert(map.files.some((file) => file.path === map.entryPath));
});

test("review validation accepts the complete machine-checkable contract", async () => {
  const result = await validateReview(fixture, validReview());
  assert.deepEqual(result.errors, []);
  assert.equal(result.readiness, "needs-answers");

  const range = await validateReview(
    fixture,
    validReview("docs/initiatives/order-handoff/requirements.md:3-5"),
  );
  assert.deepEqual(range.errors, []);
});

test("review validation rejects missing and escaping evidence", async () => {
  const missing = await validateReview(fixture, validReview("docs/missing.md:1"));
  assert(missing.errors.some((error) => error.includes("does not exist")));

  const escaping = await validateReview(fixture, validReview("../outside.md:1"));
  assert(escaping.errors.some((error) => error.includes("outside the project")));

  const missingLine = await validateReview(
    fixture,
    validReview("docs/initiatives/order-handoff/requirements.md"),
  );
  assert(missingLine.errors.some((error) => error.includes("project/path:line")));

  const invalidLine = await validateReview(
    fixture,
    validReview("docs/initiatives/order-handoff/requirements.md:999"),
  );
  assert(invalidLine.errors.some((error) => error.includes("line is outside")));

  const reversedRange = await validateReview(
    fixture,
    validReview("docs/initiatives/order-handoff/requirements.md:5-3"),
  );
  assert(reversedRange.errors.some((error) => error.includes("line is outside")));
});

test("review store creates the next review without overwriting an existing one", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-review-"));
  const initiative = path.join(root, "docs/initiatives/order-handoff");
  await mkdir(path.join(initiative, "reviews"), { recursive: true });
  await writeFile(path.join(initiative, "requirements.md"), "# Requirements\n");
  await writeFile(path.join(initiative, "decisions.md"), "# Decisions\n");
  await writeFile(path.join(initiative, "reviews/001.md"), "existing\n");

  const saved = await saveNextReview(root, "order-handoff", validReview());
  assert.equal(saved.relativePath, "docs/initiatives/order-handoff/reviews/002.md");
  assert.equal(await readFile(path.join(initiative, "reviews/001.md"), "utf8"), "existing\n");
});

test("review store creates a report-only initiative without copying its source artifact", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-external-entry-"));
  await mkdir(path.join(root, "docs/design"), { recursive: true });
  await writeFile(path.join(root, "docs/design/existing-adr.md"), "# Existing ADR\n");
  const saved = await saveNextReview(root, "existing-flow", validReview("docs/design/existing-adr.md:1"));
  assert.equal(saved.relativePath, "docs/initiatives/existing-flow/reviews/001.md");
  assert.equal(await readFile(path.join(root, "docs/design/existing-adr.md"), "utf8"), "# Existing ADR\n");
});

test("review store refuses a reviews symlink that leaves the initiative", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-symlink-"));
  const initiative = path.join(root, "docs/initiatives/order-handoff");
  const outside = await mkdtemp(path.join(tmpdir(), "mainframe-pi-outside-"));
  await mkdir(initiative, { recursive: true });
  await writeFile(path.join(initiative, "requirements.md"), "# Requirements\n");
  await writeFile(path.join(initiative, "decisions.md"), "# Decisions\n");
  await symlink(outside, path.join(initiative, "reviews"));

  await assert.rejects(
    saveNextReview(root, "order-handoff", validReview()),
    /reviews directory must not be a symbolic link/,
  );
});

test("project reader refuses absolute, traversal, and symlink escapes", async () => {
  await assert.rejects(readProjectFile(fixture, "/etc/passwd"), /outside the project/);
  await assert.rejects(readProjectFile(fixture, "../outside.md"), /outside the project/);

  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-read-"));
  await symlink("/etc/passwd", path.join(root, "escape"));
  await assert.rejects(readProjectFile(root, "escape"), /resolves outside the project/);
});

test("project discovery tools bound noisy results on large repositories", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-bounds-"));
  for (let index = 0; index < 100; index += 1) {
    await writeFile(path.join(root, `matching-${String(index).padStart(3, "0")}.md`), "shared needle\n");
  }
  assert.equal((await findProjectFiles(root, "matching")).length, 40);
  assert.equal((await grepProject(root, "shared needle")).length, 40);
  const listed = await listProjectDirectory(root);
  assert.equal(listed.length, 81);
  assert.match(listed.at(-1) ?? "", /20 more entries omitted/);
});

test("project discovery and reading exclude secrets and Pi runtime state", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-policy-"));
  await cp(fixture, root, { recursive: true });
  await writeFile(path.join(root, ".env"), "TOKEN=not-a-real-secret\n");
  await mkdir(path.join(root, ".agents/runtime/pi/sessions"), { recursive: true });
  await mkdir(path.join(root, ".claude/agent-memory"), { recursive: true });
  await writeFile(path.join(root, ".agents/runtime/pi/sessions/session.jsonl"), "private context\n");
  await writeFile(path.join(root, ".claude/agent-memory/MEMORY.md"), "stale agent memory\n");
  await writeFile(path.join(root, "AGENTS.md"), "project harness instructions\n");

  const map = await buildProjectMap(root, "order-handoff");
  assert(!map.files.some((file) => file.path === ".env"));
  assert(!map.files.some((file) => file.path.startsWith(".agents/runtime/pi/")));
  assert(!map.files.some((file) => file.path.startsWith(".claude/")));
  assert(!map.files.some((file) => file.path === "AGENTS.md"));
  await assert.rejects(readProjectFile(root, ".env"), /excluded from the business-analysis profile/);
  await assert.rejects(
    readProjectFile(root, ".agents/runtime/pi/sessions/session.jsonl"),
    /excluded from the business-analysis profile/,
  );
  await assert.rejects(
    readProjectFile(root, ".claude/agent-memory/MEMORY.md"),
    /excluded from the business-analysis profile/,
  );
  await assert.rejects(readProjectFile(root, "AGENTS.md"), /excluded from the business-analysis profile/);
  await writeFile(path.join(root, ".agents/runtime/pi/project-map.json"), "{}\n");
  assert.match(await readProjectFile(root, ".agents/runtime/pi/project-map.json"), /1: \{\}/);
});

test("an external input is staged immutably and only that runtime file becomes readable", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-target-"));
  const sourceRoot = await mkdtemp(path.join(tmpdir(), "mainframe-pi-source-"));
  const source = path.join(sourceRoot, "requirements.md");
  await writeFile(source, "# External requirements\n\nOriginal source stays separate.\n");

  const staged = await stageExternalInput(root, source);
  assert.match(staged, /^\.agents\/runtime\/pi\/inputs\/[a-f0-9]{64}\.md$/);
  assert.match(await readProjectFile(root, staged, 1, undefined, staged), /External requirements/);
  assert.equal(await readFile(source, "utf8"), "# External requirements\n\nOriginal source stays separate.\n");

  const sibling = path.join(root, ".agents/runtime/pi/inputs/unrelated.md");
  await writeFile(sibling, "must remain private\n");
  await assert.rejects(
    readProjectFile(root, ".agents/runtime/pi/inputs/unrelated.md", 1, undefined, staged),
    /excluded from the business-analysis profile/,
  );
});

test("Pi resource loading does not inherit project instructions, skills, or extensions", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "mainframe-pi-loader-"));
  await mkdir(path.join(root, ".agents/skills/private"), { recursive: true });
  await mkdir(path.join(root, ".pi/extensions"), { recursive: true });
  await writeFile(path.join(root, "AGENTS.md"), "instructions that must not load\n");
  await writeFile(
    path.join(root, ".agents/skills/private/SKILL.md"),
    "---\nname: private\ndescription: must not load\n---\n",
  );
  await writeFile(path.join(root, ".pi/extensions/unsafe.ts"), "throw new Error('must not load');\n");

  const loader = await createIsolatedLoader(root, "isolated system prompt");
  assert.equal(loader.getSystemPrompt(), "isolated system prompt");
  assert.deepEqual(loader.getAgentsFiles().agentsFiles, []);
  assert.deepEqual(loader.getSkills().skills, []);
  assert.deepEqual(loader.getExtensions().extensions, []);
});

test("profile config resolves logical model aliases without containing credentials", async () => {
  const profile = await loadProfile("config/profiles.example.json", "business-analysis");
  assert.deepEqual(profile.scouts, [
    { role: "independent-a", model: { provider: "minimax", model: "MiniMax-M3", thinking: "off" } },
    { role: "independent-b", model: { provider: "zai", model: "glm-5-turbo", thinking: "off" } },
  ]);
  assert.deepEqual(profile.critic, { provider: "minimax", model: "MiniMax-M3", thinking: "high" });
  assert.deepEqual(profile.consolidator, { provider: "zai", model: "glm-5.3", thinking: "max" });
  const source = await readFile("config/profiles.example.json", "utf8");
  assert(!/api.?key|token|secret/i.test(source));
});

test("a session too small to compact is a successful no-op", () => {
  assert.equal(isBenignCompactionNoop(new Error("Nothing to compact (session too small)")), true);
  assert.equal(isBenignCompactionNoop(new Error("Already compacted")), true);
  assert.equal(isBenignCompactionNoop(new Error("provider request failed")), false);
});

test("the turn limiter recognizes a requested terminal tool before its execution", () => {
  assert.equal(
    requestsCompletionTool(
      {
        role: "assistant",
        content: [{ type: "toolCall", id: "call-1", name: "submit_draft", arguments: {} }],
      } as never,
      "submit_draft",
    ),
    true,
  );
  assert.equal(
    requestsCompletionTool(
      {
        role: "assistant",
        content: [{ type: "toolCall", id: "call-2", name: "project_read", arguments: {} }],
      } as never,
      "submit_draft",
    ),
    false,
  );
});

test("GLM 5.3 exposes only the verified low, high, and max effort levels", () => {
  const adjusted = applyVerifiedThinkingContract(
    {
      provider: "zai",
      id: "glm-5.3",
      compat: { supportsReasoningEffort: false },
    } as never,
    { provider: "zai", model: "glm-5.3", thinking: "max" },
  );
  assert.equal((adjusted.compat as { supportsReasoningEffort?: boolean })?.supportsReasoningEffort, true);
  assert.deepEqual(adjusted.thinkingLevelMap, {
    off: null,
    minimal: null,
    low: "low",
    medium: null,
    high: "high",
    xhigh: null,
    max: "max",
  });
});

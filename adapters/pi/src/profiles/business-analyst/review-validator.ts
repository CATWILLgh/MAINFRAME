import { realpath, stat } from "node:fs/promises";
import path from "node:path";

import { isInside, resolveProjectRoot } from "../../paths.js";

export type Readiness = "ready" | "needs-answers" | "insufficient-context";

export interface ReviewValidation {
  errors: string[];
  readiness?: Readiness;
}

const REQUIRED_HEADINGS = [
  "# Business Analysis Review",
  "## Process understanding",
  "## Findings",
  "## Questions",
  "## Source-defined business scenarios",
  "## Implementation-confirmed scenarios",
  "## Readiness",
];

const FINDING_FIELDS = [
  "Scenario",
  "Gap or contradiction",
  "Consequence",
  "Evidence",
  "Question",
];

const SCENARIO_FIELDS = [
  "Initial state",
  "Event or action",
  "Expected business result",
  "Forbidden side effect",
  "Evidence",
];

function section(markdown: string, heading: string): string {
  const start = markdown.indexOf(`${heading}\n`);
  if (start < 0) return "";
  const bodyStart = start + heading.length + 1;
  const next = markdown.slice(bodyStart).search(/^#{1,2} /m);
  return next < 0 ? markdown.slice(bodyStart) : markdown.slice(bodyStart, bodyStart + next);
}

function requireFields(body: string, fields: string[], owner: string, errors: string[]): void {
  for (const field of fields) {
    if (!new RegExp(`^- ${field}:\\s*\\S`, "m").test(body)) {
      errors.push(`${owner} is missing '${field}'`);
    }
  }
}

export async function validateEvidenceReferences(
  projectRoot: string,
  references: string[],
  owner: string,
): Promise<string[]> {
  const errors: string[] = [];
  const root = await resolveProjectRoot(projectRoot);
  for (const rawReference of references) {
    const reference = rawReference.trim();
    if (/^https:\/\/[^\s]+$/.test(reference)) continue;
    const match = /^(.*):(\d+)(?:-(\d+))?$/.exec(reference);
    const relativePath = match?.[1]?.trim() ?? "";
    const firstLine = Number(match?.[2]);
    const lastLine = Number(match?.[3] ?? match?.[2]);
    if (!relativePath) {
      errors.push(`${owner} evidence must use project/path:line or an HTTPS URL: ${reference}`);
      continue;
    }
    const candidate = path.resolve(root, relativePath);
    if (!isInside(root, candidate)) {
      errors.push(`${owner} evidence is outside the project: ${reference}`);
      continue;
    }
    try {
      const resolved = await realpath(candidate);
      if (!isInside(root, resolved) || !(await stat(resolved)).isFile()) {
        errors.push(`${owner} evidence is outside the project or not a file: ${reference}`);
      } else {
        const content = await import("node:fs/promises").then(({ readFile }) => readFile(resolved, "utf8"));
        const lineCount = content.split("\n").length;
        if (firstLine < 1 || lastLine < firstLine || lastLine > lineCount) {
          errors.push(`${owner} evidence line is outside the file: ${reference}`);
        }
      }
    } catch {
      errors.push(`${owner} evidence does not exist: ${reference}`);
    }
  }
  return errors;
}

export async function validateReview(projectRoot: string, markdown: string): Promise<ReviewValidation> {
  const errors: string[] = [];
  const root = await resolveProjectRoot(projectRoot);

  let previous = -1;
  for (const heading of REQUIRED_HEADINGS) {
    const current = markdown.indexOf(heading);
    if (current < 0) {
      errors.push(`Missing heading: ${heading}`);
    } else if (current <= previous) {
      errors.push(`Heading is out of order: ${heading}`);
    }
    previous = Math.max(previous, current);
  }

  const findings = section(markdown, "## Findings");
  const findingMatches = [...findings.matchAll(/^### (F-\d{3}) — \[(process-blocker|concrete-risk|optional-improvement)\] .+$/gm)];
  if (findingMatches.length === 0 && !/^None\.\s*$/m.test(findings)) {
    errors.push("Findings must contain a typed finding or 'None.'");
  }
  for (let index = 0; index < findingMatches.length; index += 1) {
    const match = findingMatches[index];
    if (!match || match.index === undefined) continue;
    const next = findingMatches[index + 1]?.index ?? findings.length;
    const body = findings.slice(match.index + match[0].length, next);
    const owner = match[1] ?? `finding ${index + 1}`;
    requireFields(body, FINDING_FIELDS, owner, errors);
    const evidence = /^- Evidence:\s*(.+)$/m.exec(body)?.[1];
    if (evidence) errors.push(...(await validateEvidenceReferences(root, evidence.split(","), owner)));
  }

  const questions = section(markdown, "## Questions");
  const questionIds = new Set([...questions.matchAll(/^### (Q-\d{3})$/gm)].map((match) => match[1]));
  const questionMatches = [...questions.matchAll(/^### (Q-\d{3})$/gm)];
  if (questionMatches.length === 0 && !/^None\.\s*$/m.test(questions)) {
    errors.push("Questions must contain a question or 'None.'");
  }
  if (questionIds.size !== questionMatches.length) errors.push("Question ids must be unique");
  for (let index = 0; index < questionMatches.length; index += 1) {
    const match = questionMatches[index];
    if (!match || match.index === undefined) continue;
    const next = questionMatches[index + 1]?.index ?? questions.length;
    requireFields(questions.slice(match.index + match[0].length, next), ["Question"], match[1] ?? "question", errors);
  }
  for (const match of findings.matchAll(/^- Question:\s*(Q-\d{3})\s*$/gm)) {
    if (!questionIds.has(match[1])) errors.push(`Finding references missing question: ${match[1]}`);
  }

  for (const [heading, prefix] of [
    ["## Source-defined business scenarios", "R"],
    ["## Implementation-confirmed scenarios", "S"],
  ] as const) {
    const scenarios = section(markdown, heading);
    const scenarioMatches = [...scenarios.matchAll(new RegExp(`^### (${prefix}-\\d{3}) — .+$`, "gm"))];
    if (scenarioMatches.length === 0 && !/^None\.\s*$/m.test(scenarios)) {
      errors.push(`${heading.slice(3)} must contain a scenario or 'None.'`);
    }
    for (let index = 0; index < scenarioMatches.length; index += 1) {
      const match = scenarioMatches[index];
      if (!match || match.index === undefined) continue;
      const next = scenarioMatches[index + 1]?.index ?? scenarios.length;
      const body = scenarios.slice(match.index + match[0].length, next);
      const owner = match[1] ?? `scenario ${index + 1}`;
      requireFields(body, SCENARIO_FIELDS, owner, errors);
      if (prefix === "S") {
        const result = /^- Expected business result:\s*(.+)$/m.exec(body)?.[1] ?? "";
        const forbidden = /^- Forbidden side effect:\s*(.+)$/m.exec(body)?.[1] ?? "";
        if (/^(?:none\b|none of\b)/i.test(result)) {
          errors.push(`${owner} must describe a positively evidenced implemented result, not an absence`);
        }
        if (/^none possible\b/i.test(forbidden)) {
          errors.push(`${owner} must not claim that a side effect is impossible without explicit proof`);
        }
      }
      const evidence = /^- Evidence:\s*(.+)$/m.exec(body)?.[1];
      if (evidence) errors.push(...(await validateEvidenceReferences(root, evidence.split(","), owner)));
    }
    if (new Set(scenarioMatches.map((match) => match[1])).size !== scenarioMatches.length) {
      errors.push(`${prefix} scenario ids must be unique`);
    }
  }
  if (new Set(findingMatches.map((match) => match[1])).size !== findingMatches.length) {
    errors.push("Finding ids must be unique");
  }

  const readinessText = section(markdown, "## Readiness").trim();
  const readiness = ["ready", "needs-answers", "insufficient-context"].includes(readinessText)
    ? (readinessText as Readiness)
    : undefined;
  if (!readiness) errors.push("Readiness must be exactly ready, needs-answers, or insufficient-context");

  return readiness ? { errors, readiness } : { errors };
}

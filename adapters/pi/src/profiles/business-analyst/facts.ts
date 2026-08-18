import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import type { CollectorRole } from "../../model-types.js";
import { readProjectFile } from "../../project-tools.js";
import { validateEvidenceReferences } from "./review-validator.js";

export type ClaimKind =
  | "source-rule"
  | "implementation-fact"
  | "candidate-gap"
  | "candidate-conflict"
  | "external-fact";

export interface SourceSegment {
  id: string;
  startLine: number;
  endLine: number;
  preview: string;
}

export interface SubmittedClaim {
  statement: string;
  kind: ClaimKind;
  basis: "direct" | "inference";
  sourceSegmentIds: string[];
  evidence: string[];
  uncertainty: string;
  verificationQuestion: string;
}

export interface AtomicClaim extends SubmittedClaim {
  id: string;
  collector: CollectorRole;
}

export type VerificationVerdict =
  | "verified"
  | "partially-verified"
  | "unsupported"
  | "contradicted"
  | "duplicate";

export interface VerifiedClaim {
  claimId: string;
  verdict: VerificationVerdict;
  normalizedStatement: string;
  evidence: string[];
  reason: string;
  duplicateOf?: string;
}

export async function segmentEntryArtifact(
  projectRoot: string,
  entryPath: string,
  allowedRuntimeInput?: string,
): Promise<SourceSegment[]> {
  const numbered = await readProjectFile(projectRoot, entryPath, 1, 100_000, allowedRuntimeInput);
  const lines = numbered.split("\n").map((line) => {
    const match = /^(\d+): ?(.*)$/.exec(line);
    return { number: Number(match?.[1]), text: match?.[2] ?? "" };
  });
  const groups: Array<Array<{ number: number; text: string }>> = [];
  let current: Array<{ number: number; text: string }> = [];
  for (const line of lines) {
    const boundary = !line.text.trim() || (/^#{1,6}\s/.test(line.text) && current.length > 0);
    if (boundary && current.length > 0) {
      groups.push(current);
      current = [];
    }
    if (line.text.trim()) current.push(line);
    if (current.length >= 12) {
      groups.push(current);
      current = [];
    }
  }
  if (current.length) groups.push(current);
  return groups.map((group, index) => ({
    id: `SEG-${String(index + 1).padStart(3, "0")}`,
    startLine: group[0]!.number,
    endLine: group.at(-1)!.number,
    preview: group.map(({ text }) => text.trim()).join(" ").slice(0, 180),
  }));
}

export async function validateClaimSubmission(
  projectRoot: string,
  claims: SubmittedClaim[],
  noClaimSegmentIds: string[],
  segments: SourceSegment[],
): Promise<string[]> {
  const errors: string[] = [];
  const known = new Set(segments.map(({ id }) => id));
  const covered = new Set(noClaimSegmentIds);
  for (const id of noClaimSegmentIds) {
    if (!known.has(id)) errors.push(`Unknown no-claim segment: ${id}`);
  }
  for (const [index, claim] of claims.entries()) {
    const owner = `claim ${index + 1}`;
    if (!claim.statement.trim()) errors.push(`${owner} statement is empty`);
    if (!claim.evidence.length) errors.push(`${owner} has no evidence`);
    if (!claim.sourceSegmentIds.length && claim.kind === "source-rule") {
      errors.push(`${owner} source-rule has no source segment`);
    }
    for (const id of claim.sourceSegmentIds) {
      if (!known.has(id)) errors.push(`${owner} references unknown segment ${id}`);
      covered.add(id);
    }
    errors.push(...(await validateEvidenceReferences(projectRoot, claim.evidence, owner)));
  }
  for (const id of known) {
    if (!covered.has(id)) errors.push(`Primary-source segment was not accounted for: ${id}`);
  }
  return errors;
}

export function assignClaimIds(collector: CollectorRole, claims: SubmittedClaim[]): AtomicClaim[] {
  return claims.map((claim, index) => ({
    ...claim,
    id: `${collector.toUpperCase().replace(/[^A-Z0-9]+/g, "-")}-${String(index + 1).padStart(4, "0")}`,
    collector,
  }));
}

export async function writeJsonLines(filePath: string, rows: unknown[]): Promise<void> {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, "", { mode: 0o600 });
  for (const row of rows) await appendFile(filePath, `${JSON.stringify(row)}\n`, { mode: 0o600 });
}

export async function readJsonLines<T>(filePath: string): Promise<T[]> {
  const text = await readFile(filePath, "utf8");
  return text.split("\n").filter(Boolean).map((line) => JSON.parse(line) as T);
}

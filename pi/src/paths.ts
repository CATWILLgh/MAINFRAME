import { lstat, mkdir, realpath, stat } from "node:fs/promises";
import path from "node:path";

const INITIATIVE_SLUG = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

export function isInside(parent: string, candidate: string): boolean {
  const relative = path.relative(parent, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== "..");
}

export function assertInitiativeSlug(initiative: string): void {
  if (!INITIATIVE_SLUG.test(initiative)) {
    throw new Error(`Invalid initiative slug: ${initiative}`);
  }
}

export async function resolveProjectRoot(projectRoot: string): Promise<string> {
  const resolved = await realpath(projectRoot);
  const details = await stat(resolved);
  if (!details.isDirectory()) {
    throw new Error(`Project root is not a directory: ${projectRoot}`);
  }
  return resolved;
}

export async function resolveInitiativeDirectory(
  projectRoot: string,
  initiative: string,
): Promise<{ projectRoot: string; initiativeDirectory: string }> {
  assertInitiativeSlug(initiative);
  const resolvedProject = await resolveProjectRoot(projectRoot);
  const candidate = path.join(resolvedProject, "docs", "initiatives", initiative);
  const resolvedInitiative = await realpath(candidate);
  if (!isInside(resolvedProject, resolvedInitiative)) {
    throw new Error("Initiative directory resolves outside the project");
  }
  if (!(await stat(resolvedInitiative)).isDirectory()) {
    throw new Error(`Initiative is not a directory: ${initiative}`);
  }
  return { projectRoot: resolvedProject, initiativeDirectory: resolvedInitiative };
}

export async function ensureInitiativeDirectory(
  projectRoot: string,
  initiative: string,
): Promise<{ projectRoot: string; initiativeDirectory: string }> {
  assertInitiativeSlug(initiative);
  const resolvedProject = await resolveProjectRoot(projectRoot);
  const docs = await realpath(path.join(resolvedProject, "docs"));
  if (!isInside(resolvedProject, docs)) throw new Error("The docs directory resolves outside the project");
  const initiatives = path.join(docs, "initiatives");
  await mkdir(initiatives, { recursive: true });
  const resolvedInitiatives = await realpath(initiatives);
  if (!isInside(resolvedProject, resolvedInitiatives)) {
    throw new Error("The initiatives directory resolves outside the project");
  }
  const initiativeDirectory = path.join(resolvedInitiatives, initiative);
  await mkdir(initiativeDirectory, { recursive: true });
  const resolvedInitiative = await realpath(initiativeDirectory);
  if (!isInside(resolvedProject, resolvedInitiative)) {
    throw new Error("Initiative directory resolves outside the project");
  }
  return { projectRoot: resolvedProject, initiativeDirectory: resolvedInitiative };
}

export async function ensureReviewsDirectory(initiativeDirectory: string): Promise<string> {
  const reviews = path.join(initiativeDirectory, "reviews");
  await mkdir(reviews, { recursive: true });
  const linkDetails = await lstat(reviews);
  if (linkDetails.isSymbolicLink()) {
    throw new Error("The reviews directory must not be a symbolic link");
  }
  const resolved = await realpath(reviews);
  if (!isInside(initiativeDirectory, resolved)) {
    throw new Error("The reviews directory resolves outside the initiative");
  }
  return resolved;
}

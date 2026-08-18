import path from "node:path";

export const EXCLUDED_DIRECTORY_NAMES = new Set([
  ".agents",
  ".claude",
  ".codex",
  ".git",
  ".next",
  ".pi",
  ".pytest_cache",
  ".ruff_cache",
  ".tmp-plan",
  ".venv",
  ".zcode",
  "build",
  "coverage",
  "dist",
  "node_modules",
  "target",
]);

const SENSITIVE_BASENAMES = new Set([
  ".netrc",
  ".npmrc",
  ".pypirc",
  "auth.json",
  "credentials.json",
  "id_dsa",
  "id_ed25519",
  "id_rsa",
]);

const INSTRUCTION_BASENAMES = new Set(["agents.md", "claude.md"]);

export function normalizeRelative(relativePath: string): string {
  return relativePath.split(path.sep).join("/");
}

export function isExcludedRelativePath(relativePath: string): boolean {
  const normalized = normalizeRelative(relativePath);
  const basename = path.posix.basename(normalized).toLowerCase();
  if (normalized === ".agents/runtime/pi" || normalized.startsWith(".agents/runtime/pi/")) return true;
  if (basename === ".env" || basename.startsWith(".env.")) return true;
  if (INSTRUCTION_BASENAMES.has(basename)) return true;
  if (SENSITIVE_BASENAMES.has(basename)) return true;
  if (/\.(?:key|p12|pfx|pem)$/i.test(basename)) return true;
  return false;
}

export function isModelExcludedRelativePath(relativePath: string, allowedRuntimeInput?: string): boolean {
  const normalized = normalizeRelative(relativePath);
  if (normalized === ".agents/runtime/pi/project-map.json") return false;
  if (allowedRuntimeInput && normalized === normalizeRelative(allowedRuntimeInput)) return false;
  const firstSegment = normalized.split("/", 1)[0] ?? "";
  if (EXCLUDED_DIRECTORY_NAMES.has(firstSegment)) return true;
  return isExcludedRelativePath(normalized);
}

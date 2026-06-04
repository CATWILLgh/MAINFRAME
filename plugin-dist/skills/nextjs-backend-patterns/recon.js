#!/usr/bin/env node
// Deterministic Next.js backend stack recon. Stdlib only. Prints a RECON: block.
// Usage: node recon.js [project_root]
const fs = require("fs");
const path = require("path");

const root = process.argv[2] || process.cwd();
const read = (p) => { try { return fs.readFileSync(path.join(root, p), "utf8"); } catch { return null; } };
const exists = (p) => fs.existsSync(path.join(root, p));

let pkg = {};
try { pkg = JSON.parse(read("package.json") || "{}"); } catch { /* leave empty */ }
const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
const has = (n) => Object.prototype.hasOwnProperty.call(deps, n);

const nextVersion = deps.next || "not-found";

const appDir = exists("app") || exists("src/app");
const pagesDir = exists("pages") || exists("src/pages");
const router = appDir && pagesDir ? "mixed" : appDir ? "app" : pagesDir ? "pages" : "unknown";

const pm = exists("pnpm-lock.yaml") ? "pnpm"
  : exists("bun.lockb") ? "bun"
  : exists("yarn.lock") ? "yarn"
  : exists("package-lock.json") ? "npm" : "unknown";

const orm = (has("@prisma/client") || has("prisma")) ? "prisma"
  : has("drizzle-orm") ? "drizzle" : "none";

const auth = has("next-auth")
  ? (/(\b5|beta|next)/.test(String(deps["next-auth"])) ? "next-auth@5" : "next-auth@4")
  : has("@clerk/nextjs") ? "clerk"
  : has("lucia") ? "lucia" : "none";

const validation = has("zod") ? "zod" : has("valibot") ? "valibot" : "none";

let tsStrict = "unknown";
const tsconfig = read("tsconfig.json");
if (tsconfig) tsStrict = String(/"strict"\s*:\s*true/.test(tsconfig));

const out = [
  "RECON:",
  `  next_version: ${nextVersion}`,
  `  router: ${router}`,
  `  package_manager: ${pm}`,
  `  orm: ${orm}`,
  `  auth: ${auth}`,
  `  validation: ${validation}`,
  `  ts_strict: ${tsStrict}`,
];
if (nextVersion === "not-found") out.push("  WARNING: no `next` in dependencies — wrong agent?");
if (router === "mixed") out.push("  WARNING: app/ and pages/ both present — confirm the target.");
console.log(out.join("\n"));

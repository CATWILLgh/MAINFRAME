#!/usr/bin/env node
"use strict";
const fs = require("fs");
const path = require("path");
const cp = require("child_process");

const DETECT = {
  framework: [["vite", "vite"], ["next", "next"], ["@remix-run/react", "remix"], ["astro", "astro"], ["react-scripts", "cra"]],
  server_state: [["@tanstack/react-query", "tanstack-query"]],
  client_state: [["zustand", "zustand"], ["jotai", "jotai"], ["valtio", "valtio"], ["redux", "redux"], ["@reduxjs/toolkit", "redux"]],
  forms: [["react-hook-form", "rhf"]],
  validation: [["zod", "zod"], ["yup", "yup"]],
  tailwind: [["tailwindcss", "tailwind"]],
  design_system: [["@radix-ui/react-dialog", "radix-direct"], ["@mui/material", "mui"]],
  routing: [["react-router-dom", "react-router"], ["@tanstack/react-router", "tanstack-router"]],
  tables: [["@tanstack/react-table", "tanstack-table"]],
  http: [["axios", "axios"]],
};

function readJson(p) { try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return null; } }
function exists(p) { return fs.existsSync(p); }

function major(range) {
  if (!range) return null;
  const m = String(range).match(/(\d+)/);
  return m ? m[1] : null;
}

function detectPackageManager(root) {
  if (exists(path.join(root, "pnpm-lock.yaml"))) return "pnpm";
  if (exists(path.join(root, "bun.lock")) || exists(path.join(root, "bun.lockb"))) return "bun";
  if (exists(path.join(root, "yarn.lock"))) return "yarn";
  if (exists(path.join(root, "package-lock.json"))) return "npm";
  return "unknown";
}

function detectTsStrict(root) {
  const ts = readJson(path.join(root, "tsconfig.json"));
  if (!ts) return "unknown";
  const opts = ts.compilerOptions || {};
  if (opts.strict === true && opts.noUncheckedIndexedAccess === true) return "true+unchecked";
  if (opts.strict === true) return "true";
  return "false";
}

function detectArchSignal(root) {
  const src = path.join(root, "src");
  if (!exists(src)) return "unknown";
  const has = (d) => exists(path.join(src, d));
  const fsd = ["pages", "features", "entities", "widgets", "shared"].filter(has).length;
  const clean = ["presentation", "application", "domain", "infrastructure"].filter(has).length;
  if (fsd >= 2 && clean === 0) return "fsd";
  if (clean >= 2 && fsd === 0) return "clean";
  if (fsd >= 2 && clean >= 2) return "mixed";
  return "flat";
}

function tryShadcnInfo(root) {
  if (!exists(path.join(root, "components.json"))) return null;
  try {
    const out = cp.execFileSync("npx", ["--yes", "shadcn@latest", "info", "--json"],
      { cwd: root, timeout: 15000, stdio: ["ignore", "pipe", "ignore"] }).toString();
    return JSON.parse(out);
  } catch { return "components.json present, `shadcn info --json` failed"; }
}

function pickHits(deps, cands) {
  return [...new Set(cands.filter(([dep]) => deps[dep] !== undefined).map(([, label]) => label))];
}

function detectAll(root) {
  const pkg = readJson(path.join(root, "package.json")) || {};
  const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
  const out = {
    package_manager: detectPackageManager(root),
    react: major(deps["react"]) || "unknown",
    ts_strict: detectTsStrict(root),
    arch_signal: detectArchSignal(root),
  };
  for (const [cat, cands] of Object.entries(DETECT)) {
    const hits = pickHits(deps, cands);
    out[cat] = hits.length === 0 ? "none" : hits.length === 1 ? hits[0] : hits.join("+") + " (multiple — ask)";
  }
  out.server_state = out.server_state === "tanstack-query" ? `tanstack-query-${major(deps["@tanstack/react-query"]) || "?"}` : out.server_state;
  out.validation = out.validation === "zod" ? `zod-${major(deps["zod"]) || "?"}` : out.validation;
  out.tailwind = out.tailwind === "tailwind" ? `v${major(deps["tailwindcss"]) || "?"}` : out.tailwind;
  out.tables = out.tables === "tanstack-table" ? `tanstack-table-${major(deps["@tanstack/react-table"]) || "?"}` : out.tables;
  out.design_system = exists(path.join(root, "components.json")) ? (out.design_system === "none" ? "shadcn" : `shadcn+${out.design_system}`) : out.design_system;
  out.http = out.http === "axios" ? "axios" : "fetch";
  out.shadcn_info = tryShadcnInfo(root);
  return out;
}

function main() {
  const root = path.resolve(process.argv[2] || ".");
  const r = detectAll(root);
  console.log("RECON:");
  for (const [k, v] of Object.entries(r)) {
    if (k === "shadcn_info" && v && typeof v === "object") {
      console.log(`  shadcn_info: <inline JSON below>`);
      console.log(JSON.stringify(v, null, 2).split("\n").map(l => "    " + l).join("\n"));
    } else {
      console.log(`  ${k}: ${v ?? "none"}`);
    }
  }
}

main();

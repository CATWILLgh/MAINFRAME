#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const fail = (message) => {
  process.stderr.write(`mainframe-frontend recon: ${message}\n`);
  process.exit(2);
};

if (process.argv.length !== 3) {
  fail("usage: node recon.mjs <package-root>");
}

const packageRoot = path.resolve(process.argv[2]);
let rootStat;
try {
  rootStat = fs.statSync(packageRoot);
} catch {
  fail(`package root does not exist: ${packageRoot}`);
}
if (!rootStat.isDirectory()) fail(`package root is not a directory: ${packageRoot}`);

const packagePath = path.join(packageRoot, "package.json");
if (!fs.existsSync(packagePath)) fail(`package.json not found in: ${packageRoot}`);
if (fs.statSync(packagePath).size > 5 * 1024 * 1024) fail("package.json exceeds the 5 MiB reconnaissance limit");

let pkg;
try {
  pkg = JSON.parse(fs.readFileSync(packagePath, "utf8"));
} catch (error) {
  process.stdout.write(`${JSON.stringify({
    status: "invalid",
    package_root: packageRoot,
    manifest_errors: [`package.json could not be parsed: ${error?.name || "Error"}`],
  }, null, 2)}\n`);
  process.exit(1);
}
if (!pkg || typeof pkg !== "object" || Array.isArray(pkg)) fail("package.json does not contain an object");

const existsFile = (relative) => {
  try { return fs.statSync(path.join(packageRoot, relative)).isFile(); } catch { return false; }
};
const existsDirectory = (relative) => {
  try { return fs.statSync(path.join(packageRoot, relative)).isDirectory(); } catch { return false; }
};

const repositoryBoundary = (() => {
  let current = packageRoot;
  while (true) {
    if (fs.existsSync(path.join(current, ".git"))) return current;
    const parent = path.dirname(current);
    if (parent === current) return current;
    current = parent;
  }
})();

const nearestLockfile = (() => {
  const candidates = [
    ["pnpm", "pnpm-lock.yaml"], ["yarn", "yarn.lock"], ["bun", "bun.lock"],
    ["bun", "bun.lockb"], ["npm", "package-lock.json"],
  ];
  let current = packageRoot;
  while (true) {
    for (const [manager, filename] of candidates) {
      const candidate = path.join(current, filename);
      if (fs.existsSync(candidate)) {
        return { manager, path_from_package_root: path.relative(packageRoot, candidate) || filename };
      }
    }
    if (current === repositoryBoundary) return null;
    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
})();

const dependencySections = [
  pkg.dependencies, pkg.devDependencies, pkg.optionalDependencies, pkg.peerDependencies,
].filter((value) => value && typeof value === "object" && !Array.isArray(value));
const dependencies = Object.assign({}, ...dependencySections);
const has = (name) => Object.hasOwn(dependencies, name);
const detect = (mapping) => Object.entries(mapping)
  .filter(([, names]) => names.some(has))
  .map(([label]) => label)
  .sort();

const signals = {
  frameworks: detect({
    react: ["react"], next: ["next"], vite: ["vite"], remix: ["@remix-run/react"],
    astro: ["astro"], gatsby: ["gatsby"],
  }),
  routing: detect({
    "react-router": ["react-router", "react-router-dom"],
    "tanstack-router": ["@tanstack/react-router"],
  }),
  server_state: detect({
    "tanstack-query": ["@tanstack/react-query"], swr: ["swr"],
    apollo: ["@apollo/client"], urql: ["urql"],
  }),
  client_state: detect({
    redux: ["redux", "@reduxjs/toolkit"], zustand: ["zustand"], jotai: ["jotai"],
    valtio: ["valtio"], xstate: ["xstate"],
  }),
  forms_validation: detect({
    "react-hook-form": ["react-hook-form"], formik: ["formik"],
    zod: ["zod"], valibot: ["valibot"], yup: ["yup"],
  }),
  styling: detect({
    tailwind: ["tailwindcss"], "styled-components": ["styled-components"],
    emotion: ["@emotion/react"], sass: ["sass"],
  }),
  component_systems: detect({
    radix: ["@radix-ui/react-dialog"], "base-ui": ["@base-ui/react"],
    mui: ["@mui/material"], antd: ["antd"], chakra: ["@chakra-ui/react"],
    "react-aria": ["react-aria", "react-aria-components"],
  }),
  browser_capabilities: detect({
    indexeddb: ["dexie", "idb", "localforage"], pwa: ["vite-plugin-pwa", "workbox-precaching", "workbox-routing"],
    realtime: ["socket.io-client", "ws"], drag_drop: ["@dnd-kit/core", "@dnd-kit/sortable"],
    virtualization: ["@tanstack/react-virtual", "react-window"],
  }),
  content_data_ui: detect({
    tiptap: ["@tiptap/react"], lexical: ["lexical"], slate: ["slate-react"],
    markdown: ["react-markdown"], table: ["@tanstack/react-table"],
    charts: ["recharts", "chart.js", "react-chartjs-2"], graph: ["@xyflow/react"],
  }),
  testing: detect({
    vitest: ["vitest"], jest: ["jest"], "testing-library": ["@testing-library/react"],
    playwright: ["@playwright/test"], cypress: ["cypress"], msw: ["msw"],
    storybook: ["storybook", "@storybook/react", "@storybook/react-vite"],
    axe: ["axe-core", "vitest-axe"],
  }),
};

const componentConfig = (() => {
  const filename = "components.json";
  if (!existsFile(filename)) return { present: false, valid_json: null };
  const fullPath = path.join(packageRoot, filename);
  if (fs.statSync(fullPath).size > 1024 * 1024) {
    return { present: true, valid_json: false, limitation: "components.json exceeds the 1 MiB reconnaissance limit" };
  }
  try {
    const value = JSON.parse(fs.readFileSync(fullPath, "utf8"));
    return { present: true, valid_json: Boolean(value && typeof value === "object" && !Array.isArray(value)) };
  } catch {
    return { present: true, valid_json: false, limitation: "components.json could not be parsed" };
  }
})();

const scripts = pkg.scripts && typeof pkg.scripts === "object" && !Array.isArray(pkg.scripts)
  ? pkg.scripts
  : {};
const usefulScriptNames = Object.keys(scripts).filter((name) => (
  name.split(":").some((part) => [
    "build", "check", "dev", "e2e", "format", "generate", "lint", "preview",
    "start", "storybook", "test", "typecheck", "verify",
  ].includes(part.replace(/^(pre|post)/, "")))
)).sort();

const hasNext = has("next");
const hasApp = existsDirectory("app") || existsDirectory("src/app");
const hasPages = existsDirectory("pages") || existsDirectory("src/pages");
const tsconfigs = fs.readdirSync(packageRoot)
  .filter((name) => /^tsconfig(?:\.[^.]+)?\.json$/.test(name) && existsFile(name))
  .sort();

const limitations = componentConfig.limitation ? [componentConfig.limitation] : [];
const report = {
  status: limitations.length ? "partial" : "complete",
  package_root: packageRoot,
  repository_boundary: repositoryBoundary,
  package_management: { nearest_lockfile: nearestLockfile },
  runtime: {
    typescript_config_files: tsconfigs,
    declared_script_names: usefulScriptNames,
    next_router_hint: hasNext ? (hasApp && hasPages ? "mixed" : hasApp ? "app" : hasPages ? "pages" : null) : null,
  },
  component_configuration: componentConfig,
  signals,
  limitations,
  evidence_limits: [
    "declared dependencies are not installed-version or active-use proof",
    "dependency versions, sources, URLs, package names, and script bodies are intentionally omitted",
    "directory and configuration presence do not prove the served route, renderer, or component owner",
    "source files were not scanned and application code was not imported or executed",
    "environment variables, secrets, network resources, browsers, and runtime services were not inspected",
  ],
};

process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);

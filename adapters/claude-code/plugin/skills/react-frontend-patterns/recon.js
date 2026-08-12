#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const root = path.resolve(process.argv[2] || process.cwd());
const read = (name) => { try { return fs.readFileSync(path.join(root, name), "utf8"); } catch { return null; } };
const exists = (name) => fs.existsSync(path.join(root, name));
const findPackageManager = () => {
  const locks = [
    ["pnpm", "pnpm-lock.yaml"],
    ["yarn", "yarn.lock"],
    ["bun", "bun.lock"],
    ["bun", "bun.lockb"],
    ["npm", "package-lock.json"],
  ];
  let current = root;
  while (true) {
    for (const [manager, lock] of locks) {
      const candidate = path.join(current, lock);
      if (fs.existsSync(candidate)) return { manager, lockfile: candidate };
    }
    if (fs.existsSync(path.join(current, ".git"))) break;
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return { manager: null, lockfile: null };
};
let pkg = {};
try { pkg = JSON.parse(read("package.json") || "{}"); } catch {}
const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}), ...(pkg.peerDependencies || {}) };
const present = (...names) => names.filter((name) => Object.prototype.hasOwnProperty.call(deps, name));
const versions = (names) => Object.fromEntries(names.map((name) => [name, deps[name]]));
const group = (names) => versions(present(...names));
const app = exists("app") || exists("src/app");
const pages = exists("pages") || exists("src/pages");
const hasNext = Object.prototype.hasOwnProperty.call(deps, "next");
const compilerFlag = (text, name) => {
  const match = text.match(new RegExp(`["']${name}["']\\s*:\\s*(true|false)`));
  return match ? match[1] === "true" : null;
};
const typescriptConfigs = (() => {
  let names = [];
  try {
    names = fs.readdirSync(root)
      .filter((name) => /^tsconfig(?:\.[^.]+)?\.json$/.test(name))
      .sort();
  } catch {}
  return names.map((name) => {
    const text = read(name) || "";
    const extendsMatch = text.match(/["']extends["']\s*:\s*["']([^"']+)["']/);
    const references = [...text.matchAll(/["']path["']\s*:\s*["']([^"']+)["']/g)]
      .map((match) => match[1]);
    return {
      file: name,
      extends: extendsMatch ? extendsMatch[1] : null,
      references,
      strictness: {
        strict: compilerFlag(text, "strict"),
        noUncheckedIndexedAccess: compilerFlag(text, "noUncheckedIndexedAccess"),
      },
    };
  });
})();
const packageManager = findPackageManager();
const usefulScript = (name) => {
  const useful = new Set([
    "build", "check", "dev", "e2e", "format", "generate", "lint",
    "preview", "start", "storybook", "test", "typecheck", "verify",
  ]);
  const parts = name.split(":");
  const matches = (part) => useful.has(part)
    || useful.has(part.replace(/^(pre|post)/, ""));
  if (["db", "migrate", "migration", "seed"].includes(parts[0])) {
    return parts.some((part) => ["check", "test", "verify"].includes(part));
  }
  return parts.some(matches);
};

const result = {
  package_root: root,
  package: pkg.name || null,
  package_manager: packageManager.manager,
  package_manager_lockfile: packageManager.lockfile,
  dependency_values: "declared package.json specifiers; verify installed resolutions",
  runtime: {
    react_declared: deps.react || null,
    typescript_declared: deps.typescript || null,
    typescript_configs: typescriptConfigs,
  },
  frameworks: group(["vite", "next", "@remix-run/react", "astro", "react-scripts"]),
  next_router: hasNext ? (app && pages ? "mixed" : app ? "app" : pages ? "pages" : null) : null,
  routing: group(["react-router-dom", "@tanstack/react-router"]),
  server_state: group(["@tanstack/react-query", "swr", "@apollo/client", "urql"]),
  client_state: group(["zustand", "jotai", "valtio", "@reduxjs/toolkit", "redux", "xstate"]),
  forms: group(["react-hook-form", "@hookform/resolvers", "formik"]),
  validation: group(["zod", "valibot", "yup"]),
  styling: group(["tailwindcss", "styled-components", "@emotion/react"]),
  ui: { components_json: exists("components.json"), ...group(["@base-ui/react", "@radix-ui/react-dialog", "@mui/material", "antd"]) },
  offline: group(["dexie", "idb", "localforage", "vite-plugin-pwa", "workbox-precaching", "workbox-routing", "@tanstack/react-query-persist-client", "@tanstack/query-sync-storage-persister", "@tanstack/query-async-storage-persister"]),
  realtime: group(["socket.io-client", "ws"]),
  content: group(["@tiptap/react", "lexical", "slate-react", "react-markdown", "rehype-sanitize"]),
  data_ui: group(["@tanstack/react-table", "recharts", "qrcode", "jsbarcode", "xlsx"]),
  interaction_ui: group(["@dnd-kit/core", "@dnd-kit/sortable", "react-draggable", "@xyflow/react", "@tanstack/react-virtual"]),
  http: group(["axios", "ky"]),
  tests: group(["vitest", "jest", "@testing-library/react", "@testing-library/user-event", "@playwright/test", "cypress", "msw", "storybook", "@storybook/react-vite", "axe-core", "vitest-axe"]),
  scripts: Object.fromEntries(Object.entries(pkg.scripts || {}).filter(([name]) => usefulScript(name))),
};

console.log(JSON.stringify(result, null, 2));

#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const root = path.resolve(process.argv[2] || process.cwd());
const read = (name) => { try { return fs.readFileSync(path.join(root, name), "utf8"); } catch { return null; } };
const exists = (name) => fs.existsSync(path.join(root, name));
let pkg = {};
try { pkg = JSON.parse(read("package.json") || "{}"); } catch {}
const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}), ...(pkg.peerDependencies || {}) };
const present = (...names) => names.filter((name) => Object.prototype.hasOwnProperty.call(deps, name));
const versions = (names) => Object.fromEntries(names.map((name) => [name, deps[name]]));
const group = (names) => versions(present(...names));
const app = exists("app") || exists("src/app");
const pages = exists("pages") || exists("src/pages");
const hasNext = Object.prototype.hasOwnProperty.call(deps, "next");
const tsconfig = read("tsconfig.json") || "";

const result = {
  package_root: root,
  package: pkg.name || null,
  package_manager: exists("pnpm-lock.yaml") ? "pnpm" : exists("yarn.lock") ? "yarn" : exists("bun.lock") || exists("bun.lockb") ? "bun" : exists("package-lock.json") ? "npm" : null,
  runtime: { react: deps.react || null, typescript: deps.typescript || null, strict: /["']strict["']\s*:\s*true/.test(tsconfig), no_unchecked_indexed_access: /["']noUncheckedIndexedAccess["']\s*:\s*true/.test(tsconfig) },
  frameworks: group(["vite", "next", "@remix-run/react", "astro", "react-scripts"]),
  next_router: hasNext ? (app && pages ? "mixed" : app ? "app" : pages ? "pages" : null) : null,
  routing: group(["react-router-dom", "@tanstack/react-router"]),
  server_state: group(["@tanstack/react-query", "swr", "@apollo/client", "urql"]),
  client_state: group(["zustand", "jotai", "valtio", "@reduxjs/toolkit", "redux", "xstate"]),
  forms: group(["react-hook-form", "@hookform/resolvers", "formik"]),
  validation: group(["zod", "valibot", "yup"]),
  styling: group(["tailwindcss", "styled-components", "@emotion/react"]),
  ui: { components_json: exists("components.json"), ...group(["@base-ui/react", "@radix-ui/react-dialog", "@mui/material", "antd"]) },
  offline: group(["dexie", "idb", "vite-plugin-pwa", "workbox-precaching", "workbox-routing"]),
  realtime: group(["socket.io-client", "ws"]),
  content: group(["@tiptap/react", "lexical", "slate-react", "react-markdown", "rehype-sanitize"]),
  data_ui: group(["@tanstack/react-table", "recharts", "qrcode", "jsbarcode", "xlsx"]),
  http: group(["axios", "ky"]),
  tests: group(["vitest", "jest", "@testing-library/react", "@playwright/test", "cypress"]),
  scripts: pkg.scripts || {},
};

console.log(JSON.stringify(result, null, 2));

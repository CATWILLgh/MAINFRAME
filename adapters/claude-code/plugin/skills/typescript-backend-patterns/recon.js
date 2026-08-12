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
const app = exists("app") || exists("src/app");
const pages = exists("pages") || exists("src/pages");
const tsconfig = read("tsconfig.json") || "";
const group = (names) => versions(present(...names));

const result = {
  package_root: root,
  package: pkg.name || null,
  package_manager: exists("pnpm-lock.yaml") ? "pnpm" : exists("yarn.lock") ? "yarn" : exists("bun.lock") || exists("bun.lockb") ? "bun" : exists("package-lock.json") ? "npm" : null,
  runtime: { node: pkg.engines?.node || null, typescript: deps.typescript || null, module_type: pkg.type || "commonjs-default", strict: /["']strict["']\s*:\s*true/.test(tsconfig) },
  frameworks: group(["@nestjs/core", "next", "express", "fastify", "@nestjs/platform-express", "@nestjs/platform-fastify"]),
  next_router: app && pages ? "mixed" : app ? "app" : pages ? "pages" : null,
  data: group(["@prisma/client", "prisma", "typeorm", "drizzle-orm", "pg", "postgres"]),
  validation: group(["zod", "class-validator", "valibot", "ajv"]),
  auth: group(["next-auth", "@auth/core", "passport", "@nestjs/passport", "jose", "jsonwebtoken", "@clerk/nextjs"]),
  contracts: group(["@nestjs/swagger", "swagger-ui-express", "ajv", "@stoplight/prism-cli"]),
  http_clients: group(["axios", "@nestjs/axios", "undici", "got"]),
  background: group(["bullmq", "pg-boss", "agenda", "@nestjs/schedule"]),
  realtime: group(["socket.io", "ws", "@nestjs/websockets"]),
  storage: group(["minio", "@aws-sdk/client-s3", "multer", "busboy"]),
  resilience: group(["opossum", "p-retry", "bottleneck", "lru-cache", "ioredis", "redis"]),
  observability: group(["pino", "nestjs-pino", "winston", "@opentelemetry/api", "@sentry/node"]),
  tests: group(["jest", "vitest", "@playwright/test", "supertest", "testcontainers", "@testcontainers/postgresql"]),
  scripts: pkg.scripts || {},
};

console.log(JSON.stringify(result, null, 2));

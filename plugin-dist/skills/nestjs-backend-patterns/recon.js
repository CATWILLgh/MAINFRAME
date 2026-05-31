#!/usr/bin/env node
"use strict";
const fs = require("fs");
const path = require("path");

const DETECT = {
  framework: [["@nestjs/core", "nestjs"], ["express", "express"], ["fastify", "fastify"],
              ["koa", "koa"], ["@adonisjs/core", "adonisjs"]],
  orm: [["@prisma/client", "prisma"], ["drizzle-orm", "drizzle"], ["typeorm", "typeorm"]],
  validation: [["zod", "zod"], ["class-validator", "class-validator"], ["joi", "joi"]],
  auth: [["@nestjs/passport", "passport+jwt"], ["passport-jwt", "passport+jwt"],
         ["jsonwebtoken", "jwt-direct"]],
  background_workers: [["bullmq", "bullmq"], ["bull", "bull"], ["agenda", "agenda"], ["bee-queue", "bee-queue"]],
  caching: [["redis", "redis"], ["ioredis", "redis"], ["cache-manager", "cache-manager"], ["keyv", "keyv"]],
  error_reporting: [["@sentry/nestjs", "sentry"], ["@sentry/node", "sentry"]],
  observability: [["@opentelemetry/api", "otel"], ["pino", "pino"]],
  openapi_gen: [["@nestjs/swagger", "nestjs-swagger"], ["@fastify/swagger", "fastify-swagger"],
                ["swagger-ui-express", "swagger-ui-express"]],
  testing: [["testcontainers", "jest+testcontainers"], ["jest", "jest"]],
  websockets: [["@nestjs/websockets", "nestjs-ws"], ["socket.io", "socket.io"], ["ws", "ws"]],
};

function readJson(p) { try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return null; } }

function detectPackageManager(root) {
  if (fs.existsSync(path.join(root, "pnpm-lock.yaml"))) return "pnpm";
  if (fs.existsSync(path.join(root, "bun.lockb"))) return "bun";
  if (fs.existsSync(path.join(root, "yarn.lock"))) return "yarn";
  if (fs.existsSync(path.join(root, "package-lock.json"))) return "npm";
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

function detectAll(root) {
  const pkg = readJson(path.join(root, "package.json")) || {};
  const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
  const out = {
    node_version: (pkg.engines && pkg.engines.node) || "unknown",
    package_manager: detectPackageManager(root),
    ts_strict: detectTsStrict(root),
  };
  for (const [cat, cands] of Object.entries(DETECT)) {
    const hits = [...new Set(cands.filter(([dep]) => deps[dep] !== undefined).map(([, label]) => label))];
    out[cat] = hits.length === 0 ? "none" : hits.length === 1 ? hits[0] : hits.join("+") + " (multiple — ask)";
  }
  return out;
}

function main() {
  const root = path.resolve(process.argv[2] || ".");
  const r = detectAll(root);
  console.log("RECON:");
  for (const [k, v] of Object.entries(r)) console.log(`  ${k}: ${v}`);
}

main();

#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const root = path.resolve(process.argv[2] || process.cwd());
const read = (name) => {
  try { return fs.readFileSync(path.join(root, name), "utf8"); }
  catch { return null; }
};
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
const deps = {
  ...(pkg.dependencies || {}),
  ...(pkg.devDependencies || {}),
  ...(pkg.peerDependencies || {}),
};
const present = (...names) => names.filter((name) => Object.hasOwn(deps, name));
const versions = (names) => Object.fromEntries(names.map((name) => [name, deps[name]]));
const group = (names) => versions(present(...names));
const app = exists("app") || exists("src/app");
const pages = exists("pages") || exists("src/pages");
const tsconfig = read("tsconfig.json") || "";
const hasNext = present("next").length > 0;
const compilerFlag = (name) => {
  const match = tsconfig.match(new RegExp(`["']${name}["']\\s*:\\s*(true|false)`));
  return match ? match[1] === "true" : null;
};
const extendsMatch = tsconfig.match(/["']extends["']\s*:\s*["']([^"']+)["']/);
const packageManager = findPackageManager();
const usefulScript = (name) => name.split(":").some((part) => [
  "build", "check", "contract", "contracts", "dev", "format", "lint",
  "migrate", "migration", "start", "test", "typecheck", "verify",
].includes(part));

const result = {
  package_root: root,
  package: pkg.name || null,
  package_manager: packageManager.manager,
  package_manager_lockfile: packageManager.lockfile,
  dependency_values: "declared package.json specifiers; verify installed resolutions",
  runtime: {
    node_declared: pkg.engines?.node || null,
    typescript_declared: deps.typescript || null,
    module_type: pkg.type || "commonjs-default",
    tsconfig_extends: extendsMatch ? extendsMatch[1] : null,
    strictness: {
      strict: compilerFlag("strict"),
      strictNullChecks: compilerFlag("strictNullChecks"),
      noImplicitAny: compilerFlag("noImplicitAny"),
      noImplicitThis: compilerFlag("noImplicitThis"),
      strictFunctionTypes: compilerFlag("strictFunctionTypes"),
      strictBindCallApply: compilerFlag("strictBindCallApply"),
      useUnknownInCatchVariables: compilerFlag("useUnknownInCatchVariables"),
    },
  },
  frameworks: group(["@nestjs/core", "next", "express", "fastify", "@nestjs/platform-express", "@nestjs/platform-fastify"]),
  next_router: hasNext ? (app && pages ? "mixed" : app ? "app" : pages ? "pages" : null) : null,
  data: group(["@prisma/client", "prisma", "typeorm", "@nestjs/typeorm", "drizzle-orm", "drizzle-kit", "pg", "postgres"]),
  validation: group(["zod", "class-validator", "class-transformer", "valibot", "ajv", "ajv-formats"]),
  auth: group(["next-auth", "@auth/core", "passport", "@nestjs/passport", "@nestjs/jwt", "jose", "jsonwebtoken", "@clerk/nextjs"]),
  contracts: group(["@nestjs/swagger", "swagger-ui-express", "@apidevtools/swagger-parser", "ajv", "@stoplight/prism-cli"]),
  http_clients: group(["axios", "@nestjs/axios", "undici", "got"]),
  background: group(["bullmq", "@nestjs/bullmq", "pg-boss", "agenda", "@nestjs/schedule"]),
  realtime: group(["socket.io", "ws", "@nestjs/websockets", "@nestjs/platform-socket.io"]),
  storage: group(["minio", "@aws-sdk/client-s3", "multer", "busboy"]),
  resilience: group(["opossum", "p-retry", "bottleneck", "lru-cache", "ioredis", "redis"]),
  observability: group(["pino", "nestjs-pino", "winston", "@opentelemetry/api", "@sentry/node"]),
  tests: group(["jest", "vitest", "@nestjs/testing", "@playwright/test", "supertest", "testcontainers", "@testcontainers/postgresql"]),
  scripts: Object.fromEntries(Object.entries(pkg.scripts || {}).filter(([name]) => usefulScript(name))),
};

console.log(JSON.stringify(result, null, 2));

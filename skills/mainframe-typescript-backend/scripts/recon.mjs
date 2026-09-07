#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const fail = (message) => {
  process.stderr.write(`mainframe-typescript-backend recon: ${message}\n`);
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
if (!rootStat.isDirectory()) {
  fail(`package root is not a directory: ${packageRoot}`);
}

const packagePath = path.join(packageRoot, "package.json");
if (!fs.existsSync(packagePath)) {
  fail(`package.json not found in: ${packageRoot}`);
}

const readText = (filePath) => {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch {
    return null;
  }
};

const parseJson = (text, label) => {
  try {
    return { value: JSON.parse(text), error: null };
  } catch (error) {
    return { value: null, error: `${label}: ${error.message}` };
  }
};

const stripJsonComments = (text) => {
  let result = "";
  let quoted = false;
  let escaped = false;
  let lineComment = false;
  let blockComment = false;

  for (let index = 0; index < text.length; index += 1) {
    const current = text[index];
    const next = text[index + 1];

    if (lineComment) {
      if (current === "\n" || current === "\r") {
        lineComment = false;
        result += current;
      } else {
        result += " ";
      }
      continue;
    }
    if (blockComment) {
      if (current === "*" && next === "/") {
        result += "  ";
        index += 1;
        blockComment = false;
      } else {
        result += current === "\n" || current === "\r" ? current : " ";
      }
      continue;
    }
    if (quoted) {
      result += current;
      if (escaped) escaped = false;
      else if (current === "\\") escaped = true;
      else if (current === '"') quoted = false;
      continue;
    }
    if (current === '"') {
      quoted = true;
      result += current;
    } else if (current === "/" && next === "/") {
      result += "  ";
      index += 1;
      lineComment = true;
    } else if (current === "/" && next === "*") {
      result += "  ";
      index += 1;
      blockComment = true;
    } else {
      result += current;
    }
  }
  return result;
};

const removeTrailingCommas = (text) => {
  let result = "";
  let quoted = false;
  let escaped = false;
  for (let index = 0; index < text.length; index += 1) {
    const current = text[index];
    if (quoted) {
      result += current;
      if (escaped) escaped = false;
      else if (current === "\\") escaped = true;
      else if (current === '"') quoted = false;
      continue;
    }
    if (current === '"') {
      quoted = true;
      result += current;
      continue;
    }
    if (current === ",") {
      let cursor = index + 1;
      while (/\s/.test(text[cursor] || "")) cursor += 1;
      if (text[cursor] === "}" || text[cursor] === "]") continue;
    }
    result += current;
  }
  return result;
};

const packageResult = parseJson(readText(packagePath), "package.json parse error");
if (!packageResult.value || typeof packageResult.value !== "object") {
  fail(packageResult.error || "package.json does not contain an object");
}
const pkg = packageResult.value;

const repositoryBoundary = (() => {
  let current = packageRoot;
  while (true) {
    if (fs.existsSync(path.join(current, ".git"))) return current;
    const parent = path.dirname(current);
    if (parent === current) return current;
    current = parent;
  }
})();

const lockfiles = [
  ["pnpm", "pnpm-lock.yaml"],
  ["yarn", "yarn.lock"],
  ["bun", "bun.lock"],
  ["bun", "bun.lockb"],
  ["npm", "package-lock.json"],
];

const nearestLockfile = (() => {
  let current = packageRoot;
  while (true) {
    for (const [manager, filename] of lockfiles) {
      const candidate = path.join(current, filename);
      if (fs.existsSync(candidate)) {
        return {
          manager,
          path_from_package_root: path.relative(packageRoot, candidate) || filename,
        };
      }
    }
    if (current === repositoryBoundary) return null;
    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
})();

const dependencySections = [
  pkg.dependencies,
  pkg.devDependencies,
  pkg.optionalDependencies,
  pkg.peerDependencies,
].filter((section) => section && typeof section === "object");
const dependencies = Object.assign({}, ...dependencySections);

const safeSpecifier = (value) => {
  if (typeof value !== "string") return null;
  if (/^[A-Za-z0-9*~^<>=| ._+:-]+$/.test(value)) return value;
  return "[non-registry specifier omitted]";
};
const safePackageManager = (value) => {
  if (typeof value !== "string") return null;
  if (/^(npm|pnpm|yarn|bun)@[A-Za-z0-9._+~-]+$/.test(value)) return value;
  return "[unrecognized declaration omitted]";
};
const group = (names) => Object.fromEntries(
  names
    .filter((name) => Object.hasOwn(dependencies, name))
    .map((name) => [name, safeSpecifier(dependencies[name])]),
);

const tsconfigPath = path.join(packageRoot, "tsconfig.json");
const tsconfigText = readText(tsconfigPath);
let tsconfig = null;
let tsconfigError = null;
if (tsconfigText !== null) {
  const parsed = parseJson(
    removeTrailingCommas(stripJsonComments(tsconfigText)),
    "tsconfig.json parse error",
  );
  tsconfig = parsed.value;
  tsconfigError = parsed.error;
}

const compilerOptions = tsconfig?.compilerOptions || {};
const directCompilerOption = (name) => (
  Object.hasOwn(compilerOptions, name) ? compilerOptions[name] : null
);
const existsDirectory = (relativePath) => {
  try {
    return fs.statSync(path.join(packageRoot, relativePath)).isDirectory();
  } catch {
    return false;
  }
};

const scriptNames = Object.keys(pkg.scripts || {}).filter((name) => (
  name.split(":").some((part) => [
    "build", "check", "contract", "contracts", "dev", "format", "lint",
    "migrate", "migration", "start", "test", "typecheck", "verify",
  ].includes(part))
)).sort();

const hasNext = Object.hasOwn(dependencies, "next");
const hasApp = existsDirectory("app") || existsDirectory("src/app");
const hasPages = existsDirectory("pages") || existsDirectory("src/pages");

const result = {
  package_root: packageRoot,
  repository_boundary: repositoryBoundary,
  package: typeof pkg.name === "string" ? pkg.name : null,
  package_manager: {
    declared: safePackageManager(pkg.packageManager),
    nearest_lockfile: nearestLockfile,
  },
  evidence_limits: [
    "dependency values are declared specifiers, not installed resolutions or proof of active use",
    "script bodies are intentionally omitted",
    "compiler options are direct values only and may be inherited or overridden",
    "directory presence does not prove the active entrypoint or router",
  ],
  runtime: {
    node_declared: safeSpecifier(pkg.engines?.node),
    typescript_declared: safeSpecifier(dependencies.typescript),
    package_type: pkg.type === "module" || pkg.type === "commonjs" ? pkg.type : null,
    exports_present: Object.hasOwn(pkg, "exports"),
    main_present: Object.hasOwn(pkg, "main"),
    tsconfig_present: tsconfigText !== null,
    tsconfig_error: tsconfigError,
    tsconfig_extends: tsconfig?.extends ?? null,
    direct_compiler_options: {
      module: directCompilerOption("module"),
      moduleResolution: directCompilerOption("moduleResolution"),
      strict: directCompilerOption("strict"),
      strictNullChecks: directCompilerOption("strictNullChecks"),
      noImplicitAny: directCompilerOption("noImplicitAny"),
      useUnknownInCatchVariables: directCompilerOption("useUnknownInCatchVariables"),
    },
  },
  frameworks: group([
    "@nestjs/core", "@nestjs/platform-express", "@nestjs/platform-fastify",
    "next", "express", "fastify", "hono", "koa", "@trpc/server",
  ]),
  next_router_hint: hasNext ? (hasApp && hasPages ? "mixed" : hasApp ? "app" : hasPages ? "pages" : null) : null,
  data: group([
    "@prisma/client", "prisma", "typeorm", "@nestjs/typeorm", "drizzle-orm",
    "drizzle-kit", "pg", "postgres", "mysql2", "better-sqlite3",
    "@libsql/client", "mongodb", "mongoose",
  ]),
  validation: group([
    "zod", "class-validator", "class-transformer", "valibot", "ajv",
    "ajv-formats", "joi", "yup",
  ]),
  auth: group([
    "next-auth", "@auth/core", "passport", "@nestjs/passport", "@nestjs/jwt",
    "jose", "jsonwebtoken", "@clerk/nextjs",
  ]),
  contracts: group([
    "@nestjs/swagger", "swagger-ui-express", "@apidevtools/swagger-parser",
    "@trpc/server", "graphql", "@nestjs/graphql",
  ]),
  http_clients: group(["axios", "@nestjs/axios", "undici", "got", "ky"]),
  background: group([
    "bullmq", "@nestjs/bullmq", "pg-boss", "agenda", "@nestjs/schedule",
  ]),
  realtime: group([
    "socket.io", "ws", "@nestjs/websockets", "@nestjs/platform-socket.io",
  ]),
  storage: group([
    "minio", "@aws-sdk/client-s3", "multer", "busboy",
  ]),
  cache_and_resilience: group([
    "redis", "ioredis", "lru-cache", "opossum", "p-retry", "bottleneck",
  ]),
  observability: group([
    "pino", "nestjs-pino", "winston", "@opentelemetry/api", "@sentry/node",
  ]),
  tests: group([
    "node:test", "jest", "vitest", "@nestjs/testing", "@playwright/test",
    "supertest", "testcontainers", "@testcontainers/postgresql",
  ]),
  relevant_script_names: scriptNames,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);

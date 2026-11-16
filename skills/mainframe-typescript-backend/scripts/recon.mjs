#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const fail = (message) => {
  process.stderr.write(`${JSON.stringify({ error: message })}\n`);
  process.exit(2);
};

const MAX_FILE_BYTES = 1024 * 1024;
const MAX_VALUE_CHARS = 256;
const MAX_DECLARATION_CHARS = 4096;
const MAX_SCRIPT_NAMES = 48;
const MAX_CONFIG_REFERENCES = 16;
const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

if (process.argv.length !== 3) {
  fail("usage: node recon.mjs <package-root>");
}

const packageRoot = path.resolve(process.argv[2]);

let rootStat;
try {
  rootStat = fs.statSync(packageRoot);
} catch {
  fail("package root is unavailable");
}
if (!rootStat.isDirectory()) {
  fail("package root is not a directory");
}

const packagePath = path.join(packageRoot, "package.json");
const readText = (filePath, label) => {
  let descriptor;
  try {
    // Non-blocking open lets fstat reject FIFOs without waiting for a writer.
    descriptor = fs.openSync(filePath, fs.constants.O_RDONLY | fs.constants.O_NONBLOCK);
    const stat = fs.fstatSync(descriptor);
    if (!stat.isFile()) return { present: true, error: `${label}: not a regular file` };
    if (stat.size > MAX_FILE_BYTES) return { present: true, error: `${label}: size limit exceeded` };
    const buffer = Buffer.alloc(MAX_FILE_BYTES + 1);
    let length = 0;
    while (length < buffer.length) {
      const count = fs.readSync(descriptor, buffer, length, buffer.length - length, null);
      if (count === 0) break;
      length += count;
    }
    if (length > MAX_FILE_BYTES) return { present: true, error: `${label}: size limit exceeded` };
    return { present: true, text: buffer.toString("utf8", 0, length), error: null };
  } catch (error) {
    if (error.code === "ENOENT") return { present: false, error: null };
    return { present: true, error: `${label}: read unavailable` };
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
};

const parseJson = (text, label) => {
  try {
    return { value: JSON.parse(text), error: null };
  } catch {
    return { value: null, error: `${label}: invalid JSON` };
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

const packageText = readText(packagePath, "package.json");
if (!packageText.present || packageText.error) {
  fail(packageText.error || "package.json: file not found");
}
const packageResult = parseJson(packageText.text, "package.json parse error");
if (!isObject(packageResult.value)) {
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

const omissions = new Set();
const omit = (label, reason) => {
  omissions.add(`${label}: ${reason}; omitted`);
  return null;
};
let declarationChars = 0;
const boundedString = (value, label, valid = () => true) => {
  if (value === undefined) return null;
  if (typeof value !== "string" || !value || /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/.test(value)) {
    return omit(label, "invalid value");
  }
  if (value.length > MAX_VALUE_CHARS) return omit(label, "length limit exceeded");
  if (!valid(value)) return omit(label, "unrecognized value");
  if (declarationChars + value.length > MAX_DECLARATION_CHARS) {
    return omit(label, "total declaration limit exceeded");
  }
  declarationChars += value.length;
  return value;
};
const objectSection = (value, label) => {
  if (value === undefined) return {};
  if (isObject(value)) return value;
  omit(label, "expected an object");
  return {};
};
const dependencySections = ["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"]
  .map((name) => objectSection(pkg[name], name));
const dependencies = Object.assign(Object.create(null), ...dependencySections);

const safeSpecifier = (value, label) => boundedString(
  value, label, (text) => /^[A-Za-z0-9*~^<>=| ._+:-]+$/.test(text),
);
const safePackageManager = (value) => boundedString(
  value, "package_manager", (text) => /^(npm|pnpm|yarn|bun)@[A-Za-z0-9._+~-]+$/.test(text),
);
const group = (names) => Object.fromEntries(
  names
    .filter((name) => Object.hasOwn(dependencies, name))
    .map((name) => [name, safeSpecifier(dependencies[name], `dependency ${name}`)]),
);

const tsconfigPath = path.join(packageRoot, "tsconfig.json");
const tsconfigText = readText(tsconfigPath, "tsconfig.json");
let tsconfig = null;
let tsconfigError = tsconfigText.error;
if (tsconfigText.text !== undefined) {
  const parsed = parseJson(
    removeTrailingCommas(stripJsonComments(tsconfigText.text)),
    "tsconfig.json parse error",
  );
  tsconfig = isObject(parsed.value) ? parsed.value : null;
  tsconfigError = parsed.error || (tsconfig === null ? "tsconfig.json: expected an object" : null);
}

const compilerOptions = objectSection(tsconfig?.compilerOptions, "compilerOptions");
const directCompilerOption = (name) => {
  if (!Object.hasOwn(compilerOptions, name)) return null;
  const value = compilerOptions[name];
  if (name === "module" || name === "moduleResolution") {
    return boundedString(value, `compilerOptions.${name}`);
  }
  return typeof value === "boolean" ? value : omit(`compilerOptions.${name}`, "expected a boolean");
};
const configReferences = () => {
  const value = tsconfig?.extends;
  if (value === undefined) return null;
  if (!Array.isArray(value)) return boundedString(value, "tsconfig_extends");
  if (value.length > MAX_CONFIG_REFERENCES) omit("tsconfig_extends", "reference count limit exceeded");
  return value.slice(0, MAX_CONFIG_REFERENCES)
    .map((reference) => boundedString(reference, "tsconfig_extends"))
    .filter((reference) => reference !== null);
};
const existsDirectory = (relativePath) => {
  try {
    return fs.statSync(path.join(packageRoot, relativePath)).isDirectory();
  } catch {
    return false;
  }
};

const scriptNames = () => {
  const names = Object.keys(objectSection(pkg.scripts, "scripts")).filter((name) => (
    name.split(":").some((part) => [
      "build", "check", "contract", "contracts", "dev", "format", "lint",
      "migrate", "migration", "start", "test", "typecheck", "verify",
    ].includes(part))
  )).sort();
  const result = [];
  for (const name of names) {
    if (result.length >= MAX_SCRIPT_NAMES) {
      omit("relevant_script_names", "name count limit exceeded");
      break;
    }
    if (typeof pkg.scripts[name] !== "string") {
      omit("relevant_script_names", "expected a script string");
      continue;
    }
    const bounded = boundedString(name, "relevant_script_names");
    if (bounded !== null) result.push(bounded);
  }
  return result;
};

const hasNext = Object.hasOwn(dependencies, "next");
const hasApp = existsDirectory("app") || existsDirectory("src/app");
const hasPages = existsDirectory("pages") || existsDirectory("src/pages");

const result = {
  package_root: packageRoot,
  repository_boundary: repositoryBoundary,
  package: boundedString(pkg.name, "package", (name) => /^(?:@[A-Za-z0-9._~-]+\/)?[A-Za-z0-9._~-]+$/.test(name)),
  package_manager: {
    declared: safePackageManager(pkg.packageManager),
    nearest_lockfile: nearestLockfile,
  },
  evidence_limits: [
    "dependency values are declared specifiers, not installed resolutions or proof of active use",
    "script bodies are intentionally omitted",
    "compiler options are direct values only and may be inherited or overridden",
    "module and moduleResolution strings are declarations, not compiler-validated modes",
    "directory presence does not prove the active entrypoint or router",
    "extended config references are not loaded or resolved",
    "metadata has type, length, collection and total declaration limits; omissions are listed in metadata_omissions",
  ],
  runtime: {
    node_declared: safeSpecifier(objectSection(pkg.engines, "engines").node, "engines.node"),
    typescript_declared: safeSpecifier(dependencies.typescript, "dependency typescript"),
    package_type: boundedString(pkg.type, "package_type", (value) => ["module", "commonjs"].includes(value)),
    exports_present: Object.hasOwn(pkg, "exports"),
    main_present: Object.hasOwn(pkg, "main"),
    tsconfig_present: tsconfigText.present,
    tsconfig_error: tsconfigError,
    tsconfig_extends: configReferences(),
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
  relevant_script_names: scriptNames(),
  metadata_omissions: [...omissions],
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);

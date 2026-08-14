#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const root = path.resolve(process.argv[2] || process.cwd());
const configPath = path.join(root, "components.json");
const ignored = new Set([".git", ".next", "build", "coverage", "dist", "node_modules"]);
const sourceExtensions = new Set([".js", ".jsx", ".ts", ".tsx"]);

function result(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

if (!fs.existsSync(configPath)) {
  result({ shadcn: false, packageRoot: root, reason: "components.json not found" });
  process.exit(0);
}

let config;
try {
  config = JSON.parse(fs.readFileSync(configPath, "utf8"));
} catch (error) {
  process.stderr.write(`Invalid components.json: ${error.message}\n`);
  process.exit(2);
}

const uiAlias = config?.aliases?.ui || "@/components/ui";
const aliasTail = uiAlias.startsWith("@/") ? uiAlias.slice(2) : uiAlias;
const candidates = path.isAbsolute(aliasTail)
  ? [aliasTail]
  : [path.join(root, "src", aliasTail), path.join(root, aliasTail)];
const uiDir = candidates.find((candidate) => fs.existsSync(candidate)) || candidates[0];

function walk(directory, files = []) {
  if (!fs.existsSync(directory)) return files;
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (ignored.has(entry.name)) continue;
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(absolute, files);
    else if (sourceExtensions.has(path.extname(entry.name))) files.push(absolute);
  }
  return files;
}

const componentFiles = walk(uiDir).sort();
const sourceFiles = walk(root).filter((file) => !file.startsWith(`${uiDir}${path.sep}`));
const imports = new Map();
const escapedAlias = uiAlias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const importPattern = new RegExp(`["']${escapedAlias}/([^"']+)["']`, "g");

for (const file of sourceFiles) {
  const content = fs.readFileSync(file, "utf8");
  for (const match of content.matchAll(importPattern)) {
    const name = match[1].split("/")[0];
    const locations = imports.get(name) || [];
    locations.push(path.relative(root, file));
    imports.set(name, locations);
  }
}

const components = componentFiles.map((file) => {
  const relative = path.relative(uiDir, file);
  const name = relative.replace(path.extname(relative), "").split(path.sep).join("/");
  const locations = [...new Set(imports.get(name) || [])].sort();
  return { name, file: path.relative(root, file), importedBy: locations };
});

result({
  shadcn: true,
  packageRoot: root,
  componentsJson: path.relative(root, configPath),
  config: {
    style: config.style ?? null,
    base: config.base ?? null,
    rsc: config.rsc ?? null,
    iconLibrary: config.iconLibrary ?? null,
    uiAlias,
  },
  uiDirectory: path.relative(root, uiDir),
  components,
});

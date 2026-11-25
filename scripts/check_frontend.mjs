#!/usr/bin/env node
/**
 * Frontend checks for the Arr Studio panel.
 *
 * - every module parses as an ES module
 * - relative imports resolve to real files
 * - forbidden DOM/security patterns are absent
 * - the panel element is registered
 * - the bundle stays under the size budget
 *
 * Exits 0 with SKIP when the frontend directory does not exist yet.
 */

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const frontendDir = join(root, "custom_components", "arr_studio", "frontend");
const SIZE_BUDGET = 400 * 1024;

const FORBIDDEN = [
  [/\.innerHTML\b/, "innerHTML is forbidden; use el()"],
  [/\.outerHTML\b/, "outerHTML is forbidden; use el()"],
  [/insertAdjacentHTML/, "insertAdjacentHTML is forbidden"],
  [/\beval\s*\(/, "eval is forbidden"],
  [/new\s+Function\s*\(/, "new Function is forbidden"],
  [/document\.write/, "document.write is forbidden"],
  [/\bapi_?key\b/i, "API key reference in frontend code"],
  [/X-Api-Key/i, "API key header in frontend code"],
  [/\bhttps?:\/\//, "absolute URL in frontend code"],
];

const fails = [];

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(full));
    } else {
      out.push(full);
    }
  }
  return out;
}

function stripComments(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .map((line) => (line.includes("preflight: allow") ? "" : line.replace(/(?<!:)\/\/.*$/, "")))
    .join("\n");
}

if (!existsSync(frontendDir)) {
  console.log("SKIP frontend: custom_components/arr_studio/frontend does not exist yet");
  process.exit(0);
}

const files = walk(frontendDir);
const jsFiles = files.filter((file) => file.endsWith(".js"));

if (jsFiles.length === 0) {
  console.log("SKIP frontend: no JavaScript files yet");
  process.exit(0);
}

let totalBytes = 0;

for (const file of jsFiles) {
  const relative = file.slice(root.length + 1);
  const source = readFileSync(file, "utf8");
  totalBytes += Buffer.byteLength(source);

  try {
    execFileSync(process.execPath, ["--input-type=module", "--check"], {
      input: source,
      stdio: ["pipe", "ignore", "pipe"],
    });
  } catch (error) {
    const message = String(error.stderr || error.message || "syntax error")
      .split("\n")
      .find((line) => line.includes("Error")) || "syntax error";
    fails.push(`${relative}: ${message.trim()}`);
  }

  const stripped = stripComments(source);
  for (const [pattern, message] of FORBIDDEN) {
    if (pattern.test(stripped)) {
      fails.push(`${relative}: ${message}`);
    }
  }

  const importRe = /\bfrom\s+["'](\.[^"']+)["']/g;
  const dynamicRe = /\bimport\s*\(\s*["'](\.[^"']+)["']\s*\)/g;
  for (const re of [importRe, dynamicRe]) {
    let match;
    while ((match = re.exec(source)) !== null) {
      // Import specifiers may carry a ?v=<version> cache-buster; resolve
      // the bare path.
      const target = resolve(dirname(file), match[1].split("?")[0]);
      if (!existsSync(target)) {
        fails.push(`${relative}: import target missing -> ${match[1]}`);
      }
    }
  }
}

function readJsonSafe(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

// Sub-module imports must carry the integration version as a cache-buster:
// HA serves the static path with a 31-day Cache-Control, so an unversioned
// import keeps running stale code after an update (v0.1.2 -> v0.1.3 bug).
const versionRe = /\?v=(\d+\.\d+\.\d+)/g;
const importVersions = new Set();
for (const file of jsFiles) {
  const source = readFileSync(file, "utf8");
  let match;
  while ((match = versionRe.exec(source)) !== null) {
    importVersions.add(match[1]);
  }
}
if (importVersions.size === 0) {
  fails.push("sub-module imports are not versioned (?v= cache-buster missing)");
} else {
  const manifest = readJsonSafe(
    join(root, "custom_components", "arr_studio", "manifest.json"),
  );
  if (manifest && manifest.version) {
    for (const version of importVersions) {
      if (version !== manifest.version) {
        fails.push(
          `versioned import ?v=${version} != manifest version ${manifest.version}`,
        );
      }
    }
  }
}

const panelPath = join(frontendDir, "panel.js");
if (!existsSync(panelPath)) {
  fails.push("panel.js is missing");
} else if (!readFileSync(panelPath, "utf8").includes('customElements.define("arr-studio-panel"')) {
  fails.push('panel.js must call customElements.define("arr-studio-panel", ...)');
}

try {
  const placeholder = join(frontendDir, "placeholder.svg");
  if (existsSync(placeholder) && statSync(placeholder).size === 0) {
    fails.push("placeholder.svg is empty");
  }
} catch {
  // ignore stat errors; preflight handles existence
}

if (totalBytes > SIZE_BUDGET) {
  fails.push(`frontend bundle is ${(totalBytes / 1024).toFixed(1)} KB, budget is 400 KB`);
}

if (fails.length) {
  for (const failure of fails) {
    console.log(`FAIL ${failure}`);
  }
  console.log(`\nfrontend: ${fails.length} failure(s)`);
  process.exit(1);
}

console.log(
  `PASS frontend: ${jsFiles.length} module(s), ${(totalBytes / 1024).toFixed(1)} KB, syntax and patterns OK`,
);
process.exit(0);
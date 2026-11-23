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
      const target = resolve(dirname(file), match[1]);
      if (!existsSync(target)) {
        fails.push(`${relative}: import target missing -> ${match[1]}`);
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
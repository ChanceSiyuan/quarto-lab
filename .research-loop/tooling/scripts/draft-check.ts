#!/usr/bin/env -S node --import tsx

import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

import { checkDraft } from "../../../src/lib/drafts/check.js";

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..", "..");

let values: { file?: string; json?: boolean };
try {
  ({ values } = parseArgs({
    args: process.argv.slice(2),
    options: { file: { type: "string" }, json: { type: "boolean", default: false } },
    strict: true,
    allowPositionals: false,
  }));
  if (!values.file) throw new Error("draft-check requires --file drafts/<note>.qmd");
}
catch (error) {
  console.error(`draft-check: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(2);
}

try {
  const result = await checkDraft({ repoRoot: REPO_ROOT, requestedFile: values.file! });
  if (values.json) console.log(JSON.stringify(result));
  else if (result.ok) console.log(`${result.relativePath}: Draft checks passed`);
  else {
    console.error(`${result.relativePath}: ${result.diagnostics.length} Draft issue(s)`);
    for (const diagnostic of result.diagnostics) {
      console.error(`${result.relativePath}:${diagnostic.line} ${diagnostic.code} ${diagnostic.message}`);
    }
  }
  if (!result.ok) process.exitCode = 1;
}
catch (error) {
  console.error(`draft-check: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}

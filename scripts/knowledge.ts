#!/usr/bin/env -S node --import tsx
/**
 * CLI for the trusted knowledge tree.
 *
 *   knowledge.ts check
 *   knowledge.ts resolve --query <text>
 *
 * `check` validates `knowledge/` against `literature/ref.bib` and exits 1 with
 * every diagnostic when anything is wrong. `resolve` prints one JSON document —
 * the reading bundle an agent must read, or the alternatives it must choose
 * between — and exits 0 for `match`, `ambiguous`, and `no-match` alike: those
 * are answers, not failures. Only an invocation the CLI cannot honour and an
 * invalid tree exit 1.
 *
 * There are deliberately no path or output overrides. The trusted tree of this
 * repository is the only thing this command may read, so an agent cannot be
 * talked into resolving against a directory someone else prepared.
 */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

import {
  KnowledgeValidationError,
  resolveKnowledge,
  validateKnowledge,
} from "../lib/knowledge/index.js";

const USAGE = [
  "usage:",
  "  knowledge.ts check",
  "  knowledge.ts resolve --query <text>",
].join("\n");

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..");

class UsageError extends Error {}

/** The `--query` of a `resolve` invocation, or a usage error explaining why not. */
function queryOf(args: readonly string[]): string {
  let values;
  try {
    ({ values } = parseArgs({
      args: [...args],
      options: { query: { type: "string" } },
      strict: true,
      allowPositionals: false,
    }));
  } catch (error) {
    throw new UsageError(error instanceof Error ? error.message : String(error));
  }
  if (values.query === undefined) {
    throw new UsageError("resolve requires --query <text>");
  }
  return values.query;
}

async function main(argv: readonly string[]): Promise<void> {
  const [command, ...rest] = argv;

  switch (command) {
    case "check": {
      if (rest.length > 0) {
        throw new UsageError("check takes no arguments");
      }
      const report = await validateKnowledge({ repoRoot: REPO_ROOT });
      if (!report.ok) {
        // The error's message is the whole report, so `check` and `resolve`
        // describe an invalid tree in exactly the same words.
        throw new KnowledgeValidationError(report);
      }
      console.log("knowledge: the trusted tree is valid");
      return;
    }
    case "resolve": {
      const result = await resolveKnowledge(queryOf(rest), { repoRoot: REPO_ROOT });
      console.log(JSON.stringify(result, null, 2));
      return;
    }
    case undefined:
      throw new UsageError("a subcommand is required");
    default:
      throw new UsageError(`unknown subcommand "${command}"`);
  }
}

try {
  await main(process.argv.slice(2));
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(
    error instanceof UsageError ? `knowledge: ${message}\n${USAGE}` : `knowledge: ${message}`,
  );
  process.exitCode = 1;
}

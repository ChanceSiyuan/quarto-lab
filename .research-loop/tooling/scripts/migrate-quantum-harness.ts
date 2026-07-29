#!/usr/bin/env -S node --import tsx
/**
 * One-off migration CLI for the `quantum.harness` knowledge corpus.
 *
 *   migrate-quantum-harness.ts import --source <absolute .knowledge path> --revision <40-char SHA>
 *   migrate-quantum-harness.ts verify
 *   migrate-quantum-harness.ts verify-source --source <absolute .knowledge path> --revision <40-char SHA>
 *
 * `import` copies cards from the pinned revision, `verify` re-checks the
 * committed cards against the manifest without the source repository, and
 * `verify-source` additionally compares bytes with the source revision.
 */

import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  BIBLIOGRAPHY_PATH,
  importHarnessKnowledge,
  verifyHarnessImport,
  verifyHarnessImportAgainstSource,
} from "../../../src/lib/migration/harness.js";

const USAGE = [
  "usage:",
  "  migrate-quantum-harness.ts import --source <absolute .knowledge path> --revision <40-char SHA>",
  "  migrate-quantum-harness.ts verify",
  "  migrate-quantum-harness.ts verify-source --source <absolute .knowledge path> --revision <40-char SHA>",
].join("\n");

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..", "..");

class UsageError extends Error {}

interface SourceArguments {
  source: string;
  revision: string;
}

function parseSourceArguments(argv: readonly string[]): SourceArguments {
  const values = new Map<string, string>();

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const separator = argument.indexOf("=");
    const flag = separator === -1 ? argument : argument.slice(0, separator);

    if (flag !== "--source" && flag !== "--revision") {
      throw new UsageError(`unknown argument "${argument}"`);
    }
    if (values.has(flag)) {
      throw new UsageError(`${flag} was given more than once`);
    }

    let value: string | undefined;
    if (separator === -1) {
      value = argv[index + 1];
      index += 1;
    } else {
      value = argument.slice(separator + 1);
    }
    if (value === undefined || value === "" || value.startsWith("--")) {
      throw new UsageError(`${flag} requires a value`);
    }
    values.set(flag, value);
  }

  const source = values.get("--source");
  if (source === undefined) {
    throw new UsageError("--source is required");
  }
  if (!path.isAbsolute(source)) {
    throw new UsageError(
      `--source must be an absolute path, received "${source}"`,
    );
  }

  const revision = values.get("--revision");
  if (revision === undefined) {
    throw new UsageError("--revision is required");
  }
  if (!/^[0-9a-f]{40}$/.test(revision)) {
    throw new UsageError(
      `--revision must be a 40-character lowercase hex commit SHA, received "${revision}"`,
    );
  }

  return { source, revision };
}

function requireNoArguments(command: string, argv: readonly string[]): void {
  if (argv.length > 0) {
    throw new UsageError(`${command} takes no arguments`);
  }
}

async function main(argv: readonly string[]): Promise<void> {
  const [command, ...rest] = argv;

  switch (command) {
    case "import": {
      const { source, revision } = parseSourceArguments(rest);
      const manifest = await importHarnessKnowledge({
        sourceKnowledgeRoot: source,
        repoRoot: REPO_ROOT,
        sourceRevision: revision,
      });
      const bytes = manifest.files.reduce((total, e) => total + e.bytes, 0);
      console.log(`Imported ${manifest.files.length} cards (${bytes} bytes)`);
      return;
    }
    case "verify": {
      requireNoArguments(command, rest);
      const { files, bytes } = await verifyHarnessImport(REPO_ROOT);
      console.log(`Verified ${files} cards (${bytes} bytes)`);
      return;
    }
    case "verify-source": {
      const { source, revision } = parseSourceArguments(rest);
      const { files, bytes } = await verifyHarnessImportAgainstSource({
        sourceKnowledgeRoot: source,
        repoRoot: REPO_ROOT,
        sourceRevision: revision,
      });
      console.log(
        `Verified source parity for ${files} cards (${bytes} bytes) and ${BIBLIOGRAPHY_PATH}`,
      );
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
    error instanceof UsageError
      ? `migrate-quantum-harness: ${message}\n${USAGE}`
      : `migrate-quantum-harness: ${message}`,
  );
  process.exitCode = 1;
}

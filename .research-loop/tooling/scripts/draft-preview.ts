#!/usr/bin/env -S node --import tsx
/**
 * CLI for previewing one untrusted draft note.
 *
 *   draft-preview.ts --file drafts/reading-notes/example.qmd
 *
 * `--file` is a repository-relative path, and it is the whole interface: there
 * is no way to preview a directory, the drafts tree as a project, or a file
 * outside `drafts/`, because the tree is untrusted and a renderer pointed at
 * all of it would read all of it. The note is rendered with execution disabled
 * into the gitignored `drafts/.preview/`; nothing here can touch
 * `public/knowledge`, which only `knowledge.ts build` may replace.
 *
 * Exit codes are split so a script can tell the two failures apart: 2 means the
 * command line was wrong, 1 means the file may not be previewed or Quarto
 * failed.
 */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

import { previewDraft } from "../../../src/lib/drafts/preview.js";

const USAGE = [
  "usage:",
  "  draft-preview.ts --file <path to a .md or .qmd file inside drafts/> [--port <loopback-port>]",
].join("\n");

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..", "..");

/** What the command line asked to preview, or why it could not be read. */
function invocationOf(argv: readonly string[]): { requestedFile: string; previewPort?: number } {
  let values;
  try {
    ({ values } = parseArgs({
      args: [...argv],
      options: { file: { type: "string" }, port: { type: "string" } },
      strict: true,
      allowPositionals: false,
    }));
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : String(error));
  }
  if (values.file === undefined) {
    throw new Error(
      "draft-preview requires --file <path>, a repository-relative `.md` or `.qmd` file inside drafts/, for example `--file drafts/reading-notes/example.qmd`",
    );
  }
  if (values.port === undefined) return { requestedFile: values.file };
  const previewPort = Number(values.port);
  if (!Number.isInteger(previewPort) || previewPort < 1024 || previewPort > 65535) {
    throw new Error("draft-preview --port must be an integer between 1024 and 65535");
  }
  return { requestedFile: values.file, previewPort };
}

let invocation: { requestedFile: string; previewPort?: number };
try {
  invocation = invocationOf(process.argv.slice(2));
} catch (error) {
  console.error(
    `draft-preview: ${error instanceof Error ? error.message : String(error)}\n${USAGE}`,
  );
  // 2: the invocation was wrong, which is not the same failure as a file that
  // may not be previewed.
  process.exit(2);
}

try {
  // Returns when Quarto exits; the preview serves until it is stopped.
  await previewDraft({ repoRoot: REPO_ROOT, ...invocation });
} catch (error) {
  console.error(`draft-preview: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}

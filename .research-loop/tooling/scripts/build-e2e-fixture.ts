#!/usr/bin/env -S node --import tsx
/**
 * Builds the knowledge site the browser tests run against.
 *
 * The browser tests need a site with real pages in it — mathematics, a
 * citation, an image, a nested topic — and the committed `knowledge/` tree is
 * deliberately almost empty, because it holds only what a user has actually
 * promoted. So the fixture tree under `.research-loop/tests/fixtures/knowledge/valid` is
 * rendered instead, and the app is rebuilt around it.
 *
 * This is a *separate script* rather than a flag on `knowledge.ts`. That
 * CLI has no path or output overrides on purpose: it is the command agents and
 * Make targets run, and a `--knowledge-dir` on it would be a way to talk the
 * trusted build into rendering a directory someone else prepared. The library
 * takes the options; only this file, which nothing but the test setup runs,
 * passes them.
 *
 * The fixture is never copied into `knowledge/` and never committed: it lands
 * in the same gitignored `public/knowledge` the real build uses, and Task 15's
 * last step rebuilds the production tree over it. Anything that publishes must
 * run `npm run build` afterwards — `npm test` does.
 */

import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { buildKnowledgeSite } from "../../../src/lib/knowledge/index.js";

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..", "..");

/** The knowledge tree the browser tests describe. */
const FIXTURE_KNOWLEDGE_DIR = ".research-loop/tests/fixtures/knowledge/valid";

/** The bibliography those pages cite; it holds the `fixture2026` entry. */
const FIXTURE_BIBLIOGRAPHY = ".research-loop/tests/fixtures/knowledge/ref.bib";

/** Runs a command to completion, with no shell between it and the kernel. */
function run(command: string, args: readonly string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [...args], {
      cwd: REPO_ROOT,
      stdio: "inherit",
      shell: false,
    });
    child.on("error", reject);
    child.on("close", (code, signal) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(
        new Error(
          `\`${command} ${args.join(" ")}\` ${
            signal === null ? `exited with code ${code}` : `was killed by ${signal}`
          }`,
        ),
      );
    });
  });
}

try {
  const { outputDir, renderedFiles } = await buildKnowledgeSite({
    repoRoot: REPO_ROOT,
    knowledgeDir: FIXTURE_KNOWLEDGE_DIR,
    bibliographyPath: path.join(REPO_ROOT, ...FIXTURE_BIBLIOGRAPHY.split("/")),
  });
  console.log(
    `build-e2e-fixture: published ${renderedFiles} file${
      renderedFiles === 1 ? "" : "s"
    } from ${FIXTURE_KNOWLEDGE_DIR} to ${path.relative(REPO_ROOT, outputDir)}`,
  );
  await run("npm", ["run", "build:app"]);
} catch (error) {
  console.error(
    `build-e2e-fixture: ${error instanceof Error ? error.message : String(error)}`,
  );
  process.exitCode = 1;
}

/**
 * Renders the trusted knowledge tree into the published static site.
 *
 * This is the only module in the repository that spawns a program and the only
 * one that replaces a published directory, so it is written around the two ways
 * that can go wrong.
 *
 * **Nothing unvalidated is rendered.** The graph is loaded, validated
 * completely, and refused with the whole report if anything is wrong — the
 * renderer is never started for a tree with one bad page. The project Quarto is
 * pointed at is a temporary projection holding only validated files, the
 * subprocess is spawned from an argument array with `shell: false` so no page
 * title can become a command, and `--no-execute` is passed on every invocation
 * even though the generated configuration already disables execution. Two
 * independent locks on the same door.
 *
 * **The published site is never half-replaced.** Rendering happens in a
 * workspace under `work/` — inside the repository, therefore on the same
 * filesystem as `public/`, therefore renameable rather than copyable. Only
 * after the output has been verified (an `index.html` exists, and no file
 * carries a path component that would mean a source page or a private
 * directory escaped) is the old site moved aside and the new one moved in. If
 * either move fails the old site goes back, and the workspace is removed in a
 * `finally` whatever happened.
 *
 * `ProcessRunner` and `AtomicDirectoryOps` exist so those failure paths can be
 * tested: a real Quarto cannot be asked to fail on cue, and a real rename
 * cannot be asked to fail after the old site has been moved aside.
 */

import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { rmSync } from "node:fs";
import { mkdir, mkdtemp, readdir, rename, rm, stat } from "node:fs/promises";
import path from "node:path";

import { loadKnowledge, type LoadKnowledgeOptions } from "./graph.js";
import { materializeQuartoProject } from "./quarto.js";
import {
  KnowledgeValidationError,
  bibliographyPathFor,
  validateGraph,
} from "./validate.js";

/** Where the published site lives, relative to the repository root. */
export const SITE_OUTPUT_PATH = "public/knowledge";

/** Where build workspaces live: inside the repository, and gitignored. */
const WORKSPACE_PARENT = "work";
const WORKSPACE_PREFIX = "knowledge-build-";

/** The Quarto executable, when the caller names none. */
const DEFAULT_QUARTO_BIN = "quarto";

/** The page every rendered knowledge site must have. */
const REQUIRED_OUTPUT = "index.html";

/**
 * Path components that may never appear in the published site.
 *
 * `.qmd` would mean a source page was published instead of rendered; the rest
 * name the trees the knowledge site exists to keep out — the bibliography, the
 * untrusted drafts, the external literature, and the local-only raw downloads
 * and extracted figures. The audit runs on the rendered output rather than on
 * the projection, because it is the last chance to notice that a Quarto version
 * started copying something new.
 */
const FORBIDDEN_OUTPUT_COMPONENTS: readonly string[] = [
  "ref.bib",
  "drafts",
  "literature",
  ".raw",
  ".figures",
];

/**
 * How a subprocess is run. The options are fixed rather than optional: a
 * caller cannot ask for a shell, and the implementation cannot forget to
 * refuse one.
 */
export interface ProcessRunner {
  run(
    command: string,
    args: readonly string[],
    options: { cwd: string; stdio: "inherit" | "pipe"; shell: false },
  ): Promise<void>;
}

/** The two directory operations that publish a site, injectable for tests. */
export interface AtomicDirectoryOps {
  rename(from: string, to: string): Promise<void>;
  rm(path: string, options: { recursive: true; force: true }): Promise<void>;
}

export interface BuildKnowledgeSiteOptions extends LoadKnowledgeOptions {
  /** Defaults to `<repoRoot>/literature/ref.bib`. */
  bibliographyPath?: string;
  quartoBin?: string;
  runner?: ProcessRunner;
  directoryOps?: AtomicDirectoryOps;
}

export interface BuildKnowledgeSiteResult {
  outputDir: string;
  /** How many files the published site holds, as counted by the audit. */
  renderedFiles: number;
}

/** Thrown when a rendered site may not be published. */
export class KnowledgeSiteError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "KnowledgeSiteError";
  }
}

/** Spawns a program with no shell between the argument array and the kernel. */
const defaultRunner: ProcessRunner = {
  run(command, args, options) {
    return new Promise((resolve, reject) => {
      const child = spawn(command, [...args], {
        cwd: options.cwd,
        stdio: options.stdio,
        shell: options.shell,
      });
      child.on("error", (error: Error) => {
        reject(
          new KnowledgeSiteError(
            `could not run \`${command}\`: ${error.message}; the knowledge site is rendered by Quarto, which must be on PATH`,
          ),
        );
      });
      child.on("close", (code: number | null, signal: NodeJS.Signals | null) => {
        if (code === 0) {
          resolve();
          return;
        }
        reject(
          new KnowledgeSiteError(
            `\`${command} ${args.join(" ")}\` ${
              signal === null ? `exited with code ${code}` : `was killed by ${signal}`
            }`,
          ),
        );
      });
    });
  },
};

const defaultDirectoryOps: AtomicDirectoryOps = {
  rename: (from, to) => rename(from, to),
  rm: (target, options) => rm(target, options),
};

async function pathExists(target: string): Promise<boolean> {
  try {
    await stat(target);
    return true;
  } catch {
    return false;
  }
}

/**
 * Every file under a directory, as POSIX paths relative to it.
 *
 * Symbolic links are counted as files rather than followed: a link the renderer
 * produced is audited by its own name, and following one could walk out of the
 * output tree entirely.
 */
async function outputFiles(root: string): Promise<string[]> {
  const files: string[] = [];
  const walk = async (directory: string, prefix: string): Promise<void> => {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const relative = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
      if (entry.isDirectory()) {
        await walk(path.join(directory, entry.name), relative);
      } else {
        files.push(relative);
      }
    }
  };
  await walk(root, "");
  return files.sort();
}

/**
 * Checks that a rendered site may be published, and counts it.
 *
 * The required `index.html` is checked first because its absence usually means
 * the render did nothing at all; the name audit then runs over every file,
 * reporting all offenders rather than the first, so one run tells the whole
 * story.
 */
async function auditRenderedSite(outputDir: string): Promise<number> {
  if (!(await pathExists(outputDir))) {
    throw new KnowledgeSiteError(
      `the render produced no output directory at "${outputDir}"; nothing was published`,
    );
  }
  const files = await outputFiles(outputDir);
  if (!files.includes(REQUIRED_OUTPUT)) {
    throw new KnowledgeSiteError(
      `the render produced no \`${REQUIRED_OUTPUT}\` in "${outputDir}"; the published site would have no entry point, so nothing was published`,
    );
  }

  const offenders = files.filter((file) =>
    file
      .split("/")
      .some(
        (segment) =>
          segment.endsWith(".qmd") || FORBIDDEN_OUTPUT_COMPONENTS.includes(segment),
      ),
  );
  if (offenders.length > 0) {
    throw new KnowledgeSiteError(
      [
        `the render produced ${offenders.length} file${offenders.length === 1 ? "" : "s"} that a published knowledge site may not contain:`,
        ...offenders.map((file) => `  ${file}`),
        `no source page, bibliography, draft, literature entry, or local-only download may reach "${outputDir}", so nothing was published`,
      ].join("\n"),
    );
  }
  return files.length;
}

/**
 * The signals a terminal ends a render or a preview with.
 *
 * `quarto preview` runs until the user stops it, and the usual way to stop it
 * is Ctrl-C — which reaches this process as well as Quarto. Node's default
 * disposition for these signals is to die at once, so the `finally` that
 * removes the workspace would never run and every interrupted preview would
 * leave one behind.
 */
const CLEANUP_SIGNALS: readonly NodeJS.Signals[] = ["SIGINT", "SIGTERM", "SIGHUP"];

/**
 * Removes a workspace if the process is signalled, and returns the function
 * that unregisters that promise again.
 *
 * The removal is synchronous, because a signal handler has no time to await,
 * and the signal is then re-raised with the default disposition so that the
 * process still dies of what it was sent rather than surviving a Ctrl-C.
 */
function removeWorkspaceOnSignal(workspace: string): () => void {
  const onSignal = (signal: NodeJS.Signals): void => {
    detach();
    try {
      rmSync(workspace, { recursive: true, force: true });
    } catch {
      // A workspace that cannot be removed must not stop the process from
      // dying of the signal it was sent.
    }
    process.kill(process.pid, signal);
  };
  const detach = (): void => {
    for (const signal of CLEANUP_SIGNALS) {
      process.removeListener(signal, onSignal);
    }
  };
  for (const signal of CLEANUP_SIGNALS) {
    process.on(signal, onSignal);
  }
  return detach;
}

/** A validated graph and the workspace one render of it runs in. */
interface PreparedRender {
  workspace: string;
  projectDir: string;
  outputDir: string;
  repoRoot: string;
}

/**
 * Steps 1 to 4: load, validate, take a workspace, and project.
 *
 * The workspace is created under the repository's `work/` directory rather than
 * in the system temporary directory, because the site is published by renaming
 * the rendered output into `public/knowledge` and a rename cannot cross a
 * filesystem boundary.
 */
async function prepareRender(options: BuildKnowledgeSiteOptions): Promise<PreparedRender> {
  const graph = await loadKnowledge(options);
  const bibliographyPath = bibliographyPathFor(graph.repoRoot, options.bibliographyPath);
  const report = await validateGraph(graph, { bibliographyPath });
  if (!report.ok) {
    throw new KnowledgeValidationError(report);
  }

  const parent = path.join(graph.repoRoot, WORKSPACE_PARENT);
  await mkdir(parent, { recursive: true });
  const workspace = await mkdtemp(path.join(parent, WORKSPACE_PREFIX));

  try {
    const project = await materializeQuartoProject({ graph, workspace, bibliographyPath });
    return {
      workspace,
      projectDir: project.projectDir,
      outputDir: project.outputDir,
      repoRoot: graph.repoRoot,
    };
  } catch (error) {
    await rm(workspace, { recursive: true, force: true });
    throw error;
  }
}

/**
 * Renders the trusted knowledge tree and replaces the published site with it.
 *
 * The order is the contract: validate, project, render, verify, and only then
 * touch `public/knowledge`. Every failure before the last two renames leaves
 * the previously published site exactly as it was.
 */
export async function buildKnowledgeSite(
  options: BuildKnowledgeSiteOptions = {},
): Promise<BuildKnowledgeSiteResult> {
  const runner = options.runner ?? defaultRunner;
  const directoryOps = options.directoryOps ?? defaultDirectoryOps;

  const prepared = await prepareRender(options);
  const outputDir = path.join(prepared.repoRoot, ...SITE_OUTPUT_PATH.split("/"));
  const detach = removeWorkspaceOnSignal(prepared.workspace);

  try {
    // 5. Render. `--no-execute` is passed even though the generated
    // configuration disables execution: the flag is the lock that does not
    // depend on the file the projection wrote.
    await runner.run(options.quartoBin ?? DEFAULT_QUARTO_BIN, ["render", ".", "--no-execute"], {
      cwd: prepared.projectDir,
      stdio: "inherit",
      shell: false,
    });

    // 6. Verify before replacing anything.
    const renderedFiles = await auditRenderedSite(prepared.outputDir);

    // 7-9. Publish: move the old site aside, move the new one in, and put the
    // old one back if either move fails. The backup is a sibling so that both
    // renames stay within one directory, and therefore within one filesystem.
    await mkdir(path.dirname(outputDir), { recursive: true });
    const backup = path.join(
      path.dirname(outputDir),
      `.${path.basename(outputDir)}-backup-${randomUUID()}`,
    );
    const hadOldSite = await pathExists(outputDir);
    if (hadOldSite) {
      await directoryOps.rename(outputDir, backup);
    }
    try {
      await directoryOps.rename(prepared.outputDir, outputDir);
    } catch (error) {
      if (hadOldSite) {
        await directoryOps.rename(backup, outputDir);
      }
      throw error;
    }

    // 10. The old site is unreachable now; removing it is the only step whose
    // failure would be cosmetic.
    if (hadOldSite) {
      await directoryOps.rm(backup, { recursive: true, force: true });
    }

    return { outputDir, renderedFiles };
  } finally {
    detach();
    await rm(prepared.workspace, { recursive: true, force: true });
  }
}

/**
 * Serves the same validated projection Quarto would render.
 *
 * The workspace stays alive for as long as Quarto is running — it is the
 * directory being served — and is removed when Quarto exits. Preview never
 * touches `public/knowledge`: a served site is not a published one.
 */
export async function previewKnowledgeSite(
  options: BuildKnowledgeSiteOptions = {},
): Promise<void> {
  const runner = options.runner ?? defaultRunner;
  const prepared = await prepareRender(options);
  const detach = removeWorkspaceOnSignal(prepared.workspace);
  try {
    await runner.run(
      options.quartoBin ?? DEFAULT_QUARTO_BIN,
      ["preview", ".", "--no-browser", "--no-execute"],
      { cwd: prepared.projectDir, stdio: "inherit", shell: false },
    );
  } finally {
    detach();
    await rm(prepared.workspace, { recursive: true, force: true });
  }
}

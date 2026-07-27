/**
 * Previews one untrusted draft note.
 *
 * `drafts/` is the opposite of `knowledge/`: nothing in it has been reviewed,
 * nothing in it has been validated, and an import or an agent may have written
 * any of it. It is still the tree a human has to read before deciding what to
 * promote, so it needs a renderer — and pointing a renderer at an untrusted
 * directory is exactly the thing the knowledge site is built to avoid.
 *
 * The compromise is *one file, named by a human*:
 *
 * - **selection is the boundary.** `quarto preview <file>` renders the single
 *   document it is given, not the project around it. `drafts/_quarto.yml`
 *   carries no `website`, no sidebar, and no categories, so a preview cannot
 *   grow into a site build of the whole tree, and its `output-dir` is the
 *   gitignored `.preview/` — never `public/knowledge/`, which only
 *   `buildKnowledgeSite` may replace;
 * - **containment is checked on the real path.** A `..` walk and an absolute
 *   path are refused before the filesystem is touched, and then the resolved
 *   `realpath` is required to be inside the real drafts root as well, because a
 *   symbolic link named `note.md` is an ordinary relative path until the
 *   filesystem is asked where it goes. The path handed to Quarto is the real
 *   one, so what is rendered is what was checked;
 * - **execution stays off.** `--no-execute` is passed on every invocation even
 *   though the project file already disables it, the same two-locks rule the
 *   site build follows: a draft may contain any code cell at all, and none of
 *   it may run;
 * - **the argument array is never a command line.** The spawn is shell-free,
 *   and a path component that could be read as an option is refused rather than
 *   passed along, so a directory an agent named `--output-dir=` cannot become a
 *   flag.
 *
 * The residual risk is deliberate and small: between the check and the spawn,
 * the file could be replaced by a link pointing elsewhere, and Quarto would
 * follow it. Closing that would mean copying the note into a workspace, which
 * would break the one thing a preview is for — watching a file as you edit it.
 */

import { spawn } from "node:child_process";
import { realpath, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { ProcessRunner } from "../knowledge/site.js";

/** The untrusted tree a preview may read, relative to the repository root. */
export const DRAFTS_DIRECTORY = "drafts";

/** What a draft note may be. Anything else is data, not a document. */
const PREVIEWABLE_EXTENSIONS: readonly string[] = [".md", ".qmd"];

/** The Quarto executable, when the caller names none. */
const DEFAULT_QUARTO_BIN = "quarto";

/** Defaults to the repository this file is installed in. */
const DEFAULT_REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..");

/** Thrown when a file may not be previewed, or when Quarto could not run. */
export class DraftPreviewError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DraftPreviewError";
  }
}

/** One draft note, located: where the project is, and what to render in it. */
export interface ResolvedDraftFile {
  /** The real drafts root; the working directory Quarto is given. */
  draftsRoot: string;
  /** The real path of the note. */
  absoluteFile: string;
  /** The note as a POSIX path relative to `draftsRoot`; Quarto's argument. */
  relativeFile: string;
}

export interface PreviewDraftOptions {
  /** Defaults to the repository this file is installed in. */
  repoRoot?: string;
  /** The note to preview, as a repository-relative or absolute path. */
  requestedFile: string;
  quartoBin?: string;
  runner?: ProcessRunner;
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
          new DraftPreviewError(
            `could not run \`${command}\`: ${error.message}; a draft note is previewed by Quarto, which must be on PATH`,
          ),
        );
      });
      child.on("close", (code: number | null, signal: NodeJS.Signals | null) => {
        if (code === 0) {
          resolve();
          return;
        }
        reject(
          new DraftPreviewError(
            `\`${command} ${args.join(" ")}\` ${
              signal === null ? `exited with code ${code}` : `was killed by ${signal}`
            }`,
          ),
        );
      });
    });
  },
};

function toPosix(value: string): string {
  return value.split(path.sep).join("/");
}

/**
 * Whether `target` is `base` or something under it.
 *
 * The drafts root itself is accepted here and refused one step later as the
 * directory it is, so that "you named a directory" is what the user is told
 * rather than "you left the tree".
 */
function contains(base: string, target: string): boolean {
  const relative = path.relative(base, target);
  return (
    !path.isAbsolute(relative) && relative !== ".." && !relative.startsWith(`..${path.sep}`)
  );
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * Resolves a requested path to the one note a preview may render.
 *
 * Every refusal names the path exactly as it was asked for, because the caller
 * typed it and has to recognise it in the message.
 */
export async function resolveDraftFile(input: {
  repoRoot: string;
  requestedFile: string;
}): Promise<ResolvedDraftFile> {
  const { requestedFile } = input;
  const repoRoot = path.resolve(input.repoRoot);
  const draftsDir = path.join(repoRoot, DRAFTS_DIRECTORY);

  // 1. Lexically, before the filesystem is touched at all: an absolute path
  // elsewhere and a `..` walk are refused without a stat that would tell the
  // caller whether the file they named exists.
  const candidate = path.resolve(repoRoot, requestedFile);
  if (!contains(draftsDir, candidate)) {
    throw new DraftPreviewError(
      `"${requestedFile}" is outside \`${DRAFTS_DIRECTORY}/\`; a draft preview renders only a file inside "${draftsDir}"`,
    );
  }

  let draftsRoot: string;
  try {
    draftsRoot = await realpath(draftsDir);
  } catch (error) {
    throw new DraftPreviewError(
      `this repository has no readable \`${DRAFTS_DIRECTORY}/\` tree at "${draftsDir}": ${describe(error)}`,
    );
  }

  let absoluteFile: string;
  try {
    absoluteFile = await realpath(candidate);
  } catch (error) {
    throw new DraftPreviewError(
      `there is no file at "${requestedFile}" (looked for "${candidate}"): ${describe(error)}`,
    );
  }

  // 2. Again on the real path: a symbolic link, or a link in a parent
  // directory, is an ordinary relative path until it is resolved.
  if (!contains(draftsRoot, absoluteFile)) {
    throw new DraftPreviewError(
      `"${requestedFile}" resolves to "${absoluteFile}", which is outside \`${DRAFTS_DIRECTORY}/\`; a symbolic link may not lead a preview out of the drafts tree`,
    );
  }

  const found = await stat(absoluteFile);
  if (!found.isFile()) {
    throw new DraftPreviewError(
      found.isDirectory()
        ? `"${requestedFile}" is a directory, not a draft note; name the \`.md\` or \`.qmd\` file inside it that you want to preview`
        : `"${requestedFile}" is not a regular file, so there is nothing to preview`,
    );
  }

  // 3. The extension of the *real* file, which is the one Quarto is handed.
  const extension = path.extname(absoluteFile).toLowerCase();
  if (!PREVIEWABLE_EXTENSIONS.includes(extension)) {
    throw new DraftPreviewError(
      `"${requestedFile}" is not a draft note; a preview renders only ${PREVIEWABLE_EXTENSIONS.map(
        (allowed) => `\`${allowed}\``,
      ).join(" and ")} files, and this one ends in "${extension}"`,
    );
  }

  // 4. The argument Quarto will receive must be a path and nothing else. A
  // component beginning with `-` would be parsed as an option — a directory
  // named `--output-dir=` inside an untrusted tree is a redirect of the render.
  const relativeFile = toPosix(path.relative(draftsRoot, absoluteFile));
  const optionLike = relativeFile.split("/").find((segment) => segment.startsWith("-"));
  if (optionLike !== undefined) {
    throw new DraftPreviewError(
      `"${requestedFile}" contains the path component "${optionLike}", which Quarto would read as a command-line option rather than as part of a file name; rename it to preview this note`,
    );
  }

  return { draftsRoot, absoluteFile, relativeFile };
}

/**
 * Serves one draft note, and only that note.
 *
 * Quarto is run in the real drafts root so that `drafts/_quarto.yml` is the
 * project it sees — `output-dir: .preview`, no website, execution disabled —
 * and returns when Quarto exits. Nothing outside `drafts/.preview/` is written.
 */
export async function previewDraft(input: PreviewDraftOptions): Promise<void> {
  const { draftsRoot, relativeFile } = await resolveDraftFile({
    repoRoot: input.repoRoot ?? DEFAULT_REPO_ROOT,
    requestedFile: input.requestedFile,
  });

  await (input.runner ?? defaultRunner).run(
    input.quartoBin ?? DEFAULT_QUARTO_BIN,
    ["preview", relativeFile, "--no-browser", "--no-execute"],
    { cwd: draftsRoot, stdio: "inherit", shell: false },
  );
}

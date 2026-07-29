/**
 * Copies the figures out of an extracted arXiv source tree.
 *
 * The rule this module exists to enforce is that a figure is *moved, never
 * touched*. No conversion, no re-encoding, no thumbnailing, no rasterizing of
 * an EPS, and above all no TeX or PostScript interpreter — an arXiv source
 * archive is third-party input, and the moment a converter is pointed at it the
 * repository has taken on the attack surface of that converter. `copyFile` and
 * a digest comparison are the whole implementation, and that is the point.
 *
 * The relative path of a figure is preserved because it is the only stable name
 * it has: `\includegraphics{figures/plot}` resolves against the source tree, so
 * a figure tree that flattened `figures/plot.png` and `appendix/plot.png` into
 * one directory would silently lose one of them.
 *
 * The file list comes from the caller rather than from a directory walk. The
 * unpacker has already validated every one of those paths; re-walking the tree
 * would mean validating them a second time, in a second place, with a second
 * chance of getting it wrong.
 */

import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile } from "node:fs/promises";
import path from "node:path";

/**
 * The image formats a paper's figures actually arrive in.
 *
 * Everything else in a source tree — `.bbl`, `.csv`, `.dat`, a stray `.zip` —
 * stays where it is. The figure tree is for looking at, not for archiving.
 */
export const FIGURE_EXTENSIONS: readonly string[] = [
  ".eps",
  ".jpeg",
  ".jpg",
  ".pdf",
  ".png",
  ".svg",
  ".tif",
  ".tiff",
];

const FIGURE_EXTENSION_SET = new Set(FIGURE_EXTENSIONS);

/** One copied figure: both paths are relative to their own root. */
export interface CopiedFigure {
  source: string;
  destination: string;
  sha256: string;
}

/** A file in the extracted tree, as the unpacker recorded it. */
export interface ExtractedFile {
  path: string;
  bytes: number;
  sha256: string;
}

/** Thrown when a copy did not reproduce the source bytes exactly. */
export class FigureCopyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FigureCopyError";
  }
}

/** Whether a relative POSIX path names a figure, ignoring extension case. */
export function isFigurePath(relativePath: string): boolean {
  return FIGURE_EXTENSION_SET.has(path.posix.extname(relativePath).toLowerCase());
}

function sha256(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

/**
 * Copies every figure in `files` from `sourceRoot` into `figuresRoot`.
 *
 * Each copy is read back and re-digested before it is reported. `copyFile` is
 * reliable, but "byte for byte" is a claim the manifest makes to a reader who
 * will never see the original archive again, and a claim that cheap to check is
 * a claim worth checking.
 *
 * Returns the copies sorted by path, so the manifest of one archive is the same
 * on every machine.
 */
export async function copyFigures(options: {
  sourceRoot: string;
  figuresRoot: string;
  files: readonly ExtractedFile[];
}): Promise<readonly CopiedFigure[]> {
  const sourceRoot = path.resolve(options.sourceRoot);
  const figuresRoot = path.resolve(options.figuresRoot);

  const figures = options.files
    .filter((file) => isFigurePath(file.path))
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));

  const copied: CopiedFigure[] = [];
  for (const figure of figures) {
    const from = path.join(sourceRoot, figure.path);
    const to = path.join(figuresRoot, figure.path);
    await mkdir(path.dirname(to), { recursive: true, mode: 0o755 });
    await copyFile(from, to);

    const written = await readFile(to);
    const digest = sha256(written);
    if (written.length !== figure.bytes || digest !== figure.sha256) {
      throw new FigureCopyError(
        `copying the figure "${figure.path}" did not reproduce it: expected ${figure.bytes} bytes with digest ${figure.sha256}, wrote ${written.length} bytes with digest ${digest}`,
      );
    }
    copied.push({ source: figure.path, destination: figure.path, sha256: digest });
  }
  return copied;
}

/**
 * Imports the `quantum.harness` `.knowledge` corpus into this repository as
 * untrusted draft cards.
 *
 * The migration is deliberately narrow and auditable:
 *
 * - bytes are always read from a pinned Git revision of the source repository,
 *   never from its working tree, index, or untracked files;
 * - note content is copied verbatim (no normalization of line endings, front
 *   matter, links, or trailing whitespace);
 * - every write is staged under `<repoRoot>/work/` and then moved into place, so
 *   a failed run leaves no partial destination behind;
 * - the manifest records only content-derived facts (paths, byte counts,
 *   SHA-256 digests) so it stays reproducible and host independent.
 */

import { execFile, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  lstat,
  mkdir,
  readFile,
  readdir,
  realpath,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const run = promisify(execFile);

/** Repository-relative destination of the imported cards, POSIX separators. */
export const DESTINATION_PATH = "drafts/imported-quantum-harness";

/** Repository-relative destination of the imported bibliography. */
export const BIBLIOGRAPHY_PATH = "literature/ref.bib";

/** Repository-relative location of the migration manifest. */
export const MANIFEST_PATH = "docs/migrations/quantum-harness-knowledge.json";

/** Subtree of the source repository that holds the knowledge corpus. */
const SOURCE_SUBTREE = ".knowledge";

/** Source path of the only file imported from the literature subtree. */
const SOURCE_BIBLIOGRAPHY = `${SOURCE_SUBTREE}/literature/ref.bib`;

/** Source prefix whose Markdown is rendered literature, not a knowledge card. */
const SOURCE_LITERATURE_PREFIX = `${SOURCE_SUBTREE}/literature/`;

/** Staging area for a run; ignored by Git via the repository's `/work/` rule. */
const STAGING_PATH = "work/migrate-quantum-harness";

const REVISION_PATTERN = /^[0-9a-f]{40}$/;

/** Git file modes that denote a regular (non-symlink, non-submodule) file. */
const REGULAR_FILE_MODES = new Set(["100644", "100755"]);

export interface MigrationEntry {
  /** POSIX path relative to `drafts/imported-quantum-harness`. */
  path: string;
  bytes: number;
  /** Lowercase hex SHA-256 of the raw bytes. */
  sha256: string;
}

export interface MigrationManifest {
  schemaVersion: 1;
  source: {
    repository: "quantum.harness";
    subtree: ".knowledge";
    revision: string;
  };
  destination: "drafts/imported-quantum-harness";
  files: MigrationEntry[];
  bibliography: {
    path: "literature/ref.bib";
    bytes: number;
    sha256: string;
  };
}

export interface SourceOptions {
  /** Absolute path to the `.knowledge` directory of the source repository. */
  sourceKnowledgeRoot: string;
  repoRoot: string;
  /** 40-character lowercase hex commit SHA that must be the source HEAD. */
  sourceRevision: string;
}

export interface MigrationTotals {
  files: number;
  bytes: number;
}

interface SourceEntry {
  /** Path relative to the source repository root, POSIX separators. */
  path: string;
  mode: string;
  type: string;
  object: string;
}

interface SelectedSource {
  /** Cards to import, sorted by destination path. */
  cards: { destination: string; source: SourceEntry }[];
  bibliography: SourceEntry;
}

function sha256(value: Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}

function comparePosix(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function toSystemPath(root: string, posixRelative: string): string {
  return path.join(root, ...posixRelative.split("/"));
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

async function isDirectory(target: string): Promise<boolean> {
  try {
    return (await stat(target)).isDirectory();
  } catch {
    return false;
  }
}

async function pathExists(target: string): Promise<boolean> {
  try {
    await lstat(target);
    return true;
  } catch {
    return false;
  }
}

/**
 * Signals that a failed install could not be undone, so the staging tree holds
 * the only copy of the displaced originals and must be kept.
 */
class IncompleteRollbackError extends Error {}

interface PendingInstall {
  /** Staged artifact holding the new content. */
  staged: string;
  /** Final repository path the artifact is installed at. */
  target: string;
  /** Staging path an already-present target is displaced to. */
  displaced: string;
}

/**
 * Moves staged artifacts into place as one unit.
 *
 * Each target that already exists is displaced into the staging tree before it
 * is replaced, and every completed step is undone in reverse order if a later
 * step fails, so callers either get the whole new import or the exact state
 * they started from. Displaced originals stay in the staging tree, which the
 * caller only discards once every step has succeeded.
 */
async function installAtomically(
  installs: readonly PendingInstall[],
): Promise<void> {
  const undo: (() => Promise<void>)[] = [];

  try {
    for (const install of installs) {
      await mkdir(path.dirname(install.target), { recursive: true });
      if (await pathExists(install.target)) {
        await rename(install.target, install.displaced);
        undo.push(async () => {
          await rename(install.displaced, install.target);
        });
      }
      await rename(install.staged, install.target);
      undo.push(async () => {
        await rename(install.target, install.staged);
      });
    }
  } catch (error) {
    const failures: unknown[] = [];
    for (const step of undo.reverse()) {
      try {
        await step();
      } catch (rollbackError) {
        failures.push(rollbackError);
      }
    }
    if (failures.length > 0) {
      throw new IncompleteRollbackError(
        `${describe(error)} (the import could not be fully undone: ${failures.map(describe).join("; ")})`,
        { cause: error },
      );
    }
    throw error;
  }
}

async function git(
  repositoryRoot: string,
  args: readonly string[],
): Promise<string> {
  const { stdout } = await run("git", ["-C", repositoryRoot, ...args], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  return stdout;
}

/**
 * Validates the caller's source options and resolves the Git repository that
 * contains the `.knowledge` subtree.
 */
async function resolveSource(options: SourceOptions): Promise<string> {
  const { sourceKnowledgeRoot, sourceRevision } = options;

  if (!path.isAbsolute(sourceKnowledgeRoot)) {
    throw new Error(
      `source knowledge root must be an absolute path, received "${sourceKnowledgeRoot}"`,
    );
  }
  if (!REVISION_PATTERN.test(sourceRevision)) {
    throw new Error(
      `invalid source revision "${sourceRevision}": expected a 40-character lowercase hex commit SHA`,
    );
  }
  if (!(await isDirectory(sourceKnowledgeRoot))) {
    throw new Error(
      `source knowledge root "${sourceKnowledgeRoot}" is not a directory`,
    );
  }

  const knowledgeRoot = await realpath(sourceKnowledgeRoot);
  const repositoryRoot = await realpath(
    (await git(knowledgeRoot, ["rev-parse", "--show-toplevel"])).trim(),
  );

  const subtree = path
    .relative(repositoryRoot, knowledgeRoot)
    .split(path.sep)
    .join("/");
  if (subtree !== SOURCE_SUBTREE) {
    throw new Error(
      `expected "${sourceKnowledgeRoot}" to be the "${SOURCE_SUBTREE}" subtree of "${repositoryRoot}", found "${subtree}"`,
    );
  }

  const head = (await git(repositoryRoot, ["rev-parse", "HEAD"])).trim();
  if (head !== sourceRevision) {
    throw new Error(
      `source repository HEAD "${head}" does not equal the requested revision "${sourceRevision}"`,
    );
  }

  return repositoryRoot;
}

/** Lists the committed blobs of the `.knowledge` subtree at `revision`. */
async function listSourceEntries(
  repositoryRoot: string,
  revision: string,
): Promise<SourceEntry[]> {
  const stdout = await git(repositoryRoot, [
    "ls-tree",
    "-rz",
    revision,
    "--",
    SOURCE_SUBTREE,
  ]);

  const entries: SourceEntry[] = [];
  for (const record of stdout.split("\0")) {
    if (record === "") {
      continue;
    }
    const tab = record.indexOf("\t");
    if (tab === -1) {
      throw new Error(`unexpected git ls-tree record: ${JSON.stringify(record)}`);
    }
    const [mode, type, object] = record.slice(0, tab).split(" ");
    if (!mode || !type || !object) {
      throw new Error(`unexpected git ls-tree record: ${JSON.stringify(record)}`);
    }
    entries.push({ path: record.slice(tab + 1), mode, type, object });
  }
  return entries;
}

/**
 * Chooses the Markdown cards outside the literature subtree plus the single
 * bibliography file, sorted by destination path.
 */
function selectSource(entries: readonly SourceEntry[]): SelectedSource {
  const requireRegularFile = (entry: SourceEntry): SourceEntry => {
    if (entry.type !== "blob" || !REGULAR_FILE_MODES.has(entry.mode)) {
      throw new Error(
        `expected "${entry.path}" to be a regular file, found mode ${entry.mode} (${entry.type})`,
      );
    }
    return entry;
  };

  const cards = entries
    .filter(
      (entry) =>
        entry.path.endsWith(".md") &&
        entry.path.startsWith(`${SOURCE_SUBTREE}/`) &&
        !entry.path.startsWith(SOURCE_LITERATURE_PREFIX),
    )
    .map((entry) => ({
      destination: entry.path.slice(`${SOURCE_SUBTREE}/`.length),
      source: requireRegularFile(entry),
    }))
    .sort((a, b) => comparePosix(a.destination, b.destination));

  const bibliography = entries.find(
    (entry) => entry.path === SOURCE_BIBLIOGRAPHY,
  );
  if (!bibliography) {
    throw new Error(`source revision does not contain "${SOURCE_BIBLIOGRAPHY}"`);
  }

  return { cards, bibliography: requireRegularFile(bibliography) };
}

/**
 * Reads blob contents for the given object ids in one `git cat-file --batch`
 * subprocess. Object ids are hex, so nothing here depends on path quoting.
 */
async function readBlobs(
  repositoryRoot: string,
  objects: readonly string[],
): Promise<Buffer[]> {
  if (objects.length === 0) {
    return [];
  }

  const child = spawn(
    "git",
    ["-C", repositoryRoot, "cat-file", "--batch", "--buffer"],
    { stdio: ["pipe", "pipe", "pipe"] },
  );

  const stdout: Buffer[] = [];
  const stderr: Buffer[] = [];
  child.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
  child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));

  const finished = new Promise<void>((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code, signal) => {
      if (code === 0) {
        resolve();
        return;
      }
      const detail = Buffer.concat(stderr).toString("utf8").trim();
      reject(
        new Error(
          `git cat-file failed (code ${code}, signal ${signal})${detail ? `: ${detail}` : ""}`,
        ),
      );
    });
  });

  child.stdin.on("error", () => {
    // Reported through the process exit path below.
  });
  child.stdin.end(`${objects.join("\n")}\n`);

  await finished;
  return parseBatchOutput(Buffer.concat(stdout), objects);
}

function parseBatchOutput(
  output: Buffer,
  objects: readonly string[],
): Buffer[] {
  const blobs: Buffer[] = [];
  let offset = 0;

  for (const object of objects) {
    const newline = output.indexOf(0x0a, offset);
    if (newline === -1) {
      throw new Error(`git cat-file returned no header for "${object}"`);
    }
    const header = output.toString("utf8", offset, newline);
    const [id, type, size] = header.split(" ");
    if (id !== object || type !== "blob" || size === undefined) {
      throw new Error(`git cat-file returned "${header}" for "${object}"`);
    }
    const bytes = Number(size);
    if (!Number.isSafeInteger(bytes) || bytes < 0) {
      throw new Error(`git cat-file reported size "${size}" for "${object}"`);
    }
    const start = newline + 1;
    const end = start + bytes;
    if (output.length < end + 1) {
      throw new Error(`git cat-file returned truncated data for "${object}"`);
    }
    blobs.push(output.subarray(start, end));
    offset = end + 1;
  }

  if (offset !== output.length) {
    throw new Error("git cat-file returned unexpected trailing output");
  }
  return blobs;
}

/**
 * Lists every file under `root` as sorted POSIX paths relative to it.
 *
 * The listing is deliberately unfiltered: the destination holds a byte-exact
 * imported corpus, so anything the manifest does not describe — a sidecar, a
 * stray note, an editor backup — must fail verification rather than be
 * tolerated and then silently discarded by the next import.
 */
async function listDestinationFiles(root: string): Promise<string[]> {
  const found: string[] = [];

  const walk = async (directory: string): Promise<void> => {
    const entries = await readdir(directory, { withFileTypes: true });
    for (const entry of entries) {
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        await walk(absolute);
      } else {
        found.push(path.relative(root, absolute).split(path.sep).join("/"));
      }
    }
  };

  if (await isDirectory(root)) {
    await walk(root);
  }
  return found.sort(comparePosix);
}

/**
 * Guards against a hand-edited manifest steering reads outside the
 * destination, e.g. `../../etc/passwd` or `/etc/passwd`.
 */
function isSafeRelativePath(relative: string): boolean {
  if (relative === "" || relative.includes("\\") || relative.includes("\0")) {
    return false;
  }
  const segments = relative.split("/");
  return (
    !path.isAbsolute(relative) &&
    segments.every((segment) => segment !== "" && segment !== "." && segment !== "..")
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseManifest(text: string, source: string): MigrationManifest {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    throw new Error(`${source} is not valid JSON: ${describe(error)}`);
  }

  const invalid = (detail: string): never => {
    throw new Error(`${source} is not a valid migration manifest: ${detail}`);
  };
  const requireRecord = (
    value: unknown,
    field: string,
  ): Record<string, unknown> =>
    isRecord(value) ? value : invalid(`expected ${field} to be an object`);
  const requireLiteral = <T>(value: unknown, field: string, literal: T): T =>
    value === literal
      ? literal
      : invalid(`expected ${field} to be ${JSON.stringify(literal)}`);
  const requireDigest = (value: unknown, field: string): string =>
    typeof value === "string" && /^[0-9a-f]{64}$/.test(value)
      ? value
      : invalid(`expected ${field} to be a SHA-256 digest`);
  const requireByteCount = (value: unknown, field: string): number =>
    typeof value === "number" && Number.isSafeInteger(value) && value >= 0
      ? value
      : invalid(`expected ${field} to be a byte count`);

  const manifest = requireRecord(parsed, "the manifest");
  requireLiteral(manifest.schemaVersion, "schemaVersion", 1);
  requireLiteral(manifest.destination, "destination", DESTINATION_PATH);

  const origin = requireRecord(manifest.source, "source");
  requireLiteral(origin.repository, "source.repository", "quantum.harness");
  requireLiteral(origin.subtree, "source.subtree", SOURCE_SUBTREE);
  const revision = origin.revision;
  if (typeof revision !== "string" || !REVISION_PATTERN.test(revision)) {
    invalid("expected source.revision to be a commit SHA");
  }

  const bibliography = requireRecord(manifest.bibliography, "bibliography");
  requireLiteral(bibliography.path, "bibliography.path", BIBLIOGRAPHY_PATH);

  const files = manifest.files;
  if (!Array.isArray(files)) {
    invalid("expected files to be an array");
  }

  const entries: MigrationEntry[] = (files as unknown[]).map((value, index) => {
    const entry = requireRecord(value, `files[${index}]`);
    const relative = entry.path;
    if (typeof relative !== "string" || !isSafeRelativePath(relative)) {
      return invalid(
        `expected files[${index}].path to be a relative POSIX path inside ${DESTINATION_PATH}`,
      );
    }
    return {
      path: relative,
      bytes: requireByteCount(entry.bytes, `files[${index}].bytes`),
      sha256: requireDigest(entry.sha256, `files[${index}].sha256`),
    };
  });

  return {
    schemaVersion: 1,
    source: {
      repository: "quantum.harness",
      subtree: SOURCE_SUBTREE,
      revision: revision as string,
    },
    destination: DESTINATION_PATH,
    files: entries,
    bibliography: {
      path: BIBLIOGRAPHY_PATH,
      bytes: requireByteCount(bibliography.bytes, "bibliography.bytes"),
      sha256: requireDigest(bibliography.sha256, "bibliography.sha256"),
    },
  };
}

async function readManifest(repoRoot: string): Promise<MigrationManifest> {
  const absolute = toSystemPath(repoRoot, MANIFEST_PATH);
  let text: string;
  try {
    text = await readFile(absolute, "utf8");
  } catch {
    throw new Error(`${MANIFEST_PATH} is missing; run the import first`);
  }
  return parseManifest(text, MANIFEST_PATH);
}

/**
 * Refuses to replace a destination that is not a byte-exact, manifest-backed
 * import, so hand-written or edited cards are never silently overwritten.
 */
async function requireReplaceableDestination(repoRoot: string): Promise<void> {
  try {
    await verifyHarnessImport(repoRoot);
  } catch (error) {
    throw new Error(
      `refusing to overwrite the existing "${DESTINATION_PATH}": ${describe(error)}`,
      { cause: error },
    );
  }
}

export async function importHarnessKnowledge(
  options: SourceOptions,
): Promise<MigrationManifest> {
  const repoRoot = path.resolve(options.repoRoot);
  const repositoryRoot = await resolveSource(options);

  const destinationRoot = toSystemPath(repoRoot, DESTINATION_PATH);
  const bibliographyTarget = toSystemPath(repoRoot, BIBLIOGRAPHY_PATH);
  const manifestTarget = toSystemPath(repoRoot, MANIFEST_PATH);

  const destinationPresent = await isDirectory(destinationRoot);
  if (destinationPresent) {
    await requireReplaceableDestination(repoRoot);
  }

  const selected = selectSource(
    await listSourceEntries(repositoryRoot, options.sourceRevision),
  );
  const contents = await readBlobs(repositoryRoot, [
    ...selected.cards.map(({ source }) => source.object),
    selected.bibliography.object,
  ]);
  const bibliography = contents[contents.length - 1]!;

  const manifest: MigrationManifest = {
    schemaVersion: 1,
    source: {
      repository: "quantum.harness",
      subtree: SOURCE_SUBTREE,
      revision: options.sourceRevision,
    },
    destination: DESTINATION_PATH,
    files: selected.cards.map(({ destination }, index) => {
      const content = contents[index]!;
      return {
        path: destination,
        bytes: content.byteLength,
        sha256: sha256(content),
      };
    }),
    bibliography: {
      path: BIBLIOGRAPHY_PATH,
      bytes: bibliography.byteLength,
      sha256: sha256(bibliography),
    },
  };

  const stagingRoot = toSystemPath(repoRoot, STAGING_PATH);
  await rm(stagingRoot, { recursive: true, force: true });
  await mkdir(stagingRoot, { recursive: true });

  let keepStaging = false;
  try {
    const stagedCards = path.join(stagingRoot, "cards");
    for (const [index, { destination }] of selected.cards.entries()) {
      const target = toSystemPath(stagedCards, destination);
      await mkdir(path.dirname(target), { recursive: true });
      await writeFile(target, contents[index]!);
    }
    if (selected.cards.length === 0) {
      await mkdir(stagedCards, { recursive: true });
    }

    const stagedBibliography = path.join(stagingRoot, "ref.bib");
    await writeFile(stagedBibliography, bibliography);

    const stagedManifest = path.join(stagingRoot, "manifest.json");
    await writeFile(stagedManifest, `${JSON.stringify(manifest, null, 2)}\n`);

    // Install in dependency order: cards, then bibliography, then the manifest
    // that describes them. A failure at any step restores every target, so the
    // repository is never left with a half-installed import.
    const displacedRoot = path.join(stagingRoot, "replaced");
    await mkdir(displacedRoot, { recursive: true });
    await installAtomically([
      {
        staged: stagedCards,
        target: destinationRoot,
        displaced: path.join(displacedRoot, "cards"),
      },
      {
        staged: stagedBibliography,
        target: bibliographyTarget,
        displaced: path.join(displacedRoot, "ref.bib"),
      },
      {
        staged: stagedManifest,
        target: manifestTarget,
        displaced: path.join(displacedRoot, "manifest.json"),
      },
    ]);
  } catch (error) {
    if (error instanceof IncompleteRollbackError) {
      keepStaging = true;
      throw new Error(
        `${describe(error)}; "${STAGING_PATH}" was kept because it holds the only copy of the replaced files`,
        { cause: error },
      );
    }
    throw error;
  } finally {
    if (!keepStaging) {
      await rm(stagingRoot, { recursive: true, force: true });
    }
  }

  return manifest;
}

/**
 * Checks the imported cards and bibliography against the committed manifest.
 * Needs no access to the source repository.
 */
export async function verifyHarnessImport(
  repoRoot: string,
): Promise<MigrationTotals> {
  const root = path.resolve(repoRoot);
  const manifest = await readManifest(root);
  const destinationRoot = toSystemPath(root, DESTINATION_PATH);

  const expected = manifest.files.map((entry) => entry.path);
  const present = await listDestinationFiles(destinationRoot);
  const presentSet = new Set(present);
  const expectedSet = new Set(expected);

  const missing = expected.filter((relative) => !presentSet.has(relative));
  if (missing.length > 0) {
    throw new Error(
      `${DESTINATION_PATH} is missing ${missing.length} imported card(s): ${missing.join(", ")}`,
    );
  }
  const unexpected = present.filter((relative) => !expectedSet.has(relative));
  if (unexpected.length > 0) {
    throw new Error(
      `${DESTINATION_PATH} contains ${unexpected.length} file(s) that are not in ${MANIFEST_PATH}: ${unexpected.join(", ")}`,
    );
  }

  let bytes = 0;
  for (const entry of manifest.files) {
    const content = await readFile(toSystemPath(destinationRoot, entry.path));
    if (content.byteLength !== entry.bytes || sha256(content) !== entry.sha256) {
      throw new Error(
        `imported card ${entry.path} does not match ${MANIFEST_PATH}`,
      );
    }
    bytes += entry.bytes;
  }

  const bibliography = await readFile(
    toSystemPath(root, manifest.bibliography.path),
  ).catch(() => {
    throw new Error(`${manifest.bibliography.path} is missing`);
  });
  if (
    bibliography.byteLength !== manifest.bibliography.bytes ||
    sha256(bibliography) !== manifest.bibliography.sha256
  ) {
    throw new Error(
      `${manifest.bibliography.path} does not match ${MANIFEST_PATH}`,
    );
  }

  return { files: manifest.files.length, bytes };
}

/**
 * Re-derives the selection from the pinned source revision and compares raw
 * bytes on both sides, so drift in either the source or the destination fails.
 */
export async function verifyHarnessImportAgainstSource(
  options: SourceOptions,
): Promise<MigrationTotals> {
  const repoRoot = path.resolve(options.repoRoot);
  const repositoryRoot = await resolveSource(options);
  const manifest = await readManifest(repoRoot);

  if (manifest.source.revision !== options.sourceRevision) {
    throw new Error(
      `${MANIFEST_PATH} records revision "${manifest.source.revision}", not the requested "${options.sourceRevision}"`,
    );
  }

  const totals = await verifyHarnessImport(repoRoot);

  const selected = selectSource(
    await listSourceEntries(repositoryRoot, options.sourceRevision),
  );
  const sourcePaths = selected.cards.map(({ destination }) => destination);
  const manifestPaths = manifest.files.map((entry) => entry.path);
  const manifestSet = new Set(manifestPaths);
  const sourceSet = new Set(sourcePaths);

  const missing = sourcePaths.filter((relative) => !manifestSet.has(relative));
  if (missing.length > 0) {
    throw new Error(
      `${MANIFEST_PATH} is missing ${missing.length} source card(s): ${missing.join(", ")}`,
    );
  }
  const extra = manifestPaths.filter((relative) => !sourceSet.has(relative));
  if (extra.length > 0) {
    throw new Error(
      `${MANIFEST_PATH} lists ${extra.length} card(s) absent from the source revision: ${extra.join(", ")}`,
    );
  }

  const contents = await readBlobs(repositoryRoot, [
    ...selected.cards.map(({ source }) => source.object),
    selected.bibliography.object,
  ]);
  const destinationRoot = toSystemPath(repoRoot, DESTINATION_PATH);

  for (const [index, { destination }] of selected.cards.entries()) {
    const expected = contents[index]!;
    const actual = await readFile(toSystemPath(destinationRoot, destination));
    if (!actual.equals(expected)) {
      throw new Error(
        `${DESTINATION_PATH}/${destination} differs from the source revision`,
      );
    }
  }

  const expectedBibliography = contents[contents.length - 1]!;
  const actualBibliography = await readFile(
    toSystemPath(repoRoot, BIBLIOGRAPHY_PATH),
  );
  if (!actualBibliography.equals(expectedBibliography)) {
    throw new Error(`${BIBLIOGRAPHY_PATH} differs from the source revision`);
  }

  return totals;
}

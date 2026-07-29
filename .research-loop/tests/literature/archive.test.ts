import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";

import {
  ARCHIVE_LIMITS,
  ArchiveError,
  extractSourceArchive,
  type ArchiveErrorCode,
  type ExtractionResult,
} from "../../../src/lib/literature/archive.js";
import { FIGURE_EXTENSIONS } from "../../../src/lib/literature/figures.js";
import { ARCHIVE_FIXTURES } from "../fixtures/archives/build.js";

const FIXTURE_DIR = path.resolve(
  fileURLToPath(import.meta.url),
  "..",
  "..",
  "fixtures",
  "archives",
);

const CITEKEY = "fixture_2020_paper";

async function fixture(name: string): Promise<Buffer> {
  return await readFile(path.join(FIXTURE_DIR, name));
}

interface Staging {
  sourceDir: string;
  figuresDir: string;
}

async function staging(t: TestContext): Promise<Staging> {
  const root = await mkdtemp(path.join(tmpdir(), "research-loop-archive-"));
  t.after(async () => {
    await rm(root, { recursive: true, force: true });
  });
  return {
    sourceDir: path.join(root, "source"),
    figuresDir: path.join(root, "figures"),
  };
}

/** Every file under a directory, as sorted POSIX paths relative to it. */
async function listFiles(root: string): Promise<string[]> {
  const found: string[] = [];
  const walk = async (directory: string, prefix: string): Promise<void> => {
    let children;
    try {
      children = await readdir(directory, { withFileTypes: true });
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") {
        return;
      }
      throw error;
    }
    for (const child of children) {
      const relative = prefix === "" ? child.name : `${prefix}/${child.name}`;
      if (child.isDirectory()) {
        await walk(path.join(directory, child.name), relative);
      } else {
        found.push(relative);
      }
    }
  };
  await walk(root, "");
  return found.sort();
}

function sha256(bytes: Buffer | string): string {
  return createHash("sha256").update(bytes).digest("hex");
}

async function extractFixture(
  t: TestContext,
  name: string,
  overrides: {
    citekey?: string;
    limits?: Partial<Record<keyof typeof ARCHIVE_LIMITS, number>>;
  } = {},
): Promise<{ result: ExtractionResult } & Staging> {
  const dirs = await staging(t);
  const result = await extractSourceArchive({
    archive: await fixture(name),
    citekey: overrides.citekey ?? CITEKEY,
    sourceDir: dirs.sourceDir,
    figuresDir: dirs.figuresDir,
    ...(overrides.limits === undefined ? {} : { limits: overrides.limits }),
  });
  return { result, ...dirs };
}

/**
 * Runs an extraction that must be refused, and returns the refusal together
 * with what reached the staging directories — which must always be nothing.
 */
async function rejectFixture(
  t: TestContext,
  name: string,
  overrides: {
    citekey?: string;
    limits?: Partial<Record<keyof typeof ARCHIVE_LIMITS, number>>;
  } = {},
): Promise<{ error: ArchiveError; sourceFiles: string[]; figureFiles: string[] }> {
  const dirs = await staging(t);
  let error: unknown;
  try {
    await extractSourceArchive({
      archive: await fixture(name),
      citekey: overrides.citekey ?? CITEKEY,
      sourceDir: dirs.sourceDir,
      figuresDir: dirs.figuresDir,
      ...(overrides.limits === undefined ? {} : { limits: overrides.limits }),
    });
  } catch (thrown) {
    error = thrown;
  }
  assert.ok(
    error instanceof ArchiveError,
    `${name} was accepted, or refused with ${String(error)}`,
  );
  return {
    error,
    sourceFiles: await listFiles(dirs.sourceDir),
    figureFiles: await listFiles(dirs.figuresDir),
  };
}

test("the resource ceilings are the approved ones", () => {
  assert.deepEqual({ ...ARCHIVE_LIMITS }, {
    compressedBytes: 100 * 1024 * 1024,
    extractedBytes: 512 * 1024 * 1024,
    singleFileBytes: 128 * 1024 * 1024,
    entries: 10_000,
  });
});

test("every committed fixture still matches the builder that describes it", async () => {
  for (const [name, expected] of ARCHIVE_FIXTURES) {
    const committed = await fixture(name);
    if (name.endsWith(".gz")) {
      // Deflate output is not stable across zlib versions; the payload is.
      assert.deepEqual(
        gunzipSync(committed),
        gunzipSync(expected),
        `${name} decompresses to different bytes than the builder produces`,
      );
    } else {
      assert.deepEqual(committed, expected, `${name} differs from the builder`);
    }
  }
});

test("a plain tar keeps every source file byte for byte", async (t) => {
  const { result, sourceDir } = await extractFixture(t, "benign-plain.tar");

  assert.equal(result.format, "tar");
  assert.equal(result.sourceRoot, path.resolve(sourceDir));
  assert.equal(result.mainTex, "main.tex");

  assert.deepEqual(
    result.files.map((file) => file.path),
    [
      "data/table.csv",
      "figures/diagram.pdf",
      "figures/lattice.eps",
      "figures/micrograph.tif",
      "figures/nested/micrograph.tiff",
      "figures/photo.JPG",
      "figures/plot.png",
      "figures/scan.jpeg",
      "figures/sketch.svg",
      "main.bbl",
      "main.tex",
      "macros.sty",
      "refs.bib",
      "revtex-fixture.cls",
      "sections/appendix.tex",
      "sections/intro.tex",
    ].sort(),
  );

  // The manifest describes the bytes that were actually written.
  for (const file of result.files) {
    const written = await readFile(path.join(sourceDir, file.path));
    assert.equal(written.length, file.bytes, `${file.path} has the wrong length`);
    assert.equal(sha256(written), file.sha256, `${file.path} has the wrong digest`);
  }

  const main = await readFile(path.join(sourceDir, "main.tex"), "utf8");
  assert.match(main, /\\documentclass\[aps,prl\]\{revtex4-2\}/);
  assert.match(main, /\\begin\{document\}/);
  assert.equal(
    await readFile(path.join(sourceDir, "macros.sty"), "utf8"),
    "\\newcommand{\\op}[1]{\\hat{#1}}\n",
  );
  assert.equal(
    await readFile(path.join(sourceDir, "revtex-fixture.cls"), "utf8"),
    "\\ProvidesClass{revtex-fixture}\n",
  );
  assert.equal(
    await readFile(path.join(sourceDir, "refs.bib"), "utf8"),
    "@article{fixture, title = {A fixture}}\n",
  );
});

test("figures are copied byte for byte, keeping their place in the tree", async (t) => {
  const { result, sourceDir, figuresDir } = await extractFixture(t, "benign-plain.tar");

  assert.deepEqual(
    result.figures.map((figure) => figure.destination),
    [
      "figures/diagram.pdf",
      "figures/lattice.eps",
      "figures/micrograph.tif",
      "figures/nested/micrograph.tiff",
      "figures/photo.JPG",
      "figures/plot.png",
      "figures/scan.jpeg",
      "figures/sketch.svg",
    ],
  );
  for (const figure of result.figures) {
    assert.equal(figure.source, figure.destination);
  }

  assert.deepEqual(await listFiles(figuresDir), [
    "figures/diagram.pdf",
    "figures/lattice.eps",
    "figures/micrograph.tif",
    "figures/nested/micrograph.tiff",
    "figures/photo.JPG",
    "figures/plot.png",
    "figures/scan.jpeg",
    "figures/sketch.svg",
  ]);

  for (const figure of result.figures) {
    const original = await readFile(path.join(sourceDir, figure.source));
    const copied = await readFile(path.join(figuresDir, figure.destination));
    assert.deepEqual(copied, original, `${figure.destination} was not copied verbatim`);
    assert.equal(sha256(copied), figure.sha256);
  }
});

test("the figure extensions are exactly the approved eight", () => {
  assert.deepEqual([...FIGURE_EXTENSIONS].sort(), [
    ".eps",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".svg",
    ".tif",
    ".tiff",
  ]);
});

test("two extractions of one archive produce the same manifest", async (t) => {
  const first = await extractFixture(t, "benign-plain.tar");
  const second = await extractFixture(t, "benign-plain.tar");

  assert.notEqual(first.sourceDir, second.sourceDir);
  assert.deepEqual(first.result.files, second.result.files);
  assert.deepEqual(first.result.figures, second.result.figures);
  assert.equal(first.result.mainTex, second.result.mainTex);
});

test("a gzip-compressed tar is unpacked like the tar inside it", async (t) => {
  const plain = await extractFixture(t, "benign-plain.tar");
  const gzipped = await extractFixture(t, "benign-gzip.tar.gz");

  assert.equal(gzipped.result.format, "tar-gzip");
  assert.deepEqual(gzipped.result.files, plain.result.files);
  assert.deepEqual(gzipped.result.figures, plain.result.figures);
});

test("a gzip-compressed single TeX file becomes main.tex", async (t) => {
  const { result, sourceDir, figuresDir } = await extractFixture(t, "benign-single.tex.gz");

  assert.equal(result.format, "gzip-single-tex");
  assert.equal(result.mainTex, "main.tex");
  assert.deepEqual(result.files.map((file) => file.path), ["main.tex"]);
  assert.deepEqual(result.figures, []);

  const written = await readFile(path.join(sourceDir, "main.tex"), "utf8");
  assert.match(written, /\\begin\{document\}/);
  assert.deepEqual(await listFiles(sourceDir), ["main.tex"]);
  assert.deepEqual(await listFiles(figuresDir), []);
});

test("octal header fields may end in a space instead of a NUL", async (t) => {
  const { result } = await extractFixture(t, "benign-space-padded.tar");

  assert.equal(result.mainTex, "paper.tex");
  assert.deepEqual(result.files.map((file) => file.path), ["img/plot.png", "paper.tex"]);
});

test("a preferred basename outranks another, and a shallower copy outranks a nested one", async (t) => {
  const { result } = await extractFixture(t, "benign-ranked-main.tar");
  assert.equal(result.mainTex, "main.tex");
});

test("a file named after the citekey outranks an unremarkable one", async (t) => {
  const { result } = await extractFixture(t, "benign-citekey-main.tar");
  assert.equal(result.mainTex, "fixture_2020_paper.tex");
});

test("depth never overrules being the only document in the archive", async (t) => {
  const { result } = await extractFixture(t, "benign-deep-only-main.tar");
  assert.equal(result.mainTex, "src/tex/manuscript.tex");
});

test("two equally ranked documents are an ambiguity, not a coin toss", async (t) => {
  const { error, sourceFiles } = await rejectFixture(t, "reject-ambiguous-main.tar");

  assert.equal(error.code, "ambiguous-main-tex");
  assert.match(error.message, /alpha\.tex/);
  assert.match(error.message, /beta\.tex/);
  assert.ok(
    error.message.indexOf("alpha.tex") < error.message.indexOf("beta.tex"),
    "candidates are listed in lexical order",
  );
  assert.doesNotMatch(error.message, /gamma\.tex/);
  assert.deepEqual(sourceFiles, []);
});

test("an archive with no main document is refused", async (t) => {
  const { error } = await rejectFixture(t, "reject-no-main.tar");
  assert.equal(error.code, "no-main-tex");
});

test("a gzip-compressed file that is not TeX is refused", async (t) => {
  const { error } = await rejectFixture(t, "reject-single-binary.gz");
  assert.equal(error.code, "unknown-format");
});

test("bytes that are neither a tar nor a gzip stream are refused", async (t) => {
  const { error } = await rejectFixture(t, "reject-not-an-archive.bin");
  assert.equal(error.code, "unknown-format");
});

const UNSAFE_MEMBERS: readonly {
  fixture: string;
  code: ArchiveErrorCode;
  detail: RegExp;
}[] = [
  { fixture: "evil-parent-traversal.tar", code: "unsafe-member", detail: /\.\./ },
  { fixture: "evil-inner-traversal.tar", code: "unsafe-member", detail: /\.\./ },
  { fixture: "evil-absolute-path.tar", code: "unsafe-member", detail: /absolute/i },
  { fixture: "evil-absolute-prefix.tar", code: "unsafe-member", detail: /absolute/i },
  { fixture: "evil-nul-split-name.tar", code: "unsafe-member", detail: /NUL/i },
  { fixture: "evil-backslash-name.tar", code: "unsafe-member", detail: /backslash/i },
  { fixture: "evil-duplicate-normalized.tar", code: "unsafe-member", detail: /twice|duplicate/i },
  { fixture: "evil-control-character-name.tar", code: "unsafe-member", detail: /control/i },
  { fixture: "evil-symlink.tar", code: "unsupported-entry-type", detail: /symbolic link/i },
  { fixture: "evil-hardlink.tar", code: "unsupported-entry-type", detail: /hard link/i },
  { fixture: "evil-char-device.tar", code: "unsupported-entry-type", detail: /device/i },
  { fixture: "evil-block-device.tar", code: "unsupported-entry-type", detail: /device/i },
  { fixture: "evil-fifo.tar", code: "unsupported-entry-type", detail: /FIFO/i },
  { fixture: "evil-pax-header.tar", code: "unsupported-entry-type", detail: /extended header/i },
  { fixture: "evil-gnu-long-name.tar", code: "unsupported-entry-type", detail: /extended header/i },
  { fixture: "evil-bad-checksum.tar", code: "malformed", detail: /checksum/i },
  { fixture: "evil-base256-size.tar", code: "malformed", detail: /size/i },
  { fixture: "evil-truncated-content.tar", code: "malformed", detail: /truncated|ends/i },
];

for (const { fixture: name, code, detail } of UNSAFE_MEMBERS) {
  test(`${name} is refused before anything is written`, async (t) => {
    const { error, sourceFiles, figureFiles } = await rejectFixture(t, name);

    assert.equal(error.code, code, `${name}: ${error.message}`);
    assert.match(error.message, detail);
    assert.deepEqual(sourceFiles, [], `${name} wrote source files`);
    assert.deepEqual(figureFiles, [], `${name} wrote figures`);
  });
}

test("a malicious member at the end of an archive still stops the benign ones", async (t) => {
  const { error, sourceFiles, figureFiles } = await rejectFixture(t, "evil-late-symlink.tar");

  assert.equal(error.code, "unsupported-entry-type");
  assert.match(error.message, /link\.tex/);
  assert.deepEqual(sourceFiles, [], "preflight ran after the first members were written");
  assert.deepEqual(figureFiles, []);
});

test("a member larger than the single-file ceiling is refused on its claim alone", async (t) => {
  const { error } = await rejectFixture(t, "evil-oversized-file.tar");

  assert.equal(error.code, "limit-exceeded");
  assert.match(error.message, /huge\.dat/);
});

test("the extracted total is bounded", async (t) => {
  const { error } = await rejectFixture(t, "evil-oversized-total.tar", {
    limits: { extractedBytes: 8 * 1024 },
  });

  assert.equal(error.code, "limit-exceeded");
  assert.match(error.message, /total/i);
});

test("the number of members is bounded", async (t) => {
  const { error } = await rejectFixture(t, "evil-many-entries.tar", {
    limits: { entries: 4 },
  });

  assert.equal(error.code, "limit-exceeded");
  assert.match(error.message, /entries|members/i);
});

test("a decompression bomb is stopped by the extracted-bytes ceiling", async (t) => {
  const { error } = await rejectFixture(t, "evil-gzip-bomb.gz", {
    limits: { extractedBytes: 64 * 1024 },
  });

  assert.equal(error.code, "limit-exceeded");
  assert.match(error.message, /decompress/i);
});

test("an archive larger than the compressed ceiling is refused unread", async (t) => {
  const { error } = await rejectFixture(t, "benign-plain.tar", {
    limits: { compressedBytes: 512 },
  });

  assert.equal(error.code, "limit-exceeded");
  assert.match(error.message, /compressed|download/i);
});

test("a caller may tighten a ceiling but never widen one", async (t) => {
  const { error } = await rejectFixture(t, "evil-oversized-file.tar", {
    limits: {
      singleFileBytes: 8 * 1024 * 1024 * 1024,
      extractedBytes: 8 * 1024 * 1024 * 1024,
      entries: 1_000_000,
      compressedBytes: 8 * 1024 * 1024 * 1024,
    },
  });

  assert.equal(error.code, "limit-exceeded");
});

test("a staging directory that already holds files is never extracted into", async (t) => {
  const dirs = await staging(t);
  await mkdir(dirs.sourceDir, { recursive: true });
  await writeFile(path.join(dirs.sourceDir, "mine.tex"), "hand written\n", "utf8");

  await assert.rejects(
    extractSourceArchive({
      archive: await fixture("benign-plain.tar"),
      citekey: CITEKEY,
      sourceDir: dirs.sourceDir,
      figuresDir: dirs.figuresDir,
    }),
    (error: unknown) =>
      error instanceof ArchiveError && error.code === "staging-not-empty",
  );
  assert.equal(
    await readFile(path.join(dirs.sourceDir, "mine.tex"), "utf8"),
    "hand written\n",
  );
});

test("an unusable citekey is refused before an archive is read", async (t) => {
  const dirs = await staging(t);

  await assert.rejects(
    extractSourceArchive({
      archive: await fixture("benign-plain.tar"),
      citekey: "../escape",
      sourceDir: dirs.sourceDir,
      figuresDir: dirs.figuresDir,
    }),
    (error: unknown) => error instanceof ArchiveError && error.code === "unusable-citekey",
  );
});

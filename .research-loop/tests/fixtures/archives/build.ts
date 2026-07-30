#!/usr/bin/env -S node --import tsx
/**
 * Builds the archive fixtures byte by byte.
 *
 * An arXiv source archive is the one thing this repository downloads from a
 * third party and unpacks onto a developer's disk, so the tests that guard the
 * unpacker have to contain real attacks. That rules out building the malicious
 * fixtures with a tar library: every maintained implementation refuses to
 * *write* a member called `../escape.tex`, rewrites an absolute path, or drops
 * the trailing bytes of a NUL-split name — the sanitizing happens in the test
 * tool and the archive that reaches the unpacker is already harmless.
 *
 * So the headers here are assembled field by field, 512 bytes at a time, with
 * nothing between the intent and the file. The same builder writes the benign
 * fixtures; that is deliberate. If a header field, a checksum, or the
 * end-of-archive padding were wrong, every benign case would fail to extract,
 * and a malicious case that "passes" because the archive is malformed in some
 * unrelated way could not hide behind a green test.
 *
 * The fixtures are committed as binary files. `archive.test.ts` reads those
 * files, and separately asserts that they still match what this builder
 * produces, so editing an attack here without regenerating the bytes is a test
 * failure rather than a silent weakening of the corpus.
 *
 * Regenerate with:
 *
 *     node --import tsx tests/fixtures/archives/build.ts
 */

import { gzipSync } from "node:zlib";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BLOCK = 512;

/** Offsets and widths of the ustar header fields, in one place. */
const FIELD = {
  name: { offset: 0, length: 100 },
  mode: { offset: 100, length: 8 },
  uid: { offset: 108, length: 8 },
  gid: { offset: 116, length: 8 },
  size: { offset: 124, length: 12 },
  mtime: { offset: 136, length: 12 },
  chksum: { offset: 148, length: 8 },
  typeflag: { offset: 156, length: 1 },
  linkname: { offset: 157, length: 100 },
  magic: { offset: 257, length: 6 },
  version: { offset: 263, length: 2 },
  uname: { offset: 265, length: 32 },
  gname: { offset: 297, length: 32 },
  devmajor: { offset: 329, length: 8 },
  devminor: { offset: 337, length: 8 },
  prefix: { offset: 345, length: 155 },
} as const;

export interface MemberSpec {
  /** Written into the name field as UTF-8, NUL-padded. */
  name?: string;
  /** Exact bytes of the name field, for names that are not NUL-terminated. */
  rawName?: Buffer;
  /** `0` regular, `5` directory, `1` link, `2` symlink, `3`/`4` device, `6` FIFO. */
  typeflag?: string;
  linkname?: string;
  prefix?: string;
  content?: string | Buffer;
  /** Declared size, when it must differ from the emitted content. */
  declaredSize?: number;
  /** Raw bytes of the size field, for GNU base-256 sizes. */
  rawSize?: Buffer;
  /** Whether the content blocks follow the header. Default `true`. */
  emitContent?: boolean;
  /** How octal fields end: NUL (GNU) or space (some BSD tars). */
  numericStyle?: "nul" | "space";
  devmajor?: string;
  devminor?: string;
  mode?: number;
  /** Writes a checksum that does not match the header. */
  corruptChecksum?: boolean;
}

function toBuffer(content: string | Buffer | undefined): Buffer {
  if (content === undefined) {
    return Buffer.alloc(0);
  }
  return typeof content === "string" ? Buffer.from(content, "utf8") : content;
}

function putBytes(
  header: Buffer,
  field: { offset: number; length: number },
  value: Buffer,
): void {
  if (value.length > field.length) {
    throw new Error(`fixture field overflow: ${value.length} > ${field.length}`);
  }
  value.copy(header, field.offset);
}

function putText(
  header: Buffer,
  field: { offset: number; length: number },
  value: string,
): void {
  putBytes(header, field, Buffer.from(value, "utf8"));
}

/**
 * Writes an octal field.
 *
 * Historic tars disagree on the terminator: GNU writes digits then a NUL, some
 * BSD tars write digits then a space. Both are valid, and the unpacker has to
 * accept both, so both appear in the fixtures.
 */
function putOctal(
  header: Buffer,
  field: { offset: number; length: number },
  value: number,
  style: "nul" | "space",
): void {
  const digits = field.length - 1;
  const text = value.toString(8).padStart(digits, "0");
  if (text.length > digits) {
    throw new Error(`fixture octal overflow: ${value} does not fit ${digits} digits`);
  }
  putText(header, field, style === "nul" ? `${text}\0` : `${text} `);
}

/** The ustar checksum: every header byte, with the checksum field read as spaces. */
function checksum(header: Buffer): number {
  let sum = 0;
  for (let index = 0; index < BLOCK; index += 1) {
    const inChecksumField =
      index >= FIELD.chksum.offset && index < FIELD.chksum.offset + FIELD.chksum.length;
    sum += inChecksumField ? 0x20 : header[index];
  }
  return sum;
}

/** One member: a 512-byte header plus its content, padded to a block boundary. */
export function tarMember(spec: MemberSpec): Buffer {
  const header = Buffer.alloc(BLOCK);
  const content = toBuffer(spec.content);
  const style = spec.numericStyle ?? "nul";

  if (spec.rawName !== undefined) {
    putBytes(header, FIELD.name, spec.rawName);
  } else {
    putText(header, FIELD.name, spec.name ?? "");
  }
  putOctal(header, FIELD.mode, spec.mode ?? 0o644, style);
  putOctal(header, FIELD.uid, 0, style);
  putOctal(header, FIELD.gid, 0, style);
  if (spec.rawSize !== undefined) {
    putBytes(header, FIELD.size, spec.rawSize);
  } else {
    putOctal(header, FIELD.size, spec.declaredSize ?? content.length, style);
  }
  // A fixed mtime keeps the fixtures reproducible.
  putOctal(header, FIELD.mtime, 0o12345670000, style);
  putText(header, FIELD.typeflag, spec.typeflag ?? "0");
  putText(header, FIELD.linkname, spec.linkname ?? "");
  putText(header, FIELD.magic, "ustar\0");
  putText(header, FIELD.version, "00");
  putText(header, FIELD.uname, "fixture");
  putText(header, FIELD.gname, "fixture");
  if (spec.devmajor !== undefined) {
    putText(header, FIELD.devmajor, spec.devmajor);
  }
  if (spec.devminor !== undefined) {
    putText(header, FIELD.devminor, spec.devminor);
  }
  if (spec.prefix !== undefined) {
    putText(header, FIELD.prefix, spec.prefix);
  }

  const sum = checksum(header) + (spec.corruptChecksum === true ? 1 : 0);
  putText(header, FIELD.chksum, `${sum.toString(8).padStart(6, "0")}\0 `);

  if (spec.emitContent === false || content.length === 0) {
    return header;
  }
  const padded = Buffer.alloc(Math.ceil(content.length / BLOCK) * BLOCK);
  content.copy(padded);
  return Buffer.concat([header, padded]);
}

/** Members followed by the end-of-archive marker: two zero blocks. */
export function tarArchive(
  members: readonly MemberSpec[],
  options: { endBlocks?: number } = {},
): Buffer {
  const blocks = members.map(tarMember);
  const endBlocks = options.endBlocks ?? 2;
  return Buffer.concat([...blocks, Buffer.alloc(endBlocks * BLOCK)]);
}

const DOCUMENT = (title: string): string =>
  [
    "\\documentclass[aps,prl]{revtex4-2}",
    "\\usepackage{macros}",
    "\\begin{document}",
    `\\title{${title}}`,
    "\\bibliography{refs}",
    "\\end{document}",
    "",
  ].join("\n");

/** A TeX file that is *not* a main document: no `\begin{document}`. */
const SECTION = (name: string): string =>
  `\\section{${name}}\nSee \\cite{fixture} for the derivation.\n`;

/**
 * A file whose text mentions the main-document markers only inside a TeX
 * comment. Comment stripping must keep it out of the candidate set.
 */
const COMMENTED_OUT = [
  "% \\documentclass{article}",
  "% \\begin{document}",
  "\\section{Appendix}",
  "The 100\\% figure above is not a comment.",
  "",
].join("\n");

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x01]);
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46]);
const PDF = Buffer.from("%PDF-1.5\n%\u00e2\u00e3\u00cf\u00d3\n", "latin1");
const TIFF = Buffer.from([0x49, 0x49, 0x2a, 0x00, 0x08, 0x00, 0x00, 0x00]);
const EPS = Buffer.from("%!PS-Adobe-3.0 EPSF-3.0\n", "latin1");
const SVG = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"></svg>\n', "utf8");

/**
 * The benign archive every extraction assertion is written against: one main
 * document, the TeX support files that must survive, all eight figure
 * extensions (one of them upper-case), and files that are neither.
 */
const benignMembers: readonly MemberSpec[] = [
  { name: "main.tex", content: DOCUMENT("A fixture paper") },
  { name: "macros.sty", content: "\\newcommand{\\op}[1]{\\hat{#1}}\n" },
  { name: "revtex-fixture.cls", content: "\\ProvidesClass{revtex-fixture}\n" },
  { name: "refs.bib", content: "@article{fixture, title = {A fixture}}\n" },
  { name: "sections/", typeflag: "5", mode: 0o755 },
  { name: "sections/intro.tex", content: SECTION("Introduction") },
  { name: "sections/appendix.tex", content: COMMENTED_OUT },
  { name: "figures/", typeflag: "5", mode: 0o755 },
  { name: "figures/plot.png", content: PNG },
  { name: "figures/photo.JPG", content: JPEG },
  { name: "figures/scan.jpeg", content: JPEG },
  { name: "figures/diagram.pdf", content: PDF },
  { name: "figures/lattice.eps", content: EPS },
  { name: "figures/sketch.svg", content: SVG },
  { name: "figures/micrograph.tif", content: TIFF },
  { name: "figures/nested/micrograph.tiff", content: TIFF },
  { name: "data/table.csv", content: "beta,energy\n1.0,-0.5\n" },
  { name: "main.bbl", content: "\\begin{thebibliography}{1}\n\\end{thebibliography}\n" },
];

/** A tar whose numeric fields end in spaces rather than NULs. */
const spacePaddedMembers: readonly MemberSpec[] = [
  { name: "paper.tex", content: DOCUMENT("Space padded"), numericStyle: "space" },
  { name: "img/plot.png", content: PNG, numericStyle: "space" },
];

const REPEATED_ENTRY = (index: number): MemberSpec => ({
  name: `part${index}.tex`,
  content: index === 0 ? DOCUMENT("Many entries") : SECTION(`Part ${index}`),
});

const ZERO_MEGABYTE = Buffer.alloc(1024 * 1024);

function fixtures(): ReadonlyMap<string, Buffer> {
  const entries: [string, Buffer][] = [
    // --- benign -----------------------------------------------------------
    ["benign-plain.tar", tarArchive(benignMembers)],
    ["benign-gzip.tar.gz", gzipSync(tarArchive(benignMembers), { level: 9 })],
    [
      "benign-space-padded.tar",
      tarArchive(spacePaddedMembers),
    ],
    ["benign-single.tex.gz", gzipSync(Buffer.from(DOCUMENT("A single file"), "utf8"), { level: 9 })],
    [
      // `main` outranks `paper`, and the root copy outranks the nested one.
      "benign-ranked-main.tar",
      tarArchive([
        { name: "paper.tex", content: DOCUMENT("Runner up") },
        { name: "nested/main.tex", content: DOCUMENT("Nested") },
        { name: "main.tex", content: DOCUMENT("The main document") },
      ]),
    ],
    [
      // No preferred basename, so the citekey breaks the rank tie.
      "benign-citekey-main.tar",
      tarArchive([
        { name: "supplement.tex", content: DOCUMENT("Supplement") },
        { name: "fixture_2020_paper.tex", content: DOCUMENT("Named after the citekey") },
      ]),
    ],
    [
      // Only one file is a document; depth does not matter.
      "benign-deep-only-main.tar",
      tarArchive([
        { name: "src/tex/manuscript.tex", content: DOCUMENT("Deep") },
        { name: "src/tex/preamble.tex", content: SECTION("Preamble") },
      ]),
    ],

    // --- rejected for what they say ---------------------------------------
    [
      "reject-ambiguous-main.tar",
      tarArchive([
        { name: "beta.tex", content: DOCUMENT("Beta") },
        { name: "alpha.tex", content: DOCUMENT("Alpha") },
        { name: "gamma.tex", content: SECTION("Gamma") },
      ]),
    ],
    [
      "reject-no-main.tar",
      tarArchive([
        { name: "sections/intro.tex", content: SECTION("Introduction") },
        { name: "figures/plot.png", content: PNG },
      ]),
    ],
    ["reject-single-binary.gz", gzipSync(Buffer.concat([PDF, Buffer.alloc(64)]), { level: 9 })],
    ["reject-not-an-archive.bin", Buffer.concat([PDF, Buffer.alloc(1024, 0x41)])],

    // --- rejected for how they are built ----------------------------------
    [
      "evil-parent-traversal.tar",
      tarArchive([
        { name: "main.tex", content: DOCUMENT("Decoy") },
        { name: "../escape.tex", content: "pwned\n" },
      ]),
    ],
    [
      "evil-inner-traversal.tar",
      tarArchive([{ name: "sections/../../escape.tex", content: "pwned\n" }]),
    ],
    [
      "evil-absolute-path.tar",
      tarArchive([{ name: "/etc/cron.d/pwned", content: "* * * * * root sh\n" }]),
    ],
    [
      "evil-absolute-prefix.tar",
      tarArchive([{ name: "pwned", prefix: "/etc/cron.d", content: "pwned\n" }]),
    ],
    [
      // `safe.tex` NUL-terminates the name; a reader that stops at the NUL sees
      // a harmless file, and a reader that keeps the whole field sees the walk.
      "evil-nul-split-name.tar",
      tarArchive([
        {
          rawName: Buffer.concat([
            Buffer.from("safe.tex\0", "utf8"),
            Buffer.from("../../../../etc/cron.d/pwned", "utf8"),
          ]),
          content: "pwned\n",
        },
      ]),
    ],
    [
      "evil-backslash-name.tar",
      tarArchive([{ name: "..\\..\\windows\\pwned.tex", content: "pwned\n" }]),
    ],
    [
      "evil-duplicate-normalized.tar",
      tarArchive([
        { name: "src/main.tex", content: DOCUMENT("First") },
        { name: "./src//main.tex", content: DOCUMENT("Second") },
      ]),
    ],
    [
      "evil-symlink.tar",
      tarArchive([{ name: "link.tex", typeflag: "2", linkname: "/etc/passwd" }]),
    ],
    [
      "evil-hardlink.tar",
      tarArchive([{ name: "link.tex", typeflag: "1", linkname: "/etc/passwd" }]),
    ],
    [
      "evil-char-device.tar",
      tarArchive([
        { name: "tty", typeflag: "3", devmajor: "0000005\0", devminor: "0000000\0" },
      ]),
    ],
    [
      "evil-block-device.tar",
      tarArchive([
        { name: "sda", typeflag: "4", devmajor: "0000008\0", devminor: "0000000\0" },
      ]),
    ],
    ["evil-fifo.tar", tarArchive([{ name: "pipe", typeflag: "6" }])],
    [
      // The malicious member is last: nothing may reach the staging directory.
      "evil-late-symlink.tar",
      tarArchive([
        { name: "main.tex", content: DOCUMENT("Decoy") },
        { name: "macros.sty", content: "\\newcommand{\\op}{}\n" },
        { name: "figures/plot.png", content: PNG },
        { name: "link.tex", typeflag: "2", linkname: "../../../etc/passwd" },
      ]),
    ],
    [
      "evil-pax-header.tar",
      tarArchive([
        { name: "PaxHeaders/main.tex", typeflag: "x", content: "30 path=../../escape.tex\n" },
        { name: "main.tex", content: DOCUMENT("Decoy") },
      ]),
    ],
    [
      "evil-gnu-long-name.tar",
      tarArchive([
        { name: "././@LongLink", typeflag: "L", content: "../../escape.tex\0" },
        { name: "main.tex", content: DOCUMENT("Decoy") },
      ]),
    ],
    [
      "evil-control-character-name.tar",
      tarArchive([{ name: "main\n../escape.tex", content: "pwned\n" }]),
    ],
    [
      "evil-bad-checksum.tar",
      tarArchive([{ name: "main.tex", content: DOCUMENT("Bad checksum"), corruptChecksum: true }]),
    ],
    [
      // A GNU base-256 size: the high bit of the first byte marks the encoding.
      "evil-base256-size.tar",
      tarArchive([
        {
          name: "huge.dat",
          rawSize: Buffer.from([0x80, 0, 0, 0, 0, 0, 0, 0, 0x40, 0, 0, 0]),
          emitContent: false,
        },
      ]),
    ],
    [
      "evil-truncated-content.tar",
      tarArchive([{ name: "main.tex", declaredSize: 4096, content: "short\n" }]),
    ],
    [
      // 200 MiB claimed by a 512-byte header: the claim alone is over the
      // single-file ceiling, so no fixture has to be 200 MiB.
      "evil-oversized-file.tar",
      tarArchive([
        { name: "huge.dat", declaredSize: 200 * 1024 * 1024, emitContent: false },
      ]),
    ],
    [
      // Three 4 KiB members: over an 8 KiB total ceiling, under every other one.
      "evil-oversized-total.tar",
      tarArchive([
        { name: "a.dat", content: Buffer.alloc(4096, 0x61) },
        { name: "b.dat", content: Buffer.alloc(4096, 0x62) },
        { name: "c.dat", content: Buffer.alloc(4096, 0x63) },
      ]),
    ],
    [
      "evil-many-entries.tar",
      tarArchive([0, 1, 2, 3, 4, 5].map(REPEATED_ENTRY)),
    ],
    [
      // 1 MiB of zeros in roughly a kilobyte: the ratio, not the size, is the
      // attack, so the ceiling has to be on the output.
      "evil-gzip-bomb.gz",
      gzipSync(ZERO_MEGABYTE, { level: 9 }),
    ],
  ];
  return new Map(entries);
}

/** Every fixture, by file name. */
export const ARCHIVE_FIXTURES: ReadonlyMap<string, Buffer> = fixtures();

/** Where the committed fixture files live. */
export const ARCHIVE_FIXTURE_DIR = path.resolve(fileURLToPath(import.meta.url), "..");

async function main(): Promise<void> {
  for (const [name, bytes] of ARCHIVE_FIXTURES) {
    await writeFile(path.join(ARCHIVE_FIXTURE_DIR, name), bytes);
  }
  console.log(`wrote ${ARCHIVE_FIXTURES.size} archive fixtures`);
}

if (process.argv[1] !== undefined && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  await main();
}

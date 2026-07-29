import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { fileURLToPath } from "node:url";

import {
  findEntry,
  loadBibliography,
  parseBibliography,
  type LiteratureEntry,
} from "../../../src/lib/literature/bibliography.js";
import {
  entriesByMethod,
  renderMethodIndex,
  writeMethodIndexes,
} from "../../../src/lib/literature/indexes.js";
import * as literature from "../../../src/lib/literature/index.js";

const FIXTURE = path.resolve(
  fileURLToPath(import.meta.url),
  "..",
  "..",
  "fixtures",
  "literature",
  "ref.bib",
);

/** A method slug that is safe to use as a directory name. */
const SAFE_METHOD = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** A citekey that is safe to embed in a path, a URL, or Markdown. */
const SAFE_CITEKEY = /^[A-Za-z0-9][A-Za-z0-9._:-]*$/;

const ENTRY = (citekey: string): string =>
  `@article{${citekey},\n  title = {A title},\n  keywords = {ed}\n}\n`;

async function fixtureEntries(): Promise<LiteratureEntry[]> {
  return await loadBibliography(FIXTURE);
}

function entry(
  entries: readonly LiteratureEntry[],
  citekey: string,
): LiteratureEntry {
  const found = entries.find((candidate) => candidate.citekey === citekey);
  assert.ok(found, `fixture is missing ${citekey}`);
  return found;
}

async function temporaryLiteratureRoot(t: TestContext): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), "research-loop-literature-"));
  t.after(async () => {
    await rm(root, { recursive: true, force: true });
  });
  return path.join(root, "literature");
}

async function listFiles(root: string): Promise<string[]> {
  const found: string[] = [];
  const walk = async (directory: string): Promise<void> => {
    for (const child of await readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, child.name);
      if (child.isDirectory()) {
        await walk(absolute);
      } else {
        found.push(path.relative(root, absolute).split(path.sep).join("/"));
      }
    }
  };
  await walk(root);
  return found.sort();
}

test("the public literature interface exposes only the implemented commands", () => {
  assert.deepEqual(Object.keys(literature).sort(), [
    "LiteratureFetchError",
    "fetchLiteratureEntry",
    "loadBibliography",
    "syncLiterature",
    "writeMethodIndexes",
  ]);
});

test("loads every fixture entry with normalized bibliographic fields", async () => {
  const entries = await fixtureEntries();

  assert.equal(entries.length, 5);
  assert.deepEqual(
    entries.map((candidate) => candidate.citekey).sort(),
    [
      "fixture-solver",
      "fixture_2011_toolkit",
      "schollwock_2011_density",
      "sorella_1998_green",
      "white_1992_real",
    ],
  );

  assert.deepEqual(entry(entries, "schollwock_2011_density"), {
    citekey: "schollwock_2011_density",
    type: "article",
    title:
      "The density-matrix renormalization group in the age of matrix product states",
    authors: ["U. Schollwöck"],
    year: "2011",
    doi: "10.1016/j.aop.2010.09.012",
    arxiv: "1008.3477v2",
    methods: ["ed", "mps-based-algorithm"],
  });

  assert.deepEqual(entry(entries, "sorella_1998_green"), {
    citekey: "sorella_1998_green",
    type: "article",
    title: "Green Function Monte Carlo with Stochastic Reconfiguration",
    authors: ["S. Sorella"],
    year: "1998",
    doi: "10.1103/PhysRevLett.80.4558",
    arxiv: "cond-mat/9803107",
    methods: ["quantum-monte-carlo", "variational-monte-carlo"],
  });
});

test("normalizes author names from both BibTeX orderings and braced literals", async () => {
  const entries = await fixtureEntries();

  assert.deepEqual(entry(entries, "white_1992_real").authors, [
    "Steven R. White",
    "Reinhard M. Noack",
  ]);
  assert.deepEqual(entry(entries, "fixture_2011_toolkit").authors, [
    "The Fixture Collaboration",
  ]);
  assert.deepEqual(entry(entries, "fixture-solver").authors, []);
});

test("omits absent optional fields instead of inventing them", async () => {
  const entries = await fixtureEntries();
  const solver = entry(entries, "fixture-solver");

  assert.equal(solver.type, "software");
  assert.equal(solver.title, "fixture/solver");
  assert.equal(solver.year, undefined);
  assert.equal(solver.doi, undefined);
  assert.equal(solver.arxiv, undefined);

  const white = entry(entries, "white_1992_real");
  assert.equal(white.doi, undefined);
  assert.equal(white.arxiv, undefined);
  assert.equal(white.year, "1992");
});

test("returns sorted, unique method slugs", async () => {
  const entries = await fixtureEntries();

  // The fixture lists `mps-based-algorithm` twice and `ed` second.
  assert.deepEqual(entry(entries, "schollwock_2011_density").methods, [
    "ed",
    "mps-based-algorithm",
  ]);

  for (const candidate of entries) {
    assert.ok(candidate.methods.length > 0, `${candidate.citekey} has no method`);
    for (const method of candidate.methods) {
      assert.match(method, SAFE_METHOD);
    }
  }
});

test("every parsed citekey is safe to use as a path segment", async () => {
  const entries = await fixtureEntries();

  for (const candidate of entries) {
    assert.match(candidate.citekey, SAFE_CITEKEY);
    assert.ok(!candidate.citekey.includes("/"));
    assert.ok(!candidate.citekey.includes("\\"));
  }
});

test("normalizes DOIs and arXiv identifiers, keeping an explicit version", async () => {
  const entries = await fixtureEntries();

  // `doi = {https://doi.org/10.1016/j.aop.2010.09.012}` in the fixture.
  assert.equal(
    entry(entries, "schollwock_2011_density").doi,
    "10.1016/j.aop.2010.09.012",
  );
  // `eprint = {arXiv:1008.3477v2}` keeps `v2` but drops the `arXiv:` prefix.
  assert.equal(entry(entries, "schollwock_2011_density").arxiv, "1008.3477v2");
  // `eprint = {https://arxiv.org/abs/1101.2646}` drops the URL prefix.
  assert.equal(entry(entries, "fixture_2011_toolkit").arxiv, "1101.2646");
  // Pre-2007 identifiers keep their archive prefix.
  assert.equal(entry(entries, "sorella_1998_green").arxiv, "cond-mat/9803107");
});

test("rejects a duplicated citekey", () => {
  assert.throws(
    () => parseBibliography(`${ENTRY("dup")}\n${ENTRY("dup")}`),
    /dup/,
  );
});

test("rejects input the BibTeX parser reports an error for", () => {
  assert.throws(
    () =>
      parseBibliography(
        "@article{broken,\n  title = {Unclosed,\n  keywords = {ed}\n",
      ),
    /Unterminated|error/i,
  );
  assert.throws(
    () => parseBibliography("this is not bibtex at all {{{ @@@\n"),
    /error/i,
  );
});

test("rejects an entry without a usable title", () => {
  assert.throws(
    () => parseBibliography("@article{empty,\n  title = {},\n  keywords = {ed}\n}\n"),
    /empty[\s\S]*title/i,
  );
  assert.throws(
    () =>
      parseBibliography("@article{blank,\n  title = { },\n  keywords = {ed}\n}\n"),
    /blank[\s\S]*title/i,
  );
  assert.throws(
    () => parseBibliography("@article{none,\n  author = {A. B.}\n}\n"),
    /none[\s\S]*title/i,
  );
});

test("rejects an entry without a method keyword", () => {
  assert.throws(
    () => parseBibliography("@article{nokw,\n  title = {A title}\n}\n"),
    /nokw[\s\S]*keyword/i,
  );
  assert.throws(
    () =>
      parseBibliography("@article{blankkw,\n  title = {A title},\n  keywords = {}\n}\n"),
    /blankkw[\s\S]*keyword/i,
  );
});

test("rejects a method keyword that is unsafe as a directory name", () => {
  for (const keyword of [
    "../escape",
    "/absolute",
    "with space",
    "UPPER",
    "trailing-",
    "under_score",
    ".hidden",
    "dots.in.name",
    "back\\slash",
  ]) {
    assert.throws(
      () =>
        parseBibliography(
          `@article{k,\n  title = {A title},\n  keywords = {${keyword}}\n}\n`,
        ),
      /method|keyword/i,
      `expected "${keyword}" to be rejected`,
    );
  }
});

test("rejects a citekey that is unsafe as a path segment", () => {
  for (const citekey of ["bad/key", "bad\\key", "../../escape", ".hidden", "-leading"]) {
    assert.throws(
      () => parseBibliography(ENTRY(citekey)),
      /citekey/i,
      `expected "${citekey}" to be rejected`,
    );
  }

  // A citekey containing whitespace is already invalid BibTeX.
  assert.throws(() => parseBibliography(ENTRY("with space")), /citekey|parser error/i);
});

test("findEntry returns the requested entry and fails loudly otherwise", async () => {
  const entries = await fixtureEntries();

  assert.equal(findEntry(entries, "sorella_1998_green").year, "1998");
  assert.throws(() => findEntry(entries, "not_in_the_bibliography"), /not_in_the_bibliography/);
});

test("groups entries by method in a deterministic order", async () => {
  const entries = await fixtureEntries();
  const grouped = entriesByMethod(entries);
  const reversed = entriesByMethod([...entries].reverse());

  assert.deepEqual(
    [...grouped.keys()],
    ["ed", "mps-based-algorithm", "quantum-monte-carlo", "variational-monte-carlo"],
  );
  assert.deepEqual(
    grouped.get("ed")?.map((candidate) => candidate.citekey),
    ["fixture-solver", "schollwock_2011_density", "white_1992_real"],
  );
  assert.deepEqual(
    grouped.get("quantum-monte-carlo")?.map((candidate) => candidate.citekey),
    ["fixture_2011_toolkit", "sorella_1998_green"],
  );

  // Bibliography order must not leak into the grouping.
  assert.deepEqual([...reversed.keys()], [...grouped.keys()]);
  for (const [method, methodEntries] of grouped) {
    assert.deepEqual(
      reversed.get(method)?.map((candidate) => candidate.citekey),
      methodEntries.map((candidate) => candidate.citekey),
    );
  }
});

test("renders an index of bibliography metadata and external links only", async () => {
  const entries = await fixtureEntries();
  const grouped = entriesByMethod(entries);
  const index = renderMethodIndex(
    "quantum-monte-carlo",
    grouped.get("quantum-monte-carlo") ?? [],
  );

  assert.match(index, /^# .*quantum-monte-carlo/m);
  assert.match(index, /^## fixture_2011_toolkit$/m);
  assert.match(index, /^## sorella_1998_green$/m);
  assert.match(
    index,
    /^- Title: Green Function Monte Carlo with Stochastic Reconfiguration$/m,
  );
  assert.match(index, /^- Authors: S\. Sorella$/m);
  assert.match(index, /^- Year: 1998$/m);
  assert.match(
    index,
    /^- DOI: <https:\/\/doi\.org\/10\.1103\/PhysRevLett\.80\.4558>$/m,
  );
  assert.match(
    index,
    /^- arXiv: <https:\/\/arxiv\.org\/abs\/cond-mat\/9803107>$/m,
  );
  assert.match(index, /^- arXiv: <https:\/\/arxiv\.org\/abs\/1101\.2646>$/m);
  assert.ok(index.endsWith("\n"));

  // Entries appear in the grouped order, not the bibliography order.
  assert.ok(
    index.indexOf("## fixture_2011_toolkit") < index.indexOf("## sorella_1998_green"),
  );

  // Absent fields produce no line at all.
  const toolkit = index.slice(index.indexOf("## fixture_2011_toolkit"));
  assert.ok(!/^- Year:/m.test(toolkit.slice(0, toolkit.indexOf("## sorella"))));
});

test("never copies full text, the current date, or local artifact links into an index", async () => {
  const entries = await fixtureEntries();
  const fixtureText = await readFile(FIXTURE, "utf8");
  const currentYear = String(new Date().getUTCFullYear());

  assert.ok(
    fixtureText.includes("SECRETFULLTEXTMARKER"),
    "the fixture must carry an abstract for this assertion to mean anything",
  );
  assert.ok(
    !fixtureText.includes(currentYear),
    "the fixture must not mention the current year for this assertion to mean anything",
  );

  for (const [method, methodEntries] of entriesByMethod(entries)) {
    const index = renderMethodIndex(method, methodEntries);

    assert.ok(!index.includes("SECRETFULLTEXTMARKER"), "index copied full text");
    assert.ok(!index.includes(currentYear), "index embedded the current year");
    assert.doesNotMatch(index, /\d{4}-\d{2}-\d{2}/, "index embedded a date");
    assert.ok(!index.includes(".raw"), "index linked a local archive");
    assert.ok(!index.includes(".figures"), "index linked a local figure");

    // Every link is an external DOI or arXiv URL.
    for (const url of index.match(/https?:\/\/[^\s>)]+/g) ?? []) {
      assert.match(url, /^https:\/\/(doi\.org|arxiv\.org)\//, `unexpected link ${url}`);
    }
  }
});

test("renders the same bytes regardless of bibliography order", async () => {
  const entries = await fixtureEntries();
  const forward = entriesByMethod(entries);
  const backward = entriesByMethod([...entries].reverse());

  for (const [method, methodEntries] of forward) {
    assert.equal(
      renderMethodIndex(method, methodEntries),
      renderMethodIndex(method, backward.get(method) ?? []),
    );
    assert.equal(
      renderMethodIndex(method, methodEntries),
      renderMethodIndex(method, methodEntries),
    );
  }
});

test("writes one INDEX.md per method and rewrites identical bytes", async (t: TestContext) => {
  const root = await temporaryLiteratureRoot(t);
  const entries = await fixtureEntries();

  const written = await writeMethodIndexes(root, entries);

  assert.deepEqual(written, [
    path.join(root, "ed", "INDEX.md"),
    path.join(root, "mps-based-algorithm", "INDEX.md"),
    path.join(root, "quantum-monte-carlo", "INDEX.md"),
    path.join(root, "variational-monte-carlo", "INDEX.md"),
  ]);
  assert.deepEqual(await listFiles(root), [
    "ed/INDEX.md",
    "mps-based-algorithm/INDEX.md",
    "quantum-monte-carlo/INDEX.md",
    "variational-monte-carlo/INDEX.md",
  ]);

  const before = await Promise.all(written.map((file) => readFile(file, "utf8")));
  assert.equal(
    before[0],
    renderMethodIndex("ed", entriesByMethod(entries).get("ed") ?? []),
  );

  const rewritten = await writeMethodIndexes(root, [...entries].reverse());
  const after = await Promise.all(rewritten.map((file) => readFile(file, "utf8")));

  assert.deepEqual(rewritten, written);
  assert.deepEqual(after, before);
});

test("keeps the ignored .raw and .figures trees of a method directory", async (t: TestContext) => {
  const root = await temporaryLiteratureRoot(t);
  const entries = await fixtureEntries();

  await mkdir(path.join(root, "ed", ".raw", "white_1992_real"), { recursive: true });
  await writeFile(path.join(root, "ed", ".raw", "white_1992_real", "paper.pdf"), "pdf");
  await mkdir(path.join(root, "ed", ".figures", "white_1992_real"), { recursive: true });
  await writeFile(path.join(root, "ed", ".figures", "white_1992_real", "f1.png"), "png");

  await writeMethodIndexes(root, entries);

  assert.equal(
    await readFile(path.join(root, "ed", ".raw", "white_1992_real", "paper.pdf"), "utf8"),
    "pdf",
  );
  assert.equal(
    await readFile(path.join(root, "ed", ".figures", "white_1992_real", "f1.png"), "utf8"),
    "png",
  );
  assert.ok(await readFile(path.join(root, "ed", "INDEX.md"), "utf8"));
});

test("refuses a method directory holding an unexpected file and writes nothing", async (t: TestContext) => {
  const root = await temporaryLiteratureRoot(t);
  const entries = await fixtureEntries();

  await mkdir(path.join(root, "quantum-monte-carlo"), { recursive: true });
  await writeFile(path.join(root, "quantum-monte-carlo", "notes.md"), "mine\n");

  await assert.rejects(
    () => writeMethodIndexes(root, entries),
    /quantum-monte-carlo[\s\S]*notes\.md/,
  );

  // Refusing must neither delete the file nor half-write the other methods.
  assert.equal(
    await readFile(path.join(root, "quantum-monte-carlo", "notes.md"), "utf8"),
    "mine\n",
  );
  assert.deepEqual(await listFiles(root), ["quantum-monte-carlo/notes.md"]);
});

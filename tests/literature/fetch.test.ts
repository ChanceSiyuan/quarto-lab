import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

import { ARCHIVE_LIMITS, ArchiveError } from "../../lib/literature/archive.js";
import {
  ARXIV_API_URL,
  ARXIV_PDF_URL_BASE,
  ARXIV_SOURCE_URL_BASE,
  ArxivError,
  REQUEST_TIMEOUT_MS,
  arxivUserAgent,
  downloadBounded,
} from "../../lib/literature/arxiv.js";
import {
  LiteratureFetchError,
  fetchLiteratureEntry,
  syncLiterature,
  type LiteratureManifest,
} from "../../lib/literature/fetch.js";
import * as literature from "../../lib/literature/index.js";

const ARCHIVE_FIXTURE_DIR = path.resolve(
  fileURLToPath(import.meta.url),
  "..",
  "..",
  "fixtures",
  "archives",
);

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..");

const SOURCE_URL = `${ARXIV_SOURCE_URL_BASE}1610.03042v2`;
const PDF_URL = `${ARXIV_PDF_URL_BASE}1610.03042v2`;

const PDF_BYTES = Buffer.from("%PDF-1.7\n1 0 obj\n<< >>\nendobj\n%%EOF\n", "latin1");

/**
 * Two arXiv references — one pinned in the bibliography, one not — and one
 * reference with no preprint at all.
 *
 * They are written in reverse citekey order, exactly like the real
 * `literature/ref.bib`, so a sync that walked the file instead of sorting it
 * would be visible in the order of the requests it makes.
 */
const BIBLIOGRAPHY = [
  "@book{gamma_2019_local,",
  "  author = {C. Author},",
  "  title = {Gamma},",
  "  year = {2019},",
  "  doi = {10.1000/gamma},",
  "  keywords = {dmft}",
  "}",
  "",
  "@article{beta_2018_latest,",
  "  author = {B. Author},",
  "  title = {Beta},",
  "  year = {2018},",
  "  eprint = {1801.00001},",
  "  archivePrefix = {arXiv},",
  "  keywords = {ed}",
  "}",
  "",
  "@article{alpha_2016_source,",
  "  author = {A. Author},",
  "  title = {Alpha},",
  "  year = {2016},",
  "  eprint = {1610.03042v2},",
  "  archivePrefix = {arXiv},",
  "  keywords = {ed, software}",
  "}",
  "",
].join("\n");

function atomFeed(id: string, version: string): string {
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<feed xmlns="http://www.w3.org/2005/Atom">',
    `  <id>http://arxiv.org/api/query?id_list=${id}</id>`,
    "  <entry>",
    `    <id>http://arxiv.org/abs/${id}${version}</id>`,
    "    <title>Alpha</title>",
    "  </entry>",
    "</feed>",
    "",
  ].join("\n");
}

function sha256(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

/**
 * A response body. `Buffer` is a view on Node's pooled allocator, which is an
 * `ArrayBufferLike`; `BodyInit` wants a view on a plain `ArrayBuffer`.
 */
function bodyOf(bytes: Buffer): Uint8Array<ArrayBuffer> {
  const body = new Uint8Array(new ArrayBuffer(bytes.length));
  body.set(bytes);
  return body;
}

async function sourceArchive(): Promise<Buffer> {
  return gzipSync(await readFile(path.join(ARCHIVE_FIXTURE_DIR, "benign-plain.tar")), {
    level: 9,
  });
}

async function literatureRoot(t: TestContext, bibliography = BIBLIOGRAPHY): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), "research-loop-fetch-"));
  t.after(async () => {
    await rm(root, { recursive: true, force: true });
  });
  const literatureDir = path.join(root, "literature");
  await mkdir(literatureDir, { recursive: true });
  await writeFile(path.join(literatureDir, "ref.bib"), bibliography, "utf8");
  return literatureDir;
}

interface RecordedCall {
  url: string;
  headers: Record<string, string>;
  redirect: RequestRedirect | undefined;
  signal: AbortSignal | null | undefined;
}

interface MockFetch {
  fetchImpl: typeof fetch;
  calls: RecordedCall[];
}

/** Wires a `fetch` that records what it was asked for and answers from a map. */
function mockFetch(
  respond: (url: string) => Response | Promise<Response> | Error,
): MockFetch {
  const calls: RecordedCall[] = [];
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const headers: Record<string, string> = {};
    new Headers(init?.headers).forEach((value, key) => {
      headers[key.toLowerCase()] = value;
    });
    calls.push({ url, headers, redirect: init?.redirect, signal: init?.signal });
    const answer = respond(url);
    if (answer instanceof Error) {
      throw answer;
    }
    return await answer;
  }) as typeof fetch;
  return { fetchImpl, calls };
}

/** The mock arXiv every happy-path test runs against. */
async function arxivMock(
  options: { version?: string; latest?: string } = {},
): Promise<MockFetch> {
  const archive = await sourceArchive();
  return mockFetch((url) => {
    if (url.startsWith(ARXIV_API_URL)) {
      const id = new URL(url).searchParams.get("id_list") ?? "";
      return new Response(atomFeed(id, options.latest ?? "v3"), {
        headers: { "content-type": "application/atom+xml" },
      });
    }
    if (url.startsWith(ARXIV_SOURCE_URL_BASE)) {
      return new Response(bodyOf(archive), { headers: { "content-type": "application/gzip" } });
    }
    if (url.startsWith(ARXIV_PDF_URL_BASE)) {
      return new Response(PDF_BYTES, { headers: { "content-type": "application/pdf" } });
    }
    return new Response(null, { status: 404, statusText: "Not Found" });
  });
}

/** Every file under a directory, as relative POSIX path to digest. */
async function snapshot(root: string): Promise<Map<string, string>> {
  const found = new Map<string, string>();
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
        found.set(relative, sha256(await readFile(path.join(directory, child.name))));
      }
    }
  };
  await walk(root, "");
  return found;
}

async function exists(target: string): Promise<boolean> {
  try {
    await stat(target);
    return true;
  } catch {
    return false;
  }
}

/** What the staging area still holds. After any run, that is nothing. */
async function stagingEntries(root: string): Promise<string[]> {
  try {
    return (await readdir(path.join(root, ".staging"))).sort();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return [];
    }
    throw error;
  }
}

const rawDir = (root: string, method: string, citekey: string): string =>
  path.join(root, method, ".raw", citekey);
const figuresDir = (root: string, method: string, citekey: string): string =>
  path.join(root, method, ".figures", citekey);

async function readManifest(directory: string): Promise<LiteratureManifest> {
  return JSON.parse(await readFile(path.join(directory, "manifest.json"), "utf8")) as
    LiteratureManifest;
}

test("the public literature interface exposes the fetch commands", () => {
  assert.deepEqual(Object.keys(literature).sort(), [
    "LiteratureFetchError",
    "fetchLiteratureEntry",
    "loadBibliography",
    "syncLiterature",
    "writeMethodIndexes",
  ]);
});

test("requests carry a descriptive user agent, follow redirects, and can be aborted", async (t) => {
  const root = await literatureRoot(t);
  const { fetchImpl, calls } = await arxivMock();

  await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "alpha_2016_source",
    fetchImpl,
  });

  const { version } = JSON.parse(
    await readFile(path.join(REPO_ROOT, "package.json"), "utf8"),
  ) as { version: string };
  assert.equal(await arxivUserAgent(), `research-loop/${version} (literature source fetcher)`);

  assert.ok(calls.length > 0);
  for (const call of calls) {
    assert.equal(call.headers["user-agent"], `research-loop/${version} (literature source fetcher)`);
    assert.equal(call.redirect, "follow");
    assert.ok(call.signal instanceof AbortSignal, `${call.url} was sent without a signal`);
  }
});

test("a request is abandoned after sixty seconds", () => {
  assert.equal(REQUEST_TIMEOUT_MS, 60_000);
});

test("an explicit eprint version is fetched verbatim, without asking the API", async (t) => {
  const root = await literatureRoot(t);
  const { fetchImpl, calls } = await arxivMock();
  const archive = await sourceArchive();

  const manifest = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "alpha_2016_source",
    fetchImpl,
  });

  assert.deepEqual(
    calls.map((call) => call.url),
    [SOURCE_URL, PDF_URL],
  );
  assert.equal(manifest.schemaVersion, 1);
  assert.equal(manifest.citekey, "alpha_2016_source");
  assert.deepEqual(manifest.arxiv, { id: "1610.03042", version: "v2" });
  assert.deepEqual(manifest.source, {
    url: SOURCE_URL,
    bytes: archive.length,
    sha256: sha256(archive),
  });
  assert.deepEqual(manifest.pdf, {
    url: PDF_URL,
    bytes: PDF_BYTES.length,
    sha256: sha256(PDF_BYTES),
  });
  assert.equal(manifest.extraction.format, "tar-gzip");
  assert.equal(manifest.extraction.mainTex, "main.tex");
  assert.equal(manifest.extraction.files.length, 16);
  assert.equal(manifest.extraction.figures.length, 8);
});

test("both method directories of one reference hold the same verified bytes", async (t) => {
  const root = await literatureRoot(t);
  const { fetchImpl } = await arxivMock();

  const manifest = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "alpha_2016_source",
    fetchImpl,
  });

  const ed = await snapshot(rawDir(root, "ed", "alpha_2016_source"));
  const software = await snapshot(rawDir(root, "software", "alpha_2016_source"));
  assert.deepEqual([...ed].sort(), [...software].sort());
  assert.ok(ed.size > 0);

  assert.deepEqual(
    [...(await snapshot(figuresDir(root, "ed", "alpha_2016_source")))].sort(),
    [...(await snapshot(figuresDir(root, "software", "alpha_2016_source")))].sort(),
  );

  // The staged layout survives the swap intact.
  const staged = await snapshot(rawDir(root, "ed", "alpha_2016_source"));
  assert.ok(staged.has("manifest.json"));
  assert.ok(staged.has("source.tar.gz"));
  assert.ok(staged.has("paper.pdf"));
  assert.ok(staged.has("source/main.tex"));
  assert.equal(
    staged.get("source.tar.gz"),
    manifest.source.sha256,
    "the stored archive is the response that was verified",
  );
  assert.equal(staged.get("paper.pdf"), manifest.pdf.sha256);

  assert.deepEqual(
    [...(await snapshot(figuresDir(root, "ed", "alpha_2016_source")))].map(([file]) => file).sort(),
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
});

test("the written manifest is deterministic and carries no timestamp", async (t) => {
  const first = await literatureRoot(t);
  const second = await literatureRoot(t);
  const mockOne = await arxivMock();
  const mockTwo = await arxivMock();

  await fetchLiteratureEntry({
    literatureRoot: first,
    citekey: "alpha_2016_source",
    fetchImpl: mockOne.fetchImpl,
  });
  await fetchLiteratureEntry({
    literatureRoot: second,
    citekey: "alpha_2016_source",
    fetchImpl: mockTwo.fetchImpl,
  });

  const firstBytes = await readFile(
    path.join(rawDir(first, "ed", "alpha_2016_source"), "manifest.json"),
    "utf8",
  );
  const secondBytes = await readFile(
    path.join(rawDir(second, "ed", "alpha_2016_source"), "manifest.json"),
    "utf8",
  );
  assert.equal(firstBytes, secondBytes);
  assert.equal(
    firstBytes,
    await readFile(
      path.join(rawDir(first, "software", "alpha_2016_source"), "manifest.json"),
      "utf8",
    ),
  );
  assert.doesNotMatch(firstBytes, /date|time|fetched|updated/i);
  assert.equal(firstBytes.endsWith("\n"), true);
  assert.equal(
    firstBytes,
    `${JSON.stringify(JSON.parse(firstBytes), null, 2)}\n`,
    "the manifest is written as canonical two-space JSON",
  );
});

test("an eprint with no version is pinned to the version the API reports", async (t) => {
  const root = await literatureRoot(t);
  const { fetchImpl, calls } = await arxivMock({ latest: "v4" });

  const manifest = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "beta_2018_latest",
    fetchImpl,
  });

  assert.deepEqual(manifest.arxiv, { id: "1801.00001", version: "v4" });
  assert.equal(calls[0].url.startsWith(`${ARXIV_API_URL}?`), true, calls[0].url);
  assert.match(calls[0].url, /id_list=1801\.00001/);
  assert.deepEqual(calls.slice(1).map((call) => call.url), [
    `${ARXIV_SOURCE_URL_BASE}1801.00001v4`,
    `${ARXIV_PDF_URL_BASE}1801.00001v4`,
  ]);
});

test("an existing pin is reused without asking the network anything", async (t) => {
  const root = await literatureRoot(t);
  const first = await arxivMock({ latest: "v4" });
  const fetched = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "beta_2018_latest",
    fetchImpl: first.fetchImpl,
  });
  const before = await snapshot(rawDir(root, "ed", "beta_2018_latest"));

  const refuse = mockFetch(() => new Error("the network was used for a pinned entry"));
  const reused = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "beta_2018_latest",
    fetchImpl: refuse.fetchImpl,
  });

  assert.deepEqual(refuse.calls, []);
  assert.deepEqual(reused, fetched);
  assert.deepEqual(await snapshot(rawDir(root, "ed", "beta_2018_latest")), before);
});

test("a cached source tree file with the wrong bytes is refetched and repaired", async (t) => {
  const root = await literatureRoot(t);
  const first = await arxivMock();
  const manifest = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "alpha_2016_source",
    fetchImpl: first.fetchImpl,
  });
  const sourceFile = manifest.extraction.files.find((file) => file.path === "main.tex");
  assert.ok(sourceFile, "the fixture manifest did not record main.tex");
  const sourcePath = path.join(
    rawDir(root, "ed", "alpha_2016_source"),
    "source",
    sourceFile.path,
  );
  await writeFile(sourcePath, "% tampered cache\n", "utf8");

  const second = await arxivMock();
  const repaired = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "alpha_2016_source",
    fetchImpl: second.fetchImpl,
  });

  const restored = await readFile(sourcePath);
  assert.deepEqual(second.calls.map((call) => call.url), [SOURCE_URL, PDF_URL]);
  assert.deepEqual(repaired, manifest);
  assert.equal(restored.length, sourceFile.bytes);
  assert.equal(sha256(restored), sourceFile.sha256);
});

test("a cached figure with the wrong bytes is refetched and repaired", async (t) => {
  const root = await literatureRoot(t);
  const first = await arxivMock();
  const manifest = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "alpha_2016_source",
    fetchImpl: first.fetchImpl,
  });
  const figure = manifest.extraction.figures.find(
    (candidate) => candidate.destination === "figures/sketch.svg",
  );
  assert.ok(figure, "the fixture manifest did not record figures/sketch.svg");
  const figurePath = path.join(
    figuresDir(root, "ed", "alpha_2016_source"),
    figure.destination,
  );
  await writeFile(figurePath, "<svg>tampered</svg>\n", "utf8");

  const second = await arxivMock();
  const repaired = await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "alpha_2016_source",
    fetchImpl: second.fetchImpl,
  });

  assert.deepEqual(second.calls.map((call) => call.url), [SOURCE_URL, PDF_URL]);
  assert.deepEqual(repaired, manifest);
  assert.equal(sha256(await readFile(figurePath)), figure.sha256);
});

test("a pin is never silently replaced when the bibliography moves on", async (t) => {
  const root = await literatureRoot(t);
  const first = await arxivMock({ latest: "v4" });
  await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "beta_2018_latest",
    fetchImpl: first.fetchImpl,
  });
  const before = await snapshot(rawDir(root, "ed", "beta_2018_latest"));

  await writeFile(
    path.join(root, "ref.bib"),
    BIBLIOGRAPHY.replace("eprint = {1801.00001}", "eprint = {1801.00001v9}"),
    "utf8",
  );
  const second = await arxivMock();

  await assert.rejects(
    fetchLiteratureEntry({
      literatureRoot: root,
      citekey: "beta_2018_latest",
      fetchImpl: second.fetchImpl,
    }),
    (error: unknown) => {
      assert.ok(error instanceof LiteratureFetchError);
      assert.equal(error.code, "pinned-version-changed");
      assert.match(error.message, /v4/);
      assert.match(error.message, /v9/);
      return true;
    },
  );
  assert.deepEqual(second.calls, []);
  assert.deepEqual(await snapshot(rawDir(root, "ed", "beta_2018_latest")), before);
});

const FAILURES: readonly {
  name: string;
  respond: (url: string, archive: Buffer) => Response | Error;
  code: string;
  cause: { kind: "arxiv" | "archive"; code: string } | undefined;
}[] = [
  {
    name: "the source download answers with an error status",
    respond: (url) =>
      url.startsWith(ARXIV_SOURCE_URL_BASE)
        ? new Response(null, { status: 503, statusText: "Service Unavailable" })
        : new Response(PDF_BYTES),
    code: "download-failed",
    cause: { kind: "arxiv", code: "http" },
  },
  {
    name: "the PDF download answers with an error status",
    respond: (url, archive) =>
      url.startsWith(ARXIV_PDF_URL_BASE)
        ? new Response(null, { status: 404, statusText: "Not Found" })
        : new Response(bodyOf(archive)),
    code: "download-failed",
    cause: { kind: "arxiv", code: "http" },
  },
  {
    name: "the source download times out",
    respond: (url) =>
      url.startsWith(ARXIV_SOURCE_URL_BASE)
        ? new DOMException("This operation was aborted", "AbortError")
        : new Response(PDF_BYTES),
    code: "download-failed",
    cause: { kind: "arxiv", code: "timeout" },
  },
  {
    name: "the source is larger than the compressed ceiling",
    respond: (url, archive) =>
      url.startsWith(ARXIV_SOURCE_URL_BASE)
        ? new Response(bodyOf(archive), {
            headers: { "content-length": String(ARCHIVE_LIMITS.compressedBytes + 1) },
          })
        : new Response(PDF_BYTES),
    code: "download-failed",
    cause: { kind: "arxiv", code: "too-large" },
  },
  {
    name: "the source is not an archive at all",
    respond: (url) =>
      url.startsWith(ARXIV_SOURCE_URL_BASE)
        ? new Response(Buffer.from("<html>rate limited</html>", "utf8"))
        : new Response(PDF_BYTES),
    code: "unusable-source",
    cause: { kind: "archive", code: "unknown-format" },
  },
  {
    name: "the PDF is not a PDF at all",
    respond: (url, archive) =>
      url.startsWith(ARXIV_PDF_URL_BASE)
        ? new Response(Buffer.from("<html>try later</html>", "utf8"))
        : new Response(bodyOf(archive)),
    code: "unusable-pdf",
    cause: undefined,
  },
];

for (const failure of FAILURES) {
  test(`${failure.name}: nothing on disk changes`, async (t) => {
    const root = await literatureRoot(t);
    const good = await arxivMock();
    await fetchLiteratureEntry({
      literatureRoot: root,
      citekey: "alpha_2016_source",
      fetchImpl: good.fetchImpl,
    });
    const before = {
      ed: await snapshot(rawDir(root, "ed", "alpha_2016_source")),
      edFigures: await snapshot(figuresDir(root, "ed", "alpha_2016_source")),
      software: await snapshot(rawDir(root, "software", "alpha_2016_source")),
    };

    // Force a re-fetch of the same pin by removing one manifest.
    await rm(path.join(rawDir(root, "ed", "alpha_2016_source"), "manifest.json"));

    const archive = await sourceArchive();
    const broken = mockFetch((url) => failure.respond(url, archive));
    await assert.rejects(
      fetchLiteratureEntry({
        literatureRoot: root,
        citekey: "alpha_2016_source",
        fetchImpl: broken.fetchImpl,
      }),
      (error: unknown) => {
        assert.ok(error instanceof LiteratureFetchError, String(error));
        assert.equal(error.code, failure.code);
        if (failure.cause?.kind === "arxiv") {
          assert.ok(error.cause instanceof ArxivError, String(error.cause));
          assert.equal(error.cause.code, failure.cause.code);
        } else if (failure.cause?.kind === "archive") {
          assert.ok(error.cause instanceof ArchiveError, String(error.cause));
          assert.equal(error.cause.code, failure.cause.code);
        }
        return true;
      },
    );

    const after = {
      ed: await snapshot(rawDir(root, "ed", "alpha_2016_source")),
      edFigures: await snapshot(figuresDir(root, "ed", "alpha_2016_source")),
      software: await snapshot(rawDir(root, "software", "alpha_2016_source")),
    };
    before.ed.delete("manifest.json");
    assert.deepEqual(after.ed, before.ed);
    assert.deepEqual(after.edFigures, before.edFigures);
    assert.deepEqual(after.software, before.software);
    assert.deepEqual(await stagingEntries(root), [], "staging was left behind");
  });
}

test("a swap that fails halfway puts every method directory back", async (t) => {
  const root = await literatureRoot(t);
  const first = await arxivMock();
  await fetchLiteratureEntry({
    literatureRoot: root,
    citekey: "alpha_2016_source",
    fetchImpl: first.fetchImpl,
  });
  const before = {
    raw: await snapshot(rawDir(root, "ed", "alpha_2016_source")),
    figures: await snapshot(figuresDir(root, "ed", "alpha_2016_source")),
  };

  // `literature/software/.raw` becomes a file, so the third of the four moves
  // cannot even create its parent — after the first two have already happened.
  await rm(path.join(root, "software", ".raw"), { recursive: true, force: true });
  await writeFile(path.join(root, "software", ".raw"), "not a directory\n", "utf8");

  // A *different* archive, so restored content can be told from new content.
  const replacement = gzipSync(
    await readFile(path.join(ARCHIVE_FIXTURE_DIR, "benign-space-padded.tar")),
  );
  const second = mockFetch((url) =>
    url.startsWith(ARXIV_SOURCE_URL_BASE)
      ? new Response(bodyOf(replacement))
      : new Response(PDF_BYTES),
  );
  await assert.rejects(
    fetchLiteratureEntry({
      literatureRoot: root,
      citekey: "alpha_2016_source",
      fetchImpl: second.fetchImpl,
    }),
    (error: unknown) =>
      error instanceof LiteratureFetchError && error.code === "swap-failed",
  );

  assert.deepEqual(await snapshot(rawDir(root, "ed", "alpha_2016_source")), before.raw);
  assert.deepEqual(
    await snapshot(figuresDir(root, "ed", "alpha_2016_source")),
    before.figures,
  );
  assert.deepEqual(
    await readdir(path.join(root, "ed", ".raw")),
    ["alpha_2016_source"],
    "a backup directory was left behind",
  );
  assert.deepEqual(await stagingEntries(root), []);
});

test("an archive whose members are unsafe is refused, leaving nothing behind", async (t) => {
  const root = await literatureRoot(t);
  const evil = gzipSync(await readFile(path.join(ARCHIVE_FIXTURE_DIR, "evil-late-symlink.tar")));
  const broken = mockFetch((url) =>
    url.startsWith(ARXIV_SOURCE_URL_BASE) ? new Response(bodyOf(evil)) : new Response(PDF_BYTES),
  );

  await assert.rejects(
    fetchLiteratureEntry({
      literatureRoot: root,
      citekey: "alpha_2016_source",
      fetchImpl: broken.fetchImpl,
    }),
    (error: unknown) => {
      assert.ok(error instanceof LiteratureFetchError);
      assert.equal(error.code, "unusable-source");
      assert.ok(error.cause instanceof ArchiveError);
      assert.equal(error.cause.code, "unsupported-entry-type");
      return true;
    },
  );

  assert.equal(await exists(rawDir(root, "ed", "alpha_2016_source")), false);
  assert.deepEqual(await stagingEntries(root), []);
});

test("an archive with no main document is refused", async (t) => {
  const root = await literatureRoot(t);
  const noMain = gzipSync(await readFile(path.join(ARCHIVE_FIXTURE_DIR, "reject-no-main.tar")));
  const broken = mockFetch((url) =>
    url.startsWith(ARXIV_SOURCE_URL_BASE) ? new Response(bodyOf(noMain)) : new Response(PDF_BYTES),
  );

  await assert.rejects(
    fetchLiteratureEntry({
      literatureRoot: root,
      citekey: "alpha_2016_source",
      fetchImpl: broken.fetchImpl,
    }),
    (error: unknown) =>
      error instanceof LiteratureFetchError &&
      error.code === "unusable-source" &&
      error.cause instanceof ArchiveError &&
      error.cause.code === "no-main-tex",
  );
  assert.deepEqual(await stagingEntries(root), []);
});

test("a reference with no preprint is refused, not invented", async (t) => {
  const root = await literatureRoot(t);
  const { fetchImpl, calls } = await arxivMock();

  await assert.rejects(
    fetchLiteratureEntry({
      literatureRoot: root,
      citekey: "gamma_2019_local",
      fetchImpl,
    }),
    (error: unknown) =>
      error instanceof LiteratureFetchError && error.code === "no-arxiv",
  );
  assert.deepEqual(calls, []);
  assert.equal(await exists(rawDir(root, "dmft", "gamma_2019_local")), false);
});

test("a citekey the bibliography does not define is its own kind of failure", async (t) => {
  const root = await literatureRoot(t);
  const { fetchImpl } = await arxivMock();

  await assert.rejects(
    fetchLiteratureEntry({ literatureRoot: root, citekey: "not_a_reference", fetchImpl }),
    (error: unknown) =>
      error instanceof LiteratureFetchError && error.code === "unknown-citekey",
  );
});

test("sync walks the bibliography in citekey order and counts what it did", async (t) => {
  const root = await literatureRoot(t);
  const first = await arxivMock({ latest: "v4" });

  const initial = await syncLiterature({ literatureRoot: root, fetchImpl: first.fetchImpl });
  assert.deepEqual(initial, { fetched: 2, reused: 0, skippedNoArxiv: 1 });

  assert.deepEqual(
    first.calls.map((call) => call.url),
    [
      SOURCE_URL,
      PDF_URL,
      `${ARXIV_API_URL}?id_list=1801.00001&max_results=1`,
      `${ARXIV_SOURCE_URL_BASE}1801.00001v4`,
      `${ARXIV_PDF_URL_BASE}1801.00001v4`,
    ],
  );

  const second = await arxivMock({ latest: "v4" });
  const again = await syncLiterature({ literatureRoot: root, fetchImpl: second.fetchImpl });
  assert.deepEqual(again, { fetched: 0, reused: 2, skippedNoArxiv: 1 });
  assert.deepEqual(second.calls, []);
});

test("the manifest of every method directory is byte-identical after a sync", async (t) => {
  const root = await literatureRoot(t);
  const { fetchImpl } = await arxivMock({ latest: "v4" });
  await syncLiterature({ literatureRoot: root, fetchImpl });

  const ed = await readManifest(rawDir(root, "ed", "alpha_2016_source"));
  const software = await readManifest(rawDir(root, "software", "alpha_2016_source"));
  assert.deepEqual(ed, software);
  assert.equal(ed.arxiv.version, "v2");
});

// --- the HTTP layer on its own ---------------------------------------------

test("a download is bounded by what actually arrives, not by what is declared", async () => {
  const { fetchImpl } = mockFetch(
    () =>
      new Response(Buffer.alloc(4096, 0x41), {
        // A body ten times the declared length: the bound is on the bytes.
        headers: { "content-length": "10" },
      }),
  );

  await assert.rejects(
    downloadBounded({ url: "https://example.invalid/x", maxBytes: 1024, fetchImpl }),
    (error: unknown) => error instanceof ArxivError && error.code === "too-large",
  );
});

test("a declared length over the ceiling is refused without waiting for the body", async () => {
  // A body that never produces a byte: only an implementation that refuses on
  // the declared length alone can answer at all.
  const { fetchImpl } = mockFetch(
    () =>
      new Response(
        new ReadableStream<Uint8Array>({
          pull: async () => await new Promise<void>(() => undefined),
        }),
        { headers: { "content-length": "4096" } },
      ),
  );

  await assert.rejects(
    downloadBounded({ url: "https://example.invalid/x", maxBytes: 1024, fetchImpl, timeoutMs: 30_000 }),
    (error: unknown) => error instanceof ArxivError && error.code === "too-large",
  );
});

test("a request that never answers is abandoned, and says so", async () => {
  let sawAbort = false;
  const hanging = (async (_input: RequestInfo | URL, init?: RequestInit) =>
    await new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        sawAbort = true;
        reject(new DOMException("This operation was aborted", "AbortError"));
      });
    })) as typeof fetch;

  const started = Date.now();
  await assert.rejects(
    downloadBounded({
      url: "https://example.invalid/x",
      maxBytes: 1024,
      fetchImpl: hanging,
      timeoutMs: 25,
    }),
    (error: unknown) => error instanceof ArxivError && error.code === "timeout",
  );
  assert.ok(sawAbort, "the request was never given an abort signal that fired");
  assert.ok(Date.now() - started < 5_000, "the request was not abandoned promptly");
});

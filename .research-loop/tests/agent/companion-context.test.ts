import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { fileURLToPath } from "node:url";

import {
  CompanionIdError,
  decodeCompanionId,
  encodeKnowledgeId,
  encodeLiteratureId,
  encodeProblemId,
} from "../../../src/lib/companion/ids.js";
import {
  CompanionInputError,
  CompanionIntegrityError,
  CompanionNotFoundError,
  createCompanionContext,
} from "../../../src/lib/companion/context.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..", "..");
const KNOWLEDGE_FIXTURE = path.join(
  REPO_ROOT,
  ".research-loop",
  "tests",
  "fixtures",
  "knowledge",
);

const PUBLIC_BASE_URL = "https://notes.example.test/";

async function makeRepo(t: TestContext): Promise<string> {
  const root = await mkdtemp(path.join(await realpath(tmpdir()), "companion-context-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await cp(path.join(KNOWLEDGE_FIXTURE, "valid"), path.join(root, "knowledge"), {
    recursive: true,
  });
  await mkdir(path.join(root, "literature"), { recursive: true });
  await cp(
    path.join(KNOWLEDGE_FIXTURE, "ref.bib"),
    path.join(root, "literature", "ref.bib"),
  );
  await mkdir(path.join(root, "drafts"), { recursive: true });
  await writeFile(
    path.join(root, "drafts", "private.qmd"),
    "Asterism-only private draft conclusion.",
  );
  await writeProblem(root, "Prob-001", { title: "Visible Ising question" });
  await writeProblem(root, "Prob-002", {
    title: "Rejected secret question",
    status: "rejected",
    rejection: { kind: "human", reason: "Not supported." },
  });
  await writeProblem(root, "Prob-003", {
    title: "Archived secret question",
    status: "archived",
  });
  return root;
}

async function writeProblem(
  root: string,
  id: string,
  overrides: Record<string, unknown> = {},
): Promise<void> {
  const directory = path.join(root, "problems", id);
  await mkdir(directory, { recursive: true });
  const manifest = {
    schemaVersion: 1,
    id,
    title: `${id} title`,
    summary: `${id} summary`,
    status: "draft",
    gate: { type: "human-review", readiness: "specified" },
    provenance: { sourceCount: 2 },
    lastActivity: { summary: "Created", at: "2026-08-01T00:00:00.000Z" },
    createdAt: "2026-08-01T00:00:00.000Z",
    updatedAt: "2026-08-01T00:00:00.000Z",
    ...overrides,
  };
  await writeFile(path.join(directory, "problem.json"), JSON.stringify(manifest));
  await writeFile(path.join(directory, "problem.md"), "# Private problem body\n");
}

function qmd(frontmatter: Record<string, string>, body: readonly string[]): string {
  return [
    "---",
    ...Object.entries(frontmatter).map(([key, value]) => `${key}: ${value}`),
    "---",
    "",
    ...body,
    "",
  ].join("\n");
}

function readingMap(targets: readonly string[]): string[] {
  return [
    "Reviewed context.",
    "",
    "## Reading map",
    "",
    ...targets.map((target) => `- [Entry](${target})`),
  ];
}

async function makeAmbiguousRepo(t: TestContext): Promise<string> {
  const root = await mkdtemp(path.join(await realpath(tmpdir()), "companion-ambiguous-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const pages: Record<string, string> = {
    "index.qmd": qmd(
      { title: "Root", description: "Root index." },
      readingMap(["beta/index.qmd", "alpha/index.qmd"]),
    ),
    "beta/index.qmd": qmd(
      { title: "Beta", description: "Beta topic." },
      readingMap(["note.qmd"]),
    ),
    "beta/note.qmd": qmd(
      {
        title: "Shared theorem",
        description: "Beta result.",
        categories: "[theory]",
      },
      ["Beta exact content."],
    ),
    "alpha/index.qmd": qmd(
      { title: "Alpha", description: "Alpha topic." },
      readingMap(["note.qmd"]),
    ),
    "alpha/note.qmd": qmd(
      {
        title: "Shared theorem",
        description: "Alpha result.",
        categories: "[experiment]",
      },
      ["Alpha exact content."],
    ),
  };
  for (const [relativePath, source] of Object.entries(pages)) {
    const target = path.join(root, "knowledge", ...relativePath.split("/"));
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, source);
  }
  await mkdir(path.join(root, "literature"), { recursive: true });
  await writeFile(path.join(root, "literature", "ref.bib"), "");
  return root;
}

function fixedDependencies(revision: () => string = () => "fixture-revision") {
  return {
    getRepositoryRevision: async () => revision(),
  };
}

async function treeHash(root: string): Promise<string> {
  const hash = createHash("sha256");
  const walk = async (directory: string): Promise<void> => {
    const entries = await readdir(directory, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name));
    for (const entry of entries) {
      if (entry.name === ".git") continue;
      const absolute = path.join(directory, entry.name);
      const relative = path.relative(root, absolute).split(path.sep).join("/");
      hash.update(`${entry.isDirectory() ? "d" : "f"}:${relative}\0`);
      if (entry.isDirectory()) await walk(absolute);
      else hash.update(await readFile(absolute));
    }
  };
  await walk(root);
  return hash.digest("hex");
}

test("knowledge IDs expose only a versioned query and selection digest", () => {
  const id = encodeKnowledgeId({
    query: "Ising model",
    selectionDigest: "a".repeat(64),
  });
  assert.match(id, /^knowledge:[A-Za-z0-9_-]+$/);
  const encoded = id.slice("knowledge:".length);
  const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
  assert.deepEqual(payload, {
    version: 1,
    namespace: "knowledge",
    query: "Ising model",
    selectionDigest: "a".repeat(64),
  });
  assert.deepEqual(decodeCompanionId(id), payload);
  assert.equal(JSON.stringify(payload).includes("selectedPage"), false);
  assert.equal(JSON.stringify(payload).includes("knowledge/"), false);
});

test("IDs reject malformed, path-shaped, unknown, stale-version, and oversized inputs", () => {
  assert.deepEqual(decodeCompanionId(encodeProblemId("Prob-001")), {
    version: 1,
    namespace: "problem",
    problemId: "Prob-001",
  });
  assert.deepEqual(decodeCompanionId(encodeLiteratureId("fixture2026")), {
    version: 1,
    namespace: "literature",
    citekey: "fixture2026",
  });

  const invalid = [
    "unknown:value",
    "knowledge:not+base64",
    `knowledge:${Buffer.from("not json").toString("base64url")}`,
    `knowledge:${Buffer.from(JSON.stringify({ version: 2, namespace: "knowledge", query: "x", selectionDigest: "a".repeat(64) })).toString("base64url")}`,
    `knowledge:${Buffer.from(JSON.stringify({ version: 1, namespace: "knowledge", query: "x", selectionDigest: "a".repeat(64), selectedPage: "knowledge/x.qmd" })).toString("base64url")}`,
    "problem:../Prob-001",
    "problem:Prob-1",
    "literature:../secret",
    "literature:.hidden",
    `knowledge:${"a".repeat(5_000)}`,
  ];
  for (const id of invalid) {
    assert.throws(() => decodeCompanionId(id), CompanionIdError, id);
  }
});

test("creation validates repository, bibliography, limits, and credential-free public base", async (t) => {
  const root = await makeRepo(t);
  await assert.rejects(
    createCompanionContext({
      repoRoot: "relative/repository",
      publicBaseUrl: PUBLIC_BASE_URL,
    }),
    CompanionInputError,
  );
  await assert.rejects(
    createCompanionContext({
      repoRoot: root,
      bibliographyPath: path.join(root, "..", "outside.bib"),
      publicBaseUrl: PUBLIC_BASE_URL,
    }),
    /bibliography/i,
  );
  for (const publicBaseUrl of [
    "http://notes.example.test/",
    "https://user@notes.example.test/",
    "https://notes.example.test/?token=secret",
    "https://notes.example.test/#fragment",
    "https://notes.example.test/mcp/capability-token",
  ]) {
    await assert.rejects(
      createCompanionContext({ repoRoot: root, publicBaseUrl }),
      CompanionInputError,
      publicBaseUrl,
    );
  }
  await assert.rejects(
    createCompanionContext({
      repoRoot: root,
      publicBaseUrl: "https://notes.example.test/secret-value/",
      accessToken: "secret-value",
    }),
    CompanionInputError,
  );
  await assert.rejects(
    createCompanionContext({
      repoRoot: root,
      publicBaseUrl: PUBLIC_BASE_URL,
      maxResults: 0,
    }),
    CompanionInputError,
  );
});

test("knowledge fetch reruns resolution and returns every ordered file with live hashes", async (t) => {
  const root = await makeRepo(t);
  let revision = "revision-one";
  const context = await createCompanionContext({
    repoRoot: root,
    publicBaseUrl: PUBLIC_BASE_URL,
    dependencies: fixedDependencies(() => revision),
  });

  const result = (await context.search("Ising model")).find(
    (candidate) => candidate.namespace === "knowledge",
  );
  assert.ok(result);
  const first = await context.fetch(result.id);
  assert.equal(first.namespace, "knowledge");
  assert.equal(first.authority, "reviewed_knowledge");
  assert.deepEqual(
    first.files?.map((file) => file.path),
    [
      "knowledge/index.qmd",
      "knowledge/ising/index.qmd",
      "knowledge/ising/proof.qmd",
      "knowledge/ising/proposal.qmd",
      "knowledge/ising/verified-code.qmd",
    ],
  );
  assert.ok(first.files?.every((file) => /^[a-f0-9]{64}$/.test(file.sha256)));
  assert.equal(first.provenance?.repositoryRevision, "revision-one");
  assert.ok(first.text.indexOf("Research Loop Knowledge") < first.text.indexOf("Ising model"));
  assert.ok(first.text.indexOf("Ising model") < first.text.indexOf("Proof of the critical temperature"));

  const proof = path.join(root, "knowledge", "ising", "proof.qmd");
  await writeFile(proof, `${await readFile(proof, "utf8")}\nLive edit marker.\n`);
  revision = "revision-two";
  const second = await context.fetch(result.id);
  assert.equal(second.provenance?.repositoryRevision, "revision-two");
  assert.notEqual(second.files?.[2]?.sha256, first.files?.[2]?.sha256);
  assert.match(second.files?.[2]?.content ?? "", /Live edit marker/);
});

test("ambiguous knowledge stays separate and fetch fails closed for stale selections", async (t) => {
  const root = await makeAmbiguousRepo(t);
  const context = await createCompanionContext({
    repoRoot: root,
    publicBaseUrl: PUBLIC_BASE_URL,
    dependencies: fixedDependencies(),
  });
  const results = (await context.search("Shared theorem")).filter(
    (candidate) => candidate.namespace === "knowledge",
  );
  assert.equal(results.length, 2);
  assert.notEqual(results[0]?.id, results[1]?.id);
  const alpha = results.find((candidate) => candidate.title.includes("Alpha"));
  assert.ok(alpha);
  const fetched = await context.fetch(alpha.id);
  assert.deepEqual(
    fetched.files?.map((file) => file.path),
    ["knowledge/index.qmd", "knowledge/alpha/index.qmd", "knowledge/alpha/note.qmd"],
  );

  const alphaNote = path.join(root, "knowledge", "alpha", "note.qmd");
  await writeFile(
    alphaNote,
    qmd(
      {
        title: "Renamed theorem",
        description: "Alpha result.",
        categories: "[experiment]",
      },
      ["Alpha exact content."],
    ),
  );
  await assert.rejects(context.fetch(alpha.id), CompanionNotFoundError);
});

test("digest collisions are rejected before ambiguous IDs can be issued", async (t) => {
  const root = await makeAmbiguousRepo(t);
  const context = await createCompanionContext({
    repoRoot: root,
    publicBaseUrl: PUBLIC_BASE_URL,
    dependencies: {
      ...fixedDependencies(),
      sha256: async () => "f".repeat(64),
    },
  });
  await assert.rejects(context.search("Shared theorem"), CompanionIntegrityError);
});

test("draft-only text is never searched or fetched", async (t) => {
  const root = await makeRepo(t);
  const context = await createCompanionContext({
    repoRoot: root,
    publicBaseUrl: PUBLIC_BASE_URL,
    dependencies: fixedDependencies(),
  });
  assert.deepEqual(await context.search("Asterism-only"), []);
  await assert.rejects(context.fetch("draft:private.qmd"), CompanionIdError);
});

test("problem search and fetch share hidden-state denial and return clone-safe public fields", async (t) => {
  const root = await makeRepo(t);
  const context = await createCompanionContext({
    repoRoot: root,
    publicBaseUrl: PUBLIC_BASE_URL,
    dependencies: fixedDependencies(),
  });
  const visible = (await context.search("question")).filter(
    (candidate) => candidate.namespace === "problem",
  );
  assert.deepEqual(visible.map((candidate) => candidate.id), ["problem:Prob-001"]);
  const document = await context.fetch("problem:Prob-001");
  assert.equal(document.authority, "open_problem");
  assert.deepEqual(document.metadata, {
    schemaVersion: 1,
    id: "Prob-001",
    title: "Visible Ising question",
    summary: "Prob-001 summary",
    status: "draft",
    gate: { type: "human-review", readiness: "specified" },
    provenance: { sourceCount: 2 },
    lastActivity: { summary: "Created", at: "2026-08-01T00:00:00.000Z" },
    createdAt: "2026-08-01T00:00:00.000Z",
    updatedAt: "2026-08-01T00:00:00.000Z",
  });
  const metadata = document.metadata as { title: string; gate: { type: string } };
  metadata.title = "mutated";
  metadata.gate.type = "mutated";
  assert.equal((await context.fetch("problem:Prob-001")).title, "Visible Ising question");

  for (const id of ["problem:Prob-002", "problem:Prob-003", "problem:Prob-999"]) {
    await assert.rejects(
      context.fetch(id),
      (error: unknown) =>
        error instanceof CompanionNotFoundError && error.message === "document not found",
    );
  }
});

test("literature exposes only validated external-evidence metadata", async (t) => {
  const root = await makeRepo(t);
  const context = await createCompanionContext({
    repoRoot: root,
    publicBaseUrl: PUBLIC_BASE_URL,
    dependencies: fixedDependencies(),
  });
  const result = (await context.search("Ada Fixture 2026 ed")).find(
    (candidate) => candidate.namespace === "literature",
  );
  assert.ok(result);
  assert.equal(result.authority, "external_evidence");
  const document = await context.fetch(result.id);
  assert.equal(document.authority, "external_evidence");
  assert.deepEqual(document.metadata, {
    citekey: "fixture2026",
    type: "article",
    title: "A fixture result for the two-dimensional Ising model",
    authors: ["Ada Fixture", "Bo Sample"],
    year: "2026",
    doi: "10.5555/fixture.2026",
    methods: ["ed"],
  });
  const serialized = JSON.stringify(document);
  for (const forbidden of [".raw", ".figures", "fullText", "abstract", "attachmentPath"]) {
    assert.equal(serialized.includes(forbidden), false, forbidden);
  }
});

test("query and result bounds fail before repository work", async (t) => {
  const root = await makeRepo(t);
  const context = await createCompanionContext({
    repoRoot: root,
    publicBaseUrl: PUBLIC_BASE_URL,
    maxResults: 1,
    dependencies: fixedDependencies(),
  });
  assert.equal((await context.search("Ising")).length, 1);
  await assert.rejects(context.search(" "), CompanionInputError);
  await assert.rejects(context.search("x".repeat(2_049)), CompanionInputError);
  await assert.rejects(context.fetch("x".repeat(5_000)), CompanionIdError);
});

test("search and fetch leave the repository tree unchanged", async (t) => {
  const root = await makeRepo(t);
  const context = await createCompanionContext({
    repoRoot: root,
    publicBaseUrl: PUBLIC_BASE_URL,
    dependencies: fixedDependencies(),
  });
  const before = await treeHash(root);
  const result = (await context.search("Ising model"))[0];
  assert.ok(result);
  await context.fetch(result.id);
  assert.equal(await treeHash(root), before);
});

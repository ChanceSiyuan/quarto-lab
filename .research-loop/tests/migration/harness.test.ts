import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmod,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";
import { promisify } from "node:util";

import {
  importHarnessKnowledge,
  verifyHarnessImport,
  verifyHarnessImportAgainstSource,
} from "../../../src/lib/migration/harness.js";

const run = promisify(execFile);

const DESTINATION = path.join("drafts", "imported-quantum-harness");
const MANIFEST_PATH = path.join(
  "docs",
  "migrations",
  "quantum-harness-knowledge.json",
);
const BIBLIOGRAPHY = "@article{fixture2026,\n  title = {Fixture Paper},\n}\n";

/**
 * The fixture mirrors the shape of the real harness subtree: root reference
 * cards, model cards, software cards, non-Markdown tooling, and a literature
 * subtree that contributes only its bibliography.
 */
const SOURCE_FILES: readonly (readonly [string, string])[] = [
  [".knowledge/README.md", "# Harness knowledge\n\nRoot reference card.\n"],
  [".knowledge/conventions.md", "line one\r\nline two\r\n"],
  [
    ".knowledge/models/ising.md",
    "# Ising\n\nSee [api](../software/quspin/api.md).\n",
  ],
  [".knowledge/models/ref.bib", "@article{models2026,\n}\n"],
  [".knowledge/models/tests/test_models.py", "assert True\n"],
  [".knowledge/software/quspin/api.md", "# QuSpin API\n"],
  [".knowledge/solvable/benchmarks.json", "{}\n"],
  [".knowledge/literature/README.md", "# Literature\n"],
  [".knowledge/literature/ed/INDEX.md", "# Exact diagonalization\n"],
  [".knowledge/literature/ed/paper.md", "# Rendered paper\n"],
  [".knowledge/literature/ref.bib", BIBLIOGRAPHY],
];

const EXPECTED_CARDS: readonly (readonly [string, string])[] = SOURCE_FILES.flatMap(
  ([source, content]) =>
    source.endsWith(".md") && !source.startsWith(".knowledge/literature/")
      ? [[source.slice(".knowledge/".length), content] as const]
      : [],
);

const EXPECTED_PATHS = EXPECTED_CARDS.map(([relative]) => relative).sort(
  comparePosix,
);

const EXPECTED_BYTES = EXPECTED_CARDS.reduce(
  (total, [, content]) => total + Buffer.byteLength(content),
  0,
);

function comparePosix(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function sha256(value: string | Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}

async function temporaryDirectory(
  t: TestContext,
  prefix: string,
): Promise<string> {
  const directory = await mkdtemp(path.join(tmpdir(), prefix));
  t.after(async () => {
    await chmod(path.join(directory, "drafts"), 0o700).catch(() => {});
    await rm(directory, { recursive: true, force: true });
  });
  return directory;
}

interface SourceRepository {
  root: string;
  knowledgeRoot: string;
  revision: string;
}

async function makeSourceRepository(t: TestContext): Promise<SourceRepository> {
  const root = await temporaryDirectory(t, "harness-source-");
  await run("git", ["-C", root, "init", "--quiet", "--initial-branch=main"]);
  await run("git", ["-C", root, "config", "user.email", "fixture@example.com"]);
  await run("git", ["-C", root, "config", "user.name", "Fixture"]);
  await run("git", ["-C", root, "config", "core.autocrlf", "false"]);

  for (const [relative, content] of SOURCE_FILES) {
    const target = path.join(root, relative);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content);
  }

  await run("git", ["-C", root, "add", "--all"]);
  await run("git", ["-C", root, "commit", "--quiet", "-m", "fixture corpus"]);
  const { stdout } = await run("git", ["-C", root, "rev-parse", "HEAD"]);

  return {
    root,
    knowledgeRoot: path.join(root, ".knowledge"),
    revision: stdout.trim(),
  };
}

async function listRelativeFiles(root: string): Promise<string[]> {
  const found: string[] = [];

  async function walk(directory: string): Promise<void> {
    const entries = await readdir(directory, { withFileTypes: true });
    for (const entry of entries) {
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        await walk(absolute);
      } else {
        found.push(path.relative(root, absolute).split(path.sep).join("/"));
      }
    }
  }

  await walk(root);
  return found.sort(comparePosix);
}

async function exists(target: string): Promise<boolean> {
  try {
    await readFile(target);
    return true;
  } catch {
    return false;
  }
}

async function directoryExists(target: string): Promise<boolean> {
  try {
    return (await stat(target)).isDirectory();
  } catch {
    return false;
  }
}

/** Commits one more card, so a later import is observably different. */
async function commitAdditionalCard(source: SourceRepository): Promise<string> {
  await writeFile(
    path.join(source.knowledgeRoot, "models", "added.md"),
    "# Added later\n",
  );
  await run("git", ["-C", source.root, "add", "--all"]);
  await run("git", ["-C", source.root, "commit", "--quiet", "-m", "one more"]);
  const { stdout } = await run("git", ["-C", source.root, "rev-parse", "HEAD"]);
  return stdout.trim();
}

/**
 * Runs `action` while `directory` rejects writes, which is how an install step
 * is made to fail at a chosen target.
 */
async function withUnwritableDirectory(
  directory: string,
  action: () => Promise<void>,
): Promise<void> {
  await mkdir(directory, { recursive: true });
  await chmod(directory, 0o500);
  try {
    await action();
  } finally {
    await chmod(directory, 0o700);
  }
}

async function importFixture(
  t: TestContext,
): Promise<{ source: SourceRepository; repoRoot: string }> {
  const source = await makeSourceRepository(t);
  const repoRoot = await temporaryDirectory(t, "harness-target-");
  await importHarnessKnowledge({
    sourceKnowledgeRoot: source.knowledgeRoot,
    repoRoot,
    sourceRevision: source.revision,
  });
  return { source, repoRoot };
}

test("imports only non-literature Markdown cards", async (t) => {
  const { repoRoot } = await importFixture(t);

  assert.deepEqual(
    await listRelativeFiles(path.join(repoRoot, DESTINATION)),
    EXPECTED_PATHS,
  );
});

test("preserves relative paths, extensions, and raw bytes", async (t) => {
  const { repoRoot } = await importFixture(t);

  for (const [relative, content] of EXPECTED_CARDS) {
    const imported = await readFile(
      path.join(repoRoot, DESTINATION, relative),
    );
    assert.equal(
      imported.toString("utf8"),
      content,
      `content mismatch for ${relative}`,
    );
    assert.deepEqual(
      imported,
      Buffer.from(content),
      `raw bytes changed for ${relative}`,
    );
  }

  const withCrlf = await readFile(
    path.join(repoRoot, DESTINATION, "conventions.md"),
    "utf8",
  );
  assert.equal(withCrlf, "line one\r\nline two\r\n");
});

test("copies only the bibliography from the literature subtree", async (t) => {
  const { repoRoot } = await importFixture(t);

  assert.deepEqual(await listRelativeFiles(path.join(repoRoot, "literature")), [
    "ref.bib",
  ]);
  assert.equal(
    await readFile(path.join(repoRoot, "literature", "ref.bib"), "utf8"),
    BIBLIOGRAPHY,
  );
});

test("writes a sorted, source-independent manifest", async (t) => {
  const source = await makeSourceRepository(t);
  const repoRoot = await temporaryDirectory(t, "harness-target-");

  const manifest = await importHarnessKnowledge({
    sourceKnowledgeRoot: source.knowledgeRoot,
    repoRoot,
    sourceRevision: source.revision,
  });

  assert.equal(manifest.schemaVersion, 1);
  assert.equal(manifest.destination, "drafts/imported-quantum-harness");
  assert.deepEqual(manifest.source, {
    repository: "quantum.harness",
    subtree: ".knowledge",
    revision: source.revision,
  });
  assert.deepEqual(
    manifest.files.map((entry) => entry.path),
    EXPECTED_PATHS,
  );

  const byPath = new Map(manifest.files.map((entry) => [entry.path, entry]));
  for (const [relative, content] of EXPECTED_CARDS) {
    assert.deepEqual(byPath.get(relative), {
      path: relative,
      bytes: Buffer.byteLength(content),
      sha256: sha256(content),
    });
  }

  assert.deepEqual(manifest.bibliography, {
    path: "literature/ref.bib",
    bytes: Buffer.byteLength(BIBLIOGRAPHY),
    sha256: sha256(BIBLIOGRAPHY),
  });

  const persisted = await readFile(path.join(repoRoot, MANIFEST_PATH), "utf8");
  assert.deepEqual(JSON.parse(persisted), manifest);
  assert.ok(persisted.endsWith("\n"));
  assert.doesNotMatch(persisted, /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);
  assert.doesNotMatch(persisted, /timestamp|generatedAt|importedAt|"date"/i);
  assert.ok(
    !persisted.includes(tmpdir()),
    "manifest must not embed host-specific absolute paths",
  );
  assert.ok(!persisted.includes(repoRoot));
  assert.ok(!persisted.includes(source.root));
});

test("reads blobs from the requested revision, not the working tree", async (t) => {
  const source = await makeSourceRepository(t);
  const repoRoot = await temporaryDirectory(t, "harness-target-");

  await writeFile(
    path.join(source.knowledgeRoot, "models", "ising.md"),
    "TAMPERED WORKING TREE\n",
  );
  await run("git", [
    "-C",
    source.root,
    "add",
    ".knowledge/models/ising.md",
  ]);
  await writeFile(
    path.join(source.knowledgeRoot, "models", "untracked.md"),
    "untracked card\n",
  );
  await rm(path.join(source.knowledgeRoot, "README.md"));

  await importHarnessKnowledge({
    sourceKnowledgeRoot: source.knowledgeRoot,
    repoRoot,
    sourceRevision: source.revision,
  });

  assert.equal(
    await readFile(
      path.join(repoRoot, DESTINATION, "models", "ising.md"),
      "utf8",
    ),
    "# Ising\n\nSee [api](../software/quspin/api.md).\n",
  );
  assert.equal(
    await exists(path.join(repoRoot, DESTINATION, "models", "untracked.md")),
    false,
  );
  assert.equal(
    await exists(path.join(repoRoot, DESTINATION, "README.md")),
    true,
  );
});

test("rejects a revision that is not the source repository HEAD", async (t) => {
  const source = await makeSourceRepository(t);
  const repoRoot = await temporaryDirectory(t, "harness-target-");

  await assert.rejects(
    importHarnessKnowledge({
      sourceKnowledgeRoot: source.knowledgeRoot,
      repoRoot,
      sourceRevision: "0".repeat(40),
    }),
    /revision/i,
  );
  assert.equal(await exists(path.join(repoRoot, MANIFEST_PATH)), false);
});

test("stages before install and leaves no partial destination on failure", async (t) => {
  const source = await makeSourceRepository(t);
  const repoRoot = await temporaryDirectory(t, "harness-target-");

  const draftsRoot = path.join(repoRoot, "drafts");
  await mkdir(draftsRoot);
  await chmod(draftsRoot, 0o500);

  await assert.rejects(
    importHarnessKnowledge({
      sourceKnowledgeRoot: source.knowledgeRoot,
      repoRoot,
      sourceRevision: source.revision,
    }),
  );

  await chmod(draftsRoot, 0o700);
  assert.deepEqual(await readdir(draftsRoot), []);
  assert.equal(
    await exists(path.join(repoRoot, "literature", "ref.bib")),
    false,
  );
  assert.equal(await exists(path.join(repoRoot, MANIFEST_PATH)), false);
  assert.deepEqual(await readdir(path.join(repoRoot, "work")).catch(() => []), []);
});

for (const step of [
  { name: "bibliography", directory: "literature" },
  { name: "manifest", directory: path.join("docs", "migrations") },
]) {
  test(`installs nothing when the ${step.name} step fails`, async (t) => {
    const source = await makeSourceRepository(t);
    const repoRoot = await temporaryDirectory(t, "harness-target-");

    await withUnwritableDirectory(path.join(repoRoot, step.directory), async () => {
      await assert.rejects(
        importHarnessKnowledge({
          sourceKnowledgeRoot: source.knowledgeRoot,
          repoRoot,
          sourceRevision: source.revision,
        }),
      );
    });

    assert.equal(await directoryExists(path.join(repoRoot, DESTINATION)), false);
    assert.deepEqual(
      await readdir(path.join(repoRoot, "drafts")).catch(() => []),
      [],
    );
    assert.equal(
      await exists(path.join(repoRoot, "literature", "ref.bib")),
      false,
    );
    assert.equal(await exists(path.join(repoRoot, MANIFEST_PATH)), false);
    assert.deepEqual(
      await readdir(path.join(repoRoot, "work")).catch(() => []),
      [],
    );
  });

  test(`keeps the previous import when the ${step.name} step fails`, async (t) => {
    const source = await makeSourceRepository(t);
    const repoRoot = await temporaryDirectory(t, "harness-target-");

    const installed = await importHarnessKnowledge({
      sourceKnowledgeRoot: source.knowledgeRoot,
      repoRoot,
      sourceRevision: source.revision,
    });
    const installedManifest = await readFile(
      path.join(repoRoot, MANIFEST_PATH),
      "utf8",
    );
    const nextRevision = await commitAdditionalCard(source);

    await withUnwritableDirectory(path.join(repoRoot, step.directory), async () => {
      await assert.rejects(
        importHarnessKnowledge({
          sourceKnowledgeRoot: source.knowledgeRoot,
          repoRoot,
          sourceRevision: nextRevision,
        }),
      );
    });

    // Every already-swapped target is restored, so the newer card never lands
    // and the manifest still describes exactly what is on disk.
    assert.deepEqual(
      await listRelativeFiles(path.join(repoRoot, DESTINATION)),
      EXPECTED_PATHS,
    );
    assert.equal(
      await readFile(path.join(repoRoot, MANIFEST_PATH), "utf8"),
      installedManifest,
    );
    assert.deepEqual(await verifyHarnessImport(repoRoot), {
      files: installed.files.length,
      bytes: EXPECTED_BYTES,
    });
    assert.deepEqual(
      await readdir(path.join(repoRoot, "work")).catch(() => []),
      [],
    );
  });
}

test("refuses a conflicting destination instead of overwriting it", async (t) => {
  const source = await makeSourceRepository(t);
  const repoRoot = await temporaryDirectory(t, "harness-target-");

  const destination = path.join(repoRoot, DESTINATION);
  await mkdir(destination, { recursive: true });
  await writeFile(path.join(destination, "rogue.md"), "hand written\n");

  await assert.rejects(
    importHarnessKnowledge({
      sourceKnowledgeRoot: source.knowledgeRoot,
      repoRoot,
      sourceRevision: source.revision,
    }),
    /refus/i,
  );

  assert.deepEqual(await listRelativeFiles(destination), ["rogue.md"]);
  assert.equal(
    await readFile(path.join(destination, "rogue.md"), "utf8"),
    "hand written\n",
  );
});

test("re-importing a verified destination is idempotent", async (t) => {
  const source = await makeSourceRepository(t);
  const repoRoot = await temporaryDirectory(t, "harness-target-");

  const options = {
    sourceKnowledgeRoot: source.knowledgeRoot,
    repoRoot,
    sourceRevision: source.revision,
  };
  const first = await importHarnessKnowledge(options);
  const firstManifest = await readFile(
    path.join(repoRoot, MANIFEST_PATH),
    "utf8",
  );

  const second = await importHarnessKnowledge(options);

  assert.deepEqual(second, first);
  assert.equal(
    await readFile(path.join(repoRoot, MANIFEST_PATH), "utf8"),
    firstManifest,
  );
  assert.deepEqual(
    await listRelativeFiles(path.join(repoRoot, DESTINATION)),
    EXPECTED_PATHS,
  );
});

test("verifies the import without access to the source repository", async (t) => {
  const { source, repoRoot } = await importFixture(t);

  await rm(source.root, { recursive: true, force: true });

  assert.deepEqual(await verifyHarnessImport(repoRoot), {
    files: EXPECTED_PATHS.length,
    bytes: EXPECTED_BYTES,
  });
});

test("verification rejects tampered, missing, and extra cards", async (t) => {
  const { repoRoot } = await importFixture(t);
  const destination = path.join(repoRoot, DESTINATION);

  await writeFile(path.join(destination, "extra.md"), "not imported\n");
  await assert.rejects(verifyHarnessImport(repoRoot), /extra\.md/);
  await rm(path.join(destination, "extra.md"));

  await writeFile(path.join(destination, "README.md"), "changed\n");
  await assert.rejects(verifyHarnessImport(repoRoot), /README\.md/);

  await rm(path.join(destination, "README.md"));
  await assert.rejects(verifyHarnessImport(repoRoot), /README\.md/);
});

test("verification rejects unknown non-Markdown files, which import keeps", async (t) => {
  const { source, repoRoot } = await importFixture(t);
  const destination = path.join(repoRoot, DESTINATION);
  const sidecar = path.join(destination, "_metadata.yml");

  await writeFile(sidecar, "title: sidecar\n");

  await assert.rejects(verifyHarnessImport(repoRoot), /_metadata\.yml/);
  await assert.rejects(
    importHarnessKnowledge({
      sourceKnowledgeRoot: source.knowledgeRoot,
      repoRoot,
      sourceRevision: source.revision,
    }),
    /refus/i,
  );

  assert.equal(await readFile(sidecar, "utf8"), "title: sidecar\n");
  assert.deepEqual(
    await listRelativeFiles(destination),
    [...EXPECTED_PATHS, "_metadata.yml"].sort(comparePosix),
  );
});

test("verification rejects a tampered bibliography", async (t) => {
  const { repoRoot } = await importFixture(t);

  await writeFile(
    path.join(repoRoot, "literature", "ref.bib"),
    `${BIBLIOGRAPHY}@misc{added2026,\n}\n`,
  );

  await assert.rejects(verifyHarnessImport(repoRoot), /ref\.bib/);
});

test("verifies byte-level parity against the pinned source revision", async (t) => {
  const { source, repoRoot } = await importFixture(t);

  assert.deepEqual(
    await verifyHarnessImportAgainstSource({
      sourceKnowledgeRoot: source.knowledgeRoot,
      repoRoot,
      sourceRevision: source.revision,
    }),
    { files: EXPECTED_PATHS.length, bytes: EXPECTED_BYTES },
  );
});

test("source parity ignores source files outside the manifest", async (t) => {
  const { source, repoRoot } = await importFixture(t);

  assert.equal(
    await exists(path.join(source.knowledgeRoot, "solvable", "benchmarks.json")),
    true,
  );
  assert.equal(
    await exists(path.join(source.knowledgeRoot, "literature", "ed", "paper.md")),
    true,
  );

  await assert.doesNotReject(
    verifyHarnessImportAgainstSource({
      sourceKnowledgeRoot: source.knowledgeRoot,
      repoRoot,
      sourceRevision: source.revision,
    }),
  );
});

test("source parity rejects a destination that drifted from the source", async (t) => {
  const { source, repoRoot } = await importFixture(t);

  await writeFile(
    path.join(repoRoot, DESTINATION, "models", "ising.md"),
    "# Ising\n\nlocally edited\n",
  );

  await assert.rejects(
    verifyHarnessImportAgainstSource({
      sourceKnowledgeRoot: source.knowledgeRoot,
      repoRoot,
      sourceRevision: source.revision,
    }),
    /models\/ising\.md/,
  );
});

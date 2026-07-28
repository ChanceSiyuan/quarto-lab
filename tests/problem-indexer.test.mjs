import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, readFile, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { buildProblemIndex, deriveNextProblemId, scanReservedProblemIds } from "../lib/problems/indexer.mjs";
import { REQUIRED_PROBLEM_MD_HEADINGS } from "../lib/problems/schema.mjs";

const completeProblemMd = REQUIRED_PROBLEM_MD_HEADINGS
  .map((heading) => `## ${heading}\nConcrete content.`)
  .join("\n\n");

async function makeRoot() {
  const root = await mkdtempDisposable();
  await mkdir(join(root, "problems"), { recursive: true });
  return root;
}

async function mkdtempDisposable() {
  const { mkdtemp } = await import("node:fs/promises");
  return mkdtemp(join(tmpdir(), "research-loop-index-"));
}

async function writeProblem(root, id, manifestOverrides = {}, problemMd = completeProblemMd) {
  await writeProblemAt(root, "problems", id, manifestOverrides, problemMd);
}

async function writeProblemAt(root, problemsDir, id, manifestOverrides = {}, problemMd = completeProblemMd) {
  const dir = join(root, problemsDir, id);
  await mkdir(join(dir, "generation"), { recursive: true });
  const manifest = {
    schemaVersion: 1,
    id,
    title: `${id} title`,
    summary: `${id} summary`,
    status: "draft",
    gate: { type: "interval-arithmetic", readiness: "specified" },
    provenance: { sourceCount: 3 },
    lastActivity: { summary: "Created", at: "2026-07-27T10:00:00Z" },
    createdAt: "2026-07-27T10:00:00Z",
    updatedAt: "2026-07-27T10:00:00Z",
    ...manifestOverrides,
  };
  await writeFile(join(dir, "problem.json"), JSON.stringify(manifest, null, 2));
  await writeFile(join(dir, "problem.md"), problemMd);
}

test("builds a deterministic index and summary from problem directories", async () => {
  const root = await makeRoot();
  await writeProblem(root, "Prob-002", {
    status: "published",
    gate: { type: "python", readiness: "passed" },
    updatedAt: "2026-07-27T12:00:00Z",
  });
  await writeProblem(root, "Prob-001", {
    status: "accepted",
    gate: { type: "interval-arithmetic", readiness: "executable" },
    updatedAt: "2026-07-27T12:00:00Z",
  });
  await writeProblem(root, "Prob-003", {
    status: "rejected",
    rejection: { kind: "human", reason: "Novelty did not survive comparison." },
    updatedAt: "2026-07-27T11:00:00Z",
  }, "## Candidate\nRejected with evidence.");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems.map((problem) => problem.id), ["Prob-001", "Prob-002", "Prob-003"]);
  assert.deepEqual(index.summary, {
    total: 3,
    accepted: 2,
    solved: 1,
    published: 1,
    rejected: 1,
    archived: 0,
  });
  assert.equal(index.nextProblemId, "Prob-004");
  assert.deepEqual(index.diagnostics, []);
});

test("isolates damaged manifests and duplicate IDs", async () => {
  const root = await makeRoot();
  await writeProblem(root, "Prob-001");
  await writeProblem(root, "Prob-002", { id: "Prob-001" });
  await mkdir(join(root, "problems", "Prob-003"), { recursive: true });
  await writeFile(join(root, "problems", "Prob-003", "problem.json"), "{ broken json");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems.map((problem) => problem.id), ["Prob-001"]);
  assert.equal(index.diagnostics.length, 2);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Duplicate problem id/);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Invalid JSON/);
});

test("reserves IDs from damaged problem directories without indexing them", async () => {
  const root = await makeRoot();
  const damagedDir = join(root, "problems", "Prob-001");
  await mkdir(damagedDir, { recursive: true });
  await writeFile(join(damagedDir, "problem.json"), "{ broken json");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems, []);
  assert.equal(index.nextProblemId, "Prob-002");
  assert.equal(index.diagnostics.length, 1);
  assert.equal(index.diagnostics[0].relativePath, "problems/Prob-001/problem.json");
  assert.match(index.diagnostics[0].message, /Invalid JSON/);
});

test("reserves IDs from non-directory problem entries without indexing them", async () => {
  const root = await makeRoot();
  await writeFile(join(root, "problems", "Prob-001"), "occupied by a damaged local problem artifact");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems, []);
  assert.equal(index.nextProblemId, "Prob-002");
  assert.deepEqual(index.diagnostics, []);
});

test("reserves parseable manifest IDs even when the record is invalid", async () => {
  const root = await makeRoot();
  await writeProblem(root, "candidate-draft", {
    id: "Prob-007",
    status: "not-a-status",
  });

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems, []);
  assert.equal(index.nextProblemId, "Prob-008");
  assert.ok(index.diagnostics.some((item) => item.field === "status"));
});

test("handles an empty repository and derives the first ID", async () => {
  const root = await makeRoot();
  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems, []);
  assert.equal(index.nextProblemId, "Prob-001");
  assert.equal(deriveNextProblemId([{ id: "Prob-009" }, { id: "Prob-011" }]), "Prob-012");
});

test("indexes only the selected problem root and honors reserved IDs", async () => {
  const root = await makeRoot();
  await writeProblemAt(root, "problems", "Prob-002");
  await writeProblemAt(root, "examples/showcase/problems", "Prob-000");

  const index = await buildProblemIndex({
    rootDir: root,
    problemsDir: "examples/showcase/problems",
    reservedIds: ["Prob-009"],
  });

  assert.deepEqual(index.problems.map((problem) => problem.id), ["Prob-000"]);
  assert.equal(index.nextProblemId, "Prob-010");
  assert.deepEqual(index.diagnostics, []);
});

test("scans reserved problem IDs from damaged directories and ID-shaped entries", async () => {
  const root = await makeRoot();
  await writeProblem(root, "Prob-002");
  await mkdir(join(root, "problems", "draft-with-manifest-id"), { recursive: true });
  await writeFile(join(root, "problems", "draft-with-manifest-id", "problem.json"), JSON.stringify({ id: "Prob-007" }));
  await writeFile(join(root, "problems", "Prob-001"), "occupied file");
  await writeFile(join(root, "target"), "occupied symlink target");
  await symlink(join(root, "target"), join(root, "problems", "Prob-003"));

  assert.deepEqual(await scanReservedProblemIds({
    rootDir: root,
    reservedIds: ["Prob-000", "invalid", "Prob-1", "Prob-001"],
  }), ["Prob-000", "Prob-001", "Prob-002", "Prob-003", "Prob-007"]);
});

test("ignores ID-shaped problem directories, files, and symlinks", async () => {
  const root = await makeRoot();
  await writeFile(join(root, ".gitignore"), await readFile(new URL("../.gitignore", import.meta.url)));
  await mkdir(join(root, "problems", "Prob-001"), { recursive: true });
  await writeFile(join(root, "problems", "Prob-001", "local.txt"), "local workspace");
  await writeFile(join(root, "problems", "Prob-002"), "damaged local artifact");
  await writeFile(join(root, "symlink-target"), "occupied through a symlink");
  await symlink(join(root, "symlink-target"), join(root, "problems", "Prob-003"));

  const initialized = spawnSync("git", ["init", "--quiet"], { cwd: root, encoding: "utf8" });
  assert.equal(initialized.status, 0, initialized.stderr);

  const candidates = [
    "problems/Prob-001/local.txt",
    "problems/Prob-002",
    "problems/Prob-003",
  ];
  const ignored = spawnSync("git", ["check-ignore", "--no-index", "--stdin"], {
    cwd: root,
    encoding: "utf8",
    input: `${candidates.join("\n")}\n`,
  });

  assert.equal(ignored.status, 0, ignored.stderr);
  assert.deepEqual(ignored.stdout.trim().split("\n"), candidates);
});

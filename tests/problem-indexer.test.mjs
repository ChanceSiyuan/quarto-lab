import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { buildProblemIndex, deriveNextProblemId } from "../lib/problems/indexer.mjs";
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
  const dir = join(root, "problems", id);
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
  await writeProblem(root, "QMB-002", {
    status: "published",
    gate: { type: "python", readiness: "passed" },
    updatedAt: "2026-07-27T12:00:00Z",
  });
  await writeProblem(root, "QMB-001", {
    status: "accepted",
    gate: { type: "interval-arithmetic", readiness: "executable" },
    updatedAt: "2026-07-27T12:00:00Z",
  });
  await writeProblem(root, "QMB-003", {
    status: "rejected",
    rejection: { kind: "human", reason: "Novelty did not survive comparison." },
    updatedAt: "2026-07-27T11:00:00Z",
  }, "## Candidate\nRejected with evidence.");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems.map((problem) => problem.id), ["QMB-001", "QMB-002", "QMB-003"]);
  assert.deepEqual(index.summary, {
    total: 3,
    accepted: 2,
    solved: 1,
    published: 1,
    rejected: 1,
    archived: 0,
  });
  assert.equal(index.nextProblemId, "QMB-004");
  assert.deepEqual(index.diagnostics, []);
});

test("isolates damaged manifests and duplicate IDs", async () => {
  const root = await makeRoot();
  await writeProblem(root, "QMB-001");
  await writeProblem(root, "QMB-002", { id: "QMB-001" });
  await mkdir(join(root, "problems", "QMB-003"), { recursive: true });
  await writeFile(join(root, "problems", "QMB-003", "problem.json"), "{ broken json");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems.map((problem) => problem.id), ["QMB-001"]);
  assert.equal(index.diagnostics.length, 2);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Duplicate problem id/);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Invalid JSON/);
});

test("reserves IDs from damaged problem directories without indexing them", async () => {
  const root = await makeRoot();
  const damagedDir = join(root, "problems", "QMB-001");
  await mkdir(damagedDir, { recursive: true });
  await writeFile(join(damagedDir, "problem.json"), "{ broken json");

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems, []);
  assert.equal(index.nextProblemId, "QMB-002");
  assert.equal(index.diagnostics.length, 1);
  assert.equal(index.diagnostics[0].relativePath, "problems/QMB-001/problem.json");
  assert.match(index.diagnostics[0].message, /Invalid JSON/);
});

test("reserves parseable manifest IDs even when the record is invalid", async () => {
  const root = await makeRoot();
  await writeProblem(root, "candidate-draft", {
    id: "QMB-007",
    status: "not-a-status",
  });

  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems, []);
  assert.equal(index.nextProblemId, "QMB-008");
  assert.ok(index.diagnostics.some((item) => item.field === "status"));
});

test("handles an empty repository and derives the first ID", async () => {
  const root = await makeRoot();
  const index = await buildProblemIndex({ rootDir: root });

  assert.deepEqual(index.problems, []);
  assert.equal(index.nextProblemId, "QMB-001");
  assert.equal(deriveNextProblemId([{ id: "QMB-009" }, { id: "QMB-011" }]), "QMB-012");
});

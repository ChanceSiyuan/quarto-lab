import assert from "node:assert/strict";
import test from "node:test";

import { createProblemRepository } from "../lib/problems/repository.mjs";

const index = {
  schemaVersion: 1,
  generatedAt: "2026-07-27T10:00:00.000Z",
  workspacePath: "/repo/research-loop",
  nextProblemId: "QMB-004",
  summary: { total: 3, accepted: 1, solved: 0, published: 0, rejected: 1, archived: 1, target: 5 },
  diagnostics: [{ relativePath: "problems/QMB-099/problem.json", field: "status", message: "Invalid status." }],
  problems: [
    { id: "QMB-001", title: "Fresh Hamiltonian gate", summary: "Interval arithmetic gate.", status: "accepted", gate: { type: "interval-arithmetic", readiness: "executable" }, provenance: { sourceCount: 3 }, lastActivity: { summary: "Accepted", at: "2026-07-27T10:00:00Z" }, updatedAt: "2026-07-27T10:00:00Z", createdAt: "2026-07-27T09:00:00Z" },
    { id: "QMB-002", title: "Rejected catalog duplicate", summary: "Novelty failed.", status: "rejected", gate: { type: "python", readiness: "specified" }, provenance: { sourceCount: 2 }, lastActivity: { summary: "Rejected", at: "2026-07-27T11:00:00Z" }, updatedAt: "2026-07-27T11:00:00Z", createdAt: "2026-07-27T09:00:00Z", rejection: { kind: "human", reason: "Duplicate." } },
    { id: "QMB-003", title: "Archived benchmark", summary: "Paused line.", status: "archived", gate: { type: "python", readiness: "missing" }, provenance: { sourceCount: 1 }, lastActivity: { summary: "Archived", at: "2026-07-27T12:00:00Z" }, updatedAt: "2026-07-27T12:00:00Z", createdAt: "2026-07-27T09:00:00Z" },
  ],
};

test("defaults to hiding rejected and archived problems", () => {
  const repository = createProblemRepository(index);

  assert.deepEqual(repository.listProblems().map((problem) => problem.id), ["QMB-001"]);
});

test("filters by query and explicit statuses", () => {
  const repository = createProblemRepository(index);

  assert.deepEqual(repository.listProblems({ query: "duplicate", includeRejected: true }).map((problem) => problem.id), ["QMB-002"]);
  assert.deepEqual(repository.listProblems({ statuses: ["archived"], includeArchived: true }).map((problem) => problem.id), ["QMB-003"]);
});

test("returns summary, diagnostics, and individual problems without mutation", () => {
  const repository = createProblemRepository(index);

  assert.equal(repository.getSummary().accepted, 1);
  assert.equal(repository.getIndexDiagnostics()[0].relativePath, "problems/QMB-099/problem.json");
  assert.equal(repository.getProblem("QMB-001").title, "Fresh Hamiltonian gate");
  assert.equal(repository.getProblem("QMB-404"), null);
});

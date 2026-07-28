import assert from "node:assert/strict";
import test from "node:test";

import {
  buildProblemHref,
  clearProblemFilters,
  createDefaultProblemFilters,
  filterProblems,
} from "../lib/problems/view-state.mjs";

const problems = [
  { id: "Prob-001", title: "Fresh Hamiltonian gate", summary: "Interval arithmetic.", status: "accepted" },
  { id: "Prob-002", title: "Catalog duplicate", summary: "Novelty failed.", status: "rejected" },
  { id: "Prob-003", title: "Paused benchmark", summary: "Archived line.", status: "archived" },
  { id: "Prob-004", title: "Solver draft", summary: "Tensor search.", status: "draft" },
];

test("default problem filters hide rejected and archived records", () => {
  const visible = filterProblems(problems, createDefaultProblemFilters());

  assert.deepEqual(visible.map((problem) => problem.id), ["Prob-001", "Prob-004"]);
});

test("filters problems by case-insensitive text and selected lifecycle status", () => {
  const visible = filterProblems(problems, {
    ...createDefaultProblemFilters(),
    query: "HAMILTONIAN",
    selectedStatuses: ["accepted"],
  });

  assert.deepEqual(visible.map((problem) => problem.id), ["Prob-001"]);
  assert.deepEqual(filterProblems(problems, {
    ...createDefaultProblemFilters(),
    query: "tensor",
    selectedStatuses: ["accepted"],
  }), []);
});

test("clear filters makes every lifecycle record visible again", () => {
  const visible = filterProblems(problems, clearProblemFilters());

  assert.deepEqual(visible.map((problem) => problem.id), ["Prob-001", "Prob-002", "Prob-003", "Prob-004"]);
});

test("builds the stable whole-item navigation target", () => {
  assert.equal(buildProblemHref("Prob-017"), "/problems/Prob-017");
});

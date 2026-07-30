import assert from "node:assert/strict";
import test from "node:test";
import {
  buildProblemPresentation,
  buildTierMetrics,
  judgmentStatusCopy,
  judgmentStatusTone,
} from "../../src/lib/problems/presentation.mjs";

test("formats tier metrics as raw counts without a target cap", () => {
  assert.deepEqual(
    buildTierMetrics({
      total: 9,
      accepted: 4,
      solved: 3,
      published: 2,
      rejected: 1,
    }),
    [
      ["Total", 9],
      ["Accepted", 4],
      ["Solved", 3],
      ["Published", 2],
      ["Rejected", 1],
    ],
  );
});

test("builds every populated problem field in console order", () => {
  const row = buildProblemPresentation({
    id: "Prob-017",
    title: "Fresh Hamiltonian gate",
    summary: "Interval arithmetic on held-out instances.",
    status: "accepted",
    gate: { type: "interval-arithmetic", readiness: "executable" },
    provenance: { sourceCount: 12 },
    lastActivity: {
      summary: "Accepted after novelty review",
      at: "2026-07-27T10:30:00.000Z",
    },
    updatedAt: "2026-07-27T11:45:00.000Z",
  });

  assert.deepEqual(row.fields, [
    {
      key: "problem",
      label: "Problem",
      id: "Prob-017",
      title: "Fresh Hamiltonian gate",
      summary: "Interval arithmetic on held-out instances.",
    },
    { key: "status", label: "Status", value: "accepted" },
    {
      key: "gate",
      label: "Executable gate",
      primary: "interval-arithmetic",
      secondary: "executable",
    },
    { key: "scientificDemand", label: "Scientific Demand Score", value: "—" },
    {
      key: "eansv",
      label: "Expected Attributable Net Social Value (EANSV)",
      value: "—",
    },
    { key: "autoresearchFit", label: "Autoresearch Fit", value: "—" },
  ]);
});

test("renders recorded evaluation points for scenario-backed problems", () => {
  const row = buildProblemPresentation({
    id: "Prob-127",
    title: "Contraction-order optimization",
    summary: "Exact contraction-cost improvements.",
    status: "solving",
    gate: { type: "tensor-contraction", readiness: "executable" },
    provenance: { sourceCount: 1 },
    lastActivity: {
      summary: "Exported as a public solver/finalization follow-up candidate.",
      at: "2026-07-30T00:00:00.000Z",
    },
    updatedAt: "2026-07-30T00:00:00.000Z",
  });

  assert.equal(row.scientificDemand.value, "81 / 100");
  assert.equal(row.eansv.value, "$3.0M USD 2026");
  assert.equal(row.autoresearchFit.value, "98 / 100");
});

test("renders the approved Prob-000 evaluation points on the homepage", () => {
  const row = buildProblemPresentation({
    id: "Prob-000",
    title: "CSS code-distance algorithm search",
    summary: "Find a publishable CSS code-distance algorithm.",
    status: "solving",
    gate: { type: "python-benchmark", readiness: "executable" },
    provenance: { sourceCount: 3 },
    lastActivity: { summary: "Static example ledger prepared", at: "2026-07-27T02:40:00.000Z" },
    updatedAt: "2026-07-27T02:40:00.000Z",
  });

  assert.equal(row.scientificDemand.value, "33.4 / 100");
  assert.equal(row.eansv.value, "+$180K USD 2026");
  assert.equal(row.autoresearchFit.value, "88.5 / 100");
});

test("renders solving, judged, and done as distinct judgment labels", () => {
  assert.equal(judgmentStatusCopy("accepted", "Prob-017"), "Solving");
  assert.equal(judgmentStatusCopy("solved", "Prob-001"), "Judged");
  assert.equal(judgmentStatusCopy("published", "Prob-002"), "Done");
  assert.equal(judgmentStatusCopy("solving", "Prob-000"), "Done");
  assert.equal(judgmentStatusCopy("archived", "Prob-124"), "Judged");
});

test("uses one color tone for each displayed judgment label", () => {
  assert.equal(judgmentStatusTone("accepted", "Prob-017"), "solving");
  assert.equal(judgmentStatusTone("solved", "Prob-001"), "solved");
  assert.equal(judgmentStatusTone("archived", "Prob-124"), "solved");
  assert.equal(judgmentStatusTone("published", "Prob-002"), "published");
  assert.equal(judgmentStatusTone("solving", "Prob-000"), "published");
});

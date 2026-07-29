import assert from "node:assert/strict";
import test from "node:test";
import {
  buildProblemPresentation,
  buildTierMetrics,
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
    { key: "provenance", label: "Provenance", value: "12 sources" },
    {
      key: "activity",
      label: "Recent activity",
      primary: "Accepted after novelty review",
      secondary: "2026-07-27 10:30:00 UTC",
    },
    { key: "updated", label: "Updated", value: "2026-07-27 11:45:00 UTC" },
    {
      key: "open",
      label: "Open",
      value: "Open problem",
      href: "/problems/Prob-017",
    },
  ]);
});

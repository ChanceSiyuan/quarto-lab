import assert from "node:assert/strict";
import test from "node:test";
import {
  EXAMPLE_RESEARCH_PROBLEM_ID,
  getStaticResearchArtifactPath,
  getStaticResearchAttempt,
  getStaticResearchExample,
  isStaticResearchExampleProblem,
  listStaticResearchAttempts,
  validateStaticResearchFixture,
} from "../lib/problems/example-research.mjs";
import {
  buildAttemptDossier,
  buildExampleResearchLedger,
  formatQuality,
  formatSeconds,
  formatSpeedup,
  formatVerified,
} from "../lib/problems/example-presentation.mjs";

test("static example exposes five ordered immutable attempts", () => {
  assert.equal(EXAMPLE_RESEARCH_PROBLEM_ID, "Prob-000");
  assert.equal(isStaticResearchExampleProblem("Prob-000"), true);
  assert.equal(isStaticResearchExampleProblem("Prob-999"), false);

  const example = getStaticResearchExample("Prob-000");
  assert.ok(example);
  assert.equal(
    example.manifest.disclaimer,
    "Example data - synthetic results for interface demonstration only.",
  );
  assert.deepEqual(example.attempts.map((attempt) => attempt.id), [
    "ATT-001",
    "ATT-002",
    "ATT-003",
    "ATT-004",
    "ATT-005",
  ]);

  example.attempts[0].id = "MUTATED";
  assert.equal(listStaticResearchAttempts("Prob-000")[0].id, "ATT-001");
});

test("static example attempts form the declared predecessor chain", () => {
  const attempts = listStaticResearchAttempts("Prob-000");
  assert.equal(attempts[0].method.learnedFrom, null);
  for (let index = 1; index < attempts.length; index += 1) {
    assert.equal(attempts[index].method.learnedFrom, attempts[index - 1].id);
  }
  assert.equal(getStaticResearchAttempt("Prob-000", "ATT-005").promoted, true);
  assert.equal(getStaticResearchAttempt("Prob-000", "ATT-999"), null);
  assert.equal(getStaticResearchExample("Prob-999"), null);
});

test("static example validation rejects malformed display fixture content", () => {
  const example = getStaticResearchExample("Prob-000");
  const malformedCases = [
    ["manifest disclaimer", (manifest) => { manifest.disclaimer = "real results"; }, /disclaimer/],
    ["attempt title", (_manifest, attempts) => { attempts[0].title = ""; }, /title/],
    ["promoted rejection", (_manifest, attempts) => { attempts[0].promoted = true; }, /promoted/],
    ["multiple promotions", (_manifest, attempts) => { attempts[2].promoted = true; }, /promoted/],
    ["gate value", (_manifest, attempts) => { attempts[0].gate.containment = "unknown"; }, /gate/],
    ["method changes", (_manifest, attempts) => { attempts[0].method.changes = []; }, /method/],
    ["metric count", (_manifest, attempts) => { attempts[0].metrics.verifiedWitnesses = 25; }, /metrics/],
    ["interpretation", (_manifest, attempts) => { attempts[0].interpretation = ""; }, /interpretation/],
    ["provenance timestamp", (_manifest, attempts) => { attempts[0].createdAt = "not-a-timestamp"; }, /createdAt/],
    ["unsafe artifact", (_manifest, attempts) => { attempts[0].artifacts[0] = "../../secret"; }, /artifact/],
  ];

  for (const [name, mutate, expectedMessage] of malformedCases) {
    const manifest = structuredClone(example.manifest);
    const attempts = structuredClone(example.attempts);
    mutate(manifest, attempts);
    assert.throws(
      () => validateStaticResearchFixture(manifest, attempts),
      expectedMessage,
      `${name} must be rejected before presentation`,
    );
  }
});

test("static example presentation derives synthetic aggregate cards", () => {
  const example = getStaticResearchExample("Prob-000");
  const ledger = buildExampleResearchLedger(example);
  assert.deepEqual(ledger.cards, [
    { label: "Attempts", value: "5" },
    { label: "Accepted", value: "3" },
    { label: "Best hits", value: "24/24" },
    { label: "Best speedup", value: "118.2x" },
  ]);
  assert.equal(ledger.rows[0].method, "Exact meet-in-the-middle baseline");
  assert.equal(ledger.rows[1].decision, "Rejected");
  assert.equal(ledger.rows[4].href, "/problems/Prob-000/attempts/ATT-005");
});

test("static example formatting is stable for route rendering", () => {
  assert.equal(formatVerified({ verifiedWitnesses: 18, runs: 24 }), "18/24");
  assert.equal(formatQuality(0.54), "0.540");
  assert.equal(formatSeconds(1.24), "1.24 s");
  assert.equal(formatSeconds(39.8), "39.8 s");
  assert.equal(formatSpeedup(118.2), "118.2x");
  assert.equal(
    getStaticResearchArtifactPath("Prob-000", "ATT-003", "LOG.md"),
    "examples/showcase/problems/Prob-000/attempts/ATT-003/LOG.md",
  );
});

test("static example retains its synthetic gate values through shared formatting", () => {
  const example = getStaticResearchExample("Prob-000");
  const ledger = buildExampleResearchLedger(example);
  assert.deepEqual(ledger.rows[0].gate, [
    { label: "Containment", value: "passed" },
    { label: "Public smoke", value: "passed" },
    { label: "Development", value: "failed" },
  ]);
});

test("attempt dossier includes audit metadata and display sections", () => {
  const example = getStaticResearchExample("Prob-000");
  const attempt = getStaticResearchAttempt("Prob-000", "ATT-004");
  const dossier = buildAttemptDossier(attempt, example.manifest);
  assert.equal(dossier.title, "Residual-seeded local search");
  assert.equal(dossier.metrics[2].label, "Quality");
  assert.equal(dossier.metrics[2].value, "0.970");
  assert.deepEqual(dossier.evaluationPath.map((item) => item.label), [
    "Containment",
    "Public smoke",
    "Development",
    "Decision",
  ]);
  assert.deepEqual(dossier.artifacts, [
    "examples/showcase/problems/Prob-000/attempts/ATT-004/attempt.json",
    "examples/showcase/problems/Prob-000/attempts/ATT-004/LOG.md",
  ]);
});

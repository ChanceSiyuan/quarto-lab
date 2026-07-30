import assert from "node:assert/strict";
import test from "node:test";

import {
  QH127_RESEARCH_PROBLEM_ID,
  buildQh127ResearchLedger,
  getQh127Research,
  isQh127ResearchProblem,
} from "../../src/lib/problems/qh127-research.mjs";

test("qh-127 research record exposes the real run with nine attempts", () => {
  const research = getQh127Research();
  assert.equal(research.run.problemId, QH127_RESEARCH_PROBLEM_ID);
  assert.equal(research.run.status, "EXHAUSTED");
  assert.equal(research.attempts.length, 9);
  assert.equal(research.run.attemptsRecorded, 9);
  assert.equal(isQh127ResearchProblem("Prob-127"), true);
  assert.equal(isQh127ResearchProblem("Prob-000"), false);
});

test("qh-127 ledger promotes attempt-003 with the strict public improvement", () => {
  const ledger = buildQh127ResearchLedger(getQh127Research());
  const promoted = ledger.rows.filter((row) => row.promoted);
  assert.equal(promoted.length, 1);
  assert.equal(promoted[0].id, "attempt-003");
  assert.equal(promoted[0].ratio, "0.603x");
  assert.equal(promoted[0].decision, "accepted");
  assert.equal(promoted[0].learnedFrom, "attempt-002");
  for (const row of ledger.rows) {
    if (!row.promoted) {
      assert.equal(row.decision, "rejected");
    }
  }
});

test("qh-127 ledger reports the sealed finalization aggregate only", () => {
  const ledger = buildQh127ResearchLedger(getQh127Research());
  assert.equal(ledger.finalization.attempt, "attempt-003");
  assert.equal(ledger.finalization.verdict, "failed");
  assert.equal(ledger.finalization.strictlyBetter, false);
  const cardLabels = ledger.cards.map((card) => card.label);
  assert.deepEqual(cardLabels, [
    "Baseline cost",
    "Best public cost",
    "Best public ratio",
    "Attempts",
    "Sealed finalization",
    "Run status",
  ]);
});

test("qh-127 attempts chain learning references and keep costs as strings", () => {
  const { attempts } = getQh127Research();
  assert.equal(attempts[0].learnedFrom, null);
  for (let index = 1; index < attempts.length; index += 1) {
    assert.equal(attempts[index].learnedFrom, attempts[index - 1].id);
  }
  for (const attempt of attempts) {
    assert.equal(typeof attempt.outcome.exactCost, "string");
    assert.equal(typeof attempt.outcome.baselineCost, "string");
    assert.equal(attempt.strategy.slots.length, 3);
  }
});

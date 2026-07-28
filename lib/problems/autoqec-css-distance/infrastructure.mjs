import { AUTOQEC_INFRASTRUCTURE_RANGES } from "../research-schema.mjs";

export function expectedInfrastructureForAttempt(sequence, ranges = AUTOQEC_INFRASTRUCTURE_RANGES) {
  const range = ranges.find((item) => sequence >= item.first && sequence <= item.last);
  if (!range) throw new Error(`No infrastructure range for ATT-${String(sequence).padStart(3, "0")}`);
  return range;
}

export function buildCohortManifests(ranges = AUTOQEC_INFRASTRUCTURE_RANGES) {
  return ["cohort-001-100", "cohort-101-200"].map((cohort) => ({
    schemaVersion: 1,
    kind: "autoqec-css-distance-cohort",
    id: cohort,
    problemId: "Prob-001",
    attempts: ranges
      .filter((range) => range.cohort === cohort)
      .map((range) => ({
        first: range.first,
        last: range.last,
        sourceInfrastructureCommit: range.commit,
      })),
  }));
}

export async function buildInfrastructurePlan(trials, { ranges = AUTOQEC_INFRASTRUCTURE_RANGES } = {}) {
  return trials.map((trial) => {
    const range = expectedInfrastructureForAttempt(trial.sequence, ranges);
    if (trial.firstParent !== range.commit) {
      throw new Error(`infrastructure commit mismatch for ATT-${String(trial.sequence).padStart(3, "0")}: expected ${range.commit}, got ${trial.firstParent}`);
    }
    return { ...trial, commit: range.commit, cohort: range.cohort, range };
  });
}

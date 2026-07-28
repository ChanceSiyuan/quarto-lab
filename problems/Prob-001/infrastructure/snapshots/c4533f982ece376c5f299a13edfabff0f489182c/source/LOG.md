# CSS Distance Algorithm Experiment

- Algorithm: `run100-proposal-001`
- Branch: `autoresearch/css-distance/run100-proposal-001`
- Created: `2026-07-21T16:15:24Z`
- Per-run timeout: `300s`
- Dataset: private issue #38 holdout. Proposal agents do not receive selected case ids, answer keys, hidden targets, or witness vectors.
- Objective: randomized CSS-distance upper-bound witness search.

## Proposal

- Run: fresh proposal `001` of `100`.
- Model: `gpt-5.5` in the pinned public proposal image.
- Containment canary: `passed` for host-path and outbound-network denial.
- Idea: randomized kernel-vector sampling followed by stabilizer-coset descent.
- Candidate source: `proposal-workspace/candidate.py`.

## Public Contract Smoke

- Initial result: rejected by the public sparse-matrix contract smoke because the generated loader did not recognize AutoQEC `sparse_rows` JSON.
- Mechanical adaptation: added only the documented `sparse_rows` parser; search logic was unchanged.
- Adapted result: `completed`, with an independently verified upper-bound witness on the public smoke fixture.

## Screening Result

- decision: rejected
- accepted: False
- runs: 24
- verified_witnesses: 12
- target_hits: 12
- timeouts: 0
- crashes: 0
- invalid_claims: 12
- weighted_target_hits: 12
- normalized_quality: 0.5
- runtime_seconds: 4.705462539917789

# CSS Distance Algorithm Experiment

- Algorithm: `run100-proposal-055`
- Branch: `autoresearch/css-distance/run100-proposal-055`
- Created: `2026-07-21T22:08:28Z`
- Per-run timeout: `300s`
- Dataset: private issue #38 holdout. Proposal agents do not receive selected case ids, answer keys, hidden targets, or witness vectors.
- Objective: randomized CSS-distance upper-bound witness search.

## Proposal

- Run: fresh proposal `055` of `100`.
- Model: `gpt-5.5` in the pinned public proposal image.
- Containment canary: `passed` for host-path and outbound-network denial.
- Exploration theme: check-graph guided local search with tabu diversification.
- Candidate source: `proposal-workspace/candidate.py`.

## Public Contract Smoke

- Result: `completed` with an independently verified upper-bound witness.

## Screening Result

- decision: rejected
- accepted: False
- runs: 24
- verified_witnesses: 11
- target_hits: 8
- timeouts: 0
- crashes: 0
- invalid_claims: 13
- weighted_target_hits: 8
- normalized_quality: 0.40870811287477954
- runtime_seconds: 95.6267271231045

# CSS Distance Algorithm Experiment

- Algorithm: `run100-proposal-039`
- Branch: `autoresearch/css-distance/run100-proposal-039`
- Created: `2026-07-21T20:23:23Z`
- Per-run timeout: `300s`
- Dataset: private issue #38 holdout. Proposal agents do not receive selected case ids, answer keys, hidden targets, or witness vectors.
- Objective: randomized CSS-distance upper-bound witness search.

## Proposal

- Run: fresh proposal `039` of `100`.
- Model: `gpt-5.5` in the pinned public proposal image.
- Containment canary: `passed` for host-path and outbound-network denial.
- Exploration theme: check-graph guided local search with tabu diversification.
- Candidate source: `proposal-workspace/candidate.py`.

## Public Contract Smoke

- Result: `completed` with an independently verified upper-bound witness.

## Screening Result

- decision: accepted
- accepted: True
- runs: 24
- verified_witnesses: 24
- target_hits: 23
- timeouts: 0
- crashes: 0
- invalid_claims: 0
- weighted_target_hits: 23
- normalized_quality: 0.9722222222222222
- runtime_seconds: 104.60068595502526

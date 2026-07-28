# CSS Distance Algorithm Experiment

- Algorithm: `run100-proposal-003`
- Branch: `autoresearch/css-distance/run100-proposal-003`
- Created: `2026-07-21T16:56:50Z`
- Per-run timeout: `300s`
- Dataset: private issue #38 holdout. Proposal agents do not receive selected case ids, answer keys, hidden targets, or witness vectors.
- Objective: randomized CSS-distance upper-bound witness search.

## Proposal

- Run: fresh proposal `003` of `100`.
- Model: `gpt-5.5` in the pinned public proposal image.
- Containment canary: `passed` for host-path and outbound-network denial.
- Exploration theme: sparsity-aware connected-cluster growth and repair.
- Candidate source: `proposal-workspace/candidate.py`.

## Public Contract Smoke

- Result: `completed` with an independently verified upper-bound witness.

## Screening Result

- decision: accepted
- accepted: True
- runs: 24
- verified_witnesses: 22
- target_hits: 19
- timeouts: 2
- crashes: 0
- invalid_claims: 0
- weighted_target_hits: 19
- normalized_quality: 0.8732142857142856
- runtime_seconds: 1074.1065059149405

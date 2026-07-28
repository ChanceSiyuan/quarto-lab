# CSS Distance Algorithm Experiment

- Algorithm: `run100-proposal-073`
- Branch: `autoresearch/css-distance/run100-proposal-073`
- Created: `2026-07-21T23:50:56Z`
- Per-run timeout: `300s`
- Dataset: private issue #38 holdout. Proposal agents do not receive selected case ids, answer keys, hidden targets, or witness vectors.
- Objective: randomized CSS-distance upper-bound witness search.

## Proposal

- Run: fresh proposal `073` of `100`.
- Model: `gpt-5.5` in the pinned public proposal image.
- Containment canary: `passed` for host-path and outbound-network denial.
- Exploration theme: low-weight nullspace basis recombination with annealed mutations.
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
- normalized_quality: 0.9791666666666666
- runtime_seconds: 90.18463941587834

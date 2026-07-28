# CSS Distance Algorithm Experiment

- Algorithm: `run100-proposal-002`
- Branch: `autoresearch/css-distance/run100-proposal-002`
- Created: `2026-07-21T16:32:13Z`
- Per-run timeout: `300s`
- Dataset: private issue #38 holdout. Proposal agents do not receive selected case ids, answer keys, hidden targets, or witness vectors.
- Objective: randomized CSS-distance upper-bound witness search.

## Proposal

- Run: fresh proposal `002` of `100`.
- Model: `gpt-5.5` in the pinned public proposal image.
- Containment canary: `passed` for host-path and outbound-network denial.
- Exploration theme: decoder-residual logical search with randomized perturbations.
- Candidate source: `proposal-workspace/candidate.py`.

## Public Contract Smoke

- Result: `completed` with an independently verified upper-bound witness.

## Screening Result

- decision: accepted
- accepted: True
- runs: 24
- verified_witnesses: 24
- target_hits: 24
- timeouts: 0
- crashes: 0
- invalid_claims: 0
- weighted_target_hits: 24
- normalized_quality: 1.0
- runtime_seconds: 888.5027844590368

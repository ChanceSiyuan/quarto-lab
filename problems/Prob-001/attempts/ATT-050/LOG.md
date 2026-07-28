# CSS Distance Algorithm Experiment

- Algorithm: `run100-proposal-050`
- Branch: `autoresearch/css-distance/run100-proposal-050`
- Created: `2026-07-21T21:41:57Z`
- Per-run timeout: `300s`
- Dataset: private issue #38 holdout. Proposal agents do not receive selected case ids, answer keys, hidden targets, or witness vectors.
- Objective: randomized CSS-distance upper-bound witness search.

## Proposal

- Run: fresh proposal `050` of `100`.
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
- target_hits: 22
- timeouts: 0
- crashes: 0
- invalid_claims: 0
- weighted_target_hits: 22
- normalized_quality: 0.9649470899470899
- runtime_seconds: 145.83112499595154

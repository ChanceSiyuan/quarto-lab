# CSS Distance Algorithm Experiment

- Algorithm: `run100-proposal-071`
- Branch: `autoresearch/css-distance/run100-proposal-071`
- Created: `2026-07-21T23:38:01Z`
- Per-run timeout: `300s`
- Dataset: private issue #38 holdout. Proposal agents do not receive selected case ids, answer keys, hidden targets, or witness vectors.
- Objective: randomized CSS-distance upper-bound witness search.

## Proposal

- Run: fresh proposal `071` of `100`.
- Model: `gpt-5.5` in the pinned public proposal image.
- Containment canary: `passed` for host-path and outbound-network denial.
- Exploration theme: check-graph guided local search with tabu diversification.
- Candidate source: `proposal-workspace/candidate.py`.

## Public Contract Smoke

- Result: rejected before private screening because the candidate did not return an independently verified witness on the public fixture.

## Screening Result

- decision: rejected
- accepted: False
- runs: 0
- verified_witnesses: 0
- target_hits: 0
- timeouts: 0
- crashes: 0
- invalid_claims: 1
- weighted_target_hits: 0
- normalized_quality: 0.0
- runtime_seconds: 0.0

# CSS Distance Proposal 078 Report

## Overview

- Proposal: `078` of `100`
- Branch: `autoresearch/css-distance/run100-proposal-078`
- Candidate: `proposal-workspace/candidate.py`
- Objective: randomized CSS logical-operator witness search for an upper-bound certificate.
- Per-process hard timeout: `300s`

## Method

The assigned exploration direction was **syndrome-preserving bit-flip walks across stabilizer cosets**. The candidate is a heuristic witness generator; it does not attempt or claim exact distance.

## Isolation and Reproducibility

The proposal ran in a dedicated public-only workspace after a live host-path and outbound-network containment canary passed. Evaluation used a networkless container and exposed one opaque matrix pair at a time.

## Public Contract Check

Status: **not-run**. A passing check means the candidate returned a logical witness accepted by the independent verifier on a public fixture.

## Blinded Development Screening

Only aggregate values are reported; case identities, matrices, targets, seeds, and witness vectors are intentionally omitted.

| Metric | Value |
| --- | ---: |
| Decision | rejected |
| Runs | 0 |
| Verified witnesses | 0 |
| Target hits | 0 |
| Timeouts | 0 |
| Crashes | 1 |
| Invalid claims | 0 |
| Weighted target hits | 0 |
| Normalized quality | 0.0 |
| Runtime seconds | 0.0 |

## Interpretation

The proposal was rejected because screening encountered a timeout or process failure.

## Limitations

- Every accepted witness certifies an upper-bound only, never exact distance.
- Screening uses the blinded development split and does not establish family-wide performance.
- The sealed final holdout was not evaluated.

# CSS Distance Proposal 049 Report

## Overview

- Proposal: `049` of `100`
- Branch: `autoresearch/css-distance/run100-proposal-049`
- Candidate: `proposal-workspace/candidate.py`
- Objective: randomized CSS logical-operator witness search for an upper-bound certificate.
- Per-process hard timeout: `300s`

## Method

The assigned exploration direction was **randomized information-set search with adaptive column bias**. The candidate is a heuristic witness generator; it does not attempt or claim exact distance.

## Isolation and Reproducibility

The proposal ran in a dedicated public-only workspace after a live host-path and outbound-network containment canary passed. Evaluation used a networkless container and exposed one opaque matrix pair at a time.

## Public Contract Check

Status: **passed**. A passing check means the candidate returned a logical witness accepted by the independent verifier on a public fixture.

## Blinded Development Screening

Only aggregate values are reported; case identities, matrices, targets, seeds, and witness vectors are intentionally omitted.

| Metric | Value |
| --- | ---: |
| Decision | accepted |
| Runs | 24 |
| Verified witnesses | 24 |
| Target hits | 21 |
| Timeouts | 0 |
| Crashes | 0 |
| Invalid claims | 0 |
| Weighted target hits | 21 |
| Normalized quality | 0.9481780888030888 |
| Runtime seconds | 1323.6209573309752 |

## Interpretation

The proposal passed the strict screening gate: every reported result was valid and at least one blinded development target was met.

## Limitations

- Every accepted witness certifies an upper-bound only, never exact distance.
- Screening uses the blinded development split and does not establish family-wide performance.
- The sealed final holdout was not evaluated.

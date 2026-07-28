# CSS Distance Proposal 053 Report

## Overview

- Proposal: `053` of `100`
- Branch: `autoresearch/css-distance/run100-proposal-053`
- Candidate: `proposal-workspace/candidate.py`
- Objective: randomized CSS logical-operator witness search for an upper-bound certificate.
- Per-process hard timeout: `300s`

## Method

The assigned exploration direction was **population-based evolutionary search over logical cosets**. The candidate is a heuristic witness generator; it does not attempt or claim exact distance.

## Isolation and Reproducibility

The proposal ran in a dedicated public-only workspace after a live host-path and outbound-network containment canary passed. Evaluation used a networkless container and exposed one opaque matrix pair at a time.

## Public Contract Check

Status: **passed**. A passing check means the candidate returned a logical witness accepted by the independent verifier on a public fixture.

## Blinded Development Screening

Only aggregate values are reported; case identities, matrices, targets, seeds, and witness vectors are intentionally omitted.

| Metric | Value |
| --- | ---: |
| Decision | rejected |
| Runs | 24 |
| Verified witnesses | 9 |
| Target hits | 5 |
| Timeouts | 0 |
| Crashes | 0 |
| Invalid claims | 15 |
| Weighted target hits | 5 |
| Normalized quality | 0.2982817620975516 |
| Runtime seconds | 9.075726539944299 |

## Interpretation

The proposal was rejected because one or more screening runs did not produce a contract-valid, independently verified witness.

## Limitations

- Every accepted witness certifies an upper-bound only, never exact distance.
- Screening uses the blinded development split and does not establish family-wide performance.
- The sealed final holdout was not evaluated.

# Beat frozen local tensor-network contraction baselines on canonical benchmarks

## Background and Gap
Optimize an explicit tensor-network contraction plan under a pinned per-instance memory and slicing convention against a fixed local cotengra baseline.

## Research Objective
Exact contraction cost under the fixed per-instance memory and slicing convention

## Publication Threshold
The sealed final evaluation must reproduce the frozen local baseline convention and plan, validate the submitted plan independently, and pass every acceptance check.

## Executable Gate
Research Loop problem id `Prob-127` is linked to quantum harness package `qh-127` with lane `solver-finalization-follow-up`.

## Novelty Evidence
A submitted contraction plan has a strictly lower independently recomputed exact paper-C cost than the frozen local cotengra baseline on at least one canonical instance.

## Provenance
Source: https://github.com/QuantumBFS/quantum.harness/issues/127
Snapshot digest: `sha256:28366f198ec72f125e983977a06966a1cba68b7daa59cfd0ed3c85e67a46ff37`
Problem type: `optimization`; tags: tensor-networks, contraction-ordering, exact-cost.

## Fresh Evaluation Plan
Use the quantum harness flow and sealed-finalization gate only after a strict public candidate has been produced and independently validated.

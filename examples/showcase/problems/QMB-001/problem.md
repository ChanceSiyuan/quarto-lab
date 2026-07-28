# CSS code-distance algorithm search

## Background and Gap

CSS quantum error-correcting codes need fast code-distance estimation for design loops, screening, and benchmark comparison. Exact search can be reliable but expensive, while aggressive heuristics need clear verification before their claims are useful.

## Research Objective

Use an autoresearch-style loop to search for a code-distance computing algorithm for CSS codes. The target is a publishable algorithm that is either 100x faster than the synthetic baseline in this static example or demonstrates better scaling under a hard five-minute run limit.

## Publication Threshold

A candidate must return verified witnesses on the blind evaluation suite, preserve containment between proposal and evaluation data, and show a synthetic speedup or scaling advantage large enough to justify follow-up research.

## Executable Gate

Each attempt is evaluated as if it had a Python benchmark gate with a 300 second limit per run, public smoke checks, containment checks, and a development suite summary. These values are static example data only.

## Novelty Evidence

The example mirrors a workflow that first surveys SOTA algorithms and builds a held-out dataset before proposing new algorithms. The displayed numbers are fictional and are included to exercise the interface.

## Provenance

The static example is derived from the shape of a local AutoQEC-style research process. It does not copy real benchmark values, private datasets, real commits, or real scientific conclusions.

## Fresh Evaluation Plan

Future real runs should keep benchmark datasets hidden from proposal agents, record a durable `LOG.md` in each worktree, and compare every accepted attempt against a frozen SOTA baseline under the same five-minute run budget.

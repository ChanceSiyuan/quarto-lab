# CSS Distance Autoresearch Results

## Outcome

The quality-first winner is the pinned open-source `decoderDist` BP-OSD
baseline.  Under the campaign's frozen lexicographic ranking it achieved 30
weighted target hits in the three-seed finalist phase, compared with 24 for the
best blinded proposal.

The recommended practical algorithm is **randomized quotient-coset descent**
from proposal 002.  It independently verified a logical witness in every one
of 30 finalist runs, completed the finalist set in 19.50 seconds, and retained
80% of the quality winner's weighted hits.  The BP-OSD winner took 2,645.79
seconds, produced six hard timeouts, and was about 136 times slower in
aggregate.  These are upper-bound witnesses, not exact-distance certificates.

Practical recommendation: proposal 002 is now packaged as
`autoqec-search find-quotient-coset-upper-bound`. It is an experimental
randomized upper-bound witness finder, not an exact-distance method and not a
Zoo promotion source.

## SOTA Starting Point

The pre-experiment survey covered random information-set search, evolutionary
search, decoder-residual/BP-OSD search, linked-cluster methods, and
structure-aware APM witnesses.  Exact SAT/MaxSAT, ILP/MIP, and exhaustive
distance search were deliberately excluded.  Experiments began from the open
source `codeDistancePYPI` implementation pinned at commit
`a4afe9c09bbf5790da9ecc05b65c5b62343979ad`, package version
`codedistance==0.0.8`.

The upstream license metadata remains unresolved: the repository LICENSE says
MIT while package metadata says GNUv3.  Reuse outside this research experiment
requires an operator license review.

## Blinded Dataset and Evaluation

The operator selected ten finite CSS instances from the issue #38 ladder,
spanning geometric, bivariate-bicycle, APM-LDPC, and quantum-Tanner regimes.
The matrices, identities, targets, answer keys, and case-level outcomes lived
only in a private evaluator root.  Proposal agents received only the public
survey brief, source pin, command contract, and a dedicated public workspace.

Containment canaries confirmed that each proposal container could neither read
a host-only path nor resolve an outbound URL.  Candidate evaluation was
networkless and read-only.  Each candidate invocation had a 300-second hard
limit; timed-out Docker containers were force-removed by unique name.  The
evaluator independently checked the relevant CSS kernel condition and
non-membership in the corresponding stabilizer row space before accepting a
witness.

## Screening

The table contains sanitized aggregates only.  `W-hits` is the campaign's
weighted target-hit score and `quality` is the normalized upper-bound quality.

| Algorithm | Verified / runs | Target hits | W-hits | Quality | Timeouts | Invalid | Runtime (s) | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `codedistance/decoderDist` | 8 / 10 | 7 | 10 | 0.6222 | 2 | 0 | 980.47 | finalist |
| `codedistance/QDistRndMW` | 8 / 10 | 6 | 8 | 0.6126 | 2 | 0 | 690.26 | screened |
| `codedistance/QDistEvol` | 8 / 10 | 6 | 8 | 0.6126 | 2 | 0 | 692.85 | screened |
| proposal 001, generic hybrid | 0 / 10 | 0 | 0 | 0.0000 | 0 | 10 | 2823.75 | rejected |
| proposal 002, quotient-coset descent | 10 / 10 | 6 | 8 | 0.7720 | 0 | 0 | 7.31 | finalist |
| proposal 003, reducer pool | 10 / 10 | 6 | 8 | 0.7609 | 0 | 0 | 16.92 | dominated |
| proposal 004, bounded decoder ensemble | 10 / 10 | 6 | 8 | 0.7720 | 0 | 0 | 64.09 | dominated |

The pinned Python package initially failed through a circular wildcard import
and a missing `LOCheck` default.  The baseline adapters were rerun after only
mechanical compatibility fixes; their algorithm choice and iteration budgets
were unchanged.  Proposal 001 exposed an underspecified output-status contract;
the public prompt was corrected for later proposals, while its original result
was retained as negative evidence.

## Three-Seed Finalists

| Algorithm | Verified / runs | Target hits | W-hits | Quality | Timeouts | Runtime (s) |
|---|---:|---:|---:|---:|---:|---:|
| `codedistance/decoderDist` | 24 / 30 | 21 | 30 | 0.6222 | 6 | 2645.79 |
| proposal 002, quotient-coset descent | 30 / 30 | 18 | 24 | 0.7703 | 0 | 19.50 |

The frozen ranking prioritizes weighted target hits, followed by normalized
quality, verified-witness count, and runtime.  It therefore selects
`decoderDist`.  Proposal 002 is the Pareto alternative for interactive search,
large sweeps, and environments where predictable completion matters.

## Recommended Algorithm

Randomized quotient-coset descent represents binary vectors as Python integers
and performs the following upper-bound search separately for X and Z logicals:

1. Compute a kernel basis of the opposite CSS check matrix and construct
   representatives of its quotient by the stabilizer row space.
2. Bias sampling toward low-weight quotient representatives, with a mixture of
   one-, two-, three-, and small random combinations.
3. Randomly perturb a representative with low-weight stabilizers, then greedily
   descend within the coset by accepting weight-reducing stabilizer additions.
4. Stop after a bounded no-improvement budget and return the lighter verified X
   or Z logical witness.
5. Self-check the kernel and row-space conditions before printing the result;
   the external evaluator repeats both checks independently.

This algorithm is randomized and produces only a certified upper bound.  Its
implementation is retained on branch
`autoresearch/css-distance/proposal-002` with the full experiment history in
that worktree's `LOG.md`.

## Reproducibility

Public inputs, source pins, and container instructions are in this campaign
directory.  Materialize the private issue #38 holdout separately, then invoke
the evaluator with `--phase screening` or `--phase finalists` and
`--timeout-seconds 300`.  Every experiment branch retains its candidate and a
sanitized `LOG.md`; no case-level private result is committed.

Final verification passed 65 focused CSS-distance harness tests and the fresh
full repository suite (`1104 passed, 7 deselected`).  The closing Docker audit
found no surviving evaluator containers.

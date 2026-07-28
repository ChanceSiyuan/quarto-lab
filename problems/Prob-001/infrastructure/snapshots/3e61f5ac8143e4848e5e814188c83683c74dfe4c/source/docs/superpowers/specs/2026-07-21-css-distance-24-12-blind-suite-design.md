# CSS Distance 24+12 Blind Validation Suite Design

## Goal

Create a blinded validation suite for randomized CSS code-distance upper-bound
algorithms with exactly 24 development instances and 12 sealed final-holdout
instances.  The suite is the next evidence stage for the experimental
`quotient-coset-upper-bound` method packaged by PR #105 and the paper-readiness
work tracked by issue #106.

The suite must improve statistical and construction-family coverage without
letting an algorithm-proposal agent see case identities, matrices, targets,
witnesses, construction parameters, case-level outcomes, or the development /
final allocation.  All algorithm invocations retain the existing hard limit of
300 seconds per method, instance, and seed.

## Decision

Use one operator-owned source pool, stratify it by construction family and
reference strength, and commit to a 24/12 allocation before running proposal
002 or any new proposal on it.  Development evaluation may emit sanitized
aggregate feedback.  The final holdout cannot be opened by the runner until the
algorithm implementation, image, parameters, and seed manifest have been
frozen.

This is preferable to immediately proposing more algorithms because the
existing result used only ten hidden instances and three seeds.  Reusing that
small set for more rounds would increase selection bias without establishing
whether proposal 002 generalizes.

## Scope

This work includes:

- generation or import of 36 redistribution-safe finite CSS instances;
- a fixed 24-instance blind development split and 12-instance sealed final
  split;
- provenance, matrix-integrity, CSS-commutation, rank, reference, and duplicate
  validation;
- salted commitments that prove the sealed manifests were not changed;
- evaluator controls that keep both splits out of proposal workspaces;
- a freeze gate that prevents final evaluation before the candidate is pinned;
- a committed 20-seed manifest and the existing 300-second hard limit;
- machine-readable validation and negative controls for split, seal, witness,
  and freeze integrity;
- sanitized aggregate result contracts compatible with the later issue #106
  paper-readiness report.

The full five-method, 20-seed benchmark and the publication manuscript are
subsequent executions of this suite.  Building the suite must make those runs
possible and auditable, but it does not claim a paper result by itself.

## Suite composition

The allocation is fixed by broad family before individual cases are selected:

| Family | Blind development | Sealed final | Total |
|---|---:|---:|---:|
| Geometric CSS (surface and toric, balanced within each split) | 8 | 4 | 12 |
| Bivariate-bicycle | 6 | 3 | 9 |
| APM-LDPC / Kasai-derived | 4 | 2 | 6 |
| Quantum Tanner | 6 | 3 | 9 |
| **Total** | **24** | **12** | **36** |

The geometric allocation contains equal numbers of surface and toric
instances in each split: four plus four in development and two plus two in the
final holdout.

The source pool may reuse validated issue #38 ladder artifacts, but it must add
new construction parameters because that ladder contains only 19 instances and
is too concentrated in surface and toric scaling.  New BB cases must vary
construction shifts or aspect ratios, rather than merely repeat a single shift
pattern at larger block length.  New APM/Kasai and quantum-Tanner cases must be
materialized by pinned, reviewable generator recipes.

Across each split:

- at least half of the cases have an exact, independently sourced reference
  distance;
- at least one quarter are stress cases whose target is only a verified
  published or reproducibly generated upper bound;
- small, medium, and large block-length bands are represented where small is
  `n <= 128`, medium is `129 <= n <= 512`, and large is `n > 512`;
- no two cases have the same construction parameter record;
- no two cases have the same pair of canonical GF(2) row-space fingerprints;
- both X- and Z-logical searches are evaluated, even when a code is symmetric.

The final holdout must contain construction parameters or sizes absent from the
development split.  This makes it a modest extrapolation test rather than a
random duplicate of the development ladder.

## Instance record and provenance

Every source-pool record contains:

- opaque case id;
- family and construction kind;
- `n`, derived `k`, and matrix dimensions;
- paths and SHA-256 hashes for `hx.json` and `hz.json`;
- canonical row-space fingerprints for both checks;
- pinned generator command, source repository, source commit, and environment
  metadata, or a redistribution-safe imported artifact citation;
- expected distance or target upper bound, with `bound_type` equal to `exact`
  or `upper`;
- evidence for the reference value;
- a verified witness whenever `bound_type` is `upper`;
- redistribution and license-review status.

An instance is ineligible unless the curator validates matrix shape, binary
entries, `H_X H_Z^T = 0`, derived rank and `k`, file hashes, safe relative
paths, and the reference contract.  Exact values require exact-algorithm or
paper evidence.  Upper-bound values require an independently verified logical
witness and are never relabeled as exact.

## Selection and cryptographic commitment

The selection tool takes an eligible operator-only source pool and a random
32-byte selection secret.  It stratifies by the fixed family counts, reference
strength, and size bands, then selects and allocates cases deterministically
from the secret.  It writes clear manifests only below an operator-owned
private root outside every Git worktree.

The repository receives a commitment record, not the clear manifests.  The
record contains:

- schema and selection-policy versions;
- the fixed 24/12 counts and family-count table;
- SHA-256 of `random_salt || canonical_development_manifest`;
- SHA-256 of `random_salt || canonical_final_manifest`;
- a commitment to the selection secret;
- source-pool root hash;
- creation timestamp and source commit;
- no case ids, construction parameters, matrix paths, targets, witnesses, or
  per-case hashes.

The random salt and selection secret remain under the private root until
unsealing.  The later public reveal bundle includes the salt, clear manifest,
and selection material needed to reproduce the commitment.  A validator must
fail if a manifest entry, split assignment, matrix hash, or reference value is
changed after commitment.

## Blinding boundary

Proposal agents continue to run through the existing two-plane architecture.
Their container mounts only a dedicated public `proposal-workspace/` and has no
network.  Neither the Git worktree root nor either private split is mounted.
The proposal prompt may contain the public survey, candidate interface,
algorithm history, and sanitized scalar aggregates only.

Development evaluation may publish these aggregate fields:

- total invocations, verified-witness count, target-hit count, and timeout /
  invalid / crash counts;
- normalized upper-bound quality aggregated over all eligible results;
- aggregate wall time and fixed quantiles;
- Pareto decision and a bounded free-text failure-class summary that contains
  no family, size, case, target, or witness information.

It may not publish case rows, family rows, split metadata, matrix dimensions,
or rare subgroups that could identify cases.  Sanitized `LOG.md` files retain
only this allowed aggregate contract.

## Candidate freeze and final-holdout gate

Before any final-holdout invocation, the operator creates a candidate freeze
record containing:

- Git commit and hash of every executable candidate file;
- container image digest and source pin;
- complete method configuration and 300-second limit;
- the committed 20-seed manifest hash;
- development-result summary hash;
- freeze timestamp and repository commit.

The final runner rejects a missing or malformed freeze record, a dirty
candidate worktree, a candidate hash mismatch, image drift, parameter drift,
seed drift, an invalid suite commitment, or evidence of any earlier final run.
After a successful freeze, no algorithm or parameter changes are allowed.  A
changed candidate becomes a new preregistered experiment and cannot reuse the
same sealed final holdout for model selection.

Infrastructure failures may be retried only for the identical method,
instance, seed, image, and configuration.  Every attempt remains in the audit
ledger.  Algorithm timeouts are results, not infrastructure retries.

## Evaluation contract

Paper-validation execution compares the following fixed methods:

- native `random-window-upper-bound`;
- `QDistRndMW`;
- `QDistEvol`;
- `decoderDist`;
- packaged `quotient-coset-upper-bound`.

Each randomized method receives the same committed list of at least 20 seed
values on every instance.  Each invocation has an independently enforced
300-second wall-clock limit.  The controller independently verifies every X or
Z witness against the exposed ephemeral matrix pair before it contributes to
any metric.

Primary metrics are verified-witness rate, target-hit rate, normalized
upper-bound quality, timeout rate, and runtime.  Exact-reference cases report
the ratio between exact distance and returned upper bound.  Upper-reference
cases report target hit / improvement and do not imply exactness.  Rate
intervals use Wilson intervals; runtime and quality contrasts use
instance-clustered bootstrap intervals.  The preregistered primary comparison
is proposal 002 against `decoderDist`; other methods and ablations are
secondary comparisons.

Development aggregates may guide whether to abandon an algorithm, but the
final holdout is evaluated only after the primary candidate and comparison
contract are frozen.

## Files and interfaces

Implementation should keep clear data below an operator-selected private root
and add public contracts along these boundaries:

- a versioned source-pool and split-manifest schema;
- `benchmarks/css_distance_paper_validation/commitment.json` containing only
  the safe commitment record;
- `benchmarks/css_distance_paper_validation/seeds.json` containing at least 20
  fixed seeds;
- a suite preparation/materialization command that writes private manifests
  without printing case details;
- a suite validator that checks counts, allocation, provenance, matrices,
  duplicates, reference strength, commitments, and private-path permissions;
- a candidate-freeze command;
- development and final evaluator modes, with final mode requiring the freeze
  gate;
- a reveal validator for the eventual public manifest and result package.

Command names should extend the existing CSS-distance CLI namespace.  Exact
spelling is an implementation-plan decision, but the cold-review validation
path required by issue #106 must remain possible without private data after
the reveal bundle is published.

## Failure handling

- Insufficient eligible cases in any stratum stops selection; counts are never
  silently rebalanced.
- Unsafe paths, symlinks, non-regular files, hash drift, noncommuting checks,
  rank inconsistencies, invalid witnesses, missing provenance, or unresolved
  redistribution status make a source case ineligible.
- Existing private roots are never overwritten without an explicit new-run
  destination.
- Private manifests and secrets are created with owner-only permissions.
- Proposal containment failure stops all evaluation.
- Final-run attempts before freeze or after candidate drift fail closed and are
  recorded without opening a case.
- Logs and CLI output are passed through the existing private-marker sanitizer;
  no error message may include a case id, path, target, or witness.

## Verification and negative controls

Focused tests and an end-to-end fixture must prove:

1. the clear split contains exactly 24 development and 12 final instances;
2. every family count matches the fixed table and geometric cases are balanced;
3. required exact/upper and size-band coverage holds in each split;
4. source-pool records pass CSS, rank, provenance, hash, and witness checks;
5. duplicate construction records and duplicate canonical row spaces fail;
6. proposal mounts and proposal prompts contain no private suite material;
7. committed logs and summaries contain only allowed aggregate fields;
8. fewer than 20 seeds fails validation;
9. changing a manifest row, matrix, target, witness, split assignment, salt, or
   selection secret breaks commitment verification;
10. final evaluation before candidate freeze fails without opening a case;
11. candidate, image, config, or seed drift after freeze fails without opening
    a case;
12. a valid frozen candidate can evaluate ephemeral cases with the 300-second
    hard cap and independently verified witnesses;
13. a deliberate timeout leaves no evaluator process or container behind;
14. after unsealing, the public reveal reproduces both commitments and contains
    zero private/pre-publication paths.

Completion requires the focused suite, the full repository test suite, search
workspace validation, a leakage scan over tracked files and experiment logs,
and a clean worktree.  Those checks establish that the benchmark is ready for
the five-method run; they do not by themselves establish a publication claim.

## Non-goals

- No exact-distance claim for proposal 002 or any randomized method.
- No exposure of the 12-case holdout before candidate freeze.
- No proposal-agent access to development cases merely because they may later
  become public.
- No tuning on final-holdout outcomes.
- No redistribution of `codeDistancePYPI` or other external baseline artifacts
  until their license metadata is resolved.
- No manuscript drafting before the validation package is executed and
  independently audited.

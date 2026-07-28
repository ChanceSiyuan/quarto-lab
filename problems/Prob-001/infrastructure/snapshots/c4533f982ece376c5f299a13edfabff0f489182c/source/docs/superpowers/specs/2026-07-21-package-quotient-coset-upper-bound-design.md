# Package Quotient-Coset Upper-Bound Search, Draft PR, and Paper Issue

## Goal

Turn blinded proposal 002 into a reviewable experimental AutoQEC capability,
publish the completed autoresearch campaign as a draft pull request, and file a
separate issue defining the evidence required for a credible paper.  The
algorithm remains a randomized CSS logical-witness finder: it certifies an
upper bound and must never be presented as an exact-distance solver.

## Packaging Decision

Three package boundaries were considered:

1. Copy the experiment script into the campaign directory.  This preserves the
   artifact but provides no reusable Python API and little review value.
2. Add an experimental in-process finder with a narrow CLI.  This makes the
   method reusable and testable without promoting it into AutoQEC's exact-first
   distance registry.
3. Register it as a first-class distance method.  This is premature because
   promotion paths intentionally require exact distances and the method has not
   yet received paper-grade validation.

Use option 2.  Add `autoqec_search.quotient_coset_upper_bound` as a pure-Python
module and expose `autoqec-search find-quotient-coset-upper-bound`.  Do not add
the method to the exact-first distance registry and do not depend on the pinned
`codedistance` package.  This keeps the unresolved upstream license conflict
out of the packaged implementation.

## Algorithm and Public API

The module will preserve proposal 002's successful search mechanics:

- encode binary rows as Python integers;
- compute the kernel of the opposite CSS check matrix;
- construct quotient representatives modulo the stabilizer row space;
- bias random combinations toward low-weight representatives;
- add random low-weight stabilizers and greedily descend within the coset;
- search X and Z logical classes and retain the lightest witness; and
- independently verify the selected witness with AutoQEC's existing CSS
  verifier before returning it.

The Python entry point accepts Hx and Hz payloads plus explicit search options:
seed, requested basis (`x`, `z`, or `both`), a no-improvement attempt budget,
and a timeout no greater than 300 seconds.  A fixed seed and attempt budget
make the stochastic work reproducible; the timeout remains a safety ceiling.

The returned object will contain:

- `status: "completed"`;
- `method: "quotient-coset-upper-bound"`;
- `bound_type: "upper"`;
- the verified basis, vector, and upper-bound weight;
- the existing canonical CSS distance payload and verification record; and
- provenance containing the seed and search budgets.

Failure to find a witness, malformed matrices, incompatible dimensions,
invalid options, or failed independent verification raises
`SearchIntegrityError`; no output artifact is written on failure.

## CLI and Artifacts

The CLI will accept `--hx`, `--hz`, `--basis`, `--out`, `--seed`,
`--max-no-improvement`, and `--timeout-seconds`.  The timeout must be positive
and at most 300 seconds.  It writes the canonical verified distance payload to
`--out` and a distinct provenance sidecar, following the existing
`find-upper-bound-witness` conventions.  It prints a one-line completion
summary that calls the result an upper bound.

The campaign README and results report will point to the packaged command and
module rather than a local experiment-worktree path.  The proposal 002 branch
and `LOG.md` remain the immutable experimental provenance.

## Tests

Implementation will be test-driven and cover:

- GF(2) row-space, kernel, quotient-representative, and coset-reduction units;
- deterministic behavior for a fixed seed and attempt budget;
- known public rotated-surface d=3 and d=5 fixtures;
- X-only, Z-only, and both-basis selection;
- malformed, ragged, width-mismatched, and non-binary matrices;
- invalid seed, budget, basis, and timeout options, including the 300-second
  maximum;
- independent rejection of a stabilizer or non-kernel witness;
- CLI output and provenance-sidecar behavior; and
- absence of output artifacts after any failure.

The focused tests and the full repository suite must pass before publication.

## Draft Pull Request

Push `codex/css-distance-autoresearch` and open a draft PR against `main`.  The
PR will include the blinded harness, containment and hard-timeout fixes,
sanitized campaign report, packaged quotient-coset finder, tests, and public
reproduction instructions.  It will explicitly state:

- all results are upper bounds;
- the quality-first winner and practical recommendation are different;
- private holdout inputs were unavailable to proposal agents;
- proposal 002 is experimental and is not registered as an exact distance
  method; and
- the `codedistance` metadata conflict affects only the external baseline and
  requires review before redistribution.

The PR will reference issue #38 but will not close it.

## Paper-Validation Issue

Create a new issue linked to #38 and the draft PR.  Its acceptance criteria are:

- a public benchmark manifest spanning geometric, BB, APM-LDPC, and
  quantum-Tanner families across multiple sizes;
- at least 20 independent seeds per randomized method and instance;
- comparisons with native `random-window-upper-bound`, `QDistRndMW`,
  `QDistEvol`, and `decoderDist` under identical 300-second caps;
- verified-witness rate, target-hit rate, upper-bound quality, runtime
  distributions, confidence intervals, and timeout rate;
- ablations for quotient construction, low-weight sampling, stabilizer
  perturbation, and greedy descent;
- scaling and quality/runtime Pareto plots;
- a separate structured APM/Kasai track;
- committed seeds, aggregate results, witness hashes or public witnesses, and
  reproduction commands; and
- a written novelty assessment deciding whether the contribution supports a
  methods paper, a benchmark/tool paper, or only a technical report.

The issue must not claim that the current pilot is publication-ready and must
not expose any private holdout case-level results.

## Completion Criteria

The work is complete when the packaged finder and CLI are tested and
documented, all repository tests pass, the branch is pushed, a draft PR exists,
and the paper-validation issue links both issue #38 and the PR.

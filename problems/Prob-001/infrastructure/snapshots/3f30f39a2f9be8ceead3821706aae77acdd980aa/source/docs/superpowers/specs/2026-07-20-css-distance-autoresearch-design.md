# Blinded CSS Distance Autoresearch Design

## Goal

Run a Karpathy-style fixed-budget research loop for randomized CSS code-distance
upper bounds.  Each attempt must produce a concrete logical-operator witness,
run for at most 300 seconds per benchmark case, live in its own Git worktree,
and retain a sanitized `LOG.md` from which later proposal rounds can learn.

## Research basis

The public research brief covers random information-set sampling, QDistRndMW,
QDistEvol, decoder-residual search, linked/connected clusters, and
structure-aware APM witnesses.  The starting implementation is
`m-webster/codeDistancePYPI` pinned at
`a4afe9c09bbf5790da9ecc05b65c5b62343979ad`.  Exact SAT, MaxSAT, ILP, MIP,
and exhaustive distance algorithms are excluded from the campaign.

Issue #38 supplies the private evaluation pool.  The operator-selected holdout
contains calibration, discrimination, and stress cases across surface, toric,
bivariate-bicycle, APM/Kasai, and quantum-Tanner CSS codes.  Proposal agents
must not receive case identities, matrices, targets, prior witnesses, or
per-case results.

## Architecture

The campaign has two planes with a one-way interface.

1. The proposal plane receives only the public research brief, pinned source
   metadata, candidate CLI contract, and sanitized aggregate history.  A
   proposal container mounts only a dedicated `proposal-workspace/` directory
   inside the attempt's Git worktree.  It must never mount the worktree root,
   because the root checkout contains the private benchmark ladder.
2. The evaluation plane owns the private holdout.  A networkless, read-only
   evaluator container receives one opaque matrix pair and one seed at a time.
   It can read the candidate and ephemeral input but not the source ladder,
   answer key, other cases, or proposal credentials.

The controller independently checks each claimed vector.  An X witness must
lie in `ker(H_Z)` and outside `row(H_X)`; a Z witness must lie in `ker(H_X)`
and outside `row(H_Z)`.  Passing these checks certifies only
`distance <= weight(witness)`.

## Experiment lifecycle

Each algorithm attempt uses branch
`autoresearch/css-distance/<algorithm-id>` and worktree
`.worktrees/css-distance-<algorithm-id>/`.  The worktree is created before the
proposal is run and immediately receives a `LOG.md` containing the algorithm
id, branch, timestamp, fixed timeout, public objective, and no private case
metadata.

The proposal container writes a single `candidate.py`.  The operator performs
only mechanical contract adaptation when needed (for example, supporting the
documented AutoQEC matrix JSON formats); such adaptation must not add
case-specific algorithm logic.  Screening uses one private seed.  Only accepted
screening candidates advance to three-seed finalist evaluation.

Every candidate/case process group has a hard 300-second deadline.  Timeout,
crash, malformed output, and invalid witness are explicit outcomes.  Candidate
stdout is limited to one JSON object with `status`, `basis`, `vector`, and
`upper_bound`.  The controller logs only aggregate counts, weighted target
hits, normalized quality, total runtime, and the accept/reject decision.

## Ranking and retention

Candidates are compared first by verified weighted target hits, then by
normalized upper-bound quality, verified-witness count, and runtime.  Stress
cases carry more weight than regressions.  No unverified result contributes to
quality.  A result with crashes, timeouts, or invalid claims remains visible in
its worktree log so later public proposals can learn from failure modes without
learning the dataset.

The best candidate is retained only after a fresh finalist run and independent
witness verification.  Results remain upper bounds and are never promoted as
exact Zoo distance evidence.

## Failure handling

- Proposal containment must pass a live canary that cannot read a host-only
  secret and cannot reach an outbound URL.
- Proposal command construction fails closed unless the mounted directory is a
  dedicated public `proposal-workspace/` with no symlinks or private markers.
- Evaluator image metadata must match the pinned starting commit.
- Missing Docker, an unavailable image, or a mismatched image pin stops the run
  before private artifacts are exposed.
- The campaign does not weaken containment to work around infrastructure
  failures.

## Verification

Focused tests cover proposal mount isolation, private materialization,
ephemeral case exposure, independent witness verification, output limits,
process-group timeouts, scoring, and sanitized logs.  A public tiny CSS fixture
smoke-tests every candidate adapter before private screening.  Completion also
requires fresh focused and full test-suite runs plus inspection that every
experiment worktree contains `LOG.md` and no log includes private markers.


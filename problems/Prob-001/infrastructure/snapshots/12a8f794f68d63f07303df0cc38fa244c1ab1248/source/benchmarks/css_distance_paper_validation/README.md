# CSS distance paper-validation source pool

This directory contains the public, split-free matrix source pool used
to materialize the private 24-instance blind development suite and
12-instance sealed final holdout.

Committed artifacts:

- `source_pool.json`: 36 redistribution-approved CSS matrix records.
- `instances/**/hx.json` and `instances/**/hz.json`: public source matrices.
- `seeds.json`: 20 committed seeds; each algorithm run is capped at 300 seconds.
- `curation.json`: source pins, generator commands, evidence keys, and reference types.

The source pool deliberately contains no development/final split assignment.
Use `prepare-css-distance-paper-suite` with an operator-owned private root
outside Git worktrees to create the blind evaluator copy and public commitment.
The committed public seal is `commitment.json`; it contains only aggregate
counts and salted hashes.

## Operator workflow

Choose a private suite root outside Git worktrees and keep it out of proposal
agent mounts. Private suite contents must stay hidden from proposal agents. The private root stores the selection secret, salt, clear
development manifest, clear sealed final manifest, targets, and matrix copies.

```bash
export PRIVATE_SUITE_ROOT=/path/outside/git/worktrees/css-distance-paper-suite

PYTHONPATH=src python3 -m autoqec_search.cli prepare-css-distance-paper-suite \
  --root . \
  --source-pool benchmarks/css_distance_paper_validation/source_pool.json \
  --work-root "$PRIVATE_SUITE_ROOT" \
  --commitment-out benchmarks/css_distance_paper_validation/commitment.json \
  --created-at 2026-07-21T00:00:00Z

PYTHONPATH=src python3 -m autoqec_search.cli validate-css-distance-paper-suite \
  --root . \
  --source-pool benchmarks/css_distance_paper_validation/source_pool.json \
  --work-root "$PRIVATE_SUITE_ROOT" \
  --commitment benchmarks/css_distance_paper_validation/commitment.json
```

Every algorithm run is capped at 300 seconds, and every randomized method must
use the 20 committed seeds from `seeds.json`. Do not open the sealed final
holdout until the candidate freeze is written:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli freeze-css-distance-paper-candidate \
  --candidate-worktree /path/to/candidate-worktree \
  --candidate candidate.py \
  --image-digest sha256:... \
  --method-config method-config.json \
  --seeds benchmarks/css_distance_paper_validation/seeds.json \
  --development-summary development-summary.json \
  --commitment benchmarks/css_distance_paper_validation/commitment.json \
  --out candidate-freeze.json \
  --created-at 2026-07-21T00:00:00Z
```

The candidate freeze pins the Git commit, candidate file hash, image digest,
method configuration, 20 committed seeds, development summary, and suite
commitment before final evaluation.

Curation limitation: six quantum-Tanner additions are toric-product proxy
finite specs generated locally because the pinned quantum-Tanner materializer
was not available in this workspace. They are marked only as finite-spec
coverage and must not be cited as family-wide quantum-Tanner evidence.

Rebuild:

```bash
PYTHONPATH=src python3 scripts/build_css_distance_paper_pool.py --root .
```

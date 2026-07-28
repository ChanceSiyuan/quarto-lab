# CSS Distance Autoresearch

This directory holds the public inputs for randomized upper-bound CSS distance
algorithm experiments. Private holdout materialization is separate from
proposal generation so proposal agents see the survey brief and pinned source
only.

Practical recommendation: proposal 002 is now packaged as
`autoqec-search find-quotient-coset-upper-bound`. It is an experimental
randomized upper-bound witness finder, not an exact-distance method and not a
Zoo promotion source. Each verified witness supplies an upper bound only.

## Public Inputs

- `source.json` pins the starting implementation and baseline method names.
- `research-brief.md` summarizes the SOTA upper-bound methods to consider.
- `proposal-prompt.txt` is generated from those public inputs and is safe to
  send to proposal agents.

Regenerate the prompt after editing the brief or source pin:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli prepare-css-distance-proposal \
  --brief campaigns/examples/css-distance-autoresearch/research-brief.md \
  --source campaigns/examples/css-distance-autoresearch/source.json \
  --out campaigns/examples/css-distance-autoresearch/proposal-prompt.txt
```

## Paper-Validation Suite Boundary

The 24-case blind development suite plus 12-case sealed final holdout is
prepared from the public source pool in
`benchmarks/css_distance_paper_validation/source_pool.json`. The public seal is
`benchmarks/css_distance_paper_validation/commitment.json`; it contains only
aggregate counts and salted hashes.

Operator-only preparation and validation: choose `PRIVATE_SUITE_ROOT` outside Git worktrees.

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

Do not mount the private suite root into proposal containers or proposal-agent
workspaces. Proposal agents may see this campaign directory, the public
research brief, public source pins, and aggregate development feedback only;
they must not see case ids, matrices, targets, witnesses, construction
parameters, clear manifests, the selection secret, salt, or sealed final
holdout allocation.

Each algorithm run is capped at 300 seconds and randomized methods use the 20 committed seeds
in `benchmarks/css_distance_paper_validation/seeds.json`. Before
opening the sealed final holdout, freeze the candidate:

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

## Containers

Build the proposal and evaluator images from the pinned container assets:

```bash
docker build \
  -f containers/css-distance-autoresearch/proposal.Dockerfile \
  -t autoqec-css-distance-proposal:a4afe9c \
  containers/css-distance-autoresearch

docker build \
  -f containers/css-distance-autoresearch/evaluator.Dockerfile \
  -t autoqec-css-distance-evaluator:a4afe9c \
  containers/css-distance-autoresearch
```

The proposal image contains Codex and the pinned `codedistance` baseline. The
evaluator image contains only the runtime needed to execute a candidate
`candidate.py` and the pinned baseline dependencies.

## Run Order

Materialize the private holdout in an operator-only work root:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli materialize-css-distance-holdout \
  --ladder benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2.json \
  --work-root /tmp/autoqec-css-distance
```

Create one isolated algorithm worktree per attempt:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli prepare-css-distance-algorithm \
  --root . \
  --algorithm-id qdist-rndmw-seed1 \
  --created-at 2026-07-19T00:00:00Z \
  --timeout-seconds 300
```

Before sending the public prompt, create a dedicated `proposal-workspace/`
inside the algorithm worktree. Run `run_proposal_canary` against that exact
directory with a host-only path chosen by the operator and require the result
to pass. `build_proposal_command` rejects a worktree root, symlinks, hardlinks,
and private marker names; only the dedicated public directory is mounted at
`/workspace`. Then run the proposal command against the generated prompt.

Evaluate a candidate worktree through the networkless evaluator image:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run-css-distance-candidate \
  --algorithm-id qdist-rndmw-seed1 \
  --candidate-worktree .worktrees/css-distance-qdist-rndmw-seed1 \
  --work-root /tmp/autoqec-css-distance \
  --image autoqec-css-distance-evaluator:a4afe9c \
  --baseline a4afe9c09bbf5790da9ecc05b65c5b62343979ad \
  --phase screening \
  --timeout-seconds 300
```

Use `--phase finalists` only after screening produces an accepted aggregate.
Each candidate worktree receives a sanitized `LOG.md`; only scalar aggregate
metrics are written there.

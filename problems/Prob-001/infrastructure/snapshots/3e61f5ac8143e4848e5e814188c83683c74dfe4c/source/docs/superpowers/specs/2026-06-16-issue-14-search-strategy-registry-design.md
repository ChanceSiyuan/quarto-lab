# Issue #14 Search Strategy Registry Design

## Goal

Add the M2 search-strategy layer for `autoqec-search run`: a pluggable
registry for candidate proposal policies, with `grid`, `random`, and
frontier-guided `adaptive` strategies selectable from the internal campaign
artifacts.

This builds on the issue #10 autoresearch loop and keeps the issue #3 boundary:
AutoQEC owns campaign/search/provenance logic, while `rsinter` owns benchmark
execution. The implementation should make strategy choice reproducible,
auditable, and testable without changing the evaluator contract.

## Scope

In scope:

- a first-class `autoqec_search.strategies` module
- strategy registry with `grid`, `random`, and `adaptive`
- optional `search_space.strategy` contract, defaulting to `grid`
- run-level strategy metadata in `run_spec.json`, `env.json`, summaries, and
  a new `strategy_trace.json`
- runtime candidate provenance field `provenance.strategy`
- run-loop dedupe for repeated strategy proposals
- graceful exhausted-strategy handling
- `autoqec-search compare-strategies` as the human verification route
- `strategies.json`, `strategies.svg`, and `strategies.html` comparison
  outputs
- tests that make adaptive fail if it degenerates to grid order
- README and CLAUDE documentation for selecting and comparing strategies

Out of scope:

- Bayesian optimization, Optuna, Ax, or continuous optimization
- multi-objective frontiers beyond distance plus representative LER
- new candidate generation outside the explicit candidate pool
- distance-method, decoder, or general CSS adapter registries
- expanding the `search-campaign` intake skill beyond documenting the new
  internal strategy selector
- changing `rsinter` invocation or result manifest semantics

## Main Decision

Use a small registry plus a dedicated comparison command.

The normal `run` command should be able to use any registered strategy, but it
should stay focused on executing one campaign run. Strategy comparison is a
separate command:

```bash
autoqec-search compare-strategies \
  --root . \
  --campaign rotated-surface-baseline \
  --strategies grid adaptive \
  --budget-candidates 3 \
  --metrics benchmarks/fixtures/strategy-comparison/rotated-surface.json \
  --out results/search/rotated-surface-baseline/<run-id>/strategies.html
```

This keeps ordinary runs light while giving issue #14 a reviewable artifact
with numeric teeth: adaptive must reach an equal-or-better frontier quality
than grid in fewer evaluations for the comparison fixture.

## Strategy Module

Add `src/autoqec_search/strategies.py`.

Core public concepts:

- `StrategyConfig`
  - `name: str`
  - `params: dict[str, object]`
- `StrategyState`
  - search-space candidate specs
  - current frontier
  - attempted candidate ids
  - deduped candidate ids
  - seed
  - max candidate budget
  - number of completed evaluations
- `StrategyProposal`
  - candidate spec
  - strategy name
  - short reason for trace output
- `Strategy` protocol
  - `propose(state) -> list[StrategyProposal]`
- registry helpers
  - `get_strategy(name)`
  - `available_strategies()`
  - `strategy_config_from_search_space(search_space)`

The strategy module must not read or write files, call git, call `rsinter`, or
mutate candidate artifacts. It only chooses candidate specs from the current
explicit search-space pool.

## Search Space Contract

`search_space.json` gains an optional `strategy` field:

```json
{
  "campaign_id": "rotated-surface-baseline",
  "mode": "explicit_list",
  "strategy": {
    "name": "adaptive",
    "params": {}
  },
  "candidate_specs": []
}
```

Rules:

- missing `strategy` means `{"name": "grid", "params": {}}`
- supported names are `grid`, `random`, and `adaptive`
- `params` defaults to `{}`
- invalid strategy names or invalid parameter shapes are run-level errors
- the existing `explicit_list` mode remains the only production search-space
  mode for this issue

Candidate `provenance` stays concise but becomes extensible:

```json
{
  "kind": "seed",
  "label": "repo-example-d3",
  "strategy": "adaptive"
}
```

Search-space input provenance may omit `strategy`; the run loop writes a copy
with `strategy` filled in for evaluated or crashed candidate payloads. This
records which policy actually proposed the candidate without asking humans to
hand-author that field.

## Run Spec And Environment Metadata

Autoresearch `run_spec.json` records:

- existing issue #10 fields
- `strategy`: selected strategy config

`env.json` records:

- existing issue #10 fields
- `strategy_name`
- `strategy_params`

`summary.md` and `run-summary.html` include the strategy name, seed, number of
evaluated proposals, number of deduped proposals, and stop reason. Existing
leaderboard and frontier semantics stay unchanged.

## Strategy Trace

Each autoresearch run writes:

```text
results/search/<campaign>/<run-id>/strategy_trace.json
```

The trace contains:

- campaign id
- run id
- strategy config
- ordered proposal events
- for each event:
  - candidate id
  - reason
  - action: `evaluated`, `deduped`, or `exhausted`
  - verdict when evaluated
  - representative frontier quality after evaluation when available

`experiment-log.tsv` remains evaluation-only. Deduped proposals are trace
events, not experiment rows, because they did not consume evaluator budget.

## Strategy Behavior

### Grid

`grid` preserves M1 behavior:

- iterate `candidate_specs` in file order
- stop at `max_candidates`
- rely on run-loop wall-clock checks before each evaluation

This is the default and the compatibility baseline.

### Random

`random` uses the same explicit candidate pool, but orders candidates by a
deterministic shuffle seeded from the effective run seed.

Initial implementation rules:

- no new candidates are synthesized
- every candidate id appears at most once in the shuffled order
- same seed plus same search space gives the same proposal sequence
- different seeds may produce different proposal sequences

### Adaptive

`adaptive` is frontier-guided over the explicit pool.

Initial implementation rules:

- cold start chooses the smallest-distance candidate not yet attempted
- once frontier exists, prefer candidates near frontier members
- near means same distance first if there may be an improvement, then the next
  larger available distance
- when a candidate at an existing distance fails to improve that distance's
  frontier, later same-distance repeats are deprioritized
- when no useful candidate remains, return no proposals

For the rotated-surface fixture this makes adaptive move quickly from d=3 to
d=5 and d=7 after establishing the first frontier point, instead of spending
budget on repeated poorer d=3 candidates in file order.

The first adaptive strategy is deliberately simple. It is meant to prove the
registry and frontier feedback loop, not to be a general optimizer.

## Run Loop Data Flow

For `autoqec-search run`:

1. load and validate campaign, suite, task, and search space
2. derive the strategy config, defaulting to grid
3. create or validate the worktree and run skeleton
4. write strategy metadata into `run_spec.json` and `env.json`
5. initialize strategy state from candidate specs, seed, frontier, and resume
   state
6. ask the strategy for proposals before each evaluation
7. dedupe proposals against candidate ids already terminal in this run
8. evaluate the first non-duplicate proposal
9. update frontier, aggregates, and strategy trace
10. stop on wall-clock exhaustion, max-candidate exhaustion, or empty proposals
11. finalize the same report and promotion artifacts as M1

Resume must reconstruct attempted ids and frontier from validated existing
candidate outputs before asking the strategy for more proposals. Completed
candidates are not rewritten.

## De-Dupe Semantics

The run loop owns dedupe, not individual strategies.

Rules:

- a candidate with a terminal completed or crash outcome is not evaluated again
  in the same run
- a duplicate proposal is recorded in `strategy_trace.json` as `deduped`
- duplicate proposals do not append to `experiment-log.tsv`
- duplicate proposals do not update manifest mtimes
- if every proposal is duplicate and the strategy has no fresh candidate, the
  run stops with `search-space-exhausted`

This protects the evaluator from bad or experimental strategies and gives issue
#14 its duplicate-proposal negative control.

## Stop Reasons

`run_status.json` adds a `stop_reason` field. Allowed values:

- `max-candidates`
- `wall-clock`
- `search-space-exhausted`
- `completed`

For compatibility, existing committed M1 runs may either be migrated to include
`stop_reason` or the loader may accept missing `stop_reason` only for older
runs without strategy metadata. New autoresearch runs must write it.

The exhausted-strategy negative control must produce a finalized run with
`stop_reason: "search-space-exhausted"` and zero evaluated candidates.

## Compare Strategies Command

Add:

```bash
autoqec-search compare-strategies \
  --root . \
  --campaign <campaign-id> \
  --strategies grid adaptive \
  --budget-candidates <n> \
  --metrics <candidate-metrics.json> \
  --out <path>
```

The command creates three sibling artifacts. If `--out` is an HTML path, the
JSON and SVG use the same stem.

```text
strategies.json
strategies.svg
strategies.html
```

The command does not run `rsinter`. It reads deterministic candidate quality
from one of two sources:

1. `--metrics <path>`: a JSON object keyed by candidate id, with `distance` and
   `representative_ler` for every candidate that may be proposed.
2. existing completed run manifests for the campaign when `--metrics` is
   omitted. In that mode the command can only compare candidates whose
   representative task/decoder/p points are already present.

The metrics model is only for strategy-order verification, not for replacing
real benchmark runs.

The JSON artifact records:

- compared campaign id
- strategies
- candidate budget
- per-strategy proposal order
- per-evaluation frontier quality sequence
- final quality
- number of evaluations needed to reach the winning reference quality
- pass/fail assertion details

The SVG plots frontier quality versus evaluation count. The HTML embeds the SVG
and JSON table as a self-contained offline review page.

CLI exit behavior:

- exit 0 when adaptive reaches an equal-or-better frontier quality than grid in
  fewer evaluations under the comparison fixture
- exit nonzero with a clear assertion message when it does not
- exit nonzero for unknown strategies or incomparable/missing candidate metrics

## Frontier Quality For Comparison

Comparison quality is single-objective and deterministic:

```text
(max_distance_kept, -representative_ler_at_that_distance)
```

Higher is better. This matches the M1 frontier rule while staying within issue
#14 scope. Multi-objective Pareto frontiers are explicitly deferred.

## Error Handling

Run-level errors:

- unknown strategy name
- invalid strategy params
- malformed strategy field in search space
- invalid candidate id produced by a strategy
- strategy returning a candidate not in the explicit search-space pool
- invalid resume skeleton strategy metadata

Candidate-level errors remain issue #10 crash rows:

- missing matching Zoo artifacts
- invalid candidate spec
- structure failure
- distance mismatch
- rsinter failure
- malformed rsinter output

Empty proposal lists are not errors. They finalize the run with
`search-space-exhausted` unless another stop reason, such as wall clock, was
already reached.

## Testing

Unit tests:

- registry lists `grid`, `random`, and `adaptive`
- unknown strategy raises a clear `SearchIntegrityError`
- missing `search_space.strategy` normalizes to grid
- `random` is stable for a fixed seed
- `adaptive` prefers frontier-neighbor and next-distance candidates over poor
  same-distance repeats
- duplicate proposals are filtered by the run-loop dedupe helper
- exhausted proposals produce `search-space-exhausted`

Schema and loader tests:

- `search-space.schema.json` accepts valid strategy configs
- schema rejects unknown strategy names
- candidate provenance accepts optional `strategy`
- new `run_spec` strategy metadata validates
- old committed M1 runs still load

Run-loop tests with fake `rsinter`:

- grid preserves existing order
- random order is deterministic for a seed
- adaptive reaches the comparison target in fewer evaluations than grid on a
  fixture with repeated poor d=3 candidates
- duplicate strategy test hook does not rewrite a completed manifest
- exhausted strategy test hook finalizes with zero evaluations and stop reason
  `search-space-exhausted`
- resume reconstructs strategy state without recomputing terminal candidates

Compare command tests:

- writes `strategies.json`, `strategies.svg`, and `strategies.html`
- HTML is self-contained and contains the assertion summary
- adaptive passes the numeric assertion on the fixture
- replacing adaptive with a grid-order stub makes the assertion fail
- unknown strategy exits nonzero

Documentation tests:

- README mentions `search_space.strategy`
- README mentions `autoqec-search compare-strategies`
- CLAUDE mentions the issue #14 strategy registry route
- docs mention `strategy_trace.json`
- a committed `rotated-surface-strategy-fixture` campaign and
  `benchmarks/fixtures/strategy-comparison/rotated-surface.json` provide the
  comparison teeth without perturbing the M1 baseline campaign

## Verification

Primary automated verification:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_strategies.py \
  tests/test_search_run_loop.py \
  tests/test_search_run_cli.py \
  tests/test_search_load.py \
  tests/test_search_docs.py -q
```

Workspace validation:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Human route:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-strategies \
  --root . \
  --campaign rotated-surface-strategy-fixture \
  --strategies grid adaptive \
  --budget-candidates 3 \
  --metrics benchmarks/fixtures/strategy-comparison/rotated-surface.json \
  --out /tmp/autoqec-strategies.html
```

Expected result:

- command exits 0
- `strategies.html` opens offline
- `strategies.svg` shows adaptive reaching the target with fewer evaluations
- `strategies.json` records the numeric assertion
- changing adaptive to grid-order behavior makes the assertion fail

## Implementation Order

1. Add strategy schema fields and provenance schema extension.
2. Add `strategies.py` with registry, state, and the three strategies.
3. Refactor candidate selection in `run_loop.py` to use strategy proposals.
4. Add strategy metadata and `strategy_trace.json` rendering.
5. Add the strategy-comparison fixture campaign and metrics file.
6. Add `compare-strategies` model, SVG/HTML renderers, and CLI command.
7. Update docs.
8. Add and run the focused tests.

This order keeps the public contract and unit-testable strategy logic in place
before touching the worktree/evaluation loop.

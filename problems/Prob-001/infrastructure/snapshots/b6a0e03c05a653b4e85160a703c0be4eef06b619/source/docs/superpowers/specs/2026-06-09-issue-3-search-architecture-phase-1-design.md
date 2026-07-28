# Issue #3 Search Architecture Phase 1 Design

## Goal

Add the first search-layer scaffolding for `AutoQEC` so the repository can hold:

- human-authored campaign definitions
- reusable benchmark contracts
- resumable search-run records
- a minimal Python package and CLI for validating and materializing that structure

This phase establishes the storage and contract boundaries proposed in issue `#3` without yet integrating a real benchmark executor.

## Scope

This design covers:

- new top-level scaffolding under `campaigns/`, `benchmarks/`, and `results/search/`
- a new Python package under `src/autoqec_search/`
- a new standalone CLI entry point, `autoqec-search`
- JSON schemas for campaign, search-space, benchmark, run, candidate, and result-manifest records
- one repository-committed example campaign
- one repository-committed example run
- one CLI workflow that generates a new placeholder run from a campaign definition
- focused tests for validation, run initialization, and example consistency

## Non-Goals

- no `rstim` or `rsinter` integration in this phase
- no real benchmark execution
- no promotion workflow from search results into `zoo/`
- no new project skill implementation in this phase
- no cross-package merge of `autoqec_zoo` and `autoqec_search`
- no attempt to finalize every future search/evaluation field beyond what Phase 1 needs

## Main Decision

Phase 1 should build a **separate search layer** rather than extending `zoo/` directly.

The repository already has distinct meanings for its existing top-level layers:

- `.knowledge/` stores papers and notes
- `zoo/` stores curated source-of-truth code, evidence, and promoted instances

Search activity has a different lifecycle:

- campaigns express intent before a run exists
- benchmark contracts are reusable across campaigns
- run outputs are runtime artifacts rather than curated facts

Because those responsibilities differ, the search layer should live beside `zoo/`, not inside it.

## Phase Boundary

This work intentionally stops at a minimal, validated placeholder workflow:

1. define a campaign
2. validate referenced benchmark contracts
3. freeze a run into `results/search/`
4. materialize placeholder candidate and result records
5. inspect that run through a lightweight CLI summary

That keeps the first implementation useful while avoiding fake promises about benchmark execution that does not yet exist.

## Directory Layout

The Phase 1 repository shape should be:

```text
campaigns/
  README.md
  examples/
    rotated-surface-baseline/
      campaign.json
      search_space.json
      notes.md

benchmarks/
  README.md
  tasks/
    rotated-memory-x-cdep-v1.json
  decoders/
    placeholder-noop-decoder-v1.json
  suites/
    rotated-surface-baseline-v1.json
  schemas/
    campaign.schema.json
    search-space.schema.json
    benchmark-task.schema.json
    decoder-config.schema.json
    benchmark-suite.schema.json
    run-spec.schema.json
    candidate.schema.json
    result-manifest.schema.json

results/
  search/
    README.md
    rotated-surface-baseline/
      2026-06-09-example/
        run_spec.json
        env.json
        leaderboard.csv
        frontier.json
        summary.md
        candidates/
          rotated-surface-d3-example/
            candidate.json
            structure.json
            distance.json
            evaluations/
              rotated-memory-x-cdep-v1/
                placeholder-noop-decoder-v1/
                  manifest.json

src/
  autoqec_search/
    __init__.py
    cli.py
    load.py
    init_run.py
    render.py
```

## Layer Responsibilities

### `campaigns/`

This is the human-authored intent layer.

It stores:

- campaign objective
- budget and stopping policy
- search-space definition
- human notes and rationale

It does not store runtime output.

### `benchmarks/`

This is the reusable evaluation-contract layer.

It stores:

- benchmark tasks
- decoder configurations
- suites that combine those tasks and decoders
- JSON schemas used by the search package

It does not store campaign-local observations or run-specific output.

### `results/search/`

This is the runtime layer.

It stores:

- frozen run specs
- environment metadata
- candidate-level artifacts
- placeholder or future real evaluation outputs
- human-readable summaries

These files are important research records, but they are not curated source-of-truth knowledge in the same sense as `zoo/`.

## Data Contracts

Phase 1 should define small, explicit contracts rather than broad future-proof object models.

### `campaign.json`

This file defines the human intent for one campaign.

Required information should include:

- `id`
- `title`
- `objective`
- `family_id` or target family class
- `default_suite_id`
- budget fields
- stop conditions
- random-seed policy
- output/run naming policy where needed

The important rule is that `campaign.json` points to a reusable suite by id rather than embedding benchmark tasks directly.

### `search_space.json`

This file defines the candidate space for a campaign.

Phase 1 should support a modest structure:

- candidate family
- parameter dimensions
- enumerated values or ranges
- constraints
- optional hand-authored seed candidates

It does not need to encode a full search algorithm in this phase.

### Benchmark Tasks

Each file under `benchmarks/tasks/` defines one benchmark task contract.

Phase 1 should include enough structure to state:

- task id and title
- observable or benchmark target
- noise model label
- expected input type
- result metric names

The example task can remain placeholder-level as long as it is explicit that no real runner exists yet.

### Decoder Configs

Each file under `benchmarks/decoders/` defines one decoder contract.

Phase 1 should allow:

- decoder id and title
- backend family label
- parameter payload
- execution status such as `placeholder`

The first example decoder should be a deliberate no-op placeholder, not a fake real decoder.

### Benchmark Suites

Each file under `benchmarks/suites/` defines one reusable suite.

It should contain:

- `id`
- `title`
- `task_ids`
- `decoder_ids`
- optional shared settings

Suites are the bridge between campaigns and reusable benchmark contracts.

### `run_spec.json`

This file freezes the inputs for one concrete run.

It should include:

- `campaign_id`
- `run_id`
- `suite_id`
- provenance such as creation time and CLI version
- selected candidate ids
- copied or normalized settings needed to replay the run definition

This record is generated by the CLI rather than hand-authored.

### `candidate.json`

This file identifies one candidate inside one run.

It should include:

- `candidate_id`
- `campaign_id`
- `run_id`
- source family or construction id
- candidate parameters
- provenance describing whether the candidate came from enumeration, sampling, or seeds
- lifecycle status

The directory layout and payload must agree on ids.

### `manifest.json`

This file records one candidate result under one task and one decoder.

For Phase 1 it should support placeholder results with a stable shape, including:

- `campaign_id`
- `run_id`
- `candidate_id`
- `task_id`
- `decoder_id`
- `status`
- placeholder metrics or null result fields
- provenance and timestamps

The key decision is that a manifest is still emitted in placeholder runs. Later execution integrations can fill the same contract with real metrics instead of changing the filesystem structure.

## Example Data Policy

Phase 1 should include both kinds of examples:

1. a committed static example campaign under `campaigns/examples/`
2. a committed static example run under `results/search/`

The example run should use the same directory shape that future real runs will use.

This serves two purposes:

- humans can inspect the intended layout without running commands
- tests can validate that the repository always contains one coherent reference example

The CLI must also be able to materialize a fresh placeholder run from the example campaign so the dynamic workflow is exercised too.

## CLI Design

The CLI should be a standalone entry point:

```text
autoqec-search
```

It should not be nested under `autoqec-zoo` in Phase 1.

The reason is boundary clarity:

- `autoqec-zoo` manages curated Zoo data
- `autoqec-search` manages campaign, benchmark, and run-layer data

They can share repository conventions while remaining separate tools.

### `validate`

Command purpose:

- validate search-layer source and example files

Checks should include:

- schema validation for campaigns, search spaces, tasks, decoders, suites, runs, candidates, and manifests
- campaign reference integrity
- suite reference integrity
- run/candidate/manifest directory-to-payload consistency

This command is the Phase 1 gate that catches malformed data before a run is created or committed.

### `init-run`

Command purpose:

- create a new placeholder run directory from a campaign definition

Expected outputs:

- `run_spec.json`
- `env.json`
- `summary.md`
- `frontier.json`
- `leaderboard.csv`
- candidate directories
- one placeholder manifest per candidate/task/decoder combination

The command must not execute a real benchmark in this phase.

If the target run directory already exists, the command should fail unless `--force` is supplied.

### `show`

Command purpose:

- print a concise summary of an existing run

Expected summary content:

- campaign id
- run id
- suite id
- candidate count
- task ids
- decoder ids
- whether the run contains placeholder manifests

This is intentionally lightweight and should remain a text-only inspection aid in Phase 1.

## Package Structure

The new Python package should mirror the direct style already used by `autoqec_zoo`.

Recommended layout:

```text
src/autoqec_search/
  __init__.py
  cli.py
  load.py
  init_run.py
  render.py
```

Responsibilities:

- `cli.py`: argument parsing and exit-code handling
- `load.py`: JSON loading, schema validation, and cross-file integrity checks
- `init_run.py`: materialize a run directory from campaign and suite inputs
- `render.py`: render lightweight text and CSV outputs used by `summary.md`, `leaderboard.csv`, and `show`

Phase 1 should prefer plain dictionaries and focused helper functions over a large typed domain model. The surrounding repository already uses that style effectively, and the search contracts are still settling.

## Error Handling

`autoqec_search` should define its own integrity exception, parallel to `autoqec_zoo.load.IntegrityError`.

Suggested name:

```text
SearchIntegrityError
```

It should be raised for:

- schema failures
- missing referenced suite/task/decoder ids
- directory/payload id mismatches
- malformed run layout
- attempts to create an already-existing run without explicit overwrite

The CLI should catch these failures, print a concise actionable message, and return a non-zero exit code.

## Integrity Rules

At minimum, Phase 1 should enforce these cross-file checks:

- `campaign.default_suite_id` exists under `benchmarks/suites/`
- every suite `task_id` exists under `benchmarks/tasks/`
- every suite `decoder_id` exists under `benchmarks/decoders/`
- example run `run_spec.json` references an existing campaign and suite
- every `candidate.json` agrees with its directory path for campaign, run, and candidate ids
- every `manifest.json` agrees with its directory path for candidate, task, and decoder ids

Those checks are more important than adding many optional fields. The first job of Phase 1 is to ensure the filesystem contracts do not drift.

## Testing

Tests should be focused on the Phase 1 behavioral surface.

### Loader and Validation Tests

Cover:

- successful loading of the example campaign, suite, and run
- failure when a campaign references a missing suite
- failure when a suite references a missing task or decoder
- failure when candidate or manifest payload ids disagree with directory names
- failure when `init-run` targets an existing run without `--force`

### CLI Tests

Cover:

- `python -m autoqec_search.cli validate`
- `python -m autoqec_search.cli init-run`
- `python -m autoqec_search.cli show`
- expected non-zero exit codes for missing paths or malformed inputs

### Repository Example Consistency Tests

Cover:

- the committed example run validates successfully
- a newly generated run from the example campaign contains the expected file set
- rendered `summary.md` and `leaderboard.csv` contain the key expected fields without relying on brittle whole-file snapshots

## Acceptance Criteria

Phase 1 is complete when all of the following are true:

1. `pyproject.toml` exposes a new `autoqec-search` CLI entry point.
2. The repository contains committed scaffolding under `campaigns/`, `benchmarks/`, and `results/search/`.
3. The repository contains one coherent example campaign and one coherent example run.
4. `autoqec-search validate` succeeds against the committed example data.
5. `autoqec-search init-run` can generate a new placeholder run from the example campaign.
6. `autoqec-search show` prints a correct summary for the example run.
7. New search-layer tests pass without disturbing the existing `autoqec_zoo` test organization.

## Implementation Notes

Phase 1 should keep the implementation conservative:

- reuse the existing repository pattern of JSON source records plus Python validators
- avoid adding empty workflow shells for future skills or benchmark runners
- keep the example task and decoder explicit about being placeholders
- keep all generated placeholder records machine-readable, even when they do not contain real metrics yet

That gives the repository a durable shape now without pretending the execution layer already exists.

## Follow-On Work

This design intentionally sets up the next implementation slices:

1. connect one real benchmark path to `rstim` or `rsinter`
2. replace placeholder manifests with real result manifests
3. add candidate comparison and promotion workflows
4. connect promoted outputs back into `zoo/`

Those follow-on steps should build on the filesystem and CLI contracts established here rather than replacing them.

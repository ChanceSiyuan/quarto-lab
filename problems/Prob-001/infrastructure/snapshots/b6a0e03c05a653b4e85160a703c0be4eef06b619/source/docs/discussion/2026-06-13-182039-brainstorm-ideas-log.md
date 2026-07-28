# Ideas Session — 2026-06-13 18:20

## Initial Request

User asked: "$sci-brain:brainstorm-ideas 查看issue#8 完成这个issue"

## Loaded Instructions

- Project AGENTS instructions point to `CLAUDE.md`.
- `CLAUDE.md` identifies this repository as the AutoQEC coordination and knowledge harness.
- For search-layer work, `CLAUDE.md` says `campaigns/`, `benchmarks/`, and `results/search/` are the relevant boundaries and `python3 -m autoqec_search.cli validate --root .` is the validation command.

## GitHub Issue Context

Fetched issue #8 from `nzy1997/AutoQEC`: "Add real benchmark contracts, a golden-fixture catalog, and an autoqec-search preflight doctor".

The issue asks to replace placeholder benchmark contracts with real `rsinter`-backed decoder/task/suite contracts, update schemas for real decoder metadata and campaign/evaluation budgets, commit a golden fixture catalog under `benchmarks/fixtures/rotated-d3/`, and add `autoqec-search preflight [--root .] [--html OUT]`.

Verification requested by the issue:

- `autoqec-search preflight --root .` prints all PASS rows and exits 0.
- `autoqec-search preflight --root . --html /tmp/doctor.html` emits an all-green self-contained HTML page.
- Negative controls fail when `rsinter` is hidden, fixture errors exceed shots, or a real decoder omits `impl_key`.

## Working Direction

Treat the issue body as the implementation spec and inspect the existing search-layer code before editing. Follow test-first implementation where behavior changes are needed.

## Implementation Checkpoint

Implemented issue #8 by replacing the placeholder decoder contract with three real `rsinter` decoder configs:

- `rmatching-default-v1`
- `rbposd-default-v1`
- `rilpqec-default-v1`

Updated the rotated memory task contract with `p_list`, `rounds_policy`, and per-evaluation `collection.max_shots` / `collection.max_errors`. Updated the campaign schema and example campaign to use `budget.wall_clock_seconds` and `budget.max_candidates`, plus explicit stop conditions.

Added committed golden fixture files:

- `benchmarks/fixtures/manifest.json`
- `benchmarks/fixtures/rotated-d3/results.jsonl`
- `benchmarks/fixtures/rotated-d3/dem.txt`
- `benchmarks/fixtures/rotated-d3/expected.json`

Added `src/autoqec_search/preflight.py` and wired `autoqec-search preflight [--root .] [--html OUT]` into the CLI. The doctor checks:

- workspace contract loading through the existing loader
- `rsinter` discovery and successful non-empty `--version` output
- fixture manifest, DEM, results JSONL, expected LER, and CI consistency

Updated the committed example run to follow the new suite's three decoder IDs while keeping the run artifacts placeholder-valued, since issue #8 explicitly keeps full benchmark execution out of scope.

## Verification

Relevant issue #8 tests:

```text
python3 -m pytest tests/test_search_preflight.py tests/test_search_cli.py tests/test_search_load.py tests/test_search_source_data.py tests/test_search_init_run.py
29 passed
```

Search-layer validation:

```text
env PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
validated search workspace under .: 1 campaigns, 1 suites, 1 runs
```

Preflight with local `rsinter`:

```text
env PATH=/Users/nzy/mcode/rstim/target/release:$PATH PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
PASS workspace contracts
PASS rsinter available
PASS fixture manifest
PASS fixture rotated-d3
```

HTML preflight:

```text
env PATH=/Users/nzy/mcode/rstim/target/release:$PATH PYTHONPATH=src python3 -m autoqec_search.cli preflight --root . --html /private/tmp/doctor.html
all rows PASS and HTML written
```

Negative controls:

- Hidden backend with `PATH=/usr/bin` and the same Python environment: `rsinter available` row FAIL and command exits 1.
- Corrupted fixture with `errors=1001` and `shots=1000`: `fixture rotated-d3` row FAIL and command exits 1.
- Removed `impl_key` from a temporary real decoder config: `validate` rejects it with `'impl_key' is a required property`.

Full test suite:

```text
python3 -m pytest
85 passed, 1 failed, 7 deselected
```

The single failure is unrelated to issue #8: `tests/test_source_data.py::test_repo_uses_single_project_kb_layout` fails because `.claude/survey` exists in the local checkout. That directory was not created by this issue implementation and was left untouched.

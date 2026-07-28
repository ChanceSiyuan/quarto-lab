# Issue 46 Quantum Tanner Autoresearch Workflow Design

Issue: #46, "[M5] Document the quantum Tanner autoresearch operating workflow"

## Context

The repository already contains the concrete workflow pieces that this
documentation must connect:

- `campaigns/examples/quantum-tanner-autoresearch/campaign.json`
- `campaigns/examples/quantum-tanner-autoresearch/search_space.json`
- `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`
- `benchmarks/suites/quantum-tanner-rbposd-p001-v1.json`
- `benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json`
- `benchmarks/baselines/rotated-surface-single-logical-p001.json`
- `autoqec-search preflight`, `validate`, `run`, `report`, and
  `compare-surface-copy`

The missing deliverable is an operator-facing English workflow that explains
how a human starts and resumes a local Codex CLI autoresearch run, what files
are produced, where approval gates live, and why upper-bound distances remain
screening evidence rather than exact Zoo-promotion evidence.

## Non-Interactive Decisions

This Agent Desk run is non-interactive, so the standing policy resolves choices
from the issue text and repository context.

1. Put the operator page at
   `campaigns/examples/quantum-tanner-autoresearch/README.md`. This keeps the
   workflow beside the campaign, search space, fixture catalog, witnesses, and
   baseline references it names.
2. Use a time-bounded `autoqec-search run` smoke command rather than `eval`.
   The quantum Tanner screening gate and `screening.json` artifacts are
   implemented in the autoresearch run path.
3. Use source-checkout command blocks with
   `PYTHONPATH=src python3 -m autoqec_search.cli ...`, while also naming the
   installed `autoqec-search ...` command forms in prose.
4. Use the issue #45 command shape for comparison:
   `compare-surface-copy --root ... --run ... --baseline ... --out ...`.
5. Keep the page local-only and point cluster execution to issue #20 instead
   of designing SLURM behavior here.
6. Add tests under `tests/test_search_docs.py` with two
   `quantum_tanner_autoresearch_workflow` tests so the requested filtered test
   command reports `2 passed`.

## Approaches Considered

Recommended: add a campaign-local README and focused documentation tests. This
is the narrowest change that gives a new operator a followable page with real
paths and commands.

Alternative: add a general page under `docs/`. That would be discoverable from
a top-level docs tree, but this repo currently keeps the quantum Tanner
campaign inputs under `campaigns/examples/quantum-tanner-autoresearch/`, and a
general page would have to duplicate those paths from farther away.

Alternative: update only `README.md` and `CLAUDE.md`. Those files already carry
broad search-layer guidance, but issue #46 asks for an end-to-end workflow page,
not another paragraph in the general command reference.

## Documentation Shape

Create `campaigns/examples/quantum-tanner-autoresearch/README.md` with:

- prerequisites and preflight;
- workspace validation and the campaign/catalog artifacts to inspect;
- the time-bounded local run command;
- resume behavior;
- the expected run tree under `.worktrees/<run-id>/results/search/...`;
- report generation;
- surface-copy comparison using the single-logical p=0.001 baseline;
- human approval gates;
- the warning that upper-bound distances must not be promoted as exact Zoo
  distances;
- the local-only scope and a pointer to issue #20 for SLURM.

## Testing

Extend `tests/test_search_docs.py` with two tests:

1. The workflow page contains bash command blocks for preflight, validation,
   run, report, and surface-copy comparison. The test also rejects placeholder
   command text so the page does not drift into hypothetical syntax.
2. The workflow page states `p=0.001`, states the copied-surface formula
   `1 - (1 - P_single)^k`, and states that upper-bound distances must not be
   promoted as exact Zoo distances. The same test mutates an in-memory copy of
   the page to `p=0.01`, removes the formula, and removes the no-promotion
   warning, then confirms each mutation fails the guardrail assertions.

Required verification:

```bash
PYTHONPATH=src pytest -q tests/test_search_docs.py -k quantum_tanner_autoresearch_workflow
PYTHONPATH=src python3 -m pytest
```

## Out of Scope

No CLI changes, SLURM execution, project-board automation, new decoder
configuration, new benchmark data, or Zoo promotion behavior changes are part
of this issue.

## Self-Review

No placeholders remain. The selected workflow page path is within the issue's
allowed output locations. Commands and artifact names come from existing
repository files and CLI subcommands. The testing plan covers the issue's
positive checks and the requested negative controls.

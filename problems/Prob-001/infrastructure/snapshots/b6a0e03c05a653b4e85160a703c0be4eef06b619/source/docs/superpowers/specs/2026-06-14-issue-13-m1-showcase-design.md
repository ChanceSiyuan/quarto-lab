# Issue #13 M1 Showcase Design

## Goal

Finish the M1 milestone by adding the missing human front door and a committed
end-to-end showcase for the existing search pipeline.

Issue #13 closes the loop that issues #8 through #12 built in pieces:

```text
natural-language campaign request
  -> search-campaign intake and approval
  -> campaign/search-space files
  -> preflight/eval/run/report/promote pipeline
  -> committed demo report
  -> promoted instance visible in Zoo browse artifacts
```

The selected delivery model is: run a small real `rsinter` demo once for the
committed artifacts, but keep automated e2e tests fixture-backed and offline.
This gives M1 a credible final result without making CI depend on local backend
availability.

## Scope

In scope:

- `skills/search-campaign/SKILL.md`
- a committed example transcript under `skills/search-campaign/`
- a completed committed demo run under
  `results/search/rotated-surface-baseline/m1-demo/`
- demo run artifacts:
  - `run_spec.json`
  - `env.json`
  - `experiment-log.tsv`
  - `leaderboard.csv`
  - `frontier.json`
  - `summary.md`
  - `run-summary.html`
  - `report.html`
  - `run_status.json`
  - `promotion_summary.json`
  - candidate `candidate.json`, `structure.json`, `distance.json`
  - candidate `artifacts/instance.json`, `artifacts/hx.json`,
    `artifacts/hz.json`
  - at least one completed `manifest.json` with a real d=3 LER point
- an offline `tests/test_search_e2e.py`
- documentation updates in `README.md` and `CLAUDE.md`
- docs tests that assert the quick-start and M1 final-result entry points stay
  documented

Out of scope:

- the full issue #5 benchmark skill series
- `benchmark-code`, `bench-runner-distance`, `bench-runner-mc-ler`, or
  `compare-candidates` skills
- M2 general CSS-to-circuit support
- new decoders or decoder parameter registries
- pushing autoresearch branches or opening PRs from the run command
- large benchmark sweeps

## Main Decision

Implement issue #13 as an M1 showcase bundle, not as another backend feature.

The repository already has the core M1 mechanics:

- search contracts and preflight
- single-candidate eval
- time-bounded autoresearch run loop
- visual report rendering
- Zoo promotion

The missing piece is a user-facing entry path plus a durable proof that the
whole path works. The implementation should therefore add a thin project skill,
commit one small completed run, and test the final artifacts end to end.

## Project Skill

Create `skills/search-campaign/SKILL.md` in the same concise style as
`generate-code-instance` and `compute-code-distance`.

The skill supports the M1 campaign shape only:

- family is fixed to `rotated-surface-code`
- distances are positive integers
- decoders must be selected from existing `benchmarks/decoders/*.json`
- p-list values must be finite probabilities between 0 and 1
- budget includes `max_candidates` and wall-clock seconds
- promotion rules map to the existing `promote_rules.json` schema

The workflow is:

1. Understand the user's natural-language search goal.
2. Ask for missing M1 fields one at a time.
3. Produce a natural-language campaign summary.
4. Ask for explicit approval before writing any campaign files.
5. After approval, materialize:
   - `campaigns/examples/<campaign-id>/campaign.json`
   - `campaigns/examples/<campaign-id>/search_space.json`
   - `campaigns/examples/<campaign-id>/promote_rules.json`
6. Run search-layer validation.
7. Report the created files and the next command to run.

The approval gate must have teeth: before explicit approval, the skill must not
write `campaign.json`, `search_space.json`, or `promote_rules.json`.

## Skill Example Transcript

Add a short committed transcript file:

```text
skills/search-campaign/examples/rotated-surface-baseline-intake.md
```

The transcript should show:

- user asks to search rotated surface codes
- skill asks for the small set of M1 fields
- skill summarizes the proposed campaign in natural language
- user says "wait, do not write anything yet"
- skill stops without materializing files
- user later approves
- skill writes files and runs validation

This transcript is the human-readable proof for the conversation-first part of
issue #13. Automated tests should check that the transcript documents the
negative approval case.

## Demo Run

Commit one completed run under the existing campaign:

```text
results/search/rotated-surface-baseline/m1-demo/
```

The demo should evaluate the d=3 rotated-surface candidate with a reduced shot
budget. It should be produced from a real local `rsinter` run when possible, but
then checked in as ordinary repo data. CI should not need to call real
`rsinter` to validate it.

The committed run must be a completed M1 run, not a placeholder. It should have:

- `run_spec.mode` set to `autoresearch` or another completed mode accepted by
  the loader
- at least one completed manifest with a d=3 point at `p = 0.005`
- placeholder manifests for non-primary suite decoders are acceptable if the
  demo was produced through the current autoresearch loop; the e2e contract is
  the completed point, not full decoder breadth
- candidate artifacts copied under `candidates/<candidate-id>/artifacts/`
- non-empty `leaderboard.csv`
- non-empty `frontier.json`
- `report.html` with the d=3 data point
- `promotion_summary.json`
- `run_status.json` finalized when using autoresearch mode

The existing placeholder run `2026-06-09-example` may remain as historical
scaffolding, but the M1 docs should point newcomers to the completed demo run.

## Promotion Visibility

The demo must prove promotion in two places:

- `promotion_summary.json` records the accepted candidate and target Zoo path.
- `zoo/views/browse.md` and `zoo/views/instance-index.json` include the promoted
  instance.

If the promoted instance id would collide with the already curated
`rotated-surface-code-d3`, use the run candidate id as the promoted id, matching
the issue #12 promotion design. Do not overwrite existing curated instances
without explicit `--force`.

## End-To-End Test

Add `tests/test_search_e2e.py`.

The test should be offline and deterministic. It should not require real
`rsinter` on `PATH`.

Coverage:

- the committed M1 demo run loads through the search workspace loader
- `report.html` exists, is self-contained, and contains:
  - "AutoQEC Search Report"
  - the d=3 candidate id
  - the p=0.005 point
  - the committed LER value
- the committed leaderboard LER matches the relevant completed manifest point
- the committed LER is compatible with the golden fixture expectation in
  `benchmarks/fixtures/rotated-d3/expected.json`
- `promotion_summary.json` names the promoted candidate
- `zoo/views/browse.md` contains the promoted instance id
- the `search-campaign` transcript documents the pre-approval no-write case

The negative report-renderer control from the issue should be represented by a
direct assertion on the rendered/committed HTML d=3 point. If the report renderer
or committed report loses that point, this test goes red.

If a future test shells out to real `rsinter`, mark it `slow`; the default e2e
test must stay offline.

## Documentation

Update `README.md` and `CLAUDE.md` so a newcomer can see M1's final state
without reading the issue thread.

Documentation should include:

- the role of `search-campaign`
- the M1 quick-start in source checkout form:

  ```bash
  PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
  PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
  PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/<run-id>
  PYTHONPATH=src python3 -m autoqec_search.cli promote --root . --run results/search/rotated-surface-baseline/<run-id>
  ```

- the installed entry-point equivalents:

  ```bash
  autoqec-search preflight --root .
  autoqec-search run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
  autoqec-search report --root . --run results/search/rotated-surface-baseline/<run-id>
  autoqec-search promote --root . --run results/search/rotated-surface-baseline/<run-id>
  ```

- why `autoqec-search run` creates an `autoresearch/<tag>` branch and a linked
  `.worktrees/<tag>/` worktree
- where to open the committed demo `report.html`
- where to inspect the promoted Zoo instance
- how to run the e2e test:

  ```bash
  PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py
  ```

The docs should avoid implying that `python3 -m autoqec_search.cli` works from a
fresh checkout without either `PYTHONPATH=src` or an editable install.

## Data Flow

The M1 showcase data flow is:

```text
search-campaign approval
  -> campaign/search-space/promote-rules files
  -> autoqec-search validate/preflight
  -> autoqec-search run
  -> candidate artifacts and completed manifests
  -> report.html
  -> promotion_summary.json and Zoo rebuild
  -> tests/test_search_e2e.py verifies committed final state
```

The skill writes intent. The CLI writes run artifacts. Promotion writes curated
Zoo instance data. Tests read the committed final state and verify the contracts
still agree.

## Error Handling

`search-campaign` should stop with a clear message when:

- the family is not supported by M1
- a decoder id does not exist
- p-list or distance values are invalid
- the target campaign directory already exists
- the user has not explicitly approved materialization
- validation fails after writing files

For the committed demo:

- failed or missing manifests should make `tests/test_search_e2e.py` fail
- missing d=3 report content should make the e2e test fail
- missing promotion visibility should make the e2e test fail
- missing real backend should not make the offline e2e test fail

## Testing Plan

Focused tests:

- `tests/test_search_e2e.py`
- existing `tests/test_search_docs.py`
- existing report, run-loop, and promotion tests touched by any artifact shape
  updates

Recommended verification commands:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py tests/test_search_docs.py -q
PYTHONPATH=src python3 -m pytest tests/test_search_report.py tests/test_search_promote.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Optional real-backend verification, when `rsinter` is available:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
```

## Acceptance Criteria

Issue #13 is complete when:

- `skills/search-campaign/` exists and documents the approval-gated workflow
- the example transcript includes the "wait, do not write anything yet" negative
  case
- the committed M1 demo run is completed, not placeholder-only
- the committed M1 demo `report.html` can be opened directly and shows the d=3
  data point
- the committed promotion summary and Zoo browse/index artifacts show the
  promoted instance
- `tests/test_search_e2e.py` passes offline
- docs include copy-pasteable source-checkout commands and installed
  entry-point commands
- the default test suite remains independent of real `rsinter`

## Future Work

M2 should build on this M1 front door rather than expanding it in place:

- full issue #5 benchmark skill series
- general CSS-to-circuit adapter
- decoder parameter registry
- distance-method registry
- cross-run candidate comparison reports

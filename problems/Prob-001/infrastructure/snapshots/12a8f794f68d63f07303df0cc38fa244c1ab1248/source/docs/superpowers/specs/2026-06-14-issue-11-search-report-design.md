# Issue #11 Search Report Design

## Goal

Add a self-contained visual `report.html` for AutoQEC search runs.

The report is the human verification surface for issue #11. It should turn a
finished run directory into one offline HTML file with logical-error-rate plots,
leaderboard data, frontier highlights, a threshold estimate when the data
supports one, and run provenance.

The report must support both existing run modes:

- `eval`: a single-candidate evaluation run with completed per-decoder
  manifests.
- `autoresearch`: a finalized run-loop notebook with candidate verdicts,
  frontier data, and completed/crashed/placeholder manifests.

## Scope

In scope:

- CLI command:

  ```bash
  autoqec-search report --root . --run <path> [--out report.html]
  ```

- automatic `report.html` generation when `autoqec-search run` finalizes an
  autoresearch run
- one shared report renderer used by the CLI command and autoresearch
  finalization
- self-contained HTML with inline CSS, inline SVG, and embedded JSON
- LER-vs-p log-log plots with confidence intervals
- leaderboard/results table
- frontier highlights
- threshold estimate panel with method note
- provenance header
- zero-result handling that renders an explicit "No results" panel
- support for an empty run report, including any schema/loader adjustment
  needed for a run with zero candidate ids
- tests that prove the report is data-driven and offline-safe
- documentation updates in `README.md`, `CLAUDE.md`, and docs tests

Out of scope:

- interactive dashboards
- cross-run comparison views
- external JavaScript, CSS, fonts, images, or CDN assets
- promotion of run results into `zoo/`
- changing the `rsinter` execution contract
- replacing the existing lightweight `run-summary.html`

## Main Decision

Implement a new shared `autoqec_search.report` module.

The existing `run-summary.html` remains the compact autoresearch lab notebook.
The new `report.html` becomes the flagship visual report. Both the explicit
`autoqec-search report` command and the automatic autoresearch finalization path
call the same renderer so the two routes cannot drift.

The renderer consumes the existing committed run layout instead of introducing a
new artifact format:

- `run_spec.json`
- `env.json`
- `leaderboard.csv`
- `frontier.json`
- `summary.md` where useful for context
- `run_status.json` and `experiment-log.tsv` for autoresearch runs when present
- `candidate.json`, `structure.json`, and `distance.json`
- per-task/per-decoder `manifest.json` files

## CLI Behavior

Add:

```bash
autoqec-search report --root . --run results/search/<campaign>/<run-id>
```

Options:

- `--root <path>`: repository root containing `campaigns/`, `benchmarks/`, and
  `results/`; default `.`
- `--run <path>`: required run directory path
- `--out <path>`: optional output path; default is `<run>/report.html`

The command validates that `--root` exists and that `--run` points to a search
run directory. It writes the report and prints the output path.

If `--run` is relative, resolve it from the current working directory, matching
the style of the existing `show` command. The report loader should still use
`--root` for schemas, campaign metadata, benchmark tasks, and decoders.

## Automatic Autoresearch Report

When `autoqec-search run` reaches finalization, it writes
`results/search/<campaign>/<run-id>/report.html` before the final commit.

The automatic path uses the same renderer as `autoqec-search report`.
Autoresearch resume behavior recomputes the report from the current run
artifacts, so a resumed run updates the report together with
`leaderboard.csv`, `frontier.json`, `summary.md`, and `run-summary.html`.

## Report Model

The renderer first builds a normalized report model with:

- provenance:
  - campaign id
  - run id
  - run mode
  - generated timestamp from `env.json`
  - AutoQEC version
  - git SHA and branch when present
  - `rsinter` revision when present
  - seed and wall-clock budget when present
- candidate summaries:
  - candidate id
  - distance from `distance.json`
  - status from `candidate.json`
  - structure fields such as `n`, `k`, and `css_commute` when present
- result points from completed manifests:
  - candidate id
  - distance
  - task id
  - decoder id
  - physical error rate `p`
  - rounds
  - shots
  - errors
  - LER
  - CI low and high
  - seconds
- leaderboard rows from `leaderboard.csv`
- frontier entries from `frontier.json`
- run verdict rows from `experiment-log.tsv` for autoresearch runs when present

Completed manifests are the source of truth for plotted points. Leaderboard
rows are still rendered because they are the user-facing run aggregate and
because issue #11 explicitly asks for the leaderboard.

Issue #11 includes a negative control for a run directory with zero candidates.
The current `run-spec.schema.json` requires at least one candidate id, so the
implementation must either relax that schema to allow an empty `candidate_ids`
array for search runs or add a report-specific validation path that accepts the
empty-run fixture. Prefer relaxing the schema only if the rest of the search
loader can keep its existing integrity checks for nonempty runs. In either
case, the report behavior for an empty candidate list is fixed: render "No
results," show zero counts, skip charts, and emit no `NaN`.

## Plotting

Render deterministic inline SVG from Python.

Plots group data by task. Inside each task plot, series are separated by
decoder and candidate/distance. The report must include enough labels and
legend text for a reader to identify each curve without external assets.

The main plot uses log-log axes:

- x-axis: physical error rate `p`
- y-axis: logical error rate
- zero LER or zero CI lower bounds are plotted using the same small positive
  floor already used by `autoqec_search.plot`
- CI intervals are drawn as vertical bars or bands
- point tooltips or labels include decoder, candidate, distance, `p`, LER, and
  CI

If there are no completed points, the report skips chart generation and renders
an explicit "No results" panel. The generated HTML must not contain `NaN`.

## Threshold Estimate

The threshold estimate is intentionally conservative.

The renderer attempts an estimate only when there are at least two distances
with comparable points for the same task and decoder. Comparable means the
series share at least one physical error rate and each point has finite LER and
CI values. The MVP method is a coarse crossing estimate:

1. order comparable series by distance;
2. look for shared or bracketed `p` values where higher-distance and
   lower-distance LER ordering changes;
3. report the approximate crossing `p` when found.

The UI labels the value as "estimate" and includes a method note. If data is
insufficient or no crossing is detected, the threshold panel says "not enough
data" or "no crossing detected" rather than inventing a number.

## HTML Structure

`report.html` contains:

1. provenance header
2. status summary:
   - candidates
   - completed manifests
   - crashed manifests
   - placeholder manifests
   - frontier size
3. LER plot section with inline SVG
4. threshold estimate section
5. frontier table
6. leaderboard/results table
7. embedded JSON report model for traceability

The embedded JSON should be deterministic: sorted keys where practical and
stable ordering by campaign, run, task, decoder, candidate, distance, and `p`.
This gives tests a reliable way to assert that a specific LER value from the
golden fixture appears in the actual report payload.

## Safety And Self-Containment

All dynamic text is HTML-escaped.

The report must not include external assets or network references:

- no `http://`
- no `https://`
- no external scripts
- no external stylesheets
- no web fonts
- no image links

Relative links to local manifests are allowed only when they pass the existing
safe-relative-link checks from `run_render.py`. Unsafe paths render as plain
text. The report remains useful even if all links are ignored, because the core
data is embedded directly in the HTML.

## Error Handling

The report command fails with `SearchIntegrityError` for:

- missing run directory
- missing required run artifacts
- invalid run schemas
- malformed CSV or JSON
- manifest/run identity drift
- invalid numeric values that would make plotting unsafe

The zero-results case is not an error. It renders a valid HTML report with a
"No results" panel and no chart.

Autoresearch finalization should let report-rendering integrity errors fail the
run finalization, because a finalized branch without the required visual report
would violate issue #11. The failure should occur before the final commit.

## Testing

Add pure renderer tests first:

- completed eval run renders `report.html` with inline SVG, embedded JSON,
  leaderboard rows, frontier/provenance, and the golden d=3 LER from
  `benchmarks/fixtures/rotated-d3/expected.json`
- autoresearch-style run renders frontier highlights and all completed points
  while preserving keep/discard/crash status
- zero-candidate and zero-completed-results runs render "No results" and no
  `NaN`; include coverage for the schema/loader choice above
- self-contained output contains no `http://`, `https://`, external asset tags,
  or CDN-style references
- editing a LER value in a manifest or leaderboard and re-rendering changes the
  embedded JSON and SVG

Add CLI and integration tests:

- `autoqec-search report --run <run> --out <tmp/report.html>` writes the report
- `autoqec-search run ...` writes `report.html` automatically before the final
  autoresearch commit
- docs tests cover the new command and automatic report behavior

Use existing fake-`rsinter` fixtures for end-to-end tests. Do not require a real
backend for report rendering tests.

## Documentation

Update `README.md` and `CLAUDE.md` with:

- explicit `autoqec-search report --root . --run <path>` usage
- default output behavior
- automatic report generation for autoresearch runs
- offline/self-contained guarantee
- the difference between `run-summary.html` and `report.html`

## Open Design Constraints

The first implementation should prefer deterministic Python-rendered SVG and
plain HTML tables. Inline JavaScript is allowed by issue #11, but it is not
needed for the MVP unless a table interaction becomes necessary during
implementation. Avoiding JavaScript keeps the offline and test story simpler.

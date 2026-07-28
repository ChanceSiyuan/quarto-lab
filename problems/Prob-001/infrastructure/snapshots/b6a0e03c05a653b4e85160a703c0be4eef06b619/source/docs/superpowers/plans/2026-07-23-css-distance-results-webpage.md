# CSS Distance Results Webpage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one offline-safe local HTML report with a four-method open-source comparison table and an interactive 100-row proposal table that highlights only proposal 020.

**Architecture:** A focused Python module validates the public comparison CSV and the 100 committed proposal reports, converts them into typed aggregate rows, and renders one self-contained HTML file. The generated page uses inline CSS and dependency-free JavaScript for sorting and filtering; it never embeds case-level evaluator data or private paths.

**Tech Stack:** Python 3 standard library, pytest, HTML5, CSS, and vanilla JavaScript.

## Global Constraints

- Output exactly results/css-distance-autoresearch-100/index.html.
- Work from file:// with no server, network request, build step, or external asset.
- The first table contains only random-window-upper-bound, codedistance/QDistRndMW, codedistance/QDistEvol, and codedistance/decoderDist.
- The second table contains exactly proposals 001 through 100, with proposal 020 as the sole highlighted row.
- Per-invocation timeout is 300 seconds; every witness remains an upper-bound certificate, never an exact-distance claim.
- Trial median and P95 cells render as an em dash because this run retained aggregate runtime only; no quantile may be synthesized.
- Never embed case identifiers, matrices, seeds, witnesses, private paths, private filenames, target values, or manifest rows.
- Do not open or evaluate the sealed final holdout.
- Preserve unrelated user changes.

---

## File Structure

- Create src/autoqec_search/css_distance_results_page.py for validated loading, aggregation, rendering, privacy checks, writing, and the module CLI.
- Create tests/test_css_distance_results_page.py for parser, aggregation, rendering, privacy, and CLI coverage.
- Create results/css-distance-autoresearch-100/index.html as the generated standalone deliverable.

### Task 1: Parse and validate aggregate benchmark sources

**Files:**
- Create: src/autoqec_search/css_distance_results_page.py
- Create: tests/test_css_distance_results_page.py

**Interfaces:**
- Produces: BaselineRow, TrialRow, load_baseline_rows(csv_path: Path) -> list[BaselineRow], parse_trial_report(report_path: Path, proposal: int) -> TrialRow, and load_trial_rows(reports_root: Path) -> list[TrialRow].
- Consumes: the public comparison CSV and root-level REPORT.md files in worktrees named css-distance-run100-proposal-NNN.

- [ ] **Step 1: Write failing aggregation tests**

Add these tests and fixture helpers:

~~~python
def test_load_baseline_rows_computes_timeout_inclusive_statistics(tmp_path: Path) -> None:
    source = write_baseline_fixture(tmp_path, case_count=2)
    rows = load_baseline_rows(source)
    assert [row.key for row in rows] == [
        "random-window-upper-bound",
        "codedistance/QDistRndMW",
        "codedistance/QDistEvol",
        "codedistance/decoderDist",
    ]
    random_window = rows[0]
    assert random_window.cases == 2
    assert random_window.completed == 1
    assert random_window.target_hits == 1
    assert random_window.timeouts == 1
    assert random_window.total_seconds == pytest.approx(300.1)
    assert random_window.average_seconds == pytest.approx(150.05)
    assert random_window.median_seconds == pytest.approx(150.05)


def test_parse_trial_report_keeps_unrecorded_quantiles_empty(tmp_path: Path) -> None:
    report = write_report_fixture(
        tmp_path,
        proposal=20,
        method="quotient search",
        runs=24,
        verified=24,
        hits=24,
        runtime=16.8,
    )
    row = parse_trial_report(report, 20)
    assert row.proposal == 20
    assert row.average_seconds == pytest.approx(0.7)
    assert row.median_seconds is None
    assert row.p95_seconds is None
~~~

The baseline fixture must contain the exact production columns. Its first case completes every method at its target, and its second case times out random-window and decoderDist while QDistRndMW returns above target and QDistEvol hits target.

- [ ] **Step 2: Run the focused tests and confirm the expected import failure**

Run:

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_results_page.py -q
~~~

Expected: collection fails because autoqec_search.css_distance_results_page does not exist.

- [ ] **Step 3: Implement typed source loading**

Create immutable dataclasses with these fields:

~~~python
@dataclass(frozen=True)
class BaselineRow:
    key: str
    cases: int
    completed: int
    target_hits: int
    timeouts: int
    total_seconds: float
    average_seconds: float
    median_seconds: float
    interpretation: str


@dataclass(frozen=True)
class TrialRow:
    proposal: int
    method: str
    decision: str
    runs: int
    verified: int
    target_hits: int
    timeouts: int
    crashes: int
    invalid_claims: int
    total_seconds: float
    average_seconds: float | None
    median_seconds: float | None
    p95_seconds: float | None
    quality: float
~~~

Use this fixed ordered mapping:

~~~python
BASELINE_COLUMNS = (
    ("random-window-upper-bound", "random_window", "random_window_ms", "Fast on easy cases; four public-ladder timeouts."),
    ("codedistance/QDistRndMW", "codedistance_QDistRndMW", "codedistance_QDistRndMW_ms", "Random information-set baseline."),
    ("codedistance/QDistEvol", "codedistance_QDistEvol", "codedistance_QDistEvol_ms", "Evolutionary randomized baseline."),
    ("codedistance/decoderDist", "codedistance_decoderDist", "codedistance_decoderDist_ms", "BP-OSD quality-first baseline."),
)
~~~

load_baseline_rows must require every mapped CSV column plus expected, require at least one row, count timeout values, parse non-timeout values as d=N, count a hit when N is no greater than expected, and include every recorded millisecond duration in total, mean, and statistics.median.

parse_trial_report must use anchored regular expressions for the numbered title, bold assigned method, and Markdown metric rows. Accept only accepted/rejected decisions and nonnegative numeric metrics. Set average to runtime divided by runs when runs is positive; set median_seconds and p95_seconds to None.

load_trial_rows must require exactly the matching directories 001 through 100, parse each REPORT.md, and reject missing or extra numbered worktrees.

- [ ] **Step 4: Run aggregation tests**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_results_page.py -q
~~~

Expected: both aggregation tests pass.

- [ ] **Step 5: Commit Task 1**

~~~bash
git add src/autoqec_search/css_distance_results_page.py tests/test_css_distance_results_page.py
git commit -m "feat: aggregate CSS distance result tables"
~~~

### Task 2: Render the offline interactive report

**Files:**
- Modify: src/autoqec_search/css_distance_results_page.py
- Modify: tests/test_css_distance_results_page.py

**Interfaces:**
- Consumes: list[BaselineRow] and list[TrialRow].
- Produces: render_results_page(baselines, trials) -> str and write_results_page(baselines, trials, output_path) -> Path.

- [ ] **Step 1: Write failing renderer and privacy tests**

~~~python
def test_render_results_page_is_offline_complete_and_private() -> None:
    html = render_results_page(make_four_baselines(), make_one_hundred_trials())
    assert html.startswith("<!doctype html>")
    assert html.count('class="baseline-row"') == 4
    assert html.count('data-proposal="') == 100
    assert html.count("trial-highlight") == 1
    assert 'data-proposal="020"' in html
    assert "24/24 · fastest perfect" in html
    assert 'id="trial-search"' in html
    assert 'data-decision-filter="accepted"' in html
    assert 'id="visible-count"' in html
    assert "Per-invocation quantiles were not retained" in html
    assert "https://" not in html
    assert "http://" not in html
    for marker in FORBIDDEN_OUTPUT_MARKERS:
        assert marker not in html


def test_render_results_page_escapes_method_text() -> None:
    trials = make_one_hundred_trials()
    trials[0] = replace(trials[0], method="<script>alert(1)</script>")
    html = render_results_page(make_four_baselines(), trials)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
~~~

- [ ] **Step 2: Run renderer tests and confirm they fail**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_results_page.py -q
~~~

Expected: renderer tests fail because render_results_page is absent.

- [ ] **Step 3: Implement the semantic page**

Implement html.escape-based cell formatting and second formatting with three decimal places and an em dash for None. The exact page structure is:

~~~html
<header class="report-header">
  <p class="eyebrow">AutoQEC · CSS distance autoresearch</p>
  <h1>Randomized upper-bound benchmark results</h1>
  <p class="lede">Verified logical witnesses certify upper bounds only. They do not establish exact code distance.</p>
</header>
<section aria-labelledby="baseline-title">
  <h2 id="baseline-title">Open-source implementation comparison</h2>
  <p class="section-note">Public 19-instance ladder. Timeout durations are included in total, average, and median runtime.</p>
  <div class="table-shell">
    <table id="baseline-table">
      <thead><tr><th>Implementation</th><th>Cases</th><th>Completed</th><th>Target hits</th><th>Timed out</th><th>Total</th><th>Average</th><th>Median</th><th>Interpretation</th></tr></thead>
      <tbody>{baseline_rows}</tbody>
    </table>
  </div>
</section>
<section aria-labelledby="trials-title">
  <div class="section-heading">
    <div><h2 id="trials-title">All 100 proposal trials</h2><p class="section-note">Per-invocation quantiles were not retained; median and P95 are shown as —.</p></div>
    <output id="visible-count">100 trials</output>
  </div>
  <div class="toolbar">
    <label for="trial-search">Search</label>
    <input id="trial-search" type="search" autocomplete="off">
    <div role="group" aria-label="Filter by decision">
      <button type="button" data-decision-filter="all" aria-pressed="true">All</button>
      <button type="button" data-decision-filter="accepted" aria-pressed="false">Accepted</button>
      <button type="button" data-decision-filter="rejected" aria-pressed="false">Rejected</button>
    </div>
  </div>
  <div class="table-shell trial-shell">
    <table id="trials-table">
      <thead><tr><th>Proposal</th><th>Method</th><th>Decision</th><th>Runs</th><th>Verified</th><th>Hits</th><th>Timeouts</th><th>Crashes</th><th>Invalid</th><th>Total</th><th>Average</th><th>Median</th><th>P95</th><th>Quality</th></tr></thead>
      <tbody>{trial_rows}</tbody>
    </table>
  </div>
</section>
~~~

Use warm off-white #f4f1ea, white table surfaces, navy #14233b, teal #24766c, red #a04444, and gold #c58a18 only for proposal 020. Use system fonts, tabular numerals, sticky table headers, visible focus rings, and horizontal scrolling on narrow screens.

Render proposal 020 with class trial-row trial-highlight, data-proposal="020", and the badge 24/24 · fastest perfect. Every other row uses only class trial-row and has no winner badge.

Inline JavaScript must sort numeric and text columns, toggle aria-sort, search proposal/method text, filter all/accepted/rejected, and update visible-count. Sorting may move proposal 020 but must preserve its highlight.

Define and enforce:

~~~python
FORBIDDEN_OUTPUT_MARKERS = (
    "source_case_id",
    "hx_path",
    "hz_path",
    "selection-secret",
    "salt.bin",
    "AutoQEC-private",
    "/Users/",
)
~~~

write_results_page must scan the full HTML for those markers plus http:// and https://, create the requested parent only, and write through a sibling temporary file followed by Path.replace.

- [ ] **Step 4: Run renderer tests**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_results_page.py -q
~~~

Expected: all aggregation, rendering, escaping, and privacy tests pass.

- [ ] **Step 5: Commit Task 2**

~~~bash
git add src/autoqec_search/css_distance_results_page.py tests/test_css_distance_results_page.py
git commit -m "feat: render CSS distance results webpage"
~~~

### Task 3: Add the CLI and generate the real page

**Files:**
- Modify: src/autoqec_search/css_distance_results_page.py
- Modify: tests/test_css_distance_results_page.py
- Create: results/css-distance-autoresearch-100/index.html

**Interfaces:**
- Produces: python3 -m autoqec_search.css_distance_results_page --baseline-csv PATH --reports-root PATH --output PATH.

- [ ] **Step 1: Write the failing CLI integration test**

~~~python
def test_main_writes_complete_page(tmp_path: Path) -> None:
    baseline_csv = write_baseline_fixture(tmp_path, case_count=2)
    reports_root = write_one_hundred_report_fixtures(tmp_path)
    output = tmp_path / "report" / "index.html"
    assert main([
        "--baseline-csv", str(baseline_csv),
        "--reports-root", str(reports_root),
        "--output", str(output),
    ]) == 0
    html = output.read_text(encoding="utf-8")
    assert html.count('class="baseline-row"') == 4
    assert html.count('data-proposal="') == 100
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*.html")) == ["report/index.html"]
~~~

- [ ] **Step 2: Run the CLI test and confirm it fails**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_results_page.py::test_main_writes_complete_page -q
~~~

Expected: failure because main is absent.

- [ ] **Step 3: Implement the CLI**

Add build_parser() with required --baseline-csv, --reports-root, and --output Path options. main(argv) loads both sources, writes the page, prints only wrote CSS distance results page, and returns zero. Add a standard raise SystemExit(main()) module entry point.

- [ ] **Step 4: Run all focused tests**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_results_page.py -q
~~~

Expected: all tests pass.

- [ ] **Step 5: Generate the standalone page**

~~~bash
PYTHONPATH=src python3 -m autoqec_search.css_distance_results_page   --baseline-csv benchmarks/distance_ladders/surface-toric-bb-kasai-tanner-v2/rstim225-comparison.csv   --reports-root .worktrees   --output results/css-distance-autoresearch-100/index.html
~~~

Expected: wrote CSS distance results page.

- [ ] **Step 6: Verify generated invariants and privacy**

~~~bash
python3 - <<'PY'
from pathlib import Path

html = Path("results/css-distance-autoresearch-100/index.html").read_text()
assert html.count('class="baseline-row"') == 4
assert html.count('data-proposal="') == 100
assert html.count("trial-highlight") == 1
assert 'data-proposal="020"' in html
assert "24/24 · fastest perfect" in html
assert "sealed final holdout was not evaluated" in html.lower()
for marker in ("source_case_id", "hx_path", "hz_path", "selection-secret", "salt.bin", "AutoQEC-private", "/Users/", "http://", "https://"):
    assert marker not in html
print("page=pass baselines=4 trials=100 highlight=020 privacy=pass offline=pass")
PY
~~~

Expected: page=pass baselines=4 trials=100 highlight=020 privacy=pass offline=pass.

- [ ] **Step 7: Commit Task 3**

~~~bash
git add src/autoqec_search/css_distance_results_page.py tests/test_css_distance_results_page.py results/css-distance-autoresearch-100/index.html
git commit -m "feat: add CSS distance results webpage"
~~~

### Task 4: Final verification and handoff

**Files:**
- Verify: src/autoqec_search/css_distance_results_page.py
- Verify: tests/test_css_distance_results_page.py
- Verify: results/css-distance-autoresearch-100/index.html

- [ ] **Step 1: Run focused tests fresh**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_results_page.py -q
~~~

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run adjacent report tests**

~~~bash
PYTHONPATH=src python3 -m pytest tests/test_css_distance_results_page.py tests/test_search_report.py -q
~~~

Expected: all selected tests pass with zero failures.

- [ ] **Step 3: Check formatting and repository state**

~~~bash
git diff --check HEAD~1..HEAD
git status --short
~~~

Expected: no whitespace errors and a clean worktree.

- [ ] **Step 4: Report the local page**

Return the clickable absolute page path, summarize both tables and the proposal-020 highlight, and explicitly note that trial median/P95 values are unavailable because the original run retained aggregate timing only.

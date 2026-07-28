# AutoQEC

AutoQEC is a private coordination repo for automated quantum error-correction search. It combines a collaboration harness for literature and Zulip discussion with a small implementation package that validates, builds, and publishes a structured QEC Zoo layer.

This is not the main search or decoder implementation repo. The code here is focused on source curation, normalized code records, derived browse artifacts, and finite CSS instance generation.

## Long-Running Quantum Tanner Search

Use [`campaigns/examples/quantum-tanner-autoresearch/README.md`](campaigns/examples/quantum-tanner-autoresearch/README.md) for the operator workflow and start/resume commands for `scripts/run_quantum_tanner_autoresearch.sh`.
That launcher also maintains `<work-root>/aggregate/report.html`, an
append-ordered cross-round table, plus `<work-root>/aggregate/results.jsonl`
for the automatic candidate history used before later Codex proposal rounds.

## First-Time Setup

If you just cloned this repo and are opening it in Claude Code on a fresh machine, initialize it from the repo root with the project `onboard` skill:

```text
/onboard
```

You can also just say `onboard me`.

The flow is two-stage:

1. The first run enables the `zlp-harness` and `sci-brain` plugins in `~/.claude/settings.json` and asks you to restart Claude Code.
2. After restart, run `/onboard` again. The skill then delegates to `zlp-harness:zlp-onboard` to install or verify the Zulip tooling, place your `zuliprc`, and sync the project stream.

If you want the manual setup path instead, see [`CLAUDE.md`](CLAUDE.md).

Project-local agent skills live under `skills/`. For agent compatibility, `.agents/skills` and `.claude/skills` both point to that same directory.

## What Lives Here

- `.knowledge/`: local paper library and working notes for literature-grounded discussion
- `ref.bib`: project-level bibliography namespace shared by the knowledge base and future manuscripts
- `zoo/`: source-of-truth code cards, evidence records, checked-in finite instances, and derived browse artifacts
- `campaigns/`: human-authored search intent and example search spaces
- `benchmarks/`: reusable benchmark tasks, decoder configs, suites, and search-layer schemas
- `results/search/`: committed example runs plus future runtime search artifacts
- `src/autoqec_zoo/`: Python package for loading, validating, indexing, and rendering the Zoo
- `src/autoqec_search/`: Python package for validating campaign/benchmark contracts, running preflight checks, and materializing placeholder run artifacts
- `julia/tensorqec_env/`: repository-local Julia environment and scripts for TensorQEC-backed instance generation
- `Makefile`: Zulip bridge helpers plus convenience targets for Zoo and TensorQEC workflows

## Current Seeded Content

The checked-in structured data currently includes:

- code cards for `surface-code`, `rotated-surface-code`, and `bivariate-bicycle-code`
- evidence records under `zoo/evidence/2308.07915/` and `zoo/evidence/2408.10001/`
- a checked-in finite instance at `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3/`

Derived artifacts already tracked in the repo include:

- `zoo/views/code-index.json`
- `zoo/views/family-index.json`
- `zoo/views/relation-index.json`
- `zoo/views/evidence-index.json`
- `zoo/views/instance-index.json`
- `zoo/views/browse.md`
- `zoo/views/site/`
- `zoo/codes/**/card.md`

## Build the Zoo

Rebuild the derived Zoo artifacts from `zoo/codes/**/card.json`, `zoo/evidence/**/*.json`, and stored instances with either of the following:

```bash
python3 -m autoqec_zoo.cli build --root zoo
```

```bash
make zoo-build
```

The build step validates schemas and integrity, then regenerates:

- JSON indexes under `zoo/views/`
- rendered Markdown cards under `zoo/codes/**/card.md`
- the browse page at `zoo/views/browse.md`
- the static browser at `zoo/views/site/index.html`

If the package is installed, the CLI entry point is also available as:

```bash
autoqec-zoo build --root zoo
```

## Search Layer

Phase 1 search architecture scaffolding for issue `#3` lives under:

- `campaigns/`
- `benchmarks/`
- `results/search/`

Validate the committed example data with:

```bash
python3 -m autoqec_search.cli validate --root .
```

Run the search-layer doctor against contracts, fixtures, and the local `rsinter` backend with:

```bash
python3 -m autoqec_search.cli preflight --root .
```

Write the same status report as a self-contained HTML page with:

```bash
python3 -m autoqec_search.cli preflight --root . --html /tmp/doctor.html
```

Materialize a fresh placeholder run artifact tree from the example campaign with:

```bash
python3 -m autoqec_search.cli init-run --root . --campaign rotated-surface-baseline --run-id scratch-run
```

Evaluate one rotated-surface candidate through `rsinter` with:

```bash
python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.01 --run-id local-rotated-d3-eval
```

The same workflow is available as `autoqec-search eval` when the package is installed. The eval command creates a fresh run under `results/search/<campaign>/<run-id>/`, reuses matching Zoo instance artifacts when present, writes `structure.json`, `distance.json`, completed per-decoder manifests, and `candidate-plot.svg`. It strictly requires `rsinter` on `PATH`; missing or outdated `rsinter` is a hard failure.

For issue #17 and later code-family-agnostic checks, add `--general-css` to keep
candidate resolution, structure checks, manifests, and plots the same while
writing an `rsinter` `input_type = "css"` spec. This path converts stored
`hx.json` and `hz.json` artifacts into the upstream contract
`hx/hz -> rstim CSS -> DEM -> decoder`; it requires upstream rstim #46/#51
support on the `rsinter` executable. The default eval command remains the
surface-specific path. BB/qLDPC campaigns remain issue #18.

```bash
python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-css-fixture --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id local-general-css-d3 --general-css
```

Distance-method work lives in `src/autoqec_search/distance_methods.py`. The
registry is exact-first. The default `copied-zoo-exact` method records Zoo
`derived_properties.distance` as `bound_type: "exact"` and writes method
options plus provenance into `distance.json`; it must not require `qec-code`.
The guarded `rstim-ilp-exact` method is reserved for the external exact CSS
distance backend and currently fails clearly with
`rstim exact CSS distance backend is not available` when that backend is not
installed. Randomized upper bounds live in rstim and are not a first-class
AutoQEC method for closing issue #15. Promotion requires exact distances by
default and must never treat an upper bound as Zoo
`derived_properties.distance`.

Run the tiny autoresearch loop for the campaign with:

```bash
python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 90s
```

The installed form is `autoqec-search run`. The run command creates a local branch `autoresearch/<tag>` and a linked worktree under `.worktrees/<tag>/`, writes the lab notebook artifacts under that worktree's `results/search/<campaign>/<run-id>/`, and commits each start/evaluate/finalize step on the branch. Autoresearch runs write `experiment-log.tsv`, `leaderboard.csv`, `frontier.json`, `summary.md`, `run-summary.html`, `report.html`, and `run_status.json`.

Use `--run-id <id>` for deterministic local checks, `--resume --run-id <id>` to continue an existing run worktree, and `--cleanup-worktree` to remove the linked worktree after the final commit while keeping the `autoresearch/<tag>` branch. The command strictly requires `rsinter` on `PATH`; backend failures become candidate crash manifests, while budget timeouts leave placeholder candidates that can be retried with `--resume`.

Search strategy selection is recorded internally in `search_space.strategy`.
When the field is absent, `autoqec-search run` uses `grid`, preserving the M1
candidate order. Supported strategies are `grid`, `random`, and `adaptive`.
Every strategy-aware run writes `strategy_trace.json` next to
`experiment-log.tsv`; the trace records evaluated, deduped, and exhausted
proposal events without polluting the experiment log.

Compare grid and adaptive behavior on the committed strategy fixture with:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-strategies \
  --root . \
  --campaign rotated-surface-strategy-fixture \
  --strategies grid adaptive \
  --budget-candidates 3 \
  --metrics benchmarks/fixtures/strategy-comparison/rotated-surface.json \
  --out /tmp/autoqec-strategies.html
```

The installed form is `autoqec-search compare-strategies`. The command writes
sibling `strategies.json`, `strategies.svg`, and `strategies.html` artifacts.
It exits nonzero if adaptive does not reach the grid target quality in fewer
evaluations on the fixture.

### Benchmark skills and candidate comparison

Issue #19 adds the full benchmark skill series:

- `benchmark-code` - conversation-first intake, preflight, approval, and dispatch.
- `bench-runner-distance` - deterministic distance review or eval-backed distance runs.
- `bench-runner-mc-ler` - MC-LER runs through existing `eval`, `run`, and `report` commands.
- `compare-candidates` - review two or more completed run directories.

The direct CLI comparison route is:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-candidates \
  --root . \
  --run results/search/<campaign-a>/<run-a> \
  --run results/search/<campaign-b>/<run-b> \
  --out /tmp/autoqec-candidates.html
```

The installed form is `autoqec-search compare-candidates`.

Comparison requires a shared task/decoder/p grid. Runs with different benchmark
tasks fail as incomparable rather than receiving a misleading ranking.
Overall winner reporting is strong-only. Tentative point winners stay visible,
but the overall field stays `no-clear-winner` unless every shared point has the
same strong winner. The committed BB72 OSD1 smoke artifacts prove the AutoQEC
orchestration path; the deferred BB72 OSD10 published-reference curve remains
an rstim-side validation.

Render a self-contained visual report for any completed search run with:

```bash
python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/<run-id>
```

The installed form is `autoqec-search report`. By default the command writes
`report.html` inside the run directory; pass `--out /tmp/report.html` to write
elsewhere. The report is a single offline HTML file with inline CSS/SVG and
embedded JSON, so it can be opened directly from a committed branch with no
network access. Autoresearch runs also write `report.html` automatically during
finalization. `run-summary.html` remains the compact lab notebook summary, while
`report.html` is the visual verification surface with plots, leaderboard rows,
frontier highlights, threshold estimate notes, and provenance.

Promote accepted autoresearch candidates into the curated Zoo with:

```bash
python3 -m autoqec_search.cli promote --root . --run results/search/rotated-surface-baseline/<run-id>
```

The installed form is `autoqec-search promote`. Promotion reads
`promote_rules.json` next to the campaign, evaluates frontier candidates, copies
accepted `instance.json` / `hx.json` / `hz.json` bundles into
`zoo/codes/<code-id>/instances/<candidate-id>/`, writes
`promotion_summary.json`, and rebuilds `zoo/views/instance-index.json`,
`zoo/views/browse.md`, card markdown, and the static site. Existing curated
instance ids are protected; pass `--force` only when intentionally replacing a
previous local promotion.

`autoqec-search run` invokes the same promotion step during finalization. When
no campaign `promote_rules.json` exists, it writes a skip summary and still
finalizes the autoresearch branch.

### M1 Search Showcase

Issue #13 closes the M1 search milestone with a committed conversation-first
demo:

- `skills/search-campaign/` captures the approval-gated campaign intake flow.
- `results/search/rotated-surface-baseline/m1-demo/` is the finalized
  autoresearch run covering d=3/5/7 with `surface_code:rotated_memory_z`,
  rounds=3*d, and physical error rates
  0.008, 0.009, 0.01, 0.011, 0.012.
- `results/search/rotated-surface-baseline/m1-demo/report.html` is the
  self-contained offline report for the M1 result.
- Promoted Zoo instances from that run:
  `zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/`,
  `zoo/codes/rotated-surface-code/instances/rotated-surface-d5-example/`, and
  `zoo/codes/rotated-surface-code/instances/rotated-surface-d7-example/`.

Verify the final M1 result from a source checkout with:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

To reproduce the workflow locally instead of reading the committed result, use a
fresh run id:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/local-m1-demo
PYTHONPATH=src python3 -m autoqec_search.cli promote --root . --run results/search/rotated-surface-baseline/local-m1-demo
```

If the package is installed, the same commands are also available under the `autoqec-search` entry point.

## Finite Instance Generation

This repo can generate finite-size CSS parity-check instances under `zoo/codes/**/instances/` using TensorQEC in a repository-local Julia environment.

Current generator support in `julia/tensorqec_env/scripts/generate_instance.jl` covers:

- `surface-code`
- `rotated-surface-code`
- `bivariate-bicycle-code`

Useful entry points:

- `make tensorqec-setup`
- project skill `setup-tensorqec`
- project skill `generate-code-instance`
- project skill `compute-code-distance`

Generated bundles contain:

- `instance.json`
- `hx.json`
- `hz.json`

Distance evaluation is separated from generation. Use `compute-code-distance` to populate or recompute `derived_properties.distance` for an existing stored instance.

## Collaboration Harness

The repo is wired to the `QEC-automated search` Zulip stream on `https://qec-harness.zulipchat.com`.

Common commands:

```bash
make zulip-whoami
make zulip-topics
make zulip-messages TOPIC=resources LIMIT=20 FORMAT=md
make zulip-pull
make zulip-send TOPIC=resources MSG="hello"
```

The local Zulip archive lives under `.zulip/` and is gitignored.

## Agent Workflows

This repo is designed to work with the project instructions in [`CLAUDE.md`](CLAUDE.md) and the Codex-facing notes in [`AGENTS.md`](AGENTS.md).

Skills are the preferred entry points for repeatable agent workflows. Use the
project-local skills for AutoQEC-specific work, and the installed companion
skills for research, collaboration, GitHub, and artifact tasks.

### AutoQEC project skills

- `onboard` - first-time repository, plugin, and Zulip setup.
- `search-campaign` - turn natural-language search intent into an approved
  campaign record.
- `benchmark-code` - intake and dispatch for distance or Monte Carlo benchmark
  workflows.
- `bench-runner-distance` - deterministic distance review or eval-backed
  distance runs.
- `bench-runner-mc-ler` - Monte Carlo logical-error-rate runs through the
  existing search/eval/report commands.
- `compare-candidates` - compare completed benchmark or search runs on a shared
  task grid.
- `setup-tensorqec` - prepare or verify the repository-local Julia/TensorQEC
  environment.
- `generate-code-instance` - generate finite CSS instance bundles under
  `zoo/codes/**/instances/`.
- `compute-code-distance` - compute or record distance data for stored
  instances.
- `extract-zoo-evidence` - extract paper-specific Zoo evidence from a reference
  already indexed in `.knowledge/`.

### Research and knowledge skills

- `sci-brain:survey` - survey a research topic and build a grounded knowledge
  base.
- `sci-brain:download-ref` or `download-ref` - add arXiv IDs or DOIs to
  `.knowledge/`.
- `sci-brain:survey-writer` - write a focused literature survey or field
  assessment from an existing knowledge base.
- `sci-brain:brainstorm-ideas` and `sci-brain:idea-writer` - develop research
  directions and turn selected ideas into proposal-style plans.
- `sci-brain:paper-reviewer` and `sci-brain:paper-writer` - review or draft
  scientific manuscripts.

### Collaboration and repo operations

- `zulip-reply` - inspect the project Zulip stream and draft replies; send only
  after explicit approval.
- `zlp-advisor` - run advisor-style research supervision checks against the
  current project context.
- `github:github` - summarize or triage GitHub repositories, issues, and pull
  requests.
- `github:gh-fix-ci` and `github:gh-address-comments` - fix failing PR checks or
  address actionable review feedback.
- `github:yeet` - publish local changes to GitHub with an intentional commit and
  draft pull request.

### Artifact and development support

- `pdf:pdf`, `documents:documents`, `presentations:Presentations`, and
  `spreadsheets:Spreadsheets` - create, edit, render, and verify document
  artifacts.
- `imagegen` - generate or edit bitmap images when a visual asset is needed.
- `browser:control-in-app-browser` - inspect local or web UI in the in-app
  browser.
- Superpowers skills - guide brainstorming, debugging, TDD, worktrees, plan
  writing/execution, code review, and final verification.

For technical AutoQEC or QEC questions, check `.knowledge/`, `ref.bib`, and
`zoo/` before relying on memory. For single-paper evidence extraction from
`.knowledge/`, use `extract-zoo-evidence`.

## Development Notes

Python packaging metadata lives in `pyproject.toml`, with the package exposed as `autoqec-zoo`.

Tests live under `tests/` and can be run with:

```bash
python3 -m pytest
```

For repo-specific operating conventions, onboarding details, and knowledge-base workflow rules, see [`CLAUDE.md`](CLAUDE.md).

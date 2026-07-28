# Issue 46 Quantum Tanner Autoresearch Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested operator workflow page for the local quantum Tanner autoresearch loop.

**Architecture:** The workflow is documentation-only. A campaign-local README names the real campaign, suite, catalog, run, report, and surface-copy comparison commands; focused documentation tests enforce command blocks and scientific guardrails.

**Tech Stack:** Markdown documentation, Python `pytest`, existing `autoqec_search.cli` command surface.

## Global Constraints

- Workflow page path is `campaigns/examples/quantum-tanner-autoresearch/README.md`.
- Documentation tests live in `tests/test_search_docs.py`.
- The workflow must include command blocks for preflight, validation, a time-bounded quantum Tanner run, report generation, and surface-copy comparison.
- The workflow must state `p=0.001`.
- The workflow must state that surface multi-logical results are computed from a single-logical patch with `1 - (1 - P_single)^k`.
- The workflow must state that upper-bound distances must not be promoted as exact Zoo distances.
- The workflow is local-only and points SLURM/cluster execution to issue #20.
- No CLI behavior, benchmark data, decoder config, or Zoo promotion behavior changes are allowed.

---

## File Structure

- Modify `tests/test_search_docs.py`: add two issue-specific tests and helpers for extracting bash command blocks and checking guardrail text.
- Create `campaigns/examples/quantum-tanner-autoresearch/README.md`: the operator workflow page.

### Task 1: Tested Workflow Documentation

**Files:**
- Modify: `tests/test_search_docs.py`
- Create: `campaigns/examples/quantum-tanner-autoresearch/README.md`

**Interfaces:**
- Consumes: existing CLI commands in `src/autoqec_search/cli.py`.
- Produces: a Markdown workflow page that tests can read from `REPO_ROOT / "campaigns/examples/quantum-tanner-autoresearch/README.md"`.

- [ ] **Step 1: Write the failing documentation tests**

Add these helpers and tests to `tests/test_search_docs.py`:

```python
import re


QT_WORKFLOW_DOC = (
    REPO_ROOT / "campaigns" / "examples" / "quantum-tanner-autoresearch" / "README.md"
)


def _bash_blocks(document: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)\n```", document, flags=re.DOTALL)


def _assert_quantum_tanner_guardrails(document: str) -> None:
    assert "p=0.001" in document
    assert "1 - (1 - P_single)^k" in document
    assert "upper-bound distances must not be promoted as exact Zoo distances" in document


def test_quantum_tanner_autoresearch_workflow_has_runnable_command_blocks() -> None:
    document = QT_WORKFLOW_DOC.read_text()
    blocks = _bash_blocks(document)
    commands = "\n".join(blocks)

    assert "autoqec-search preflight" in document
    assert "python3 -m autoqec_search.cli preflight --root ." in commands
    assert "python3 -m autoqec_search.cli validate --root ." in commands
    assert "python3 -m autoqec_search.cli run --root ." in commands
    assert "--campaign quantum-tanner-autoresearch" in commands
    assert "python3 -m autoqec_search.cli report --root .worktrees/local-qt-p001" in commands
    assert "python3 -m autoqec_search.cli compare-surface-copy --root .worktrees/local-qt-p001" in commands
    assert "--baseline benchmarks/baselines/rotated-surface-single-logical-p001.json" in commands

    for block in blocks:
        assert "<" not in block
        assert ">" not in block


def test_quantum_tanner_autoresearch_workflow_states_scientific_guardrails() -> None:
    document = QT_WORKFLOW_DOC.read_text()
    _assert_quantum_tanner_guardrails(document)

    for corrupted in (
        document.replace("p=0.001", "p=0.01"),
        document.replace("1 - (1 - P_single)^k", ""),
        document.replace(
            "upper-bound distances must not be promoted as exact Zoo distances",
            "",
        ),
    ):
        try:
            _assert_quantum_tanner_guardrails(corrupted)
        except AssertionError:
            pass
        else:
            raise AssertionError("negative-control mutation unexpectedly passed")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_docs.py -k quantum_tanner_autoresearch_workflow
```

Expected: FAIL because `campaigns/examples/quantum-tanner-autoresearch/README.md` does not exist yet.

- [ ] **Step 3: Write the workflow README**

Create `campaigns/examples/quantum-tanner-autoresearch/README.md` with this content:

````markdown
# Quantum Tanner Autoresearch Workflow

## Scope

This page is the local operating loop for the quantum Tanner autoresearch
campaign. It explains how to start, inspect, resume, and review a Codex CLI run
whose durable state lives in files, commits, run logs, and reports.

This is not a SLURM or cluster execution design. Keep cluster execution on the
separate tracking issue, GitHub issue #20.

## Inputs

The workflow uses the committed local fixtures and contracts:

- `campaigns/examples/quantum-tanner-autoresearch/campaign.json`
- `campaigns/examples/quantum-tanner-autoresearch/search_space.json`
- `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`
- `campaigns/examples/quantum-tanner-autoresearch/witnesses/`
- `benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json`
- `benchmarks/suites/quantum-tanner-rbposd-p001-v1.json`
- `benchmarks/baselines/rotated-surface-single-logical-p001.json`

The benchmark is fixed at `p=0.001`. The surface baseline is a single-logical
rotated surface patch table; copied surface multi-logical results are computed
from that single-logical patch with `1 - (1 - P_single)^k`.

## Command Form

The installed entry point is `autoqec-search`, so an installed checkout can use
commands such as `autoqec-search preflight --root .`. The blocks below use the
source-checkout form so they run before installation.

## 1. Preflight

Run preflight before spending decoder time. This checks the workspace
contracts, fixture records, and local `rsinter` availability, and writes an HTML
doctor page for review.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root . --html /tmp/autoqec-qt-preflight.html
```

Approval gate: open `/tmp/autoqec-qt-preflight.html` or read the terminal table.
Do not continue to a run until the failures are understood. A missing `rsinter`
backend is a local setup problem, not something to hide in chat.

## 2. Validate the Campaign Workspace

Validate the campaign, benchmark suite, fixture catalog, and any committed run
artifacts. This is the static contract check for the workflow inputs.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Review these files before approving a run:

- `campaigns/examples/quantum-tanner-autoresearch/search_space.json`
- `campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json`
- `benchmarks/suites/quantum-tanner-rbposd-p001-v1.json`
- `benchmarks/tasks/quantum-tanner-css-memory-x-rbposd-p001-v1.json`
- `benchmarks/baselines/rotated-surface-single-logical-p001.json`

## 3. Start a Local Smoke Run

Use a fresh run id. The example run id is `local-qt-p001`; change it only if
that branch or worktree already exists. The command creates branch
`autoresearch/local-qt-p001` and linked worktree `.worktrees/local-qt-p001/`.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign quantum-tanner-autoresearch --wall-clock 90s --run-id local-qt-p001 --distance-method random-window-upper-bound
```

Expected run root:
`.worktrees/local-qt-p001/results/search/quantum-tanner-autoresearch/local-qt-p001/`.

Expected run-level artifacts:

- `run_spec.json`
- `env.json`
- `experiment-log.tsv`
- `leaderboard.csv`
- `frontier.json`
- `strategy_trace.json`
- `summary.md`
- `run-summary.html`
- `report.html`
- `run_status.json`
- `promotion_summary.json`

Expected candidate artifacts live under
`candidates/quantum-tanner-toric-d4/`,
`candidates/quantum-tanner-toric-d6/`, and
`candidates/quantum-tanner-toric-d8/`. Inspect `screening.json` first. In the
committed smoke search space, d4 is admitted by a valid upper-bound witness, d6
is skipped because it has no upper-bound payload, and d8 fails because its
witness is invalid.

Upper-bound distances are screening evidence only. The rule is that
upper-bound distances must not be promoted as exact Zoo distances, and
`promotion_summary.json` must be read with that rule in mind.

## 4. Resume Instead of Restarting

If the run stops on wall-clock budget or local interruption, resume the same
run id. Resume uses the existing `autoresearch/local-qt-p001` branch and
`.worktrees/local-qt-p001/` worktree.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign quantum-tanner-autoresearch --wall-clock 15m --run-id local-qt-p001 --resume
```

Approval gate: review the latest `experiment-log.tsv`, `run_status.json`,
`screening.json` files, and git commits on `autoresearch/local-qt-p001` before
deciding to resume.

## 5. Regenerate the Run Report

Autoresearch finalization writes `report.html` automatically. Re-run the report
command after manual inspection or after checking out the autoresearch branch.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli report --root .worktrees/local-qt-p001 --run results/search/quantum-tanner-autoresearch/local-qt-p001
```

Review
`.worktrees/local-qt-p001/results/search/quantum-tanner-autoresearch/local-qt-p001/report.html`
and the compact
`.worktrees/local-qt-p001/results/search/quantum-tanner-autoresearch/local-qt-p001/run-summary.html`.

Codex CLI can wait on shell commands without spending tokens on wall-clock
time. The operator should summarize command outcomes into the run artifacts and
review notes instead of streaming long decoder logs into chat.

## 6. Build the Surface-Copy Comparison

Run the comparison from the original checkout root after the Tanner run exists
in `.worktrees/local-qt-p001/`.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-surface-copy --root .worktrees/local-qt-p001 --run results/search/quantum-tanner-autoresearch/local-qt-p001 --baseline benchmarks/baselines/rotated-surface-single-logical-p001.json --out /tmp/quantum-tanner-surface-copy.html
```

This writes `/tmp/quantum-tanner-surface-copy.html` and
`/tmp/quantum-tanner-surface-copy.json`. The comparison uses only Tanner points
whose manifest records `logical_failure_aggregation: "any_logical"`. It chooses
the largest odd surface distance `d` satisfying `k*d*d <= n`, then computes the
copied block surface logical failure probability from the single patch with
`1 - (1 - P_single)^k`.

Approval gate: compare the HTML and JSON with the Tanner `report.html` before
copying conclusions into a report or PR. Rejected comparison rows are evidence
of incompatible units or budgets, not losses.

## 7. Final Review Checklist

- Preflight output was reviewed before running.
- `validate --root .` passed before running.
- The run id and wall-clock budget were chosen by a human operator.
- Every candidate has a visible `screening.json`.
- Admitted Tanner points use `p=0.001`.
- Surface-copy comparison used
  `benchmarks/baselines/rotated-surface-single-logical-p001.json`.
- Upper-bound distances were not treated as exact Zoo-promotion evidence.
- Cluster execution was deferred to GitHub issue #20.
````

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
PYTHONPATH=src pytest -q tests/test_search_docs.py -k quantum_tanner_autoresearch_workflow
```

Expected: `2 passed`.

- [ ] **Step 5: Run the requested full repository verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add tests/test_search_docs.py campaigns/examples/quantum-tanner-autoresearch/README.md docs/superpowers/plans/2026-07-08-issue-46-quantum-tanner-autoresearch-workflow.md
git commit -m "docs: add quantum Tanner autoresearch workflow"
```

## Plan Self-Review

The plan covers the issue's command-block requirements, the p=0.001 guardrail,
the copied-surface formula, the upper-bound no-promotion warning, local-only
scope, and the requested verification commands. No placeholders remain in
commands. The implementation task is intentionally single-task because the
change is a documentation page plus its direct documentation tests; splitting
the two would create an unreviewable intermediate state where failing tests are
committed without the document.

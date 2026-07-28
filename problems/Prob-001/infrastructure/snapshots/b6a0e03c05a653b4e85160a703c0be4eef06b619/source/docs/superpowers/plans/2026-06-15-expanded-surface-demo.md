# Expanded Surface Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the M1 rotated surface-code showcase to d=3/5/7 across p=`0.001,0.002,0.005,0.01,0.02`.

**Architecture:** The campaign source records define the larger candidate and p matrix. The autoresearch loop consumes the task's full p-list, while promotion rules only add missing extra p values. The committed `m1-demo` artifacts are regenerated from those source records and remain the single canonical M1 result.

**Tech Stack:** Python package under `src/autoqec_search`, pytest, JSON source records, TensorQEC Julia scripts for finite CSS instances, `rsinter` for final benchmark artifacts.

---

## File Structure

- Modify `src/autoqec_search/run_loop.py`: change p-value selection so autoresearch uses all task p values.
- Modify `tests/test_search_run_loop.py`: add RED tests for full task p-list selection.
- Modify `tests/test_search_source_data.py`: pin the expanded example source records.
- Modify `tests/test_search_run_cli.py`: update fake-run expectations from two d=3 candidates to d=3/5/7.
- Modify `tests/test_search_e2e.py`: assert the committed M1 run has three distances and five p values.
- Modify `tests/test_search_docs.py`, `README.md`, and `CLAUDE.md`: describe the expanded M1 final showcase.
- Modify JSON records under `campaigns/examples/rotated-surface-baseline/` and `benchmarks/tasks/`.
- Create `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d5/` and `rotated-surface-code-d7/`.
- Replace generated artifacts under `results/search/rotated-surface-baseline/m1-demo/`.

### Task 1: RED Test For Full Autoresearch P-List

**Files:**
- Modify: `tests/test_search_run_loop.py`
- Modify: `src/autoqec_search/run_loop.py`

- [ ] **Step 1: Write failing p-list tests**

Add `autoresearch_evaluation_p_values` to the import list in `tests/test_search_run_loop.py`:

```python
from autoqec_search.run_loop import (
    CandidateRecord,
    RunConfig,
    autoresearch_evaluation_p_values,
    candidate_is_complete,
    choose_seed,
    default_tag,
    parse_wall_clock_seconds,
    representative_ler,
    update_frontier,
    validate_path_segment,
)
```

Add these helpers and tests after `test_representative_ler_rejects_invalid_ler_values`:

```python
def _write_campaign_with_promote_rule(
    worktree_root: Path,
    run_root: Path,
    *,
    rule_p: float,
) -> None:
    campaign_dir = worktree_root / "campaigns" / "examples" / "rotated-surface-baseline"
    campaign_dir.mkdir(parents=True)
    (campaign_dir / "campaign.json").write_text(
        json.dumps({"id": "rotated-surface-baseline"}) + "\n"
    )
    (campaign_dir / "promote_rules.json").write_text(
        json.dumps({"max_ler_at_p": {"p": rule_p, "ler": 0.5}}) + "\n"
    )
    run_root.mkdir(parents=True)
    (run_root / "run_spec.json").write_text(
        json.dumps({"campaign_id": "rotated-surface-baseline"}) + "\n"
    )


def test_autoresearch_evaluation_p_values_uses_task_p_list(tmp_path: Path) -> None:
    worktree_root = tmp_path / "worktree"
    run_root = tmp_path / "run"
    task_p_list = [0.001, 0.002, 0.005, 0.01, 0.02]
    _write_campaign_with_promote_rule(worktree_root, run_root, rule_p=0.005)

    assert autoresearch_evaluation_p_values(
        worktree_root,
        run_root,
        task_p_list,
    ) == task_p_list


def test_autoresearch_evaluation_p_values_appends_extra_promotion_p(
    tmp_path: Path,
) -> None:
    worktree_root = tmp_path / "worktree"
    run_root = tmp_path / "run"
    _write_campaign_with_promote_rule(worktree_root, run_root, rule_p=0.005)

    assert autoresearch_evaluation_p_values(
        worktree_root,
        run_root,
        [0.001, 0.002],
    ) == [0.001, 0.002, 0.005]
```

- [ ] **Step 2: Run RED test**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_run_loop.py::test_autoresearch_evaluation_p_values_uses_task_p_list tests/test_search_run_loop.py::test_autoresearch_evaluation_p_values_appends_extra_promotion_p -q
```

Expected: FAIL because `autoresearch_evaluation_p_values` currently treats the third argument as one representative float, not a list.

- [ ] **Step 3: Implement minimal p-list behavior**

In `src/autoqec_search/run_loop.py`, replace the function with:

```python
def autoresearch_evaluation_p_values(
    worktree_root: Path,
    run_root: Path,
    task_p_list: list[float],
) -> list[float]:
    p_values = list(task_p_list)
    rule_p = _promotion_rule_p_without_validation(worktree_root, run_root)
    if rule_p is not None and rule_p not in p_values:
        p_values.append(rule_p)
    return p_values
```

Update the call in `run_autoresearch`:

```python
selected_p_values = autoresearch_evaluation_p_values(
    worktree_root,
    run_root,
    [float(value) for value in task["p_list"]],
)
```

- [ ] **Step 4: Run GREEN test**

Run the same focused pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_search_run_loop.py src/autoqec_search/run_loop.py
git commit -m "fix: evaluate full autoresearch p list"
```

### Task 2: RED Test And Update Source Records

**Files:**
- Modify: `tests/test_search_source_data.py`
- Modify: `campaigns/examples/rotated-surface-baseline/campaign.json`
- Modify: `campaigns/examples/rotated-surface-baseline/search_space.json`
- Modify: `benchmarks/tasks/rotated-memory-x-cdep-v1.json`

- [ ] **Step 1: Write failing source-data assertions**

In `tests/test_search_source_data.py`, replace the current candidate-id and campaign-budget assertions with:

```python
    search_space = _load_json(example_root / "search_space.json")
    candidate_ids = [
        candidate["candidate_id"] for candidate in search_space["candidate_specs"]
    ]
    assert candidate_ids == [
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ]
    assert [
        candidate["parameters"]["distance"]
        for candidate in search_space["candidate_specs"]
    ] == [3, 5, 7]

    task = _load_json(REPO_ROOT / "benchmarks" / "tasks" / "rotated-memory-x-cdep-v1.json")
    assert task["p_list"] == [0.001, 0.002, 0.005, 0.01, 0.02]

    campaign = _load_json(example_root / "campaign.json")
    assert campaign["budget"]["max_candidates"] == 3
    assert campaign["stop_conditions"]["max_candidates"] == 3
```

- [ ] **Step 2: Run RED test**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_source_data.py::test_search_example_source_files_validate_against_checked_in_schemas -q
```

Expected: FAIL because source records still have two d=3 candidates and four p values.

- [ ] **Step 3: Update source records**

Set `campaign.json` max candidates to `3`:

```json
  "budget": {
    "wall_clock_seconds": 3600,
    "max_candidates": 3
  },
  "stop_conditions": {
    "max_candidates": 3,
    "max_wall_clock_seconds": 3600
  },
```

Set `benchmarks/tasks/rotated-memory-x-cdep-v1.json` p-list to:

```json
  "p_list": [
    0.001,
    0.002,
    0.005,
    0.01,
    0.02
  ],
```

Set `search_space.json` candidate specs to:

```json
  "candidate_specs": [
    {
      "candidate_id": "rotated-surface-d3-example",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 3,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "seed",
        "label": "repo-example-d3"
      }
    },
    {
      "candidate_id": "rotated-surface-d5-example",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 5,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "seed",
        "label": "repo-example-d5"
      }
    },
    {
      "candidate_id": "rotated-surface-d7-example",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 7,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "seed",
        "label": "repo-example-d7"
      }
    }
  ]
```

- [ ] **Step 4: Run GREEN test**

Run the same source-data pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_search_source_data.py campaigns/examples/rotated-surface-baseline/campaign.json campaigns/examples/rotated-surface-baseline/search_space.json benchmarks/tasks/rotated-memory-x-cdep-v1.json
git commit -m "feat: expand rotated surface search matrix"
```

### Task 3: Update Run CLI Tests For Three Distances

**Files:**
- Modify: `tests/test_search_run_cli.py`

- [ ] **Step 1: Write failing assertions for d=3/5/7 run output**

Update `_assert_lab_notebook` so it expects all three distances in the fake autoresearch run:

```python
    for candidate_id in (
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ):
        assert candidate_id in report

    log = (run_root / "experiment-log.tsv").read_text()
    assert "rotated-surface-d3-example\t0.013\tkeep\tentered frontier for distance 3" in log
    assert "rotated-surface-d5-example\t0.02\tkeep\tentered frontier for distance 5" in log
    assert "rotated-surface-d7-example\t0.02\tkeep\tentered frontier for distance 7" in log

    leaderboard = (run_root / "leaderboard.csv").read_text()
    assert "rotated-surface-d3-example" in leaderboard
    assert "rotated-surface-d5-example" in leaderboard
    assert "rotated-surface-d7-example" in leaderboard
```

Update branch-log assertions to expect `evaluate rotated-surface-d5-example` and `evaluate rotated-surface-d7-example` instead of `rotated-surface-d3-repeat`.

In `test_run_autoresearch_allow_dirty_root_uses_clean_branch_state`, replace the candidate-id assertion with:

```python
    assert run_spec["candidate_ids"] == [
        "rotated-surface-d3-example",
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ]
    log = (run_root / "experiment-log.tsv").read_text()
    assert "rotated-surface-d7-example\t0.02\tkeep\tentered frontier for distance 7" in log
```

- [ ] **Step 2: Run RED test**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_run_cli.py::test_run_autoresearch_orchestrates_worktree_branch_and_lab_notebook tests/test_search_run_cli.py::test_run_autoresearch_allow_dirty_root_uses_clean_branch_state -q
```

Expected: FAIL until source records and fake run expectations agree.

- [ ] **Step 3: Keep fake rsinter emitting all p values**

The fake helper already emits one record for every p value from `spec.toml`. Keep this stable error schedule so the d=3 candidate has LER `0.013` and d=5/d=7 have LER `0.02`:

```python
errors = 13 if spec_path.parts[-3] == "rotated-surface-d3-example" else 20
```

No production code change is part of this task.

- [ ] **Step 4: Run GREEN test**

Run the same focused pytest command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_search_run_cli.py
git commit -m "test: cover expanded autoresearch demo matrix"
```

### Task 4: Generate d=5 And d=7 Canonical Zoo Instances

**Files:**
- Create: `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d5/`
- Create: `zoo/codes/rotated-surface-code/instances/rotated-surface-code-d7/`
- Modify generated Zoo views/cards after rebuild.

- [ ] **Step 1: Confirm TensorQEC environment exists**

Run:

```bash
test -d julia/tensorqec_env && test -f julia/tensorqec_env/scripts/generate_instance.jl && test -f julia/tensorqec_env/scripts/compute_distance.jl
```

Expected: exit 0.

- [ ] **Step 2: Generate temporary bundles**

Run:

```bash
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/generate_instance.jl --code-id rotated-surface-code --distance 5 --output-root /private/tmp/autoqec-rotated-surface-code-d5
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/generate_instance.jl --code-id rotated-surface-code --distance 7 --output-root /private/tmp/autoqec-rotated-surface-code-d7
```

Expected: each temporary bundle has `instance.json`, `hx.json`, and `hz.json`.

- [ ] **Step 3: Compute and record distances**

Run:

```bash
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/compute_distance.jl --hx-path /private/tmp/autoqec-rotated-surface-code-d5/hx.json --hz-path /private/tmp/autoqec-rotated-surface-code-d5/hz.json
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/compute_distance.jl --hx-path /private/tmp/autoqec-rotated-surface-code-d7/hx.json --hz-path /private/tmp/autoqec-rotated-surface-code-d7/hz.json
```

Expected stdout JSON: `{"distance":5}` and `{"distance":7}`. Update each temporary `instance.json` so `derived_properties.distance` is the computed integer.

Use this structured JSON update:

```bash
python3 - <<'PY'
import json
from pathlib import Path
for distance in (5, 7):
    root = Path(f"/private/tmp/autoqec-rotated-surface-code-d{distance}")
    path = root / "instance.json"
    payload = json.loads(path.read_text())
    payload["derived_properties"]["distance"] = distance
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY
```

- [ ] **Step 4: Install generated bundles**

Create:

```text
zoo/codes/rotated-surface-code/instances/rotated-surface-code-d5/
zoo/codes/rotated-surface-code/instances/rotated-surface-code-d7/
```

Move each temporary bundle into the matching directory. Do not overwrite an existing directory.

- [ ] **Step 5: Rebuild Zoo views**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_zoo.cli build --root . --date 2026-06-15
```

Expected: generated Zoo views mention `rotated-surface-code-d5` and `rotated-surface-code-d7`.

- [ ] **Step 6: Validate source data**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_source_data.py::test_zoo_source_files_validate_against_checked_in_schemas tests/test_build.py::test_build_zoo_writes_indexes -q
```

Expected: PASS. If `test_build_zoo_writes_indexes` has exact counts, update it to expect the new instance count.

- [ ] **Step 7: Commit**

```bash
git add zoo/codes/rotated-surface-code/instances/rotated-surface-code-d5 zoo/codes/rotated-surface-code/instances/rotated-surface-code-d7 zoo/views zoo/codes/rotated-surface-code/card.md tests/test_build.py
git commit -m "feat: add larger rotated surface instances"
```

### Task 5: Update Docs And E2E Expectations

**Files:**
- Modify: `tests/test_search_e2e.py`
- Modify: `tests/test_search_docs.py`
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write failing e2e expectations**

In `tests/test_search_e2e.py`, add:

```python
CANDIDATE_IDS = [
    "rotated-surface-d3-example",
    "rotated-surface-d5-example",
    "rotated-surface-d7-example",
]
EXPECTED_DISTANCES = [3, 5, 7]
EXPECTED_P_VALUES = [0.001, 0.002, 0.005, 0.01, 0.02]
```

Update the run test to assert:

```python
    assert run.payload["candidate_ids"] == CANDIDATE_IDS
    assert run_status["frontier_size"] == 3

    for candidate_id in CANDIDATE_IDS:
        candidate_root = DEMO_RUN_ROOT / "candidates" / candidate_id
        for artifact_name in ("instance.json", "hx.json", "hz.json"):
            assert (candidate_root / "artifacts" / artifact_name).is_file()
        manifest = _load_json(
            candidate_root
            / "evaluations"
            / TASK_ID
            / DECODER_ID
            / "manifest.json"
        )
        assert [point["p"] for point in manifest["points"]] == EXPECTED_P_VALUES
```

Keep the existing golden p=0.005 exact check for `rotated-surface-d3-example`.

Update the report/promotion test to assert all promoted candidate ids:

```python
    assert set(CANDIDATE_IDS).issubset(promoted_ids)
    for candidate_id in CANDIDATE_IDS:
        instance_root = (
            REPO_ROOT
            / "zoo"
            / "codes"
            / "rotated-surface-code"
            / "instances"
            / candidate_id
        )
        for artifact_name in ("instance.json", "hx.json", "hz.json"):
            assert (instance_root / artifact_name).is_file()
```

- [ ] **Step 2: Update docs tests**

In `tests/test_search_docs.py`, add assertions that both README and CLAUDE mention:

```python
        assert "d=3/5/7" in document
        assert "0.001, 0.002, 0.005, 0.01, 0.02" in document
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py tests/test_search_docs.py -q
```

Expected: FAIL until docs and committed artifacts are regenerated.

- [ ] **Step 4: Update README and CLAUDE**

In both files' M1 showcase section, state that `m1-demo` covers d=3/5/7 and p=`0.001, 0.002, 0.005, 0.01, 0.02`. Mention promoted instances under:

```text
zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/
zoo/codes/rotated-surface-code/instances/rotated-surface-d5-example/
zoo/codes/rotated-surface-code/instances/rotated-surface-d7-example/
```

- [ ] **Step 5: Commit docs/test expectation changes**

Commit these expectation changes before regenerating artifacts. The e2e test remains red until Task 6 replaces `m1-demo`.

```bash
git add tests/test_search_e2e.py tests/test_search_docs.py README.md CLAUDE.md
git commit -m "docs: describe expanded m1 surface showcase"
```

### Task 6: Regenerate The Canonical `m1-demo` Run

**Files:**
- Replace: `results/search/rotated-surface-baseline/m1-demo/`
- Create or update promoted instances:
  - `zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/`
  - `zoo/codes/rotated-surface-code/instances/rotated-surface-d5-example/`
  - `zoo/codes/rotated-surface-code/instances/rotated-surface-d7-example/`
- Modify generated Zoo views/cards after promotion.

- [ ] **Step 1: Remove the old committed run from the PR branch**

Run after confirming `git status -sb` is clean:

```bash
rm -rf results/search/rotated-surface-baseline/m1-demo
git add -A results/search/rotated-surface-baseline/m1-demo
git commit -m "chore: remove old m1 demo artifacts"
```

Expected: `results/search/rotated-surface-baseline/m1-demo` is absent from the current branch so the run branch can recreate it.

- [ ] **Step 2: Remove stale local autoresearch branch if present**

Run:

```bash
git branch --list autoresearch/m1-demo
```

If it exists, run:

```bash
git branch -d autoresearch/m1-demo
```

Expected: branch is absent before rerun. If `-d` refuses because it is unmerged, stop and ask before force-deleting.

- [ ] **Step 3: Run autoresearch from a clean PR branch**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 3600s --run-id m1-demo --cleanup-worktree
```

Expected: branch `autoresearch/m1-demo` is created and finalized. It evaluates d=3, d=5, and d=7, each with five p points.

- [ ] **Step 4: Fast-forward merge generated artifacts**

Run from the PR branch worktree:

```bash
git merge --ff-only autoresearch/m1-demo
```

Expected: current branch now contains the regenerated `m1-demo` artifacts and promotion outputs.

- [ ] **Step 5: Sanitize committed run host**

Edit `results/search/rotated-surface-baseline/m1-demo/env.json` so:

```json
  "host": "committed-m1-demo"
```

Regenerate the report after the env edit:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/m1-demo
```

Commit the sanitization if it changes files:

```bash
git add results/search/rotated-surface-baseline/m1-demo
git commit -m "chore: sanitize expanded m1 demo provenance"
```

- [ ] **Step 6: Sanity-check expanded artifacts**

Run:

```bash
PYTHONPATH=src python3 - <<'PY'
import json
from pathlib import Path
root = Path("results/search/rotated-surface-baseline/m1-demo")
expected_candidates = [
    "rotated-surface-d3-example",
    "rotated-surface-d5-example",
    "rotated-surface-d7-example",
]
expected_p = [0.001, 0.002, 0.005, 0.01, 0.02]
run_spec = json.loads((root / "run_spec.json").read_text())
assert run_spec["candidate_ids"] == expected_candidates
for candidate_id in expected_candidates:
    manifest = json.loads((root / "candidates" / candidate_id / "evaluations" / "rotated-memory-x-cdep-v1" / "rmatching-default-v1" / "manifest.json").read_text())
    assert [point["p"] for point in manifest["points"]] == expected_p
print("expanded m1 artifact matrix ok")
PY
```

Expected: prints `expanded m1 artifact matrix ok`.

### Task 7: Final Verification And PR Update

**Files:**
- No planned code edits beyond fixes found by verification.

- [ ] **Step 1: Run focused tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_run_loop.py tests/test_search_source_data.py tests/test_search_run_cli.py tests/test_search_e2e.py tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS with existing deselections only.

- [ ] **Step 3: Validate search layer**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: validates committed campaigns, suites, and runs.

- [ ] **Step 4: Check for local path leaks**

Run:

```bash
rg -n "/Users/|issue-13-m1-showcase|nzydeMac-mini.local|\\.worktrees/m1-demo" results/search/rotated-surface-baseline/m1-demo
```

Expected: no matches.

- [ ] **Step 5: Push PR branch**

Run:

```bash
git status -sb
git push
```

Expected: branch `codex/issue-13-m1-showcase` is pushed to PR #27.

# Issue 17 General CSS Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `autoqec-search eval --general-css` mode that converts stored CSS `hx/hz` artifacts into the upstream rstim CSS contract, runs `rsinter`, and reproduces the rotated-surface d=3 golden fixture through that path.

**Architecture:** Keep the existing surface-specific adapter as the default path. Add focused CSS helpers in `autoqec_search.rsinter`, thread a `general_css` boolean through `cli.py` and `eval_run.py`, and keep completed manifests, plotting, reports, and promotion consumers unchanged.

**Tech Stack:** Python 3.11+, `pytest`, `jsonschema`, stdlib `tomllib`, existing `autoqec_search` modules, external `rsinter` CLI.

---

## File Structure

- Modify `src/autoqec_search/rsinter.py`: add CSS matrix wrapper conversion, CSS TOML generation, task observable to CSS basis mapping, and old-backend CSS error normalization. Keep `write_spec_toml(...)` as the surface-compatible public wrapper.
- Modify `src/autoqec_search/eval_run.py`: add `general_css: bool = False`, write CSS wrapper files after copying candidate artifacts, and choose `write_css_spec_toml(...)` only when requested.
- Modify `src/autoqec_search/cli.py`: add `--general-css` to `eval` and pass it to `evaluate_single_candidate(...)`.
- Modify `tests/test_search_rsinter.py`: add unit coverage for CSS wrapper conversion, CSS spec generation, unsupported observables, CSS rows without `params.distance`, and CSS backend-error normalization.
- Modify `tests/test_search_eval_cli.py`: teach fake `rsinter` both surface and CSS specs, then test fixture reproduction, baseline CSS smoke, CSS artifacts, and old-backend failure behavior.
- Create `benchmarks/tasks/rotated-memory-x-cdep-v1.json`: fixture-compatible x-basis task matching `benchmarks/fixtures/rotated-d3/expected.json`.
- Create `benchmarks/suites/rotated-surface-css-fixture-v1.json`: one-task, one-decoder suite for the golden reproduction point.
- Create `campaigns/examples/rotated-surface-css-fixture/campaign.json` and `search_space.json`: narrow fixture campaign selecting the existing d=3 rotated-surface candidate.
- Modify `tests/test_search_load.py` and `tests/test_search_cli.py`: update expected workspace counts and ids.
- Modify `README.md`, `CLAUDE.md`, and `tests/test_search_docs.py`: document the default surface path, `--general-css`, and fixture reproduction command.

---

### Task 1: Add rsinter CSS Adapter Unit Tests

**Files:**
- Modify: `tests/test_search_rsinter.py`

- [ ] **Step 1: Write failing CSS adapter tests**

Append these tests after `test_write_spec_toml_rejects_invalid_batch_size` in `tests/test_search_rsinter.py`, and add `write_css_matrix_wrapper` and `write_css_spec_toml` to the existing import from `autoqec_search.rsinter`.

```python
def test_write_css_matrix_wrapper_converts_autoqec_dense_matrix(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "rsinter" / "input" / "hx.css.json"
    source = {
        "format": "dense_binary_matrix",
        "n_rows": 2,
        "n_cols": 3,
        "data": [[1, 0, 1], [0, 1, 0]],
    }

    write_css_matrix_wrapper(output_path, source)

    assert json.loads(output_path.read_text()) == {
        "format": "dense",
        "rows": [[1, 0, 1], [0, 1, 0]],
    }


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"format": "dense", "n_rows": 1, "n_cols": 1, "data": [[1]]}, "format"),
        (
            {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 2, "data": [[1]]},
            "row width",
        ),
        (
            {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 1, "data": [[2]]},
            "binary",
        ),
    ],
)
def test_write_css_matrix_wrapper_rejects_invalid_payloads(
    tmp_path: Path,
    payload: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(SearchIntegrityError, match=match):
        write_css_matrix_wrapper(tmp_path / "bad.css.json", payload)


def test_write_css_spec_toml_writes_general_css_runner_params(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "rotated-memory-x-cdep-v1",
        "observable": "logical_x",
        "p_list": [0.005],
        "collection": {"max_shots": 100000, "max_errors": 1000},
    }
    decoders = {
        "rmatching-default-v1": {
            "id": "rmatching-default-v1",
            "impl_key": "rmatching",
            "language": "rust",
        }
    }

    write_css_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rmatching-default-v1"],
        code_id="rotated-surface-code",
        hx_path=Path("input/hx.css.json"),
        hz_path=Path("input/hz.css.json"),
        rounds=3,
        p_values=[0.005],
    )

    parsed = tomllib.loads(spec_path.read_text())
    assert parsed["name"] == "autoqec-rotated-memory-x-cdep-v1"
    assert parsed["plot"]["series"] == {
        "group_by": ["runner", "params.code_id"],
        "label_template": "{runner} {params.code_id}",
    }
    assert parsed["runner"] == [
        {
            "name": "rmatching-default-v1",
            "language": "rust",
            "impl_key": "rmatching",
            "params": {
                "input_type": "css",
                "code_id": "rotated-surface-code",
                "hx": "input/hx.css.json",
                "hz": "input/hz.css.json",
                "basis": "x",
                "schedule": "greedy",
                "rounds": [3],
                "p": [0.005],
                "max_shots": 100000,
                "max_errors": 1000,
                "batch_size": 256,
            },
        }
    ]
    assert "distance" not in parsed["runner"][0]["params"]


def test_write_css_spec_toml_maps_logical_z_to_basis_z(tmp_path: Path) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "rotated-memory-z-cdep-v1",
        "observable": "logical_z",
        "p_list": [0.008],
        "collection": {"max_shots": 1000, "max_errors": 50},
    }
    decoders = {
        "rmatching-default-v1": {
            "id": "rmatching-default-v1",
            "impl_key": "rmatching",
            "language": "rust",
        }
    }

    write_css_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rmatching-default-v1"],
        code_id="rotated-surface-code",
        hx_path=Path("input/hx.css.json"),
        hz_path=Path("input/hz.css.json"),
        rounds=9,
        p_values=[0.008],
    )

    assert tomllib.loads(spec_path.read_text())["runner"][0]["params"]["basis"] == "z"


def test_write_css_spec_toml_rejects_unsupported_observable(tmp_path: Path) -> None:
    task = {
        "id": "unsupported-task",
        "observable": "logical_y",
        "p_list": [0.005],
        "collection": {"max_shots": 1000, "max_errors": 50},
    }
    decoders = {
        "rmatching-default-v1": {
            "id": "rmatching-default-v1",
            "impl_key": "rmatching",
            "language": "rust",
        }
    }

    with pytest.raises(SearchIntegrityError, match="unsupported task observable"):
        write_css_spec_toml(
            tmp_path / "spec.toml",
            task=task,
            decoders=decoders,
            selected_decoder_ids=["rmatching-default-v1"],
            code_id="rotated-surface-code",
            hx_path=Path("input/hx.css.json"),
            hz_path=Path("input/hz.css.json"),
            rounds=3,
            p_values=[0.005],
        )


def test_parse_results_jsonl_accepts_css_rows_without_distance(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    record = _result_record(params={"distance": None})
    del record["params"]["distance"]
    path.write_text(json.dumps(record, sort_keys=True) + "\n")

    points = parse_results_jsonl(
        path,
        expected_decoder_id="rmatching-default-v1",
        expected_task_id="rotated-memory-x-cdep-v1",
        expected_distance=3,
        expected_p_values=[0.005],
    )

    assert points[0]["p"] == 0.005
    assert points[0]["rounds"] == 3
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py -q
```

Expected: FAIL with import errors for `write_css_matrix_wrapper` and `write_css_spec_toml`.

- [ ] **Step 3: Keep the red tests for the next task**

Run `git status --short` and confirm `tests/test_search_rsinter.py` is the only
modified file. Do not commit the failing tests by themselves; Task 2 commits
the tests with the implementation after the target test file is green.

---

### Task 2: Implement rsinter CSS Helpers

**Files:**
- Modify: `src/autoqec_search/rsinter.py`
- Test: `tests/test_search_rsinter.py`

- [ ] **Step 1: Add CSS helper implementation**

In `src/autoqec_search/rsinter.py`, add `from typing import Any` to the imports. Then insert these helpers above `write_spec_toml(...)`:

```python
def _collection_batch_size(collection: dict) -> int:
    batch_size = int(collection.get("batch_size", RSINTER_DEFAULT_BATCH_SIZE))
    if batch_size <= 0:
        raise SearchIntegrityError(f"invalid rsinter batch_size: {batch_size}")
    return batch_size


def _p_list_text(p_values: list[float]) -> str:
    return ", ".join(str(value) for value in p_values)


def _benchmark_header_lines(task: dict) -> list[str]:
    benchmark_name = f"autoqec-{task['id']}"
    return [
        f"name = {_toml_string(benchmark_name)}",
        "version = 1",
        'mode = "independent"',
        "",
    ]


def _plot_lines(task: dict, *, css: bool) -> list[str]:
    plot_title = f"AutoQEC {task['id']}"
    group_by = '["runner", "params.code_id"]' if css else '["runner", "params.distance"]'
    label_template = "{runner} {params.code_id}" if css else "{runner} d={params.distance}"
    return [
        "[plot]",
        f"title = {_toml_string(plot_title)}",
        "[plot.x]",
        'field = "params.p"',
        'scale = "log"',
        'label = "Physical Error Rate"',
        "[plot.series]",
        f"group_by = {group_by}",
        f"label_template = {_toml_string(label_template)}",
        "[[plot.panel]]",
        'metric = "metrics.logical_error_rate"',
        'scale = "log"',
        'label = "Logical Error Rate"',
        "",
    ]


def _require_dense_binary_matrix(payload: dict[str, Any]) -> list[list[int]]:
    if payload.get("format") != "dense_binary_matrix":
        raise SearchIntegrityError("CSS matrix format must be dense_binary_matrix")
    n_rows = payload.get("n_rows")
    n_cols = payload.get("n_cols")
    data = payload.get("data")
    if type(n_rows) is not int or n_rows < 0:
        raise SearchIntegrityError("CSS matrix n_rows must be a nonnegative integer")
    if type(n_cols) is not int or n_cols < 0:
        raise SearchIntegrityError("CSS matrix n_cols must be a nonnegative integer")
    if not isinstance(data, list) or len(data) != n_rows:
        raise SearchIntegrityError("CSS matrix data row count does not match n_rows")
    rows: list[list[int]] = []
    for row_index, row in enumerate(data):
        if not isinstance(row, list) or len(row) != n_cols:
            raise SearchIntegrityError(f"CSS matrix row width mismatch at row {row_index}")
        converted_row: list[int] = []
        for col_index, value in enumerate(row):
            if value not in (0, 1):
                raise SearchIntegrityError(
                    f"CSS matrix entries must be binary at row {row_index}, col {col_index}"
                )
            converted_row.append(int(value))
        rows.append(converted_row)
    return rows


def write_css_matrix_wrapper(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = _require_dense_binary_matrix(payload)
    output_path.write_text(
        json.dumps({"format": "dense", "rows": rows}, indent=2, sort_keys=True) + "\n"
    )


def _basis_for_task(task: dict) -> str:
    observable = task.get("observable")
    if observable == "logical_x":
        return "x"
    if observable == "logical_z":
        return "z"
    raise SearchIntegrityError(f"unsupported task observable for CSS eval: {observable}")
```

Replace the current body of `write_spec_toml(...)` with a call to a new `write_surface_spec_toml(...)`, and add `write_css_spec_toml(...)` below it:

```python
def write_spec_toml(
    spec_path: str | Path,
    *,
    task: dict,
    decoders: dict[str, dict],
    selected_decoder_ids: list[str],
    distance: int,
    rounds: int,
    p_values: list[float],
) -> None:
    write_surface_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=selected_decoder_ids,
        distance=distance,
        rounds=rounds,
        p_values=p_values,
    )


def write_surface_spec_toml(
    spec_path: str | Path,
    *,
    task: dict,
    decoders: dict[str, dict],
    selected_decoder_ids: list[str],
    distance: int,
    rounds: int,
    p_values: list[float],
) -> None:
    output_path = Path(spec_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    p_list = _p_list_text(p_values)
    collection = task["collection"]
    batch_size = _collection_batch_size(collection)

    lines = _benchmark_header_lines(task)
    for decoder_id in selected_decoder_ids:
        decoder = decoders[decoder_id]
        lines.extend(
            [
                "[[runner]]",
                f"name = {_toml_string(decoder_id)}",
                f"language = {_toml_string(decoder.get('language', 'rust'))}",
                f"impl_key = {_toml_string(decoder['impl_key'])}",
                "[runner.params]",
                f"distance = [{distance}]",
                f"rounds = [{rounds}]",
                f"p = [{p_list}]",
                f'max_shots = {int(collection["max_shots"])}',
                f'max_errors = {int(collection["max_errors"])}',
                f"batch_size = {batch_size}",
                "",
            ]
        )
    lines.extend(_plot_lines(task, css=False))
    output_path.write_text("\n".join(lines))


def write_css_spec_toml(
    spec_path: str | Path,
    *,
    task: dict,
    decoders: dict[str, dict],
    selected_decoder_ids: list[str],
    code_id: str,
    hx_path: str | Path,
    hz_path: str | Path,
    rounds: int,
    p_values: list[float],
    schedule: str = "greedy",
) -> None:
    output_path = Path(spec_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    p_list = _p_list_text(p_values)
    collection = task["collection"]
    batch_size = _collection_batch_size(collection)
    basis = _basis_for_task(task)
    hx_text = Path(hx_path).as_posix()
    hz_text = Path(hz_path).as_posix()

    lines = _benchmark_header_lines(task)
    for decoder_id in selected_decoder_ids:
        decoder = decoders[decoder_id]
        lines.extend(
            [
                "[[runner]]",
                f"name = {_toml_string(decoder_id)}",
                f"language = {_toml_string(decoder.get('language', 'rust'))}",
                f"impl_key = {_toml_string(decoder['impl_key'])}",
                "[runner.params]",
                'input_type = "css"',
                f"code_id = {_toml_string(code_id)}",
                f"hx = {_toml_string(hx_text)}",
                f"hz = {_toml_string(hz_text)}",
                f"basis = {_toml_string(basis)}",
                f"schedule = {_toml_string(schedule)}",
                f"rounds = [{rounds}]",
                f"p = [{p_list}]",
                f'max_shots = {int(collection["max_shots"])}',
                f'max_errors = {int(collection["max_errors"])}',
                f"batch_size = {batch_size}",
                "",
            ]
        )
    lines.extend(_plot_lines(task, css=True))
    output_path.write_text("\n".join(lines))
```

- [ ] **Step 2: Run rsinter tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit rsinter CSS helpers**

```bash
git add src/autoqec_search/rsinter.py tests/test_search_rsinter.py
git commit -m "feat: add rsinter css spec helpers"
```

---

### Task 3: Add Fixture Campaign Contracts

**Files:**
- Create: `benchmarks/tasks/rotated-memory-x-cdep-v1.json`
- Create: `benchmarks/suites/rotated-surface-css-fixture-v1.json`
- Create: `campaigns/examples/rotated-surface-css-fixture/campaign.json`
- Create: `campaigns/examples/rotated-surface-css-fixture/search_space.json`
- Modify: `tests/test_search_load.py`
- Modify: `tests/test_search_cli.py`

- [ ] **Step 1: Add fixture task**

Create `benchmarks/tasks/rotated-memory-x-cdep-v1.json`:

```json
{
  "id": "rotated-memory-x-cdep-v1",
  "title": "Rotated Memory X under circuit depolarizing noise",
  "observable": "logical_x",
  "noise_model": "circuit_depolarizing",
  "input_type": "stim-detector-error-model",
  "p_list": [
    0.005
  ],
  "rounds_policy": {
    "kind": "distance-scaled",
    "multiplier": 1,
    "minimum": 3
  },
  "collection": {
    "max_shots": 100000,
    "max_errors": 1000
  },
  "result_metrics": [
    "logical_error_rate"
  ],
  "execution_status": "real"
}
```

- [ ] **Step 2: Add fixture suite**

Create `benchmarks/suites/rotated-surface-css-fixture-v1.json`:

```json
{
  "id": "rotated-surface-css-fixture-v1",
  "title": "Rotated Surface CSS Fixture v1",
  "task_ids": [
    "rotated-memory-x-cdep-v1"
  ],
  "decoder_ids": [
    "rmatching-default-v1"
  ],
  "shared_settings": {
    "runner": "rsinter",
    "fixture_manifest": "benchmarks/fixtures/manifest.json"
  }
}
```

- [ ] **Step 3: Add fixture campaign**

Create `campaigns/examples/rotated-surface-css-fixture/campaign.json`:

```json
{
  "id": "rotated-surface-css-fixture",
  "title": "Rotated Surface CSS Fixture",
  "objective": "Reproduce the rotated d=3 golden fixture through the general CSS adapter.",
  "family_id": "surface-code",
  "default_suite_id": "rotated-surface-css-fixture-v1",
  "budget": {
    "wall_clock_seconds": 3600,
    "max_candidates": 1
  },
  "stop_conditions": {
    "max_candidates": 1,
    "max_wall_clock_seconds": 3600
  },
  "random_seed_policy": {
    "mode": "fixed",
    "seed": 7
  }
}
```

Create `campaigns/examples/rotated-surface-css-fixture/search_space.json`:

```json
{
  "campaign_id": "rotated-surface-css-fixture",
  "mode": "explicit_list",
  "candidate_specs": [
    {
      "candidate_id": "rotated-surface-d3-example",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 3,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "fixture",
        "label": "repo-example-d3"
      }
    }
  ]
}
```

- [ ] **Step 4: Update workspace count tests**

In `tests/test_search_load.py`, change the expected ids in `test_load_search_workspace_collects_campaigns_and_contracts` to:

```python
    assert sorted(workspace.campaigns) == [
        "rotated-surface-baseline",
        "rotated-surface-css-fixture",
        "rotated-surface-strategy-fixture",
    ]
    assert sorted(workspace.search_spaces) == [
        "rotated-surface-baseline",
        "rotated-surface-css-fixture",
        "rotated-surface-strategy-fixture",
    ]
    assert sorted(workspace.tasks) == [
        "rotated-memory-x-cdep-v1",
        M1_TASK_ID,
    ]
    assert sorted(workspace.suites) == [
        "rotated-surface-baseline-v1",
        "rotated-surface-css-fixture-v1",
    ]
```

In `tests/test_search_cli.py`, update `test_validate_command_reports_workspace_counts` to assert:

```python
    assert "3 campaigns" in result.stdout
    assert "2 suites" in result.stdout
```

- [ ] **Step 5: Run contract tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_load.py::test_load_search_workspace_collects_campaigns_and_contracts tests/test_search_cli.py::test_validate_command_reports_workspace_counts -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: both commands PASS, and validate prints `3 campaigns` and `2 suites`.

- [ ] **Step 6: Commit fixture contracts**

```bash
git add benchmarks/tasks/rotated-memory-x-cdep-v1.json benchmarks/suites/rotated-surface-css-fixture-v1.json campaigns/examples/rotated-surface-css-fixture/campaign.json campaigns/examples/rotated-surface-css-fixture/search_space.json tests/test_search_load.py tests/test_search_cli.py
git commit -m "feat: add rotated surface css fixture campaign"
```

---

### Task 4: Wire `--general-css` Through Eval

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `src/autoqec_search/eval_run.py`
- Modify: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Update fake rsinter for surface and CSS specs**

In `tests/test_search_eval_cli.py`, replace the body of `_write_fake_rsinter(...)` with a script that branches on `params.get("input_type")`:

```python
    executable.write_text(
        f"""#!{sys.executable}
import json
import sys
from pathlib import Path
import tomllib

if sys.argv[1:] == ["--version"]:
    print("rsinter git main abc123")
    raise SystemExit(0)

args = sys.argv[1:]
if args[:2] != ["bench", "run"]:
    raise SystemExit(2)

spec_path = Path(args[args.index("--spec") + 1])
out_dir = Path(args[args.index("--out") + 1])
spec = tomllib.loads(spec_path.read_text())
for runner in spec.get("runner", []):
    decoder_id = runner["name"]
    params = runner["params"]
    results_dir = out_dir / decoder_id / "test-run"
    results_dir.mkdir(parents=True, exist_ok=True)
    records = []
    rounds = int(params["rounds"][0])
    input_type = params.get("input_type", "surface_rotated_memory_x")
    if input_type == "css":
        hx_path = spec_path.parent / params["hx"]
        hz_path = spec_path.parent / params["hz"]
        hx = json.loads(hx_path.read_text())
        hz = json.loads(hz_path.read_text())
        if hx["format"] != "dense" or hz["format"] != "dense":
            raise SystemExit(11)
        if "distance" in params:
            raise SystemExit(12)
        include_distance = False
    else:
        distance = int(params["distance"][0])
        include_distance = True
    for index, p in enumerate(params["p"]):
        p = float(p)
        if p in (0.005, 0.01):
            shots = 76533
            errors = 1000
            decode_us_per_shot = 0.29047292017822396
            num_shots_generated = 76544
        else:
            shots = 1000
            errors = max(1, round(p * shots))
            decode_us_per_shot = 250.0 + index
            num_shots_generated = shots
        row_params = {{
            "rounds": rounds,
            "p": p,
        }}
        if include_distance:
            row_params["distance"] = distance
        records.append(
            json.dumps(
                {{
                    "benchmark": spec["name"],
                    "runner": decoder_id,
                    "language": runner["language"],
                    "status": "ok",
                    "params": row_params,
                    "case_summary": {{
                        "num_dets": 8,
                        "num_obs": 1,
                        "num_shots_generated": num_shots_generated,
                    }},
                    "metrics": {{
                        "shots_used": shots,
                        "logical_errors": errors,
                        "logical_error_rate": errors / shots,
                        "decode_us_per_shot": decode_us_per_shot,
                    }},
                    "artifacts": {{}},
                    "error": None,
                }},
                sort_keys=True,
            )
        )
    (results_dir / "results.jsonl").write_text("\\n".join(records) + "\\n")
raise SystemExit(0)
"""
    )
```

- [ ] **Step 2: Add failing CLI tests for CSS mode**

Add these tests after `test_eval_campaign_candidate_writes_completed_selected_manifest_and_plot`:

```python
def test_eval_general_css_fixture_reproduces_rotated_d3_golden(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-css-fixture",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.005",
        "--run-id",
        "css-fixture",
        "--general-css",
    )

    assert result.returncode == 0, result.stderr
    candidate_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-css-fixture"
        / "css-fixture"
        / "candidates"
        / "rotated-surface-d3-example"
    )
    assert sorted(path.name for path in (candidate_root / "rsinter" / "input").iterdir()) == [
        "hx.css.json",
        "hz.css.json",
    ]
    assert _load_json(candidate_root / "rsinter" / "input" / "hx.css.json")[
        "format"
    ] == "dense"
    spec_text = (candidate_root / "rsinter" / "spec.toml").read_text()
    assert 'input_type = "css"' in spec_text
    assert 'code_id = "rotated-surface-code"' in spec_text
    assert 'hx = "input/hx.css.json"' in spec_text
    assert 'hz = "input/hz.css.json"' in spec_text
    assert 'basis = "x"' in spec_text
    assert 'schedule = "greedy"' in spec_text
    assert "distance = [" not in spec_text

    completed_manifest = _load_json(
        candidate_root
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    point = completed_manifest["points"][0]
    expected = _load_json(
        work_root / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json"
    )
    assert completed_manifest["task_id"] == expected["task_id"]
    assert point["p"] == expected["p"]
    assert expected["binomial_ci_95"]["lower"] <= point["ler"]
    assert point["ler"] <= expected["binomial_ci_95"]["upper"]


def test_eval_general_css_baseline_uses_task_observable_for_basis_z(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "rotated-surface-baseline",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.008",
        "--run-id",
        "css-baseline",
        "--general-css",
    )

    assert result.returncode == 0, result.stderr
    spec_text = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "css-baseline"
        / "candidates"
        / "rotated-surface-d3-example"
        / "rsinter"
        / "spec.toml"
    ).read_text()
    assert 'input_type = "css"' in spec_text
    assert 'basis = "z"' in spec_text
```

- [ ] **Step 3: Run the new CLI tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py::test_eval_general_css_fixture_reproduces_rotated_d3_golden tests/test_search_eval_cli.py::test_eval_general_css_baseline_uses_task_observable_for_basis_z -q
```

Expected: FAIL because `--general-css` is not recognized.

- [ ] **Step 4: Add CLI option**

In `src/autoqec_search/cli.py`, add this next to the existing eval options:

```python
    eval_parser.add_argument("--general-css", action="store_true")
```

Update the `evaluate_single_candidate(...)` call to include:

```python
                general_css=args.general_css,
```

- [ ] **Step 5: Thread CSS mode through `eval_run.py`**

In `src/autoqec_search/eval_run.py`, update the import from `autoqec_search.rsinter` to include:

```python
    write_css_matrix_wrapper,
    write_css_spec_toml,
```

Add `general_css: bool = False` to both `evaluate_resolved_candidate_into_run(...)` and `evaluate_single_candidate(...)`.

Inside `evaluate_single_candidate(...)`, pass `general_css=general_css` into `evaluate_resolved_candidate_into_run(...)`.

In `evaluate_resolved_candidate_into_run(...)`, replace the single `write_spec_toml(...)` call with:

```python
    if general_css:
        input_dir = candidate_root / "rsinter" / "input"
        hx_input = input_dir / "hx.css.json"
        hz_input = input_dir / "hz.css.json"
        write_css_matrix_wrapper(hx_input, candidate.hx)
        write_css_matrix_wrapper(hz_input, candidate.hz)
        write_css_spec_toml(
            spec_path,
            task=task,
            decoders=workspace.decoders,
            selected_decoder_ids=selected_decoder_ids,
            code_id=candidate.spec.code_family,
            hx_path=Path("input/hx.css.json"),
            hz_path=Path("input/hz.css.json"),
            rounds=rounds,
            p_values=selected_p_values,
        )
    else:
        write_spec_toml(
            spec_path,
            task=task,
            decoders=workspace.decoders,
            selected_decoder_ids=selected_decoder_ids,
            distance=copied_distance,
            rounds=rounds,
            p_values=selected_p_values,
        )
```

- [ ] **Step 6: Run CSS eval tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py::test_eval_general_css_fixture_reproduces_rotated_d3_golden tests/test_search_eval_cli.py::test_eval_general_css_baseline_uses_task_observable_for_basis_z -q
```

Expected: PASS.

- [ ] **Step 7: Run existing eval tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py tests/test_search_rsinter.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit CSS eval wiring**

```bash
git add src/autoqec_search/cli.py src/autoqec_search/eval_run.py tests/test_search_eval_cli.py
git commit -m "feat: wire general css eval mode"
```

---

### Task 5: Normalize Old CSS Backend Failures

**Files:**
- Modify: `src/autoqec_search/rsinter.py`
- Modify: `tests/test_search_rsinter.py`
- Modify: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Add unit test for backend error normalization**

Append this test near the existing `run_rsinter` tests in `tests/test_search_rsinter.py`:

```python
def test_run_rsinter_normalizes_missing_general_css_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["/bin/rsinter", "bench", "run"],
            returncode=7,
            stdout="",
            stderr="unknown field `input_type` in runner params",
        )

    monkeypatch.setattr(rsinter_module.subprocess, "run", fake_run)

    with pytest.raises(SearchIntegrityError, match="upstream rstim general CSS support"):
        run_rsinter(tmp_path / "spec.toml", tmp_path / "out", executable="/bin/rsinter")
```

- [ ] **Step 2: Add CLI old-backend regression test**

Add this helper after `_write_failing_rsinter(...)` in `tests/test_search_eval_cli.py`:

```python
def _write_old_css_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "old-css-bin"
    bin_dir.mkdir()
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import sys

if sys.argv[1:] == ["--version"]:
    print("rsinter git main oldcss")
    raise SystemExit(0)

print("unknown field `input_type` in runner params", file=sys.stderr)
raise SystemExit(7)
"""
    )
    executable.chmod(0o755)
    return bin_dir
```

Add this test after the CSS eval tests:

```python
def test_eval_general_css_old_backend_reports_required_upstream_support(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)

    result = _run_eval(
        work_root,
        _env_with_rsinter(_write_old_css_rsinter(tmp_path)),
        "--campaign",
        "rotated-surface-css-fixture",
        "--distance",
        "3",
        "--decoder",
        "rmatching-default-v1",
        "--p",
        "0.005",
        "--run-id",
        "old-css-backend",
        "--general-css",
    )

    assert result.returncode == 1
    assert "upstream rstim general CSS support from #46 / #51 is required" in result.stderr
```

- [ ] **Step 3: Run failure-normalization tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py::test_run_rsinter_normalizes_missing_general_css_support tests/test_search_eval_cli.py::test_eval_general_css_old_backend_reports_required_upstream_support -q
```

Expected: FAIL because `run_rsinter(...)` still returns the raw backend message.

- [ ] **Step 4: Implement failure normalization**

In `src/autoqec_search/rsinter.py`, add these helpers above `run_rsinter(...)`:

```python
def _requires_general_css_support(message: str) -> bool:
    lowered = message.lower()
    css_markers = ("input_type", "css", "hx", "hz", "basis")
    old_backend_markers = ("unknown field", "unknown variant", "unknown input", "invalid type")
    return any(marker in lowered for marker in css_markers) and any(
        marker in lowered for marker in old_backend_markers
    )


def _rsinter_failure_message(result: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part.strip() for part in (result.stderr, result.stdout) if part.strip())
    if _requires_general_css_support(combined):
        return (
            "upstream rstim general CSS support from #46 / #51 is required: "
            f"{combined}"
        )
    return combined
```

In `run_rsinter(...)`, replace the nonzero return handling with:

```python
    if result.returncode != 0:
        raise SearchIntegrityError(
            f"rsinter bench run exited {result.returncode}: "
            f"{_rsinter_failure_message(result)}"
        )
```

- [ ] **Step 5: Run failure-normalization tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py::test_run_rsinter_normalizes_missing_general_css_support tests/test_search_eval_cli.py::test_eval_general_css_old_backend_reports_required_upstream_support -q
```

Expected: PASS.

- [ ] **Step 6: Commit failure normalization**

```bash
git add src/autoqec_search/rsinter.py tests/test_search_rsinter.py tests/test_search_eval_cli.py
git commit -m "fix: explain missing rstim css backend support"
```

---

### Task 6: Document General CSS Eval

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_search_docs.py`

- [ ] **Step 1: Add docs assertions**

Append this test to `tests/test_search_docs.py`:

```python
def test_docs_mention_general_css_eval_path() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "--general-css" in document
        assert "hx/hz -> rstim CSS -> DEM -> decoder" in document
        assert "rotated-surface-css-fixture" in document
        assert "upstream rstim #46/#51" in document
        assert "BB/qLDPC campaigns remain issue #18" in document
```

- [ ] **Step 2: Run docs test to verify it fails**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py::test_docs_mention_general_css_eval_path -q
```

Expected: FAIL because the docs do not yet mention `--general-css`.

- [ ] **Step 3: Update README eval section**

In `README.md`, after the paragraph that starts `The same workflow is available as autoqec-search eval`, add:

```markdown

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
```

- [ ] **Step 4: Update CLAUDE eval guidance**

In `CLAUDE.md`, after the issue #9 eval paragraph, add:

```markdown

For issue `#17`, use `--general-css` when the eval must go through the generic
CSS adapter:

```bash
python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-css-fixture --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id local-general-css-d3 --general-css
```

This keeps the existing surface path as the default, but routes stored
`hx/hz -> rstim CSS -> DEM -> decoder`. It requires upstream rstim #46/#51
support in `rsinter`; malformed or noncommuting `hx/hz` fail before backend
execution. BB/qLDPC campaigns remain issue #18.
```

- [ ] **Step 5: Run docs tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit docs**

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: describe general css eval path"
```

---

### Task 7: Final Verification

**Files:**
- No planned source edits.
- Verification may create ignored local results under
  `results/search/rotated-surface-css-fixture/local-general-css-d3/`.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py tests/test_search_eval_cli.py tests/test_search_load.py tests/test_search_cli.py tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run workspace validation**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: exits 0 and prints a validated workspace summary with `3 campaigns` and `2 suites`.

- [ ] **Step 3: Run full test suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 4: Optional local real-backend smoke**

Run only if `rsinter` on `PATH` is built from upstream rstim with #46/#51 support:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-css-fixture --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id local-general-css-d3 --general-css --force
```

Expected: exits 0, writes `results/search/rotated-surface-css-fixture/local-general-css-d3/`, writes `rsinter/input/hx.css.json`, writes a completed `rotated-memory-x-cdep-v1/rmatching-default-v1/manifest.json`, and the point LER lies inside `benchmarks/fixtures/rotated-d3/expected.json`'s Wilson CI band.

- [ ] **Step 5: Inspect git status**

Run:

```bash
git status --short
```

Expected: no unstaged tracked changes remain after Tasks 1 through 6. If the
optional local smoke created
`results/search/rotated-surface-css-fixture/local-general-css-d3/`, leave it
untracked and state that it is local verification output.

- [ ] **Step 6: Confirm no extra commit is needed**

Run:

```bash
git log --oneline -6
```

Expected: the most recent implementation commits correspond to Tasks 1 through
6, and no additional verification-only commit is needed.

---

## Self-Review Notes

- Spec coverage: Tasks 1 and 2 cover CSS wrapper conversion, CSS TOML generation, observable-to-basis mapping, and CSS result parsing without `params.distance`. Task 3 covers the fixture-compatible task, suite, and campaign. Task 4 covers the explicit `--general-css` eval path while keeping surface default behavior. Task 5 covers old-backend support errors. Task 6 covers README and CLAUDE documentation. Task 7 covers final verification and optional real-backend smoke.
- Scope control: The plan does not add BB/qLDPC campaign files, distance-method registry work, decoder-registry changes, or AutoQEC-side CSS circuit generation.
- Compatibility: `write_spec_toml(...)` remains as the surface-compatible wrapper, and `general_css` defaults to `False` so existing autoresearch and eval callers continue using the surface-specific path.

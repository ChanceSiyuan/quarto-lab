# Issue #9 Rsinter Contract Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `autoqec-search eval` complete issue #9 against the current real GitHub/dev `rsinter` CLI by generating a valid benchmark spec and parsing real `BenchmarkResultRow` output.

**Architecture:** Keep the existing AutoQEC eval orchestration and manifest schema. Fix the rsinter adapter boundary in `src/autoqec_search/rsinter.py`, then update the CLI fake backend so tests exercise the same contract as real rsinter. Do not modify `rstim` or `rsinter` in this plan.

**Tech Stack:** Python 3.11, pytest, standard-library `json`, `tomllib`, `pathlib`, `subprocess`, current GitHub/dev `rsinter` on `PATH`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/autoqec_search/rsinter.py` | Generate rsinter benchmark TOML, execute `rsinter`, parse real `BenchmarkResultRow` JSONL into AutoQEC point dictionaries. |
| `src/autoqec_search/eval_run.py` | Pass copied candidate distance into the parser for validation. |
| `tests/test_search_rsinter.py` | Unit tests for TOML generation, parser success cases, and parser validation failures. |
| `tests/test_search_eval_cli.py` | End-to-end CLI tests with a fake rsinter that consumes the generated TOML and emits real row-shaped JSONL. |

No new production module is needed. The boundary is narrow enough to keep in the existing adapter file.

---

### Task 1: Update Rsinter TOML Tests To Match Current BenchmarkSpec

**Files:**
- Modify: `tests/test_search_rsinter.py`

- [ ] **Step 1: Replace the TOML shape assertions**

In `tests/test_search_rsinter.py`, replace `test_write_spec_toml_writes_runner_task_and_decoder_config` with:

```python
def test_write_spec_toml_writes_current_rsinter_benchmark_spec(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "rotated-memory-x-cdep-v1",
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

    write_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rmatching-default-v1"],
        distance=3,
        rounds=3,
        p_values=[0.005],
    )

    parsed = tomllib.loads(spec_path.read_text())
    assert parsed["name"] == "autoqec-rotated-memory-x-cdep-v1"
    assert parsed["version"] == 1
    assert parsed["mode"] == "independent"
    assert parsed["plot"]["title"] == "AutoQEC rotated-memory-x-cdep-v1"
    assert parsed["plot"]["x"] == {
        "field": "params.p",
        "scale": "log",
        "label": "Physical Error Rate",
    }
    assert parsed["plot"]["series"] == {
        "group_by": ["runner", "params.distance"],
        "label_template": "{runner} d={params.distance}",
    }
    assert parsed["plot"]["panel"] == [
        {
            "metric": "metrics.logical_error_rate",
            "scale": "log",
            "label": "Logical Error Rate",
        }
    ]
    assert parsed["runner"] == [
        {
            "name": "rmatching-default-v1",
            "language": "rust",
            "impl_key": "rmatching",
            "params": {
                "distance": [3],
                "rounds": [3],
                "p": [0.005],
                "max_shots": 1000,
                "max_errors": 50,
                "batch_size": 256,
            },
        }
    ]
```

- [ ] **Step 2: Replace the string escaping test**

In `tests/test_search_rsinter.py`, replace `test_write_spec_toml_escapes_scalar_strings_as_valid_toml` with:

```python
def test_write_spec_toml_escapes_scalar_strings_as_valid_toml(tmp_path: Path) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    decoder_id = 'rmatching "quoted" \\ id\nnext'
    impl_key = 'impl "key" \\ value\nnext'
    task_id = 'task "id" \\ value\nnext'
    language = 'rust "lang" \\ value\nnext'
    task = {
        "id": task_id,
        "p_list": [0.005],
        "collection": {"max_shots": 1000, "max_errors": 50, "batch_size": 16},
    }
    decoders = {
        decoder_id: {
            "id": decoder_id,
            "impl_key": impl_key,
            "language": language,
        }
    }

    write_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=[decoder_id],
        distance=3,
        rounds=3,
        p_values=[0.005],
    )

    parsed = tomllib.loads(spec_path.read_text())
    assert parsed["name"] == f"autoqec-{task_id}"
    runner = parsed["runner"][0]
    assert runner["name"] == decoder_id
    assert runner["impl_key"] == impl_key
    assert runner["language"] == language
    assert runner["params"]["batch_size"] == 16
```

- [ ] **Step 3: Run the TOML tests and verify they fail**

Run:

```sh
python3 -m pytest tests/test_search_rsinter.py::test_write_spec_toml_writes_current_rsinter_benchmark_spec tests/test_search_rsinter.py::test_write_spec_toml_escapes_scalar_strings_as_valid_toml -v
```

Expected: FAIL because the current implementation writes no top-level benchmark metadata, writes runner `id` instead of `name`, and omits `batch_size`.

- [ ] **Step 4: Leave the failing tests uncommitted**

Do not commit at this point. Task 2 will make the tests pass and commit the
passing test plus implementation together.

---

### Task 2: Generate A Complete Current Rsinter Benchmark Spec

**Files:**
- Modify: `src/autoqec_search/rsinter.py`
- Test: `tests/test_search_rsinter.py`

- [ ] **Step 1: Add default batch-size constant**

Near `RSINTER_RUN_TIMEOUT_SECONDS`, add:

```python
RSINTER_DEFAULT_BATCH_SIZE = 256
```

- [ ] **Step 2: Replace `write_spec_toml`**

Replace the body of `write_spec_toml` in `src/autoqec_search/rsinter.py` with:

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
    output_path = Path(spec_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    p_list = ", ".join(str(value) for value in p_values)
    collection = task["collection"]
    batch_size = int(collection.get("batch_size", RSINTER_DEFAULT_BATCH_SIZE))
    if batch_size <= 0:
        raise SearchIntegrityError(f"invalid rsinter batch_size: {batch_size}")

    benchmark_name = f"autoqec-{task['id']}"
    lines: list[str] = [
        f"name = {_toml_string(benchmark_name)}",
        "version = 1",
        'mode = "independent"',
        "",
    ]
    for decoder_id in selected_decoder_ids:
        decoder = decoders[decoder_id]
        lines.extend(
            [
                "[[runner]]",
                f"name = {_toml_string(decoder_id)}",
                f"language = {_toml_string(decoder.get('language', 'rust'))}",
                f"impl_key = {_toml_string(decoder['impl_key'])}",
                "",
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

    plot_title = f"AutoQEC {task['id']}"
    lines.extend(
        [
            "[plot]",
            f"title = {_toml_string(plot_title)}",
            "",
            "[plot.x]",
            'field = "params.p"',
            'scale = "log"',
            'label = "Physical Error Rate"',
            "",
            "[plot.series]",
            'group_by = ["runner", "params.distance"]',
            'label_template = "{runner} d={params.distance}"',
            "",
            "[[plot.panel]]",
            'metric = "metrics.logical_error_rate"',
            'scale = "log"',
            'label = "Logical Error Rate"',
            "",
        ]
    )
    output_path.write_text("\n".join(lines))
```

- [ ] **Step 3: Run the TOML tests and verify they pass**

Run:

```sh
python3 -m pytest tests/test_search_rsinter.py::test_write_spec_toml_writes_current_rsinter_benchmark_spec tests/test_search_rsinter.py::test_write_spec_toml_escapes_scalar_strings_as_valid_toml -v
```

Expected: PASS.

- [ ] **Step 4: Commit the implementation**

```sh
git add src/autoqec_search/rsinter.py tests/test_search_rsinter.py
git commit -m "fix: generate current rsinter benchmark specs"
```

---

### Task 3: Update JSONL Parser Tests To Real BenchmarkResultRow Shape

**Files:**
- Modify: `tests/test_search_rsinter.py`

- [ ] **Step 1: Replace `_write_result` helper**

Replace `_write_result` at the top of `tests/test_search_rsinter.py` with:

```python
def _result_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "benchmark": "autoqec-rotated-memory-x-cdep-v1",
        "runner": "rmatching-default-v1",
        "language": "rust",
        "status": "ok",
        "params": {"distance": 3, "rounds": 3, "p": 0.005},
        "case_summary": {"num_dets": 8, "num_obs": 1},
        "metrics": {
            "shots_used": 1000,
            "logical_errors": 5,
            "logical_error_rate": 0.005,
            "decode_us_per_shot": 1.25,
        },
        "artifacts": {},
        "error": None,
    }
    record.update(overrides)
    return record


def _write_result(path: Path, **overrides: object) -> None:
    path.write_text(json.dumps(_result_record(**overrides), sort_keys=True) + "\n")
```

- [ ] **Step 2: Update success parser call**

In `test_parse_results_jsonl_builds_points`, update the call to:

```python
points = parse_results_jsonl(
    path,
    expected_decoder_id="rmatching-default-v1",
    expected_task_id="rotated-memory-x-cdep-v1",
    expected_p_values=[0.005],
    expected_distance=3,
)
```

Expected point stays:

```python
{
    "p": 0.005,
    "rounds": 3,
    "shots": 1000,
    "errors": 5,
    "ler": 0.005,
    "ci_low": pytest.approx(0.00214, abs=0.00001),
    "ci_high": pytest.approx(0.01165, abs=0.00001),
    "seconds": 0.00125,
}
```

`seconds` is `decode_us_per_shot * shots / 1_000_000`.

- [ ] **Step 3: Update parser failure tests to nested fields**

Update invalid-record parameterization to:

```python
@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"metrics": {"shots_used": "1000", "logical_errors": 5}}, "missing numeric metric shots_used"),
        ({"metrics": {"shots_used": 1000, "logical_errors": None}}, "missing numeric metric logical_errors"),
        ({"runner": "unexpected"}, "unexpected runner"),
        ({"status": "failed"}, "rsinter row status is not ok"),
        ({"params": {"distance": 3, "rounds": 3, "p": 0.01}}, "unexpected p"),
        ({"params": {"distance": 5, "rounds": 3, "p": 0.005}}, "unexpected distance"),
    ],
)
def test_parse_results_jsonl_rejects_invalid_records(
    tmp_path: Path, overrides: dict[str, object], match: str
) -> None:
    path = tmp_path / "results.jsonl"
    _write_result(path, **overrides)

    with pytest.raises(SearchIntegrityError, match=match):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_p_values=[0.005],
            expected_distance=3,
        )
```

- [ ] **Step 4: Update duplicate-p test**

Use real rows:

```python
def test_parse_results_jsonl_rejects_duplicate_p_records(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    record = _result_record()
    path.write_text(
        "\n".join(
            [
                json.dumps(record, sort_keys=True),
                json.dumps(record, sort_keys=True),
            ]
        )
        + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="line 2: duplicate p"):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_p_values=[0.005],
            expected_distance=3,
        )
```

- [ ] **Step 5: Update remaining parser calls**

For every `parse_results_jsonl(...)` call in parser tests, add:

```python
expected_distance=3,
```

For `test_parse_results_jsonl_rejects_errors_exceeding_shots`, write:

```python
_write_result(
    path,
    metrics={
        "shots_used": 1000,
        "logical_errors": 1001,
        "logical_error_rate": 1.001,
    },
)
```

For invalid integer and seconds tests, replace the parameterization with:

```python
@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"params": {"distance": 3, "rounds": 1.9, "p": 0.005}}, "missing integer params.rounds"),
        ({"metrics": {"shots_used": 1000.7, "logical_errors": 5}}, "integer metric shots_used"),
        ({"metrics": {"shots_used": 1000, "logical_errors": 2.8}}, "integer metric logical_errors"),
        ({"params": {"distance": 3, "rounds": 0, "p": 0.005}}, "invalid rounds"),
        ({"metrics": {"shots_used": 1000, "logical_errors": 5, "decode_us_per_shot": -1}}, "invalid decode_us_per_shot"),
    ],
)
```

- [ ] **Step 6: Run parser tests and verify they fail**

Run:

```sh
python3 -m pytest tests/test_search_rsinter.py::test_parse_results_jsonl_builds_points tests/test_search_rsinter.py::test_parse_results_jsonl_rejects_invalid_records -v
```

Expected: FAIL because production parser still expects flat fake rows and does not accept `expected_distance`.

- [ ] **Step 7: Leave the failing tests uncommitted**

Do not commit at this point. Task 4 will make the tests pass and commit the
passing test plus implementation together.

---

### Task 4: Parse Real BenchmarkResultRow JSONL

**Files:**
- Modify: `src/autoqec_search/rsinter.py`
- Test: `tests/test_search_rsinter.py`

- [ ] **Step 1: Add nested-field helpers**

Add these helpers below `_require_number`:

```python
def _require_object(record: dict, key: str, path: Path, line_number: int) -> dict:
    value = record.get(key)
    if not isinstance(value, dict):
        raise SearchIntegrityError(f"{path}:{line_number}: missing object {key}")
    return value


def _require_string(record: dict, key: str, path: Path, line_number: int) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise SearchIntegrityError(f"{path}:{line_number}: missing string {key}")
    return value


def _number_to_int(value: int | float, label: str, path: Path, line_number: int) -> int:
    if isinstance(value, bool) or not isfinite(float(value)) or int(value) != value:
        raise SearchIntegrityError(f"{path}:{line_number}: missing integer {label}")
    return int(value)


def _require_numeric_metric(
    metrics: dict, key: str, path: Path, line_number: int
) -> float:
    value = metrics.get(key)
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise SearchIntegrityError(
            f"{path}:{line_number}: missing numeric metric {key}"
        )
    return float(value)


def _optional_numeric_metric(
    metrics: dict, key: str, path: Path, line_number: int, *, default: float = 0.0
) -> float:
    value = metrics.get(key, default)
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise SearchIntegrityError(f"{path}:{line_number}: invalid {key}")
    return float(value)
```

- [ ] **Step 2: Change parser signature**

Change `parse_results_jsonl` signature to:

```python
def parse_results_jsonl(
    path: str | Path,
    *,
    expected_decoder_id: str,
    expected_task_id: str,
    expected_p_values: list[float],
    expected_distance: int,
) -> list[dict]:
```

`expected_task_id` remains in the signature for AutoQEC manifest context, but real rsinter rows do not currently include task id. Do not validate a missing task id.

- [ ] **Step 3: Replace row parsing body**

Inside the line loop, after confirming `record` is a dict, replace the flat-field validation with:

```python
runner = _require_string(record, "runner", results_path, line_number)
if runner != expected_decoder_id:
    raise SearchIntegrityError(f"{results_path}:{line_number}: unexpected runner")
status = _require_string(record, "status", results_path, line_number)
if status != "ok":
    raise SearchIntegrityError(
        f"{results_path}:{line_number}: rsinter row status is not ok: {status}"
    )

params = _require_object(record, "params", results_path, line_number)
metrics = _require_object(record, "metrics", results_path, line_number)

p = float(_require_number(params, "p", results_path, line_number))
if p not in expected_p_values:
    raise SearchIntegrityError(f"{results_path}:{line_number}: unexpected p: {p}")
if p in seen_p:
    raise SearchIntegrityError(
        f"{results_path}: line {line_number}: duplicate p: {p}"
    )
seen_p.add(p)

rounds = _number_to_int(
    _require_number(params, "rounds", results_path, line_number),
    "params.rounds",
    results_path,
    line_number,
)
if rounds < 1:
    raise SearchIntegrityError(
        f"{results_path}:{line_number}: invalid rounds: {rounds}"
    )

distance_value = params.get("distance")
if distance_value is not None:
    distance = _number_to_int(
        _require_number(params, "distance", results_path, line_number),
        "params.distance",
        results_path,
        line_number,
    )
    if distance != expected_distance:
        raise SearchIntegrityError(
            f"{results_path}:{line_number}: unexpected distance: {distance}"
        )

shots = _number_to_int(
    _require_numeric_metric(metrics, "shots_used", results_path, line_number),
    "metric shots_used",
    results_path,
    line_number,
)
errors = _number_to_int(
    _require_numeric_metric(metrics, "logical_errors", results_path, line_number),
    "metric logical_errors",
    results_path,
    line_number,
)
decode_us_per_shot = _optional_numeric_metric(
    metrics, "decode_us_per_shot", results_path, line_number
)
if decode_us_per_shot < 0:
    raise SearchIntegrityError(
        f"{results_path}:{line_number}: invalid decode_us_per_shot"
    )
if shots < 1:
    raise SearchIntegrityError(f"{results_path}:{line_number}: invalid shots: {shots}")
if errors < 0:
    raise SearchIntegrityError(f"{results_path}:{line_number}: invalid errors: {errors}")

reported_ler = _optional_numeric_metric(
    metrics, "logical_error_rate", results_path, line_number, default=errors / shots
)
actual_ler = errors / shots
if abs(reported_ler - actual_ler) > 1e-12:
    raise SearchIntegrityError(
        f"{results_path}:{line_number}: logical_error_rate does not match counts"
    )

ci_low, ci_high = wilson_interval(errors=errors, shots=shots)
points.append(
    {
        "p": p,
        "rounds": rounds,
        "shots": shots,
        "errors": errors,
        "ler": actual_ler,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "seconds": decode_us_per_shot * shots / 1_000_000,
    }
)
```

- [ ] **Step 4: Update eval orchestration call**

In `src/autoqec_search/eval_run.py`, update the parser call to:

```python
points = parse_results_jsonl(
    out_dir / decoder_id / "test-run" / "results.jsonl",
    expected_decoder_id=decoder_id,
    expected_task_id=task["id"],
    expected_p_values=selected_p_values,
    expected_distance=copied_distance,
)
```

- [ ] **Step 5: Run rsinter parser tests**

Run:

```sh
python3 -m pytest tests/test_search_rsinter.py -q
```

Expected: PASS for rsinter unit tests.

- [ ] **Step 6: Commit parser implementation**

```sh
git add src/autoqec_search/rsinter.py src/autoqec_search/eval_run.py tests/test_search_rsinter.py
git commit -m "fix: parse current rsinter result rows"
```

---

### Task 5: Update CLI Fake Rsinter And End-To-End Assertions

**Files:**
- Modify: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Update fake rsinter writer**

In `_write_fake_rsinter`, replace the loop body with:

```python
for runner in spec.get("runner", []):
    decoder_id = runner["name"]
    params = runner["params"]
    results_dir = out_dir / decoder_id / "test-run"
    results_dir.mkdir(parents=True, exist_ok=True)
    records = []
    rounds = int(params["rounds"][0])
    distance = int(params["distance"][0])
    for index, p in enumerate(params["p"]):
        p = float(p)
        shots = 1000
        errors = max(1, round(p * shots))
        records.append(
            json.dumps(
                {
                    "benchmark": spec["name"],
                    "runner": decoder_id,
                    "language": runner["language"],
                    "status": "ok",
                    "params": {
                        "distance": distance,
                        "rounds": rounds,
                        "p": p,
                    },
                    "case_summary": {
                        "num_dets": 8,
                        "num_obs": 1,
                        "num_shots_generated": shots,
                    },
                    "metrics": {
                        "shots_used": shots,
                        "logical_errors": errors,
                        "logical_error_rate": errors / shots,
                        "decode_us_per_shot": 250.0 + index,
                    },
                    "artifacts": {},
                    "error": None,
                },
                sort_keys=True,
            )
        )
    (results_dir / "results.jsonl").write_text("\\n".join(records) + "\\n")
```

- [ ] **Step 2: Update spec assertions in CLI test**

In `test_eval_campaign_candidate_writes_completed_selected_manifest_and_plot`, replace:

```python
assert 'id = "rmatching-default-v1"' in spec_text
assert 'id = "rbposd-default-v1"' not in spec_text
```

with:

```python
assert 'name = "autoqec-rotated-memory-x-cdep-v1"' in spec_text
assert 'name = "rmatching-default-v1"' in spec_text
assert 'name = "rbposd-default-v1"' not in spec_text
assert "batch_size = 256" in spec_text
assert "[plot]" in spec_text
```

- [ ] **Step 3: Update seconds assertion if needed**

The completed manifest point now gets seconds from `decode_us_per_shot * shots / 1_000_000`. If the test asserts seconds directly, use:

```python
assert completed_manifest["points"][0]["seconds"] == 0.25
```

No change is needed if the test only checks `ler`, `p`, `shots`, and `errors`.

- [ ] **Step 4: Run the focused CLI test**

Run:

```sh
python3 -m pytest tests/test_search_eval_cli.py::test_eval_campaign_candidate_writes_completed_selected_manifest_and_plot -v
```

Expected: PASS.

- [ ] **Step 5: Run all eval CLI tests**

Run:

```sh
python3 -m pytest tests/test_search_eval_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit CLI fake update**

```sh
git add tests/test_search_eval_cli.py
git commit -m "test: align fake rsinter with current output rows"
```

---

### Task 6: Full Verification And Real Rsinter Smoke

**Files:**
- No planned source edits.

- [ ] **Step 1: Run focused regression suite**

Run:

```sh
python3 -m pytest tests/test_search_rsinter.py tests/test_search_eval_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run adjacent search eval tests**

Run:

```sh
python3 -m pytest tests/test_search_docs.py tests/test_search_plot.py tests/test_search_eval_schemas.py -q
```

Expected: PASS.

- [ ] **Step 3: Validate search workspace**

Run:

```sh
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected:

```text
validated search workspace under .: 1 campaigns, 1 suites, 1 runs
```

- [ ] **Step 4: Run real rsinter smoke in a temporary workspace**

Create a fresh temporary copy of the repository content needed by search eval:

```sh
tmp_root="$(mktemp -d /private/tmp/autoqec-issue9-real-check.XXXXXX)"
cp -R campaigns benchmarks results zoo src pyproject.toml "$tmp_root"/
PYTHONPATH="$PWD/src" python3 -m autoqec_search.cli eval --root "$tmp_root" --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id codex-issue9-real-check
```

Expected: command exits 0 and prints a summary containing:

```text
evaluated candidate rotated-surface-d3-example
```

The temporary directory is outside the repository, so the real smoke should not
dirty the AutoQEC worktree.

- [ ] **Step 5: Inspect real artifacts**

Run:

```sh
test -f "$tmp_root/results/search/rotated-surface-baseline/codex-issue9-real-check/candidates/rotated-surface-d3-example/candidate-plot.svg"
test -f "$tmp_root/results/search/rotated-surface-baseline/codex-issue9-real-check/candidates/rotated-surface-d3-example/evaluations/rotated-memory-x-cdep-v1/rmatching-default-v1/manifest.json"
python3 -m json.tool "$tmp_root/results/search/rotated-surface-baseline/codex-issue9-real-check/candidates/rotated-surface-d3-example/evaluations/rotated-memory-x-cdep-v1/rmatching-default-v1/manifest.json"
```

Expected manifest properties:

```json
{
  "status": "completed",
  "decoder_id": "rmatching-default-v1",
  "points": [
    {
      "p": 0.005,
      "rounds": 3
    }
  ]
}
```

The exact `shots`, `errors`, `ler`, and confidence interval values come from real sampling and should not be hard-coded in this inspection.

- [ ] **Step 6: Check git status**

Run:

```sh
git status --short
```

Expected: only intentional source/test changes are present before final commit.

- [ ] **Step 7: Commit final implementation state**

If previous task commits were not made individually, make one final commit:

```sh
git add src/autoqec_search/rsinter.py src/autoqec_search/eval_run.py tests/test_search_rsinter.py tests/test_search_eval_cli.py
git commit -m "fix: complete issue 9 rsinter integration"
```

If previous task commits already captured every change, skip this commit and record the successful verification commands in the final response.

---

## Notes For Upstream Rsinter Issues

After AutoQEC verification passes, prepare upstream issue text for `rsinter` covering:

1. `rsinter bench run` requires `[plot]` even for run-only execution.
2. `batch_size` has no default and is mandatory in every runner params block.
3. TOML parse errors like `missing field name` do not identify whether the missing field is top-level or runner-level.

Do not file these issues until the AutoQEC adapter is passing real smoke verification; the exact wording can cite the working AutoQEC adapter as evidence.

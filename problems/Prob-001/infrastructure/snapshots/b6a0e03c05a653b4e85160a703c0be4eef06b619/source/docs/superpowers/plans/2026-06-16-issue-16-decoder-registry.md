# Issue 16 Decoder Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add concrete decoder registry entries with tunable `rsinter` parameters, pass them through evaluation, and record them in manifests, leaderboards, plots, reports, and docs.

**Architecture:** Keep the existing suite model: suites select concrete decoder IDs, and each decoder JSON file is one reproducible backend parameterization. `autoqec_search.rsinter` is the parameter bridge from decoder config to generated TOML and from `rsinter` row params to completed manifests. Renderers consume a stable `decoder_parameters` object without changing candidate, distance, strategy, or promotion behavior.

**Tech Stack:** Python 3.12, `jsonschema`, `pytest`, TOML parsed with `tomllib`, existing `autoqec_search` CLI, deterministic fake `rsinter` scripts in tests.

---

## File Structure

- Modify `benchmarks/schemas/decoder-config.schema.json`: backend-aware decoder parameter validation.
- Modify `benchmarks/decoders/rmatching-default-v1.json`: remove non-upstream `profile`.
- Modify `benchmarks/decoders/rbposd-default-v1.json`: remove non-upstream `profile`.
- Modify `benchmarks/decoders/rilpqec-default-v1.json`: remove non-upstream `profile`.
- Create `benchmarks/decoders/rbposd-osd0-v1.json`: concrete rbposd configuration for the low-order comparison.
- Create `benchmarks/decoders/rbposd-osd10-v1.json`: concrete rbposd configuration for the high-order comparison.
- Modify `benchmarks/suites/rotated-surface-baseline-v1.json`: include the additional rbposd configs.
- Modify `benchmarks/schemas/result-manifest.schema.json`: allow optional `decoder_parameters` on completed manifests.
- Modify `src/autoqec_search/rsinter.py`: write decoder params into TOML, parse normalized backend params, and build completed manifests with `decoder_parameters`.
- Modify `src/autoqec_search/eval_run.py`: pass configured decoder params into parser and manifest builder.
- Modify `src/autoqec_search/render.py`: add `decoder_parameters` to eval leaderboards.
- Modify `src/autoqec_search/plot.py`: accept and render decoder parameter labels.
- Modify `src/autoqec_search/report.py`: include decoder parameters in report model, points, SVG titles, and tables.
- Modify `tests/test_search_eval_schemas.py`: schema coverage for decoder configs and manifest compatibility.
- Modify `tests/test_search_rsinter.py`: unit coverage for TOML generation, result parsing, and manifest construction.
- Modify `tests/test_search_eval_cli.py`: deterministic fake backend e2e for `osd_order=0` vs `osd_order=10`.
- Modify `tests/test_search_plot.py`: plot label coverage for parameterized manifests.
- Modify `tests/test_search_report.py`: report model/render coverage for parameterized manifests.
- Modify `README.md`, `CLAUDE.md`, and `benchmarks/README.md`: document decoder registry behavior and Issue 16 verification boundary.

## Task 1: Decoder Config Schema And Registry Data

**Files:**
- Modify: `benchmarks/schemas/decoder-config.schema.json`
- Modify: `benchmarks/decoders/rmatching-default-v1.json`
- Modify: `benchmarks/decoders/rbposd-default-v1.json`
- Modify: `benchmarks/decoders/rilpqec-default-v1.json`
- Create: `benchmarks/decoders/rbposd-osd0-v1.json`
- Create: `benchmarks/decoders/rbposd-osd10-v1.json`
- Modify: `benchmarks/suites/rotated-surface-baseline-v1.json`
- Test: `tests/test_search_eval_schemas.py`

- [ ] **Step 1: Write failing decoder schema tests**

Add these imports near the top of `tests/test_search_eval_schemas.py` if they are not already present:

```python
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
```

Append these tests to `tests/test_search_eval_schemas.py`:

```python
def test_decoder_config_schema_accepts_backend_specific_parameters() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "decoder-config.schema.json")
    validator = Draft202012Validator(schema)

    validator.validate(
        {
            "id": "rmatching-default-v1",
            "title": "RMatching Default via rsinter",
            "backend": "rsinter",
            "impl_key": "rmatching",
            "language": "rust",
            "parameters": {},
            "execution_status": "real",
        }
    )
    validator.validate(
        {
            "id": "rbposd-osd10-v1",
            "title": "RBP-OSD OSD Order 10 via rsinter",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {
                "bp_iters": 50,
                "early_stop": True,
                "osd_order": 10,
            },
            "execution_status": "real",
        }
    )
    validator.validate(
        {
            "id": "rilpqec-highs-fast-v1",
            "title": "RILP-QEC HiGHS Fast via rsinter",
            "backend": "rsinter",
            "impl_key": "rilpqec",
            "language": "rust",
            "parameters": {
                "backend": "highs",
                "time_limit_s": 5.0,
                "mip_gap": 0.05,
                "threads": 2,
                "verbose": False,
            },
            "execution_status": "real",
        }
    )


@pytest.mark.parametrize(
    "decoder",
    [
        {
            "id": "rbposd-bogus-v1",
            "title": "Bad RBP-OSD",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {"bogus": 1},
            "execution_status": "real",
        },
        {
            "id": "rmatching-osd-v1",
            "title": "Bad RMatching",
            "backend": "rsinter",
            "impl_key": "rmatching",
            "language": "rust",
            "parameters": {"osd_order": 10},
            "execution_status": "real",
        },
        {
            "id": "rbposd-conflict-v1",
            "title": "Bad RBP-OSD Alias Conflict",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {"bp_iters": 50, "max_bp_iterations": 60},
            "execution_status": "real",
        },
        {
            "id": "rbposd-negative-v1",
            "title": "Bad RBP-OSD Negative",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {"osd_order": -1},
            "execution_status": "real",
        },
        {
            "id": "rilpqec-time-v1",
            "title": "Bad RILP-QEC Time",
            "backend": "rsinter",
            "impl_key": "rilpqec",
            "language": "rust",
            "parameters": {"time_limit_s": 0},
            "execution_status": "real",
        },
    ],
)
def test_decoder_config_schema_rejects_invalid_backend_parameters(
    decoder: dict,
) -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "decoder-config.schema.json")

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(decoder)
```

- [ ] **Step 2: Run schema tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py::test_decoder_config_schema_accepts_backend_specific_parameters tests/test_search_eval_schemas.py::test_decoder_config_schema_rejects_invalid_backend_parameters -q
```

Expected: FAIL because `profile`-style arbitrary parameters are still allowed and backend-specific constraints are not enforced.

- [ ] **Step 3: Replace decoder config schema**

Replace `benchmarks/schemas/decoder-config.schema.json` with:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "title",
    "backend",
    "impl_key",
    "language",
    "parameters",
    "execution_status"
  ],
  "properties": {
    "id": { "type": "string", "minLength": 1 },
    "title": { "type": "string", "minLength": 1 },
    "backend": { "const": "rsinter" },
    "impl_key": { "enum": ["rmatching", "rbposd", "rilpqec"] },
    "language": { "const": "rust" },
    "parameters": { "type": "object" },
    "execution_status": { "const": "real" }
  },
  "allOf": [
    {
      "if": {
        "properties": { "impl_key": { "const": "rmatching" } },
        "required": ["impl_key"]
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false,
            "maxProperties": 0
          }
        }
      }
    },
    {
      "if": {
        "properties": { "impl_key": { "const": "rbposd" } },
        "required": ["impl_key"]
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "bp_iters": { "type": "integer", "minimum": 0 },
              "max_bp_iterations": { "type": "integer", "minimum": 0 },
              "early_stop": { "type": "boolean" },
              "osd_order": { "type": "integer", "minimum": 0 }
            },
            "not": {
              "required": ["bp_iters", "max_bp_iterations"]
            }
          }
        }
      }
    },
    {
      "if": {
        "properties": { "impl_key": { "const": "rilpqec" } },
        "required": ["impl_key"]
      },
      "then": {
        "properties": {
          "parameters": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "backend": { "enum": ["auto", "highs", "gurobi"] },
              "time_limit_s": { "type": "number", "exclusiveMinimum": 0 },
              "mip_gap": {
                "type": "number",
                "minimum": 0,
                "exclusiveMaximum": 1
              },
              "threads": { "type": "integer", "minimum": 1 },
              "verbose": { "type": "boolean" }
            }
          }
        }
      }
    }
  ]
}
```

- [ ] **Step 4: Update existing decoder config JSON**

Set `benchmarks/decoders/rmatching-default-v1.json` to:

```json
{
  "id": "rmatching-default-v1",
  "title": "RMatching Default via rsinter",
  "backend": "rsinter",
  "impl_key": "rmatching",
  "language": "rust",
  "parameters": {},
  "execution_status": "real"
}
```

Set `benchmarks/decoders/rbposd-default-v1.json` to:

```json
{
  "id": "rbposd-default-v1",
  "title": "RBP-OSD Default via rsinter",
  "backend": "rsinter",
  "impl_key": "rbposd",
  "language": "rust",
  "parameters": {},
  "execution_status": "real"
}
```

Set `benchmarks/decoders/rilpqec-default-v1.json` to:

```json
{
  "id": "rilpqec-default-v1",
  "title": "RILP-QEC Default via rsinter",
  "backend": "rsinter",
  "impl_key": "rilpqec",
  "language": "rust",
  "parameters": {},
  "execution_status": "real"
}
```

Create `benchmarks/decoders/rbposd-osd0-v1.json`:

```json
{
  "id": "rbposd-osd0-v1",
  "title": "RBP-OSD OSD Order 0 via rsinter",
  "backend": "rsinter",
  "impl_key": "rbposd",
  "language": "rust",
  "parameters": {
    "bp_iters": 50,
    "early_stop": true,
    "osd_order": 0
  },
  "execution_status": "real"
}
```

Create `benchmarks/decoders/rbposd-osd10-v1.json`:

```json
{
  "id": "rbposd-osd10-v1",
  "title": "RBP-OSD OSD Order 10 via rsinter",
  "backend": "rsinter",
  "impl_key": "rbposd",
  "language": "rust",
  "parameters": {
    "bp_iters": 50,
    "early_stop": true,
    "osd_order": 10
  },
  "execution_status": "real"
}
```

Update `benchmarks/suites/rotated-surface-baseline-v1.json` decoder list to:

```json
[
  "rmatching-default-v1",
  "rbposd-default-v1",
  "rbposd-osd0-v1",
  "rbposd-osd10-v1",
  "rilpqec-default-v1"
]
```

- [ ] **Step 5: Run schema tests to verify they pass**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py::test_decoder_config_schema_accepts_backend_specific_parameters tests/test_search_eval_schemas.py::test_decoder_config_schema_rejects_invalid_backend_parameters -q
```

Expected: PASS.

- [ ] **Step 6: Run workspace validation to catch suite/config drift**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: this may FAIL at this point because historical run specs still have the old suite decoder list. That drift is addressed in Task 3 by making historical run validation compare against run-time artifacts rather than current suite expansion.

- [ ] **Step 7: Commit schema and registry data**

```bash
git add benchmarks/schemas/decoder-config.schema.json benchmarks/decoders/rmatching-default-v1.json benchmarks/decoders/rbposd-default-v1.json benchmarks/decoders/rilpqec-default-v1.json benchmarks/decoders/rbposd-osd0-v1.json benchmarks/decoders/rbposd-osd10-v1.json benchmarks/suites/rotated-surface-baseline-v1.json tests/test_search_eval_schemas.py
git commit -m "feat: add parameterized decoder configs"
```

## Task 2: Rsinter Parameter Bridge

**Files:**
- Modify: `src/autoqec_search/rsinter.py`
- Modify: `src/autoqec_search/eval_run.py`
- Test: `tests/test_search_rsinter.py`

- [ ] **Step 1: Write failing unit tests for TOML generation and result parsing**

In `tests/test_search_rsinter.py`, update imports:

```python
from autoqec_search.rsinter import (
    ParsedResults,
    build_completed_manifest,
    parse_decoder_filter,
    parse_p_filter,
    parse_results_jsonl,
    require_rsinter,
    rounds_for_task,
    run_rsinter,
    validate_selected_decoders,
    validate_selected_p_values,
    wilson_interval,
    write_spec_toml,
)
```

Update `test_write_spec_toml_writes_current_rsinter_benchmark_spec()` so the `decoders` fixture includes parameters:

```python
decoders = {
    "rbposd-osd10-v1": {
        "id": "rbposd-osd10-v1",
        "impl_key": "rbposd",
        "language": "rust",
        "parameters": {
            "bp_iters": 50,
            "early_stop": True,
            "osd_order": 10,
        },
    }
}
```

Change the selected decoder ID and expected runner:

```python
selected_decoder_ids=["rbposd-osd10-v1"],
```

Assert the parsed runner is:

```python
assert parsed["runner"] == [
    {
        "name": "rbposd-osd10-v1",
        "language": "rust",
        "impl_key": "rbposd",
        "params": {
            "distance": [3],
            "rounds": [3],
            "p": [0.005],
            "max_shots": 1000,
            "max_errors": 50,
            "batch_size": 256,
            "bp_iters": 50,
            "early_stop": True,
            "osd_order": 10,
        },
    }
]
```

Append these tests:

```python
def test_parse_results_jsonl_returns_decoder_parameters(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-osd10-v1",
                params={
                    "bp_iters": 50,
                    "early_stop": True,
                    "osd_order": 10,
                },
            ),
            sort_keys=True,
        )
        + "\n"
    )

    parsed = parse_results_jsonl(
        path,
        expected_decoder_id="rbposd-osd10-v1",
        expected_task_id="rotated-memory-x-cdep-v1",
        expected_distance=3,
        expected_p_values=[0.005],
        expected_decoder_parameters={
            "bp_iters": 50,
            "early_stop": True,
            "osd_order": 10,
        },
    )

    assert isinstance(parsed, ParsedResults)
    assert parsed.decoder_parameters == {
        "bp_iters": 50,
        "early_stop": True,
        "osd_order": 10,
    }
    assert parsed.points[0]["ler"] == 0.005


def test_parse_results_jsonl_rejects_missing_configured_decoder_parameter(
    tmp_path: Path,
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-osd10-v1",
                params={"bp_iters": 50, "early_stop": True},
            ),
            sort_keys=True,
        )
        + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="missing decoder parameter: osd_order"):
        parse_results_jsonl(
            path,
            expected_decoder_id="rbposd-osd10-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_distance=3,
            expected_p_values=[0.005],
            expected_decoder_parameters={
                "bp_iters": 50,
                "early_stop": True,
                "osd_order": 10,
            },
        )


def test_parse_results_jsonl_accepts_max_bp_iterations_alias(
    tmp_path: Path,
) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-alias-v1",
                params={"bp_iters": 60, "early_stop": True, "osd_order": 4},
            ),
            sort_keys=True,
        )
        + "\n"
    )

    parsed = parse_results_jsonl(
        path,
        expected_decoder_id="rbposd-alias-v1",
        expected_task_id="rotated-memory-x-cdep-v1",
        expected_distance=3,
        expected_p_values=[0.005],
        expected_decoder_parameters={"max_bp_iterations": 60},
    )

    assert parsed.decoder_parameters["bp_iters"] == 60


def test_build_completed_manifest_records_decoder_parameters() -> None:
    manifest = build_completed_manifest(
        campaign_id="rotated-surface-baseline",
        run_id="test-eval",
        candidate_id="rotated-surface-d3-example",
        task_id="rotated-memory-x-cdep-v1",
        decoder_id="rbposd-osd10-v1",
        decoder_parameters={"bp_iters": 50, "early_stop": True, "osd_order": 10},
        created_at="2026-06-13T10:20:39Z",
        tool_revisions={
            "rsinter": "rsinter git main abc123",
            "autoqec_search": "0.1.0",
        },
        points=[
            {
                "p": 0.005,
                "rounds": 3,
                "shots": 1000,
                "errors": 5,
                "ler": 0.005,
                "ci_low": 0.00214,
                "ci_high": 0.01165,
                "seconds": 1.25,
            }
        ],
    )

    assert manifest["decoder_parameters"] == {
        "bp_iters": 50,
        "early_stop": True,
        "osd_order": 10,
    }
```

- [ ] **Step 2: Run unit tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py::test_write_spec_toml_writes_current_rsinter_benchmark_spec tests/test_search_rsinter.py::test_parse_results_jsonl_returns_decoder_parameters tests/test_search_rsinter.py::test_parse_results_jsonl_rejects_missing_configured_decoder_parameter tests/test_search_rsinter.py::test_parse_results_jsonl_accepts_max_bp_iterations_alias tests/test_search_rsinter.py::test_build_completed_manifest_records_decoder_parameters -q
```

Expected: FAIL because `ParsedResults` does not exist, TOML does not include decoder params, and manifest builder has no `decoder_parameters` argument.

- [ ] **Step 3: Add rsinter parameter helpers and return type**

In `src/autoqec_search/rsinter.py`, add imports:

```python
from dataclasses import dataclass
from typing import Any
```

Add below constants:

```python
GENERIC_RESULT_PARAM_KEYS = {
    "input_type",
    "distance",
    "rounds",
    "p",
    "max_shots",
    "max_errors",
    "max_wall_seconds",
    "batch_size",
    "basis",
    "schedule",
    "hx",
    "hz",
    "observables",
    "code_id",
}


@dataclass(frozen=True)
class ParsedResults:
    points: list[dict]
    decoder_parameters: dict[str, Any]
```

Add helper functions before `parse_results_jsonl()`:

```python
def _is_scalar_parameter(value: Any) -> bool:
    return (
        value is None
        or isinstance(value, str)
        or isinstance(value, bool)
        or (isinstance(value, int) and not isinstance(value, bool))
        or (isinstance(value, float) and isfinite(value))
    )


def _sorted_scalar_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    for key, value in parameters.items():
        if not isinstance(key, str) or not key:
            raise SearchIntegrityError("decoder parameter keys must be non-empty strings")
        if not _is_scalar_parameter(value):
            raise SearchIntegrityError(f"decoder parameter {key} must be a scalar")
    return {key: parameters[key] for key in sorted(parameters)}


def _canonical_expected_decoder_parameters(
    parameters: dict[str, Any] | None,
) -> dict[str, Any]:
    if not parameters:
        return {}
    normalized = dict(parameters)
    if "max_bp_iterations" in normalized:
        normalized["bp_iters"] = normalized.pop("max_bp_iterations")
    return _sorted_scalar_parameters(normalized)


def _row_decoder_parameters(
    row_params: dict[str, Any],
    expected_decoder_parameters: dict[str, Any] | None,
) -> dict[str, Any]:
    observed = {
        key: value
        for key, value in row_params.items()
        if key not in GENERIC_RESULT_PARAM_KEYS
    }
    observed = _sorted_scalar_parameters(observed)
    expected = _canonical_expected_decoder_parameters(expected_decoder_parameters)
    for key, expected_value in expected.items():
        if key not in observed:
            raise SearchIntegrityError(f"missing decoder parameter: {key}")
        if observed[key] != expected_value:
            raise SearchIntegrityError(
                f"decoder parameter mismatch for {key}: {observed[key]} != {expected_value}"
            )
    return observed


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and isfinite(value):
        return repr(value)
    if value is None:
        raise SearchIntegrityError("decoder parameters cannot be null in rsinter TOML")
    raise SearchIntegrityError(f"unsupported decoder parameter value: {value!r}")
```

- [ ] **Step 4: Change result parsing to return ParsedResults**

Change the signature of `parse_results_jsonl()`:

```python
def parse_results_jsonl(
    path: str | Path,
    *,
    expected_decoder_id: str,
    expected_task_id: str,
    expected_distance: int,
    expected_p_values: list[float],
    expected_decoder_parameters: dict[str, Any] | None = None,
) -> ParsedResults:
```

Inside the function, initialize before the loop:

```python
decoder_parameters: dict[str, Any] | None = None
```

After `params = _require_object(...)`, add:

```python
row_decoder_parameters = _row_decoder_parameters(
    params,
    expected_decoder_parameters,
)
if decoder_parameters is None:
    decoder_parameters = row_decoder_parameters
elif decoder_parameters != row_decoder_parameters:
    raise SearchIntegrityError(
        f"{results_path}:{line_number}: decoder parameters changed across p values"
    )
```

At the end, replace the current list return:

```python
return ParsedResults(
    points=sorted(points, key=lambda point: point["p"]),
    decoder_parameters=decoder_parameters or {},
)
```

- [ ] **Step 5: Write decoder params into TOML**

In `write_spec_toml()`, inside the runner loop after `batch_size`, append decoder parameters:

```python
        for key, value in _sorted_scalar_parameters(
            dict(decoder.get("parameters", {}))
        ).items():
            lines.append(f"{key} = {_toml_scalar(value)}")
```

The runner block should still append a blank line after parameters.

- [ ] **Step 6: Add decoder_parameters to completed manifests**

Change `build_completed_manifest()` signature:

```python
def build_completed_manifest(
    *,
    campaign_id: str,
    run_id: str,
    candidate_id: str,
    task_id: str,
    decoder_id: str,
    decoder_parameters: dict[str, Any],
    created_at: str,
    tool_revisions: dict[str, str],
    points: list[dict],
) -> dict:
```

Add the field to the returned dict:

```python
"decoder_parameters": _sorted_scalar_parameters(dict(decoder_parameters)),
```

- [ ] **Step 7: Update eval_run call site**

In `src/autoqec_search/eval_run.py`, replace the parse/build block inside `evaluate_resolved_candidate_into_run()` with:

```python
        parsed = parse_results_jsonl(
            out_dir / decoder_id / "test-run" / "results.jsonl",
            expected_decoder_id=decoder_id,
            expected_task_id=task["id"],
            expected_distance=copied_distance,
            expected_p_values=selected_p_values,
            expected_decoder_parameters=workspace.decoders[decoder_id].get("parameters", {}),
        )
        manifest = build_completed_manifest(
            campaign_id=campaign_id,
            run_id=run_id,
            candidate_id=candidate_id,
            task_id=task["id"],
            decoder_id=decoder_id,
            decoder_parameters=parsed.decoder_parameters,
            created_at=created_at,
            tool_revisions={
                "autoqec_search": __version__,
                "rsinter": rsinter_version,
            },
            points=parsed.points,
        )
```

- [ ] **Step 8: Update existing tests that expect list results**

In `tests/test_search_rsinter.py`, for tests that currently do:

```python
points = parse_results_jsonl(...)
assert points == [...]
```

change to:

```python
parsed = parse_results_jsonl(...)
assert parsed.decoder_parameters == {}
assert parsed.points == [...]
```

In tests that only assert one field, change `points[0]` to `parsed.points[0]`.

In `test_build_completed_manifest_returns_status_completed_and_points()`, pass:

```python
decoder_parameters={},
```

and assert:

```python
assert manifest["decoder_parameters"] == {}
```

- [ ] **Step 9: Run rsinter unit tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit rsinter bridge**

```bash
git add src/autoqec_search/rsinter.py src/autoqec_search/eval_run.py tests/test_search_rsinter.py
git commit -m "feat: pass decoder parameters to rsinter"
```

## Task 3: Manifest Schema, Historical Compatibility, And Validation

**Files:**
- Modify: `benchmarks/schemas/result-manifest.schema.json`
- Modify: `src/autoqec_search/load.py`
- Test: `tests/test_search_eval_schemas.py`
- Test: `tests/test_search_load.py`

- [ ] **Step 1: Write failing manifest schema compatibility test**

Append to `tests/test_search_eval_schemas.py`:

```python
def test_completed_result_manifest_accepts_decoder_parameters() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "candidate_id": "rotated-surface-d3-example",
        "task_id": "rotated-memory-z-cdep-v1",
        "decoder_id": "rbposd-osd10-v1",
        "decoder_parameters": {"bp_iters": 50, "early_stop": True, "osd_order": 10},
        "status": "completed",
        "created_at": "2026-06-13T10:20:39Z",
        "tool_revisions": {
            "rsinter": "rsinter git main abc123",
            "autoqec_search": "0.1.0",
        },
        "points": [
            {
                "p": 0.005,
                "rounds": 3,
                "shots": 1000,
                "errors": 5,
                "ler": 0.005,
                "ci_low": 0.00214,
                "ci_high": 0.01165,
                "seconds": 1.25,
            }
        ],
    }

    Draft202012Validator(schema).validate(manifest)


def test_completed_result_manifest_rejects_non_scalar_decoder_parameter() -> None:
    schema = _load_json(
        REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json"
    )
    manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "candidate_id": "rotated-surface-d3-example",
        "task_id": "rotated-memory-z-cdep-v1",
        "decoder_id": "rbposd-osd10-v1",
        "decoder_parameters": {"osd_order": [10]},
        "status": "completed",
        "created_at": "2026-06-13T10:20:39Z",
        "tool_revisions": {
            "rsinter": "rsinter git main abc123",
            "autoqec_search": "0.1.0",
        },
        "points": [
            {
                "p": 0.005,
                "rounds": 3,
                "shots": 1000,
                "errors": 5,
                "ler": 0.005,
                "ci_low": 0.00214,
                "ci_high": 0.01165,
                "seconds": 1.25,
            }
        ],
    }

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(manifest)
```

- [ ] **Step 2: Write failing historical suite drift test**

Append to `tests/test_search_load.py`:

```python
def test_load_search_workspace_allows_historical_run_decoder_list_after_suite_expands(
    tmp_path: Path,
) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

    suite_path = work_root / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
    suite = json.loads(suite_path.read_text())
    assert "rbposd-osd10-v1" in suite["decoder_ids"]

    workspace = load_search_workspace(work_root)

    historical = workspace.runs["rotated-surface-baseline/2026-06-09-example"]
    assert historical.payload["decoder_ids"] == [
        "rmatching-default-v1",
        "rbposd-default-v1",
        "rilpqec-default-v1",
    ]
```

If `tests/test_search_load.py` lacks imports, add:

```python
import json
import shutil
from pathlib import Path

from autoqec_search.load import load_search_workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
```

- [ ] **Step 3: Run targeted tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py::test_completed_result_manifest_accepts_decoder_parameters tests/test_search_eval_schemas.py::test_completed_result_manifest_rejects_non_scalar_decoder_parameter tests/test_search_load.py::test_load_search_workspace_allows_historical_run_decoder_list_after_suite_expands -q
```

Expected: FAIL because the manifest schema does not accept `decoder_parameters`, and run loading still rejects historical run `decoder_ids` drift.

- [ ] **Step 4: Update result manifest schema**

In the completed-manifest branch of `benchmarks/schemas/result-manifest.schema.json`, add `decoder_parameters` to `properties` but not to `required`:

```json
"decoder_parameters": {
  "type": "object",
  "additionalProperties": {
    "anyOf": [
      { "type": "string" },
      { "type": "integer" },
      { "type": "number" },
      { "type": "boolean" },
      { "type": "null" }
    ]
  }
}
```

Keep `additionalProperties: false` so unexpected top-level fields still fail.

- [ ] **Step 5: Relax historical run suite drift in loader**

In `src/autoqec_search/load.py`, replace this check in `load_search_run()`:

```python
    if payload["decoder_ids"] != suite["decoder_ids"]:
        raise SearchIntegrityError(f"run decoder_ids drift on {run_root}")
```

with:

```python
    unknown_run_decoders = sorted(set(payload["decoder_ids"]) - set(suite["decoder_ids"]))
    if unknown_run_decoders:
        raise SearchIntegrityError(
            f"run decoder_ids unknown on {run_root}: {', '.join(unknown_run_decoders)}"
        )
```

Keep the task drift check unchanged. This allows old runs with a subset of the current suite decoders but still rejects run specs that name decoders no longer known to the suite.

- [ ] **Step 6: Run targeted tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py::test_completed_result_manifest_accepts_decoder_parameters tests/test_search_eval_schemas.py::test_completed_result_manifest_rejects_non_scalar_decoder_parameter tests/test_search_eval_schemas.py::test_result_manifest_schema_still_accepts_existing_placeholder_manifest tests/test_search_load.py::test_load_search_workspace_allows_historical_run_decoder_list_after_suite_expands -q
```

Expected: PASS.

- [ ] **Step 7: Run validate**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: PASS with a line like `validated search workspace under .`.

- [ ] **Step 8: Commit manifest schema compatibility**

```bash
git add benchmarks/schemas/result-manifest.schema.json src/autoqec_search/load.py tests/test_search_eval_schemas.py tests/test_search_load.py
git commit -m "feat: record decoder parameters in manifests"
```

## Task 4: Leaderboard, Plot, And Report Surfaces

**Files:**
- Modify: `src/autoqec_search/render.py`
- Modify: `src/autoqec_search/plot.py`
- Modify: `src/autoqec_search/report.py`
- Test: `tests/test_search_eval_cli.py`
- Test: `tests/test_search_plot.py`
- Test: `tests/test_search_report.py`

- [ ] **Step 1: Write failing leaderboard test update**

In `tests/test_search_eval_cli.py`, update `test_render_eval_leaderboard_quotes_csv_fields_with_commas()` expected header:

```python
assert rows[0] == [
    "candidate_id",
    "task_id",
    "decoder_id",
    "decoder_parameters",
    "p",
    "shots",
    "errors",
    "ler",
    "ci_low",
    "ci_high",
    "status",
]
```

Add `decoder_parameters` to the test manifest:

```python
"decoder_parameters": {"z": "comma,value"},
```

Update expected data row:

```python
assert rows[1] == [
    "candidate,comma",
    "task,comma",
    "decoder,comma",
    '{"z":"comma,value"}',
    "0.005",
    "1000",
    "5",
    "0.005",
    "0.002",
    "0.011",
    "completed",
]
```

- [ ] **Step 2: Write failing plot parameter label test**

In `tests/test_search_plot.py`, update `_manifest()` signature:

```python
def _manifest(
    decoder_id: str,
    *,
    task_id: str = "rotated-memory-x-cdep-v1",
    points: list[dict[str, object]] | None = None,
    decoder_parameters: dict[str, object] | None = None,
) -> dict[str, object]:
```

Add the field in the returned dict:

```python
"decoder_parameters": {} if decoder_parameters is None else decoder_parameters,
```

Append:

```python
def test_render_candidate_plot_includes_decoder_parameters_in_labels() -> None:
    svg = render_candidate_plot(
        candidate_id="rotated-surface-d3",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=[
            _manifest(
                "rbposd-osd10-v1",
                decoder_parameters={
                    "bp_iters": 50,
                    "early_stop": True,
                    "osd_order": 10,
                },
            )
        ],
    )

    assert "rbposd-osd10-v1 {&quot;bp_iters&quot;:50,&quot;early_stop&quot;:true,&quot;osd_order&quot;:10}" in svg
    assert "params={&quot;bp_iters&quot;:50,&quot;early_stop&quot;:true,&quot;osd_order&quot;:10}" in svg
```

- [ ] **Step 3: Write failing report model test update**

In `tests/test_search_report.py`, in `_make_completed_eval_run()`, add to `manifest`:

```python
"decoder_parameters": {"bp_iters": 50, "early_stop": True, "osd_order": 10},
```

Update `test_build_report_model_collects_completed_eval_points()` expected point:

```python
"decoder_parameters": {"bp_iters": 50, "early_stop": True, "osd_order": 10},
```

Also assert:

```python
assert model["manifests"][0]["decoder_parameters"] == {
    "bp_iters": 50,
    "early_stop": True,
    "osd_order": 10,
}
```

Append:

```python
def test_render_report_html_includes_decoder_parameters(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = _make_completed_eval_run(work_root)

    html = render_report_html(build_report_model(work_root, run_root))

    assert "decoder_parameters" in html
    assert "&quot;osd_order&quot;: 10" in html or '"osd_order": 10' in html
```

- [ ] **Step 4: Run surface tests to verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py::test_render_eval_leaderboard_quotes_csv_fields_with_commas tests/test_search_plot.py::test_render_candidate_plot_includes_decoder_parameters_in_labels tests/test_search_report.py::test_build_report_model_collects_completed_eval_points tests/test_search_report.py::test_render_report_html_includes_decoder_parameters -q
```

Expected: FAIL because renderers do not yet expose decoder parameters.

- [ ] **Step 5: Add stable JSON formatting in render.py**

In `src/autoqec_search/render.py`, add:

```python
import json
```

Add helper:

```python
def _json_cell(payload: object) -> str:
    if not isinstance(payload, dict):
        return "{}"
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
```

In `render_eval_leaderboard()`, add `"decoder_parameters"` after `"decoder_id"` in the header, and add this value after `manifest["decoder_id"]` in each row:

```python
_json_cell(manifest.get("decoder_parameters", {})),
```

- [ ] **Step 6: Update plot labels**

In `src/autoqec_search/plot.py`, add:

```python
import json
```

Update `DecoderSeries`:

```python
@dataclass(frozen=True)
class DecoderSeries:
    decoder_id: str
    decoder_parameters: dict[str, Any]
    label: str
    points: tuple[PlotPoint, ...]
```

Add helper:

```python
def _parameter_label(parameters: dict[str, Any]) -> str:
    if not parameters:
        return ""
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"))
```

In `_read_series()`, after decoder ID validation:

```python
        decoder_parameters = manifest.get("decoder_parameters", {})
        if decoder_parameters is None:
            decoder_parameters = {}
        if not isinstance(decoder_parameters, dict):
            raise SearchIntegrityError(
                f"manifest {decoder_id} has invalid decoder_parameters"
            )
        parameter_text = _parameter_label(decoder_parameters)
        label = decoder_id if not parameter_text else f"{decoder_id} {parameter_text}"
```

When constructing `DecoderSeries`, use:

```python
        series.append(
            DecoderSeries(
                decoder_id=decoder_id,
                decoder_parameters=dict(decoder_parameters),
                label=label,
                points=parsed_points,
            )
        )
```

Replace legend and tooltip use of `item.decoder_id` for human labels with `item.label`. The point title should become:

```python
            parameter_text = _parameter_label(item.decoder_parameters)
            label = (
                f"{item.label}: p={_format_float(point.p)}, "
                f"LER={_format_float(point.ler)}, "
                f"CI=[{_format_float(point.ci_low)}, {_format_float(point.ci_high)}]"
            )
            if parameter_text:
                label += f", params={parameter_text}"
```

- [ ] **Step 7: Update report model**

In `src/autoqec_search/report.py`, add helper:

```python
def _decoder_parameters(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("decoder_parameters", {})
    return dict(value) if isinstance(value, dict) else {}
```

Update `_point_payload()` return dict:

```python
"decoder_parameters": _decoder_parameters(manifest),
```

In `build_report_model()`, update manifest summary dict:

```python
                    "decoder_parameters": _decoder_parameters(manifest),
```

In `render_ler_svg()`, include decoder parameters in numeric point:

```python
"decoder_parameters": point.get("decoder_parameters", {}),
```

Change `by_series` key to include stable JSON:

```python
parameter_text = json.dumps(
    point["decoder_parameters"] if isinstance(point["decoder_parameters"], dict) else {},
    sort_keys=True,
    separators=(",", ":"),
)
key = (
    point["task_id"],
    point["decoder_id"],
    parameter_text,
    point["candidate_id"],
    distance,
)
```

Update `_series_label()` and `_legend_label()` signatures:

```python
def _series_label(key: tuple[str, str, str, str, int]) -> str:
    task_id, decoder_id, parameter_text, candidate_id, distance = key
    suffix = "" if parameter_text == "{}" else f" params={parameter_text}"
    return f"{task_id} / {decoder_id}{suffix} / {candidate_id} / d={distance}"


def _legend_label(key: tuple[str, str, str, str, int]) -> str:
    _task_id, decoder_id, parameter_text, candidate_id, distance = key
    suffix = "" if parameter_text == "{}" else f" {parameter_text}"
    return f"{decoder_id}{suffix} d={distance}: {candidate_id}"
```

- [ ] **Step 8: Run surface tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py::test_render_eval_leaderboard_quotes_csv_fields_with_commas tests/test_search_plot.py::test_render_candidate_plot_includes_decoder_parameters_in_labels tests/test_search_report.py::test_build_report_model_collects_completed_eval_points tests/test_search_report.py::test_render_report_html_includes_decoder_parameters -q
```

Expected: PASS.

- [ ] **Step 9: Commit render/report surfaces**

```bash
git add src/autoqec_search/render.py src/autoqec_search/plot.py src/autoqec_search/report.py tests/test_search_eval_cli.py tests/test_search_plot.py tests/test_search_report.py
git commit -m "feat: surface decoder parameters in reports"
```

## Task 5: CLI Fake-Backend End-To-End Teeth

**Files:**
- Modify: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Update fake rsinter to echo decoder params**

In `_write_fake_rsinter()` inside `tests/test_search_eval_cli.py`, replace the current inner loop body under `for index, p in enumerate(params["p"]):` with this complete block:

```python
        p = float(p)
        rounds = int(params["rounds"][0])
        distance = int(params["distance"][0])
        shots = 1000
        decode_us_per_shot = 250.0 + index
        num_shots_generated = shots
        osd_order = int(params.get("osd_order", -1))
        if osd_order == 10:
            errors = 4
        elif osd_order == 0:
            errors = 40
        elif p == 0.01:
            shots = 76533
            errors = 1000
            decode_us_per_shot = 0.29047292017822396
            num_shots_generated = 76544
        else:
            errors = max(1, round(p * shots))
        records.append(
            json.dumps(
                {{
                    "benchmark": spec["name"],
                    "runner": decoder_id,
                    "language": runner["language"],
                    "status": "ok",
                    "params": {{
                        **{{
                            key: value
                            for key, value in params.items()
                            if key not in {{"distance", "rounds", "p"}}
                        }},
                        "distance": distance,
                        "rounds": rounds,
                        "p": p,
                    }},
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
```

- [ ] **Step 2: Add end-to-end test**

Append to `tests/test_search_eval_cli.py`:

```python
def test_eval_records_parameterized_rbposd_decoders_with_distinct_ler(
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
        "rbposd-osd0-v1,rbposd-osd10-v1",
        "--p",
        "0.005",
        "--run-id",
        "parameterized-rbposd",
    )

    assert result.returncode == 0, result.stderr
    candidate_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "parameterized-rbposd"
        / "candidates"
        / "rotated-surface-d3-example"
    )

    order0 = _load_json(
        candidate_root
        / "evaluations"
        / "rotated-memory-z-cdep-v1"
        / "rbposd-osd0-v1"
        / "manifest.json"
    )
    order10 = _load_json(
        candidate_root
        / "evaluations"
        / "rotated-memory-z-cdep-v1"
        / "rbposd-osd10-v1"
        / "manifest.json"
    )

    assert order0["decoder_parameters"]["osd_order"] == 0
    assert order10["decoder_parameters"]["osd_order"] == 10
    assert order10["points"][0]["ler"] < order0["points"][0]["ler"]

    leaderboard = (candidate_root.parent.parent / "leaderboard.csv").read_text()
    assert '"{""bp_iters"":50,""early_stop"":true,""osd_order"":0}"' in leaderboard
    assert '"{""bp_iters"":50,""early_stop"":true,""osd_order"":10}"' in leaderboard

    plot = (candidate_root / "candidate-plot.svg").read_text()
    assert "rbposd-osd0-v1" in plot
    assert "rbposd-osd10-v1" in plot
    assert "osd_order&quot;:0" in plot
    assert "osd_order&quot;:10" in plot
```

- [ ] **Step 3: Run end-to-end test**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py::test_eval_records_parameterized_rbposd_decoders_with_distinct_ler -q
```

Expected: PASS.

- [ ] **Step 4: Run broader eval CLI tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py -q
```

Expected: PASS. If existing assertions expect the old leaderboard header or old suite decoder list, update them to the new header/list while keeping their behavioral intent.

- [ ] **Step 5: Commit e2e teeth**

```bash
git add tests/test_search_eval_cli.py
git commit -m "test: verify parameterized decoder eval"
```

## Task 6: Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `benchmarks/README.md`

- [ ] **Step 1: Update README search layer docs**

In `README.md`, after the `eval` command paragraph, add:

```markdown
Decoder configs under `benchmarks/decoders/` are concrete registry entries.
Each file selects an `rsinter` implementation through `impl_key` and may set
backend-specific `parameters`; for example `rbposd-osd10-v1` sets
`osd_order = 10`. Suites still select decoder IDs, so `--decoder
rbposd-osd10-v1` runs that exact parameterization. Completed manifests,
leaderboards, plots, and reports record `decoder_parameters` so parameterized
decoder runs are reproducible from committed artifacts.
```

- [ ] **Step 2: Update CLAUDE issue 16 guidance**

In `CLAUDE.md`, after the Issue #14 paragraph, add:

```markdown
For issue `#16` and M2 decoder-registry work, decoder configs under
`benchmarks/decoders/` are concrete parameterized registry entries. Use
`parameters` only for backend-specific `rsinter` knobs accepted by
`decoder-config.schema.json`: `rbposd` supports `bp_iters`, `early_stop`, and
`osd_order`; `rilpqec` supports backend/solver knobs; `rmatching` takes no
decoder parameters. `autoqec-search eval` and `run` pass those parameters to
`rsinter`, and completed manifests plus `leaderboard.csv` record
`decoder_parameters`.

Verify the decoder registry with:

```sh
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py::test_eval_records_parameterized_rbposd_decoders_with_distinct_ler -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Issue #16 is intentionally verified on the existing rotated-surface d=3 path;
the BB `[[72,12,6]]` and general CSS adapter route belongs to issues #17/#18.
```
```

- [ ] **Step 3: Update benchmarks README**

Append to `benchmarks/README.md`:

```markdown
## Decoder Registry

Files in `decoders/` are concrete decoder registry entries. A decoder config
names the `rsinter` backend implementation with `impl_key` and stores exact
backend parameters in `parameters`. The schema rejects unknown keys so
misspelled decoder knobs fail during `autoqec-search validate` instead of being
silently ignored.

Suites refer to decoder IDs, not inline overrides. To compare two settings of
the same backend, add two decoder files such as `rbposd-osd0-v1.json` and
`rbposd-osd10-v1.json`, then list both IDs in the suite.
```

- [ ] **Step 4: Run docs/search validation tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py tests/test_search_source_data.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: PASS.

- [ ] **Step 5: Commit docs**

```bash
git add README.md CLAUDE.md benchmarks/README.md
git commit -m "docs: describe decoder registry parameters"
```

## Task 7: Final Verification

**Files:**
- No source edits expected

- [ ] **Step 1: Run focused test suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py tests/test_search_rsinter.py tests/test_search_eval_cli.py tests/test_search_plot.py tests/test_search_report.py tests/test_search_load.py -q
```

Expected: PASS.

- [ ] **Step 2: Run search validation**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: PASS.

- [ ] **Step 3: Run preflight with local rsinter when available**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

Expected: PASS if `rsinter` is on `PATH` and fixture records remain valid. If this fails only because `rsinter` is missing from `PATH`, record that as an environment limitation and keep the fake-backend CI tests as the deterministic Issue 16 proof.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: no uncommitted changes.

- [ ] **Step 5: Summarize completion**

Report:

```text
Implemented Issue 16 decoder registry:
- backend-aware decoder schema and parameterized rbposd configs
- decoder params passed to rsinter and recorded in completed manifests
- leaderboard, plot, and report surfaces include decoder parameters
- deterministic fake-backend test proves osd_order=10 beats osd_order=0 on rotated-surface d=3
- validation/preflight status
```

# PR31 Issue 16 Decoder Registry Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete PR31 so it can genuinely close issue #16 with canonical decoder parameters, real CSS/BB `rsinter` evaluation, and a real predict-zero negative control.

**Architecture:** The work has two coordinated parts. First, `rsinter` exposes its existing `VacuousDecoder` as a real `predict-zero` bench runner. Then AutoQEC canonicalizes decoder params, adds an explicit CSS instance candidate path, emits `rsinter` CSS specs from committed Zoo matrices, records artifacts, and validates the issue #16 numeric checks.

**Tech Stack:** Rust `rsinter`, Python 3.12, `pytest`, `jsonschema`, TOML via `tomllib`, existing AutoQEC search CLI, existing Julia/TensorQEC instance generator.

---

## Scope Check

The approved spec spans two repositories, but the `rsinter` part is a small prerequisite for the AutoQEC negative control. This plan keeps them in one dependency-ordered plan and splits them into separate tasks. The AutoQEC PR must not claim full issue #16 completion until the `rsinter` task is complete and available to preflight/eval.

## File Structure

### Rsinter companion repository

- Create `/Users/nzy/rcode/rstim/rsinter/src/bench/runners/predict_zero.rs`: real bench runner for `VacuousDecoder`.
- Modify `/Users/nzy/rcode/rstim/rsinter/src/bench/runners/mod.rs`: export the new runner module.
- Modify `/Users/nzy/rcode/rstim/rsinter/src/bench/registry.rs`: register `predict-zero`, list it in defaults, and reject decoder-specific params.

### AutoQEC repository

- Modify `src/autoqec_search/decoder_parameters.py`: canonical decoder parameter helpers for config, TOML, parser, manifest, report, and plot consumers.
- Modify `src/autoqec_search/rsinter.py`: fixed rounds policy, CSS TOML fields, optional distance parsing, canonical expected/observed decoder params.
- Modify `src/autoqec_search/eval_candidates.py`: explicit Zoo instance candidate path and nested instance parameters for evaluated candidate payloads.
- Modify `src/autoqec_search/eval_run.py`: evaluate CSS candidates without a distance scalar and pass copied matrix paths into TOML generation.
- Modify `src/autoqec_search/render.py`, `src/autoqec_search/plot.py`, and `src/autoqec_search/report.py`: display optional distance cleanly for CSS runs.
- Modify `src/autoqec_search/load.py`: accept evaluated candidate payloads with nested JSON parameters and keep `distance.json` present with `distance: null` for CSS candidates.
- Modify `src/autoqec_search/preflight.py`: require the `predict-zero` runner when `predict-zero-v1` exists in the workspace.
- Modify schemas under `benchmarks/schemas/`: CSS task fields, predict-zero decoder config, explicit instance search-space candidate, nested evaluated candidate parameters.
- Create benchmark data under `benchmarks/tasks/`, `benchmarks/suites/`, `benchmarks/decoders/`, and `campaigns/examples/decoder-registry-css-bb-smoke/`.
- Create BB instance under `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/`.
- Add or modify tests in `tests/test_search_rsinter.py`, `tests/test_search_eval_candidates.py`, `tests/test_search_eval_schemas.py`, `tests/test_search_eval_cli.py`, `tests/test_search_preflight.py`, `tests/test_search_report.py`, `tests/test_search_plot.py`, and `tests/test_search_docs.py`.
- Update `README.md`, `CLAUDE.md`, and `benchmarks/README.md`.

## Task 1: Expose `predict-zero` In Rsinter

**Files:**
- Create: `/Users/nzy/rcode/rstim/rsinter/src/bench/runners/predict_zero.rs`
- Modify: `/Users/nzy/rcode/rstim/rsinter/src/bench/runners/mod.rs`
- Modify: `/Users/nzy/rcode/rstim/rsinter/src/bench/registry.rs`

- [ ] **Step 1: Write the failing registry test**

Append this test module to `/Users/nzy/rcode/rstim/rsinter/src/bench/registry.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_registry_exposes_predict_zero_runner() {
        let names = default_rust_runner_names();
        assert!(names.contains(&"predict-zero".to_string()));

        let registry = build_default_rust_runner_registry();
        let runner = registry
            .get("predict-zero")
            .expect("predict-zero runner is registered");
        assert_eq!(runner.name(), "predict-zero");
    }

    #[test]
    fn predict_zero_rejects_decoder_specific_params() {
        let params = BTreeMap::from([
            ("input_type".to_string(), Value::String("surface_rotated_memory_x".into())),
            ("distance".to_string(), Value::Array(vec![Value::Integer(3)])),
            ("rounds".to_string(), Value::Array(vec![Value::Integer(3)])),
            ("p".to_string(), Value::Array(vec![Value::Float(0.01)])),
            ("max_shots".to_string(), Value::Integer(10)),
            ("max_errors".to_string(), Value::Integer(10)),
            ("batch_size".to_string(), Value::Integer(2)),
            ("osd_order".to_string(), Value::Integer(10)),
        ]);

        let error = expand_runner_points_for_runner("predict-zero", &params)
            .expect_err("predict-zero does not accept rbposd params");
        assert_eq!(error, "unknown predict-zero runner param: osd_order");
    }
}
```

- [ ] **Step 2: Run the focused rsinter test and verify it fails**

Run:

```bash
cargo test -p rsinter default_registry_exposes_predict_zero_runner predict_zero_rejects_decoder_specific_params
```

Expected: FAIL because `predict-zero` is not registered.

- [ ] **Step 3: Add the runner implementation**

Create `/Users/nzy/rcode/rstim/rsinter/src/bench/runners/predict_zero.rs`:

```rust
use crate::bench::registry::{BenchCasePoint, BenchRunContext, RustBenchRunner};
use crate::bench::result::{BenchmarkResultRow, ParamMap};
use crate::bench::runners::run_decoder_point;
use crate::decode::VacuousDecoder;

pub struct PredictZeroRunner;

impl RustBenchRunner for PredictZeroRunner {
    fn name(&self) -> &'static str {
        "predict-zero"
    }

    fn run_point(
        &self,
        point: &BenchCasePoint,
        ctx: &BenchRunContext,
    ) -> Result<BenchmarkResultRow, String> {
        let decoder = VacuousDecoder;
        let decoder_params = ParamMap::new();
        run_decoder_point(self.name(), &decoder, point, ctx, &decoder_params)
    }
}
```

Modify `/Users/nzy/rcode/rstim/rsinter/src/bench/runners/mod.rs`:

```rust
pub mod predict_zero;
pub mod rbposd;
pub mod rilpqec;
pub mod rmatching;
```

Modify `/Users/nzy/rcode/rstim/rsinter/src/bench/registry.rs` imports and registry construction:

```rust
use crate::bench::runners::predict_zero::PredictZeroRunner;
use crate::bench::runners::rbposd::RbposdRunner;
use crate::bench::runners::rilpqec::RilpqecRunner;
use crate::bench::runners::rmatching::RmatchingRunner;

pub fn default_rust_runner_names() -> Vec<String> {
    ["rmatching", "rbposd", "rilpqec", "predict-zero"]
        .into_iter()
        .map(|name| name.to_string())
        .collect()
}

pub fn build_default_rust_runner_registry() -> RustRunnerRegistry {
    let mut registry: RustRunnerRegistry = BTreeMap::new();
    registry.insert("rmatching".into(), Box::new(RmatchingRunner));
    registry.insert("rbposd".into(), Box::new(RbposdRunner));
    registry.insert("rilpqec".into(), Box::new(RilpqecRunner));
    registry.insert("predict-zero".into(), Box::new(PredictZeroRunner));
    registry
}
```

Modify `is_decoder_param_key()` in `/Users/nzy/rcode/rstim/rsinter/src/bench/registry.rs`:

```rust
fn is_decoder_param_key(runner_name: &str, key: &str) -> bool {
    match runner_name {
        "rbposd" => matches!(
            key,
            "bp_iters" | "max_bp_iterations" | "early_stop" | "osd_order"
        ),
        "rilpqec" => matches!(
            key,
            "backend" | "time_limit_s" | "mip_gap" | "threads" | "verbose"
        ),
        "rmatching" | "predict-zero" | "generic" => false,
        _ => false,
    }
}
```

- [ ] **Step 4: Run rsinter tests and verify they pass**

Run:

```bash
cargo test -p rsinter default_registry_exposes_predict_zero_runner predict_zero_rejects_decoder_specific_params
cargo test -p rsinter bench
```

Expected: PASS.

- [ ] **Step 5: Commit the rsinter companion change**

Run:

```bash
git -C /Users/nzy/rcode/rstim add rsinter/src/bench/runners/predict_zero.rs rsinter/src/bench/runners/mod.rs rsinter/src/bench/registry.rs
git -C /Users/nzy/rcode/rstim commit -m "feat(rsinter): expose predict-zero bench runner"
```

Expected: commit created in the `rstim` repository.

## Task 2: Canonicalize Decoder Parameters In AutoQEC

**Files:**
- Modify: `src/autoqec_search/decoder_parameters.py`
- Modify: `src/autoqec_search/rsinter.py`
- Test: `tests/test_search_rsinter.py`
- Test: `tests/test_search_eval_schemas.py`

- [ ] **Step 1: Write failing canonicalization tests**

Add this import to `tests/test_search_rsinter.py`:

```python
from autoqec_search.decoder_parameters import canonical_decoder_parameters
```

Append these tests to `tests/test_search_rsinter.py`:

```python
def test_canonical_decoder_parameters_maps_rbposd_alias() -> None:
    assert canonical_decoder_parameters(
        {"max_bp_iterations": 60, "osd_order": 4},
        impl_key="rbposd",
    ) == {"bp_iters": 60, "osd_order": 4}


def test_canonical_decoder_parameters_rejects_rbposd_alias_conflict() -> None:
    with pytest.raises(ValueError, match="both bp_iters and max_bp_iterations"):
        canonical_decoder_parameters(
            {"bp_iters": 50, "max_bp_iterations": 60},
            impl_key="rbposd",
        )


def test_write_spec_toml_writes_canonical_rbposd_alias(tmp_path: Path) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "rotated-memory-z-cdep-v1",
        "input_type": "stim-detector-error-model",
        "p_list": [0.005],
        "collection": {"max_shots": 1000, "max_errors": 50},
    }
    decoders = {
        "rbposd-alias-v1": {
            "id": "rbposd-alias-v1",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {"max_bp_iterations": 60, "osd_order": 4},
        }
    }

    write_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rbposd-alias-v1"],
        distance=3,
        rounds=3,
        p_values=[0.005],
    )

    params = tomllib.loads(spec_path.read_text())["runner"][0]["params"]
    assert params["bp_iters"] == 60
    assert "max_bp_iterations" not in params
    assert params["osd_order"] == 4
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py::test_canonical_decoder_parameters_maps_rbposd_alias tests/test_search_rsinter.py::test_canonical_decoder_parameters_rejects_rbposd_alias_conflict tests/test_search_rsinter.py::test_write_spec_toml_writes_canonical_rbposd_alias -q
```

Expected: FAIL because `canonical_decoder_parameters` is not exported and TOML generation still writes raw config params.

- [ ] **Step 3: Implement shared canonicalization**

Add to `src/autoqec_search/decoder_parameters.py`:

```python
def canonical_decoder_parameters(
    parameters: Any,
    *,
    impl_key: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_decoder_parameters(parameters)
    if impl_key == "rbposd" and "max_bp_iterations" in normalized:
        if "bp_iters" in normalized:
            raise DecoderParameterError(
                "rbposd parameters must not set both bp_iters and max_bp_iterations"
            )
        normalized["bp_iters"] = normalized.pop("max_bp_iterations")
    return {key: normalized[key] for key in sorted(normalized)}


def canonical_decoder_config(decoder: dict[str, Any]) -> dict[str, Any]:
    impl_key = decoder.get("impl_key")
    if impl_key is not None and not isinstance(impl_key, str):
        raise DecoderParameterError("decoder impl_key must be a string")
    canonical = dict(decoder)
    canonical["parameters"] = canonical_decoder_parameters(
        decoder.get("parameters", {}),
        impl_key=impl_key,
    )
    return canonical
```

Modify `src/autoqec_search/rsinter.py` imports:

```python
from autoqec_search.decoder_parameters import (
    DecoderParameterError,
    canonical_decoder_config,
    canonical_decoder_parameters,
)
```

Replace `_canonical_expected_decoder_parameters()` in `src/autoqec_search/rsinter.py`:

```python
def _canonical_expected_decoder_parameters(
    parameters: dict[str, Any] | None,
    *,
    impl_key: str | None = None,
) -> dict[str, Any]:
    try:
        return canonical_decoder_parameters(parameters or {}, impl_key=impl_key)
    except DecoderParameterError as exc:
        raise SearchIntegrityError(str(exc)) from exc
```

Change `_row_decoder_parameters()` signature and expected call:

```python
def _row_decoder_parameters(
    row_params: dict[str, Any],
    expected_decoder_parameters: dict[str, Any] | None,
    *,
    expected_impl_key: str | None = None,
) -> dict[str, Any]:
    observed = {
        key: value
        for key, value in row_params.items()
        if key not in GENERIC_RESULT_PARAM_KEYS
    }
    observed = _sorted_scalar_parameters(observed)
    expected = _canonical_expected_decoder_parameters(
        expected_decoder_parameters,
        impl_key=expected_impl_key,
    )
    for key, expected_value in expected.items():
        if key not in observed:
            raise SearchIntegrityError(f"missing decoder parameter: {key}")
        if observed[key] != expected_value:
            raise SearchIntegrityError(
                "decoder parameter mismatch for "
                f"{key}: {observed[key]} != {expected_value}"
            )
    return observed
```

Add `expected_impl_key` to `parse_results_jsonl()` and pass it through:

```python
def parse_results_jsonl(
    path: str | Path,
    *,
    expected_decoder_id: str,
    expected_task_id: str,
    expected_distance: int | None,
    expected_p_values: list[float],
    expected_decoder_parameters: dict[str, Any] | None = None,
    expected_impl_key: str | None = None,
) -> ParsedResults:
    ...
        row_decoder_parameters = _row_decoder_parameters(
            params,
            expected_decoder_parameters,
            expected_impl_key=expected_impl_key,
        )
```

In `write_spec_toml()`, canonicalize the decoder before writing parameters:

```python
        decoder = canonical_decoder_config(decoders[decoder_id])
        lines.extend(
            [
                "[[runner]]",
                f"name = {_toml_string(decoder_id)}",
                f"language = {_toml_string(decoder.get('language', 'rust'))}",
                f"impl_key = {_toml_string(decoder['impl_key'])}",
                "[runner.params]",
            ]
        )
```

- [ ] **Step 4: Pass impl_key from eval into parser**

Modify the parser call in `src/autoqec_search/eval_run.py`:

```python
        decoder_config = workspace.decoders[decoder_id]
        parsed = parse_results_jsonl(
            out_dir / decoder_id / "test-run" / "results.jsonl",
            expected_decoder_id=decoder_id,
            expected_task_id=task["id"],
            expected_distance=copied_distance,
            expected_p_values=selected_p_values,
            expected_decoder_parameters=decoder_config.get("parameters", {}),
            expected_impl_key=decoder_config.get("impl_key"),
        )
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py tests/test_search_eval_schemas.py -q
```

Expected: PASS.

Commit:

```bash
git add src/autoqec_search/decoder_parameters.py src/autoqec_search/rsinter.py src/autoqec_search/eval_run.py tests/test_search_rsinter.py tests/test_search_eval_schemas.py
git commit -m "fix: canonicalize decoder parameter aliases"
```

## Task 3: Add CSS Task Schema, Predict-Zero Decoder Config, And Smoke Campaign Data

**Files:**
- Modify: `benchmarks/schemas/benchmark-task.schema.json`
- Modify: `benchmarks/schemas/decoder-config.schema.json`
- Modify: `benchmarks/schemas/search-space.schema.json`
- Modify: `benchmarks/schemas/candidate.schema.json`
- Create: `benchmarks/tasks/bb-css-memory-x-cdep-v1.json`
- Create: `benchmarks/decoders/predict-zero-v1.json`
- Create: `benchmarks/suites/decoder-registry-css-bb-smoke-v1.json`
- Create: `campaigns/examples/decoder-registry-css-bb-smoke/campaign.json`
- Create: `campaigns/examples/decoder-registry-css-bb-smoke/search_space.json`
- Test: `tests/test_search_eval_schemas.py`

- [ ] **Step 1: Write failing schema tests**

Append to `tests/test_search_eval_schemas.py`:

```python
def test_benchmark_task_schema_accepts_css_fixed_rounds_task() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "benchmark-task.schema.json")
    Draft202012Validator(schema).validate(
        {
            "id": "bb-css-memory-x-cdep-v1",
            "title": "BB CSS Memory X under circuit depolarizing noise",
            "observable": "logical_x",
            "noise_model": "circuit_depolarizing",
            "input_type": "css",
            "p_list": [0.01],
            "rounds_policy": {"kind": "fixed", "rounds": 3},
            "collection": {"max_shots": 2000, "max_errors": 200, "batch_size": 256},
            "css_memory": {"basis": "x", "schedule": "greedy"},
            "result_metrics": ["logical_error_rate"],
            "execution_status": "real",
        }
    )


def test_search_space_schema_accepts_explicit_instance_candidate() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "search-space.schema.json")
    Draft202012Validator(schema).validate(
        {
            "campaign_id": "decoder-registry-css-bb-smoke",
            "mode": "explicit_list",
            "candidate_specs": [
                {
                    "candidate_id": "bivariate-bicycle-code-m6-n6",
                    "code_family": "bivariate-bicycle-code",
                    "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
                    "provenance": {
                        "kind": "zoo-instance",
                        "label": "fixed BB CSS decoder-registry validation instance",
                    },
                }
            ],
        }
    )


def test_candidate_schema_accepts_nested_instance_parameters() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "candidate.schema.json")
    Draft202012Validator(schema).validate(
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "campaign_id": "decoder-registry-css-bb-smoke",
            "run_id": "issue16-bb-css-validation",
            "code_family": "bivariate-bicycle-code",
            "parameters": {
                "m": 6,
                "n": 6,
                "vc": [[1, 0], [0, 1]],
                "hd": [[1, 1], [0, 2]],
            },
            "provenance": {
                "kind": "zoo-instance",
                "label": "fixed BB CSS decoder-registry validation instance",
            },
            "status": "evaluated",
        }
    )


def test_decoder_config_schema_accepts_predict_zero() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "decoder-config.schema.json")
    Draft202012Validator(schema).validate(
        {
            "id": "predict-zero-v1",
            "title": "Predict Zero via rsinter",
            "backend": "rsinter",
            "impl_key": "predict-zero",
            "language": "rust",
            "parameters": {},
            "execution_status": "real",
        }
    )
```

- [ ] **Step 2: Run schema tests and verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py::test_benchmark_task_schema_accepts_css_fixed_rounds_task tests/test_search_eval_schemas.py::test_search_space_schema_accepts_explicit_instance_candidate tests/test_search_eval_schemas.py::test_candidate_schema_accepts_nested_instance_parameters tests/test_search_eval_schemas.py::test_decoder_config_schema_accepts_predict_zero -q
```

Expected: FAIL because the schemas only accept distance-scaled tasks, scalar candidates, and the old decoder impl list.

- [ ] **Step 3: Update schemas**

In `benchmarks/schemas/benchmark-task.schema.json`, replace the `rounds_policy` property with:

```json
"rounds_policy": {
  "oneOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "multiplier", "minimum"],
      "properties": {
        "kind": { "const": "distance-scaled" },
        "multiplier": { "type": "integer", "minimum": 1 },
        "minimum": { "type": "integer", "minimum": 1 }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "rounds"],
      "properties": {
        "kind": { "const": "fixed" },
        "rounds": { "type": "integer", "minimum": 1 }
      }
    }
  ]
},
"css_memory": {
  "type": "object",
  "additionalProperties": false,
  "required": ["basis", "schedule"],
  "properties": {
    "basis": { "enum": ["x", "z"] },
    "schedule": { "enum": ["greedy", "sequential"] }
  }
}
```

Also add `"css_memory"` to `properties`, not to `required`; enforce it in loader/preflight for `input_type == "css"`.

In `benchmarks/schemas/decoder-config.schema.json`, add `"predict-zero"` to `impl_key.enum` and add this `allOf` branch:

```json
{
  "if": {
    "properties": { "impl_key": { "const": "predict-zero" } },
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
}
```

In `benchmarks/schemas/search-space.schema.json`, let each `candidate_specs` item be one of the existing parameter candidate or this explicit instance shape:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["candidate_id", "code_family", "instance_path", "provenance"],
  "properties": {
    "candidate_id": { "type": "string", "minLength": 1 },
    "code_family": { "type": "string", "minLength": 1 },
    "instance_path": { "type": "string", "minLength": 1 },
    "provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "label"],
      "properties": {
        "kind": { "type": "string", "minLength": 1 },
        "label": { "type": "string", "minLength": 1 },
        "strategy": { "enum": ["grid", "random", "adaptive"] }
      }
    }
  }
}
```

In `benchmarks/schemas/candidate.schema.json`, replace scalar-only `parameters.additionalProperties` with this recursive JSON value definition:

```json
"$defs": {
  "jsonValue": {
    "anyOf": [
      { "type": "string" },
      { "type": "integer" },
      { "type": "number" },
      { "type": "boolean" },
      { "type": "null" },
      {
        "type": "array",
        "items": { "$ref": "#/$defs/jsonValue" }
      },
      {
        "type": "object",
        "additionalProperties": { "$ref": "#/$defs/jsonValue" }
      }
    ]
  }
}
```

Use `{ "$ref": "#/$defs/jsonValue" }` for `parameters.additionalProperties`.

- [ ] **Step 4: Add benchmark registry data**

Create `benchmarks/tasks/bb-css-memory-x-cdep-v1.json`:

```json
{
  "id": "bb-css-memory-x-cdep-v1",
  "title": "BB CSS Memory X under circuit depolarizing noise",
  "observable": "logical_x",
  "noise_model": "circuit_depolarizing",
  "input_type": "css",
  "p_list": [0.01],
  "rounds_policy": {
    "kind": "fixed",
    "rounds": 3
  },
  "collection": {
    "max_shots": 2000,
    "max_errors": 200,
    "batch_size": 256
  },
  "css_memory": {
    "basis": "x",
    "schedule": "greedy"
  },
  "result_metrics": ["logical_error_rate"],
  "execution_status": "real"
}
```

Create `benchmarks/decoders/predict-zero-v1.json`:

```json
{
  "id": "predict-zero-v1",
  "title": "Predict Zero via rsinter",
  "backend": "rsinter",
  "impl_key": "predict-zero",
  "language": "rust",
  "parameters": {},
  "execution_status": "real"
}
```

Create `benchmarks/suites/decoder-registry-css-bb-smoke-v1.json`:

```json
{
  "id": "decoder-registry-css-bb-smoke-v1",
  "title": "Decoder Registry CSS BB Smoke v1",
  "task_ids": ["bb-css-memory-x-cdep-v1"],
  "decoder_ids": [
    "rbposd-osd0-v1",
    "rbposd-osd10-v1",
    "predict-zero-v1"
  ],
  "shared_settings": {
    "runner": "rsinter",
    "fixture_manifest": "benchmarks/fixtures/manifest.json"
  }
}
```

Create `campaigns/examples/decoder-registry-css-bb-smoke/campaign.json`:

```json
{
  "id": "decoder-registry-css-bb-smoke",
  "title": "Decoder Registry CSS BB Smoke",
  "default_suite_id": "decoder-registry-css-bb-smoke-v1",
  "budget": {
    "wall_clock_seconds": 600,
    "max_candidates": 1
  },
  "stop_conditions": {
    "max_candidates": 1
  },
  "execution_status": "real"
}
```

Create `campaigns/examples/decoder-registry-css-bb-smoke/search_space.json`:

```json
{
  "campaign_id": "decoder-registry-css-bb-smoke",
  "mode": "explicit_list",
  "candidate_specs": [
    {
      "candidate_id": "bivariate-bicycle-code-m6-n6",
      "code_family": "bivariate-bicycle-code",
      "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
      "provenance": {
        "kind": "zoo-instance",
        "label": "fixed BB CSS decoder-registry validation instance"
      }
    }
  ]
}
```

- [ ] **Step 5: Run schema tests and commit**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py -q
```

Expected: PASS.

Commit:

```bash
git add benchmarks/schemas/benchmark-task.schema.json benchmarks/schemas/decoder-config.schema.json benchmarks/schemas/search-space.schema.json benchmarks/schemas/candidate.schema.json benchmarks/tasks/bb-css-memory-x-cdep-v1.json benchmarks/decoders/predict-zero-v1.json benchmarks/suites/decoder-registry-css-bb-smoke-v1.json campaigns/examples/decoder-registry-css-bb-smoke/campaign.json campaigns/examples/decoder-registry-css-bb-smoke/search_space.json tests/test_search_eval_schemas.py
git commit -m "feat: add css bb smoke benchmark contracts"
```

## Task 4: Resolve Explicit Zoo Instance Candidates

**Files:**
- Modify: `src/autoqec_search/eval_candidates.py`
- Modify: `src/autoqec_search/eval_run.py`
- Modify: `src/autoqec_search/load.py`
- Test: `tests/test_search_eval_candidates.py`
- Test: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Write failing candidate resolution tests**

Append to `tests/test_search_eval_candidates.py`:

```python
def test_resolve_explicit_instance_candidate_uses_instance_path(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "zoo", root / "zoo")
    spec = {
        "candidate_id": "rotated-surface-code-d3",
        "code_family": "rotated-surface-code",
        "instance_path": "zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3",
        "provenance": {"kind": "zoo-instance", "label": "direct"},
    }

    candidate = resolve_campaign_candidate_spec(
        root,
        spec,
        campaign_id="direct-campaign",
    )

    assert candidate.spec.candidate_id == "rotated-surface-code-d3"
    assert candidate.spec.parameters == {"distance": 3, "layout": "rotated"}
    assert candidate.artifact_root.name == "rotated-surface-code-d3"
    assert candidate.source_kind == "explicit-zoo-instance"


def test_copy_candidate_artifacts_writes_unavailable_distance_for_css_without_distance(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    instance_root = (
        root / "zoo" / "codes" / "bivariate-bicycle-code" / "instances" / "bb-small"
    )
    instance_root.mkdir(parents=True)
    _write_json(
        instance_root / "instance.json",
        {
            "id": "bb-small",
            "code_id": "bivariate-bicycle-code",
            "family_id": "bivariate-bicycle-code",
            "title": "BB Small",
            "parameters": {"m": 6, "n": 6, "vc": [[1, 0]], "hd": [[0, 1]]},
            "derived_properties": {"n": 72, "mx": 36, "mz": 36},
            "artifacts": {"hx": "hx.json", "hz": "hz.json"},
            "provenance": {"source": "test"},
        },
    )
    _write_json(instance_root / "hx.json", {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 0, "data": []})
    _write_json(instance_root / "hz.json", {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 0, "data": []})
    candidate = resolve_campaign_candidate_spec(
        root,
        {
            "candidate_id": "bb-small",
            "code_family": "bivariate-bicycle-code",
            "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bb-small",
            "provenance": {"kind": "zoo-instance", "label": "direct"},
        },
        campaign_id="direct-campaign",
    )

    copy_candidate_artifacts(candidate, tmp_path / "candidate")

    distance = _load_json(tmp_path / "candidate" / "distance.json")
    assert distance == {
        "status": "unavailable",
        "distance": None,
        "method": "not-recorded-on-zoo-instance",
        "source_instance_id": "bb-small",
        "source_instance_path": str(instance_root),
    }
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_candidates.py::test_resolve_explicit_instance_candidate_uses_instance_path tests/test_search_eval_candidates.py::test_copy_candidate_artifacts_writes_unavailable_distance_for_css_without_distance -q
```

Expected: FAIL because `instance_path` is not supported and distance is required.

- [ ] **Step 3: Extend candidate model**

Modify `CandidateInput` in `src/autoqec_search/eval_candidates.py`:

```python
@dataclass(frozen=True)
class CandidateInput:
    candidate_id: str
    campaign_id: str
    code_family: str
    parameters: dict[str, Any]
    provenance: dict[str, Any]
    instance_path: str | None = None
```

Add helpers:

```python
def _validate_relative_repo_path(value: str, *, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    if not path.parts:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    return path


def _candidate_spec_from_explicit_instance(
    payload: dict[str, Any],
    campaign_id: str,
) -> CandidateInput:
    for key in ("candidate_id", "code_family", "instance_path", "provenance"):
        if key not in payload:
            raise SearchIntegrityError(f"missing candidate field: {key}")
    if not isinstance(payload["provenance"], dict):
        raise SearchIntegrityError("candidate provenance must be an object")
    _validate_path_segment(payload["candidate_id"], label="candidate_id")
    instance_path = _validate_relative_repo_path(
        payload["instance_path"],
        label="instance_path",
    )
    return CandidateInput(
        candidate_id=payload["candidate_id"],
        campaign_id=campaign_id,
        code_family=payload["code_family"],
        parameters={},
        provenance=dict(payload["provenance"]),
        instance_path=str(instance_path),
    )
```

Modify `resolve_campaign_candidate_spec()`:

```python
def resolve_campaign_candidate_spec(
    root: Path,
    candidate_spec: dict[str, Any],
    *,
    campaign_id: str,
) -> ResolvedCandidate:
    if "instance_path" in candidate_spec:
        spec = _candidate_spec_from_explicit_instance(candidate_spec, campaign_id)
        return _resolve_explicit_zoo_instance(root, spec)
    spec = _candidate_spec_from_search_space(candidate_spec, campaign_id)
    return _resolve_matching_zoo_instance(root, spec)
```

Add `_resolve_explicit_zoo_instance()`:

```python
def _resolve_explicit_zoo_instance(root: Path, spec: CandidateInput) -> ResolvedCandidate:
    if spec.instance_path is None:
        raise SearchIntegrityError("explicit candidate is missing instance_path")
    artifact_root = root / spec.instance_path
    instance, hx, hz = _load_artifact_bundle(artifact_root, require_distance=False)
    if instance.get("id") != spec.candidate_id:
        raise SearchIntegrityError("explicit instance id mismatch")
    if instance.get("code_id") != spec.code_family:
        raise SearchIntegrityError("explicit instance code_id mismatch")
    return ResolvedCandidate(
        spec=CandidateInput(
            candidate_id=spec.candidate_id,
            campaign_id=spec.campaign_id,
            code_family=spec.code_family,
            parameters=dict(instance.get("parameters", {})),
            provenance=spec.provenance,
            instance_path=spec.instance_path,
        ),
        artifact_root=artifact_root,
        instance=instance,
        hx=hx,
        hz=hz,
        source_kind="explicit-zoo-instance",
    )
```

Change `_load_artifact_bundle()`:

```python
def _load_artifact_bundle(
    artifact_root: Path,
    *,
    require_distance: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    instance_path = artifact_root / "instance.json"
    instance = _load_json(instance_path, "instance artifact")
    artifacts = instance.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SearchIntegrityError(f"missing instance artifacts field: {instance_path}")
    _validate_artifact_names(artifacts, instance_path)

    hx = _load_json(artifact_root / "hx.json", "hx artifact")
    hz = _load_json(artifact_root / "hz.json", "hz artifact")
    if require_distance:
        _require_positive_recorded_distance(instance, instance_path)
    return instance, hx, hz
```

Keep existing calls distance-strict by passing no new argument.

- [ ] **Step 4: Write nullable distance artifact**

Replace the distance-writing tail of `copy_candidate_artifacts()`:

```python
    source_instance_id = candidate.instance.get("id")
    if not isinstance(source_instance_id, str) or not source_instance_id:
        raise SearchIntegrityError(
            f"missing source instance id: {candidate.artifact_root / 'instance.json'}"
        )
    derived_properties = candidate.instance.get("derived_properties")
    distance = (
        derived_properties.get("distance")
        if isinstance(derived_properties, dict)
        else None
    )
    if type(distance) is int and distance > 0:
        distance_payload = {
            "status": "completed",
            "distance": distance,
            "method": "copied-from-zoo-instance",
            "source_instance_id": source_instance_id,
            "source_instance_path": str(candidate.artifact_root),
        }
    elif distance is None:
        distance_payload = {
            "status": "unavailable",
            "distance": None,
            "method": "not-recorded-on-zoo-instance",
            "source_instance_id": source_instance_id,
            "source_instance_path": str(candidate.artifact_root),
        }
    else:
        raise SearchIntegrityError("copied instance distance must be a positive integer")
    _write_json(candidate_root / "distance.json", distance_payload)
```

- [ ] **Step 5: Allow campaign eval without --distance for a single explicit instance**

Modify `_resolve_candidate()` in `src/autoqec_search/eval_run.py`:

```python
    if distance is None:
        search_space = workspace.search_spaces.get(campaign_id)
        explicit_specs = []
        if isinstance(search_space, dict):
            explicit_specs = [
                spec
                for spec in search_space.get("candidate_specs", [])
                if isinstance(spec, dict) and "instance_path" in spec
            ]
        if len(explicit_specs) == 1:
            return resolve_campaign_candidate_spec(
                root,
                explicit_specs[0],
                campaign_id=campaign_id,
            )
        raise SearchIntegrityError("eval requires --distance unless --candidate is set")
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_candidates.py tests/test_search_eval_cli.py::test_eval_invalid_decoder_filter_fails_before_rsinter -q
```

Expected: PASS.

Commit:

```bash
git add src/autoqec_search/eval_candidates.py src/autoqec_search/eval_run.py src/autoqec_search/load.py tests/test_search_eval_candidates.py tests/test_search_eval_cli.py
git commit -m "feat: resolve explicit zoo instance candidates"
```

## Task 5: Emit And Parse Rsinter CSS Specs

**Files:**
- Modify: `src/autoqec_search/rsinter.py`
- Modify: `src/autoqec_search/eval_run.py`
- Modify: `src/autoqec_search/render.py`
- Modify: `src/autoqec_search/plot.py`
- Modify: `src/autoqec_search/report.py`
- Test: `tests/test_search_rsinter.py`
- Test: `tests/test_search_plot.py`
- Test: `tests/test_search_report.py`

- [ ] **Step 1: Write failing CSS TOML and parser tests**

Append to `tests/test_search_rsinter.py`:

```python
def test_rounds_for_fixed_task_does_not_require_distance() -> None:
    assert rounds_for_task({"rounds_policy": {"kind": "fixed", "rounds": 3}}, distance=None) == 3


def test_write_spec_toml_writes_css_runner_params(tmp_path: Path) -> None:
    spec_path = tmp_path / "candidate" / "rsinter" / "spec.toml"
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "p_list": [0.01],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 2000, "max_errors": 200, "batch_size": 256},
        "css_memory": {"basis": "x", "schedule": "greedy"},
    }
    decoders = {
        "rbposd-osd10-v1": {
            "id": "rbposd-osd10-v1",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {"bp_iters": 50, "early_stop": True, "osd_order": 10},
        }
    }

    write_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rbposd-osd10-v1"],
        distance=None,
        rounds=3,
        p_values=[0.01],
        css_input={
            "code_id": "bivariate-bicycle-code-m6-n6",
            "hx": "../artifacts/hx.json",
            "hz": "../artifacts/hz.json",
        },
    )

    params = tomllib.loads(spec_path.read_text())["runner"][0]["params"]
    assert params["input_type"] == "css"
    assert params["code_id"] == "bivariate-bicycle-code-m6-n6"
    assert params["hx"] == "../artifacts/hx.json"
    assert params["hz"] == "../artifacts/hz.json"
    assert params["basis"] == "x"
    assert params["schedule"] == "greedy"
    assert "distance" not in params
    assert params["osd_order"] == 10


def test_parse_results_jsonl_accepts_css_rows_without_distance(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-osd10-v1",
                params={
                    "input_type": "css",
                    "code_id": "bivariate-bicycle-code-m6-n6",
                    "hx": "../artifacts/hx.json",
                    "hz": "../artifacts/hz.json",
                    "basis": "x",
                    "schedule": "greedy",
                    "rounds": 3,
                    "p": 0.01,
                    "bp_iters": 50,
                    "early_stop": True,
                    "osd_order": 10,
                },
                metrics={
                    "shots_used": 2000,
                    "logical_errors": 40,
                    "logical_error_rate": 0.02,
                },
            ),
            sort_keys=True,
        )
        + "\n"
    )

    parsed = parse_results_jsonl(
        path,
        expected_decoder_id="rbposd-osd10-v1",
        expected_task_id="bb-css-memory-x-cdep-v1",
        expected_distance=None,
        expected_p_values=[0.01],
        expected_decoder_parameters={"bp_iters": 50, "early_stop": True, "osd_order": 10},
        expected_impl_key="rbposd",
    )

    assert parsed.decoder_parameters["osd_order"] == 10
    assert parsed.points[0]["ler"] == 0.02
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py::test_rounds_for_fixed_task_does_not_require_distance tests/test_search_rsinter.py::test_write_spec_toml_writes_css_runner_params tests/test_search_rsinter.py::test_parse_results_jsonl_accepts_css_rows_without_distance -q
```

Expected: FAIL because fixed rounds, `css_input`, and `expected_distance=None` are unsupported.

- [ ] **Step 3: Implement fixed rounds**

Replace `rounds_for_task()` in `src/autoqec_search/rsinter.py`:

```python
def rounds_for_task(task: dict, *, distance: int | None) -> int:
    policy = task["rounds_policy"]
    if policy["kind"] == "fixed":
        rounds = int(policy["rounds"])
        if rounds < 1:
            raise SearchIntegrityError(f"invalid fixed rounds: {rounds}")
        return rounds
    if policy["kind"] != "distance-scaled":
        raise SearchIntegrityError(f"unsupported rounds policy: {policy['kind']}")
    if distance is None:
        raise SearchIntegrityError("distance-scaled rounds require a distance")
    return max(int(policy["minimum"]), int(policy["multiplier"]) * distance)
```

Update all call sites so `distance` may be `None`.

- [ ] **Step 4: Implement CSS TOML branch**

Change `write_spec_toml()` signature in `src/autoqec_search/rsinter.py`:

```python
def write_spec_toml(
    spec_path: str | Path,
    *,
    task: dict,
    decoders: dict[str, dict],
    selected_decoder_ids: list[str],
    distance: int | None,
    rounds: int,
    p_values: list[float],
    css_input: dict[str, str] | None = None,
) -> None:
```

Inside the runner loop, replace the hard-coded distance params with:

```python
                f"rounds = [{rounds}]",
                f"p = [{p_list}]",
                f'max_shots = {int(collection["max_shots"])}',
                f'max_errors = {int(collection["max_errors"])}',
                f"batch_size = {batch_size}",
```

Then insert input-specific params before decoder params:

```python
        if task.get("input_type") == "css":
            if css_input is None:
                raise SearchIntegrityError("css rsinter spec requires css_input")
            css_memory = task.get("css_memory")
            if not isinstance(css_memory, dict):
                raise SearchIntegrityError("css task requires css_memory")
            for key in ("code_id", "hx", "hz"):
                value = css_input.get(key)
                if not isinstance(value, str) or not value:
                    raise SearchIntegrityError(f"css_input missing {key}")
            lines.extend(
                [
                    'input_type = "css"',
                    f"code_id = {_toml_string(css_input['code_id'])}",
                    f"hx = {_toml_string(css_input['hx'])}",
                    f"hz = {_toml_string(css_input['hz'])}",
                    f"basis = {_toml_string(str(css_memory['basis']))}",
                    f"schedule = {_toml_string(str(css_memory['schedule']))}",
                ]
            )
        else:
            if distance is None:
                raise SearchIntegrityError("surface rsinter spec requires distance")
            lines.append(f"distance = [{distance}]")
```

For plot metadata, use CSS grouping when distance is absent:

```python
    if task.get("input_type") == "css":
        group_by = '["runner", "params.code_id"]'
        label_template = "{runner} {params.code_id}"
    else:
        group_by = '["runner", "params.distance"]'
        label_template = "{runner} d={params.distance}"
```

Write these in the `[plot.series]` block.

- [ ] **Step 5: Implement optional distance parsing**

In `parse_results_jsonl()`, keep validating distance only when expected distance is provided:

```python
        if expected_distance is not None:
            if "distance" not in params:
                raise SearchIntegrityError(
                    f"{results_path}:{line_number}: missing distance"
                )
            distance = _require_int(
                params, "distance", results_path, line_number, "param"
            )
            if distance != expected_distance:
                raise SearchIntegrityError(
                    f"{results_path}:{line_number}: unexpected distance: {distance}"
                )
        elif "distance" in params:
            _require_int(params, "distance", results_path, line_number, "param")
```

- [ ] **Step 6: Pass CSS input from eval**

In `src/autoqec_search/eval_run.py`, make copied distance nullable:

```python
def _copied_instance_distance(candidate: ResolvedCandidate) -> int | None:
    derived_properties = candidate.instance.get("derived_properties")
    distance = (
        derived_properties.get("distance")
        if isinstance(derived_properties, dict)
        else None
    )
    if distance is None:
        return None
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError("copied instance distance must be a positive integer")
    return distance
```

Before `write_spec_toml()`:

```python
    css_input = None
    if task.get("input_type") == "css":
        css_input = {
            "code_id": str(candidate.instance.get("id", candidate_id)),
            "hx": "../artifacts/hx.json",
            "hz": "../artifacts/hz.json",
        }
```

Pass it:

```python
        distance=copied_distance,
        rounds=rounds,
        p_values=selected_p_values,
        css_input=css_input,
```

- [ ] **Step 7: Allow plots and summaries with no distance**

Change `render_candidate_plot()` signature in `src/autoqec_search/plot.py`:

```python
def render_candidate_plot(
    candidate_id: str,
    distance: int | None,
    task_id: str,
    generated_at: str,
    manifests: list[dict],
) -> str:
```

Replace the footer:

```python
    distance_text = "unavailable" if distance is None else str(distance)
    footer = (
        f"candidate={candidate_id}, distance={distance_text}, "
        f"task={task_id}, generated={generated_at}"
    )
```

Change `render_eval_summary()` in `src/autoqec_search/render.py`:

```python
    distance_text = "unavailable" if distance is None else str(distance)
```

Use `distance_text` in the distance line.

In `src/autoqec_search/report.py`, change `_point_payload()` to accept `distance: int | None`, remove the error for completed points with `distance is None`, and skip threshold estimation for points whose distance is not an integer:

```python
        distance = point.get("distance")
        if type(distance) is not int or p is None or ler is None:
            continue
```

- [ ] **Step 8: Run tests and commit**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_rsinter.py tests/test_search_plot.py tests/test_search_report.py -q
```

Expected: PASS.

Commit:

```bash
git add src/autoqec_search/rsinter.py src/autoqec_search/eval_run.py src/autoqec_search/render.py src/autoqec_search/plot.py src/autoqec_search/report.py tests/test_search_rsinter.py tests/test_search_plot.py tests/test_search_report.py
git commit -m "feat: emit css rsinter benchmark specs"
```

## Task 6: Add Fake-Rsinter CSS E2E Coverage

**Files:**
- Modify: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Update fake rsinter to understand CSS params**

In `_write_fake_rsinter()` inside `tests/test_search_eval_cli.py`, replace:

```python
    distance = int(params["distance"][0])
```

with:

```python
    distance = int(params["distance"][0]) if "distance" in params else None
    input_type = params.get("input_type", "surface_rotated_memory_x")
    code_id = params.get("code_id")
```

Replace row params creation:

```python
        row_params = {
            "rounds": rounds,
            "p": p,
            **decoder_params,
        }
        if distance is not None:
            row_params["distance"] = distance
        if input_type == "css":
            row_params.update(
                {
                    "input_type": "css",
                    "code_id": code_id,
                    "hx": params["hx"],
                    "hz": params["hz"],
                    "basis": params["basis"],
                    "schedule": params["schedule"],
                }
            )
```

Add predict-zero deterministic errors:

```python
        if decoder_id == "predict-zero-v1":
            errors = shots // 2
```

- [ ] **Step 2: Write CSS eval CLI test**

Append to `tests/test_search_eval_cli.py`:

```python
def test_eval_css_bb_smoke_records_params_and_negative_control(
    tmp_path: Path,
) -> None:
    work_root = _copy_search_tree(tmp_path)
    bb_instance = (
        work_root
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    bb_instance.mkdir(parents=True)
    _write_json(
        bb_instance / "instance.json",
        {
            "id": "bivariate-bicycle-code-m6-n6",
            "code_id": "bivariate-bicycle-code",
            "family_id": "bivariate-bicycle-code",
            "title": "Bivariate Bicycle Code m=6 n=6",
            "parameters": {
                "m": 6,
                "n": 6,
                "vc": [[1, 0], [0, 1]],
                "hd": [[1, 1], [0, 2]],
            },
            "derived_properties": {"n": 72, "mx": 36, "mz": 36},
            "artifacts": {"hx": "hx.json", "hz": "hz.json"},
            "provenance": {"source": "test"},
        },
    )
    _write_json(bb_instance / "hx.json", {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 2, "data": [[1, 1]]})
    _write_json(bb_instance / "hz.json", {"format": "dense_binary_matrix", "n_rows": 1, "n_cols": 2, "data": [[0, 0]]})
    env = _env_with_rsinter(_write_fake_rsinter(tmp_path))

    result = _run_eval(
        work_root,
        env,
        "--campaign",
        "decoder-registry-css-bb-smoke",
        "--decoder",
        "rbposd-osd0-v1",
        "--decoder",
        "rbposd-osd10-v1",
        "--decoder",
        "predict-zero-v1",
        "--p",
        "0.01",
        "--run-id",
        "css-bb-smoke",
    )

    assert result.returncode == 0, result.stderr
    candidate_root = (
        work_root
        / "results"
        / "search"
        / "decoder-registry-css-bb-smoke"
        / "css-bb-smoke"
        / "candidates"
        / "bivariate-bicycle-code-m6-n6"
    )
    task_id = "bb-css-memory-x-cdep-v1"
    osd0 = _load_json(candidate_root / "evaluations" / task_id / "rbposd-osd0-v1" / "manifest.json")
    osd10 = _load_json(candidate_root / "evaluations" / task_id / "rbposd-osd10-v1" / "manifest.json")
    zero = _load_json(candidate_root / "evaluations" / task_id / "predict-zero-v1" / "manifest.json")

    assert osd0["decoder_parameters"]["osd_order"] == 0
    assert osd10["decoder_parameters"]["osd_order"] == 10
    assert osd10["points"][0]["ler"] < osd0["points"][0]["ler"]
    assert 0.35 <= zero["points"][0]["ler"] <= 0.65
    assert _load_json(candidate_root / "distance.json")["distance"] is None

    spec_text = (candidate_root / "rsinter" / "spec.toml").read_text()
    assert 'input_type = "css"' in spec_text
    assert 'code_id = "bivariate-bicycle-code-m6-n6"' in spec_text
    assert 'hx = "../artifacts/hx.json"' in spec_text
    assert "distance = [" not in spec_text
```

- [ ] **Step 3: Run the CSS eval CLI test and commit**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_cli.py::test_eval_css_bb_smoke_records_params_and_negative_control -q
```

Expected: PASS.

Commit:

```bash
git add tests/test_search_eval_cli.py
git commit -m "test: cover css bb decoder registry eval"
```

## Task 7: Add The Fixed BB Instance And Real Validation Artifact

**Files:**
- Create: `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/instance.json`
- Create: `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/hx.json`
- Create: `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/hz.json`
- Create: `results/search/decoder-registry-css-bb-smoke/issue16-bb-css-validation/...`
- Test: `tests/test_search_e2e.py`

- [ ] **Step 1: Generate the BB instance**

Run:

```bash
julia --startup-file=no --history-file=no --project=julia/tensorqec_env julia/tensorqec_env/scripts/generate_instance.jl --code-id bivariate-bicycle-code --m 6 --n 6 --vc '[[1,0],[0,1]]' --hd '[[1,1],[0,2]]' --output-root zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6
```

Expected: `instance.json`, `hx.json`, and `hz.json` exist under `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/`.

- [ ] **Step 2: Validate generated instance shape**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_cli.py::test_tensorqec_generator_writes_bbcode_instance -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: PASS.

- [ ] **Step 3: Run the real CSS BB eval**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign decoder-registry-css-bb-smoke --decoder rbposd-osd0-v1 --decoder rbposd-osd10-v1 --decoder predict-zero-v1 --p 0.01 --run-id issue16-bb-css-validation --force
```

Expected: command exits 0 and creates `results/search/decoder-registry-css-bb-smoke/issue16-bb-css-validation/`.

- [ ] **Step 4: Write artifact validation test**

Append to `tests/test_search_e2e.py`:

```python
def test_issue16_bb_css_validation_artifact_closes_decoder_registry_gap() -> None:
    run_root = (
        REPO_ROOT
        / "results"
        / "search"
        / "decoder-registry-css-bb-smoke"
        / "issue16-bb-css-validation"
    )
    candidate_root = run_root / "candidates" / "bivariate-bicycle-code-m6-n6"
    task_id = "bb-css-memory-x-cdep-v1"

    osd0 = _load_json(candidate_root / "evaluations" / task_id / "rbposd-osd0-v1" / "manifest.json")
    osd10 = _load_json(candidate_root / "evaluations" / task_id / "rbposd-osd10-v1" / "manifest.json")
    zero = _load_json(candidate_root / "evaluations" / task_id / "predict-zero-v1" / "manifest.json")

    assert osd0["status"] == "completed"
    assert osd10["status"] == "completed"
    assert zero["status"] == "completed"
    assert osd0["decoder_parameters"]["osd_order"] == 0
    assert osd10["decoder_parameters"]["osd_order"] == 10
    assert osd10["points"][0]["ler"] < osd0["points"][0]["ler"]
    assert 0.35 <= zero["points"][0]["ler"] <= 0.65

    for decoder_id in ("rbposd-osd0-v1", "rbposd-osd10-v1", "predict-zero-v1"):
        row_path = candidate_root / "rsinter" / "out" / decoder_id / "test-run" / "results.jsonl"
        assert row_path.is_file()
        row = json.loads(row_path.read_text().splitlines()[0])
        assert row["params"]["input_type"] == "css"
        assert row["params"]["code_id"] == "bivariate-bicycle-code-m6-n6"
        assert row["params"]["hx"] == "../artifacts/hx.json"
        assert row["params"]["hz"] == "../artifacts/hz.json"
```

- [ ] **Step 5: Run artifact validation and commit**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py::test_issue16_bb_css_validation_artifact_closes_decoder_registry_gap -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: PASS.

Commit:

```bash
git add zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6 results/search/decoder-registry-css-bb-smoke/issue16-bb-css-validation tests/test_search_e2e.py
git commit -m "test: add issue16 bb css validation artifact"
```

## Task 8: Preflight And Documentation

**Files:**
- Modify: `src/autoqec_search/preflight.py`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `benchmarks/README.md`
- Test: `tests/test_search_preflight.py`
- Test: `tests/test_search_docs.py`

- [ ] **Step 1: Write failing preflight test**

Append to `tests/test_search_preflight.py`:

```python
def test_preflight_requires_predict_zero_when_decoder_is_registered(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rsinter = bin_dir / "rsinter"
    rsinter.write_text(
        f"""#!{sys.executable}
import sys
if sys.argv[1:] == ["--version"]:
    print("rsinter git main without-predict-zero")
    raise SystemExit(0)
if sys.argv[1:3] == ["bench", "run"]:
    print("unknown rust runner: predict-zero", file=sys.stderr)
    raise SystemExit(1)
raise SystemExit(2)
"""
    )
    rsinter.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "preflight",
            "--root",
            str(work_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "predict-zero" in result.stdout + result.stderr
```

- [ ] **Step 2: Implement predict-zero preflight check**

Add this import to `src/autoqec_search/preflight.py`:

```python
import tempfile
```

Add a helper in `src/autoqec_search/preflight.py`:

```python
def _workspace_uses_predict_zero(root: Path) -> bool:
    decoder_path = root / "benchmarks" / "decoders" / "predict-zero-v1.json"
    if not decoder_path.is_file():
        return False
    decoder = _load_json(decoder_path)
    return decoder.get("impl_key") == "predict-zero"
```

Add the real smoke check:

```python
def _check_predict_zero_runner(root: Path) -> PreflightRow:
    if not _workspace_uses_predict_zero(root):
        return PreflightRow("PASS", "rsinter predict-zero runner", "not used")
    rsinter = shutil.which("rsinter")
    if rsinter is None:
        return PreflightRow("FAIL", "rsinter predict-zero runner", "rsinter not found on PATH")
    spec_text = """name = "autoqec-preflight-predict-zero"
version = 1
mode = "independent"

[[runner]]
name = "predict-zero-v1"
language = "rust"
impl_key = "predict-zero"

[runner.params]
distance = [3]
rounds = [3]
p = [0.01]
max_shots = 1
max_errors = 1
batch_size = 1

[plot]
title = "AutoQEC predict-zero preflight"

[plot.x]
field = "params.p"
scale = "log"
label = "Physical Error Rate"

[plot.series]
group_by = ["runner", "params.distance"]
label_template = "{runner} d={params.distance}"

[[plot.panel]]
metric = "metrics.logical_error_rate"
scale = "log"
label = "Logical Error Rate"
"""
    with tempfile.TemporaryDirectory(prefix="autoqec-preflight-predict-zero-") as tmp:
        tmp_root = Path(tmp)
        spec_path = tmp_root / "spec.toml"
        out_dir = tmp_root / "out"
        spec_path.write_text(spec_text)
        result = subprocess.run(
            [rsinter, "bench", "run", "--spec", str(spec_path), "--language", "rust", "--out", str(out_dir)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            return PreflightRow(
                "FAIL",
                "rsinter predict-zero runner",
                detail or "predict-zero smoke run failed",
            )
        result_path = out_dir / "predict-zero-v1" / "test-run" / "results.jsonl"
        if not result_path.is_file():
            return PreflightRow(
                "FAIL",
                "rsinter predict-zero runner",
                f"missing smoke results: {result_path}",
            )
    return PreflightRow(
        "PASS",
        "rsinter predict-zero runner",
        "predict-zero smoke run succeeded",
    )
```

Add `_check_predict_zero_runner(root)` to the rows returned by `run_preflight()` immediately after `_check_rsinter()`.

- [ ] **Step 3: Update docs tests**

Append to `tests/test_search_docs.py`:

```python
def test_docs_mention_issue16_css_bb_validation_boundary() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()
    benchmarks = (REPO_ROOT / "benchmarks" / "README.md").read_text()

    for document in (readme, claude, benchmarks):
        assert "decoder-registry-css-bb-smoke" in document
        assert "predict-zero-v1" in document
        assert "bp_iters" in document
        assert "max_bp_iterations" in document
        assert "bivariate-bicycle-code-m6-n6" in document
        assert "Closes #16" in document or "issue #16" in document
```

- [ ] **Step 4: Update docs text**

Add a section to `benchmarks/README.md`:

```markdown
## Decoder Registry Issue #16 Validation

Decoder configs are concrete registry entries. `rbposd` accepts
`max_bp_iterations` as an input alias, but generated specs and artifacts record
the canonical `bp_iters` key.

The `decoder-registry-css-bb-smoke` campaign validates issue #16 against the
fixed `bivariate-bicycle-code-m6-n6` CSS instance through `rsinter`'s
`input_type = "css"` path. The suite compares `rbposd-osd0-v1`,
`rbposd-osd10-v1`, and `predict-zero-v1`. `predict-zero-v1` is a negative
control and requires an installed `rsinter` with the `predict-zero` runner.
```

Add this paragraph to `README.md` near the existing `autoqec-search eval` section:

```markdown
Issue #16 is validated by `decoder-registry-css-bb-smoke`, which runs the fixed
`bivariate-bicycle-code-m6-n6` CSS instance through `rsinter` with
`rbposd-osd0-v1`, `rbposd-osd10-v1`, and `predict-zero-v1`. `rbposd`
accepts `max_bp_iterations` as an input alias, but generated specs and
artifacts use canonical `bp_iters`. `predict-zero-v1` requires an installed
`rsinter` with the `predict-zero` runner and acts as the negative control for
issue #16.
```

Add this bullet to `CLAUDE.md` near the existing search-layer notes:

```markdown
- Decoder-registry issue #16 is complete only when
  `decoder-registry-css-bb-smoke` has a real `issue16-bb-css-validation`
  artifact for `bivariate-bicycle-code-m6-n6`; manifests must record
  `osd_order`, `max_bp_iterations` must canonicalize to `bp_iters`, and
  `predict-zero-v1` must run through a real `rsinter` `predict-zero` runner.
```

- [ ] **Step 5: Run preflight/docs tests and commit**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_preflight.py tests/test_search_docs.py -q
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

Expected: PASS when the `rsinter` companion runner is installed.

Commit:

```bash
git add src/autoqec_search/preflight.py README.md CLAUDE.md benchmarks/README.md tests/test_search_preflight.py tests/test_search_docs.py
git commit -m "docs: document issue16 css bb validation"
```

## Task 9: Full Verification And PR Body Update

**Files:**
- Modify PR #31 body on GitHub

- [ ] **Step 1: Run focused test suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_eval_schemas.py tests/test_search_rsinter.py tests/test_search_eval_candidates.py tests/test_search_eval_cli.py tests/test_search_plot.py tests/test_search_report.py tests/test_search_preflight.py tests/test_search_docs.py tests/test_search_e2e.py -q
```

Expected: PASS.

- [ ] **Step 2: Run workspace commands**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

Expected: both PASS.

- [ ] **Step 3: Run full pytest**

Run:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 4: Update PR #31 body**

Use the GitHub app or `gh pr edit 31` to replace the PR body with text that includes:

```markdown
Closes #16

## Issue #16 validation

- Decoder configs are concrete registry entries.
- `max_bp_iterations` is accepted as an input alias and canonicalized to `bp_iters`.
- `decoder-registry-css-bb-smoke` runs the fixed `bivariate-bicycle-code-m6-n6` CSS instance through real `rsinter`.
- Result rows and manifests record `osd_order` for `rbposd-osd0-v1` and `rbposd-osd10-v1`.
- The committed `issue16-bb-css-validation` artifact satisfies `LER(rbposd-osd10-v1) < LER(rbposd-osd0-v1)`.
- `predict-zero-v1` is a real `rsinter` negative control and lands in the configured wide LER window.
```

- [ ] **Step 5: Confirm no local catch-all commit is needed**

If Task 9 modified only the PR body, no local commit is needed. If verification reveals local code, doc, or artifact corrections, return to the task that owns those files, update its tests and implementation, rerun that task's verification command, and create that task's scoped commit. Do not create a catch-all finalization commit.

```bash
git status --short
```

Expected: `git status --short` is empty after task-scoped commits, and the PR body accurately reflects issue #16 completion.

## Self-Review Checklist

- Spec coverage: Tasks 1 and 8 cover real predict-zero; Tasks 2 and 5 cover canonical params; Tasks 3, 4, 5, 6, and 7 cover CSS/BB eval and artifacts; Task 9 covers final verification and PR body.
- Open-slot scan: The plan names files, tests, code snippets, commands, and expected outcomes for each task.
- Type consistency: `distance` becomes `int | None` in `rsinter.py`, `eval_run.py`, plotting, summary, and reporting. Decoder parameter canonicalization lives in `decoder_parameters.py` and is reused from `rsinter.py`.

# Issue 18 BB qLDPC Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete AutoQEC issue #18 by carrying the paper-backed BB72 `[[72,12,6]]` bivariate-bicycle CSS instance through search, rsinter evaluation, reference validation, reporting, and Zoo promotion.

**Architecture:** Keep AutoQEC responsible for curated instance provenance, campaign definitions, result parsing, reference checks, reporting, and promotion. Keep rstim/rsinter/qec-code responsible for CSS circuit generation, explicit logical observables, BP+OSD behavior, and exact distance verification. The hot path uses the recorded exact BB72 Zoo distance and a fast positive-shot rsinter contract; heavy qec-code and long paper-reference runs remain focused/manual checks.

**Tech Stack:** Python 3.11, pytest, jsonschema, AutoQEC search CLI, AutoQEC Zoo builder, rsinter CSS benchmark TOML, rstim/qec-code manual verification binaries.

## Global Constraints

- Preserve the existing AutoQEC module boundaries: `autoqec_search` owns campaign/eval/report/promotion, `autoqec_zoo` owns Zoo build/render.
- Do not make the qec-code BB72 ILP probe part of normal fast tests; it took about 149 seconds locally on 2026-06-18.
- Do not present zero-shot rsinter rows as evidence; completed AutoQEC manifests must keep positive `shots`.
- BB72 paper parameters are `l = 6`, `m = 6`, `A = x^3 + y + y^2`, `B = y^3 + x + x^2`, paper ref `2308.07915`.
- BB72 exact distance is `6`, and accepted artifacts must keep `parameters.distance`, `derived_properties.distance`, `distance.json.distance`, and frontier distance equal to `6`.
- The BB72 task uses `input_type = "css"`, `observable = "logical_x"`, `basis = "x"`, `schedule = "greedy"`, and `rounds = 3`.
- The BB72 BP+OSD runner uses `bp_algorithm = "min_sum"`, `bp_iters = 50`, `early_stop = true`, `osd_method = "combination_sweep"`, and `osd_order = 10`.
- The BB72 rsinter spec must include `hx`, `hz`, `observables`, `seed`, and must not include surface-style distance arrays such as `distance = [3]`.
- Published-reference validation uses Bravyi Table 6 coefficients `d_circ = 6`, `c0 = 11.09`, `c1 = 365.6`, `c2 = -16088`.
- Promotion must reject non-exact distance payloads, missing/null distance, distance mismatches, and failed required reference checks.

---

## File Structure

- Modify `benchmarks/schemas/decoder-config.schema.json`: allow paper-facing rbposd labels `bp_algorithm` and `osd_method`.
- Modify `benchmarks/schemas/benchmark-task.schema.json`: allow CSS memory `seed` and `observables` requirement metadata.
- Modify `benchmarks/schemas/result-manifest.schema.json`: allow completed manifest `run_metadata`.
- Modify `benchmarks/schemas/promote-rules.schema.json`: add `require_reference_check`.
- Modify `zoo/schemas/code-instance.schema.json`: allow optional `artifacts.observables_x = "observables_x.json"`.
- Modify `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/instance.json`: normalize BB72 paper/generator metadata and exact distance.
- Create `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/observables_x.json`: explicit BB72 logical-X observable rows.
- Modify `src/autoqec_search/eval_candidates.py`: load/copy optional observable artifacts, resolve explicit-instance parameters and distance, accept nested JSON candidate parameters.
- Modify `src/autoqec_search/rsinter.py`: write observable wrappers, emit `observables` and `seed`, preserve rsinter observable metadata separately from decoder parameters.
- Modify `src/autoqec_search/eval_run.py`: write CSS observable inputs and require them for BB72 paper-facing tasks.
- Create `src/autoqec_search/reference_check.py`: load a reference fixture, evaluate observed Wilson intervals, write PASS/FAIL JSON.
- Modify `src/autoqec_search/cli.py`: add `autoqec-search reference-check`.
- Modify `src/autoqec_search/report.py`: include reference-check status and run metadata in the report model and HTML.
- Modify `src/autoqec_search/promote.py`: enforce required `reference_check.json`, promote optional observable artifacts, and include them in idempotency checks.
- Create `benchmarks/fixtures/bb72-reference/expected.json`: Bravyi Table 6 reference fixture.
- Create `benchmarks/decoders/rbposd-bb72-osd10-v1.json`: BB72 paper-facing rbposd decoder config.
- Modify `benchmarks/tasks/bb-css-memory-x-cdep-v1.json`: make it BB72 paper-facing with positive shots, seed, and required observables.
- Create `benchmarks/suites/bb72-qldpc-campaign-v1.json`: primary BB72 suite.
- Create `campaigns/examples/bb72-qldpc-campaign/campaign.json`.
- Create `campaigns/examples/bb72-qldpc-campaign/search_space.json`.
- Create `campaigns/examples/bb72-qldpc-campaign/promote_rules.json`.
- Add focused tests in `tests/test_search_eval_candidates.py`, `tests/test_search_rsinter.py`, `tests/test_search_eval_run.py`, `tests/test_search_reference_check.py`, `tests/test_search_promote.py`, `tests/test_search_report.py`, and `tests/test_load.py`.

---

### Task 1: Accept BB72 BP+OSD Parameter Labels In Schemas

**Files:**
- Modify: `benchmarks/schemas/decoder-config.schema.json`
- Test: `tests/test_search_rsinter.py`

**Interfaces:**
- Consumes: existing `Draft202012Validator` schema-loading test pattern.
- Produces: schema acceptance for rbposd `bp_algorithm` and `osd_method`, used by `benchmarks/decoders/rbposd-bb72-osd10-v1.json` in Task 6.

- [ ] **Step 1: Write the failing schema test**

Append this test to `tests/test_search_rsinter.py`:

```python
def test_decoder_schema_accepts_bb72_paper_rbposd_parameters() -> None:
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "benchmarks" / "schemas" / "decoder-config.schema.json").read_text()
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        {
            "id": "rbposd-bb72-osd10-v1",
            "title": "BB72 BP+OSD OSD10 via rsinter",
            "backend": "rsinter",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {
                "bp_algorithm": "min_sum",
                "bp_iters": 50,
                "early_stop": True,
                "osd_method": "combination_sweep",
                "osd_order": 10,
            },
            "execution_status": "real",
        }
    )
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/test_search_rsinter.py::test_decoder_schema_accepts_bb72_paper_rbposd_parameters -q
```

Expected: FAIL with a jsonschema validation error naming `bp_algorithm` or `osd_method`.

- [ ] **Step 3: Update the decoder schema**

In `benchmarks/schemas/decoder-config.schema.json`, update the rbposd `parameters.properties` object to include:

```json
"bp_algorithm": { "enum": ["min_sum"] },
"osd_method": { "enum": ["combination_sweep"] },
```

Keep these existing rbposd properties:

```json
"bp_iters": { "type": "integer", "minimum": 0 },
"max_bp_iterations": { "type": "integer", "minimum": 0 },
"early_stop": { "type": "boolean" },
"osd_order": { "type": "integer", "minimum": 0 }
```

Keep `additionalProperties: false`.

- [ ] **Step 4: Run the focused test and existing decoder tests**

Run:

```bash
uv run pytest tests/test_search_rsinter.py::test_decoder_schema_accepts_bb72_paper_rbposd_parameters tests/test_search_load.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add benchmarks/schemas/decoder-config.schema.json tests/test_search_rsinter.py
git commit -m "test: accept bb72 rbposd parameter labels"
```

---

### Task 2: Normalize BB72 Zoo Instance And Optional Observables Artifact

**Files:**
- Modify: `zoo/schemas/code-instance.schema.json`
- Modify: `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/instance.json`
- Create: `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/observables_x.json`
- Modify: `src/autoqec_search/eval_candidates.py`
- Test: `tests/test_search_eval_candidates.py`
- Test: `tests/test_load.py`

**Interfaces:**
- Consumes: existing Zoo instance `hx.json` and `hz.json`.
- Produces: `ResolvedCandidate.observables_x: dict[str, Any] | None`, optional `artifacts/observables_x.json` copied into candidate run artifacts, and a schema-valid BB72 instance with exact distance metadata.

- [ ] **Step 1: Write failing candidate artifact tests**

Append these tests to `tests/test_search_eval_candidates.py`:

```python
def test_resolve_explicit_bb72_instance_loads_distance_and_observables() -> None:
    candidate = resolve_campaign_candidate_spec(
        REPO_ROOT,
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "code_family": "bivariate-bicycle-code",
            "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
            "provenance": {
                "kind": "paper-seed",
                "label": "Bravyi et al. BB [[72,12,6]]",
            },
        },
        campaign_id="bb72-qldpc-campaign",
    )

    assert candidate.spec.parameters["distance"] == 6
    assert candidate.spec.parameters["paper"] == {
        "l": 6,
        "m": 6,
        "A": "x^3 + y + y^2",
        "B": "y^3 + x + x^2",
        "paper_ref": "2308.07915",
    }
    assert candidate.instance["derived_properties"]["distance"] == 6
    assert candidate.observables_x is not None
    assert candidate.observables_x["format"] == "sparse_rows"
    assert candidate.observables_x["num_cols"] == 72
    assert len(candidate.observables_x["rows"]) == 12


def test_copy_candidate_artifacts_preserves_bb72_observables(tmp_path: Path) -> None:
    candidate = resolve_campaign_candidate_spec(
        REPO_ROOT,
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "code_family": "bivariate-bicycle-code",
            "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
            "provenance": {"kind": "paper-seed", "label": "BB72"},
        },
        campaign_id="bb72-qldpc-campaign",
    )

    copy_candidate_artifacts(candidate, tmp_path / "candidate")

    assert sorted(path.name for path in (tmp_path / "candidate" / "artifacts").iterdir()) == [
        "hx.json",
        "hz.json",
        "instance.json",
        "observables_x.json",
    ]
    copied = _load_json(tmp_path / "candidate" / "artifacts" / "observables_x.json")
    assert copied["num_cols"] == 72
    assert len(copied["rows"]) == 12
```

Append this schema/structure test to `tests/test_load.py`:

```python
def test_bb72_instance_is_paper_backed_and_schema_valid() -> None:
    from jsonschema import Draft202012Validator
    from autoqec_search.structure import summarize_css_structure

    root = Path(__file__).resolve().parents[1]
    instance_root = root / "zoo" / "codes" / "bivariate-bicycle-code" / "instances" / "bivariate-bicycle-code-m6-n6"
    schema = json.loads((root / "zoo" / "schemas" / "code-instance.schema.json").read_text())
    instance = json.loads((instance_root / "instance.json").read_text())
    hx = json.loads((instance_root / "hx.json").read_text())
    hz = json.loads((instance_root / "hz.json").read_text())

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(instance)
    structure = summarize_css_structure(hx, hz)

    assert instance["parameters"]["distance"] == 6
    assert instance["parameters"]["paper"]["paper_ref"] == "2308.07915"
    assert instance["derived_properties"]["distance"] == 6
    assert structure["n"] == 72
    assert structure["k"] == 12
    assert structure["css_commute"] is True
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run pytest tests/test_search_eval_candidates.py::test_resolve_explicit_bb72_instance_loads_distance_and_observables tests/test_search_eval_candidates.py::test_copy_candidate_artifacts_preserves_bb72_observables tests/test_load.py::test_bb72_instance_is_paper_backed_and_schema_valid -q
```

Expected: FAIL because the BB72 instance has null distance, no `observables_x.json`, and `ResolvedCandidate` has no `observables_x`.

- [ ] **Step 3: Extend the Zoo instance schema**

In `zoo/schemas/code-instance.schema.json`, update `properties.artifacts` to allow optional `observables_x` while keeping `hx` and `hz` required:

```json
"artifacts": {
  "type": "object",
  "additionalProperties": false,
  "required": [
    "hx",
    "hz"
  ],
  "properties": {
    "hx": {
      "const": "hx.json"
    },
    "hz": {
      "const": "hz.json"
    },
    "observables_x": {
      "const": "observables_x.json"
    }
  }
}
```

In the same schema, extend `properties.provenance.properties` to allow the two paper-backed BB72 provenance fields used by the replacement instance:

```json
"exact_distance": {
  "type": "object",
  "additionalProperties": false,
  "required": [
    "bound_type",
    "distance",
    "method",
    "rstim_issue",
    "verified_command"
  ],
  "properties": {
    "bound_type": {
      "const": "exact"
    },
    "distance": {
      "type": "integer",
      "minimum": 1
    },
    "method": {
      "type": "string",
      "minLength": 1
    },
    "rstim_issue": {
      "type": "string",
      "minLength": 1
    },
    "verified_command": {
      "type": "string",
      "minLength": 1
    }
  }
},
"paper_evidence": {
  "type": "array",
  "minItems": 1,
  "items": {
    "type": "string",
    "minLength": 1
  }
}
```

- [ ] **Step 4: Normalize the BB72 instance metadata**

Replace `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/instance.json` with this schema-valid payload:

```json
{
  "artifacts": {
    "hx": "hx.json",
    "hz": "hz.json",
    "observables_x": "observables_x.json"
  },
  "code_id": "bivariate-bicycle-code",
  "derived_properties": {
    "distance": 6,
    "kx": null,
    "kz": null,
    "mx": 36,
    "mz": 36,
    "n": 72
  },
  "family_id": "bivariate-bicycle-code",
  "id": "bivariate-bicycle-code-m6-n6",
  "instance_kind": "finite_css_instance",
  "matrix_format": "dense_binary_json",
  "parameters": {
    "distance": 6,
    "generator": {
      "hd": [
        [
          1,
          1
        ],
        [
          0,
          2
        ]
      ],
      "m": 6,
      "n": 6,
      "source_convention": "autoqec-bivariate-bicycle-fallback",
      "vc": [
        [
          1,
          0
        ],
        [
          0,
          1
        ]
      ]
    },
    "paper": {
      "A": "x^3 + y + y^2",
      "B": "y^3 + x + x^2",
      "l": 6,
      "m": 6,
      "paper_ref": "2308.07915"
    }
  },
  "provenance": {
    "exact_distance": {
      "bound_type": "exact",
      "distance": 6,
      "method": "qec-code code css-distance exact",
      "rstim_issue": "nzy1997/rstim#101",
      "verified_command": "cargo test -p qec-code --features distance-ilp-highs --test cli code_css_distance_exact_bb72_known_distance_with_ilp -q"
    },
    "generated_at": "2026-06-16T00:00:00Z",
    "generator": "autoqec-bivariate-bicycle-fallback",
    "generator_env": "python3",
    "generator_parameters": {
      "hd": [
        [
          1,
          1
        ],
        [
          0,
          2
        ]
      ],
      "m": 6,
      "n": 6,
      "vc": [
        [
          1,
          0
        ],
        [
          0,
          1
        ]
      ]
    },
    "generator_script": "scripts/generate_bivariate_bicycle_instance.py",
    "paper_evidence": [
      "zoo/evidence/2308.07915/bivariate-bicycle-code.parameter-claim.01.json",
      "zoo/evidence/2308.07915/bivariate-bicycle-code.distance-claim.01.json"
    ]
  },
  "title": "Bivariate Bicycle Code [[72,12,6]]"
}
```

- [ ] **Step 5: Add the explicit logical-X observables artifact**

Create `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/observables_x.json` with this exact content:

```json
{
  "format": "sparse_rows",
  "num_cols": 72,
  "rows": [
    [3, 6, 12, 15, 18, 24],
    [4, 7, 13, 16, 19, 25],
    [5, 8, 14, 17, 20, 26],
    [0, 9, 12, 15, 21, 27],
    [3, 6, 9, 15, 21, 30],
    [4, 7, 10, 16, 22, 31],
    [0, 1, 3, 4, 6, 7, 9, 10, 36, 37, 39, 40],
    [0, 2, 3, 5, 6, 8, 9, 11, 36, 38, 39, 41],
    [0, 1, 2, 5, 6, 7, 8, 9, 12, 14, 37, 39, 42, 44],
    [2, 4, 6, 8, 13, 15, 36, 37, 38, 39, 43, 45],
    [2, 4, 7, 8, 9, 10, 12, 16, 36, 37, 38, 39, 42, 46],
    [0, 1, 4, 5, 6, 7, 8, 11, 13, 17, 36, 38, 43, 47]
  ]
}
```

- [ ] **Step 6: Load and copy optional observables in `eval_candidates.py`**

Change the dataclass and artifact bundle contract to:

```python
@dataclass(frozen=True)
class ResolvedCandidate:
    spec: CandidateInput
    artifact_root: Path
    instance: dict[str, Any]
    hx: dict[str, Any]
    hz: dict[str, Any]
    source_kind: str
    observables_x: dict[str, Any] | None = None
```

Replace `_validate_artifact_names` with:

```python
def _validate_artifact_names(artifacts: dict[str, Any], path: Path) -> None:
    required = {"hx": "hx.json", "hz": "hz.json"}
    optional = {"observables_x": "observables_x.json"}
    allowed = {**required, **optional}
    for key, expected in required.items():
        if artifacts.get(key) != expected:
            raise SearchIntegrityError(f"unsupported artifact reference: {path}")
    for key, value in artifacts.items():
        if key not in allowed or value != allowed[key]:
            raise SearchIntegrityError(f"unsupported artifact reference: {path}")
```

Change `_load_artifact_bundle` to return observables:

```python
def _load_artifact_bundle(
    artifact_root: Path,
    *,
    require_distance: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    instance_path = artifact_root / "instance.json"
    instance = _load_json(instance_path, "instance artifact")
    artifacts = instance.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SearchIntegrityError(f"missing instance artifacts field: {instance_path}")
    _validate_artifact_names(artifacts, instance_path)

    hx = _load_json(artifact_root / "hx.json", "hx artifact")
    hz = _load_json(artifact_root / "hz.json", "hz artifact")
    observables_x = None
    if artifacts.get("observables_x") == "observables_x.json":
        observables_x = _load_json(artifact_root / "observables_x.json", "logical-X observables artifact")
    if require_distance:
        _require_positive_recorded_distance(instance, instance_path)
    return instance, hx, hz, observables_x
```

Update all callers to unpack four values and pass `observables_x=observables_x` into `ResolvedCandidate`.

In `copy_candidate_artifacts`, add:

```python
    if candidate.observables_x is not None:
        _write_json(artifacts_root / "observables_x.json", candidate.observables_x)
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
uv run pytest tests/test_search_eval_candidates.py::test_resolve_explicit_bb72_instance_loads_distance_and_observables tests/test_search_eval_candidates.py::test_copy_candidate_artifacts_preserves_bb72_observables tests/test_load.py::test_bb72_instance_is_paper_backed_and_schema_valid -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add zoo/schemas/code-instance.schema.json zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/instance.json zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/observables_x.json src/autoqec_search/eval_candidates.py tests/test_search_eval_candidates.py tests/test_load.py
git commit -m "feat: normalize bb72 instance artifacts"
```

---

### Task 3: Resolve Explicit-Instance Parameters And Nested Candidate Payloads

**Files:**
- Modify: `src/autoqec_search/eval_candidates.py`
- Test: `tests/test_search_eval_candidates.py`
- Test: `tests/test_search_run_loop.py`

**Interfaces:**
- Consumes: BB72 instance parameters from Task 2.
- Produces: explicit-instance candidates whose `CandidateInput.parameters` include nested `paper`, nested `generator`, and positive `distance`; directory candidate reload accepts the same JSON shape.

- [ ] **Step 1: Write failing tests for explicit resolution and directory reload**

Append to `tests/test_search_eval_candidates.py`:

```python
def test_explicit_instance_resolution_rejects_parameter_distance_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    instance_root = root / "zoo" / "codes" / "bivariate-bicycle-code" / "instances" / "bivariate-bicycle-code-m6-n6"
    instance_root.mkdir(parents=True)
    source = REPO_ROOT / "zoo" / "codes" / "bivariate-bicycle-code" / "instances" / "bivariate-bicycle-code-m6-n6"
    for name in ("instance.json", "hx.json", "hz.json", "observables_x.json"):
        shutil.copyfile(source / name, instance_root / name)
    instance = _load_json(instance_root / "instance.json")
    instance["parameters"]["distance"] = 5
    instance["derived_properties"]["distance"] = 6
    _write_json(instance_root / "instance.json", instance)

    with pytest.raises(SearchIntegrityError, match="instance parameter distance"):
        resolve_campaign_candidate_spec(
            root,
            {
                "candidate_id": "bivariate-bicycle-code-m6-n6",
                "code_family": "bivariate-bicycle-code",
                "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
                "provenance": {"kind": "paper-seed", "label": "BB72"},
            },
            campaign_id="bb72-qldpc-campaign",
        )


def test_resolve_directory_candidate_accepts_nested_bb72_parameters(tmp_path: Path) -> None:
    source = tmp_path / "source-candidate"
    artifacts = source / "artifacts"
    artifacts.mkdir(parents=True)
    zoo_instance_root = REPO_ROOT / "zoo" / "codes" / "bivariate-bicycle-code" / "instances" / "bivariate-bicycle-code-m6-n6"
    for name in ("instance.json", "hx.json", "hz.json", "observables_x.json"):
        shutil.copyfile(zoo_instance_root / name, artifacts / name)
    instance = _load_json(artifacts / "instance.json")
    _write_json(
        source / "candidate.json",
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "campaign_id": "bb72-qldpc-campaign",
            "run_id": "source-run",
            "code_family": "bivariate-bicycle-code",
            "parameters": instance["parameters"],
            "provenance": {"kind": "paper-seed", "label": "BB72"},
            "status": "evaluated",
        },
    )

    candidate = resolve_directory_candidate(
        REPO_ROOT,
        source,
        campaign_id="bb72-qldpc-campaign",
    )

    assert candidate.spec.parameters["distance"] == 6
    assert candidate.spec.parameters["paper"]["paper_ref"] == "2308.07915"
    assert candidate.artifact_root == artifacts
```

Append to `tests/test_search_run_loop.py`:

```python
def test_update_frontier_accepts_bb72_distance_from_resolved_candidate() -> None:
    config = RunConfig(
        campaign_id="bb72-qldpc-campaign",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        task_id="bb-css-memory-x-cdep-v1",
        primary_decoder_id="rbposd-bb72-osd10-v1",
        representative_p=0.003,
    )
    manifest = _completed_manifest("bivariate-bicycle-code-m6-n6", ler=0.01)
    manifest["campaign_id"] = "bb72-qldpc-campaign"
    manifest["task_id"] = "bb-css-memory-x-cdep-v1"
    manifest["decoder_id"] = "rbposd-bb72-osd10-v1"
    manifest["points"][0]["p"] = 0.003

    frontier, row = update_frontier(
        config,
        [],
        CandidateRecord(
            candidate_id="bivariate-bicycle-code-m6-n6",
            distance=6,
            completed_manifests=[manifest],
        ),
    )

    assert row.status == "keep"
    assert frontier[0].distance == 6
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run pytest tests/test_search_eval_candidates.py::test_explicit_instance_resolution_rejects_parameter_distance_mismatch tests/test_search_eval_candidates.py::test_resolve_directory_candidate_accepts_nested_bb72_parameters tests/test_search_run_loop.py::test_update_frontier_accepts_bb72_distance_from_resolved_candidate -q
```

Expected: the directory reload test FAILS because nested parameters are rejected.

- [ ] **Step 3: Add exact-distance parameter normalization**

In `src/autoqec_search/eval_candidates.py`, add:

```python
def _resolved_instance_parameters(instance: dict[str, Any], path: Path) -> dict[str, Any]:
    parameters = instance.get("parameters")
    if not isinstance(parameters, dict):
        raise SearchIntegrityError(f"instance parameters must be an object: {path}")
    resolved = dict(parameters)
    derived_properties = instance.get("derived_properties")
    distance = (
        derived_properties.get("distance")
        if isinstance(derived_properties, dict)
        else None
    )
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError(f"invalid recorded distance on instance: {path}")
    parameter_distance = resolved.get("distance")
    if parameter_distance is None:
        resolved["distance"] = distance
    elif parameter_distance != distance:
        raise SearchIntegrityError(
            f"instance parameter distance mismatch: parameters.distance {parameter_distance} != derived_properties.distance {distance}"
        )
    return resolved
```

In `_resolve_explicit_zoo_instance`, replace `parameters=dict(instance.get("parameters", {}))` with:

```python
            parameters=_resolved_instance_parameters(
                instance,
                artifact_root / "instance.json",
            ),
```

- [ ] **Step 4: Accept nested JSON parameter values for directory candidates**

Replace `_valid_parameter_value` with recursive JSON validation:

```python
def _valid_parameter_value(value: Any) -> bool:
    if value is None or isinstance(value, str) or isinstance(value, bool):
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_valid_parameter_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _valid_parameter_value(nested)
            for key, nested in value.items()
        )
    return False
```

Add `import math` at the top of the file.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_search_eval_candidates.py tests/test_search_run_loop.py::test_update_frontier_accepts_bb72_distance_from_resolved_candidate -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/autoqec_search/eval_candidates.py tests/test_search_eval_candidates.py tests/test_search_run_loop.py
git commit -m "feat: resolve explicit instance parameters"
```

---

### Task 4: Emit BB72 CSS Rsinter Observables, Seed, And Metadata

**Files:**
- Modify: `benchmarks/schemas/benchmark-task.schema.json`
- Modify: `benchmarks/schemas/result-manifest.schema.json`
- Modify: `src/autoqec_search/rsinter.py`
- Modify: `src/autoqec_search/eval_run.py`
- Test: `tests/test_search_rsinter.py`
- Test: `tests/test_search_eval_run.py`

**Interfaces:**
- Consumes: `ResolvedCandidate.observables_x` from Task 2.
- Produces: CSS rsinter TOML with `observables` and `seed`; completed manifests with `decoder_parameters` containing BP+OSD params and `run_metadata` containing observable provenance fields.

- [ ] **Step 1: Write failing rsinter spec and parser tests**

Append to `tests/test_search_rsinter.py`:

```python
def test_write_css_spec_toml_writes_observables_seed_and_bb72_params(tmp_path: Path) -> None:
    spec_path = tmp_path / "rsinter" / "spec.toml"
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "observable": "logical_x",
        "p_list": [0.003],
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "required",
        },
    }
    decoders = {
        "rbposd-bb72-osd10-v1": {
            "id": "rbposd-bb72-osd10-v1",
            "impl_key": "rbposd",
            "language": "rust",
            "parameters": {
                "bp_algorithm": "min_sum",
                "bp_iters": 50,
                "early_stop": True,
                "osd_method": "combination_sweep",
                "osd_order": 10,
            },
        }
    }

    write_css_spec_toml(
        spec_path,
        task=task,
        decoders=decoders,
        selected_decoder_ids=["rbposd-bb72-osd10-v1"],
        code_id="bivariate-bicycle-code-m6-n6",
        hx_path=Path("input/hx.css.json"),
        hz_path=Path("input/hz.css.json"),
        observables_path=Path("input/observables.css.json"),
        rounds=3,
        p_values=[0.003],
    )

    params = tomllib.loads(spec_path.read_text())["runner"][0]["params"]
    assert params["observables"] == "input/observables.css.json"
    assert params["seed"] == 12345
    assert params["bp_algorithm"] == "min_sum"
    assert params["osd_method"] == "combination_sweep"
    assert "distance" not in params
```

Append:

```python
def test_parse_results_jsonl_preserves_bb72_observable_metadata(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            _result_record(
                runner="rbposd-bb72-osd10-v1",
                params={
                    "input_type": "css",
                    "code_id": "bivariate-bicycle-code-m6-n6",
                    "hx": "input/hx.css.json",
                    "hz": "input/hz.css.json",
                    "observables": "input/observables.css.json",
                    "basis": "x",
                    "schedule": "greedy",
                    "rounds": 3,
                    "p": 0.003,
                    "seed": 12345,
                    "decoder_impl": "rbposd",
                    "logical_observable_source": "explicit",
                    "logical_observable_basis": "x",
                    "logical_failure_aggregation": "any_logical",
                    "logical_observable_count": 12,
                    "bp_algorithm": "min_sum",
                    "bp_iters": 50,
                    "early_stop": True,
                    "osd_method": "combination_sweep",
                    "osd_order": 10,
                },
                metrics={
                    "shots_used": 64,
                    "logical_errors": 0,
                    "logical_error_rate": 0.0,
                },
            ),
            sort_keys=True,
        )
        + "\n"
    )

    parsed = parse_results_jsonl(
        path,
        expected_decoder_id="rbposd-bb72-osd10-v1",
        expected_task_id="bb-css-memory-x-cdep-v1",
        expected_distance=None,
        expected_p_values=[0.003],
        expected_decoder_parameters={
            "bp_algorithm": "min_sum",
            "bp_iters": 50,
            "early_stop": True,
            "osd_method": "combination_sweep",
            "osd_order": 10,
        },
        expected_impl_key="rbposd",
    )

    assert parsed.decoder_parameters == {
        "bp_algorithm": "min_sum",
        "bp_iters": 50,
        "early_stop": True,
        "osd_method": "combination_sweep",
        "osd_order": 10,
    }
    assert parsed.run_metadata == {
        "decoder_impl": "rbposd",
        "logical_failure_aggregation": "any_logical",
        "logical_observable_basis": "x",
        "logical_observable_count": 12,
        "logical_observable_source": "explicit",
        "seed": 12345,
    }
```

- [ ] **Step 2: Write failing eval-run observable test**

Append to `tests/test_search_eval_run.py`:

```python
def test_css_eval_writes_required_bb72_observables_and_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = {
        "id": "bb-css-memory-x-cdep-v1",
        "input_type": "css",
        "observable": "logical_x",
        "p_list": [0.003],
        "rounds_policy": {"kind": "fixed", "rounds": 3},
        "collection": {"max_shots": 64, "max_errors": 32, "batch_size": 64},
        "css_memory": {
            "basis": "x",
            "schedule": "greedy",
            "seed": 12345,
            "observables": "required",
        },
    }
    candidate = _candidate(distance=6)
    object.__setattr__(
        candidate,
        "observables_x",
        {"format": "sparse_rows", "num_cols": 1, "rows": [[0]]},
    )
    workspace = _workspace()
    workspace.decoders["rbposd-bb72-osd10-v1"] = {
        "id": "rbposd-bb72-osd10-v1",
        "impl_key": "rbposd",
        "language": "rust",
        "parameters": {
            "bp_algorithm": "min_sum",
            "bp_iters": 50,
            "early_stop": True,
            "osd_method": "combination_sweep",
            "osd_order": 10,
        },
    }

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        spec_text = spec_path.read_text()
        assert 'observables = "input/observables.css.json"' in spec_text
        assert "seed = 12345" in spec_text
        assert json.loads((spec_path.parent / "input" / "observables.css.json").read_text()) == {
            "format": "sparse_rows",
            "num_cols": 1,
            "rows": [[0]],
        }
        result_path = out_dir / "rbposd-bb72-osd10-v1" / "test-run" / "results.jsonl"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            json.dumps(
                {
                    "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                    "runner": "rbposd-bb72-osd10-v1",
                    "language": "rust",
                    "status": "ok",
                    "params": {
                        "input_type": "css",
                        "code_id": "bivariate-bicycle-code-m6-n6",
                        "hx": "input/hx.css.json",
                        "hz": "input/hz.css.json",
                        "observables": "input/observables.css.json",
                        "basis": "x",
                        "schedule": "greedy",
                        "rounds": 3,
                        "p": 0.003,
                        "seed": 12345,
                        "decoder_impl": "rbposd",
                        "logical_observable_source": "explicit",
                        "logical_observable_basis": "x",
                        "logical_failure_aggregation": "any_logical",
                        "logical_observable_count": 1,
                        "bp_algorithm": "min_sum",
                        "bp_iters": 50,
                        "early_stop": True,
                        "osd_method": "combination_sweep",
                        "osd_order": 10,
                    },
                    "case_summary": {},
                    "metrics": {
                        "shots_used": 64,
                        "logical_errors": 0,
                        "logical_error_rate": 0.0,
                    },
                    "artifacts": {},
                    "error": None,
                },
                sort_keys=True,
            )
            + "\n"
        )

    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fake_run_rsinter)

    result = evaluate_resolved_candidate_into_run(
        run_root=tmp_path / "run",
        run_id="bb72-observables",
        campaign_id="bb72-qldpc-campaign",
        candidate=candidate,
        workspace=workspace,
        suite={"decoder_ids": ["rbposd-bb72-osd10-v1"]},
        task=task,
        selected_decoder_ids=["rbposd-bb72-osd10-v1"],
        selected_p_values=[0.003],
        created_at="2026-06-18T00:00:00Z",
        rsinter_executable="/bin/rsinter",
        rsinter_version="rsinter test",
        general_css=True,
    )

    manifest = result.completed_manifests[0]
    assert manifest["run_metadata"]["logical_observable_source"] == "explicit"
    assert manifest["decoder_parameters"]["osd_method"] == "combination_sweep"
```

- [ ] **Step 3: Run the failing tests**

Run:

```bash
uv run pytest tests/test_search_rsinter.py::test_write_css_spec_toml_writes_observables_seed_and_bb72_params tests/test_search_rsinter.py::test_parse_results_jsonl_preserves_bb72_observable_metadata tests/test_search_eval_run.py::test_css_eval_writes_required_bb72_observables_and_metadata -q
```

Expected: FAIL because `write_css_spec_toml` has no `observables_path`, `ParsedResults` has no `run_metadata`, and eval does not write observable inputs.

- [ ] **Step 4: Extend task and manifest schemas**

In `benchmarks/schemas/benchmark-task.schema.json`, extend `css_memory.properties`:

```json
"seed": { "type": "integer", "minimum": 0 },
"observables": { "enum": ["required", "optional"] }
```

In `benchmarks/schemas/result-manifest.schema.json`, add optional completed-manifest `run_metadata`:

```json
"run_metadata": {
  "type": "object",
  "additionalProperties": {
    "type": ["string", "number", "integer", "boolean", "null"]
  }
}
```

- [ ] **Step 5: Implement rsinter observable and metadata support**

In `src/autoqec_search/rsinter.py`, add:

```python
RESULT_METADATA_PARAM_KEYS = {
    "decoder_impl",
    "logical_failure_aggregation",
    "logical_observable_basis",
    "logical_observable_count",
    "logical_observable_source",
    "seed",
}
```

Add validator/writer:

```python
def write_css_observables_wrapper(path: str | Path, payload: dict[str, Any]) -> None:
    if payload.get("format") != "sparse_rows":
        raise SearchIntegrityError("CSS observables format must be sparse_rows")
    num_cols = payload.get("num_cols")
    rows = payload.get("rows")
    if type(num_cols) is not int or num_cols <= 0:
        raise SearchIntegrityError("CSS observables num_cols must be a positive integer")
    if not isinstance(rows, list) or not rows:
        raise SearchIntegrityError("CSS observables rows must be a nonempty list")
    normalized_rows: list[list[int]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            raise SearchIntegrityError(f"CSS observables row {row_index} must be a list")
        normalized_row: list[int] = []
        previous = -1
        for col in row:
            if type(col) is not int or col < 0 or col >= num_cols:
                raise SearchIntegrityError(f"CSS observables row {row_index} has invalid column")
            if col <= previous:
                raise SearchIntegrityError(f"CSS observables row {row_index} columns must be strictly increasing")
            previous = col
            normalized_row.append(col)
        normalized_rows.append(normalized_row)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {"format": "sparse_rows", "num_cols": num_cols, "rows": normalized_rows},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
```

Change `ParsedResults` to:

```python
@dataclass(frozen=True)
class ParsedResults:
    points: list[dict]
    decoder_parameters: dict[str, Any]
    run_metadata: dict[str, Any]
```

Inside `parse_results_jsonl`, build `row_run_metadata` from `RESULT_METADATA_PARAM_KEYS`, exclude those keys from decoder parameters, require metadata consistency across rows, and return it:

```python
        row_run_metadata = {
            key: params[key]
            for key in sorted(RESULT_METADATA_PARAM_KEYS)
            if key in params
        }
        row_decoder_parameters = canonical_decoder_parameters(
            {
                key: value
                for key, value in params.items()
                if key not in GENERIC_RESULT_PARAM_KEYS
                and key not in RESULT_METADATA_PARAM_KEYS
            },
            impl_key=expected_impl_key,
        )
```

Keep the existing decoder parameter equality check. Add a `run_metadata` variable with the same consistency behavior as `decoder_parameters`.

Change `build_completed_manifest` to accept `run_metadata: dict[str, Any] | None = None` and include:

```python
    manifest = {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "decoder_id": decoder_id,
        "decoder_parameters": canonical_decoder_parameters(
            dict(decoder_parameters or {})
        ),
        "status": "completed",
        "created_at": created_at,
        "tool_revisions": tool_revisions,
        "points": points,
    }
    if run_metadata:
        manifest["run_metadata"] = dict(sorted(run_metadata.items()))
    return manifest
```

Change `write_css_spec_toml` signature to include `observables_path: str | Path | None = None`. If present, emit:

```python
                f"observables = {_toml_string(Path(observables_path).as_posix())}",
```

After `batch_size`, if the CSS memory config has a seed, emit:

```python
        css_memory = task.get("css_memory")
        seed = css_memory.get("seed") if isinstance(css_memory, dict) else None
        if seed is not None:
            if type(seed) is not int or seed < 0:
                raise SearchIntegrityError(f"invalid CSS memory seed: {seed}")
            lines.append(f"seed = {seed}")
```

- [ ] **Step 6: Wire eval-run observable inputs**

In `src/autoqec_search/eval_run.py`, import `write_css_observables_wrapper`.

In the `general_css` branch, after writing `hx_input` and `hz_input`, add:

```python
        css_memory = task.get("css_memory")
        observables_policy = (
            css_memory.get("observables")
            if isinstance(css_memory, dict)
            else None
        )
        observables_input: Path | None = None
        if candidate.observables_x is not None:
            observables_input = input_dir / "observables.css.json"
            write_css_observables_wrapper(observables_input, candidate.observables_x)
        elif observables_policy == "required":
            raise SearchIntegrityError(
                f"task {task['id']} requires explicit CSS observables for {candidate_id}"
            )
```

Pass the optional path to `write_css_spec_toml`:

```python
            observables_path=(
                Path("input/observables.css.json")
                if observables_input is not None
                else None
            ),
```

When building the completed manifest, pass:

```python
            run_metadata=parsed.run_metadata,
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
uv run pytest tests/test_search_rsinter.py::test_write_css_spec_toml_writes_observables_seed_and_bb72_params tests/test_search_rsinter.py::test_parse_results_jsonl_preserves_bb72_observable_metadata tests/test_search_eval_run.py::test_css_eval_writes_required_bb72_observables_and_metadata tests/test_search_eval_run.py::test_css_eval_parses_no_distance_results_when_instance_has_recorded_distance -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add benchmarks/schemas/benchmark-task.schema.json benchmarks/schemas/result-manifest.schema.json src/autoqec_search/rsinter.py src/autoqec_search/eval_run.py tests/test_search_rsinter.py tests/test_search_eval_run.py
git commit -m "feat: emit css observables for bb72 rsinter"
```

---

### Task 5: Add Published-Reference Checker

**Files:**
- Create: `src/autoqec_search/reference_check.py`
- Modify: `src/autoqec_search/cli.py`
- Create: `benchmarks/fixtures/bb72-reference/expected.json`
- Test: `tests/test_search_reference_check.py`

**Interfaces:**
- Consumes: completed manifest points with `shots`, `errors`, `ler`, `ci_low`, and `ci_high`.
- Produces: `reference_check.json` with `status = "pass"` or `status = "fail"`, selected expected LER, observed CI, candidate/decoder/task identity, and fixture provenance.

- [ ] **Step 1: Add the reference fixture**

Create `benchmarks/fixtures/bb72-reference/expected.json`:

```json
{
  "candidate_id": "bivariate-bicycle-code-m6-n6",
  "decoder_id": "rbposd-bb72-osd10-v1",
  "distance": 6,
  "paper_id": "2308.07915",
  "points": [
    {
      "expected_ler": 0.004582883142537217,
      "p": 0.003
    },
    {
      "expected_ler": 0.5074729501581476,
      "p": 0.01
    }
  ],
  "reference_formula": {
    "c0": 11.09,
    "c1": 365.6,
    "c2": -16088,
    "d_circ": 6,
    "form": "p^(d_circ/2) * exp(c0 + c1*p + c2*p^2)"
  },
  "source": {
    "distance_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.distance-claim.01.json",
    "parameter_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.parameter-claim.01.json",
    "threshold_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.threshold-evidence.01.json"
  },
  "task_id": "bb-css-memory-x-cdep-v1"
}
```

- [ ] **Step 2: Write failing checker tests**

Create `tests/test_search_reference_check.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.reference_check import (
    expected_ler_from_table6,
    evaluate_reference_check,
    write_reference_check,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _manifest_root(tmp_path: Path, *, ci_low: float, ci_high: float, shots: int = 1000) -> Path:
    run_root = tmp_path / "run"
    manifest_path = (
        run_root
        / "candidates"
        / "bivariate-bicycle-code-m6-n6"
        / "evaluations"
        / "bb-css-memory-x-cdep-v1"
        / "rbposd-bb72-osd10-v1"
        / "manifest.json"
    )
    _write_json(
        manifest_path,
        {
            "campaign_id": "bb72-qldpc-campaign",
            "run_id": "reference-fixture",
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "task_id": "bb-css-memory-x-cdep-v1",
            "decoder_id": "rbposd-bb72-osd10-v1",
            "status": "completed",
            "created_at": "2026-06-18T00:00:00Z",
            "tool_revisions": {"autoqec_search": "0.1.0", "rsinter": "fake"},
            "points": [
                {
                    "p": 0.003,
                    "rounds": 3,
                    "shots": shots,
                    "errors": 5,
                    "ler": 0.005,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "seconds": 0.01,
                }
            ],
        },
    )
    return run_root


def _fixture(tmp_path: Path) -> Path:
    path = tmp_path / "expected.json"
    _write_json(
        path,
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "decoder_id": "rbposd-bb72-osd10-v1",
            "task_id": "bb-css-memory-x-cdep-v1",
            "paper_id": "2308.07915",
            "distance": 6,
            "reference_formula": {
                "d_circ": 6,
                "c0": 11.09,
                "c1": 365.6,
                "c2": -16088,
                "form": "p^(d_circ/2) * exp(c0 + c1*p + c2*p^2)",
            },
            "points": [{"p": 0.003, "expected_ler": 0.004582883142537217}],
            "source": {
                "parameter_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.parameter-claim.01.json",
                "distance_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.distance-claim.01.json",
                "threshold_evidence": "zoo/evidence/2308.07915/bivariate-bicycle-code.threshold-evidence.01.json",
            },
        },
    )
    return path


def test_expected_ler_from_table6_matches_bb72_fixture_values() -> None:
    assert expected_ler_from_table6(0.003, d_circ=6, c0=11.09, c1=365.6, c2=-16088) == pytest.approx(
        0.004582883142537217
    )
    assert expected_ler_from_table6(0.01, d_circ=6, c0=11.09, c1=365.6, c2=-16088) == pytest.approx(
        0.5074729501581476
    )


def test_reference_check_passes_when_expected_ler_is_inside_ci(tmp_path: Path) -> None:
    run_root = _manifest_root(tmp_path, ci_low=0.001, ci_high=0.01)

    result = evaluate_reference_check(run_root, _fixture(tmp_path))

    assert result["status"] == "pass"
    assert result["points"][0]["status"] == "pass"
    assert result["points"][0]["expected_ler"] == pytest.approx(0.004582883142537217)


def test_reference_check_fails_when_expected_ler_is_outside_ci(tmp_path: Path) -> None:
    run_root = _manifest_root(tmp_path, ci_low=0.01, ci_high=0.02)

    result = evaluate_reference_check(run_root, _fixture(tmp_path))

    assert result["status"] == "fail"
    assert result["points"][0]["status"] == "fail"


def test_reference_check_rejects_zero_shot_evidence(tmp_path: Path) -> None:
    run_root = _manifest_root(tmp_path, ci_low=0.0, ci_high=1.0, shots=0)

    with pytest.raises(SearchIntegrityError, match="positive shots"):
        evaluate_reference_check(run_root, _fixture(tmp_path))


def test_write_reference_check_persists_json(tmp_path: Path) -> None:
    run_root = _manifest_root(tmp_path, ci_low=0.001, ci_high=0.01)
    output = write_reference_check(run_root, _fixture(tmp_path), None)

    assert output == run_root / "reference_check.json"
    assert json.loads(output.read_text())["status"] == "pass"
```

- [ ] **Step 3: Run the failing tests**

Run:

```bash
uv run pytest tests/test_search_reference_check.py -q
```

Expected: FAIL because `autoqec_search.reference_check` does not exist.

- [ ] **Step 4: Implement `reference_check.py`**

Create `src/autoqec_search/reference_check.py` with:

```python
from __future__ import annotations

import json
from math import exp, isfinite
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must be an object: {path}")
    return payload


def _finite_probability(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SearchIntegrityError(f"{label} must be a probability")
    numeric = float(value)
    if not isfinite(numeric) or not 0 < numeric < 1:
        raise SearchIntegrityError(f"{label} must be a probability")
    return numeric


def _finite_rate(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SearchIntegrityError(f"{label} must be a rate")
    numeric = float(value)
    if not isfinite(numeric) or not 0 <= numeric <= 1:
        raise SearchIntegrityError(f"{label} must be a rate")
    return numeric


def expected_ler_from_table6(
    p: float,
    *,
    d_circ: int,
    c0: float,
    c1: float,
    c2: float,
) -> float:
    return p ** (d_circ / 2) * exp(c0 + c1 * p + c2 * p * p)


def _manifest_path(run_root: Path, fixture: dict[str, Any]) -> Path:
    return (
        run_root
        / "candidates"
        / str(fixture["candidate_id"])
        / "evaluations"
        / str(fixture["task_id"])
        / str(fixture["decoder_id"])
        / "manifest.json"
    )


def _completed_manifest(run_root: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    path = _manifest_path(run_root, fixture)
    manifest = _load_json(path, "reference manifest")
    for key in ("candidate_id", "task_id", "decoder_id"):
        if manifest.get(key) != fixture.get(key):
            raise SearchIntegrityError(f"reference manifest {key} mismatch: {path}")
    if manifest.get("status") != "completed":
        raise SearchIntegrityError(f"reference manifest is not completed: {path}")
    return manifest


def _point_by_p(manifest: dict[str, Any], p: float) -> dict[str, Any]:
    points = manifest.get("points")
    if not isinstance(points, list):
        raise SearchIntegrityError("reference manifest points must be a list")
    for point in points:
        if isinstance(point, dict) and point.get("p") == p:
            return point
    raise SearchIntegrityError(f"missing reference p point: {p:g}")


def _check_point(observed: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    p = _finite_probability(expected.get("p"), label="reference p")
    expected_ler = _finite_probability(expected.get("expected_ler"), label="expected_ler")
    shots = observed.get("shots")
    if type(shots) is not int or shots <= 0:
        raise SearchIntegrityError("reference check requires positive shots")
    ci_low = _finite_rate(observed.get("ci_low"), label="ci_low")
    ci_high = _finite_rate(observed.get("ci_high"), label="ci_high")
    if ci_low > ci_high:
        raise SearchIntegrityError("reference CI lower bound exceeds upper bound")
    ler = observed.get("ler")
    if not isinstance(ler, (int, float)) or isinstance(ler, bool) or not isfinite(float(ler)):
        raise SearchIntegrityError("reference observed ler must be finite")
    status = "pass" if ci_low <= expected_ler <= ci_high else "fail"
    return {
        "p": p,
        "status": status,
        "expected_ler": expected_ler,
        "observed_ler": float(ler),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "shots": shots,
        "errors": int(observed.get("errors", 0)),
    }


def evaluate_reference_check(run_root: Path, fixture_path: Path) -> dict[str, Any]:
    run_root = run_root.resolve()
    fixture_path = fixture_path.resolve()
    fixture = _load_json(fixture_path, "reference fixture")
    manifest = _completed_manifest(run_root, fixture)
    points = []
    for expected in fixture.get("points", []):
        if not isinstance(expected, dict):
            raise SearchIntegrityError("reference fixture point must be an object")
        p = _finite_probability(expected.get("p"), label="reference p")
        points.append(_check_point(_point_by_p(manifest, p), expected))
    if not points:
        raise SearchIntegrityError("reference fixture points must be nonempty")
    status = "pass" if all(point["status"] == "pass" for point in points) else "fail"
    return {
        "status": status,
        "fixture_path": str(fixture_path),
        "paper_id": fixture.get("paper_id"),
        "candidate_id": fixture.get("candidate_id"),
        "task_id": fixture.get("task_id"),
        "decoder_id": fixture.get("decoder_id"),
        "distance": fixture.get("distance"),
        "source": fixture.get("source", {}),
        "points": points,
    }


def write_reference_check(
    run_root: Path,
    fixture_path: Path,
    output_path: Path | None,
) -> Path:
    payload = evaluate_reference_check(run_root, fixture_path)
    path = output_path or run_root / "reference_check.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path
```

- [ ] **Step 5: Add CLI subcommand**

In `src/autoqec_search/cli.py`, import:

```python
from autoqec_search.reference_check import write_reference_check
```

Add parser:

```python
    reference_parser = subparsers.add_parser(
        "reference-check", help="Validate a run against a published reference fixture"
    )
    reference_parser.add_argument("--root", default=".")
    reference_parser.add_argument("--run", required=True)
    reference_parser.add_argument("--fixture", required=True)
    reference_parser.add_argument("--out", default=None)
```

Add command branch:

```python
        if args.command == "reference-check":
            root = Path(args.root)
            run_root = Path(args.run)
            if not run_root.is_absolute():
                run_root = root / run_root
            fixture_path = Path(args.fixture)
            if not fixture_path.is_absolute():
                fixture_path = root / fixture_path
            output_path = Path(args.out) if args.out is not None else None
            written = write_reference_check(run_root, fixture_path, output_path)
            payload = json.loads(written.read_text())
            print(f"reference check {payload['status']} written to {written}")
            return 0 if payload["status"] == "pass" else 1
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/test_search_reference_check.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/autoqec_search/reference_check.py src/autoqec_search/cli.py benchmarks/fixtures/bb72-reference/expected.json tests/test_search_reference_check.py
git commit -m "feat: add bb72 published reference checker"
```

---

### Task 6: Add BB72 Campaign, Suite, Promotion Gate, And Report Fields

**Files:**
- Create: `benchmarks/decoders/rbposd-bb72-osd10-v1.json`
- Modify: `benchmarks/tasks/bb-css-memory-x-cdep-v1.json`
- Create: `benchmarks/suites/bb72-qldpc-campaign-v1.json`
- Create: `campaigns/examples/bb72-qldpc-campaign/campaign.json`
- Create: `campaigns/examples/bb72-qldpc-campaign/search_space.json`
- Create: `campaigns/examples/bb72-qldpc-campaign/promote_rules.json`
- Modify: `benchmarks/schemas/promote-rules.schema.json`
- Modify: `src/autoqec_search/promote.py`
- Modify: `src/autoqec_search/report.py`
- Test: `tests/test_search_promote.py`
- Test: `tests/test_search_report.py`
- Test: `tests/test_load.py`

**Interfaces:**
- Consumes: reference checker output `run_root/reference_check.json` from Task 5.
- Produces: a loadable BB72 campaign, report model with reference-check status, and promotion enforcement for required reference checks.

- [ ] **Step 1: Write failing workspace/campaign test**

Append to `tests/test_load.py`:

```python
def test_bb72_qldpc_campaign_loads() -> None:
    from autoqec_search.load import load_search_workspace

    workspace = load_search_workspace(Path(__file__).resolve().parents[1])

    campaign = workspace.campaigns["bb72-qldpc-campaign"]
    search_space = workspace.search_spaces["bb72-qldpc-campaign"]
    suite = workspace.suites[campaign["default_suite_id"]]
    task = workspace.tasks["bb-css-memory-x-cdep-v1"]
    decoder = workspace.decoders["rbposd-bb72-osd10-v1"]

    assert campaign["family_id"] == "bivariate-bicycle-code"
    assert search_space["candidate_specs"][0]["instance_path"].endswith("bivariate-bicycle-code-m6-n6")
    assert suite["decoder_ids"][0] == "rbposd-bb72-osd10-v1"
    assert task["css_memory"]["observables"] == "required"
    assert task["css_memory"]["seed"] == 12345
    assert decoder["parameters"]["osd_method"] == "combination_sweep"
```

- [ ] **Step 2: Write failing promotion/reference gate test**

In `tests/test_search_promote.py`, add a helper mutation inside `_make_finished_run` callers by copying `reference_check.json`. Append:

```python
def test_evaluate_promotions_requires_passing_reference_check_when_configured(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    _write_json(
        run_root / "reference_check.json",
        {
            "status": "fail",
            "candidate_id": "rotated-surface-d3-example",
            "task_id": "rotated-memory-z-cdep-v1",
            "decoder_id": "rmatching-default-v1",
            "points": [],
        },
    )

    with pytest.raises(SearchIntegrityError, match="reference check failed"):
        evaluate_promotions(run_root, {"require_reference_check": True, "require_distance_verified": True})

    reference = _load_json(run_root / "reference_check.json")
    reference["status"] = "pass"
    _write_json(run_root / "reference_check.json", reference)

    decisions = evaluate_promotions(run_root, {"require_reference_check": True, "require_distance_verified": True})
    assert decisions[0].status == "promote"
```

- [ ] **Step 3: Write failing report reference-check test**

Append to `tests/test_search_report.py`:

```python
def test_report_model_includes_reference_check_status(tmp_path: Path) -> None:
    from tests.test_search_promote import _make_finished_run, _write_json
    from autoqec_search.report import build_report_model

    work_root, run_root = _make_finished_run(tmp_path)
    _write_json(
        run_root / "reference_check.json",
        {
            "status": "pass",
            "candidate_id": "rotated-surface-d3-example",
            "task_id": "rotated-memory-z-cdep-v1",
            "decoder_id": "rmatching-default-v1",
            "points": [{"p": 0.01, "status": "pass"}],
        },
    )

    model = build_report_model(work_root, run_root)

    assert model["reference_check"]["status"] == "pass"
    assert model["reference_check"]["points"][0]["status"] == "pass"
```

- [ ] **Step 4: Run the failing tests**

Run:

```bash
uv run pytest tests/test_load.py::test_bb72_qldpc_campaign_loads tests/test_search_promote.py::test_evaluate_promotions_requires_passing_reference_check_when_configured tests/test_search_report.py::test_report_model_includes_reference_check_status -q
```

Expected: FAIL because campaign files and reference gate/report fields do not exist.

- [ ] **Step 5: Add BB72 decoder, task, suite, and campaign files**

Create `benchmarks/decoders/rbposd-bb72-osd10-v1.json`:

```json
{
  "backend": "rsinter",
  "execution_status": "real",
  "id": "rbposd-bb72-osd10-v1",
  "impl_key": "rbposd",
  "language": "rust",
  "parameters": {
    "bp_algorithm": "min_sum",
    "bp_iters": 50,
    "early_stop": true,
    "osd_method": "combination_sweep",
    "osd_order": 10
  },
  "title": "BB72 BP+OSD OSD10 via rsinter"
}
```

Replace `benchmarks/tasks/bb-css-memory-x-cdep-v1.json` with:

```json
{
  "collection": {
    "batch_size": 64,
    "decoder_overrides": {
      "predict-zero-v1": {
        "max_errors": 64,
        "max_shots": 64
      },
      "rbposd-bb72-osd10-v1": {
        "max_errors": 32,
        "max_shots": 64
      }
    },
    "max_errors": 32,
    "max_shots": 64
  },
  "css_memory": {
    "basis": "x",
    "observables": "required",
    "schedule": "greedy",
    "seed": 12345
  },
  "execution_status": "real",
  "id": "bb-css-memory-x-cdep-v1",
  "input_type": "css",
  "noise_model": "circuit_depolarizing",
  "observable": "logical_x",
  "p_list": [
    0.003,
    0.01
  ],
  "result_metrics": [
    "logical_error_rate"
  ],
  "rounds_policy": {
    "kind": "fixed",
    "rounds": 3
  },
  "title": "BB72 CSS Memory X under circuit depolarizing noise"
}
```

Create `benchmarks/suites/bb72-qldpc-campaign-v1.json`:

```json
{
  "decoder_ids": [
    "rbposd-bb72-osd10-v1",
    "predict-zero-v1"
  ],
  "id": "bb72-qldpc-campaign-v1",
  "shared_settings": {
    "reference_fixture": "benchmarks/fixtures/bb72-reference/expected.json",
    "runner": "rsinter"
  },
  "task_ids": [
    "bb-css-memory-x-cdep-v1"
  ],
  "title": "BB72 qLDPC Campaign v1"
}
```

Create `campaigns/examples/bb72-qldpc-campaign/campaign.json`:

```json
{
  "budget": {
    "max_candidates": 1,
    "wall_clock_seconds": 900
  },
  "default_suite_id": "bb72-qldpc-campaign-v1",
  "family_id": "bivariate-bicycle-code",
  "id": "bb72-qldpc-campaign",
  "objective": "Run the paper-backed BB72 bivariate-bicycle qLDPC seed through the M2 search pipeline.",
  "random_seed_policy": {
    "mode": "fixed",
    "seed": 7
  },
  "stop_conditions": {
    "max_candidates": 1,
    "max_wall_clock_seconds": 900
  },
  "title": "BB72 qLDPC Campaign"
}
```

Create `campaigns/examples/bb72-qldpc-campaign/search_space.json`:

```json
{
  "campaign_id": "bb72-qldpc-campaign",
  "candidate_specs": [
    {
      "candidate_id": "bivariate-bicycle-code-m6-n6",
      "code_family": "bivariate-bicycle-code",
      "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
      "provenance": {
        "kind": "paper-seed",
        "label": "Bravyi et al. BB [[72,12,6]]"
      }
    }
  ],
  "mode": "explicit_list",
  "strategy": {
    "name": "grid",
    "params": {}
  }
}
```

Create `campaigns/examples/bb72-qldpc-campaign/promote_rules.json`:

```json
{
  "max_ler_at_p": {
    "ler": 1.0,
    "p": 0.003
  },
  "min_distance": 6,
  "require_distance_verified": true,
  "require_reference_check": true
}
```

- [ ] **Step 6: Add reference-check promotion rule**

In `benchmarks/schemas/promote-rules.schema.json`, add:

```json
"require_reference_check": {
  "type": "boolean",
  "default": false
}
```

In `src/autoqec_search/promote.py`, update `_normalize_rules`:

```python
    normalized.setdefault("require_reference_check", False)
```

Add:

```python
def _require_reference_check(run_root: Path, rules: dict[str, Any]) -> None:
    if not rules.get("require_reference_check", False):
        return
    path = run_root / "reference_check.json"
    payload = _load_json(path, "reference check")
    if payload.get("status") != "pass":
        raise SearchIntegrityError(f"reference check failed for {run_root}")
```

Call `_require_reference_check(run_root, rules)` once in `evaluate_promotions` after run identity validation and before iterating frontier items.

- [ ] **Step 7: Include reference check in report model and HTML**

In `src/autoqec_search/report.py`, add:

```python
def _optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return _load_json(path)
```

In `build_report_model`, include:

```python
        "reference_check": _optional_json(run_root / "reference_check.json"),
```

In `render_report_html`, add a compact section whose text contains `Reference check` and the escaped status value. Keep it near the run summary so failed reference status is visible without scrolling to raw JSON.

- [ ] **Step 8: Run focused tests**

Run:

```bash
uv run pytest tests/test_load.py::test_bb72_qldpc_campaign_loads tests/test_search_promote.py::test_evaluate_promotions_requires_passing_reference_check_when_configured tests/test_search_report.py::test_report_model_includes_reference_check_status -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add benchmarks/decoders/rbposd-bb72-osd10-v1.json benchmarks/tasks/bb-css-memory-x-cdep-v1.json benchmarks/suites/bb72-qldpc-campaign-v1.json campaigns/examples/bb72-qldpc-campaign/campaign.json campaigns/examples/bb72-qldpc-campaign/search_space.json campaigns/examples/bb72-qldpc-campaign/promote_rules.json benchmarks/schemas/promote-rules.schema.json src/autoqec_search/promote.py src/autoqec_search/report.py tests/test_search_promote.py tests/test_search_report.py tests/test_load.py
git commit -m "feat: add bb72 qldpc campaign contract"
```

---

### Task 7: Run BB72 Through A Fake-Light End-To-End Pipeline

**Files:**
- Modify: `tests/test_search_e2e.py`
- Modify: `src/autoqec_search/promote.py`
- Test: `tests/test_search_e2e.py`

**Interfaces:**
- Consumes: BB72 campaign from Task 6.
- Produces: a deterministic fake-light run that writes completed manifests, leaderboard, frontier, report, reference check, promotion summary, and promoted Zoo instance including optional observables.

- [ ] **Step 1: Write fake-light E2E test**

Append to `tests/test_search_e2e.py`:

```python
def test_bb72_campaign_fake_light_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil
    from autoqec_search.cli import main

    root = tmp_path / "work"
    for name in ("benchmarks", "campaigns", "zoo"):
        shutil.copytree(Path(__file__).resolve().parents[1] / name, root / name)
    (root / "results" / "search").mkdir(parents=True)

    def fake_require_rsinter() -> tuple[str, str]:
        return "/bin/rsinter", "rsinter fake bb72"

    def fake_run_rsinter(
        spec_path: Path,
        out_dir: Path,
        *,
        executable: str,
        timeout_seconds: int = 3600,
        requires_general_css_support: bool = False,
    ) -> None:
        spec_text = spec_path.read_text()
        assert 'observables = "input/observables.css.json"' in spec_text
        assert "seed = 12345" in spec_text
        for runner, errors in [
            ("rbposd-bb72-osd10-v1", 0),
            ("predict-zero-v1", 48),
        ]:
            result_path = out_dir / runner / "test-run" / "results.jsonl"
            result_path.parent.mkdir(parents=True)
            rows = []
            for p in [0.003, 0.01]:
                rows.append(
                    {
                        "benchmark": "autoqec-bb-css-memory-x-cdep-v1",
                        "runner": runner,
                        "language": "rust",
                        "status": "ok",
                        "params": {
                            "input_type": "css",
                            "code_id": "bivariate-bicycle-code-m6-n6",
                            "hx": "input/hx.css.json",
                            "hz": "input/hz.css.json",
                            "observables": "input/observables.css.json",
                            "basis": "x",
                            "schedule": "greedy",
                            "rounds": 3,
                            "p": p,
                            "seed": 12345,
                            "decoder_impl": "rbposd" if runner.startswith("rbposd") else "predict-zero",
                            "logical_observable_source": "explicit",
                            "logical_observable_basis": "x",
                            "logical_failure_aggregation": "any_logical",
                            "logical_observable_count": 12,
                            **(
                                {
                                    "bp_algorithm": "min_sum",
                                    "bp_iters": 50,
                                    "early_stop": True,
                                    "osd_method": "combination_sweep",
                                    "osd_order": 10,
                                }
                                if runner.startswith("rbposd")
                                else {}
                            ),
                        },
                        "case_summary": {},
                        "metrics": {
                            "shots_used": 64,
                            "logical_errors": (
                                0
                                if runner.startswith("rbposd") and p == 0.003
                                else 32
                                if runner.startswith("rbposd")
                                else errors
                            ),
                            "logical_error_rate": (
                                0
                                if runner.startswith("rbposd") and p == 0.003
                                else 32 / 64
                                if runner.startswith("rbposd")
                                else errors / 64
                            ),
                        },
                        "artifacts": {},
                        "error": None,
                    }
                )
            result_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")

    monkeypatch.setattr("autoqec_search.run_loop.require_rsinter", fake_require_rsinter)
    monkeypatch.setattr("autoqec_search.eval_run.run_rsinter", fake_run_rsinter)

    assert main(
        [
            "run",
            "--root",
            str(root),
            "--campaign",
            "bb72-qldpc-campaign",
            "--run-id",
            "fake-bb72",
            "--allow-dirty-root",
        ]
    ) == 0
    run_root = root / "results" / "search" / "bb72-qldpc-campaign" / "fake-bb72"
    assert (run_root / "leaderboard.csv").is_file()
    assert json.loads((run_root / "frontier.json").read_text())["items"][0]["distance"] == 6

    assert main(
        [
            "reference-check",
            "--root",
            str(root),
            "--run",
            str(run_root),
            "--fixture",
            "benchmarks/fixtures/bb72-reference/expected.json",
        ]
    ) == 0
    assert json.loads((run_root / "reference_check.json").read_text())["status"] == "pass"

    assert main(["report", "--root", str(root), "--run", str(run_root)]) == 0
    assert "Reference check" in (run_root / "report.html").read_text()

    assert main(["promote", "--root", str(root), "--run", str(run_root), "--force"]) == 0
    target = root / "zoo" / "codes" / "bivariate-bicycle-code" / "instances" / "bivariate-bicycle-code-m6-n6"
    assert (target / "observables_x.json").is_file()
    assert "bivariate-bicycle-code-m6-n6" in (root / "zoo" / "views" / "browse.md").read_text()
```

- [ ] **Step 2: Run the failing E2E test**

Run:

```bash
uv run pytest tests/test_search_e2e.py::test_bb72_campaign_fake_light_e2e -q
```

Expected: FAIL until optional observables are fully promoted and the fake run can satisfy reference-check/report requirements.

- [ ] **Step 3: Promote optional observables**

Update `src/autoqec_search/promote.py`:

Extend `PromotionDecision` with:

```python
    observables_x_payload: dict[str, Any] | None
```

Return optional observables from `_require_artifacts`:

```python
    observables_x = None
    artifact_ref = instance.get("artifacts")
    if isinstance(artifact_ref, dict) and artifact_ref.get("observables_x") == "observables_x.json":
        observables_x = _load_json(artifact_root / "observables_x.json", "observables_x artifact")
```

Write optional observables in `_install_instance`:

```python
        if decision.observables_x_payload is not None:
            _write_json(staged / "observables_x.json", decision.observables_x_payload)
```

Include the optional observables in `_target_matches_promotion_payload` equality checks so repeated promotion is idempotent.

- [ ] **Step 4: Run fake-light E2E and promotion tests**

Run:

```bash
uv run pytest tests/test_search_e2e.py::test_bb72_campaign_fake_light_e2e tests/test_search_promote.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_search_e2e.py src/autoqec_search/promote.py
git commit -m "test: cover bb72 fake-light campaign flow"
```

---

### Task 8: Run Real BB72 Artifacts, Reference Check, Report, Promotion, And Verification

**Files:**
- Create or refresh: `results/search/bb72-qldpc-campaign/<run-id>/` run artifact tree
- Modify: `zoo/views/instance-index.json`
- Modify: `zoo/views/browse.md`
- Modify: `zoo/views/site/index.html`
- Modify: `zoo/views/site/assets/app.js` only if Zoo build output changes it
- Modify: `zoo/views/site/assets/styles.css` only if Zoo build output changes it
- Modify: `zoo/codes/bivariate-bicycle-code/card.md`
- Test: repository-wide fast tests

**Interfaces:**
- Consumes: all previous tasks.
- Produces: committed issue #18 run artifacts and regenerated Zoo outputs.

- [ ] **Step 1: Confirm the rsinter binary**

Run:

```bash
/Users/nzy/rcode/rstim/target/debug/rsinter --version
```

Expected: prints the rstim PR #107-era `rsinter` version. If it fails, build it from `/Users/nzy/rcode/rstim` before running AutoQEC:

```bash
cd /Users/nzy/rcode/rstim
cargo build -p rsinter
```

- [ ] **Step 2: Put the current rsinter binary on PATH for this shell**

Run:

```bash
export PATH="/Users/nzy/rcode/rstim/target/debug:$PATH"
rsinter --version
```

Expected: the first `rsinter` on PATH is `/Users/nzy/rcode/rstim/target/debug/rsinter`, not `/Users/nzy/.cargo/bin/rsinter`.

- [ ] **Step 3: Run the BB72 campaign**

Run:

```bash
uv run autoqec-search run \
  --root . \
  --campaign bb72-qldpc-campaign \
  --run-id issue18-bb72-qldpc \
  --allow-dirty-root
```

Expected:

- `results/search/bb72-qldpc-campaign/issue18-bb72-qldpc/run_spec.json` exists.
- `frontier.json` has one item for `bivariate-bicycle-code-m6-n6` at distance `6`.
- `candidates/bivariate-bicycle-code-m6-n6/evaluations/bb-css-memory-x-cdep-v1/rbposd-bb72-osd10-v1/manifest.json` is completed with positive shots.
- `candidate.json`, `distance.json`, `structure.json`, `leaderboard.csv`, `summary.md`, `run-summary.html`, and `experiment-log.tsv` exist.

- [ ] **Step 4: Run the published-reference check**

Run:

```bash
uv run autoqec-search reference-check \
  --root . \
  --run results/search/bb72-qldpc-campaign/issue18-bb72-qldpc \
  --fixture benchmarks/fixtures/bb72-reference/expected.json
```

Expected: exit code `0` and `reference_check.json` with `status = "pass"`.

If the reference check fails with a statistically honest miss, keep the raw run artifacts and inspect `reference_check.json`; do not change the checker to force a pass.

- [ ] **Step 5: Write the HTML report**

Run:

```bash
uv run autoqec-search report \
  --root . \
  --run results/search/bb72-qldpc-campaign/issue18-bb72-qldpc
```

Expected:

- `results/search/bb72-qldpc-campaign/issue18-bb72-qldpc/report.html` exists.
- The report includes BB72 candidate identity, exact distance `6`, decoder parameters, observable metadata, LER plot, and reference-check status.

- [ ] **Step 6: Promote accepted BB72 instance**

Run:

```bash
uv run autoqec-search promote \
  --root . \
  --run results/search/bb72-qldpc-campaign/issue18-bb72-qldpc \
  --force
```

Expected:

- `promotion_summary.json` has `status = "completed"`.
- The promoted item is `bivariate-bicycle-code-m6-n6`.
- `zoo/views/instance-index.json` contains `bivariate-bicycle-code-m6-n6`.
- `zoo/views/browse.md` includes the promoted BB72 instance.
- `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6/observables_x.json` remains present.

- [ ] **Step 7: Run fast verification**

Run:

```bash
uv run pytest tests/test_search_eval_candidates.py tests/test_search_rsinter.py tests/test_search_eval_run.py tests/test_search_reference_check.py tests/test_search_promote.py tests/test_search_report.py tests/test_search_e2e.py tests/test_load.py -q
```

Expected: PASS.

Run:

```bash
uv run pytest -q
```

Expected: PASS for all non-slow tests.

- [ ] **Step 8: Run workspace validation**

Run:

```bash
uv run autoqec-search validate --root .
uv run autoqec-zoo validate --root zoo
```

Expected: both commands exit `0`.

- [ ] **Step 9: Run focused heavy exact-distance verification when refreshing evidence**

Run only when the issue #18 branch needs a fresh local exact-distance evidence note:

```bash
cd /Users/nzy/rcode/rstim
cargo test -p qec-code --features distance-ilp-highs --test cli \
  code_css_distance_exact_bb72_known_distance_with_ilp -q
```

Expected: PASS. Local probe on 2026-06-18 took about 149 seconds.

- [ ] **Step 10: Commit final issue #18 artifacts**

```bash
git add results/search/bb72-qldpc-campaign/issue18-bb72-qldpc zoo/views zoo/codes/bivariate-bicycle-code/card.md zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6
git status --short
git commit -m "feat: complete bb72 qldpc campaign"
```

---

## Self-Review Notes

- Spec coverage: Tasks 2, 3, and 4 cover BB72 instance provenance, explicit distance propagation, observables, rsinter spec, and result metadata. Task 5 covers the published-reference fixture/checker. Tasks 6 and 7 cover campaign/suite/promotion/report integration and negative gates. Task 8 covers real artifacts, Zoo output, and verification.
- Dependency order: Task 1 can run first and independently. Tasks 2 and 3 are prerequisites for Task 4. Task 5 is independent after manifests exist as fixtures. Task 6 depends on Tasks 1, 4, and 5. Task 7 depends on Tasks 2 through 6. Task 8 is last.
- Negative controls: noncommuting candidates remain covered by existing eval tests; this plan adds nested-parameter, distance-mismatch, zero-shot reference, failed-reference promotion, and fake-light end-to-end controls. If implementation reveals a missing noncommuting BB-like fixture, add it beside `tests/test_search_eval_run.py` using the existing `candidate CSS checks do not commute` assertion.

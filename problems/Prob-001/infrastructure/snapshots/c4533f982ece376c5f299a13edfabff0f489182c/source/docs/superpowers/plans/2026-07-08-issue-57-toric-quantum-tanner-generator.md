# Issue 57 Toric Quantum Tanner Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate toric quantum Tanner spec files and a compatible distance-ladder manifest from a validated sweep config.

**Architecture:** Extend `autoqec_search.quantum_tanner_generator` from a validator into a planner/writer. The planner builds deterministic toric spec JSON and manifest entries in memory, validates output paths and id uniqueness before writes, and the writer atomically performs the planned filesystem changes only after validation succeeds.

**Tech Stack:** Python 3.14, stdlib `dataclasses`, `json`, `pathlib`, existing `pytest` and CLI subprocess test style.

## Global Constraints

- Reuse `src/autoqec_search/quantum_tanner_generator.py` for generation.
- Reuse candidate ids `quantum-tanner-toric-d<distance>`.
- Reuse qec-code specs `quantum_tanner:toric_d<distance>`.
- Toric spec JSON must match `src/bin/autoqec-quantum-tanner-toric-spec.rs`: construction mode `lr_cayley_no_cover_v1`, base group `Z_d x Z_d`, local `[1, 1]` parity checks, generator indices `[d, d * (d - 1)]` and `[1, d - 1]`.
- Fixture ids must be hyphenated: `quantum-tanner-toric-d<distance>`.
- Manifest entries must include `instance_id`, `code_id`, `qec_code_spec`, `quantum_tanner_spec`, `n`, optional `k`, `expected_distance`, and `expected_bound_type`.
- For toric quantum Tanner entries, use `n = distance * distance`, `k = 2`, and `expected_distance = distance`.
- `quantum_tanner_spec` manifest paths must be relative to the manifest parent when possible.
- Dry-run must not write files.
- Reject repository-escaping paths and candidate-id collisions before writing any partial manifest.
- Do not call `qec-code` or create `hx.json` or `hz.json`.
- Required final verification is `PYTHONPATH=src python3 -m pytest`.

---

## File Structure

- Modify `src/autoqec_search/quantum_tanner_generator.py`: add manifest path normalization, generation dataclasses, toric spec builder, dry-run planner, path validation, write runner, and summary rendering.
- Modify `src/autoqec_search/cli.py`: add `generate-quantum-tanner-sweep --config --root --dry-run`.
- Modify `tests/fixtures/quantum_tanner_sweep/good.json`: include `distance_ladder_manifest_path` so tests cover the manifest contract explicitly.
- Modify `tests/test_search_quantum_tanner_generator.py`: add red tests for dry-run, write-run, unsafe output rejection, collision rejection, and CLI behavior.

### Task 1: Red Tests For Generator Behavior

**Files:**
- Modify: `tests/fixtures/quantum_tanner_sweep/good.json`
- Modify: `tests/test_search_quantum_tanner_generator.py`

**Interfaces:**
- Consumes: existing `load_quantum_tanner_sweep_config`.
- Produces test expectations for `plan_quantum_tanner_sweep_generation`, `generate_quantum_tanner_sweep`, and CLI command `generate-quantum-tanner-sweep`.

- [ ] **Step 1: Add explicit manifest path to the fixture**

Patch `tests/fixtures/quantum_tanner_sweep/good.json` by adding:

```json
"distance_ladder_manifest_path": "benchmarks/distance_ladders/generated-quantum-tanner.json"
```

- [ ] **Step 2: Add failing dry-run and write-run tests**

Add imports:

```python
from autoqec_search.quantum_tanner_generator import (
    generate_quantum_tanner_sweep,
    load_quantum_tanner_sweep_config,
    normalize_quantum_tanner_sweep_config,
    plan_quantum_tanner_sweep_generation,
    render_quantum_tanner_generation_summary,
    render_quantum_tanner_sweep_summary,
)
```

Add a helper that rewrites output paths into a temporary repo-relative tree:

```python
def _temp_generation_payload(tmp_path: Path, **updates: object) -> dict[str, object]:
    root_name = tmp_path.name
    payload = _payload(
        output_root=f"{root_name}/generated",
        spec_root=f"{root_name}/generated/quantum_tanner_specs",
        instance_root=f"{root_name}/instances",
        catalog_path=f"{root_name}/generated_fixture_catalog.json",
        search_space_path=f"{root_name}/generated_search_space.json",
        distance_ladder_manifest_path=f"{root_name}/generated-ladder.json",
    )
    payload.update(updates)
    return payload
```

Add assertions:

```python
def test_generation_dry_run_plans_specs_and_manifest(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    plan = plan_quantum_tanner_sweep_generation(tmp_path.parent, config)

    assert [entry["instance_id"] for entry in plan.manifest["entries"]] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]
    assert [path.name for path in plan.spec_paths] == ["toric-d4.json", "toric-d6.json"]
    assert plan.manifest["entries"][0]["quantum_tanner_spec"] == (
        f"{tmp_path.name}/generated/quantum_tanner_specs/toric-d4.json"
    )
    assert not plan.manifest_path.exists()
    assert "would write 2 quantum Tanner specs" in render_quantum_tanner_generation_summary(plan, dry_run=True)
```

```python
def test_generation_write_run_writes_specs_and_manifest(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    plan = generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)

    assert plan.manifest_path.is_file()
    manifest = json.loads(plan.manifest_path.read_text())
    assert len(manifest["entries"]) == 2
    assert [entry["quantum_tanner_spec"] for entry in manifest["entries"]] == [
        f"{tmp_path.name}/generated/quantum_tanner_specs/toric-d4.json",
        f"{tmp_path.name}/generated/quantum_tanner_specs/toric-d6.json",
    ]
    for distance, spec_path in zip((4, 6), plan.spec_paths, strict=True):
        spec = json.loads(spec_path.read_text())
        assert spec["fixture_id"] == f"quantum-tanner-toric-d{distance}"
        assert spec["construction_mode"] == "lr_cayley_no_cover_v1"
        assert spec["base_group"]["name"] == f"Z{distance}xZ{distance}"
        assert spec["base_group"]["order"] == distance * distance
        assert spec["local_codes"]["h_a"] == [[1, 1]]
        assert spec["local_codes"]["h_b"] == [[1, 1]]
```

- [ ] **Step 3: Add failing negative-control tests**

```python
def test_generation_rejects_spec_path_escape_before_writes(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(
        _temp_generation_payload(
            tmp_path,
            spec_root=f"{tmp_path.name}/generated/../outside",
        )
    )

    with pytest.raises(SearchIntegrityError, match="spec output path"):
        generate_quantum_tanner_sweep(tmp_path.parent, config, dry_run=False)

    assert not (tmp_path / "generated-ladder.json").exists()
```

```python
def test_generation_rejects_candidate_id_collisions_before_writes(tmp_path: Path) -> None:
    config = normalize_quantum_tanner_sweep_config(_temp_generation_payload(tmp_path))
    duplicate = config.candidates[0]
    collided = replace(config, candidates=(duplicate, duplicate))

    with pytest.raises(SearchIntegrityError, match="duplicate candidate_id"):
        generate_quantum_tanner_sweep(tmp_path.parent, collided, dry_run=False)

    assert not (tmp_path / "generated-ladder.json").exists()
```

- [ ] **Step 4: Run focused tests to verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
```

Expected: FAIL because the generation functions and CLI do not exist.

### Task 2: Implement Planner, Writer, And CLI

**Files:**
- Modify: `src/autoqec_search/quantum_tanner_generator.py`
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_quantum_tanner_generator.py`

**Interfaces:**
- Produces: `plan_quantum_tanner_sweep_generation(repo_root: Path, config: QuantumTannerSweepConfig) -> QuantumTannerGenerationPlan`.
- Produces: `generate_quantum_tanner_sweep(repo_root: Path, config: QuantumTannerSweepConfig, *, dry_run: bool = False) -> QuantumTannerGenerationPlan`.
- Produces: `render_quantum_tanner_generation_summary(plan: QuantumTannerGenerationPlan, *, dry_run: bool) -> str`.
- Produces CLI: `python3 -m autoqec_search.cli generate-quantum-tanner-sweep --config <path> [--root <path>] [--dry-run]`.

- [ ] **Step 1: Add generation dataclasses and manifest path field**

Add:

```python
@dataclass(frozen=True)
class QuantumTannerGenerationPlan:
    repo_root: Path
    manifest_path: Path
    spec_paths: tuple[Path, ...]
    specs: tuple[dict[str, Any], ...]
    manifest: dict[str, Any]
    write_paths: tuple[Path, ...]
```

Add `distance_ladder_manifest_path: Path` to `QuantumTannerSweepConfig`, parsed by
`_safe_repo_relative_path` from the optional field
`distance_ladder_manifest_path`, defaulting to
`output_root / "distance_ladder.json"`.

- [ ] **Step 2: Implement deterministic toric spec construction**

Add:

```python
def build_toric_quantum_tanner_spec(distance: int, *, fixture_id: str) -> dict[str, Any]:
    order = distance * distance
    return {
        "fixture_id": fixture_id,
        "construction_mode": "lr_cayley_no_cover_v1",
        "base_group": {
            "name": f"Z{distance}xZ{distance}",
            "element_order": f"id = {distance}*x + y for (x,y) in Z{distance} x Z{distance}",
            "order": order,
            "identity": 0,
            "multiplication_table": [
                [
                    distance * (((left // distance) + (right // distance)) % distance)
                    + (((left % distance) + (right % distance)) % distance)
                    for right in range(order)
                ]
                for left in range(order)
            ],
        },
        "a_generator_indices": [distance, distance * (distance - 1)],
        "b_generator_indices": [1, distance - 1],
        "local_codes": {
            "matrix_role": "parity_check",
            "field": "GF(2)",
            "h_a": [[1, 1]],
            "h_b": [[1, 1]],
        },
    }
```

- [ ] **Step 3: Implement plan validation and manifest rendering**

Implement helper behavior:

```python
def _resolve_repo_path(repo_root: Path, path: Path, *, label: str) -> Path:
    resolved_root = repo_root.resolve()
    resolved = (repo_root / path).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise SearchIntegrityError(f"{label} must resolve within repository root: {path}")
    return resolved
```

`plan_quantum_tanner_sweep_generation` must:

- reject duplicate candidate ids;
- resolve every spec and manifest path within `repo_root`;
- build manifest id from `campaign_id`;
- set `artifact_root` to `instance_root` relative to manifest parent when possible;
- set `results_table` to `<manifest stem>-results.csv`;
- add one manifest entry per candidate with `n`, `k`, and expected fields;
- collect all write paths as specs plus manifest path.

- [ ] **Step 4: Implement write-run and summary**

`generate_quantum_tanner_sweep(..., dry_run=True)` returns the plan without
writing. With `dry_run=False`, create parent directories and write each JSON
payload using `json.dumps(..., indent=2, sort_keys=False) + "\n"` after the full
plan has been validated.

- [ ] **Step 5: Add CLI command**

In `build_parser`, add:

```python
generate_qt_sweep_parser = subparsers.add_parser(
    "generate-quantum-tanner-sweep",
    help="Generate quantum Tanner toric specs and a distance-ladder manifest",
)
generate_qt_sweep_parser.add_argument("--config", required=True)
generate_qt_sweep_parser.add_argument("--root", default=".")
generate_qt_sweep_parser.add_argument("--dry-run", action="store_true")
```

In `main`, add:

```python
if args.command == "generate-quantum-tanner-sweep":
    config = load_quantum_tanner_sweep_config(Path(args.config))
    plan = generate_quantum_tanner_sweep(Path(args.root), config, dry_run=args.dry_run)
    print(render_quantum_tanner_generation_summary(plan, dry_run=args.dry_run), end="")
    return 0
```

- [ ] **Step 6: Run focused tests to verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
```

Expected: PASS.

### Task 3: Full Verification And Review

**Files:**
- Review all changed files.

**Interfaces:**
- Consumes: completed Task 1 and Task 2 changes.
- Produces: verified branch ready for PR creation.

- [ ] **Step 1: Run required full test suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: PASS.

- [ ] **Step 2: Review the diff for scope and generated artifacts**

Run:

```bash
git diff --stat
git diff -- docs/superpowers/specs/2026-07-08-issue-57-toric-quantum-tanner-generator-design.md docs/superpowers/plans/2026-07-08-issue-57-toric-quantum-tanner-generator.md src/autoqec_search/quantum_tanner_generator.py src/autoqec_search/cli.py tests/fixtures/quantum_tanner_sweep/good.json tests/test_search_quantum_tanner_generator.py
```

Expected: only issue #57 docs, generator, CLI, fixture, and test files changed.

- [ ] **Step 3: Commit implementation**

Run:

```bash
git add docs/superpowers/specs/2026-07-08-issue-57-toric-quantum-tanner-generator-design.md docs/superpowers/plans/2026-07-08-issue-57-toric-quantum-tanner-generator.md src/autoqec_search/quantum_tanner_generator.py src/autoqec_search/cli.py tests/fixtures/quantum_tanner_sweep/good.json tests/test_search_quantum_tanner_generator.py
git commit -m "Implement #57 quantum Tanner toric generator"
```

Expected: one commit on the worker branch.

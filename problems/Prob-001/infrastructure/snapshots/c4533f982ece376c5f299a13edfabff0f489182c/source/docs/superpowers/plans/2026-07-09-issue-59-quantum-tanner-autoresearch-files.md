# Issue 59 Quantum Tanner Autoresearch Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit generated quantum Tanner fixture catalogs and explicit-list search spaces that the existing search workspace validator and catalog resolver consume without special cases.

**Architecture:** Keep emission in `autoqec_search.quantum_tanner_generator`, because it already owns normalized sweep config, distance ordering, and materialized candidate paths. Keep catalog-path workspace validation in the `validate` CLI path to avoid importing `quantum_tanner_catalog` from `load.py`, which would introduce a circular dependency.

**Tech Stack:** Python 3, pytest, jsonschema, existing `autoqec_search` CLI and distance-ladder exporter.

## Global Constraints

- Input is generated instance directories containing `instance.json`, `hx.json`, and `hz.json`, plus normalized sweep config and campaign id.
- Output is `fixture_catalog.json` with one search-ready entry per materialized candidate and `search_space.json` with `mode: "explicit_list"`.
- Files must be compatible with `benchmarks/schemas/search-space.schema.json` and the generalized catalog validator from #55.
- Preserve provenance fields from generated distance ladder and instance metadata, including `qec_code_spec`, `quantum_tanner_spec`, generator, construction mode, and base group when available.
- Do not invent upper-bound witnesses; search-space entries omit `upper_bound_witness_path`.
- Emit deterministic ordering by distance, then candidate id.
- Workspace validation must follow emitted `fixture_catalog_path`.
- Out of scope: autoresearch execution, rbposd, surface-copy comparison, witness finding.

---

## File Structure

- Modify `src/autoqec_search/quantum_tanner_generator.py`: add generated catalog/search-space emission helpers, provenance extraction, and summary output.
- Modify `src/autoqec_search/cli.py`: validate distinct `fixture_catalog_path` values referenced by search spaces during `validate`.
- Modify `src/autoqec_search/quantum_tanner_catalog.py`: allow source-instance `quantum_tanner_spec` values that are relative to a generated distance-ladder manifest while catalog provenance stores the root-relative spec path.
- Modify `tests/test_search_quantum_tanner_generator.py`: add TDD coverage for generated files, schema shape, fixed `/tmp/autoqec-generated-qt-root` verification fixture, and missing-`hz.json` failures.
- Modify `tests/test_search_quantum_tanner_catalog.py`: cover generated manifest-relative `quantum_tanner_spec` provenance.

### Task 1: Red Tests For Emitted Autoresearch Files

**Files:**
- Modify: `tests/test_search_quantum_tanner_generator.py`
- Modify: `tests/test_search_quantum_tanner_catalog.py`

**Interfaces:**
- Consumes: existing `generate_quantum_tanner_sweep()`, fake `qec-code`, and catalog resolver helpers.
- Produces: failing tests that define `emit_quantum_tanner_autoresearch_files()` behavior and workspace validation expectations.

- [ ] **Step 1: Add imports and helpers**

Add imports in `tests/test_search_quantum_tanner_generator.py`:

```python
import shutil

from jsonschema import Draft202012Validator

from autoqec_search.cli import main
from autoqec_search.quantum_tanner_catalog import (
    load_quantum_tanner_fixture_catalog,
    resolve_quantum_tanner_fixture_entry,
    validate_quantum_tanner_fixture_catalog,
)
from autoqec_search.quantum_tanner_generator import (
    emit_quantum_tanner_autoresearch_files,
    generate_quantum_tanner_sweep,
    load_quantum_tanner_sweep_config,
    materialize_quantum_tanner_sweep,
    normalize_quantum_tanner_sweep_config,
    plan_quantum_tanner_sweep_generation,
    render_quantum_tanner_generation_summary,
    render_quantum_tanner_sweep_summary,
)
```

Add helpers:

```python
GENERATED_QT_ROOT = Path("/tmp/autoqec-generated-qt-root")


def _copy_generation_workspace(work_root: Path) -> Path:
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True)
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    return work_root


def _workspace_generation_payload(work_root: Path, **updates: object) -> dict[str, object]:
    payload = _payload(
        output_root="campaigns/examples/quantum-tanner-autoresearch/generated",
        spec_root="campaigns/examples/quantum-tanner-autoresearch/generated/quantum_tanner_specs",
        instance_root="benchmarks/distance_ladders/generated-quantum-tanner/instances",
        catalog_path="campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json",
        search_space_path="campaigns/examples/quantum-tanner-autoresearch/search_space.json",
        distance_ladder_manifest_path="benchmarks/distance_ladders/generated-quantum-tanner.json",
        qec_code_bin=str(_write_fake_qec_code(work_root / "qec-code")),
        distance_ladder_exporter_bin=str(_distance_ladder_exporter_bin()),
    )
    payload.update(updates)
    return payload
```

- [ ] **Step 2: Add the main generated-file test**

Add:

```python
def test_generation_materializes_and_emits_catalog_and_search_space_for_workspace_validation() -> None:
    work_root = _copy_generation_workspace(GENERATED_QT_ROOT)
    config = normalize_quantum_tanner_sweep_config(_workspace_generation_payload(work_root))

    plan = generate_quantum_tanner_sweep(
        work_root,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )

    assert plan.autoresearch_files is not None
    catalog_path = work_root / config.catalog_path
    search_space_path = work_root / config.search_space_path
    assert catalog_path.is_file()
    assert search_space_path.is_file()

    catalog = load_quantum_tanner_fixture_catalog(work_root, config.catalog_path)
    assert [entry["candidate_id"] for entry in catalog["entries"]] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]
    assert [entry["distance"] for entry in catalog["entries"]] == [4, 6]

    search_space = json.loads(search_space_path.read_text())
    Draft202012Validator(
        json.loads((work_root / "benchmarks/schemas/search-space.schema.json").read_text())
    ).validate(search_space)
    assert search_space == {
        "campaign_id": "quantum-tanner-autoresearch",
        "mode": "explicit_list",
        "candidate_specs": [
            {
                "candidate_id": "quantum-tanner-toric-d4",
                "code_family": "quantum-tanner-code",
                "fixture_catalog_path": str(config.catalog_path),
                "provenance": {
                    "kind": "distance-ladder-fixture",
                    "label": "quantum-tanner-toric-d4",
                },
            },
            {
                "candidate_id": "quantum-tanner-toric-d6",
                "code_family": "quantum-tanner-code",
                "fixture_catalog_path": str(config.catalog_path),
                "provenance": {
                    "kind": "distance-ladder-fixture",
                    "label": "quantum-tanner-toric-d6",
                },
            },
        ],
    }

    for entry in catalog["entries"]:
        resolved = resolve_quantum_tanner_fixture_entry(
            work_root,
            entry,
            campaign_id=config.campaign_id,
            catalog_path=config.catalog_path,
        )
        assert resolved.spec.candidate_id == entry["candidate_id"]
        assert resolved.hx["n_cols"] == entry["n"]
        assert resolved.hz["n_cols"] == entry["n"]

    assert main(["validate", "--root", str(work_root)]) == 0
```

- [ ] **Step 3: Add the missing-artifact negative control**

Add:

```python
def test_emitted_catalog_validation_fails_when_generated_hz_is_missing(tmp_path: Path) -> None:
    work_root = _copy_generation_workspace(tmp_path / "generated-root")
    config = normalize_quantum_tanner_sweep_config(_workspace_generation_payload(work_root))
    generate_quantum_tanner_sweep(
        work_root,
        config,
        dry_run=False,
        materialize=True,
        force=True,
    )
    missing_hz = work_root / config.candidates[1].hz_path
    missing_hz.unlink()

    with pytest.raises(SearchIntegrityError, match="missing hz artifact"):
        validate_quantum_tanner_fixture_catalog(work_root, config.catalog_path)
    assert main(["validate", "--root", str(work_root)]) != 0
```

- [ ] **Step 4: Add generated manifest-relative provenance coverage**

Add to `tests/test_search_quantum_tanner_catalog.py`:

```python
def test_generated_catalog_accepts_root_relative_spec_that_matches_manifest_relative_instance(
    tmp_path: Path,
) -> None:
    work_root = _copy_catalog_repo(tmp_path / "manifest-relative")
    entry = _write_generated_toric_fixture(work_root, distance=10, n=100)
    entry["provenance"]["distance_ladder_manifest"] = str(
        DISTANCE_LADDER_REL.with_suffix(".json")
    )
    entry["provenance"]["quantum_tanner_spec"] = str(
        DISTANCE_LADDER_REL / "quantum_tanner_specs/toric-d10.json"
    )
    instance_path = work_root / entry["source_instance"]
    instance = _load_json(instance_path)
    instance["quantum_tanner_spec"] = (
        "surface-toric-bb-kasai-tanner-v2/quantum_tanner_specs/toric-d10.json"
    )
    _write_json(instance_path, instance)
    payload = {
        "catalog_id": "generated-quantum-tanner-fixtures",
        "schema_version": 1,
        "entries": [entry],
    }
    _write_json(work_root / GENERATED_CATALOG_REL, payload)

    validate_quantum_tanner_fixture_catalog(work_root, GENERATED_CATALOG_REL)
```

- [ ] **Step 5: Run tests and confirm RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py tests/test_search_quantum_tanner_catalog.py -q
```

Expected before implementation: fails because `emit_quantum_tanner_autoresearch_files` and `plan.autoresearch_files` do not exist, and workspace validation does not follow generated `fixture_catalog_path`.

### Task 2: Implement Generator Emission

**Files:**
- Modify: `src/autoqec_search/quantum_tanner_generator.py`

**Interfaces:**
- Consumes: `QuantumTannerSweepConfig`, materialized candidate paths, generated spec JSON, and source `instance.json`.
- Produces: `emit_quantum_tanner_autoresearch_files(repo_root, config) -> QuantumTannerAutoresearchFiles` and `QuantumTannerGenerationPlan.autoresearch_files`.

- [ ] **Step 1: Add dataclass and JSON helpers**

Add:

```python
@dataclass(frozen=True)
class QuantumTannerAutoresearchFiles:
    catalog_path: Path
    search_space_path: Path
    catalog: dict[str, Any]
    search_space: dict[str, Any]
```

Add `_load_required_json_object(path, label)` and `_candidate_sort_key(candidate)`.

- [ ] **Step 2: Build root-relative paths and provenance**

Add helpers:

```python
def _repo_relative_path(repo_root: Path, path: Path, *, label: str) -> str:
    resolved = path.resolve()
    root_resolved = repo_root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise SearchIntegrityError(f"{label} must resolve within repository root: {path}")
    return _path_text(resolved.relative_to(root_resolved))


def _source_instance_quantum_tanner_spec(
    plan: QuantumTannerGenerationPlan,
    instance: dict[str, Any],
) -> str:
    value = instance.get("quantum_tanner_spec")
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError("source instance quantum_tanner_spec must be a non-empty string")
    spec_path = Path(value)
    if spec_path.is_absolute():
        return _repo_relative_path(plan.repo_root, spec_path, label="source instance quantum_tanner_spec")
    resolved = (plan.manifest_path.parent / spec_path).resolve()
    return _repo_relative_path(plan.repo_root, resolved, label="source instance quantum_tanner_spec")
```

Load the generated quantum Tanner spec from `candidate.quantum_tanner_spec_path`
and preserve `construction_mode` plus `base_group.name` when present.

- [ ] **Step 3: Build and validate catalog entries**

For each candidate sorted by `(distance, candidate_id)`:

```python
entry = {
    "candidate_id": candidate.candidate_id,
    "code_id": config.code_id,
    "n": instance["n"],
    "k": instance["k"],
    "distance": instance["expected_distance"],
    "hx": _repo_relative_path(plan.repo_root, hx_path, label="hx artifact"),
    "hz": _repo_relative_path(plan.repo_root, hz_path, label="hz artifact"),
    "source_fixture_path": _repo_relative_path(plan.repo_root, instance_dir, label="source fixture directory"),
    "source_instance": _repo_relative_path(plan.repo_root, instance_path, label="source_instance artifact"),
    "provenance": {
        "kind": "distance-ladder-fixture",
        "label": candidate.candidate_id,
        "distance_ladder_manifest": _repo_relative_path(plan.repo_root, plan.manifest_path, label="distance ladder manifest"),
        "qec_code_spec": instance["qec_code_spec"],
        "quantum_tanner_spec": _source_instance_quantum_tanner_spec(plan, instance),
        "generator": generator_tool,
        "construction_mode": construction_mode,
        "base_group": base_group_name,
    },
    "search_ready": True,
    "adaptation": "catalog-normalized-finite-css-instance",
}
```

Fail with `SearchIntegrityError("missing hz artifact: <path>")` or the existing
missing-artifact message if any materialized file is absent.

- [ ] **Step 4: Write catalog and search space atomically enough for this repo**

Resolve configured `catalog_path` and `search_space_path` with `_resolve_repo_path()`.
Create parents, write JSON with `indent=2`, `sort_keys=False`, trailing newline.
Call `validate_quantum_tanner_fixture_catalog(repo_root, config.catalog_path)` after
writing the catalog and before returning.

- [ ] **Step 5: Hook emission into generation**

In `generate_quantum_tanner_sweep()`, after successful materialization, call
`emit_quantum_tanner_autoresearch_files(plan, config)` and store the returned
value in `QuantumTannerGenerationPlan.autoresearch_files`.

Keep `materialize=False` behavior unchanged: no catalog/search-space files are
emitted.

- [ ] **Step 6: Update summary**

Append summary lines when `plan.autoresearch_files is not None`:

```python
emitted fixture_catalog: <path>
emitted search_space: <path>
```

- [ ] **Step 7: Run targeted generator/catalog tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py tests/test_search_quantum_tanner_catalog.py -q
```

Expected after Task 2: generator emission tests pass, but CLI workspace validation test may still fail until Task 3.

### Task 3: Validate Catalog Paths Referenced By Search Spaces

**Files:**
- Modify: `src/autoqec_search/cli.py`

**Interfaces:**
- Consumes: `workspace.search_spaces` loaded by `load_search_workspace(root)`.
- Produces: CLI `validate --root` validation of all distinct catalog paths referenced by catalog-backed search-space entries.

- [ ] **Step 1: Add collector helper**

Add near `main()`:

```python
def _fixture_catalog_paths_from_search_spaces(search_spaces: dict[str, dict]) -> tuple[str, ...]:
    paths: set[str] = set()
    for search_space in search_spaces.values():
        for candidate_spec in search_space.get("candidate_specs", []):
            if isinstance(candidate_spec, dict) and "fixture_catalog_path" in candidate_spec:
                path = candidate_spec["fixture_catalog_path"]
                if isinstance(path, str) and path:
                    paths.add(path)
    return tuple(sorted(paths))
```

- [ ] **Step 2: Use the collector in `validate`**

Replace the default-only catalog validation block with:

```python
catalog_paths = set(_fixture_catalog_paths_from_search_spaces(workspace.search_spaces))
if (root / DEFAULT_CATALOG_PATH).is_file():
    catalog_paths.add(str(DEFAULT_CATALOG_PATH))
for catalog_path in sorted(catalog_paths):
    validate_quantum_tanner_fixture_catalog(root, catalog_path)
```

- [ ] **Step 3: Run targeted tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py tests/test_search_quantum_tanner_catalog.py -q
```

Expected: all targeted tests pass.

### Task 4: Verification, Review, And PR

**Files:**
- No code files beyond Tasks 1-3.

**Interfaces:**
- Consumes: completed implementation.
- Produces: verified branch, committed changes, pushed PR.

- [ ] **Step 1: Run required issue verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py tests/test_search_quantum_tanner_catalog.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root /tmp/autoqec-generated-qt-root
```

Expected: targeted pytest passes and `/tmp/autoqec-generated-qt-root` validates the emitted generated catalog path.

- [ ] **Step 2: Run repository pytest gate**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: full test suite passes.

- [ ] **Step 3: Review the diff**

Run:

```bash
git diff --stat origin/main HEAD
git diff --check
```

Expected: only scoped docs, generator, CLI/catalog validation, and tests changed; no whitespace errors.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add src/autoqec_search/quantum_tanner_generator.py src/autoqec_search/quantum_tanner_catalog.py src/autoqec_search/cli.py tests/test_search_quantum_tanner_generator.py tests/test_search_quantum_tanner_catalog.py docs/superpowers/plans/2026-07-09-issue-59-quantum-tanner-autoresearch-files.md
git commit -m "Implement #59: emit generated Tanner autoresearch files"
```

- [ ] **Step 5: Finish branch**

Use `superpowers:verification-before-completion` and
`superpowers:finishing-a-development-branch`. Choose the recommended Agent Desk
finishing option from the Standing Answer Policy: push and create a pull
request; do not merge.

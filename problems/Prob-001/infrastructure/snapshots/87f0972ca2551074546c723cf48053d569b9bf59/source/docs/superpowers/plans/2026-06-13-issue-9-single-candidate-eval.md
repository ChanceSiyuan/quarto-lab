# Issue #9 Single-Candidate Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `autoqec-search eval` for one rotated-surface candidate, producing a fresh real evaluation run with copied instance artifacts, structure and distance artifacts, rsinter-backed manifests, an SVG LER plot, and a CLI summary.

**Architecture:** Keep the existing placeholder run workflow intact and add a separate eval pipeline under `src/autoqec_search/`. The new pipeline is split into focused modules: schema compatibility, CSS structure math, candidate artifact resolution, rsinter adaptation/parsing, SVG plotting, and CLI orchestration.

**Tech Stack:** Python 3.11, `pytest`, `jsonschema`, standard-library `json`/`pathlib`/`shutil`/`subprocess`/`math`, checked-in JSON schemas, deterministic fake `rsinter` for CI tests.

---

## File Structure

| File | Responsibility |
|---|---|
| `benchmarks/schemas/run-spec.schema.json` | Accept both existing placeholder runs and new eval runs. |
| `benchmarks/schemas/candidate.schema.json` | Accept both placeholder and evaluated candidate records. |
| `benchmarks/schemas/result-manifest.schema.json` | Accept existing placeholder manifests and new completed pointwise manifests. |
| `src/autoqec_search/structure.py` | Validate dense binary matrices, compute GF(2) ranks, check CSS commutation, and build `structure.json` payloads. |
| `src/autoqec_search/eval_candidates.py` | Resolve a candidate from campaign parameters or `--candidate`, find/copy matching Zoo artifacts, and write `distance.json`. |
| `src/autoqec_search/rsinter.py` | Validate eval filters, write `rsinter/spec.toml`, run `rsinter`, parse `results.jsonl`, compute LER and Wilson intervals, and build manifests. |
| `src/autoqec_search/plot.py` | Render standalone deterministic SVG plots from completed manifests. |
| `src/autoqec_search/eval_run.py` | Orchestrate one fresh eval run from CLI arguments. |
| `src/autoqec_search/render.py` | Add real-eval leaderboard and summary rendering helpers while preserving existing placeholder rendering. |
| `src/autoqec_search/cli.py` | Add the `eval` subcommand and route errors through the existing clean CLI path. |
| `tests/test_search_eval_schemas.py` | Schema tests for completed eval records and existing placeholder records. |
| `tests/test_search_structure.py` | Unit tests for GF(2) rank, commutation, and structure summaries. |
| `tests/test_search_eval_candidates.py` | Candidate source and artifact-resolution tests. |
| `tests/test_search_rsinter.py` | Filter, spec-writing, JSONL parsing, and CI tests. |
| `tests/test_search_plot.py` | SVG renderer tests. |
| `tests/test_search_eval_cli.py` | End-to-end CLI tests with fake `rsinter`. |
| `README.md` | Document the new eval command and strict `rsinter` dependency. |
| `CLAUDE.md` | Add repo guidance for issue #9 eval runs. |

---

### Task 1: Evolve Search Schemas For Real Eval Records

**Files:**
- Modify: `benchmarks/schemas/run-spec.schema.json`
- Modify: `benchmarks/schemas/candidate.schema.json`
- Modify: `benchmarks/schemas/result-manifest.schema.json`
- Create: `tests/test_search_eval_schemas.py`

- [ ] **Step 1: Write schema tests for completed eval records**

Create `tests/test_search_eval_schemas.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_eval_schemas_accept_completed_records() -> None:
    schema_root = REPO_ROOT / "benchmarks" / "schemas"

    run_spec = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "suite_id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-x-cdep-v1"],
        "decoder_ids": ["rmatching-default-v1"],
        "candidate_ids": ["rotated-surface-d3-example"],
        "created_at": "2026-06-13T10:20:39Z",
        "mode": "eval",
    }
    candidate = {
        "candidate_id": "rotated-surface-d3-example",
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "code_family": "rotated-surface-code",
        "parameters": {"distance": 3, "layout": "rotated"},
        "provenance": {"kind": "seed", "label": "repo-example"},
        "status": "evaluated",
    }
    manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "test-eval",
        "candidate_id": "rotated-surface-d3-example",
        "task_id": "rotated-memory-x-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "completed",
        "created_at": "2026-06-13T10:20:39Z",
        "tool_revisions": {
            "rsinter": "rsinter 0.1.1",
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

    Draft202012Validator(_load_json(schema_root / "run-spec.schema.json")).validate(
        run_spec
    )
    Draft202012Validator(_load_json(schema_root / "candidate.schema.json")).validate(
        candidate
    )
    Draft202012Validator(
        _load_json(schema_root / "result-manifest.schema.json")
    ).validate(manifest)


def test_result_manifest_schema_still_accepts_existing_placeholder_manifest() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "result-manifest.schema.json")
    manifest = _load_json(
        REPO_ROOT
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )

    Draft202012Validator(schema).validate(manifest)
```

- [ ] **Step 2: Run the schema tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_eval_schemas.py -v
```

Expected: `test_eval_schemas_accept_completed_records` fails because `mode`, candidate `status`, and manifest `status` only accept placeholder values.

- [ ] **Step 3: Update `run-spec.schema.json`**

In `benchmarks/schemas/run-spec.schema.json`, replace:

```json
"mode": { "enum": ["placeholder"] }
```

with:

```json
"mode": { "enum": ["placeholder", "eval"] }
```

- [ ] **Step 4: Update `candidate.schema.json`**

In `benchmarks/schemas/candidate.schema.json`, replace:

```json
"status": { "enum": ["placeholder"] }
```

with:

```json
"status": { "enum": ["placeholder", "evaluated"] }
```

- [ ] **Step 5: Replace `result-manifest.schema.json` with a oneOf schema**

Replace the entire file with:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "oneOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "campaign_id",
        "run_id",
        "candidate_id",
        "task_id",
        "decoder_id",
        "status",
        "metrics",
        "created_at"
      ],
      "properties": {
        "campaign_id": { "type": "string", "minLength": 1 },
        "run_id": { "type": "string", "minLength": 1 },
        "candidate_id": { "type": "string", "minLength": 1 },
        "task_id": { "type": "string", "minLength": 1 },
        "decoder_id": { "type": "string", "minLength": 1 },
        "status": { "const": "placeholder" },
        "metrics": {
          "type": "object",
          "minProperties": 1,
          "additionalProperties": {
            "type": ["number", "null"]
          }
        },
        "created_at": {
          "type": "string",
          "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"
        }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "campaign_id",
        "run_id",
        "candidate_id",
        "task_id",
        "decoder_id",
        "status",
        "created_at",
        "tool_revisions",
        "points"
      ],
      "properties": {
        "campaign_id": { "type": "string", "minLength": 1 },
        "run_id": { "type": "string", "minLength": 1 },
        "candidate_id": { "type": "string", "minLength": 1 },
        "task_id": { "type": "string", "minLength": 1 },
        "decoder_id": { "type": "string", "minLength": 1 },
        "status": { "const": "completed" },
        "created_at": {
          "type": "string",
          "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"
        },
        "tool_revisions": {
          "type": "object",
          "minProperties": 1,
          "additionalProperties": { "type": "string", "minLength": 1 }
        },
        "points": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": [
              "p",
              "rounds",
              "shots",
              "errors",
              "ler",
              "ci_low",
              "ci_high",
              "seconds"
            ],
            "properties": {
              "p": { "type": "number", "exclusiveMinimum": 0 },
              "rounds": { "type": "integer", "minimum": 1 },
              "shots": { "type": "integer", "minimum": 1 },
              "errors": { "type": "integer", "minimum": 0 },
              "ler": { "type": "number", "minimum": 0, "maximum": 1 },
              "ci_low": { "type": "number", "minimum": 0, "maximum": 1 },
              "ci_high": { "type": "number", "minimum": 0, "maximum": 1 },
              "seconds": { "type": "number", "minimum": 0 }
            }
          }
        }
      }
    }
  ]
}
```

- [ ] **Step 6: Run schema and existing search-load tests**

Run:

```bash
python3 -m pytest tests/test_search_eval_schemas.py tests/test_search_load.py tests/test_search_source_data.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add benchmarks/schemas/run-spec.schema.json benchmarks/schemas/candidate.schema.json benchmarks/schemas/result-manifest.schema.json tests/test_search_eval_schemas.py
git commit -m "feat: allow completed search eval records"
```

---

### Task 2: Add CSS Structure Math

**Files:**
- Create: `src/autoqec_search/structure.py`
- Create: `tests/test_search_structure.py`

- [ ] **Step 1: Write structure tests**

Create `tests/test_search_structure.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.structure import gf2_rank, summarize_css_structure


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTANCE_ROOT = (
    REPO_ROOT
    / "zoo"
    / "codes"
    / "rotated-surface-code"
    / "instances"
    / "rotated-surface-code-d3"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_gf2_rank_handles_dependent_rows() -> None:
    assert gf2_rank([[1, 0, 1], [0, 1, 1], [1, 1, 0]]) == 2
    assert gf2_rank([[1, 0, 0], [0, 1, 0], [0, 0, 1]]) == 3


def test_summarize_css_structure_reports_rotated_d3() -> None:
    summary = summarize_css_structure(
        _load_json(INSTANCE_ROOT / "hx.json"),
        _load_json(INSTANCE_ROOT / "hz.json"),
    )

    assert summary == {
        "status": "completed",
        "n": 9,
        "k": 1,
        "rank_hx": 4,
        "rank_hz": 4,
        "mx": 4,
        "mz": 4,
        "css_commute": True,
        "commutation_failures": [],
    }


def test_summarize_css_structure_reports_commutation_failure() -> None:
    hx = _load_json(INSTANCE_ROOT / "hx.json")
    hz = _load_json(INSTANCE_ROOT / "hz.json")
    hz["data"][0][2] = 1

    summary = summarize_css_structure(hx, hz)

    assert summary["status"] == "failed"
    assert summary["css_commute"] is False
    assert summary["commutation_failures"] == [{"hx_row": 0, "hz_row": 0}]


def test_summarize_css_structure_rejects_mismatched_column_counts() -> None:
    hx = _load_json(INSTANCE_ROOT / "hx.json")
    hz = _load_json(INSTANCE_ROOT / "hz.json")
    hz["n_cols"] = 10

    with pytest.raises(SearchIntegrityError, match="matrix column mismatch"):
        summarize_css_structure(hx, hz)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_structure.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autoqec_search.structure'`.

- [ ] **Step 3: Implement `structure.py`**

Create `src/autoqec_search/structure.py`:

```python
from __future__ import annotations

from autoqec_search.load import SearchIntegrityError


DenseMatrix = list[list[int]]


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def matrix_data(payload: dict, label: str) -> DenseMatrix:
    required_keys = {"format", "n_rows", "n_cols", "data"}
    if not isinstance(payload, dict) or not required_keys.issubset(payload):
        raise SearchIntegrityError(f"invalid matrix payload: {label}")
    if payload["format"] != "dense_binary_matrix":
        raise SearchIntegrityError(f"unsupported matrix format: {label}")
    if not _is_plain_int(payload["n_rows"]) or not _is_plain_int(payload["n_cols"]):
        raise SearchIntegrityError(f"invalid matrix dimensions: {label}")
    if not isinstance(payload["data"], list):
        raise SearchIntegrityError(f"invalid matrix data: {label}")
    if payload["n_rows"] != len(payload["data"]):
        raise SearchIntegrityError(f"matrix row count mismatch: {label}")

    rows: DenseMatrix = []
    for row in payload["data"]:
        if not isinstance(row, list):
            raise SearchIntegrityError(f"invalid matrix row: {label}")
        if len(row) != payload["n_cols"]:
            raise SearchIntegrityError(f"matrix column mismatch: {label}")
        if any(not _is_plain_int(bit) or bit not in (0, 1) for bit in row):
            raise SearchIntegrityError(f"matrix contains non-binary entries: {label}")
        rows.append([int(bit) for bit in row])
    return rows


def gf2_rank(matrix: DenseMatrix) -> int:
    rows = [row[:] for row in matrix if any(row)]
    if not rows:
        return 0

    rank = 0
    column_count = len(rows[0])
    for column in range(column_count):
        pivot_index = next(
            (index for index in range(rank, len(rows)) if rows[index][column] == 1),
            None,
        )
        if pivot_index is None:
            continue
        rows[rank], rows[pivot_index] = rows[pivot_index], rows[rank]
        for index in range(len(rows)):
            if index != rank and rows[index][column] == 1:
                rows[index] = [
                    left ^ right for left, right in zip(rows[index], rows[rank], strict=True)
                ]
        rank += 1
        if rank == len(rows):
            break
    return rank


def commutation_failures(hx: DenseMatrix, hz: DenseMatrix) -> list[dict[str, int]]:
    failures: list[dict[str, int]] = []
    for hx_index, hx_row in enumerate(hx):
        for hz_index, hz_row in enumerate(hz):
            overlap = sum(left & right for left, right in zip(hx_row, hz_row, strict=True))
            if overlap % 2:
                failures.append({"hx_row": hx_index, "hz_row": hz_index})
    return failures


def summarize_css_structure(hx_payload: dict, hz_payload: dict) -> dict:
    if hx_payload.get("n_cols") != hz_payload.get("n_cols"):
        raise SearchIntegrityError("matrix column mismatch: hx.json vs hz.json")

    hx = matrix_data(hx_payload, "hx.json")
    hz = matrix_data(hz_payload, "hz.json")
    rank_hx = gf2_rank(hx)
    rank_hz = gf2_rank(hz)
    failures = commutation_failures(hx, hz)
    n = int(hx_payload["n_cols"])
    summary = {
        "status": "completed" if not failures else "failed",
        "n": n,
        "k": n - rank_hx - rank_hz,
        "rank_hx": rank_hx,
        "rank_hz": rank_hz,
        "mx": int(hx_payload["n_rows"]),
        "mz": int(hz_payload["n_rows"]),
        "css_commute": not failures,
        "commutation_failures": failures,
    }
    return summary
```

- [ ] **Step 4: Run structure tests**

Run:

```bash
python3 -m pytest tests/test_search_structure.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/structure.py tests/test_search_structure.py
git commit -m "feat: add CSS structure checks for search eval"
```

---

### Task 3: Resolve Candidate Sources And Copy Artifacts

**Files:**
- Create: `src/autoqec_search/eval_candidates.py`
- Create: `tests/test_search_eval_candidates.py`

- [ ] **Step 1: Write candidate-resolution tests**

Create `tests/test_search_eval_candidates.py`:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from autoqec_search.eval_candidates import (
    CandidateInput,
    copy_candidate_artifacts,
    resolve_campaign_candidate,
    resolve_directory_candidate,
)
from autoqec_search.load import SearchIntegrityError, load_search_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_resolve_campaign_candidate_reuses_zoo_rotated_d3() -> None:
    workspace = load_search_workspace(REPO_ROOT)

    candidate = resolve_campaign_candidate(
        REPO_ROOT,
        workspace,
        campaign_id="rotated-surface-baseline",
        distance=3,
    )

    assert candidate.spec.candidate_id == "rotated-surface-d3-example"
    assert candidate.spec.code_family == "rotated-surface-code"
    assert candidate.artifact_root.name == "rotated-surface-code-d3"
    assert candidate.instance["derived_properties"]["distance"] == 3


def test_copy_candidate_artifacts_writes_artifacts_and_distance(tmp_path: Path) -> None:
    workspace = load_search_workspace(REPO_ROOT)
    candidate = resolve_campaign_candidate(
        REPO_ROOT,
        workspace,
        campaign_id="rotated-surface-baseline",
        distance=3,
    )
    candidate_root = tmp_path / "candidate"

    copy_candidate_artifacts(candidate, candidate_root)

    assert sorted(path.name for path in (candidate_root / "artifacts").iterdir()) == [
        "hx.json",
        "hz.json",
        "instance.json",
    ]
    distance = _load_json(candidate_root / "distance.json")
    assert distance["distance"] == 3
    assert distance["method"] == "copied-from-zoo-instance"
    assert distance["source_instance_id"] == "rotated-surface-code-d3"


def test_resolve_directory_candidate_prefers_candidate_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source-candidate"
    artifacts = source / "artifacts"
    artifacts.mkdir(parents=True)
    zoo_instance_root = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    for name in ("instance.json", "hx.json", "hz.json"):
        shutil.copyfile(zoo_instance_root / name, artifacts / name)
    (source / "candidate.json").write_text(
        json.dumps(
            {
                "candidate_id": "external-d3",
                "campaign_id": "rotated-surface-baseline",
                "run_id": "source-run",
                "code_family": "rotated-surface-code",
                "parameters": {"distance": 3, "layout": "rotated"},
                "provenance": {"kind": "external", "label": "tmp"},
                "status": "evaluated",
            },
            indent=2,
        )
        + "\n"
    )

    candidate = resolve_directory_candidate(
        REPO_ROOT,
        source,
        campaign_id="rotated-surface-baseline",
    )

    assert candidate.spec.candidate_id == "external-d3"
    assert candidate.artifact_root == artifacts
    assert candidate.instance["id"] == "rotated-surface-code-d3"


def test_resolve_campaign_candidate_fails_without_recorded_distance(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")
    instance_path = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
        / "instance.json"
    )
    instance = _load_json(instance_path)
    instance["derived_properties"]["distance"] = None
    instance_path.write_text(json.dumps(instance, indent=2) + "\n")

    workspace = load_search_workspace(work_root)

    with pytest.raises(SearchIntegrityError, match="recorded distance"):
        resolve_campaign_candidate(
            work_root,
            workspace,
            campaign_id="rotated-surface-baseline",
            distance=3,
        )
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_eval_candidates.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autoqec_search.eval_candidates'`.

- [ ] **Step 3: Implement `eval_candidates.py`**

Create `src/autoqec_search/eval_candidates.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil

from autoqec_search.load import SearchIntegrityError, SearchWorkspace


@dataclass(frozen=True)
class CandidateInput:
    candidate_id: str
    campaign_id: str
    code_family: str
    parameters: dict
    provenance: dict


@dataclass(frozen=True)
class ResolvedCandidate:
    spec: CandidateInput
    artifact_root: Path
    instance: dict
    hx: dict
    hz: dict
    source_kind: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")


def _candidate_from_payload(payload: dict, campaign_id: str) -> CandidateInput:
    return CandidateInput(
        candidate_id=payload["candidate_id"],
        campaign_id=campaign_id,
        code_family=payload["code_family"],
        parameters=payload["parameters"],
        provenance=payload["provenance"],
    )


def _load_artifact_bundle(artifact_root: Path) -> tuple[dict, dict, dict]:
    instance_path = artifact_root / "instance.json"
    _require_file(instance_path, "instance artifact")
    instance = _load_json(instance_path)
    hx_path = artifact_root / instance["artifacts"]["hx"]
    hz_path = artifact_root / instance["artifacts"]["hz"]
    _require_file(hx_path, "hx artifact")
    _require_file(hz_path, "hz artifact")
    return instance, _load_json(hx_path), _load_json(hz_path)


def _matching_zoo_instance_root(root: Path, code_family: str, parameters: dict) -> Path:
    for instance_path in sorted((root / "zoo" / "codes").glob("*/instances/*/instance.json")):
        instance = _load_json(instance_path)
        if instance.get("code_id") != code_family:
            continue
        if instance.get("parameters") == parameters:
            return instance_path.parent
    raise SearchIntegrityError(
        f"no matching Zoo instance for {code_family} with parameters {parameters}"
    )


def _ensure_recorded_distance(instance: dict, source: Path) -> None:
    distance = instance.get("derived_properties", {}).get("distance")
    if not isinstance(distance, int) or isinstance(distance, bool) or distance <= 0:
        raise SearchIntegrityError(f"missing recorded distance on source instance: {source}")


def resolve_campaign_candidate(
    root: Path,
    workspace: SearchWorkspace,
    *,
    campaign_id: str,
    distance: int,
) -> ResolvedCandidate:
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")
    search_space = workspace.search_spaces[campaign_id]
    matches = [
        candidate
        for candidate in search_space["candidate_specs"]
        if candidate["code_family"] == "rotated-surface-code"
        and candidate["parameters"].get("distance") == distance
        and candidate["parameters"].get("layout") == "rotated"
    ]
    if len(matches) != 1:
        raise SearchIntegrityError(
            f"expected one rotated-surface candidate at distance {distance}, found {len(matches)}"
        )

    spec = _candidate_from_payload(matches[0], campaign_id)
    artifact_root = _matching_zoo_instance_root(root, spec.code_family, spec.parameters)
    instance, hx, hz = _load_artifact_bundle(artifact_root)
    _ensure_recorded_distance(instance, artifact_root / "instance.json")
    return ResolvedCandidate(
        spec=spec,
        artifact_root=artifact_root,
        instance=instance,
        hx=hx,
        hz=hz,
        source_kind="zoo-instance",
    )


def resolve_directory_candidate(
    root: Path,
    candidate_dir: Path,
    *,
    campaign_id: str,
) -> ResolvedCandidate:
    candidate_path = candidate_dir / "candidate.json"
    _require_file(candidate_path, "candidate payload")
    spec = _candidate_from_payload(_load_json(candidate_path), campaign_id)

    local_artifact_root = candidate_dir / "artifacts"
    artifact_root = (
        local_artifact_root
        if (local_artifact_root / "instance.json").is_file()
        else _matching_zoo_instance_root(root, spec.code_family, spec.parameters)
    )
    instance, hx, hz = _load_artifact_bundle(artifact_root)
    _ensure_recorded_distance(instance, artifact_root / "instance.json")
    return ResolvedCandidate(
        spec=spec,
        artifact_root=artifact_root,
        instance=instance,
        hx=hx,
        hz=hz,
        source_kind="candidate-dir" if artifact_root == local_artifact_root else "zoo-instance",
    )


def candidate_payload(candidate: ResolvedCandidate, run_id: str) -> dict:
    return {
        "candidate_id": candidate.spec.candidate_id,
        "campaign_id": candidate.spec.campaign_id,
        "run_id": run_id,
        "code_family": candidate.spec.code_family,
        "parameters": candidate.spec.parameters,
        "provenance": candidate.spec.provenance,
        "status": "evaluated",
    }


def copy_candidate_artifacts(candidate: ResolvedCandidate, candidate_root: Path) -> None:
    artifacts_root = candidate_root / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    for name in ("instance.json", "hx.json", "hz.json"):
        shutil.copyfile(candidate.artifact_root / name, artifacts_root / name)

    distance = candidate.instance["derived_properties"]["distance"]
    distance_payload = {
        "status": "completed",
        "distance": distance,
        "method": "copied-from-zoo-instance",
        "source_instance_id": candidate.instance["id"],
        "source_instance_path": str(candidate.artifact_root),
    }
    (candidate_root / "distance.json").write_text(
        json.dumps(distance_payload, indent=2, sort_keys=True) + "\n"
    )
```

- [ ] **Step 4: Run candidate tests**

Run:

```bash
python3 -m pytest tests/test_search_eval_candidates.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/eval_candidates.py tests/test_search_eval_candidates.py
git commit -m "feat: resolve single eval candidates"
```

---

### Task 4: Add rsinter Spec Writing And Result Parsing

**Files:**
- Create: `src/autoqec_search/rsinter.py`
- Create: `tests/test_search_rsinter.py`

- [ ] **Step 1: Write rsinter unit tests**

Create `tests/test_search_rsinter.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.rsinter import (
    build_completed_manifest,
    parse_decoder_filter,
    parse_p_filter,
    parse_results_jsonl,
    rounds_for_task,
    wilson_interval,
    write_spec_toml,
)


def test_filter_parsers_accept_repeated_and_comma_separated_values() -> None:
    assert parse_decoder_filter(["rmatching-default-v1,rbposd-default-v1"]) == [
        "rmatching-default-v1",
        "rbposd-default-v1",
    ]
    assert parse_decoder_filter(["rmatching-default-v1", "rbposd-default-v1"]) == [
        "rmatching-default-v1",
        "rbposd-default-v1",
    ]
    assert parse_p_filter(["0.005,0.01"]) == [0.005, 0.01]
    assert parse_p_filter(["0.005", "0.01"]) == [0.005, 0.01]


def test_rounds_for_distance_scaled_task() -> None:
    task = {
        "rounds_policy": {"kind": "distance-scaled", "multiplier": 1, "minimum": 3}
    }

    assert rounds_for_task(task, distance=3) == 3
    assert rounds_for_task(task, distance=5) == 5


def test_wilson_interval_matches_golden_fixture_band() -> None:
    low, high = wilson_interval(errors=5, shots=1000)

    assert round(low, 5) == 0.00214
    assert round(high, 5) == 0.01165


def test_parse_results_jsonl_builds_points(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            {
                "decoder_id": "rmatching-default-v1",
                "task_id": "rotated-memory-x-cdep-v1",
                "p": 0.005,
                "rounds": 3,
                "shots": 1000,
                "errors": 5,
                "seconds": 1.25,
            },
            sort_keys=True,
        )
        + "\n"
    )

    points = parse_results_jsonl(
        path,
        expected_decoder_id="rmatching-default-v1",
        expected_task_id="rotated-memory-x-cdep-v1",
        expected_p_values=[0.005],
    )

    assert points == [
        {
            "p": 0.005,
            "rounds": 3,
            "shots": 1000,
            "errors": 5,
            "ler": 0.005,
            "ci_low": pytest.approx(0.00214, abs=0.00001),
            "ci_high": pytest.approx(0.01165, abs=0.00001),
            "seconds": 1.25,
        }
    ]


def test_parse_results_jsonl_rejects_errors_exceeding_shots(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps(
            {
                "decoder_id": "rmatching-default-v1",
                "task_id": "rotated-memory-x-cdep-v1",
                "p": 0.005,
                "rounds": 3,
                "shots": 1000,
                "errors": 1001,
            }
        )
        + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="errors exceed shots"):
        parse_results_jsonl(
            path,
            expected_decoder_id="rmatching-default-v1",
            expected_task_id="rotated-memory-x-cdep-v1",
            expected_p_values=[0.005],
        )


def test_build_completed_manifest() -> None:
    manifest = build_completed_manifest(
        campaign_id="rotated-surface-baseline",
        run_id="test-eval",
        candidate_id="rotated-surface-d3-example",
        task_id="rotated-memory-x-cdep-v1",
        decoder_id="rmatching-default-v1",
        created_at="2026-06-13T10:20:39Z",
        tool_revisions={"rsinter": "rsinter 0.1.1", "autoqec_search": "0.1.0"},
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

    assert manifest["status"] == "completed"
    assert manifest["points"][0]["ler"] == 0.005


def test_write_spec_toml_contains_runner_params(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.toml"
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

    text = spec_path.read_text()
    assert 'id = "rmatching-default-v1"' in text
    assert 'impl_key = "rmatching"' in text
    assert "distance = [3]" in text
    assert "p = [0.005]" in text
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_rsinter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autoqec_search.rsinter'`.

- [ ] **Step 3: Implement `rsinter.py`**

Create `src/autoqec_search/rsinter.py` with these functions:

```python
from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
import shutil
import subprocess

from autoqec_search.load import SearchIntegrityError


PINNED_RSINTER_MIN_VERSION = "0.1.1"


def parse_decoder_filter(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    parsed = [item.strip() for value in values for item in value.split(",")]
    return [item for item in parsed if item]


def parse_p_filter(values: list[str] | None) -> list[float] | None:
    if not values:
        return None
    parsed: list[float] = []
    for value in values:
        for item in value.split(","):
            text = item.strip()
            if text:
                parsed.append(float(text))
    return parsed


def validate_selected_decoders(suite: dict, selected: list[str] | None) -> list[str]:
    suite_decoders = suite["decoder_ids"]
    if selected is None:
        return suite_decoders
    unknown = sorted(set(selected) - set(suite_decoders))
    if unknown:
        raise SearchIntegrityError(f"decoder filter not in suite: {', '.join(unknown)}")
    return selected


def validate_selected_p_values(task: dict, selected: list[float] | None) -> list[float]:
    task_values = [float(value) for value in task["p_list"]]
    if selected is None:
        return task_values
    unknown = [value for value in selected if value not in task_values]
    if unknown:
        raise SearchIntegrityError(f"p filter not in task p_list: {unknown}")
    return selected


def rounds_for_task(task: dict, *, distance: int) -> int:
    policy = task["rounds_policy"]
    if policy["kind"] != "distance-scaled":
        raise SearchIntegrityError(f"unsupported rounds policy: {policy['kind']}")
    return max(int(policy["minimum"]), int(policy["multiplier"]) * distance)


def wilson_interval(*, errors: int, shots: int, z: float = 1.96) -> tuple[float, float]:
    if shots <= 0:
        raise SearchIntegrityError(f"invalid shots: {shots}")
    if errors < 0:
        raise SearchIntegrityError(f"invalid errors: {errors}")
    if errors > shots:
        raise SearchIntegrityError(f"errors exceed shots: {errors} > {shots}")
    phat = errors / shots
    denominator = 1 + z * z / shots
    center = (phat + z * z / (2 * shots)) / denominator
    margin = z * sqrt((phat * (1 - phat) + z * z / (4 * shots)) / shots) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _require_number(record: dict, key: str, path: Path, line_number: int) -> int | float:
    value = record.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise SearchIntegrityError(f"{path}:{line_number}: missing numeric {key}")
    return value


def parse_results_jsonl(
    path: Path,
    *,
    expected_decoder_id: str,
    expected_task_id: str,
    expected_p_values: list[float],
) -> list[dict]:
    points: list[dict] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SearchIntegrityError(
                f"{path}:{line_number}: invalid JSONL record: {exc}"
            ) from exc
        if record.get("decoder_id") != expected_decoder_id:
            raise SearchIntegrityError(f"{path}:{line_number}: unexpected decoder_id")
        if record.get("task_id") != expected_task_id:
            raise SearchIntegrityError(f"{path}:{line_number}: unexpected task_id")
        p = float(_require_number(record, "p", path, line_number))
        if p not in expected_p_values:
            raise SearchIntegrityError(f"{path}:{line_number}: unexpected p: {p}")
        rounds = int(_require_number(record, "rounds", path, line_number))
        shots = int(_require_number(record, "shots", path, line_number))
        errors = int(_require_number(record, "errors", path, line_number))
        seconds = float(record.get("seconds", 0.0))
        ci_low, ci_high = wilson_interval(errors=errors, shots=shots)
        points.append(
            {
                "p": p,
                "rounds": rounds,
                "shots": shots,
                "errors": errors,
                "ler": errors / shots,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "seconds": seconds,
            }
        )
    if not points:
        raise SearchIntegrityError(f"{path}: no result records")
    expected_set = set(expected_p_values)
    actual_set = {point["p"] for point in points}
    if actual_set != expected_set:
        raise SearchIntegrityError(f"{path}: missing p results: {sorted(expected_set - actual_set)}")
    return sorted(points, key=lambda point: point["p"])


def build_completed_manifest(
    *,
    campaign_id: str,
    run_id: str,
    candidate_id: str,
    task_id: str,
    decoder_id: str,
    created_at: str,
    tool_revisions: dict[str, str],
    points: list[dict],
) -> dict:
    return {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "decoder_id": decoder_id,
        "status": "completed",
        "created_at": created_at,
        "tool_revisions": tool_revisions,
        "points": points,
    }


def write_spec_toml(
    spec_path: Path,
    *,
    task: dict,
    decoders: dict[str, dict],
    selected_decoder_ids: list[str],
    distance: int,
    rounds: int,
    p_values: list[float],
) -> None:
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    p_list = ", ".join(str(value) for value in p_values)
    lines: list[str] = []
    for decoder_id in selected_decoder_ids:
        decoder = decoders[decoder_id]
        lines.extend(
            [
                "[[runner]]",
                f'id = "{decoder_id}"',
                f'impl_key = "{decoder["impl_key"]}"',
                f'task_id = "{task["id"]}"',
                f'language = "{decoder.get("language", "rust")}"',
                "[runner.params]",
                f"distance = [{distance}]",
                f"rounds = [{rounds}]",
                f"p = [{p_list}]",
                f'max_shots = {int(task["collection"]["max_shots"])}',
                f'max_errors = {int(task["collection"]["max_errors"])}',
                "",
            ]
        )
    spec_path.write_text("\n".join(lines))


def require_rsinter() -> tuple[str, str]:
    executable = shutil.which("rsinter")
    if executable is None:
        raise SearchIntegrityError("rsinter not found on PATH")
    result = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    version_text = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        raise SearchIntegrityError(
            f"rsinter --version exited {result.returncode}: {version_text}"
        )
    return executable, version_text


def run_rsinter(spec_path: Path, out_dir: Path, *, executable: str) -> None:
    result = subprocess.run(
        [
            executable,
            "bench",
            "run",
            "--spec",
            str(spec_path),
            "--language",
            "rust",
            "--out",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SearchIntegrityError(
            f"rsinter bench run exited {result.returncode}: {result.stderr.strip()}"
        )
```

- [ ] **Step 4: Run rsinter unit tests**

Run:

```bash
python3 -m pytest tests/test_search_rsinter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/rsinter.py tests/test_search_rsinter.py
git commit -m "feat: add rsinter eval adapter"
```

---

### Task 5: Render Per-Candidate SVG Plots

**Files:**
- Create: `src/autoqec_search/plot.py`
- Create: `tests/test_search_plot.py`

- [ ] **Step 1: Write SVG plot tests**

Create `tests/test_search_plot.py`:

```python
from __future__ import annotations

from autoqec_search.plot import render_candidate_plot


def test_render_candidate_plot_includes_decoder_series_and_ci() -> None:
    manifests = [
        {
            "decoder_id": "rmatching-default-v1",
            "task_id": "rotated-memory-x-cdep-v1",
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
                },
                {
                    "p": 0.01,
                    "rounds": 3,
                    "shots": 1000,
                    "errors": 20,
                    "ler": 0.02,
                    "ci_low": 0.013,
                    "ci_high": 0.031,
                    "seconds": 1.40,
                },
            ],
        }
    ]

    svg = render_candidate_plot(
        candidate_id="rotated-surface-d3-example",
        distance=3,
        task_id="rotated-memory-x-cdep-v1",
        generated_at="2026-06-13T10:20:39Z",
        manifests=manifests,
    )

    assert svg.startswith("<svg")
    assert "rotated-surface-d3-example" in svg
    assert "rmatching-default-v1" in svg
    assert "0.005" in svg
    assert "ci-interval" in svg
    assert "polyline" in svg
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_plot.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autoqec_search.plot'`.

- [ ] **Step 3: Implement `plot.py`**

Create `src/autoqec_search/plot.py`:

```python
from __future__ import annotations

from html import escape
from math import log10


COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b"]


def _domain(values: list[float]) -> tuple[float, float]:
    low = min(values)
    high = max(values)
    if low == high:
        return low / 2, high * 2
    return low, high


def _scale_log(value: float, domain: tuple[float, float], low: float, high: float) -> float:
    domain_low, domain_high = log10(domain[0]), log10(domain[1])
    ratio = (log10(value) - domain_low) / (domain_high - domain_low)
    return low + ratio * (high - low)


def render_candidate_plot(
    *,
    candidate_id: str,
    distance: int,
    task_id: str,
    generated_at: str,
    manifests: list[dict],
) -> str:
    all_points = [point for manifest in manifests for point in manifest["points"]]
    x_domain = _domain([float(point["p"]) for point in all_points])
    y_values = [
        max(float(value), 1e-12)
        for point in all_points
        for value in (point["ci_low"], point["ler"], point["ci_high"])
    ]
    y_domain = _domain(y_values)

    width = 760
    height = 480
    left = 82
    right = 700
    top = 42
    bottom = 390
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,sans-serif;font-size:13px} .axis{stroke:#222;stroke-width:1.2} .grid{stroke:#ddd;stroke-width:1} .ci-interval{stroke-width:1.4;opacity:.7} .series{fill:none;stroke-width:2.2}</style>",
        f'<text x="{left}" y="24" font-size="18">LER vs p for {escape(candidate_id)}</text>',
        f'<line class="axis" x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}"/>',
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{bottom}"/>',
        f'<text x="{(left + right) / 2 - 30}" y="430">physical error rate p</text>',
        f'<text x="16" y="{(top + bottom) / 2}" transform="rotate(-90 16 {(top + bottom) / 2})">logical error rate</text>',
    ]

    for index, manifest in enumerate(manifests):
        color = COLORS[index % len(COLORS)]
        coords: list[str] = []
        for point in sorted(manifest["points"], key=lambda item: item["p"]):
            x = _scale_log(float(point["p"]), x_domain, left, right)
            y = _scale_log(max(float(point["ler"]), 1e-12), y_domain, bottom, top)
            y_low = _scale_log(max(float(point["ci_low"]), 1e-12), y_domain, bottom, top)
            y_high = _scale_log(max(float(point["ci_high"]), 1e-12), y_domain, bottom, top)
            coords.append(f"{x:.2f},{y:.2f}")
            parts.append(
                f'<line class="ci-interval" x1="{x:.2f}" y1="{y_low:.2f}" x2="{x:.2f}" y2="{y_high:.2f}" stroke="{color}"/>'
            )
            parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"><title>p={point["p"]}, LER={point["ler"]}</title></circle>'
            )
            parts.append(
                f'<text x="{x + 6:.2f}" y="{bottom + 18:.2f}" fill="#333">{point["p"]}</text>'
            )
        parts.append(
            f'<polyline class="series" points="{" ".join(coords)}" stroke="{color}"/>'
        )
        legend_y = top + 20 + index * 20
        parts.append(
            f'<line x1="540" y1="{legend_y}" x2="570" y2="{legend_y}" stroke="{color}" stroke-width="2.2"/>'
        )
        parts.append(
            f'<text x="578" y="{legend_y + 4}">{escape(manifest["decoder_id"])}</text>'
        )

    footer = (
        f"candidate={candidate_id}; distance={distance}; task={task_id}; generated={generated_at}"
    )
    parts.append(f'<text x="{left}" y="462" fill="#555">{escape(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run plot tests**

Run:

```bash
python3 -m pytest tests/test_search_plot.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/plot.py tests/test_search_plot.py
git commit -m "feat: render candidate LER plots"
```

---

### Task 6: Orchestrate `autoqec-search eval`

**Files:**
- Create: `src/autoqec_search/eval_run.py`
- Modify: `src/autoqec_search/cli.py`
- Modify: `src/autoqec_search/render.py`
- Create: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Write end-to-end CLI tests with fake rsinter**

Create `tests/test_search_eval_cli.py`:

```python
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_eval_tree(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")
    return work_root


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _env_with_fake_rsinter(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    rsinter = bin_dir / "rsinter"
    rsinter.write_text(
        "#!" + sys.executable + "\n"
        + """import json
import sys
from pathlib import Path

if sys.argv[1:] == ["--version"]:
    print("rsinter 0.1.1")
    raise SystemExit(0)

out_dir = Path(sys.argv[sys.argv.index("--out") + 1])
runner_dir = out_dir / "rmatching-default-v1" / "test-run"
runner_dir.mkdir(parents=True, exist_ok=True)
(runner_dir / "results.jsonl").write_text(
    json.dumps(
        {
            "decoder_id": "rmatching-default-v1",
            "task_id": "rotated-memory-x-cdep-v1",
            "p": 0.005,
            "rounds": 3,
            "shots": 1000,
            "errors": 5,
            "seconds": 1.25,
        },
        sort_keys=True,
    )
    + "\\n"
)
"""
    )
    rsinter.chmod(rsinter.stat().st_mode | stat.S_IXUSR)
    return {
        **os.environ,
        "PATH": str(bin_dir),
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }


def test_eval_campaign_distance_writes_fresh_real_run(tmp_path: Path) -> None:
    work_root = _copy_eval_tree(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "eval",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--distance",
            "3",
            "--decoder",
            "rmatching-default-v1",
            "--p",
            "0.005",
            "--run-id",
            "test-eval",
        ],
        capture_output=True,
        text=True,
        env=_env_with_fake_rsinter(tmp_path),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "evaluated candidate rotated-surface-d3-example" in result.stdout

    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "test-eval"
    candidate_root = run_root / "candidates" / "rotated-surface-d3-example"
    assert _load_json(run_root / "run_spec.json")["mode"] == "eval"
    assert _load_json(candidate_root / "candidate.json")["status"] == "evaluated"
    assert _load_json(candidate_root / "structure.json")["css_commute"] is True
    assert _load_json(candidate_root / "structure.json")["k"] == 1
    assert _load_json(candidate_root / "distance.json")["distance"] == 3
    manifest = _load_json(
        candidate_root
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    assert manifest["status"] == "completed"
    assert manifest["points"][0]["ler"] == 0.005
    assert (candidate_root / "candidate-plot.svg").is_file()
    assert (candidate_root / "rsinter" / "spec.toml").is_file()
    assert (
        candidate_root
        / "rsinter"
        / "out"
        / "rmatching-default-v1"
        / "test-run"
        / "results.jsonl"
    ).is_file()


def test_eval_fails_when_rsinter_is_missing(tmp_path: Path) -> None:
    work_root = _copy_eval_tree(tmp_path)
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env = {
        **os.environ,
        "PATH": str(empty_bin),
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "eval",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--distance",
            "3",
            "--run-id",
            "missing-rsinter",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "rsinter not found on PATH" in result.stderr
    assert not (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "missing-rsinter"
    ).exists()


def test_eval_rejects_invalid_decoder_before_rsinter(tmp_path: Path) -> None:
    work_root = _copy_eval_tree(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "eval",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--distance",
            "3",
            "--decoder",
            "missing-decoder",
            "--run-id",
            "bad-filter",
        ],
        capture_output=True,
        text=True,
        env=_env_with_fake_rsinter(tmp_path),
    )

    assert result.returncode == 1
    assert "decoder filter not in suite" in result.stderr


def test_eval_candidate_dir_uses_external_candidate_id(tmp_path: Path) -> None:
    work_root = _copy_eval_tree(tmp_path)
    source = tmp_path / "candidate-dir"
    source.mkdir()
    (source / "candidate.json").write_text(
        json.dumps(
            {
                "candidate_id": "external-d3",
                "campaign_id": "rotated-surface-baseline",
                "run_id": "source-run",
                "code_family": "rotated-surface-code",
                "parameters": {"distance": 3, "layout": "rotated"},
                "provenance": {"kind": "external", "label": "tmp"},
                "status": "evaluated",
            },
            indent=2,
        )
        + "\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "eval",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--candidate",
            str(source),
            "--decoder",
            "rmatching-default-v1",
            "--p",
            "0.005",
            "--run-id",
            "candidate-dir-eval",
        ],
        capture_output=True,
        text=True,
        env=_env_with_fake_rsinter(tmp_path),
    )

    assert result.returncode == 0, result.stderr + result.stdout
    candidate_root = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "candidate-dir-eval"
        / "candidates"
        / "external-d3"
    )
    assert _load_json(candidate_root / "candidate.json")["candidate_id"] == "external-d3"
```

- [ ] **Step 2: Run the new CLI tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_eval_cli.py -v
```

Expected: FAIL because the `eval` subcommand does not exist.

- [ ] **Step 3: Add eval summary and leaderboard helpers**

In `src/autoqec_search/render.py`, append:

```python

def render_eval_leaderboard(manifests: list[dict]) -> str:
    lines = ["candidate_id,task_id,decoder_id,p,shots,errors,ler,ci_low,ci_high,status"]
    for manifest in manifests:
        for point in manifest["points"]:
            lines.append(
                ",".join(
                    [
                        manifest["candidate_id"],
                        manifest["task_id"],
                        manifest["decoder_id"],
                        str(point["p"]),
                        str(point["shots"]),
                        str(point["errors"]),
                        str(point["ler"]),
                        str(point["ci_low"]),
                        str(point["ci_high"]),
                        manifest["status"],
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def render_eval_summary(
    *,
    campaign_id: str,
    run_id: str,
    candidate_id: str,
    task_ids: list[str],
    decoder_ids: list[str],
    structure: dict,
    distance: int,
) -> str:
    lines = [
        "# Search Eval Summary",
        "",
        f"- campaign: `{campaign_id}`",
        f"- run: `{run_id}`",
        f"- candidate: `{candidate_id}`",
        f"- distance: `{distance}`",
        f"- n: `{structure['n']}`",
        f"- k: `{structure['k']}`",
        f"- css_commute: `{str(structure['css_commute']).lower()}`",
        "",
        "## Tasks",
        "",
    ]
    lines.extend(f"- `{task_id}`" for task_id in task_ids)
    lines.extend(["", "## Decoders", ""])
    lines.extend(f"- `{decoder_id}`" for decoder_id in decoder_ids)
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Implement `eval_run.py`**

Create `src/autoqec_search/eval_run.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from autoqec_search import __version__
from autoqec_search.eval_candidates import (
    candidate_payload,
    copy_candidate_artifacts,
    resolve_campaign_candidate,
    resolve_directory_candidate,
)
from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.plot import render_candidate_plot
from autoqec_search.render import render_eval_leaderboard, render_eval_summary
from autoqec_search.rsinter import (
    build_completed_manifest,
    parse_decoder_filter,
    parse_p_filter,
    parse_results_jsonl,
    require_rsinter,
    rounds_for_task,
    run_rsinter,
    validate_selected_decoders,
    validate_selected_p_values,
    write_spec_toml,
)
from autoqec_search.structure import summarize_css_structure


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _default_run_id(timestamp: str) -> str:
    return timestamp.replace("-", "").replace(":", "").replace("T", "T").removesuffix("Z") + "Z-eval"


def _validate_run_id(run_id: str) -> None:
    run_path = Path(run_id)
    if (
        not run_id
        or "/" in run_id
        or "\\" in run_id
        or run_path.name != run_id
        or run_path != Path(run_path.name)
        or run_id in {".", ".."}
    ):
        raise SearchIntegrityError(f"run_id must be a single path segment: {run_id}")


def evaluate_single_candidate(
    *,
    root: Path,
    campaign_id: str,
    distance: int | None,
    candidate_dir: Path | None,
    decoder_filters: list[str] | None,
    p_filters: list[str] | None,
    run_id: str | None,
    force: bool,
) -> Path:
    workspace = load_search_workspace(root)
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")
    campaign = workspace.campaigns[campaign_id]
    suite = workspace.suites[campaign["default_suite_id"]]
    task_id = suite["task_ids"][0]
    task = workspace.tasks[task_id]

    selected_decoder_ids = validate_selected_decoders(
        suite, parse_decoder_filter(decoder_filters)
    )
    selected_p_values = validate_selected_p_values(task, parse_p_filter(p_filters))

    if candidate_dir is not None:
        candidate = resolve_directory_candidate(root, candidate_dir, campaign_id=campaign_id)
    else:
        if distance is None:
            raise SearchIntegrityError("missing required --distance for campaign eval")
        candidate = resolve_campaign_candidate(
            root, workspace, campaign_id=campaign_id, distance=distance
        )

    resolved_distance = int(candidate.instance["derived_properties"]["distance"])
    rounds = rounds_for_task(task, distance=resolved_distance)
    rsinter_executable, rsinter_version = require_rsinter()

    created_at = _now_timestamp()
    actual_run_id = run_id or _default_run_id(created_at)
    _validate_run_id(actual_run_id)
    run_root = root / "results" / "search" / campaign_id / actual_run_id
    if run_root.exists():
        if not force:
            raise SearchIntegrityError(f"run already exists: {run_root}")
        shutil.rmtree(run_root)

    candidate_root = run_root / "candidates" / candidate.spec.candidate_id
    run_spec = {
        "campaign_id": campaign_id,
        "run_id": actual_run_id,
        "suite_id": suite["id"],
        "task_ids": [task_id],
        "decoder_ids": selected_decoder_ids,
        "candidate_ids": [candidate.spec.candidate_id],
        "created_at": created_at,
        "mode": "eval",
    }
    _write_json(run_root / "run_spec.json", run_spec)
    _write_json(
        run_root / "env.json",
        {
            "tool": "autoqec-search",
            "version": __version__,
            "generated_at": created_at,
            "mode": "eval",
        },
    )
    _write_json(run_root / "frontier.json", {"campaign_id": campaign_id, "run_id": actual_run_id, "items": []})
    _write_json(candidate_root / "candidate.json", candidate_payload(candidate, actual_run_id))
    copy_candidate_artifacts(candidate, candidate_root)

    structure = summarize_css_structure(candidate.hx, candidate.hz)
    _write_json(candidate_root / "structure.json", structure)
    if not structure["css_commute"]:
        raise SearchIntegrityError("CSS commutation failed")

    spec_path = candidate_root / "rsinter" / "spec.toml"
    out_dir = candidate_root / "rsinter" / "out"
    write_spec_toml(
        spec_path,
        task=task,
        decoders=workspace.decoders,
        selected_decoder_ids=selected_decoder_ids,
        distance=resolved_distance,
        rounds=rounds,
        p_values=selected_p_values,
    )
    run_rsinter(spec_path, out_dir, executable=rsinter_executable)

    manifests: list[dict] = []
    tool_revisions = {"rsinter": rsinter_version, "autoqec_search": __version__}
    for decoder_id in selected_decoder_ids:
        results_path = out_dir / decoder_id / "test-run" / "results.jsonl"
        if not results_path.is_file():
            raise SearchIntegrityError(f"missing rsinter results: {results_path}")
        points = parse_results_jsonl(
            results_path,
            expected_decoder_id=decoder_id,
            expected_task_id=task_id,
            expected_p_values=selected_p_values,
        )
        manifest = build_completed_manifest(
            campaign_id=campaign_id,
            run_id=actual_run_id,
            candidate_id=candidate.spec.candidate_id,
            task_id=task_id,
            decoder_id=decoder_id,
            created_at=created_at,
            tool_revisions=tool_revisions,
            points=points,
        )
        _write_json(
            candidate_root / "evaluations" / task_id / decoder_id / "manifest.json",
            manifest,
        )
        manifests.append(manifest)

    _write_text(run_root / "leaderboard.csv", render_eval_leaderboard(manifests))
    _write_text(
        run_root / "summary.md",
        render_eval_summary(
            campaign_id=campaign_id,
            run_id=actual_run_id,
            candidate_id=candidate.spec.candidate_id,
            task_ids=[task_id],
            decoder_ids=selected_decoder_ids,
            structure=structure,
            distance=resolved_distance,
        ),
    )
    _write_text(
        candidate_root / "candidate-plot.svg",
        render_candidate_plot(
            candidate_id=candidate.spec.candidate_id,
            distance=resolved_distance,
            task_id=task_id,
            generated_at=created_at,
            manifests=manifests,
        ),
    )
    return run_root
```

- [ ] **Step 5: Add `eval` to the CLI**

In `src/autoqec_search/cli.py`, add this import:

```python
from autoqec_search.eval_run import evaluate_single_candidate
```

In `build_parser()`, add:

```python
    eval_parser = subparsers.add_parser(
        "eval", help="Evaluate one candidate through rsinter"
    )
    eval_parser.add_argument("--root", default=".")
    eval_parser.add_argument("--campaign", required=True)
    eval_parser.add_argument("--distance", type=int, default=None)
    eval_parser.add_argument("--candidate", default=None)
    eval_parser.add_argument("--decoder", action="append", default=None)
    eval_parser.add_argument("--p", action="append", default=None)
    eval_parser.add_argument("--run-id", default=None)
    eval_parser.add_argument("--force", action="store_true")
```

In `main()`, add this branch before `show`:

```python
        if args.command == "eval":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = evaluate_single_candidate(
                root=root,
                campaign_id=args.campaign,
                distance=args.distance,
                candidate_dir=Path(args.candidate) if args.candidate else None,
                decoder_filters=args.decoder,
                p_filters=args.p,
                run_id=args.run_id,
                force=args.force,
            )
            candidate_ids = sorted(
                path.name for path in (run_root / "candidates").iterdir() if path.is_dir()
            )
            print(f"evaluated candidate {candidate_ids[0]} at {run_root}")
            return 0
```

- [ ] **Step 6: Run CLI eval tests**

Run:

```bash
python3 -m pytest tests/test_search_eval_cli.py -v
```

Expected: PASS.

- [ ] **Step 7: Run broader search tests**

Run:

```bash
python3 -m pytest tests/test_search_eval_schemas.py tests/test_search_structure.py tests/test_search_eval_candidates.py tests/test_search_rsinter.py tests/test_search_plot.py tests/test_search_eval_cli.py tests/test_search_cli.py tests/test_search_load.py tests/test_search_init_run.py tests/test_search_preflight.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/autoqec_search/eval_run.py src/autoqec_search/cli.py src/autoqec_search/render.py tests/test_search_eval_cli.py
git commit -m "feat: add single-candidate eval command"
```

---

### Task 7: Document Eval Workflow And Run Final Verification

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Test: `tests/test_search_docs.py`

- [ ] **Step 1: Add documentation assertions**

In `tests/test_search_docs.py`, add:

```python

def test_docs_mention_single_candidate_eval_command() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "autoqec-search eval" in readme
    assert "--campaign rotated-surface-baseline --distance 3" in readme
    assert "rsinter" in readme
    assert "autoqec-search eval" in claude
    assert "strictly requires `rsinter`" in claude
```

- [ ] **Step 2: Run the docs test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_search_docs.py::test_docs_mention_single_candidate_eval_command -v
```

Expected: FAIL because the docs do not mention the eval command yet.

- [ ] **Step 3: Update `README.md`**

In the Search Layer section after the preflight commands, add this Markdown block:

````markdown
Evaluate one rotated-surface candidate through the real `rsinter` backend with:

```bash
python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id local-rotated-d3-eval
```

The eval command creates a fresh run under `results/search/<campaign>/<run-id>/`, reuses matching Zoo instance artifacts when present, writes `structure.json`, `distance.json`, completed per-decoder manifests, and `candidate-plot.svg`. It strictly requires `rsinter` on `PATH`; missing `rsinter` is a hard failure.
````

- [ ] **Step 4: Update `CLAUDE.md`**

In the Search Layer section after the preflight guidance, add this Markdown block:

````markdown
For issue `#9` and single-candidate evaluation work, use:

```sh
python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.005
```

This command strictly requires `rsinter` on `PATH`, creates a fresh eval run, reuses matching Zoo instance artifacts, copies recorded distance from the instance, invokes `rsinter`, and writes `candidate-plot.svg`.
````

- [ ] **Step 5: Run docs and full test suite**

Run:

```bash
python3 -m pytest
```

Expected: PASS.

- [ ] **Step 6: Run the eval smoke command with fake `rsinter` through pytest**

Run:

```bash
python3 -m pytest tests/test_search_eval_cli.py::test_eval_campaign_distance_writes_fresh_real_run -v
```

Expected: PASS and generated temp-run artifacts include `candidate-plot.svg`.

- [ ] **Step 7: Optional local backend verification**

Only run this command when `rsinter` is installed locally:

```bash
python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id local-rotated-d3-eval
```

Expected: exit 0, `structure.json` reports `n=9`, `k=1`, `css_commute=true`, `distance.json` reports `3`, and the completed manifest LER lies inside the CI band in `benchmarks/fixtures/rotated-d3/expected.json`.

- [ ] **Step 8: Commit**

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: document single-candidate eval workflow"
```

---

## Final Checks

Run these before handing back the implementation:

```bash
python3 -m pytest
python3 -m autoqec_search.cli validate --root .
python3 -m autoqec_search.cli preflight --root .
```

Expected:

- `python3 -m pytest` passes.
- `validate` passes.
- `preflight` passes only when `rsinter` is installed; if `rsinter` is not installed, report that limitation explicitly and include the passing test evidence from fake-rsinter coverage.

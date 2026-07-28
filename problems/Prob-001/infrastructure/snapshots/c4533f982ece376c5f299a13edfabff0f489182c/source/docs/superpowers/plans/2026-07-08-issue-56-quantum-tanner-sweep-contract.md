# Issue 56 Quantum Tanner Sweep Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested quantum Tanner toric sweep configuration validator and CLI summary command.

**Architecture:** A new `autoqec_search.quantum_tanner_generator` module owns the source sweep contract, path and distance validation, normalized dataclasses, and summary rendering. `autoqec_search.cli` exposes a thin `validate-quantum-tanner-sweep --config` command that delegates to the module and uses the existing `SearchIntegrityError` error path.

**Tech Stack:** Python 3.14, stdlib `dataclasses`, `json`, `pathlib`, existing `pytest` and CLI subprocess test style.

## Global Constraints

- Parser/validator module path is `src/autoqec_search/quantum_tanner_generator.py`.
- CLI command name is `validate-quantum-tanner-sweep`.
- CLI option is `--config <path>`.
- Required config fields are `campaign_id`, `distances`, `code_id`, `output_root`, `spec_root`, `instance_root`, `catalog_path`, `search_space_path`, and `expected_bound_type`.
- Optional `qec_code_bin` defaults to `qec-code`.
- Reject absolute paths, `..` path traversal, empty/current-directory paths, duplicate distances, non-integer distances, bool distances, and `distance < 2`.
- Sort distances only after duplicate validation.
- Deterministic candidate ids are `quantum-tanner-toric-d<distance>`.
- Valid `expected_bound_type` values are `exact` and `upper`.
- Do not generate matrices, call `qec-code`, write catalog files, write search-space files, or edit existing generated quantum Tanner artifacts.
- Include one minimal valid JSON fixture for reproducible CLI validation.

---

## File Structure

- Create `src/autoqec_search/quantum_tanner_generator.py`: load/validate/normalize the sweep config and render a summary.
- Modify `src/autoqec_search/cli.py`: import the new helpers, add the parser subcommand, and handle the command.
- Create `tests/fixtures/quantum_tanner_sweep/good.json`: minimal valid fixture.
- Create `tests/test_search_quantum_tanner_generator.py`: TDD coverage for normalization and CLI success/failure.

### Task 1: Quantum Tanner Sweep Contract And CLI

**Files:**
- Create: `src/autoqec_search/quantum_tanner_generator.py`
- Modify: `src/autoqec_search/cli.py`
- Create: `tests/fixtures/quantum_tanner_sweep/good.json`
- Create: `tests/test_search_quantum_tanner_generator.py`

**Interfaces:**
- Consumes: JSON config files with required fields listed in Global Constraints.
- Produces: `load_quantum_tanner_sweep_config(config_path: Path) -> QuantumTannerSweepConfig`.
- Produces: `normalize_quantum_tanner_sweep_config(payload: object, *, config_path: Path | None = None) -> QuantumTannerSweepConfig`.
- Produces: `render_quantum_tanner_sweep_summary(config: QuantumTannerSweepConfig) -> str`.
- Produces CLI: `python3 -m autoqec_search.cli validate-quantum-tanner-sweep --config <path>`.

- [ ] **Step 1: Add the valid JSON fixture**

Create `tests/fixtures/quantum_tanner_sweep/good.json`:

```json
{
  "campaign_id": "quantum-tanner-autoresearch",
  "distances": [4, 6],
  "code_id": "quantum-tanner-code",
  "output_root": "campaigns/examples/quantum-tanner-autoresearch/generated",
  "spec_root": "campaigns/examples/quantum-tanner-autoresearch/generated/quantum_tanner_specs",
  "instance_root": "benchmarks/distance_ladders/generated-quantum-tanner/instances",
  "catalog_path": "campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json",
  "search_space_path": "campaigns/examples/quantum-tanner-autoresearch/generated_search_space.json",
  "expected_bound_type": "exact"
}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_search_quantum_tanner_generator.py`:

```python
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_generator import (
    load_quantum_tanner_sweep_config,
    normalize_quantum_tanner_sweep_config,
    render_quantum_tanner_sweep_summary,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "quantum_tanner_sweep" / "good.json"


def _payload(**updates: object) -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text())
    payload.update(updates)
    return payload


def _write_config(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _run_cli(config_path: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate-quantum-tanner-sweep",
            "--config",
            str(config_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def test_valid_sweep_config_normalizes_distances_and_candidate_paths() -> None:
    config = load_quantum_tanner_sweep_config(FIXTURE)

    assert config.campaign_id == "quantum-tanner-autoresearch"
    assert config.code_id == "quantum-tanner-code"
    assert config.distances == (4, 6)
    assert config.output_root == Path("campaigns/examples/quantum-tanner-autoresearch/generated")
    assert config.spec_root == Path(
        "campaigns/examples/quantum-tanner-autoresearch/generated/quantum_tanner_specs"
    )
    assert config.instance_root == Path(
        "benchmarks/distance_ladders/generated-quantum-tanner/instances"
    )
    assert config.catalog_path == Path(
        "campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json"
    )
    assert config.search_space_path == Path(
        "campaigns/examples/quantum-tanner-autoresearch/generated_search_space.json"
    )
    assert config.expected_bound_type == "exact"
    assert config.qec_code_bin == "qec-code"
    assert [candidate.candidate_id for candidate in config.candidates] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]

    d4 = config.candidates[0]
    assert d4.distance == 4
    assert d4.qec_code_spec == "quantum_tanner:toric_d4"
    assert d4.quantum_tanner_spec_path == Path(
        "campaigns/examples/quantum-tanner-autoresearch/generated/quantum_tanner_specs/toric-d4.json"
    )
    assert d4.instance_dir == Path(
        "benchmarks/distance_ladders/generated-quantum-tanner/instances/quantum-tanner-toric-d4"
    )
    assert d4.instance_path == d4.instance_dir / "instance.json"
    assert d4.hx_path == d4.instance_dir / "hx.json"
    assert d4.hz_path == d4.instance_dir / "hz.json"


def test_distances_are_sorted_but_duplicates_are_rejected() -> None:
    config = normalize_quantum_tanner_sweep_config(_payload(distances=[6, 4]))
    assert config.distances == (4, 6)
    assert [candidate.candidate_id for candidate in config.candidates] == [
        "quantum-tanner-toric-d4",
        "quantum-tanner-toric-d6",
    ]

    with pytest.raises(SearchIntegrityError, match="distances"):
        normalize_quantum_tanner_sweep_config(_payload(distances=[4, 4]))


@pytest.mark.parametrize("distances", [[4.0], ["4"], [True], [1]])
def test_invalid_distances_report_distances_field(distances: list[object]) -> None:
    with pytest.raises(SearchIntegrityError, match="distances"):
        normalize_quantum_tanner_sweep_config(_payload(distances=distances))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("catalog_path", "../outside/fixture_catalog.json"),
        ("spec_root", "/tmp/specs"),
        ("instance_root", ""),
        ("search_space_path", "."),
    ],
)
def test_unsafe_paths_report_the_invalid_field(field: str, value: str) -> None:
    with pytest.raises(SearchIntegrityError, match=field):
        normalize_quantum_tanner_sweep_config(_payload(**{field: value}))


def test_summary_lists_exactly_normalized_candidate_ids() -> None:
    summary = render_quantum_tanner_sweep_summary(load_quantum_tanner_sweep_config(FIXTURE))

    assert "validated quantum Tanner sweep: quantum-tanner-autoresearch" in summary
    assert "quantum-tanner-toric-d4" in summary
    assert "quantum-tanner-toric-d6" in summary
    assert "quantum-tanner-toric-d8" not in summary


def test_cli_validates_fixture_and_prints_candidate_summary() -> None:
    result = _run_cli(FIXTURE)

    assert result.returncode == 0, result.stderr
    assert "quantum-tanner-toric-d4" in result.stdout
    assert "quantum-tanner-toric-d6" in result.stdout
    assert "quantum-tanner-toric-d8" not in result.stdout


def test_cli_rejects_duplicate_distances_and_unsafe_path(tmp_path: Path) -> None:
    duplicate = _write_config(tmp_path / "duplicate.json", _payload(distances=[4, 4]))
    duplicate_result = _run_cli(duplicate)
    assert duplicate_result.returncode == 1
    assert "distances" in duplicate_result.stderr

    unsafe = _write_config(
        tmp_path / "unsafe.json",
        _payload(catalog_path="../outside/fixture_catalog.json"),
    )
    unsafe_result = _run_cli(unsafe)
    assert unsafe_result.returncode == 1
    assert "catalog_path" in unsafe_result.stderr
```

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
```

Expected: FAIL because `autoqec_search.quantum_tanner_generator` does not exist.

- [ ] **Step 4: Implement `quantum_tanner_generator.py`**

Create `src/autoqec_search/quantum_tanner_generator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError


DEFAULT_QEC_CODE_BIN = "qec-code"
VALID_EXPECTED_BOUND_TYPES = {"exact", "upper"}


@dataclass(frozen=True)
class QuantumTannerSweepCandidate:
    distance: int
    candidate_id: str
    qec_code_spec: str
    quantum_tanner_spec_path: Path
    instance_dir: Path
    instance_path: Path
    hx_path: Path
    hz_path: Path


@dataclass(frozen=True)
class QuantumTannerSweepConfig:
    campaign_id: str
    distances: tuple[int, ...]
    code_id: str
    output_root: Path
    spec_root: Path
    instance_root: Path
    catalog_path: Path
    search_space_path: Path
    expected_bound_type: str
    qec_code_bin: str
    candidates: tuple[QuantumTannerSweepCandidate, ...]
    config_path: Path | None = None


def _require_object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SearchIntegrityError("quantum_tanner_sweep config must be an object")
    return payload


def _require_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"{field} must be a non-empty string")
    return value


def _safe_repo_relative_path(payload: dict[str, Any], field: str) -> Path:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"{field} must be a safe repository-relative path")
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or str(path) == "."
        or any(part == ".." for part in path.parts)
    ):
        raise SearchIntegrityError(f"{field} must be a safe repository-relative path: {value}")
    return path


def _normalize_distances(payload: dict[str, Any]) -> tuple[int, ...]:
    distances = payload.get("distances")
    if not isinstance(distances, list) or not distances:
        raise SearchIntegrityError("distances must be a non-empty list")
    seen: set[int] = set()
    normalized: list[int] = []
    for value in distances:
        if type(value) is not int:
            raise SearchIntegrityError("distances must contain only integers")
        if value < 2:
            raise SearchIntegrityError("distances must be >= 2")
        if value in seen:
            raise SearchIntegrityError(f"distances must be unique: duplicate {value}")
        seen.add(value)
        normalized.append(value)
    return tuple(sorted(normalized))


def _candidate_for_distance(
    distance: int,
    *,
    spec_root: Path,
    instance_root: Path,
) -> QuantumTannerSweepCandidate:
    candidate_id = f"quantum-tanner-toric-d{distance}"
    instance_dir = instance_root / candidate_id
    return QuantumTannerSweepCandidate(
        distance=distance,
        candidate_id=candidate_id,
        qec_code_spec=f"quantum_tanner:toric_d{distance}",
        quantum_tanner_spec_path=spec_root / f"toric-d{distance}.json",
        instance_dir=instance_dir,
        instance_path=instance_dir / "instance.json",
        hx_path=instance_dir / "hx.json",
        hz_path=instance_dir / "hz.json",
    )


def normalize_quantum_tanner_sweep_config(
    payload: Any,
    *,
    config_path: Path | None = None,
) -> QuantumTannerSweepConfig:
    payload = _require_object(payload)
    campaign_id = _require_string(payload, "campaign_id")
    code_id = _require_string(payload, "code_id")
    output_root = _safe_repo_relative_path(payload, "output_root")
    spec_root = _safe_repo_relative_path(payload, "spec_root")
    instance_root = _safe_repo_relative_path(payload, "instance_root")
    catalog_path = _safe_repo_relative_path(payload, "catalog_path")
    search_space_path = _safe_repo_relative_path(payload, "search_space_path")
    expected_bound_type = _require_string(payload, "expected_bound_type")
    if expected_bound_type not in VALID_EXPECTED_BOUND_TYPES:
        raise SearchIntegrityError(
            "expected_bound_type must be one of: "
            + ", ".join(sorted(VALID_EXPECTED_BOUND_TYPES))
        )
    qec_code_bin = payload.get("qec_code_bin", DEFAULT_QEC_CODE_BIN)
    if not isinstance(qec_code_bin, str) or not qec_code_bin:
        raise SearchIntegrityError("qec_code_bin must be a non-empty string")
    distances = _normalize_distances(payload)
    candidates = tuple(
        _candidate_for_distance(
            distance,
            spec_root=spec_root,
            instance_root=instance_root,
        )
        for distance in distances
    )
    return QuantumTannerSweepConfig(
        campaign_id=campaign_id,
        distances=distances,
        code_id=code_id,
        output_root=output_root,
        spec_root=spec_root,
        instance_root=instance_root,
        catalog_path=catalog_path,
        search_space_path=search_space_path,
        expected_bound_type=expected_bound_type,
        qec_code_bin=qec_code_bin,
        candidates=candidates,
        config_path=config_path,
    )


def load_quantum_tanner_sweep_config(config_path: Path) -> QuantumTannerSweepConfig:
    payload = json.loads(config_path.read_text())
    return normalize_quantum_tanner_sweep_config(payload, config_path=config_path)


def render_quantum_tanner_sweep_summary(config: QuantumTannerSweepConfig) -> str:
    lines = [
        f"validated quantum Tanner sweep: {config.campaign_id}",
        f"code_id: {config.code_id}",
        "distances: " + ", ".join(str(distance) for distance in config.distances),
        f"output_root: {config.output_root}",
        f"spec_root: {config.spec_root}",
        f"instance_root: {config.instance_root}",
        f"catalog_path: {config.catalog_path}",
        f"search_space_path: {config.search_space_path}",
        f"expected_bound_type: {config.expected_bound_type}",
        f"qec_code_bin: {config.qec_code_bin}",
        "candidates:",
    ]
    for candidate in config.candidates:
        lines.extend(
            [
                f"- {candidate.candidate_id}",
                f"  distance: {candidate.distance}",
                f"  qec_code_spec: {candidate.qec_code_spec}",
                f"  quantum_tanner_spec_path: {candidate.quantum_tanner_spec_path}",
                f"  instance_path: {candidate.instance_path}",
                f"  hx_path: {candidate.hx_path}",
                f"  hz_path: {candidate.hz_path}",
            ]
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Wire the CLI command**

Modify `src/autoqec_search/cli.py` imports:

```python
from autoqec_search.quantum_tanner_generator import (
    load_quantum_tanner_sweep_config,
    render_quantum_tanner_sweep_summary,
)
```

Add this parser in `build_parser()` near the other validation commands:

```python
    validate_qt_sweep_parser = subparsers.add_parser(
        "validate-quantum-tanner-sweep",
        help="Validate a generated quantum Tanner toric sweep config",
    )
    validate_qt_sweep_parser.add_argument("--config", required=True)
```

Add this branch in `main()`:

```python
        if args.command == "validate-quantum-tanner-sweep":
            config = load_quantum_tanner_sweep_config(Path(args.config))
            print(render_quantum_tanner_sweep_summary(config), end="")
            return 0
```

- [ ] **Step 6: Run focused tests to verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
```

Expected: PASS.

- [ ] **Step 7: Run issue verification commands**

Create `/tmp/qt-sweep-good.json` with the fixture payload and run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-sweep --config /tmp/qt-sweep-good.json
```

Expected: exit 0; stdout contains `quantum-tanner-toric-d4` and
`quantum-tanner-toric-d6`, and does not contain `quantum-tanner-toric-d8`.

Create `/tmp/qt-sweep-bad.json` with duplicate distances and run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-sweep --config /tmp/qt-sweep-bad.json
```

Expected: nonzero; stderr contains `distances`.

Create `/tmp/qt-sweep-unsafe.json` with
`"catalog_path": "../outside/fixture_catalog.json"` and run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-sweep --config /tmp/qt-sweep-unsafe.json
```

Expected: nonzero; stderr contains `catalog_path`.

- [ ] **Step 8: Run the full project test suite**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```bash
git add src/autoqec_search/quantum_tanner_generator.py src/autoqec_search/cli.py tests/fixtures/quantum_tanner_sweep/good.json tests/test_search_quantum_tanner_generator.py docs/superpowers/specs/2026-07-08-issue-56-quantum-tanner-sweep-contract-design.md docs/superpowers/plans/2026-07-08-issue-56-quantum-tanner-sweep-contract.md
git commit -m "Implement #56 quantum Tanner sweep contract"
```

## Self-Review

Spec coverage is complete: the plan defines the module, CLI, validation rules,
candidate ids, safe paths, fixture, positive CLI command, and negative controls.
No placeholder instructions remain. Function names and types match across the
task and CLI wiring steps.

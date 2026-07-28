# Issue #12 Zoo Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `autoqec-search promote` and automatic autoresearch finalization that copies rule-accepted candidates into `zoo/` and rebuilds the browse artifacts.

**Architecture:** Implement a focused `autoqec_search.promote` module for rules, evaluation, safe copy, summary writing, and Zoo rebuild. Keep `autoqec_zoo.build` pure, wire `cli.py` and `run_loop.py` as thin callers, and verify behavior with fake-`rsinter` integration tests.

**Tech Stack:** Python 3.11, argparse, jsonschema, pytest, temporary git repositories, existing `autoqec_search` and `autoqec_zoo` packages.

---

## File Structure

- Create `benchmarks/schemas/promote-rules.schema.json`: strict JSON schema for `min_distance`, `max_ler_at_p`, and `require_distance_verified`.
- Create `campaigns/examples/rotated-surface-baseline/promote_rules.json`: example campaign policy used by integration tests and docs.
- Create `src/autoqec_search/promote.py`: rule loading, candidate evaluation, promoted instance payload rewrite, safe instance install, Zoo rebuild, and summary rendering.
- Modify `src/autoqec_search/cli.py`: add `promote` subcommand and connect CLI errors to existing `SearchIntegrityError` handling.
- Modify `src/autoqec_search/run_loop.py`: call promotion during finalization before the final commit.
- Create `tests/test_search_promote.py`: focused schema, evaluator, payload, overwrite, and CLI tests.
- Modify `tests/test_search_run_cli.py`: add autoresearch integration checks for promotion with rules and skip summary without rules.
- Modify `tests/test_search_docs.py`: assert docs mention the new command and automatic promotion behavior.
- Modify `README.md` and `CLAUDE.md`: document `promote_rules.json`, `autoqec-search promote`, run finalization, and overwrite safety.

## Task 1: Rules Schema And Rule Loading

**Files:**
- Create: `benchmarks/schemas/promote-rules.schema.json`
- Create: `campaigns/examples/rotated-surface-baseline/promote_rules.json`
- Create: `src/autoqec_search/promote.py`
- Test: `tests/test_search_promote.py`

- [ ] **Step 1: Write failing schema and rule-loading tests**

Create `tests/test_search_promote.py` with these initial tests and helpers:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from autoqec_search.load import SearchIntegrityError
from autoqec_search.promote import load_promote_rules


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _copy_search_tree(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    shutil.copytree(REPO_ROOT / "zoo", work_root / "zoo")
    return work_root


def test_promote_rules_schema_accepts_documented_shape() -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "promote-rules.schema.json")
    Draft202012Validator(schema).validate(
        {
            "min_distance": 3,
            "max_ler_at_p": {"p": 0.005, "ler": 0.5},
            "require_distance_verified": True,
        }
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"min_distance": 0},
        {"max_ler_at_p": {"p": 0.0, "ler": 0.5}},
        {"max_ler_at_p": {"p": 0.005, "ler": 1.5}},
        {"require_distance_verified": "yes"},
        {"unexpected": True},
    ],
)
def test_promote_rules_schema_rejects_invalid_payloads(payload: dict) -> None:
    schema = _load_json(REPO_ROOT / "benchmarks" / "schemas" / "promote-rules.schema.json")
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(payload)


def test_load_promote_rules_uses_campaign_sibling_file(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"

    loaded = load_promote_rules(work_root, run_root, rules_path=None)

    assert loaded is not None
    assert loaded.path == (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    )
    assert loaded.rules["min_distance"] == 3
    assert loaded.rules["max_ler_at_p"] == {"p": 0.005, "ler": 0.5}
    assert loaded.rules["require_distance_verified"] is True


def test_load_promote_rules_accepts_explicit_override(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"
    override = tmp_path / "strict-rules.json"
    _write_json(override, {"min_distance": 5})

    loaded = load_promote_rules(work_root, run_root, rules_path=override)

    assert loaded is not None
    assert loaded.path == override
    assert loaded.rules == {"min_distance": 5, "require_distance_verified": True}


def test_load_promote_rules_returns_none_when_campaign_has_no_rules(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.unlink()
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"

    assert load_promote_rules(work_root, run_root, rules_path=None) is None


def test_load_promote_rules_rejects_invalid_rules_file(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    _write_json(rules, {"min_distance": 0})
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "2026-06-09-example"

    with pytest.raises(SearchIntegrityError, match="invalid promote rules"):
        load_promote_rules(work_root, run_root, rules_path=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_promote.py -q
```

Expected: FAIL because `benchmarks/schemas/promote-rules.schema.json`, `campaigns/examples/rotated-surface-baseline/promote_rules.json`, and `autoqec_search.promote` do not exist.

- [ ] **Step 3: Add the promote-rules schema**

Create `benchmarks/schemas/promote-rules.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "min_distance": {
      "type": "integer",
      "minimum": 1
    },
    "max_ler_at_p": {
      "type": "object",
      "additionalProperties": false,
      "required": ["p", "ler"],
      "properties": {
        "p": {
          "type": "number",
          "exclusiveMinimum": 0,
          "exclusiveMaximum": 1
        },
        "ler": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        }
      }
    },
    "require_distance_verified": {
      "type": "boolean",
      "default": true
    }
  }
}
```

- [ ] **Step 4: Add example campaign rules**

Create `campaigns/examples/rotated-surface-baseline/promote_rules.json`:

```json
{
  "max_ler_at_p": {
    "ler": 0.5,
    "p": 0.005
  },
  "min_distance": 3,
  "require_distance_verified": true
}
```

- [ ] **Step 5: Add minimal rule-loading implementation**

Create `src/autoqec_search/promote.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.load import SearchIntegrityError


@dataclass(frozen=True)
class LoadedPromoteRules:
    path: Path
    rules: dict[str, Any]


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def validate_path_segment(value: str, *, label: str) -> None:
    value_path = Path(value)
    if (
        not value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or "/" in value
        or "\\" in value
        or value_path.name != value
        or value_path != Path(value_path.name)
        or value in {".", ".."}
    ):
        raise SearchIntegrityError(f"{label} must be a single path segment: {value}")


def _run_spec(run_root: Path) -> dict[str, Any]:
    return _load_json(run_root / "run_spec.json", "run spec")


def _campaign_dir(root: Path, campaign_id: str) -> Path:
    for campaign_path in sorted((root / "campaigns").glob("**/campaign.json")):
        payload = _load_json(campaign_path, "campaign")
        if payload.get("id") == campaign_id:
            return campaign_path.parent
    raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")


def _normalize_rules(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.setdefault("require_distance_verified", True)
    return normalized


def _validate_rules(root: Path, rules_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    schema_path = root / "benchmarks" / "schemas" / "promote-rules.schema.json"
    schema = _load_json(schema_path, "promote rules schema")
    normalized = _normalize_rules(payload)
    try:
        Draft202012Validator(schema).validate(normalized)
    except ValidationError as exc:
        detail = exc.message
        if exc.json_path != "$":
            detail = f"{exc.json_path}: {detail}"
        raise SearchIntegrityError(f"invalid promote rules at {rules_path}: {detail}") from exc
    return normalized


def load_promote_rules(
    root: Path,
    run_root: Path,
    *,
    rules_path: Path | None,
) -> LoadedPromoteRules | None:
    root = root.resolve()
    run_root = run_root.resolve()
    run_spec = _run_spec(run_root)
    campaign_id = run_spec.get("campaign_id")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise SearchIntegrityError(f"invalid run campaign_id: {run_root / 'run_spec.json'}")
    validate_path_segment(campaign_id, label="campaign_id")

    if rules_path is None:
        candidate_path = _campaign_dir(root, campaign_id) / "promote_rules.json"
        if not candidate_path.exists():
            return None
        actual_rules_path = candidate_path
    else:
        actual_rules_path = rules_path if rules_path.is_absolute() else (Path.cwd() / rules_path)

    payload = _load_json(actual_rules_path, "promote rules")
    return LoadedPromoteRules(
        path=actual_rules_path,
        rules=_validate_rules(root, actual_rules_path, payload),
    )
```

- [ ] **Step 6: Run schema and rule-loading tests**

Run:

```bash
python3 -m pytest tests/test_search_promote.py -q
```

Expected: PASS for all tests in `tests/test_search_promote.py`.

- [ ] **Step 7: Commit**

```bash
git add benchmarks/schemas/promote-rules.schema.json campaigns/examples/rotated-surface-baseline/promote_rules.json src/autoqec_search/promote.py tests/test_search_promote.py
git commit -m "feat: add promote rules loading"
```

## Task 2: Candidate Evaluation And Instance Payload Rewrite

**Files:**
- Modify: `src/autoqec_search/promote.py`
- Test: `tests/test_search_promote.py`

- [ ] **Step 1: Add failing evaluator tests**

Append these helpers and tests to `tests/test_search_promote.py`:

```python
def _make_finished_run(tmp_path: Path, *, ler: float = 0.013) -> tuple[Path, Path]:
    work_root = _copy_search_tree(tmp_path)
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "finished"
    candidate_root = run_root / "candidates" / "rotated-surface-d3-example"
    artifact_source = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    artifact_root = candidate_root / "artifacts"
    artifact_root.mkdir(parents=True)
    for name in ("instance.json", "hx.json", "hz.json"):
        shutil.copyfile(artifact_source / name, artifact_root / name)

    _write_json(
        run_root / "run_spec.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "finished",
            "suite_id": "rotated-surface-baseline-v1",
            "task_ids": ["rotated-memory-x-cdep-v1"],
            "decoder_ids": ["rmatching-default-v1"],
            "candidate_ids": ["rotated-surface-d3-example"],
            "created_at": "2026-06-14T03:11:22Z",
            "mode": "autoresearch",
            "tag": "finished",
            "wall_clock_seconds": 90,
            "seed": 7,
        },
    )
    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "finished",
            "items": [
                {
                    "candidate_id": "rotated-surface-d3-example",
                    "distance": 3,
                    "decoder_id": "rmatching-default-v1",
                    "p": 0.005,
                    "ler": ler,
                    "manifest_path": (
                        "candidates/rotated-surface-d3-example/evaluations/"
                        "rotated-memory-x-cdep-v1/rmatching-default-v1/manifest.json"
                    ),
                }
            ],
        },
    )
    _write_json(
        candidate_root / "candidate.json",
        {
            "candidate_id": "rotated-surface-d3-example",
            "campaign_id": "rotated-surface-baseline",
            "run_id": "finished",
            "code_family": "rotated-surface-code",
            "parameters": {"distance": 3, "layout": "rotated"},
            "provenance": {"kind": "seed", "label": "repo-example"},
            "status": "evaluated",
        },
    )
    _write_json(
        candidate_root / "distance.json",
        {
            "status": "completed",
            "distance": 3,
            "method": "copied-from-zoo-instance",
            "source_instance_id": "rotated-surface-code-d3",
            "source_instance_path": str(artifact_source),
        },
    )
    _write_json(
        candidate_root / "evaluations" / "rotated-memory-x-cdep-v1" / "rmatching-default-v1" / "manifest.json",
        {
            "campaign_id": "rotated-surface-baseline",
            "run_id": "finished",
            "candidate_id": "rotated-surface-d3-example",
            "task_id": "rotated-memory-x-cdep-v1",
            "decoder_id": "rmatching-default-v1",
            "status": "completed",
            "created_at": "2026-06-14T03:11:22Z",
            "tool_revisions": {"autoqec_search": "0.1.0", "rsinter": "fake"},
            "points": [
                {
                    "p": 0.005,
                    "rounds": 3,
                    "shots": 1000,
                    "errors": int(round(ler * 1000)),
                    "ler": ler,
                    "ci_low": max(0.0, ler / 2),
                    "ci_high": min(1.0, ler * 2),
                    "seconds": 0.01,
                }
            ],
        },
    )
    return work_root, run_root


def test_evaluate_promotions_accepts_frontier_candidate_under_rules(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)

    decisions = evaluate_promotions(
        run_root,
        {
            "min_distance": 3,
            "max_ler_at_p": {"p": 0.005, "ler": 0.5},
            "require_distance_verified": True,
        },
    )

    assert [decision.status for decision in decisions] == ["promote"]
    assert decisions[0].candidate_id == "rotated-surface-d3-example"
    assert decisions[0].code_id == "rotated-surface-code"
    assert decisions[0].instance_payload["id"] == "rotated-surface-d3-example"
    assert decisions[0].instance_payload["derived_properties"]["distance"] == 3
    assert decisions[0].source_manifest_path.endswith("manifest.json")


def test_evaluate_promotions_skips_candidate_below_min_distance(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)

    decisions = evaluate_promotions(run_root, {"min_distance": 5, "require_distance_verified": True})

    assert [decision.status for decision in decisions] == ["skipped"]
    assert decisions[0].reason == "distance 3 is below min_distance 5"


def test_evaluate_promotions_skips_candidate_above_ler_limit(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path, ler=0.75)

    decisions = evaluate_promotions(
        run_root,
        {"max_ler_at_p": {"p": 0.005, "ler": 0.5}, "require_distance_verified": True},
    )

    assert [decision.status for decision in decisions] == ["skipped"]
    assert decisions[0].reason == "LER 0.75 at p=0.005 exceeds limit 0.5"


def test_evaluate_promotions_skips_when_ler_point_is_absent(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)

    decisions = evaluate_promotions(
        run_root,
        {"max_ler_at_p": {"p": 0.001, "ler": 0.5}, "require_distance_verified": True},
    )

    assert [decision.status for decision in decisions] == ["skipped"]
    assert decisions[0].reason == "missing LER point at p=0.001"


def test_evaluate_promotions_rejects_unverified_distance_when_required(tmp_path: Path) -> None:
    from autoqec_search.promote import evaluate_promotions

    _work_root, run_root = _make_finished_run(tmp_path)
    distance_path = run_root / "candidates" / "rotated-surface-d3-example" / "distance.json"
    distance = _load_json(distance_path)
    distance["status"] = "not-computed"
    _write_json(distance_path, distance)

    with pytest.raises(SearchIntegrityError, match="distance is not verified"):
        evaluate_promotions(run_root, {"min_distance": 3, "require_distance_verified": True})
```

- [ ] **Step 2: Run evaluator tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_promote.py -q
```

Expected: FAIL because `evaluate_promotions` and `PromotionDecision` do not exist.

- [ ] **Step 3: Implement promotion decisions and evaluation**

Append this code to `src/autoqec_search/promote.py`, below `load_promote_rules`:

```python
@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    status: str
    reason: str | None
    code_id: str | None
    target_instance_id: str | None
    source_manifest_path: str | None
    candidate_root: Path | None
    instance_payload: dict[str, Any] | None
    hx_payload: dict[str, Any] | None
    hz_payload: dict[str, Any] | None


def _frontier(run_root: Path) -> dict[str, Any]:
    payload = _load_json(run_root / "frontier.json", "frontier")
    items = payload.get("items")
    if not isinstance(items, list):
        raise SearchIntegrityError(f"invalid frontier items: {run_root / 'frontier.json'}")
    return payload


def _candidate_root(run_root: Path, candidate_id: str) -> Path:
    validate_path_segment(candidate_id, label="candidate_id")
    return run_root / "candidates" / candidate_id


def _require_candidate_payload(candidate_root: Path, *, campaign_id: str, run_id: str) -> dict[str, Any]:
    payload = _load_json(candidate_root / "candidate.json", "candidate payload")
    if payload.get("candidate_id") != candidate_root.name:
        raise SearchIntegrityError(f"candidate id mismatch: {candidate_root}")
    if payload.get("campaign_id") != campaign_id:
        raise SearchIntegrityError(f"candidate campaign_id mismatch: {candidate_root}")
    if payload.get("run_id") != run_id:
        raise SearchIntegrityError(f"candidate run_id mismatch: {candidate_root}")
    if payload.get("status") != "evaluated":
        raise SearchIntegrityError(f"candidate is not evaluated: {candidate_root.name}")
    if not isinstance(payload.get("code_family"), str) or not payload["code_family"]:
        raise SearchIntegrityError(f"candidate code_family is invalid: {candidate_root.name}")
    if not isinstance(payload.get("parameters"), dict):
        raise SearchIntegrityError(f"candidate parameters are invalid: {candidate_root.name}")
    return payload


def _require_distance(candidate_root: Path, rules: dict[str, Any]) -> int:
    payload = _load_json(candidate_root / "distance.json", "candidate distance")
    status = payload.get("status")
    distance = payload.get("distance")
    if rules.get("require_distance_verified", True) and status != "completed":
        raise SearchIntegrityError(f"distance is not verified for {candidate_root.name}")
    if not isinstance(distance, int) or isinstance(distance, bool) or distance <= 0:
        raise SearchIntegrityError(f"invalid distance for {candidate_root.name}")
    return distance


def _require_artifacts(candidate_root: Path, candidate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    artifact_root = candidate_root / "artifacts"
    instance = _load_json(artifact_root / "instance.json", "instance artifact")
    hx = _load_json(artifact_root / "hx.json", "hx artifact")
    hz = _load_json(artifact_root / "hz.json", "hz artifact")
    if instance.get("code_id") != candidate["code_family"]:
        raise SearchIntegrityError(f"candidate artifact code_id mismatch: {candidate_root.name}")
    if instance.get("parameters") != candidate["parameters"]:
        raise SearchIntegrityError(f"candidate artifact parameters mismatch: {candidate_root.name}")
    if instance.get("artifacts") != {"hx": "hx.json", "hz": "hz.json"}:
        raise SearchIntegrityError(f"unsupported instance artifact references: {candidate_root.name}")
    return instance, hx, hz


def _manifest_path(run_root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError("frontier manifest_path must be a nonempty string")
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise SearchIntegrityError(f"unsafe frontier manifest_path: {value}")
    return run_root / path


def _ler_at_p(manifest: dict[str, Any], p_value: float) -> float | None:
    points = manifest.get("points")
    if not isinstance(points, list):
        raise SearchIntegrityError("completed manifest points must be a list")
    for point in points:
        if not isinstance(point, dict):
            raise SearchIntegrityError("completed manifest point must be an object")
        if point.get("p") != p_value:
            continue
        ler = point.get("ler")
        if not isinstance(ler, (int, float)) or isinstance(ler, bool) or not 0 <= float(ler) <= 1:
            raise SearchIntegrityError(f"invalid LER value at p={p_value}: {ler}")
        return float(ler)
    return None


def _skip(candidate_id: str, reason: str) -> PromotionDecision:
    return PromotionDecision(
        candidate_id=candidate_id,
        status="skipped",
        reason=reason,
        code_id=None,
        target_instance_id=None,
        source_manifest_path=None,
        candidate_root=None,
        instance_payload=None,
        hx_payload=None,
        hz_payload=None,
    )


def _rewrite_instance_payload(
    instance: dict[str, Any],
    *,
    candidate_id: str,
    source_run: str,
    source_manifest_path: str,
    rules: dict[str, Any],
) -> dict[str, Any]:
    rewritten = dict(instance)
    rewritten["id"] = candidate_id
    if not isinstance(rewritten.get("title"), str) or not rewritten["title"]:
        distance = rewritten.get("derived_properties", {}).get("distance")
        rewritten["title"] = f"{rewritten['code_id']} candidate {candidate_id} d={distance}"
    provenance = dict(rewritten.get("provenance") if isinstance(rewritten.get("provenance"), dict) else {})
    provenance.update(
        {
            "promoted_by": "autoqec-search promote",
            "source_run": source_run,
            "source_candidate_id": candidate_id,
            "source_manifest_path": source_manifest_path,
            "promote_rules": rules,
        }
    )
    rewritten["provenance"] = provenance
    return rewritten


def evaluate_promotions(run_root: Path, rules: dict[str, Any]) -> list[PromotionDecision]:
    run_root = run_root.resolve()
    run_spec = _run_spec(run_root)
    campaign_id = run_spec.get("campaign_id")
    run_id = run_spec.get("run_id")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise SearchIntegrityError("run_spec campaign_id must be a nonempty string")
    if not isinstance(run_id, str) or not run_id:
        raise SearchIntegrityError("run_spec run_id must be a nonempty string")
    validate_path_segment(campaign_id, label="campaign_id")
    validate_path_segment(run_id, label="run_id")

    frontier = _frontier(run_root)
    if frontier.get("campaign_id") != campaign_id or frontier.get("run_id") != run_id:
        raise SearchIntegrityError("frontier identity does not match run_spec")

    decisions: list[PromotionDecision] = []
    for item in frontier["items"]:
        if not isinstance(item, dict):
            raise SearchIntegrityError("frontier item must be an object")
        candidate_id = item.get("candidate_id")
        if not isinstance(candidate_id, str):
            raise SearchIntegrityError("frontier candidate_id must be a string")
        candidate_root = _candidate_root(run_root, candidate_id)
        candidate = _require_candidate_payload(candidate_root, campaign_id=campaign_id, run_id=run_id)
        distance = _require_distance(candidate_root, rules)

        min_distance = rules.get("min_distance")
        if isinstance(min_distance, int) and distance < min_distance:
            decisions.append(_skip(candidate_id, f"distance {distance} is below min_distance {min_distance}"))
            continue

        manifest_path_text = item.get("manifest_path")
        manifest_path = _manifest_path(run_root, manifest_path_text)
        manifest = _load_json(manifest_path, "frontier manifest")
        if manifest.get("status") != "completed":
            raise SearchIntegrityError(f"frontier manifest is not completed: {manifest_path}")

        max_ler = rules.get("max_ler_at_p")
        if isinstance(max_ler, dict):
            p_value = float(max_ler["p"])
            limit = float(max_ler["ler"])
            ler = _ler_at_p(manifest, p_value)
            if ler is None:
                decisions.append(_skip(candidate_id, f"missing LER point at p={p_value:g}"))
                continue
            if ler > limit:
                decisions.append(_skip(candidate_id, f"LER {ler:g} at p={p_value:g} exceeds limit {limit:g}"))
                continue

        instance, hx, hz = _require_artifacts(candidate_root, candidate)
        decisions.append(
            PromotionDecision(
                candidate_id=candidate_id,
                status="promote",
                reason=None,
                code_id=candidate["code_family"],
                target_instance_id=candidate_id,
                source_manifest_path=str(Path(manifest_path_text)),
                candidate_root=candidate_root,
                instance_payload=_rewrite_instance_payload(
                    instance,
                    candidate_id=candidate_id,
                    source_run=f"{campaign_id}/{run_id}",
                    source_manifest_path=str(Path(manifest_path_text)),
                    rules=rules,
                ),
                hx_payload=hx,
                hz_payload=hz,
            )
        )

    return decisions
```

- [ ] **Step 4: Run evaluator tests**

Run:

```bash
python3 -m pytest tests/test_search_promote.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/promote.py tests/test_search_promote.py
git commit -m "feat: evaluate promotion candidates"
```

## Task 3: Promote CLI, Safe Copy, Summary, And Zoo Rebuild

**Files:**
- Modify: `src/autoqec_search/promote.py`
- Modify: `src/autoqec_search/cli.py`
- Test: `tests/test_search_promote.py`

- [ ] **Step 1: Add failing install and CLI tests**

Append these tests to `tests/test_search_promote.py`:

```python
def test_promote_run_copies_instance_and_rebuilds_zoo(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)

    summary = promote_run(work_root, run_root, rules_path=None, force=False)

    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    assert summary["status"] == "completed"
    assert [item["candidate_id"] for item in summary["promoted"]] == ["rotated-surface-d3-example"]
    assert target.is_dir()
    instance = _load_json(target / "instance.json")
    assert instance["id"] == "rotated-surface-d3-example"
    assert instance["provenance"]["promoted_by"] == "autoqec-search promote"
    assert instance["provenance"]["source_run"] == "rotated-surface-baseline/finished"
    instance_index = _load_json(work_root / "zoo" / "views" / "instance-index.json")
    assert "rotated-surface-d3-example" in [item["id"] for item in instance_index["items"]]
    card_md = (work_root / "zoo" / "codes" / "rotated-surface-code" / "card.md").read_text()
    assert "`rotated-surface-d3-example`" in card_md
    persisted = _load_json(run_root / "promotion_summary.json")
    assert persisted == summary


def test_promote_run_tight_rules_do_not_copy_instance(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    strict_rules = tmp_path / "strict-rules.json"
    _write_json(strict_rules, {"min_distance": 5})

    summary = promote_run(work_root, run_root, rules_path=strict_rules, force=False)

    target = (
        work_root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    assert summary["status"] == "completed"
    assert summary["promoted"] == []
    assert summary["skipped"][0]["reason"] == "distance 3 is below min_distance 5"
    assert not target.exists()


def test_promote_run_without_rules_writes_skip_summary(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.unlink()

    summary = promote_run(work_root, run_root, rules_path=None, force=False)

    assert summary["status"] == "skipped_no_rules"
    assert summary["promoted"] == []
    assert summary["skipped"] == []
    assert _load_json(run_root / "promotion_summary.json") == summary


def test_promote_run_refuses_existing_target_without_force(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    promote_run(work_root, run_root, rules_path=None, force=False)

    with pytest.raises(SearchIntegrityError, match="target instance already exists"):
        promote_run(work_root, run_root, rules_path=None, force=False)


def test_promote_run_force_replaces_existing_target(tmp_path: Path) -> None:
    from autoqec_search.promote import promote_run

    work_root, run_root = _make_finished_run(tmp_path)
    promote_run(work_root, run_root, rules_path=None, force=False)

    summary = promote_run(work_root, run_root, rules_path=None, force=True)

    assert summary["status"] == "completed"
    assert [item["candidate_id"] for item in summary["promoted"]] == ["rotated-surface-d3-example"]


def test_promote_cli_copies_instance(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    work_root, run_root = _make_finished_run(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "promote",
            "--root",
            str(work_root),
            "--run",
            str(run_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "promotion complete for rotated-surface-baseline/finished: 1 promoted, 0 skipped" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_promote.py -q
```

Expected: FAIL because `promote_run`, summary writing, instance install, rebuild, and CLI command are not implemented.

- [ ] **Step 3: Implement promote_run, install, rebuild, and summary writing**

Add the imports near the top of `src/autoqec_search/promote.py`, then append the remaining code below `evaluate_promotions`:

```python
from datetime import date, datetime, timezone
import shutil
import tempfile

from autoqec_zoo.build import build_zoo


@dataclass(frozen=True)
class InstalledInstance:
    target: Path
    backup: Path | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _install_instance(
    root: Path,
    decision: PromotionDecision,
    *,
    force: bool,
) -> InstalledInstance:
    if decision.status != "promote":
        raise SearchIntegrityError(f"cannot install non-promotion decision: {decision.status}")
    if decision.code_id is None or decision.target_instance_id is None:
        raise SearchIntegrityError(f"promotion decision missing target identity: {decision.candidate_id}")
    target_parent = root / "zoo" / "codes" / decision.code_id / "instances"
    if not target_parent.is_dir():
        raise SearchIntegrityError(f"unknown Zoo code instance directory: {target_parent}")
    target = target_parent / decision.target_instance_id
    if target.exists() and not force:
        raise SearchIntegrityError(f"target instance already exists: {target}")

    staging = Path(tempfile.mkdtemp(prefix=f".{decision.target_instance_id}.tmp-", dir=target_parent))
    backup: Path | None = None
    try:
        _write_json(staging / "instance.json", decision.instance_payload or {})
        _write_json(staging / "hx.json", decision.hx_payload or {})
        _write_json(staging / "hz.json", decision.hz_payload or {})

        if target.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{decision.target_instance_id}.previous-", dir=target_parent))
            backup.rmdir()
            target.rename(backup)
        staging.rename(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists() and not target.exists():
            backup.rename(target)
        raise
    return InstalledInstance(target=target, backup=backup)


def _rollback_installs(installed: list[InstalledInstance]) -> None:
    for item in reversed(installed):
        if item.target.exists():
            shutil.rmtree(item.target)
        if item.backup is not None and item.backup.exists():
            item.backup.rename(item.target)


def _cleanup_install_backups(installed: list[InstalledInstance]) -> None:
    for item in installed:
        if item.backup is not None and item.backup.exists():
            shutil.rmtree(item.backup)


def _summary_item(decision: PromotionDecision, target: Path | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "candidate_id": decision.candidate_id,
        "status": decision.status,
    }
    if decision.reason is not None:
        item["reason"] = decision.reason
    if decision.code_id is not None:
        item["code_id"] = decision.code_id
    if decision.target_instance_id is not None:
        item["target_instance_id"] = decision.target_instance_id
    if decision.source_manifest_path is not None:
        item["source_manifest_path"] = decision.source_manifest_path
    if target is not None:
        item["target_path"] = str(target)
    return item


def _run_identity(run_root: Path) -> tuple[str, str]:
    run_spec = _run_spec(run_root)
    campaign_id = run_spec.get("campaign_id")
    run_id = run_spec.get("run_id")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise SearchIntegrityError("run_spec campaign_id must be a nonempty string")
    if not isinstance(run_id, str) or not run_id:
        raise SearchIntegrityError("run_spec run_id must be a nonempty string")
    return campaign_id, run_id


def _write_summary(run_root: Path, summary: dict[str, Any]) -> dict[str, Any]:
    _write_json(run_root / "promotion_summary.json", summary)
    return summary


def promote_run(
    root: Path,
    run_root: Path,
    *,
    rules_path: Path | None,
    force: bool,
) -> dict[str, Any]:
    root = root.resolve()
    run_root = run_root.resolve()
    campaign_id, run_id = _run_identity(run_root)
    loaded_rules = load_promote_rules(root, run_root, rules_path=rules_path)
    generated_at = _utc_now()

    if loaded_rules is None:
        return _write_summary(
            run_root,
            {
                "campaign_id": campaign_id,
                "run_id": run_id,
                "generated_at": generated_at,
                "status": "skipped_no_rules",
                "rules_path": None,
                "rules": None,
                "force": force,
                "promoted": [],
                "skipped": [],
                "failed": [],
            },
        )

    decisions = evaluate_promotions(run_root, loaded_rules.rules)
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    installed: list[InstalledInstance] = []

    for decision in decisions:
        if decision.status == "skipped":
            skipped.append(_summary_item(decision))
            continue
        try:
            installed_item = _install_instance(root, decision, force=force)
        except SearchIntegrityError as exc:
            failed.append({**_summary_item(decision), "reason": str(exc)})
            break
        installed.append(installed_item)
        promoted.append(_summary_item(decision, installed_item.target))

    if failed:
        _rollback_installs(installed)
        _write_summary(
            run_root,
            {
                "campaign_id": campaign_id,
                "run_id": run_id,
                "generated_at": generated_at,
                "status": "failed",
                "rules_path": str(loaded_rules.path),
                "rules": loaded_rules.rules,
                "force": force,
                "promoted": promoted,
                "skipped": skipped,
                "failed": failed,
            },
        )
        raise SearchIntegrityError(failed[0]["reason"])

    if promoted:
        try:
            build_zoo(root / "zoo", generated_at=date.today().isoformat())
        except Exception as exc:
            _rollback_installs(installed)
            failed.append(
                {
                    "candidate_id": "__zoo_build__",
                    "status": "failed",
                    "reason": str(exc),
                }
            )
            _write_summary(
                run_root,
                {
                    "campaign_id": campaign_id,
                    "run_id": run_id,
                    "generated_at": generated_at,
                    "status": "failed",
                    "rules_path": str(loaded_rules.path),
                    "rules": loaded_rules.rules,
                    "force": force,
                    "promoted": promoted,
                    "skipped": skipped,
                    "failed": failed,
                },
            )
            raise SearchIntegrityError(f"Zoo rebuild failed: {exc}") from exc
        _cleanup_install_backups(installed)

    summary = {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "generated_at": generated_at,
        "status": "completed",
        "rules_path": str(loaded_rules.path),
        "rules": loaded_rules.rules,
        "force": force,
        "promoted": promoted,
        "skipped": skipped,
        "failed": [],
    }
    _write_summary(run_root, summary)
    return summary


def render_promotion_cli_summary(summary: dict[str, Any]) -> str:
    campaign_id = summary["campaign_id"]
    run_id = summary["run_id"]
    if summary["status"] == "skipped_no_rules":
        return f"promotion skipped for {campaign_id}/{run_id}: no promote_rules.json\n"
    return (
        f"promotion complete for {campaign_id}/{run_id}: "
        f"{len(summary['promoted'])} promoted, {len(summary['skipped'])} skipped\n"
    )
```

- [ ] **Step 4: Wire the CLI subcommand**

Modify `src/autoqec_search/cli.py`.

Add this import with the other `autoqec_search` imports:

```python
from autoqec_search.promote import promote_run, render_promotion_cli_summary
```

Add this parser block after the `report` parser block:

```python
    promote_parser = subparsers.add_parser(
        "promote", help="Promote accepted search candidates into the Zoo"
    )
    promote_parser.add_argument("--root", default=".")
    promote_parser.add_argument("--run", required=True)
    promote_parser.add_argument("--rules", default=None)
    promote_parser.add_argument("--force", action="store_true")
```

Add this command branch in `main`, after the `report` branch:

```python
        if args.command == "promote":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = Path(args.run)
            if not run_root.is_absolute():
                run_root = Path.cwd() / run_root
            if not run_root.exists():
                parser.error(f"run root does not exist: {run_root}")
            summary = promote_run(
                root,
                run_root,
                rules_path=Path(args.rules) if args.rules else None,
                force=args.force,
            )
            print(render_promotion_cli_summary(summary), end="")
            return 0
```

- [ ] **Step 5: Run promote tests**

Run:

```bash
python3 -m pytest tests/test_search_promote.py -q
```

Expected: PASS.

- [ ] **Step 6: Run search CLI smoke tests**

Run:

```bash
python3 -m pytest tests/test_search_promote.py tests/test_search_eval_cli.py::test_eval_campaign_candidate_writes_completed_selected_manifest_and_plot -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/autoqec_search/promote.py src/autoqec_search/cli.py tests/test_search_promote.py
git commit -m "feat: promote candidates into zoo"
```

## Task 4: Automatic Promotion At Autoresearch Finalization

**Files:**
- Modify: `src/autoqec_search/run_loop.py`
- Modify: `tests/test_search_run_cli.py`

- [ ] **Step 1: Add failing run-loop integration tests**

Append these tests to `tests/test_search_run_cli.py`:

```python
def test_run_autoresearch_promotes_kept_candidate_into_zoo(tmp_path: Path, monkeypatch) -> None:
    work_root = _copy_repo(tmp_path)
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="promotion-check")
    worktree = work_root / ".worktrees" / "promotion-check"
    promoted = (
        worktree
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )

    assert run_root == (
        worktree
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "promotion-check"
    )
    assert promoted.is_dir()
    instance = json.loads((promoted / "instance.json").read_text())
    assert instance["id"] == "rotated-surface-d3-example"
    assert instance["provenance"]["source_run"] == "rotated-surface-baseline/promotion-check"
    summary = json.loads((run_root / "promotion_summary.json").read_text())
    assert summary["status"] == "completed"
    assert [item["candidate_id"] for item in summary["promoted"]] == ["rotated-surface-d3-example"]
    instance_index = json.loads((worktree / "zoo" / "views" / "instance-index.json").read_text())
    assert "rotated-surface-d3-example" in [item["id"] for item in instance_index["items"]]

    branch_log = subprocess.run(
        ["git", "log", "--oneline", "autoresearch/promotion-check"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "finalize autoresearch run promotion-check" in branch_log


def test_run_autoresearch_missing_rules_writes_skip_summary(tmp_path: Path, monkeypatch) -> None:
    work_root = _copy_repo(tmp_path)
    rules = work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "promote_rules.json"
    rules.unlink()
    _commit_all(work_root, "remove promote rules")
    bin_dir = _write_fake_rsinter(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    run_root = _run_direct(work_root, run_id="promotion-skip")

    summary = json.loads((run_root / "promotion_summary.json").read_text())
    assert summary["status"] == "skipped_no_rules"
    assert summary["promoted"] == []
    promoted = (
        work_root
        / ".worktrees"
        / "promotion-skip"
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-d3-example"
    )
    assert not promoted.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py::test_run_autoresearch_promotes_kept_candidate_into_zoo tests/test_search_run_cli.py::test_run_autoresearch_missing_rules_writes_skip_summary -q
```

Expected: FAIL because `run_autoresearch` does not call promotion.

- [ ] **Step 3: Wire promotion into run finalization**

Modify `src/autoqec_search/run_loop.py`.

Add this import near the other imports:

```python
from autoqec_search.promote import promote_run
```

Change the finalization block in `run_autoresearch` from:

```python
    write_aggregates(run_root, config, rows, frontier)
    write_final_status(run_root, config, rows, frontier, utc_now())
    write_report_html(worktree_root, run_root)
    git_commit_all(worktree_root, f"finalize autoresearch run {actual_run_id}")
```

to:

```python
    write_aggregates(run_root, config, rows, frontier)
    write_final_status(run_root, config, rows, frontier, utc_now())
    write_report_html(worktree_root, run_root)
    promote_run(worktree_root, run_root, rules_path=None, force=False)
    git_commit_all(worktree_root, f"finalize autoresearch run {actual_run_id}")
```

- [ ] **Step 4: Run focused run-loop promotion tests**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py::test_run_autoresearch_promotes_kept_candidate_into_zoo tests/test_search_run_cli.py::test_run_autoresearch_missing_rules_writes_skip_summary -q
```

Expected: PASS.

- [ ] **Step 5: Run existing run CLI tests**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py -q
```

Expected: PASS. If an existing assertion assumes no `promotion_summary.json`, update that assertion to include the new finalization artifact and keep the semantic checks intact.

- [ ] **Step 6: Commit**

```bash
git add src/autoqec_search/run_loop.py tests/test_search_run_cli.py
git commit -m "feat: promote during autoresearch finalization"
```

## Task 5: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_search_docs.py`

- [ ] **Step 1: Add failing docs tests**

Append this test to `tests/test_search_docs.py`:

```python
def test_docs_mention_zoo_promotion_command_and_rules() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "autoqec-search promote" in readme
    assert "promote_rules.json" in readme
    assert "--force" in readme
    assert "promotion_summary.json" in readme
    assert "zoo/views/instance-index.json" in readme

    assert "autoqec-search promote" in claude
    assert "promote_rules.json" in claude
    assert "promotion_summary.json" in claude
    assert "auto-copy accepted instance into the curated Zoo" in claude
```

- [ ] **Step 2: Run docs test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_search_docs.py::test_docs_mention_zoo_promotion_command_and_rules -q
```

Expected: FAIL because docs do not describe issue #12 yet.

- [ ] **Step 3: Update README search-layer section**

In `README.md`, after the `autoqec-search report` paragraph, add:

````markdown
Promote accepted autoresearch candidates into the curated Zoo with:

```bash
python3 -m autoqec_search.cli promote --root . --run results/search/rotated-surface-baseline/<run-id>
```

The installed form is `autoqec-search promote`. Promotion reads
`promote_rules.json` next to the campaign, evaluates frontier candidates, copies
accepted `instance.json` / `hx.json` / `hz.json` bundles into
`zoo/codes/<code-id>/instances/<candidate-id>/`, writes
`promotion_summary.json`, and rebuilds `zoo/views/instance-index.json`,
`zoo/views/browse.md`, card markdown, and the static site. Existing curated
instance ids are protected; pass `--force` only when intentionally replacing a
previous local promotion.

`autoqec-search run` invokes the same promotion step during finalization. When
no campaign `promote_rules.json` exists, it writes a skip summary and still
finalizes the autoresearch branch.
````

- [ ] **Step 4: Update CLAUDE search-layer guidance**

In `CLAUDE.md`, after the issue `#11` report section, add:

````markdown
For issue `#12` and Zoo promotion, use:

```sh
python3 -m autoqec_search.cli promote --root . --run results/search/<campaign>/<run-id>
```

The installed form is `autoqec-search promote`. Promotion reads
`promote_rules.json` beside the campaign unless `--rules` is supplied, evaluates
kept frontier candidates, refuses to overwrite curated instance ids without
`--force`, auto-copy accepted instance into the curated Zoo under
`zoo/codes/<code-id>/instances/<candidate-id>/`, writes
`promotion_summary.json`, and rebuilds `zoo/views/instance-index.json`,
`zoo/views/browse.md`, card markdown, and the static site. Autoresearch
finalization runs the same promotion path automatically; missing rules produce
a skip summary instead of failing the run.
````

- [ ] **Step 5: Run docs tests**

Run:

```bash
python3 -m pytest tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 6: Run focused promotion test suite**

Run:

```bash
python3 -m pytest tests/test_search_promote.py tests/test_search_run_cli.py::test_run_autoresearch_promotes_kept_candidate_into_zoo tests/test_search_run_cli.py::test_run_autoresearch_missing_rules_writes_skip_summary tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 7: Run full test suite**

Run:

```bash
python3 -m pytest
```

Expected: PASS, with any marked slow tests deselected by the repository pytest config.

- [ ] **Step 8: Run search validation**

Run:

```bash
python3 -m autoqec_search.cli validate --root .
```

Expected output includes:

```text
validated search workspace under .:
```

- [ ] **Step 9: Run Zoo build validation**

Run:

```bash
python3 -m autoqec_zoo.cli build --root zoo
```

Expected output:

```text
built zoo artifacts under zoo
```

- [ ] **Step 10: Inspect final git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: changed files are limited to promotion schema/rules, `autoqec_search` promotion/CLI/run-loop code, promotion/run/docs tests, and README/CLAUDE docs.

- [ ] **Step 11: Commit**

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: document zoo promotion workflow"
```

## Self-Review Notes

- Spec coverage: the plan covers the schema, evaluator, CLI, candidate-id instance ids, provenance rewrite, overwrite refusal and `--force`, promotion summary, Zoo rebuild, autoresearch finalization, docs, and tests.
- Scope check: full evidence drafting and cross-run comparison remain out of scope.
- Type consistency: the central API is `load_promote_rules(root, run_root, rules_path=...)`, `evaluate_promotions(run_root, rules)`, and `promote_run(root, run_root, rules_path=..., force=...)` across tests, CLI, and run-loop wiring.

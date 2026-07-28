from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.distance_methods import load_distance_payload
from autoqec_search.load import SearchIntegrityError
from autoqec_zoo.build import build_zoo


COMPLETED_POINT_KEYS = {
    "p",
    "rounds",
    "shots",
    "errors",
    "ler",
    "ci_low",
    "ci_high",
    "seconds",
}


@dataclass(frozen=True)
class LoadedPromoteRules:
    path: Path
    rules: dict[str, Any]


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value}")


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(), parse_constant=_reject_json_constant)
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid {label} JSON at {path}: {exc.msg}") from exc
    except ValueError as exc:
        raise SearchIntegrityError(f"invalid {label} JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n")


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
    normalized.setdefault("require_reference_check", False)
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
    _validate_normalized_rules_values(rules_path, normalized)
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
    observables_x_payload: dict[str, Any] | None


def _frontier(run_root: Path) -> dict[str, Any]:
    payload = _load_json(run_root / "frontier.json", "frontier")
    items = payload.get("items")
    if not isinstance(items, list):
        raise SearchIntegrityError(f"invalid frontier items: {run_root / 'frontier.json'}")
    return payload


def _candidate_root(run_root: Path, candidate_id: str) -> Path:
    validate_path_segment(candidate_id, label="candidate_id")
    return run_root / "candidates" / candidate_id


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_int(value: object) -> bool:
    return _is_int(value) and value >= 1


def _is_nonnegative_int(value: object) -> bool:
    return _is_int(value) and value >= 0


def _is_finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _is_probability(value: object) -> bool:
    return _is_finite_number(value) and 0 < value < 1


def _is_rate(value: object) -> bool:
    return _is_finite_number(value) and 0 <= value <= 1


def _is_nonnegative_number(value: object) -> bool:
    return _is_finite_number(value) and value >= 0


def _validate_normalized_rules_values(rules_path: Path, rules: dict[str, Any]) -> None:
    max_ler = rules.get("max_ler_at_p")
    if not isinstance(max_ler, dict):
        return
    p_value = max_ler.get("p")
    if not _is_probability(p_value):
        raise SearchIntegrityError(
            f"invalid promote rules at {rules_path}: $.max_ler_at_p.p must satisfy 0 < p < 1"
        )
    ler = max_ler.get("ler")
    if not _is_rate(ler):
        raise SearchIntegrityError(
            f"invalid promote rules at {rules_path}: $.max_ler_at_p.ler must satisfy 0 <= ler <= 1"
        )


def _require_reference_check(run_root: Path, rules: dict[str, Any]) -> None:
    if not rules.get("require_reference_check", False):
        return
    path = run_root / "reference_check.json"
    payload = _load_json(path, "reference check")
    if payload.get("status") != "pass":
        raise SearchIntegrityError(f"reference check failed for {run_root}")


def _frontier_field(item: dict[str, Any], field: str) -> Any:
    if field not in item:
        raise SearchIntegrityError(f"frontier item {field} is required")
    return item[field]


def _frontier_string(item: dict[str, Any], field: str) -> str:
    value = _frontier_field(item, field)
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"frontier item {field} must be a nonempty string")
    return value


def _frontier_positive_int(item: dict[str, Any], field: str) -> int:
    value = _frontier_field(item, field)
    if not _is_positive_int(value):
        raise SearchIntegrityError(f"frontier item {field} must be a positive integer")
    return value


def _frontier_probability(item: dict[str, Any], field: str) -> float:
    value = _frontier_field(item, field)
    if not _is_probability(value):
        raise SearchIntegrityError(f"frontier item {field} must satisfy 0 < {field} < 1")
    return float(value)


def _frontier_rate(item: dict[str, Any], field: str) -> float:
    value = _frontier_field(item, field)
    if not _is_rate(value):
        raise SearchIntegrityError(f"frontier item {field} must satisfy 0 <= {field} <= 1")
    return float(value)


@dataclass(frozen=True)
class FrontierItem:
    candidate_id: str
    distance: int
    decoder_id: str
    p: float
    ler: float
    manifest_path_text: str
    task_id: str


def _manifest_path_parts(value: str) -> tuple[str, str, str]:
    parts = Path(value).parts
    if len(parts) != 6 or parts[0] != "candidates" or parts[2] != "evaluations" or parts[5] != "manifest.json":
        raise SearchIntegrityError(f"frontier item manifest_path has unsupported layout: {value}")
    path_candidate_id = parts[1]
    task_id = parts[3]
    decoder_id = parts[4]
    validate_path_segment(path_candidate_id, label="manifest_path candidate_id")
    validate_path_segment(task_id, label="manifest_path task_id")
    validate_path_segment(decoder_id, label="manifest_path decoder_id")
    return path_candidate_id, task_id, decoder_id


def _require_frontier_item(item: dict[str, Any]) -> FrontierItem:
    candidate_id = _frontier_string(item, "candidate_id")
    validate_path_segment(candidate_id, label="candidate_id")
    distance = _frontier_positive_int(item, "distance")
    decoder_id = _frontier_string(item, "decoder_id")
    validate_path_segment(decoder_id, label="decoder_id")
    p = _frontier_probability(item, "p")
    ler = _frontier_rate(item, "ler")
    manifest_path_text = _frontier_string(item, "manifest_path")
    path_candidate_id, task_id, path_decoder_id = _manifest_path_parts(manifest_path_text)
    if path_candidate_id != candidate_id:
        raise SearchIntegrityError("frontier manifest identity mismatch: manifest_path candidate_id")
    if path_decoder_id != decoder_id:
        raise SearchIntegrityError("frontier manifest identity mismatch: manifest_path decoder_id")
    return FrontierItem(
        candidate_id=candidate_id,
        distance=distance,
        decoder_id=decoder_id,
        p=p,
        ler=ler,
        manifest_path_text=manifest_path_text,
        task_id=task_id,
    )


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


def _require_distance(
    candidate_root: Path,
    rules: dict[str, Any],
    *,
    candidate: dict[str, Any],
    frontier_distance: int,
) -> int:
    distance_path = candidate_root / "distance.json"
    payload = _load_json(distance_path, "candidate distance")
    loaded = load_distance_payload(distance_path)
    status = payload.get("status")
    distance = loaded.distance
    if loaded.bound_type != "exact":
        raise SearchIntegrityError(
            f"candidate {candidate_root.name} promotion requires an exact distance; "
            f"got bound_type {loaded.bound_type or 'unknown'}"
        )
    if rules.get("require_distance_verified", True) and status != "completed":
        raise SearchIntegrityError(f"distance is not verified for {candidate_root.name}")
    if not isinstance(distance, int) or isinstance(distance, bool) or distance <= 0:
        raise SearchIntegrityError(f"invalid distance for {candidate_root.name}")
    candidate_distance = candidate["parameters"].get("distance")
    if candidate_distance != distance:
        raise SearchIntegrityError(
            f"distance mismatch for {candidate_root.name}: distance.json {distance} != candidate parameters {candidate_distance}"
        )
    if frontier_distance != distance:
        raise SearchIntegrityError(
            f"distance mismatch for {candidate_root.name}: distance.json {distance} != frontier item {frontier_distance}"
        )
    return distance


def _require_artifacts(
    candidate_root: Path, candidate: dict[str, Any], *, distance: int
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    artifact_root = candidate_root / "artifacts"
    instance = _load_json(artifact_root / "instance.json", "instance artifact")
    hx = _load_json(artifact_root / "hx.json", "hx artifact")
    hz = _load_json(artifact_root / "hz.json", "hz artifact")
    if instance.get("code_id") != candidate["code_family"]:
        raise SearchIntegrityError(f"candidate artifact code_id mismatch: {candidate_root.name}")
    if instance.get("parameters") != candidate["parameters"]:
        raise SearchIntegrityError(f"candidate artifact parameters mismatch: {candidate_root.name}")
    artifact_ref = instance.get("artifacts")
    if (
        not isinstance(artifact_ref, dict)
        or artifact_ref.get("hx") != "hx.json"
        or artifact_ref.get("hz") != "hz.json"
    ):
        raise SearchIntegrityError(f"unsupported instance artifact references: {candidate_root.name}")
    allowed_artifact_refs = {"hx", "hz", "observables_x"}
    if set(artifact_ref) - allowed_artifact_refs:
        raise SearchIntegrityError(f"unsupported instance artifact references: {candidate_root.name}")
    observables_x = None
    if artifact_ref.get("observables_x") == "observables_x.json":
        observables_x = _load_json(
            artifact_root / "observables_x.json",
            "observables_x artifact",
        )
    elif "observables_x" in artifact_ref:
        raise SearchIntegrityError(f"unsupported instance artifact references: {candidate_root.name}")
    derived_properties = instance.get("derived_properties")
    if not isinstance(derived_properties, dict) or derived_properties.get("distance") != distance:
        raise SearchIntegrityError(
            f"distance mismatch for {candidate_root.name}: distance.json {distance} != instance derived_properties.distance"
        )
    return instance, hx, hz, observables_x


def _manifest_path(run_root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError("frontier item manifest_path must be a nonempty string")
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise SearchIntegrityError(f"frontier item manifest_path is unsafe: {value}")
    return run_root / path


def _validate_completed_manifest_point(point: object, *, index: int) -> None:
    if not isinstance(point, dict) or set(point) != COMPLETED_POINT_KEYS:
        raise SearchIntegrityError(f"completed manifest point {index} is malformed")
    if not (
        _is_nonnegative_int(point.get("errors"))
        and _is_positive_int(point.get("shots"))
        and point["errors"] <= point["shots"]
    ):
        raise SearchIntegrityError(f"completed manifest point {index} has invalid shot/error counts")
    if not (
        _is_rate(point.get("ci_low"))
        and _is_rate(point.get("ci_high"))
        and _is_rate(point.get("ler"))
        and point["ci_low"] <= point["ci_high"]
        and point["ci_low"] <= point["ler"] <= point["ci_high"]
    ):
        raise SearchIntegrityError(f"completed manifest point {index} has invalid rate fields")
    if not (
        _is_probability(point.get("p"))
        and _is_positive_int(point.get("rounds"))
        and _is_nonnegative_number(point.get("seconds"))
    ):
        raise SearchIntegrityError(f"completed manifest point {index} has invalid p/rounds/seconds fields")


def _validate_completed_manifest_points(manifest: dict[str, Any]) -> None:
    points = manifest.get("points")
    if not isinstance(points, list) or not points:
        raise SearchIntegrityError("completed manifest points must be a nonempty list")
    for index, point in enumerate(points):
        _validate_completed_manifest_point(point, index=index)


def _require_completed_manifest(
    manifest_path: Path,
    *,
    campaign_id: str,
    run_id: str,
    candidate_id: str,
    task_id: str,
    decoder_id: str,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path, "frontier manifest")
    if manifest.get("status") != "completed":
        raise SearchIntegrityError(f"frontier manifest is not completed: {manifest_path}")
    expected = {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "task_id": task_id,
        "decoder_id": decoder_id,
    }
    for field, expected_value in expected.items():
        if manifest.get(field) != expected_value:
            raise SearchIntegrityError(
                f"frontier manifest identity mismatch for {field}: expected {expected_value}, got {manifest.get(field)}"
            )
    _validate_completed_manifest_points(manifest)
    return manifest


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
        observables_x_payload=None,
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
            "promote_rules": _json_clone(rules),
        }
    )
    rewritten["provenance"] = provenance
    return rewritten


def evaluate_promotions(run_root: Path, rules: dict[str, Any]) -> list[PromotionDecision]:
    run_root = run_root.resolve()
    rules = _normalize_rules(rules)
    _validate_normalized_rules_values(run_root / "promote_rules.json", rules)
    run_spec = _run_spec(run_root)
    campaign_id = run_spec.get("campaign_id")
    run_id = run_spec.get("run_id")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise SearchIntegrityError("run_spec campaign_id must be a nonempty string")
    if not isinstance(run_id, str) or not run_id:
        raise SearchIntegrityError("run_spec run_id must be a nonempty string")
    validate_path_segment(campaign_id, label="campaign_id")
    validate_path_segment(run_id, label="run_id")
    _require_reference_check(run_root, rules)

    frontier = _frontier(run_root)
    if frontier.get("campaign_id") != campaign_id or frontier.get("run_id") != run_id:
        raise SearchIntegrityError("frontier identity does not match run_spec")

    decisions: list[PromotionDecision] = []
    for item in frontier["items"]:
        if not isinstance(item, dict):
            raise SearchIntegrityError("frontier item must be an object")
        frontier_item = _require_frontier_item(item)
        candidate_id = frontier_item.candidate_id
        candidate_root = _candidate_root(run_root, candidate_id)
        candidate = _require_candidate_payload(candidate_root, campaign_id=campaign_id, run_id=run_id)
        distance = _require_distance(
            candidate_root,
            rules,
            candidate=candidate,
            frontier_distance=frontier_item.distance,
        )
        instance, hx, hz, observables_x = _require_artifacts(
            candidate_root,
            candidate,
            distance=distance,
        )

        manifest_path_text = frontier_item.manifest_path_text
        manifest_path = _manifest_path(run_root, manifest_path_text)
        manifest = _require_completed_manifest(
            manifest_path,
            campaign_id=campaign_id,
            run_id=run_id,
            candidate_id=candidate_id,
            task_id=frontier_item.task_id,
            decoder_id=frontier_item.decoder_id,
        )

        min_distance = rules.get("min_distance")
        if isinstance(min_distance, int) and distance < min_distance:
            decisions.append(_skip(candidate_id, f"distance {distance} is below min_distance {min_distance}"))
            continue

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
                observables_x_payload=observables_x,
            )
        )

    return decisions


@dataclass(frozen=True)
class InstalledInstance:
    target: Path
    backup: Path | None
    changed: bool = True


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _unique_sibling(path: Path, label: str) -> Path:
    return path.with_name(f".{path.name}.{label}-{uuid4().hex}")


def _backup_path(target: Path) -> Path:
    return target.parent.parent / ".promote-backups" / f"{target.name}-{uuid4().hex}"


def _require_promotion_payload(
    decision: PromotionDecision,
) -> tuple[
    str,
    str,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any] | None,
]:
    if (
        decision.status != "promote"
        or decision.code_id is None
        or decision.target_instance_id is None
        or decision.instance_payload is None
        or decision.hx_payload is None
        or decision.hz_payload is None
    ):
        raise SearchIntegrityError(f"incomplete promotion decision: {decision.candidate_id}")
    validate_path_segment(decision.code_id, label="code_id")
    validate_path_segment(decision.target_instance_id, label="target_instance_id")
    if decision.instance_payload.get("id") != decision.target_instance_id:
        raise SearchIntegrityError(f"promotion instance id mismatch: {decision.candidate_id}")
    if decision.instance_payload.get("code_id") != decision.code_id:
        raise SearchIntegrityError(f"promotion instance code_id mismatch: {decision.candidate_id}")
    return (
        decision.code_id,
        decision.target_instance_id,
        decision.instance_payload,
        decision.hx_payload,
        decision.hz_payload,
        decision.observables_x_payload,
    )


def _existing_instance_dirs_with_id(root: Path, instance_id: str) -> list[Path]:
    matches: list[Path] = []
    for instance_path in sorted((root / "zoo" / "codes").glob("*/instances/*/instance.json")):
        payload = _load_json(instance_path, "existing instance")
        if payload.get("id") == instance_id:
            matches.append(instance_path.parent)
    return matches


def _target_matches_promotion_payload(
    target: Path,
    instance: dict[str, Any],
    hx: dict[str, Any],
    hz: dict[str, Any],
    observables_x: dict[str, Any] | None,
) -> bool:
    try:
        existing_instance = _load_json(target / "instance.json", "existing target instance")
        existing_hx = _load_json(target / "hx.json", "existing target hx")
        existing_hz = _load_json(target / "hz.json", "existing target hz")
        existing_observables_x = None
        if (target / "observables_x.json").exists():
            existing_observables_x = _load_json(
                target / "observables_x.json",
                "existing target observables_x",
            )
    except SearchIntegrityError:
        return False
    return (
        _without_promotion_provenance(existing_instance)
        == _without_promotion_provenance(instance)
        and existing_hx == hx
        and existing_hz == hz
        and existing_observables_x == observables_x
    )


def _without_promotion_provenance(instance: dict[str, Any]) -> dict[str, Any]:
    normalized = _json_clone(instance)
    provenance = normalized.get("provenance")
    if isinstance(provenance, dict):
        for key in (
            "promoted_by",
            "source_run",
            "source_candidate_id",
            "source_manifest_path",
            "promote_rules",
        ):
            provenance.pop(key, None)
        if not provenance:
            normalized.pop("provenance", None)
    return normalized


def _install_instance(root: Path, decision: PromotionDecision, force: bool) -> InstalledInstance:
    code_id, target_instance_id, instance, hx, hz, observables_x = (
        _require_promotion_payload(decision)
    )
    target = root / "zoo" / "codes" / code_id / "instances" / target_instance_id
    existing_dirs = _existing_instance_dirs_with_id(root, target_instance_id)
    other_existing_dirs = [existing for existing in existing_dirs if existing != target]
    if other_existing_dirs:
        raise SearchIntegrityError(
            f"instance id already exists at {other_existing_dirs[0]}: {target_instance_id}"
        )
    if target.exists() and not force:
        if _target_matches_promotion_payload(target, instance, hx, hz, observables_x):
            return InstalledInstance(target=target, backup=None, changed=False)
        raise SearchIntegrityError(f"target instance already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    staged = _unique_sibling(target, "promote-tmp")
    backup: Path | None = None
    try:
        _write_json(staged / "instance.json", instance)
        _write_json(staged / "hx.json", hx)
        _write_json(staged / "hz.json", hz)
        if observables_x is not None:
            _write_json(staged / "observables_x.json", observables_x)
        if target.exists():
            backup = _backup_path(target)
            backup.parent.mkdir(parents=True, exist_ok=True)
            target.rename(backup)
        staged.rename(target)
    except Exception:
        if backup is not None and backup.exists():
            if target.exists():
                shutil.rmtree(target)
            backup.rename(target)
        if staged.exists():
            shutil.rmtree(staged)
        raise
    return InstalledInstance(target=target, backup=backup, changed=True)


def _rollback_installs(installs: list[InstalledInstance]) -> None:
    for installed in reversed(installs):
        if installed.changed and installed.target.exists():
            shutil.rmtree(installed.target)
        if installed.backup is not None and installed.backup.exists():
            installed.target.parent.mkdir(parents=True, exist_ok=True)
            installed.backup.rename(installed.target)


def _cleanup_install_backups(installs: list[InstalledInstance]) -> None:
    for installed in installs:
        if installed.backup is not None and installed.backup.exists():
            shutil.rmtree(installed.backup)
            try:
                installed.backup.parent.rmdir()
            except OSError:
                pass


def _snapshot_generated_zoo_outputs(root: Path) -> Path:
    zoo_root = root / "zoo"
    snapshot = _unique_sibling(zoo_root, "generated-snapshot")
    views = zoo_root / "views"
    if views.exists():
        shutil.copytree(views, snapshot / "views")
    cards_root = snapshot / "cards"
    for card_path in sorted((zoo_root / "codes").glob("*/card.md")):
        target = cards_root / card_path.parent.name / "card.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(card_path, target)
    return snapshot


def _restore_generated_zoo_outputs(root: Path, snapshot: Path) -> None:
    zoo_root = root / "zoo"
    views = zoo_root / "views"
    snapshot_views = snapshot / "views"
    if views.exists():
        shutil.rmtree(views)
    if snapshot_views.exists():
        shutil.copytree(snapshot_views, views)

    snapshot_cards = {
        card_path.parent.name: card_path
        for card_path in (snapshot / "cards").glob("*/card.md")
    }
    for card_path in sorted((zoo_root / "codes").glob("*/card.md")):
        if card_path.parent.name not in snapshot_cards:
            card_path.unlink()
    for code_id, snapshot_card in snapshot_cards.items():
        target = zoo_root / "codes" / code_id / "card.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot_card, target)


def _cleanup_generated_zoo_snapshot(snapshot: Path) -> None:
    if snapshot.exists():
        shutil.rmtree(snapshot)


def _rebuild_zoo_with_generated_snapshot(root: Path) -> None:
    snapshot = _snapshot_generated_zoo_outputs(root)
    try:
        build_zoo(root / "zoo", generated_at=date.today().isoformat())
    except Exception as exc:
        try:
            _restore_generated_zoo_outputs(root, snapshot)
        except Exception as restore_exc:
            raise SearchIntegrityError(
                f"Zoo rebuild failed: {exc}; generated artifact restore failed: {restore_exc}"
            ) from exc
        raise SearchIntegrityError(f"Zoo rebuild failed: {exc}") from exc
    finally:
        _cleanup_generated_zoo_snapshot(snapshot)


def _summary_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _summary_item(
    decision: PromotionDecision,
    *,
    root: Path | None = None,
    target: Path | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {"candidate_id": decision.candidate_id}
    if decision.code_id is not None:
        item["code_id"] = decision.code_id
    if decision.target_instance_id is not None:
        item["target_instance_id"] = decision.target_instance_id
    if decision.source_manifest_path is not None:
        item["source_manifest_path"] = decision.source_manifest_path
    if decision.reason is not None:
        item["reason"] = decision.reason
    if target is not None:
        item["target"] = _summary_path(root, target) if root is not None else str(target)
    return item


def _run_identity(run_root: Path) -> str:
    run_spec = _run_spec(run_root)
    campaign_id = run_spec.get("campaign_id")
    run_id = run_spec.get("run_id")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise SearchIntegrityError("run_spec campaign_id must be a nonempty string")
    if not isinstance(run_id, str) or not run_id:
        raise SearchIntegrityError("run_spec run_id must be a nonempty string")
    validate_path_segment(campaign_id, label="campaign_id")
    validate_path_segment(run_id, label="run_id")
    return f"{campaign_id}/{run_id}"


def _summary_base(
    root: Path,
    run_root: Path,
    *,
    status: str,
    rules_path: Path | None,
    rules: dict[str, Any] | None,
    force: bool,
) -> dict[str, Any]:
    return {
        "status": status,
        "generated_at": _utc_now(),
        "run": _run_identity(run_root),
        "rules_path": _summary_path(root, rules_path) if rules_path is not None else None,
        "rules": _json_clone(rules) if rules is not None else None,
        "force": force,
        "promoted": [],
        "skipped": [],
        "failures": [],
    }


def _write_summary(run_root: Path, summary: dict[str, Any]) -> None:
    _write_json(run_root / "promotion_summary.json", summary)


def _best_effort_rules_path(root: Path, run_root: Path, rules_path: Path | None) -> Path | None:
    if rules_path is not None:
        return rules_path if rules_path.is_absolute() else (Path.cwd() / rules_path)
    try:
        run_spec = _run_spec(run_root)
        campaign_id = run_spec.get("campaign_id")
        if not isinstance(campaign_id, str) or not campaign_id:
            return None
        validate_path_segment(campaign_id, label="campaign_id")
        candidate_path = _campaign_dir(root, campaign_id) / "promote_rules.json"
    except SearchIntegrityError:
        return None
    if not candidate_path.exists():
        return None
    return candidate_path


def promote_run(
    root: Path,
    run_root: Path,
    *,
    rules_path: Path | None,
    force: bool,
) -> dict[str, Any]:
    root = root.resolve()
    run_root = run_root.resolve()
    try:
        loaded_rules = load_promote_rules(root, run_root, rules_path=rules_path)
    except Exception as exc:
        summary = _summary_base(
            root,
            run_root,
            status="failed",
            rules_path=_best_effort_rules_path(root, run_root, rules_path),
            rules=None,
            force=force,
        )
        summary["failures"] = [{"reason": str(exc)}]
        _write_summary(run_root, summary)
        if isinstance(exc, SearchIntegrityError):
            raise
        raise SearchIntegrityError(f"promotion failed: {exc}") from exc
    if loaded_rules is None:
        summary = _summary_base(
            root,
            run_root,
            status="skipped_no_rules",
            rules_path=None,
            rules=None,
            force=force,
        )
        _write_summary(run_root, summary)
        return summary

    decisions = evaluate_promotions(run_root, loaded_rules.rules)
    skipped = [
        _summary_item(decision)
        for decision in decisions
        if decision.status == "skipped"
    ]
    promoted: list[dict[str, Any]] = []
    installs: list[InstalledInstance] = []
    current_candidate_id: str | None = None

    try:
        for decision in decisions:
            if decision.status == "skipped":
                continue
            if decision.status != "promote":
                raise SearchIntegrityError(
                    f"unsupported promotion decision status for {decision.candidate_id}: {decision.status}"
                )
            current_candidate_id = decision.candidate_id
            installed = _install_instance(root, decision, force)
            installs.append(installed)
            promoted.append(_summary_item(decision, root=root, target=installed.target))

        current_candidate_id = None
        if any(installed.changed for installed in installs):
            _rebuild_zoo_with_generated_snapshot(root)
        _cleanup_install_backups(installs)
    except Exception as exc:
        rollback_error: Exception | None = None
        try:
            _rollback_installs(installs)
        except Exception as rollback_exc:  # pragma: no cover - best-effort error path
            rollback_error = rollback_exc

        failure: dict[str, Any] = {"reason": str(exc)}
        if current_candidate_id is not None:
            failure["candidate_id"] = current_candidate_id
        if rollback_error is not None:
            failure["rollback_error"] = str(rollback_error)

        summary = _summary_base(
            root,
            run_root,
            status="failed",
            rules_path=loaded_rules.path,
            rules=loaded_rules.rules,
            force=force,
        )
        summary["skipped"] = skipped
        summary["failures"] = [failure]
        _write_summary(run_root, summary)

        if rollback_error is not None:
            raise SearchIntegrityError(
                f"promotion failed and rollback failed: {exc}; rollback: {rollback_error}"
            ) from exc
        if isinstance(exc, SearchIntegrityError):
            raise
        raise SearchIntegrityError(f"promotion failed: {exc}") from exc

    summary = _summary_base(
        root,
        run_root,
        status="completed",
        rules_path=loaded_rules.path,
        rules=loaded_rules.rules,
        force=force,
    )
    summary["promoted"] = promoted
    summary["skipped"] = skipped
    _write_summary(run_root, summary)
    return summary


def render_promotion_cli_summary(summary: dict[str, Any]) -> str:
    run = summary.get("run", "unknown run")
    if summary.get("status") == "skipped_no_rules":
        return f"promotion skipped for {run}: no promote rules\n"
    promoted_count = len(summary.get("promoted", []))
    skipped_count = len(summary.get("skipped", []))
    if summary.get("status") == "failed":
        failure_count = len(summary.get("failures", []))
        return (
            f"promotion failed for {run}: "
            f"{promoted_count} promoted, {skipped_count} skipped, {failure_count} failed\n"
        )
    return f"promotion complete for {run}: {promoted_count} promoted, {skipped_count} skipped\n"

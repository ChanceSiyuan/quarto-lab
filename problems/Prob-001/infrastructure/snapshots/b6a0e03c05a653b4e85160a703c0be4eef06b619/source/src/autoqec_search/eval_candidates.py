from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

from autoqec_search.distance_methods import (
    compute_distance_payload,
    normalize_distance_method_options,
)
from autoqec_search.load import SearchIntegrityError, SearchWorkspace


@dataclass(frozen=True)
class CandidateInput:
    candidate_id: str
    campaign_id: str
    code_family: str
    parameters: dict[str, Any]
    provenance: dict[str, Any]
    instance_path: str | None = None


@dataclass(frozen=True)
class ResolvedCandidate:
    spec: CandidateInput
    artifact_root: Path
    instance: dict[str, Any]
    hx: dict[str, Any]
    hz: dict[str, Any]
    source_kind: str
    observables_x: dict[str, Any] | None = None


CANDIDATE_DISTANCE_ERROR = "candidate distance must be a positive integer"


def _validate_path_segment(value: str, *, label: str) -> None:
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


def _validate_relative_repo_path(value: str, *, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    if not path.parts:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    return path


def _validate_resolved_path_under_root(root: Path, path: Path, *, label: str) -> None:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as error:
        raise SearchIntegrityError(
            f"{label} must be a safe relative path under repository root: {path}"
        ) from error


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    return payload


def _require_positive_recorded_distance(instance: dict[str, Any], path: Path) -> int:
    derived_properties = instance.get("derived_properties")
    if not isinstance(derived_properties, dict):
        raise SearchIntegrityError(f"missing recorded distance on instance: {path}")
    distance = derived_properties.get("distance")
    if not isinstance(distance, int) or isinstance(distance, bool) or distance <= 0:
        raise SearchIntegrityError(f"invalid recorded distance on instance: {path}")
    return distance


def _require_positive_candidate_distance(parameters: dict[str, Any]) -> int:
    distance = parameters.get("distance")
    if isinstance(distance, bool) or type(distance) is not int or distance <= 0:
        raise SearchIntegrityError(CANDIDATE_DISTANCE_ERROR)
    return distance


def _validate_candidate_distance_parameter(
    parameters: dict[str, Any],
    *,
    allow_unknown_distance: bool = False,
) -> int | None:
    distance = parameters.get("distance")
    if distance is None:
        if allow_unknown_distance:
            return None
        raise SearchIntegrityError(CANDIDATE_DISTANCE_ERROR)
    if isinstance(distance, bool):
        raise SearchIntegrityError(CANDIDATE_DISTANCE_ERROR)
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError(CANDIDATE_DISTANCE_ERROR)
    return distance


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


def _allow_unknown_exact_distance(provenance: dict[str, Any]) -> bool:
    if provenance.get("kind") != "proposal-derived":
        return False
    proposal = provenance.get("proposal")
    if not isinstance(proposal, dict):
        raise SearchIntegrityError(
            "proposal-derived candidate missing provenance.proposal"
        )
    if proposal.get("exact_distance_status") != "unknown":
        raise SearchIntegrityError(
            "proposal-derived candidate must record unknown exact distance status"
        )
    return True


def _validate_candidate_provenance(provenance: Any) -> dict[str, Any]:
    if (
        not isinstance(provenance, dict)
        or not isinstance(provenance.get("kind"), str)
        or not provenance["kind"]
        or not isinstance(provenance.get("label"), str)
        or not provenance["label"]
    ):
        raise SearchIntegrityError("invalid candidate payload")
    allowed_keys = {"kind", "label", "strategy", "proposal"}
    if set(provenance) - allowed_keys:
        raise SearchIntegrityError("invalid candidate payload")
    if "strategy" in provenance and provenance["strategy"] not in {
        "grid",
        "random",
        "adaptive",
    }:
        raise SearchIntegrityError("invalid candidate payload")
    if provenance["kind"] == "proposal-derived":
        proposal = provenance.get("proposal")
        if not isinstance(proposal, dict):
            raise SearchIntegrityError("invalid candidate payload")
    elif "proposal" in provenance:
        raise SearchIntegrityError("invalid candidate payload")
    return dict(provenance)


def _resolved_instance_parameters(
    instance: dict[str, Any],
    path: Path,
    *,
    allow_unknown_distance: bool = False,
) -> dict[str, Any]:
    parameters = instance.get("parameters")
    if not isinstance(parameters, dict):
        raise SearchIntegrityError(f"instance parameters must be an object: {path}")
    resolved = dict(parameters)
    derived_properties = instance.get("derived_properties")
    if not isinstance(derived_properties, dict):
        raise SearchIntegrityError(f"missing recorded distance on instance: {path}")
    distance = derived_properties.get("distance")
    parameter_distance = resolved.get("distance")
    if parameter_distance is None and distance is None:
        if not allow_unknown_distance:
            raise SearchIntegrityError(f"invalid recorded distance on instance: {path}")
        resolved["distance"] = None
    elif parameter_distance is None:
        if type(distance) is not int or isinstance(distance, bool) or distance <= 0:
            raise SearchIntegrityError(f"invalid recorded distance on instance: {path}")
        resolved["distance"] = distance
    else:
        if (
            type(parameter_distance) is not int
            or isinstance(parameter_distance, bool)
            or parameter_distance <= 0
        ):
            raise SearchIntegrityError(
                f"instance parameter distance must be a positive integer: {path}"
            )
        if type(distance) is not int or isinstance(distance, bool) or distance <= 0:
            raise SearchIntegrityError(f"invalid recorded distance on instance: {path}")
        if parameter_distance != distance:
            raise SearchIntegrityError(
                "instance parameter distance mismatch: "
                f"parameters.distance {parameter_distance} != "
                f"derived_properties.distance {distance}"
            )
    return resolved


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
        observables_x = _load_json(
            artifact_root / "observables_x.json",
            "logical-X observables artifact",
        )
    if require_distance:
        _require_positive_recorded_distance(instance, instance_path)
    return instance, hx, hz, observables_x


def _candidate_spec_from_search_space(
    payload: dict[str, Any],
    campaign_id: str,
) -> CandidateInput:
    if payload.get("campaign_id", campaign_id) != campaign_id:
        raise SearchIntegrityError(
            f"candidate campaign_id mismatch: {payload.get('campaign_id')} != {campaign_id}"
        )
    for key in ("candidate_id", "code_family", "parameters", "provenance"):
        if key not in payload:
            raise SearchIntegrityError(f"missing candidate field: {key}")
    if not isinstance(payload["parameters"], dict):
        raise SearchIntegrityError("candidate parameters must be an object")
    if not isinstance(payload["provenance"], dict):
        raise SearchIntegrityError("candidate provenance must be an object")
    _require_positive_candidate_distance(payload["parameters"])
    return CandidateInput(
        candidate_id=payload["candidate_id"],
        campaign_id=campaign_id,
        code_family=payload["code_family"],
        parameters=dict(payload["parameters"]),
        provenance=dict(payload["provenance"]),
    )


def _candidate_spec_from_explicit_instance(
    payload: dict[str, Any],
    campaign_id: str,
) -> CandidateInput:
    for key in ("candidate_id", "code_family", "instance_path", "provenance"):
        if key not in payload:
            raise SearchIntegrityError(f"missing candidate field: {key}")
    if not isinstance(payload["provenance"], dict):
        raise SearchIntegrityError("candidate provenance must be an object")
    provenance = _validate_candidate_provenance(payload["provenance"])
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
        provenance=provenance,
        instance_path=str(instance_path),
    )


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


def _normalized_instance_payload(
    instance: dict[str, Any],
    *,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(instance)
    normalized["parameters"] = dict(parameters)
    return normalized


def _directory_candidate_from_payload(
    payload: dict[str, Any],
    campaign_id: str,
) -> CandidateInput:
    required_keys = {
        "candidate_id",
        "campaign_id",
        "run_id",
        "code_family",
        "parameters",
        "provenance",
        "status",
    }
    if set(payload) != required_keys:
        raise SearchIntegrityError("invalid candidate payload")
    if (
        not isinstance(payload["candidate_id"], str)
        or not payload["candidate_id"]
        or not isinstance(payload["campaign_id"], str)
        or not payload["campaign_id"]
        or not isinstance(payload["run_id"], str)
        or not payload["run_id"]
        or not isinstance(payload["code_family"], str)
        or not payload["code_family"]
        or not isinstance(payload["status"], str)
        or payload["status"] not in {"placeholder", "evaluated"}
    ):
        raise SearchIntegrityError("invalid candidate payload")
    parameters = payload["parameters"]
    if (
        not isinstance(parameters, dict)
        or not parameters
        or not all(isinstance(key, str) for key in parameters)
        or not all(_valid_parameter_value(value) for value in parameters.values())
    ):
        raise SearchIntegrityError("invalid candidate payload")
    provenance = _validate_candidate_provenance(payload["provenance"])
    _validate_candidate_distance_parameter(
        parameters,
        allow_unknown_distance=_allow_unknown_exact_distance(provenance),
    )
    if payload["campaign_id"] != campaign_id:
        raise SearchIntegrityError(
            f"candidate campaign_id mismatch: {payload['campaign_id']} != {campaign_id}"
        )
    return CandidateInput(
        candidate_id=payload["candidate_id"],
        campaign_id=campaign_id,
        code_family=payload["code_family"],
        parameters=dict(parameters),
        provenance=provenance,
    )


def _parameters_match(
    instance_parameters: Any,
    candidate_parameters: dict[str, Any],
) -> bool:
    if not isinstance(instance_parameters, dict):
        return False
    if set(instance_parameters) != set(candidate_parameters):
        return False
    for key, candidate_value in candidate_parameters.items():
        instance_value = instance_parameters[key]
        if key == "distance":
            if instance_value is None or candidate_value is None:
                if instance_value is not None or candidate_value is not None:
                    return False
                continue
            if type(instance_value) is not int or type(candidate_value) is not int:
                return False
            if instance_value != candidate_value:
                return False
        elif instance_value != candidate_value:
            return False
    return True


def _validate_instance_matches_spec(
    instance: dict[str, Any],
    spec: CandidateInput,
) -> None:
    if instance.get("code_id") != spec.code_family:
        raise SearchIntegrityError("candidate artifact code_id mismatch")
    if not _parameters_match(instance.get("parameters"), spec.parameters):
        raise SearchIntegrityError("candidate artifact parameters mismatch")
    expected_distance = _validate_candidate_distance_parameter(
        spec.parameters,
        allow_unknown_distance=_allow_unknown_exact_distance(spec.provenance),
    )
    derived_properties = instance.get("derived_properties")
    actual_distance = (
        derived_properties.get("distance")
        if isinstance(derived_properties, dict)
        else None
    )
    if actual_distance != expected_distance:
        raise SearchIntegrityError("candidate artifact distance mismatch")


def _matching_zoo_instances(
    root: Path,
    *,
    code_family: str,
    parameters: dict[str, Any],
) -> list[Path]:
    matches: list[Path] = []
    for instance_path in sorted(
        (root / "zoo" / "codes").glob("*/instances/*/instance.json")
    ):
        instance = _load_json(instance_path, "Zoo instance")
        if (
            instance.get("code_id") == code_family
            and _parameters_match(instance.get("parameters"), parameters)
        ):
            matches.append(instance_path.parent)
    return matches


def _is_promoted_instance(path: Path) -> bool:
    instance = _load_json(path / "instance.json", "Zoo instance")
    provenance = instance.get("provenance")
    return (
        isinstance(provenance, dict)
        and provenance.get("promoted_by") == "autoqec-search promote"
    )


def _invalid_distance_targets_request(value: Any, requested_distance: int) -> bool:
    if isinstance(value, bool):
        return int(value) == requested_distance
    if isinstance(value, float):
        return value.is_integer() and int(value) == requested_distance
    return False


def _candidate_spec_matches_distance(
    candidate_spec: dict[str, Any],
    distance: int,
) -> bool:
    parameters = candidate_spec.get("parameters", {})
    if not isinstance(parameters, dict):
        return False
    candidate_distance = parameters.get("distance")
    if type(candidate_distance) is not int or candidate_distance <= 0:
        if _invalid_distance_targets_request(candidate_distance, distance):
            raise SearchIntegrityError(CANDIDATE_DISTANCE_ERROR)
        return False
    return candidate_distance == distance


def _resolve_matching_zoo_instance(root: Path, spec: CandidateInput) -> ResolvedCandidate:
    _validate_path_segment(spec.candidate_id, label="candidate_id")
    matches = _matching_zoo_instances(
        root,
        code_family=spec.code_family,
        parameters=spec.parameters,
    )
    if not matches:
        raise SearchIntegrityError(
            "no matching Zoo instance for candidate "
            f"{spec.candidate_id}: {spec.code_family} {spec.parameters}"
        )
    if len(matches) > 1:
        canonical_matches = [path for path in matches if not _is_promoted_instance(path)]
        if len(canonical_matches) == 1:
            matches = canonical_matches
    if len(matches) > 1:
        exact_id_matches = [
            path
            for path in matches
            if _load_json(path / "instance.json", "Zoo instance").get("id") == spec.candidate_id
        ]
        if len(exact_id_matches) == 1:
            matches = exact_id_matches
        elif len(exact_id_matches) > 1:
            raise SearchIntegrityError(
                "multiple matching Zoo instances for candidate "
                f"{spec.candidate_id}: {', '.join(str(path) for path in exact_id_matches)}"
            )
    if len(matches) > 1:
        raise SearchIntegrityError(
            "multiple matching Zoo instances for candidate "
            f"{spec.candidate_id}: {', '.join(str(path) for path in matches)}"
        )
    instance, hx, hz, observables_x = _load_artifact_bundle(matches[0])
    return ResolvedCandidate(
        spec=spec,
        artifact_root=matches[0],
        instance=instance,
        hx=hx,
        hz=hz,
        source_kind="zoo-instance",
        observables_x=observables_x,
    )


def _resolve_explicit_zoo_instance(root: Path, spec: CandidateInput) -> ResolvedCandidate:
    if spec.instance_path is None:
        raise SearchIntegrityError("explicit candidate is missing instance_path")
    artifact_root = root / spec.instance_path
    _validate_resolved_path_under_root(root, artifact_root, label="instance_path")
    instance, hx, hz, observables_x = _load_artifact_bundle(
        artifact_root,
        require_distance=False,
    )
    explicit_ids = [
        instance[key]
        for key in ("id", "instance_id", "candidate_id")
        if key in instance and instance[key] is not None
    ]
    if not explicit_ids or any(value != spec.candidate_id for value in explicit_ids):
        raise SearchIntegrityError("explicit instance id mismatch")
    if instance.get("code_id") != spec.code_family:
        raise SearchIntegrityError("explicit instance code_id mismatch")
    resolved_parameters = _resolved_instance_parameters(
        instance,
        artifact_root / "instance.json",
        allow_unknown_distance=_allow_unknown_exact_distance(spec.provenance),
    )
    return ResolvedCandidate(
        spec=CandidateInput(
            candidate_id=spec.candidate_id,
            campaign_id=spec.campaign_id,
            code_family=spec.code_family,
            parameters=resolved_parameters,
            provenance=spec.provenance,
            instance_path=spec.instance_path,
        ),
        artifact_root=artifact_root,
        instance=_normalized_instance_payload(instance, parameters=resolved_parameters),
        hx=hx,
        hz=hz,
        source_kind="explicit-zoo-instance",
        observables_x=observables_x,
    )


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


def resolve_campaign_candidate(
    root: Path,
    workspace: SearchWorkspace,
    *,
    campaign_id: str,
    distance: int,
) -> ResolvedCandidate:
    if campaign_id not in workspace.search_spaces:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")
    matching_specs = [
        candidate_spec
        for candidate_spec in workspace.search_spaces[campaign_id]["candidate_specs"]
        if _candidate_spec_matches_distance(candidate_spec, distance)
    ]
    if not matching_specs:
        raise SearchIntegrityError(
            f"no candidate in campaign {campaign_id} has distance {distance}"
        )
    return resolve_campaign_candidate_spec(
        root,
        matching_specs[0],
        campaign_id=campaign_id,
    )


def resolve_directory_candidate(
    root: Path,
    candidate_dir: Path,
    *,
    campaign_id: str,
) -> ResolvedCandidate:
    candidate_path = candidate_dir / "candidate.json"
    spec = _directory_candidate_from_payload(
        _load_json(candidate_path, "candidate payload"),
        campaign_id,
    )
    artifacts_root = candidate_dir / "artifacts"
    if artifacts_root.is_dir():
        instance, hx, hz, observables_x = _load_artifact_bundle(artifacts_root)
        _validate_instance_matches_spec(instance, spec)
        return ResolvedCandidate(
            spec=spec,
            artifact_root=artifacts_root,
            instance=instance,
            hx=hx,
            hz=hz,
            source_kind="candidate-artifacts",
            observables_x=observables_x,
        )
    return _resolve_matching_zoo_instance(root, spec)


def candidate_payload(candidate: ResolvedCandidate, run_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate.spec.candidate_id,
        "campaign_id": candidate.spec.campaign_id,
        "run_id": run_id,
        "code_family": candidate.spec.code_family,
        "parameters": candidate.spec.parameters,
        "provenance": candidate.spec.provenance,
        "status": "evaluated",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def copy_candidate_artifacts(
    candidate: ResolvedCandidate,
    candidate_root: Path,
    *,
    distance_payload: dict[str, Any] | None = None,
) -> None:
    artifacts_root = candidate_root / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)

    _write_json(artifacts_root / "instance.json", candidate.instance)
    _write_json(artifacts_root / "hx.json", candidate.hx)
    _write_json(artifacts_root / "hz.json", candidate.hz)
    if candidate.observables_x is not None:
        _write_json(artifacts_root / "observables_x.json", candidate.observables_x)

    payload = distance_payload
    if payload is None:
        derived_properties = candidate.instance.get("derived_properties")
        recorded_distance = (
            derived_properties.get("distance")
            if isinstance(derived_properties, dict)
            else None
        )
        if recorded_distance is None:
            source_instance_id = candidate.instance.get("id")
            if not isinstance(source_instance_id, str) or not source_instance_id:
                raise SearchIntegrityError(
                    "missing source instance id: "
                    f"{candidate.artifact_root / 'instance.json'}"
                )
            payload = {
                "status": "unavailable",
                "distance": None,
                "method": "not-recorded-on-zoo-instance",
                "source_instance_id": source_instance_id,
                "source_instance_path": str(candidate.artifact_root),
            }
        else:
            payload = compute_distance_payload(
                candidate,
                normalize_distance_method_options(method=None, seed=0),
            )
    _write_json(candidate_root / "distance.json", payload)

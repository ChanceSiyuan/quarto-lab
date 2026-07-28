from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_proposal_materialization import (
    MANIFEST_FILENAME,
    SPEC_FILENAME,
)


REQUIRED_OUTPUT_FILENAMES = (
    "instance.json",
    "hx.json",
    "hz.json",
    SPEC_FILENAME,
)
FINGERPRINT_OUTPUT_FILENAMES = (
    "hx.json",
    "hz.json",
    SPEC_FILENAME,
)


@dataclass(frozen=True)
class ProposalImportCandidate:
    candidate_id: str
    candidate_fingerprint: str
    proposal_fingerprint: str
    search_space_candidate: dict[str, Any]


@dataclass(frozen=True)
class ProposalImportSummary:
    imported: int
    preserved: int
    search_space_path: Path
    imported_candidate_ids: tuple[str, ...]


def import_quantum_tanner_proposal_instances(
    root: Path,
    campaign_id: str,
    search_space_path: Path,
    instance_root: Path | None = None,
    manifest_path: Path | None = None,
    duplicate_policy: str = "reject",
) -> ProposalImportSummary:
    if duplicate_policy != "reject":
        raise SearchIntegrityError(
            f"unsupported duplicate_policy: {duplicate_policy}"
        )
    if (instance_root is None) == (manifest_path is None):
        raise SearchIntegrityError(
            "exactly one of instance_root or manifest_path is required"
        )
    resolved_root = root.resolve()
    resolved_search_space_path = _resolve_search_space_path(
        resolved_root,
        search_space_path,
    )
    search_space_validator = _search_space_validator(resolved_root)
    search_space = _load_or_create_search_space(
        resolved_search_space_path,
        campaign_id,
    )
    if search_space.get("campaign_id") != campaign_id:
        raise SearchIntegrityError(
            "search_space campaign_id mismatch for "
            f"{resolved_search_space_path}: {search_space.get('campaign_id')} != {campaign_id}"
        )
    if search_space.get("mode") != "explicit_list":
        raise SearchIntegrityError(
            f"search space mode must be explicit_list: {resolved_search_space_path}"
        )
    candidate_specs = search_space.get("candidate_specs")
    if not isinstance(candidate_specs, list):
        raise SearchIntegrityError(
            f"search space candidate_specs must be a list: {resolved_search_space_path}"
        )
    if resolved_search_space_path.is_file():
        _validate_search_space_schema(
            search_space_validator,
            search_space,
            resolved_search_space_path,
        )

    manifest_paths = _collect_manifest_paths(
        resolved_root,
        instance_root=instance_root,
        manifest_path=manifest_path,
    )
    imported_candidates = tuple(
        _load_import_candidate(resolved_root, manifest_file)
        for manifest_file in manifest_paths
    )
    _check_import_duplicates(imported_candidates)

    existing_by_id: dict[str, dict[str, Any]] = {}
    existing_proposal_fingerprint_to_id: dict[str, str] = {}
    existing_candidate_fingerprint_to_id: dict[str, str] = {}
    for candidate_spec in candidate_specs:
        if not isinstance(candidate_spec, dict):
            raise SearchIntegrityError(
                f"candidate_specs entries must be objects: {resolved_search_space_path}"
            )
        candidate_id = candidate_spec.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise SearchIntegrityError(
                f"candidate_id must be a non-empty string: {resolved_search_space_path}"
            )
        if candidate_id in existing_by_id:
            raise SearchIntegrityError(
                f"duplicate candidate_id in search space: {candidate_id}"
            )
        existing_by_id[candidate_id] = candidate_spec
        proposal_payload = _existing_proposal_payload(candidate_spec)
        if proposal_payload is None:
            continue
        proposal_fingerprint = proposal_payload["proposal_fingerprint"]
        candidate_fingerprint = proposal_payload["candidate_fingerprint"]
        _remember_unique_mapping(
            existing_proposal_fingerprint_to_id,
            proposal_fingerprint,
            candidate_id,
            label="proposal fingerprint",
        )
        _remember_unique_mapping(
            existing_candidate_fingerprint_to_id,
            candidate_fingerprint,
            candidate_id,
            label="candidate fingerprint",
        )

    for imported_candidate in imported_candidates:
        existing_proposal_id = existing_proposal_fingerprint_to_id.get(
            imported_candidate.proposal_fingerprint
        )
        if (
            existing_proposal_id is not None
            and existing_proposal_id != imported_candidate.candidate_id
        ):
            raise SearchIntegrityError(
                "duplicate proposal fingerprint: "
                f"{imported_candidate.proposal_fingerprint} already used by "
                f"{existing_proposal_id}, cannot import {imported_candidate.candidate_id}"
            )
        existing_candidate_id = existing_candidate_fingerprint_to_id.get(
            imported_candidate.candidate_fingerprint
        )
        if (
            existing_candidate_id is not None
            and existing_candidate_id != imported_candidate.candidate_id
        ):
            raise SearchIntegrityError(
                "duplicate candidate fingerprint: "
                f"{imported_candidate.candidate_fingerprint} already used by "
                f"{existing_candidate_id}, cannot import {imported_candidate.candidate_id}"
            )

    replacements: dict[str, dict[str, Any]] = {}
    for imported_candidate in imported_candidates:
        existing_spec = existing_by_id.get(imported_candidate.candidate_id)
        if existing_spec is not None:
            existing_payload = _existing_proposal_payload(existing_spec)
            if existing_payload is None:
                raise SearchIntegrityError(
                    f"candidate_id collision with non proposal-derived candidate: {imported_candidate.candidate_id}"
                )
            if (
                existing_payload["candidate_fingerprint"]
                != imported_candidate.candidate_fingerprint
            ):
                raise SearchIntegrityError(
                    "candidate_id collision with changed candidate fingerprint: "
                    f"{imported_candidate.candidate_id}"
                )
        replacements[imported_candidate.candidate_id] = (
            imported_candidate.search_space_candidate
        )

    updated_candidate_specs: list[dict[str, Any]] = []
    preserved = 0
    replaced_ids = set(replacements)
    for candidate_spec in candidate_specs:
        candidate_id = candidate_spec["candidate_id"]
        if candidate_id in replaced_ids:
            updated_candidate_specs.append(replacements.pop(candidate_id))
            continue
        updated_candidate_specs.append(candidate_spec)
        preserved += 1
    for imported_candidate in imported_candidates:
        if imported_candidate.candidate_id in replacements:
            updated_candidate_specs.append(replacements.pop(imported_candidate.candidate_id))

    updated_search_space = dict(search_space)
    updated_search_space["candidate_specs"] = updated_candidate_specs
    _validate_search_space_schema(
        search_space_validator,
        updated_search_space,
        resolved_search_space_path,
    )
    _atomic_write_json(resolved_search_space_path, updated_search_space)
    return ProposalImportSummary(
        imported=len(imported_candidates),
        preserved=preserved,
        search_space_path=resolved_search_space_path,
        imported_candidate_ids=tuple(
            candidate.candidate_id for candidate in imported_candidates
        ),
    )


def _collect_manifest_paths(
    root: Path,
    *,
    instance_root: Path | None,
    manifest_path: Path | None,
) -> tuple[Path, ...]:
    if manifest_path is not None:
        resolved_manifest = _resolve_path_under_root(
            root,
            manifest_path,
            label="manifest path",
        )
        if resolved_manifest.name != MANIFEST_FILENAME:
            raise SearchIntegrityError(
                f"manifest path must point to {MANIFEST_FILENAME}: {resolved_manifest}"
            )
        if not resolved_manifest.is_file():
            raise SearchIntegrityError(f"missing manifest: {resolved_manifest}")
        return (resolved_manifest,)

    assert instance_root is not None
    resolved_instance_root = _resolve_path_under_root(
        root,
        instance_root,
        label="instance root",
    )
    if not resolved_instance_root.is_dir():
        raise SearchIntegrityError(f"missing instance root: {resolved_instance_root}")
    manifests = tuple(
        sorted(
            path
            for path in resolved_instance_root.glob(f"*/{MANIFEST_FILENAME}")
            if path.is_file()
        )
    )
    if not manifests:
        raise SearchIntegrityError(
            f"no materialization manifests found under {resolved_instance_root}"
        )
    return manifests


def _load_import_candidate(root: Path, manifest_path: Path) -> ProposalImportCandidate:
    manifest = _load_json_object(manifest_path, "materialization manifest")
    instance_dir = manifest_path.parent
    instance_path = instance_dir / "instance.json"
    hx_path = instance_dir / "hx.json"
    hz_path = instance_dir / "hz.json"
    spec_path = instance_dir / SPEC_FILENAME
    instance = _load_json_object(instance_path, "instance artifact")
    hx = _validate_sparse_rows_matrix_payload(
        _load_json_object(hx_path, "hx artifact"),
        path=hx_path,
        label="hx artifact",
    )
    hz = _validate_sparse_rows_matrix_payload(
        _load_json_object(hz_path, "hz artifact"),
        path=hz_path,
        label="hz artifact",
    )
    _load_json_object(spec_path, "qec-code quantum Tanner spec")
    _validate_instance_bundle_references(instance, instance_path)

    candidate_id = _require_candidate_id_match(
        instance_dir.name,
        instance.get("candidate_id"),
        instance.get("instance_id"),
        manifest.get("candidate_id"),
    )
    proposal_id = _require_non_empty_string(
        manifest.get("proposal_id"),
        label=f"proposal_id in {manifest_path}",
    )
    instance_proposal_id = _require_non_empty_string(
        instance.get("proposal_id"),
        label=f"proposal_id in {instance_path}",
    )
    if instance_proposal_id != proposal_id:
        raise SearchIntegrityError(
            f"mismatched proposal_id between instance and manifest: {instance_path}"
        )

    proposal_fingerprint = _require_non_empty_string(
        manifest.get("proposal_fingerprint"),
        label=f"proposal_fingerprint in {manifest_path}",
    )
    validator = manifest.get("validator")
    if not isinstance(validator, dict):
        raise SearchIntegrityError(f"missing validator on manifest: {manifest_path}")
    validator_fingerprint = _require_non_empty_string(
        validator.get("fingerprint"),
        label=f"validator fingerprint in {manifest_path}",
    )
    output_hashes = manifest.get("output_hashes")
    if not isinstance(output_hashes, dict):
        raise SearchIntegrityError(f"missing output_hashes on manifest: {manifest_path}")
    normalized_output_hashes = _validate_output_hashes(
        output_hashes,
        instance_path=instance_path,
        hx_path=hx_path,
        hz_path=hz_path,
        spec_path=spec_path,
        manifest_path=manifest_path,
    )

    if instance.get("code_id") != "quantum-tanner-code":
        raise SearchIntegrityError(
            f"instance code_id must be quantum-tanner-code: {instance_path}"
        )
    parameters = instance.get("parameters")
    if not isinstance(parameters, dict):
        raise SearchIntegrityError(f"instance parameters must be an object: {instance_path}")
    derived_properties = instance.get("derived_properties")
    if not isinstance(derived_properties, dict):
        raise SearchIntegrityError(
            f"instance derived_properties must be an object: {instance_path}"
        )
    if parameters.get("distance") is not None:
        raise SearchIntegrityError(
            f"proposal-derived instance must not record an exact distance in parameters: {instance_path}"
        )
    if derived_properties.get("distance") is not None:
        raise SearchIntegrityError(
            f"proposal-derived instance must not record an exact distance in derived_properties: {instance_path}"
        )
    exact_distance_status = manifest.get("exact_distance_status")
    if exact_distance_status is not None and exact_distance_status != "unknown":
        raise SearchIntegrityError(
            f"unexpected exact_distance_status on manifest: {manifest_path}"
        )
    materializer_version = _require_non_empty_string(
        manifest.get("materializer_version"),
        label=f"materializer_version in {manifest_path}",
    )
    qec_code = manifest.get("qec_code")
    if not isinstance(qec_code, dict):
        raise SearchIntegrityError(f"missing qec_code on manifest: {manifest_path}")

    dimensions = {
        "kx": _require_optional_nonnegative_int_field(
            derived_properties,
            "kx",
            label=f"derived_properties.kx in {instance_path}",
        ),
        "kz": _require_optional_nonnegative_int_field(
            derived_properties,
            "kz",
            label=f"derived_properties.kz in {instance_path}",
        ),
        "mx": _require_positive_int_field(
            derived_properties,
            "mx",
            label=f"derived_properties.mx in {instance_path}",
        ),
        "mz": _require_positive_int_field(
            derived_properties,
            "mz",
            label=f"derived_properties.mz in {instance_path}",
        ),
        "n": _require_positive_int_field(
            derived_properties,
            "n",
            label=f"n in {instance_path}",
        ),
    }
    if instance.get("n") != dimensions["n"]:
        raise SearchIntegrityError(f"instance n mismatch: {instance_path}")
    _validate_css_dimensions(hx, hz, dimensions, instance_path)

    fingerprint_payload = {
        "dimensions": dimensions,
        "output_hashes": {
            name: normalized_output_hashes[name]
            for name in FINGERPRINT_OUTPUT_FILENAMES
        },
        "proposal_fingerprint": proposal_fingerprint,
        "validator_fingerprint": validator_fingerprint,
    }
    candidate_fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    search_space_candidate = {
        "candidate_id": candidate_id,
        "code_family": "quantum-tanner-code",
        "instance_path": _relative_to_root(root, instance_dir),
        "provenance": {
            "kind": "proposal-derived",
            "label": proposal_id,
            "proposal": {
                "proposal_id": proposal_id,
                "proposal_fingerprint": proposal_fingerprint,
                "validator_fingerprint": validator_fingerprint,
                "candidate_fingerprint": candidate_fingerprint,
                "materialization_manifest": _relative_to_root(root, manifest_path),
                "qec_code_spec_path": _relative_to_root(root, spec_path),
                "output_hashes": {
                    name: normalized_output_hashes[name]
                    for name in sorted(normalized_output_hashes)
                },
                "materializer_version": materializer_version,
                "exact_distance_status": "unknown",
                "materialization_run": {"qec_code": qec_code},
            },
        },
    }
    return ProposalImportCandidate(
        candidate_id=candidate_id,
        candidate_fingerprint=candidate_fingerprint,
        proposal_fingerprint=proposal_fingerprint,
        search_space_candidate=search_space_candidate,
    )


def _resolve_search_space_path(root: Path, path: Path) -> Path:
    resolved = _resolve_path_under_root(root, path, label="search space path")
    if resolved.name != "search_space.json":
        raise SearchIntegrityError(
            "search_space_path must be named search_space.json so validate --root can load it"
        )
    return resolved


def _search_space_validator(root: Path) -> Draft202012Validator:
    schema_path = root / "benchmarks" / "schemas" / "search-space.schema.json"
    schema = _load_json_object(schema_path, "search-space schema")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise SearchIntegrityError(f"invalid search-space schema: {schema_path}") from error
    return Draft202012Validator(schema)


def _load_or_create_search_space(path: Path, campaign_id: str) -> dict[str, Any]:
    if path.is_file():
        return _load_json_object(path, "search space")
    return {
        "campaign_id": campaign_id,
        "mode": "explicit_list",
        "candidate_specs": [],
    }


def _validate_search_space_schema(
    validator: Draft202012Validator,
    payload: dict[str, Any],
    path: Path,
) -> None:
    try:
        validator.validate(payload)
    except ValidationError as error:
        raise SearchIntegrityError(
            f"invalid search space schema for {path}: {error.message}"
        ) from error


def _resolve_path_under_root(root: Path, path: Path, *, label: str) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise SearchIntegrityError(
            f"{label} must be a safe relative path under repository root: {path}"
        ) from error
    return resolved


def _relative_to_root(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must contain a JSON object: {path}")
    return payload


def _require_non_empty_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"missing {label}")
    return value


def _require_positive_int_field(
    payload: dict[str, Any],
    key: str,
    *,
    label: str,
) -> int:
    if key not in payload:
        raise SearchIntegrityError(f"missing {label}")
    return _require_positive_int(payload[key], label=label)


def _require_optional_nonnegative_int_field(
    payload: dict[str, Any],
    key: str,
    *,
    label: str,
) -> int | None:
    if key not in payload:
        raise SearchIntegrityError(f"missing {label}")
    value = payload[key]
    if value is None:
        return None
    return _require_nonnegative_int(value, label=label)


def _require_positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise SearchIntegrityError(f"{label} must be a positive integer")
    return value


def _require_nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        raise SearchIntegrityError(f"{label} must be a nonnegative integer")
    return value


def _require_candidate_id_match(*values: object) -> str:
    normalized = [
        _require_non_empty_string(value, label="candidate id")
        for value in values
    ]
    candidate_id = normalized[0]
    for other in normalized[1:]:
        if other != candidate_id:
            raise SearchIntegrityError(
                "mismatched candidate ids in proposal materialization bundle: "
                + ", ".join(normalized)
            )
    return candidate_id


def _validate_instance_bundle_references(
    instance: dict[str, Any],
    instance_path: Path,
) -> None:
    artifacts = instance.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SearchIntegrityError(
            "instance artifacts must be an object with bundle-local references "
            f"hx='hx.json' and hz='hz.json': {instance_path}"
        )

    expected_artifacts = {"hx": "hx.json", "hz": "hz.json"}
    unsupported_artifacts = sorted(
        key for key in artifacts.keys() if key not in expected_artifacts
    )
    if unsupported_artifacts:
        raise SearchIntegrityError(
            "unsupported artifact references in instance bundle "
            f"{instance_path}: {', '.join(unsupported_artifacts)}; "
            "supported keys are hx and hz pointing to bundle-local files"
        )
    for key, expected_filename in expected_artifacts.items():
        value = artifacts.get(key)
        if value != expected_filename:
            raise SearchIntegrityError(
                "instance bundle must reference bundle-local artifact "
                f"{key}='{expected_filename}' in {instance_path}; got {value!r}"
            )

    spec_reference = instance.get("quantum_tanner_spec")
    if spec_reference != SPEC_FILENAME:
        raise SearchIntegrityError(
            "instance bundle must reference bundle-local quantum_tanner_spec "
            f"'{SPEC_FILENAME}' in {instance_path}; got {spec_reference!r}"
        )


def _validate_output_hashes(
    output_hashes: dict[str, Any],
    *,
    instance_path: Path,
    hx_path: Path,
    hz_path: Path,
    spec_path: Path,
    manifest_path: Path,
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    required_paths = {
        "instance.json": instance_path,
        "hx.json": hx_path,
        "hz.json": hz_path,
        SPEC_FILENAME: spec_path,
    }
    for name, expected_path in required_paths.items():
        expected_hash = _require_non_empty_string(
            output_hashes.get(name),
            label=f"output hash for {name} in {manifest_path}",
        )
        actual_hash = hashlib.sha256(expected_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise SearchIntegrityError(
                f"output hash mismatch for {name}: {expected_path}"
            )
        normalized[name] = expected_hash
    for name, value in output_hashes.items():
        if isinstance(name, str) and isinstance(value, str) and name not in normalized:
            normalized[name] = value
    return normalized


def _validate_sparse_rows_matrix_payload(
    payload: dict[str, Any],
    *,
    path: Path,
    label: str,
) -> dict[str, Any]:
    if payload.get("format") != "sparse_rows":
        raise SearchIntegrityError(f"{label} format must be sparse_rows: {path}")
    num_cols = payload.get("num_cols")
    rows = payload.get("rows")
    if type(num_cols) is not int or num_cols <= 0:
        raise SearchIntegrityError(f"{label} num_cols must be a positive integer: {path}")
    if not isinstance(rows, list):
        raise SearchIntegrityError(f"{label} rows must be a list: {path}")
    normalized_rows: list[list[int]] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            raise SearchIntegrityError(f"{label} row {row_index} must be a list: {path}")
        normalized_row: list[int] = []
        previous = -1
        for column in row:
            if type(column) is not int:
                raise SearchIntegrityError(
                    f"{label} row {row_index} has invalid column: {path}"
                )
            if column < 0 or column >= num_cols:
                raise SearchIntegrityError(
                    f"{label} row {row_index} has out-of-range column: {path}"
                )
            if column <= previous:
                raise SearchIntegrityError(
                    f"{label} row {row_index} columns must be strictly increasing: {path}"
                )
            previous = column
            normalized_row.append(column)
        normalized_rows.append(normalized_row)
    return {"format": "sparse_rows", "num_cols": num_cols, "rows": normalized_rows}


def _validate_css_dimensions(
    hx: dict[str, Any],
    hz: dict[str, Any],
    dimensions: dict[str, int | None],
    instance_path: Path,
) -> None:
    n = dimensions["n"]
    mx = dimensions["mx"]
    mz = dimensions["mz"]
    if hx["num_cols"] != hz["num_cols"]:
        raise SearchIntegrityError(f"matrix column mismatch: {instance_path}")
    if hx["num_cols"] != n:
        raise SearchIntegrityError(f"matrix width mismatch: {instance_path}")
    if len(hx["rows"]) != mx:
        raise SearchIntegrityError(f"hx row count mismatch: {instance_path}")
    if len(hz["rows"]) != mz:
        raise SearchIntegrityError(f"hz row count mismatch: {instance_path}")


def _check_import_duplicates(candidates: tuple[ProposalImportCandidate, ...]) -> None:
    proposal_fingerprint_to_id: dict[str, str] = {}
    candidate_fingerprint_to_id: dict[str, str] = {}
    seen_candidate_ids: set[str] = set()
    for candidate in candidates:
        if candidate.candidate_id in seen_candidate_ids:
            raise SearchIntegrityError(
                f"duplicate candidate_id among imports: {candidate.candidate_id}"
            )
        seen_candidate_ids.add(candidate.candidate_id)
        _remember_unique_mapping(
            proposal_fingerprint_to_id,
            candidate.proposal_fingerprint,
            candidate.candidate_id,
            label="proposal fingerprint",
        )
        _remember_unique_mapping(
            candidate_fingerprint_to_id,
            candidate.candidate_fingerprint,
            candidate.candidate_id,
            label="candidate fingerprint",
        )


def _remember_unique_mapping(
    mapping: dict[str, str],
    fingerprint: str,
    candidate_id: str,
    *,
    label: str,
) -> None:
    existing = mapping.get(fingerprint)
    if existing is None:
        mapping[fingerprint] = candidate_id
        return
    if existing != candidate_id:
        raise SearchIntegrityError(
            f"duplicate {label}: {fingerprint} used by {existing} and {candidate_id}"
        )


def _existing_proposal_payload(candidate_spec: dict[str, Any]) -> dict[str, str] | None:
    provenance = candidate_spec.get("provenance")
    if not isinstance(provenance, dict):
        return None
    if provenance.get("kind") != "proposal-derived":
        return None
    proposal = provenance.get("proposal")
    if not isinstance(proposal, dict):
        raise SearchIntegrityError(
            "proposal-derived candidate missing provenance.proposal: "
            f"{candidate_spec.get('candidate_id')}"
        )
    proposal_fingerprint = _require_non_empty_string(
        proposal.get("proposal_fingerprint"),
        label="proposal_fingerprint on existing proposal-derived candidate",
    )
    candidate_fingerprint = _require_non_empty_string(
        proposal.get("candidate_fingerprint"),
        label="candidate_fingerprint on existing proposal-derived candidate",
    )
    return {
        "proposal_fingerprint": proposal_fingerprint,
        "candidate_fingerprint": candidate_fingerprint,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

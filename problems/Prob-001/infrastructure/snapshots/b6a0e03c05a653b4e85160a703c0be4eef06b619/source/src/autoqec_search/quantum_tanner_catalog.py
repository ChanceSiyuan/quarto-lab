from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from autoqec_search.eval_candidates import CandidateInput, ResolvedCandidate
from autoqec_search.load import SearchIntegrityError

DEFAULT_CATALOG_PATH = Path(
    "campaigns/examples/quantum-tanner-autoresearch/fixture_catalog.json"
)
EXPECTED_CATALOG_ID = "quantum-tanner-autoresearch-m1-fixtures"
EXPECTED_SCHEMA_VERSION = 1
EXPECTED_CANDIDATE_IDS = [
    "quantum-tanner-toric-d4",
    "quantum-tanner-toric-d6",
    "quantum-tanner-toric-d8",
]
DISTANCE_LADDER_PREFIX = "benchmarks/distance_ladders/"
DISTANCE_LADDER_ID = "surface-toric-bb-kasai-tanner-v2"
EXPECTED_ADAPTATION = "catalog-normalized-finite-css-instance"
EXPECTED_ENTRY_PROPERTIES = {
    "quantum-tanner-toric-d4": {
        "n": 16,
        "k": 2,
        "distance": 4,
        "base_group": "Z4xZ4",
        "qec_code_spec": "quantum_tanner:toric_d4",
    },
    "quantum-tanner-toric-d6": {
        "n": 36,
        "k": 2,
        "distance": 6,
        "base_group": "Z6xZ6",
        "qec_code_spec": "quantum_tanner:toric_d6",
    },
    "quantum-tanner-toric-d8": {
        "n": 64,
        "k": 2,
        "distance": 8,
        "base_group": "Z8xZ8",
        "qec_code_spec": "quantum_tanner:toric_d8",
    },
}


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise SearchIntegrityError(f"missing quantum tanner fixture catalog: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid quantum tanner fixture catalog: {path}") from exc


def _resolve_catalog_path(root: Path, catalog_path: str | Path) -> Path:
    path = Path(catalog_path)
    if path.is_absolute():
        return path
    return root / path


def _is_default_catalog_path(root: Path, catalog_path: str | Path) -> bool:
    return _resolve_catalog_path(root, catalog_path).resolve() == (
        root / DEFAULT_CATALOG_PATH
    ).resolve()


def _catalog_path_for_provenance(root: Path, catalog_path: str | Path) -> str:
    path = Path(catalog_path)
    if not path.is_absolute():
        return str(path)
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _is_plain_int(value: Any) -> bool:
    return type(value) is int


def _safe_repo_relative_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts) or not path.parts:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    return path


def _require_existing_file(root: Path, value: str, *, label: str) -> Path:
    path = _safe_repo_relative_path(value, label=label)
    resolved = (root / path).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise SearchIntegrityError(f"{label} must resolve within repository root: {value}")
    if not resolved.is_file():
        raise SearchIntegrityError(f"missing {label}: {resolved}")
    return resolved


def _require_existing_directory(root: Path, value: str, *, label: str) -> Path:
    path = _safe_repo_relative_path(value, label=label)
    resolved = (root / path).resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise SearchIntegrityError(f"{label} must resolve within repository root: {value}")
    if not resolved.is_dir():
        raise SearchIntegrityError(f"missing {label}: {resolved}")
    return resolved


def _validate_sparse_rows_matrix(path: Path, *, label: str) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    if payload.get("format") != "sparse_rows":
        raise SearchIntegrityError(f"{label} format must be sparse_rows: {path}")
    num_cols = payload.get("num_cols")
    rows = payload.get("rows")
    if not _is_plain_int(num_cols) or num_cols <= 0:
        raise SearchIntegrityError(f"{label} num_cols must be a positive integer: {path}")
    if not isinstance(rows, list):
        raise SearchIntegrityError(f"{label} rows must be a list: {path}")
    for row_index, row in enumerate(rows):
        if not isinstance(row, list):
            raise SearchIntegrityError(f"{label} row {row_index} must be a list: {path}")
        previous = -1
        for column in row:
            if not _is_plain_int(column):
                raise SearchIntegrityError(
                    f"{label} row {row_index} has invalid column: {path}"
                )
            if column < 0 or column >= num_cols:
                raise SearchIntegrityError(
                    f"{label} row {row_index} has invalid column: {path}"
                )
            if column <= previous:
                raise SearchIntegrityError(
                    f"{label} row {row_index} columns must be strictly increasing: {path}"
                )
            previous = column
    return payload


def _sparse_rows_to_dense_binary_matrix(payload: dict[str, Any]) -> dict[str, Any]:
    num_cols = int(payload["num_cols"])
    rows: list[list[int]] = []
    for sparse_row in payload["rows"]:
        dense_row = [0] * num_cols
        for column in sparse_row:
            dense_row[column] = 1
        rows.append(dense_row)
    return {
        "format": "dense_binary_matrix",
        "n_rows": len(rows),
        "n_cols": num_cols,
        "data": rows,
    }


def _validate_entry_numbers(entry: dict[str, Any]) -> None:
    if not _is_plain_int(entry["n"]) or entry["n"] <= 0:
        raise SearchIntegrityError("invalid n in quantum tanner fixture catalog")
    if not _is_plain_int(entry["k"]) or entry["k"] < 0:
        raise SearchIntegrityError("invalid k in quantum tanner fixture catalog")
    if not _is_plain_int(entry["distance"]) or entry["distance"] <= 0:
        raise SearchIntegrityError("invalid distance in quantum tanner fixture catalog")


def _normalize_quantum_tanner_spec(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(
            "invalid provenance quantum_tanner_spec in quantum tanner fixture catalog"
        )
    if value.startswith(DISTANCE_LADDER_PREFIX):
        return value[len(DISTANCE_LADDER_PREFIX) :]
    return value


def _normalize_generator(value: Any) -> str | dict[str, Any]:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        tool = value.get("tool")
        if isinstance(tool, str) and tool:
            return value
    raise SearchIntegrityError(
        "invalid provenance generator in quantum tanner fixture catalog"
    )


def _canonical_repo_relative_quantum_tanner_spec(
    root: Path,
    value: Any,
    *,
    distance_ladder_manifest: Any = None,
) -> str:
    normalized = _normalize_quantum_tanner_spec(value)
    root_resolved = root.resolve()

    def _try_resolve(path: Path) -> str | None:
        resolved = path.resolve()
        if resolved != root_resolved and root_resolved not in resolved.parents:
            return None
        if not resolved.is_file():
            return None
        return str(resolved.relative_to(root_resolved))

    direct = _try_resolve(root / normalized)
    if direct is not None:
        return direct

    if isinstance(distance_ladder_manifest, str) and distance_ladder_manifest:
        manifest_rel = _safe_repo_relative_path(
            distance_ladder_manifest,
            label="distance_ladder_manifest",
        )
        manifest_parent = (root / manifest_rel).resolve().parent
        via_manifest = _try_resolve(manifest_parent / normalized)
        if via_manifest is not None:
            return via_manifest

    via_prefix = _try_resolve(root / DISTANCE_LADDER_PREFIX / normalized)
    if via_prefix is not None:
        return via_prefix

    raise SearchIntegrityError(
        "invalid provenance quantum_tanner_spec in quantum tanner fixture catalog"
    )


def _expected_entry_metadata(candidate_id: str) -> dict[str, Any]:
    properties = EXPECTED_ENTRY_PROPERTIES.get(candidate_id)
    if properties is None:
        raise SearchIntegrityError(
            f"unexpected candidate_id in quantum tanner fixture catalog: {candidate_id}"
        )
    distance = properties["distance"]
    fixture_root = (
        f"benchmarks/distance_ladders/{DISTANCE_LADDER_ID}/instances/{candidate_id}"
    )
    quantum_tanner_spec = (
        f"benchmarks/distance_ladders/{DISTANCE_LADDER_ID}/"
        f"quantum_tanner_specs/toric-d{distance}.json"
    )
    return {
        "candidate_id": candidate_id,
        "code_id": "quantum-tanner-code",
        "n": properties["n"],
        "k": properties["k"],
        "distance": distance,
        "hx": f"{fixture_root}/hx.json",
        "hz": f"{fixture_root}/hz.json",
        "source_fixture_path": fixture_root,
        "source_instance": f"{fixture_root}/instance.json",
        "search_ready": True,
        "adaptation": EXPECTED_ADAPTATION,
        "provenance": {
            "kind": "distance-ladder-fixture",
            "label": candidate_id,
            "distance_ladder": DISTANCE_LADDER_ID,
            "qec_code_spec": properties["qec_code_spec"],
            "quantum_tanner_spec": quantum_tanner_spec,
            "generator": "qec-code",
            "construction_mode": "lr_cayley_no_cover_v1",
            "base_group": properties["base_group"],
        },
    }


def _validate_expected_entry_metadata(entry: dict[str, Any]) -> None:
    expected = _expected_entry_metadata(entry["candidate_id"])
    for key in (
        "code_id",
        "n",
        "k",
        "distance",
        "hx",
        "hz",
        "source_fixture_path",
        "source_instance",
        "search_ready",
        "adaptation",
    ):
        if entry.get(key) != expected[key]:
            raise SearchIntegrityError(
                f"{key} mismatch in quantum tanner fixture catalog"
            )
    if entry.get("provenance") != expected["provenance"]:
        raise SearchIntegrityError("provenance mismatch in quantum tanner fixture catalog")


def _validate_source_fixture_provenance(
    entry: dict[str, Any],
    *,
    root: Path,
    hx_path: Path,
    hz_path: Path,
    source_fixture_path: Path,
    source_instance_path: Path,
) -> None:
    expected_hx_path = (source_fixture_path / "hx.json").resolve()
    expected_hz_path = (source_fixture_path / "hz.json").resolve()
    expected_source_instance_path = (source_fixture_path / "instance.json").resolve()
    if hx_path != expected_hx_path:
        raise SearchIntegrityError("source fixture hx mismatch in quantum tanner fixture catalog")
    if hz_path != expected_hz_path:
        raise SearchIntegrityError("source fixture hz mismatch in quantum tanner fixture catalog")
    if source_instance_path != expected_source_instance_path:
        raise SearchIntegrityError(
            "source fixture instance path mismatch in quantum tanner fixture catalog"
        )

    source_instance = _load_json(source_instance_path)
    if not isinstance(source_instance, dict):
        raise SearchIntegrityError(
            "invalid source fixture instance in quantum tanner fixture catalog"
        )
    canonical_provenance_spec = _canonical_repo_relative_quantum_tanner_spec(
        root,
        entry["provenance"]["quantum_tanner_spec"],
        distance_ladder_manifest=entry["provenance"].get("distance_ladder_manifest"),
    )
    source_instance_quantum_tanner_spec = source_instance.get("quantum_tanner_spec")
    canonical_source_spec = _canonical_repo_relative_quantum_tanner_spec(
        root,
        source_instance_quantum_tanner_spec,
        distance_ladder_manifest=entry["provenance"].get("distance_ladder_manifest"),
    )
    expected_instance = {
        "instance_id": entry["candidate_id"],
        "code_id": entry["code_id"],
        "n": entry["n"],
        "k": entry["k"],
        "expected_distance": entry["distance"],
        "expected_bound_type": "exact",
        "qec_code_spec": entry["provenance"]["qec_code_spec"],
    }
    for key, expected in expected_instance.items():
        if source_instance.get(key) != expected:
            raise SearchIntegrityError(
                f"source fixture {key} mismatch in quantum tanner fixture catalog"
            )
    if canonical_source_spec != canonical_provenance_spec:
        raise SearchIntegrityError(
            "source fixture quantum_tanner_spec mismatch in quantum tanner fixture catalog"
        )
    if source_instance.get("artifacts") != {"hx": "hx.json", "hz": "hz.json"}:
        raise SearchIntegrityError(
            "source fixture artifacts mismatch in quantum tanner fixture catalog"
        )


def _validate_entry(
    root: Path,
    entry: dict[str, Any],
    candidate_ids: set[str],
    *,
    strict_smoke_catalog: bool,
) -> None:
    required_fields = {
        "candidate_id",
        "code_id",
        "n",
        "k",
        "distance",
        "hx",
        "hz",
        "source_fixture_path",
        "source_instance",
        "provenance",
        "search_ready",
        "adaptation",
    }
    missing = sorted(field for field in required_fields if field not in entry)
    if missing:
        raise SearchIntegrityError(
            "missing quantum tanner fixture catalog entry field: " + ", ".join(missing)
        )
    if not isinstance(entry["candidate_id"], str) or not entry["candidate_id"]:
        raise SearchIntegrityError("invalid candidate_id in quantum tanner fixture catalog")
    if entry["candidate_id"] in candidate_ids:
        raise SearchIntegrityError(f"duplicate candidate_id: {entry['candidate_id']}")
    candidate_ids.add(entry["candidate_id"])
    if not isinstance(entry["code_id"], str) or not entry["code_id"]:
        raise SearchIntegrityError("invalid code_id in quantum tanner fixture catalog")
    _validate_entry_numbers(entry)
    if not isinstance(entry["adaptation"], str) or not entry["adaptation"]:
        raise SearchIntegrityError("invalid adaptation in quantum tanner fixture catalog")
    if not isinstance(entry["search_ready"], bool):
        raise SearchIntegrityError("invalid search_ready in quantum tanner fixture catalog")

    hx_path = _require_existing_file(root, entry["hx"], label="hx artifact")
    hz_path = _require_existing_file(root, entry["hz"], label="hz artifact")
    source_fixture_path = _require_existing_directory(
        root,
        entry["source_fixture_path"],
        label="source fixture directory",
    )
    source_instance_path = _require_existing_file(
        root, entry["source_instance"], label="source_instance artifact"
    )

    provenance = entry["provenance"]
    if not isinstance(provenance, dict):
        raise SearchIntegrityError("invalid provenance in quantum tanner fixture catalog")
    for key in ("kind", "label", "qec_code_spec", "quantum_tanner_spec", "base_group"):
        if key not in provenance:
            raise SearchIntegrityError(
                f"missing provenance field {key} in quantum tanner fixture catalog"
            )
    if provenance["label"] != entry["candidate_id"]:
        raise SearchIntegrityError("provenance label mismatch in quantum tanner fixture catalog")
    if not isinstance(provenance["kind"], str) or not provenance["kind"]:
        raise SearchIntegrityError("invalid provenance kind in quantum tanner fixture catalog")
    if not isinstance(provenance["qec_code_spec"], str) or not provenance["qec_code_spec"]:
        raise SearchIntegrityError(
            "invalid provenance qec_code_spec in quantum tanner fixture catalog"
        )
    _canonical_repo_relative_quantum_tanner_spec(
        root,
        provenance["quantum_tanner_spec"],
        distance_ladder_manifest=provenance.get("distance_ladder_manifest"),
    )
    _normalize_generator(provenance.get("generator"))
    if not isinstance(provenance["base_group"], str) or not provenance["base_group"]:
        raise SearchIntegrityError(
            "invalid provenance base_group in quantum tanner fixture catalog"
        )

    _validate_source_fixture_provenance(
        entry,
        root=root,
        hx_path=hx_path,
        hz_path=hz_path,
        source_fixture_path=source_fixture_path,
        source_instance_path=source_instance_path,
    )

    hx = _validate_sparse_rows_matrix(hx_path, label="hx artifact")
    hz = _validate_sparse_rows_matrix(hz_path, label="hz artifact")
    if hx["num_cols"] != hz["num_cols"]:
        raise SearchIntegrityError("hx and hz num_cols mismatch in quantum tanner fixture catalog")
    if hx["num_cols"] != entry["n"]:
        raise SearchIntegrityError("matrix width mismatch in quantum tanner fixture catalog")
    if strict_smoke_catalog:
        _validate_expected_entry_metadata(entry)


def _validate_entry_payload(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise SearchIntegrityError("quantum tanner fixture catalog entry must be an object")
    required_fields = {
        "candidate_id",
        "code_id",
        "n",
        "k",
        "distance",
        "hx",
        "hz",
        "source_fixture_path",
        "source_instance",
        "provenance",
        "search_ready",
        "adaptation",
    }
    missing = sorted(field for field in required_fields if field not in entry)
    if missing:
        raise SearchIntegrityError(
            "missing quantum tanner fixture catalog entry field: " + ", ".join(missing)
        )
    provenance = entry["provenance"]
    if not isinstance(provenance, dict):
        raise SearchIntegrityError("invalid provenance in quantum tanner fixture catalog")
    for key in ("kind", "label", "qec_code_spec", "quantum_tanner_spec", "base_group"):
        if key not in provenance:
            raise SearchIntegrityError(
                f"missing provenance field {key} in quantum tanner fixture catalog"
            )
    if not isinstance(entry["candidate_id"], str) or not entry["candidate_id"]:
        raise SearchIntegrityError("invalid candidate_id in quantum tanner fixture catalog")
    if not isinstance(entry["code_id"], str) or not entry["code_id"]:
        raise SearchIntegrityError("invalid code_id in quantum tanner fixture catalog")
    _validate_entry_numbers(entry)
    if not isinstance(entry["search_ready"], bool):
        raise SearchIntegrityError("invalid search_ready in quantum tanner fixture catalog")
    if not isinstance(entry["adaptation"], str) or not entry["adaptation"]:
        raise SearchIntegrityError("invalid adaptation in quantum tanner fixture catalog")
    if not isinstance(provenance["kind"], str) or not provenance["kind"]:
        raise SearchIntegrityError("invalid provenance kind in quantum tanner fixture catalog")
    if not isinstance(provenance["label"], str) or not provenance["label"]:
        raise SearchIntegrityError("invalid provenance label in quantum tanner fixture catalog")
    if provenance["label"] != entry["candidate_id"]:
        raise SearchIntegrityError("provenance label mismatch in quantum tanner fixture catalog")
    if not isinstance(provenance["qec_code_spec"], str) or not provenance["qec_code_spec"]:
        raise SearchIntegrityError(
            "invalid provenance qec_code_spec in quantum tanner fixture catalog"
        )
    _normalize_quantum_tanner_spec(provenance["quantum_tanner_spec"])
    _normalize_generator(provenance.get("generator"))
    if not isinstance(provenance["base_group"], str) or not provenance["base_group"]:
        raise SearchIntegrityError(
            "invalid provenance base_group in quantum tanner fixture catalog"
        )
    return entry


def _validate_quantum_tanner_fixture_entry(
    root: Path,
    entry: Any,
    *,
    require_search_ready: bool,
) -> dict[str, Any]:
    entry = _validate_entry_payload(entry)
    if require_search_ready and entry.get("search_ready") is not True:
        raise SearchIntegrityError(
            f"quantum tanner fixture entry is not search-ready: {entry.get('candidate_id')}"
        )

    hx_path = _require_existing_file(root, entry["hx"], label="hx artifact")
    hz_path = _require_existing_file(root, entry["hz"], label="hz artifact")
    source_fixture_path = _require_existing_directory(
        root,
        entry["source_fixture_path"],
        label="source fixture directory",
    )
    source_instance_path = _require_existing_file(
        root,
        entry["source_instance"],
        label="source_instance artifact",
    )
    quantum_tanner_spec_path = _require_existing_file(
        root,
        _canonical_repo_relative_quantum_tanner_spec(
            root,
            entry["provenance"]["quantum_tanner_spec"],
            distance_ladder_manifest=entry["provenance"].get("distance_ladder_manifest"),
        ),
        label="quantum_tanner_spec artifact",
    )

    _validate_source_fixture_provenance(
        entry,
        root=root,
        hx_path=hx_path,
        hz_path=hz_path,
        source_fixture_path=source_fixture_path,
        source_instance_path=source_instance_path,
    )

    hx = _validate_sparse_rows_matrix(hx_path, label="hx artifact")
    hz = _validate_sparse_rows_matrix(hz_path, label="hz artifact")
    if hx["num_cols"] != hz["num_cols"]:
        raise SearchIntegrityError("hx and hz num_cols mismatch in quantum tanner fixture catalog")
    if hx["num_cols"] != entry["n"]:
        raise SearchIntegrityError("matrix width mismatch in quantum tanner fixture catalog")

    return {
        "entry": entry,
        "hx_path": hx_path,
        "hz_path": hz_path,
        "source_fixture_path": source_fixture_path,
        "source_instance_path": source_instance_path,
        "quantum_tanner_spec_path": quantum_tanner_spec_path,
        "hx_payload": hx,
        "hz_payload": hz,
    }


def _validate_catalog_payload(
    root: Path,
    payload: Any,
    *,
    strict_smoke_catalog: bool,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SearchIntegrityError("invalid quantum tanner fixture catalog")
    if strict_smoke_catalog:
        if payload.get("catalog_id") != EXPECTED_CATALOG_ID:
            raise SearchIntegrityError("catalog_id mismatch in quantum tanner fixture catalog")
    elif not isinstance(payload.get("catalog_id"), str) or not payload.get("catalog_id"):
        raise SearchIntegrityError("invalid catalog_id in quantum tanner fixture catalog")
    if payload.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise SearchIntegrityError("schema_version mismatch in quantum tanner fixture catalog")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise SearchIntegrityError("quantum tanner fixture catalog entries must be a non-empty list")
    candidate_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SearchIntegrityError("quantum tanner fixture catalog entry must be an object")
        _validate_entry(
            root,
            entry,
            candidate_ids,
            strict_smoke_catalog=strict_smoke_catalog,
        )
    if strict_smoke_catalog and [entry["candidate_id"] for entry in entries] != EXPECTED_CANDIDATE_IDS:
        raise SearchIntegrityError(
            "candidate_id set/order mismatch in quantum tanner fixture catalog"
        )
    return payload


def load_quantum_tanner_fixture_catalog(
    root: Path,
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
    *,
    strict_smoke_catalog: bool | None = None,
) -> dict[str, Any]:
    resolved_catalog_path = _resolve_catalog_path(root, catalog_path)
    payload = _load_json(resolved_catalog_path)
    if strict_smoke_catalog is None:
        strict_smoke_catalog = _is_default_catalog_path(root, catalog_path)
    return _validate_catalog_payload(
        root,
        payload,
        strict_smoke_catalog=strict_smoke_catalog,
    )


def validate_quantum_tanner_fixture_catalog(
    root: Path,
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
    *,
    strict_smoke_catalog: bool | None = None,
) -> None:
    load_quantum_tanner_fixture_catalog(
        root,
        catalog_path,
        strict_smoke_catalog=strict_smoke_catalog,
    )


def _build_normalized_quantum_tanner_instance(
    entry: dict[str, Any],
    *,
    hx_payload: dict[str, Any],
    hz_payload: dict[str, Any],
    catalog_provenance_path: str,
) -> dict[str, Any]:
    return {
        "id": entry["candidate_id"],
        "code_id": entry["code_id"],
        "family_id": "quantum-tanner-code",
        "title": f"Quantum Tanner Toric Fixture d={entry['distance']}",
        "instance_kind": "finite_css_instance",
        "matrix_format": "dense_binary_json",
        "parameters": {
            "distance": entry["distance"],
            "construction": "quantum-tanner-toric",
            "source_fixture_id": entry["candidate_id"],
            "qec_code_spec": entry["provenance"]["qec_code_spec"],
            "quantum_tanner_spec": entry["provenance"]["quantum_tanner_spec"],
            "base_group": entry["provenance"]["base_group"],
        },
        "derived_properties": {
            "n": entry["n"],
            "k": entry["k"],
            "distance": entry["distance"],
            "bound_type": "exact",
            "mx": len(hx_payload["rows"]),
            "mz": len(hz_payload["rows"]),
        },
        "artifacts": {"hx": "hx.json", "hz": "hz.json"},
        "provenance": {
            "source": "quantum-tanner-fixture-catalog",
            "catalog": catalog_provenance_path,
            "source_fixture_path": entry["source_fixture_path"],
            "source_instance": entry["source_instance"],
            "adaptation": entry["adaptation"],
            "fixture_provenance": dict(entry["provenance"]),
        },
    }


def normalize_quantum_tanner_fixture_entry(
    root: Path,
    entry: dict[str, Any],
    *,
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
) -> dict[str, Any]:
    validated = _validate_quantum_tanner_fixture_entry(root, entry, require_search_ready=True)
    return _build_normalized_quantum_tanner_instance(
        validated["entry"],
        hx_payload=validated["hx_payload"],
        hz_payload=validated["hz_payload"],
        catalog_provenance_path=_catalog_path_for_provenance(root, catalog_path),
    )

def resolve_quantum_tanner_fixture_entry(
    root: Path,
    entry: dict[str, Any],
    *,
    campaign_id: str = "quantum-tanner-autoresearch",
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
) -> ResolvedCandidate:
    validated = _validate_quantum_tanner_fixture_entry(root, entry, require_search_ready=True)
    entry = validated["entry"]
    normalized = _build_normalized_quantum_tanner_instance(
        entry,
        hx_payload=validated["hx_payload"],
        hz_payload=validated["hz_payload"],
        catalog_provenance_path=_catalog_path_for_provenance(root, catalog_path),
    )
    spec = CandidateInput(
        candidate_id=entry["candidate_id"],
        campaign_id=campaign_id,
        code_family=entry["code_id"],
        parameters=dict(normalized["parameters"]),
        provenance={
            "kind": entry["provenance"]["kind"],
            "label": entry["candidate_id"],
        },
    )
    artifact_root = validated["source_fixture_path"]
    return ResolvedCandidate(
        spec=spec,
        artifact_root=artifact_root,
        instance=normalized,
        hx=_sparse_rows_to_dense_binary_matrix(validated["hx_payload"]),
        hz=_sparse_rows_to_dense_binary_matrix(validated["hz_payload"]),
        source_kind="quantum-tanner-fixture-catalog",
    )

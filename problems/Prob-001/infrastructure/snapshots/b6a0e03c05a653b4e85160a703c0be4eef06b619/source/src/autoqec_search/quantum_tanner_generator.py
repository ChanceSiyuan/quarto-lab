from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_catalog import (
    DEFAULT_CATALOG_PATH,
    EXPECTED_CATALOG_ID,
    validate_quantum_tanner_fixture_catalog,
)


DEFAULT_QEC_CODE_BIN = "qec-code"
DEFAULT_DISTANCE_LADDER_EXPORTER_BIN = "autoqec-distance-ladder"
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
    distance_ladder_manifest_path: Path
    expected_bound_type: str
    qec_code_bin: str
    distance_ladder_exporter_bin: str
    candidates: tuple[QuantumTannerSweepCandidate, ...]
    config_path: Path | None = None


@dataclass(frozen=True)
class QuantumTannerAutoresearchFiles:
    catalog_path: Path
    search_space_path: Path
    catalog: dict[str, Any]
    search_space: dict[str, Any]


@dataclass(frozen=True)
class QuantumTannerGenerationPlan:
    repo_root: Path
    manifest_path: Path
    spec_paths: tuple[Path, ...]
    specs: tuple[dict[str, Any], ...]
    manifest: dict[str, Any]
    write_paths: tuple[Path, ...]
    materialization: MaterializationResult | None = None
    autoresearch_files: QuantumTannerAutoresearchFiles | None = None


@dataclass(frozen=True)
class MaterializationResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


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
    payload: object,
    *,
    config_path: Path | None = None,
) -> QuantumTannerSweepConfig:
    normalized_payload = _require_object(payload)
    campaign_id = _require_string(normalized_payload, "campaign_id")
    code_id = _require_string(normalized_payload, "code_id")
    output_root = _safe_repo_relative_path(normalized_payload, "output_root")
    spec_root = _safe_repo_relative_path(normalized_payload, "spec_root")
    instance_root = _safe_repo_relative_path(normalized_payload, "instance_root")
    catalog_path = _safe_repo_relative_path(normalized_payload, "catalog_path")
    search_space_path = _safe_repo_relative_path(normalized_payload, "search_space_path")
    distance_ladder_manifest_path = _safe_repo_relative_path(
        normalized_payload,
        "distance_ladder_manifest_path",
    ) if "distance_ladder_manifest_path" in normalized_payload else output_root / "distance_ladder.json"
    expected_bound_type = _require_string(normalized_payload, "expected_bound_type")
    if expected_bound_type not in VALID_EXPECTED_BOUND_TYPES:
        raise SearchIntegrityError(
            "expected_bound_type must be one of: "
            + ", ".join(sorted(VALID_EXPECTED_BOUND_TYPES))
        )
    qec_code_bin = normalized_payload.get("qec_code_bin", DEFAULT_QEC_CODE_BIN)
    if not isinstance(qec_code_bin, str) or not qec_code_bin:
        raise SearchIntegrityError("qec_code_bin must be a non-empty string")
    distance_ladder_exporter_bin = normalized_payload.get(
        "distance_ladder_exporter_bin",
        DEFAULT_DISTANCE_LADDER_EXPORTER_BIN,
    )
    if (
        not isinstance(distance_ladder_exporter_bin, str)
        or not distance_ladder_exporter_bin
    ):
        raise SearchIntegrityError(
            "distance_ladder_exporter_bin must be a non-empty string"
        )
    distances = _normalize_distances(normalized_payload)
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
        distance_ladder_manifest_path=distance_ladder_manifest_path,
        expected_bound_type=expected_bound_type,
        qec_code_bin=qec_code_bin,
        distance_ladder_exporter_bin=distance_ladder_exporter_bin,
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
        f"distance_ladder_manifest_path: {config.distance_ladder_manifest_path}",
        f"expected_bound_type: {config.expected_bound_type}",
        f"qec_code_bin: {config.qec_code_bin}",
        f"distance_ladder_exporter_bin: {config.distance_ladder_exporter_bin}",
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


def build_toric_quantum_tanner_spec(distance: int, *, fixture_id: str) -> dict[str, Any]:
    order = distance * distance
    return {
        "fixture_id": fixture_id,
        "construction_mode": "lr_cayley_no_cover_v1",
        "base_group": {
            "name": f"Z{distance}xZ{distance}",
            "element_order": (
                f"id = {distance}*x + y for (x,y) in Z{distance} x Z{distance}"
            ),
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


def _resolve_repo_path(repo_root: Path, path: Path, *, label: str) -> Path:
    if path.is_absolute() or not path.parts or any(part == ".." for part in path.parts):
        raise SearchIntegrityError(f"{label} must resolve within repository root: {path}")
    resolved_root = repo_root.resolve()
    resolved = (repo_root / path).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise SearchIntegrityError(f"{label} must resolve within repository root: {path}")
    return resolved


def _path_text(path: Path) -> str:
    return path.as_posix()


def _repo_relative_path(repo_root: Path, path: Path, *, label: str) -> str:
    resolved = path.resolve()
    root_resolved = repo_root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise SearchIntegrityError(f"{label} must resolve within repository root: {path}")
    return _path_text(resolved.relative_to(root_resolved))


def _load_required_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    return payload


def _candidate_sort_key(candidate: QuantumTannerSweepCandidate) -> tuple[int, str]:
    return (candidate.distance, candidate.candidate_id)


def _source_instance_quantum_tanner_spec(
    plan: QuantumTannerGenerationPlan,
    instance: dict[str, Any],
) -> str:
    value = instance.get("quantum_tanner_spec")
    if not isinstance(value, str) or not value:
        raise SearchIntegrityError(
            "source instance quantum_tanner_spec must be a non-empty string"
        )
    spec_path = Path(value)
    if spec_path.is_absolute():
        return _repo_relative_path(
            plan.repo_root,
            spec_path,
            label="source instance quantum_tanner_spec",
        )
    resolved = (plan.manifest_path.parent / spec_path).resolve()
    return _repo_relative_path(
        plan.repo_root,
        resolved,
        label="source instance quantum_tanner_spec",
    )


def _normalize_generator_provenance(
    instance: dict[str, Any],
    *,
    fallback_tool: str,
) -> str | dict[str, Any]:
    generator = instance.get("generator")
    if isinstance(generator, dict) and isinstance(generator.get("tool"), str) and generator["tool"]:
        return generator
    if isinstance(generator, str) and generator:
        return generator
    return fallback_tool


def _manifest_artifact_root(manifest_path: Path, instance_root: Path) -> str:
    manifest_parent = manifest_path.parent
    try:
        return _path_text(instance_root.relative_to(manifest_parent))
    except ValueError:
        return _path_text(Path(os.path.relpath(instance_root, manifest_parent)))


def _manifest_relative_path(manifest_path: Path, target_path: Path) -> str:
    manifest_parent = manifest_path.parent
    try:
        return _path_text(target_path.relative_to(manifest_parent))
    except ValueError:
        return _path_text(Path(os.path.relpath(target_path, manifest_parent)))


def _is_explicit_tool_path(value: str) -> bool:
    if Path(value).is_absolute():
        return True
    separators = {os.sep}
    if os.altsep is not None:
        separators.add(os.altsep)
    return any(separator in value for separator in separators)


def _validate_materialization_tool_paths(config: QuantumTannerSweepConfig) -> None:
    if not _is_explicit_tool_path(config.qec_code_bin):
        raise SearchIntegrityError(
            "qec_code_bin must be an explicit path when materialize=True"
        )
    if not _is_explicit_tool_path(config.distance_ladder_exporter_bin):
        raise SearchIntegrityError(
            "distance_ladder_exporter_bin must be an explicit path when materialize=True"
        )


def _exporter_command(
    plan: QuantumTannerGenerationPlan,
    config: QuantumTannerSweepConfig,
    *,
    force: bool,
) -> tuple[str, ...]:
    command = (
        config.distance_ladder_exporter_bin,
        "export",
        "--manifest",
        str(plan.manifest_path),
        "--qec-code-bin",
        config.qec_code_bin,
    )
    if force:
        command = (*command, "--force")
    return command


def _format_exporter_failure(
    command: tuple[str, ...],
    result: subprocess.CompletedProcess[str],
) -> str:
    return "\n".join(
        [
            "distance-ladder exporter failed",
            "command: " + " ".join(command),
            f"exit_code: {result.returncode}",
            "stdout:",
            result.stdout.rstrip(),
            "stderr:",
            result.stderr.rstrip(),
        ]
    )


def _format_exporter_oserror(command: tuple[str, ...], err: OSError) -> str:
    return "\n".join(
        [
            "distance-ladder exporter failed",
            "command: " + " ".join(command),
            "stdout:",
            "",
            "stderr:",
            str(err),
        ]
    )


def plan_quantum_tanner_sweep_generation(
    repo_root: Path,
    config: QuantumTannerSweepConfig,
) -> QuantumTannerGenerationPlan:
    resolved_repo_root = repo_root.resolve()
    manifest_path = _resolve_repo_path(
        resolved_repo_root,
        config.distance_ladder_manifest_path,
        label="distance ladder manifest path",
    )
    seen_candidate_ids: set[str] = set()
    spec_paths: list[Path] = []
    specs: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for candidate in config.candidates:
        if candidate.candidate_id in seen_candidate_ids:
            raise SearchIntegrityError(
                f"duplicate candidate_id in quantum Tanner sweep config: {candidate.candidate_id}"
            )
        seen_candidate_ids.add(candidate.candidate_id)
        spec_path = _resolve_repo_path(
            resolved_repo_root,
            candidate.quantum_tanner_spec_path,
            label="spec output path",
        )
        spec_paths.append(spec_path)
        specs.append(
            build_toric_quantum_tanner_spec(
                candidate.distance,
                fixture_id=candidate.candidate_id,
            )
        )
        entries.append(
            {
                "instance_id": candidate.candidate_id,
                "code_id": config.code_id,
                "qec_code_spec": candidate.qec_code_spec,
                "quantum_tanner_spec": _manifest_relative_path(manifest_path, spec_path),
                "n": candidate.distance * candidate.distance,
                "k": 2,
                "expected_distance": candidate.distance,
                "expected_bound_type": config.expected_bound_type,
            }
        )

    resolved_instance_root = _resolve_repo_path(
        resolved_repo_root,
        config.instance_root,
        label="instance root",
    )
    manifest = {
        "id": config.campaign_id,
        "title": f"{config.campaign_id} distance ladder",
        "artifact_root": _manifest_artifact_root(manifest_path, resolved_instance_root),
        "results_table": f"{manifest_path.stem}-results.csv",
        "entries": entries,
    }
    write_paths = (*spec_paths, manifest_path)
    return QuantumTannerGenerationPlan(
        repo_root=resolved_repo_root,
        manifest_path=manifest_path,
        spec_paths=tuple(spec_paths),
        specs=tuple(specs),
        manifest=manifest,
        write_paths=tuple(write_paths),
    )


def materialize_quantum_tanner_sweep(
    plan: QuantumTannerGenerationPlan,
    config: QuantumTannerSweepConfig,
    *,
    force: bool = False,
) -> MaterializationResult:
    _validate_materialization_tool_paths(config)
    candidate_dirs = _resolved_candidate_instance_dirs(plan, config)
    newly_created_candidate_dirs = tuple(
        candidate_dir for candidate_dir in candidate_dirs if not candidate_dir.exists()
    )
    missing_candidate_artifacts = _snapshot_missing_candidate_artifacts(candidate_dirs)
    command = _exporter_command(plan, config, force=force)
    try:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=plan.repo_root,
            )
        except OSError as err:
            raise SearchIntegrityError(_format_exporter_oserror(command, err)) from err
        if completed.returncode != 0:
            raise SearchIntegrityError(_format_exporter_failure(command, completed))
    except SearchIntegrityError:
        _cleanup_new_candidate_artifacts(missing_candidate_artifacts)
        _cleanup_new_candidate_dirs(newly_created_candidate_dirs)
        raise
    return MaterializationResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _resolved_candidate_instance_dirs(
    plan: QuantumTannerGenerationPlan,
    config: QuantumTannerSweepConfig,
) -> tuple[Path, ...]:
    return tuple(
        _resolve_repo_path(
            plan.repo_root,
            candidate.instance_dir,
            label=f"instance directory for {candidate.candidate_id}",
        )
        for candidate in config.candidates
    )


def _cleanup_new_candidate_dirs(candidate_dirs: tuple[Path, ...]) -> None:
    for candidate_dir in candidate_dirs:
        if candidate_dir.exists():
            shutil.rmtree(candidate_dir)


def _candidate_artifact_paths(candidate_dir: Path) -> tuple[Path, ...]:
    return (
        candidate_dir / "instance.json",
        candidate_dir / "hx.json",
        candidate_dir / "hz.json",
    )


def _snapshot_missing_candidate_artifacts(candidate_dirs: tuple[Path, ...]) -> tuple[Path, ...]:
    return tuple(
        artifact
        for candidate_dir in candidate_dirs
        for artifact in _candidate_artifact_paths(candidate_dir)
        if not artifact.exists()
    )


def _cleanup_new_candidate_artifacts(artifact_paths: tuple[Path, ...]) -> None:
    for artifact_path in artifact_paths:
        if artifact_path.exists():
            artifact_path.unlink()


def _generator_tool_name(qec_code_bin: str) -> str:
    return Path(qec_code_bin).name if qec_code_bin else qec_code_bin


def _catalog_id_for_path(catalog_path: Path) -> str:
    if catalog_path == DEFAULT_CATALOG_PATH:
        return EXPECTED_CATALOG_ID
    return "generated-quantum-tanner-fixtures"


def _build_quantum_tanner_fixture_catalog(
    plan: QuantumTannerGenerationPlan,
    config: QuantumTannerSweepConfig,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    generator_tool = _generator_tool_name(config.qec_code_bin)
    for candidate in sorted(config.candidates, key=_candidate_sort_key):
        instance_dir = _resolve_repo_path(
            plan.repo_root,
            candidate.instance_dir,
            label=f"source fixture directory for {candidate.candidate_id}",
        )
        instance_path = _resolve_repo_path(
            plan.repo_root,
            candidate.instance_path,
            label=f"source_instance artifact for {candidate.candidate_id}",
        )
        hx_path = _resolve_repo_path(
            plan.repo_root,
            candidate.hx_path,
            label=f"hx artifact for {candidate.candidate_id}",
        )
        hz_path = _resolve_repo_path(
            plan.repo_root,
            candidate.hz_path,
            label=f"hz artifact for {candidate.candidate_id}",
        )
        spec_path = _resolve_repo_path(
            plan.repo_root,
            candidate.quantum_tanner_spec_path,
            label=f"quantum_tanner_spec artifact for {candidate.candidate_id}",
        )
        instance = _load_required_json_object(instance_path, "source_instance artifact")
        generated_spec = _load_required_json_object(spec_path, "quantum_tanner_spec artifact")
        source_quantum_tanner_spec = _source_instance_quantum_tanner_spec(plan, instance)
        base_group = generated_spec.get("base_group")
        base_group_name = None
        if isinstance(base_group, dict):
            name = base_group.get("name")
            if isinstance(name, str) and name:
                base_group_name = name
        construction_mode = generated_spec.get("construction_mode")
        if not hx_path.is_file():
            raise SearchIntegrityError(f"missing hx artifact: {hx_path}")
        if not hz_path.is_file():
            raise SearchIntegrityError(f"missing hz artifact: {hz_path}")
        entry = {
            "candidate_id": candidate.candidate_id,
            "code_id": config.code_id,
            "n": instance["n"],
            "k": instance["k"],
            "distance": instance["expected_distance"],
            "hx": _repo_relative_path(plan.repo_root, hx_path, label="hx artifact"),
            "hz": _repo_relative_path(plan.repo_root, hz_path, label="hz artifact"),
            "source_fixture_path": _repo_relative_path(
                plan.repo_root,
                instance_dir,
                label="source fixture directory",
            ),
            "source_instance": _repo_relative_path(
                plan.repo_root,
                instance_path,
                label="source_instance artifact",
            ),
            "provenance": {
                "kind": "distance-ladder-fixture",
                "label": candidate.candidate_id,
                "distance_ladder_manifest": _repo_relative_path(
                    plan.repo_root,
                    plan.manifest_path,
                    label="distance ladder manifest",
                ),
                "qec_code_spec": instance["qec_code_spec"],
                "quantum_tanner_spec": source_quantum_tanner_spec,
                "generator": _normalize_generator_provenance(
                    instance,
                    fallback_tool=generator_tool,
                ),
                "construction_mode": construction_mode,
                "base_group": base_group_name,
            },
            "search_ready": True,
            "adaptation": "catalog-normalized-finite-css-instance",
        }
        entries.append(entry)
    return {
        "catalog_id": _catalog_id_for_path(config.catalog_path),
        "schema_version": 1,
        "entries": entries,
    }


def _build_quantum_tanner_search_space(config: QuantumTannerSweepConfig) -> dict[str, Any]:
    return {
        "campaign_id": config.campaign_id,
        "mode": "explicit_list",
        "candidate_specs": [
            {
                "candidate_id": candidate.candidate_id,
                "code_family": config.code_id,
                "fixture_catalog_path": _path_text(config.catalog_path),
                "provenance": {
                    "kind": "distance-ladder-fixture",
                    "label": candidate.candidate_id,
                },
            }
            for candidate in sorted(config.candidates, key=_candidate_sort_key)
        ],
    }


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def _validate_workspace_visible_search_space_path(
    repo_root: Path,
    config: QuantumTannerSweepConfig,
) -> None:
    if config.search_space_path.name != "search_space.json":
        raise SearchIntegrityError(
            "search_space_path must be named search_space.json so validate --root can load it"
        )
    search_space_path = _resolve_repo_path(
        repo_root,
        config.search_space_path,
        label="search space path",
    )
    root_resolved = repo_root.resolve()
    search_space_rel = search_space_path.resolve().relative_to(root_resolved)
    if not search_space_rel.parts or search_space_rel.parts[0] != "campaigns":
        raise SearchIntegrityError(
            "search_space_path must be under campaigns/ so validate --root can load it"
        )
    campaign_path = search_space_path.with_name("campaign.json")
    if not campaign_path.is_file():
        raise SearchIntegrityError(
            "search_space_path must be adjacent to campaign.json so validate --root can load it"
        )


def _emit_quantum_tanner_autoresearch_files_from_plan(
    plan: QuantumTannerGenerationPlan,
    config: QuantumTannerSweepConfig,
) -> QuantumTannerAutoresearchFiles:
    _validate_workspace_visible_search_space_path(plan.repo_root, config)
    catalog_path = _resolve_repo_path(
        plan.repo_root,
        config.catalog_path,
        label="fixture catalog path",
    )
    search_space_path = _resolve_repo_path(
        plan.repo_root,
        config.search_space_path,
        label="search space path",
    )
    catalog = _build_quantum_tanner_fixture_catalog(plan, config)
    search_space = _build_quantum_tanner_search_space(config)
    _write_json_file(catalog_path, catalog)
    _write_json_file(search_space_path, search_space)
    validate_quantum_tanner_fixture_catalog(plan.repo_root, config.catalog_path)
    return QuantumTannerAutoresearchFiles(
        catalog_path=catalog_path,
        search_space_path=search_space_path,
        catalog=catalog,
        search_space=search_space,
    )


def emit_quantum_tanner_autoresearch_files(
    repo_root: Path | QuantumTannerGenerationPlan,
    config: QuantumTannerSweepConfig,
    *,
    dry_run: bool = False,
    materialize: bool = True,
    force: bool = False,
) -> QuantumTannerAutoresearchFiles | None:
    if isinstance(repo_root, QuantumTannerGenerationPlan):
        return _emit_quantum_tanner_autoresearch_files_from_plan(repo_root, config)
    resolved_repo_root = Path(repo_root).resolve()
    plan = generate_quantum_tanner_sweep(
        resolved_repo_root,
        config,
        dry_run=dry_run,
        materialize=materialize,
        force=force,
    )
    if not dry_run and not materialize:
        emitted = _emit_quantum_tanner_autoresearch_files_from_plan(plan, config)
        plan = replace(plan, autoresearch_files=emitted)
    if plan.autoresearch_files is None:
        return None
    catalog_path = (
        config.catalog_path
        if config.catalog_path.is_absolute()
        else resolved_repo_root / config.catalog_path
    )
    search_space_path = (
        config.search_space_path
        if config.search_space_path.is_absolute()
        else resolved_repo_root / config.search_space_path
    )
    return replace(
        plan.autoresearch_files,
        catalog_path=catalog_path,
        search_space_path=search_space_path,
    )


def generate_quantum_tanner_sweep(
    repo_root: Path,
    config: QuantumTannerSweepConfig,
    *,
    dry_run: bool = False,
    materialize: bool = False,
    force: bool = False,
) -> QuantumTannerGenerationPlan:
    if materialize:
        _validate_materialization_tool_paths(config)
        if not dry_run:
            _validate_workspace_visible_search_space_path(repo_root, config)
    plan = plan_quantum_tanner_sweep_generation(repo_root, config)
    if dry_run:
        return plan

    for path in plan.write_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    for spec_path, spec in zip(plan.spec_paths, plan.specs, strict=True):
        spec_path.write_text(json.dumps(spec, indent=2, sort_keys=False) + "\n")
    plan.manifest_path.write_text(
        json.dumps(plan.manifest, indent=2, sort_keys=False) + "\n"
    )
    materialization = None
    if materialize:
        materialization = materialize_quantum_tanner_sweep(
            plan,
            config,
            force=force,
        )
        plan = replace(plan, materialization=materialization)
        plan = replace(
            plan,
            autoresearch_files=_emit_quantum_tanner_autoresearch_files_from_plan(
                plan,
                config,
            ),
        )
    return plan


def render_quantum_tanner_generation_summary(
    plan: QuantumTannerGenerationPlan,
    *,
    dry_run: bool,
) -> str:
    action = "would write" if dry_run else "wrote"
    lines = [
        (
            f"{action} {len(plan.spec_paths)} quantum Tanner specs and 1 distance ladder "
            f"manifest for {plan.manifest['id']}"
        ),
        f"manifest_path: {plan.manifest_path}",
        "candidate_ids: "
        + ", ".join(entry["instance_id"] for entry in plan.manifest["entries"]),
    ]
    if plan.materialization is not None:
        lines.extend(
            [
                f"materialized {len(plan.manifest['entries'])} quantum Tanner instances",
                "exporter_command: " + " ".join(plan.materialization.command),
            ]
        )
    if plan.autoresearch_files is not None:
        lines.extend(
            [
                f"emitted fixture_catalog: {plan.autoresearch_files.catalog_path}",
                f"emitted search_space: {plan.autoresearch_files.search_space_path}",
            ]
        )
    return "\n".join(lines) + "\n"

from __future__ import annotations

import json
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_catalog import resolve_quantum_tanner_fixture_entry
from autoqec_search.upper_bound_witness_finder import (
    convert_qec_code_random_window_upper_bound_result,
    run_qec_code_random_window_upper_bound,
)


def _safe_relative_repo_path(value: str | Path, *, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or any(part == ".." for part in path.parts) or not path.parts:
        raise SearchIntegrityError(f"{label} must be a safe relative path: {value}")
    return path


def _resolve_within_root(root: Path, repo_path: Path, *, label: str) -> Path:
    resolved_root = root.resolve()
    resolved_path = (root / repo_path).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise SearchIntegrityError(f"{label} must resolve within repository root: {repo_path}")
    return resolved_path


def _resolve_repo_path(root: Path, value: str | Path, *, label: str) -> tuple[Path, Path]:
    repo_path = _safe_relative_repo_path(value, label=label)
    return repo_path, _resolve_within_root(root, repo_path, label=label)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    return payload


def _prepare_json_write(path: Path, payload: dict[str, Any], *, label: str) -> Path:
    if path.is_dir():
        raise SearchIntegrityError(f"{label} output path must not be a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(text)
        return Path(tmp.name)


def _atomic_write_json(path: Path, payload: dict[str, Any], *, label: str) -> None:
    tmp_path: Path | None = None
    try:
        tmp_path = _prepare_json_write(path, payload, label=label)
        tmp_path.replace(path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _candidate_specs(search_space: dict[str, Any]) -> list[dict[str, Any]]:
    candidate_specs = search_space.get("candidate_specs")
    if not isinstance(candidate_specs, list) or not candidate_specs:
        raise SearchIntegrityError("search_space candidate_specs must be a non-empty list")
    validated: list[dict[str, Any]] = []
    for candidate_spec in candidate_specs:
        if not isinstance(candidate_spec, dict):
            raise SearchIntegrityError("search_space candidate_spec must be an object")
        validated.append(dict(candidate_spec))
    return validated


def _resolve_campaign_search_space_path(root: Path, campaign_id: str) -> Path:
    matches: list[Path] = []
    for campaign_path in sorted((root / "campaigns").glob("**/campaign.json")):
        campaign = _load_json_object(campaign_path, label="campaign")
        if campaign.get("id") == campaign_id:
            matches.append(campaign_path.with_name("search_space.json"))
    if not matches:
        raise SearchIntegrityError(f"missing campaign search_space for campaign_id: {campaign_id}")
    if len(matches) > 1:
        joined = ", ".join(str(path) for path in matches)
        raise SearchIntegrityError(f"duplicate campaign_id search_space matches: {joined}")
    if not matches[0].is_file():
        raise SearchIntegrityError(f"missing campaign search_space: {matches[0]}")
    return matches[0]


def _resolve_search_space(
    root: Path,
    *,
    campaign_id: str | None,
    search_space_path: Path | None,
) -> tuple[Path, Path, dict[str, Any], str]:
    if search_space_path is not None:
        repo_path, resolved = _resolve_repo_path(root, search_space_path, label="search_space_path")
    elif campaign_id is not None:
        resolved = _resolve_campaign_search_space_path(root, campaign_id)
        repo_path = resolved.resolve().relative_to(root.resolve())
    else:
        raise SearchIntegrityError("either campaign_id or search_space_path is required")

    search_space = _load_json_object(resolved, label="search_space")
    resolved_campaign_id = search_space.get("campaign_id")
    if not isinstance(resolved_campaign_id, str) or not resolved_campaign_id:
        raise SearchIntegrityError(f"search_space campaign_id must be a nonempty string: {resolved}")
    if campaign_id is not None and resolved_campaign_id != campaign_id:
        raise SearchIntegrityError(
            "campaign_id does not match search_space campaign_id: "
            f"{campaign_id} != {resolved_campaign_id}"
        )
    return repo_path, resolved, search_space, resolved_campaign_id


def _catalog_entries_by_candidate(
    root: Path,
    fixture_catalog_path: Path,
) -> dict[str, dict[str, Any]]:
    _, resolved_catalog_path = _resolve_repo_path(
        root,
        fixture_catalog_path,
        label="fixture_catalog_path",
    )
    catalog = _load_json_object(resolved_catalog_path, label="quantum tanner fixture catalog")
    entries_payload = catalog.get("entries")
    if not isinstance(entries_payload, list) or not entries_payload:
        raise SearchIntegrityError("quantum tanner fixture catalog entries must be a non-empty list")
    entries: dict[str, dict[str, Any]] = {}
    for entry in entries_payload:
        if not isinstance(entry, dict):
            raise SearchIntegrityError("quantum tanner fixture catalog entry must be an object")
        candidate_id = entry["candidate_id"]
        if not isinstance(candidate_id, str) or not candidate_id:
            raise SearchIntegrityError("invalid candidate_id in quantum tanner fixture catalog")
        if candidate_id in entries:
            raise SearchIntegrityError(f"duplicate candidate_id: {candidate_id}")
        entries[candidate_id] = entry
    return entries


def _candidate_targets_catalog(
    candidate_spec: dict[str, Any],
    fixture_catalog_repo_path: Path,
) -> bool:
    candidate_catalog_path = candidate_spec.get("fixture_catalog_path")
    if candidate_catalog_path is None:
        return False
    if not isinstance(candidate_catalog_path, str) or not candidate_catalog_path:
        raise SearchIntegrityError("fixture_catalog_path must be a nonempty string")
    candidate_catalog_repo_path = _safe_relative_repo_path(
        candidate_catalog_path,
        label="fixture_catalog_path",
    )
    return candidate_catalog_repo_path == fixture_catalog_repo_path


def _safe_candidate_id_segment(candidate_id: str) -> None:
    if (
        candidate_id in {".", ".."}
        or "/" in candidate_id
        or "\\" in candidate_id
        or any(
            unicodedata.category(character).startswith("C")
            for character in candidate_id
        )
    ):
        raise SearchIntegrityError("candidate_id must be a safe path segment")


def _validate_distinct_output_paths(paths: list[tuple[str, Path]]) -> None:
    seen: dict[Path, str] = {}
    for label, path in paths:
        resolved = path.resolve()
        existing_label = seen.get(resolved)
        if existing_label is not None:
            raise SearchIntegrityError(
                "output paths must be distinct: "
                f"{existing_label} and {label} both resolve to {resolved}"
            )
        seen[resolved] = label


def _planned_witness_output_paths(
    candidate_specs: list[dict[str, Any]],
    *,
    fixture_catalog_repo_path: Path,
    witness_dir_resolved: Path,
) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    for candidate_spec in candidate_specs:
        candidate_id = candidate_spec.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise SearchIntegrityError("candidate_id must be a nonempty string")
        if not _candidate_targets_catalog(candidate_spec, fixture_catalog_repo_path):
            continue
        try:
            _safe_candidate_id_segment(candidate_id)
        except SearchIntegrityError:
            continue
        paths.append(
            (
                f"witness:{candidate_id}",
                witness_dir_resolved / f"{candidate_id}-upper-bound-witness.json",
            )
        )
    return paths


def _witness_repo_path(witness_dir: Path, *, candidate_id: str) -> Path:
    return witness_dir / f"{candidate_id}-upper-bound-witness.json"


def _candidate_summary(
    *,
    candidate_id: str,
    status: str,
    reason: str,
    basis: str,
    weight: int | None,
    witness_path: str | None,
    search_space_updated: bool,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "status": status,
        "reason": reason,
        "basis": basis,
        "weight": weight,
        "witness_path": witness_path,
        "search_space_updated": search_space_updated,
    }


def _attached_weight(converted: dict[str, Any], witness_payload: dict[str, Any]) -> int:
    distance_payload = converted.get("distance_payload")
    if isinstance(distance_payload, dict):
        upper_bound = distance_payload.get("upper_bound")
        if type(upper_bound) is int and upper_bound > 0:
            return int(upper_bound)
    vector = witness_payload.get("vector")
    if isinstance(vector, list):
        return sum(int(bit) for bit in vector)
    raise SearchIntegrityError("converted witness payload is missing vector")


def attach_quantum_tanner_witnesses(
    root: Path,
    *,
    campaign_id: str | None,
    search_space_path: Path | None,
    fixture_catalog_path: Path,
    witness_dir: Path,
    basis: str,
    qec_code_bin: str,
    iterations: int,
    restarts: int,
    seed: int,
    target_weight: int | None,
    timeout_seconds: float,
    force: bool = False,
    out_search_space_path: Path | None = None,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    if basis not in {"x", "z"}:
        raise SearchIntegrityError(f"basis must be one of x or z: {basis}")

    root = root.resolve()
    fixture_catalog_repo_path, _ = _resolve_repo_path(
        root,
        fixture_catalog_path,
        label="fixture_catalog_path",
    )
    witness_dir_repo_path, witness_dir_resolved = _resolve_repo_path(
        root,
        witness_dir,
        label="witness_dir",
    )
    search_space_repo_path, resolved_search_space_path, search_space, resolved_campaign_id = (
        _resolve_search_space(
            root,
            campaign_id=campaign_id,
            search_space_path=search_space_path,
        )
    )
    out_search_space_repo_path, out_search_space_resolved = (
        _resolve_repo_path(root, out_search_space_path, label="out_search_space_path")
        if out_search_space_path is not None
        else (search_space_repo_path, resolved_search_space_path)
    )
    summary_repo_path, summary_resolved = (
        _resolve_repo_path(root, summary_path, label="summary_path")
        if summary_path is not None
        else (None, None)
    )

    catalog_entries = _catalog_entries_by_candidate(root, fixture_catalog_repo_path)
    candidate_specs = _candidate_specs(search_space)
    output_paths = [("search_space", out_search_space_resolved)]
    if summary_resolved is not None:
        output_paths.append(("summary", summary_resolved))
    output_paths.extend(
        _planned_witness_output_paths(
            candidate_specs,
            fixture_catalog_repo_path=fixture_catalog_repo_path,
            witness_dir_resolved=witness_dir_resolved,
        )
    )
    _validate_distinct_output_paths(output_paths)

    updated_specs: list[dict[str, Any]] = []
    candidate_summaries: list[dict[str, Any]] = []
    attached_count = 0
    skipped_count = 0
    failed_count = 0

    for candidate_spec in candidate_specs:
        candidate_id = candidate_spec.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise SearchIntegrityError("candidate_id must be a nonempty string")
        if not _candidate_targets_catalog(candidate_spec, fixture_catalog_repo_path):
            updated_specs.append(candidate_spec)
            continue
        try:
            _safe_candidate_id_segment(candidate_id)
        except SearchIntegrityError as exc:
            updated_specs.append(candidate_spec)
            candidate_summaries.append(
                _candidate_summary(
                    candidate_id=candidate_id,
                    status="failed",
                    reason=str(exc),
                    basis=basis,
                    weight=None,
                    witness_path=None,
                    search_space_updated=False,
                )
            )
            failed_count += 1
            continue
        witness_repo_path = _witness_repo_path(
            witness_dir_repo_path,
            candidate_id=candidate_id,
        )
        witness_resolved_path = witness_dir_resolved / witness_repo_path.name
        existing_witness_path = candidate_spec.get("upper_bound_witness_path")
        if existing_witness_path is not None and not isinstance(existing_witness_path, str):
            raise SearchIntegrityError("upper_bound_witness_path must be a string when present")
        if not force and existing_witness_path:
            updated_specs.append(candidate_spec)
            candidate_summaries.append(
                _candidate_summary(
                    candidate_id=candidate_id,
                    status="skipped",
                    reason="existing_upper_bound_witness_path",
                    basis=basis,
                    weight=None,
                    witness_path=existing_witness_path,
                    search_space_updated=False,
                )
            )
            skipped_count += 1
            continue
        if not force and witness_resolved_path.exists():
            updated_specs.append(candidate_spec)
            candidate_summaries.append(
                _candidate_summary(
                    candidate_id=candidate_id,
                    status="skipped",
                    reason="existing_witness_file",
                    basis=basis,
                    weight=None,
                    witness_path=str(witness_repo_path),
                    search_space_updated=False,
                )
            )
            skipped_count += 1
            continue

        entry = catalog_entries.get(candidate_id)
        if entry is None:
            updated_specs.append(candidate_spec)
            candidate_summaries.append(
                _candidate_summary(
                    candidate_id=candidate_id,
                    status="failed",
                    reason="missing_catalog_entry",
                    basis=basis,
                    weight=None,
                    witness_path=str(witness_repo_path),
                    search_space_updated=False,
                )
            )
            failed_count += 1
            continue
        try:
            resolved = resolve_quantum_tanner_fixture_entry(
                root,
                entry,
                campaign_id=resolved_campaign_id,
                catalog_path=fixture_catalog_repo_path,
            )
            hx_path = resolved.artifact_root / "hx.json"
            hz_path = resolved.artifact_root / "hz.json"
            raw_result = run_qec_code_random_window_upper_bound(
                hx_path,
                hz_path,
                qec_code_bin=qec_code_bin,
                iterations=iterations,
                restarts=restarts,
                seed=seed,
                target_weight=target_weight,
                timeout_seconds=timeout_seconds,
            )
            converted = convert_qec_code_random_window_upper_bound_result(
                raw_result,
                resolved.hx,
                resolved.hz,
            )
            witness_payload = converted["witness_payload"]
            found_basis = witness_payload.get("basis")
            if found_basis != basis:
                raise SearchIntegrityError(
                    f"incompatible witness basis: requested {basis}, found {found_basis}"
                )

            _atomic_write_json(witness_resolved_path, witness_payload, label="witness")
            updated_spec = dict(candidate_spec)
            updated_spec["upper_bound_witness_path"] = str(witness_repo_path)
            updated_specs.append(updated_spec)
            candidate_summaries.append(
                _candidate_summary(
                    candidate_id=candidate_id,
                    status="attached",
                    reason="verified_upper_bound_witness",
                    basis=basis,
                    weight=_attached_weight(converted, witness_payload),
                    witness_path=str(witness_repo_path),
                    search_space_updated=True,
                )
            )
            attached_count += 1
        except SearchIntegrityError as exc:
            updated_specs.append(candidate_spec)
            candidate_summaries.append(
                _candidate_summary(
                    candidate_id=candidate_id,
                    status="failed",
                    reason=str(exc),
                    basis=basis,
                    weight=None,
                    witness_path=str(witness_repo_path),
                    search_space_updated=False,
                )
            )
            failed_count += 1

    updated_search_space = dict(search_space)
    updated_search_space["candidate_specs"] = updated_specs
    _atomic_write_json(
        out_search_space_resolved,
        updated_search_space,
        label="search_space",
    )

    summary = {
        "schema_version": 1,
        "campaign_id": resolved_campaign_id,
        "basis": basis,
        "fixture_catalog_path": str(fixture_catalog_repo_path),
        "search_space_path": str(out_search_space_repo_path),
        "source_search_space_path": str(search_space_repo_path),
        "witness_dir": str(witness_dir_repo_path),
        "force": force,
        "counts": {
            "attached": attached_count,
            "skipped": skipped_count,
            "failed": failed_count,
        },
        "candidates": candidate_summaries,
    }
    if summary_repo_path is not None:
        summary["summary_path"] = str(summary_repo_path)
        assert summary_resolved is not None
        _atomic_write_json(summary_resolved, summary, label="summary")
    return summary

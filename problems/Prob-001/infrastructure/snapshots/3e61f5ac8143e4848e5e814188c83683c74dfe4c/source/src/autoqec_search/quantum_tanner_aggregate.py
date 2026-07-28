from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
from math import isfinite
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.quantum_tanner_report import describe_local_code
from autoqec_search.screening import load_screening_json


AGGREGATE_SCHEMA_VERSION = 1
_TERMINAL_ATTEMPT_STATUSES = frozenset({"completed", "failed", "interrupted"})
_QUANTUM_TANNER_CAMPAIGN_ROOT = (
    Path("campaigns") / "examples" / "quantum-tanner-autoresearch"
)


@dataclass(frozen=True)
class AggregatePaths:
    root: Path
    ledger: Path
    report: Path
    state: Path


@dataclass(frozen=True)
class AggregateUpdate:
    appended_records: int
    ledger_path: Path
    report_path: Path


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SearchIntegrityError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"invalid {label}: {path}")
    return payload


def _optional_json_object(path: Path, label: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json_object(path, label)


def _proposal_record(
    accepted: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any]:
    accepted_record = accepted.get("record")
    status = accepted.get("status")
    if not isinstance(accepted_record, dict) or not isinstance(status, dict):
        raise SearchIntegrityError("invalid accepted proposal context")
    group = proposal.get("base_group")
    local_codes = proposal.get("local_codes")
    if not isinstance(group, dict) or not isinstance(local_codes, dict):
        raise SearchIntegrityError("accepted proposal is missing construction metadata")
    h_a = local_codes.get("h_a")
    h_b = local_codes.get("h_b")
    try:
        local_code_a = describe_local_code(h_a)
        local_code_b = describe_local_code(h_b)
    except ValueError as exc:
        raise SearchIntegrityError("accepted proposal has invalid local codes") from exc
    return {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "candidate_ordinal": accepted_record.get("proposal_index"),
        "candidate_id": accepted_record.get("proposal_id"),
        "proposal_fingerprint": accepted_record.get("fingerprint"),
        "round": status.get("round"),
        "attempt": status.get("attempt"),
        "source_commit": status.get("source_commit"),
        "recorded_at": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "status": "failed",
        "stage": status.get("stage"),
        "reason": status.get("message"),
        "construction": {
            "base_group": {"name": group.get("name"), "order": group.get("order")},
            "a_generator_indices": proposal.get("a_generator_indices"),
            "b_generator_indices": proposal.get("b_generator_indices"),
            "h_a": h_a,
            "h_b": h_b,
            "local_code_a": local_code_a,
            "local_code_b": local_code_b,
        },
        "code": {"n": None, "k": None, "rate": None},
        "screening": {"status": None, "reason": None, "x_upper_bound": None},
        "benchmark": None,
        "source_run_frontier": False,
        "artifacts": {"report": None, "definitions": None},
    }


def _overlay_materialized_instance(record: dict[str, Any], path: Path) -> None:
    instance = _optional_json_object(path, "materialized instance")
    if instance is None:
        return
    derived = instance.get("derived_properties")
    if not isinstance(derived, dict):
        raise SearchIntegrityError(f"invalid materialized instance: {path}")
    candidate_id = record.get("candidate_id")
    if any(
        field in instance and instance[field] != candidate_id
        for field in ("candidate_id", "instance_id", "proposal_id")
    ):
        raise SearchIntegrityError(f"invalid materialized instance: {path}")
    top_n = instance.get("n")
    derived_n = derived.get("n")
    top_k = instance.get("k")
    derived_k = derived.get("k")
    for container, field, value in (
        (instance, "n", top_n),
        (derived, "n", derived_n),
    ):
        if field in container and (type(value) is not int or value < 1):
            raise SearchIntegrityError(f"invalid materialized instance: {path}")
    for container, field, value in (
        (instance, "k", top_k),
        (derived, "k", derived_k),
    ):
        if field in container and (type(value) is not int or value < 0):
            raise SearchIntegrityError(f"invalid materialized instance: {path}")
    if (
        "n" in instance
        and "n" in derived
        and top_n != derived_n
    ) or (
        "k" in instance
        and "k" in derived
        and top_k != derived_k
    ):
        raise SearchIntegrityError(f"invalid materialized instance: {path}")
    n = derived_n if "n" in derived else top_n
    k = derived_k if "k" in derived else top_k
    if type(n) is int and type(k) is int and k > n:
        raise SearchIntegrityError(f"invalid materialized instance: {path}")
    record["code"] = {
        "n": n,
        "k": k,
        "rate": k / n if type(n) is int and type(k) is int else None,
    }


def _overlay_witness(record: dict[str, Any], path: Path) -> bool:
    summary = _optional_json_object(path, "witness summary")
    if summary is None:
        return False
    candidates = summary.get("candidates")
    if not isinstance(candidates, list):
        raise SearchIntegrityError(f"invalid witness summary: {path}")
    seen_candidate_ids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise SearchIntegrityError(f"invalid witness summary: {path}")
        candidate_id = candidate.get("candidate_id")
        candidate_status = candidate.get("status")
        reason = candidate.get("reason")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or candidate_id in seen_candidate_ids
            or candidate_status not in {"attached", "failed"}
            or not isinstance(reason, str)
            or not reason
        ):
            raise SearchIntegrityError(f"invalid witness summary: {path}")
        seen_candidate_ids.add(candidate_id)
        if candidate_id != record["candidate_id"]:
            continue
        if candidate_status == "failed":
            record["status"] = "failed"
            record["reason"] = reason
            return True
        return False
    return False


def _manifest_reason(manifest: dict[str, Any]) -> str:
    for key in ("reason", "message", "error"):
        value = manifest.get(key)
        if isinstance(value, str) and value:
            return value
    return f"evaluation_manifest_status:{manifest.get('status')}"


def _json_number(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and isfinite(float(value))
    )


def _valid_created_at(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return False
    return True


def _valid_manifest_identity(
    manifest: dict[str, Any],
    path: Path,
    candidate_id: str,
    campaign_id: str,
    run_id: str,
) -> bool:
    expected = {
        "campaign_id": campaign_id,
        "candidate_id": candidate_id,
        "task_id": path.parent.parent.name,
        "decoder_id": path.parent.name,
        "run_id": run_id,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        return False
    return _valid_created_at(manifest.get("created_at"))


def _valid_completed_point(point: object) -> bool:
    if not isinstance(point, dict) or set(point) != {
        "ci_high",
        "ci_low",
        "errors",
        "ler",
        "p",
        "rounds",
        "seconds",
        "shots",
    }:
        return False
    errors = point.get("errors")
    shots = point.get("shots")
    rounds = point.get("rounds")
    if (
        type(errors) is not int
        or errors < 0
        or type(shots) is not int
        or shots < 1
        or errors > shots
        or type(rounds) is not int
        or rounds < 1
    ):
        return False
    if not all(
        _json_number(point.get(key))
        for key in ("ci_high", "ci_low", "ler", "p", "seconds")
    ):
        return False
    ci_low = float(point["ci_low"])
    ci_high = float(point["ci_high"])
    ler = float(point["ler"])
    p = float(point["p"])
    seconds = float(point["seconds"])
    return (
        0.0 <= ci_low <= ler <= ci_high <= 1.0
        and 0.0 < p < 1.0
        and seconds >= 0.0
    )


def _valid_decoder_parameters(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return all(
        parameter is None
        or isinstance(parameter, str | bool)
        or _json_number(parameter)
        for parameter in value.values()
    )


def _valid_run_metadata(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "decoder_impl",
        "logical_failure_aggregation",
        "logical_observable_basis",
        "logical_observable_count",
        "logical_observable_source",
        "seed",
    }:
        return False
    return (
        all(
            isinstance(value.get(field), str) and bool(value[field])
            for field in (
                "decoder_impl",
                "logical_failure_aggregation",
                "logical_observable_source",
            )
        )
        and value.get("logical_observable_basis") in {"x", "z"}
        and type(value.get("logical_observable_count")) is int
        and value["logical_observable_count"] >= 1
        and type(value.get("seed")) is int
        and value["seed"] >= 0
    )


def _validate_evaluation_manifest(
    manifest: dict[str, Any],
    path: Path,
    candidate_id: str,
    campaign_id: str,
    run_id: str,
) -> str:
    status = manifest.get("status")
    if not _valid_manifest_identity(
        manifest,
        path,
        candidate_id,
        campaign_id,
        run_id,
    ):
        raise SearchIntegrityError(f"invalid evaluation manifest: {path}")
    if status == "completed":
        allowed = {
            "campaign_id",
            "candidate_id",
            "created_at",
            "decoder_id",
            "decoder_parameters",
            "points",
            "run_id",
            "run_metadata",
            "status",
            "task_id",
            "tool_revisions",
        }
        required = allowed - {"decoder_parameters", "run_metadata"}
        tool_revisions = manifest.get("tool_revisions")
        points = manifest.get("points")
        valid = (
            required <= set(manifest) <= allowed
            and isinstance(tool_revisions, dict)
            and bool(tool_revisions)
            and all(isinstance(value, str) and value for value in tool_revisions.values())
            and isinstance(points, list)
            and bool(points)
            and all(_valid_completed_point(point) for point in points)
            and (
                "decoder_parameters" not in manifest
                or _valid_decoder_parameters(manifest["decoder_parameters"])
            )
            and (
                "run_metadata" not in manifest
                or _valid_run_metadata(manifest["run_metadata"])
            )
        )
    elif status == "placeholder":
        metrics = manifest.get("metrics")
        valid = set(manifest) == {
            "campaign_id",
            "candidate_id",
            "created_at",
            "decoder_id",
            "metrics",
            "run_id",
            "status",
            "task_id",
        } and isinstance(metrics, dict) and bool(metrics) and all(
            value is None or _json_number(value) for value in metrics.values()
        )
    elif status == "crash":
        valid = set(manifest) == {
            "campaign_id",
            "candidate_id",
            "created_at",
            "decoder_id",
            "error",
            "run_id",
            "status",
            "task_id",
        } and isinstance(manifest.get("error"), str) and bool(manifest["error"])
    else:
        valid = False
    if not valid:
        raise SearchIntegrityError(f"invalid evaluation manifest: {path}")
    return status


def _completed_benchmark(manifest: dict[str, Any], path: Path) -> dict[str, Any]:
    points = manifest.get("points")
    if not isinstance(points, list) or not points or not isinstance(points[0], dict):
        raise SearchIntegrityError(f"invalid evaluation manifest: {path}")
    point = points[0]
    return {
        "task_id": manifest.get("task_id"),
        "decoder_id": manifest.get("decoder_id"),
        "p": point.get("p"),
        "rounds": point.get("rounds"),
        "errors": point.get("errors"),
        "shots": point.get("shots"),
        "ler": point.get("ler"),
        "ci_low": point.get("ci_low"),
        "ci_high": point.get("ci_high"),
        "seconds": point.get("seconds"),
    }


def _source_definition_target(run_root: Path, candidate_id: str) -> str | None:
    definitions_path = run_root / "construction-definitions.html"
    if not definitions_path.is_file():
        return None
    attempted_candidate_ids: list[str] = []
    candidates_root = run_root / "candidates"
    if candidates_root.is_dir():
        for candidate_root in sorted(candidates_root.iterdir()):
            if not candidate_root.is_dir():
                continue
            attempted = (candidate_root / "screening.json").is_file()
            if not attempted:
                for manifest_path in sorted(
                    candidate_root.glob("evaluations/*/*/manifest.json")
                ):
                    manifest = _load_json_object(
                        manifest_path, "evaluation manifest"
                    )
                    if manifest.get("status") in {"completed", "crash"}:
                        attempted = True
                        break
            if attempted:
                attempted_candidate_ids.append(candidate_root.name)
    try:
        definition_index = attempted_candidate_ids.index(candidate_id) + 1
    except ValueError:
        return None
    return f"{definitions_path}#candidate-{definition_index}"


def _overlay_run_candidate(record: dict[str, Any], run_root: Path) -> str | None:
    candidate_root = run_root / "candidates" / str(record["candidate_id"])
    campaign_id = run_root.parent.name
    run_id = run_root.name
    _overlay_materialized_instance(record, candidate_root / "artifacts" / "instance.json")
    candidate_outcome: str | None = None

    screening_path = candidate_root / "screening.json"
    screening = load_screening_json(screening_path)
    if screening is not None:
        screening_status = screening.get("screening_status")
        screening_reason = screening.get("reason")
        x_upper_bound = screening.get("distance_upper_bound")
        if (
            screening_status == "admitted"
            and type(x_upper_bound) is not int
        ) or (
            screening_status in {"skipped", "failed"}
            and x_upper_bound is not None
        ):
            raise SearchIntegrityError(f"invalid candidate screening: {screening_path}")
        record["screening"] = {
            "status": screening_status,
            "reason": screening_reason,
            "x_upper_bound": x_upper_bound,
        }
        if screening_status == "skipped":
            record["status"] = "skipped"
            record["reason"] = screening_reason or "screening_skipped"
            candidate_outcome = "skipped"
        elif screening_status == "failed":
            record["status"] = "failed"
            record["reason"] = screening_reason or "screening_failed"
            candidate_outcome = "failed"

    manifest_paths = sorted(candidate_root.glob("evaluations/*/*/manifest.json"))
    manifests = [
        (
            path,
            _load_json_object(path, "evaluation manifest"),
        )
        for path in manifest_paths
    ]
    for path, manifest in manifests:
        _validate_evaluation_manifest(
            manifest,
            path,
            str(record["candidate_id"]),
            campaign_id,
            run_id,
        )
    completed = next(
        ((path, manifest) for path, manifest in manifests if manifest.get("status") == "completed"),
        None,
    )
    if completed is not None:
        manifest_path, manifest = completed
        record["benchmark"] = _completed_benchmark(manifest, manifest_path)
        record["status"] = "evaluated"
        record["reason"] = None
        candidate_outcome = "evaluated"
    else:
        crash = next(
            (manifest for _path, manifest in manifests if manifest.get("status") == "crash"),
            None,
        )
    if completed is None and crash is not None:
        record["benchmark"] = None
        record["status"] = "failed"
        record["reason"] = _manifest_reason(crash)
        candidate_outcome = "failed"

    frontier_path = run_root / "frontier.json"
    frontier = _optional_json_object(frontier_path, "source run frontier")
    if frontier is not None:
        if (
            frontier.get("campaign_id") != campaign_id
            or frontier.get("run_id") != run_id
        ):
            raise SearchIntegrityError(f"invalid source run frontier: {frontier_path}")
        items = frontier.get("items")
        if not isinstance(items, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("candidate_id"), str)
            or not item["candidate_id"]
            for item in items
        ):
            raise SearchIntegrityError(f"invalid source run frontier: {frontier_path}")
        record["source_run_frontier"] = any(
            item.get("candidate_id") == record["candidate_id"] for item in items
        )

    report_path = run_root / "report.html"
    record["artifacts"] = {
        "report": str(report_path) if report_path.is_file() else None,
        "definitions": _source_definition_target(
            run_root, str(record["candidate_id"])
        ),
    }
    return candidate_outcome


def _accepted_records(summary: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    accepted_records = summary.get("accepted_records")
    if not isinstance(accepted_records, list) or any(
        not isinstance(record, dict) for record in accepted_records
    ):
        raise SearchIntegrityError(f"invalid ingestion summary: {path}")
    ordinals: set[int] = set()
    proposal_ids: set[str] = set()
    proposal_paths: set[Path] = set()
    ingested_root = path.parent.resolve()
    for accepted_record in accepted_records:
        proposal_index = accepted_record.get("proposal_index")
        if type(proposal_index) is not int or proposal_index < 0:
            raise SearchIntegrityError(f"invalid ingestion summary: {path}")
        if proposal_index in ordinals:
            raise SearchIntegrityError(f"invalid ingestion summary: {path}")
        ordinals.add(proposal_index)
        for field in ("fingerprint", "path", "proposal_id"):
            value = accepted_record.get(field)
            if not isinstance(value, str) or not value:
                raise SearchIntegrityError(f"invalid ingestion summary: {path}")
        proposal_id = accepted_record["proposal_id"]
        if proposal_id in proposal_ids:
            raise SearchIntegrityError(f"invalid ingestion summary: {path}")
        proposal_ids.add(proposal_id)
        relative_path = Path(accepted_record["path"])
        if not relative_path.parts or relative_path.is_absolute() or any(
            part == ".." for part in relative_path.parts
        ):
            raise SearchIntegrityError(f"invalid ingestion summary: {path}")
        resolved_path = (path.parent / relative_path).resolve()
        if (
            not resolved_path.is_relative_to(ingested_root)
            or resolved_path in proposal_paths
        ):
            raise SearchIntegrityError(f"invalid ingestion summary: {path}")
        proposal_paths.add(resolved_path)
    return accepted_records


def _validate_attempt_status(status: dict[str, Any], path: Path) -> None:
    for field in ("round", "attempt"):
        value = status.get(field)
        if type(value) is not int or value < 1:
            raise SearchIntegrityError(f"invalid attempt status: {path}")
    for field in ("source_commit", "stage", "status"):
        value = status.get(field)
        if not isinstance(value, str) or not value:
            raise SearchIntegrityError(f"invalid attempt status: {path}")
    message = status.get("message")
    if message is not None and not isinstance(message, str):
        raise SearchIntegrityError(f"invalid attempt status: {path}")


def collect_attempt_records(attempt_dir: Path) -> list[dict[str, Any]]:
    attempt_dir = Path(attempt_dir)
    status_path = attempt_dir / "status.json"
    status = _load_json_object(status_path, "attempt status")
    _validate_attempt_status(status, status_path)
    accepted_count = status.get("accepted")
    if accepted_count is None:
        return []
    if type(accepted_count) is not int or accepted_count < 0:
        raise SearchIntegrityError(f"invalid accepted count in attempt status: {status_path}")
    if accepted_count == 0:
        return []

    summary_value = status.get("proposal_summary_path")
    if not isinstance(summary_value, str) or not summary_value:
        raise SearchIntegrityError(f"attempt status is missing proposal summary: {status_path}")
    summary_path = Path(summary_value)
    summary = _load_json_object(summary_path, "ingestion summary")
    accepted_records = _accepted_records(summary, summary_path)
    if summary.get("accepted") != accepted_count or len(accepted_records) != accepted_count:
        raise SearchIntegrityError(f"ingestion summary accepted count mismatch: {summary_path}")

    canonical_witness_path = (
        attempt_dir
        / "checkout"
        / _QUANTUM_TANNER_CAMPAIGN_ROOT
        / "witnesses"
        / "witness_finder_summary.json"
    )
    witness_path: Path | None = (
        canonical_witness_path if canonical_witness_path.exists() else None
    )
    witness_value = status.get("witness_summary_path")
    if witness_value is not None:
        if not isinstance(witness_value, str) or not witness_value:
            raise SearchIntegrityError(f"invalid witness summary path: {status_path}")
        witness_path = Path(witness_value)

    run_root: Path | None = None
    run_root_value = status.get("run_root")
    if run_root_value is not None:
        if not isinstance(run_root_value, str) or not run_root_value:
            raise SearchIntegrityError(f"invalid run_root in attempt status: {status_path}")
        run_root = Path(run_root_value)

    terminal_status = status.get("status")
    records: list[dict[str, Any]] = []
    for accepted_record in accepted_records:
        proposal_path = summary_path.parent / accepted_record["path"]
        proposal = _load_json_object(proposal_path, "accepted proposal")
        if proposal.get("proposal_id") != accepted_record["proposal_id"]:
            raise SearchIntegrityError(
                "accepted proposal proposal_id mismatch for "
                f"{accepted_record['proposal_id']}: {proposal_path}"
            )
        record = _proposal_record(
            {"record": accepted_record, "status": status},
            proposal,
        )
        candidate_id = str(record["candidate_id"])
        materialized_path = (
            attempt_dir
            / "checkout"
            / _QUANTUM_TANNER_CAMPAIGN_ROOT
            / "proposal-instances"
            / candidate_id
            / "instance.json"
        )
        _overlay_materialized_instance(record, materialized_path)
        witness_failure_reason: str | None = None
        if witness_path is not None:
            if _overlay_witness(record, witness_path):
                witness_failure_reason = str(record["reason"])
        run_outcome: str | None = None
        if run_root is not None:
            run_outcome = _overlay_run_candidate(record, run_root)

        if run_outcome == "evaluated":
            candidate_outcome = True
        elif witness_failure_reason is not None:
            record["status"] = "failed"
            record["reason"] = witness_failure_reason
            candidate_outcome = True
        elif run_outcome in {"failed", "skipped"}:
            candidate_outcome = True
        else:
            candidate_outcome = False

        if candidate_outcome:
            pass
        elif terminal_status == "interrupted":
            record["status"] = "interrupted"
            record["reason"] = (
                status.get("message")
                or status.get("signal")
                or record.get("reason")
                or "attempt_interrupted"
            )
        elif terminal_status == "failed":
            record["status"] = "failed"
            record["reason"] = (
                record.get("reason") or status.get("message") or "attempt_failed"
            )
        elif terminal_status == "completed" and record["status"] == "failed":
            record["reason"] = record.get("reason") or "missing_completed_evaluation"
        records.append(record)
    return records


def install_terminal_attempt(
    work_root: Path, attempt_dir: Path
) -> AggregateUpdate:
    attempt_dir = Path(attempt_dir)
    status = _load_json_object(attempt_dir / "status.json", "attempt status")
    if status.get("status") not in _TERMINAL_ATTEMPT_STATUSES:
        raise SearchIntegrityError(f"attempt is not terminal: {attempt_dir}")
    round_number = status.get("round")
    attempt_number = status.get("attempt")
    if (
        type(round_number) is not int
        or round_number < 1
        or type(attempt_number) is not int
        or attempt_number < 1
    ):
        raise SearchIntegrityError(f"terminal attempt has invalid identity: {attempt_dir}")
    attempt_key = f"round-{round_number:04d}/attempt-{attempt_number:03d}"
    return append_attempt_records(
        work_root,
        attempt_key,
        collect_attempt_records(attempt_dir),
    )


def reconcile_terminal_attempts(work_root: Path) -> AggregateUpdate:
    paths = aggregate_paths(work_root)
    initialize_aggregate(work_root)
    appended_records = 0
    rounds_root = Path(work_root) / "rounds"
    if rounds_root.is_dir():
        for round_dir in sorted(rounds_root.glob("round-*")):
            if not round_dir.is_dir():
                continue
            for attempt_dir in sorted(round_dir.glob("attempt-*")):
                if not attempt_dir.is_dir():
                    continue
                status_path = attempt_dir / "status.json"
                if not status_path.is_file():
                    continue
                status = _load_json_object(status_path, "attempt status")
                if status.get("status") not in _TERMINAL_ATTEMPT_STATUSES:
                    continue
                update = install_terminal_attempt(work_root, attempt_dir)
                appended_records += update.appended_records
    return AggregateUpdate(
        appended_records=appended_records,
        ledger_path=paths.ledger,
        report_path=paths.report,
    )


def aggregate_paths(work_root: Path) -> AggregatePaths:
    root = Path(work_root).resolve() / "aggregate"
    return AggregatePaths(
        root=root,
        ledger=root / "results.jsonl",
        report=root / "report.html",
        state=root / "state.json",
    )


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        tmp_path.unlink(missing_ok=True)


def _unsafe_directory(path: Path) -> SearchIntegrityError:
    return SearchIntegrityError(f"unsafe aggregate directory: {path}")


def _unsafe_file(path: Path) -> SearchIntegrityError:
    return SearchIntegrityError(f"unsafe aggregate file: {path}")


def _validate_aggregate_directory(path: Path, *, allow_create: bool) -> None:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        if not allow_create:
            raise _unsafe_directory(path) from None
        try:
            path.mkdir(parents=True)
        except FileExistsError:
            pass
        try:
            metadata = os.lstat(path)
        except OSError as exc:
            raise _unsafe_directory(path) from exc
    except OSError as exc:
        raise _unsafe_directory(path) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise _unsafe_directory(path)


def _validate_aggregate_file(path: Path, *, allow_missing: bool) -> bool:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        if allow_missing:
            return False
        raise _unsafe_file(path) from None
    except OSError as exc:
        raise _unsafe_file(path) from exc
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise _unsafe_file(path)
    return True


def _validate_aggregate_layout(
    paths: AggregatePaths, *, allow_create: bool, allow_missing_files: bool
) -> dict[Path, bool]:
    _validate_aggregate_directory(paths.root, allow_create=allow_create)
    return {
        path: _validate_aggregate_file(path, allow_missing=allow_missing_files)
        for path in (paths.ledger, paths.report, paths.state)
    }


def _read_text(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _unsafe_file(path) from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise _unsafe_file(path)
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            descriptor = -1
            return handle.read()
    except (OSError, UnicodeError) as exc:
        raise SearchIntegrityError(f"could not read aggregate file: {path}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _validate_ledger_record(
    record: Any, *, line_number: int, expected_sequence: int
) -> dict[str, Any]:
    label = f"aggregate ledger line {line_number}"
    if not isinstance(record, dict):
        raise SearchIntegrityError(f"{label} must be an object")
    schema_version = record.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version != AGGREGATE_SCHEMA_VERSION
    ):
        raise SearchIntegrityError(f"{label} has invalid schema_version")
    sequence = record.get("sequence")
    if type(sequence) is not int or sequence != expected_sequence:
        raise SearchIntegrityError(f"{label} has invalid sequence")
    attempt_key = record.get("attempt_key")
    if not isinstance(attempt_key, str) or not attempt_key:
        raise SearchIntegrityError(f"{label} has invalid attempt_key")
    if type(record.get("candidate_ordinal")) is not int:
        raise SearchIntegrityError(f"{label} has invalid candidate_ordinal")
    for field in ("candidate_id", "proposal_fingerprint", "status"):
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise SearchIntegrityError(f"{label} has invalid {field}")
    return record


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    ordinals_by_attempt: dict[str, set[int]] = {}
    for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SearchIntegrityError(
                f"aggregate ledger line {line_number} is invalid JSON"
            ) from exc
        record = _validate_ledger_record(
            payload, line_number=line_number, expected_sequence=line_number
        )
        attempt_key = record["attempt_key"]
        candidate_ordinal = record["candidate_ordinal"]
        seen_ordinals = ordinals_by_attempt.setdefault(attempt_key, set())
        if candidate_ordinal in seen_ordinals:
            raise SearchIntegrityError(
                f"aggregate ledger line {line_number} has duplicate candidate_ordinal"
            )
        seen_ordinals.add(candidate_ordinal)
        records.append(record)
    return records


def _load_state(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise SearchIntegrityError(f"invalid aggregate state JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"aggregate state must be an object: {path}")
    schema_version = payload.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version != AGGREGATE_SCHEMA_VERSION
    ):
        raise SearchIntegrityError(f"aggregate state has invalid schema_version: {path}")
    installed_attempts = payload.get("installed_attempts")
    if not isinstance(installed_attempts, dict):
        raise SearchIntegrityError(f"aggregate state has invalid installed_attempts: {path}")
    for attempt_key, candidate_ordinals in installed_attempts.items():
        if (
            not isinstance(attempt_key, str)
            or not attempt_key
            or not isinstance(candidate_ordinals, list)
            or any(type(ordinal) is not int for ordinal in candidate_ordinals)
            or candidate_ordinals != sorted(set(candidate_ordinals))
        ):
            raise SearchIntegrityError(
                f"aggregate state has invalid installed_attempts: {path}"
            )
    next_sequence = payload.get("next_sequence")
    if type(next_sequence) is not int or next_sequence < 1:
        raise SearchIntegrityError(f"aggregate state has invalid next_sequence: {path}")
    return payload


def _installed_attempts_for_records(
    records: list[dict[str, Any]],
) -> dict[str, list[int]]:
    installed_attempts: dict[str, list[int]] = {}
    for record in records:
        installed_attempts.setdefault(record["attempt_key"], []).append(
            record["candidate_ordinal"]
        )
    return {
        attempt_key: sorted(candidate_ordinals)
        for attempt_key, candidate_ordinals in sorted(installed_attempts.items())
    }


def _state_for_attempts(
    installed_attempts: dict[str, list[int]], *, next_sequence: int
) -> dict[str, Any]:
    return {
        "installed_attempts": dict(sorted(installed_attempts.items())),
        "next_sequence": next_sequence,
        "schema_version": AGGREGATE_SCHEMA_VERSION,
    }


def _state_text(
    installed_attempts: dict[str, list[int]], *, next_sequence: int
) -> str:
    return (
        json.dumps(
            _state_for_attempts(
                installed_attempts,
                next_sequence=next_sequence,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _reconcile_installed_attempts(
    records: list[dict[str, Any]], state: dict[str, Any]
) -> dict[str, list[int]]:
    ledger_attempts = _installed_attempts_for_records(records)
    state_attempts = state["installed_attempts"]
    inconsistent_attempts = sorted(
        attempt_key
        for attempt_key, candidate_ordinals in state_attempts.items()
        if candidate_ordinals and attempt_key not in ledger_attempts
    )
    if inconsistent_attempts:
        raise SearchIntegrityError(
            "aggregate state installed_attempts are inconsistent with ledger: "
            + ", ".join(inconsistent_attempts)
        )
    installed_attempts = {
        attempt_key: []
        for attempt_key, candidate_ordinals in state_attempts.items()
        if not candidate_ordinals
    }
    installed_attempts.update(ledger_attempts)
    return installed_attempts


def _ledger_text(records: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )


def _html_text(value: object) -> str:
    if value is None or value == "":
        return "—"
    return html.escape(str(value), quote=True)


def _html_json_for_script(payload: object) -> str:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _format_round_attempt(record: dict[str, Any]) -> str:
    round_number = record.get("round")
    attempt_number = record.get("attempt")
    if round_number is None and attempt_number is None:
        return "—"
    return f"{_html_text(round_number)} / {_html_text(attempt_number)}"


def _format_candidate(record: dict[str, Any]) -> str:
    candidate = _html_text(record.get("candidate_id"))
    fingerprint = _html_text(record.get("proposal_fingerprint"))
    return f"<strong>{candidate}</strong><br><code>{fingerprint}</code>"


def _format_status(record: dict[str, Any]) -> str:
    status = str(record.get("status") or "unknown")
    reason = _html_text(record.get("reason"))
    badge = f'<span class="badge {html.escape(status, quote=True)}">{_html_text(status)}</span>'
    return f"{badge}<br>{reason}"


def _format_base_group(record: dict[str, Any]) -> str:
    group = record.get("construction", {}).get("base_group")
    if not isinstance(group, dict):
        return "—"
    name = _html_text(group.get("name"))
    order = _html_text(group.get("order"))
    return f"{name}<br><span class=\"muted\">order {order}</span>"


def _format_generators(record: dict[str, Any]) -> str:
    construction = record.get("construction")
    if not isinstance(construction, dict):
        return "—"
    a_generators = construction.get("a_generator_indices")
    b_generators = construction.get("b_generator_indices")
    if a_generators is None and b_generators is None:
        return "—"
    return (
        f"A {_html_text(a_generators)}"
        f"<br>B {_html_text(b_generators)}"
    )


def _local_code_label(local_code: object) -> str:
    if isinstance(local_code, dict):
        for key in ("label", "name", "parameters"):
            value = local_code.get(key)
            if value not in (None, ""):
                return str(value)
    if local_code not in (None, ""):
        return str(local_code)
    return ""


def _format_local_codes(record: dict[str, Any]) -> str:
    construction = record.get("construction")
    if not isinstance(construction, dict):
        return "—"
    code_a = _local_code_label(construction.get("local_code_a"))
    code_b = _local_code_label(construction.get("local_code_b"))
    if not code_a and not code_b:
        return "—"
    return f"A {_html_text(code_a)}<br>B {_html_text(code_b)}"


def _format_css_parameters(record: dict[str, Any]) -> str:
    code = record.get("code")
    if not isinstance(code, dict):
        return "—"
    n = code.get("n")
    k = code.get("k")
    if n is None or k is None:
        return "—"
    return f"[[{_html_text(n)}, {_html_text(k)}]]"


def _format_rate(record: dict[str, Any]) -> str:
    code = record.get("code")
    if not isinstance(code, dict):
        return "—"
    rate = code.get("rate")
    if isinstance(rate, int | float) and not isinstance(rate, bool):
        return f"{float(rate):.6g}"
    return "—"


def _format_screening_bound(record: dict[str, Any]) -> str:
    screening = record.get("screening")
    if not isinstance(screening, dict):
        return "—"
    return _html_text(screening.get("x_upper_bound"))


def _format_screening(record: dict[str, Any]) -> str:
    screening = record.get("screening")
    if not isinstance(screening, dict):
        return "—"
    status = _html_text(screening.get("status"))
    reason = _html_text(screening.get("reason"))
    if status == "—" and reason == "—":
        return "—"
    return f"{status}<br>{reason}"


def _benchmark(record: dict[str, Any]) -> dict[str, Any] | None:
    benchmark = record.get("benchmark")
    return benchmark if isinstance(benchmark, dict) else None


def _format_errors_shots(record: dict[str, Any]) -> str:
    benchmark = _benchmark(record)
    if benchmark is None:
        return "—"
    errors = benchmark.get("errors")
    shots = benchmark.get("shots")
    if errors is None or shots is None:
        return "—"
    return f"{_html_text(errors)} / {_html_text(shots)}"


def _format_ler(record: dict[str, Any]) -> str:
    benchmark = _benchmark(record)
    if benchmark is None:
        return "—"
    return _html_text(benchmark.get("ler"))


def _format_ci(record: dict[str, Any]) -> str:
    benchmark = _benchmark(record)
    if benchmark is None:
        return "—"
    low = benchmark.get("ci_low")
    high = benchmark.get("ci_high")
    if low is None or high is None:
        return "—"
    return f"[{_html_text(low)}, {_html_text(high)}]"


def _format_decoding_time(record: dict[str, Any]) -> str:
    benchmark = _benchmark(record)
    if benchmark is None:
        return "—"
    seconds = benchmark.get("seconds")
    if seconds is None:
        return "—"
    return f"{_html_text(seconds)} s"


def _relative_artifact_href(report_path: Path, artifact: object) -> str | None:
    if not isinstance(artifact, str) or not artifact:
        return None
    return os.path.relpath(Path(artifact), start=report_path.parent)


def _format_artifacts(record: dict[str, Any], report_path: Path) -> str:
    artifacts = record.get("artifacts")
    links: list[str] = []
    if isinstance(artifacts, dict):
        for key, label in (("report", "Report"), ("definitions", "Definitions")):
            href = _relative_artifact_href(report_path, artifacts.get(key))
            if href is not None:
                links.append(
                    f'<a href="{html.escape(href, quote=True)}">{label}</a>'
                )
    if record.get("source_run_frontier") is True:
        links.append('<span class="frontier">Source-run frontier</span>')
    return "<br>".join(links) if links else "—"


def _summary_cards(records: list[dict[str, Any]]) -> list[tuple[str, int]]:
    completed_rounds = {
        record.get("round")
        for record in records
        if record.get("round") is not None
    }
    evaluated = sum(1 for record in records if record.get("status") == "evaluated")
    skipped = sum(1 for record in records if record.get("status") == "skipped")
    failed_interrupted = sum(
        1
        for record in records
        if record.get("status") in {"failed", "interrupted"}
    )
    source_frontier = sum(
        1 for record in records if record.get("source_run_frontier") is True
    )
    return [
        ("Completed rounds", len(completed_rounds)),
        ("Total codes", len(records)),
        ("Evaluated", evaluated),
        ("Skipped", skipped),
        ("Failed / interrupted", failed_interrupted),
        ("Source-run frontier", source_frontier),
    ]


def _record_row_html(record: dict[str, Any], report_path: Path) -> str:
    cells = [
        _format_round_attempt(record),
        _format_candidate(record),
        _format_status(record),
        _format_base_group(record),
        _format_generators(record),
        _format_local_codes(record),
        _format_css_parameters(record),
        _format_rate(record),
        _format_screening_bound(record),
        _format_screening(record),
        _format_errors_shots(record),
        _format_ler(record),
        _format_ci(record),
        _format_decoding_time(record),
        _format_artifacts(record, report_path),
    ]
    return (
        '<tr data-candidate-row="true">'
        + "".join(f"<td>{cell}</td>" for cell in cells)
        + "</tr>"
    )


def render_aggregate_report_html(
    records: list[dict[str, Any]], *, report_path: Path | None = None
) -> str:
    if report_path is None:
        report_path = Path("aggregate") / "report.html"
    cards = "".join(
        "<article>"
        f'<span class="card-label">{html.escape(label, quote=True)}</span>'
        f'<span class="card-value">{value}</span>'
        "</article>"
        for label, value in _summary_cards(records)
    )
    headings = (
        "Round / attempt",
        "Finite code / candidate",
        "Status / reason",
        "Base group",
        "A / B generators",
        "Local classical code",
        "CSS parameters",
        "Code rate",
        "X upper bound",
        "Screening",
        "errors / shots",
        "LER",
        "95% CI",
        "Decoding time",
        "Source artifacts",
    )
    header = "".join(f"<th>{html.escape(heading)}</th>" for heading in headings)
    rows = "".join(_record_row_html(record, report_path) for record in records)
    if not rows:
        rows = (
            f'<tr><td colspan="{len(headings)}" class="empty">'
            "No aggregate records yet.</td></tr>"
        )
    ledger_json = _html_json_for_script(records)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quantum Tanner aggregate report</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f6f7f9; color: #17202a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 28px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p {{ line-height: 1.5; }}
    .subtitle {{ margin: 0 0 20px; color: #52606d; }}
    .notice {{ margin: 20px 0; padding: 12px 14px; border: 1px solid #d7dde5; background: #ffffff; border-radius: 8px; }}
    .cards {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 10px; margin: 20px 0; }}
    article {{ background: #ffffff; border: 1px solid #d7dde5; border-radius: 8px; padding: 12px; }}
    .card-label {{ display: block; color: #52606d; font-size: 12px; }}
    .card-value {{ display: block; margin-top: 6px; font-size: 24px; font-weight: 700; }}
    .table-wrap {{ overflow-x: auto; background: #ffffff; border: 1px solid #d7dde5; border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1280px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e6eaf0; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ position: sticky; top: 0; background: #eef2f7; color: #344054; font-size: 12px; }}
    tr:last-child td {{ border-bottom: 0; }}
    code {{ white-space: nowrap; }}
    a {{ color: #2457a6; }}
    .muted {{ color: #667085; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 700; }}
    .badge.evaluated {{ background: #e4f7e7; color: #17663a; }}
    .badge.skipped {{ background: #fff4d6; color: #8a5a00; }}
    .badge.failed {{ background: #fde8e8; color: #9b1c1c; }}
    .badge.interrupted {{ background: #ece9ff; color: #4934a8; }}
    .badge.unknown {{ background: #edf0f3; color: #344054; }}
    .frontier {{ color: #344054; font-weight: 700; }}
    .empty {{ text-align: center; color: #667085; }}
    details {{ margin-top: 20px; }}
    pre {{ overflow-x: auto; padding: 12px; background: #111827; color: #f9fafb; border-radius: 8px; }}
    @media (max-width: 900px) {{
      main {{ padding: 18px; }}
      .cards {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Quantum Tanner aggregate report</h1>
    <p class="subtitle">Append-ordered terminal results collected from this work root.</p>
    <section class="cards">{cards}</section>
    <p class="notice">Zero observed errors do not prove a zero logical error rate; use the recorded 95% confidence interval. X upper bounds are randomized screening evidence, not exact code distances.</p>
    <section class="table-wrap">
      <table>
        <thead><tr>{header}</tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    <details>
      <summary>Embedded aggregate data</summary>
      <script type="application/json" id="autoqec-quantum-tanner-aggregate">{ledger_json}</script>
      <pre>{html.escape(ledger_json)}</pre>
    </details>
  </main>
</body>
</html>
"""


def _render_report(
    records: list[dict[str, Any]], *, report_path: Path | None = None
) -> str:
    return render_aggregate_report_html(records, report_path=report_path)


def write_aggregate_report(work_root: Path) -> Path:
    initialize_aggregate(work_root)
    paths = aggregate_paths(work_root)
    records = load_aggregate_records(work_root)
    _atomic_write_text(
        paths.report, render_aggregate_report_html(records, report_path=paths.report)
    )
    return paths.report


def _matrix_history(matrix: object, *, label: str) -> dict[str, object]:
    if not isinstance(matrix, list) or not matrix:
        return {label: None}
    cells = sum(len(row) for row in matrix if isinstance(row, list))
    if cells <= 64:
        return {label: matrix}
    canonical = json.dumps(matrix, separators=(",", ":"), sort_keys=True).encode()
    first_row = matrix[0]
    width = len(first_row) if isinstance(first_row, list) else 0
    return {
        f"{label}_dimensions": [len(matrix), width],
        f"{label}_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _history_record(record: dict[str, Any]) -> dict[str, object]:
    construction = record.get("construction")
    if not isinstance(construction, dict):
        construction = {}
    history: dict[str, object] = {
        "sequence": record.get("sequence"),
        "attempt_key": record.get("attempt_key"),
        "round": record.get("round"),
        "attempt": record.get("attempt"),
        "candidate_id": record.get("candidate_id"),
        "proposal_fingerprint": record.get("proposal_fingerprint"),
        "status": record.get("status"),
        "reason": record.get("reason"),
        "base_group": construction.get("base_group"),
        "a_generator_indices": construction.get("a_generator_indices"),
        "b_generator_indices": construction.get("b_generator_indices"),
        "local_code_a": construction.get("local_code_a"),
        "local_code_b": construction.get("local_code_b"),
        "code": record.get("code"),
        "screening": record.get("screening"),
    }
    history.update(_matrix_history(construction.get("h_a"), label="h_a"))
    history.update(_matrix_history(construction.get("h_b"), label="h_b"))
    return history


def candidate_history_prompt(work_root: Path) -> str:
    records = load_aggregate_records(work_root)
    history = [_history_record(record) for record in records]
    history_json = json.dumps(history, sort_keys=True)
    return (
        "Quantum Tanner aggregate candidate history for this work root.\n"
        "Do not repeat listed candidate IDs, proposal fingerprints, "
        "base-group/generator sets, or local classical codes. Failed, skipped, "
        "and interrupted rows are part of the search history and must be avoided "
        "along with evaluated rows.\n"
        f"{history_json}\n"
    )


def historical_fingerprints(work_root: Path) -> set[str]:
    return {
        fingerprint
        for fingerprint in (
            record.get("proposal_fingerprint")
            for record in load_aggregate_records(work_root)
        )
        if isinstance(fingerprint, str) and fingerprint
    }


def initialize_aggregate(work_root: Path) -> AggregateUpdate:
    paths = aggregate_paths(work_root)
    existing = _validate_aggregate_layout(
        paths, allow_create=True, allow_missing_files=True
    )
    if existing[paths.ledger]:
        records = _load_ledger(paths.ledger)
    else:
        _atomic_write_text(paths.ledger, "")
        records = []
    if existing[paths.state]:
        _load_state(paths.state)
    else:
        _atomic_write_text(
            paths.state,
            _state_text(
                _installed_attempts_for_records(records),
                next_sequence=len(records) + 1,
            ),
        )
    if not existing[paths.report]:
        _atomic_write_text(paths.report, _render_report(records, report_path=paths.report))
    return AggregateUpdate(
        appended_records=0,
        ledger_path=paths.ledger,
        report_path=paths.report,
    )


def load_aggregate_records(work_root: Path) -> list[dict[str, Any]]:
    paths = aggregate_paths(work_root)
    _validate_aggregate_layout(
        paths, allow_create=False, allow_missing_files=False
    )
    return _load_ledger(paths.ledger)


def _validated_incoming_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied_records: list[dict[str, Any]] = []
    ordinals: set[int] = set()
    for record in records:
        if not isinstance(record, dict):
            raise SearchIntegrityError("aggregate record must be an object")
        candidate_ordinal = record.get("candidate_ordinal")
        if type(candidate_ordinal) is not int:
            raise SearchIntegrityError("aggregate record has invalid candidate_ordinal")
        if candidate_ordinal in ordinals:
            raise SearchIntegrityError("duplicate candidate_ordinal in aggregate record batch")
        ordinals.add(candidate_ordinal)
        copied_records.append(dict(record))
    return copied_records


def append_attempt_records(
    work_root: Path, attempt_key: str, records: list[dict[str, Any]]
) -> AggregateUpdate:
    if not isinstance(attempt_key, str) or not attempt_key:
        raise SearchIntegrityError("invalid aggregate attempt_key")
    incoming_records = _validated_incoming_records(records)
    initialize_aggregate(work_root)
    paths = aggregate_paths(work_root)
    _validate_aggregate_layout(
        paths, allow_create=False, allow_missing_files=False
    )
    current_records = _load_ledger(paths.ledger)
    state = _load_state(paths.state)
    installed_attempts = _reconcile_installed_attempts(current_records, state)
    incoming_ordinals = sorted(
        record["candidate_ordinal"] for record in incoming_records
    )

    if attempt_key in installed_attempts:
        if incoming_ordinals != installed_attempts[attempt_key]:
            raise SearchIntegrityError(
                "candidate_ordinal set mismatch for installed aggregate attempt: "
                f"{attempt_key}"
            )
        _atomic_write_text(
            paths.report, _render_report(current_records, report_path=paths.report)
        )
        _atomic_write_text(
            paths.state,
            _state_text(
                installed_attempts,
                next_sequence=len(current_records) + 1,
            ),
        )
        return AggregateUpdate(
            appended_records=0,
            ledger_path=paths.ledger,
            report_path=paths.report,
        )

    next_sequence = len(current_records) + 1
    appended_records: list[dict[str, Any]] = []
    for offset, record in enumerate(incoming_records):
        appended = dict(record)
        appended["attempt_key"] = attempt_key
        appended["sequence"] = next_sequence + offset
        _validate_ledger_record(
            appended,
            line_number=next_sequence + offset,
            expected_sequence=next_sequence + offset,
        )
        appended_records.append(appended)
    all_records = [*current_records, *appended_records]
    installed_attempts[attempt_key] = incoming_ordinals

    _atomic_write_text(paths.ledger, _ledger_text(all_records))
    _atomic_write_text(paths.report, _render_report(all_records, report_path=paths.report))
    _atomic_write_text(
        paths.state,
        _state_text(installed_attempts, next_sequence=len(all_records) + 1),
    )
    return AggregateUpdate(
        appended_records=len(appended_records),
        ledger_path=paths.ledger,
        report_path=paths.report,
    )

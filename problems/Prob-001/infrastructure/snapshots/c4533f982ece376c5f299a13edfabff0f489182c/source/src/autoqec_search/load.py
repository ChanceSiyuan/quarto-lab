from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator


class SearchIntegrityError(ValueError):
    """Raised when search-layer files disagree with each other."""


CREATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True)
class LoadedCandidate:
    payload: dict
    manifests: dict[tuple[str, str], dict]


@dataclass(frozen=True)
class LoadedRun:
    payload: dict
    root: Path
    candidates: dict[str, LoadedCandidate]


@dataclass(frozen=True)
class SearchWorkspace:
    campaigns: dict[str, dict]
    search_spaces: dict[str, dict]
    tasks: dict[str, dict]
    decoders: dict[str, dict]
    suites: dict[str, dict]
    runs: dict[str, LoadedRun]


QUANTUM_TANNER_P001_TASK_ID = "quantum-tanner-css-memory-x-rbposd-p001-v1"
QUANTUM_TANNER_P001_SUITE_ID = "quantum-tanner-rbposd-p001-v1"
QUANTUM_TANNER_P001_DECODER_ID = "rbposd-osd10-v1"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _validator(path: Path) -> Draft202012Validator:
    return Draft202012Validator(_load_json(path))


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")


def _require_directory(path: Path) -> None:
    if not path.is_dir():
        raise SearchIntegrityError(f"missing required directory: {path}")


def _validate_autoresearch_metadata(run_root: Path, payload: dict) -> None:
    for key in ("tag", "wall_clock_seconds", "seed"):
        if key not in payload:
            raise SearchIntegrityError(f"autoresearch run missing {key}: {run_root}")
    if not isinstance(payload["tag"], str) or not payload["tag"]:
        raise SearchIntegrityError(f"autoresearch run has invalid tag: {run_root}")
    if type(payload["wall_clock_seconds"]) is not int or payload["wall_clock_seconds"] < 1:
        raise SearchIntegrityError(
            f"autoresearch run has invalid wall_clock_seconds: {run_root}"
        )
    if type(payload["seed"]) is not int:
        raise SearchIntegrityError(f"autoresearch run has invalid seed: {run_root}")

    _require_file(run_root / "experiment-log.tsv", "experiment log artifact")
    _require_file(run_root / "run-summary.html", "run summary HTML artifact")
    run_status_path = run_root / "run_status.json"
    _require_file(run_status_path, "run status artifact")
    run_status = _load_json(run_status_path)

    expected_keys = {
        "campaign_id",
        "run_id",
        "tag",
        "status",
        "finalized_at",
        "candidates_attempted",
        "frontier_size",
    }
    strategy = payload.get("strategy")
    has_strategy = isinstance(strategy, dict)
    if has_strategy:
        expected_keys.add("stop_reason")
        _require_file(run_root / "strategy_trace.json", "strategy trace artifact")
    if set(run_status) != expected_keys:
        raise SearchIntegrityError(
            f"run_status keys mismatch for {run_status_path}: "
            f"{sorted(run_status)} != {sorted(expected_keys)}"
        )
    for key in ("campaign_id", "run_id", "tag"):
        if run_status[key] != payload[key]:
            raise SearchIntegrityError(
                f"run_status {key} mismatch for {run_status_path}: "
                f"{run_status[key]} != {payload[key]}"
            )
    if run_status["status"] != "finalized":
        raise SearchIntegrityError(
            f"run_status status mismatch for {run_status_path}: "
            f"{run_status['status']} != finalized"
        )
    if (
        not isinstance(run_status["finalized_at"], str)
        or CREATED_AT_RE.fullmatch(run_status["finalized_at"]) is None
    ):
        raise SearchIntegrityError(
            f"run_status finalized_at is invalid for {run_status_path}"
        )
    candidates_attempted = run_status["candidates_attempted"]
    frontier_size = run_status["frontier_size"]
    if (
        type(candidates_attempted) is not int
        or candidates_attempted < 0
        or candidates_attempted > len(payload["candidate_ids"])
    ):
        raise SearchIntegrityError(
            f"run_status candidates_attempted is invalid for {run_status_path}"
        )
    if (
        type(frontier_size) is not int
        or frontier_size < 0
        or frontier_size > candidates_attempted
    ):
        raise SearchIntegrityError(
            f"run_status frontier_size is invalid for {run_status_path}"
        )
    if has_strategy:
        stop_reason = run_status.get("stop_reason")
        allowed = {"max-candidates", "wall-clock", "search-space-exhausted", "completed"}
        if stop_reason not in allowed:
            raise SearchIntegrityError(
                f"run_status stop_reason is invalid for {run_status_path}"
            )


def _duplicate_items(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _duplicate_candidate_ids(search_space: dict) -> list[str]:
    candidate_ids: list[str] = []
    for candidate_spec in search_space["candidate_specs"]:
        candidate_ids.append(candidate_spec["candidate_id"])
    return _duplicate_items(candidate_ids)


def _load_campaigns(
    root: Path,
    campaign_validator: Draft202012Validator,
    search_space_validator: Draft202012Validator,
) -> tuple[dict[str, dict], dict[str, dict]]:
    campaigns: dict[str, dict] = {}
    search_spaces: dict[str, dict] = {}

    for campaign_path in sorted((root / "campaigns").glob("**/campaign.json")):
        campaign = _load_json(campaign_path)
        campaign_validator.validate(campaign)

        search_space_path = campaign_path.with_name("search_space.json")
        _require_file(search_space_path, "search space")
        search_space = _load_json(search_space_path)
        search_space_validator.validate(search_space)

        if campaign["id"] in campaigns:
            raise SearchIntegrityError(f"duplicate campaign id: {campaign['id']}")
        if search_space["campaign_id"] != campaign["id"]:
            raise SearchIntegrityError(
                f"search_space campaign_id mismatch for {search_space_path}: "
                f"{search_space['campaign_id']} != {campaign['id']}"
            )
        duplicate_candidate_ids = _duplicate_candidate_ids(search_space)
        if duplicate_candidate_ids:
            raise SearchIntegrityError(
                "duplicate candidate_id in search space: "
                + ", ".join(duplicate_candidate_ids)
            )

        campaigns[campaign["id"]] = campaign
        search_spaces[campaign["id"]] = search_space

    return campaigns, search_spaces


def _load_indexed_directory(
    root: Path,
    subdir: str,
    validator: Draft202012Validator,
) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for path in sorted((root / "benchmarks" / subdir).glob("*.json")):
        payload = _load_json(path)
        validator.validate(payload)
        if payload["id"] in items:
            raise SearchIntegrityError(
                f"duplicate id in benchmarks/{subdir}: {payload['id']}"
            )
        items[payload["id"]] = payload
    return items


def _load_baselines(root: Path) -> None:
    from autoqec_search.baselines import load_surface_single_logical_baseline

    baselines_root = root / "benchmarks" / "baselines"
    for baseline_path in sorted(baselines_root.glob("*.json")):
        load_surface_single_logical_baseline(baseline_path)


def _validate_quantum_tanner_p001_contract(
    tasks: dict[str, dict],
    decoders: dict[str, dict],
    suites: dict[str, dict],
) -> None:
    if (
        QUANTUM_TANNER_P001_TASK_ID not in tasks
        and QUANTUM_TANNER_P001_SUITE_ID not in suites
    ):
        return

    if QUANTUM_TANNER_P001_TASK_ID not in tasks:
        raise SearchIntegrityError(
            "missing quantum Tanner p001 task: "
            f"{QUANTUM_TANNER_P001_TASK_ID}"
        )
    if QUANTUM_TANNER_P001_SUITE_ID not in suites:
        raise SearchIntegrityError(
            "missing quantum Tanner p001 suite: "
            f"{QUANTUM_TANNER_P001_SUITE_ID}"
        )

    task = tasks[QUANTUM_TANNER_P001_TASK_ID]
    suite = suites[QUANTUM_TANNER_P001_SUITE_ID]

    if suite.get("task_ids") != [QUANTUM_TANNER_P001_TASK_ID]:
        raise SearchIntegrityError(
            "quantum Tanner p001 suite task_ids must be exactly "
            f"['{QUANTUM_TANNER_P001_TASK_ID}']"
        )
    if suite.get("decoder_ids") != [QUANTUM_TANNER_P001_DECODER_ID]:
        raise SearchIntegrityError(
            "quantum Tanner p001 suite decoder_ids must be exactly "
            f"['{QUANTUM_TANNER_P001_DECODER_ID}']"
        )
    decoder = decoders.get(QUANTUM_TANNER_P001_DECODER_ID)
    if decoder is None:
        raise SearchIntegrityError(
            "missing quantum Tanner p001 decoder: "
            f"{QUANTUM_TANNER_P001_DECODER_ID}"
        )
    if decoder.get("impl_key") != "rbposd":
        raise SearchIntegrityError("quantum Tanner p001 decoder must use impl_key rbposd")
    if 0.01 in task.get("p_list", []):
        raise SearchIntegrityError("quantum Tanner p001 task must not contain p=0.01")
    if task.get("p_list") != [0.001]:
        raise SearchIntegrityError("quantum Tanner p001 task must use exactly p=0.001")
    if task.get("input_type") != "css":
        raise SearchIntegrityError('quantum Tanner p001 task input_type must be "css"')
    css_memory = task.get("css_memory")
    if not isinstance(css_memory, dict) or css_memory.get("observables") != "optional":
        raise SearchIntegrityError(
            'quantum Tanner p001 task css_memory.observables must be "optional"'
        )
    shared_settings = suite.get("shared_settings")
    bad_shared_p = (
        isinstance(shared_settings, dict)
        and any(
            type(value) in (int, float) and value == 0.01
            for value in shared_settings.values()
        )
    )
    if bad_shared_p:
        raise SearchIntegrityError(
            "quantum Tanner p001 suite shared_settings must not contain p=0.01"
        )


def _validate_quantum_tanner_screening(path: Path) -> dict:
    _require_file(path, "quantum Tanner screening artifact")
    payload = _load_json(path)
    expected_keys = {
        "screening_status",
        "distance_bound_type",
        "distance_upper_bound",
        "reason",
    }
    if set(payload) != expected_keys:
        raise SearchIntegrityError(f"invalid quantum Tanner screening keys: {path}")
    screening_status = payload["screening_status"]
    if screening_status not in {"admitted", "skipped", "failed"}:
        raise SearchIntegrityError(f"invalid quantum Tanner screening status: {path}")
    if payload["distance_bound_type"] != "upper":
        raise SearchIntegrityError(
            f"invalid quantum Tanner screening distance_bound_type: {path}"
        )
    upper_bound = payload["distance_upper_bound"]
    if screening_status == "admitted":
        if type(upper_bound) is not int or upper_bound <= 0:
            raise SearchIntegrityError(
                f"invalid quantum Tanner admitted distance_upper_bound: {path}"
            )
    elif upper_bound is not None:
        raise SearchIntegrityError(
            f"skipped or failed quantum Tanner screening must not record a bound: {path}"
        )
    reason = payload["reason"]
    if not isinstance(reason, str) or not reason:
        raise SearchIntegrityError(f"invalid quantum Tanner screening reason: {path}")
    return payload


def _validate_quantum_tanner_screening_consistency(
    candidate_root: Path,
    screening: dict,
    manifests: dict[tuple[str, str], dict],
) -> None:
    status = screening["screening_status"]
    manifest_statuses = [manifest.get("status") for manifest in manifests.values()]
    if status == "admitted":
        for manifest in manifests.values():
            if manifest.get("status") != "completed":
                raise SearchIntegrityError(
                    "admitted quantum Tanner screening requires completed manifest: "
                    f"{candidate_root}"
                )
            points = manifest.get("points")
            if (
                not isinstance(points, list)
                or [point.get("p") for point in points if isinstance(point, dict)]
                != [0.001]
            ):
                raise SearchIntegrityError(
                    "admitted quantum Tanner screening requires exactly p=0.001: "
                    f"{candidate_root}"
                )
            metadata = manifest.get("run_metadata")
            if (
                not isinstance(metadata, dict)
                or metadata.get("logical_failure_aggregation") != "any_logical"
                or metadata.get("logical_observable_source") != "explicit"
            ):
                raise SearchIntegrityError(
                    "admitted quantum Tanner screening requires explicit any_logical "
                    f"metadata: {candidate_root}"
                )
    elif status == "skipped":
        if any(manifest_status != "placeholder" for manifest_status in manifest_statuses):
            raise SearchIntegrityError(
                "skipped quantum Tanner screening requires placeholder manifest: "
                f"{candidate_root}"
            )
        if (candidate_root / "rsinter").exists():
            raise SearchIntegrityError(
                f"skipped quantum Tanner screening must not have rsinter output: {candidate_root}"
            )
    elif status == "failed":
        if any(manifest_status != "crash" for manifest_status in manifest_statuses):
            raise SearchIntegrityError(
                "failed quantum Tanner screening requires crash manifest: "
                f"{candidate_root}"
            )


def _load_runs(
    root: Path,
    run_spec_validator: Draft202012Validator,
    candidate_validator: Draft202012Validator,
    manifest_validator: Draft202012Validator,
    campaigns: dict[str, dict],
    suites: dict[str, dict],
) -> dict[str, LoadedRun]:
    runs: dict[str, LoadedRun] = {}
    run_glob_root = root / "results" / "search"

    for run_spec_path in sorted(run_glob_root.glob("*/*/run_spec.json")):
        run_root = run_spec_path.parent
        loaded_run = load_search_run(
            run_root,
            run_spec_validator=run_spec_validator,
            candidate_validator=candidate_validator,
            manifest_validator=manifest_validator,
            campaigns=campaigns,
            suites=suites,
        )
        runs[f"{loaded_run.payload['campaign_id']}/{loaded_run.payload['run_id']}"] = (
            loaded_run
        )

    return runs


def load_search_run(
    run_root: Path,
    *,
    run_spec_validator: Draft202012Validator,
    candidate_validator: Draft202012Validator,
    manifest_validator: Draft202012Validator,
    campaigns: dict[str, dict],
    suites: dict[str, dict],
) -> LoadedRun:
    run_spec_path = run_root / "run_spec.json"
    payload = _load_json(run_spec_path)
    run_spec_validator.validate(payload)

    _require_file(run_root / "env.json", "env artifact")
    _require_file(run_root / "frontier.json", "frontier artifact")
    _require_file(run_root / "leaderboard.csv", "leaderboard artifact")
    _require_file(run_root / "summary.md", "summary artifact")
    if payload["mode"] == "autoresearch":
        _validate_autoresearch_metadata(run_root, payload)

    if payload["campaign_id"] not in campaigns:
        raise SearchIntegrityError(
            f"unknown campaign_id on run {run_root}: {payload['campaign_id']}"
        )
    if payload["suite_id"] not in suites:
        raise SearchIntegrityError(
            f"unknown suite_id on run {run_root}: {payload['suite_id']}"
        )
    if run_root.parent.name != payload["campaign_id"]:
        raise SearchIntegrityError(
            f"run campaign directory mismatch for {run_root}: {run_root.parent.name}"
        )
    if run_root.name != payload["run_id"]:
        raise SearchIntegrityError(
            f"run id directory mismatch for {run_root}: {run_root.name}"
        )

    suite = suites[payload["suite_id"]]
    if payload["task_ids"] != suite["task_ids"]:
        raise SearchIntegrityError(f"run task_ids drift on {run_root}")
    duplicate_run_decoders = _duplicate_items(payload["decoder_ids"])
    if duplicate_run_decoders:
        raise SearchIntegrityError(
            f"duplicate decoder_id on run {run_root}: "
            f"{', '.join(duplicate_run_decoders)}"
        )
    unknown_run_decoders = sorted(set(payload["decoder_ids"]) - set(suite["decoder_ids"]))
    if unknown_run_decoders:
        raise SearchIntegrityError(
            f"run decoder_ids unknown on {run_root}: "
            f"{', '.join(unknown_run_decoders)}"
        )

    candidates_root = run_root / "candidates"
    if not candidates_root.is_dir():
        raise SearchIntegrityError(f"missing candidates directory: {candidates_root}")

    actual_candidate_ids = sorted(path.name for path in candidates_root.iterdir() if path.is_dir())
    expected_candidate_ids = sorted(payload["candidate_ids"])
    if actual_candidate_ids != expected_candidate_ids:
        raise SearchIntegrityError(
            f"candidate directory mismatch for {run_root}: "
            f"{actual_candidate_ids} != {expected_candidate_ids}"
        )

    loaded_candidates: dict[str, LoadedCandidate] = {}
    requires_screening = payload["suite_id"] == QUANTUM_TANNER_P001_SUITE_ID
    for candidate_id in payload["candidate_ids"]:
        candidate_root = candidates_root / candidate_id
        screening: dict | None = None
        candidate_path = candidate_root / "candidate.json"
        _require_file(candidate_path, "candidate payload")
        _require_file(candidate_root / "structure.json", "structure artifact")
        _require_file(candidate_root / "distance.json", "distance artifact")

        candidate = _load_json(candidate_path)
        candidate_validator.validate(candidate)

        if candidate["candidate_id"] != candidate_id:
            raise SearchIntegrityError(
                f"candidate_id mismatch for {candidate_path}: "
                f"{candidate['candidate_id']} != {candidate_id}"
            )
        if candidate["campaign_id"] != payload["campaign_id"]:
            raise SearchIntegrityError(
                f"candidate campaign_id mismatch for {candidate_path}"
            )
        if candidate["run_id"] != payload["run_id"]:
            raise SearchIntegrityError(f"candidate run_id mismatch for {candidate_path}")
        if requires_screening:
            screening = _validate_quantum_tanner_screening(
                candidate_root / "screening.json"
            )

        manifests: dict[tuple[str, str], dict] = {}
        for task_id in payload["task_ids"]:
            for decoder_id in payload["decoder_ids"]:
                manifest_path = (
                    candidate_root / "evaluations" / task_id / decoder_id / "manifest.json"
                )
                _require_file(manifest_path, "result manifest")
                manifest = _load_json(manifest_path)
                manifest_validator.validate(manifest)

                if manifest["campaign_id"] != payload["campaign_id"]:
                    raise SearchIntegrityError(
                        f"manifest campaign_id mismatch for {manifest_path}"
                    )
                if manifest["run_id"] != payload["run_id"]:
                    raise SearchIntegrityError(
                        f"manifest run_id mismatch for {manifest_path}"
                    )
                if manifest["candidate_id"] != candidate_id:
                    raise SearchIntegrityError(
                        f"manifest candidate_id mismatch for {manifest_path}"
                    )
                if manifest["task_id"] != task_id:
                    raise SearchIntegrityError(
                        f"manifest task_id mismatch for {manifest_path}"
                    )
                if manifest["decoder_id"] != decoder_id:
                    raise SearchIntegrityError(
                        f"manifest decoder_id mismatch for {manifest_path}"
                    )

                manifests[(task_id, decoder_id)] = manifest
        if screening is not None:
            _validate_quantum_tanner_screening_consistency(
                candidate_root,
                screening,
                manifests,
            )

        loaded_candidates[candidate_id] = LoadedCandidate(
            payload=candidate,
            manifests=manifests,
        )

    return LoadedRun(
        payload=payload,
        root=run_root,
        candidates=loaded_candidates,
    )


def load_search_workspace(root: Path) -> SearchWorkspace:
    for required_dir in (
        root / "campaigns",
        root / "benchmarks" / "tasks",
        root / "benchmarks" / "decoders",
        root / "benchmarks" / "suites",
        root / "benchmarks" / "schemas",
        root / "results" / "search",
    ):
        _require_directory(required_dir)

    schema_root = root / "benchmarks" / "schemas"
    campaign_validator = _validator(schema_root / "campaign.schema.json")
    search_space_validator = _validator(schema_root / "search-space.schema.json")
    task_validator = _validator(schema_root / "benchmark-task.schema.json")
    decoder_validator = _validator(schema_root / "decoder-config.schema.json")
    suite_validator = _validator(schema_root / "benchmark-suite.schema.json")
    run_spec_validator = _validator(schema_root / "run-spec.schema.json")
    candidate_validator = _validator(schema_root / "candidate.schema.json")
    manifest_validator = _validator(schema_root / "result-manifest.schema.json")

    campaigns, search_spaces = _load_campaigns(
        root, campaign_validator, search_space_validator
    )
    tasks = _load_indexed_directory(root, "tasks", task_validator)
    decoders = _load_indexed_directory(root, "decoders", decoder_validator)
    suites = _load_indexed_directory(root, "suites", suite_validator)
    _load_baselines(root)

    for task_id, task in tasks.items():
        collection = task["collection"]
        overrides = collection.get("decoder_overrides", {})
        unknown = sorted(set(overrides) - set(decoders))
        if unknown:
            raise SearchIntegrityError(
                f"unknown decoder_overrides on task {task_id}: {', '.join(unknown)}"
            )

    for campaign_id, campaign in campaigns.items():
        if campaign["default_suite_id"] not in suites:
            raise SearchIntegrityError(
                f"unknown default_suite_id on {campaign_id}: "
                f"{campaign['default_suite_id']}"
            )

    for suite_id, suite in suites.items():
        for task_id in suite["task_ids"]:
            if task_id not in tasks:
                raise SearchIntegrityError(f"unknown task_id on suite {suite_id}: {task_id}")
        for decoder_id in suite["decoder_ids"]:
            if decoder_id not in decoders:
                raise SearchIntegrityError(
                    f"unknown decoder_id on suite {suite_id}: {decoder_id}"
                )

    _validate_quantum_tanner_p001_contract(tasks, decoders, suites)

    runs = _load_runs(
        root,
        run_spec_validator,
        candidate_validator,
        manifest_validator,
        campaigns,
        suites,
    )

    return SearchWorkspace(
        campaigns=campaigns,
        search_spaces=search_spaces,
        tasks=tasks,
        decoders=decoders,
        suites=suites,
        runs=runs,
    )

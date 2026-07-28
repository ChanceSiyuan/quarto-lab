from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from autoqec_search import __version__
from autoqec_search.distance_methods import (
    COPIED_ZOO_EXACT,
    DistanceMethodOptions,
    LoadedDistancePayload,
    distance_method_metadata,
    compute_distance_payload,
    load_distance_payload_from_dict,
    normalize_distance_method_options,
)
from autoqec_search.eval_candidates import (
    ResolvedCandidate,
    candidate_payload,
    copy_candidate_artifacts,
    resolve_campaign_candidate,
    resolve_campaign_candidate_spec,
    resolve_directory_candidate,
)
from autoqec_search.load import (
    SearchIntegrityError,
    SearchWorkspace,
    _load_campaigns,
    _load_indexed_directory,
    _require_directory,
    _validate_quantum_tanner_p001_contract,
    _validator,
)
from autoqec_search.plot import render_candidate_plot
from autoqec_search.render import render_eval_leaderboard, render_eval_summary
from autoqec_search.rsinter import (
    build_completed_manifest,
    expected_explicit_observable_run_metadata,
    parse_decoder_filter,
    parse_p_filter,
    parse_results_jsonl,
    exact_distance_required_message,
    require_rsinter,
    rounds_for_task,
    run_rsinter,
    task_requires_explicit_css_observables,
    validate_selected_decoders,
    validate_selected_p_values,
    write_css_matrix_wrapper,
    write_css_observables_wrapper,
    write_css_spec_toml,
    write_spec_toml,
)
from autoqec_search.structure import matrix_data, summarize_css_structure


@dataclass(frozen=True)
class EvalRunResult:
    run_root: Path
    candidate_root: Path
    candidate_id: str
    run_id: str


@dataclass(frozen=True)
class CandidateEvaluationResult:
    candidate_root: Path
    candidate_id: str
    distance: int | None
    upper_bound: int | None
    distance_bound_type: str | None
    structure: dict
    completed_manifests: list[dict]
    completed_by_decoder: dict[str, dict]
    selected_decoder_ids: list[str]
    selected_p_values: list[float]
    rsinter_version: str


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def _sparse_rows_payload(payload: dict, label: str) -> dict:
    rows = matrix_data(payload, label)
    matrix_format = payload.get("format")
    if matrix_format == "dense_binary_matrix":
        num_cols = int(payload["n_cols"])
    elif matrix_format == "sparse_rows":
        num_cols = int(payload["num_cols"])
    else:
        raise SearchIntegrityError(
            f"{label} must be dense_binary_matrix or sparse_rows"
        )
    return {
        "format": "sparse_rows",
        "num_cols": num_cols,
        "rows": [[column for column, bit in enumerate(row) if bit] for row in rows],
    }


def _write_css_rsinter_matrix_artifacts(
    candidate_root: Path,
    candidate: ResolvedCandidate,
) -> dict[str, str]:
    hx_path = candidate_root / "artifacts" / "hx.sparse_rows.json"
    hz_path = candidate_root / "artifacts" / "hz.sparse_rows.json"
    _write_json(hx_path, _sparse_rows_payload(candidate.hx, "hx.json"))
    _write_json(hz_path, _sparse_rows_payload(candidate.hz, "hz.json"))
    return {
        "hx": "../artifacts/hx.sparse_rows.json",
        "hz": "../artifacts/hz.sparse_rows.json",
    }


def _css_task_basis(task: dict) -> str:
    css_memory = task.get("css_memory")
    if isinstance(css_memory, dict) and css_memory.get("basis") in {"x", "z"}:
        return str(css_memory["basis"])
    observable = task.get("observable")
    if observable == "logical_x":
        return "x"
    if observable == "logical_z":
        return "z"
    raise SearchIntegrityError(
        f"unsupported task observable for CSS eval: {observable}"
    )


def _created_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _default_run_id(created_at: str) -> str:
    stamp = (
        created_at.replace("-", "")
        .replace(":", "")
        .replace("T", "T")
        .removesuffix("Z")
    )
    return f"eval-{stamp}Z"


def _validate_run_id(run_id: str) -> None:
    _validate_path_segment(run_id, label="run_id")


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


def _validate_eval_path_ids(*, campaign_id: str, suite: dict, task: dict) -> None:
    _validate_path_segment(campaign_id, label="campaign_id")
    _validate_path_segment(task["id"], label="task_id")
    for task_id in suite["task_ids"]:
        _validate_path_segment(task_id, label="task_id")
    for decoder_id in suite["decoder_ids"]:
        _validate_path_segment(decoder_id, label="decoder_id")


def _exchange_directories(left: Path, right: Path) -> bool:
    libc = ctypes.CDLL(None, use_errno=True)
    rename_exchange = 0x00000002

    if sys.platform == "darwin":
        renamex_np = getattr(libc, "renamex_np", None)
        if renamex_np is None:
            return False

        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        result = renamex_np(os.fsencode(left), os.fsencode(right), rename_exchange)
    elif sys.platform.startswith("linux"):
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            return False

        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        at_fdcwd = getattr(os, "AT_FDCWD", -100)
        result = renameat2(
            at_fdcwd,
            os.fsencode(left),
            at_fdcwd,
            os.fsencode(right),
            rename_exchange,
        )
    else:
        return False

    if result == 0:
        return True

    error = ctypes.get_errno()
    unsupported_errors = {
        errno.EINVAL,
        errno.ENOSYS,
        errno.EXDEV,
        getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
        errno.EOPNOTSUPP,
    }
    if error in unsupported_errors:
        return False
    raise OSError(error, os.strerror(error), f"{left} <-> {right}")


def _install_staged_run(stage_root: Path, run_root: Path) -> None:
    if not run_root.exists():
        stage_root.rename(run_root)
        return

    if _exchange_directories(stage_root, run_root):
        shutil.rmtree(stage_root)
        return

    backup_root = Path(
        tempfile.mkdtemp(prefix=f".{run_root.name}.previous-", dir=run_root.parent)
    )
    backup_root.rmdir()
    run_root.rename(backup_root)
    try:
        stage_root.rename(run_root)
    except Exception:
        if not run_root.exists() and backup_root.exists():
            backup_root.rename(run_root)
        raise
    shutil.rmtree(backup_root)


def _candidate_distance(candidate: ResolvedCandidate) -> int:
    distance = candidate.spec.parameters.get("distance")
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError("candidate distance must be a positive integer")
    return distance


def _copied_instance_distance(
    candidate: ResolvedCandidate,
    *,
    allow_missing: bool = False,
) -> int | None:
    derived_properties = candidate.instance.get("derived_properties")
    distance = (
        derived_properties.get("distance")
        if isinstance(derived_properties, dict)
        else None
    )
    if distance is None and allow_missing:
        return None
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError("copied instance distance must be a positive integer")
    return distance


def _explicit_observable_row_count(observables_x: dict[str, Any]) -> int:
    rows = observables_x.get("rows") if isinstance(observables_x, dict) else None
    return len(rows) if isinstance(rows, list) else 0


def _validate_explicit_x_observable_count(
    *,
    candidate_id: str,
    observables_x: dict[str, Any],
    structure: dict,
) -> None:
    expected_k = structure.get("k")
    if type(expected_k) is not int or expected_k <= 0:
        return
    row_count = _explicit_observable_row_count(observables_x)
    if row_count != expected_k:
        raise SearchIntegrityError(
            f"explicit X observables define {row_count} rows, expected k = {expected_k}"
        )


def _unavailable_distance_payload(candidate: ResolvedCandidate) -> dict[str, object]:
    source_instance_id = candidate.instance.get("id")
    if not isinstance(source_instance_id, str) or not source_instance_id:
        raise SearchIntegrityError("missing source instance id")
    return {
        "status": "unavailable",
        "distance": None,
        "method": "not-recorded-on-zoo-instance",
        "source_instance_id": source_instance_id,
        "source_instance_path": str(candidate.artifact_root),
    }


def _distance_context(loaded_distance: LoadedDistancePayload) -> dict[str, object]:
    return {
        "method": loaded_distance.method,
        "bound_type": loaded_distance.bound_type,
        "upper_bound": loaded_distance.upper_bound,
    }


def _load_eval_workspace(root: Path) -> SearchWorkspace:
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

    campaigns, search_spaces = _load_campaigns(
        root, campaign_validator, search_space_validator
    )
    tasks = _load_indexed_directory(root, "tasks", task_validator)
    decoders = _load_indexed_directory(root, "decoders", decoder_validator)
    suites = _load_indexed_directory(root, "suites", suite_validator)
    _validate_quantum_tanner_p001_contract(tasks, decoders, suites)

    for campaign_key, campaign in campaigns.items():
        if campaign["default_suite_id"] not in suites:
            raise SearchIntegrityError(
                f"unknown default_suite_id on {campaign_key}: "
                f"{campaign['default_suite_id']}"
            )

    for suite_id, suite in suites.items():
        for task_id in suite["task_ids"]:
            if task_id not in tasks:
                raise SearchIntegrityError(
                    f"unknown task_id on suite {suite_id}: {task_id}"
                )
        for decoder_id in suite["decoder_ids"]:
            if decoder_id not in decoders:
                raise SearchIntegrityError(
                    f"unknown decoder_id on suite {suite_id}: {decoder_id}"
                )

    return SearchWorkspace(
        campaigns=campaigns,
        search_spaces=search_spaces,
        tasks=tasks,
        decoders=decoders,
        suites=suites,
        runs={},
    )


def _placeholder_manifest(
    *,
    campaign_id: str,
    run_id: str,
    candidate_id: str,
    task: dict,
    decoder_id: str,
    created_at: str,
) -> dict:
    return {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "candidate_id": candidate_id,
        "task_id": task["id"],
        "decoder_id": decoder_id,
        "status": "placeholder",
        "metrics": {metric_name: None for metric_name in task["result_metrics"]},
        "created_at": created_at,
    }


def _single_task(suite: dict, tasks: dict[str, dict]) -> dict:
    if len(suite["task_ids"]) != 1:
        raise SearchIntegrityError("eval currently requires a single-task suite")
    return tasks[suite["task_ids"][0]]


def _resolve_candidate(
    root: Path,
    workspace,
    *,
    campaign_id: str,
    distance: int | None,
    candidate_dir: Path | None,
) -> ResolvedCandidate:
    if candidate_dir is not None:
        candidate = resolve_directory_candidate(
            root,
            candidate_dir,
            campaign_id=campaign_id,
        )
        if distance is not None and _candidate_distance(candidate) != distance:
            raise SearchIntegrityError(
                "candidate distance does not match --distance: "
                f"{_candidate_distance(candidate)} != {distance}"
            )
        return candidate

    if distance is None:
        search_space = workspace.search_spaces.get(campaign_id)
        explicit_specs = []
        if isinstance(search_space, dict):
            explicit_specs = [
                spec
                for spec in search_space.get("candidate_specs", [])
                if isinstance(spec, dict) and "instance_path" in spec
            ]
        if len(explicit_specs) == 1:
            return resolve_campaign_candidate_spec(
                root,
                explicit_specs[0],
                campaign_id=campaign_id,
            )
        raise SearchIntegrityError("eval requires --distance unless --candidate is set")
    return resolve_campaign_candidate(
        root,
        workspace,
        campaign_id=campaign_id,
        distance=distance,
    )


def evaluate_resolved_candidate_into_run(
    *,
    run_root: Path,
    run_id: str,
    campaign_id: str,
    candidate: ResolvedCandidate,
    workspace: SearchWorkspace,
    suite: dict,
    task: dict,
    selected_decoder_ids: list[str],
    selected_p_values: list[float],
    created_at: str,
    rsinter_executable: str,
    rsinter_version: str,
    distance_method_options: DistanceMethodOptions | None = None,
    rsinter_timeout_seconds: int | None = None,
    general_css: bool = False,
    distance_payload_override: dict[str, object] | None = None,
    observables_x_override: dict[str, Any] | None = None,
) -> CandidateEvaluationResult:
    distance_method_options = distance_method_options or normalize_distance_method_options(
        method=None,
        seed=0,
    )
    candidate_id = candidate.spec.candidate_id
    _validate_path_segment(candidate_id, label="candidate_id")
    task_is_css = task.get("input_type") == "css"
    structure = summarize_css_structure(candidate.hx, candidate.hz)
    candidate_root = run_root / "candidates" / candidate_id

    if not structure["css_commute"]:
        _write_json(candidate_root / "structure.json", structure)
        raise SearchIntegrityError(f"candidate CSS checks do not commute: {candidate_id}")

    copied_distance = _copied_instance_distance(candidate, allow_missing=task_is_css)
    if distance_payload_override is not None:
        distance_payload = dict(distance_payload_override)
    elif (
        copied_distance is None
        and task_is_css
        and distance_method_options.method == COPIED_ZOO_EXACT
    ):
        distance_payload = _unavailable_distance_payload(candidate)
    else:
        distance_payload = compute_distance_payload(candidate, distance_method_options)
    loaded_distance = load_distance_payload_from_dict(
        distance_payload,
        label=f"distance method result for {candidate_id}",
    )
    if loaded_distance.distance is None and not task_is_css:
        raise SearchIntegrityError(
            exact_distance_required_message(
                "non-CSS evaluation",
                distance_context=_distance_context(loaded_distance),
            )
        )
    effective_distance = loaded_distance.distance
    rounds = rounds_for_task(
        task,
        distance=effective_distance,
        distance_context=_distance_context(loaded_distance),
    )

    _write_json(
        candidate_root / "candidate.json",
        candidate_payload(candidate, run_id),
    )
    copy_candidate_artifacts(
        candidate,
        candidate_root,
        distance_payload=distance_payload,
    )
    _write_json(candidate_root / "structure.json", structure)

    spec_path = candidate_root / "rsinter" / "spec.toml"
    out_dir = candidate_root / "rsinter" / "out"
    css_basis = _css_task_basis(task) if (general_css or task_is_css) else None
    requires_explicit_observables = task_requires_explicit_css_observables(task)
    observables_x = (
        observables_x_override
        if observables_x_override is not None
        else candidate.observables_x
    )
    should_emit_observables = (
        observables_x_override is not None or requires_explicit_observables
    )
    if should_emit_observables and observables_x is not None and css_basis != "x":
        raise SearchIntegrityError(
            f"candidate {candidate_id} has logical-X observables, "
            f"but task {task['id']} uses basis {css_basis}"
        )
    if should_emit_observables and observables_x is not None:
        _validate_explicit_x_observable_count(
            candidate_id=candidate_id,
            observables_x=observables_x,
            structure=structure,
        )
    emitted_observables = False
    expected_observable_run_metadata_by_decoder: dict[str, dict[str, object]] = {}
    if general_css:
        input_dir = candidate_root / "rsinter" / "input"
        hx_input = input_dir / "hx.css.json"
        hz_input = input_dir / "hz.css.json"
        write_css_matrix_wrapper(hx_input, candidate.hx)
        write_css_matrix_wrapper(hz_input, candidate.hz)
        observables_input: Path | None = None
        if should_emit_observables and observables_x is not None:
            observables_input = input_dir / "observables.css.json"
            write_css_observables_wrapper(observables_input, observables_x)
            emitted_observables = True
        elif requires_explicit_observables:
            raise SearchIntegrityError(
                f"task {task['id']} requires explicit CSS observables for {candidate_id}"
            )
        write_css_spec_toml(
            spec_path,
            task=task,
            decoders=workspace.decoders,
            selected_decoder_ids=selected_decoder_ids,
            code_id=(
                candidate.spec.code_family
                if general_css and not task_is_css
                else str(candidate.instance.get("id", candidate_id))
            ),
            hx_path=Path("input/hx.css.json"),
            hz_path=Path("input/hz.css.json"),
            observables_path=(
                Path("input/observables.css.json")
                if observables_input is not None
                else None
            ),
            rounds=rounds,
            p_values=selected_p_values,
        )
    elif task_is_css:
        css_matrix_input = _write_css_rsinter_matrix_artifacts(candidate_root, candidate)
        observables_input: Path | None = None
        if should_emit_observables and observables_x is not None:
            observables_input = (
                candidate_root / "rsinter" / "input" / "observables.css.json"
            )
            write_css_observables_wrapper(observables_input, observables_x)
            emitted_observables = True
        elif requires_explicit_observables:
            raise SearchIntegrityError(
                f"task {task['id']} requires explicit CSS observables for {candidate_id}"
            )
        write_css_spec_toml(
            spec_path,
            task=task,
            decoders=workspace.decoders,
            selected_decoder_ids=selected_decoder_ids,
            code_id=str(candidate.instance.get("id", candidate_id)),
            hx_path=css_matrix_input["hx"],
            hz_path=css_matrix_input["hz"],
            observables_path=(
                Path("input/observables.css.json")
                if observables_input is not None
                else None
            ),
            rounds=rounds,
            p_values=selected_p_values,
        )
    else:
        write_spec_toml(
            spec_path,
            task=task,
            decoders=workspace.decoders,
            selected_decoder_ids=selected_decoder_ids,
            distance=effective_distance,
            rounds=rounds,
            p_values=selected_p_values,
        )
    if emitted_observables:
        observable_count = _explicit_observable_row_count(observables_x)
        expected_observable_run_metadata_by_decoder = {
            decoder_id: expected_explicit_observable_run_metadata(
                task=task,
                decoder=workspace.decoders[decoder_id],
                basis=css_basis,
                observable_count=observable_count,
            )
            for decoder_id in selected_decoder_ids
        }
    if rsinter_timeout_seconds is None:
        run_rsinter(
            spec_path,
            out_dir,
            executable=rsinter_executable,
            requires_general_css_support=general_css,
        )
    else:
        run_rsinter(
            spec_path,
            out_dir,
            executable=rsinter_executable,
            timeout_seconds=rsinter_timeout_seconds,
            requires_general_css_support=general_css,
        )

    completed_manifests: list[dict] = []
    completed_by_decoder: dict[str, dict] = {}
    for decoder_id in selected_decoder_ids:
        decoder_config = workspace.decoders[decoder_id]
        expected_decoder_observable_run_metadata = (
            expected_observable_run_metadata_by_decoder.get(decoder_id)
        )
        parsed = parse_results_jsonl(
            out_dir / decoder_id / "test-run" / "results.jsonl",
            expected_decoder_id=decoder_id,
            expected_task_id=task["id"],
            expected_distance=None if (general_css or task_is_css) else effective_distance,
            expected_p_values=selected_p_values,
            expected_decoder_parameters=decoder_config.get("parameters", {}),
            expected_impl_key=decoder_config.get("impl_key"),
            require_observable_run_metadata=emitted_observables,
            expected_observable_run_metadata=expected_decoder_observable_run_metadata,
        )
        manifest = build_completed_manifest(
            campaign_id=campaign_id,
            run_id=run_id,
            candidate_id=candidate_id,
            task_id=task["id"],
            decoder_id=decoder_id,
            decoder_parameters=parsed.decoder_parameters,
            created_at=created_at,
            tool_revisions={
                "autoqec_search": __version__,
                "rsinter": rsinter_version,
            },
            points=parsed.points,
            run_metadata=parsed.run_metadata,
            require_observable_run_metadata=emitted_observables,
            expected_observable_run_metadata=expected_decoder_observable_run_metadata,
        )
        completed_manifests.append(manifest)
        completed_by_decoder[decoder_id] = manifest

    for decoder_id in suite["decoder_ids"]:
        if decoder_id in completed_by_decoder:
            manifest = completed_by_decoder[decoder_id]
        else:
            manifest = _placeholder_manifest(
                campaign_id=campaign_id,
                run_id=run_id,
                candidate_id=candidate_id,
                task=task,
                decoder_id=decoder_id,
                created_at=created_at,
            )
        _write_json(
            candidate_root
            / "evaluations"
            / task["id"]
            / decoder_id
            / "manifest.json",
            manifest,
        )

    _write_text(
        candidate_root / "candidate-plot.svg",
        render_candidate_plot(
            candidate_id,
            effective_distance,
            task["id"],
            created_at,
            completed_manifests,
        ),
    )

    return CandidateEvaluationResult(
        candidate_root=candidate_root,
        candidate_id=candidate_id,
        distance=effective_distance,
        upper_bound=loaded_distance.upper_bound,
        distance_bound_type=loaded_distance.bound_type,
        structure=structure,
        completed_manifests=completed_manifests,
        completed_by_decoder=completed_by_decoder,
        selected_decoder_ids=selected_decoder_ids,
        selected_p_values=selected_p_values,
        rsinter_version=rsinter_version,
    )


def evaluate_single_candidate(
    root: Path,
    *,
    campaign_id: str,
    distance: int | None,
    candidate_dir: Path | None,
    run_id: str | None,
    decoder_filter: list[str] | None,
    p_filter: list[str] | None,
    general_css: bool = False,
    force: bool,
    distance_method_options: DistanceMethodOptions | None = None,
) -> EvalRunResult:
    distance_method_options = distance_method_options or normalize_distance_method_options(
        method=None,
        seed=0,
    )
    workspace = _load_eval_workspace(root)
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")

    campaign = workspace.campaigns[campaign_id]
    suite = workspace.suites[campaign["default_suite_id"]]
    task = _single_task(suite, workspace.tasks)
    _validate_eval_path_ids(campaign_id=campaign_id, suite=suite, task=task)
    selected_decoder_ids = validate_selected_decoders(
        suite,
        parse_decoder_filter(decoder_filter),
    )
    selected_p_values = validate_selected_p_values(task, parse_p_filter(p_filter))

    candidate = _resolve_candidate(
        root,
        workspace,
        campaign_id=campaign_id,
        distance=distance,
        candidate_dir=candidate_dir,
    )
    candidate_id = candidate.spec.candidate_id
    _validate_path_segment(candidate_id, label="candidate_id")

    created_at = _created_at()
    actual_run_id = run_id or _default_run_id(created_at)
    _validate_run_id(actual_run_id)
    run_root = root / "results" / "search" / campaign_id / actual_run_id
    target_candidate_root = run_root / "candidates" / candidate_id
    if run_root.exists() and not force:
        raise SearchIntegrityError(f"run already exists: {run_root}")

    task_is_css = task.get("input_type") == "css"
    copied_distance = _copied_instance_distance(candidate, allow_missing=task_is_css)
    rounds_for_task(task, distance=copied_distance)
    structure = summarize_css_structure(candidate.hx, candidate.hz)
    if not structure["css_commute"]:
        if not run_root.exists():
            _write_json(target_candidate_root / "structure.json", structure)
        raise SearchIntegrityError(f"candidate CSS checks do not commute: {candidate_id}")

    rsinter_executable, rsinter_version = require_rsinter()
    run_root.parent.mkdir(parents=True, exist_ok=True)
    stage_root = Path(
        tempfile.mkdtemp(prefix=f".{actual_run_id}.tmp-", dir=run_root.parent)
    )

    try:
        candidate_result = evaluate_resolved_candidate_into_run(
            run_root=stage_root,
            run_id=actual_run_id,
            campaign_id=campaign_id,
            candidate=candidate,
            workspace=workspace,
            suite=suite,
            task=task,
            selected_decoder_ids=selected_decoder_ids,
            selected_p_values=selected_p_values,
            created_at=created_at,
            rsinter_executable=rsinter_executable,
            rsinter_version=rsinter_version,
            distance_method_options=distance_method_options,
            general_css=general_css,
        )
        candidate_root = candidate_result.candidate_root
        completed_manifests = candidate_result.completed_manifests
        structure = candidate_result.structure
        copied_distance = candidate_result.distance

        _write_json(
            stage_root / "env.json",
            {
                "tool": "autoqec-search",
                "version": __version__,
                "generated_at": created_at,
                "mode": "eval",
                "rsinter": rsinter_version,
                "distance_method": distance_method_metadata(distance_method_options),
            },
        )
        _write_json(
            stage_root / "frontier.json",
            {
                "campaign_id": campaign_id,
                "run_id": actual_run_id,
                "items": [
                    {
                        "candidate_id": candidate_id,
                        "status": "evaluated",
                        "selected_decoder_ids": selected_decoder_ids,
                        "selected_p_values": selected_p_values,
                    }
                ],
            },
        )

        run_spec = {
            "campaign_id": campaign_id,
            "run_id": actual_run_id,
            "suite_id": suite["id"],
            "task_ids": suite["task_ids"],
            "decoder_ids": suite["decoder_ids"],
            "candidate_ids": [candidate_id],
            "created_at": created_at,
            "mode": "eval",
        }
        _write_text(
            stage_root / "leaderboard.csv",
            render_eval_leaderboard(completed_manifests),
        )
        _write_text(
            stage_root / "summary.md",
            render_eval_summary(
                campaign_id=campaign_id,
                run_id=actual_run_id,
                candidate_id=candidate_id,
                task_ids=[task["id"]],
                decoder_ids=selected_decoder_ids,
                deferred_decoder_ids=[
                    decoder_id
                    for decoder_id in suite["decoder_ids"]
                    if decoder_id not in selected_decoder_ids
                ],
                structure=structure,
                distance=copied_distance,
            ),
        )
        _write_json(stage_root / "run_spec.json", run_spec)

        _install_staged_run(stage_root, run_root)
    except Exception:
        if stage_root.exists():
            shutil.rmtree(stage_root)
        raise

    return EvalRunResult(
        run_root=run_root,
        candidate_root=target_candidate_root,
        candidate_id=candidate_id,
        run_id=actual_run_id,
    )

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from jsonschema.exceptions import SchemaError, ValidationError

from autoqec_search.css_distance_autoresearch import (
    build_public_proposal_prompt,
    create_css_distance_algorithm_worktree,
    evaluate_css_distance_algorithm,
)
from autoqec_search.css_distance_container import (
    CssDistanceContainerError,
    DockerCandidateCommandBuilder,
    DockerImage,
    require_docker_preflight,
)
from autoqec_search.css_distance_eval import (
    DEFAULT_TIMEOUT_SECONDS,
    CssDistanceEvalError,
    materialize_private_holdout,
)
from autoqec_search.css_distance_seal import create_candidate_freeze
from autoqec_search.css_distance_suite import (
    MINIMUM_SEEDS,
    TIME_LIMIT_SECONDS,
    load_and_validate_source_pool,
    prepare_blind_suite,
    verify_suite_commitment,
)
from autoqec_search.distance_methods import normalize_distance_method_options
from autoqec_search.compare_candidates import (
    compare_candidate_runs,
    write_compare_candidates,
)
from autoqec_search.structure import verify_css_upper_bound_witness
from autoqec_search.quotient_coset_upper_bound import (
    find_quotient_coset_upper_bound,
)
from autoqec_search.upper_bound_witness_finder import (
    run_qec_code_random_window_upper_bound_css_witness,
)
from autoqec_search.surface_copy_comparison import (
    compare_surface_copy,
    write_surface_copy_comparison,
)
from autoqec_search.eval_run import evaluate_single_candidate
from autoqec_search.eval_candidates import resolve_campaign_candidate_spec
from autoqec_search.init_run import init_placeholder_run
from autoqec_search.load import (
    SearchIntegrityError,
    _load_campaigns,
    _load_indexed_directory,
    _validator,
    load_search_run,
    load_search_workspace,
)
from autoqec_search.preflight import (
    render_preflight_table,
    run_preflight,
    write_preflight_html,
)
from autoqec_search.promote import promote_run, render_promotion_cli_summary
from autoqec_search.quantum_tanner_catalog import (
    DEFAULT_CATALOG_PATH,
    validate_quantum_tanner_fixture_catalog,
)
from autoqec_search.quantum_tanner_proposal_materialization import (
    materialize_quantum_tanner_proposal_files,
)
from autoqec_search.quantum_tanner_proposal_import import (
    import_quantum_tanner_proposal_instances,
)
from autoqec_search.quantum_tanner_proposals import (
    QuantumTannerProposalValidationError,
    validate_quantum_tanner_proposal_file,
)
from autoqec_search.quantum_tanner_generator import (
    generate_quantum_tanner_sweep,
    load_quantum_tanner_sweep_config,
    render_quantum_tanner_generation_summary,
    render_quantum_tanner_sweep_summary,
)
from autoqec_search.quantum_tanner_ai_handoff import (
    ingest_quantum_tanner_ai_batch,
    prepare_quantum_tanner_ai_batch,
)
from autoqec_search.quantum_tanner_ai_feedback import (
    build_quantum_tanner_ai_feedback,
    write_quantum_tanner_ai_feedback,
)
from autoqec_search.quantum_tanner_witness_batch import (
    attach_quantum_tanner_witnesses,
)
from autoqec_search.quantum_tanner_proposal_observables import (
    complete_quantum_tanner_proposal_observables,
)
from autoqec_search.reference_check import write_reference_check
from autoqec_search.report import write_report_html
from autoqec_search.render import render_eval_success, render_run_overview
from autoqec_search.run_loop import choose_seed, run_autoresearch
from autoqec_search.strategy_compare import compare_strategies, write_strategy_comparison


def _repo_root_from_run(run_root: Path) -> Path:
    if (
        run_root.parent.parent.name != "search"
        or run_root.parent.parent.parent.name != "results"
    ):
        raise SearchIntegrityError(
            "run path must look like results/search/<campaign-id>/<run-id>"
        )
    return run_root.parent.parent.parent.parent


def _fixture_catalog_paths_from_search_spaces(
    search_spaces: dict[str, dict],
) -> tuple[str, ...]:
    paths: set[str] = set()
    for search_space in search_spaces.values():
        for candidate_spec in search_space.get("candidate_specs", []):
            if isinstance(candidate_spec, dict) and "fixture_catalog_path" in candidate_spec:
                path = candidate_spec["fixture_catalog_path"]
                if isinstance(path, str) and path:
                    candidate_path = Path(path)
                    if candidate_path.is_absolute() or any(part == ".." for part in candidate_path.parts):
                        raise SearchIntegrityError(
                            f"fixture_catalog_path must be a safe relative path: {path}"
                        )
                    paths.add(path)
    return tuple(sorted(paths))


def _should_skip_missing_legacy_zoo_instance(
    root: Path,
    candidate_spec: dict[str, Any],
) -> bool:
    instance_path = candidate_spec.get("instance_path")
    provenance = candidate_spec.get("provenance")
    if not isinstance(instance_path, str) or not isinstance(provenance, dict):
        return False
    if provenance.get("kind") == "proposal-derived":
        return False
    # Some search-layer tests copy campaigns/benchmarks/results without the Zoo tree.
    return instance_path.startswith("zoo/") and not (root / "zoo").exists()


def _validate_explicit_instance_candidates(
    root: Path,
    search_spaces: dict[str, dict],
) -> None:
    for campaign_id, search_space in search_spaces.items():
        for candidate_spec in search_space["candidate_specs"]:
            if "instance_path" not in candidate_spec:
                continue
            if _should_skip_missing_legacy_zoo_instance(root, candidate_spec):
                continue
            resolve_campaign_candidate_spec(
                root,
                candidate_spec,
                campaign_id=campaign_id,
            )


def _load_json_file(path: Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must contain a JSON object: {path}")
    return payload


def _default_provenance_path(out_path: Path) -> Path:
    return out_path.with_name(out_path.name + ".provenance.json")


def _is_explicit_tool_path(value: str) -> bool:
    path = Path(value)
    if path.is_absolute():
        return True
    separators = {os.sep}
    if os.altsep is not None:
        separators.add(os.altsep)
    return any(separator in value for separator in separators)


def _resolve_distance_ladder_exporter_bin(root: Path, configured: str) -> str:
    if _is_explicit_tool_path(configured):
        return configured
    found = shutil.which(configured)
    if found:
        return found
    checkout_binary = root / "target" / "debug" / configured
    if checkout_binary.is_file():
        return str(checkout_binary)
    raise SearchIntegrityError(
        "distance-ladder materialization requires autoqec-distance-ladder; "
        f"could not resolve {configured!r} on PATH or at {checkout_binary}"
    )


def _render_quantum_tanner_candidate_generation_summary(
    plan: Any,
    *,
    dry_run: bool,
) -> str:
    action = "would generate" if dry_run else "generated"
    distances = [entry["expected_distance"] for entry in plan.manifest["entries"]]
    lines = [
        f"{action} {len(plan.manifest['entries'])} quantum Tanner candidates for {plan.manifest['id']}",
        "candidate_ids: [" + ", ".join(str(distance) for distance in distances) + "]",
        f"manifest_path: {plan.manifest_path}",
    ]
    for entry in plan.manifest["entries"]:
        candidate_id = entry["instance_id"]
        distance = entry["expected_distance"]
        lines.extend(
            [
                f"- {candidate_id}",
                f"  n={entry['n']}",
                f"  k={entry['k']}",
                f"  distance_label=d{distance}",
                f"  quantum_tanner_spec: {entry['quantum_tanner_spec']}",
                f"  instance_dir: {plan.manifest['artifact_root']}/{candidate_id}",
            ]
        )
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


def _render_attach_quantum_tanner_witnesses_summary(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return (
        f"attached={counts['attached']} "
        f"skipped={counts['skipped']} "
        f"failed={counts['failed']}\n"
        f"search_space={summary['search_space_path']}\n"
        f"summary={summary['summary_path']}\n"
    )


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


def _require_css_distance_timeout(value: object) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
        or value > 300
    ):
        raise SearchIntegrityError(
            "timeout_seconds must be a positive finite number no greater than 300"
        )
    return value


def _atomic_write_witness_with_provenance(
    witness_path: Path,
    witness_payload: dict[str, Any],
    provenance_path: Path,
    provenance_payload: dict[str, Any],
) -> None:
    witness_tmp: Path | None = None
    provenance_tmp: Path | None = None
    witness_backup: Path | None = None
    provenance_backup: Path | None = None
    witness_published = False
    provenance_published = False

    def backup_existing_output(path: Path) -> Path | None:
        if not path.exists():
            return None
        fd, backup_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".bak",
        )
        os.close(fd)
        backup_path = Path(backup_name)
        os.replace(path, backup_path)
        return backup_path

    try:
        witness_tmp = _prepare_json_write(
            witness_path,
            witness_payload,
            label="witness",
        )
        provenance_tmp = _prepare_json_write(
            provenance_path,
            provenance_payload,
            label="provenance",
        )
        witness_backup = backup_existing_output(witness_path)
        provenance_backup = backup_existing_output(provenance_path)
        witness_tmp.replace(witness_path)
        witness_tmp = None
        witness_published = True
        provenance_tmp.replace(provenance_path)
        provenance_tmp = None
        provenance_published = True
    except OSError as exc:
        rollback_errors: list[OSError] = []
        for path, published in (
            (provenance_path, provenance_published),
            (witness_path, witness_published),
        ):
            if not published:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError as rollback_exc:
                rollback_errors.append(rollback_exc)
        for path, backup_path in (
            (provenance_path, provenance_backup),
            (witness_path, witness_backup),
        ):
            if backup_path is None:
                continue
            try:
                os.replace(backup_path, path)
            except OSError as rollback_exc:
                rollback_errors.append(rollback_exc)
        detail = str(exc)
        if rollback_errors:
            detail += "; rollback failed: " + "; ".join(
                str(rollback_exc) for rollback_exc in rollback_errors
            )
        raise SearchIntegrityError(
            f"could not write witness and provenance outputs: {detail}"
        ) from exc
    else:
        for backup_path in (witness_backup, provenance_backup):
            if backup_path is not None:
                backup_path.unlink(missing_ok=True)
    finally:
        if witness_tmp is not None:
            witness_tmp.unlink(missing_ok=True)
        if provenance_tmp is not None:
            provenance_tmp.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoqec-search")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate the search workspace layout"
    )
    validate_parser.add_argument(
        "--root",
        default=".",
        help="Repository root containing campaigns/, benchmarks/, and results/",
    )

    validate_qt_sweep_parser = subparsers.add_parser(
        "validate-quantum-tanner-sweep",
        help="Validate a generated quantum Tanner toric sweep config",
    )
    validate_qt_sweep_parser.add_argument("--config", required=True)

    validate_qt_proposal_parser = subparsers.add_parser(
        "validate-quantum-tanner-proposal",
        help="Validate a quantum Tanner AI proposal JSON file",
    )
    validate_qt_proposal_parser.add_argument("--proposal", required=True)
    validate_qt_proposal_parser.add_argument("--max-group-order", type=int, default=32)

    materialize_qt_proposals_parser = subparsers.add_parser(
        "materialize-quantum-tanner-proposals",
        help="Materialize validated quantum Tanner proposals through qec-code",
    )
    materialize_qt_proposals_parser.add_argument("--root", default=".")
    materialize_qt_proposals_parser.add_argument(
        "--proposal",
        action="append",
        required=True,
    )
    materialize_qt_proposals_parser.add_argument("--out-root", required=True)
    materialize_qt_proposals_parser.add_argument("--qec-code-bin", required=True)
    materialize_qt_proposals_parser.add_argument("--max-group-order", type=int, default=32)
    materialize_qt_proposals_parser.add_argument("--force", action="store_true")

    import_qt_proposals_parser = subparsers.add_parser(
        "import-quantum-tanner-proposal-instances",
        help="Import materialized quantum Tanner proposal instances into a search space",
    )
    import_qt_proposals_parser.add_argument("--root", default=".")
    import_qt_proposals_parser.add_argument("--campaign", required=True)
    import_source_group = import_qt_proposals_parser.add_mutually_exclusive_group(
        required=True
    )
    import_source_group.add_argument("--instance-root", default=None)
    import_source_group.add_argument("--manifest", default=None)
    import_qt_proposals_parser.add_argument("--search-space", required=True)
    import_qt_proposals_parser.add_argument(
        "--duplicate-policy",
        choices=["reject"],
        default="reject",
    )

    complete_qt_proposal_observables_parser = subparsers.add_parser(
        "complete-quantum-tanner-proposal-observables",
        help="Complete logical-X observables for proposal-derived quantum Tanner instances",
    )
    complete_qt_proposal_observables_parser.add_argument("--root", default=".")
    complete_qt_proposal_observables_parser.add_argument("--search-space", required=True)
    complete_qt_proposal_observables_parser.add_argument(
        "--basis",
        choices=["x"],
        required=True,
    )
    complete_qt_proposal_observables_parser.add_argument("--qec-code-bin", default=None)
    complete_qt_proposal_observables_parser.add_argument("--force", action="store_true")

    generate_qt_sweep_parser = subparsers.add_parser(
        "generate-quantum-tanner-sweep",
        help="Generate quantum Tanner toric specs and a distance-ladder manifest",
    )
    generate_qt_sweep_parser.add_argument("--config", required=True)
    generate_qt_sweep_parser.add_argument("--root", default=".")
    generate_qt_sweep_parser.add_argument("--dry-run", action="store_true")
    generate_qt_sweep_parser.add_argument("--materialize", action="store_true")
    generate_qt_sweep_parser.add_argument("--distance-ladder-exporter-bin", default=None)
    generate_qt_sweep_parser.add_argument("--force", action="store_true")

    generate_qt_candidates_parser = subparsers.add_parser(
        "generate-quantum-tanner-candidates",
        help="Generate materialized quantum Tanner candidates and autoresearch inputs",
    )
    generate_qt_candidates_parser.add_argument("--root", default=".")
    generate_qt_candidates_parser.add_argument("--config", required=True)
    generate_qt_candidates_parser.add_argument("--qec-code-bin", default=None)
    generate_qt_candidates_parser.add_argument("--dry-run", action="store_true")
    generate_qt_candidates_parser.add_argument("--force", action="store_true")

    prepare_qt_ai_batch_parser = subparsers.add_parser(
        "prepare-quantum-tanner-ai-batch",
        help="Prepare an offline AI proposal batch request for quantum Tanner search",
    )
    prepare_qt_ai_batch_parser.add_argument("--root", default=".")
    prepare_qt_ai_batch_parser.add_argument("--campaign", required=True)
    prepare_qt_ai_batch_parser.add_argument("--out", required=True)
    prepare_qt_ai_batch_parser.add_argument("--count", type=int, required=True)
    prepare_qt_ai_batch_parser.add_argument("--max-group-order", type=int, required=True)
    prepare_qt_ai_batch_parser.add_argument("--max-physical-qubits", type=int, default=None)
    prepare_qt_ai_batch_parser.add_argument("--feedback", default=None)

    ingest_qt_ai_batch_parser = subparsers.add_parser(
        "ingest-quantum-tanner-ai-batch",
        help="Ingest an offline AI proposal batch response for quantum Tanner search",
    )
    ingest_qt_ai_batch_parser.add_argument("--root", default=".")
    ingest_qt_ai_batch_parser.add_argument("--response", required=True)
    ingest_qt_ai_batch_parser.add_argument("--out", required=True)
    ingest_qt_ai_batch_parser.add_argument("--max-group-order", type=int, required=True)
    ingest_qt_ai_batch_parser.add_argument("--max-physical-qubits", type=int, default=None)

    prepare_css_distance_algorithm_parser = subparsers.add_parser(
        "prepare-css-distance-algorithm",
        help="Create an isolated CSS-distance algorithm worktree and LOG.md",
    )
    prepare_css_distance_algorithm_parser.add_argument("--root", default=".")
    prepare_css_distance_algorithm_parser.add_argument("--algorithm-id", required=True)
    prepare_css_distance_algorithm_parser.add_argument("--created-at", required=True)
    prepare_css_distance_algorithm_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
    )
    prepare_css_distance_algorithm_parser.add_argument(
        "--allow-dirty-root",
        action="store_true",
    )

    prepare_css_distance_proposal_parser = subparsers.add_parser(
        "prepare-css-distance-proposal",
        help="Write a redacted public prompt for CSS-distance algorithm proposals",
    )
    prepare_css_distance_proposal_parser.add_argument("--brief", required=True)
    prepare_css_distance_proposal_parser.add_argument("--source", required=True)
    prepare_css_distance_proposal_parser.add_argument("--out", required=True)

    materialize_css_distance_holdout_parser = subparsers.add_parser(
        "materialize-css-distance-holdout",
        help="Materialize the private CSS-distance holdout under a work root",
    )
    materialize_css_distance_holdout_parser.add_argument("--ladder", required=True)
    materialize_css_distance_holdout_parser.add_argument("--work-root", required=True)

    run_css_distance_candidate_parser = subparsers.add_parser(
        "run-css-distance-candidate",
        help="Run one CSS-distance candidate through the Docker evaluator",
    )
    run_css_distance_candidate_parser.add_argument("--algorithm-id", required=True)
    run_css_distance_candidate_parser.add_argument("--candidate-worktree", required=True)
    run_css_distance_candidate_parser.add_argument("--work-root", required=True)
    run_css_distance_candidate_parser.add_argument(
        "--phase",
        choices=["screening", "finalists"],
        default="screening",
    )
    run_css_distance_candidate_parser.add_argument("--image", required=True)
    run_css_distance_candidate_parser.add_argument("--baseline", required=True)
    run_css_distance_candidate_parser.add_argument("--output-root", default=None)
    run_css_distance_candidate_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )

    prepare_css_distance_paper_suite_parser = subparsers.add_parser(
        "prepare-css-distance-paper-suite",
        help="Prepare the private blinded CSS-distance paper validation split",
    )
    prepare_css_distance_paper_suite_parser.add_argument("--root", default=".")
    prepare_css_distance_paper_suite_parser.add_argument("--source-pool", required=True)
    prepare_css_distance_paper_suite_parser.add_argument("--work-root", required=True)
    prepare_css_distance_paper_suite_parser.add_argument("--commitment-out", required=True)
    prepare_css_distance_paper_suite_parser.add_argument("--created-at", required=True)

    validate_css_distance_paper_suite_parser = subparsers.add_parser(
        "validate-css-distance-paper-suite",
        help="Validate the private CSS-distance paper suite commitment",
    )
    validate_css_distance_paper_suite_parser.add_argument("--root", default=".")
    validate_css_distance_paper_suite_parser.add_argument("--source-pool", required=True)
    validate_css_distance_paper_suite_parser.add_argument("--work-root", required=True)
    validate_css_distance_paper_suite_parser.add_argument("--commitment", required=True)

    freeze_css_distance_paper_candidate_parser = subparsers.add_parser(
        "freeze-css-distance-paper-candidate",
        help="Freeze a CSS-distance paper-validation candidate before final holdout",
    )
    freeze_css_distance_paper_candidate_parser.add_argument(
        "--candidate-worktree", required=True
    )
    freeze_css_distance_paper_candidate_parser.add_argument("--candidate", required=True)
    freeze_css_distance_paper_candidate_parser.add_argument("--image-digest", required=True)
    freeze_css_distance_paper_candidate_parser.add_argument("--method-config", required=True)
    freeze_css_distance_paper_candidate_parser.add_argument("--seeds", required=True)
    freeze_css_distance_paper_candidate_parser.add_argument(
        "--development-summary", required=True
    )
    freeze_css_distance_paper_candidate_parser.add_argument("--commitment", required=True)
    freeze_css_distance_paper_candidate_parser.add_argument("--out", required=True)
    freeze_css_distance_paper_candidate_parser.add_argument("--created-at", required=True)

    preflight_parser = subparsers.add_parser(
        "preflight", help="Run contract, backend, and fixture doctor checks"
    )
    preflight_parser.add_argument(
        "--root",
        default=".",
        help="Repository root containing campaigns/, benchmarks/, and results/",
    )
    preflight_parser.add_argument(
        "--html",
        default=None,
        help="Optional output path for a self-contained HTML status page",
    )

    init_run_parser = subparsers.add_parser(
        "init-run", help="Create a placeholder run from a campaign"
    )
    init_run_parser.add_argument("--root", default=".")
    init_run_parser.add_argument("--campaign", required=True)
    init_run_parser.add_argument("--run-id", required=True)
    init_run_parser.add_argument("--timestamp", default=None)
    init_run_parser.add_argument("--force", action="store_true")

    eval_parser = subparsers.add_parser(
        "eval", help="Evaluate one candidate through rsinter"
    )
    eval_parser.add_argument("--root", default=".")
    eval_parser.add_argument("--campaign", required=True)
    eval_parser.add_argument("--distance", type=int, default=None)
    eval_parser.add_argument("--candidate", default=None)
    eval_parser.add_argument("--decoder", action="append", default=None)
    eval_parser.add_argument("--p", action="append", default=None)
    eval_parser.add_argument("--run-id", default=None)
    eval_parser.add_argument("--general-css", action="store_true")
    eval_parser.add_argument("--force", action="store_true")
    eval_parser.add_argument("--distance-method", default=None)
    eval_parser.add_argument("--qec-code-bin", default="qec-code")

    run_parser = subparsers.add_parser(
        "run", help="Run a time-bounded autoresearch loop in a git worktree"
    )
    run_parser.add_argument("--root", default=".")
    run_parser.add_argument("--campaign", required=True)
    run_parser.add_argument("--wall-clock", default=None)
    run_parser.add_argument("--seed", type=int, default=None)
    run_parser.add_argument("--run-id", default=None)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--cleanup-worktree", action="store_true")
    run_parser.add_argument("--allow-dirty-root", action="store_true")
    run_parser.add_argument("--distance-method", default=None)
    run_parser.add_argument("--qec-code-bin", default="qec-code")

    show_parser = subparsers.add_parser("show", help="Print a concise summary of one run")
    show_parser.add_argument("--run", required=True)

    report_parser = subparsers.add_parser(
        "report", help="Write a self-contained HTML report for one run"
    )
    report_parser.add_argument("--root", default=".")
    report_parser.add_argument("--run", required=True)
    report_parser.add_argument("--out", default=None)

    feedback_parser = subparsers.add_parser(
        "summarize-quantum-tanner-ai-feedback",
        help="Summarize a completed quantum Tanner AI proposal round",
    )
    feedback_parser.add_argument("--root", default=".")
    feedback_parser.add_argument("--run", required=True)
    feedback_parser.add_argument("--proposal-summary", default=None)
    feedback_parser.add_argument("--surface-copy", default=None)
    feedback_parser.add_argument("--out-json", required=True)
    feedback_parser.add_argument("--out-html", required=True)

    promote_parser = subparsers.add_parser(
        "promote", help="Promote accepted search candidates into the Zoo"
    )
    promote_parser.add_argument("--root", default=".")
    promote_parser.add_argument("--run", required=True)
    promote_parser.add_argument("--rules", default=None)
    promote_parser.add_argument("--force", action="store_true")

    reference_parser = subparsers.add_parser(
        "reference-check",
        help="Validate a run against a published reference fixture",
    )
    reference_parser.add_argument("--root", default=".")
    reference_parser.add_argument("--run", required=True)
    reference_parser.add_argument("--fixture", required=True)
    reference_parser.add_argument("--out", default=None)

    compare_parser = subparsers.add_parser(
        "compare-strategies",
        help="Compare search strategy ordering against fixture metrics",
    )
    compare_parser.add_argument("--root", default=".")
    compare_parser.add_argument("--campaign", required=True)
    compare_parser.add_argument("--strategies", nargs="+", required=True)
    compare_parser.add_argument("--budget-candidates", type=int, required=True)
    compare_parser.add_argument("--metrics", required=True)
    compare_parser.add_argument("--out", required=True)
    compare_parser.add_argument("--seed", type=int, default=None)

    compare_candidates_parser = subparsers.add_parser(
        "compare-candidates",
        help="Compare completed candidate points across two or more search runs",
        description="Compare completed candidate points across two or more search runs",
    )
    compare_candidates_parser.add_argument("--root", default=".")
    compare_candidates_parser.add_argument("--run", action="append", required=True)
    compare_candidates_parser.add_argument("--label", action="append", default=None)
    compare_candidates_parser.add_argument("--out", required=True)

    compare_surface_copy_parser = subparsers.add_parser(
        "compare-surface-copy",
        help="Compare Tanner candidates against copied rotated-surface baselines",
    )
    compare_surface_copy_parser.add_argument("--root", default=".")
    compare_surface_copy_parser.add_argument("--run", required=True)
    compare_surface_copy_parser.add_argument("--baseline", required=True)
    compare_surface_copy_parser.add_argument("--out", required=True)

    verify_witness_parser = subparsers.add_parser(
        "verify-witness",
        help="Verify a CSS upper-bound witness JSON payload",
    )
    verify_witness_parser.add_argument("--hx", required=True)
    verify_witness_parser.add_argument("--hz", required=True)
    verify_witness_parser.add_argument("--witness", required=True)

    find_witness_parser = subparsers.add_parser(
        "find-upper-bound-witness",
        help="Find and write one CSS upper-bound witness using qec-code",
    )
    find_witness_parser.add_argument("--hx", required=True)
    find_witness_parser.add_argument("--hz", required=True)
    find_witness_parser.add_argument("--basis", choices=["x", "z"], required=True)
    find_witness_parser.add_argument("--out", required=True)
    find_witness_parser.add_argument("--qec-code-bin", default="qec-code")
    find_witness_parser.add_argument("--iterations", type=int, default=1000)
    find_witness_parser.add_argument("--restarts", type=int, default=8)
    find_witness_parser.add_argument("--seed", type=int, default=12345)
    find_witness_parser.add_argument("--target-weight", type=int, default=None)
    find_witness_parser.add_argument("--timeout-seconds", type=float, default=300)
    find_witness_parser.add_argument("--provenance-out", default=None)

    find_quotient_coset_parser = subparsers.add_parser(
        "find-quotient-coset-upper-bound",
        help="Find and write one CSS upper-bound witness using the in-process quotient-coset search",
    )
    find_quotient_coset_parser.add_argument("--hx", required=True)
    find_quotient_coset_parser.add_argument("--hz", required=True)
    find_quotient_coset_parser.add_argument(
        "--basis", choices=["x", "z", "both"], default="both"
    )
    find_quotient_coset_parser.add_argument("--out", required=True)
    find_quotient_coset_parser.add_argument("--seed", type=int, default=0)
    find_quotient_coset_parser.add_argument("--max-no-improvement", type=int, default=2500)
    find_quotient_coset_parser.add_argument("--timeout-seconds", type=float, default=300)
    find_quotient_coset_parser.add_argument("--provenance-out", default=None)

    attach_qt_witnesses_parser = subparsers.add_parser(
        "attach-quantum-tanner-witnesses",
        help="Attach generated upper-bound witnesses to quantum Tanner candidates",
    )
    attach_qt_witnesses_parser.add_argument("--root", default=".")
    attach_source_group = attach_qt_witnesses_parser.add_mutually_exclusive_group(
        required=True
    )
    attach_source_group.add_argument("--campaign", default=None)
    attach_source_group.add_argument("--search-space", default=None)
    attach_qt_witnesses_parser.add_argument("--fixture-catalog", required=True)
    attach_qt_witnesses_parser.add_argument("--witness-dir", required=True)
    attach_qt_witnesses_parser.add_argument("--out-search-space", default=None)
    attach_qt_witnesses_parser.add_argument("--summary-out", default=None)
    attach_qt_witnesses_parser.add_argument(
        "--basis",
        choices=["x", "z"],
        required=True,
    )
    attach_qt_witnesses_parser.add_argument("--qec-code-bin", default="qec-code")
    attach_qt_witnesses_parser.add_argument("--iterations", type=int, default=1000)
    attach_qt_witnesses_parser.add_argument("--restarts", type=int, default=8)
    attach_qt_witnesses_parser.add_argument("--seed", type=int, default=12345)
    attach_qt_witnesses_parser.add_argument("--target-weight", type=int, default=None)
    attach_qt_witnesses_parser.add_argument("--timeout-seconds", type=float, default=300)
    attach_qt_witnesses_parser.add_argument("--force", action="store_true")
    attach_qt_witnesses_parser.add_argument("--require-all", action="store_true")
    attach_qt_witnesses_parser.add_argument("--fail-on-skipped", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "validate":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            workspace = load_search_workspace(root)
            catalog_paths = set(
                _fixture_catalog_paths_from_search_spaces(workspace.search_spaces)
            )
            if (root / DEFAULT_CATALOG_PATH).is_file():
                catalog_paths.add(str(DEFAULT_CATALOG_PATH))
            for catalog_path in sorted(catalog_paths):
                validate_quantum_tanner_fixture_catalog(root, catalog_path)
            _validate_explicit_instance_candidates(root, workspace.search_spaces)
            print(
                f"validated search workspace under {root}: "
                f"{len(workspace.campaigns)} campaigns, "
                f"{len(workspace.suites)} suites, "
                f"{len(workspace.runs)} runs"
            )
            return 0

        if args.command == "validate-quantum-tanner-sweep":
            config = load_quantum_tanner_sweep_config(Path(args.config))
            print(render_quantum_tanner_sweep_summary(config), end="")
            return 0

        if args.command == "validate-quantum-tanner-proposal":
            summary = validate_quantum_tanner_proposal_file(
                Path(args.proposal),
                max_group_order=args.max_group_order,
            )
            print(
                "PASS quantum_tanner_proposal "
                f"proposal_id={summary.proposal_id} "
                f"group_order={summary.group_order} "
                f"fingerprint={summary.fingerprint}"
            )
            print(json.dumps(summary.to_dict(), sort_keys=True))
            return 0

        if args.command == "materialize-quantum-tanner-proposals":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            summary = materialize_quantum_tanner_proposal_files(
                root,
                tuple(Path(path) for path in args.proposal),
                Path(args.out_root),
                qec_code_bin=args.qec_code_bin,
                max_group_order=args.max_group_order,
                force=args.force,
            )
            print(f"materialized={summary.materialized} failed={summary.failed}")
            for instance in summary.instances:
                print(f"- {instance.candidate_id}: {instance.instance_dir}")
            return 0

        if args.command == "import-quantum-tanner-proposal-instances":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            summary = import_quantum_tanner_proposal_instances(
                root,
                campaign_id=args.campaign,
                search_space_path=Path(args.search_space),
                instance_root=(
                    Path(args.instance_root) if args.instance_root is not None else None
                ),
                manifest_path=Path(args.manifest) if args.manifest is not None else None,
                duplicate_policy=args.duplicate_policy,
            )
            print(
                f"imported={summary.imported} "
                f"preserved={summary.preserved} "
                f"search_space={summary.search_space_path}"
            )
            return 0

        if args.command == "generate-quantum-tanner-sweep":
            config = load_quantum_tanner_sweep_config(Path(args.config))
            if args.distance_ladder_exporter_bin is not None:
                if not args.distance_ladder_exporter_bin:
                    raise SearchIntegrityError(
                        "distance_ladder_exporter_bin must be a non-empty string"
                    )
                config = replace(
                    config,
                    distance_ladder_exporter_bin=args.distance_ladder_exporter_bin,
                )
            plan = generate_quantum_tanner_sweep(
                Path(args.root),
                config,
                dry_run=args.dry_run,
                materialize=args.materialize,
                force=args.force,
            )
            print(
                render_quantum_tanner_generation_summary(
                    plan,
                    dry_run=args.dry_run,
                ),
                end="",
            )
            return 0

        if args.command == "generate-quantum-tanner-candidates":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            config = load_quantum_tanner_sweep_config(Path(args.config))
            if args.qec_code_bin is not None:
                if not args.qec_code_bin:
                    raise SearchIntegrityError("qec_code_bin must be a non-empty string")
                config = replace(config, qec_code_bin=args.qec_code_bin)
            if not args.dry_run:
                if not _is_explicit_tool_path(config.qec_code_bin):
                    raise SearchIntegrityError(
                        "qec_code_bin must be an explicit path for generate-quantum-tanner-candidates"
                    )
                config = replace(
                    config,
                    distance_ladder_exporter_bin=_resolve_distance_ladder_exporter_bin(
                        root,
                        config.distance_ladder_exporter_bin,
                    ),
                )
            plan = generate_quantum_tanner_sweep(
                root,
                config,
                dry_run=args.dry_run,
                materialize=not args.dry_run,
                force=args.force,
            )
            print(
                _render_quantum_tanner_candidate_generation_summary(
                    plan,
                    dry_run=args.dry_run,
                ),
                end="",
            )
            return 0

        if args.command == "prepare-quantum-tanner-ai-batch":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            out_dir = Path(args.out)
            prepare_quantum_tanner_ai_batch(
                root,
                campaign_id=args.campaign,
                out_dir=out_dir,
                count=args.count,
                max_group_order=args.max_group_order,
                max_physical_qubits=args.max_physical_qubits,
                feedback_path=Path(args.feedback) if args.feedback is not None else None,
            )
            print(f"wrote quantum Tanner AI batch request to {out_dir}")
            return 0

        if args.command == "ingest-quantum-tanner-ai-batch":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            out_dir = Path(args.out)
            summary = ingest_quantum_tanner_ai_batch(
                root,
                response_path=Path(args.response),
                out_dir=out_dir,
                max_group_order=args.max_group_order,
                max_physical_qubits=args.max_physical_qubits,
            )
            print(
                "ingested quantum Tanner AI batch "
                f"accepted={summary['accepted']} "
                f"rejected={summary['rejected']} "
                f"duplicate={summary['duplicate']}"
            )
            print(f"summary={out_dir / 'summary.json'}")
            return 0

        if args.command == "prepare-css-distance-algorithm":
            timeout_seconds = _require_css_distance_timeout(args.timeout_seconds)
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            experiment = create_css_distance_algorithm_worktree(
                root,
                algorithm_id=args.algorithm_id,
                created_at=args.created_at,
                allow_dirty_root=args.allow_dirty_root,
                timeout_seconds=timeout_seconds,
            )
            print(
                "prepared CSS-distance algorithm worktree "
                f"branch={experiment.branch} "
                f"path={experiment.worktree_root}"
            )
            return 0

        if args.command == "prepare-css-distance-proposal":
            source = _load_json_file(Path(args.source), label="CSS-distance source")
            prompt = build_public_proposal_prompt(
                research_brief=Path(args.brief).read_text(),
                source_pin=source,
            )
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(prompt, encoding="utf-8")
            print(f"wrote CSS-distance proposal prompt to {out_path}")
            return 0

        if args.command == "materialize-css-distance-holdout":
            holdout = materialize_private_holdout(
                ladder_path=Path(args.ladder),
                work_root=Path(args.work_root),
            )
            print(
                "materialized private CSS-distance holdout "
                f"cases={len(holdout['cases'])} "
                f"root={Path(args.work_root) / 'private' / 'holdout'}"
            )
            return 0

        if args.command == "run-css-distance-candidate":
            timeout_seconds = _require_css_distance_timeout(args.timeout_seconds)
            image = DockerImage(args.image, args.baseline)
            require_docker_preflight(image)
            work_root = Path(args.work_root)
            candidate_worktree = Path(args.candidate_worktree)
            output_root = (
                Path(args.output_root)
                if args.output_root is not None
                else work_root / "candidate-output" / args.algorithm_id
            )
            command_builder = DockerCandidateCommandBuilder(
                image=image,
                candidate_worktree=candidate_worktree,
                output_root=output_root,
            )
            result = evaluate_css_distance_algorithm(
                algorithm_id=args.algorithm_id,
                candidate_worktree=candidate_worktree,
                work_root=work_root,
                command=["candidate-entrypoint"],
                phase=args.phase,
                command_builder=command_builder,
                timeout_seconds=timeout_seconds,
            )
            summary = result.summary
            print(
                "completed CSS-distance candidate "
                f"algorithm={result.algorithm_id} "
                f"phase={result.phase} "
                f"decision={summary['decision']} "
                f"weighted_target_hits={summary.get('weighted_target_hits', 0)}"
            )
            return 0

        if args.command == "prepare-css-distance-paper-suite":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            commitment = prepare_blind_suite(
                root=root,
                source_pool_path=Path(args.source_pool),
                work_root=Path(args.work_root),
                commitment_path=Path(args.commitment_out),
                created_at=args.created_at,
            )
            counts = commitment["counts"]
            print(
                "prepared blinded CSS-distance paper suite "
                f"development={counts['development']} final={counts['final']}"
            )
            return 0

        if args.command == "validate-css-distance-paper-suite":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            load_and_validate_source_pool(root=root, path=Path(args.source_pool))
            commitment = _load_json_file(
                Path(args.commitment),
                label="CSS-distance suite commitment",
            )
            private_root = (
                Path(args.work_root) / "private" / "css-distance-paper-suite"
            )
            summary = verify_suite_commitment(
                private_root=private_root,
                commitment=commitment,
            )
            print(
                f"status={summary['status']} "
                f"development={summary['development']} "
                f"final={summary['final']} "
                f"time_limit_seconds={TIME_LIMIT_SECONDS} "
                f"minimum_seeds={MINIMUM_SEEDS}"
            )
            return 0

        if args.command == "freeze-css-distance-paper-candidate":
            freeze = create_candidate_freeze(
                candidate_worktree=Path(args.candidate_worktree),
                candidate_path=Path(args.candidate),
                image_digest=args.image_digest,
                method_config=_load_json_file(
                    Path(args.method_config),
                    label="CSS-distance method config",
                ),
                seed_manifest=_load_json_file(
                    Path(args.seeds),
                    label="CSS-distance seed manifest",
                ),
                development_summary=_load_json_file(
                    Path(args.development_summary),
                    label="CSS-distance development summary",
                ),
                suite_commitment=_load_json_file(
                    Path(args.commitment),
                    label="CSS-distance suite commitment",
                ),
                created_at=args.created_at,
            )
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(freeze, sort_keys=True, indent=2) + "\n")
            print(
                "froze CSS-distance paper candidate "
                f"time_limit_seconds={freeze['time_limit_seconds']}"
            )
            return 0

        if args.command == "attach-quantum-tanner-witnesses":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            witness_dir = Path(args.witness_dir)
            summary_out = (
                Path(args.summary_out)
                if args.summary_out is not None
                else witness_dir / "witness_finder_summary.json"
            )
            summary = attach_quantum_tanner_witnesses(
                root,
                campaign_id=args.campaign,
                search_space_path=Path(args.search_space) if args.search_space else None,
                fixture_catalog_path=Path(args.fixture_catalog),
                witness_dir=witness_dir,
                basis=args.basis,
                qec_code_bin=args.qec_code_bin,
                iterations=args.iterations,
                restarts=args.restarts,
                seed=args.seed,
                target_weight=args.target_weight,
                timeout_seconds=args.timeout_seconds,
                force=args.force,
                out_search_space_path=(
                    Path(args.out_search_space) if args.out_search_space is not None else None
                ),
                summary_path=summary_out,
            )
            print(_render_attach_quantum_tanner_witnesses_summary(summary), end="")
            counts = summary["counts"]
            if (args.require_all or args.fail_on_skipped) and (
                counts["skipped"] > 0 or counts["failed"] > 0
            ):
                return 1
            return 0

        if args.command == "complete-quantum-tanner-proposal-observables":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            summary = complete_quantum_tanner_proposal_observables(
                root,
                Path(args.search_space),
                basis=args.basis,
                qec_code_bin=args.qec_code_bin,
                force=args.force,
            )
            print(
                f"completed={summary.completed} "
                f"skipped={summary.skipped} "
                f"search_space={summary.search_space_path}"
            )
            for completion in summary.completions:
                print(f"- {completion.candidate_id}: {completion.observables_path}")
            return 0

        if args.command == "preflight":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            report = run_preflight(root)
            print(render_preflight_table(report), end="")
            if args.html is not None:
                write_preflight_html(report, Path(args.html))
            return 0 if report.is_all_green else 1

        if args.command == "init-run":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = init_placeholder_run(
                root,
                args.campaign,
                args.run_id,
                timestamp=args.timestamp,
                force=args.force,
            )
            print(f"initialized placeholder run at {run_root}")
            return 0

        if args.command == "eval":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            result = evaluate_single_candidate(
                root,
                campaign_id=args.campaign,
                distance=args.distance,
                candidate_dir=Path(args.candidate) if args.candidate else None,
                run_id=args.run_id,
                decoder_filter=args.decoder,
                p_filter=args.p,
                general_css=args.general_css,
                force=args.force,
                distance_method_options=normalize_distance_method_options(
                    method=args.distance_method,
                    qec_code_bin=args.qec_code_bin,
                ),
            )
            print(render_eval_success(result.candidate_id, result.run_root), end="")
            return 0

        if args.command == "run":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = run_autoresearch(
                root,
                campaign_id=args.campaign,
                wall_clock=args.wall_clock,
                seed=args.seed,
                run_id=args.run_id,
                resume=args.resume,
                cleanup_worktree=args.cleanup_worktree,
                allow_dirty_root=args.allow_dirty_root,
                distance_method=args.distance_method,
                qec_code_bin=args.qec_code_bin,
            )
            branch = f"autoresearch/{run_root.name}"
            if args.cleanup_worktree:
                print(
                    f"completed autoresearch run on {branch}; "
                    "worktree removed after final commit"
                )
            else:
                print(f"completed autoresearch run on {branch} at {run_root}")
            return 0

        if args.command == "show":
            run_root = Path(args.run)
            if not run_root.exists():
                parser.error(f"run root does not exist: {run_root}")
            repo_root = _repo_root_from_run(run_root)
            schema_root = repo_root / "benchmarks" / "schemas"
            campaign_validator = _validator(schema_root / "campaign.schema.json")
            search_space_validator = _validator(schema_root / "search-space.schema.json")
            task_validator = _validator(schema_root / "benchmark-task.schema.json")
            decoder_validator = _validator(schema_root / "decoder-config.schema.json")
            suite_validator = _validator(schema_root / "benchmark-suite.schema.json")
            run_spec_validator = _validator(schema_root / "run-spec.schema.json")
            candidate_validator = _validator(schema_root / "candidate.schema.json")
            manifest_validator = _validator(schema_root / "result-manifest.schema.json")

            campaigns, _ = _load_campaigns(
                repo_root, campaign_validator, search_space_validator
            )
            tasks = _load_indexed_directory(repo_root, "tasks", task_validator)
            decoders = _load_indexed_directory(repo_root, "decoders", decoder_validator)
            suites = _load_indexed_directory(repo_root, "suites", suite_validator)

            for campaign_id, campaign in campaigns.items():
                if campaign["default_suite_id"] not in suites:
                    raise SearchIntegrityError(
                        f"unknown default_suite_id on {campaign_id}: "
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

            loaded_run = load_search_run(
                run_root,
                run_spec_validator=run_spec_validator,
                candidate_validator=candidate_validator,
                manifest_validator=manifest_validator,
                campaigns=campaigns,
                suites=suites,
            )
            placeholder_count = sum(
                1
                for candidate in loaded_run.candidates.values()
                for manifest in candidate.manifests.values()
                if manifest["status"] == "placeholder"
            )
            print(render_run_overview(loaded_run.payload, placeholder_count), end="")
            return 0

        if args.command == "report":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = Path(args.run)
            if not run_root.is_absolute():
                run_root = root / run_root
            if not run_root.exists():
                parser.error(f"run root does not exist: {run_root}")
            output_path = write_report_html(
                root,
                run_root,
                Path(args.out) if args.out is not None else None,
            )
            print(f"wrote search report to {output_path}")
            return 0

        if args.command == "summarize-quantum-tanner-ai-feedback":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = Path(args.run)
            if not run_root.is_absolute():
                run_root = root / run_root
            model = build_quantum_tanner_ai_feedback(
                root,
                run_root,
                proposal_summary_path=(
                    Path(args.proposal_summary)
                    if args.proposal_summary is not None
                    else None
                ),
                surface_copy_path=(
                    Path(args.surface_copy) if args.surface_copy is not None else None
                ),
            )
            written = write_quantum_tanner_ai_feedback(
                model,
                out_json=Path(args.out_json),
                out_html=Path(args.out_html),
            )
            print(
                "wrote quantum Tanner AI feedback to "
                f"{written['json']} and {written['html']}"
            )
            return 0

        if args.command == "promote":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = Path(args.run)
            if not run_root.is_absolute():
                run_root = root / run_root
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

        if args.command == "reference-check":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            run_root = Path(args.run)
            if not run_root.is_absolute():
                run_root = root / run_root
            fixture_path = Path(args.fixture)
            if not fixture_path.is_absolute():
                fixture_path = root / fixture_path
            output_path = Path(args.out) if args.out is not None else None
            written = write_reference_check(run_root, fixture_path, output_path)
            payload = json.loads(written.read_text())
            print(f"reference check {payload['status']} written to {written}")
            return 0 if payload["status"] == "pass" else 1

        if args.command == "compare-strategies":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            schema_root = root / "benchmarks" / "schemas"
            campaigns, search_spaces = _load_campaigns(
                root,
                _validator(schema_root / "campaign.schema.json"),
                _validator(schema_root / "search-space.schema.json"),
            )
            if args.campaign not in search_spaces:
                raise SearchIntegrityError(
                    f"unknown search space campaign_id: {args.campaign}"
                )
            campaign = campaigns[args.campaign]
            seed = choose_seed(args.seed, campaign)
            metrics_path = Path(args.metrics)
            if not metrics_path.is_absolute():
                metrics_path = root / metrics_path
            metrics = json.loads(metrics_path.read_text())
            if not isinstance(metrics, dict):
                raise SearchIntegrityError(
                    f"strategy metrics must be an object: {metrics_path}"
                )
            model = compare_strategies(
                campaign_id=args.campaign,
                search_space=search_spaces[args.campaign],
                metrics=metrics,
                strategy_names=args.strategies,
                budget_candidates=args.budget_candidates,
                seed=seed,
            )
            written = write_strategy_comparison(model, Path(args.out))
            if not model["assertion"]["passed"]:
                raise SearchIntegrityError("adaptive strategy did not beat grid")
            print(f"wrote strategy comparison to {written['html']}")
            return 0

        if args.command == "compare-candidates":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            model = compare_candidate_runs(
                root,
                [Path(run_path) for run_path in args.run],
                labels=args.label,
            )
            written = write_compare_candidates(model, Path(args.out))
            print(f"wrote candidate comparison to {written['html']}")
            return 0

        if args.command == "compare-surface-copy":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            model = compare_surface_copy(
                root,
                Path(args.run),
                Path(args.baseline),
            )
            written = write_surface_copy_comparison(model, Path(args.out))
            print(f"wrote surface copy comparison to {written['html']}")
            return 0

        if args.command == "find-upper-bound-witness":
            hx_path = Path(args.hx)
            hz_path = Path(args.hz)
            out_path = Path(args.out)
            provenance_path = (
                Path(args.provenance_out)
                if args.provenance_out is not None
                else _default_provenance_path(out_path)
            )
            if provenance_path.resolve() == out_path.resolve():
                raise SearchIntegrityError(
                    "provenance output path must be distinct from witness output path"
                )
            hx_payload = _load_json_file(hx_path, label="hx")
            hz_payload = _load_json_file(hz_path, label="hz")
            result = run_qec_code_random_window_upper_bound_css_witness(
                hx_path,
                hz_path,
                hx_payload=hx_payload,
                hz_payload=hz_payload,
                qec_code_bin=args.qec_code_bin,
                iterations=args.iterations,
                restarts=args.restarts,
                seed=args.seed,
                target_weight=args.target_weight,
                timeout_seconds=args.timeout_seconds,
            )
            witness_payload = result["witness_payload"]
            found_basis = witness_payload["basis"]
            if found_basis != args.basis:
                raise SearchIntegrityError(
                    "incompatible witness basis: "
                    f"requested {args.basis}, found {found_basis}"
                )
            distance_payload = result["distance_payload"]
            provenance = {
                "basis_requested": args.basis,
                "distance_payload": distance_payload,
                "hx": str(hx_path),
                "hz": str(hz_path),
                "iterations": args.iterations,
                "provenance_path": str(provenance_path),
                "qec_code_bin": args.qec_code_bin,
                "qec_code_result": result["qec_code_result"],
                "restarts": args.restarts,
                "seed": args.seed,
                "target_weight": args.target_weight,
                "timeout_seconds": args.timeout_seconds,
                "verification": result["verification"],
                "witness_path": str(out_path),
            }
            _atomic_write_witness_with_provenance(
                out_path,
                witness_payload,
                provenance_path,
                provenance,
            )
            print(
                "found upper-bound witness: "
                f"basis={found_basis} "
                f"weight={distance_payload['upper_bound']} "
                f"method={distance_payload['method']} "
                f"out={out_path}"
            )
            print(f"wrote provenance: {provenance_path}")
            return 0

        if args.command == "find-quotient-coset-upper-bound":
            hx_path = Path(args.hx)
            hz_path = Path(args.hz)
            out_path = Path(args.out)
            provenance_path = (
                Path(args.provenance_out)
                if args.provenance_out is not None
                else _default_provenance_path(out_path)
            )
            if provenance_path.resolve() == out_path.resolve():
                raise SearchIntegrityError(
                    "provenance output path must be distinct from witness output path"
                )
            hx_payload = _load_json_file(hx_path, label="hx")
            hz_payload = _load_json_file(hz_path, label="hz")
            result = find_quotient_coset_upper_bound(
                hx_payload,
                hz_payload,
                basis=args.basis,
                seed=args.seed,
                max_no_improvement=args.max_no_improvement,
                timeout_seconds=args.timeout_seconds,
            )
            provenance = dict(result["provenance"])
            provenance.update(
                {
                    "basis_found": result["basis"],
                    "distance_payload": result["distance_payload"],
                    "hx": str(hx_path),
                    "hz": str(hz_path),
                    "provenance_path": str(provenance_path),
                    "verification": result["verification"],
                    "witness_path": str(out_path),
                }
            )
            _atomic_write_witness_with_provenance(
                out_path,
                result["witness_payload"],
                provenance_path,
                provenance,
            )
            print(
                "found quotient-coset upper-bound witness: "
                f"basis={result['basis']} "
                f"weight={result['upper_bound']} "
                f"method={result['method']} "
                f"out={out_path}"
            )
            print(f"wrote provenance: {provenance_path}")
            return 0

        if args.command == "verify-witness":
            result = verify_css_upper_bound_witness(
                json.loads(Path(args.hx).read_text()),
                json.loads(Path(args.hz).read_text()),
                json.loads(Path(args.witness).read_text()),
            )
            print(json.dumps(result, sort_keys=True))
            return 0 if result["status"] == "pass" else 1

    except (
        SearchIntegrityError,
        CssDistanceEvalError,
        CssDistanceContainerError,
        QuantumTannerProposalValidationError,
        FileNotFoundError,
        json.JSONDecodeError,
        ValidationError,
        SchemaError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

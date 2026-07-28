from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from autoqec_search.eval_candidates import (
    CandidateInput,
    ResolvedCandidate,
    candidate_payload,
    copy_candidate_artifacts,
    resolve_campaign_candidate,
    resolve_campaign_candidate_spec,
    resolve_directory_candidate,
)
from autoqec_search.load import SearchIntegrityError, load_search_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _row_mask(row: list[int]) -> int:
    mask = 0
    for index, value in enumerate(row):
        if value:
            mask |= 1 << index
    return mask


def _sparse_row_mask(columns: list[int]) -> int:
    mask = 0
    for column in columns:
        mask |= 1 << column
    return mask


def _gf2_rank(rows: list[int]) -> int:
    pivots: dict[int, int] = {}
    for row in rows:
        value = row
        while value:
            pivot = value.bit_length() - 1
            existing = pivots.get(pivot)
            if existing is None:
                pivots[pivot] = value
                break
            value ^= existing
    return len(pivots)


def _make_directory_candidate(tmp_path: Path) -> Path:
    source = tmp_path / "source-candidate"
    artifacts = source / "artifacts"
    artifacts.mkdir(parents=True)
    zoo_instance_root = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    for name in ("instance.json", "hx.json", "hz.json"):
        shutil.copyfile(zoo_instance_root / name, artifacts / name)
    _write_json(
        source / "candidate.json",
        {
            "candidate_id": "external-d3",
            "campaign_id": "rotated-surface-baseline",
            "run_id": "source-run",
            "code_family": "rotated-surface-code",
            "parameters": {"distance": 3, "layout": "rotated"},
            "provenance": {"kind": "external", "label": "tmp"},
            "status": "evaluated",
        },
    )
    return source


def _make_repo_with_campaign_candidate_distance(
    tmp_path: Path,
    candidate_distance,
    *,
    artifact_distance: int,
) -> Path:
    root = tmp_path / "repo"
    campaign_root = root / "campaigns" / "examples" / "rotated-surface-baseline"
    campaign_root.mkdir(parents=True)
    (root / "results" / "search").mkdir(parents=True)
    shutil.copyfile(
        REPO_ROOT / "campaigns" / "examples" / "rotated-surface-baseline" / "campaign.json",
        campaign_root / "campaign.json",
    )
    shutil.copyfile(
        REPO_ROOT
        / "campaigns"
        / "examples"
        / "rotated-surface-baseline"
        / "search_space.json",
        campaign_root / "search_space.json",
    )
    search_space_path = campaign_root / "search_space.json"
    search_space = _load_json(search_space_path)
    search_space["candidate_specs"][0]["parameters"]["distance"] = candidate_distance
    _write_json(search_space_path, search_space)

    for subdir in ("tasks", "decoders", "suites", "schemas"):
        shutil.copytree(
            REPO_ROOT / "benchmarks" / subdir,
            root / "benchmarks" / subdir,
        )

    instance_root = (
        root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    instance_root.mkdir(parents=True)
    source_instance_root = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    for name in ("instance.json", "hx.json", "hz.json"):
        shutil.copyfile(source_instance_root / name, instance_root / name)
    instance_path = instance_root / "instance.json"
    instance = _load_json(instance_path)
    instance["parameters"]["distance"] = artifact_distance
    instance["derived_properties"]["distance"] = artifact_distance
    _write_json(instance_path, instance)
    return root


def test_resolve_campaign_candidate_reuses_zoo_rotated_d3() -> None:
    workspace = load_search_workspace(REPO_ROOT)

    candidate = resolve_campaign_candidate(
        REPO_ROOT,
        workspace,
        campaign_id="rotated-surface-baseline",
        distance=3,
    )

    assert candidate.spec.candidate_id == "rotated-surface-d3-example"
    assert candidate.spec.code_family == "rotated-surface-code"
    assert candidate.artifact_root.name == "rotated-surface-code-d3"
    assert candidate.instance["derived_properties"]["distance"] == 3


def test_copy_candidate_artifacts_writes_artifacts_and_distance(tmp_path: Path) -> None:
    workspace = load_search_workspace(REPO_ROOT)
    candidate = resolve_campaign_candidate(
        REPO_ROOT,
        workspace,
        campaign_id="rotated-surface-baseline",
        distance=3,
    )
    candidate_root = tmp_path / "candidate"

    copy_candidate_artifacts(candidate, candidate_root)

    assert sorted(path.name for path in (candidate_root / "artifacts").iterdir()) == [
        "hx.json",
        "hz.json",
        "instance.json",
    ]
    distance = _load_json(candidate_root / "distance.json")
    assert distance["distance"] == 3
    assert distance["method"] == "copied-zoo-exact"
    assert distance["bound_type"] == "exact"
    assert distance["source_instance_id"] == "rotated-surface-code-d3"


def test_resolve_directory_candidate_prefers_candidate_artifacts(
    tmp_path: Path,
) -> None:
    source = _make_directory_candidate(tmp_path)
    artifacts = source / "artifacts"

    candidate = resolve_directory_candidate(
        REPO_ROOT,
        source,
        campaign_id="rotated-surface-baseline",
    )

    assert candidate.spec.candidate_id == "external-d3"
    assert candidate.artifact_root == artifacts
    assert candidate.source_kind == "candidate-artifacts"
    assert candidate.instance["derived_properties"]["distance"] == 3


def test_resolve_directory_candidate_rejects_artifact_code_family_mismatch(
    tmp_path: Path,
) -> None:
    source = _make_directory_candidate(tmp_path)
    instance_path = source / "artifacts" / "instance.json"
    instance = _load_json(instance_path)
    instance["code_id"] = "different-code"
    _write_json(instance_path, instance)

    with pytest.raises(SearchIntegrityError, match="candidate artifact code_id mismatch"):
        resolve_directory_candidate(
            REPO_ROOT,
            source,
            campaign_id="rotated-surface-baseline",
        )


def test_resolve_directory_candidate_rejects_artifact_parameters_mismatch(
    tmp_path: Path,
) -> None:
    source = _make_directory_candidate(tmp_path)
    instance_path = source / "artifacts" / "instance.json"
    instance = _load_json(instance_path)
    instance["parameters"] = {"distance": 5, "layout": "rotated"}
    _write_json(instance_path, instance)

    with pytest.raises(SearchIntegrityError, match="candidate artifact parameters mismatch"):
        resolve_directory_candidate(
            REPO_ROOT,
            source,
            campaign_id="rotated-surface-baseline",
        )


def test_resolve_directory_candidate_rejects_artifact_distance_mismatch(
    tmp_path: Path,
) -> None:
    source = _make_directory_candidate(tmp_path)
    instance_path = source / "artifacts" / "instance.json"
    instance = _load_json(instance_path)
    instance["derived_properties"]["distance"] = 5
    _write_json(instance_path, instance)

    with pytest.raises(SearchIntegrityError, match="candidate artifact distance mismatch"):
        resolve_directory_candidate(
            REPO_ROOT,
            source,
            campaign_id="rotated-surface-baseline",
        )


@pytest.mark.parametrize("distance", [True, 3.0])
def test_resolve_directory_candidate_rejects_non_integer_candidate_distance(
    tmp_path: Path,
    distance,
) -> None:
    source = _make_directory_candidate(tmp_path)
    candidate_path = source / "candidate.json"
    payload = _load_json(candidate_path)
    payload["parameters"]["distance"] = distance
    _write_json(candidate_path, payload)

    with pytest.raises(
        SearchIntegrityError,
        match="candidate distance must be a positive integer",
    ):
        resolve_directory_candidate(
            REPO_ROOT,
            source,
            campaign_id="rotated-surface-baseline",
        )


@pytest.mark.parametrize(
    ("candidate_distance", "requested_distance", "artifact_distance"),
    [
        (True, 1, 1),
        (3.0, 3, 3),
    ],
)
def test_resolve_campaign_candidate_rejects_non_integer_candidate_distance(
    tmp_path: Path,
    candidate_distance,
    requested_distance: int,
    artifact_distance: int,
) -> None:
    root = _make_repo_with_campaign_candidate_distance(
        tmp_path,
        candidate_distance,
        artifact_distance=artifact_distance,
    )
    workspace = load_search_workspace(root)

    with pytest.raises(
        SearchIntegrityError,
        match="candidate distance must be a positive integer",
    ):
        resolve_campaign_candidate(
            root,
            workspace,
            campaign_id="rotated-surface-baseline",
            distance=requested_distance,
        )


def test_resolve_directory_candidate_rejects_traversal_artifact_reference(
    tmp_path: Path,
) -> None:
    source = _make_directory_candidate(tmp_path)
    instance_path = source / "artifacts" / "instance.json"
    instance = _load_json(instance_path)
    instance["artifacts"]["hx"] = "../hx.json"
    _write_json(instance_path, instance)

    with pytest.raises(SearchIntegrityError, match="unsupported artifact reference"):
        resolve_directory_candidate(
            REPO_ROOT,
            source,
            campaign_id="rotated-surface-baseline",
        )


def test_resolve_directory_candidate_rejects_absolute_artifact_reference(
    tmp_path: Path,
) -> None:
    source = _make_directory_candidate(tmp_path)
    instance_path = source / "artifacts" / "instance.json"
    instance = _load_json(instance_path)
    instance["artifacts"]["hx"] = str(tmp_path / "hx.json")
    _write_json(instance_path, instance)

    with pytest.raises(SearchIntegrityError, match="unsupported artifact reference"):
        resolve_directory_candidate(
            REPO_ROOT,
            source,
            campaign_id="rotated-surface-baseline",
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop("run_id"),
        lambda payload: payload.__setitem__("candidate_id", 123),
        lambda payload: payload.__setitem__("code_family", 123),
        lambda payload: payload.__setitem__("status", 123),
        lambda payload: payload.__setitem__("status", "unknown"),
    ],
)
def test_resolve_directory_candidate_rejects_invalid_candidate_payload(
    tmp_path: Path,
    mutate,
) -> None:
    source = _make_directory_candidate(tmp_path)
    candidate_path = source / "candidate.json"
    payload = _load_json(candidate_path)
    mutate(payload)
    _write_json(candidate_path, payload)

    with pytest.raises(SearchIntegrityError, match="invalid candidate payload"):
        resolve_directory_candidate(
            REPO_ROOT,
            source,
            campaign_id="rotated-surface-baseline",
        )


def test_missing_recorded_distance_on_matching_zoo_instance_raises(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    campaign_root = root / "campaigns" / "examples" / "rotated-surface-baseline"
    campaign_root.mkdir(parents=True)
    (root / "results" / "search").mkdir(parents=True)
    shutil.copyfile(
        REPO_ROOT / "campaigns" / "examples" / "rotated-surface-baseline" / "campaign.json",
        campaign_root / "campaign.json",
    )
    shutil.copyfile(
        REPO_ROOT
        / "campaigns"
        / "examples"
        / "rotated-surface-baseline"
        / "search_space.json",
        campaign_root / "search_space.json",
    )
    for subdir in ("tasks", "decoders", "suites", "schemas"):
        shutil.copytree(
            REPO_ROOT / "benchmarks" / subdir,
            root / "benchmarks" / subdir,
        )

    instance_root = (
        root
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    instance_root.mkdir(parents=True)
    source_instance_root = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / "rotated-surface-code-d3"
    )
    for name in ("instance.json", "hx.json", "hz.json"):
        shutil.copyfile(source_instance_root / name, instance_root / name)
    instance = _load_json(instance_root / "instance.json")
    instance["derived_properties"].pop("distance")
    (instance_root / "instance.json").write_text(
        json.dumps(instance, indent=2, sort_keys=True) + "\n"
    )

    workspace = load_search_workspace(root)
    with pytest.raises(SearchIntegrityError, match="recorded distance"):
        resolve_campaign_candidate(
            root,
            workspace,
            campaign_id="rotated-surface-baseline",
            distance=3,
        )


def test_resolve_campaign_candidate_spec_reuses_zoo_instance_for_expanded_candidate() -> None:
    workspace = load_search_workspace(REPO_ROOT)
    candidate_spec = workspace.search_spaces["rotated-surface-baseline"]["candidate_specs"][1]

    candidate = resolve_campaign_candidate_spec(
        REPO_ROOT,
        candidate_spec,
        campaign_id="rotated-surface-baseline",
    )

    assert candidate.spec.candidate_id == "rotated-surface-d5-example"
    assert candidate.spec.code_family == "rotated-surface-code"
    assert candidate.spec.parameters == {"distance": 5, "layout": "rotated"}
    assert candidate.artifact_root.name == "rotated-surface-code-d5"


def test_resolve_campaign_candidate_by_distance_uses_first_matching_spec() -> None:
    workspace = load_search_workspace(REPO_ROOT)

    candidate = resolve_campaign_candidate(
        REPO_ROOT,
        workspace,
        campaign_id="rotated-surface-baseline",
        distance=3,
    )

    assert candidate.spec.candidate_id == "rotated-surface-d3-example"


def test_resolve_explicit_instance_candidate_uses_instance_path(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "zoo", root / "zoo")
    spec = {
        "candidate_id": "rotated-surface-code-d3",
        "code_family": "rotated-surface-code",
        "instance_path": "zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3",
        "provenance": {"kind": "zoo-instance", "label": "direct"},
    }

    candidate = resolve_campaign_candidate_spec(
        root,
        spec,
        campaign_id="direct-campaign",
    )

    assert candidate.spec.candidate_id == "rotated-surface-code-d3"
    assert candidate.spec.parameters == {"distance": 3, "layout": "rotated"}
    assert candidate.artifact_root.name == "rotated-surface-code-d3"
    assert candidate.source_kind == "explicit-zoo-instance"


def test_explicit_instance_resolution_rejects_parameter_distance_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    instance_root = (
        root
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    instance_root.mkdir(parents=True)
    source = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    for name in ("instance.json", "hx.json", "hz.json", "observables_x.json"):
        shutil.copyfile(source / name, instance_root / name)
    instance = _load_json(instance_root / "instance.json")
    instance["parameters"]["distance"] = 5
    instance["derived_properties"]["distance"] = 6
    _write_json(instance_root / "instance.json", instance)

    with pytest.raises(SearchIntegrityError, match="instance parameter distance"):
        resolve_campaign_candidate_spec(
            root,
            {
                "candidate_id": "bivariate-bicycle-code-m6-n6",
                "code_family": "bivariate-bicycle-code",
                "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
                "provenance": {"kind": "paper-seed", "label": "BB72"},
            },
            campaign_id="bb72-qldpc-campaign",
        )


@pytest.mark.parametrize("invalid_distance", [6.0, True])
def test_explicit_instance_resolution_rejects_non_integer_parameter_distance(
    tmp_path: Path,
    invalid_distance: object,
) -> None:
    root = tmp_path / "repo"
    instance_root = (
        root
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    instance_root.mkdir(parents=True)
    source = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    for name in ("instance.json", "hx.json", "hz.json", "observables_x.json"):
        shutil.copyfile(source / name, instance_root / name)
    instance = _load_json(instance_root / "instance.json")
    instance["parameters"]["distance"] = invalid_distance
    instance["derived_properties"]["distance"] = 6
    _write_json(instance_root / "instance.json", instance)

    with pytest.raises(
        SearchIntegrityError,
        match="instance parameter distance must be a positive integer",
    ):
        resolve_campaign_candidate_spec(
            root,
            {
                "candidate_id": "bivariate-bicycle-code-m6-n6",
                "code_family": "bivariate-bicycle-code",
                "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
                "provenance": {"kind": "paper-seed", "label": "BB72"},
            },
            campaign_id="bb72-qldpc-campaign",
        )


def test_resolve_explicit_instance_candidate_rejects_symlink_escape(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    outside_instance = tmp_path / "outside-instance"
    outside_instance.mkdir(parents=True)
    _write_json(
        outside_instance / "instance.json",
        {
            "id": "escape",
            "code_id": "rotated-surface-code",
            "family_id": "rotated-surface-code",
            "title": "Escaped Instance",
            "parameters": {"distance": 3, "layout": "rotated"},
            "derived_properties": {"n": 9},
            "artifacts": {"hx": "hx.json", "hz": "hz.json"},
            "provenance": {"source": "test"},
        },
    )
    _write_json(
        outside_instance / "hx.json",
        {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 0, "data": []},
    )
    _write_json(
        outside_instance / "hz.json",
        {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 0, "data": []},
    )
    instances_root = (
        root / "zoo" / "codes" / "rotated-surface-code" / "instances"
    )
    instances_root.mkdir(parents=True)
    (instances_root / "escape").symlink_to(
        outside_instance,
        target_is_directory=True,
    )

    with pytest.raises(SearchIntegrityError, match="instance_path|safe relative path"):
        resolve_campaign_candidate_spec(
            root,
            {
                "candidate_id": "escape",
                "code_family": "rotated-surface-code",
                "instance_path": "zoo/codes/rotated-surface-code/instances/escape",
                "provenance": {"kind": "zoo-instance", "label": "direct"},
            },
            campaign_id="direct-campaign",
        )


@pytest.mark.parametrize(
    "instance_path",
    [
        "/zoo/codes/rotated-surface-code/instances/escape",
        "zoo/codes/rotated-surface-code/instances/../escape",
    ],
)
def test_resolve_explicit_instance_candidate_rejects_unsafe_instance_path(
    tmp_path: Path,
    instance_path: str,
) -> None:
    with pytest.raises(SearchIntegrityError, match="instance_path.*safe relative path"):
        resolve_campaign_candidate_spec(
            tmp_path / "repo",
            {
                "candidate_id": "escape",
                "code_family": "rotated-surface-code",
                "instance_path": instance_path,
                "provenance": {"kind": "zoo-instance", "label": "direct"},
            },
            campaign_id="direct-campaign",
        )


def test_copy_candidate_artifacts_writes_unavailable_distance_for_css_without_distance(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    instance_root = (
        root / "zoo" / "codes" / "bivariate-bicycle-code" / "instances" / "bb-small"
    )
    instance_root.mkdir(parents=True)
    _write_json(
        instance_root / "instance.json",
        {
            "id": "bb-small",
            "code_id": "bivariate-bicycle-code",
            "family_id": "bivariate-bicycle-code",
            "title": "BB Small",
            "parameters": {"m": 6, "n": 6, "vc": [[1, 0]], "hd": [[0, 1]]},
            "derived_properties": {"n": 72, "mx": 36, "mz": 36},
            "artifacts": {"hx": "hx.json", "hz": "hz.json"},
            "provenance": {"source": "test"},
        },
    )
    _write_json(
        instance_root / "hx.json",
        {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 0, "data": []},
    )
    _write_json(
        instance_root / "hz.json",
        {"format": "dense_binary_matrix", "n_rows": 0, "n_cols": 0, "data": []},
    )
    candidate = ResolvedCandidate(
        spec=CandidateInput(
            candidate_id="bb-small",
            campaign_id="direct-campaign",
            code_family="bivariate-bicycle-code",
            parameters={"m": 6, "n": 6, "vc": [[1, 0]], "hd": [[0, 1]]},
            provenance={"kind": "zoo-instance", "label": "direct"},
            instance_path="zoo/codes/bivariate-bicycle-code/instances/bb-small",
        ),
        artifact_root=instance_root,
        instance=_load_json(instance_root / "instance.json"),
        hx=_load_json(instance_root / "hx.json"),
        hz=_load_json(instance_root / "hz.json"),
        source_kind="explicit-zoo-instance",
    )

    copy_candidate_artifacts(candidate, tmp_path / "candidate")

    distance = _load_json(tmp_path / "candidate" / "distance.json")
    assert distance == {
        "status": "unavailable",
        "distance": None,
        "method": "not-recorded-on-zoo-instance",
        "source_instance_id": "bb-small",
        "source_instance_path": str(instance_root),
    }


def test_resolve_explicit_bb72_instance_loads_distance_and_observables() -> None:
    candidate = resolve_campaign_candidate_spec(
        REPO_ROOT,
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "code_family": "bivariate-bicycle-code",
            "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
            "provenance": {
                "kind": "paper-seed",
                "label": "Bravyi et al. BB [[72,12,6]]",
            },
        },
        campaign_id="bb72-qldpc-campaign",
    )

    assert candidate.spec.parameters["distance"] == 6
    assert candidate.spec.parameters["paper"] == {
        "l": 6,
        "m": 6,
        "A": "x^3 + y + y^2",
        "B": "y^3 + x + x^2",
        "paper_ref": "2308.07915",
    }
    assert candidate.instance["derived_properties"]["distance"] == 6
    assert candidate.observables_x is not None
    assert candidate.observables_x["format"] == "sparse_rows"
    assert candidate.observables_x["num_cols"] == 72
    assert len(candidate.observables_x["rows"]) == 12


def test_checked_in_bb72_observables_are_x_logicals() -> None:
    instance_root = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    hx = _load_json(instance_root / "hx.json")["data"]
    hz = _load_json(instance_root / "hz.json")["data"]
    observables_x = _load_json(instance_root / "observables_x.json")
    observable_masks = [
        _sparse_row_mask(row) for row in observables_x["rows"]
    ]

    hz_masks = [_row_mask(row) for row in hz]
    for observable_index, observable in enumerate(observable_masks):
        anticommuting_rows = [
            row_index
            for row_index, hz_row in enumerate(hz_masks)
            if (observable & hz_row).bit_count() % 2
        ]
        assert anticommuting_rows == [], (
            f"observable {observable_index} anticommutes with Hz rows "
            f"{anticommuting_rows}"
        )

    hx_rank = _gf2_rank([_row_mask(row) for row in hx])
    assert _gf2_rank([_row_mask(row) for row in hx] + observable_masks) == (
        hx_rank + len(observable_masks)
    )


def test_copy_candidate_artifacts_preserves_bb72_observables(tmp_path: Path) -> None:
    candidate = resolve_campaign_candidate_spec(
        REPO_ROOT,
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "code_family": "bivariate-bicycle-code",
            "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
            "provenance": {"kind": "paper-seed", "label": "BB72"},
        },
        campaign_id="bb72-qldpc-campaign",
    )

    copy_candidate_artifacts(candidate, tmp_path / "candidate")

    assert sorted(path.name for path in (tmp_path / "candidate" / "artifacts").iterdir()) == [
        "hx.json",
        "hz.json",
        "instance.json",
        "observables_x.json",
    ]
    copied = _load_json(tmp_path / "candidate" / "artifacts" / "observables_x.json")
    assert copied["num_cols"] == 72
    assert len(copied["rows"]) == 12


def test_copy_candidate_artifacts_normalizes_explicit_instance_for_reload(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    instance_root = (
        root
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    instance_root.mkdir(parents=True)
    source = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    for name in ("instance.json", "hx.json", "hz.json", "observables_x.json"):
        shutil.copyfile(source / name, instance_root / name)
    instance = _load_json(instance_root / "instance.json")
    instance["parameters"].pop("distance", None)
    instance["derived_properties"]["distance"] = 6
    _write_json(instance_root / "instance.json", instance)

    candidate = resolve_campaign_candidate_spec(
        root,
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "code_family": "bivariate-bicycle-code",
            "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
            "provenance": {"kind": "paper-seed", "label": "BB72"},
        },
        campaign_id="bb72-qldpc-campaign",
    )

    assert candidate.spec.parameters["distance"] == 6

    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    _write_json(candidate_root / "candidate.json", candidate_payload(candidate, "copied-run"))
    copy_candidate_artifacts(candidate, candidate_root)

    copied_instance = _load_json(candidate_root / "artifacts" / "instance.json")
    assert copied_instance["parameters"]["distance"] == 6

    reloaded = resolve_directory_candidate(
        root,
        candidate_root,
        campaign_id="bb72-qldpc-campaign",
    )

    assert reloaded.spec.parameters["distance"] == 6
    assert reloaded.spec.parameters["paper"]["paper_ref"] == "2308.07915"
    assert reloaded.artifact_root == candidate_root / "artifacts"


def test_resolve_directory_candidate_accepts_nested_bb72_parameters(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-candidate"
    artifacts = source / "artifacts"
    artifacts.mkdir(parents=True)
    zoo_instance_root = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "bivariate-bicycle-code"
        / "instances"
        / "bivariate-bicycle-code-m6-n6"
    )
    for name in ("instance.json", "hx.json", "hz.json", "observables_x.json"):
        shutil.copyfile(zoo_instance_root / name, artifacts / name)
    instance = _load_json(artifacts / "instance.json")
    _write_json(
        source / "candidate.json",
        {
            "candidate_id": "bivariate-bicycle-code-m6-n6",
            "campaign_id": "bb72-qldpc-campaign",
            "run_id": "source-run",
            "code_family": "bivariate-bicycle-code",
            "parameters": instance["parameters"],
            "provenance": {"kind": "paper-seed", "label": "BB72"},
            "status": "evaluated",
        },
    )

    candidate = resolve_directory_candidate(
        REPO_ROOT,
        source,
        campaign_id="bb72-qldpc-campaign",
    )

    assert candidate.spec.parameters["distance"] == 6
    assert candidate.spec.parameters["paper"]["paper_ref"] == "2308.07915"
    assert candidate.artifact_root == artifacts

from __future__ import annotations

from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.run_render import FrontierItem
from autoqec_search.run_loop import _selected_candidate_specs
from autoqec_search.strategies import (
    AdaptiveStrategy,
    StrategyProposal,
    StrategyState,
    available_strategies,
    frontier_quality,
    get_strategy,
    normalize_strategy_config,
    with_strategy_provenance,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _candidate(candidate_id: str, distance: int) -> dict:
    return {
        "candidate_id": candidate_id,
        "code_family": "rotated-surface-code",
        "parameters": {"distance": distance, "layout": "rotated"},
        "provenance": {"kind": "seed", "label": candidate_id},
    }


def _candidate_without_distance(candidate_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "code_family": "custom-code",
        "parameters": {"layout": "bespoke"},
        "provenance": {"kind": "seed", "label": candidate_id},
    }


def _state(
    candidate_specs: list[dict],
    *,
    frontier: list[FrontierItem] | None = None,
    attempted_candidate_ids: set[str] | None = None,
    seed: int = 7,
) -> StrategyState:
    return StrategyState(
        candidate_specs=candidate_specs,
        frontier=frontier or [],
        attempted_candidate_ids=attempted_candidate_ids or set(),
        deduped_candidate_ids=set(),
        seed=seed,
        max_candidates=None,
        evaluations_completed=0,
    )


def _frontier_item(candidate_id: str, distance: int, ler: float) -> FrontierItem:
    return FrontierItem(
        candidate_id=candidate_id,
        distance=distance,
        decoder_id="rmatching-default-v1",
        p=0.005,
        ler=ler,
        manifest_path=f"candidates/{candidate_id}/manifest.json",
    )


def test_available_strategies_lists_registry_names() -> None:
    assert available_strategies() == ["adaptive", "grid", "random"]


def test_normalize_strategy_config_defaults_to_grid() -> None:
    assert normalize_strategy_config({}) == {"name": "grid", "params": {}}


def test_normalize_strategy_config_rejects_unknown_strategy() -> None:
    with pytest.raises(SearchIntegrityError, match="unknown search strategy"):
        normalize_strategy_config({"strategy": {"name": "spiral", "params": {}}})


def test_grid_proposes_remaining_specs_in_file_order() -> None:
    specs = [
        _candidate("rotated-surface-d3-example", 3),
        _candidate("rotated-surface-d5-example", 5),
        _candidate("rotated-surface-d7-example", 7),
    ]
    state = _state(
        specs,
        attempted_candidate_ids={"rotated-surface-d3-example"},
    )

    proposals = get_strategy("grid").propose(state)

    assert [proposal.candidate_id for proposal in proposals] == [
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
    ]
    assert [proposal.candidate_spec for proposal in proposals] == [specs[1], specs[2]]
    assert {proposal.strategy for proposal in proposals} == {"grid"}


def test_grid_proposes_schema_valid_candidate_without_distance() -> None:
    specs = [
        _candidate("rotated-surface-d3-example", 3),
        _candidate_without_distance("distance-free-grid-candidate"),
    ]

    proposals = get_strategy("grid").propose(
        _state(specs, attempted_candidate_ids={"rotated-surface-d3-example"})
    )

    assert [proposal.candidate_id for proposal in proposals] == [
        "distance-free-grid-candidate"
    ]
    assert proposals[0].reason == "file-order"


def test_random_proposal_order_is_deterministic_and_contains_all_specs() -> None:
    specs = [
        _candidate("rotated-surface-d3-example", 3),
        _candidate("rotated-surface-d5-example", 5),
        _candidate("rotated-surface-d7-example", 7),
        _candidate("rotated-surface-d9-example", 9),
    ]

    state = _state(
        specs,
        attempted_candidate_ids={"rotated-surface-d3-example"},
        seed=11,
    )

    first_order = [
        proposal.candidate_id for proposal in get_strategy("random").propose(state)
    ]
    second_order = [
        proposal.candidate_id for proposal in get_strategy("random").propose(state)
    ]

    assert second_order == first_order
    assert sorted(first_order) == [
        "rotated-surface-d5-example",
        "rotated-surface-d7-example",
        "rotated-surface-d9-example",
    ]


def test_random_proposes_schema_valid_candidate_without_distance() -> None:
    specs = [
        _candidate_without_distance("distance-free-random-candidate"),
        _candidate("rotated-surface-d3-example", 3),
    ]

    proposals = get_strategy("random").propose(
        _state(specs, attempted_candidate_ids={"rotated-surface-d3-example"}, seed=11)
    )

    assert [proposal.candidate_id for proposal in proposals] == [
        "distance-free-random-candidate"
    ]
    assert proposals[0].reason == "seeded-shuffle:seed11"


@pytest.mark.parametrize("strategy_name", ["adaptive", "grid", "random"])
def test_strategies_return_empty_list_when_exhausted(strategy_name: str) -> None:
    specs = [
        _candidate("rotated-surface-d3-example", 3),
        _candidate("rotated-surface-d5-example", 5),
    ]
    state = _state(
        specs,
        attempted_candidate_ids={
            "rotated-surface-d3-example",
            "rotated-surface-d5-example",
        },
    )

    assert get_strategy(strategy_name).propose(state) == []


def test_adaptive_cold_start_proposes_smallest_distance() -> None:
    specs = [
        _candidate("rotated-surface-d7-example", 7),
        _candidate("rotated-surface-d3-example", 3),
        _candidate("rotated-surface-d5-example", 5),
    ]

    proposals = AdaptiveStrategy().propose(_state(specs))
    proposal = proposals[0]

    assert len(proposals) == 1
    assert proposal.candidate_id == "rotated-surface-d3-example"
    assert "cold-start" in proposal.reason


def test_adaptive_frontier_proposes_next_distance_above_current_frontier() -> None:
    specs = [
        _candidate("rotated-surface-d3-example", 3),
        _candidate("rotated-surface-d5-example", 5),
        _candidate("rotated-surface-d7-example", 7),
    ]
    state = _state(
        specs,
        frontier=[_frontier_item("rotated-surface-d3-example", 3, 0.013)],
        attempted_candidate_ids={"rotated-surface-d3-example"},
    )

    proposals = AdaptiveStrategy().propose(state)
    proposal = proposals[0]

    assert len(proposals) == 1
    assert proposal.candidate_id == "rotated-surface-d5-example"
    assert "next-distance" in proposal.reason


def test_adaptive_prefers_same_distance_improvement_after_next_distance() -> None:
    specs = [
        _candidate("rotated-surface-d3-example", 3),
        _candidate("rotated-surface-d5-example", 5),
        _candidate("rotated-surface-d5-repeat", 5),
    ]
    state = _state(
        specs,
        frontier=[_frontier_item("rotated-surface-d5-example", 5, 0.013)],
        attempted_candidate_ids={"rotated-surface-d5-example"},
    )

    proposal = AdaptiveStrategy().propose(state)[0]

    assert proposal.candidate_id == "rotated-surface-d5-repeat"
    assert "same-distance-improvement" in proposal.reason


def test_adaptive_falls_back_to_any_remaining_when_no_next_or_same_distance() -> None:
    specs = [
        _candidate("rotated-surface-d3-example", 3),
        _candidate("rotated-surface-d4-example", 4),
        _candidate("rotated-surface-d5-example", 5),
    ]
    state = _state(
        specs,
        frontier=[_frontier_item("rotated-surface-d5-example", 5, 0.013)],
        attempted_candidate_ids={"rotated-surface-d5-example"},
    )

    proposal = AdaptiveStrategy().propose(state)[0]

    assert proposal.candidate_id == "rotated-surface-d3-example"
    assert "fallback" in proposal.reason


def test_adaptive_rejects_candidate_without_distance() -> None:
    spec = _candidate_without_distance("distance-free-adaptive-candidate")

    with pytest.raises(SearchIntegrityError, match="distance"):
        AdaptiveStrategy().propose(_state([spec]))


def test_adaptive_accepts_normalized_explicit_instance_spec() -> None:
    workspace = load_search_workspace(REPO_ROOT)
    candidate_spec = _selected_candidate_specs(
        REPO_ROOT,
        workspace,
        "decoder-registry-css-bb-smoke",
        workspace.campaigns["decoder-registry-css-bb-smoke"],
    )[0]
    strategy_spec = with_strategy_provenance(candidate_spec, "adaptive")

    proposal = AdaptiveStrategy().propose(_state([strategy_spec]))[0]

    assert proposal.candidate_id == "bivariate-bicycle-code-m6-n6"
    assert proposal.reason == "cold-start:smallest-distance:d6"
    assert strategy_spec["parameters"]["distance"] == 6


def test_frontier_quality_empty_and_prefers_largest_distance_then_lower_ler() -> None:
    assert frontier_quality([]) == (0, 0.0)
    assert frontier_quality(
        [
            _frontier_item("d3-low", 3, 0.001),
            _frontier_item("d5-high", 5, 0.2),
        ]
    ) == (5, -0.2)
    assert frontier_quality(
        [
            _frontier_item("d5-high", 5, 0.2),
            _frontier_item("d5-low", 5, 0.01),
        ]
    ) == (5, -0.01)


def test_strategy_proposal_candidate_id_validates_spec() -> None:
    proposal = StrategyProposal(
        candidate_spec={"parameters": {"distance": 3}},
        strategy="grid",
        reason="test",
    )

    with pytest.raises(SearchIntegrityError, match="candidate_id"):
        _ = proposal.candidate_id


def test_get_strategy_and_provenance_helpers() -> None:
    strategy = get_strategy("grid")
    spec = _candidate("rotated-surface-d3-example", 3)

    updated = with_strategy_provenance(spec, strategy.name)

    assert strategy.name == "grid"
    assert updated is not spec
    assert updated["provenance"] is not spec["provenance"]
    assert updated["provenance"]["strategy"] == "grid"
    assert "strategy" not in spec["provenance"]


def test_adaptive_candidate_distance_must_be_positive_int() -> None:
    spec = _candidate("rotated-surface-d0-example", 0)

    with pytest.raises(SearchIntegrityError, match="distance"):
        AdaptiveStrategy().propose(_state([spec]))

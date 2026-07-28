from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Protocol

from autoqec_search.load import SearchIntegrityError
from autoqec_search.run_render import FrontierItem


@dataclass(frozen=True)
class StrategyProposal:
    candidate_spec: dict
    strategy: str
    reason: str

    @property
    def candidate_id(self) -> str:
        return _candidate_id(self.candidate_spec)


@dataclass(frozen=True)
class StrategyState:
    candidate_specs: list[dict]
    frontier: list[FrontierItem]
    attempted_candidate_ids: set[str]
    deduped_candidate_ids: set[str]
    seed: int
    max_candidates: int | None
    evaluations_completed: int


class Strategy(Protocol):
    name: str

    def propose(self, state: StrategyState) -> list[StrategyProposal]:
        """Return proposed candidates to evaluate, or an empty list when exhausted."""


@dataclass(frozen=True)
class GridStrategy:
    name: str = "grid"

    def propose(self, state: StrategyState) -> list[StrategyProposal]:
        remaining = _remaining_specs(state)
        return [
            StrategyProposal(
                candidate_spec=candidate_spec,
                strategy=self.name,
                reason="file-order",
            )
            for candidate_spec in remaining
        ]


@dataclass(frozen=True)
class RandomStrategy:
    name: str = "random"

    def propose(self, state: StrategyState) -> list[StrategyProposal]:
        remaining = _remaining_specs(state)
        random.Random(state.seed).shuffle(remaining)
        return [
            StrategyProposal(
                candidate_spec=candidate_spec,
                strategy=self.name,
                reason=f"seeded-shuffle:seed{state.seed}",
            )
            for candidate_spec in remaining
        ]


@dataclass(frozen=True)
class AdaptiveStrategy:
    name: str = "adaptive"

    def propose(self, state: StrategyState) -> list[StrategyProposal]:
        remaining = _remaining_specs(state)
        if not remaining:
            return []
        if not state.frontier:
            candidate_spec = min(remaining, key=_distance_then_id)
            distance = _candidate_distance(candidate_spec)
            return [
                StrategyProposal(
                    candidate_spec=candidate_spec,
                    strategy=self.name,
                    reason=f"cold-start:smallest-distance:d{distance}",
                )
            ]

        current_max_distance = max(item.distance for item in state.frontier)
        next_distance_specs = [
            spec
            for spec in remaining
            if _candidate_distance(spec) > current_max_distance
        ]
        if next_distance_specs:
            candidate_spec = min(next_distance_specs, key=_distance_then_id)
            distance = _candidate_distance(candidate_spec)
            return [
                StrategyProposal(
                    candidate_spec=candidate_spec,
                    strategy=self.name,
                    reason=(
                        "next-distance:"
                        f"frontier-d{current_max_distance}:candidate-d{distance}"
                    ),
                )
            ]

        for distance in sorted({item.distance for item in state.frontier}, reverse=True):
            same_distance_specs = [
                spec for spec in remaining if _candidate_distance(spec) == distance
            ]
            if same_distance_specs:
                candidate_spec = min(same_distance_specs, key=_candidate_id)
                return [
                    StrategyProposal(
                        candidate_spec=candidate_spec,
                        strategy=self.name,
                        reason=f"same-distance-improvement:d{distance}",
                    )
                ]

        candidate_spec = min(remaining, key=_distance_then_id)
        distance = _candidate_distance(candidate_spec)
        return [
            StrategyProposal(
                candidate_spec=candidate_spec,
                strategy=self.name,
                reason=f"fallback:any-remaining:d{distance}",
            )
        ]


def available_strategies() -> list[str]:
    return sorted(_STRATEGIES)


def get_strategy(name: str) -> Strategy:
    if name not in _STRATEGIES:
        raise SearchIntegrityError(
            f"unknown search strategy: {name}; "
            f"available strategies: {', '.join(available_strategies())}"
        )
    return _STRATEGIES[name]


def normalize_strategy_config(search_space: dict) -> dict:
    raw_strategy = search_space.get("strategy", "grid")
    if isinstance(raw_strategy, str):
        name = raw_strategy
        params = {}
    elif isinstance(raw_strategy, dict):
        name = raw_strategy.get("name", "grid")
        params = raw_strategy.get("params", {})
    else:
        raise SearchIntegrityError("strategy must be a string or object")

    if not isinstance(name, str) or not name:
        raise SearchIntegrityError("strategy name must be a non-empty string")
    get_strategy(name)
    if not isinstance(params, dict):
        raise SearchIntegrityError(f"strategy params must be an object for {name}")
    return {"name": name, "params": dict(params)}


def with_strategy_provenance(candidate_spec: dict, strategy: str) -> dict:
    get_strategy(strategy)
    updated = dict(candidate_spec)
    provenance = dict(candidate_spec.get("provenance", {}))
    provenance["strategy"] = strategy
    updated["provenance"] = provenance
    return updated


def frontier_quality(frontier: list[FrontierItem]) -> tuple[int, float]:
    if not frontier:
        return (0, 0.0)
    return max((item.distance, -item.ler) for item in frontier)


def _candidate_id(candidate_spec: dict) -> str:
    candidate_id = candidate_spec.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise SearchIntegrityError("candidate spec has invalid candidate_id")
    return candidate_id


def _candidate_distance(candidate_spec: dict) -> int:
    candidate_id = _candidate_id(candidate_spec)
    parameters = candidate_spec.get("parameters")
    if not isinstance(parameters, dict):
        raise SearchIntegrityError(f"candidate {candidate_id} missing parameters")
    distance = parameters.get("distance")
    if type(distance) is not int or distance < 1:
        raise SearchIntegrityError(
            f"candidate {candidate_id} has invalid positive integer distance"
        )
    return distance


def _distance_then_id(candidate_spec: dict) -> tuple[int, str]:
    return (_candidate_distance(candidate_spec), _candidate_id(candidate_spec))


def _remaining_specs(state: StrategyState) -> list[dict]:
    attempted_candidate_ids = set(state.attempted_candidate_ids)
    return [
        spec
        for spec in state.candidate_specs
        if _candidate_id(spec) not in attempted_candidate_ids
    ]


_STRATEGIES: dict[str, Strategy] = {
    "adaptive": AdaptiveStrategy(),
    "grid": GridStrategy(),
    "random": RandomStrategy(),
}


__all__ = [
    "AdaptiveStrategy",
    "GridStrategy",
    "RandomStrategy",
    "Strategy",
    "StrategyProposal",
    "StrategyState",
    "available_strategies",
    "frontier_quality",
    "get_strategy",
    "normalize_strategy_config",
    "with_strategy_provenance",
]

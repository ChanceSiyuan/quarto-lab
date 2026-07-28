# Issue 14 Search Strategy Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add selectable grid, random, and adaptive search strategies to `autoqec-search run`, plus a `compare-strategies` verification command with durable strategy artifacts.

**Architecture:** Keep candidate evaluation unchanged and put proposal policy in a new `autoqec_search.strategies` module. The run loop asks a strategy for candidate proposals, owns de-duplication and trace output, and records selected strategy metadata in run artifacts. A separate `autoqec_search.strategy_compare` module simulates strategy order from candidate metrics and renders `strategies.json`, `strategies.svg`, and `strategies.html`.

**Tech Stack:** Python 3.11, dataclasses, stdlib JSON/HTML/SVG rendering, existing `jsonschema` validation, pytest, existing fake-`rsinter` CLI tests.

---

## File Structure

- Create `src/autoqec_search/strategies.py`: strategy config/state/proposal dataclasses, registry, grid/random/adaptive implementations, proposal de-duplication helpers.
- Create `src/autoqec_search/strategy_compare.py`: loads candidate metrics, simulates strategies, computes frontier quality, renders JSON/SVG/HTML, returns assertion status for CLI.
- Create `tests/test_search_strategies.py`: unit tests for strategy normalization, registry, deterministic proposal order, adaptive behavior, and duplicate/exhausted helpers.
- Create `tests/test_search_strategy_compare.py`: focused tests for compare model and renderers.
- Modify `benchmarks/schemas/search-space.schema.json`: allow optional `strategy`.
- Modify `benchmarks/schemas/candidate.schema.json`: allow optional `provenance.strategy`.
- Modify `benchmarks/schemas/run-spec.schema.json`: allow optional `strategy`.
- Modify `src/autoqec_search/load.py`: normalize or validate new run status and strategy-trace requirements without breaking committed M1 runs.
- Modify `src/autoqec_search/run_render.py`: render strategy metadata and stop reason in markdown and HTML summaries.
- Modify `src/autoqec_search/run_loop.py`: replace fixed list iteration with strategy proposals; write `strategy_trace.json`; fill `provenance.strategy`; write stop reasons.
- Modify `src/autoqec_search/cli.py`: add `compare-strategies` parser and handler.
- Create `campaigns/examples/rotated-surface-strategy-fixture/campaign.json`: small comparison campaign.
- Create `campaigns/examples/rotated-surface-strategy-fixture/search_space.json`: explicit candidates ordered so grid spends budget poorly and adaptive wins.
- Create `benchmarks/fixtures/strategy-comparison/rotated-surface.json`: deterministic distance/LER metrics for comparison tests.
- Modify `README.md`, `CLAUDE.md`, and `tests/test_search_docs.py`: document strategy selection, trace output, and compare command.

## Task 1: Strategy Schema And Loader Contracts

**Files:**
- Modify: `benchmarks/schemas/search-space.schema.json`
- Modify: `benchmarks/schemas/candidate.schema.json`
- Modify: `benchmarks/schemas/run-spec.schema.json`
- Modify: `src/autoqec_search/load.py:59-127`
- Test: `tests/test_search_load.py`

- [ ] **Step 1: Add failing loader/schema tests**

Append these tests to `tests/test_search_load.py`:

```python
def test_search_space_accepts_strategy_config(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)
    search_space_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "search_space.json"
    )
    payload = json.loads(search_space_path.read_text())
    payload["strategy"] = {"name": "adaptive", "params": {}}
    search_space_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    workspace = load_search_workspace(work_root)

    assert workspace.search_spaces["rotated-surface-baseline"]["strategy"] == {
        "name": "adaptive",
        "params": {},
    }


def test_search_space_rejects_unknown_strategy_name(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)
    search_space_path = (
        work_root / "campaigns" / "examples" / "rotated-surface-baseline" / "search_space.json"
    )
    payload = json.loads(search_space_path.read_text())
    payload["strategy"] = {"name": "mystery", "params": {}}
    search_space_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    with pytest.raises(Exception, match="mystery"):
        load_search_workspace(work_root)


def test_candidate_provenance_accepts_strategy_field(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)
    candidate_path = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "candidates"
        / "rotated-surface-d3-example"
        / "candidate.json"
    )
    payload = json.loads(candidate_path.read_text())
    payload["provenance"]["strategy"] = "grid"
    candidate_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    workspace = load_search_workspace(work_root)

    loaded = workspace.runs[
        "rotated-surface-baseline/2026-06-09-example"
    ].candidates["rotated-surface-d3-example"]
    assert loaded.payload["provenance"]["strategy"] == "grid"


def test_new_autoresearch_run_status_requires_stop_reason(tmp_path: Path) -> None:
    work_root = _copy_search_workspace(tmp_path)
    run_root = _make_example_run_autoresearch(work_root)
    run_spec_path = run_root / "run_spec.json"
    run_spec = json.loads(run_spec_path.read_text())
    run_spec["strategy"] = {"name": "grid", "params": {}}
    run_spec_path.write_text(json.dumps(run_spec, indent=2, sort_keys=True) + "\n")
    strategy_trace = {
        "campaign_id": run_spec["campaign_id"],
        "run_id": run_spec["run_id"],
        "strategy": {"name": "grid", "params": {}},
        "events": [],
    }
    (run_root / "strategy_trace.json").write_text(
        json.dumps(strategy_trace, indent=2, sort_keys=True) + "\n"
    )

    with pytest.raises(SearchIntegrityError, match="stop_reason"):
        load_search_workspace(work_root)
```

- [ ] **Step 2: Run the focused failing tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_load.py::test_search_space_accepts_strategy_config tests/test_search_load.py::test_search_space_rejects_unknown_strategy_name tests/test_search_load.py::test_candidate_provenance_accepts_strategy_field tests/test_search_load.py::test_new_autoresearch_run_status_requires_stop_reason -q
```

Expected: at least the strategy and provenance tests fail because schemas currently reject the new fields.

- [ ] **Step 3: Update schemas**

Change `benchmarks/schemas/search-space.schema.json` so top-level `required` stays `["campaign_id", "mode", "candidate_specs"]`, but `properties` includes:

```json
"strategy": {
  "type": "object",
  "additionalProperties": false,
  "required": ["name"],
  "properties": {
    "name": { "enum": ["grid", "random", "adaptive"] },
    "params": {
      "type": "object",
      "additionalProperties": {
        "anyOf": [
          { "type": "string" },
          { "type": "integer" },
          { "type": "number" },
          { "type": "boolean" },
          { "type": "null" }
        ]
      }
    }
  }
}
```

In both provenance schemas, replace:

```json
"provenance": {
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "label"],
  "properties": {
    "kind": { "type": "string", "minLength": 1 },
    "label": { "type": "string", "minLength": 1 }
  }
}
```

with:

```json
"provenance": {
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "label"],
  "properties": {
    "kind": { "type": "string", "minLength": 1 },
    "label": { "type": "string", "minLength": 1 },
    "strategy": { "enum": ["grid", "random", "adaptive"] }
  }
}
```

In `benchmarks/schemas/run-spec.schema.json`, add optional:

```json
"strategy": {
  "type": "object",
  "additionalProperties": false,
  "required": ["name", "params"],
  "properties": {
    "name": { "enum": ["grid", "random", "adaptive"] },
    "params": {
      "type": "object",
      "additionalProperties": {
        "anyOf": [
          { "type": "string" },
          { "type": "integer" },
          { "type": "number" },
          { "type": "boolean" },
          { "type": "null" }
        ]
      }
    }
  }
}
```

- [ ] **Step 4: Update loader run-status compatibility**

In `src/autoqec_search/load.py`, update `_validate_autoresearch_metadata()` so `run_status` can have old keys for runs without `payload["strategy"]`, and must have `stop_reason` for new strategy-aware runs:

```python
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
```

Then after `frontier_size` validation, add:

```python
    if has_strategy:
        stop_reason = run_status.get("stop_reason")
        allowed = {"max-candidates", "wall-clock", "search-space-exhausted", "completed"}
        if stop_reason not in allowed:
            raise SearchIntegrityError(
                f"run_status stop_reason is invalid for {run_status_path}"
            )
```

- [ ] **Step 5: Run schema/loader tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_load.py -q
```

Expected: all tests in `tests/test_search_load.py` pass.

- [ ] **Step 6: Commit schema contract changes**

Run:

```bash
git add benchmarks/schemas/search-space.schema.json benchmarks/schemas/candidate.schema.json benchmarks/schemas/run-spec.schema.json src/autoqec_search/load.py tests/test_search_load.py
git commit -m "feat: extend search schemas for strategies"
```

## Task 2: Strategy Registry Unit

**Files:**
- Create: `src/autoqec_search/strategies.py`
- Create: `tests/test_search_strategies.py`

- [ ] **Step 1: Write failing strategy tests**

Create `tests/test_search_strategies.py`:

```python
from __future__ import annotations

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.run_render import FrontierItem
from autoqec_search.strategies import (
    StrategyState,
    available_strategies,
    frontier_quality,
    get_strategy,
    normalize_strategy_config,
)


def _candidate(candidate_id: str, distance: int) -> dict:
    return {
        "candidate_id": candidate_id,
        "code_family": "rotated-surface-code",
        "parameters": {"distance": distance, "layout": "rotated"},
        "provenance": {"kind": "seed", "label": candidate_id},
    }


def _state(
    *,
    frontier: list[FrontierItem] | None = None,
    attempted: set[str] | None = None,
    seed: int = 7,
) -> StrategyState:
    return StrategyState(
        candidate_specs=[
            _candidate("d3-poor-a", 3),
            _candidate("d3-poor-b", 3),
            _candidate("d5-good", 5),
            _candidate("d7-good", 7),
        ],
        frontier=frontier or [],
        attempted_candidate_ids=attempted or set(),
        deduped_candidate_ids=set(),
        seed=seed,
        max_candidates=4,
        evaluations_completed=0,
    )


def test_available_strategies_lists_public_names() -> None:
    assert available_strategies() == ["adaptive", "grid", "random"]


def test_normalize_strategy_config_defaults_to_grid() -> None:
    assert normalize_strategy_config({}) == {"name": "grid", "params": {}}


def test_normalize_strategy_config_rejects_unknown_name() -> None:
    with pytest.raises(SearchIntegrityError, match="unknown search strategy"):
        normalize_strategy_config({"strategy": {"name": "mystery", "params": {}}})


def test_grid_proposes_file_order() -> None:
    proposals = get_strategy("grid").propose(_state())
    assert [proposal.candidate_id for proposal in proposals] == [
        "d3-poor-a",
        "d3-poor-b",
        "d5-good",
        "d7-good",
    ]


def test_random_is_deterministic_for_seed() -> None:
    first = get_strategy("random").propose(_state(seed=123))
    second = get_strategy("random").propose(_state(seed=123))
    assert [proposal.candidate_id for proposal in first] == [
        proposal.candidate_id for proposal in second
    ]
    assert sorted(proposal.candidate_id for proposal in first) == [
        "d3-poor-a",
        "d3-poor-b",
        "d5-good",
        "d7-good",
    ]


def test_adaptive_cold_start_proposes_smallest_distance() -> None:
    proposals = get_strategy("adaptive").propose(_state())
    assert proposals[0].candidate_id == "d3-poor-a"
    assert "cold-start" in proposals[0].reason


def test_adaptive_moves_to_next_distance_after_frontier() -> None:
    frontier = [
        FrontierItem(
            candidate_id="d3-poor-a",
            distance=3,
            decoder_id="rmatching-default-v1",
            p=0.005,
            ler=0.03,
            manifest_path="candidates/d3-poor-a/manifest.json",
        )
    ]
    proposals = get_strategy("adaptive").propose(
        _state(frontier=frontier, attempted={"d3-poor-a"})
    )
    assert proposals[0].candidate_id == "d5-good"
    assert "next-distance" in proposals[0].reason


def test_frontier_quality_prefers_larger_distance_then_lower_ler() -> None:
    assert frontier_quality([]) == (0, 0.0)
    assert frontier_quality(
        [
            FrontierItem(
                candidate_id="d3",
                distance=3,
                decoder_id="rmatching-default-v1",
                p=0.005,
                ler=0.03,
                manifest_path="candidates/d3/manifest.json",
            ),
            FrontierItem(
                candidate_id="d5",
                distance=5,
                decoder_id="rmatching-default-v1",
                p=0.005,
                ler=0.02,
                manifest_path="candidates/d5/manifest.json",
            ),
        ]
    ) == (5, -0.02)
```

- [ ] **Step 2: Run tests to verify missing module failure**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_strategies.py -q
```

Expected: import fails because `autoqec_search.strategies` does not exist.

- [ ] **Step 3: Implement `strategies.py`**

Create `src/autoqec_search/strategies.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Protocol

from autoqec_search.load import SearchIntegrityError
from autoqec_search.run_render import FrontierItem


PUBLIC_STRATEGIES = {"grid", "random", "adaptive"}


@dataclass(frozen=True)
class StrategyProposal:
    candidate_spec: dict[str, Any]
    strategy: str
    reason: str

    @property
    def candidate_id(self) -> str:
        value = self.candidate_spec.get("candidate_id")
        if not isinstance(value, str) or not value:
            raise SearchIntegrityError("strategy produced candidate without candidate_id")
        return value


@dataclass(frozen=True)
class StrategyState:
    candidate_specs: list[dict[str, Any]]
    frontier: list[FrontierItem]
    attempted_candidate_ids: set[str]
    deduped_candidate_ids: set[str]
    seed: int
    max_candidates: int
    evaluations_completed: int


class Strategy(Protocol):
    name: str

    def propose(self, state: StrategyState) -> list[StrategyProposal]:
        ...


def _candidate_distance(candidate_spec: dict[str, Any]) -> int:
    parameters = candidate_spec.get("parameters")
    if not isinstance(parameters, dict):
        raise SearchIntegrityError("candidate parameters must be an object")
    distance = parameters.get("distance")
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError("candidate distance must be a positive integer")
    return distance


def _remaining_specs(state: StrategyState) -> list[dict[str, Any]]:
    remaining = []
    for spec in state.candidate_specs:
        candidate_id = spec.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise SearchIntegrityError("candidate_id must be a string")
        if candidate_id in state.attempted_candidate_ids:
            continue
        remaining.append(spec)
    return remaining


def _proposal(strategy: str, candidate_spec: dict[str, Any], reason: str) -> StrategyProposal:
    return StrategyProposal(candidate_spec=candidate_spec, strategy=strategy, reason=reason)


class GridStrategy:
    name = "grid"

    def propose(self, state: StrategyState) -> list[StrategyProposal]:
        return [
            _proposal(self.name, spec, "grid-order")
            for spec in _remaining_specs(state)
        ]


class RandomStrategy:
    name = "random"

    def propose(self, state: StrategyState) -> list[StrategyProposal]:
        remaining = list(_remaining_specs(state))
        rng = random.Random(state.seed)
        rng.shuffle(remaining)
        return [
            _proposal(self.name, spec, f"seeded-shuffle:{state.seed}")
            for spec in remaining
        ]


class AdaptiveStrategy:
    name = "adaptive"

    def propose(self, state: StrategyState) -> list[StrategyProposal]:
        remaining = _remaining_specs(state)
        if not remaining:
            return []
        remaining_sorted = sorted(
            remaining,
            key=lambda spec: (_candidate_distance(spec), str(spec["candidate_id"])),
        )
        if not state.frontier:
            return [_proposal(self.name, remaining_sorted[0], "cold-start-smallest-distance")]

        frontier_distances = sorted({item.distance for item in state.frontier})
        max_frontier_distance = max(frontier_distances)
        larger = [
            spec
            for spec in remaining_sorted
            if _candidate_distance(spec) > max_frontier_distance
        ]
        if larger:
            return [_proposal(self.name, larger[0], "next-distance-frontier-expansion")]

        frontier_distance_set = set(frontier_distances)
        same_distance = [
            spec
            for spec in remaining_sorted
            if _candidate_distance(spec) in frontier_distance_set
        ]
        if same_distance:
            return [_proposal(self.name, same_distance[0], "same-distance-improvement-check")]

        return [_proposal(self.name, remaining_sorted[0], "remaining-distance")]


STRATEGIES: dict[str, Strategy] = {
    "grid": GridStrategy(),
    "random": RandomStrategy(),
    "adaptive": AdaptiveStrategy(),
}


def available_strategies() -> list[str]:
    return sorted(STRATEGIES)


def get_strategy(name: str) -> Strategy:
    try:
        return STRATEGIES[name]
    except KeyError as exc:
        raise SearchIntegrityError(f"unknown search strategy: {name}") from exc


def normalize_strategy_config(search_space: dict[str, Any]) -> dict[str, Any]:
    raw = search_space.get("strategy", {"name": "grid", "params": {}})
    if not isinstance(raw, dict):
        raise SearchIntegrityError("search strategy must be an object")
    name = raw.get("name", "grid")
    params = raw.get("params", {})
    if not isinstance(name, str) or not name:
        raise SearchIntegrityError("search strategy name must be a string")
    if name not in PUBLIC_STRATEGIES:
        raise SearchIntegrityError(f"unknown search strategy: {name}")
    if not isinstance(params, dict):
        raise SearchIntegrityError("search strategy params must be an object")
    get_strategy(name)
    return {"name": name, "params": dict(params)}


def with_strategy_provenance(candidate_spec: dict[str, Any], strategy_name: str) -> dict[str, Any]:
    updated = dict(candidate_spec)
    provenance = dict(updated.get("provenance", {}))
    provenance["strategy"] = strategy_name
    updated["provenance"] = provenance
    return updated


def frontier_quality(frontier: list[FrontierItem]) -> tuple[int, float]:
    if not frontier:
        return (0, 0.0)
    best_distance = max(item.distance for item in frontier)
    best_ler = min(item.ler for item in frontier if item.distance == best_distance)
    return (best_distance, -best_ler)
```

- [ ] **Step 4: Run strategy tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_strategies.py -q
```

Expected: all strategy unit tests pass.

- [ ] **Step 5: Commit strategy registry**

Run:

```bash
git add src/autoqec_search/strategies.py tests/test_search_strategies.py
git commit -m "feat: add search strategy registry"
```

## Task 3: Strategy Comparison Model And Renderers

**Files:**
- Create: `src/autoqec_search/strategy_compare.py`
- Create: `tests/test_search_strategy_compare.py`

- [ ] **Step 1: Write failing compare tests**

Create `tests/test_search_strategy_compare.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.strategy_compare import (
    compare_strategies,
    render_strategy_comparison_html,
    render_strategy_comparison_svg,
    write_strategy_comparison,
)


def _candidate(candidate_id: str, distance: int) -> dict:
    return {
        "candidate_id": candidate_id,
        "code_family": "rotated-surface-code",
        "parameters": {"distance": distance, "layout": "rotated"},
        "provenance": {"kind": "seed", "label": candidate_id},
    }


def _search_space() -> dict:
    return {
        "campaign_id": "rotated-surface-strategy-fixture",
        "mode": "explicit_list",
        "candidate_specs": [
            _candidate("d3-a", 3),
            _candidate("d3-b", 3),
            _candidate("d5", 5),
            _candidate("d7", 7),
        ],
    }


def _metrics() -> dict:
    return {
        "d3-a": {"distance": 3, "representative_ler": 0.03},
        "d3-b": {"distance": 3, "representative_ler": 0.04},
        "d5": {"distance": 5, "representative_ler": 0.02},
        "d7": {"distance": 7, "representative_ler": 0.01},
    }


def test_compare_strategies_asserts_adaptive_reaches_grid_quality_faster() -> None:
    model = compare_strategies(
        campaign_id="rotated-surface-strategy-fixture",
        search_space=_search_space(),
        metrics=_metrics(),
        strategy_names=["grid", "adaptive"],
        budget_candidates=3,
        seed=7,
    )

    assert model["assertion"]["passed"] is True
    assert model["assertion"]["adaptive_evaluations"] < model["assertion"]["grid_evaluations"]
    assert model["series"]["adaptive"]["proposal_order"] == ["d3-a", "d5", "d7"]


def test_compare_strategies_rejects_missing_metrics() -> None:
    metrics = _metrics()
    del metrics["d5"]

    with pytest.raises(SearchIntegrityError, match="missing strategy metric"):
        compare_strategies(
            campaign_id="rotated-surface-strategy-fixture",
            search_space=_search_space(),
            metrics=metrics,
            strategy_names=["grid", "adaptive"],
            budget_candidates=3,
            seed=7,
        )


def test_render_strategy_comparison_outputs_offline_artifacts(tmp_path: Path) -> None:
    model = compare_strategies(
        campaign_id="rotated-surface-strategy-fixture",
        search_space=_search_space(),
        metrics=_metrics(),
        strategy_names=["grid", "adaptive"],
        budget_candidates=3,
        seed=7,
    )

    svg = render_strategy_comparison_svg(model)
    html = render_strategy_comparison_html(model, svg)
    assert "<svg" in svg
    assert "http://" not in html
    assert "https://" not in html
    assert "Strategy Comparison" in html

    html_path = tmp_path / "strategies.html"
    written = write_strategy_comparison(model, html_path)
    assert written["json"].name == "strategies.json"
    assert written["svg"].name == "strategies.svg"
    assert written["html"].name == "strategies.html"
    assert json.loads(written["json"].read_text())["assertion"]["passed"] is True
```

- [ ] **Step 2: Run compare tests to verify missing module failure**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_strategy_compare.py -q
```

Expected: import fails because `autoqec_search.strategy_compare` does not exist.

- [ ] **Step 3: Implement `strategy_compare.py`**

Create `src/autoqec_search/strategy_compare.py` with:

```python
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.run_render import FrontierItem
from autoqec_search.strategies import StrategyState, frontier_quality, get_strategy


def _metric_for(metrics: dict[str, Any], candidate_id: str) -> tuple[int, float]:
    payload = metrics.get(candidate_id)
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"missing strategy metric for {candidate_id}")
    distance = payload.get("distance")
    ler = payload.get("representative_ler")
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError(f"invalid strategy metric distance for {candidate_id}")
    if not isinstance(ler, (int, float)) or isinstance(ler, bool) or not 0 <= float(ler) <= 1:
        raise SearchIntegrityError(f"invalid strategy metric representative_ler for {candidate_id}")
    return distance, float(ler)


def _update_synthetic_frontier(
    frontier: list[FrontierItem],
    *,
    candidate_id: str,
    distance: int,
    ler: float,
) -> list[FrontierItem]:
    by_distance = {item.distance: item for item in frontier}
    existing = by_distance.get(distance)
    if existing is None or ler < existing.ler:
        by_distance[distance] = FrontierItem(
            candidate_id=candidate_id,
            distance=distance,
            decoder_id="strategy-metric",
            p=0.0,
            ler=ler,
            manifest_path=f"strategy-metrics/{candidate_id}.json",
        )
    return sorted(by_distance.values(), key=lambda item: (item.distance, item.candidate_id))


def _simulate_strategy(
    *,
    strategy_name: str,
    candidate_specs: list[dict[str, Any]],
    metrics: dict[str, Any],
    budget_candidates: int,
    seed: int,
) -> dict[str, Any]:
    frontier: list[FrontierItem] = []
    attempted: set[str] = set()
    proposal_order: list[str] = []
    quality_sequence: list[dict[str, Any]] = []
    strategy = get_strategy(strategy_name)

    while len(proposal_order) < budget_candidates:
        state = StrategyState(
            candidate_specs=candidate_specs,
            frontier=frontier,
            attempted_candidate_ids=set(attempted),
            deduped_candidate_ids=set(),
            seed=seed,
            max_candidates=budget_candidates,
            evaluations_completed=len(proposal_order),
        )
        proposals = strategy.propose(state)
        fresh = [proposal for proposal in proposals if proposal.candidate_id not in attempted]
        if not fresh:
            break
        proposal = fresh[0]
        candidate_id = proposal.candidate_id
        distance, ler = _metric_for(metrics, candidate_id)
        attempted.add(candidate_id)
        proposal_order.append(candidate_id)
        frontier = _update_synthetic_frontier(
            frontier,
            candidate_id=candidate_id,
            distance=distance,
            ler=ler,
        )
        quality = frontier_quality(frontier)
        quality_sequence.append(
            {
                "evaluations": len(proposal_order),
                "candidate_id": candidate_id,
                "max_distance": quality[0],
                "negative_ler": quality[1],
            }
        )

    final_quality = frontier_quality(frontier)
    return {
        "proposal_order": proposal_order,
        "quality_sequence": quality_sequence,
        "final_quality": {"max_distance": final_quality[0], "negative_ler": final_quality[1]},
    }


def _quality_tuple(point: dict[str, Any]) -> tuple[int, float]:
    return (int(point["max_distance"]), float(point["negative_ler"]))


def _evaluations_to_reach(series: dict[str, Any], target: tuple[int, float]) -> int | None:
    for point in series["quality_sequence"]:
        if _quality_tuple(point) >= target:
            return int(point["evaluations"])
    return None


def compare_strategies(
    *,
    campaign_id: str,
    search_space: dict[str, Any],
    metrics: dict[str, Any],
    strategy_names: list[str],
    budget_candidates: int,
    seed: int,
) -> dict[str, Any]:
    if budget_candidates < 1:
        raise SearchIntegrityError("budget_candidates must be positive")
    candidate_specs = list(search_space.get("candidate_specs", []))
    if not candidate_specs:
        raise SearchIntegrityError("strategy comparison requires candidate_specs")
    series = {
        name: _simulate_strategy(
            strategy_name=name,
            candidate_specs=candidate_specs,
            metrics=metrics,
            budget_candidates=budget_candidates,
            seed=seed,
        )
        for name in strategy_names
    }
    if "grid" not in series or "adaptive" not in series:
        raise SearchIntegrityError("strategy comparison requires grid and adaptive")
    grid_final = series["grid"]["final_quality"]
    target = (int(grid_final["max_distance"]), float(grid_final["negative_ler"]))
    grid_evaluations = _evaluations_to_reach(series["grid"], target)
    adaptive_evaluations = _evaluations_to_reach(series["adaptive"], target)
    passed = (
        grid_evaluations is not None
        and adaptive_evaluations is not None
        and adaptive_evaluations < grid_evaluations
    )
    return {
        "campaign_id": campaign_id,
        "strategy_names": strategy_names,
        "budget_candidates": budget_candidates,
        "seed": seed,
        "series": series,
        "assertion": {
            "passed": passed,
            "target_quality": {"max_distance": target[0], "negative_ler": target[1]},
            "grid_evaluations": grid_evaluations,
            "adaptive_evaluations": adaptive_evaluations,
        },
    }


def render_strategy_comparison_svg(model: dict[str, Any]) -> str:
    width = 720
    height = 360
    left = 56
    bottom = 316
    plot_width = 620
    plot_height = 250
    max_evaluations = max(
        [1]
        + [
            point["evaluations"]
            for series in model["series"].values()
            for point in series["quality_sequence"]
        ]
    )
    max_distance = max(
        [1]
        + [
            point["max_distance"]
            for series in model["series"].values()
            for point in series["quality_sequence"]
        ]
    )
    colors = {"grid": "#3454d1", "adaptive": "#0f7b4f", "random": "#9a5b00"}
    polylines = []
    for name, series in model["series"].items():
        points = []
        for point in series["quality_sequence"]:
            x = left + (point["evaluations"] / max_evaluations) * plot_width
            y = bottom - (point["max_distance"] / max_distance) * plot_height
            points.append(f"{x:.1f},{y:.1f}")
        if points:
            color = colors.get(name, "#333333")
            polylines.append(
                f"<polyline fill='none' stroke='{color}' stroke-width='3' points='{' '.join(points)}'/>"
            )
            last = points[-1].split(",")
            polylines.append(
                f"<text x='{float(last[0]) + 8:.1f}' y='{float(last[1]) + 4:.1f}'>{escape(name)}</text>"
            )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="white"/>
  <text x="24" y="32" font-family="system-ui" font-size="20" font-weight="700">Strategy Comparison</text>
  <line x1="{left}" y1="66" x2="{left}" y2="{bottom}" stroke="#333"/>
  <line x1="{left}" y1="{bottom}" x2="{left + plot_width}" y2="{bottom}" stroke="#333"/>
  <text x="18" y="180" font-family="system-ui" font-size="13" transform="rotate(-90 18 180)">best distance</text>
  <text x="300" y="348" font-family="system-ui" font-size="13">evaluations</text>
  {''.join(polylines)}
</svg>
"""


def render_strategy_comparison_html(model: dict[str, Any], svg: str) -> str:
    rows = []
    for name, series in model["series"].items():
        rows.append(
            "<tr>"
            f"<td>{escape(name)}</td>"
            f"<td>{escape(', '.join(series['proposal_order']))}</td>"
            f"<td>{escape(str(series['final_quality']['max_distance']))}</td>"
            f"<td>{escape(str(series['final_quality']['negative_ler']))}</td>"
            "</tr>"
        )
    payload = json.dumps(model, indent=2, sort_keys=True).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC Strategy Comparison</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1100px; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.4rem 0.55rem; text-align: left; }}
    th {{ background: #eef2f6; }}
    pre {{ background: #f6f8fa; padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>Strategy Comparison</h1>
  {svg}
  <p>Assertion passed: <strong>{str(model['assertion']['passed']).lower()}</strong></p>
  <table>
    <thead><tr><th>Strategy</th><th>Order</th><th>Max distance</th><th>Negative LER</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h2>Model JSON</h2>
  <pre>{escape(payload)}</pre>
</body>
</html>
"""


def write_strategy_comparison(model: dict[str, Any], html_path: Path) -> dict[str, Path]:
    stem = html_path.with_suffix("")
    json_path = stem.with_suffix(".json")
    svg_path = stem.with_suffix(".svg")
    actual_html_path = stem.with_suffix(".html")
    svg = render_strategy_comparison_svg(model)
    html = render_strategy_comparison_html(model, svg)
    actual_html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    svg_path.write_text(svg)
    actual_html_path.write_text(html)
    return {"json": json_path, "svg": svg_path, "html": actual_html_path}
```

- [ ] **Step 4: Run compare tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_strategy_compare.py -q
```

Expected: all compare tests pass.

- [ ] **Step 5: Commit compare model**

Run:

```bash
git add src/autoqec_search/strategy_compare.py tests/test_search_strategy_compare.py
git commit -m "feat: compare search strategies"
```

## Task 4: Strategy Fixture Campaign And Metrics

**Files:**
- Create: `campaigns/examples/rotated-surface-strategy-fixture/campaign.json`
- Create: `campaigns/examples/rotated-surface-strategy-fixture/search_space.json`
- Create: `benchmarks/fixtures/strategy-comparison/rotated-surface.json`
- Modify: `tests/test_search_load.py`

- [ ] **Step 1: Add failing fixture load assertion**

In `tests/test_search_load.py`, update `test_load_search_workspace_collects_campaigns_and_contracts()`:

```python
    assert sorted(workspace.campaigns) == [
        "rotated-surface-baseline",
        "rotated-surface-strategy-fixture",
    ]
    assert sorted(workspace.search_spaces) == [
        "rotated-surface-baseline",
        "rotated-surface-strategy-fixture",
    ]
```

- [ ] **Step 2: Run the failing fixture assertion**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_load.py::test_load_search_workspace_collects_campaigns_and_contracts -q
```

Expected: failure because the fixture campaign does not exist.

- [ ] **Step 3: Add fixture files**

Create `campaigns/examples/rotated-surface-strategy-fixture/campaign.json`:

```json
{
  "budget": {
    "max_candidates": 3,
    "wall_clock_seconds": 3600
  },
  "default_suite_id": "rotated-surface-baseline-v1",
  "family_id": "surface-code",
  "id": "rotated-surface-strategy-fixture",
  "objective": "Fixture campaign for comparing grid and adaptive strategy order without changing the M1 baseline.",
  "random_seed_policy": {
    "mode": "fixed",
    "seed": 7
  },
  "stop_conditions": {
    "max_candidates": 3,
    "max_wall_clock_seconds": 3600
  },
  "title": "Rotated Surface Strategy Fixture"
}
```

Create `campaigns/examples/rotated-surface-strategy-fixture/search_space.json`:

```json
{
  "campaign_id": "rotated-surface-strategy-fixture",
  "candidate_specs": [
    {
      "candidate_id": "strategy-d3-a",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 3,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "fixture",
        "label": "strategy-d3-a"
      }
    },
    {
      "candidate_id": "strategy-d3-b",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 3,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "fixture",
        "label": "strategy-d3-b"
      }
    },
    {
      "candidate_id": "strategy-d5",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 5,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "fixture",
        "label": "strategy-d5"
      }
    },
    {
      "candidate_id": "strategy-d7",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 7,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "fixture",
        "label": "strategy-d7"
      }
    }
  ],
  "mode": "explicit_list",
  "strategy": {
    "name": "adaptive",
    "params": {}
  }
}
```

Create `benchmarks/fixtures/strategy-comparison/rotated-surface.json`:

```json
{
  "strategy-d3-a": {
    "distance": 3,
    "representative_ler": 0.03
  },
  "strategy-d3-b": {
    "distance": 3,
    "representative_ler": 0.04
  },
  "strategy-d5": {
    "distance": 5,
    "representative_ler": 0.02
  },
  "strategy-d7": {
    "distance": 7,
    "representative_ler": 0.01
  }
}
```

- [ ] **Step 4: Run workspace validation**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
PYTHONPATH=src python3 -m pytest tests/test_search_load.py::test_load_search_workspace_collects_campaigns_and_contracts -q
```

Expected: validation exits 0 and the load test passes.

- [ ] **Step 5: Commit fixture campaign**

Run:

```bash
git add campaigns/examples/rotated-surface-strategy-fixture benchmarks/fixtures/strategy-comparison/rotated-surface.json tests/test_search_load.py
git commit -m "test: add strategy comparison fixture campaign"
```

## Task 5: CLI For Strategy Comparison

**Files:**
- Modify: `src/autoqec_search/cli.py:42-220`
- Test: `tests/test_search_strategy_compare.py`

- [ ] **Step 1: Add failing CLI test**

Append to `tests/test_search_strategy_compare.py`:

```python
def test_compare_strategies_cli_writes_artifacts(tmp_path: Path) -> None:
    from autoqec_search.cli import main

    out_path = tmp_path / "strategies.html"
    rc = main(
        [
            "compare-strategies",
            "--root",
            str(Path(__file__).resolve().parents[1]),
            "--campaign",
            "rotated-surface-strategy-fixture",
            "--strategies",
            "grid",
            "adaptive",
            "--budget-candidates",
            "3",
            "--metrics",
            str(
                Path(__file__).resolve().parents[1]
                / "benchmarks"
                / "fixtures"
                / "strategy-comparison"
                / "rotated-surface.json"
            ),
            "--out",
            str(out_path),
        ]
    )

    assert rc == 0
    assert out_path.is_file()
    assert out_path.with_suffix(".json").is_file()
    assert out_path.with_suffix(".svg").is_file()
```

- [ ] **Step 2: Run CLI test to verify missing command failure**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_strategy_compare.py::test_compare_strategies_cli_writes_artifacts -q
```

Expected: parser exits because `compare-strategies` is not registered.

- [ ] **Step 3: Add parser and handler**

In `src/autoqec_search/cli.py`, add imports:

```python
import json
from autoqec_search.strategy_compare import compare_strategies, write_strategy_comparison
```

In `build_parser()`, after `run_parser`, add:

```python
    compare_parser = subparsers.add_parser(
        "compare-strategies",
        help="Compare search strategies on deterministic candidate metrics",
    )
    compare_parser.add_argument("--root", default=".")
    compare_parser.add_argument("--campaign", required=True)
    compare_parser.add_argument("--strategies", nargs="+", required=True)
    compare_parser.add_argument("--budget-candidates", type=int, required=True)
    compare_parser.add_argument("--metrics", required=True)
    compare_parser.add_argument("--out", required=True)
    compare_parser.add_argument("--seed", type=int, default=None)
```

In `main()`, after the `run` branch, add:

```python
        if args.command == "compare-strategies":
            root = Path(args.root)
            if not root.exists():
                parser.error(f"repository root does not exist: {root}")
            workspace = load_search_workspace(root)
            if args.campaign not in workspace.search_spaces:
                raise SearchIntegrityError(f"unknown campaign_id: {args.campaign}")
            campaign = workspace.campaigns[args.campaign]
            seed = args.seed
            if seed is None:
                policy = campaign.get("random_seed_policy")
                seed = (
                    policy.get("seed")
                    if isinstance(policy, dict) and type(policy.get("seed")) is int
                    else 0
                )
            metrics = json.loads(Path(args.metrics).read_text())
            if not isinstance(metrics, dict):
                raise SearchIntegrityError("strategy metrics must be a JSON object")
            model = compare_strategies(
                campaign_id=args.campaign,
                search_space=workspace.search_spaces[args.campaign],
                metrics=metrics,
                strategy_names=list(args.strategies),
                budget_candidates=args.budget_candidates,
                seed=seed,
            )
            written = write_strategy_comparison(model, Path(args.out))
            print(f"wrote strategy comparison to {written['html']}")
            if not model["assertion"]["passed"]:
                raise SearchIntegrityError("adaptive strategy did not beat grid")
            return 0
```

- [ ] **Step 4: Run compare CLI tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_strategy_compare.py -q
```

Expected: all strategy comparison tests pass.

- [ ] **Step 5: Commit compare CLI**

Run:

```bash
git add src/autoqec_search/cli.py tests/test_search_strategy_compare.py
git commit -m "feat: add compare-strategies command"
```

## Task 6: Run Loop Strategy Metadata And Trace

**Files:**
- Modify: `src/autoqec_search/run_loop.py:50-66`
- Modify: `src/autoqec_search/run_loop.py:190-220`
- Modify: `src/autoqec_search/run_loop.py:978-1042`
- Modify: `src/autoqec_search/run_loop.py:1071-1435`
- Modify: `src/autoqec_search/run_render.py`
- Test: `tests/test_search_run_loop.py`
- Test: `tests/test_search_run_cli.py`

- [ ] **Step 1: Add failing unit tests for skeleton metadata and trace helpers**

In `tests/test_search_run_loop.py`, update imports to include `StrategyEvent` after it is introduced by this task:

```python
from autoqec_search.run_loop import (
    CandidateRecord,
    RunConfig,
    StrategyEvent,
    autoresearch_evaluation_p_values,
    candidate_is_complete,
    choose_seed,
    default_tag,
    parse_wall_clock_seconds,
    representative_ler,
    render_strategy_trace,
    update_frontier,
    validate_path_segment,
)
```

Append:

```python
def test_render_strategy_trace_records_events() -> None:
    payload = render_strategy_trace(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        strategy={"name": "adaptive", "params": {}},
        events=[
            StrategyEvent(
                candidate_id="rotated-surface-d3-example",
                reason="cold-start-smallest-distance",
                action="evaluated",
                verdict="keep",
                frontier_quality=(3, -0.013),
            )
        ],
    )

    assert payload["strategy"] == {"name": "adaptive", "params": {}}
    assert payload["events"][0]["candidate_id"] == "rotated-surface-d3-example"
    assert payload["events"][0]["frontier_quality"] == {
        "max_distance": 3,
        "negative_ler": -0.013,
    }


def test_write_run_skeleton_records_strategy_metadata(tmp_path: Path) -> None:
    from autoqec_search.run_loop import write_run_skeleton

    run_root = tmp_path / "results" / "search" / "rotated-surface-baseline" / "fixed-check"
    env = {"tool": "autoqec-search", "version": "0.1.0", "generated_at": "2026-06-14T03:11:22Z", "mode": "autoresearch"}
    suite = {"id": "rotated-surface-baseline-v1", "task_ids": ["rotated-memory-x-cdep-v1"], "decoder_ids": ["rmatching-default-v1"]}
    run_spec = write_run_skeleton(
        run_root,
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        suite=suite,
        candidate_ids=["rotated-surface-d3-example"],
        created_at="2026-06-14T03:11:22Z",
        wall_clock_seconds=90,
        seed=7,
        env=env,
        strategy={"name": "adaptive", "params": {}},
    )

    assert run_spec["strategy"] == {"name": "adaptive", "params": {}}
```

- [ ] **Step 2: Run unit tests to verify missing helper failure**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_run_loop.py::test_render_strategy_trace_records_events tests/test_search_run_loop.py::test_write_run_skeleton_records_strategy_metadata -q
```

Expected: import/signature failures because run-loop strategy trace helpers do not exist yet.

- [ ] **Step 3: Add trace dataclass and renderer**

In `src/autoqec_search/run_loop.py`, add imports:

```python
from autoqec_search.strategies import (
    StrategyState,
    frontier_quality,
    get_strategy,
    normalize_strategy_config,
    with_strategy_provenance,
)
```

After `CandidateRecord`, add:

```python
@dataclass(frozen=True)
class StrategyEvent:
    candidate_id: str | None
    reason: str
    action: str
    verdict: str | None
    frontier_quality: tuple[int, float] | None
```

Add:

```python
def render_strategy_trace(
    *,
    campaign_id: str,
    run_id: str,
    strategy: dict[str, Any],
    events: list[StrategyEvent],
) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "strategy": strategy,
        "events": [
            {
                "candidate_id": event.candidate_id,
                "reason": event.reason,
                "action": event.action,
                "verdict": event.verdict,
                "frontier_quality": (
                    None
                    if event.frontier_quality is None
                    else {
                        "max_distance": event.frontier_quality[0],
                        "negative_ler": event.frontier_quality[1],
                    }
                ),
            }
            for event in events
        ],
    }
```

- [ ] **Step 4: Extend skeleton and env metadata**

Change `write_run_skeleton()` signature to include:

```python
    strategy: dict[str, Any] | None = None,
```

Inside `run_spec`, add:

```python
    if strategy is not None:
        run_spec["strategy"] = strategy
```

Change `build_env()` signature to include:

```python
    strategy: dict[str, Any] | None = None,
```

Before returning, build `env` as a dict and add:

```python
    if strategy is not None:
        env["strategy_name"] = strategy["name"]
        env["strategy_params"] = strategy["params"]
    return env
```

- [ ] **Step 5: Fill strategy provenance on candidate payloads**

In `write_placeholder_candidates()` and `write_crash_candidate()`, use `with_strategy_provenance()` before writing `candidate.json`. The concrete change in `write_crash_candidate()`:

```python
    strategy_name = str(candidate_spec.get("_strategy_name", "grid"))
    payload = {
        ...
        "provenance": (
            with_strategy_provenance({"provenance": provenance}, strategy_name)["provenance"]
            if isinstance(provenance, dict)
            else {"kind": "invalid", "label": "invalid-candidate", "strategy": strategy_name}
        ),
        ...
    }
```

In `write_placeholder_candidates()`, set:

```python
                "provenance": candidate_spec["provenance"],
```

to:

```python
                "provenance": dict(candidate_spec["provenance"]),
```

The strategy field is added when the run loop proposes the spec.

- [ ] **Step 6: Replace fixed candidate loop with strategy proposals**

In `_selected_candidate_specs()`, stop slicing by `_max_candidates(campaign)`. Return every `candidate_spec` after validating ids. The candidate budget limits the number of evaluations, not the strategy's visibility into the pool:

```python
def _selected_candidate_specs(workspace, campaign_id: str, campaign: dict) -> list[dict]:
    if campaign_id not in workspace.search_spaces:
        raise SearchIntegrityError(f"unknown search space campaign_id: {campaign_id}")
    candidate_specs = list(workspace.search_spaces[campaign_id]["candidate_specs"])
    if not candidate_specs:
        raise SearchIntegrityError(f"campaign has no candidate specs: {campaign_id}")
    for spec in candidate_specs:
        candidate_id = spec.get("candidate_id")
        if not isinstance(candidate_id, str):
            raise SearchIntegrityError("candidate_id must be a string")
        validate_path_segment(candidate_id, label="candidate_id")
    return candidate_specs
```

In `run_autoresearch()`, after loading workspace and before skeleton writing, add:

```python
    search_space = workspace.search_spaces[campaign_id]
    strategy_config = normalize_strategy_config(search_space)
    strategy = get_strategy(strategy_config["name"])
```

Pass `strategy_config` into `build_env()` and `write_run_skeleton()`.

Before the loop, initialize:

```python
    strategy_events: list[StrategyEvent] = []
    attempted_candidate_ids: set[str] = set()
```

If `resume` is true, rebuild `rows`, `frontier`, and `attempted_candidate_ids` from terminal candidate outputs before asking the strategy for new proposals:

```python
    if resume:
        for candidate_spec in selected_specs:
            candidate_id = candidate_spec["candidate_id"]
            candidate_root = run_root / "candidates" / candidate_id
            if not candidate_has_terminal_outcome(
                candidate_root,
                task_id=config.task_id,
                primary_decoder_id=config.primary_decoder_id,
                required_p_values=selected_p_values,
                task_ids=suite["task_ids"],
                decoder_ids=suite["decoder_ids"],
                campaign_id=campaign_id,
                run_id=actual_run_id,
            ):
                continue
            existing_row, existing_record = load_existing_candidate_outcome(
                config,
                candidate_root,
                suite["decoder_ids"],
            )
            attempted_candidate_ids.add(candidate_id)
            if existing_record is None:
                rows.append(existing_row)
            else:
                frontier, row = update_frontier(config, frontier, existing_record)
                rows.append(row)
            strategy_events.append(
                StrategyEvent(
                    candidate_id=candidate_id,
                    reason="resume-terminal-candidate",
                    action="evaluated",
                    verdict=rows[-1].status,
                    frontier_quality=frontier_quality(frontier),
                )
            )
```

Replace:

```python
    for candidate_spec in selected_specs:
```

with:

```python
    while len(rows) < _max_candidates(campaign):
        state = StrategyState(
            candidate_specs=selected_specs,
            frontier=list(frontier),
            attempted_candidate_ids=set(attempted_candidate_ids),
            deduped_candidate_ids={
                event.candidate_id
                for event in strategy_events
                if event.action == "deduped" and event.candidate_id is not None
            },
            seed=actual_seed,
            max_candidates=_max_candidates(campaign),
            evaluations_completed=len(rows),
        )
        proposals = strategy.propose(state)
        if not proposals:
            stop_reason = "search-space-exhausted"
            strategy_events.append(
                StrategyEvent(
                    candidate_id=None,
                    reason="strategy-returned-no-proposals",
                    action="exhausted",
                    verdict=None,
                    frontier_quality=frontier_quality(frontier),
                )
            )
            break
        fresh_proposal = None
        for proposal in proposals:
            if proposal.candidate_id in attempted_candidate_ids:
                strategy_events.append(
                    StrategyEvent(
                        candidate_id=proposal.candidate_id,
                        reason=proposal.reason,
                        action="deduped",
                        verdict=None,
                        frontier_quality=frontier_quality(frontier),
                    )
                )
                continue
            fresh_proposal = proposal
            break
        if fresh_proposal is None:
            stop_reason = "search-space-exhausted"
            break
        candidate_spec = with_strategy_provenance(
            fresh_proposal.candidate_spec,
            fresh_proposal.strategy,
        )
        candidate_spec["_strategy_name"] = fresh_proposal.strategy
        candidate_id = fresh_proposal.candidate_id
```

Set `stop_reason = "completed"` before the loop. When `remaining_seconds <= 0`, set `stop_reason = "wall-clock"` before `break`. When the loop exits because `len(rows) >= _max_candidates(campaign)`, set `stop_reason = "max-candidates"`.

After producing `row`, add:

```python
        attempted_candidate_ids.add(candidate_id)
        strategy_events.append(
            StrategyEvent(
                candidate_id=candidate_id,
                reason=fresh_proposal.reason,
                action="evaluated",
                verdict=row.status,
                frontier_quality=frontier_quality(frontier),
            )
        )
```

After each `write_aggregates()`, write:

```python
        _write_json(
            run_root / "strategy_trace.json",
            render_strategy_trace(
                campaign_id=campaign_id,
                run_id=actual_run_id,
                strategy=strategy_config,
                events=strategy_events,
            ),
        )
```

- [ ] **Step 7: Extend final status and summaries**

Change `write_final_status()` signature:

```python
    stop_reason: str,
```

Add to payload:

```python
            "stop_reason": stop_reason,
```

In `run_render.py`, extend `render_autoresearch_summary()` and `render_run_summary_html()` signatures with:

```python
    strategy: dict | None = None,
    stop_reason: str | None = None,
```

Add lines in the markdown summary:

```python
        f"- strategy: `{_md_inline(strategy['name'])}`" if strategy else "- strategy: `grid`",
        f"- stop_reason: `{_md_inline(stop_reason or 'completed')}`",
```

Add matching HTML meta rows:

```python
    <strong>Strategy</strong><span>{escape(str((strategy or {'name': 'grid'})['name']))}</span>
    <strong>Stop reason</strong><span>{escape(stop_reason or 'completed')}</span>
```

Update `write_aggregates()` to pass the strategy and current stop reason once those values are available. For interim writes before final stop, pass `stop_reason=None`.

- [ ] **Step 8: Add run CLI assertions**

In `tests/test_search_run_cli.py`, update `_assert_lab_notebook()`:

```python
    run_spec = json.loads((run_root / "run_spec.json").read_text())
    assert run_spec["strategy"] == {"name": "grid", "params": {}}
    assert (run_root / "strategy_trace.json").is_file()
    trace = json.loads((run_root / "strategy_trace.json").read_text())
    assert trace["strategy"] == {"name": "grid", "params": {}}
    assert any(event["action"] == "evaluated" for event in trace["events"])
    assert json.loads((run_root / "run_status.json").read_text())["stop_reason"] in {
        "max-candidates",
        "completed",
        "wall-clock",
        "search-space-exhausted",
    }
```

- [ ] **Step 9: Run run-loop and CLI tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_run_loop.py tests/test_search_run_cli.py -q
```

Expected: both files pass.

- [ ] **Step 10: Commit run-loop integration**

Run:

```bash
git add src/autoqec_search/run_loop.py src/autoqec_search/run_render.py tests/test_search_run_loop.py tests/test_search_run_cli.py
git commit -m "feat: drive autoresearch with strategy proposals"
```

## Task 7: Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_search_docs.py`

- [ ] **Step 1: Add failing documentation tests**

Append to `tests/test_search_docs.py`:

```python
def test_docs_mention_search_strategy_registry() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "search_space.strategy" in document
        assert "autoqec-search compare-strategies" in document
        assert "strategy_trace.json" in document
        assert "rotated-surface-strategy-fixture" in document
        assert "benchmarks/fixtures/strategy-comparison/rotated-surface.json" in document
```

- [ ] **Step 2: Run docs test to verify failure**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py::test_docs_mention_search_strategy_registry -q
```

Expected: fails because docs do not mention issue #14 artifacts yet.

- [ ] **Step 3: Update README**

In `README.md`, after the autoresearch `run` section, add:

```markdown
Search strategy selection is recorded internally in `search_space.strategy`.
When the field is absent, `autoqec-search run` uses `grid`, preserving the M1
candidate order. Supported strategies are `grid`, `random`, and `adaptive`.
Every strategy-aware run writes `strategy_trace.json` next to
`experiment-log.tsv`; the trace records evaluated, deduped, and exhausted
proposal events without polluting the experiment log.

Compare grid and adaptive behavior on the committed strategy fixture with:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-strategies \
  --root . \
  --campaign rotated-surface-strategy-fixture \
  --strategies grid adaptive \
  --budget-candidates 3 \
  --metrics benchmarks/fixtures/strategy-comparison/rotated-surface.json \
  --out /tmp/autoqec-strategies.html
```

The command writes sibling `strategies.json`, `strategies.svg`, and
`strategies.html` artifacts. It exits nonzero if adaptive does not reach the
grid target quality in fewer evaluations on the fixture.
```

- [ ] **Step 4: Update CLAUDE**

In `CLAUDE.md`, after the issue #10 run section, add:

```markdown
For issue `#14` and M2 search strategy work, `search_space.strategy` selects
the proposal policy for `autoqec-search run`. Missing strategy means `grid`.
Supported names are `grid`, `random`, and `adaptive`; new runs record the
selected strategy in `run_spec.json`, `env.json`, and `strategy_trace.json`.

Verify the strategy comparison fixture with:

```sh
PYTHONPATH=src python3 -m autoqec_search.cli compare-strategies --root . --campaign rotated-surface-strategy-fixture --strategies grid adaptive --budget-candidates 3 --metrics benchmarks/fixtures/strategy-comparison/rotated-surface.json --out /tmp/autoqec-strategies.html
```
```

- [ ] **Step 5: Run documentation tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
```

Expected: all documentation tests pass.

- [ ] **Step 6: Commit docs**

Run:

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: describe search strategy registry"
```

## Task 8: Full Verification And Issue Closure

**Files:**
- No source edits expected unless verification exposes a failing contract.

- [ ] **Step 1: Run focused issue #14 tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_strategies.py \
  tests/test_search_strategy_compare.py \
  tests/test_search_run_loop.py \
  tests/test_search_run_cli.py \
  tests/test_search_load.py \
  tests/test_search_docs.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run workspace validation**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: exits 0 and reports the search workspace counts.

- [ ] **Step 3: Run the human-route comparison command**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-strategies \
  --root . \
  --campaign rotated-surface-strategy-fixture \
  --strategies grid adaptive \
  --budget-candidates 3 \
  --metrics benchmarks/fixtures/strategy-comparison/rotated-surface.json \
  --out /tmp/autoqec-strategies.html
```

Expected: exits 0 and writes `/tmp/autoqec-strategies.html`, `/tmp/autoqec-strategies.svg`, and `/tmp/autoqec-strategies.json`.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: no uncommitted files.

- [ ] **Step 5: Summarize completion**

Report:

- strategy registry implemented
- `run` records strategy metadata and trace
- `compare-strategies` writes JSON/SVG/HTML and asserts adaptive beats grid on fixture
- focused tests and validation passed
- note any tests not run

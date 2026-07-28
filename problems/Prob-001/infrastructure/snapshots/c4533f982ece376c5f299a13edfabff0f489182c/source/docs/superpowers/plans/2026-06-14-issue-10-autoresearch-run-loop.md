# Issue 10 Autoresearch Run Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `autoqec-search run`, a time-bounded, resumable autoresearch loop that runs inside an isolated git worktree and commits a reviewable lab notebook.

**Architecture:** Reuse the issue #9 candidate evaluator by extracting a candidate-level helper from `eval_run.py`. Add `run_loop.py` for campaign orchestration, git worktree isolation, resume checks, verdicts, frontier updates, and commits. Add `run_render.py` for the notebook text/HTML outputs so the orchestration logic stays focused.

**Tech Stack:** Python 3.11 standard library, `jsonschema`, `pytest`, local `git`, fake `rsinter` for CLI tests, existing `autoqec_search` package layout.

---

## File Structure

| File | Responsibility |
|---|---|
| `benchmarks/schemas/run-spec.schema.json` | Accept `mode: "autoresearch"` and optional autoresearch metadata. |
| `benchmarks/schemas/candidate.schema.json` | Accept crashed candidates in autoresearch runs. |
| `benchmarks/schemas/result-manifest.schema.json` | Accept candidate-level crash manifests. |
| `campaigns/examples/rotated-surface-baseline/campaign.json` | Raise the example candidate budget to two candidates. |
| `campaigns/examples/rotated-surface-baseline/search_space.json` | Add a second valid d=3 candidate for loop keep/discard behavior. |
| `src/autoqec_search/eval_candidates.py` | Resolve a candidate from an explicit search-space candidate spec. |
| `src/autoqec_search/eval_run.py` | Extract reusable candidate evaluation into an existing run directory. |
| `src/autoqec_search/run_render.py` | Render experiment log, keep-only leaderboard, frontier JSON, summary Markdown, and self-contained HTML. |
| `src/autoqec_search/run_loop.py` | Parse budgets, manage tags, create/resume git worktrees, run the candidate loop, and commit artifacts. |
| `src/autoqec_search/cli.py` | Add the `run` subcommand and wire arguments into `run_loop.run_autoresearch`. |
| `README.md` | Document `autoqec-search run`. |
| `CLAUDE.md` | Document repo-specific run-loop usage and worktree behavior. |
| `tests/test_search_eval_schemas.py` | Schema coverage for autoresearch and crash records. |
| `tests/test_search_source_data.py` | Source-data expectations for the expanded example campaign. |
| `tests/test_search_eval_candidates.py` | Explicit candidate-spec resolver and duplicate-distance behavior. |
| `tests/test_search_eval_cli.py` | Existing eval regression coverage after the candidate resolver changes. |
| `tests/test_search_run_render.py` | Pure rendering tests for notebook artifacts. |
| `tests/test_search_run_loop.py` | Pure loop helper tests for budgets, tags, frontier, resume checks, and git command wrappers. |
| `tests/test_search_run_cli.py` | End-to-end CLI tests using a temporary git repo and fake `rsinter`. |
| `tests/test_search_docs.py` | Documentation coverage for the new command. |

---

### Task 1: Extend Schemas And Example Campaign

**Files:**
- Modify: `benchmarks/schemas/run-spec.schema.json`
- Modify: `benchmarks/schemas/candidate.schema.json`
- Modify: `benchmarks/schemas/result-manifest.schema.json`
- Modify: `campaigns/examples/rotated-surface-baseline/campaign.json`
- Modify: `campaigns/examples/rotated-surface-baseline/search_space.json`
- Modify: `tests/test_search_eval_schemas.py`
- Modify: `tests/test_search_source_data.py`

- [ ] **Step 1: Add failing schema tests**

Append these tests to `tests/test_search_eval_schemas.py`:

```python
def test_autoresearch_schemas_accept_run_and_crash_records() -> None:
    schema_root = REPO_ROOT / "benchmarks" / "schemas"
    run_spec = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "suite_id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-x-cdep-v1"],
        "decoder_ids": [
            "rmatching-default-v1",
            "rbposd-default-v1",
            "rilpqec-default-v1",
        ],
        "candidate_ids": [
            "rotated-surface-d3-example",
            "rotated-surface-d3-repeat",
        ],
        "created_at": "2026-06-14T03:11:22Z",
        "mode": "autoresearch",
        "tag": "fixed-check",
        "wall_clock_seconds": 90,
        "seed": 7,
    }
    crashed_candidate = {
        "candidate_id": "rotated-surface-invalid-d1",
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "code_family": "rotated-surface-code",
        "parameters": {"distance": 1, "layout": "rotated"},
        "provenance": {"kind": "test", "label": "invalid-distance"},
        "status": "crashed",
    }
    crash_manifest = {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "candidate_id": "rotated-surface-invalid-d1",
        "task_id": "rotated-memory-x-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "crash",
        "created_at": "2026-06-14T03:11:22Z",
        "error": "no matching Zoo instance",
    }

    Draft202012Validator(_load_json(schema_root / "run-spec.schema.json")).validate(
        run_spec
    )
    Draft202012Validator(_load_json(schema_root / "candidate.schema.json")).validate(
        crashed_candidate
    )
    Draft202012Validator(
        _load_json(schema_root / "result-manifest.schema.json")
    ).validate(crash_manifest)
```

Update `test_eval_schemas_accept_completed_records` in the same file by leaving its existing `mode: "eval"` object unchanged. That test proves the schema extension remains backwards compatible.

- [ ] **Step 2: Add failing source-data expectations**

In `tests/test_search_source_data.py`, after the suite validation assertion near
the end of `test_search_example_source_files_validate_against_checked_in_schemas`,
add:

```python
    search_space = _load_json(example_root / "search_space.json")
    candidate_ids = [
        candidate["candidate_id"] for candidate in search_space["candidate_specs"]
    ]
    assert candidate_ids == [
        "rotated-surface-d3-example",
        "rotated-surface-d3-repeat",
    ]

    campaign = _load_json(example_root / "campaign.json")
    assert campaign["budget"]["max_candidates"] == 2
    assert campaign["stop_conditions"]["max_candidates"] == 2
```

- [ ] **Step 3: Run the new schema/source tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_eval_schemas.py::test_autoresearch_schemas_accept_run_and_crash_records tests/test_search_source_data.py::test_search_example_source_files_validate_against_checked_in_schemas -q
```

Expected: FAIL. The run-spec schema rejects `mode: "autoresearch"` and new metadata, the candidate schema rejects `status: "crashed"`, the result manifest schema rejects `status: "crash"`, and the source-data test still sees one candidate.

- [ ] **Step 4: Update `run-spec.schema.json`**

Replace the `mode` property with this enum and add the three optional properties under `properties`:

```json
    "mode": { "enum": ["placeholder", "eval", "autoresearch"] },
    "tag": { "type": "string", "minLength": 1 },
    "wall_clock_seconds": { "type": "integer", "minimum": 1 },
    "seed": { "type": "integer" }
```

Keep `required` unchanged so existing placeholder and eval records remain valid.

- [ ] **Step 5: Update `candidate.schema.json`**

Replace the `status` enum with:

```json
    "status": { "enum": ["placeholder", "evaluated", "crashed"] }
```

- [ ] **Step 6: Add crash manifest support**

In `benchmarks/schemas/result-manifest.schema.json`, add this third object to the top-level `oneOf` array after the completed-manifest object:

```json
    {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "campaign_id",
        "run_id",
        "candidate_id",
        "task_id",
        "decoder_id",
        "status",
        "created_at",
        "error"
      ],
      "properties": {
        "campaign_id": { "type": "string", "minLength": 1 },
        "run_id": { "type": "string", "minLength": 1 },
        "candidate_id": { "type": "string", "minLength": 1 },
        "task_id": { "type": "string", "minLength": 1 },
        "decoder_id": { "type": "string", "minLength": 1 },
        "status": { "const": "crash" },
        "created_at": {
          "type": "string",
          "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"
        },
        "error": { "type": "string", "minLength": 1 }
      }
    }
```

- [ ] **Step 7: Expand the example campaign**

Change `campaigns/examples/rotated-surface-baseline/campaign.json` so both max-candidate values are `2`:

```json
  "budget": {
    "wall_clock_seconds": 3600,
    "max_candidates": 2
  },
  "stop_conditions": {
    "max_candidates": 2,
    "max_wall_clock_seconds": 3600
  },
```

Replace `campaigns/examples/rotated-surface-baseline/search_space.json` with:

```json
{
  "campaign_id": "rotated-surface-baseline",
  "mode": "explicit_list",
  "candidate_specs": [
    {
      "candidate_id": "rotated-surface-d3-example",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 3,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "seed",
        "label": "repo-example"
      }
    },
    {
      "candidate_id": "rotated-surface-d3-repeat",
      "code_family": "rotated-surface-code",
      "parameters": {
        "distance": 3,
        "layout": "rotated"
      },
      "provenance": {
        "kind": "seed",
        "label": "repeat-for-run-loop"
      }
    }
  ]
}
```

- [ ] **Step 8: Run schema/source tests**

Run:

```bash
python3 -m pytest tests/test_search_eval_schemas.py tests/test_search_source_data.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit schema and source-data changes**

Run:

```bash
git add benchmarks/schemas/run-spec.schema.json benchmarks/schemas/candidate.schema.json benchmarks/schemas/result-manifest.schema.json campaigns/examples/rotated-surface-baseline/campaign.json campaigns/examples/rotated-surface-baseline/search_space.json tests/test_search_eval_schemas.py tests/test_search_source_data.py
git commit -m "feat: extend search schemas for autoresearch runs"
```

---

### Task 2: Resolve Explicit Campaign Candidate Specs

**Files:**
- Modify: `src/autoqec_search/eval_candidates.py`
- Modify: `tests/test_search_eval_candidates.py`
- Test: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Add failing resolver tests**

Append these tests to `tests/test_search_eval_candidates.py`:

```python
def test_resolve_campaign_candidate_spec_reuses_zoo_instance_for_repeat_candidate() -> None:
    workspace = load_search_workspace(REPO_ROOT)
    repeat_spec = workspace.search_spaces["rotated-surface-baseline"]["candidate_specs"][1]

    candidate = resolve_campaign_candidate_spec(
        REPO_ROOT,
        repeat_spec,
        campaign_id="rotated-surface-baseline",
    )

    assert candidate.spec.candidate_id == "rotated-surface-d3-repeat"
    assert candidate.spec.code_family == "rotated-surface-code"
    assert candidate.spec.parameters == {"distance": 3, "layout": "rotated"}
    assert candidate.artifact_root.name == "rotated-surface-code-d3"


def test_resolve_campaign_candidate_by_distance_uses_first_matching_spec() -> None:
    workspace = load_search_workspace(REPO_ROOT)

    candidate = resolve_campaign_candidate(
        REPO_ROOT,
        workspace,
        campaign_id="rotated-surface-baseline",
        distance=3,
    )

    assert candidate.spec.candidate_id == "rotated-surface-d3-example"
```

Update the import block in the same file to include the new function:

```python
from autoqec_search.eval_candidates import (
    copy_candidate_artifacts,
    resolve_campaign_candidate,
    resolve_campaign_candidate_spec,
    resolve_directory_candidate,
)
```

- [ ] **Step 2: Run the resolver tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_eval_candidates.py::test_resolve_campaign_candidate_spec_reuses_zoo_instance_for_repeat_candidate tests/test_search_eval_candidates.py::test_resolve_campaign_candidate_by_distance_uses_first_matching_spec -q
```

Expected: FAIL. `resolve_campaign_candidate_spec` is missing, and `resolve_campaign_candidate` rejects duplicate distance matches.

- [ ] **Step 3: Implement explicit spec resolution**

In `src/autoqec_search/eval_candidates.py`, add this public helper just above `resolve_campaign_candidate`:

```python
def resolve_campaign_candidate_spec(
    root: Path,
    candidate_spec: dict[str, Any],
    *,
    campaign_id: str,
) -> ResolvedCandidate:
    spec = _candidate_spec_from_search_space(candidate_spec, campaign_id)
    return _resolve_matching_zoo_instance(root, spec)
```

Then replace the duplicate-distance block in `resolve_campaign_candidate`:

```python
    if len(matching_specs) > 1:
        raise SearchIntegrityError(
            f"multiple candidates in campaign {campaign_id} have distance {distance}"
        )
    spec = _candidate_spec_from_search_space(matching_specs[0], campaign_id)
    return _resolve_matching_zoo_instance(root, spec)
```

with:

```python
    return resolve_campaign_candidate_spec(
        root,
        matching_specs[0],
        campaign_id=campaign_id,
    )
```

- [ ] **Step 4: Run resolver and eval regression tests**

Run:

```bash
python3 -m pytest tests/test_search_eval_candidates.py tests/test_search_eval_cli.py -q
```

Expected: PASS. The existing `eval --distance 3` CLI continues to evaluate `rotated-surface-d3-example`.

- [ ] **Step 5: Commit resolver changes**

Run:

```bash
git add src/autoqec_search/eval_candidates.py tests/test_search_eval_candidates.py
git commit -m "feat: resolve campaign candidates by explicit spec"
```

---

### Task 3: Extract A Candidate-Level Eval Helper

**Files:**
- Modify: `src/autoqec_search/eval_run.py`
- Modify: `tests/test_search_eval_cli.py`

- [ ] **Step 1: Add an eval regression that checks duplicate-distance search space still works**

In `tests/test_search_eval_cli.py`, add this assertion inside `test_eval_campaign_candidate_writes_completed_selected_manifest_and_plot`, after loading `run_spec`:

```python
    assert run_spec["candidate_ids"] == ["rotated-surface-d3-example"]
```

This pins the public `eval` behavior before the refactor.

- [ ] **Step 2: Add candidate evaluation result dataclass**

In `src/autoqec_search/eval_run.py`, after `EvalRunResult`, add:

```python
@dataclass(frozen=True)
class CandidateEvaluationResult:
    candidate_root: Path
    candidate_id: str
    distance: int
    structure: dict
    completed_manifests: list[dict]
    completed_by_decoder: dict[str, dict]
    selected_decoder_ids: list[str]
    selected_p_values: list[float]
    rsinter_version: str
```

- [ ] **Step 3: Extract helper function into `eval_run.py`**

Add this function above `evaluate_single_candidate`:

```python
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
) -> CandidateEvaluationResult:
    candidate_id = candidate.spec.candidate_id
    _validate_path_segment(candidate_id, label="candidate_id")
    copied_distance = _copied_instance_distance(candidate)
    rounds = rounds_for_task(task, distance=copied_distance)
    structure = summarize_css_structure(candidate.hx, candidate.hz)
    candidate_root = run_root / "candidates" / candidate_id

    if not structure["css_commute"]:
        _write_json(candidate_root / "structure.json", structure)
        raise SearchIntegrityError(f"candidate CSS checks do not commute: {candidate_id}")

    _write_json(
        candidate_root / "candidate.json",
        candidate_payload(candidate, run_id),
    )
    copy_candidate_artifacts(candidate, candidate_root)
    _write_json(candidate_root / "structure.json", structure)

    spec_path = candidate_root / "rsinter" / "spec.toml"
    out_dir = candidate_root / "rsinter" / "out"
    write_spec_toml(
        spec_path,
        task=task,
        decoders=workspace.decoders,
        selected_decoder_ids=selected_decoder_ids,
        distance=copied_distance,
        rounds=rounds,
        p_values=selected_p_values,
    )
    run_rsinter(spec_path, out_dir, executable=rsinter_executable)

    completed_manifests: list[dict] = []
    completed_by_decoder: dict[str, dict] = {}
    for decoder_id in selected_decoder_ids:
        points = parse_results_jsonl(
            out_dir / decoder_id / "test-run" / "results.jsonl",
            expected_decoder_id=decoder_id,
            expected_task_id=task["id"],
            expected_distance=copied_distance,
            expected_p_values=selected_p_values,
        )
        manifest = build_completed_manifest(
            campaign_id=campaign_id,
            run_id=run_id,
            candidate_id=candidate_id,
            task_id=task["id"],
            decoder_id=decoder_id,
            created_at=created_at,
            tool_revisions={
                "autoqec_search": __version__,
                "rsinter": rsinter_version,
            },
            points=points,
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
            copied_distance,
            task["id"],
            created_at,
            completed_manifests,
        ),
    )

    return CandidateEvaluationResult(
        candidate_root=candidate_root,
        candidate_id=candidate_id,
        distance=copied_distance,
        structure=structure,
        completed_manifests=completed_manifests,
        completed_by_decoder=completed_by_decoder,
        selected_decoder_ids=selected_decoder_ids,
        selected_p_values=selected_p_values,
        rsinter_version=rsinter_version,
    )
```

- [ ] **Step 4: Replace the duplicated body inside `evaluate_single_candidate`**

Inside `evaluate_single_candidate`, keep workspace loading, filters, candidate resolution, run-id selection, staging, and run-level file writes. Replace the candidate-level block from `candidate_root = stage_root / "candidates" / candidate_id` through the `candidate-plot.svg` write with:

```python
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
        )
        candidate_root = candidate_result.candidate_root
        completed_manifests = candidate_result.completed_manifests
        structure = candidate_result.structure
        copied_distance = candidate_result.distance
```

Remove the now-duplicated candidate-level local code from the old body.

- [ ] **Step 5: Run eval CLI tests**

Run:

```bash
python3 -m pytest tests/test_search_eval_cli.py tests/test_search_eval_candidates.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit eval helper refactor**

Run:

```bash
git add src/autoqec_search/eval_run.py tests/test_search_eval_cli.py
git commit -m "refactor: expose reusable candidate evaluation helper"
```

---

### Task 4: Add Notebook Renderers

**Files:**
- Create: `src/autoqec_search/run_render.py`
- Create: `tests/test_search_run_render.py`

- [ ] **Step 1: Add renderer tests**

Create `tests/test_search_run_render.py` with:

```python
from __future__ import annotations

import csv
import io

from autoqec_search.run_render import (
    ExperimentRow,
    FrontierItem,
    render_autoresearch_leaderboard,
    render_autoresearch_summary,
    render_experiment_log,
    render_frontier,
    render_run_summary_html,
)


def _rows() -> list[ExperimentRow]:
    return [
        ExperimentRow(
            candidate_id="rotated-surface-d3-example",
            ler=0.013,
            status="keep",
            description="entered frontier for distance 3",
        ),
        ExperimentRow(
            candidate_id="rotated-surface-d3-repeat",
            ler=0.02,
            status="discard",
            description="did not improve distance 3 frontier",
        ),
        ExperimentRow(
            candidate_id="rotated-surface-invalid-d1",
            ler=None,
            status="crash",
            description="no matching Zoo instance",
        ),
    ]


def _frontier() -> list[FrontierItem]:
    return [
        FrontierItem(
            candidate_id="rotated-surface-d3-example",
            distance=3,
            decoder_id="rmatching-default-v1",
            p=0.005,
            ler=0.013,
            manifest_path=(
                "candidates/rotated-surface-d3-example/evaluations/"
                "rotated-memory-x-cdep-v1/rmatching-default-v1/manifest.json"
            ),
        )
    ]


def test_render_experiment_log_uses_required_columns() -> None:
    text = render_experiment_log(_rows())

    assert text.splitlines()[0] == "candidate\tler\tstatus\tdescription"
    assert "rotated-surface-d3-example\t0.013\tkeep\tentered frontier for distance 3" in text
    assert "rotated-surface-invalid-d1\t\tcrash\tno matching Zoo instance" in text


def test_render_leaderboard_contains_only_keep_rows() -> None:
    text = render_autoresearch_leaderboard(_rows(), _frontier())
    rows = list(csv.reader(io.StringIO(text)))

    assert rows[0] == [
        "candidate_id",
        "distance",
        "decoder_id",
        "p",
        "ler",
        "status",
        "manifest_path",
    ]
    assert len(rows) == 2
    assert rows[1][0] == "rotated-surface-d3-example"
    assert rows[1][5] == "keep"


def test_render_frontier_returns_machine_readable_payload() -> None:
    payload = render_frontier(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        items=_frontier(),
    )

    assert payload["campaign_id"] == "rotated-surface-baseline"
    assert payload["run_id"] == "fixed-check"
    assert payload["items"][0]["distance"] == 3
    assert payload["items"][0]["candidate_id"] == "rotated-surface-d3-example"


def test_render_summary_and_html_escape_text() -> None:
    rows = [
        ExperimentRow(
            candidate_id='candidate <x> & "y"',
            ler=None,
            status="crash",
            description='failure <bad> & "quoted"',
        )
    ]

    summary = render_autoresearch_summary(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=rows,
        frontier=[],
    )
    html = render_run_summary_html(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        rows=rows,
        frontier=[],
    )

    assert "# Autoresearch Run Summary" in summary
    assert "- crashes: `1`" in summary
    assert "<!doctype html>" in html
    assert "candidate &lt;x&gt; &amp; &quot;y&quot;" in html
    assert "failure &lt;bad&gt; &amp; &quot;quoted&quot;" in html
    assert 'candidate <x> & "y"' not in html
```

- [ ] **Step 2: Run renderer tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_run_render.py -q
```

Expected: FAIL because `autoqec_search.run_render` does not exist.

- [ ] **Step 3: Implement `run_render.py`**

Create `src/autoqec_search/run_render.py` with:

```python
from __future__ import annotations

import csv
from dataclasses import dataclass
from html import escape
import io
from typing import Literal


Verdict = Literal["keep", "discard", "crash"]


@dataclass(frozen=True)
class ExperimentRow:
    candidate_id: str
    ler: float | None
    status: Verdict
    description: str


@dataclass(frozen=True)
class FrontierItem:
    candidate_id: str
    distance: int
    decoder_id: str
    p: float
    ler: float
    manifest_path: str


def _format_ler(value: float | None) -> str:
    if value is None:
        return ""
    return format(value, ".12g")


def render_experiment_log(rows: list[ExperimentRow]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(["candidate", "ler", "status", "description"])
    for row in rows:
        writer.writerow(
            [row.candidate_id, _format_ler(row.ler), row.status, row.description]
        )
    return output.getvalue()


def render_autoresearch_leaderboard(
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
) -> str:
    keep_ids = {row.candidate_id for row in rows if row.status == "keep"}
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "candidate_id",
            "distance",
            "decoder_id",
            "p",
            "ler",
            "status",
            "manifest_path",
        ]
    )
    for item in sorted(frontier, key=lambda value: (value.distance, value.candidate_id)):
        if item.candidate_id not in keep_ids:
            continue
        writer.writerow(
            [
                item.candidate_id,
                item.distance,
                item.decoder_id,
                item.p,
                _format_ler(item.ler),
                "keep",
                item.manifest_path,
            ]
        )
    return output.getvalue()


def render_frontier(
    *,
    campaign_id: str,
    run_id: str,
    items: list[FrontierItem],
) -> dict:
    return {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "items": [
            {
                "candidate_id": item.candidate_id,
                "distance": item.distance,
                "decoder_id": item.decoder_id,
                "p": item.p,
                "ler": item.ler,
                "manifest_path": item.manifest_path,
            }
            for item in sorted(items, key=lambda value: (value.distance, value.candidate_id))
        ],
    }


def _counts(rows: list[ExperimentRow]) -> dict[str, int]:
    return {
        "keep": sum(1 for row in rows if row.status == "keep"),
        "discard": sum(1 for row in rows if row.status == "discard"),
        "crash": sum(1 for row in rows if row.status == "crash"),
    }


def render_autoresearch_summary(
    *,
    campaign_id: str,
    run_id: str,
    tag: str,
    wall_clock_seconds: int,
    seed: int,
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
) -> str:
    counts = _counts(rows)
    lines = [
        "# Autoresearch Run Summary",
        "",
        f"- campaign: `{campaign_id}`",
        f"- run: `{run_id}`",
        f"- branch tag: `{tag}`",
        f"- wall_clock_seconds: `{wall_clock_seconds}`",
        f"- seed: `{seed}`",
        f"- candidates attempted: `{len(rows)}`",
        f"- keeps: `{counts['keep']}`",
        f"- discards: `{counts['discard']}`",
        f"- crashes: `{counts['crash']}`",
        "",
        "## Frontier",
        "",
    ]
    if not frontier:
        lines.append("- empty")
    else:
        for item in sorted(frontier, key=lambda value: (value.distance, value.candidate_id)):
            lines.append(
                "- "
                f"`{item.candidate_id}` d={item.distance} "
                f"{item.decoder_id} p={item.p} LER={_format_ler(item.ler)}"
            )
    lines.extend(["", "## Experiment Log", ""])
    for row in rows:
        ler = _format_ler(row.ler) if row.ler is not None else "n/a"
        lines.append(f"- `{row.status}` `{row.candidate_id}` LER={ler}: {row.description}")
    return "\n".join(lines).rstrip() + "\n"


def render_run_summary_html(
    *,
    campaign_id: str,
    run_id: str,
    tag: str,
    wall_clock_seconds: int,
    seed: int,
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
) -> str:
    counts = _counts(rows)
    timeline = "\n".join(
        "<tr>"
        f"<td>{escape(row.candidate_id)}</td>"
        f"<td class='{escape(row.status)}'>{escape(row.status)}</td>"
        f"<td>{escape(_format_ler(row.ler))}</td>"
        f"<td>{escape(row.description)}</td>"
        "</tr>"
        for row in rows
    )
    frontier_rows = "\n".join(
        "<tr>"
        f"<td>{escape(item.candidate_id)}</td>"
        f"<td>{item.distance}</td>"
        f"<td>{escape(item.decoder_id)}</td>"
        f"<td>{item.p}</td>"
        f"<td>{escape(_format_ler(item.ler))}</td>"
        f"<td><a href='{escape(item.manifest_path, quote=True)}'>manifest</a></td>"
        "</tr>"
        for item in sorted(frontier, key=lambda value: (value.distance, value.candidate_id))
    )
    if not timeline:
        timeline = "<tr><td colspan='4'>No candidates attempted.</td></tr>"
    if not frontier_rows:
        frontier_rows = "<tr><td colspan='6'>No kept candidates.</td></tr>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC autoresearch run {escape(run_id)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1200px; margin: 1rem 0; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.45rem 0.6rem; text-align: left; }}
    th {{ background: #eef2f6; }}
    .keep {{ color: #0f6b3d; font-weight: 700; }}
    .discard {{ color: #8a5a00; font-weight: 700; }}
    .crash {{ color: #a51d2d; font-weight: 700; }}
    .meta {{ display: grid; grid-template-columns: max-content 1fr; gap: 0.35rem 0.8rem; }}
  </style>
</head>
<body>
  <h1>AutoQEC Autoresearch Run</h1>
  <section class="meta">
    <strong>Campaign</strong><span>{escape(campaign_id)}</span>
    <strong>Run</strong><span>{escape(run_id)}</span>
    <strong>Branch tag</strong><span>{escape(tag)}</span>
    <strong>Wall clock seconds</strong><span>{wall_clock_seconds}</span>
    <strong>Seed</strong><span>{seed}</span>
    <strong>Verdicts</strong><span>{counts['keep']} keep, {counts['discard']} discard, {counts['crash']} crash</span>
  </section>
  <h2>Timeline</h2>
  <table>
    <thead><tr><th>Candidate</th><th>Status</th><th>LER</th><th>Description</th></tr></thead>
    <tbody>
{timeline}
    </tbody>
  </table>
  <h2>Running Leaderboard</h2>
  <table>
    <thead><tr><th>Candidate</th><th>Distance</th><th>Decoder</th><th>p</th><th>LER</th><th>Manifest</th></tr></thead>
    <tbody>
{frontier_rows}
    </tbody>
  </table>
</body>
</html>
"""
```

- [ ] **Step 4: Run renderer tests**

Run:

```bash
python3 -m pytest tests/test_search_run_render.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit renderers**

Run:

```bash
git add src/autoqec_search/run_render.py tests/test_search_run_render.py
git commit -m "feat: render autoresearch notebook artifacts"
```

---

### Task 5: Add Pure Run-Loop Helpers

**Files:**
- Create: `src/autoqec_search/run_loop.py`
- Create: `tests/test_search_run_loop.py`

- [ ] **Step 1: Add pure helper tests**

Create `tests/test_search_run_loop.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError
from autoqec_search.run_loop import (
    CandidateRecord,
    RunConfig,
    candidate_is_complete,
    choose_seed,
    default_tag,
    parse_wall_clock_seconds,
    representative_ler,
    update_frontier,
    validate_path_segment,
)
from autoqec_search.run_render import ExperimentRow


def _completed_manifest(candidate_id: str, ler: float = 0.013) -> dict:
    return {
        "campaign_id": "rotated-surface-baseline",
        "run_id": "fixed-check",
        "candidate_id": candidate_id,
        "task_id": "rotated-memory-x-cdep-v1",
        "decoder_id": "rmatching-default-v1",
        "status": "completed",
        "created_at": "2026-06-14T03:11:22Z",
        "tool_revisions": {"autoqec_search": "0.1.0", "rsinter": "fake"},
        "points": [
            {
                "p": 0.005,
                "rounds": 3,
                "shots": 1000,
                "errors": int(round(ler * 1000)),
                "ler": ler,
                "ci_low": max(0.0, ler / 2),
                "ci_high": min(1.0, ler * 2),
                "seconds": 0.01,
            }
        ],
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [("90", 90), ("90s", 90), ("5m", 300), ("1h", 3600)],
)
def test_parse_wall_clock_seconds_accepts_supported_forms(value: str, expected: int) -> None:
    assert parse_wall_clock_seconds(value) == expected


@pytest.mark.parametrize("value", ["0", "-1", "1d", "abc", "1.5m", ""])
def test_parse_wall_clock_seconds_rejects_invalid_forms(value: str) -> None:
    with pytest.raises(SearchIntegrityError):
        parse_wall_clock_seconds(value)


def test_choose_seed_prefers_cli_then_campaign_fixed_seed_then_zero() -> None:
    assert choose_seed(11, {"random_seed_policy": {"mode": "fixed", "seed": 7}}) == 11
    assert choose_seed(None, {"random_seed_policy": {"mode": "fixed", "seed": 7}}) == 7
    assert choose_seed(None, {"random_seed_policy": {"mode": "none", "seed": None}}) == 0


def test_default_tag_uses_campaign_timestamp_and_seed() -> None:
    assert (
        default_tag(
            campaign_id="rotated-surface-baseline",
            created_at="2026-06-14T03:11:22Z",
            seed=7,
        )
        == "rotated-surface-baseline-20260614T031122Z-seed7"
    )


@pytest.mark.parametrize("value", ["", ".", "..", "bad/name", "bad\\name", "bad\nname"])
def test_validate_path_segment_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(SearchIntegrityError):
        validate_path_segment(value, label="run_id")


def test_representative_ler_reads_primary_decoder_and_p() -> None:
    assert representative_ler(
        [_completed_manifest("candidate-a", ler=0.013)],
        decoder_id="rmatching-default-v1",
        p=0.005,
    ) == pytest.approx(0.013)


def test_update_frontier_keeps_first_and_discards_worse_same_distance() -> None:
    config = RunConfig(
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        wall_clock_seconds=90,
        seed=7,
        task_id="rotated-memory-x-cdep-v1",
        primary_decoder_id="rmatching-default-v1",
        representative_p=0.005,
    )
    first = CandidateRecord(
        candidate_id="rotated-surface-d3-example",
        distance=3,
        completed_manifests=[_completed_manifest("rotated-surface-d3-example", 0.013)],
    )
    second = CandidateRecord(
        candidate_id="rotated-surface-d3-repeat",
        distance=3,
        completed_manifests=[_completed_manifest("rotated-surface-d3-repeat", 0.02)],
    )

    frontier, first_row = update_frontier(config, [], first)
    frontier, second_row = update_frontier(config, frontier, second)

    assert first_row.status == "keep"
    assert second_row.status == "discard"
    assert [item.candidate_id for item in frontier] == ["rotated-surface-d3-example"]


def test_candidate_is_complete_requires_all_expected_manifests(tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidates" / "rotated-surface-d3-example"
    manifest_path = (
        candidate_root
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(_completed_manifest("rotated-surface-d3-example")) + "\n")

    assert candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )
    manifest_path.unlink()
    assert not candidate_is_complete(
        candidate_root,
        task_ids=["rotated-memory-x-cdep-v1"],
        decoder_ids=["rmatching-default-v1"],
    )
```

- [ ] **Step 2: Run pure helper tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_run_loop.py -q
```

Expected: FAIL because `autoqec_search.run_loop` does not exist.

- [ ] **Step 3: Implement pure helpers in `run_loop.py`**

Create `src/autoqec_search/run_loop.py` with these imports, dataclasses, and pure helpers:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from autoqec_search.load import SearchIntegrityError
from autoqec_search.run_render import ExperimentRow, FrontierItem


DURATION_RE = re.compile(r"^([1-9][0-9]*)([smh]?)$")


@dataclass(frozen=True)
class RunConfig:
    campaign_id: str
    run_id: str
    tag: str
    wall_clock_seconds: int
    seed: int
    task_id: str
    primary_decoder_id: str
    representative_p: float


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    distance: int
    completed_manifests: list[dict]


def parse_wall_clock_seconds(value: str) -> int:
    match = DURATION_RE.fullmatch(value)
    if match is None:
        raise SearchIntegrityError(f"invalid wall-clock duration: {value}")
    amount = int(match.group(1))
    suffix = match.group(2)
    multiplier = {"": 1, "s": 1, "m": 60, "h": 3600}[suffix]
    return amount * multiplier


def choose_seed(cli_seed: int | None, campaign: dict[str, Any]) -> int:
    if cli_seed is not None:
        return cli_seed
    policy = campaign.get("random_seed_policy")
    if isinstance(policy, dict) and policy.get("mode") == "fixed":
        seed = policy.get("seed")
        if isinstance(seed, int) and not isinstance(seed, bool):
            return seed
    return 0


def default_tag(*, campaign_id: str, created_at: str, seed: int) -> str:
    stamp = created_at.replace("-", "").replace(":", "").removesuffix("Z")
    return f"{campaign_id}-{stamp}-seed{seed}"


def validate_path_segment(value: str, *, label: str) -> None:
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def representative_ler(
    completed_manifests: list[dict],
    *,
    decoder_id: str,
    p: float,
) -> float:
    for manifest in completed_manifests:
        if manifest.get("decoder_id") != decoder_id:
            continue
        for point in manifest.get("points", []):
            if point.get("p") == p:
                ler = point.get("ler")
                if isinstance(ler, int | float) and not isinstance(ler, bool):
                    return float(ler)
    raise SearchIntegrityError(
        f"missing representative LER for decoder {decoder_id} at p={p}"
    )


def _manifest_path(candidate_id: str, task_id: str, decoder_id: str) -> str:
    return (
        f"candidates/{candidate_id}/evaluations/"
        f"{task_id}/{decoder_id}/manifest.json"
    )


def update_frontier(
    config: RunConfig,
    frontier: list[FrontierItem],
    candidate: CandidateRecord,
) -> tuple[list[FrontierItem], ExperimentRow]:
    ler = representative_ler(
        candidate.completed_manifests,
        decoder_id=config.primary_decoder_id,
        p=config.representative_p,
    )
    new_item = FrontierItem(
        candidate_id=candidate.candidate_id,
        distance=candidate.distance,
        decoder_id=config.primary_decoder_id,
        p=config.representative_p,
        ler=ler,
        manifest_path=_manifest_path(
            candidate.candidate_id,
            config.task_id,
            config.primary_decoder_id,
        ),
    )
    kept: list[FrontierItem] = []
    replaced = False
    for item in frontier:
        if item.distance != candidate.distance:
            kept.append(item)
            continue
        if ler < item.ler:
            kept.append(new_item)
            replaced = True
        else:
            kept.append(item)
            row = ExperimentRow(
                candidate_id=candidate.candidate_id,
                ler=ler,
                status="discard",
                description=f"did not improve distance {candidate.distance} frontier",
            )
            return sorted(kept, key=lambda value: (value.distance, value.candidate_id)), row
    if replaced or all(item.distance != candidate.distance for item in frontier):
        if not replaced:
            kept.append(new_item)
        row = ExperimentRow(
            candidate_id=candidate.candidate_id,
            ler=ler,
            status="keep",
            description=f"entered frontier for distance {candidate.distance}",
        )
        return sorted(kept, key=lambda value: (value.distance, value.candidate_id)), row
    raise SearchIntegrityError(f"frontier update failed for {candidate.candidate_id}")


def candidate_is_complete(
    candidate_root: Path,
    *,
    task_ids: list[str],
    decoder_ids: list[str],
) -> bool:
    for task_id in task_ids:
        for decoder_id in decoder_ids:
            manifest_path = (
                candidate_root
                / "evaluations"
                / task_id
                / decoder_id
                / "manifest.json"
            )
            if not manifest_path.is_file():
                return False
            try:
                payload = json.loads(manifest_path.read_text())
            except json.JSONDecodeError:
                return False
            if payload.get("status") not in {"completed", "placeholder", "crash"}:
                return False
    return True
```

- [ ] **Step 4: Run pure helper tests**

Run:

```bash
python3 -m pytest tests/test_search_run_loop.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit pure helpers**

Run:

```bash
git add src/autoqec_search/run_loop.py tests/test_search_run_loop.py
git commit -m "feat: add autoresearch run-loop helpers"
```

---

### Task 6: Add Git Worktree Helpers And Run Skeleton Creation

**Files:**
- Modify: `src/autoqec_search/run_loop.py`
- Modify: `tests/test_search_run_loop.py`

- [ ] **Step 1: Add git helper tests**

Append these tests to `tests/test_search_run_loop.py`:

```python
def test_git_status_porcelain_reports_clean_and_dirty_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "tracked.txt").write_text("tracked\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)

    from autoqec_search.run_loop import git_status_porcelain

    assert git_status_porcelain(repo) == ""
    (repo / "tracked.txt").write_text("dirty\n")
    assert "tracked.txt" in git_status_porcelain(repo)


def test_write_run_skeleton_writes_autoresearch_metadata(tmp_path: Path) -> None:
    from autoqec_search.run_loop import write_run_skeleton

    run_root = tmp_path / "results" / "search" / "rotated-surface-baseline" / "fixed-check"
    run_spec = write_run_skeleton(
        run_root=run_root,
        campaign_id="rotated-surface-baseline",
        run_id="fixed-check",
        tag="fixed-check",
        suite={"id": "rotated-surface-baseline-v1", "task_ids": ["rotated-memory-x-cdep-v1"], "decoder_ids": ["rmatching-default-v1"]},
        candidate_ids=["rotated-surface-d3-example"],
        created_at="2026-06-14T03:11:22Z",
        wall_clock_seconds=90,
        seed=7,
        env={"tool": "autoqec-search", "mode": "autoresearch"},
    )

    assert run_spec["mode"] == "autoresearch"
    assert run_spec["tag"] == "fixed-check"
    assert (run_root / "run_spec.json").is_file()
    assert (run_root / "env.json").is_file()
```

- [ ] **Step 2: Run the git helper tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_search_run_loop.py::test_git_status_porcelain_reports_clean_and_dirty_repo tests/test_search_run_loop.py::test_write_run_skeleton_writes_autoresearch_metadata -q
```

Expected: FAIL because the new helpers do not exist.

- [ ] **Step 3: Add subprocess and file helpers**

Append this code to `src/autoqec_search/run_loop.py`:

```python
def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SearchIntegrityError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def git_status_porcelain(root: Path) -> str:
    return run_git(root, "status", "--porcelain")


def git_head_sha(root: Path) -> str:
    return run_git(root, "rev-parse", "HEAD")


def git_branch_exists(root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", branch],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def git_commit_all(root: Path, message: str) -> bool:
    run_git(root, "add", "-A")
    if git_status_porcelain(root) == "":
        return False
    run_git(root, "commit", "-m", message)
    return True


def write_run_skeleton(
    *,
    run_root: Path,
    campaign_id: str,
    run_id: str,
    tag: str,
    suite: dict,
    candidate_ids: list[str],
    created_at: str,
    wall_clock_seconds: int,
    seed: int,
    env: dict,
) -> dict:
    run_spec = {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "suite_id": suite["id"],
        "task_ids": suite["task_ids"],
        "decoder_ids": suite["decoder_ids"],
        "candidate_ids": candidate_ids,
        "created_at": created_at,
        "mode": "autoresearch",
        "tag": tag,
        "wall_clock_seconds": wall_clock_seconds,
        "seed": seed,
    }
    _write_json(run_root / "run_spec.json", run_spec)
    _write_json(run_root / "env.json", env)
    return run_spec
```

- [ ] **Step 4: Run run-loop unit tests**

Run:

```bash
python3 -m pytest tests/test_search_run_loop.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit git helpers**

Run:

```bash
git add src/autoqec_search/run_loop.py tests/test_search_run_loop.py
git commit -m "feat: add autoresearch git skeleton helpers"
```

---

### Task 7: Implement The Autoresearch Loop

**Files:**
- Modify: `src/autoqec_search/run_loop.py`
- Create: `tests/test_search_run_cli.py`

- [ ] **Step 1: Create CLI test utilities**

Create `tests/test_search_run_cli.py` with the imports and helpers below:

```python
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_repo(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(
        REPO_ROOT,
        work_root,
        ignore=shutil.ignore_patterns(".git", ".worktrees", "__pycache__", "*.pyc"),
    )
    subprocess.run(["git", "init"], cwd=work_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=work_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=work_root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=work_root, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=work_root, check=True, capture_output=True, text=True)
    return work_root


def _write_fake_rsinter(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "rsinter"
    executable.write_text(
        f"""#!{sys.executable}
import json
import sys
from pathlib import Path
import tomllib

if sys.argv[1:] == ["--version"]:
    print("rsinter fake run-loop")
    raise SystemExit(0)

args = sys.argv[1:]
spec_path = Path(args[args.index("--spec") + 1])
out_dir = Path(args[args.index("--out") + 1])
spec = tomllib.loads(spec_path.read_text())
candidate_id = spec_path.parents[1].name
for runner in spec.get("runner", []):
    decoder_id = runner["name"]
    params = runner["params"]
    results_dir = out_dir / decoder_id / "test-run"
    results_dir.mkdir(parents=True, exist_ok=True)
    records = []
    distance = int(params["distance"][0])
    rounds = int(params["rounds"][0])
    for p in params["p"]:
        p = float(p)
        shots = 1000
        errors = 13
        if candidate_id.endswith("repeat"):
            errors = 20
        records.append(json.dumps(
            {{
                "benchmark": spec["name"],
                "runner": decoder_id,
                "language": runner["language"],
                "status": "ok",
                "params": {{"distance": distance, "rounds": rounds, "p": p}},
                "metrics": {{
                    "shots_used": shots,
                    "logical_errors": errors,
                    "logical_error_rate": errors / shots,
                    "decode_us_per_shot": 10.0,
                }},
            }},
            sort_keys=True,
        ))
    (results_dir / "results.jsonl").write_text("\\n".join(records) + "\\n")
raise SystemExit(0)
"""
    )
    executable.chmod(0o755)
    return bin_dir


def _env(bin_dir: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }


def _run_autoresearch(work_root: Path, env: dict[str, str], *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
    )
```

- [ ] **Step 2: Add a failing end-to-end keep/discard test**

Append this test to `tests/test_search_run_cli.py`:

```python
def test_run_creates_worktree_branch_and_lab_notebook(tmp_path: Path) -> None:
    work_root = _copy_repo(tmp_path)
    env = _env(_write_fake_rsinter(tmp_path))

    result = _run_autoresearch(
        work_root,
        env,
        "--wall-clock",
        "90s",
        "--run-id",
        "fixed-check",
    )

    assert result.returncode == 0, result.stderr
    assert "autoresearch/fixed-check" in result.stdout
    assert subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout == ""

    worktree = work_root / ".worktrees" / "fixed-check"
    run_root = worktree / "results" / "search" / "rotated-surface-baseline" / "fixed-check"
    assert run_root.is_dir()
    assert (run_root / "run-summary.html").is_file()

    log = (run_root / "experiment-log.tsv").read_text()
    assert "rotated-surface-d3-example\t0.013\tkeep\t" in log
    assert "rotated-surface-d3-repeat\t0.02\tdiscard\t" in log

    leaderboard = (run_root / "leaderboard.csv").read_text()
    assert "rotated-surface-d3-example" in leaderboard
    assert "rotated-surface-d3-repeat" not in leaderboard

    branch_log = subprocess.run(
        ["git", "log", "--oneline", "autoresearch/fixed-check"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "start autoresearch run fixed-check" in branch_log
    assert "evaluate rotated-surface-d3-example" in branch_log
    assert "evaluate rotated-surface-d3-repeat" in branch_log
```

- [ ] **Step 3: Run the CLI test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py::test_run_creates_worktree_branch_and_lab_notebook -q
```

Expected: FAIL because the `run` command and orchestration function do not exist.

- [ ] **Step 4: Add orchestration imports**

At the top of `src/autoqec_search/run_loop.py`, add:

```python
import os
import socket
import time

from autoqec_search import __version__
from autoqec_search.eval_candidates import resolve_campaign_candidate_spec
from autoqec_search.eval_run import (
    _load_eval_workspace,
    _single_task,
    evaluate_resolved_candidate_into_run,
)
from autoqec_search.rsinter import require_rsinter
from autoqec_search.run_render import (
    render_autoresearch_leaderboard,
    render_autoresearch_summary,
    render_experiment_log,
    render_frontier,
    render_run_summary_html,
)
```

- [ ] **Step 5: Add worktree setup and environment helpers**

Append this code to `src/autoqec_search/run_loop.py`:

```python
def effective_wall_clock_seconds(campaign: dict, cli_value: str | None) -> int:
    if cli_value is not None:
        return parse_wall_clock_seconds(cli_value)
    budget = campaign.get("budget")
    if isinstance(budget, dict) and isinstance(budget.get("wall_clock_seconds"), int):
        return int(budget["wall_clock_seconds"])
    stop_conditions = campaign.get("stop_conditions")
    if isinstance(stop_conditions, dict) and isinstance(
        stop_conditions.get("max_wall_clock_seconds"), int
    ):
        return int(stop_conditions["max_wall_clock_seconds"])
    raise SearchIntegrityError("missing wall-clock budget")


def create_or_resume_worktree(
    *,
    root: Path,
    tag: str,
    resume: bool,
    allow_dirty_root: bool,
) -> tuple[Path, str]:
    branch = f"autoresearch/{tag}"
    worktree_root = root / ".worktrees" / tag
    if not resume and git_branch_exists(root, branch):
        raise SearchIntegrityError(f"branch already exists: {branch}")
    if not resume and not allow_dirty_root and git_status_porcelain(root):
        raise SearchIntegrityError("root working tree is dirty")
    if resume:
        if not git_branch_exists(root, branch):
            raise SearchIntegrityError(f"missing branch for resume: {branch}")
        if not worktree_root.exists():
            worktree_root.parent.mkdir(parents=True, exist_ok=True)
            run_git(root, "worktree", "add", str(worktree_root), branch)
        return worktree_root, branch
    worktree_root.parent.mkdir(parents=True, exist_ok=True)
    run_git(root, "worktree", "add", "-b", branch, str(worktree_root), "HEAD")
    return worktree_root, branch


def build_env(
    *,
    root: Path,
    branch: str,
    created_at: str,
    seed: int,
    wall_clock_seconds: int,
    rsinter_version: str,
) -> dict:
    return {
        "tool": "autoqec-search",
        "version": __version__,
        "generated_at": created_at,
        "mode": "autoresearch",
        "git_sha": git_head_sha(root),
        "branch": branch,
        "host": socket.gethostname(),
        "seed": seed,
        "wall_clock_seconds": wall_clock_seconds,
        "rsinter": rsinter_version,
    }
```

- [ ] **Step 6: Add aggregate file writer**

Append:

```python
def write_aggregates(
    *,
    run_root: Path,
    config: RunConfig,
    rows: list[ExperimentRow],
    frontier: list[FrontierItem],
) -> None:
    _write_text(run_root / "experiment-log.tsv", render_experiment_log(rows))
    _write_text(
        run_root / "leaderboard.csv",
        render_autoresearch_leaderboard(rows, frontier),
    )
    _write_json(
        run_root / "frontier.json",
        render_frontier(
            campaign_id=config.campaign_id,
            run_id=config.run_id,
            items=frontier,
        ),
    )
    _write_text(
        run_root / "summary.md",
        render_autoresearch_summary(
            campaign_id=config.campaign_id,
            run_id=config.run_id,
            tag=config.tag,
            wall_clock_seconds=config.wall_clock_seconds,
            seed=config.seed,
            rows=rows,
            frontier=frontier,
        ),
    )
    _write_text(
        run_root / "run-summary.html",
        render_run_summary_html(
            campaign_id=config.campaign_id,
            run_id=config.run_id,
            tag=config.tag,
            wall_clock_seconds=config.wall_clock_seconds,
            seed=config.seed,
            rows=rows,
            frontier=frontier,
        ),
    )
```

- [ ] **Step 7: Add existing-outcome and crash artifact helpers**

Append:

```python
def load_existing_candidate_outcome(
    *,
    config: RunConfig,
    candidate_root: Path,
    decoder_ids: list[str],
) -> tuple[ExperimentRow, CandidateRecord | None]:
    primary_manifest_path = (
        candidate_root
        / "evaluations"
        / config.task_id
        / config.primary_decoder_id
        / "manifest.json"
    )
    primary_manifest = json.loads(primary_manifest_path.read_text())
    candidate_id = primary_manifest["candidate_id"]
    if primary_manifest.get("status") == "crash":
        return (
            ExperimentRow(
                candidate_id=candidate_id,
                ler=None,
                status="crash",
                description=str(primary_manifest.get("error", "candidate crashed")),
            ),
            None,
        )

    distance_payload = json.loads((candidate_root / "distance.json").read_text())
    distance = distance_payload.get("distance")
    if type(distance) is not int or distance <= 0:
        raise SearchIntegrityError(f"invalid completed distance for {candidate_id}")
    completed_manifests: list[dict] = []
    for decoder_id in decoder_ids:
        manifest_path = (
            candidate_root
            / "evaluations"
            / config.task_id
            / decoder_id
            / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") == "completed":
            completed_manifests.append(manifest)
    if not completed_manifests:
        raise SearchIntegrityError(f"completed candidate has no completed manifests: {candidate_id}")
    return (
        ExperimentRow(
            candidate_id=candidate_id,
            ler=representative_ler(
                completed_manifests,
                decoder_id=config.primary_decoder_id,
                p=config.representative_p,
            ),
            status="keep",
            description=f"reloaded completed candidate {candidate_id}",
        ),
        CandidateRecord(
            candidate_id=candidate_id,
            distance=distance,
            completed_manifests=completed_manifests,
        ),
    )


def write_crash_candidate(
    *,
    run_root: Path,
    campaign_id: str,
    run_id: str,
    candidate_spec: dict,
    task_ids: list[str],
    decoder_ids: list[str],
    created_at: str,
    error: str,
) -> None:
    candidate_id = str(candidate_spec.get("candidate_id", "unknown-candidate"))
    candidate_root = run_root / "candidates" / candidate_id
    payload = {
        "candidate_id": candidate_id,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "code_family": str(candidate_spec.get("code_family", "unknown-code-family")),
        "parameters": candidate_spec.get("parameters")
        if isinstance(candidate_spec.get("parameters"), dict)
        else {"invalid": True},
        "provenance": candidate_spec.get("provenance")
        if isinstance(candidate_spec.get("provenance"), dict)
        else {"kind": "invalid", "label": "invalid-candidate"},
        "status": "crashed",
    }
    _write_json(candidate_root / "candidate.json", payload)
    _write_json(candidate_root / "structure.json", {"status": "crash", "error": error})
    _write_json(candidate_root / "distance.json", {"status": "crash", "distance": None, "error": error})
    for task_id in task_ids:
        for decoder_id in decoder_ids:
            _write_json(
                candidate_root / "evaluations" / task_id / decoder_id / "manifest.json",
                {
                    "campaign_id": campaign_id,
                    "run_id": run_id,
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "decoder_id": decoder_id,
                    "status": "crash",
                    "created_at": created_at,
                    "error": error,
                },
            )
```

- [ ] **Step 8: Implement `run_autoresearch`**

Append:

```python
def run_autoresearch(
    root: Path,
    *,
    campaign_id: str,
    wall_clock: str | None,
    seed: int | None,
    run_id: str | None,
    resume: bool,
    cleanup_worktree: bool,
    allow_dirty_root: bool,
) -> Path:
    workspace = _load_eval_workspace(root)
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")
    campaign = workspace.campaigns[campaign_id]
    suite = workspace.suites[campaign["default_suite_id"]]
    task = _single_task(suite, workspace.tasks)
    created_at = utc_now()
    actual_seed = choose_seed(seed, campaign)
    tag = run_id or default_tag(
        campaign_id=campaign_id,
        created_at=created_at,
        seed=actual_seed,
    )
    validate_path_segment(tag, label="run_id")
    actual_run_id = tag
    wall_clock_seconds = effective_wall_clock_seconds(campaign, wall_clock)
    candidate_specs = workspace.search_spaces[campaign_id]["candidate_specs"]
    max_candidates = int(campaign["stop_conditions"]["max_candidates"])
    selected_specs = candidate_specs[:max_candidates]
    candidate_ids = [str(spec["candidate_id"]) for spec in selected_specs]
    primary_decoder_id = suite["decoder_ids"][0]
    representative_p = float(task["p_list"][0])

    worktree_root, branch = create_or_resume_worktree(
        root=root,
        tag=tag,
        resume=resume,
        allow_dirty_root=allow_dirty_root,
    )
    run_root = worktree_root / "results" / "search" / campaign_id / actual_run_id
    config = RunConfig(
        campaign_id=campaign_id,
        run_id=actual_run_id,
        tag=tag,
        wall_clock_seconds=wall_clock_seconds,
        seed=actual_seed,
        task_id=task["id"],
        primary_decoder_id=primary_decoder_id,
        representative_p=representative_p,
    )

    rsinter_executable, rsinter_version = require_rsinter()
    if not resume:
        env = build_env(
            root=root,
            branch=branch,
            created_at=created_at,
            seed=actual_seed,
            wall_clock_seconds=wall_clock_seconds,
            rsinter_version=rsinter_version,
        )
        write_run_skeleton(
            run_root=run_root,
            campaign_id=campaign_id,
            run_id=actual_run_id,
            tag=tag,
            suite=suite,
            candidate_ids=candidate_ids,
            created_at=created_at,
            wall_clock_seconds=wall_clock_seconds,
            seed=actual_seed,
            env=env,
        )
        write_aggregates(run_root=run_root, config=config, rows=[], frontier=[])
        git_commit_all(worktree_root, f"start autoresearch run {actual_run_id}")

    rows: list[ExperimentRow] = []
    frontier: list[FrontierItem] = []
    started = time.monotonic()
    for candidate_spec in selected_specs:
        candidate_id = str(candidate_spec["candidate_id"])
        candidate_root = run_root / "candidates" / candidate_id
        if resume and candidate_is_complete(
            candidate_root,
            task_ids=suite["task_ids"],
            decoder_ids=suite["decoder_ids"],
        ):
            existing_row, existing_record = load_existing_candidate_outcome(
                config=config,
                candidate_root=candidate_root,
                decoder_ids=suite["decoder_ids"],
            )
            if existing_record is None:
                rows.append(existing_row)
            else:
                frontier, row = update_frontier(config, frontier, existing_record)
                rows.append(row)
            continue
        if time.monotonic() - started >= wall_clock_seconds:
            break
        try:
            candidate = resolve_campaign_candidate_spec(
                worktree_root,
                candidate_spec,
                campaign_id=campaign_id,
            )
            result = evaluate_resolved_candidate_into_run(
                run_root=run_root,
                run_id=actual_run_id,
                campaign_id=campaign_id,
                candidate=candidate,
                workspace=workspace,
                suite=suite,
                task=task,
                selected_decoder_ids=suite["decoder_ids"],
                selected_p_values=[representative_p],
                created_at=utc_now(),
                rsinter_executable=rsinter_executable,
                rsinter_version=rsinter_version,
            )
            frontier, row = update_frontier(
                config,
                frontier,
                CandidateRecord(
                    candidate_id=result.candidate_id,
                    distance=result.distance,
                    completed_manifests=result.completed_manifests,
                ),
            )
        except Exception as exc:
            message = str(exc)
            write_crash_candidate(
                run_root=run_root,
                campaign_id=campaign_id,
                run_id=actual_run_id,
                candidate_spec=candidate_spec,
                task_ids=suite["task_ids"],
                decoder_ids=suite["decoder_ids"],
                created_at=utc_now(),
                error=message,
            )
            row = ExperimentRow(
                candidate_id=candidate_id,
                ler=None,
                status="crash",
                description=message,
            )
        rows.append(row)
        write_aggregates(run_root=run_root, config=config, rows=rows, frontier=frontier)
        git_commit_all(worktree_root, f"evaluate {candidate_id}")

    write_aggregates(run_root=run_root, config=config, rows=rows, frontier=frontier)
    git_commit_all(worktree_root, f"finalize autoresearch run {actual_run_id}")
    if cleanup_worktree:
        run_git(root, "worktree", "remove", str(worktree_root))
    return run_root
```

- [ ] **Step 9: Run the CLI test and verify it still fails at the parser**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py::test_run_creates_worktree_branch_and_lab_notebook -q
```

Expected: FAIL because `autoqec-search run` is not wired into `cli.py`.

- [ ] **Step 10: Do not commit yet**

Leave these changes uncommitted. Task 8 wires the CLI and commits a passing slice.

---

### Task 8: Wire The CLI Command

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_run_cli.py`

- [ ] **Step 1: Import the orchestrator**

Add this import to `src/autoqec_search/cli.py`:

```python
from autoqec_search.run_loop import run_autoresearch
```

- [ ] **Step 2: Add parser arguments**

In `build_parser()`, after the `eval` parser, add:

```python
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
```

- [ ] **Step 3: Add command handling**

In `main()`, after the `eval` command block and before `show`, add:

```python
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
            )
            branch = f"autoresearch/{run_root.name}"
            print(f"completed autoresearch run on {branch} at {run_root}")
            return 0
```

- [ ] **Step 4: Run the first CLI test**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py::test_run_creates_worktree_branch_and_lab_notebook -q
```

Expected: PASS.

- [ ] **Step 5: Commit CLI and loop**

Run:

```bash
git add src/autoqec_search/run_loop.py src/autoqec_search/cli.py tests/test_search_run_cli.py
git commit -m "feat: add autoresearch run command"
```

---

### Task 9: Add Crash, Resume, Budget, And Cleanup CLI Coverage

**Files:**
- Modify: `tests/test_search_run_cli.py`
- Modify: `src/autoqec_search/run_loop.py`

- [ ] **Step 1: Add crash-tolerant negative control test**

Append:

```python
def test_run_logs_crash_and_continues_other_candidates(tmp_path: Path) -> None:
    work_root = _copy_repo(tmp_path)
    search_space_path = (
        work_root
        / "campaigns"
        / "examples"
        / "rotated-surface-baseline"
        / "search_space.json"
    )
    payload = json.loads(search_space_path.read_text())
    payload["candidate_specs"].insert(
        1,
        {
            "candidate_id": "rotated-surface-invalid-d1",
            "code_family": "rotated-surface-code",
            "parameters": {"distance": 1, "layout": "rotated"},
            "provenance": {"kind": "test", "label": "invalid-distance"},
        },
    )
    search_space_path.write_text(json.dumps(payload, indent=2) + "\n")
    campaign_path = (
        work_root
        / "campaigns"
        / "examples"
        / "rotated-surface-baseline"
        / "campaign.json"
    )
    campaign = json.loads(campaign_path.read_text())
    campaign["budget"]["max_candidates"] = 3
    campaign["stop_conditions"]["max_candidates"] = 3
    campaign_path.write_text(json.dumps(campaign, indent=2) + "\n")
    subprocess.run(["git", "add", "-A"], cwd=work_root, check=True)
    subprocess.run(["git", "commit", "-m", "add invalid test candidate"], cwd=work_root, check=True, capture_output=True, text=True)

    result = _run_autoresearch(
        work_root,
        _env(_write_fake_rsinter(tmp_path)),
        "--wall-clock",
        "90s",
        "--run-id",
        "crash-check",
    )

    assert result.returncode == 0, result.stderr
    run_root = work_root / ".worktrees" / "crash-check" / "results" / "search" / "rotated-surface-baseline" / "crash-check"
    log = (run_root / "experiment-log.tsv").read_text()
    assert "rotated-surface-invalid-d1\t\tcrash\t" in log
    assert "rotated-surface-d3-repeat\t0.02\tdiscard\t" in log
```

- [ ] **Step 2: Add resume recomputes one missing candidate test**

Append:

```python
def test_run_resume_recomputes_candidate_with_missing_manifest(tmp_path: Path) -> None:
    work_root = _copy_repo(tmp_path)
    env = _env(_write_fake_rsinter(tmp_path))
    first = _run_autoresearch(
        work_root,
        env,
        "--wall-clock",
        "90s",
        "--run-id",
        "resume-check",
    )
    assert first.returncode == 0, first.stderr
    manifest = (
        work_root
        / ".worktrees"
        / "resume-check"
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "resume-check"
        / "candidates"
        / "rotated-surface-d3-repeat"
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "rmatching-default-v1"
        / "manifest.json"
    )
    manifest.unlink()
    subprocess.run(["git", "add", "-A"], cwd=work_root / ".worktrees" / "resume-check", check=True)
    subprocess.run(["git", "commit", "-m", "remove one manifest"], cwd=work_root / ".worktrees" / "resume-check", check=True, capture_output=True, text=True)

    second = _run_autoresearch(
        work_root,
        env,
        "--wall-clock",
        "90s",
        "--run-id",
        "resume-check",
        "--resume",
    )

    assert second.returncode == 0, second.stderr
    assert manifest.is_file()
    branch_log = subprocess.run(
        ["git", "log", "--oneline", "autoresearch/resume-check"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert branch_log.count("evaluate rotated-surface-d3-repeat") == 2
    assert branch_log.count("evaluate rotated-surface-d3-example") == 1
```

- [ ] **Step 3: Add tiny-budget and cleanup tests**

Append:

```python
def test_run_tiny_budget_writes_summary(tmp_path: Path) -> None:
    work_root = _copy_repo(tmp_path)
    result = _run_autoresearch(
        work_root,
        _env(_write_fake_rsinter(tmp_path)),
        "--wall-clock",
        "1s",
        "--run-id",
        "tiny-budget",
    )

    assert result.returncode == 0, result.stderr
    run_root = work_root / ".worktrees" / "tiny-budget" / "results" / "search" / "rotated-surface-baseline" / "tiny-budget"
    assert (run_root / "summary.md").is_file()
    assert (run_root / "run-summary.html").is_file()


def test_run_cleanup_worktree_leaves_branch(tmp_path: Path) -> None:
    work_root = _copy_repo(tmp_path)
    result = _run_autoresearch(
        work_root,
        _env(_write_fake_rsinter(tmp_path)),
        "--wall-clock",
        "90s",
        "--run-id",
        "cleanup-check",
        "--cleanup-worktree",
    )

    assert result.returncode == 0, result.stderr
    assert not (work_root / ".worktrees" / "cleanup-check").exists()
    branches = subprocess.run(
        ["git", "branch", "--list", "autoresearch/cleanup-check"],
        cwd=work_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "autoresearch/cleanup-check" in branches
```

- [ ] **Step 4: Run the new CLI tests**

Run:

```bash
python3 -m pytest tests/test_search_run_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit negative controls**

Run:

```bash
git add src/autoqec_search/run_loop.py tests/test_search_run_cli.py
git commit -m "test: cover autoresearch crash resume and cleanup"
```

---

### Task 10: Update Loader Validation For Autoresearch Runs

**Files:**
- Modify: `src/autoqec_search/load.py`
- Modify: `tests/test_search_load.py`

- [ ] **Step 1: Add load test for autoresearch run**

Append to `tests/test_search_load.py`:

```python
def test_load_search_workspace_accepts_autoresearch_run_with_crash_manifest(
    tmp_path: Path,
) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "autoresearch-example"
    candidate_root = run_root / "candidates" / "rotated-surface-invalid-d1"
    run_root.mkdir(parents=True)
    (run_root / "run_spec.json").write_text(json.dumps({
        "campaign_id": "rotated-surface-baseline",
        "run_id": "autoresearch-example",
        "suite_id": "rotated-surface-baseline-v1",
        "task_ids": ["rotated-memory-x-cdep-v1"],
        "decoder_ids": ["rmatching-default-v1", "rbposd-default-v1", "rilpqec-default-v1"],
        "candidate_ids": ["rotated-surface-invalid-d1"],
        "created_at": "2026-06-14T03:11:22Z",
        "mode": "autoresearch",
        "tag": "autoresearch-example",
        "wall_clock_seconds": 90,
        "seed": 7,
    }, indent=2) + "\n")
    (run_root / "env.json").write_text("{}\n")
    (run_root / "frontier.json").write_text(json.dumps({"campaign_id": "rotated-surface-baseline", "run_id": "autoresearch-example", "items": []}) + "\n")
    (run_root / "leaderboard.csv").write_text("candidate_id,distance,decoder_id,p,ler,status,manifest_path\n")
    (run_root / "summary.md").write_text("# Summary\n")
    (run_root / "experiment-log.tsv").write_text("candidate\tler\tstatus\tdescription\nrotated-surface-invalid-d1\t\tcrash\tbad\n")
    (run_root / "run-summary.html").write_text("<!doctype html><html></html>\n")
    (candidate_root / "candidate.json").parent.mkdir(parents=True)
    (candidate_root / "candidate.json").write_text(json.dumps({
        "candidate_id": "rotated-surface-invalid-d1",
        "campaign_id": "rotated-surface-baseline",
        "run_id": "autoresearch-example",
        "code_family": "rotated-surface-code",
        "parameters": {"distance": 1, "layout": "rotated"},
        "provenance": {"kind": "test", "label": "invalid-distance"},
        "status": "crashed",
    }, indent=2) + "\n")
    (candidate_root / "structure.json").write_text(json.dumps({"status": "crash", "error": "bad"}) + "\n")
    (candidate_root / "distance.json").write_text(json.dumps({"status": "crash", "distance": None, "error": "bad"}) + "\n")
    for decoder_id in ["rmatching-default-v1", "rbposd-default-v1", "rilpqec-default-v1"]:
        manifest_path = candidate_root / "evaluations" / "rotated-memory-x-cdep-v1" / decoder_id / "manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps({
            "campaign_id": "rotated-surface-baseline",
            "run_id": "autoresearch-example",
            "candidate_id": "rotated-surface-invalid-d1",
            "task_id": "rotated-memory-x-cdep-v1",
            "decoder_id": decoder_id,
            "status": "crash",
            "created_at": "2026-06-14T03:11:22Z",
            "error": "bad",
        }, indent=2) + "\n")

    workspace = load_search_workspace(work_root)

    loaded = workspace.runs["rotated-surface-baseline/autoresearch-example"]
    assert loaded.payload["mode"] == "autoresearch"
    assert loaded.candidates["rotated-surface-invalid-d1"].payload["status"] == "crashed"
```

- [ ] **Step 2: Run load test**

Run:

```bash
python3 -m pytest tests/test_search_load.py::test_load_search_workspace_accepts_autoresearch_run_with_crash_manifest -q
```

Expected: PASS after Task 1 schema changes. If it fails because `load_search_run` requires only the existing common files, add a conditional check for autoresearch-only files:

```python
    if payload["mode"] == "autoresearch":
        _require_file(run_root / "experiment-log.tsv", "experiment log")
        _require_file(run_root / "run-summary.html", "run summary html")
```

- [ ] **Step 3: Run load suite**

Run:

```bash
python3 -m pytest tests/test_search_load.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit loader coverage**

Run:

```bash
git add src/autoqec_search/load.py tests/test_search_load.py
git commit -m "test: validate autoresearch run loading"
```

---

### Task 11: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_search_docs.py`

- [ ] **Step 1: Add failing docs assertions**

Append this test to `tests/test_search_docs.py`:

```python
def test_docs_mention_autoresearch_run_command() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "autoqec-search run" in readme
    assert "--wall-clock 90s" in readme
    assert "autoresearch/" in readme
    assert ".worktrees/" in readme

    assert "autoqec-search run" in claude
    assert "--cleanup-worktree" in claude
    assert "autoresearch/" in claude
```

- [ ] **Step 2: Run docs test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_search_docs.py::test_docs_mention_autoresearch_run_command -q
```

Expected: FAIL because docs do not mention the new command.

- [ ] **Step 3: Update README Search Layer section**

In `README.md`, after the existing `autoqec-search eval` example, add:

```markdown
Run a time-bounded autoresearch loop in an isolated git worktree:

```bash
python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 90s
```

The run command creates a local branch `autoresearch/<tag>` and a worktree
under `.worktrees/<tag>`, writes `experiment-log.tsv`, `leaderboard.csv`,
`frontier.json`, `summary.md`, and `run-summary.html`, and commits the lab
notebook on that branch. Nothing is pushed. Add `--cleanup-worktree` to remove
the local worktree after the final commit while keeping the branch.
```

- [ ] **Step 4: Update CLAUDE Search Layer section**

In `CLAUDE.md`, after the issue #9 command block, add:

```markdown
For issue `#10` and the time-bounded autoresearch loop, use:

```sh
python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 90s
```

The command creates a local worktree at `.worktrees/<tag>` and commits the
reviewable lab notebook on branch `autoresearch/<tag>`. The original checkout
should remain clean. Use `--run-id <id>` for deterministic local checks,
`--resume` to continue an existing branch, and `--cleanup-worktree` to remove
the worktree after the final commit while leaving the branch.
```

- [ ] **Step 5: Run docs tests**

Run:

```bash
python3 -m pytest tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit docs**

Run:

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: document autoresearch run loop"
```

---

### Task 12: Final Verification

**Files:**
- No planned source edits.

- [ ] **Step 1: Run focused test suites**

Run:

```bash
python3 -m pytest tests/test_search_run_render.py tests/test_search_run_loop.py tests/test_search_run_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run regression suites touched by this work**

Run:

```bash
python3 -m pytest tests/test_search_eval_cli.py tests/test_search_eval_candidates.py tests/test_search_eval_schemas.py tests/test_search_load.py tests/test_search_source_data.py tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 3: Validate the workspace**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: exits 0 and prints a validated search workspace summary.

- [ ] **Step 4: Run the full test suite**

Run:

```bash
python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 5: Inspect git history and working tree**

Run:

```bash
git status --short
git log --oneline -8
```

Expected: `git status --short` is empty. The recent log contains the task commits from this plan.

# Issue 94 Quantum Tanner AI Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `summarize-quantum-tanner-ai-feedback` to produce compact JSON and self-contained HTML feedback from a completed quantum Tanner proposal run.

**Architecture:** Reuse `autoqec_search.report.build_report_model(...)` for validated run state, then enrich it with optional proposal-ingest summary and optional surface-copy comparison JSON. Keep the new behavior in one focused module with thin `cli.py` wiring.

**Tech Stack:** Python 3.14, stdlib JSON/HTML helpers, existing `SearchIntegrityError`, existing pytest CLI test style.

## Global Constraints

- Command name is exactly `summarize-quantum-tanner-ai-feedback`.
- Inputs are `--root`, `--run`, optional `--proposal-summary`, optional `--surface-copy`, `--out-json`, and `--out-html`.
- Outputs are compact `quantum-tanner-ai-feedback.json` and offline-safe `quantum-tanner-ai-feedback.html`.
- JSON preserves exact numeric fields from artifacts where practical: `p`, `logical_error_rate`, `shots`, `errors`, `upper_bound`, `n`, `k`, and surface-copy status/numeric fields.
- Include rejected proposals with typed reasons, not only candidates that reached rbposd.
- HTML is self-contained and must not reference network assets.
- Accepted proposal summary records whose candidate id is absent from the run fail nonzero with `proposal feedback candidate mismatch`.
- This issue does not generate proposals, call a live model, materialize candidates, or run decoders.

---

### Task 1: Feedback CLI Tests

**Files:**
- Create: `tests/test_search_quantum_tanner_ai_feedback.py`

**Interfaces:**
- Consumes: CLI command `summarize-quantum-tanner-ai-feedback` expected to be missing at first.
- Produces: Two tests required by issue #94 and reusable fixture helpers for a minimal completed quantum Tanner run.

- [ ] **Step 1: Write the failing positive and mismatch tests**

Create `tests/test_search_quantum_tanner_ai_feedback.py` with these concrete helpers and assertions:

```python
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "quantum-tanner-css-memory-x-rbposd-p001-v1"
DECODER_ID = "rbposd-osd10-v1"
SUITE_ID = "quantum-tanner-rbposd-p001-v1"
CAMPAIGN_ID = "quantum-tanner-autoresearch"
RUN_ID = "feedback-fixture-run"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "autoqec_search.cli", *args],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
```

Add a `_fixture_root(tmp_path: Path) -> tuple[Path, Path, Path, Path]` helper that copies `benchmarks/schemas`, writes one benchmark task/decoder/suite, writes campaign/search-space files for two candidates, and writes a run under `results/search/quantum-tanner-autoresearch/feedback-fixture-run`.

The fixture must include:

```python
candidate_specs = [
    {
        "candidate_id": "ai-valid-dihedral-d3",
        "code_family": "quantum-tanner-code",
        "parameters": {"label": "ai-valid-dihedral-d3"},
        "provenance": {
            "kind": "proposal-derived",
            "label": "ai-valid-dihedral-d3",
            "proposal": {
                "proposal_id": "ai-valid-dihedral-d3",
                "proposal_fingerprint": "fp-valid",
                "validator_fingerprint": "validator-fp",
                "candidate_fingerprint": "candidate-fp-valid",
                "materialization_manifest": "manifest-valid.json",
                "qec_code_spec_path": "spec-valid.json",
                "output_hashes": {"hx.json": "hx", "hz.json": "hz", "instance.json": "inst"},
                "materializer_version": "fixture",
                "exact_distance_status": "unknown",
                "materialization_run": {"qec_code": "fixture"},
            },
        },
    },
    {
        "candidate_id": "ai-skipped-dihedral-d5",
        "code_family": "quantum-tanner-code",
        "parameters": {"label": "ai-skipped-dihedral-d5"},
        "provenance": {"kind": "fixture", "label": "ai-skipped-dihedral-d5"},
    },
]
```

For `ai-valid-dihedral-d3`, write `candidate.json`, `structure.json` with `n: 36`, `k: 2`, `screening.json` with `screening_status: admitted`, `distance.json` with `bound_type: upper` and `upper_bound: 3`, and a completed evaluation manifest with one point:

```python
{
    "p": 0.001,
    "rounds": 9,
    "shots": 10000,
    "errors": 12,
    "ler": 0.0012,
    "ci_low": 0.0007,
    "ci_high": 0.0018,
    "seconds": 2.5,
}
```

For `ai-skipped-dihedral-d5`, write `candidate.json`, `structure.json` with `n: 64`, `k: 2`, `screening.json` with `screening_status: skipped`, `distance.json` with `upper_bound: 5`, and no completed evaluation manifest.

Write a proposal summary JSON containing one accepted record for `ai-valid-dihedral-d3`, one rejected record for `ai-invalid-nonsymmetric-generators` with `error_kind: NonSymmetricGeneratorSet`, and one duplicate record with `error_kind: DuplicateProposal`.

Write a surface-copy JSON with one accepted row for `ai-valid-dihedral-d3` containing `status`, `surface_distance`, `surface_block_ler`, and copied physical-budget fields.

Add the positive test:

```python
def test_feedback_report_summarizes_completed_proposal_run(tmp_path: Path) -> None:
    root, run_root, proposal_summary, surface_copy = _fixture_root(tmp_path)
    out_json = tmp_path / "quantum-tanner-ai-feedback.json"
    out_html = tmp_path / "quantum-tanner-ai-feedback.html"

    result = _run_cli(
        root,
        "summarize-quantum-tanner-ai-feedback",
        "--root", str(root),
        "--run", str(run_root.relative_to(root)),
        "--proposal-summary", str(proposal_summary),
        "--surface-copy", str(surface_copy),
        "--out-json", str(out_json),
        "--out-html", str(out_html),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_json.read_text())
    candidate = next(
        item for item in payload["candidates"]
        if item["candidate_id"] == "ai-valid-dihedral-d3"
    )
    assert candidate["proposal_id"] == "ai-valid-dihedral-d3"
    assert candidate["proposal_fingerprint"] == "fp-valid"
    assert candidate["validation_status"] == "accepted"
    assert candidate["materialization_status"] == "present"
    assert candidate["screening_status"] == "admitted"
    assert candidate["upper_bound"] == 3
    assert candidate["n"] == 36
    assert candidate["k"] == 2
    assert candidate["ler_points"][0]["p"] == 0.001
    assert candidate["ler_points"][0]["logical_error_rate"] == 0.0012
    assert candidate["ler_points"][0]["shots"] == 10000
    assert candidate["ler_points"][0]["errors"] == 12
    assert candidate["surface_copy"]["status"] == "accepted"
    assert payload["rejected_proposals"][0]["proposal_id"] == "ai-invalid-nonsymmetric-generators"
    assert "ai-valid-dihedral-d3" in payload["next_prompt_context"]["candidate_ids_with_p001_ler"]

    html = out_html.read_text()
    assert "ai-valid-dihedral-d3" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "//cdn" not in html
    assert "src=" not in html
    assert "href=" not in html
```

Add the mismatch test:

```python
def test_feedback_report_rejects_inconsistent_candidate_ids(tmp_path: Path) -> None:
    root, run_root, proposal_summary, surface_copy = _fixture_root(tmp_path)
    summary = json.loads(proposal_summary.read_text())
    summary["accepted_records"][0]["candidate_id"] = "missing-candidate"
    proposal_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    result = _run_cli(
        root,
        "summarize-quantum-tanner-ai-feedback",
        "--root", str(root),
        "--run", str(run_root.relative_to(root)),
        "--proposal-summary", str(proposal_summary),
        "--surface-copy", str(surface_copy),
        "--out-json", str(tmp_path / "feedback.json"),
        "--out-html", str(tmp_path / "feedback.html"),
    )

    assert result.returncode != 0
    assert "proposal feedback candidate mismatch" in result.stderr
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_ai_feedback.py::test_feedback_report_summarizes_completed_proposal_run \
  tests/test_search_quantum_tanner_ai_feedback.py::test_feedback_report_rejects_inconsistent_candidate_ids \
  -q
```

Expected: both tests fail because `summarize-quantum-tanner-ai-feedback` is not registered yet.

- [ ] **Step 3: Commit failing tests**

Commit only the test file:

```bash
git add tests/test_search_quantum_tanner_ai_feedback.py
git commit -m "test: cover quantum Tanner AI feedback report"
```

---

### Task 2: Feedback Model And HTML Writer

**Files:**
- Create: `src/autoqec_search/quantum_tanner_ai_feedback.py`
- Test: `tests/test_search_quantum_tanner_ai_feedback.py`

**Interfaces:**
- Consumes: `build_report_model(root, run_root)`, optional proposal summary JSON, optional surface-copy JSON.
- Produces: `build_quantum_tanner_ai_feedback(...) -> dict[str, Any]`, `write_quantum_tanner_ai_feedback(...) -> dict[str, Path]`, and offline-safe `render_quantum_tanner_ai_feedback_html(model) -> str`.

- [ ] **Step 1: Implement the minimal module**

Create `src/autoqec_search/quantum_tanner_ai_feedback.py` with:

```python
from __future__ import annotations

import json
import math
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from autoqec_search.distance_methods import load_distance_payload
from autoqec_search.load import SearchIntegrityError
from autoqec_search.report import build_report_model


FEEDBACK_SCHEMA_VERSION = 1
REPORT_KIND = "quantum-tanner-ai-feedback"
TARGET_P = 0.001


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SearchIntegrityError(f"{label} must contain a JSON object: {path}")
    return payload
```

Add helpers for relative input resolution, proposal-summary normalization, surface-copy row selection, distance upper-bound extraction, p=0.001 LER row conversion, and candidate provenance extraction. The p=0.001 conversion must emit `logical_error_rate` from the report-model point's `ler` value.

The candidate payload must contain at least:

```python
{
    "candidate_id": candidate_id,
    "proposal_id": proposal_id,
    "proposal_fingerprint": proposal_fingerprint,
    "validation_status": validation_status,
    "materialization_status": "present",
    "screening_status": screening_status,
    "screening_reason": screening_reason,
    "n": candidate.get("n"),
    "k": candidate.get("k"),
    "upper_bound": distance_payload.upper_bound,
    "distance_bound_type": distance_payload.bound_type,
    "ler_points": ler_points,
    "surface_copy": surface_copy,
    "rejection_reasons": rejection_reasons,
}
```

Raise `SearchIntegrityError` with text containing `proposal feedback candidate mismatch` when any accepted proposal-summary record maps to a candidate id that is not in the run's candidate ids.

- [ ] **Step 2: Implement offline-safe HTML rendering**

Add:

```python
def render_quantum_tanner_ai_feedback_html(model: dict[str, Any]) -> str:
    payload = json.dumps(model, indent=2, sort_keys=True)
    # Build an inline table of candidate id, validation, screening, upper bound,
    # p=0.001 LER, and surface-copy status.
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoQEC Quantum Tanner AI Feedback</title>
  <style>
    body {{ color: #1f2933; font-family: system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; width: 100%; }}
    th, td {{ border: 1px solid #c7d0d9; padding: 0.4rem 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; }}
    code, pre {{ background: #f6f8fa; }}
    pre {{ padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  ...
  <script type="application/json" id="quantum-tanner-ai-feedback-data">{escape(payload)}</script>
  <pre>{escape(payload)}</pre>
</body>
</html>
"""
```

Do not emit `src=`, `href=`, `http://`, or `https://`.

- [ ] **Step 3: Implement JSON and HTML writer**

Add:

```python
def write_quantum_tanner_ai_feedback(
    model: dict[str, Any],
    *,
    out_json: Path,
    out_html: Path,
) -> dict[str, Path]:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    out_html.write_text(render_quantum_tanner_ai_feedback_html(model))
    return {"json": out_json, "html": out_html}
```

- [ ] **Step 4: Run tests and verify module is still unreachable from CLI**

Run the two issue tests again. Expected: still fail at CLI registration, not at model import.

---

### Task 3: CLI Wiring, Green Tests, And Verification

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `src/autoqec_search/quantum_tanner_ai_feedback.py`
- Test: `tests/test_search_quantum_tanner_ai_feedback.py`

**Interfaces:**
- Consumes: `build_quantum_tanner_ai_feedback(...)` and `write_quantum_tanner_ai_feedback(...)`.
- Produces: user-facing CLI command.

- [ ] **Step 1: Wire parser and main dispatch**

In `src/autoqec_search/cli.py`, import:

```python
from autoqec_search.quantum_tanner_ai_feedback import (
    build_quantum_tanner_ai_feedback,
    write_quantum_tanner_ai_feedback,
)
```

Add parser:

```python
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
```

Add dispatch before generic report/promote commands:

```python
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
            Path(args.proposal_summary) if args.proposal_summary is not None else None
        ),
        surface_copy_path=Path(args.surface_copy) if args.surface_copy is not None else None,
    )
    written = write_quantum_tanner_ai_feedback(
        model,
        out_json=Path(args.out_json),
        out_html=Path(args.out_html),
    )
    print(f"wrote quantum Tanner AI feedback to {written['json']} and {written['html']}")
    return 0
```

- [ ] **Step 2: Run focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_search_quantum_tanner_ai_feedback.py::test_feedback_report_summarizes_completed_proposal_run \
  tests/test_search_quantum_tanner_ai_feedback.py::test_feedback_report_rejects_inconsistent_candidate_ids \
  -q
```

Expected: `2 passed`.

- [ ] **Step 3: Run full verification**

Run:

```bash
PYTHONPATH=src python3 -m pytest
```

Expected: full repository suite passes.

- [ ] **Step 4: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 5: Commit implementation**

Commit implementation and plan:

```bash
git add docs/superpowers/plans/2026-07-10-issue-94-quantum-tanner-ai-feedback.md src/autoqec_search/cli.py src/autoqec_search/quantum_tanner_ai_feedback.py tests/test_search_quantum_tanner_ai_feedback.py
git commit -m "feat: add quantum Tanner AI feedback report"
```

---

## Self-Review

- Spec coverage: command interface, compact JSON, HTML, numeric preservation, rejected proposals, surface-copy inclusion, mismatch failure, and verification commands are covered by the tasks.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: public function names and CLI argument names are consistent across all tasks.

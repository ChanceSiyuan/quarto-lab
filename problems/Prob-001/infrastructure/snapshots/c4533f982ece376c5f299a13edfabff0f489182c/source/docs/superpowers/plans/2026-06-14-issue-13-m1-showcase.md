# Issue 13 M1 Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the issue #13 conversation-first `search-campaign` skill, commit the completed `m1-demo` search run, verify the M1 report/promotion final state offline, and document the M1 quick-start.

**Architecture:** Keep the new user-facing skill as a thin project-level workflow document over the existing search CLI. Generate the committed M1 artifacts through the existing `autoqec-search run` autoresearch path, then copy the finalized run and promoted Zoo outputs from the run worktree into the main tree. Add an offline e2e test that reads committed artifacts, compares the d=3 point to the golden fixture CI, and checks report plus Zoo promotion visibility.

**Tech Stack:** Markdown project skills, Python 3.11, pytest, existing `autoqec_search` CLI modules, existing `autoqec_zoo` build outputs, local `rsinter` for one real demo capture.

---

## File Structure

- Create `skills/search-campaign/SKILL.md`: conversation-first M1 intake workflow with an explicit pre-materialization approval gate.
- Create `skills/search-campaign/examples/rotated-surface-baseline-intake.md`: committed transcript proving the no-write-before-approval case.
- Create `tests/test_search_e2e.py`: offline checks for the skill transcript, committed `m1-demo` run, report content, leaderboard/manifest consistency, golden fixture compatibility, and Zoo promotion visibility.
- Add `results/search/rotated-surface-baseline/m1-demo/`: completed autoresearch run copied from `.worktrees/m1-demo/`.
- Add `zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/`: promoted instance copied from the finalized demo worktree.
- Modify generated Zoo artifacts from the demo promotion:
  - `zoo/views/instance-index.json`
  - `zoo/views/browse.md`
  - `zoo/views/site/`
  - `zoo/codes/rotated-surface-code/card.md`
- Modify `tests/test_search_docs.py`: assert the docs mention `search-campaign`, `m1-demo`, source-checkout commands, and the e2e test.
- Modify `README.md`: add an M1 final-result / quick-start section with `PYTHONPATH=src` commands and installed entry-point equivalents.
- Modify `CLAUDE.md`: add agent-facing issue #13 / M1 final-result instructions.

## Task 1: Add The Search-Campaign Approval-Gate Skill

**Files:**
- Create: `tests/test_search_e2e.py`
- Create: `skills/search-campaign/SKILL.md`
- Create: `skills/search-campaign/examples/rotated-surface-baseline-intake.md`

- [ ] **Step 1: Write the failing approval-gate test**

Create `tests/test_search_e2e.py` with this initial content:

```python
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_search_campaign_skill_has_approval_gate_and_example_transcript() -> None:
    skill_path = REPO_ROOT / "skills" / "search-campaign" / "SKILL.md"
    transcript_path = (
        REPO_ROOT
        / "skills"
        / "search-campaign"
        / "examples"
        / "rotated-surface-baseline-intake.md"
    )

    skill = skill_path.read_text()
    transcript = transcript_path.read_text()

    assert "search-campaign" in skill
    assert "explicit approval" in skill
    assert "must not write" in skill
    assert "campaign.json" in skill
    assert "search_space.json" in skill
    assert "promote_rules.json" in skill
    assert "autoqec_search.cli validate" in skill
    assert "rotated-surface-code" in skill

    assert "wait, do not write anything yet" in transcript
    assert "No campaign files are written." in transcript
    assert "Approved. Write the campaign files." in transcript
    assert "validation passes" in transcript
```

- [ ] **Step 2: Run the approval-gate test and verify it fails**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py::test_search_campaign_skill_has_approval_gate_and_example_transcript -q
```

Expected: FAIL with `FileNotFoundError` for `skills/search-campaign/SKILL.md`.

- [ ] **Step 3: Create the skill file**

Create `skills/search-campaign/SKILL.md` with this content:

````markdown
---
name: search-campaign
description: Use when a user wants to start an AutoQEC search campaign from natural language rather than hand-writing campaign JSON.
---

# search-campaign

## Overview

This is the M1 conversation-first front door for AutoQEC search campaigns.
It turns a user's natural-language research goal into campaign files only after
the user explicitly approves the summarized campaign.

The skill is intentionally thin. It writes campaign intent and validates the
search workspace; it does not run expensive search jobs inline.

## M1 Scope

Supported in M1:

- code family: `rotated-surface-code`
- candidate parameters: positive integer `distance` and `layout: rotated`
- decoders: existing ids under `benchmarks/decoders/*.json`
- physical error probabilities: finite values satisfying `0 < p < 1`
- budgets: `max_candidates` and wall-clock seconds
- promotion policy: the existing `promote_rules.json` shape

Out of scope for this skill:

- arbitrary CSS candidates
- new decoder definitions
- full issue #5 benchmark runner skills
- running `autoqec-search run` without a separate user decision

## Workflow

1. Read the user's search goal.
2. Resolve or ask for the M1 fields one at a time:
   - campaign id
   - objective
   - distances
   - decoder ids
   - p-list
   - `max_candidates`
   - wall-clock seconds
   - promotion rule threshold
3. Summarize the proposed campaign in natural language.
4. Ask for explicit approval before materializing files.
5. Before approval, you must not write `campaign.json`,
   `search_space.json`, or `promote_rules.json`.
6. After explicit approval, write:
   - `campaigns/examples/<campaign-id>/campaign.json`
   - `campaigns/examples/<campaign-id>/search_space.json`
   - `campaigns/examples/<campaign-id>/promote_rules.json`
7. Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

8. Report the written files and the next command:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign <campaign-id> --wall-clock <seconds>s --run-id <run-id> --allow-dirty-root
```

## Validation Rules

- Stop if the family is not `rotated-surface-code`.
- Stop if any distance is not a positive integer.
- Stop if any decoder id is not present in `benchmarks/decoders/`.
- Stop if any p-list value is not a finite probability.
- Stop if the target campaign directory already exists.
- Stop if the user has not explicitly approved materialization.
- Stop if `autoqec-search validate` fails after writing files.

## Approval Gate Language

Use clear approval language. A user saying "looks good", "approved", or
"write the files" is approval. A user saying "wait", "not yet", "show me
first", or "do not write anything yet" is not approval.

When there is no approval, say that no campaign files are written.
````

- [ ] **Step 4: Create the example transcript**

Create `skills/search-campaign/examples/rotated-surface-baseline-intake.md` with this content:

````markdown
# Rotated Surface Baseline Intake Example

User: I want to search rotated surface codes and see whether the d=3 baseline
can make it through the M1 pipeline.

Assistant: I can set up an M1 search campaign for `rotated-surface-code`.
What campaign id should I use?

User: `rotated-surface-baseline`

Assistant: Which distances should the campaign enumerate?

User: Just distance 3 for the demo.

Assistant: Which decoder ids should it use?

User: Use the existing suite defaults.

Assistant: Which physical error probabilities should be checked?

User: Include `0.005`, and keep the normal task defaults.

Assistant: What budget should I use?

User: At most two candidates and a 60 second local run.

Assistant: What promotion rule should gate the result?

User: Promote if distance is at least 3 and LER at p=0.005 is at most 0.5.

Assistant: Summary before writing files:

- campaign id: `rotated-surface-baseline`
- family: `rotated-surface-code`
- distances: `3`
- decoders: existing `rotated-surface-baseline-v1` suite defaults
- p-list: task defaults plus promotion check at `0.005`
- budget: two candidates, 60 seconds
- promotion: `min_distance = 3`, `max_ler_at_p = {p = 0.005, ler = 0.5}`

Do you explicitly approve writing `campaign.json`, `search_space.json`, and
`promote_rules.json`?

User: wait, do not write anything yet

Assistant: No campaign files are written. I will wait for explicit approval
before materializing `campaign.json`, `search_space.json`, or
`promote_rules.json`.

User: Approved. Write the campaign files.

Assistant: I write the campaign files and run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

The validation passes. Next command:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
```
````

- [ ] **Step 5: Run the approval-gate test and verify it passes**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py::test_search_campaign_skill_has_approval_gate_and_example_transcript -q
```

Expected: PASS.

- [ ] **Step 6: Commit the skill and transcript**

Run:

```bash
git add tests/test_search_e2e.py skills/search-campaign/SKILL.md skills/search-campaign/examples/rotated-surface-baseline-intake.md
git commit -m "feat: add search campaign intake skill"
```

Expected: commit succeeds.

## Task 2: Add Offline M1 Demo E2E Tests

**Files:**
- Modify: `tests/test_search_e2e.py`
- Later generated by Task 3:
  - `results/search/rotated-surface-baseline/m1-demo/`
  - `zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/`
  - `zoo/views/instance-index.json`
  - `zoo/views/browse.md`

- [ ] **Step 1: Replace the e2e test file with full offline coverage**

Replace `tests/test_search_e2e.py` with this content:

```python
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from autoqec_search.load import load_search_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_RUN_ID = "m1-demo"
CAMPAIGN_ID = "rotated-surface-baseline"
CANDIDATE_ID = "rotated-surface-d3-example"
TASK_ID = "rotated-memory-x-cdep-v1"
DECODER_ID = "rmatching-default-v1"
DEMO_RUN_ROOT = REPO_ROOT / "results" / "search" / CAMPAIGN_ID / DEMO_RUN_ID


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _demo_manifest() -> dict[str, Any]:
    return _load_json(
        DEMO_RUN_ROOT
        / "candidates"
        / CANDIDATE_ID
        / "evaluations"
        / TASK_ID
        / DECODER_ID
        / "manifest.json"
    )


def _golden_fixture() -> dict[str, Any]:
    return _load_json(REPO_ROOT / "benchmarks" / "fixtures" / "rotated-d3" / "expected.json")


def _demo_point_at_golden_p() -> dict[str, Any]:
    manifest = _demo_manifest()
    expected = _golden_fixture()
    for point in manifest["points"]:
        if math.isclose(float(point["p"]), float(expected["p"]), rel_tol=0.0, abs_tol=1e-15):
            return point
    raise AssertionError(f"missing p={expected['p']} point in M1 demo manifest")


def _leaderboard_rows() -> list[dict[str, str]]:
    with (DEMO_RUN_ROOT / "leaderboard.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_search_campaign_skill_has_approval_gate_and_example_transcript() -> None:
    skill_path = REPO_ROOT / "skills" / "search-campaign" / "SKILL.md"
    transcript_path = (
        REPO_ROOT
        / "skills"
        / "search-campaign"
        / "examples"
        / "rotated-surface-baseline-intake.md"
    )

    skill = skill_path.read_text()
    transcript = transcript_path.read_text()

    assert "search-campaign" in skill
    assert "explicit approval" in skill
    assert "must not write" in skill
    assert "campaign.json" in skill
    assert "search_space.json" in skill
    assert "promote_rules.json" in skill
    assert "autoqec_search.cli validate" in skill
    assert "rotated-surface-code" in skill

    assert "wait, do not write anything yet" in transcript
    assert "No campaign files are written." in transcript
    assert "Approved. Write the campaign files." in transcript
    assert "validation passes" in transcript


def test_m1_demo_run_loads_and_matches_golden_fixture() -> None:
    workspace = load_search_workspace(REPO_ROOT)
    run = workspace.runs[f"{CAMPAIGN_ID}/{DEMO_RUN_ID}"]

    assert run.payload["mode"] == "autoresearch"
    assert run.payload["run_id"] == DEMO_RUN_ID
    assert CANDIDATE_ID in run.payload["candidate_ids"]

    run_status = _load_json(DEMO_RUN_ROOT / "run_status.json")
    assert run_status["status"] == "finalized"
    assert run_status["run_id"] == DEMO_RUN_ID
    assert run_status["frontier_size"] >= 1

    candidate_root = DEMO_RUN_ROOT / "candidates" / CANDIDATE_ID
    for artifact_name in ("instance.json", "hx.json", "hz.json"):
        assert (candidate_root / "artifacts" / artifact_name).is_file()

    manifest = _demo_manifest()
    assert manifest["status"] == "completed"
    assert manifest["candidate_id"] == CANDIDATE_ID
    assert manifest["task_id"] == TASK_ID
    assert manifest["decoder_id"] == DECODER_ID

    point = _demo_point_at_golden_p()
    expected = _golden_fixture()
    ci = expected["binomial_ci_95"]
    assert point["rounds"] == expected["rounds"]
    assert point["shots"] >= 1
    assert 0 <= point["errors"] <= point["shots"]
    assert ci["lower"] <= point["ler"] <= ci["upper"]

    frontier = _load_json(DEMO_RUN_ROOT / "frontier.json")
    assert frontier["campaign_id"] == CAMPAIGN_ID
    assert frontier["run_id"] == DEMO_RUN_ID
    assert any(item["candidate_id"] == CANDIDATE_ID for item in frontier["items"])

    rows = _leaderboard_rows()
    keep_row = next(row for row in rows if row["candidate_id"] == CANDIDATE_ID)
    assert keep_row["status"] == "keep"
    assert keep_row["decoder_id"] == DECODER_ID
    assert math.isclose(float(keep_row["ler"]), point["ler"], rel_tol=1e-10, abs_tol=1e-15)


def test_m1_demo_report_and_promotion_are_visible() -> None:
    point = _demo_point_at_golden_p()
    report = (DEMO_RUN_ROOT / "report.html").read_text()

    assert "AutoQEC Search Report" in report
    assert CANDIDATE_ID in report
    assert str(point["p"]) in report
    assert str(point["ler"]) in report
    assert "http://" not in report
    assert "https://" not in report

    promotion_summary = _load_json(DEMO_RUN_ROOT / "promotion_summary.json")
    assert promotion_summary["status"] == "completed"
    promoted_ids = {item["candidate_id"] for item in promotion_summary["promoted"]}
    assert CANDIDATE_ID in promoted_ids

    instance_path = (
        REPO_ROOT
        / "zoo"
        / "codes"
        / "rotated-surface-code"
        / "instances"
        / CANDIDATE_ID
        / "instance.json"
    )
    promoted_instance = _load_json(instance_path)
    assert promoted_instance["id"] == CANDIDATE_ID
    assert promoted_instance["provenance"]["source_run"] == f"{CAMPAIGN_ID}/{DEMO_RUN_ID}"

    instance_index = _load_json(REPO_ROOT / "zoo" / "views" / "instance-index.json")
    assert any(item["id"] == CANDIDATE_ID for item in instance_index["items"])

    browse = (REPO_ROOT / "zoo" / "views" / "browse.md").read_text()
    assert CANDIDATE_ID in browse
```

- [ ] **Step 2: Run the M1 demo e2e tests and verify they fail**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py -q
```

Expected: FAIL because `results/search/rotated-surface-baseline/m1-demo/` does not exist yet.

## Task 3: Generate And Commit The M1 Demo Artifacts

**Files:**
- Add: `results/search/rotated-surface-baseline/m1-demo/**`
- Add: `zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/**`
- Modify: `zoo/views/instance-index.json`
- Modify: `zoo/views/browse.md`
- Modify: `zoo/views/site/**`
- Modify: `zoo/codes/rotated-surface-code/card.md`
- Test: `tests/test_search_e2e.py`

- [ ] **Step 1: Verify the real backend is available**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

Expected: exit code 0, all rows PASS, and output includes `rsinter available` plus `fixture rotated-d3`.

- [ ] **Step 2: Run the real M1 demo in an autoresearch worktree**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id m1-demo --allow-dirty-root
```

Expected: exit code 0 and output includes:

```text
completed autoresearch run on autoresearch/m1-demo at
```

Expected generated worktree path:

```text
.worktrees/m1-demo/results/search/rotated-surface-baseline/m1-demo/
```

- [ ] **Step 3: Inspect the generated demo point**

Run:

```bash
PYTHONPATH=src python3 - <<'PY'
import json
from pathlib import Path

root = Path(".worktrees/m1-demo/results/search/rotated-surface-baseline/m1-demo")
manifest = json.loads((root / "candidates/rotated-surface-d3-example/evaluations/rotated-memory-x-cdep-v1/rmatching-default-v1/manifest.json").read_text())
expected = json.loads(Path("benchmarks/fixtures/rotated-d3/expected.json").read_text())
point = next(p for p in manifest["points"] if abs(p["p"] - expected["p"]) < 1e-15)
ci = expected["binomial_ci_95"]
print(f"p={point['p']} ler={point['ler']} ci=[{ci['lower']}, {ci['upper']}]")
raise SystemExit(0 if ci["lower"] <= point["ler"] <= ci["upper"] else 1)
PY
```

Expected: exit code 0 and printed LER lies inside the golden fixture CI.

- [ ] **Step 4: Copy the finalized run and promoted Zoo artifacts into the main tree**

Run:

```bash
mkdir -p results/search/rotated-surface-baseline
cp -R .worktrees/m1-demo/results/search/rotated-surface-baseline/m1-demo results/search/rotated-surface-baseline/
mkdir -p zoo/codes/rotated-surface-code/instances
cp -R .worktrees/m1-demo/zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example zoo/codes/rotated-surface-code/instances/
cp .worktrees/m1-demo/zoo/codes/rotated-surface-code/card.md zoo/codes/rotated-surface-code/card.md
cp .worktrees/m1-demo/zoo/views/code-index.json zoo/views/code-index.json
cp .worktrees/m1-demo/zoo/views/evidence-index.json zoo/views/evidence-index.json
cp .worktrees/m1-demo/zoo/views/family-index.json zoo/views/family-index.json
cp .worktrees/m1-demo/zoo/views/instance-index.json zoo/views/instance-index.json
cp .worktrees/m1-demo/zoo/views/relation-index.json zoo/views/relation-index.json
cp .worktrees/m1-demo/zoo/views/browse.md zoo/views/browse.md
cp .worktrees/m1-demo/zoo/views/site/index.html zoo/views/site/index.html
cp .worktrees/m1-demo/zoo/views/site/assets/app.js zoo/views/site/assets/app.js
cp .worktrees/m1-demo/zoo/views/site/assets/styles.css zoo/views/site/assets/styles.css
```

Expected: files are copied into the main worktree.

- [ ] **Step 5: Remove the temporary autoresearch worktree**

Run:

```bash
git worktree remove .worktrees/m1-demo
```

Expected: exit code 0. The branch `autoresearch/m1-demo` may remain local.

- [ ] **Step 6: Run the offline M1 demo e2e tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py -q
```

Expected: PASS.

- [ ] **Step 7: Validate the search workspace with the committed demo**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: exit code 0 and output includes `validated search workspace`.

- [ ] **Step 8: Commit the demo artifacts and e2e tests**

Run:

```bash
git add tests/test_search_e2e.py results/search/rotated-surface-baseline/m1-demo zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example zoo/codes/rotated-surface-code/card.md zoo/views
git commit -m "test: add m1 demo e2e coverage"
```

Expected: commit succeeds.

## Task 4: Document The M1 Final Result And Quick-Start

**Files:**
- Modify: `tests/test_search_docs.py`
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add failing docs assertions**

Append this test to `tests/test_search_docs.py`:

```python
def test_docs_mention_search_campaign_and_m1_demo_quickstart() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    for document in (readme, claude):
        assert "search-campaign" in document
        assert "m1-demo" in document
        assert "results/search/rotated-surface-baseline/m1-demo/report.html" in document
        assert "PYTHONPATH=src python3 -m autoqec_search.cli preflight --root ." in document
        assert "PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py" in document
        assert "autoqec-search preflight --root ." in document
```

- [ ] **Step 2: Run the docs test and verify it fails**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py::test_docs_mention_search_campaign_and_m1_demo_quickstart -q
```

Expected: FAIL because the docs do not yet mention the new M1 final-result path.

- [ ] **Step 3: Update README.md**

In `README.md`, add this section after the "Search Layer" command overview and before "Finite Instance Generation":

````markdown
## M1 Final Result

Issue #13 finishes the M1 path with a conversation-first front door and a
committed demo run.

Use the project skill when you want to start from natural language instead of
hand-writing campaign JSON:

```text
/search-campaign
```

The `search-campaign` skill performs intake, summarizes the proposed campaign,
waits for explicit approval, then writes `campaign.json`, `search_space.json`,
and `promote_rules.json` before running validation.

The committed M1 demo lives at:

```text
results/search/rotated-surface-baseline/m1-demo/
```

Open the final visual report directly from:

```text
results/search/rotated-surface-baseline/m1-demo/report.html
```

The promoted demo instance is visible in:

```text
zoo/views/browse.md
```

From a source checkout, use `PYTHONPATH=src` unless you have installed the
package:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/local-m1-demo
PYTHONPATH=src python3 -m autoqec_search.cli promote --root . --run results/search/rotated-surface-baseline/local-m1-demo
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py
```

If the package is installed, the equivalent commands are:

```bash
autoqec-search preflight --root .
autoqec-search run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
autoqec-search report --root . --run results/search/rotated-surface-baseline/local-m1-demo
autoqec-search promote --root . --run results/search/rotated-surface-baseline/local-m1-demo
```

`autoqec-search run` creates an `autoresearch/<run-id>` branch and a linked
`.worktrees/<run-id>/` worktree. The committed `m1-demo` run is the small
checked-in showcase; local runs are ordinary experiment artifacts unless you
choose to commit them.
````

- [ ] **Step 4: Update CLAUDE.md**

In `CLAUDE.md`, add this section near the existing Search Layer guidance:

````markdown
For issue `#13` and the M1 final-result path:

- Use `skills/search-campaign` when a user wants to start a search campaign from
  natural language. The skill must summarize the proposed campaign and wait for
  explicit approval before writing `campaign.json`, `search_space.json`, or
  `promote_rules.json`.
- The committed M1 demo run is
  `results/search/rotated-surface-baseline/m1-demo/`.
- The final report to open is
  `results/search/rotated-surface-baseline/m1-demo/report.html`.
- The promoted demo instance should be visible in `zoo/views/browse.md` and
  `zoo/views/instance-index.json`.
- From a source checkout, prefer:

  ```bash
  PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
  PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
  PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/local-m1-demo
  PYTHONPATH=src python3 -m autoqec_search.cli promote --root . --run results/search/rotated-surface-baseline/local-m1-demo
  PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py
  ```

- Installed entry-point equivalents begin with `autoqec-search`; the preflight
  form is `autoqec-search preflight --root .`.
````

- [ ] **Step 5: Run docs tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the documentation**

Run:

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: document m1 search showcase"
```

Expected: commit succeeds.

## Task 5: Final Verification

**Files:**
- Verify all files changed by Tasks 1 through 4.

- [ ] **Step 1: Run focused e2e and docs tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py tests/test_search_docs.py -q
```

Expected: PASS.

- [ ] **Step 2: Run report and promotion regression tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_report.py tests/test_search_promote.py -q
```

Expected: PASS.

- [ ] **Step 3: Validate the complete search workspace**

Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

Expected: exit code 0 and output includes `validated search workspace`.

- [ ] **Step 4: Verify the committed report is offline-safe**

Run:

```bash
grep -E 'https?://' results/search/rotated-surface-baseline/m1-demo/report.html
```

Expected: exit code 1 with no matches.

- [ ] **Step 5: Inspect the final diff**

Run:

```bash
git status --short
git diff --stat HEAD~3..HEAD
```

Expected: `git status --short` is clean if all task commits were made. The diff stat contains only the issue #13 skill, tests, demo artifacts, generated Zoo updates, and documentation.

## Self-Review Checklist

- Spec coverage: Tasks 1 through 4 cover the `search-campaign` skill, approval-gate transcript, committed `m1-demo` run, offline e2e test, docs updates, and M1 final result visibility.
- Scope check: The plan does not implement issue #5 benchmark skills, M2 general CSS support, new decoders, or new distance methods.
- Type consistency: The e2e test uses existing schema fields: `run_spec.mode`, `manifest.points`, autoresearch `leaderboard.csv`, `promotion_summary.promoted`, and `zoo/views/instance-index.json.items`.
- Verification: Task 5 covers e2e/docs tests, report/promotion regressions, workspace validation, and offline report safety.

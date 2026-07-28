# Issue #3 Search Architecture Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 1 search-layer scaffolding for issue `#3`: committed `campaigns/`, `benchmarks/`, and `results/search/` directories; a new `autoqec-search` CLI; schema validation; one committed example campaign; one committed example run; and one command that materializes fresh placeholder runs from the example campaign.

**Architecture:** Keep `zoo/` untouched as curated source-of-truth data and build a separate search layer beside it. The new `src/autoqec_search/` package follows the existing `autoqec_zoo` style: JSON source records, focused validators, a thin CLI, and deterministic file generation for placeholder runs.

**Tech Stack:** Python 3.11+, `jsonschema`, `pytest`, standard-library `json`, `argparse`, `shutil`, and checked-in JSON/Markdown/CSV artifacts.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Add the `autoqec-search` console entry point to the existing distribution. |
| `src/autoqec_search/__init__.py` | Package marker and version string used by generated run metadata. |
| `src/autoqec_search/cli.py` | `validate`, `init-run`, and `show` CLI entry points. |
| `src/autoqec_search/load.py` | JSON loading, schema validation, cross-file integrity checks, and workspace aggregation. |
| `src/autoqec_search/init_run.py` | Create placeholder run directories and candidate/manifest records from a campaign. |
| `src/autoqec_search/render.py` | Render `summary.md`, `leaderboard.csv`, and `show` output. |
| `campaigns/README.md` | Local contract for campaign definitions. |
| `campaigns/examples/rotated-surface-baseline/campaign.json` | The committed example campaign. |
| `campaigns/examples/rotated-surface-baseline/search_space.json` | The committed example candidate list. |
| `campaigns/examples/rotated-surface-baseline/notes.md` | Human-readable explanation of the example campaign. |
| `benchmarks/README.md` | Local contract for reusable benchmark tasks, decoders, suites, and schemas. |
| `benchmarks/tasks/rotated-memory-x-cdep-v1.json` | The committed example task contract. |
| `benchmarks/decoders/placeholder-noop-decoder-v1.json` | The committed placeholder decoder contract. |
| `benchmarks/suites/rotated-surface-baseline-v1.json` | Reusable suite linking the example task and decoder. |
| `benchmarks/schemas/*.schema.json` | Search-layer schemas for campaign, search space, task, decoder, suite, run spec, candidate, and manifest. |
| `results/search/README.md` | Local contract for runtime artifacts and committed example runs. |
| `results/search/rotated-surface-baseline/2026-06-09-example/**` | The committed example placeholder run. |
| `tests/test_search_cli.py` | CLI smoke tests for `validate`, `init-run`, and `show`. |
| `tests/test_search_source_data.py` | Schema checks for committed search-layer source files. |
| `tests/test_search_load.py` | Loader success and negative integrity checks. |
| `tests/test_search_init_run.py` | Placeholder-run generation tests. |
| `tests/test_search_docs.py` | Root-doc integration checks. |
| `README.md` | Mention the search layer and example commands. |
| `CLAUDE.md` | Add repo guidance for `campaigns/`, `benchmarks/`, and `results/search/`. |

---

### Task 1: Add The `autoqec-search` Package And CLI Skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `src/autoqec_search/__init__.py`
- Create: `src/autoqec_search/cli.py`
- Test: `tests/test_search_cli.py`

- [ ] **Step 1: Write the failing CLI smoke test**

Create `tests/test_search_cli.py`:

```python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_validate_rejects_missing_repo_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-repo"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate",
            "--root",
            str(missing_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert "repository root does not exist" in result.stderr
```

- [ ] **Step 2: Run the test to verify the module is missing**

Run: `pytest tests/test_search_cli.py::test_validate_rejects_missing_repo_root -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoqec_search'`

- [ ] **Step 3: Add the package marker, console script, and minimal CLI**

In `pyproject.toml`, change the `[project.scripts]` block to:

```toml
[project.scripts]
autoqec-zoo = "autoqec_zoo.cli:main"
autoqec-search = "autoqec_search.cli:main"
```

Create `src/autoqec_search/__init__.py`:

```python
"""AutoQEC search-layer package."""

__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `src/autoqec_search/cli.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        root = Path(args.root)
        if not root.exists():
            parser.error(f"repository root does not exist: {root}")
        print(f"search workspace root ok: {root}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the smoke test again**

Run: `pytest tests/test_search_cli.py::test_validate_rejects_missing_repo_root -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/autoqec_search/__init__.py src/autoqec_search/cli.py tests/test_search_cli.py
git commit -m "feat: add autoqec-search CLI skeleton"
```

---

### Task 2: Check In Schemas, READMEs, And Example Source Records

**Files:**
- Create: `campaigns/README.md`
- Create: `campaigns/examples/rotated-surface-baseline/campaign.json`
- Create: `campaigns/examples/rotated-surface-baseline/search_space.json`
- Create: `campaigns/examples/rotated-surface-baseline/notes.md`
- Create: `benchmarks/README.md`
- Create: `benchmarks/tasks/rotated-memory-x-cdep-v1.json`
- Create: `benchmarks/decoders/placeholder-noop-decoder-v1.json`
- Create: `benchmarks/suites/rotated-surface-baseline-v1.json`
- Create: `benchmarks/schemas/campaign.schema.json`
- Create: `benchmarks/schemas/search-space.schema.json`
- Create: `benchmarks/schemas/benchmark-task.schema.json`
- Create: `benchmarks/schemas/decoder-config.schema.json`
- Create: `benchmarks/schemas/benchmark-suite.schema.json`
- Create: `benchmarks/schemas/run-spec.schema.json`
- Create: `benchmarks/schemas/candidate.schema.json`
- Create: `benchmarks/schemas/result-manifest.schema.json`
- Create: `results/search/README.md`
- Test: `tests/test_search_source_data.py`

- [ ] **Step 1: Write the failing source-data test**

Create `tests/test_search_source_data.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_search_example_source_files_validate_against_checked_in_schemas() -> None:
    schema_root = REPO_ROOT / "benchmarks" / "schemas"
    campaign_validator = Draft202012Validator(
        _load_json(schema_root / "campaign.schema.json")
    )
    search_space_validator = Draft202012Validator(
        _load_json(schema_root / "search-space.schema.json")
    )
    task_validator = Draft202012Validator(
        _load_json(schema_root / "benchmark-task.schema.json")
    )
    decoder_validator = Draft202012Validator(
        _load_json(schema_root / "decoder-config.schema.json")
    )
    suite_validator = Draft202012Validator(
        _load_json(schema_root / "benchmark-suite.schema.json")
    )

    example_root = REPO_ROOT / "campaigns" / "examples" / "rotated-surface-baseline"
    campaign_validator.validate(_load_json(example_root / "campaign.json"))
    search_space_validator.validate(_load_json(example_root / "search_space.json"))
    task_validator.validate(
        _load_json(REPO_ROOT / "benchmarks" / "tasks" / "rotated-memory-x-cdep-v1.json")
    )
    decoder_validator.validate(
        _load_json(
            REPO_ROOT / "benchmarks" / "decoders" / "placeholder-noop-decoder-v1.json"
        )
    )
    suite_validator.validate(
        _load_json(
            REPO_ROOT / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
        )
    )

    assert (REPO_ROOT / "campaigns" / "README.md").is_file()
    assert (REPO_ROOT / "benchmarks" / "README.md").is_file()
    assert (REPO_ROOT / "results" / "search" / "README.md").is_file()
```

- [ ] **Step 2: Run the test to verify the data is still missing**

Run: `pytest tests/test_search_source_data.py::test_search_example_source_files_validate_against_checked_in_schemas -v`
Expected: FAIL with `FileNotFoundError` under `benchmarks/schemas/` or `campaigns/`

- [ ] **Step 3: Add the three README files**

Create `campaigns/README.md`:

```markdown
# Search Campaigns

This directory stores human-authored search intent.

## Source files

- `campaign.json`: campaign objective, default suite, budget, and stop conditions
- `search_space.json`: candidate definitions to materialize into runs
- `notes.md`: human context and review notes

## Current convention

Phase 1 examples live under `campaigns/examples/`.
```

Create `benchmarks/README.md`:

```markdown
# Search Benchmarks

This directory stores reusable benchmark contracts for the search layer.

## Contents

- `tasks/`: benchmark task definitions
- `decoders/`: decoder configuration records
- `suites/`: reusable task + decoder groupings
- `schemas/`: JSON Schemas used by `autoqec-search`

These records are reusable across campaigns.
```

Create `results/search/README.md`:

```markdown
# Search Results

This directory stores runtime search artifacts.

## Meaning

- `results/search/<campaign-id>/<run-id>/` is one concrete run
- committed example runs are allowed here
- these files are not curated `zoo/` source-of-truth data

Use `autoqec-search init-run` to materialize new placeholder runs.
```

- [ ] **Step 4: Add the JSON Schemas**

Create `benchmarks/schemas/campaign.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "title",
    "objective",
    "family_id",
    "default_suite_id",
    "budget",
    "stop_conditions",
    "random_seed_policy"
  ],
  "properties": {
    "id": { "type": "string", "minLength": 1 },
    "title": { "type": "string", "minLength": 1 },
    "objective": { "type": "string", "minLength": 1 },
    "family_id": { "type": "string", "minLength": 1 },
    "default_suite_id": { "type": "string", "minLength": 1 },
    "budget": {
      "type": "object",
      "additionalProperties": false,
      "required": ["candidate_limit"],
      "properties": {
        "candidate_limit": { "type": "integer", "minimum": 1 }
      }
    },
    "stop_conditions": {
      "type": "object",
      "additionalProperties": false,
      "required": ["max_candidates"],
      "properties": {
        "max_candidates": { "type": "integer", "minimum": 1 }
      }
    },
    "random_seed_policy": {
      "type": "object",
      "additionalProperties": false,
      "required": ["mode", "seed"],
      "properties": {
        "mode": { "enum": ["fixed", "none"] },
        "seed": { "type": ["integer", "null"] }
      }
    }
  }
}
```

Create `benchmarks/schemas/search-space.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["campaign_id", "mode", "candidate_specs"],
  "properties": {
    "campaign_id": { "type": "string", "minLength": 1 },
    "mode": { "enum": ["explicit_list"] },
    "candidate_specs": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["candidate_id", "code_family", "parameters", "provenance"],
        "properties": {
          "candidate_id": { "type": "string", "minLength": 1 },
          "code_family": { "type": "string", "minLength": 1 },
          "parameters": {
            "type": "object",
            "minProperties": 1,
            "additionalProperties": {
              "anyOf": [
                { "type": "string" },
                { "type": "integer" },
                { "type": "number" },
                { "type": "boolean" },
                { "type": "null" }
              ]
            }
          },
          "provenance": {
            "type": "object",
            "additionalProperties": false,
            "required": ["kind", "label"],
            "properties": {
              "kind": { "type": "string", "minLength": 1 },
              "label": { "type": "string", "minLength": 1 }
            }
          }
        }
      }
    }
  }
}
```

Create `benchmarks/schemas/benchmark-task.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "title",
    "observable",
    "noise_model",
    "input_type",
    "result_metrics",
    "execution_status"
  ],
  "properties": {
    "id": { "type": "string", "minLength": 1 },
    "title": { "type": "string", "minLength": 1 },
    "observable": { "type": "string", "minLength": 1 },
    "noise_model": { "type": "string", "minLength": 1 },
    "input_type": { "type": "string", "minLength": 1 },
    "result_metrics": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "minLength": 1 }
    },
    "execution_status": { "enum": ["placeholder"] }
  }
}
```

Create `benchmarks/schemas/decoder-config.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "title", "backend", "parameters", "execution_status"],
  "properties": {
    "id": { "type": "string", "minLength": 1 },
    "title": { "type": "string", "minLength": 1 },
    "backend": { "type": "string", "minLength": 1 },
    "parameters": {
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
    },
    "execution_status": { "enum": ["placeholder"] }
  }
}
```

Create `benchmarks/schemas/benchmark-suite.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "title", "task_ids", "decoder_ids", "shared_settings"],
  "properties": {
    "id": { "type": "string", "minLength": 1 },
    "title": { "type": "string", "minLength": 1 },
    "task_ids": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "minLength": 1 }
    },
    "decoder_ids": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "minLength": 1 }
    },
    "shared_settings": {
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

Create `benchmarks/schemas/run-spec.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "campaign_id",
    "run_id",
    "suite_id",
    "task_ids",
    "decoder_ids",
    "candidate_ids",
    "created_at",
    "mode"
  ],
  "properties": {
    "campaign_id": { "type": "string", "minLength": 1 },
    "run_id": { "type": "string", "minLength": 1 },
    "suite_id": { "type": "string", "minLength": 1 },
    "task_ids": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "minLength": 1 }
    },
    "decoder_ids": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "minLength": 1 }
    },
    "candidate_ids": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string", "minLength": 1 }
    },
    "created_at": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"
    },
    "mode": { "enum": ["placeholder"] }
  }
}
```

Create `benchmarks/schemas/candidate.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "candidate_id",
    "campaign_id",
    "run_id",
    "code_family",
    "parameters",
    "provenance",
    "status"
  ],
  "properties": {
    "candidate_id": { "type": "string", "minLength": 1 },
    "campaign_id": { "type": "string", "minLength": 1 },
    "run_id": { "type": "string", "minLength": 1 },
    "code_family": { "type": "string", "minLength": 1 },
    "parameters": {
      "type": "object",
      "minProperties": 1,
      "additionalProperties": {
        "anyOf": [
          { "type": "string" },
          { "type": "integer" },
          { "type": "number" },
          { "type": "boolean" },
          { "type": "null" }
        ]
      }
    },
    "provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "label"],
      "properties": {
        "kind": { "type": "string", "minLength": 1 },
        "label": { "type": "string", "minLength": 1 }
      }
    },
    "status": { "enum": ["placeholder"] }
  }
}
```

Create `benchmarks/schemas/result-manifest.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "campaign_id",
    "run_id",
    "candidate_id",
    "task_id",
    "decoder_id",
    "status",
    "metrics",
    "created_at"
  ],
  "properties": {
    "campaign_id": { "type": "string", "minLength": 1 },
    "run_id": { "type": "string", "minLength": 1 },
    "candidate_id": { "type": "string", "minLength": 1 },
    "task_id": { "type": "string", "minLength": 1 },
    "decoder_id": { "type": "string", "minLength": 1 },
    "status": { "enum": ["placeholder"] },
    "metrics": {
      "type": "object",
      "minProperties": 1,
      "additionalProperties": {
        "type": ["number", "null"]
      }
    },
    "created_at": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"
    }
  }
}
```

- [ ] **Step 5: Add the example campaign, task, decoder, and suite**

Create `campaigns/examples/rotated-surface-baseline/campaign.json`:

```json
{
  "id": "rotated-surface-baseline",
  "title": "Rotated Surface Baseline",
  "objective": "Materialize one placeholder search run for a circuit-backed family.",
  "family_id": "surface-code",
  "default_suite_id": "rotated-surface-baseline-v1",
  "budget": {
    "candidate_limit": 1
  },
  "stop_conditions": {
    "max_candidates": 1
  },
  "random_seed_policy": {
    "mode": "fixed",
    "seed": 7
  }
}
```

Create `campaigns/examples/rotated-surface-baseline/search_space.json`:

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
    }
  ]
}
```

Create `campaigns/examples/rotated-surface-baseline/notes.md`:

```markdown
# Rotated Surface Baseline

This example campaign is intentionally tiny.

- one committed candidate
- one placeholder benchmark task
- one placeholder decoder

Its purpose is to lock down the Phase 1 file contracts for issue `#3`.
```

Create `benchmarks/tasks/rotated-memory-x-cdep-v1.json`:

```json
{
  "id": "rotated-memory-x-cdep-v1",
  "title": "Rotated Memory X under circuit depolarizing noise (placeholder)",
  "observable": "logical_x",
  "noise_model": "cdep",
  "input_type": "circuit-backed-css-code",
  "result_metrics": [
    "logical_error_rate"
  ],
  "execution_status": "placeholder"
}
```

Create `benchmarks/decoders/placeholder-noop-decoder-v1.json`:

```json
{
  "id": "placeholder-noop-decoder-v1",
  "title": "Placeholder No-op Decoder",
  "backend": "placeholder",
  "parameters": {},
  "execution_status": "placeholder"
}
```

Create `benchmarks/suites/rotated-surface-baseline-v1.json`:

```json
{
  "id": "rotated-surface-baseline-v1",
  "title": "Rotated Surface Baseline v1",
  "task_ids": [
    "rotated-memory-x-cdep-v1"
  ],
  "decoder_ids": [
    "placeholder-noop-decoder-v1"
  ],
  "shared_settings": {
    "runner": "placeholder"
  }
}
```

- [ ] **Step 6: Run the source-data test**

Run: `pytest tests/test_search_source_data.py::test_search_example_source_files_validate_against_checked_in_schemas -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add campaigns benchmarks results/search/README.md tests/test_search_source_data.py
git commit -m "feat: add search architecture schemas and example source data"
```

---

### Task 3: Implement Workspace Loading And Real Validation

**Files:**
- Create: `src/autoqec_search/load.py`
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_cli.py`
- Create: `tests/test_search_load.py`

- [ ] **Step 1: Write the failing loader and validate tests**

Create `tests/test_search_load.py`:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from autoqec_search.load import SearchIntegrityError, load_search_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_search_workspace_collects_campaigns_and_contracts() -> None:
    workspace = load_search_workspace(REPO_ROOT)

    assert sorted(workspace.campaigns) == ["rotated-surface-baseline"]
    assert sorted(workspace.search_spaces) == ["rotated-surface-baseline"]
    assert sorted(workspace.tasks) == ["rotated-memory-x-cdep-v1"]
    assert sorted(workspace.decoders) == ["placeholder-noop-decoder-v1"]
    assert sorted(workspace.suites) == ["rotated-surface-baseline-v1"]
    assert workspace.runs == {}
    assert (
        workspace.search_spaces["rotated-surface-baseline"]["candidate_specs"][0]["candidate_id"]
        == "rotated-surface-d3-example"
    )


def test_load_search_workspace_rejects_unknown_default_suite(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

    campaign_path = (
        work_root
        / "campaigns"
        / "examples"
        / "rotated-surface-baseline"
        / "campaign.json"
    )
    payload = json.loads(campaign_path.read_text())
    payload["default_suite_id"] = "missing-suite"
    campaign_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="unknown default_suite_id"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_suite_with_unknown_task(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

    suite_path = work_root / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
    payload = json.loads(suite_path.read_text())
    payload["task_ids"] = ["missing-task"]
    suite_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="unknown task_id"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_suite_with_unknown_decoder(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

    suite_path = work_root / "benchmarks" / "suites" / "rotated-surface-baseline-v1.json"
    payload = json.loads(suite_path.read_text())
    payload["decoder_ids"] = ["missing-decoder"]
    suite_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="unknown decoder_id"):
        load_search_workspace(work_root)
```

Append this test to `tests/test_search_cli.py`:

```python
def test_validate_command_reports_workspace_counts() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "validate",
            "--root",
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "validated search workspace under" in result.stdout
    assert "1 campaigns" in result.stdout
    assert "1 suites" in result.stdout
```

- [ ] **Step 2: Run the tests to verify real validation is still missing**

Run: `pytest tests/test_search_load.py tests/test_search_cli.py::test_validate_command_reports_workspace_counts -v`
Expected: FAIL with `ModuleNotFoundError` for `autoqec_search.load` or with the old placeholder `search workspace root ok`

- [ ] **Step 3: Implement `load.py` and wire `validate` to it**

Create `src/autoqec_search/load.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from jsonschema import Draft202012Validator


class SearchIntegrityError(ValueError):
    """Raised when search-layer files disagree with each other."""


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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _validator(path: Path) -> Draft202012Validator:
    return Draft202012Validator(_load_json(path))


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise SearchIntegrityError(f"missing {label}: {path}")


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

        if search_space["campaign_id"] != campaign["id"]:
            raise SearchIntegrityError(
                f"search_space campaign_id mismatch for {search_space_path}: "
                f"{search_space['campaign_id']} != {campaign['id']}"
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
        items[payload["id"]] = payload
    return items


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
        payload = _load_json(run_spec_path)
        run_spec_validator.validate(payload)

        _require_file(run_root / "env.json", "env artifact")
        _require_file(run_root / "frontier.json", "frontier artifact")
        _require_file(run_root / "leaderboard.csv", "leaderboard artifact")
        _require_file(run_root / "summary.md", "summary artifact")

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
        if payload["decoder_ids"] != suite["decoder_ids"]:
            raise SearchIntegrityError(f"run decoder_ids drift on {run_root}")

        candidates_root = run_root / "candidates"
        if not candidates_root.is_dir():
            raise SearchIntegrityError(f"missing candidates directory: {candidates_root}")

        actual_candidate_ids = sorted(
            path.name for path in candidates_root.iterdir() if path.is_dir()
        )
        expected_candidate_ids = sorted(payload["candidate_ids"])
        if actual_candidate_ids != expected_candidate_ids:
            raise SearchIntegrityError(
                f"candidate directory mismatch for {run_root}: "
                f"{actual_candidate_ids} != {expected_candidate_ids}"
            )

        loaded_candidates: dict[str, LoadedCandidate] = {}
        for candidate_id in payload["candidate_ids"]:
            candidate_root = candidates_root / candidate_id
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

            manifests: dict[tuple[str, str], dict] = {}
            for task_id in payload["task_ids"]:
                for decoder_id in payload["decoder_ids"]:
                    manifest_path = (
                        candidate_root
                        / "evaluations"
                        / task_id
                        / decoder_id
                        / "manifest.json"
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

            loaded_candidates[candidate_id] = LoadedCandidate(
                payload=candidate,
                manifests=manifests,
            )

        runs[f"{payload['campaign_id']}/{payload['run_id']}"] = LoadedRun(
            payload=payload,
            root=run_root,
            candidates=loaded_candidates,
        )

    return runs


def load_search_workspace(root: Path) -> SearchWorkspace:
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
```

Replace `src/autoqec_search/cli.py` with:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autoqec_search.load import SearchIntegrityError, load_search_workspace


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
            print(
                f"validated search workspace under {root}: "
                f"{len(workspace.campaigns)} campaigns, "
                f"{len(workspace.suites)} suites, "
                f"{len(workspace.runs)} runs"
            )
            return 0

    except SearchIntegrityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the new tests**

Run: `pytest tests/test_search_load.py tests/test_search_cli.py::test_validate_command_reports_workspace_counts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/load.py src/autoqec_search/cli.py tests/test_search_cli.py tests/test_search_load.py
git commit -m "feat: validate search workspace files"
```

---

### Task 4: Materialize Placeholder Runs From The Example Campaign

**Files:**
- Create: `src/autoqec_search/render.py`
- Create: `src/autoqec_search/init_run.py`
- Modify: `src/autoqec_search/cli.py`
- Create: `tests/test_search_init_run.py`

- [ ] **Step 1: Write the failing `init-run` tests**

Create `tests/test_search_init_run.py`:

```python
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_search_tree(tmp_path: Path) -> Path:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")
    return work_root


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_init_run_creates_placeholder_run(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "tmp-run",
            "--timestamp",
            "2026-06-09T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr

    run_root = work_root / "results" / "search" / "rotated-surface-baseline" / "tmp-run"
    assert sorted(path.name for path in run_root.iterdir()) == [
        "candidates",
        "env.json",
        "frontier.json",
        "leaderboard.csv",
        "run_spec.json",
        "summary.md",
    ]

    run_spec = _load_json(run_root / "run_spec.json")
    assert run_spec["campaign_id"] == "rotated-surface-baseline"
    assert run_spec["suite_id"] == "rotated-surface-baseline-v1"
    assert run_spec["candidate_ids"] == ["rotated-surface-d3-example"]

    manifest = _load_json(
        run_root
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "placeholder-noop-decoder-v1"
        / "manifest.json"
    )
    assert manifest["status"] == "placeholder"
    assert manifest["metrics"] == {"logical_error_rate": None}


def test_init_run_rejects_existing_run_without_force(tmp_path: Path) -> None:
    work_root = _copy_search_tree(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "tmp-run",
            "--timestamp",
            "2026-06-09T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert first.returncode == 0, first.stderr

    second = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "init-run",
            "--root",
            str(work_root),
            "--campaign",
            "rotated-surface-baseline",
            "--run-id",
            "tmp-run",
            "--timestamp",
            "2026-06-09T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert second.returncode == 1
    assert "run already exists" in second.stderr
```

- [ ] **Step 2: Run the tests to verify `init-run` is still missing**

Run: `pytest tests/test_search_init_run.py -v`
Expected: FAIL with `invalid choice: 'init-run'` or `ImportError` for `autoqec_search.init_run`

- [ ] **Step 3: Implement `render.py`, `init_run.py`, and the `init-run` command**

Create `src/autoqec_search/render.py`:

```python
from __future__ import annotations


def render_summary(campaign: dict, suite: dict, run_spec: dict) -> str:
    lines = [
        "# Search Run Summary",
        "",
        f"- campaign: `{campaign['id']}`",
        f"- suite: `{suite['id']}`",
        f"- run: `{run_spec['run_id']}`",
        f"- mode: `{run_spec['mode']}`",
        f"- candidates: `{len(run_spec['candidate_ids'])}`",
        "",
        "## Tasks",
        "",
    ]
    for task_id in run_spec["task_ids"]:
        lines.append(f"- `{task_id}`")
    lines.extend(["", "## Decoders", ""])
    for decoder_id in run_spec["decoder_ids"]:
        lines.append(f"- `{decoder_id}`")
    return "\n".join(lines).rstrip() + "\n"


def render_leaderboard(manifests: list[dict]) -> str:
    lines = ["candidate_id,task_id,decoder_id,status"]
    for manifest in manifests:
        lines.append(
            ",".join(
                [
                    manifest["candidate_id"],
                    manifest["task_id"],
                    manifest["decoder_id"],
                    manifest["status"],
                ]
            )
        )
    return "\n".join(lines) + "\n"


def render_run_overview(run_spec: dict, placeholder_count: int) -> str:
    return (
        f"campaign: {run_spec['campaign_id']}\n"
        f"run: {run_spec['run_id']}\n"
        f"suite: {run_spec['suite_id']}\n"
        f"candidates: {len(run_spec['candidate_ids'])}\n"
        f"tasks: {', '.join(run_spec['task_ids'])}\n"
        f"decoders: {', '.join(run_spec['decoder_ids'])}\n"
        f"placeholder manifests: {placeholder_count}\n"
    )
```

Create `src/autoqec_search/init_run.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from autoqec_search import __version__
from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.render import render_leaderboard, render_summary


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def _resolve_timestamp(timestamp: str | None) -> str:
    if timestamp is not None:
        return timestamp
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def init_placeholder_run(
    root: Path,
    campaign_id: str,
    run_id: str,
    *,
    timestamp: str | None = None,
    force: bool = False,
) -> Path:
    workspace = load_search_workspace(root)
    if campaign_id not in workspace.campaigns:
        raise SearchIntegrityError(f"unknown campaign_id: {campaign_id}")

    campaign = workspace.campaigns[campaign_id]
    search_space = workspace.search_spaces[campaign_id]
    suite = workspace.suites[campaign["default_suite_id"]]
    created_at = _resolve_timestamp(timestamp)
    run_root = root / "results" / "search" / campaign_id / run_id

    if run_root.exists():
        if not force:
            raise SearchIntegrityError(f"run already exists: {run_root}")
        shutil.rmtree(run_root)

    candidate_ids = [
        candidate_spec["candidate_id"]
        for candidate_spec in search_space["candidate_specs"]
    ]
    run_spec = {
        "campaign_id": campaign["id"],
        "run_id": run_id,
        "suite_id": suite["id"],
        "task_ids": suite["task_ids"],
        "decoder_ids": suite["decoder_ids"],
        "candidate_ids": candidate_ids,
        "created_at": created_at,
        "mode": "placeholder",
    }

    _write_json(run_root / "run_spec.json", run_spec)
    _write_json(
        run_root / "env.json",
        {
            "tool": "autoqec-search",
            "version": __version__,
            "generated_at": created_at,
            "mode": "placeholder",
        },
    )
    _write_json(
        run_root / "frontier.json",
        {
            "campaign_id": campaign["id"],
            "run_id": run_id,
            "items": [],
        },
    )

    manifests_for_csv: list[dict] = []
    for candidate_spec in search_space["candidate_specs"]:
        candidate_root = run_root / "candidates" / candidate_spec["candidate_id"]
        candidate_payload = {
            "candidate_id": candidate_spec["candidate_id"],
            "campaign_id": campaign["id"],
            "run_id": run_id,
            "code_family": candidate_spec["code_family"],
            "parameters": candidate_spec["parameters"],
            "provenance": candidate_spec["provenance"],
            "status": "placeholder",
        }
        _write_json(candidate_root / "candidate.json", candidate_payload)
        _write_json(
            candidate_root / "structure.json",
            {"status": "not-computed", "n": None, "mx": None, "mz": None},
        )
        _write_json(
            candidate_root / "distance.json",
            {"status": "not-computed", "distance": None},
        )

        for task_id in suite["task_ids"]:
            task = workspace.tasks[task_id]
            for decoder_id in suite["decoder_ids"]:
                manifest = {
                    "campaign_id": campaign["id"],
                    "run_id": run_id,
                    "candidate_id": candidate_spec["candidate_id"],
                    "task_id": task_id,
                    "decoder_id": decoder_id,
                    "status": "placeholder",
                    "metrics": {
                        metric_name: None for metric_name in task["result_metrics"]
                    },
                    "created_at": created_at,
                }
                _write_json(
                    candidate_root
                    / "evaluations"
                    / task_id
                    / decoder_id
                    / "manifest.json",
                    manifest,
                )
                manifests_for_csv.append(manifest)

    _write_text(run_root / "leaderboard.csv", render_leaderboard(manifests_for_csv))
    _write_text(run_root / "summary.md", render_summary(campaign, suite, run_spec))
    return run_root
```

Replace `src/autoqec_search/cli.py` with:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autoqec_search.init_run import init_placeholder_run
from autoqec_search.load import SearchIntegrityError, load_search_workspace


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

    init_run_parser = subparsers.add_parser(
        "init-run", help="Create a placeholder run from a campaign"
    )
    init_run_parser.add_argument("--root", default=".")
    init_run_parser.add_argument("--campaign", required=True)
    init_run_parser.add_argument("--run-id", required=True)
    init_run_parser.add_argument("--timestamp", default=None)
    init_run_parser.add_argument("--force", action="store_true")

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
            print(
                f"validated search workspace under {root}: "
                f"{len(workspace.campaigns)} campaigns, "
                f"{len(workspace.suites)} suites, "
                f"{len(workspace.runs)} runs"
            )
            return 0

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

    except SearchIntegrityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the `init-run` tests**

Run: `pytest tests/test_search_init_run.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_search/render.py src/autoqec_search/init_run.py src/autoqec_search/cli.py tests/test_search_init_run.py
git commit -m "feat: materialize placeholder search runs"
```

---

### Task 5: Commit The Example Run And Add `show`

**Files:**
- Modify: `src/autoqec_search/cli.py`
- Modify: `tests/test_search_load.py`
- Modify: `tests/test_search_cli.py`
- Create: `results/search/rotated-surface-baseline/2026-06-09-example/**`

- [ ] **Step 1: Write the failing example-run and `show` tests**

Append this test to `tests/test_search_load.py`:

```python
def test_load_search_workspace_collects_example_run() -> None:
    workspace = load_search_workspace(REPO_ROOT)

    assert sorted(workspace.runs) == ["rotated-surface-baseline/2026-06-09-example"]
    loaded_run = workspace.runs["rotated-surface-baseline/2026-06-09-example"]
    assert loaded_run.payload["suite_id"] == "rotated-surface-baseline-v1"
    assert sorted(loaded_run.candidates) == ["rotated-surface-d3-example"]
```

Append these negative tests to `tests/test_search_load.py`:

```python
def test_load_search_workspace_rejects_candidate_directory_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

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
    payload["candidate_id"] = "mismatched-candidate-id"
    candidate_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="candidate_id mismatch"):
        load_search_workspace(work_root)


def test_load_search_workspace_rejects_manifest_task_mismatch(tmp_path: Path) -> None:
    work_root = tmp_path / "work"
    shutil.copytree(REPO_ROOT / "campaigns", work_root / "campaigns")
    shutil.copytree(REPO_ROOT / "benchmarks", work_root / "benchmarks")
    shutil.copytree(REPO_ROOT / "results", work_root / "results")

    manifest_path = (
        work_root
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
        / "candidates"
        / "rotated-surface-d3-example"
        / "evaluations"
        / "rotated-memory-x-cdep-v1"
        / "placeholder-noop-decoder-v1"
        / "manifest.json"
    )
    payload = json.loads(manifest_path.read_text())
    payload["task_id"] = "wrong-task-id"
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(SearchIntegrityError, match="manifest task_id mismatch"):
        load_search_workspace(work_root)
```

Append this test to `tests/test_search_cli.py`:

```python
def test_show_prints_example_run_summary() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    run_root = (
        REPO_ROOT
        / "results"
        / "search"
        / "rotated-surface-baseline"
        / "2026-06-09-example"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autoqec_search.cli",
            "show",
            "--run",
            str(run_root),
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "campaign: rotated-surface-baseline" in result.stdout
    assert "run: 2026-06-09-example" in result.stdout
    assert "candidates: 1" in result.stdout
    assert "placeholder manifests: 1" in result.stdout
```

- [ ] **Step 2: Run the tests to verify the example run and `show` are still missing**

Run: `pytest tests/test_search_load.py::test_load_search_workspace_collects_example_run tests/test_search_cli.py::test_show_prints_example_run_summary -v`
Expected: FAIL because `results/search/rotated-surface-baseline/2026-06-09-example/` does not exist or because `show` is not yet a valid subcommand

- [ ] **Step 3: Add the `show` command**

Replace `src/autoqec_search/cli.py` with:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autoqec_search.init_run import init_placeholder_run
from autoqec_search.load import SearchIntegrityError, load_search_workspace
from autoqec_search.render import render_run_overview


def _repo_root_from_run(run_root: Path) -> Path:
    if (
        run_root.parent.parent.name != "search"
        or run_root.parent.parent.parent.name != "results"
    ):
        raise SearchIntegrityError(
            "run path must look like results/search/<campaign-id>/<run-id>"
        )
    return run_root.parent.parent.parent.parent


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

    init_run_parser = subparsers.add_parser(
        "init-run", help="Create a placeholder run from a campaign"
    )
    init_run_parser.add_argument("--root", default=".")
    init_run_parser.add_argument("--campaign", required=True)
    init_run_parser.add_argument("--run-id", required=True)
    init_run_parser.add_argument("--timestamp", default=None)
    init_run_parser.add_argument("--force", action="store_true")

    show_parser = subparsers.add_parser("show", help="Print a concise summary of one run")
    show_parser.add_argument("--run", required=True)

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
            print(
                f"validated search workspace under {root}: "
                f"{len(workspace.campaigns)} campaigns, "
                f"{len(workspace.suites)} suites, "
                f"{len(workspace.runs)} runs"
            )
            return 0

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

        if args.command == "show":
            run_root = Path(args.run)
            if not run_root.exists():
                parser.error(f"run root does not exist: {run_root}")
            repo_root = _repo_root_from_run(run_root)
            workspace = load_search_workspace(repo_root)
            run_key = f"{run_root.parent.name}/{run_root.name}"
            if run_key not in workspace.runs:
                raise SearchIntegrityError(f"unknown run: {run_key}")
            loaded_run = workspace.runs[run_key]
            placeholder_count = sum(
                1
                for candidate in loaded_run.candidates.values()
                for manifest in candidate.manifests.values()
                if manifest["status"] == "placeholder"
            )
            print(render_run_overview(loaded_run.payload, placeholder_count), end="")
            return 0

    except SearchIntegrityError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate and commit the example run**

Run:

```bash
python3 -m autoqec_search.cli init-run \
  --root . \
  --campaign rotated-surface-baseline \
  --run-id 2026-06-09-example \
  --timestamp 2026-06-09T00:00:00Z \
  --force
```

Expected: prints `initialized placeholder run at results/search/rotated-surface-baseline/2026-06-09-example`

- [ ] **Step 5: Run the example-run and `show` tests**

Run: `pytest tests/test_search_load.py::test_load_search_workspace_collects_example_run tests/test_search_cli.py::test_show_prints_example_run_summary -v`
Expected: PASS

- [ ] **Step 6: Run full search-layer validation**

Run: `python3 -m autoqec_search.cli validate --root .`
Expected: prints `validated search workspace under .: 1 campaigns, 1 suites, 1 runs`

- [ ] **Step 7: Commit**

```bash
git add src/autoqec_search/cli.py tests/test_search_load.py tests/test_search_cli.py results/search/rotated-surface-baseline/2026-06-09-example
git commit -m "feat: add committed example search run and show command"
```

---

### Task 6: Update Root Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Create: `tests/test_search_docs.py`

- [ ] **Step 1: Write the failing docs test**

Create `tests/test_search_docs.py`:

```python
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_repo_docs_reference_search_layer() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    claude = (REPO_ROOT / "CLAUDE.md").read_text()

    assert "campaigns/" in readme
    assert "benchmarks/" in readme
    assert "autoqec-search" in readme
    assert "results/search/" in claude
    assert "autoqec-search" in claude
```

- [ ] **Step 2: Run the docs test to confirm the repo docs still ignore the search layer**

Run: `pytest tests/test_search_docs.py -v`
Expected: FAIL on one or more missing substrings

- [ ] **Step 3: Update `README.md` and `CLAUDE.md`**

In `README.md`, replace the `What Lives Here` list with:

```markdown
- `.knowledge/`: local paper library and working notes for literature-grounded discussion
- `zoo/`: source-of-truth code cards, evidence records, checked-in finite instances, and derived browse artifacts
- `campaigns/`: human-authored search intent and example search spaces
- `benchmarks/`: reusable benchmark tasks, decoder configs, suites, and search-layer schemas
- `results/search/`: committed example runs plus future runtime search artifacts
- `src/autoqec_zoo/`: Python package for loading, validating, indexing, and rendering the Zoo
- `src/autoqec_search/`: Python package for validating campaign/benchmark contracts and materializing placeholder runs
- `julia/tensorqec_env/`: repository-local Julia environment and scripts for TensorQEC-backed instance generation
- `Makefile`: Zulip bridge helpers plus convenience targets for Zoo and TensorQEC workflows
```

Add this section after `Build the Zoo`:

````markdown
## Search Layer

Phase 1 search architecture scaffolding for issue `#3` lives under:

- `campaigns/`
- `benchmarks/`
- `results/search/`

Validate the committed example data with:

```bash
python3 -m autoqec_search.cli validate --root .
```

Materialize a fresh placeholder run from the example campaign with:

```bash
python3 -m autoqec_search.cli init-run --root . --campaign rotated-surface-baseline --run-id scratch-run
```
````

In `CLAUDE.md`, add this section after `Structured Zoo (\`zoo/\`) — normalized code knowledge`:

````markdown
## Search Layer (`campaigns/`, `benchmarks/`, `results/search/`)

When working on issue `#3` or related search-architecture tasks, keep these boundaries:

- `campaigns/` stores human-authored campaign intent
- `benchmarks/` stores reusable task, decoder, suite, and schema contracts
- `results/search/` stores run artifacts and example runs, not curated Zoo source-of-truth data

Validate the committed search-layer records with:

```sh
python3 -m autoqec_search.cli validate --root .
```
````

- [ ] **Step 4: Run the docs test again**

Run: `pytest tests/test_search_docs.py -v`
Expected: PASS

- [ ] **Step 5: Run the whole targeted search-layer suite**

Run: `pytest tests/test_search_cli.py tests/test_search_source_data.py tests/test_search_load.py tests/test_search_init_run.py tests/test_search_docs.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md tests/test_search_docs.py
git commit -m "docs: describe search layer scaffolding"
```

---

## Final Verification

- [ ] **Step 1: Run the full repo test suite**

Run: `python3 -m pytest`
Expected: PASS

- [ ] **Step 2: Verify the committed example run through the CLI**

Run: `python3 -m autoqec_search.cli show --run results/search/rotated-surface-baseline/2026-06-09-example`
Expected:

```text
campaign: rotated-surface-baseline
run: 2026-06-09-example
suite: rotated-surface-baseline-v1
candidates: 1
tasks: rotated-memory-x-cdep-v1
decoders: placeholder-noop-decoder-v1
placeholder manifests: 1
```

- [ ] **Step 3: Verify the new tree is committed cleanly**

Run: `git status --short`
Expected: no output

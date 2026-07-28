# QEC Zoo Storage and Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working `zoo/` layer for AutoQEC: schema-validated canonical code cards plus paper-level evidence, with deterministic derived indexes, per-code markdown summaries, and a local static browser.

**Architecture:** Keep `zoo/codes/**/card.json` and `zoo/evidence/**/*.json` as the only source of truth. A small Python builder validates those files against checked-in JSON Schemas, enforces cross-file integrity, then regenerates `zoo/views/*.json`, `zoo/codes/**/card.md`, and `zoo/views/site/**`. Canonical cards stay hand-authored in v1; the builder never infers new stable facts from evidence.

**Tech Stack:** Python 3.11+, `jsonschema`, `pytest`, standard-library JSON/HTML rendering, Makefile

---

## File Structure

- `pyproject.toml`: package metadata, runtime/test dependencies, CLI entry point
- `src/autoqec_zoo/__init__.py`: package marker
- `src/autoqec_zoo/cli.py`: `build` command entry point
- `src/autoqec_zoo/load.py`: schema loading, source JSON loading, integrity validation
- `src/autoqec_zoo/build.py`: derived-index build orchestration and file writes
- `src/autoqec_zoo/render_markdown.py`: canonical card markdown projection
- `src/autoqec_zoo/render_site.py`: self-contained static site shell and JS/CSS assets
- `tests/test_cli.py`: CLI smoke tests
- `tests/conftest.py`: add `src/` to `sys.path` for test imports
- `tests/test_source_data.py`: schema validation for checked-in `zoo/` source data
- `tests/test_load.py`: loader and cross-reference integrity tests
- `tests/test_build.py`: derived JSON + markdown generation tests
- `tests/test_site.py`: static site artifact tests
- `zoo/README.md`: local contract for the Zoo layer
- `zoo/schemas/code-card.schema.json`: canonical card schema
- `zoo/schemas/evidence.schema.json`: evidence schema
- `zoo/schemas/view-index.schema.json`: generated-index schema
- `zoo/codes/<slug>/card.json`: canonical source records
- `zoo/evidence/<paper-id>/*.json`: evidence source records
- `Makefile`: `zoo-build` convenience target
- `README.md`: top-level note about the Zoo build command
- `CLAUDE.md`: repo-local guidance to consult and rebuild `zoo/`

### Task 1: Bootstrap the Python Zoo builder package

**Files:**
- Create: `pyproject.toml`
- Create: `src/autoqec_zoo/__init__.py`
- Create: `src/autoqec_zoo/cli.py`
- Create: `tests/conftest.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI smoke test**

```python
# tests/conftest.py
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
```

```python
# tests/test_cli.py
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_build_command_rejects_missing_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-zoo"
    repo_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "autoqec_zoo.cli", "build", "--root", str(missing_root)],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert "zoo root does not exist" in result.stderr
```

- [ ] **Step 2: Run the test to verify the module is missing**

Run: `pytest tests/test_cli.py::test_build_command_rejects_missing_root -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoqec_zoo'`

- [ ] **Step 3: Add the package metadata and minimal CLI**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "autoqec-zoo"
version = "0.1.0"
description = "Structured QEC Zoo builder for AutoQEC"
requires-python = ">=3.11"
dependencies = [
  "jsonschema>=4.23,<5"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2,<9"
]

[project.scripts]
autoqec-zoo = "autoqec_zoo.cli:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```python
# src/autoqec_zoo/__init__.py
"""AutoQEC Zoo builder package."""
```

```python
# src/autoqec_zoo/cli.py
from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoqec-zoo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Validate and build Zoo artifacts")
    build_parser.add_argument("--root", default="zoo", help="Path to the zoo root directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        root = Path(args.root)
        if not root.exists():
            parser.error(f"zoo root does not exist: {root}")
        print(f"zoo root ok: {root}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the smoke test again**

Run: `pytest tests/test_cli.py::test_build_command_rejects_missing_root -v`
Expected: PASS

- [ ] **Step 5: Commit the bootstrap**

```bash
git add pyproject.toml src/autoqec_zoo/__init__.py src/autoqec_zoo/cli.py tests/conftest.py tests/test_cli.py
git commit -m "feat: bootstrap zoo builder package"
```

### Task 2: Check in schemas and seed source-of-truth Zoo data

**Files:**
- Create: `zoo/README.md`
- Create: `zoo/schemas/code-card.schema.json`
- Create: `zoo/schemas/evidence.schema.json`
- Create: `zoo/schemas/view-index.schema.json`
- Create: `zoo/codes/surface-code/card.json`
- Create: `zoo/codes/rotated-surface-code/card.json`
- Create: `zoo/codes/bivariate-bicycle-code/card.json`
- Create: `zoo/evidence/2408.10001/bivariate-bicycle-code.parameters.json`
- Create: `tests/test_source_data.py`

- [ ] **Step 1: Write the failing source-data schema test**

```python
# tests/test_source_data.py
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
ZOO_ROOT = REPO_ROOT / "zoo"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_seed_cards_and_evidence_validate_against_checked_in_schemas() -> None:
    code_schema = _load_json(ZOO_ROOT / "schemas" / "code-card.schema.json")
    evidence_schema = _load_json(ZOO_ROOT / "schemas" / "evidence.schema.json")

    code_validator = Draft202012Validator(code_schema)
    evidence_validator = Draft202012Validator(evidence_schema)

    for rel_path in [
        "codes/surface-code/card.json",
        "codes/rotated-surface-code/card.json",
        "codes/bivariate-bicycle-code/card.json",
    ]:
        code_validator.validate(_load_json(ZOO_ROOT / rel_path))

    evidence_validator.validate(
        _load_json(ZOO_ROOT / "evidence/2408.10001/bivariate-bicycle-code.parameters.json")
    )
```

- [ ] **Step 2: Run the test to verify the checked-in Zoo data is still missing**

Run: `pytest tests/test_source_data.py::test_seed_cards_and_evidence_validate_against_checked_in_schemas -v`
Expected: FAIL with `FileNotFoundError` under `zoo/schemas/` or `zoo/codes/`

- [ ] **Step 3: Add the README and schemas**

````markdown
# zoo/README.md
# AutoQEC Zoo

This directory stores structured code knowledge derived from papers.

## Source of truth

- `codes/**/card.json`: canonical code cards
- `evidence/**/*.json`: paper-level evidence

## Derived artifacts

- `codes/**/card.md`
- `views/*.json`
- `views/browse.md`
- `views/site/**`

Do not hand-edit derived artifacts. Rebuild them with:

```bash
python3 -m autoqec_zoo.cli build --root zoo
```
````

```json
// zoo/schemas/code-card.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "kind",
    "title",
    "aliases",
    "summary",
    "construction",
    "parameters",
    "assumptions",
    "known_decoders",
    "distance_methods",
    "relations",
    "evidence_refs",
    "source_refs",
    "updated_at"
  ],
  "properties": {
    "id": { "type": "string", "minLength": 1 },
    "kind": { "enum": ["code_family", "code_variant"] },
    "title": { "type": "string", "minLength": 1 },
    "family": { "type": "string" },
    "aliases": {
      "type": "array",
      "items": { "type": "string" }
    },
    "summary": { "type": "string", "minLength": 1 },
    "construction": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "description"],
      "properties": {
        "type": { "type": "string", "minLength": 1 },
        "description": { "type": "string", "minLength": 1 }
      }
    },
    "parameters": {
      "type": "object",
      "additionalProperties": { "type": ["string", "number", "boolean", "null"] }
    },
    "assumptions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "known_decoders": {
      "type": "array",
      "items": { "type": "string" }
    },
    "distance_methods": {
      "type": "array",
      "items": { "type": "string" }
    },
    "relations": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["type", "target"],
        "properties": {
          "type": { "type": "string", "minLength": 1 },
          "target": { "type": "string", "minLength": 1 }
        }
      }
    },
    "evidence_refs": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "source_refs": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "updated_at": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
    }
  }
}
```

```json
// zoo/schemas/evidence.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "paper_id",
    "code_id",
    "claim_type",
    "title",
    "context",
    "claim",
    "provenance",
    "uncertainty_flags"
  ],
  "properties": {
    "id": { "type": "string", "minLength": 1 },
    "paper_id": { "type": "string", "minLength": 1 },
    "code_id": { "type": "string", "minLength": 1 },
    "claim_type": {
      "enum": [
        "construction_note",
        "parameter_claim",
        "decoder_claim",
        "distance_claim",
        "threshold_evidence",
        "relation_claim"
      ]
    },
    "title": { "type": "string", "minLength": 1 },
    "context": {
      "type": "object",
      "additionalProperties": false,
      "required": ["noise_model", "decoder", "distance_method", "assumptions", "parameter_point"],
      "properties": {
        "noise_model": { "type": ["string", "null"] },
        "decoder": { "type": ["string", "null"] },
        "distance_method": { "type": ["string", "null"] },
        "assumptions": {
          "type": "array",
          "items": { "type": "string" }
        },
        "parameter_point": {
          "type": "object",
          "additionalProperties": true
        }
      }
    },
    "claim": {
      "type": "object",
      "additionalProperties": false,
      "required": ["statement", "value", "unit", "qualifiers"],
      "properties": {
        "statement": { "type": "string", "minLength": 1 },
        "value": {},
        "unit": { "type": ["string", "null"] },
        "qualifiers": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    "provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["section", "quote_ref", "confidence"],
      "properties": {
        "section": { "type": "string", "minLength": 1 },
        "quote_ref": { "type": "string", "minLength": 1 },
        "confidence": { "enum": ["low", "medium", "high"] }
      }
    },
    "uncertainty_flags": {
      "type": "array",
      "items": {
        "enum": [
          "unresolved_code_identity",
          "conflicting_claims",
          "insufficient_evidence",
          "schema_valid_but_semantically_uncertain"
        ]
      }
    }
  }
}
```

```json
// zoo/schemas/view-index.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["generated_at", "items"],
  "properties": {
    "generated_at": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object"
      }
    }
  }
}
```

- [ ] **Step 4: Add the seed canonical cards and one evidence record**

```json
// zoo/codes/surface-code/card.json
{
  "id": "surface-code",
  "kind": "code_family",
  "title": "Surface Code",
  "aliases": ["toric code on a planar patch"],
  "summary": "A topological stabilizer-code family defined on two-dimensional lattices with local parity checks.",
  "construction": {
    "type": "topological_css",
    "description": "Surface-code families place X and Z stabilizers on a two-dimensional cell complex with boundary choices defining variants."
  },
  "parameters": {
    "logical_qubits": "variant dependent",
    "distance_formula": "d",
    "rate_scaling": "k / n -> 0"
  },
  "assumptions": [
    "2D local geometry",
    "stabilizer syndrome measurements"
  ],
  "known_decoders": [
    "MWPM",
    "Union-Find",
    "Tensor-network decoder"
  ],
  "distance_methods": [
    "analytical from geometry"
  ],
  "relations": [
    {
      "type": "has_variant",
      "target": "rotated-surface-code"
    }
  ],
  "evidence_refs": [],
  "source_refs": [],
  "updated_at": "2026-05-27"
}
```

```json
// zoo/codes/rotated-surface-code/card.json
{
  "id": "rotated-surface-code",
  "kind": "code_variant",
  "title": "Rotated Surface Code",
  "family": "surface-code",
  "aliases": ["rotated planar code"],
  "summary": "A surface-code variant with a rotated lattice layout that reduces physical-qubit count for the same code distance.",
  "construction": {
    "type": "topological_css",
    "description": "Defined on a rotated square lattice with boundary choices that preserve one logical qubit while compressing the layout."
  },
  "parameters": {
    "logical_qubits": "typically 1",
    "distance_formula": "d",
    "block_length_formula": "2d^2 - 1"
  },
  "assumptions": [
    "2D nearest-neighbor geometry",
    "stabilizer measurements available"
  ],
  "known_decoders": [
    "MWPM",
    "Union-Find"
  ],
  "distance_methods": [
    "analytical from geometry"
  ],
  "relations": [
    {
      "type": "variant_of",
      "target": "surface-code"
    }
  ],
  "evidence_refs": [],
  "source_refs": [],
  "updated_at": "2026-05-27"
}
```

```json
// zoo/codes/bivariate-bicycle-code/card.json
{
  "id": "bivariate-bicycle-code",
  "kind": "code_family",
  "title": "Bivariate Bicycle Code",
  "aliases": ["BB code"],
  "summary": "A qLDPC code family built from pairs of bivariate circulant polynomials.",
  "construction": {
    "type": "qldpc_css",
    "description": "Constructed from commuting parity-check matrices derived from bivariate bicycle polynomial data."
  },
  "parameters": {
    "logical_qubits": "construction dependent",
    "distance_formula": "not fixed in closed form",
    "rate_scaling": "family dependent"
  },
  "assumptions": [
    "CSS construction",
    "circulant polynomial input data"
  ],
  "known_decoders": [
    "belief propagation",
    "ordered statistics decoding"
  ],
  "distance_methods": [
    "algorithmic search",
    "matrix-based lower-bound analysis"
  ],
  "relations": [],
  "evidence_refs": [
    "2408.10001:bivariate-bicycle-code.parameters"
  ],
  "source_refs": [
    "2408.10001"
  ],
  "updated_at": "2026-05-27"
}
```

```json
// zoo/evidence/2408.10001/bivariate-bicycle-code.parameters.json
{
  "id": "2408.10001:bivariate-bicycle-code.parameters",
  "paper_id": "2408.10001",
  "code_id": "bivariate-bicycle-code",
  "claim_type": "parameter_claim",
  "title": "Representative finite-length BB-code parameter points",
  "context": {
    "noise_model": null,
    "decoder": null,
    "distance_method": "matrix-based search",
    "assumptions": [
      "finite-size code instances are generated from coprime bivariate polynomial choices"
    ],
    "parameter_point": {
      "instance_keys": ["L18-K8-D4", "L90-K8-D10"]
    }
  },
  "claim": {
    "statement": "The paper reports explicit finite-length parameter sets for coprime bivariate bicycle constructions.",
    "value": null,
    "unit": null,
    "qualifiers": [
      "paper-specific finite-length examples"
    ]
  },
  "provenance": {
    "section": "Code constructions",
    "quote_ref": "construction:p4:table1",
    "confidence": "medium"
  },
  "uncertainty_flags": []
}
```

- [ ] **Step 5: Run the schema test again**

Run: `pytest tests/test_source_data.py::test_seed_cards_and_evidence_validate_against_checked_in_schemas -v`
Expected: PASS

- [ ] **Step 6: Commit the checked-in schemas and seed data**

```bash
git add zoo/README.md zoo/schemas/*.json zoo/codes/*/card.json zoo/evidence/2408.10001/*.json tests/test_source_data.py
git commit -m "feat: add zoo schemas and seed source data"
```

### Task 3: Implement source loading and cross-file integrity checks

**Files:**
- Create: `src/autoqec_zoo/load.py`
- Create: `tests/test_load.py`

- [ ] **Step 1: Write failing loader and integrity tests**

```python
# tests/test_load.py
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from autoqec_zoo.load import IntegrityError, load_zoo


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_zoo_collects_cards_and_evidence() -> None:
    dataset = load_zoo(REPO_ROOT / "zoo")

    assert sorted(dataset.cards) == [
        "bivariate-bicycle-code",
        "rotated-surface-code",
        "surface-code",
    ]
    assert sorted(dataset.evidence) == [
        "2408.10001:bivariate-bicycle-code.parameters"
    ]
    assert dataset.cards["rotated-surface-code"]["family"] == "surface-code"


def test_load_zoo_rejects_missing_evidence_ref(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    card_path = work_root / "codes" / "surface-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["evidence_refs"].append("missing:surface-code.claim")
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="missing evidence_ref"):
        load_zoo(work_root)


def test_load_zoo_rejects_evidence_with_unknown_code_id(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    evidence_path = work_root / "evidence" / "2408.10001" / "bivariate-bicycle-code.parameters.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["code_id"] = "unknown-code"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")

    with pytest.raises(IntegrityError, match="unknown code_id"):
        load_zoo(work_root)
```

- [ ] **Step 2: Run the loader tests to verify the functions are still missing**

Run: `pytest tests/test_load.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `autoqec_zoo.load`

- [ ] **Step 3: Implement the loader and integrity checks**

```python
# src/autoqec_zoo/load.py
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from jsonschema import Draft202012Validator


class IntegrityError(ValueError):
    """Raised when source-of-truth files disagree with each other."""


@dataclass(frozen=True)
class ZooDataset:
    cards: dict[str, dict]
    evidence: dict[str, dict]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _validator(schema_path: Path) -> Draft202012Validator:
    return Draft202012Validator(_load_json(schema_path))


def load_zoo(root: Path) -> ZooDataset:
    schema_root = root / "schemas"
    card_validator = _validator(schema_root / "code-card.schema.json")
    evidence_validator = _validator(schema_root / "evidence.schema.json")

    cards: dict[str, dict] = {}
    evidence_by_id: dict[str, dict] = {}

    for card_path in sorted((root / "codes").glob("*/card.json")):
        card = _load_json(card_path)
        card_validator.validate(card)
        cards[card["id"]] = card

    for evidence_path in sorted((root / "evidence").glob("*/*.json")):
        evidence = _load_json(evidence_path)
        evidence_validator.validate(evidence)

        parent_paper_id = evidence_path.parent.name
        if evidence["paper_id"] != parent_paper_id:
            raise IntegrityError(
                f"paper_id mismatch for {evidence_path}: "
                f"{evidence['paper_id']} != {parent_paper_id}"
            )

        evidence_by_id[evidence["id"]] = evidence

    for card_id, card in cards.items():
        if card["kind"] == "code_variant" and "family" not in card:
            raise IntegrityError(f"variant card missing family: {card_id}")

        if card.get("family") and card["family"] not in cards:
            raise IntegrityError(f"unknown family for {card_id}: {card['family']}")

        for evidence_ref in card["evidence_refs"]:
            if evidence_ref not in evidence_by_id:
                raise IntegrityError(f"missing evidence_ref on {card_id}: {evidence_ref}")
            if evidence_by_id[evidence_ref]["paper_id"] not in card["source_refs"]:
                raise IntegrityError(
                    f"source_refs missing paper for {card_id}: {evidence_by_id[evidence_ref]['paper_id']}"
                )

    for evidence_id, evidence in evidence_by_id.items():
        if evidence["code_id"] not in cards:
            raise IntegrityError(f"unknown code_id on {evidence_id}: {evidence['code_id']}")

    return ZooDataset(cards=cards, evidence=evidence_by_id)
```

- [ ] **Step 4: Run the loader tests again**

Run: `pytest tests/test_load.py -v`
Expected: PASS

- [ ] **Step 5: Commit the loader**

```bash
git add src/autoqec_zoo/load.py tests/test_load.py
git commit -m "feat: validate zoo source records"
```

### Task 4: Build derived indexes and per-code markdown

**Files:**
- Create: `src/autoqec_zoo/build.py`
- Create: `src/autoqec_zoo/render_markdown.py`
- Create: `tests/test_build.py`

- [ ] **Step 1: Write failing build-output tests**

```python
# tests/test_build.py
from __future__ import annotations

import json
import shutil
from pathlib import Path

from autoqec_zoo.build import build_zoo


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_writes_indexes_markdown_and_browse_page(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-27")

    code_index = json.loads((work_root / "views" / "code-index.json").read_text())
    family_index = json.loads((work_root / "views" / "family-index.json").read_text())
    relation_index = json.loads((work_root / "views" / "relation-index.json").read_text())
    evidence_index = json.loads((work_root / "views" / "evidence-index.json").read_text())
    card_md = (work_root / "codes" / "bivariate-bicycle-code" / "card.md").read_text()
    browse_md = (work_root / "views" / "browse.md").read_text()

    assert code_index["generated_at"] == "2026-05-27"
    assert [item["id"] for item in code_index["items"]] == [
        "bivariate-bicycle-code",
        "rotated-surface-code",
        "surface-code",
    ]
    family_items = {item["id"]: item for item in family_index["items"]}
    assert family_items["surface-code"]["variant_ids"] == ["rotated-surface-code"]
    assert relation_index["items"][0] == {
        "source_id": "rotated-surface-code",
        "type": "variant_of",
        "target_id": "surface-code"
    }
    assert evidence_index["items"][0]["id"] == "2408.10001:bivariate-bicycle-code.parameters"
    assert "## Canonical Facts" in card_md
    assert "## Paper-Specific Evidence" in card_md
    assert "The paper reports explicit finite-length parameter sets" in card_md.split("## Paper-Specific Evidence", 1)[1]
    assert "# QEC Zoo Browse" in browse_md


def test_build_aggregates_multiple_evidence_records_for_one_code(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    extra_evidence = {
        "id": "2408.10001:bivariate-bicycle-code.decoder",
        "paper_id": "2408.10001",
        "code_id": "bivariate-bicycle-code",
        "claim_type": "decoder_claim",
        "title": "Decoder note for finite-length BB codes",
        "context": {
            "noise_model": "depolarizing noise",
            "decoder": "belief propagation",
            "distance_method": None,
            "assumptions": ["finite-length numerical study"],
            "parameter_point": {"instance_keys": ["L18-K8-D4"]}
        },
        "claim": {
            "statement": "The paper discusses decoder behavior for representative finite-length instances.",
            "value": None,
            "unit": None,
            "qualifiers": ["paper-local decoder evidence"]
        },
        "provenance": {
            "section": "Decoder discussion",
            "quote_ref": "decoder:p6:para1",
            "confidence": "medium"
        },
        "uncertainty_flags": []
    }
    (work_root / "evidence" / "2408.10001" / "bivariate-bicycle-code.decoder.json").write_text(
        json.dumps(extra_evidence, indent=2) + "\n"
    )

    card_path = work_root / "codes" / "bivariate-bicycle-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["evidence_refs"].append("2408.10001:bivariate-bicycle-code.decoder")
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    build_zoo(work_root, generated_at="2026-05-27")

    code_index = json.loads((work_root / "views" / "code-index.json").read_text())
    code_items = {item["id"]: item for item in code_index["items"]}
    assert code_items["bivariate-bicycle-code"]["evidence_count"] == 2


def test_build_is_deterministic_for_same_input(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-27")
    first_code_index = (work_root / "views" / "code-index.json").read_text()
    first_browse = (work_root / "views" / "browse.md").read_text()

    build_zoo(work_root, generated_at="2026-05-27")
    second_code_index = (work_root / "views" / "code-index.json").read_text()
    second_browse = (work_root / "views" / "browse.md").read_text()

    assert second_code_index == first_code_index
    assert second_browse == first_browse


def test_conflicting_claims_stay_out_of_canonical_facts(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    conflict_evidence = {
        "id": "2408.10001:bivariate-bicycle-code.threshold-conflict",
        "paper_id": "2408.10001",
        "code_id": "bivariate-bicycle-code",
        "claim_type": "threshold_evidence",
        "title": "Conflicting threshold estimate",
        "context": {
            "noise_model": "phenomenological noise",
            "decoder": "belief propagation",
            "distance_method": None,
            "assumptions": ["finite-size scaling fit"],
            "parameter_point": {"distance_values": [8, 10, 12]}
        },
        "claim": {
            "statement": "Threshold is reported around 0.8% under a paper-specific fit.",
            "value": 0.008,
            "unit": "physical_error_rate",
            "qualifiers": ["conflicting threshold estimate"]
        },
        "provenance": {
            "section": "Threshold results",
            "quote_ref": "threshold:p7:para2",
            "confidence": "medium"
        },
        "uncertainty_flags": ["conflicting_claims"]
    }
    (work_root / "evidence" / "2408.10001" / "bivariate-bicycle-code.threshold-conflict.json").write_text(
        json.dumps(conflict_evidence, indent=2) + "\n"
    )

    card_path = work_root / "codes" / "bivariate-bicycle-code" / "card.json"
    card = json.loads(card_path.read_text())
    card["evidence_refs"].append("2408.10001:bivariate-bicycle-code.threshold-conflict")
    card_path.write_text(json.dumps(card, indent=2) + "\n")

    build_zoo(work_root, generated_at="2026-05-27")

    card_md = (work_root / "codes" / "bivariate-bicycle-code" / "card.md").read_text()
    canonical_section, evidence_section = card_md.split("## Paper-Specific Evidence", 1)

    assert "Threshold is reported around 0.8% under a paper-specific fit." not in canonical_section
    assert "Threshold is reported around 0.8% under a paper-specific fit." in evidence_section
```

- [ ] **Step 2: Run the build test to verify the builder is missing**

Run: `pytest tests/test_build.py::test_build_writes_indexes_markdown_and_browse_page -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `autoqec_zoo.build`

- [ ] **Step 3: Implement markdown rendering and derived-index generation**

```python
# src/autoqec_zoo/render_markdown.py
from __future__ import annotations


def render_card_markdown(card: dict, evidence_records: list[dict]) -> str:
    lines = [
        f"# {card['title']}",
        "",
        card["summary"],
        "",
        "## Canonical Facts",
        "",
        f"- `id`: `{card['id']}`",
        f"- `kind`: `{card['kind']}`",
    ]

    if card.get("family"):
        lines.append(f"- `family`: `{card['family']}`")

    if card["aliases"]:
        lines.extend(["", "### Aliases", ""])
        lines.extend(f"- {alias}" for alias in card["aliases"])

    lines.extend(
        [
            "",
            "### Construction",
            "",
            f"- `type`: `{card['construction']['type']}`",
            f"- {card['construction']['description']}",
            "",
            "### Parameters",
            "",
        ]
    )
    lines.extend(f"- `{key}`: {value}" for key, value in card["parameters"].items())

    lines.extend(["", "### Assumptions", ""])
    lines.extend(f"- {item}" for item in card["assumptions"])

    lines.extend(["", "### Known Decoders", ""])
    lines.extend(f"- {item}" for item in card["known_decoders"])

    lines.extend(["", "### Distance Methods", ""])
    lines.extend(f"- {item}" for item in card["distance_methods"])

    lines.extend(["", "### Relations", ""])
    if card["relations"]:
        lines.extend(f"- `{rel['type']}` -> `{rel['target']}`" for rel in card["relations"])
    else:
        lines.append("- None")

    lines.extend(["", "## Paper-Specific Evidence", ""])
    if evidence_records:
        for evidence in evidence_records:
            lines.extend(
                [
                    f"### {evidence['title']}",
                    "",
                    f"- `paper_id`: `{evidence['paper_id']}`",
                    f"- `claim_type`: `{evidence['claim_type']}`",
                    f"- `statement`: {evidence['claim']['statement']}",
                    f"- `quote_ref`: `{evidence['provenance']['quote_ref']}`",
                    "",
                ]
            )
    else:
        lines.extend(["No linked evidence yet.", ""])

    lines.extend(["## Source Papers", ""])
    if card["source_refs"]:
        lines.extend(f"- `{paper_id}`" for paper_id in card["source_refs"])
    else:
        lines.append("- None")

    return "\n".join(lines).rstrip() + "\n"
```

```python
# src/autoqec_zoo/build.py
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from autoqec_zoo.load import ZooDataset, load_zoo
from autoqec_zoo.render_markdown import render_card_markdown


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _build_code_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        items.append(
            {
                "id": card["id"],
                "title": card["title"],
                "kind": card["kind"],
                "family": card.get("family"),
                "summary": card["summary"],
                "source_count": len(card["source_refs"]),
                "evidence_count": len(card["evidence_refs"]),
                "known_decoders": card["known_decoders"]
            }
        )
    return {"generated_at": generated_at, "items": items}


def _build_family_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        if card["kind"] != "code_family":
            continue
        variants = sorted(
            variant["id"]
            for variant in dataset.cards.values()
            if variant.get("family") == card["id"]
        )
        items.append({"id": card["id"], "title": card["title"], "variant_ids": variants})
    return {"generated_at": generated_at, "items": items}


def _build_relation_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        for relation in card["relations"]:
            if relation["type"] == "has_variant":
                continue
            items.append(
                {
                    "source_id": card["id"],
                    "type": relation["type"],
                    "target_id": relation["target"]
                }
            )
    return {"generated_at": generated_at, "items": items}


def _build_evidence_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for evidence in sorted(dataset.evidence.values(), key=lambda item: item["id"]):
        items.append(
            {
                "id": evidence["id"],
                "paper_id": evidence["paper_id"],
                "code_id": evidence["code_id"],
                "claim_type": evidence["claim_type"],
                "title": evidence["title"],
                "uncertainty_flags": evidence["uncertainty_flags"]
            }
        )
    return {"generated_at": generated_at, "items": items}


def _render_browse_markdown(dataset: ZooDataset) -> str:
    lines = ["# QEC Zoo Browse", "", "## By Code", ""]
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        lines.append(f"- `{card['id']}` — {card['summary']}")
    lines.extend(["", "## By Paper", ""])
    for evidence in sorted(dataset.evidence.values(), key=lambda item: item["id"]):
        lines.append(f"- `{evidence['paper_id']}` -> `{evidence['code_id']}` ({evidence['claim_type']})")
    return "\n".join(lines).rstrip() + "\n"


def build_zoo(root: Path, generated_at: str) -> None:
    dataset = load_zoo(root)
    view_schema = json.loads((root / "schemas" / "view-index.schema.json").read_text())
    validator = Draft202012Validator(view_schema)

    views = {
        "code-index.json": _build_code_index(dataset, generated_at),
        "family-index.json": _build_family_index(dataset, generated_at),
        "relation-index.json": _build_relation_index(dataset, generated_at),
        "evidence-index.json": _build_evidence_index(dataset, generated_at),
    }

    for filename, payload in views.items():
        validator.validate(payload)
        _write_json(root / "views" / filename, payload)

    for card in dataset.cards.values():
        evidence_records = [dataset.evidence[item] for item in card["evidence_refs"]]
        (root / "codes" / card["id"] / "card.md").write_text(
            render_card_markdown(card, evidence_records)
        )

    (root / "views" / "browse.md").write_text(_render_browse_markdown(dataset))
```

- [ ] **Step 4: Run the build test again**

Run: `pytest tests/test_build.py::test_build_writes_indexes_markdown_and_browse_page -v`
Expected: PASS

- [ ] **Step 5: Commit the derived-artifact builder**

```bash
git add src/autoqec_zoo/build.py src/autoqec_zoo/render_markdown.py tests/test_build.py
git commit -m "feat: build derived zoo indexes and markdown"
```

### Task 5: Render the local static browser and wire the full CLI build command

**Files:**
- Create: `src/autoqec_zoo/render_site.py`
- Modify: `src/autoqec_zoo/build.py`
- Modify: `src/autoqec_zoo/cli.py`
- Modify: `tests/test_cli.py`
- Create: `tests/test_site.py`
- Modify: `Makefile`

- [ ] **Step 1: Write failing site and CLI integration tests**

```python
# tests/test_site.py
from __future__ import annotations

import shutil
from pathlib import Path

from autoqec_zoo.build import build_zoo


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_writes_static_site_shell_with_embedded_state(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    build_zoo(work_root, generated_at="2026-05-27")

    html = (work_root / "views" / "site" / "index.html").read_text()
    js = (work_root / "views" / "site" / "assets" / "app.js").read_text()
    css = (work_root / "views" / "site" / "assets" / "styles.css").read_text()

    assert '<script id="app-state" type="application/json">' in html
    assert "Canonical Facts" in html
    assert "Paper-Specific Evidence" in html
    assert "renderCodeList" in js
    assert ".layout" in css
```

```python
# tests/test_cli.py
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_build_command_rejects_missing_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-zoo"
    repo_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "autoqec_zoo.cli", "build", "--root", str(missing_root)],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 2
    assert "zoo root does not exist" in result.stderr


def test_build_command_writes_expected_artifacts(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    work_root = tmp_path / "repo"
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    shutil.copytree(repo_root / "zoo", work_root / "zoo")

    result = subprocess.run(
        [sys.executable, "-m", "autoqec_zoo.cli", "build", "--root", str(work_root / "zoo")],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "built zoo artifacts" in result.stdout
    assert (work_root / "zoo" / "views" / "site" / "index.html").exists()
```

- [ ] **Step 2: Run the site and CLI tests to verify the renderer is still missing**

Run: `pytest tests/test_site.py tests/test_cli.py::test_build_command_writes_expected_artifacts -v`
Expected: FAIL because `views/site/` artifacts are not generated and the CLI still only prints `zoo root ok`

- [ ] **Step 3: Implement the site renderer and full build command**

```python
# src/autoqec_zoo/render_site.py
from __future__ import annotations

import json


def render_site_assets(app_state: dict) -> tuple[str, str, str]:
    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AutoQEC Zoo</title>
    <link rel="stylesheet" href="assets/styles.css">
  </head>
  <body>
    <div class="layout">
      <aside class="sidebar">
        <h1>AutoQEC Zoo</h1>
        <label class="label" for="family-filter">Family</label>
        <select id="family-filter"></select>
        <div id="code-list"></div>
      </aside>
      <main class="detail">
        <section>
          <h2>Canonical Facts</h2>
          <div id="canonical-panel"></div>
        </section>
        <section>
          <h2>Paper-Specific Evidence</h2>
          <div id="evidence-panel"></div>
        </section>
      </main>
    </div>
    <script id="app-state" type="application/json">{json.dumps(app_state)}</script>
    <script src="assets/app.js"></script>
  </body>
</html>
"""

    js = """const appState = JSON.parse(document.getElementById('app-state').textContent);
const codeList = document.getElementById('code-list');
const familyFilter = document.getElementById('family-filter');
const canonicalPanel = document.getElementById('canonical-panel');
const evidencePanel = document.getElementById('evidence-panel');

function renderCodeList() {
  const family = familyFilter.value;
  const filtered = appState.codes.filter((item) => !family || item.family === family || item.id === family);
  codeList.innerHTML = filtered
    .map((item) => `<button class="code-item" data-code-id="${item.id}">${item.title}</button>`)
    .join('');
  codeList.querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => renderDetail(button.dataset.codeId));
  });
}

function renderDetail(codeId) {
  const card = appState.cards[codeId];
  const evidence = appState.evidence.filter((item) => item.code_id === codeId);
  canonicalPanel.innerHTML = `
    <h3>${card.title}</h3>
    <p>${card.summary}</p>
    <ul>
      <li><strong>Kind:</strong> ${card.kind}</li>
      <li><strong>Family:</strong> ${card.family || '-'}</li>
      <li><strong>Decoders:</strong> ${card.known_decoders.join(', ') || '-'}</li>
    </ul>
  `;
  evidencePanel.innerHTML = evidence.length
    ? evidence.map((item) => `<article><h3>${item.title}</h3><p>${item.claim.statement}</p><p><code>${item.paper_id}</code> · <code>${item.claim_type}</code></p></article>`).join('')
    : '<p>No linked evidence yet.</p>';
}

function init() {
  const families = ['', ...new Set(appState.codes.map((item) => item.family).filter(Boolean))];
  familyFilter.innerHTML = families.map((family) => `<option value="${family}">${family || 'All families'}</option>`).join('');
  familyFilter.addEventListener('change', renderCodeList);
  renderCodeList();
  renderDetail(appState.codes[0].id);
}

init();
"""

    css = """:root { color-scheme: light; font-family: ui-sans-serif, system-ui, sans-serif; }
body { margin: 0; background: #f5f7fa; color: #18212f; }
.layout { display: grid; grid-template-columns: 320px 1fr; min-height: 100vh; }
.sidebar { padding: 20px; border-right: 1px solid #d9e1ea; background: #ffffff; }
.detail { padding: 24px; display: grid; gap: 24px; }
.label { display: block; margin-bottom: 8px; font-size: 12px; text-transform: uppercase; color: #607080; }
#family-filter { width: 100%; margin-bottom: 16px; padding: 8px; }
.code-item { width: 100%; text-align: left; margin-bottom: 8px; padding: 10px 12px; border: 1px solid #ccd6e0; background: #fff; cursor: pointer; }
section { background: #fff; border: 1px solid #d9e1ea; padding: 16px; }
article { padding: 12px 0; border-top: 1px solid #e5ebf1; }
article:first-child { border-top: 0; padding-top: 0; }"""

    return html, js, css
```

```python
# src/autoqec_zoo/build.py
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from autoqec_zoo.load import ZooDataset, load_zoo
from autoqec_zoo.render_markdown import render_card_markdown
from autoqec_zoo.render_site import render_site_assets


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _build_code_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        items.append(
            {
                "id": card["id"],
                "title": card["title"],
                "kind": card["kind"],
                "family": card.get("family"),
                "summary": card["summary"],
                "source_count": len(card["source_refs"]),
                "evidence_count": len(card["evidence_refs"]),
                "known_decoders": card["known_decoders"]
            }
        )
    return {"generated_at": generated_at, "items": items}


def _build_family_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        if card["kind"] != "code_family":
            continue
        variants = sorted(
            variant["id"]
            for variant in dataset.cards.values()
            if variant.get("family") == card["id"]
        )
        items.append({"id": card["id"], "title": card["title"], "variant_ids": variants})
    return {"generated_at": generated_at, "items": items}


def _build_relation_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        for relation in card["relations"]:
            if relation["type"] == "has_variant":
                continue
            items.append(
                {
                    "source_id": card["id"],
                    "type": relation["type"],
                    "target_id": relation["target"]
                }
            )
    return {"generated_at": generated_at, "items": items}


def _build_evidence_index(dataset: ZooDataset, generated_at: str) -> dict:
    items = []
    for evidence in sorted(dataset.evidence.values(), key=lambda item: item["id"]):
        items.append(
            {
                "id": evidence["id"],
                "paper_id": evidence["paper_id"],
                "code_id": evidence["code_id"],
                "claim_type": evidence["claim_type"],
                "title": evidence["title"],
                "uncertainty_flags": evidence["uncertainty_flags"]
            }
        )
    return {"generated_at": generated_at, "items": items}


def _render_browse_markdown(dataset: ZooDataset) -> str:
    lines = ["# QEC Zoo Browse", "", "## By Code", ""]
    for card in sorted(dataset.cards.values(), key=lambda item: item["id"]):
        lines.append(f"- `{card['id']}` — {card['summary']}")
    lines.extend(["", "## By Paper", ""])
    for evidence in sorted(dataset.evidence.values(), key=lambda item: item["id"]):
        lines.append(f"- `{evidence['paper_id']}` -> `{evidence['code_id']}` ({evidence['claim_type']})")
    return "\n".join(lines).rstrip() + "\n"


def build_zoo(root: Path, generated_at: str) -> None:
    dataset = load_zoo(root)
    view_schema = json.loads((root / "schemas" / "view-index.schema.json").read_text())
    validator = Draft202012Validator(view_schema)

    code_index = _build_code_index(dataset, generated_at)
    family_index = _build_family_index(dataset, generated_at)
    relation_index = _build_relation_index(dataset, generated_at)
    evidence_index = _build_evidence_index(dataset, generated_at)

    for filename, payload in {
        "code-index.json": code_index,
        "family-index.json": family_index,
        "relation-index.json": relation_index,
        "evidence-index.json": evidence_index,
    }.items():
        validator.validate(payload)
        _write_json(root / "views" / filename, payload)

    for card in dataset.cards.values():
        evidence_records = [dataset.evidence[item] for item in card["evidence_refs"]]
        (root / "codes" / card["id"] / "card.md").write_text(
            render_card_markdown(card, evidence_records)
        )

    (root / "views" / "browse.md").write_text(_render_browse_markdown(dataset))

    app_state = {
        "codes": code_index["items"],
        "cards": dataset.cards,
        "evidence": list(dataset.evidence.values()),
        "families": family_index["items"],
        "relations": relation_index["items"]
    }
    html, js, css = render_site_assets(app_state)
    site_root = root / "views" / "site"
    assets_root = site_root / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)
    (site_root / "index.html").write_text(html)
    (assets_root / "app.js").write_text(js)
    (assets_root / "styles.css").write_text(css)
```

```python
# src/autoqec_zoo/cli.py
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from autoqec_zoo.build import build_zoo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoqec-zoo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Validate and build Zoo artifacts")
    build_parser.add_argument("--root", default="zoo", help="Path to the zoo root directory")
    build_parser.add_argument("--date", default=date.today().isoformat(), help="Override the generated_at date")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        root = Path(args.root)
        if not root.exists():
            parser.error(f"zoo root does not exist: {root}")
        build_zoo(root, generated_at=args.date)
        print(f"built zoo artifacts under {root}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

```make
.PHONY: zoo-build

zoo-build:
	python3 -m autoqec_zoo.cli build --root zoo
```

- [ ] **Step 4: Run the site and CLI tests again**

Run: `pytest tests/test_site.py tests/test_cli.py::test_build_command_writes_expected_artifacts -v`
Expected: PASS

- [ ] **Step 5: Commit the site renderer and build command**

```bash
git add src/autoqec_zoo/render_site.py src/autoqec_zoo/build.py src/autoqec_zoo/cli.py tests/test_site.py tests/test_cli.py Makefile
git commit -m "feat: render static zoo browser"
```

### Task 6: Document the workflow and run end-to-end verification

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the top-level README with the Zoo build command**

````markdown
## Structured Zoo Layer

This repo also hosts a structured `zoo/` layer for normalized code cards and paper evidence.

Rebuild the derived Zoo artifacts with:

```bash
make zoo-build
```
````

- [ ] **Step 2: Update `CLAUDE.md` so future work consults `zoo/` alongside `.knowledge/`**

````markdown
## Structured Zoo (`zoo/`) — normalized code knowledge

When answering code-ontology or code-comparison questions, check `zoo/` before re-deriving facts from raw papers.

- `zoo/codes/**/card.json` — canonical stable facts
- `zoo/evidence/**/*.json` — paper-specific claims and parameter points
- `zoo/views/browse.md` — generated human-readable entry point

Regenerate the derived artifacts after editing source records:

```sh
make zoo-build
```
````

- [ ] **Step 3: Run the full test suite**

Run: `pytest -v`
Expected: PASS for `tests/test_cli.py`, `tests/test_source_data.py`, `tests/test_load.py`, `tests/test_build.py`, and `tests/test_site.py`

- [ ] **Step 4: Run the end-to-end builder on the checked-in `zoo/` tree**

Run: `python3 -m autoqec_zoo.cli build --root zoo --date 2026-05-27`
Expected:

```text
built zoo artifacts under zoo
```

And these files should exist:

```text
zoo/codes/surface-code/card.md
zoo/codes/rotated-surface-code/card.md
zoo/codes/bivariate-bicycle-code/card.md
zoo/views/code-index.json
zoo/views/family-index.json
zoo/views/relation-index.json
zoo/views/evidence-index.json
zoo/views/browse.md
zoo/views/site/index.html
zoo/views/site/assets/app.js
zoo/views/site/assets/styles.css
```

- [ ] **Step 5: Commit the docs and generated artifacts**

```bash
git add README.md CLAUDE.md zoo/codes/*/card.md zoo/views
git commit -m "docs: document zoo workflow and generated views"
```

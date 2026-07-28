# Error Correction Zoo Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vendor a full, committed snapshot of the Error Correction Zoo (`errorcorrectionzoo/eczoo_data`) as a separate, CC-BY-SA-marked reference layer under `zoo/external/eczoo/`, then build a queryable JSON index (codes + relation graph) and an offline static browse site from it.

**Architecture:** A `make eczoo-fetch` shell step vendors the upstream YAML into `zoo/external/eczoo/raw/`. A new pure-Python module `src/autoqec_zoo/eczoo.py` parses that YAML into two derived JSON artifacts (`index/eczoo-codes.json`, `index/eczoo-relations.json`), computing inverse relation edges, validating against two new schemas, and rendering `views/browse.md` + a self-contained `views/site/`. A new `autoqec-zoo eczoo` CLI subcommand and `make eczoo-build`/`eczoo-update` targets drive it. The existing curated zoo (`codes/**/card.json`, `evidence/**`) is untouched except for one optional cross-link field.

**Tech Stack:** Python 3.11+, PyYAML (new dependency), jsonschema (existing), pytest (existing). Bash + git for the fetch step.

---

## File structure

| File | Responsibility |
|---|---|
| `scripts/fetch_eczoo.sh` (create) | Clone upstream at a pinned SHA, copy `codes/` + `LICENSE` into `raw/`, stamp `SNAPSHOT.md`. |
| `zoo/external/eczoo/NOTICE.md` (create) | CC-BY-SA attribution + statement of changes. |
| `zoo/external/eczoo/SNAPSHOT.md` (create, then overwritten by fetch) | Pinned upstream commit SHA + fetch date. |
| `zoo/schemas/eczoo-code.schema.json` (create) | Schema for one record in `eczoo-codes.json`. |
| `zoo/schemas/eczoo-relation.schema.json` (create) | Schema for the `eczoo-relations.json` envelope. |
| `zoo/schemas/code-card.schema.json` (modify) | Add optional `eczoo_ref` cross-link field. |
| `src/autoqec_zoo/eczoo.py` (create) | Parse YAML → records, build relation edges, validate, write index + views. |
| `src/autoqec_zoo/eczoo_site.py` (create) | Render the self-contained eczoo static site (html/js/css). |
| `src/autoqec_zoo/cli.py` (modify) | Add the `eczoo` subcommand. |
| `pyproject.toml` (modify) | Add `pyyaml` dependency. |
| `Makefile` (modify) | Add `eczoo-fetch`, `eczoo-build`, `eczoo-update`. |
| `tests/fixtures/eczoo/codes/**` (create) | Three fixture YAMLs mirroring the real schema. |
| `tests/test_eczoo.py` (create) | Unit tests for parser, relations, index, schema, views. |
| `CLAUDE.md` / `zoo/README.md` (modify) | Document the eczoo reference layer + license boundary. |

### eczoo-codes.json record shape (the contract used throughout)

```json
{
  "code_id": "surface",
  "name": "Kitaev surface code",
  "short_name": "Surface",
  "family_path": ["quantum", "qubits", "stabilizer", "topological", "surface"],
  "introduced": "\\cite{arXiv:quant-ph/9707021}",
  "description_excerpt": "A family of QLDPC codes...",
  "features": { "rate": "...", "decoders": ["MWPM", "Union-Find"] },
  "parents": ["qubit_css"],
  "cousins": ["toric"],
  "source_path": "codes/quantum/qubits/stabilizer/topological/surface/surface.yml"
}
```

### eczoo-relations.json edge shape

```json
{ "source": "surface", "target": "qubit_css", "type": "parent" }
```

`type ∈ {"parent","child","cousin"}`. Every upstream `parent` edge `A→B` also emits the inverse `child` edge `B→A`. `cousin` edges are symmetric (emitted both directions, deduped).

---

## Task 1: Add PyYAML dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, change the `dependencies` list under `[project]` from:

```toml
dependencies = [
  "jsonschema>=4.23,<5"
]
```

to:

```toml
dependencies = [
  "jsonschema>=4.23,<5",
  "pyyaml>=6.0,<7"
]
```

- [ ] **Step 2: Install it**

Run: `python3 -m pip install --user 'pyyaml>=6.0,<7'`
Expected: `Successfully installed pyyaml-6.x` (or "already satisfied").

- [ ] **Step 3: Verify import**

Run: `python3 -c "import yaml; print(yaml.__version__)"`
Expected: prints a `6.x` version with no traceback.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add pyyaml dependency for eczoo import"
```

---

## Task 2: Fetch script + attribution scaffolding

This task is infrastructure (network + files), not TDD. It produces the vendored snapshot and the license bookkeeping, and **confirms the real upstream schema** before the parser is written.

**Files:**
- Create: `scripts/fetch_eczoo.sh`
- Create: `zoo/external/eczoo/NOTICE.md`

- [ ] **Step 1: Write the fetch script**

Create `scripts/fetch_eczoo.sh`:

```bash
#!/usr/bin/env bash
# Vendor a snapshot of the Error Correction Zoo data (CC-BY-SA 4.0).
# Usage: scripts/fetch_eczoo.sh [REF]
# REF defaults to the pinned SHA below; pass a tag/branch/sha to override.
set -euo pipefail

REPO="https://github.com/errorcorrectionzoo/eczoo_data.git"
PINNED_REF="${1:-main}"   # replace 'main' with a resolved SHA in Step 4
DEST="zoo/external/eczoo"
RAW="$DEST/raw"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Cloning $REPO @ $PINNED_REF ..."
git clone --no-checkout --depth 1 --branch "$PINNED_REF" "$REPO" "$tmp/repo" 2>/dev/null \
  || git clone "$REPO" "$tmp/repo"
git -C "$tmp/repo" checkout "$PINNED_REF"
SHA="$(git -C "$tmp/repo" rev-parse HEAD)"

echo "Copying codes/ and LICENSE into $RAW ..."
rm -rf "$RAW"
mkdir -p "$RAW"
cp -R "$tmp/repo/codes" "$RAW/codes"
# Carry whatever license file upstream ships (name varies).
for f in LICENSE LICENSE.md LICENSE.txt COPYING; do
  [ -f "$tmp/repo/$f" ] && cp "$tmp/repo/$f" "$DEST/LICENSE"
done

cat > "$DEST/SNAPSHOT.md" <<EOF
# eczoo snapshot

- upstream: errorcorrectionzoo/eczoo_data
- commit: $SHA
- ref requested: $PINNED_REF
- fetched: $(date -u +%Y-%m-%d)
EOF

echo "Done. Snapshot SHA: $SHA"
echo "Files: $(find "$RAW/codes" -name '*.yml' | wc -l) yml"
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x scripts/fetch_eczoo.sh`

- [ ] **Step 3: Run the fetch**

Run: `bash scripts/fetch_eczoo.sh`
Expected: prints `Done. Snapshot SHA: <40-hex>` and a yml count in the hundreds. `zoo/external/eczoo/raw/codes/` now populated; `zoo/external/eczoo/LICENSE` and `SNAPSHOT.md` exist.

- [ ] **Step 4: Confirm the real schema and pin the SHA**

Run: `find zoo/external/eczoo/raw/codes -name '*.yml' | head -3`
Then open one file and confirm these field names exist: `code_id`, `name`, `short_name`, `description`, `relations.parents` (list of `{code_id, detail}`), `relations.cousins`, `features`. Verify the carried `LICENSE` text is CC-BY-SA 4.0.

Edit `scripts/fetch_eczoo.sh`: replace `PINNED_REF="${1:-main}"` default `main` with the resolved 40-char SHA from Step 3 so the snapshot is reproducible.

> If any field name differs from the contract above, update the fixtures in Task 5 and the field reads in Task 4 to match before proceeding. This is the one place schema reality is reconciled.

- [ ] **Step 5: Write the NOTICE file**

Create `zoo/external/eczoo/NOTICE.md`:

```markdown
# Attribution — Error Correction Zoo data

The contents of this directory (`zoo/external/eczoo/`), including the vendored
YAML under `raw/` and all derived artifacts under `index/` and `views/`, are
adapted from **The Error Correction Zoo** (V. V. Albert and P. Faist, editors),
https://errorcorrectionzoo.org.

- Source repository: https://github.com/errorcorrectionzoo/eczoo_data
- Snapshot commit: see `SNAPSHOT.md`
- License: Creative Commons Attribution-ShareAlike 4.0 International
  (CC-BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/

## Changes made

- Selected the `codes/` YAML tree only (other upstream assets omitted).
- Derived `index/eczoo-codes.json` and `index/eczoo-relations.json` by parsing,
  filtering, and reshaping the YAML; computed inverse relation edges.
- Generated `views/browse.md` and `views/site/` from the derived index.

These derived artifacts remain licensed CC-BY-SA 4.0. This obligation applies
only to the eczoo-derived material in this directory; the rest of this
repository (the importer code, JSON schemas, and original curated cards) is
licensed under the repository's own terms.
```

- [ ] **Step 6: Commit the vendored snapshot + attribution**

```bash
git add scripts/fetch_eczoo.sh zoo/external/eczoo/NOTICE.md zoo/external/eczoo/SNAPSHOT.md zoo/external/eczoo/LICENSE zoo/external/eczoo/raw
git commit -m "feat: vendor Error Correction Zoo data snapshot (CC-BY-SA 4.0)"
```

---

## Task 3: Index schemas

**Files:**
- Create: `zoo/schemas/eczoo-code.schema.json`
- Create: `zoo/schemas/eczoo-relation.schema.json`

- [ ] **Step 1: Write the code-index schema**

Create `zoo/schemas/eczoo-code.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["generated_at", "items"],
  "properties": {
    "generated_at": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "code_id", "name", "short_name", "family_path",
          "introduced", "description_excerpt", "features",
          "parents", "cousins", "source_path"
        ],
        "properties": {
          "code_id": { "type": "string", "minLength": 1 },
          "name": { "type": "string", "minLength": 1 },
          "short_name": { "type": ["string", "null"] },
          "family_path": { "type": "array", "items": { "type": "string" } },
          "introduced": { "type": ["string", "null"] },
          "description_excerpt": { "type": "string" },
          "features": {
            "type": "object",
            "additionalProperties": {
              "type": ["string", "array"],
              "items": { "type": "string" }
            }
          },
          "parents": { "type": "array", "items": { "type": "string" } },
          "cousins": { "type": "array", "items": { "type": "string" } },
          "source_path": { "type": "string", "minLength": 1 }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the relation-index schema**

Create `zoo/schemas/eczoo-relation.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["generated_at", "items"],
  "properties": {
    "generated_at": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$" },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["source", "target", "type"],
        "properties": {
          "source": { "type": "string", "minLength": 1 },
          "target": { "type": "string", "minLength": 1 },
          "type": { "enum": ["parent", "child", "cousin"] }
        }
      }
    }
  }
}
```

- [ ] **Step 3: Validate both schemas are well-formed**

Run:
```bash
python3 -c "import json,glob; from jsonschema import Draft202012Validator as V; [V.check_schema(json.load(open(p))) for p in glob.glob('zoo/schemas/eczoo-*.schema.json')]; print('ok')"
```
Expected: prints `ok` with no traceback.

- [ ] **Step 4: Commit**

```bash
git add zoo/schemas/eczoo-code.schema.json zoo/schemas/eczoo-relation.schema.json
git commit -m "feat: add eczoo index schemas"
```

---

## Task 4: YAML → code record parser

**Files:**
- Create: `src/autoqec_zoo/eczoo.py`
- Create: `tests/fixtures/eczoo/codes/topo/surface.yml`
- Test: `tests/test_eczoo.py`

- [ ] **Step 1: Write a fixture YAML**

Create `tests/fixtures/eczoo/codes/topo/surface.yml`:

```yaml
code_id: surface
name: 'Kitaev surface code'
short_name: 'Surface'
introduced: '\cite{arXiv:quant-ph/9707021}'
description: |
  A family of topological CSS stabilizer codes defined on a 2D lattice with
  local parity checks. The boundary conditions select the variant.
protection: |
  Distance d grows with linear lattice size.
features:
  rate: 'k/n -> 0'
  decoders:
    - 'MWPM'
    - 'Union-Find'
relations:
  parents:
    - code_id: qubit_css
      detail: 'is a CSS code'
  cousins:
    - code_id: toric
      detail: 'periodic boundary'
_meta:
  changelog:
    - user_id: x
      date: '2024-01-01'
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_eczoo.py`:

```python
from pathlib import Path

from autoqec_zoo.eczoo import parse_code_file

FIXTURES = Path(__file__).parent / "fixtures" / "eczoo"


def test_parse_code_file_extracts_record():
    raw_codes = FIXTURES / "codes"
    record = parse_code_file(raw_codes / "topo" / "surface.yml", raw_codes)

    assert record["code_id"] == "surface"
    assert record["name"] == "Kitaev surface code"
    assert record["short_name"] == "Surface"
    assert record["family_path"] == ["topo"]
    assert record["introduced"] == r"\cite{arXiv:quant-ph/9707021}"
    assert record["description_excerpt"].startswith("A family of topological CSS")
    assert record["features"]["decoders"] == ["MWPM", "Union-Find"]
    assert record["parents"] == ["qubit_css"]
    assert record["cousins"] == ["toric"]
    assert record["source_path"] == "codes/topo/surface.yml"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_eczoo.py::test_parse_code_file_extracts_record -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autoqec_zoo.eczoo'`.

- [ ] **Step 4: Write the parser**

Create `src/autoqec_zoo/eczoo.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

_FEATURE_KEYS = (
    "rate",
    "encoders",
    "decoders",
    "fault_tolerance",
    "transversal_gates",
    "general_gates",
    "threshold",
    "code_capacity_threshold",
)
_EXCERPT_LEN = 280


def _relation_ids(relations: dict, key: str) -> list[str]:
    entries = (relations or {}).get(key) or []
    ids = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("code_id"):
            ids.append(str(entry["code_id"]))
    return ids


def _excerpt(text) -> str:
    if not text:
        return ""
    flat = " ".join(str(text).split())
    if len(flat) <= _EXCERPT_LEN:
        return flat
    return flat[:_EXCERPT_LEN].rstrip() + "…"


def _features(raw_features) -> dict:
    raw_features = raw_features or {}
    out = {}
    for key in _FEATURE_KEYS:
        if key not in raw_features:
            continue
        value = raw_features[key]
        if isinstance(value, list):
            out[key] = [" ".join(str(item).split()) for item in value]
        elif value is not None:
            out[key] = " ".join(str(value).split())
    return out


def parse_code_file(path: Path, raw_codes_root: Path) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    rel_path = path.relative_to(raw_codes_root)
    family_path = list(rel_path.parts[:-1])
    relations = data.get("relations") or {}
    return {
        "code_id": str(data["code_id"]),
        "name": str(data.get("name") or data["code_id"]),
        "short_name": (str(data["short_name"]) if data.get("short_name") else None),
        "family_path": family_path,
        "introduced": (str(data["introduced"]) if data.get("introduced") else None),
        "description_excerpt": _excerpt(data.get("description")),
        "features": _features(data.get("features")),
        "parents": _relation_ids(relations, "parents"),
        "cousins": _relation_ids(relations, "cousins"),
        "source_path": "codes/" + "/".join(rel_path.parts),
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_eczoo.py::test_parse_code_file_extracts_record -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/autoqec_zoo/eczoo.py tests/test_eczoo.py tests/fixtures/eczoo/codes/topo/surface.yml
git commit -m "feat: parse eczoo code YAML into normalized records"
```

---

## Task 5: Directory loader with no-silent-drop reconciliation

**Files:**
- Modify: `src/autoqec_zoo/eczoo.py`
- Create: `tests/fixtures/eczoo/codes/ldpc/bicycle.yml`
- Create: `tests/fixtures/eczoo/codes/broken/bad.yml`
- Modify: `tests/test_eczoo.py`

- [ ] **Step 1: Add two more fixtures**

Create `tests/fixtures/eczoo/codes/ldpc/bicycle.yml`:

```yaml
code_id: bivariate_bicycle
name: 'Bivariate bicycle code'
short_name: 'BB'
description: 'A QLDPC code built from two commuting circulant matrices.'
features:
  rate: 'constant'
relations:
  parents:
    - code_id: qubit_css
      detail: 'CSS'
```

Create `tests/fixtures/eczoo/codes/broken/bad.yml` (no `code_id` → unparseable):

```yaml
name: 'Missing code id'
description: 'This entry has no code_id and must be skipped, not crash.'
```

- [ ] **Step 2: Write the failing test**

Add to `tests/test_eczoo.py`:

```python
from autoqec_zoo.eczoo import load_eczoo_codes


def test_load_eczoo_codes_loads_all_and_reports_skips():
    raw_codes = FIXTURES / "codes"
    records, skipped = load_eczoo_codes(raw_codes)

    ids = {r["code_id"] for r in records}
    assert {"surface", "bivariate_bicycle"} <= ids
    assert any("bad.yml" in s for s in skipped)
    total_yml = len(list(raw_codes.rglob("*.yml")))
    assert len(records) + len(skipped) == total_yml
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_eczoo.py::test_load_eczoo_codes_loads_all_and_reports_skips -v`
Expected: FAIL — `ImportError: cannot import name 'load_eczoo_codes'`.

- [ ] **Step 4: Implement the loader**

Add to `src/autoqec_zoo/eczoo.py`:

```python
def load_eczoo_codes(raw_codes_root: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    skipped: list[str] = []
    for path in sorted(raw_codes_root.rglob("*.yml")):
        try:
            records.append(parse_code_file(path, raw_codes_root))
        except (KeyError, yaml.YAMLError, ValueError) as exc:
            skipped.append(f"{path}: {exc}")
    return records, skipped
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_eczoo.py::test_load_eczoo_codes_loads_all_and_reports_skips -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/autoqec_zoo/eczoo.py tests/test_eczoo.py tests/fixtures/eczoo/codes/ldpc/bicycle.yml tests/fixtures/eczoo/codes/broken/bad.yml
git commit -m "feat: load eczoo code dir with skip reconciliation"
```

---

## Task 6: Relation-graph builder with inverse edges

**Files:**
- Modify: `src/autoqec_zoo/eczoo.py`
- Modify: `tests/test_eczoo.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eczoo.py`:

```python
from autoqec_zoo.eczoo import build_relations


def test_build_relations_adds_inverse_edges():
    records = [
        {"code_id": "surface", "parents": ["qubit_css"], "cousins": ["toric"]},
        {"code_id": "qubit_css", "parents": [], "cousins": []},
        {"code_id": "toric", "parents": [], "cousins": []},
    ]
    edges, unresolved = build_relations(records)

    assert {"source": "surface", "target": "qubit_css", "type": "parent"} in edges
    assert {"source": "qubit_css", "target": "surface", "type": "child"} in edges
    assert {"source": "surface", "target": "toric", "type": "cousin"} in edges
    assert {"source": "toric", "target": "surface", "type": "cousin"} in edges
    assert unresolved == []


def test_build_relations_flags_unresolved_targets():
    records = [{"code_id": "surface", "parents": ["ghost"], "cousins": []}]
    edges, unresolved = build_relations(records)

    assert {"source": "surface", "target": "ghost", "type": "parent"} in edges
    assert "ghost" in unresolved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_eczoo.py -k build_relations -v`
Expected: FAIL — `ImportError: cannot import name 'build_relations'`.

- [ ] **Step 3: Implement the builder**

Add to `src/autoqec_zoo/eczoo.py`:

```python
def build_relations(records: list[dict]) -> tuple[list[dict], list[str]]:
    known = {r["code_id"] for r in records}
    edge_set: set[tuple[str, str, str]] = set()
    unresolved: set[str] = set()

    for record in records:
        source = record["code_id"]
        for parent in record.get("parents", []):
            edge_set.add((source, parent, "parent"))
            edge_set.add((parent, source, "child"))
            if parent not in known:
                unresolved.add(parent)
        for cousin in record.get("cousins", []):
            edge_set.add((source, cousin, "cousin"))
            edge_set.add((cousin, source, "cousin"))
            if cousin not in known:
                unresolved.add(cousin)

    edges = [
        {"source": s, "target": t, "type": k}
        for (s, t, k) in sorted(edge_set)
    ]
    return edges, sorted(unresolved)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_eczoo.py -k build_relations -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_zoo/eczoo.py tests/test_eczoo.py
git commit -m "feat: build eczoo relation graph with inverse edges"
```

---

## Task 7: Index writer + schema validation

**Files:**
- Modify: `src/autoqec_zoo/eczoo.py`
- Modify: `tests/test_eczoo.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eczoo.py`:

```python
import json

from autoqec_zoo.eczoo import build_eczoo_index

SCHEMA_ROOT = Path(__file__).parents[1] / "zoo" / "schemas"


def test_build_eczoo_index_writes_validated_artifacts(tmp_path):
    out = tmp_path / "index"
    result = build_eczoo_index(
        raw_codes_root=FIXTURES / "codes",
        index_root=out,
        schema_root=SCHEMA_ROOT,
        generated_at="2026-05-29",
    )

    codes = json.loads((out / "eczoo-codes.json").read_text())
    relations = json.loads((out / "eczoo-relations.json").read_text())

    assert codes["generated_at"] == "2026-05-29"
    code_ids = {item["code_id"] for item in codes["items"]}
    assert "surface" in code_ids
    assert any(e["type"] == "child" for e in relations["items"])
    # reconciliation surfaced, not hidden
    assert result["indexed_count"] + result["skipped_count"] == result["input_count"]
    assert result["skipped_count"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_eczoo.py::test_build_eczoo_index_writes_validated_artifacts -v`
Expected: FAIL — `ImportError: cannot import name 'build_eczoo_index'`.

- [ ] **Step 3: Implement the index writer**

Add to `src/autoqec_zoo/eczoo.py` (add `import json` and `from jsonschema import Draft202012Validator` at the top of the file with the other imports):

```python
def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_eczoo_index(
    raw_codes_root: Path,
    index_root: Path,
    schema_root: Path,
    generated_at: str,
) -> dict:
    records, skipped = load_eczoo_codes(raw_codes_root)
    edges, unresolved = build_relations(records)

    codes_doc = {"generated_at": generated_at, "items": records}
    relations_doc = {"generated_at": generated_at, "items": edges}

    code_validator = Draft202012Validator(
        json.loads((schema_root / "eczoo-code.schema.json").read_text())
    )
    relation_validator = Draft202012Validator(
        json.loads((schema_root / "eczoo-relation.schema.json").read_text())
    )
    code_validator.validate(codes_doc)
    relation_validator.validate(relations_doc)

    _write_json(index_root / "eczoo-codes.json", codes_doc)
    _write_json(index_root / "eczoo-relations.json", relations_doc)

    input_count = len(list(raw_codes_root.rglob("*.yml")))
    return {
        "input_count": input_count,
        "indexed_count": len(records),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "edge_count": len(edges),
        "unresolved": unresolved,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_eczoo.py::test_build_eczoo_index_writes_validated_artifacts -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_zoo/eczoo.py tests/test_eczoo.py
git commit -m "feat: write and validate eczoo index artifacts"
```

---

## Task 8: browse.md renderer

**Files:**
- Modify: `src/autoqec_zoo/eczoo.py`
- Modify: `tests/test_eczoo.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eczoo.py`:

```python
from autoqec_zoo.eczoo import render_eczoo_browse


def test_render_eczoo_browse_groups_by_top_family():
    records = [
        {"code_id": "surface", "name": "Surface", "short_name": "Surface",
         "family_path": ["quantum", "topo"], "description_excerpt": "topological code",
         "parents": ["qubit_css"], "cousins": []},
        {"code_id": "rep", "name": "Repetition", "short_name": None,
         "family_path": ["classical"], "description_excerpt": "repeat bits",
         "parents": [], "cousins": []},
    ]
    md = render_eczoo_browse(records)

    assert "# Error Correction Zoo (mirror)" in md
    assert "## quantum" in md
    assert "## classical" in md
    assert "`surface`" in md
    assert "Surface" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_eczoo.py::test_render_eczoo_browse_groups_by_top_family -v`
Expected: FAIL — `ImportError: cannot import name 'render_eczoo_browse'`.

- [ ] **Step 3: Implement the renderer**

Add to `src/autoqec_zoo/eczoo.py`:

```python
def render_eczoo_browse(records: list[dict]) -> str:
    groups: dict[str, list[dict]] = {}
    for record in records:
        top = record["family_path"][0] if record["family_path"] else "(root)"
        groups.setdefault(top, []).append(record)

    lines = [
        "# Error Correction Zoo (mirror)",
        "",
        "Derived from The Error Correction Zoo (CC-BY-SA 4.0). See `../NOTICE.md`.",
        "",
    ]
    for top in sorted(groups):
        lines.append(f"## {top}")
        lines.append("")
        for record in sorted(groups[top], key=lambda r: r["code_id"]):
            label = record["name"]
            lines.append(f"- `{record['code_id']}` — {label}: {record['description_excerpt']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_eczoo.py::test_render_eczoo_browse_groups_by_top_family -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_zoo/eczoo.py tests/test_eczoo.py
git commit -m "feat: render eczoo browse.md grouped by family"
```

---

## Task 9: Static site renderer

**Files:**
- Create: `src/autoqec_zoo/eczoo_site.py`
- Modify: `tests/test_eczoo.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eczoo.py`:

```python
from autoqec_zoo.eczoo_site import render_eczoo_site


def test_render_eczoo_site_embeds_data():
    codes_doc = {"generated_at": "2026-05-29", "items": [
        {"code_id": "surface", "name": "Surface", "short_name": "Surface",
         "family_path": ["quantum"], "introduced": None,
         "description_excerpt": "x", "features": {}, "parents": [], "cousins": [],
         "source_path": "codes/quantum/surface.yml"}
    ]}
    relations_doc = {"generated_at": "2026-05-29", "items": []}
    html, js, css = render_eczoo_site(codes_doc, relations_doc)

    assert "<!doctype html>" in html.lower()
    assert "eczoo" in html.lower()
    assert "EMBEDDED_STATE" in js
    assert "surface" in js  # embedded data
    assert "</script" not in js  # closing tags escaped so the embed can't break out
    assert len(css) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_eczoo.py::test_render_eczoo_site_embeds_data -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autoqec_zoo.eczoo_site'`.

- [ ] **Step 3: Implement the site renderer**

Create `src/autoqec_zoo/eczoo_site.py`:

```python
from __future__ import annotations

import json


def render_eczoo_site(codes_doc: dict, relations_doc: dict) -> tuple[str, str, str]:
    state = {"codes": codes_doc["items"], "relations": relations_doc["items"],
             "generated_at": codes_doc["generated_at"]}
    state_json = json.dumps(state, sort_keys=True).replace("</", "<\\/")

    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>eczoo mirror</title>
    <link rel="stylesheet" href="assets/styles.css">
  </head>
  <body>
    <div class="layout">
      <aside class="sidebar">
        <h1>eczoo mirror</h1>
        <input id="search" class="filter" placeholder="filter codes...">
        <div id="code-list" class="code-list"></div>
      </aside>
      <main class="detail">
        <section class="panel">
          <h2 id="code-title">Select a code</h2>
          <p id="code-meta" class="summary"></p>
          <p id="code-desc"></p>
        </section>
        <section class="panel">
          <h3>Relations</h3>
          <div id="relations"></div>
        </section>
      </main>
    </div>
    <script src="assets/app.js"></script>
  </body>
</html>
"""

    js = "const EMBEDDED_STATE = " + state_json + """;
(function () {
  const state = EMBEDDED_STATE;
  const byId = {};
  state.codes.forEach(c => { byId[c.code_id] = c; });
  const list = document.getElementById("code-list");
  const search = document.getElementById("search");

  function rels(id) {
    return state.relations.filter(e => e.source === id);
  }
  function show(id) {
    const c = byId[id];
    if (!c) return;
    document.getElementById("code-title").textContent = c.name + " (" + c.code_id + ")";
    document.getElementById("code-meta").textContent = c.family_path.join(" / ");
    document.getElementById("code-desc").textContent = c.description_excerpt || "";
    const r = document.getElementById("relations");
    r.innerHTML = "";
    rels(id).forEach(e => {
      const div = document.createElement("div");
      const a = document.createElement("a");
      a.href = "#" + e.target;
      a.textContent = e.target;
      a.onclick = () => show(e.target);
      div.appendChild(document.createTextNode(e.type + ": "));
      div.appendChild(a);
      r.appendChild(div);
    });
  }
  function render(filter) {
    list.innerHTML = "";
    state.codes
      .filter(c => !filter || (c.code_id + " " + c.name).toLowerCase().includes(filter))
      .forEach(c => {
        const item = document.createElement("button");
        item.className = "code-list-item";
        item.textContent = c.code_id;
        item.onclick = () => show(c.code_id);
        list.appendChild(item);
      });
  }
  search.addEventListener("input", e => render(e.target.value.toLowerCase()));
  render("");
})();
"""

    css = """body { font-family: system-ui, sans-serif; margin: 0; }
.layout { display: flex; min-height: 100vh; }
.sidebar { width: 280px; border-right: 1px solid #ddd; padding: 1rem; overflow-y: auto; }
.detail { flex: 1; padding: 1rem 2rem; }
.filter { width: 100%; margin-bottom: 1rem; padding: 0.4rem; }
.code-list { display: flex; flex-direction: column; gap: 2px; }
.code-list-item { text-align: left; border: none; background: none; padding: 4px 6px; cursor: pointer; }
.code-list-item:hover { background: #f0f0f0; }
.panel { margin-bottom: 1.5rem; }
.summary { color: #666; }
"""
    return html, js, css
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_eczoo.py::test_render_eczoo_site_embeds_data -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/autoqec_zoo/eczoo_site.py tests/test_eczoo.py
git commit -m "feat: render self-contained eczoo browse site"
```

---

## Task 10: Top-level build orchestrator

**Files:**
- Modify: `src/autoqec_zoo/eczoo.py`
- Modify: `tests/test_eczoo.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eczoo.py`:

```python
from autoqec_zoo.eczoo import build_eczoo


def test_build_eczoo_writes_index_and_views(tmp_path):
    # Arrange a fake zoo root: external/eczoo/raw/codes + schemas.
    zoo_root = tmp_path / "zoo"
    raw_codes = zoo_root / "external" / "eczoo" / "raw" / "codes"
    raw_codes.mkdir(parents=True)
    (raw_codes / "topo").mkdir()
    (raw_codes / "topo" / "surface.yml").write_text(
        (FIXTURES / "codes" / "topo" / "surface.yml").read_text()
    )
    # Copy schemas next to the fake root.
    schemas = zoo_root / "schemas"
    schemas.mkdir()
    for name in ("eczoo-code.schema.json", "eczoo-relation.schema.json"):
        (schemas / name).write_text((SCHEMA_ROOT / name).read_text())

    result = build_eczoo(zoo_root, generated_at="2026-05-29")

    base = zoo_root / "external" / "eczoo"
    assert (base / "index" / "eczoo-codes.json").exists()
    assert (base / "index" / "eczoo-relations.json").exists()
    assert (base / "views" / "browse.md").exists()
    assert (base / "views" / "site" / "index.html").exists()
    assert (base / "views" / "site" / "assets" / "app.js").exists()
    assert (base / "views" / "site" / "assets" / "styles.css").exists()
    assert result["indexed_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_eczoo.py::test_build_eczoo_writes_index_and_views -v`
Expected: FAIL — `ImportError: cannot import name 'build_eczoo'`.

- [ ] **Step 3: Implement the orchestrator**

Add to `src/autoqec_zoo/eczoo.py` (add `from autoqec_zoo.eczoo_site import render_eczoo_site` to the imports):

```python
def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def build_eczoo(zoo_root: Path, generated_at: str) -> dict:
    base = zoo_root / "external" / "eczoo"
    raw_codes = base / "raw" / "codes"
    if not raw_codes.exists():
        raise FileNotFoundError(
            f"eczoo raw data not found at {raw_codes}; run `make eczoo-fetch` first"
        )

    result = build_eczoo_index(
        raw_codes_root=raw_codes,
        index_root=base / "index",
        schema_root=zoo_root / "schemas",
        generated_at=generated_at,
    )

    codes_doc = json.loads((base / "index" / "eczoo-codes.json").read_text())
    relations_doc = json.loads((base / "index" / "eczoo-relations.json").read_text())

    _write_text(base / "views" / "browse.md", render_eczoo_browse(codes_doc["items"]))

    html, js, css = render_eczoo_site(codes_doc, relations_doc)
    site = base / "views" / "site"
    _write_text(site / "index.html", html)
    _write_text(site / "assets" / "app.js", js)
    _write_text(site / "assets" / "styles.css", css)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_eczoo.py::test_build_eczoo_writes_index_and_views -v`
Expected: PASS.

- [ ] **Step 5: Run the whole eczoo test module**

Run: `python3 -m pytest tests/test_eczoo.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/autoqec_zoo/eczoo.py tests/test_eczoo.py
git commit -m "feat: orchestrate eczoo index + views build"
```

---

## Task 11: CLI subcommand

**Files:**
- Modify: `src/autoqec_zoo/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Read the existing CLI test for the pattern**

Run: `sed -n '1,40p' tests/test_cli.py`
Expected: shows how the existing `build` command is invoked in tests (via `main([...])`). Mirror that style in Step 2.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_cli.py` (adjust imports to match the file's existing style):

```python
def test_cli_eczoo_builds_index(tmp_path):
    from autoqec_zoo.cli import main

    zoo_root = tmp_path / "zoo"
    raw_codes = zoo_root / "external" / "eczoo" / "raw" / "codes" / "topo"
    raw_codes.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "eczoo" / "codes" / "topo" / "surface.yml"
    (raw_codes / "surface.yml").write_text(fixture.read_text())
    schemas = zoo_root / "schemas"
    schemas.mkdir()
    real_schemas = Path(__file__).parents[1] / "zoo" / "schemas"
    for name in ("eczoo-code.schema.json", "eczoo-relation.schema.json"):
        (schemas / name).write_text((real_schemas / name).read_text())

    rc = main(["eczoo", "--root", str(zoo_root), "--date", "2026-05-29"])

    assert rc == 0
    assert (zoo_root / "external" / "eczoo" / "index" / "eczoo-codes.json").exists()
```

(Ensure `from pathlib import Path` is imported in `tests/test_cli.py`.)

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::test_cli_eczoo_builds_index -v`
Expected: FAIL — `SystemExit: 2` / "invalid choice: 'eczoo'".

- [ ] **Step 4: Add the subcommand**

In `src/autoqec_zoo/cli.py`, add the import near the top:

```python
from autoqec_zoo.eczoo import build_eczoo
```

In `build_parser()`, after the existing `build` subparser block (before `return parser`), add:

```python
    eczoo_parser = subparsers.add_parser(
        "eczoo", help="Build the eczoo mirror index and views"
    )
    eczoo_parser.add_argument("--root", default="zoo", help="Path to the zoo root directory")
    eczoo_parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Generation date for built artifacts",
    )
```

In `main()`, before the final `parser.error(...)` line, add:

```python
    if args.command == "eczoo":
        root = Path(args.root)
        if not root.exists():
            parser.error(f"zoo root does not exist: {root}")
        result = build_eczoo(root, generated_at=args.date)
        print(
            f"built eczoo mirror: {result['indexed_count']} codes, "
            f"{result['edge_count']} edges, {result['skipped_count']} skipped"
        )
        if result["skipped"]:
            print("skipped files:")
            for line in result["skipped"]:
                print(f"  - {line}")
        if result["unresolved"]:
            print(f"unresolved relation targets: {len(result['unresolved'])}")
        return 0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py::test_cli_eczoo_builds_index -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/autoqec_zoo/cli.py tests/test_cli.py
git commit -m "feat: add eczoo CLI subcommand"
```

---

## Task 12: Cross-link field on curated cards

**Files:**
- Modify: `zoo/schemas/code-card.schema.json`
- Test: `tests/test_eczoo.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eczoo.py`:

```python
def test_code_card_schema_allows_optional_eczoo_ref():
    from jsonschema import Draft202012Validator

    schema = json.loads((SCHEMA_ROOT / "code-card.schema.json").read_text())
    validator = Draft202012Validator(schema)

    base = json.loads((SCHEMA_ROOT.parent / "codes" / "surface-code" / "card.json").read_text())
    # eczoo_ref is optional: present is valid
    with_ref = {**base, "eczoo_ref": "surface"}
    validator.validate(with_ref)
    # absent is still valid
    validator.validate(base)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_eczoo.py::test_code_card_schema_allows_optional_eczoo_ref -v`
Expected: FAIL — `jsonschema.exceptions.ValidationError: Additional properties are not allowed ('eczoo_ref' ...)` (because `additionalProperties` is `false`).

- [ ] **Step 3: Add the optional property**

In `zoo/schemas/code-card.schema.json`, inside `"properties"`, add an entry (e.g. right after the `"family"` property):

```json
    "eczoo_ref": { "type": "string", "minLength": 1 },
```

Do **not** add it to the `required` array — it stays optional.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_eczoo.py::test_code_card_schema_allows_optional_eczoo_ref -v`
Expected: PASS.

- [ ] **Step 5: Verify the existing zoo still builds**

Run: `python3 -m autoqec_zoo.cli build --root zoo && python3 -m pytest tests/ -q`
Expected: build prints `built zoo artifacts under zoo`; full test suite PASSES.

- [ ] **Step 6: Commit**

```bash
git add zoo/schemas/code-card.schema.json tests/test_eczoo.py
git commit -m "feat: allow optional eczoo_ref cross-link on code cards"
```

---

## Task 13: Makefile targets + end-to-end run

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add the targets**

In `Makefile`, add `eczoo-fetch eczoo-build eczoo-update` to the `.PHONY` line, then append after the `zoo-build` target:

```makefile
eczoo-fetch:
	bash scripts/fetch_eczoo.sh $(REF)

eczoo-build:
	python3 -m autoqec_zoo.cli eczoo --root zoo

eczoo-update: eczoo-fetch eczoo-build
```

- [ ] **Step 2: Run the real end-to-end build**

(Assumes Task 2's fetch already populated `zoo/external/eczoo/raw/`.)
Run: `make eczoo-build`
Expected: prints `built eczoo mirror: <N> codes, <M> edges, <K> skipped` with N in the hundreds. Inspect any skipped/unresolved lines printed — they should be few; if a large fraction skipped, the field mapping in Task 4 needs reconciliation against the real schema (see Task 2 Step 4).

- [ ] **Step 3: Spot-check the artifacts**

Run:
```bash
python3 -c "import json; d=json.load(open('zoo/external/eczoo/index/eczoo-codes.json')); print(len(d['items']), 'codes')"
python3 -c "import json; d=json.load(open('zoo/external/eczoo/index/eczoo-relations.json')); print(len(d['items']), 'edges'); print(sorted({e['type'] for e in d['items']}))"
head -20 zoo/external/eczoo/views/browse.md
```
Expected: code/edge counts in the hundreds/thousands; relation types include `parent`, `child`, `cousin`; browse.md shows family-grouped entries.

- [ ] **Step 4: Open the site (optional manual check)**

Run: `open zoo/external/eczoo/views/site/index.html`
Expected: a sidebar lists code IDs; the filter box narrows the list; clicking a code shows its family path, description, and relation links.

- [ ] **Step 5: Commit the Makefile and generated artifacts**

```bash
git add Makefile zoo/external/eczoo/index zoo/external/eczoo/views
git commit -m "feat: add eczoo make targets and committed mirror artifacts"
```

---

## Task 14: Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `zoo/README.md`

- [ ] **Step 1: Document the reference layer in zoo/README.md**

Append to `zoo/README.md`:

```markdown
## External reference layer: Error Correction Zoo mirror

`external/eczoo/` is a committed, full mirror of The Error Correction Zoo
(`errorcorrectionzoo/eczoo_data`), used as a read-only reference. It is
**separate** from the curated source-of-truth above and is licensed CC-BY-SA 4.0
(see `external/eczoo/NOTICE.md`).

- `external/eczoo/raw/` — vendored upstream YAML (do not hand-edit)
- `external/eczoo/index/eczoo-codes.json`, `eczoo-relations.json` — derived index
- `external/eczoo/views/browse.md`, `views/site/` — derived browse artifacts

Refresh and rebuild:

```bash
make eczoo-update     # fetch upstream snapshot, then rebuild index + views
make eczoo-build      # rebuild from the existing raw/ snapshot only
```

Curated cards may point at an eczoo entry via the optional `eczoo_ref` field
(an eczoo `code_id`).
```

- [ ] **Step 2: Add a pointer in CLAUDE.md**

In `CLAUDE.md`, under the "Structured Zoo (`zoo/`)" section, add a bullet:

```markdown
- `zoo/external/eczoo/` — committed CC-BY-SA mirror of the Error Correction Zoo
  (codes + relation graph). For code-ontology lookups across the full QEC
  catalog, search `zoo/external/eczoo/index/` or browse `views/browse.md`.
  Rebuild with `make eczoo-build`; refresh the snapshot with `make eczoo-update`.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md zoo/README.md
git commit -m "docs: document the eczoo reference layer"
```

---

## Final verification

- [ ] Run the full suite: `python3 -m pytest tests/ -q` — all PASS.
- [ ] Confirm the curated build is unaffected: `python3 -m autoqec_zoo.cli build --root zoo` succeeds.
- [ ] Confirm `git status` is clean and the eczoo mirror (raw + index + views + NOTICE + LICENSE + SNAPSHOT) is committed.
- [ ] Confirm `zoo/external/eczoo/NOTICE.md` and `LICENSE` are present (CC-BY-SA compliance).

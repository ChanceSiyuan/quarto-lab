# Zoo Evidence Extraction Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-level skill that extracts single-paper Zoo evidence drafts from `.knowledge/` and approves reviewed drafts into formal evidence records, while keeping draft files out of normal Zoo loads and builds.

**Architecture:** Keep the extraction logic as a workflow skill rather than a heavy CLI pipeline. The repo code changes are limited to enforcing the draft/formal boundary in the existing Zoo loader/builder, while the skill itself encodes the extract/approve process, file naming, and review gates. Approval promotes reviewed draft files into the existing formal `evidence.schema.json` contract by rename only after schema-compatible normalization.

**Tech Stack:** Markdown skill authoring, Python 3.11+, `jsonschema`, `pytest`, existing `autoqec_zoo` loader/builder

---

## File Structure

- `.claude/skills/extract-zoo-evidence/SKILL.md`: project-level skill for extract/approve workflow
- `src/autoqec_zoo/load.py`: ignore `*.draft.json` when loading formal evidence
- `tests/test_load.py`: loader regression tests for draft-ignore behavior
- `tests/test_build.py`: end-to-end regression test proving draft evidence stays out of generated views
- `README.md`: top-level note introducing the new project skill
- `CLAUDE.md`: repo-local guidance telling future agents when to use the skill

### Task 1: Make the Zoo loader ignore draft evidence files

**Files:**
- Modify: `tests/test_load.py`
- Modify: `src/autoqec_zoo/load.py`

- [ ] **Step 1: Write the failing loader test for ignored draft files**

```python
def test_load_zoo_ignores_draft_evidence_files(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    draft_evidence = {
        "id": "2408.10001:bivariate-bicycle-code.decoder-draft",
        "paper_id": "2408.10001",
        "code_id": "bivariate-bicycle-code",
        "claim_type": "decoder_claim",
        "title": "Draft decoder note",
        "context": {
            "noise_model": None,
            "decoder": "belief propagation",
            "distance_method": None,
            "assumptions": ["draft only"],
            "parameter_point": {"instance_keys": ["L18-K8-D4"]},
        },
        "claim": {
            "statement": "Draft-only decoder statement.",
            "value": None,
            "unit": None,
            "qualifiers": ["draft"],
        },
        "provenance": {
            "section": "Draft section",
            "quote_ref": "draft:p1:para1",
            "confidence": "low",
        },
        "uncertainty_flags": [],
        "proposed_code_slug": "bivariate-bicycle-code",
    }
    (
        work_root
        / "evidence"
        / "2408.10001"
        / "bivariate-bicycle-code.decoder-claim.01.draft.json"
    ).write_text(json.dumps(draft_evidence, indent=2) + "\n")

    dataset = load_zoo(work_root)

    assert "2408.10001:bivariate-bicycle-code.decoder-draft" not in dataset.evidence
    assert sorted(dataset.evidence) == ["2408.10001:bivariate-bicycle-code.parameters"]
```

- [ ] **Step 2: Run the loader test to verify draft files are still being considered**

Run: `python3 -m pytest tests/test_load.py::test_load_zoo_ignores_draft_evidence_files -v`
Expected: FAIL because the loader currently glob-matches all `*.json` files under `zoo/evidence/*/`

- [ ] **Step 3: Update the loader to skip `*.draft.json` files**

```python
def load_zoo(root: Path) -> ZooDataset:
    schema_root = root / "schemas"
    card_validator = _validator(schema_root / "code-card.schema.json")
    evidence_validator = _validator(schema_root / "evidence.schema.json")

    cards: dict[str, dict] = {}
    evidence_by_id: dict[str, dict] = {}

    for card_path in sorted((root / "codes").glob("*/card.json")):
        card = _load_json(card_path)
        if card.get("kind") == "code_variant" and not card.get("family"):
            raise IntegrityError(f"variant card missing family: {card['id']}")
        card_validator.validate(card)
        cards[card["id"]] = card

    for evidence_path in sorted((root / "evidence").glob("*/*.json")):
        if evidence_path.name.endswith(".draft.json"):
            continue

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
        if card.get("family"):
            if card["family"] not in cards:
                raise IntegrityError(f"unknown family for {card_id}: {card['family']}")
            if card["kind"] == "code_variant" and cards[card["family"]]["kind"] != "code_family":
                raise IntegrityError(f"family must reference code_family: {card_id}")

        for evidence_ref in card["evidence_refs"]:
            if evidence_ref not in evidence_by_id:
                raise IntegrityError(f"missing evidence_ref on {card_id}: {evidence_ref}")
            if evidence_by_id[evidence_ref]["paper_id"] not in card["source_refs"]:
                raise IntegrityError(
                    f"source_refs missing paper for {card_id}: "
                    f"{evidence_by_id[evidence_ref]['paper_id']}"
                )

    for evidence_id, evidence in evidence_by_id.items():
        if evidence["code_id"] not in cards:
            raise IntegrityError(f"unknown code_id on {evidence_id}: {evidence['code_id']}")

    return ZooDataset(cards=cards, evidence=evidence_by_id)
```

- [ ] **Step 4: Run the focused loader test again**

Run: `python3 -m pytest tests/test_load.py::test_load_zoo_ignores_draft_evidence_files -v`
Expected: PASS

- [ ] **Step 5: Run the full loader suite**

Run: `python3 -m pytest tests/test_load.py -v`
Expected: PASS

- [ ] **Step 6: Commit the loader change**

```bash
git add src/autoqec_zoo/load.py tests/test_load.py
git commit -m "fix: ignore zoo draft evidence files"
```

### Task 2: Add the project-level extract/approve skill

**Files:**
- Create: `.claude/skills/extract-zoo-evidence/SKILL.md`

- [ ] **Step 1: Write the skill file with the approved trigger contract**

```markdown
---
name: extract-zoo-evidence
description: Use when extracting QEC Zoo evidence drafts from a single paper already indexed in this repo's .knowledge/ directory, or when reviewing and approving zoo evidence draft files into formal evidence records.
---

# extract-zoo-evidence

## Overview

This is a project-level AutoQEC skill for the structured Zoo layer.

It supports exactly two actions:

- `extract`: read one `.knowledge/<paper>.md` file and write one or more `zoo/evidence/<paper-id>/*.draft.json` files
- `approve`: review one or more `zoo/evidence/<paper-id>/*.draft.json` files and promote approved drafts to formal `.json` evidence records

This skill does not:

- process multiple papers at once
- read raw PDFs directly
- download arXiv or DOI inputs
- edit `zoo/codes/**/card.json`
- rebuild `zoo/views`

## When to Use

- The user wants structured Zoo evidence extracted from a single paper already present in `.knowledge/`
- The user wants to approve one or more Zoo evidence draft files
- The request is specifically about creating or promoting `zoo/evidence/` records, not about canonical card editing

Do not use:

- for generic paper summaries
- for bulk `.knowledge/` ingestion
- for canonical card authoring
- for rebuilding Zoo views or the static site

## Input Contract

### Extract

Input must be exactly one `.knowledge/<paper>.md` file.

### Approve

Input must be one or more `zoo/evidence/<paper-id>/*.draft.json` files.

If the input does not match one of these shapes, stop and explain the mismatch.

## Draft Naming

Write draft files under:

- `zoo/evidence/<paper-id>/`

Use this filename pattern:

- `<code-slug>.<claim-type>.<nn>.draft.json`

Examples:

- `bivariate-bicycle-code.parameter-claim.01.draft.json`
- `surface-code.threshold-evidence.02.draft.json`

Draft files are provisional and must not be treated as formal Zoo evidence.

## Draft Rules

Each draft file contains exactly one claim under one context.

Allowed draft-only fields:

- `proposed_code_slug`
- `proposed_title`
- `approval_notes`

If a code is not yet present under `zoo/codes/`, drafts may still be written, but those drafts are not eligible for approval until a canonical card exists.

## Extract Workflow

1. Read exactly one `.knowledge/<paper>.md` file.
2. Determine the paper id from the knowledge-base record.
3. Identify code mentions and map them to existing `zoo/codes/**/card.json` entries when possible.
4. For each code, extract only claims that can be represented faithfully as Zoo evidence.
5. Use one draft file per single claim and single contextual envelope.
6. Write the draft files under `zoo/evidence/<paper-id>/`.
7. Print a terminal summary including:
   - input paper path
   - paper id
   - recognized codes
   - generated draft files
   - unknown codes
   - low-confidence mappings
   - next-step approval recommendation

## Extraction Style

Be conservative:

- do not invent unsupported semantics
- do not merge distinct contexts
- do not upgrade paper-conditional claims into canonical truth
- keep `claim.statement` faithful to the paper
- keep uncertainty in the evidence layer

Prefer claim types such as:

- `parameter_claim`
- `decoder_claim`
- `threshold_evidence`
- `distance_claim`
- `relation_claim`

If a claim cannot be represented faithfully, omit it rather than distort it.

## Approve Workflow

1. Read one or more `*.draft.json` files selected by the user.
2. For each draft, review:
   - `paper_id`
   - `code_id`
   - claim type choice
   - faithfulness of `claim.statement`
   - appropriateness of extracted context
   - whether the draft still depends on a non-canonical code
3. If the draft references a code that does not yet have a canonical card, stop approval for that draft.
4. Before promotion:
   - remove draft-only fields
   - ensure the record fully satisfies `zoo/schemas/evidence.schema.json`
5. Promote approved drafts by renaming:
   - `*.draft.json -> *.json`
6. Print a terminal summary including:
   - approved files
   - rejected or deferred files
   - reasons
   - recommendation to run `make zoo-build`

## Build Boundary

Normal Zoo loading and building ignore `*.draft.json`.

Only approved `.json` evidence files should enter the loader, indexes, markdown views, and site generation.

## Failure Conditions

Stop rather than guess when:

- the input is not exactly one `.knowledge/*.md` file for extract
- the input is not one or more `*.draft.json` files for approve
- the paper id cannot be determined reliably
- code mapping is too ambiguous
- the claim cannot be represented faithfully
- approval depends on a code with no canonical card
- the formal evidence schema does not validate after draft-only fields are removed
```

- [ ] **Step 2: Sanity-read the skill file for trigger quality and scope leaks**

Run: `sed -n '1,260p' .claude/skills/extract-zoo-evidence/SKILL.md`
Expected: the description only describes when to use the skill, and the body only covers single-paper extract / draft approve behavior

- [ ] **Step 3: Commit the project-level skill**

```bash
git add .claude/skills/extract-zoo-evidence/SKILL.md
git commit -m "feat: add zoo evidence extraction skill"
```

### Task 3: Document the new skill in repo guidance

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Extend the existing README Zoo section with the skill reference**

```markdown
## Structured Zoo Layer

This repo also hosts a structured `zoo/` layer for normalized code cards and paper evidence.

Rebuild the derived Zoo artifacts with:

```bash
make zoo-build
```

For single-paper evidence extraction from `.knowledge/`, use the project skill:

- `.claude/skills/extract-zoo-evidence`
```

- [ ] **Step 2: Extend the existing CLAUDE.md Zoo section with the skill reference**

```markdown
## Structured Zoo (`zoo/`) — normalized code knowledge

When answering code-ontology or code-comparison questions, check `zoo/` before re-deriving facts from raw papers.

- `zoo/codes/**/card.json` — canonical stable facts
- `zoo/evidence/**/*.json` — paper-specific claims and parameter points
- `zoo/views/browse.md` — generated human-readable entry point

For extracting new evidence from a paper already indexed in `.knowledge/`, use the project skill:

- `.claude/skills/extract-zoo-evidence`

Regenerate the derived artifacts after editing source records:

```sh
make zoo-build
```
```

- [ ] **Step 3: Review the updated docs to ensure they extend the existing sections instead of duplicating them**

Run: `sed -n '1,120p' README.md && printf '\n---\n' && sed -n '70,130p' CLAUDE.md`
Expected: docs mention only the single-paper `.knowledge/` evidence-extraction workflow and do not create duplicate Zoo sections

- [ ] **Step 4: Commit the repo guidance updates**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document zoo evidence extraction skill"
```

### Task 4: Verify the draft/build boundary end to end

**Files:**
- Modify: `tests/test_build.py`

- [ ] **Step 1: Write a failing build test that proves draft files are ignored**

```python
def test_build_ignores_draft_evidence_files(tmp_path: Path) -> None:
    work_root = tmp_path / "zoo"
    shutil.copytree(REPO_ROOT / "zoo", work_root)

    draft_evidence = {
        "id": "2408.10001:bivariate-bicycle-code.threshold-draft",
        "paper_id": "2408.10001",
        "code_id": "bivariate-bicycle-code",
        "claim_type": "threshold_evidence",
        "title": "Draft threshold note",
        "context": {
            "noise_model": "phenomenological noise",
            "decoder": "belief propagation",
            "distance_method": None,
            "assumptions": ["draft only"],
            "parameter_point": {"distance_values": [8, 10, 12]},
        },
        "claim": {
            "statement": "Draft threshold claim.",
            "value": 0.008,
            "unit": "physical_error_rate",
            "qualifiers": ["draft only"],
        },
        "provenance": {
            "section": "Draft section",
            "quote_ref": "draft:p2:para1",
            "confidence": "low",
        },
        "uncertainty_flags": [],
        "approval_notes": "do not include in build",
    }
    (
        work_root
        / "evidence"
        / "2408.10001"
        / "bivariate-bicycle-code.threshold-evidence.01.draft.json"
    ).write_text(json.dumps(draft_evidence, indent=2) + "\n")

    build_zoo(work_root, generated_at="2026-05-27")

    evidence_index = json.loads((work_root / "views" / "evidence-index.json").read_text())
    ids = [item["id"] for item in evidence_index["items"]]

    assert "2408.10001:bivariate-bicycle-code.threshold-draft" not in ids
```

- [ ] **Step 2: Run the focused build test to verify the end-to-end draft boundary**

Run: `python3 -m pytest tests/test_build.py::test_build_ignores_draft_evidence_files -v`
Expected: PASS once the loader change from Task 1 is in place

- [ ] **Step 3: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: PASS

- [ ] **Step 4: Run the checked-in Zoo build end to end**

Run: `python3 -m autoqec_zoo.cli build --root zoo --date 2026-05-27`
Expected:

```text
built zoo artifacts under zoo
```

- [ ] **Step 5: Commit the final verification coverage**

```bash
git add tests/test_build.py
git commit -m "test: verify zoo drafts stay out of builds"
```

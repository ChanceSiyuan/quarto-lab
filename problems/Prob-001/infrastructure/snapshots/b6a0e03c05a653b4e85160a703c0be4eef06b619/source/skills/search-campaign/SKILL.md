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

- campaign `family_id`: `surface-code`
- candidate `code_family`: `rotated-surface-code`
- candidate parameters: positive integer `distance` and `layout: rotated`
- benchmark suite: an existing `default_suite_id`, such as
  `rotated-surface-baseline-v1`
- decoders: selected through the suite and existing ids under
  `benchmarks/decoders/*.json`
- physical error probabilities: finite values satisfying `0 < p < 1`, coming
  from benchmark task defaults and promotion rule points
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
   - suite id, or preferred decoder ids to map to an existing suite
   - p-values needed beyond the benchmark task defaults, such as the
     promotion check point
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

   In `campaign.json`, materialize `family_id: surface-code` and
   `default_suite_id`, not a free-form decoder list. In `search_space.json`,
   each candidate spec uses `code_family: rotated-surface-code`.
7. Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

8. Report the written files and the next command:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign <campaign-id> --wall-clock <seconds>s --run-id <run-id> --allow-dirty-root
```

## Validation Rules

- Stop if the requested candidate code variant is not `rotated-surface-code`.
- Stop if any distance is not a positive integer.
- Stop if `family_id` would not be `surface-code`.
- Stop if any candidate `code_family` would not be `rotated-surface-code`.
- Stop if `default_suite_id` is not present in `benchmarks/suites/*.json`.
- Stop if any preferred decoder id is not present in `benchmarks/decoders/*.json`
  or is not selected by the chosen suite.
- Stop if any benchmark task default or promotion p-value is not a finite
  probability.
- Stop if the target campaign directory already exists.
- Stop if the user has not explicitly approved materialization.
- Stop if `autoqec-search validate` fails after writing files.

## Approval Gate Language

Use clear approval language. A user saying "looks good", "approved", or
"write the files" is approval. A user saying "wait", "not yet", "show me
first", or "do not write anything yet" is not approval.

When there is no approval, say that no campaign files are written.

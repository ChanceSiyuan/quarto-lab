---
name: compare-candidates
description: Use when comparing two or more AutoQEC search runs and ranking candidates by completed LER points.
---

# compare-candidates

## Overview

This is the review skill for cross-run candidate comparison. It calls
`autoqec-search compare-candidates` on two or more run directories and reports
the generated comparison report.

It must not summarize incomparable runs as a ranked comparison.

## Workflow

1. Resolve two or more run directories under `results/search/`.
2. Explain that the default comparability key is shared task/decoder/p.
3. Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-candidates \
  --root . \
  --run <run-a> \
  --run <run-b> \
  --out <output.html>
```

4. If labels are helpful, include:

```bash
--label <label-a> --label <label-b>
```

5. Report:
   - comparison HTML path
   - comparison JSON path
   - overall winner classification
   - overall winner reporting is strong-only
   - whether any winner is tentative because confidence intervals overlap

## Rules

- Require at least two run directories.
- Completed manifest points are the only ranked data.
- Placeholder and crash manifests are skipped and reported.
- Incomparable runs fail with `incomparable runs: no shared task/decoder/p grid`.
- Do not add a cross-task ranking by hand.
- Do not rank surface and BB runs unless they share task, decoder, and p values
  in the model.
- Overall winner reporting is strong-only: tentative point winners stay visible,
  but the overall field stays `no-clear-winner` unless every shared point has
  the same strong winner.

## Output

Given `--out /tmp/compare.html`, the command writes:

- `/tmp/compare.html`
- `/tmp/compare.json`

The HTML report is self-contained and safe to open offline.

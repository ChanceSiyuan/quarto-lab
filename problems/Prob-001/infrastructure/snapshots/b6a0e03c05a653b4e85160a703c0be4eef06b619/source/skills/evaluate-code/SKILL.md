---
name: evaluate-code
description: Use when evaluating a finite CSS/QEC code with rstim or rsinter, especially requests for code distance upper bounds, random-window CSS distance, p=1e-3 LER, logical error rate per round, max_errors budgets, or gated benchmark runs.
---

# Evaluate Code

## Overview

Evaluate one code in two gated stages: first run rstim's CSS distance upper-bound search, then ask the user whether to continue with a single p = 1e-3 logical-error-rate benchmark reported per round.

Use current rstim tooling; do not reimplement distance search, circuit generation, decoding, confidence intervals, or plotting.

## Workflow

1. Resolve the target code:
   - Prefer explicit CSS `hx.json` and `hz.json` paths.
   - Use explicit logical observables when provided; otherwise state that rsinter will use its canonical fallback.
   - Resolve `code_id`, memory `basis`, decoder, and output directory. Use `basis = "x"`, `schedule = "greedy"`, `decoder = "rbposd"` or the user's requested decoder when not specified.
2. Locate rstim binaries:
   - Prefer `/Users/nzy/rcode/rstim/target/release/qec-code` and `/Users/nzy/rcode/rstim/target/release/rsinter` when present.
   - Otherwise run from `/Users/nzy/rcode/rstim` with `cargo run -q -p qec-code -- ...` or `cargo run -q -p rsinter -- ...`.
   - If a command shape is uncertain, check `--help` before running it.
3. Run distance upper bound with the current windowed sampler:

```bash
qec-code code css-distance random-window-upper-bound \
  --hx <hx.json> \
  --hz <hz.json> \
  --iterations 5000 \
  --restarts 8 \
  --seed 20260626 \
  --json
```

Use `--code-id <built-in-id>` instead of `--hx/--hz` only for registered built-in CSS codes. Add `--target-weight <known-target>` only when the user or source artifact gives a target upper bound.

4. Parse the JSON result. Report:
   - `status`
   - `method`
   - `bound_type`
   - `upper_bound`
   - `logical_class`
   - witness `weight`
   - key search stats, especially `target_reached`
5. Stop after reporting the bound and ask whether to continue with LER. Do not start the LER benchmark until the user explicitly approves.
6. If approved, create a temporary rsinter benchmark spec for one point:

```toml
name = "evaluate_code_p001"
version = 1
mode = "independent"

[[runner]]
name = "rbposd-osd10-v1"
language = "rust"
impl_key = "rbposd"

[runner.params]
input_type = "css"
code_id = "<code-id>"
hx = "<hx.json>"
hz = "<hz.json>"
observables = "<observables.json>"
basis = "x"
schedule = "greedy"
rounds = [<upper_bound>]
p = [0.001]
seed = 20260626
max_shots = <reasonable-shot-budget>
max_errors = 100
batch_size = 64
bp_algorithm = "min_sum"
bp_iters = 50
early_stop = true
osd_method = "combination_sweep"
osd_order = 10

[plot]
title = "Evaluate Code p=1e-3"
logical_rate_unit = "per_round"

[plot.x]
field = "params.p"
scale = "log"
label = "Physical Error Rate"

[plot.series]
group_by = ["runner", "params.code_id"]
label_template = "{runner} {params.code_id}"

[[plot.panel]]
metric = "metrics.logical_error_rate"
scale = "log"
label = "Logical Error Rate per Round"
```

Omit the `observables` line when no explicit logical observable file is available.

If the user meant `mar_error_shot`, treat it as rsinter `max_errors = 100` unless the active CLI help shows a different exact field.

7. Run:

```bash
rsinter bench run --spec <spec.toml> --language rust --out <out-dir>
rsinter bench plot --spec <spec.toml> --input <out-dir>/results.jsonl --out <out-dir>/plot.svg
```

8. Report the per-round LER from the plot/report semantics and keep the raw shot-level fields visible: shots used, logical errors, shot LER, rounds, and stop reason.

## Rules

- Never call an upper bound an exact distance or promotion-safe distance.
- Use `upper_bound` as the rsinter `rounds` value only because the user requested that policy.
- Do not write Zoo records, promotion artifacts, or curated `instance.json` distance fields.
- Stop and preserve exact stderr/stdout if rstim, qec-code, rsinter, rbposd, or CSS parsing fails.
- Do not silently increase `max_errors` above 100 for the p = 1e-3 point.
- If `max_shots` is not specified by the user or an existing benchmark contract, choose a modest local budget and state it before asking approval.

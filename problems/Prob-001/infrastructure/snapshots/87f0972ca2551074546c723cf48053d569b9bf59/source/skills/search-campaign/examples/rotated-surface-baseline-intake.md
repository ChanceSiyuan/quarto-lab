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
- family_id: surface-code
- code_family: rotated-surface-code
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

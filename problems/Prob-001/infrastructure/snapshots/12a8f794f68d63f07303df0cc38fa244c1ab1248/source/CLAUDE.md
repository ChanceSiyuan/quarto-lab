# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

Reference / discussion harness for **AutoQEC**: automated quantum error-correction search, literature tracking, note-taking, and Zulip-based collaboration. This repo is the coordination shell, not the main implementation repo. It bundles the knowledge base, project notes, and the Zulip bridge for the `QEC-automated search` stream.

Git remote: `CodingThrust/AutoQEC` (intended private repo).

## First-time setup (per machine)

**Easiest: just say "onboard me" or "/onboard".**

The flow is two-stage:

1. The thin `onboard` skill in `skills/onboard/` edits `~/.claude/settings.json` to enable the **`zlp-harness`** and **`sci-brain`** plugins globally, then asks you to restart Claude Code.
2. After restart, the same project-level `onboard` skill delegates Zulip setup to `Skill("zlp-harness:zlp-onboard")`, which reads `make zulip-config`, walks through `zlp-cli` install, Zulip API key placement, bridge verification, and the first message sync.

Project-local skills live canonically under `skills/`. For agent compatibility, `.claude/skills` and `.agents/skills` both point to that same directory.

Manual checklist if you'd rather DIY:

1. **Claude Code installed.**
2. **Enable both plugins in `~/.claude/settings.json`**:
   ```jsonc
   "extraKnownMarketplaces": {
     "zlp-harness": {
       "source": { "source": "github", "repo": "GiggleLiu/zlp-harness" }
     },
     "sci-brain": {
       "source": { "source": "github", "repo": "QuantumBFS/sci-brain" }
     }
   },
   "enabledPlugins": {
     "zlp-harness@zlp-harness": true,
     "sci-brain@sci-brain": true
   }
   ```
   Then restart Claude Code.
3. **`zlp` CLI** — `python3 -m pip install --user zlp-cli`
4. **A Zulip API key for `https://qec-harness.zulipchat.com`** — log in there, then open *Personal settings → Account & privacy → API key → Show/change your API key → Download zuliprc*. Save the file to `~/zulip-workspaces/qec-harness/zuliprc` and `chmod 600` it. That path is the default `ZULIP_CONFIG_DIR_DEFAULT`; override with `export ZULIP_CONFIG_DIR=/your/path` only if you keep the credential elsewhere.
5. **`pymupdf4llm`** — only needed when adding new references with `sci-brain:download-ref` or similar workflows:
   ```sh
   python3 -m pip install --user pymupdf4llm
   ```
   If pip complains about an externally managed environment, re-run with `--break-system-packages`.

Verify with `make zulip-whoami`, then run `make zulip-pull IMPORT_HISTORY=1` once to seed `.zulip/`.

## Common commands

All `make` targets are Zulip-bridge wrappers. Run from the repo root.

```sh
# Verify auth
make zulip-whoami

# Inspect the stream
make zulip-topics
make zulip-messages TOPIC=resources LIMIT=5
make zulip-messages TOPIC=resources LIMIT=20 FORMAT=md

# Mirror messages into .zulip/ (gitignored)
make zulip-pull
make zulip-pull TOPIC=resources
make zulip-pull IMPORT_HISTORY=1

# Post a message
make zulip-send TOPIC=resources MSG="hello"
make zulip-send TOPIC=resources MSG_FILE=.zulip/.drafts/msg.md
```

## Knowledge base (`.knowledge/`) — check first

When answering any technical question on this repo's topics, search `.knowledge/` and consult `ref.bib` before anything else.

- `.knowledge/INDEX.md` — table of contents for downloaded references
- `.knowledge/NOTES.md` — project-level survey notes, including imported legacy survey notes
- one markdown file per paper under `.knowledge/`
- `ref.bib` — project-level bibliography namespace for the knowledge base
- `.knowledge/.raw/` and `.knowledge/.figures/` — source PDFs and extracted figures; both are gitignored

Search recipe:

```sh
rg --hidden -g '!.raw' -g '!.figures' "term" .knowledge/
```

If a relevant paper is missing, use a `sci-brain` knowledge workflow instead of answering from memory.

## Structured Zoo (`zoo/`) — normalized code knowledge

When answering code-ontology or code-comparison questions, check `zoo/` before re-deriving facts from raw papers.

- `zoo/codes/**/card.json` — canonical stable facts
- `zoo/evidence/**/*.json` — paper-specific claims and parameter points
- `zoo/views/browse.md` — generated human-readable entry point
- `zoo/external/eczoo/` — committed CC-BY-SA mirror of the Error Correction Zoo
  (codes + relation graph). For code-ontology lookups across the full QEC
  catalog, search `zoo/external/eczoo/index/` or browse `views/browse.md`.
  Rebuild with `make eczoo-build`; refresh the snapshot with `make eczoo-update`.

For extracting new evidence from a paper already indexed in `.knowledge/`, use the project skill:

- `skills/extract-zoo-evidence`

Regenerate the derived artifacts after editing source records:

```sh
make zoo-build
```

## Search Layer (`campaigns/`, `benchmarks/`, `results/search/`)

When working on issue `#3` or related search-architecture tasks, keep these boundaries:

- `campaigns/` stores human-authored campaign intent
- `benchmarks/` stores reusable task, decoder, suite, and schema contracts
- `results/search/` stores run artifacts and example runs, not curated Zoo source-of-truth data

Validate the committed search-layer records with:

```sh
python3 -m autoqec_search.cli validate --root .
```

The installed console entry point for the same workflow is `autoqec-search`.

For issue `#9` and single-candidate evaluation work, use:

```sh
python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-baseline --distance 3 --decoder rmatching-default-v1 --p 0.01
```

The installed form is `autoqec-search eval`. This command strictly requires `rsinter` on `PATH`, creates a fresh eval run, reuses matching Zoo instance artifacts, copies recorded distance from the instance, invokes `rsinter`, and writes `candidate-plot.svg`.

For issue `#17`, use `--general-css` when the eval must go through the generic
CSS adapter:

```bash
python3 -m autoqec_search.cli eval --root . --campaign rotated-surface-css-fixture --distance 3 --decoder rmatching-default-v1 --p 0.005 --run-id local-general-css-d3 --general-css
```

This keeps the existing surface path as the default, but routes stored
`hx/hz -> rstim CSS -> DEM -> decoder`. It requires upstream rstim #46/#51
support in `rsinter`; malformed or noncommuting `hx/hz` fail before backend
execution. BB/qLDPC campaigns remain issue #18.

Distance-method work lives in `src/autoqec_search/distance_methods.py`. The
registry is exact-first. The default `copied-zoo-exact` method records Zoo
`derived_properties.distance` as `bound_type: "exact"` and writes method
options plus provenance into `distance.json`; it must not require `qec-code`.
The guarded `rstim-ilp-exact` method is reserved for the external exact CSS
distance backend and currently fails clearly with
`rstim exact CSS distance backend is not available` when that backend is not
installed. Randomized upper bounds live in rstim and are not a first-class
AutoQEC method for closing issue #15. Promotion requires exact distances by
default and must never treat an upper bound as Zoo
`derived_properties.distance`.

For issue `#10` and autoresearch run-loop work, use:

```sh
python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 90s --run-id local-autoresearch
```

The installed form is `autoqec-search run`. This command strictly requires `rsinter` on `PATH`, creates branch `autoresearch/<tag>` and worktree `.worktrees/<tag>/`, evaluates candidates from the campaign search space, and commits a lab notebook under `results/search/<campaign>/<run-id>/`. The notebook includes `experiment-log.tsv`, `leaderboard.csv`, `frontier.json`, `summary.md`, `run-summary.html`, `report.html`, and `run_status.json`. Use `--resume --run-id <id>` to continue a run and `--cleanup-worktree` to remove the linked worktree after the final commit while keeping the branch.

For the long-running quantum Tanner launcher
`scripts/run_quantum_tanner_autoresearch.sh`, also check
`<work-root>/aggregate/report.html`. It is the append-ordered cross-round table,
with `<work-root>/aggregate/results.jsonl` as the durable ledger and the
automatic history source for later Codex proposal prompts. `--resume` can
rebuild a missing aggregate from terminal attempts when the pinned source
commit still matches.

For issue `#14` and M2 search strategy work, `search_space.strategy` selects
the proposal policy for `autoqec-search run`. Missing strategy means `grid`.
Supported names are `grid`, `random`, and `adaptive`; new runs record the
selected strategy in `run_spec.json`, `env.json`, and `strategy_trace.json`.

Verify the strategy comparison fixture with:

```sh
PYTHONPATH=src python3 -m autoqec_search.cli compare-strategies --root . --campaign rotated-surface-strategy-fixture --strategies grid adaptive --budget-candidates 3 --metrics benchmarks/fixtures/strategy-comparison/rotated-surface.json --out /tmp/autoqec-strategies.html
```

The installed form is `autoqec-search compare-strategies`.

For issue `#19`, the benchmark skill series is intentionally thin:

- `benchmark-code` performs conversation-first intake, preflight, approval, and
  dispatch.
- `bench-runner-distance` uses existing distance artifacts and eval-backed
  distance generation.
- `bench-runner-mc-ler` routes through `autoqec-search eval`, `run`, and
  `report`.
- `compare-candidates` calls `autoqec-search compare-candidates` on two or more
  run directories.

Use:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli compare-candidates --root . \
  --run results/search/<campaign-a>/<run-a> \
  --run results/search/<campaign-b>/<run-b> \
  --out /tmp/autoqec-candidates.html
```

Default comparability is shared task/decoder/p. Do not hand-rank runs with
different benchmark tasks. Overall winner reporting is strong-only. Tentative
point winners stay visible, but the overall field stays `no-clear-winner`
unless every shared point has the same strong winner. The BB72 OSD1 smoke run
is AutoQEC orchestration evidence, not the deferred OSD10 published-reference
validation.

For issue `#11` and visual run verification, use:

```sh
python3 -m autoqec_search.cli report --root . --run results/search/<campaign>/<run-id>
```

The installed form is `autoqec-search report`. The default output is
`<run>/report.html`; `--out` can write the report elsewhere. The file is
self-contained and offline-safe: inline CSS/SVG plus embedded JSON, with no
network assets. Autoresearch finalization writes `report.html` automatically
alongside `run-summary.html`; use `run-summary.html` for the compact lab
notebook and `report.html` for visual verification.

For issue `#12` and Zoo promotion, use:

```sh
python3 -m autoqec_search.cli promote --root . --run results/search/<campaign>/<run-id>
```

The installed form is `autoqec-search promote`. Promotion reads
`promote_rules.json` beside the campaign unless `--rules` is supplied, evaluates
kept frontier candidates, refuses to overwrite curated instance ids without
`--force`, auto-copy accepted instance into the curated Zoo under
`zoo/codes/<code-id>/instances/<candidate-id>/`, writes
`promotion_summary.json`, and rebuilds `zoo/views/instance-index.json`,
`zoo/views/browse.md`, card markdown, and the static site. Autoresearch
finalization runs the same promotion path automatically; missing rules produce
a skip summary instead of failing the run.

For issue `#13` and the M1 final showcase, the committed result is:

- approval-gated intake skill: `skills/search-campaign/`
- finalized run: `results/search/rotated-surface-baseline/m1-demo/`
  covering d=3/5/7 with `surface_code:rotated_memory_z`, rounds=3*d,
  and physical error rates 0.008, 0.009, 0.01, 0.011, 0.012
- offline report:
  `results/search/rotated-surface-baseline/m1-demo/report.html`
- promoted Zoo instances:
  `zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/`
  `zoo/codes/rotated-surface-code/instances/rotated-surface-d5-example/`
  `zoo/codes/rotated-surface-code/instances/rotated-surface-d7-example/`

Verify the M1 final result from a source checkout with:

```sh
PYTHONPATH=src python3 -m pytest tests/test_search_e2e.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

To rerun the same workflow locally, use a fresh run id so the committed
`m1-demo` stays immutable:

```sh
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign rotated-surface-baseline --wall-clock 60s --run-id local-m1-demo --allow-dirty-root
PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/rotated-surface-baseline/local-m1-demo
PYTHONPATH=src python3 -m autoqec_search.cli promote --root . --run results/search/rotated-surface-baseline/local-m1-demo
```

## Generated Code Instances

When the user asks to generate or store finite-size parity-check matrices, use the project skills:

- `setup-tensorqec` to prepare `julia/tensorqec_env/`
- `generate-code-instance` to create `instance.json`, `hx.json`, and `hz.json` under `zoo/codes/<code-id>/instances/`
- `compute-code-distance` to evaluate an existing stored instance and record `derived_properties.distance`

The repo also provides a direct helper target:

- `make tensorqec-setup`

Generated instances are program-produced source-of-truth records. They are neither canonical card facts nor paper evidence.

For newly generated instances, offer distance computation only when `derived_properties.n <= 200`; skip the prompt when `derived_properties.n > 200`.

## Sci-brain workflows

This harness expects `sci-brain` to be available once onboarding is complete. Useful entry points:

- `sci-brain:survey` — broad topic survey with source gathering
- `sci-brain:download-ref` — add arXiv IDs / DOIs into `.knowledge/`
- `sci-brain:review-writer` — synthesize a focused state-of-the-art summary
- `sci-brain:ideas` — brainstorm concrete research directions
- `sci-brain:idea-writer` — turn selected directions into a structured proposal

For simple "add this paper" requests, prefer `sci-brain:download-ref`. For bigger "what is happening in this area" requests, start with `sci-brain:survey` or `review-writer`.

## Zulip channel (`.zulip/`) — discussion archive

Co-author chat lives in the **`QEC-automated search`** stream on `https://qec-harness.zulipchat.com`. The root `Makefile` wraps the [`zlp`](https://pypi.org/project/zlp-cli/) CLI to mirror that stream into `.zulip/` (gitignored).

The Makefile pins the site, stream, and default credential directory, then exports the env vars `zlp` needs (`ZULIP_CONFIG_FILE`, `ZLP_ARCHIVE_ROOT`, `ZLP_RUN_ROOT`).

Caveats:

- Stream-wide pulls can land in a hash-suffixed `_all-<hash>/` folder.
- `make zulip-pull` mirrors the user's own outgoing messages too.
- `make zulip-send` silently creates a new topic if `TOPIC=` does not match an existing one. Verify spelling with `make zulip-topics | grep -F "<topic>"` first.
- Do not add AI-attribution signatures to outgoing Zulip messages.

## Doing common tasks

**"Check Zulip" / "what did X say" / "draft a reply"**  
Use `zulip-reply`.

**"Add this arXiv ref" / "add this DOI"**  
Use `sci-brain:download-ref`.

**"Survey the latest work on automated QEC / decoder search / neutral-atom QEC / erasure decoding"**  
Use `sci-brain:survey` first, then ground follow-up work in the resulting `.knowledge/` files.

**"Write a literature review / status memo"**  
Use `sci-brain:review-writer`.

**"Brainstorm research directions"**  
Use `sci-brain:ideas`.

## Reliable update sources

Use these sources when looking for current external updates during advisor-style reviews or scheduled scans.

- Source types: arXiv, official project repositories, high-signal lab/group pages, peer-reviewed venues
- arXiv queries / categories:
  - `cat:quant-ph AND ("error correction" OR decoder OR erasure OR leakage)`
  - `cat:quant-ph AND ("neutral atom" OR Rydberg) AND ("error correction" OR erasure)`
  - `cat:quant-ph AND ("LDPC" OR "bivariate bicycle" OR "tensor network decoder")`
- Web-search keywords:
  - `quantum error correction automated search`
  - `neutral atom quantum error correction`
  - `erasure decoding quantum code`
  - `quantum decoder benchmark`
  - `tesseract decoder Stim`
- People / groups / venues / benchmarks to watch:
  - Google Quantum AI / Stim / tesseract-decoder
  - IBM Quantum qLDPC and BB code work
  - neutral-atom QEC groups around Harvard, Chicago, Caltech, Princeton
  - QIP, PRX Quantum, Quantum, Nature Physics, Nature
- Other reliable sources:
  - `https://arxiv.org/list/quant-ph/new`
  - official GitHub release pages for decoders and simulation stacks
  - linked implementation repos once they are added to this section
- Avoid:
  - unsourced social summaries, SEO blogs, and generic AI-generated news roundups

## What is not in this repo

- No main implementation code yet
- No LaTeX manuscript draft yet (`main.tex`, article-level build files, etc.)
- No committed Zulip archive; `.zulip/` is per-machine state

When implementation repos become stable, list them here and keep this harness focused on discussion, references, and coordination.

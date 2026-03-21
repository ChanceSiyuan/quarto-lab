# _instructions/ — Claude review & generation scripts

Decision tree: which file do I need?

| Task | File | How to use |
|---|---|---|
| Screen a paper for relevance | `identify.md` | Paste into Claude |
| Complete (t.b.c.) gaps in a draft | `revise.md` | Paste into Claude |
| Expand notes into Quarto article | `generate.md` | Paste into Claude |
| Integrate .qmd results into LaTeX paper | `integrate_paper.md` | Paste into Claude |
| Generate research issues from a .qmd | `generate_issues.md` | Paste into Claude |
| Polish Quarto Topics (overnight) | `polish_topics.sh` | `nohup` |
| Polish LaTeX paper (overnight) | `polish_paper.sh` | `nohup` |
| Review experiment notes (overnight) | `review_experiments.sh` | `nohup` |
| Deep cyclic paper review | `review_logical_gaps.sh` | `nohup` |

## Shell scripts — common options

All scripts source `lib/claude_runner.sh` and accept these flags:

| Flag | Description | Default |
|---|---|---|
| `--dry-run` | Print what would be done, no Claude calls | `false` |
| `--model=MODEL` | Override the model | per-script |
| `--max=N` | Max iterations | per-script |
| `--cap=N` | Weekly opus call cap | `50` |
| `--start-round=N` | Resume from round N (`review_logical_gaps` only) | `1` |

### Typical usage

```bash
# Create a safety branch first
git add -A && git commit -m "baseline"
git checkout -b polish-$(date +%Y%m%d)

# Fire-and-forget overnight
nohup ./_instructions/polish_topics.sh > polish.log 2>&1 &

# Single target
nohup ./_instructions/review_experiments.sh Experiments/posts/Bernien2017_scars > review.log 2>&1 &

# Dry-run to see what would happen
./_instructions/polish_paper.sh --dry-run
```

## Adding a new review script

1. Set any config overrides (`MODEL`, `MAX_ITERATIONS`, `CALL_LOG`, etc.)
2. Source the library: `source "$REPO_ROOT/_instructions/lib/claude_runner.sh"`
3. Call `parse_common_args TARGETS "$@"` to handle standard flags
4. Define your `build_preamble()`, `QUALITY_CRITERIA`, and review/improve prompts
5. Use `run_claude "desc" "prompt" "preamble" [OUTPUT_VAR]` — returns 0/1/2

## Directory layout

```
_instructions/
├── README.md              ← this file
├── lib/
│   └── claude_runner.sh   ← shared infrastructure
├── polish_paper.sh        ← overnight LaTeX paper polish
├── polish_topics.sh       ← overnight Quarto topic polish
├── review_experiments.sh  ← overnight experiment note review
├── review_logical_gaps.sh ← cyclic section-by-section paper review
├── revise.md              ← complete (t.b.c.) gaps from chat or paper
├── generate.md            ← expand notes into Quarto articles
├── integrate_paper.md     ← integrate Quarto results into LaTeX
├── identify.md            ← screen papers for relevance
├── generate_issues.md     ← generate research issues
└── archive/               ← superseded originals
```

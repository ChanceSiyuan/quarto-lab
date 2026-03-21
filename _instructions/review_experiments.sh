#!/bin/bash
# review_experiments.sh — Overnight review-and-improve loop for experiment reading notes
#
# Processes paper reading notes in Experiments/posts/*, reviewing each for:
#   (0) What was done, observed, and its scientific/practical value
#   (1) Architecture comparison relative to 1-zone/3-zone/4-zone benchmarks
#   (2) Most important technique needing optimization
#   (3) Completeness check with improvement suggestions
#
# Usage:
#   nohup ./_instructions/review_experiments.sh > review_experiments.log 2>&1 &
#   nohup ./_instructions/review_experiments.sh Experiments/posts/Bernien2017_scars > review.log 2>&1 &
#   ./_instructions/review_experiments.sh --dry-run
#
# Safety: create a git safety net BEFORE launching:
#   git add -A && git commit -m "baseline before experiment review"
#   git checkout -b review-experiments-$(date +%Y%m%d)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
REPO_ROOT="$(pwd)"

# ──────────────────────────── Config & args ───────────────────────
MODEL="opus"
MAX_ITERATIONS=50

source "$REPO_ROOT/_instructions/lib/claude_runner.sh"

REVIEW_QMD="Experiments/posts/Lukin_timereview/index.qmd"

TARGETS=()
parse_common_args TARGETS "$@"

# If no targets, discover all post folders with an index.qmd
if [ ${#TARGETS[@]} -eq 0 ]; then
  while IFS= read -r dir; do
    case "$dir" in
      */Lukin_timereview|*/Frequencylock|*/Rb87overview) continue ;;
    esac
    [ -f "$dir/index.qmd" ] || [ -f "$dir/digital-analog.qmd" ] && TARGETS+=("$dir")
  done < <(find Experiments/posts -mindepth 1 -maxdepth 1 -type d | sort)
fi

echo "============================================"
echo "  REVIEW EXPERIMENTS — $(date)"
echo "  Targets (${#TARGETS[@]}): ${TARGETS[*]}"
echo "  Model: $MODEL | Dry-run: $DRY_RUN"
echo "  Max iterations: $MAX_ITERATIONS"
echo "============================================"

# ──────────────────────────── Preamble builder ────────────────────

build_preamble() {
  local dir="$1"
  local bib
  bib=$(detect_bib "$dir")
  local bib_note=""
  [ -n "$bib" ] && bib_note="The bibliography file is at $bib — read it to know what citations are available."

  cat <<PREAMBLE
You are working in the directory $dir/ of a Quarto website at $REPO_ROOT.

CONTEXT: This is a reading note for a specific research paper from the Lukin group's neutral atom quantum simulation program. The main review article is at $REPO_ROOT/$REVIEW_QMD — read it for architecture context (1-zone, 3-zone, 4-zone benchmarks and bottlenecks).

GROUND RULES (never violate):
1. ONLY cite papers already in the bibliography file. $bib_note If you need a new ref, web-search for the paper, verify it exists, add its BibTeX, then cite it. NEVER fabricate a citation.
2. You may append new sections, fill in TODOs, and fix factual/mathematical errors. Do NOT delete or heavily reorganize existing content.
3. After finishing, commit with: git add <files> && git commit -m "<type>: <file> — <summary>"
4. Reader = quantum-computing PhD student. They know the basics. Get to the physics.
5. If stuck on anything for >3 minutes, add <!-- TODO: ... --> and move on.
6. All files use lang: en. Math: \$...\$ inline, \$\$...\$\$ display. Citations: [@key].
7. Use web search to look up papers on arxiv when you need specific experimental parameters, figures, or results not currently in the notes.
PREAMBLE
}

QUALITY_CRITERIA='Quality criteria for experiment reading notes:

--- Content completeness (4-point checklist) ---
(E0) OPERATIONS AND OBSERVATIONS: What operations did the paper perform? What was observed/measured? Does the note explain the scientific significance, practical value, and whether the results verify something previously untested?
(E1) ARCHITECTURE COMPARISON: Does the note compare experimental metrics against the 1-zone/3-zone/4-zone benchmarks from the review? Are specific parameters compared (atom count, gate fidelity, readout fidelity, coherence, etc.)? Are hardware upgrades over prior generations noted?
(E2) CRITICAL TECHNIQUE: Does the note identify the single most important technique that needs optimization for this specific experiment? Is the analysis specific (not generic) — explaining WHY this technique is the bottleneck and HOW improving it would help?
(E3) COMPLETENESS CHECK: Are there remaining TODOs? Are specific numerical values from the paper included (not just qualitative descriptions)? Could a reader extract concrete quantities without consulting the original paper?

--- Factual integrity ---
(F1) All citations resolve against the bibliography file.
(F2) Experimental parameters match the original paper (verify via web search if uncertain).
(F3) Architecture comparisons are accurate relative to the review benchmarks.

--- Readability ---
(R1) Tables are used for structured comparisons (not prose lists).
(R2) Callout boxes are used for experiment protocols.
(R3) The note is self-contained — a reader should understand the experiment without reading the original paper.'

# ──────────────────────────── Main loop ───────────────────────────

ITERATION=0

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
  for WORKDIR in "${TARGETS[@]}"; do
    ITERATION=$((ITERATION + 1))
    if [ $ITERATION -gt $MAX_ITERATIONS ]; then
      echo "  Reached $MAX_ITERATIONS iterations — stopping."
      break 2
    fi

    PREAMBLE=$(build_preamble "$WORKDIR")
    BIB=$(detect_bib "$WORKDIR")
    QMD=$(detect_qmd "$WORKDIR")
    BIB_INSTRUCTION=""
    [ -n "$BIB" ] && BIB_INSTRUCTION="and $BIB"

    echo ""
    echo "============================================"
    echo "  ITERATION $ITERATION — REVIEW: $WORKDIR"
    echo "  QMD: $QMD"
    echo "  $(date)"
    echo "============================================"

    # ── Step A: Review ──────────────────────────────────────────

    REVIEW_PROMPT="You are a CRITICAL REVIEWER auditing experiment reading notes.

STEP 1: Read the .qmd file(s) in $WORKDIR/ $BIB_INSTRUCTION. Also read the main review at $REVIEW_QMD for architecture context.

STEP 2: Evaluate each of the 4 content criteria (E0-E3) and supporting criteria (F1-F3, R1-R3):

$QUALITY_CRITERIA

STEP 3: For each criterion that is NOT fully satisfied, use web search to find the relevant arxiv paper and look up the specific missing information (experimental parameters, results, figures).

Output a structured report:

=== $(basename "$WORKDIR") ===
PASS: E0, E1, ...
FAIL:
- E2: <specific deficiency>
- E3: <specific missing data, e.g., 'Missing specific gate fidelity numbers from Table 1 of the paper'>
- F2: <specific parameter that needs verification>
MISSING DATA (from arxiv search):
- <parameter>: <value found> (source: arxiv:XXXX.XXXXX, Table/Figure N)
PRIORITY FIX: <the single most impactful improvement>

Rules:
- Be specific. 'Needs more detail' is not acceptable — specify WHAT detail is missing.
- Use web search to find missing experimental parameters.
- If everything genuinely passes all criteria, write ALL PASS.
- Do NOT suggest fixes — only diagnose with precision."

    REVIEW_OUTPUT=""
    run_claude "Review $WORKDIR (#$ITERATION)" "$REVIEW_PROMPT" "$PREAMBLE" REVIEW_OUTPUT || continue

    # Check if all criteria pass
    if echo "$REVIEW_OUTPUT" | grep -q "ALL PASS" && ! echo "$REVIEW_OUTPUT" | grep -q "^FAIL:"; then
      echo ""
      echo "  ALL CRITERIA PASS for $WORKDIR at iteration $ITERATION"
      echo "  Moving to next target..."
      sleep "$PAUSE_BETWEEN"
      continue
    fi

    sleep "$PAUSE_BETWEEN"

    echo ""
    echo "============================================"
    echo "  ITERATION $ITERATION — IMPROVE: $WORKDIR"
    echo "  $(date)"
    echo "============================================"

    # ── Step B: Improve ─────────────────────────────────────────

    IMPROVE_PROMPT="You are an IMPROVER. Read the .qmd file(s) in $WORKDIR/ $BIB_INSTRUCTION and the review at $REVIEW_QMD.

Here is the review report from the previous step:

--- BEGIN REVIEW ---
$REVIEW_OUTPUT
--- END REVIEW ---

$QUALITY_CRITERIA

Your task:
1. Read the review report. Focus on FAIL items and MISSING DATA.
2. For each missing experimental parameter listed in MISSING DATA:
   - Web-search for the paper on arxiv
   - Find the specific number/value
   - Add it to the appropriate section of the .qmd file
3. For E0-E3 failures:
   - E0 (operations/observations): Add a clear description of what was done and why it matters
   - E1 (architecture comparison): Add a comparison table against the review benchmarks
   - E2 (critical technique): Add analysis of the single most important bottleneck
   - E3 (completeness): Fill in TODOs with specific values from the paper
4. Fix at most 2-3 issues per iteration. Be thorough on each.
5. Do NOT delete existing content. Append or edit in-place.
6. If adding citations, web-search to verify the BibTeX entry exists.
7. Commit: git add <files> && git commit -m 'review: <file> — <what was added>'"

run_claude "Improve $WORKDIR (#$ITERATION)" "$IMPROVE_PROMPT" "$PREAMBLE" || continue

    echo ""
    echo "  Iteration $ITERATION complete at $(date)"
    sleep "$PAUSE_BETWEEN"
  done

  echo ""
  echo "  Full round complete. Starting next round... ($ITERATION/$MAX_ITERATIONS)"
  echo "  (Press Ctrl+C to stop)"
  sleep "$PAUSE_BETWEEN"
done

echo ""
echo "============================================"
echo "  ALL $MAX_ITERATIONS ITERATIONS COMPLETE — $(date)"
echo "============================================"

#!/bin/bash
# generate_and_polish.sh — Three-phase overnight automation for Noisy_complexity
#
# Phase 1 (IDENTIFY):  Read all sources, create folder scaffold (index, sidebar, stubs)
# Phase 2 (GENERATE):  Write full content for each .qmd file (1 call per file)
# Phase 3 (POLISH):    Iterative REVIEW → IMPROVE loop until quality passes or budget exhausted
#
# Usage:
#   # Full run (all 3 phases)
#   nohup theory/Noisy_complexity/generate_and_polish.sh > noisy_gen.log 2>&1 &
#
#   # Skip to Phase 2 (scaffold already exists)
#   nohup theory/Noisy_complexity/generate_and_polish.sh --start-phase=2 > noisy_gen.log 2>&1 &
#
#   # Skip to Phase 3 only (all .qmd files already written)
#   nohup theory/Noisy_complexity/generate_and_polish.sh --start-phase=3 > noisy_gen.log 2>&1 &
#
#   # Dry run
#   theory/Noisy_complexity/generate_and_polish.sh --dry-run
#
# Safety: create a git safety net BEFORE launching:
#   git add -A && git commit -m "baseline before noisy-complexity generation"
#   git checkout -b noisy-gen-$(date +%Y%m%d)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
REPO_ROOT="$(pwd)"

# ──────────────────────────── Config ─────────────────────────────

MAX_ITERATIONS=30
PAUSE_BETWEEN=10
START_PHASE=1

# Source material paths (relative to REPO_ROOT)
SRC_DIR="theory/Noisy_complexity"
OUT_DIR="theory/Noisy_complexity"
PDF_FILE="$SRC_DIR/Project_ Noisy circuit simulation.pdf"
FOLDER1="$SRC_DIR/classical_simu_non_unital_by_pauli_path"
FOLDER2="$SRC_DIR/Noise_induced_Phase_transition_in_noisy_Clifford_T_circuit"

# Budget + progress tracking
STATE_DIR="$REPO_ROOT/.noisy_gen_state"
CALL_LOG="$STATE_DIR/opus_calls.log"
PROGRESS_FILE="$STATE_DIR/progress"

source "$REPO_ROOT/_instructions/lib/claude_runner.sh"

# Parse extra flag --start-phase=N alongside standard flags
TARGETS=()
for arg in "$@"; do
  case "$arg" in
    --start-phase=*) START_PHASE="${arg#--start-phase=}" ;;
    *)               TARGETS+=("$arg") ;;
  esac
done
parse_common_args TARGETS "${TARGETS[@]+"${TARGETS[@]}"}"

mkdir -p "$STATE_DIR"
touch "$CALL_LOG" "$PROGRESS_FILE"

# Reference template: Shadow_tomography
REF_DIR="theory/Shadow_tomography"

echo "============================================"
echo "  NOISY COMPLEXITY — GENERATE & POLISH"
echo "  $(date)"
echo "  Source: $SRC_DIR"
echo "  Output: $OUT_DIR"
echo "  Start phase: $START_PHASE"
echo "  Model: $MODEL | Dry-run: $DRY_RUN"
echo "============================================"

# ──────────────────────────── Preamble (shared) ──────────────────

PREAMBLE="You are a senior quantum information researcher working on a Quarto website at $REPO_ROOT.

SOURCE MATERIALS (READ these thoroughly — they are the ONLY ground truth):
- Research diary PDF (80 pages, Chinese+English): $REPO_ROOT/$PDF_FILE
- LaTeX project 1 (Pauli spectrum / truncation):
    $REPO_ROOT/$FOLDER1/main/Submission.tex (main paper)
    $REPO_ROOT/$FOLDER1/main/Technical details.tex (appendix)
    $REPO_ROOT/$FOLDER1/main/draft.tex (earlier draft)
    $REPO_ROOT/$FOLDER1/main/references.bib
    $REPO_ROOT/$FOLDER1/Presentation/pre.tex (slides)
    $REPO_ROOT/$FOLDER1/Presentation/pre2.tex (slides)
- LaTeX project 2 (gadget + percolation):
    $REPO_ROOT/$FOLDER2/main/draft.tex (main paper)
    $REPO_ROOT/$FOLDER2/main/references.bib
    $REPO_ROOT/$FOLDER2/Presentation/pre.tex (slides)

REFERENCE TEMPLATE (mimic this structure):
- Index page: $REPO_ROOT/$REF_DIR/index.qmd
- Sidebar: $REPO_ROOT/$REF_DIR/_sidebar.yml
- Example sub-page: $REPO_ROOT/$REF_DIR/intro.qmd

OUTPUT DIRECTORY: $REPO_ROOT/$OUT_DIR

PLAN FILE (read this for topic breakdown and requirements): $REPO_ROOT/$SRC_DIR/plan.md

GROUND RULES (never violate):
1. Reader = quantum computing PhD student. No undergraduate explanations. Get to the physics/math.
2. Language: English (lang: en). Translate Chinese source material into formal academic English.
3. Math: \$...\$ inline, \$\$...\$\$ display. Citations: [@key].
4. Formal blocks: Definitions (::: {#def-* .callout-note icon=\"false\"}), Theorems/Lemmas (::: {#thm-* .callout-important icon=\"false\"}), Proofs (::: {.callout-note collapse=\"true\"}).
5. ONLY cite papers in refs.bib. To add a new ref: web-search, verify it exists, add BibTeX to refs.bib, then cite. NEVER fabricate.
6. Every substantive point (theorem, lemma, conjecture, observation, open question) from the sources MUST appear in exactly one .qmd file. No content loss.
7. If stuck on anything for >3 minutes, add <!-- TODO: ... --> and move on.
8. After each task, commit: git add <files> && git commit -m '<type>: <summary>'"

# ──────────────────────────── Phase 1: IDENTIFY ──────────────────

if [ "$START_PHASE" -le 1 ] && ! grep -qF "phase1_done" "$PROGRESS_FILE" 2>/dev/null; then
  echo ""
  echo "========================================================"
  echo "  PHASE 1: IDENTIFY — Read Sources & Create Scaffold"
  echo "  $(date)"
  echo "========================================================"

  PHASE1_PROMPT="You are executing Phase 1 of the Noisy_complexity topic generation.

YOUR TASK:
1. Read the plan file at $REPO_ROOT/$SRC_DIR/plan.md to understand the full requirements.
2. Read ALL source materials listed in the plan (the PDF, ALL .tex files in both Folder1 and Folder2, ALL .bib files).
3. Read the reference template folder $REPO_ROOT/$REF_DIR/ (index.qmd, _sidebar.yml, intro.qmd) to understand the target format.
4. Based on the source material, CONFIRM or REVISE the topic breakdown in the plan. The plan lists 7 provisional topics. You may merge, split, or rename them, but you MUST cover every substantive point from the sources.
5. Create the output directory and generate ALL of the following files:

   a) $REPO_ROOT/$OUT_DIR/_sidebar.yml — navigation structure (follow Shadow_tomography format exactly)
   b) $REPO_ROOT/$OUT_DIR/refs.bib — unified bibliography:
      - Merge ALL entries from Folder1/main/references.bib and Folder2/main/references.bib
      - Add references cited by name/URL in the PDF (web-search to get proper BibTeX)
      - Include foundational papers mentioned in the sources (Aharonov1996, Ben-Or2013, Schuster2024, etc.)
   c) $REPO_ROOT/$OUT_DIR/index.qmd — full landing page following Shadow_tomography/index.qmd format:
      - YAML frontmatter with title, date, categories, description, abstract, bibliography
      - Introduction section (3-5 paragraphs on noisy circuit simulation landscape)
      - Overview and Motivation with links to each sub-page and key concepts
      - Central Problems (callout boxes for 3-4 core research questions)
      - Notation and Conventions table
      - Key Results Summary table
   d) Stub .qmd files for each topic — each stub contains:
      - Complete YAML frontmatter
      - 'Summary and Key Questions' section (3-5 sentences + bulleted questions)
      - Section headers (empty) showing the planned structure
      - <!-- SOURCE: ... --> comments mapping each section to specific source pages/files

6. Commit everything: git add $OUT_DIR && git commit -m 'scaffold: Noisy_complexity topic folder with index and stubs'

CRITICAL: After creating the stubs, list all .qmd filenames you created (excluding index.qmd) — this list will drive Phase 2."

  PHASE1_OUTPUT=""
  run_claude "Phase 1: Identify & Scaffold" "$PHASE1_PROMPT" "$PREAMBLE" PHASE1_OUTPUT
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "phase1_done" >> "$PROGRESS_FILE"
  elif [ "$rc" -eq 2 ]; then
    echo "  Budget exhausted in Phase 1. Exiting."
    exit 1
  else
    echo "  Phase 1 failed. Check log and retry."
    exit 1
  fi
  sleep "$PAUSE_BETWEEN"
fi

# ──────────────────────────── Phase 2: GENERATE ──────────────────

if [ "$START_PHASE" -le 2 ]; then
  echo ""
  echo "========================================================"
  echo "  PHASE 2: GENERATE — Write Full Content"
  echo "  $(date)"
  echo "========================================================"

  # Discover all stub .qmd files (excluding index.qmd)
  QMD_FILES=()
  if [ -d "$OUT_DIR" ]; then
    while IFS= read -r f; do
      QMD_FILES+=("$f")
    done < <(find "$OUT_DIR" -maxdepth 1 -name '*.qmd' ! -name 'index.qmd' | sort)
  fi

  if [ ${#QMD_FILES[@]} -eq 0 ]; then
    echo "  ERROR: No .qmd stubs found in $OUT_DIR. Run Phase 1 first."
    exit 1
  fi

  echo "  Found ${#QMD_FILES[@]} stub files to generate:"
  printf '    %s\n' "${QMD_FILES[@]}"

  for QMD_FILE in "${QMD_FILES[@]}"; do
    BASENAME=$(basename "$QMD_FILE")
    PHASE2_MARKER="phase2_${BASENAME}"

    if grep -qF "$PHASE2_MARKER" "$PROGRESS_FILE" 2>/dev/null; then
      echo "  [SKIP] $BASENAME — already generated."
      continue
    fi

    if ! check_budget; then
      echo "  Budget exhausted during Phase 2. Will resume from here next run."
      exit 1
    fi

    echo ""
    echo "  ── Generating: $BASENAME ──"

    GENERATE_PROMPT="You are executing Phase 2 for file: $BASENAME

YOUR TASK: Transform the stub file $REPO_ROOT/$QMD_FILE into a COMPLETE, publication-quality Quarto article.

STEPS:
1. Read the plan: $REPO_ROOT/$SRC_DIR/plan.md
2. Read the stub file: $REPO_ROOT/$QMD_FILE — it contains SOURCE mapping comments telling you which source sections to read.
3. Read ALL mapped source materials (the specific .tex sections and PDF pages indicated in the stub).
4. Read the bibliography: $REPO_ROOT/$OUT_DIR/refs.bib
5. Read the index page for context: $REPO_ROOT/$OUT_DIR/index.qmd
6. Write the FULL content for this file:

CONTENT REQUIREMENTS:
- The 'Summary and Key Questions' section must be substantive (not just the stub version).
- Each technical section must contain:
  * Clear exposition connecting to the broader narrative
  * All relevant theorems/lemmas in formal callout blocks with proof sketches
  * All conjectures and numerical observations from the sources
  * Cross-references to other .qmd files where topics connect
- Translate all Chinese content into formal academic English.
- Use web search to:
  * Complete unclear/vague arguments from the PDF research diary
  * Find proper citations for results referenced by name but not formally cited
  * Verify mathematical claims and fill derivation gaps
  * Find recent related work (post-2023) that connects to each topic
- Add any new references to refs.bib.
- Mark anything you cannot resolve with <!-- TODO: ... -->.

COMPLETENESS CHECK: After writing, re-read the source mapping comments and verify that EVERY point listed there appears in your output. If anything is missing, add it.

7. Commit: git add $QMD_FILE $OUT_DIR/refs.bib && git commit -m 'generate: $BASENAME — full content'"

    run_claude "Phase 2: Generate $BASENAME" "$GENERATE_PROMPT" "$PREAMBLE"
    rc=$?
    if [ "$rc" -eq 0 ]; then
      echo "$PHASE2_MARKER" >> "$PROGRESS_FILE"
    elif [ "$rc" -eq 2 ]; then
      echo "  Budget exhausted. Will resume from $BASENAME next run."
      exit 1
    else
      echo "  WARNING: Generation of $BASENAME may have failed. Continuing..."
    fi
    sleep "$PAUSE_BETWEEN"
  done

  echo ""
  echo "  Phase 2 complete. All files generated."
fi

# ──────────────────────────── Phase 3: POLISH ────────────────────

if [ "$START_PHASE" -le 3 ]; then
  echo ""
  echo "========================================================"
  echo "  PHASE 3: POLISH — Iterative Review & Improve"
  echo "  $(date)"
  echo "========================================================"

  WORKDIR="$OUT_DIR"
  BIB="$OUT_DIR/refs.bib"

  QUALITY_CRITERIA='Quality criteria for each sub-page:

--- Structural completeness ---
(Q1) Has a clear "Summary and Key Questions" section (3-5 sentences + bulleted questions).
(Q2) Core technical sections are present with sufficient depth. No section is merely a stub or placeholder.
(Q3) Important results are in theorem/lemma callout boxes with proof sketches.
(Q4) Source coverage: ALL points from the mapped source materials appear. No content loss.
(Q5) Cross-references to related .qmd files are present where topics connect.

--- Factual & citation integrity ---
(Q6) All [@citekey] citations resolve against refs.bib. No <!-- TODO --> markers remain.
(Q7) Content is detailed enough for a PhD student to reconstruct the argument without consulting original papers.
(Q8) No sections are suspiciously short (< 5 lines) compared to sibling sections.

--- Readability & logical coherence (read LINE BY LINE) ---
(Q9)  Every derivation step follows logically. No hidden leaps.
(Q10) Notation is consistent WITHIN and ACROSS files. Same symbol = same meaning everywhere.
(Q11) Physical/mathematical reasoning is self-consistent. Approximation conditions are stated.
(Q12) Theoretical completeness: key derivations have all essential steps; a reader could reconstruct using ONLY what is written.'

  POLISH_PREAMBLE="You are working in the directory $WORKDIR/ of a Quarto website at $REPO_ROOT.

SOURCE MATERIALS (consult when verifying content or filling gaps):
- PDF: $REPO_ROOT/$PDF_FILE
- Folder1 .tex files: $REPO_ROOT/$FOLDER1/main/
- Folder2 .tex files: $REPO_ROOT/$FOLDER2/main/
- Plan: $REPO_ROOT/$SRC_DIR/plan.md

GROUND RULES (never violate):
1. ONLY cite papers in $BIB. To add a new ref: web-search, verify, add BibTeX, then cite. NEVER fabricate.
2. Do NOT rewrite, delete, reorganize, or rephrase existing text. You may ONLY: append new sections, fill in <!-- TODO --> placeholders, fix factual/mathematical errors in-place, and improve unclear passages.
3. After finishing, commit with: git add <files> && git commit -m '<type>: <file> — <summary>'
4. Theorem statements must be precise and correct. Proofs: short sketches (key idea in ≤10 lines) + citation.
5. Reader = quantum-computing PhD student. No undergraduate explanations.
6. If stuck on anything for >3 minutes, add <!-- TODO: ... --> and move on.
7. All files use lang: en. Math: \$...\$ inline, \$\$...\$\$ display. Citations: [@key]."

  ITERATION=0
  POLISH_START=$(grep -c "^phase3_iter_" "$PROGRESS_FILE" 2>/dev/null || true)
  ITERATION=${POLISH_START:-0}

  while [ "$ITERATION" -lt "$MAX_ITERATIONS" ]; do
    ITERATION=$((ITERATION + 1))
    ITER_MARKER="phase3_iter_${ITERATION}"

    if grep -qF "$ITER_MARKER" "$PROGRESS_FILE" 2>/dev/null; then
      echo "  [SKIP] Polish iteration $ITERATION — already done."
      continue
    fi

    if ! check_budget; then
      echo "  Budget exhausted. Sleeping 1 hour..."
      sleep 3600
      if ! check_budget; then
        echo "  Still exhausted. Exiting. Resume with --start-phase=3"
        exit 0
      fi
    fi

    echo ""
    echo "============================================"
    echo "  POLISH ITERATION $ITERATION / $MAX_ITERATIONS — REVIEW"
    echo "  $(date)"
    echo "============================================"

    # ── Step A: Review ──────────────────────────────────────────

    REVIEW_PROMPT="You are a CRITICAL REVIEWER performing a deep, line-by-line audit.

STEP 1: Read ALL .qmd files in $WORKDIR/ and $BIB — every line, no skimming.

STEP 2: For each sub-page file, perform TWO passes:

  PASS 1 — Structural checklist (Q1-Q8): does each required section exist and have sufficient depth?
  PASS 2 — Line-by-line coherence audit (Q9-Q12): read every sentence and check:
    - Does this sentence follow logically from the previous one?
    - Is notation consistent within and across files?
    - Do claimed properties follow from the stated formalism?
    - Are approximation validity regimes stated?
    - Could a careful reader reconstruct the argument without opening cited papers?

ALSO CHECK source coverage: Compare the content against the source materials (PDF, Folder1, Folder2). Flag any substantive point that is MISSING from the .qmd files.

$QUALITY_CRITERIA

Output a structured report in this EXACT format (one block per file):

=== <filename> ===
PASS: Q1, Q3, Q5
FAIL:
- Q2: <specific deficiency with line number or quoted sentence>
- Q9: Line 47 says '...' but the preceding paragraph only establishes '...' — the connection is missing.
- Q10: Symbol X used on line 32 conflicts with definition in index.qmd line 15.
PRIORITY FIX: <the single most impactful issue to fix>

Rules:
- Be ruthlessly strict. A section that exists but is hand-wavy counts as FAIL.
- For Q9-Q12 failures, cite the SPECIFIC line number or quote the problematic sentence.
- If everything genuinely passes all 12 criteria, write ALL PASS.
- Do NOT suggest fixes — only diagnose problems with precision."

    REVIEW_OUTPUT=""
    run_claude "Polish Review #$ITERATION" "$REVIEW_PROMPT" "$POLISH_PREAMBLE" REVIEW_OUTPUT || {
      echo "  Review failed, skipping this iteration."
      sleep "$PAUSE_BETWEEN"
      continue
    }

    # Check if all files pass
    if echo "$REVIEW_OUTPUT" | grep -q "ALL PASS" && ! echo "$REVIEW_OUTPUT" | grep -q "^FAIL:"; then
      echo ""
      echo "  ALL FILES PASS at iteration $ITERATION"
      echo "$ITER_MARKER" >> "$PROGRESS_FILE"
      echo "  Polish complete!"
      break
    fi

    sleep "$PAUSE_BETWEEN"

    echo ""
    echo "============================================"
    echo "  POLISH ITERATION $ITERATION / $MAX_ITERATIONS — IMPROVE"
    echo "  $(date)"
    echo "============================================"

    # ── Step B: Improve ─────────────────────────────────────────

    IMPROVE_PROMPT="You are an IMPROVER. Read ALL .qmd files in $WORKDIR/ and $BIB.

Here is the review report from the previous step:

--- BEGIN REVIEW ---
$REVIEW_OUTPUT
--- END REVIEW ---

$QUALITY_CRITERIA

Your task:
1. Read the review report carefully. Pay special attention to Q9-Q12 failures — these are coherence and theory issues.
2. Identify the TOP 2-3 HIGHEST-IMPACT deficiencies across all files. Priority order:
   (a) Q4 — missing source content (content loss is the worst defect)
   (b) Q11/Q12 — physical/mathematical inconsistencies or incomplete theory
   (c) Q9/Q10 — logical gaps or notation inconsistencies
   (d) PRIORITY FIX annotations from the reviewer
   (e) Q6 — unresolved TODO markers or broken citations
   (f) Other Q1-Q8 structural issues
3. Fix those 2-3 deficiencies by editing the relevant files:
   - Consult the source materials (PDF, Folder1/Folder2 .tex files) to fill content gaps.
   - Re-derive any problematic step to verify correctness before writing.
   - Use web search to complete unclear arguments or find missing citations.
   - Ensure fixes are self-consistent with the rest of the file and across files.
4. Do NOT rewrite or reorganize existing text — only append, correct errors, or fill placeholders.
5. If fixes require new references, web-search, verify, add to refs.bib.
6. After fixing, re-read the edited section in context to confirm no NEW inconsistencies.
7. Commit: git add <files> && git commit -m 'polish(iter $ITERATION): <what was fixed>'

Focus on 2-3 high-impact fixes per iteration. Be thorough rather than superficial."

    run_claude "Polish Improve #$ITERATION" "$IMPROVE_PROMPT" "$POLISH_PREAMBLE"

    echo "$ITER_MARKER" >> "$PROGRESS_FILE"
    echo ""
    echo "  Polish iteration $ITERATION complete at $(date)"
    sleep "$PAUSE_BETWEEN"
  done
fi

# ──────────────────────────── Summary ────────────────────────────

echo ""
echo "========================================================"
echo "  ALL PHASES COMPLETE — $(date)"
echo "  Weekly calls used: $(count_weekly_calls)"
echo "  Progress file: $PROGRESS_FILE"
echo "========================================================"
echo ""
echo "Next steps:"
echo "  1. Review generated files: ls $OUT_DIR/*.qmd"
echo "  2. Check remaining TODOs: grep -r 'TODO' $OUT_DIR/"
echo "  3. Preview site: quarto preview"
echo "  4. Continue polishing: $0 --start-phase=3"

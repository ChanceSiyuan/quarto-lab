#!/bin/bash
# polish_paper.sh — Iterative review-and-improve loop for main.tex
#
# Runs a REVIEW → IMPROVE cycle on the Multi_copy_shadow_tomography paper.
# Designed to run continuously until Ctrl+C or weekly opus budget exhausted.
#
# Usage:
#   nohup ./_instructions/polish_paper.sh > polish_paper.log 2>&1 &
#
#   # Dry-run:
#   ./_instructions/polish_paper.sh --dry-run
#
# Safety: create a git safety net BEFORE launching:
#   git add -A && git commit -m "baseline before paper polish"
#   git checkout -b polish-paper-$(date +%Y%m%d)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
REPO_ROOT="$(pwd)"

# ──────────────────────────── Config ────────────────────────────
TEX_FILE="_resource/Multi_copy_shadow_tomography/main.tex"
BIB_FILE="_resource/Multi_copy_shadow_tomography/references.bib"
MAX_RETRIES=30
RETRY_WAIT=600            # 10 min between retries on rate limit
PAUSE_BETWEEN=15          # seconds between review→improve
MODEL="opus"
DRY_RUN=false

# Opus weekly budget control: stop when weekly calls reach this % of cap
OPUS_WEEKLY_CAP=50        # max opus calls per week (adjust to your plan)
OPUS_BUDGET_PERCENT=100    # stop at 70% of weekly cap
STATE_DIR="$REPO_ROOT/.polish_state"
CALL_LOG="$STATE_DIR/opus_calls.log"

# ──────────────────────────── Args ──────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --cap=*)   OPUS_WEEKLY_CAP="${arg#--cap=}" ;;
  esac
done

mkdir -p "$STATE_DIR"
touch "$CALL_LOG"

# ──────────────────────────── Budget tracking ───────────────────
get_week_id() { date +%G-W%V; }

count_weekly_calls() {
  local week_id count
  week_id=$(get_week_id)
  count=$(grep -c "^${week_id}" "$CALL_LOG" 2>/dev/null) || true
  echo "${count:-0}"
}

record_call() {
  echo "$(get_week_id) $(date +%s) $(date)" >> "$CALL_LOG"
}

check_budget() {
  local used max_allowed
  used=$(count_weekly_calls)
  max_allowed=$(( OPUS_WEEKLY_CAP * OPUS_BUDGET_PERCENT / 100 ))
  if [ "$used" -ge "$max_allowed" ]; then
    echo "  BUDGET EXHAUSTED: $used / $max_allowed calls (${OPUS_BUDGET_PERCENT}% of ${OPUS_WEEKLY_CAP}) this week."
    echo "  Stopping to preserve remaining opus quota."
    return 1
  fi
  echo "  Budget: $used / $max_allowed calls used this week."
  return 0
}

# ──────────────────────────── Preamble ──────────────────────────

PREAMBLE="You are a senior quantum information researcher polishing a LaTeX paper.

WORKING FILES:
- Main tex: $REPO_ROOT/$TEX_FILE
- Bibliography: $REPO_ROOT/$BIB_FILE

REFERENCE MATERIALS (read these when you need background, derivation details, or context):
- Quarto research notes on the f-compatibility framework:
  $REPO_ROOT/theory/Posts/compatibility/f-compatiability.qmd
  $REPO_ROOT/theory/Posts/compatibility/compatiablity.qmd
  $REPO_ROOT/theory/Posts/compatibility/multicopy_compatiability.qmd
  $REPO_ROOT/theory/Posts/compatibility/multi-copy_localshadow.qmd
  $REPO_ROOT/theory/Posts/compatibility/multicopy_estimation_framework.qmd
  $REPO_ROOT/theory/Posts/compatibility/nonparametric.qmd
- Shadow tomography notes:
  $REPO_ROOT/theory/Topics/Shadow_tomography/intro.qmd
  $REPO_ROOT/theory/Topics/Shadow_tomography/3desgin_multi_local_shadow.qmd
  $REPO_ROOT/theory/Topics/Shadow_tomography/3d2c_appli1.qmd
  $REPO_ROOT/theory/Topics/Shadow_tomography/3d2c_appli2.qmd
  $REPO_ROOT/theory/Topics/Shadow_tomography/multicopy.qmd
  $REPO_ROOT/theory/Topics/Shadow_tomography/nonlocal_multicopy.qmd
  $REPO_ROOT/theory/Topics/Shadow_tomography/lowerbound.qmd
- Background tex notes in _resource/:
  $REPO_ROOT/_resource/Shadows.tex (shadow tomography background)
  $REPO_ROOT/_resource/Lowerbound.tex (lower bound techniques)
  $REPO_ROOT/_resource/Purity.tex (purity estimation)
  $REPO_ROOT/_resource/Clifford_sym.tex (Clifford symmetry)
  $REPO_ROOT/_resource/Upperbound.tex (upper bound constructions)
  $REPO_ROOT/_resource/Preliminaries.tex (mathematical preliminaries)
- Discussion notes:
  $REPO_ROOT/_resource/Claude-非交换算子的k-replica对称扩展与SDP优化.md

HOW TO USE REFERENCES:
- When encountering a derivation you are unsure about, READ the relevant .qmd or .tex reference file to find the detailed calculation.
- When a TODO asks you to prove something, check the reference notes first — the proof may already exist there.
- When you need to verify a claim or find a missing step, USE WEB SEARCH to look up the relevant paper on arXiv or journals.
- When adding citations, web-search for the exact paper to get correct BibTeX.

GROUND RULES (never violate):
1. Do NOT restructure or heavily rewrite the appendix. Work within the existing structure.
2. ONLY cite papers already in the bibliography. If you need a new reference, web-search for the exact BibTeX entry, verify the paper exists and is relevant, add it to references.bib, then cite it. NEVER fabricate a citation key or paper.
3. Red-colored text (\\color{red}...\\color{black} or \\textcolor{red}{...}) marks TODOs. When you COMPLETE a TODO, keep the completed content in red so the author can review it. When you ADD a new TODO, also mark it in red.
4. Maintain notation consistency: use \\tr, \\ox, \\1, \\ket, \\bra, \\proj, \\cF, \\cH, etc. as defined in the preamble.
5. Reader = quantum computing researcher. No undergraduate explanations.
6. After finishing edits, commit with: git add $TEX_FILE $BIB_FILE && git commit -m 'polish: <concise summary of what was fixed>'
7. The paper uses revtex4-2, PRL-style main body (~4 pages) + Supplemental Material appendix.
8. If stuck on anything for >5 minutes, add \\textcolor{red}{[TODO: ...]} and move on.
9. When unsure about a mathematical step, ALWAYS consult the reference materials or web-search before guessing."

# ──────────────────────────── Quality criteria ──────────────────

QUALITY_CRITERIA='Quality criteria (read the file LINE BY LINE):

--- Logical correctness ---
(L1) Every derivation step follows logically from the previous one. If the text says "therefore" or "it follows that", the conclusion must actually follow. Flag any gap.
(L2) All operator commutation claims are verified: check [A,B]=0 claims with explicit calculation or clear reference.
(L3) Eigenvalue claims match the operator structure. Spin-1 vs spin-1/2 claims are consistent.
(L4) The conditions for theorem applicability are stated and satisfied where the theorem is invoked.
(L5) No circular reasoning: results in the main text do not silently depend on appendix results that in turn depend on the main text result.

--- Rigor and precision ---
(R1) Definitions are complete: all symbols are defined before use, quantifiers (for all, there exists) are explicit.
(R2) Theorem statements have all necessary hypotheses. No implicit assumptions.
(R3) Proof sketches contain the key non-trivial step, not just the conclusion.
(R4) Approximation regimes are stated with validity conditions.
(R5) Notation is consistent WITHIN and ACROSS main text and appendix. Same symbol = same meaning everywhere.

--- TODO and completeness ---
(T1) All \\color{red} and \\textcolor{red} TODO markers are catalogued.
(T2) Empty \\begin{proof}...\\end{proof} blocks are flagged.
(T3) Sections that end abruptly or trail off are flagged.
(T4) Missing examples in example paragraphs (empty \\paragraph{} blocks) are flagged.

--- Main text vs appendix coherence ---
(C1) Main text claims are substantiated by appendix proofs. No orphan claims.
(C2) Theorem/lemma/equation references resolve correctly.
(C3) The main text narrative is optimized: concise, no redundancy with appendix, proper forward references.
(C4) The abstract accurately summarizes the actual content.

--- Citations ---
(X1) All \\cite{} keys exist in references.bib. No undefined references.
(X2) Key results are properly attributed. No missing citations for well-known results.
(X3) Related work is adequately discussed.'

# ──────────────────────────── Helpers ───────────────────────────

run_claude() {
  local desc="$1"
  local prompt="$2"
  local attempt=1

  if $DRY_RUN; then
    echo "[DRY-RUN] Would run: $desc"
    echo "[DRY-RUN] Prompt length: ${#prompt} chars"
    return 0
  fi

  while [ $attempt -le $MAX_RETRIES ]; do
    if ! check_budget; then
      return 2
    fi

    echo ""
    echo "--------------------------------------------"
    echo "  STARTING: $desc (attempt $attempt/$MAX_RETRIES)"
    echo "  $(date)"
    echo "--------------------------------------------"

    local output
    output=$(claude -p \
      --dangerously-skip-permissions \
      --model "$MODEL" \
      --append-system-prompt "$PREAMBLE" \
      "$prompt" 2>&1) && {
      record_call
      echo "$output"
      echo ""
      echo "  FINISHED: $desc at $(date)"
      echo "--------------------------------------------"
      sleep 5
      return 0
    }

    if echo "$output" | grep -qi "limit\|rate\|quota\|resets\|throttl\|overloaded"; then
      echo "$output"
      echo "  RATE LIMITED — waiting ${RETRY_WAIT}s (attempt $attempt/$MAX_RETRIES)"
      sleep $RETRY_WAIT
      attempt=$((attempt + 1))
    else
      echo "$output"
      echo "  ERROR (non-rate-limit): $desc — skipping."
      echo "--------------------------------------------"
      sleep 10
      return 1
    fi
  done

  echo "  GAVE UP after $MAX_RETRIES retries: $desc"
  return 1
}

# ──────────────────────────── Main loop ─────────────────────────

echo "============================================"
echo "  POLISH PAPER — $(date)"
echo "  File: $TEX_FILE"
echo "  Model: $MODEL | Dry-run: $DRY_RUN"
echo "  Weekly cap: $OPUS_WEEKLY_CAP | Budget: ${OPUS_BUDGET_PERCENT}%"
echo "============================================"

ITERATION=0

while true; do
  ITERATION=$((ITERATION + 1))

  if ! check_budget; then
    echo "  Weekly budget exhausted. Sleeping 1 hour before rechecking..."
    sleep 3600
    continue
  fi

  echo ""
  echo "============================================"
  echo "  ITERATION $ITERATION — REVIEW"
  echo "  $(date)"
  echo "============================================"

  # ── Step A: Review ──────────────────────────────────────────

  REVIEW_PROMPT="You are a CRITICAL REVIEWER performing a deep, line-by-line audit of a quantum computing paper.

STEP 1: Read the ENTIRE file $TEX_FILE — every line from \\begin{document} to \\end{document}. Also read $BIB_FILE to know available citations.

STEP 2: Perform THREE passes:

  PASS 1 — Logical correctness (L1-L5): For every equation, derivation, and theorem invocation, verify the logic. Check commutation claims, eigenvalue statements, and theorem conditions.

  PASS 2 — Rigor and precision (R1-R5): Check definitions, theorem statements, notation consistency. Flag any imprecise or hand-wavy statements.

  PASS 3 — Completeness and coherence (T1-T4, C1-C4, X1-X3): Catalogue all TODOs, empty proofs, undefined references. Check main text vs appendix coherence.

$QUALITY_CRITERIA

Output a structured report in this EXACT format:

=== LOGICAL ISSUES ===
- [L#] Line NNN: <specific issue with quoted text>
...

=== RIGOR ISSUES ===
- [R#] Line NNN: <specific issue>
...

=== TODO STATUS ===
- Line NNN: <todo description> — STATUS: [open/partially done/can be completed now]
...

=== EMPTY/INCOMPLETE SECTIONS ===
- Line NNN: <what is missing>
...

=== CITATION ISSUES ===
- Line NNN: <missing or broken citation>
...

=== MAIN TEXT OPTIMIZATION ===
- <specific suggestion for improving main text based on appendix content>
...

=== REDUNDANCIES ===
- Line NNN: <what can be removed and why>
...

=== PRIORITY FIXES (ranked) ===
1. <most impactful fix>
2. <second most impactful>
3. <third>

Rules:
- Be ruthlessly strict. Hand-wavy arguments count as failures.
- For every issue, cite the SPECIFIC line number or quote the problematic text.
- Do NOT suggest fixes in detail — only diagnose problems with precision.
- If everything genuinely passes all criteria, write ALL PASS."

  if $DRY_RUN; then
    run_claude "Review #$ITERATION" "$REVIEW_PROMPT"
    sleep 1
    continue
  fi

  REVIEW_OUTPUT=$(claude -p \
    --dangerously-skip-permissions \
    --model "$MODEL" \
    --append-system-prompt "$PREAMBLE" \
    "$REVIEW_PROMPT" 2>&1) && {
    record_call
    echo "$REVIEW_OUTPUT"
  } || {
    if echo "$REVIEW_OUTPUT" | grep -qi "limit\|rate\|quota\|resets\|throttl\|overloaded"; then
      echo "  RATE LIMITED during review — waiting ${RETRY_WAIT}s"
      sleep $RETRY_WAIT
      continue
    fi
    echo "$REVIEW_OUTPUT"
    echo "  Review failed — waiting 60s and retrying..."
    sleep 60
    continue
  }

  if echo "$REVIEW_OUTPUT" | grep -q "ALL PASS"; then
    echo ""
    echo "  ALL CHECKS PASS at iteration $ITERATION"
    echo "  Paper is clean. Exiting."
    break
  fi

  sleep "$PAUSE_BETWEEN"

  # ── Step B: Improve ─────────────────────────────────────────

  echo ""
  echo "============================================"
  echo "  ITERATION $ITERATION — IMPROVE"
  echo "  $(date)"
  echo "============================================"

  IMPROVE_PROMPT="You are an IMPROVER. Read the ENTIRE file $TEX_FILE and $BIB_FILE.

Here is the review report from the previous step:

--- BEGIN REVIEW ---
$REVIEW_OUTPUT
--- END REVIEW ---

$QUALITY_CRITERIA

Your task — address the TOP 2-3 issues from the PRIORITY FIXES list:

TASK CATEGORIES (in priority order):
(A) LOGICAL ERRORS: Fix derivation gaps, incorrect commutation claims, wrong eigenvalues, theorem misapplications. These are the most critical.
(B) RIGOR: Make imprecise statements precise. Add missing quantifiers, hypotheses, validity conditions.
(C) TODO COMPLETION: For red-marked TODOs that can be completed:
    - Complete the TODO content with rigorous mathematics
    - Keep the completed content in \\color{red}...\\color{black} so the author can review
    - If a TODO requires information you don't have, add a more specific TODO description
(D) CITATIONS: Add missing citations. Web-search for the paper first, verify it exists, then add the BibTeX entry to references.bib.
(E) MAIN TEXT OPTIMIZATION: Based on appendix content, improve the main text narrative. Make it more concise, add proper forward references, remove redundancy.
(F) NEW TODOs: If you discover issues that need the author's input, add \\textcolor{red}{[TODO: specific description]} at the relevant location.
(G) REDUNDANCY REMOVAL: Delete genuinely redundant text (not just move it).

EXECUTION RULES:
1. Fix at most 2-3 issues per iteration. Be thorough on each fix rather than superficial on many.
2. Do NOT restructure or heavily rewrite the appendix. Only fix errors and complete TODOs within existing structure.
3. For every edit, re-read the surrounding 10 lines to confirm no new inconsistencies are introduced.
4. If adding a new citation, web-search to find the correct BibTeX entry. Verify the paper title, authors, and year match.
5. When completing a TODO or fixing a derivation gap, FIRST read the relevant reference .qmd/.tex files listed in the system prompt. The detailed proofs and calculations are often already there.
6. When you encounter an unfamiliar identity, commutation relation, or technique, USE WEB SEARCH to verify it (e.g., search arXiv for the relevant paper).
7. Commit after fixing: git add $TEX_FILE $BIB_FILE && git commit -m 'polish: <concise summary>'
8. After committing, briefly summarize what was fixed and what remains."

  run_claude "Improve #$ITERATION" "$IMPROVE_PROMPT"
  rc=$?

  if [ "$rc" -eq 2 ]; then
    echo "  Budget exhausted during improve step. Sleeping 1 hour..."
    sleep 3600
    continue
  fi

  echo ""
  echo "  Iteration $ITERATION complete at $(date)"
  sleep "$PAUSE_BETWEEN"

  echo ""
  echo "  Starting next iteration..."
  echo "  (Press Ctrl+C to stop)"
done

echo ""
echo "============================================"
echo "  POLISH PAPER COMPLETE — $(date)"
echo "  Total iterations: $ITERATION"
echo "  Weekly calls used: $(count_weekly_calls)"
echo "============================================"

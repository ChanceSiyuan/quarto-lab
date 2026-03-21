#!/bin/bash
# review_logical_gaps.sh — 50-round cyclic review of main.tex
#
# Each round has TWO phases:
#   Phase A (diagnose): Diagnose logical gaps, consistency issues, and areas for improvement
#   Phase B (fix): Auto-fix the diagnosed issues; mark ALL changes in \textcolor{red}{...}
#
# Usage:
#   nohup ./_instructions/review_logical_gaps.sh > review_gaps.log 2>&1 &
#   ./_instructions/review_logical_gaps.sh --dry-run
#   ./_instructions/review_logical_gaps.sh --start-round=5
#   ./_instructions/review_logical_gaps.sh --cap=80
#
# Safety: create a git safety net BEFORE launching:
#   git add -A && git commit -m "baseline before cyclic review"
#   git checkout -b cyclic-review-$(date +%Y%m%d)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
REPO_ROOT="$(pwd)"

# ──────────────────────────── Config & args ───────────────────────
TEX_FILE="_resource/Project__Compatiablity_of_properties/main.tex"
BIB_FILE="_resource/Project__Compatiablity_of_properties/references.bib"
SDP_FILE="_resource/Project__Compatiablity_of_properties/solve_dual_sdp.py"

TOTAL_ROUNDS=50
MAX_RETRIES=30
START_ROUND=1

# Budget + progress tracking
OPUS_WEEKLY_CAP=50
OPUS_BUDGET_PERCENT=100
STATE_DIR="$REPO_ROOT/.review_state"
CALL_LOG="$STATE_DIR/opus_calls.log"
DIAG_DIR="$STATE_DIR/diagnostics"
PROGRESS_FILE="$STATE_DIR/round_progress"

source "$REPO_ROOT/_instructions/lib/claude_runner.sh"

TARGETS=()
parse_common_args TARGETS "$@"

mkdir -p "$STATE_DIR" "$DIAG_DIR"
touch "$CALL_LOG" "$PROGRESS_FILE"

# Section definitions: "START_LINE:END_LINE:TYPE:SECTION_NAME"
SECTIONS=(
  "155:167:main:Introduction"
  "168:193:main:Framework"
  "194:225:main:Tensor product structure and nonlinearity"
  "226:256:main:Nonlocal strategies and local no-go"
  "257:269:main:Discussion"
  "347:420:appendix:Review of compatibility"
  "421:680:appendix:Definition of f-incompatibility"
  "681:849:appendix:f-incompatibility program primal and dual"
  "850:949:appendix:Tensor product extension"
  "950:1122:appendix:Examples"
  "1123:1435:appendix:Multi-copy local estimation"
  "1436:1730:appendix:Multi-copy local shadows"
  "1731:2009:appendix:Lower bounds for nonlinear Pauli shadow"
)
NUM_SECTIONS=${#SECTIONS[@]}

# ──────────────────────────── Preamble ────────────────────────────

PREAMBLE="You are a senior quantum information theorist performing a rigorous review of a LaTeX paper on measurement compatibility and f-incompatibility.

WORKING FILES:
- Main tex: $REPO_ROOT/$TEX_FILE
- Bibliography: $REPO_ROOT/$BIB_FILE
- SDP solver: $REPO_ROOT/$SDP_FILE

REFERENCE MATERIALS:
- Quarto research notes:
  $REPO_ROOT/theory/Posts/compatibility/f-compatiability.qmd
  $REPO_ROOT/theory/Posts/compatibility/compatiablity.qmd
  $REPO_ROOT/theory/Posts/compatibility/multicopy_compatiability.qmd
  $REPO_ROOT/theory/Posts/compatibility/multi-copy_localshadow.qmd
  $REPO_ROOT/theory/Posts/compatibility/multicopy_estimation_framework.qmd
  $REPO_ROOT/theory/Posts/compatibility/nonparametric.qmd
- Shadow tomography notes:
  $REPO_ROOT/theory/Topics/Shadow_tomography/intro.qmd
  $REPO_ROOT/theory/Topics/Shadow_tomography/multicopy.qmd
- Background tex notes:
  $REPO_ROOT/_resource/Bilinear-Optimization-Dual-Problem-Derivation.md

HOW TO USE REFERENCES:
- When a derivation step seems unjustified, READ the relevant .qmd reference to check whether the full proof exists there.
- When you encounter an identity or claim you are unsure about, USE WEB SEARCH to verify it.

NOTATION (defined in the preamble):
\\tr = Tr, \\ox = \\otimes, \\1 = \\mathbbm{1}, \\ket, \\bra, \\proj, \\cF = \\mathcal{F}, \\cH = \\mathcal{H}, \\cA = \\mathcal{A}, \\cJ = \\mathcal{J}, \\cL = \\mathcal{L}, \\sym = sym

CRITICAL FORMATTING RULE FOR ALL EDITS:
- Wrap ALL modified/added text in \\textcolor{red}{...} so the author can see exactly what changed.
- For inline changes: replace 'old text' with '\\textcolor{red}{new text}'.
- For added sentences: \\textcolor{red}{New sentence here.}
- For equation fixes: wrap the changed part in \\textcolor{red}{...} inside the math environment.
- Do NOT remove existing \\color{red}...\\color{black} TODO markers.
- Do NOT wrap unchanged text in red.
- Grammar/typo fixes should also be in red so the author can review them."

# ──────────────────────────── Logic criteria ──────────────────────

LOGIC_CRITERIA='LOGICAL REVIEW CRITERIA — apply ALL to EVERY sentence:

--- Deductive validity ---
(D1) Every "therefore/thus/hence/it follows" must have explicit premises that logically entail the conclusion.
(D2) Every equation-to-equation step must be verifiable. Non-trivial identities must be cited or proved.
(D3) Quantifier scope: "for all rho" must hold for ALL rho, not just special cases.
(D4) Implication direction: "A implies B" is NOT "B implies A".

--- Proof structure ---
(P1) Each proof must establish what the theorem claims. Check conclusion matches statement.
(P2) Two-direction proofs (=> and <=) must both be complete.
(P3) Induction: base case + inductive step. Recursion: well-founded ordering.
(P4) Check for hidden assumptions not in theorem hypotheses.

--- Definitions and consistency ---
(C1) Every symbol defined before first use.
(C2) Definitions self-consistent.
(C3) Notation consistent: same symbol = same meaning.
(C4) Domain/range compatibility in every equation.

--- Quantum-specific ---
(Q1) Operator positivity claims verified.
(Q2) POVM completeness Sigma_j Pi_j = I verified.
(Q3) Trace identities verified, especially with symmetric embeddings.
(Q4) Tensor product dimensions match.
(Q5) Hermiticity of claimed-Hermitian operators verified.

--- Mathematical rigor ---
(M1) Limit exchanges (Sigma<->lim, Sigma<->tr) justified.
(M2) Convexity arguments: verify convexity.
(M3) SDP strong duality: Slater condition verified.
(M4) Polarization identity: span property verified.'

# ──────────────────────────── Main loop ───────────────────────────

echo "============================================"
echo "  CYCLIC REVIEW — $(date)"
echo "  File: $TEX_FILE"
echo "  Model: $MODEL | Dry-run: $DRY_RUN"
echo "  Total rounds: $TOTAL_ROUNDS (starting at $START_ROUND)"
echo "  Sections per cycle: $NUM_SECTIONS"
echo "  Weekly cap: $OPUS_WEEKLY_CAP | Budget: ${OPUS_BUDGET_PERCENT}%"
echo "============================================"

for (( round = START_ROUND; round <= TOTAL_ROUNDS; round++ )); do
  sec_idx=$(( (round - 1) % NUM_SECTIONS ))
  section_spec="${SECTIONS[$sec_idx]}"
  IFS=':' read -r sec_start sec_end sec_type sec_name <<< "$section_spec"

  echo ""
  echo "========================================================"
  echo "  ROUND $round / $TOTAL_ROUNDS"
  echo "  Section: $sec_name (lines $sec_start-$sec_end)"
  echo "  Type: $sec_type"
  echo "  $(date)"
  echo "========================================================"

  DIAG_FILE="$DIAG_DIR/round${round}_diagnose.md"

  # ── Phase A: Diagnose ─────────────────────────────────────────

  if ! is_round_phase_done "$round" "A"; then
    if ! check_budget; then
      echo "  Budget exhausted. Sleeping 1 hour..."
      sleep 3600
      continue
    fi

    echo ""
    echo "  -- Phase A: Diagnose --"

    if [ "$sec_type" = "appendix" ]; then
      DIAGNOSE_PROMPT="You are performing a DIAGNOSTIC PASS on an appendix section of a quantum information paper.

TARGET SECTION: '$sec_name' (lines $sec_start-$sec_end of $TEX_FILE).
Read the ENTIRE file for context, but ONLY diagnose lines $sec_start-$sec_end.

$LOGIC_CRITERIA

YOUR TASK: Go through lines $sec_start-$sec_end SENTENCE BY SENTENCE, EQUATION BY EQUATION. Produce a structured diagnostic report.

For EACH issue found, report:
---
ISSUE #N
Location: line ~XXX (quote the problematic text)
Category: [LOGICAL_GAP | UNJUSTIFIED_STEP | MISSING_HYPOTHESIS | QUANTIFIER_ERROR | DIMENSION_MISMATCH | CIRCULARITY | INCOMPLETE_PROOF | OVER_CLAIMING | SIGN_FACTOR_ERROR | IMPLICIT_ASSUMPTION | GRAMMAR | TYPO | CLARITY | NOTATION_INCONSISTENCY]
Severity: [CRITICAL | MAJOR | MINOR]
Description: What is wrong and why.
Suggested fix: Concrete proposed correction.
---

Also check for:
1. Grammar, spelling, and typographical errors
2. Unclear or ambiguous phrasing that could be improved
3. Missing cross-references or broken \\ref{} links
4. Notation inconsistencies with other sections
5. Redundant or overly verbose passages that could be tightened

EXECUTION:
1. READ the entire file first for context.
2. For each suspicious math step, TRY to verify it yourself (work out the algebra). Only flag if genuinely wrong or unjustified.
3. When unsure about an identity, READ the reference .qmd files or USE WEB SEARCH.
4. Be thorough but precise — no false positives.
5. Write the complete diagnostic report to: $DIAG_FILE
6. At the end, summarize: total issues found, breakdown by severity, the single most critical issue.
7. Do NOT edit the tex file in this phase."

    else
      DIAGNOSE_PROMPT="You are performing a DIAGNOSTIC PASS on a main text section of a PRL-style quantum information paper.

TARGET SECTION: '$sec_name' (lines $sec_start-$sec_end of $TEX_FILE).
Read the ENTIRE file (main text + appendix) for context, but ONLY diagnose lines $sec_start-$sec_end.

The appendix contains the full proofs (lines 339-2009). The main text (lines 155-269) is a concise PRL-style summary.

YOUR TASK: Evaluate the main text section for quality, accuracy, and alignment with the appendix. Report:

For EACH issue found:
---
ISSUE #N
Location: line ~XXX (quote the problematic text)
Category: [CLAIM_MISMATCH | MISSING_REFERENCE | WRONG_REFERENCE | UNCLEAR_STATEMENT | NOTATION_INCONSISTENCY | REDUNDANCY | MISSING_INTUITION | GRAMMAR | STYLE | QUANTITATIVE_ERROR]
Severity: [CRITICAL | MAJOR | MINOR]
Description: What is wrong and why.
Suggested fix: Concrete proposed correction.
---

Specifically check:
1. CLAIMS vs PROOFS: Does every main text claim accurately reflect its appendix proof? Verify theorem statements, conditions, and quantitative results.
2. REFERENCES: Do all \\ref{} point to the correct appendix label? Are theorem numbers correct?
3. NARRATIVE: Is the story clear and self-contained? Can a reader follow without the appendix?
4. CONCISENESS: PRL style demands every sentence earns its place. Flag redundancy.
5. INTUITION: Are key insights from appendix proofs reflected in the main text?
6. GRAMMAR & STYLE: Fix-worthy grammar, clarity, or style issues.

EXECUTION:
1. READ the entire file, especially the appendix sections that this main text section references.
2. Cross-check every claim against the appendix.
3. Write the complete diagnostic report to: $DIAG_FILE
4. Summarize at the end.
5. Do NOT edit the tex file in this phase."
    fi

    run_claude "Round $round Phase A: Diagnose $sec_name" "$DIAGNOSE_PROMPT" "$PREAMBLE"
    rc=$?

    if [ "$rc" -eq 2 ]; then
      echo "  Budget exhausted. Sleeping 1 hour..."
      sleep 3600
      continue
    fi

    mark_round_phase_done "$round" "A"
    sleep "$PAUSE_BETWEEN"
  else
    echo "  [SKIP] Round $round Phase A — already done."
  fi

  # ── Phase B: Fix ──────────────────────────────────────────────

  if ! is_round_phase_done "$round" "B"; then
    if ! check_budget; then
      echo "  Budget exhausted. Sleeping 1 hour..."
      sleep 3600
      continue
    fi

    echo ""
    echo "  -- Phase B: Fix --"

    if [ "$sec_type" = "appendix" ]; then
      FIX_PROMPT="You are implementing fixes for diagnosed issues in an appendix section of a quantum information paper.

TARGET SECTION: '$sec_name' (lines $sec_start-$sec_end of $TEX_FILE).
DIAGNOSTIC REPORT: Read the file $DIAG_FILE for the list of issues diagnosed in Phase A.

YOUR TASK: For EACH issue in the diagnostic report, implement a fix directly in the tex file.

=== RULES FOR FIXING ===

1. LOGICAL GAPS — Add the missing justification step. Wrap added text in \\textcolor{red}{...}:
   Example: After 'This implies X.' add '\\textcolor{red}{This follows because [full justification].}'
   If the gap requires a new equation, add it wrapped in red.

2. UNJUSTIFIED STEPS — Add explicit derivation or citation. Wrap in \\textcolor{red}{...}.

3. SIGN/FACTOR ERRORS — Correct the equation. Wrap the corrected part in \\textcolor{red}{...}.

4. MISSING HYPOTHESES — Add the missing condition to the theorem statement. Wrap in \\textcolor{red}{...}.

5. GRAMMAR/TYPO — Fix in place, wrapped in \\textcolor{red}{...} (even small fixes, so author can review).

6. CLARITY — Rewrite unclear passages for better readability. Wrap in \\textcolor{red}{...}.

7. NOTATION — Fix inconsistencies. Wrap in \\textcolor{red}{...}.

=== FORMATTING ===

- Use \\textcolor{red}{...} for ALL changes (not \\color{red}...\\color{black}).
  Exception: preserve existing \\color{red}...\\color{black} TODO markers as-is.
- For multi-line additions, wrap each logical unit in its own \\textcolor{red}{...}.
- Inside math environments, use \\textcolor{red}{...} around the changed subexpression.
- Do NOT restructure paragraphs or rewrite entire proofs. Make surgical, targeted fixes.
- Do NOT remove any existing content unless replacing it with a correction.

=== EXECUTION ===
1. READ the diagnostic report ($DIAG_FILE) first.
2. READ the tex file, focusing on lines $sec_start-$sec_end.
3. For each diagnosed issue (sorted by severity: CRITICAL first):
   a. Verify the issue is real (re-check the math yourself).
   b. If confirmed, implement the fix.
   c. If you disagree with the diagnosis, skip it and note why.
4. After all fixes, output a SUMMARY:
   - Issues fixed (count, by category)
   - Issues skipped (with reasons)
   - Any new issues discovered during fixing
5. Do NOT commit — the script handles commits."

    else
      FIX_PROMPT="You are implementing improvements to a main text section of a PRL-style quantum information paper.

TARGET SECTION: '$sec_name' (lines $sec_start-$sec_end of $TEX_FILE).
DIAGNOSTIC REPORT: Read the file $DIAG_FILE for the list of issues diagnosed in Phase A.

The appendix (lines 339-2009) is the source of truth for all claims.

YOUR TASK: For EACH issue in the diagnostic report, improve the main text.

=== RULES FOR IMPROVING ===

1. CLAIM MISMATCHES — Revise the main text to match the appendix (appendix is source of truth). Wrap changes in \\textcolor{red}{...}.

2. WRONG/MISSING REFERENCES — Fix \\ref{} links. Wrap in \\textcolor{red}{...}.

3. UNCLEAR STATEMENTS — Rewrite for clarity while maintaining PRL conciseness. Wrap in \\textcolor{red}{...}.

4. MISSING INTUITION — Add a brief intuitive explanation from the appendix proof. Wrap in \\textcolor{red}{...}.

5. REDUNDANCY — Tighten the prose (PRL: every word counts). Wrap changed text in \\textcolor{red}{...}.

6. QUANTITATIVE ERRORS — Correct numbers/scaling. Wrap in \\textcolor{red}{...}.

7. GRAMMAR/STYLE — Fix in place. Wrap in \\textcolor{red}{...}.

=== FORMATTING ===

- Use \\textcolor{red}{...} for ALL modifications.
  Exception: preserve existing \\color{red}...\\color{black} markers.
- Make surgical edits. Do NOT rewrite the entire section from scratch.
- Maintain PRL style: \\prlsection{}, \\prlsubsection{}, concise prose.
- If adding text, it must earn its place — no padding.

=== EXECUTION ===
1. READ the diagnostic report ($DIAG_FILE).
2. READ the full tex file, cross-referencing with the appendix.
3. Implement fixes by severity (CRITICAL first).
4. Output a SUMMARY of changes made and issues skipped.
5. Do NOT commit."
    fi

    run_claude "Round $round Phase B: Fix $sec_name" "$FIX_PROMPT" "$PREAMBLE"
    rc=$?

    if [ "$rc" -eq 2 ]; then
      echo "  Budget exhausted. Sleeping 1 hour..."
      sleep 3600
      continue
    fi

    mark_round_phase_done "$round" "B"
    sleep "$PAUSE_BETWEEN"
  else
    echo "  [SKIP] Round $round Phase B — already done."
  fi

  # ── Commit after each round ──────────────────────────────────

  if ! $DRY_RUN; then
    cd "$REPO_ROOT"
    if git diff --quiet "$TEX_FILE" 2>/dev/null; then
      echo "  No changes to commit after round $round."
    else
      git add "$TEX_FILE"
      git commit -m "review(round $round/$TOTAL_ROUNDS): [$sec_type] $sec_name — diagnosed and fixed"
      echo "  Round $round committed."
    fi
  fi

  echo ""
  echo "  Round $round complete. Weekly calls used: $(count_weekly_calls)"
  echo ""

done

# ── Final summary ──────────────────────────────────────────────

echo ""
echo "========================================================"
echo "  ALL $TOTAL_ROUNDS ROUNDS COMPLETE"
echo "  $(date)"
echo "  Weekly calls used: $(count_weekly_calls)"
echo "========================================================"
echo ""
echo "Diagnostic reports saved in: $DIAG_DIR/"
echo "Use 'git log --oneline' to see all review commits."
echo ""
echo "To accept all red changes, run:"
echo "  sed -i 's/\\\\textcolor{red}{\\([^}]*\\)}/\\1/g' $TEX_FILE"
echo "To reject all red changes, run:"
echo "  sed -i 's/\\\\textcolor{red}{[^}]*}//g' $TEX_FILE"

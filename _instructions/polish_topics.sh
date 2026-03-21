#!/bin/bash
# polish_topics.sh — Overnight iterative quality-improvement loop for Topic folders
#
# Runs a REVIEW -> IMPROVE cycle on one or more Topic folders.
#
# Usage:
#   nohup ./_instructions/polish_topics.sh theory/Topics/Shadow_tomography > polish.log 2>&1 &
#   nohup ./_instructions/polish_topics.sh > polish.log 2>&1 &     # all Topics
#   ./_instructions/polish_topics.sh --dry-run theory/Topics/IQP
#
# Safety: create a git safety net BEFORE launching:
#   git add -A && git commit -m "baseline before overnight polish"
#   git checkout -b polish-$(date +%Y%m%d)

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
REPO_ROOT="$(pwd)"

# ──────────────────────────── Config & args ───────────────────────
MAX_ITERATIONS=30

source "$REPO_ROOT/_instructions/lib/claude_runner.sh"

TARGETS=()
parse_common_args TARGETS "$@"

# If no targets, discover all Topic folders with >=2 .qmd files
if [ ${#TARGETS[@]} -eq 0 ]; then
  while IFS= read -r dir; do
    count=$(find "$dir" -maxdepth 1 -name '*.qmd' | wc -l)
    [ "$count" -ge 2 ] && TARGETS+=("$dir")
  done < <(find theory/Topics -mindepth 1 -maxdepth 1 -type d | sort)
fi

echo "============================================"
echo "  POLISH TOPICS — $(date)"
echo "  Targets: ${TARGETS[*]}"
echo "  Model: $MODEL | Dry-run: $DRY_RUN"
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

GROUND RULES (never violate):
1. ONLY cite papers already in the bibliography file. $bib_note If you need a new ref, web-search for the paper, verify it exists, add its BibTeX, then cite it. NEVER fabricate a citation.
2. Do NOT rewrite, delete, reorganize, or rephrase existing text. You may ONLY: append new sections, fill in placeholders marked (t.b.c.) or (todo) or <!-- TODO -->, and fix factual/mathematical errors in-place.
3. After finishing, commit with: git add <files> && git commit -m "<type>: <file> — <summary>"
4. Theorem statements must be precise and correct. Proofs: short sketches (key idea in ≤10 lines) + citation. No full algebraic derivations.
5. Reader = quantum-computing PhD student. They know the basics. No undergraduate explanations. Get to the physics/math.
6. If stuck on anything for >3 minutes, add <!-- TODO: ... --> and move on.
7. All files use lang: en. Math: \$...\$ inline, \$\$...\$\$ display. Citations: [@key]. Theorems: :::{#thm-name .callout-important icon="false"}. Proofs: :::{.callout-note collapse="true"}.
PREAMBLE
}

QUALITY_CRITERIA='Quality criteria for each sub-page:

--- Structural completeness ---
(Q1) Has a clear introductory paragraph (2-5 sentences) stating the topic, its significance, and what the page covers.
(Q2) Core technical sections are present (Hamiltonian / formalism / definitions, key results, references to literature). No section is merely a stub.
(Q3) Important results are in theorem/lemma callout boxes with proof sketches when appropriate.
(Q4) If applicable, an "Experiment overview" or "Key results" section organized by research group/paper with concrete numbers (qubit counts, fidelities, exponents, etc.).
(Q5) If applicable, an "Open problems" section with 3-6 concrete, actionable bullets.

--- Factual & citation integrity ---
(Q6) All [@citekey] citations resolve against the bibliography file. No <!-- TODO --> markers remain.
(Q7) Content is detailed enough that a reader can extract specific quantities without consulting the original paper.
(Q8) No sections are suspiciously short (< 5 lines) compared to sibling sections in the same file.

--- Readability & logical coherence (read LINE BY LINE) ---
(Q9)  Every derivation step follows logically from the previous one. No hidden leaps: if the text says "therefore" or "it follows that", the conclusion must actually follow. Flag any gap where a reader would ask "how did we get here?".
(Q10) Notation is consistent WITHIN and ACROSS files. The same symbol must mean the same thing everywhere. Flag every inconsistency with exact conflicting definitions.
(Q11) Physical/mathematical reasoning is self-consistent. Symmetries match claimed phases; perturbative regimes are valid; approximation conditions are stated. Flag any contradiction.
(Q12) Theoretical completeness: key derivations have all essential steps present; approximations are stated with validity conditions; a reader could reconstruct the argument using ONLY what is written. Flag where adding 2-5 sentences would significantly improve understanding.'

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
    BIB_INSTRUCTION=""
    [ -n "$BIB" ] && BIB_INSTRUCTION="and $BIB"

    echo ""
    echo "============================================"
    echo "  ITERATION $ITERATION — REVIEW: $WORKDIR"
    echo "  $(date)"
    echo "============================================"

    # ── Step A: Review ──────────────────────────────────────────

    REVIEW_PROMPT="You are a CRITICAL REVIEWER performing a deep, line-by-line audit.

STEP 1: Read ALL .qmd files in $WORKDIR/ $BIB_INSTRUCTION — every line, no skimming.

STEP 2: For each sub-page file, perform TWO passes:

  PASS 1 — Structural checklist (Q1-Q8): does each required section exist and have sufficient depth?
  PASS 2 — Line-by-line coherence audit (Q9-Q12): read every sentence and check:
    - Does this sentence follow logically from the previous one?
    - Is notation consistent within and across files?
    - Do claimed properties follow from the stated formalism?
    - Are approximation validity regimes stated?
    - Could a careful reader reconstruct the argument without opening cited papers?

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
    run_claude "Review $WORKDIR (#$ITERATION)" "$REVIEW_PROMPT" "$PREAMBLE" REVIEW_OUTPUT || continue

    # Check if all files pass
    if echo "$REVIEW_OUTPUT" | grep -q "ALL PASS" && ! echo "$REVIEW_OUTPUT" | grep -q "^FAIL:"; then
      echo ""
      echo "  ALL FILES IN $WORKDIR PASS at iteration $ITERATION"
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

    IMPROVE_PROMPT="You are an IMPROVER. Read ALL .qmd files in $WORKDIR/ $BIB_INSTRUCTION.

Here is the review report from the previous step:

--- BEGIN REVIEW ---
$REVIEW_OUTPUT
--- END REVIEW ---

$QUALITY_CRITERIA

Your task:
1. Read the review report carefully. Pay special attention to Q9-Q12 failures — these are coherence and theory issues that undermine credibility.
2. Identify the single HIGHEST-IMPACT deficiency across all files. Priority order:
   (a) Q11/Q12 — physical/mathematical inconsistencies or incomplete theory
   (b) Q9/Q10 — logical gaps or notation inconsistencies
   (c) PRIORITY FIX annotations from the reviewer
   (d) Other Q1-Q8 structural issues
3. Fix ONLY that one deficiency by editing the relevant file:
   - Re-derive any problematic step to verify correctness before writing.
   - State approximations explicitly with validity conditions.
   - Ensure the fix is self-consistent with the rest of the file and across files.
   - If a derivation gap needs filling, write the missing steps concisely.
4. Do NOT rewrite or reorganize existing text — only append, correct errors, or fill placeholders.
5. If the fix requires new references, web-search, verify, add to the bibliography.
6. After fixing, re-read the edited section in context (5 lines before and after) to confirm no NEW inconsistencies.
7. Commit with: git add <files> && git commit -m 'polish: <file> — <what was fixed>'

Focus on ONE fix per iteration. Be thorough on that one fix rather than superficial on many."

    run_claude "Improve $WORKDIR (#$ITERATION)" "$IMPROVE_PROMPT" "$PREAMBLE"

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

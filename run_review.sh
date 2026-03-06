#!/bin/bash
# run_review.sh — Fire-and-forget review expansion via Claude Code CLI
#
# Usage:
#   chmod +x run_review.sh
#   nohup ./run_review.sh > review_expansion.log 2>&1 &
#
# Safety: run git safety net BEFORE launching:
#   git add -A && git commit -m "baseline before AI review expansion"
#   git tag review-baseline
#   git checkout -b review-expansion

set -euo pipefail
cd "$(dirname "$0")"

WORKDIR="theory/Topics/simulation_model"

PREAMBLE='You are working in the directory theory/Topics/simulation_model/ of a Quarto website at '"$(pwd)"'.

GROUND RULES (never violate):
1. ONLY cite papers already in refs.bib. Read refs.bib first. If you need a new ref, web-search for the paper, verify it exists, add its BibTeX to refs.bib, then cite it. NEVER fabricate a citation.
2. For existing files (index.qmd, TFIM.qmd, ferm_Hubbard.qmd, Boson-Hubbard.qmd, honeycomb.qmd, puccd.qmd, Effective_ham.qmd): ONLY append new sections or fill in placeholders. Do NOT rewrite, delete, reorganize, or rephrase existing text.
3. After finishing, commit with: git add <files> && git commit -m "<type>: <file> — <summary>"
4. Theorem statements must be precise and correct. Proofs: short sketches (key idea in ≤10 lines) + citation to source. No full algebraic derivations for new content.
5. Reader = quantum computing experimentalist. They know Rydberg blockade, tweezers, 2nd quantization, basic QI. No undergraduate explanations. Get to the physics.
6. If stuck on anything for >3 minutes, add <!-- TODO: ... --> and move on.
7. All files use lang: en. Math: $...$ inline, $$...$$ display. Citations: [@key]. Theorems: :::{#thm-name .callout-important icon="false"}. Proofs: :::{.callout-note collapse="true"}.
'

MAX_RETRIES=20
RETRY_WAIT=300  # 5 minutes between retries on rate limit

run_claude() {
  local desc="$1"
  local prompt="$2"
  local attempt=1

  while [ $attempt -le $MAX_RETRIES ]; do
    echo ""
    echo "============================================"
    echo "  STARTING: $desc (attempt $attempt/$MAX_RETRIES)"
    echo "  $(date)"
    echo "============================================"
    echo ""

    local output
    output=$(claude -p \
      --dangerously-skip-permissions \
      --model opus \
      --append-system-prompt "$PREAMBLE" \
      "$prompt" 2>&1) && {
      echo "$output"
      echo ""
      echo "  FINISHED: $desc at $(date)"
      echo "============================================"
      sleep 5
      return 0
    }

    # Check if it was a rate limit error
    if echo "$output" | grep -qi "limit\|rate\|quota\|resets\|throttl\|overloaded"; then
      echo "$output"
      echo ""
      echo "  RATE LIMITED: $desc — waiting ${RETRY_WAIT}s before retry (attempt $attempt/$MAX_RETRIES)"
      echo "  $(date)"
      sleep $RETRY_WAIT
      attempt=$((attempt + 1))
    else
      # Non-rate-limit error — print and move on
      echo "$output"
      echo ""
      echo "  ERROR (non-rate-limit): $desc — skipping."
      echo "  $(date)"
      echo "============================================"
      sleep 5
      return 1
    fi
  done

  echo "  GAVE UP after $MAX_RETRIES retries: $desc"
  echo "============================================"
  return 1
}

# ─────────────────────────────────────────────────────────────────
# Phase 2: Enhance index.qmd
# ─────────────────────────────────────────────────────────────────

run_claude "Phase 2 — index.qmd" \
"Read ALL files in $WORKDIR/ (every .qmd file and refs.bib in full).

Then APPEND to $WORKDIR/index.qmd (insert before the final refs block at the end):

1. A notation callout (insert right after the existing '# Overview' section) defining: Ω (Rabi frequency), Δ (laser detuning), n_i = |r_i⟩⟨r_i| (Rydberg projector), C_6 (van der Waals coefficient, V = C_6/R^6), C_3 (dipolar coefficient, V = C_3/R^3), R_b = (C_6/Ω)^{1/6} (blockade radius).

2. For each model section in index.qmd that currently has only a Hamiltonian + 1-2 sentences, append 3-5 sentences covering: largest system demonstrated, key open problem, next milestone. Use only refs from refs.bib.

3. A new section '# Research Groups {#sec-groups}' with a Markdown table:
   | Group | Location | Species | Max \$N\$ | Key analog results |
   Fill this from information in the existing .qmd files and refs.bib. Include at minimum: Lukin (Harvard), Browaeys/Lahaye (IOGS Palaiseau), Bloch/Gross/Zeiher (MPQ Munich), Ahn (KAIST), Bakr (Princeton), Lin Li (HUST), QuEra, PASQAL.

4. A new section '# Experiment Timeline {#sec-timeline}' with a chronological Markdown table covering ALL analog Rydberg experiments referenced across the entire review. Columns: Year | Group | \$N\$ | Model | Key result | Ref.

5. For 6 new sub-pages to be created later, add 'See the [detailed notes](filename.qmd).' links in the corresponding model sections:
   - XY/XXZ section → XY_XXZ.qmd
   - Density wave section → density_wave.qmd
   - Topological sections (QSL, SPT, Haldane) → topological.qmd
   - LGT sections (U(1), Z2, dimer) → LGT.qmd
   - Dynamical sections (PXP/scars, DTC, coarsening) → dynamics.qmd
   - Optimization section (MIS) → optimization.qmd

Commit: git add $WORKDIR/index.qmd && git commit -m 'append: index.qmd — notation, status blurbs, groups table, timeline, links'"

# ─────────────────────────────────────────────────────────────────
# Phase 3: Create new sub-pages (one session per file)
# ─────────────────────────────────────────────────────────────────

run_claude "Phase 3.1 — XY_XXZ.qmd" \
"Read $WORKDIR/index.qmd and $WORKDIR/refs.bib in full to understand context.

Create the file $WORKDIR/XY_XXZ.qmd about: Dipolar XY model, XXZ Heisenberg, spin squeezing, magnon spectroscopy.

Use this structure:
---
title: 'Dipolar XY and XXZ Models'
date: '2026-03-05'
categories: [Readings]
bibliography: refs.bib
lang: en
---

[← Back to Index](index.qmd)

# Dipolar XY and XXZ Models

<2-3 sentences: resonant dipole-dipole flip-flop between two Rydberg states realizes XY exchange with 1/r^3 coupling; microwave/dressing engineering extends to XXZ; important for quantum magnetism, metrological squeezing, and transport.>

## Hamiltonian & Rydberg mapping

<XY Hamiltonian and XXZ Hamiltonian. Which atomic states (e.g. nS, nP) encode spin-1/2. How dipolar C3 exchange gives XY, how microwave coupling or Rydberg dressing adds Ising anisotropy for XXZ. Parameter regime table mapping Rydberg quantities to model parameters.>

## Key phenomena

<Spin squeezing below SQL, magnon dispersion relation, tunable anisotropy from XY through Heisenberg to Ising, floating phase with incommensurate order. Use theorem/callout boxes for key theoretical results with proof sketch style.>

## Experiment overview

<Organize by research group. For each experiment:
**Author et al. (Year)** [@citekey] — *N atoms, geometry.* One-sentence key result. One sentence on what is new vs prior.

Key refs to cover: bornet2023scalable, chen2025spectroscopy, scholl2022microwave, chen2024anisotropic, chen2025floating. Also check refs.bib for any other XY/XXZ refs.

End with a summary comparison table:
| Year | Group | Ref | \$N\$ | Dim | Key physics | What is new |>

## Open problems

<3-6 concrete bullet points about what has not been done yet, citing theory proposals from refs.bib where available.>

## References
::: {#refs}
:::

If you need new references not in refs.bib, web-search to find them, verify they exist, add BibTeX to refs.bib.
Commit: git add $WORKDIR/XY_XXZ.qmd $WORKDIR/refs.bib && git commit -m 'create: XY_XXZ.qmd — dipolar XY/XXZ review'"

run_claude "Phase 3.2 — topological.qmd" \
"Read $WORKDIR/index.qmd and $WORKDIR/refs.bib in full.

Create $WORKDIR/topological.qmd about: Topological phases realized in Rydberg arrays — quantum spin liquid / toric code on ruby lattice, symmetry-protected topological phase / bosonic SSH, Haldane phase in spin-1 chains.

Same overall structure as described for XY_XXZ.qmd (YAML header, back-link, intro, Hamiltonian & mapping, key phenomena, experiment overview by group with summary table, open problems, refs block).

Key refs: semeghini2021probing, verresen2021prediction, deleseleuc2019observation, fromonteil2025haldane, kornjaca2023trimer, zhang2022density. Check refs.bib for others.

Cover: ruby-lattice blockade → quantum dimer model → toric code mapping; alternating tweezer spacing → bosonic SSH with dipolar hopping; three Rydberg levels near Förster resonance → spin-1 Heisenberg → Haldane phase; trimer spin liquid on honeycomb.

If you need new refs, web-search, verify, add to refs.bib.
Commit: git add $WORKDIR/topological.qmd $WORKDIR/refs.bib && git commit -m 'create: topological.qmd — topological phases review'"

run_claude "Phase 3.3 — LGT.qmd" \
"Read $WORKDIR/index.qmd and $WORKDIR/refs.bib in full.

Create $WORKDIR/LGT.qmd about: Lattice gauge theories — U(1) Schwinger model, Z₂ lattice gauge theory, string breaking, quantum dimer models.

Same structure (YAML, back-link, intro, Hamiltonian & mapping, key phenomena, experiment overview by group with table, open problems, refs).

Key refs: surace2020lattice, observation2025string, homeier2023z2, geier2023floquet, samajdar2020quantum, dimer2025gadgets, zhou2022thermalization, wang2023interrelated. Check refs.bib for others.

Cover: how PXP blockade constraint in 1D enforces Gauss's law and maps to Schwinger model; domain walls as charged particles; 2D kagome for (2+1)D U(1) and string breaking; Floquet-driven Z₂ on ladders; Rydberg gadgets (auxiliary atoms) transforming blockade into general dimer constraints for Rokhsar-Kivelson Hamiltonian. Also mention cold-atom optical lattice LGT experiments (zhou2022thermalization, wang2023interrelated) for comparison.

If you need new refs, web-search, verify, add to refs.bib.
Commit: git add $WORKDIR/LGT.qmd $WORKDIR/refs.bib && git commit -m 'create: LGT.qmd — lattice gauge theory review'"

run_claude "Phase 3.4 — density_wave.qmd" \
"Read $WORKDIR/index.qmd and $WORKDIR/refs.bib in full.

Create $WORKDIR/density_wave.qmd about: Commensurate density-wave ordered phases (devil's staircase), Z₂/Z₃/Z₄/star/striped order, quantum floating phase, Kibble-Zurek dynamics.

Same structure (YAML, back-link, intro, Hamiltonian & mapping, key phenomena, experiment overview by group with table, open problems, refs).

Key refs: ebadi2021quantum, keesling2019quantum, chen2025floating, scholl2021quantum, bernien2017probing. Check refs.bib for others.

Cover: how tuning Δ/Ω and R_b/a in the TFIM Hamiltonian selects different commensurate fillings forming a devil's staircase; the cascade of Z₂ → Z₃ → Z₄ → star/striped on various 2D lattices; the incommensurate floating phase with quasi-long-range order observed on ladder arrays; quantum Kibble-Zurek mechanism and critical exponent measurements during slow sweeps through QPTs.

If you need new refs, web-search, verify, add to refs.bib.
Commit: git add $WORKDIR/density_wave.qmd $WORKDIR/refs.bib && git commit -m 'create: density_wave.qmd — density wave phases review'"

run_claude "Phase 3.5 — dynamics.qmd" \
"Read $WORKDIR/index.qmd and $WORKDIR/refs.bib in full.

Create $WORKDIR/dynamics.qmd about: Dynamical phenomena — PXP model / quantum many-body scars, discrete time crystals, quantum coarsening / Higgs mode, information scrambling and OTOCs.

Same structure (YAML, back-link, intro, Hamiltonian & mapping, key phenomena, experiment overview by group with table, open problems, refs).

Key refs: bernien2017probing, bluvstein2021controlling, bluvstein2025quantum, kongkhambut2024higher, chen2024collapse, zhang2025anomalous, maskara2025emergent. Check refs.bib for others.

Cover: PXP Hamiltonian as strong-blockade limit, scar tower and anomalous revivals from Néel state; Floquet stabilization of scars → discrete time crystal with subharmonic response; higher-order n-DTCs with Cs EIT scheme; curvature-driven quantum coarsening of AF domains after crossing QPT, amplitude (Higgs) mode oscillations; OTOC collapse-revival patterns in Rydberg chains, anomalous scrambling from scar-induced periodicity; emergent disorder from position noise causing sub-ballistic dynamics.

If you need new refs, web-search, verify, add to refs.bib.
Commit: git add $WORKDIR/dynamics.qmd $WORKDIR/refs.bib && git commit -m 'create: dynamics.qmd — dynamical phenomena review'"

run_claude "Phase 3.6 — optimization.qmd" \
"Read $WORKDIR/index.qmd and $WORKDIR/refs.bib in full.

Create $WORKDIR/optimization.qmd about: Optimization — maximum independent set (MIS) on unit-disk graphs, quantum speedup claims, variational algorithms, 3D graph embeddings.

Same structure (YAML, back-link, intro, Hamiltonian & mapping, key phenomena, experiment overview by group with table, open problems, refs).

Key refs: ebadi2022quantum, song2021quantum, kim2022finding. Check refs.bib for others.

Cover: exact equivalence between blockade Hamiltonian and MIS on unit-disk graphs; hardness controlled by solution degeneracy and local minima density; observed superlinear quantum speedup on hardest instances up to 289 qubits; 3D Rydberg arrays enabling non-planar graph embeddings (Cayley trees, Platonic solids); variational quantum algorithms for MIS.

If you need new refs, web-search, verify, add to refs.bib.
Commit: git add $WORKDIR/optimization.qmd $WORKDIR/refs.bib && git commit -m 'create: optimization.qmd — optimization review'"

# ─────────────────────────────────────────────────────────────────
# Phase 4: Expand existing sub-pages
# ─────────────────────────────────────────────────────────────────

run_claude "Phase 4.1 — Boson-Hubbard.qmd" \
"Read $WORKDIR/Boson-Hubbard.qmd and $WORKDIR/refs.bib in full.

APPEND to the end of $WORKDIR/Boson-Hubbard.qmd (do NOT modify any existing text):

1. A new section '## Experiment overview' covering the experimental realization of the bosonic t-J-V model. Cover qiao2025 and qiao2025doped (bosonic antiferromagnet and doped quantum antiferromagnet on Sr-87 / Rb-87 tweezer arrays, Gross group at MPQ, Browaeys group). Organize by group with a summary comparison table.

2. A new section '## Open problems' with 3-5 concrete bullets: fermionic vs bosonic hole statistics and when the difference matters; scaling to larger systems; connection to cuprate superconductivity; accessing d-wave pairing regime.

Commit: git add $WORKDIR/Boson-Hubbard.qmd && git commit -m 'append: Boson-Hubbard.qmd — experiments and open problems'"

run_claude "Phase 4.2 — honeycomb.qmd" \
"Read $WORKDIR/honeycomb.qmd and $WORKDIR/refs.bib.

APPEND to the end of $WORKDIR/honeycomb.qmd (do NOT modify existing text):

A new section '## Open problems' with 4-6 concrete bullets about: realizing pure Kitaev interactions in analog (vs needing Floquet/digital); demonstrating non-Abelian anyon braiding; scaling to larger system sizes for robust topological gap; comparing analog vs digital approaches (Evered 2025 digital result vs analog proposals); measuring topological entanglement entropy experimentally.

Commit: git add $WORKDIR/honeycomb.qmd && git commit -m 'append: honeycomb.qmd — open problems'"

run_claude "Phase 4.3 — puccd.qmd" \
"Read $WORKDIR/puccd.qmd and $WORKDIR/refs.bib.

APPEND to the end of $WORKDIR/puccd.qmd (do NOT modify existing text):

1. A new section '## Experiment status' — Has any neutral-atom pUCCD experiment been demonstrated as of early 2026? If not (which is likely), state this clearly and describe what experimental capabilities would be needed (coherent transport fidelity, CZ gate fidelity, number of qubits, measurement scheme).

2. A new section '## Open problems' with 3-5 bullets: scaling beyond small molecules; comparison with VQE on superconducting/ion platforms; error budget analysis (transport vs gate vs readout); extension beyond seniority-zero; integration with virtual distillation error mitigation.

Commit: git add $WORKDIR/puccd.qmd && git commit -m 'append: puccd.qmd — experiment status and open problems'"

run_claude "Phase 4.4 — ferm_Hubbard.qmd" \
"Read $WORKDIR/ferm_Hubbard.qmd in full.

Find the placeholder text '(t.b.c.)' near line 496 (in the section about QPU error / adiabatic preparation error). Replace ONLY that placeholder with 5-10 sentences explaining how to quantify the adiabatic state preparation error for the transverse-field Ising ground state on the Rydberg QPU. Cover: adiabatic theorem and gap condition, quasi-adiabatic sweep protocol, diabatic excitation probability scaling, fidelity witnesses from measurable quantities, and how this error composes with the mean-field error. Cite relevant refs from refs.bib.

Do NOT modify any other part of the file.

Commit: git add $WORKDIR/ferm_Hubbard.qmd && git commit -m 'append: ferm_Hubbard.qmd — fill QPU error tbc placeholder'"

run_claude "Phase 4.5 — TFIM.qmd" \
"Read $WORKDIR/TFIM.qmd and $WORKDIR/refs.bib.

APPEND to the end of $WORKDIR/TFIM.qmd (do NOT modify existing text):

A new section '## Open problems' with 5-7 concrete bullets about: precise critical exponent measurement in 2D; finite-temperature crossover vs QPT; scaling coherent simulation beyond 300 atoms; role of long-range 1/r^6 tail vs ideal NN Ising; entanglement witnesses and entanglement entropy measurement; disorder effects from position fluctuations (cf. maskara2025emergent); accessing dynamical structure factor in the critical regime.

Commit: git add $WORKDIR/TFIM.qmd && git commit -m 'append: TFIM.qmd — open problems'"

# ─────────────────────────────────────────────────────────────────
# Phase 5: Consistency check (one-time)
# ─────────────────────────────────────────────────────────────────

run_claude "Phase 5 — consistency check" \
"Read ALL .qmd files in $WORKDIR/ and refs.bib.

Perform these checks and fix any issues:

1. Every model section in index.qmd must have a working link to a sub-page. Verify all links point to files that exist. Fix any broken links.

2. Every sub-page must have '[← Back to Index](index.qmd)' near the top. Add it if missing.

3. Check refs.bib for duplicate keys (same key appearing in two @article entries). Remove duplicates if found.

4. Check that every sub-page has 'bibliography: refs.bib' in its YAML header.

5. Fix any issues found and commit:
   git add $WORKDIR/ && git commit -m 'fix: cross-references, links, and consistency' || echo 'Nothing to fix'

6. Then try to render: cd $(pwd) && quarto render $WORKDIR/index.qmd 2>&1 || echo 'Render had warnings/errors — check log'
   If there are fixable errors (broken citations, syntax issues), fix them and commit:
   git add $WORKDIR/ && git commit -m 'fix: quarto render errors' || echo 'Nothing to fix'"

echo ""
echo "============================================"
echo "  PHASES 2-5 COMPLETE — $(date)"
echo "  Entering Phase 6: iterative quality improvement loop"
echo "  This will run INDEFINITELY until you Ctrl+C"
echo "============================================"

# ─────────────────────────────────────────────────────────────────
# Phase 6: Iterative quality improvement (runs forever until killed)
#
# Each iteration:
#   Step A — REVIEW: read all files, produce a critique listing deficiencies
#   Step B — IMPROVE: pick the most impactful deficiency and fix it
# ─────────────────────────────────────────────────────────────────

QUALITY_CRITERIA='Quality criteria for each sub-page:

--- Structural completeness ---
(Q1) Has a 2-3 sentence intro stating which model, which Rydberg mechanism, and why it matters.
(Q2) "Hamiltonian & Rydberg mapping" section with explicit Hamiltonian, parameter identification, and a parameter regime table.
(Q3) "Key phenomena" section with phase diagram highlights, key observables, and classical simulation barriers. Important results in theorem callout boxes with proof sketch.
(Q4) "Experiment overview" organized by research group, each entry has: year, group, N atoms, geometry, species, key result, what is new. Ends with a summary comparison table.
(Q5) "Open problems" with 3-6 concrete, actionable bullets citing proposals from refs.bib.

--- Factual & citation integrity ---
(Q6) All citations resolve against refs.bib. No <!-- TODO --> markers remain.
(Q7) Content is detailed enough that an experimentalist can extract specific numbers (atom counts, fidelities, critical exponents) without consulting the original paper.
(Q8) No sections are suspiciously short (< 5 lines) compared to sibling sections in the same file.

--- Readability & logical coherence (CRITICAL — read LINE BY LINE) ---
(Q9)  Every derivation step follows logically from the previous one. No hidden leaps: if the text says "therefore" or "it follows that", check that the conclusion actually follows from the premises. Flag any gap where a reader would ask "wait, how did we get here?".
(Q10) Notation is consistent WITHIN and ACROSS files. The same symbol must mean the same thing everywhere. E.g. if index.qmd defines n_i = |r_i⟩⟨r_i|, sub-pages must not silently redefine n_i as number operator. Flag every inconsistency with the exact conflicting definitions.
(Q11) Physical reasoning is self-consistent. If a Hamiltonian is presented with certain symmetries, the claimed phase diagram and phenomena must be compatible with those symmetries. If a perturbative expansion is used, the stated validity regime must be correct. Flag any statement that contradicts the model as written.
(Q12) Theoretical completeness: for each model, check whether the key theoretical ingredients are present and correct:
      - Is the effective Hamiltonian derivation complete or does it hand-wave a crucial step?
      - Are the approximations (mean-field, perturbative, exact) clearly stated with their validity conditions?
      - Are phase boundaries stated with the correct scaling/exponents?
      - Could a reader reconstruct the mapping from Rydberg physics to the target model using ONLY what is written, without external references?
      Flag any place where the theory is incomplete, vague, or where adding 2-5 sentences would significantly improve understanding.'

ITERATION=0

while true; do
  ITERATION=$((ITERATION + 1))

  echo ""
  echo "============================================"
  echo "  PHASE 6 — REVIEW iteration $ITERATION"
  echo "  $(date)"
  echo "============================================"

  # Step A: Review — find deficiencies
  REVIEW_OUTPUT=$(claude -p \
    --dangerously-skip-permissions \
    --model opus \
    --append-system-prompt "$PREAMBLE" \
    "You are a CRITICAL REVIEWER performing a deep, line-by-line audit.

STEP 1: Read ALL .qmd files in $WORKDIR/ and refs.bib — every line, no skimming.

STEP 2: For each sub-page file (excluding index.qmd and Effective_ham.qmd), perform TWO passes:

  PASS 1 — Structural checklist (Q1-Q8): does each required section exist and have sufficient depth?
  PASS 2 — Line-by-line coherence audit (Q9-Q12): read every sentence and ask yourself:
    - Does this sentence follow logically from the previous one, or is there a hidden leap?
    - Is the notation here consistent with how the same symbol is used elsewhere in this file AND in index.qmd?
    - If a Hamiltonian is written, do the claimed properties (symmetries, phases, limits) actually follow from it?
    - If an approximation is invoked, is the validity regime stated? Would a careful reader spot a contradiction?
    - Could a quantum computing experimentalist reconstruct the full Rydberg-to-model mapping from what is written, without needing to open the cited paper?

$QUALITY_CRITERIA

Output a structured report in this EXACT format (one block per file):

=== <filename> ===
PASS: Q1, Q3, Q5
FAIL:
- Q2: Missing parameter regime table mapping Rydberg quantities to model params.
- Q4: Only 2 experiments listed; refs.bib contains at least 5 relevant papers (list them by key).
- Q7: Atom count missing for Bornet 2023 entry.
- Q8: 'Key phenomena' section is only 3 lines.
- Q9: Line 47 says 'therefore the ground state is Z2-ordered' but the preceding paragraph only discusses the classical limit — the quantum fluctuation argument is missing.
- Q10: sigma^x_i used on line 32 but index.qmd defines spin operators as S^x_i = sigma^x_i/2. Inconsistent factor of 2.
- Q11: Section claims XXZ model has U(1) symmetry but the written Hamiltonian includes a term that breaks it.
- Q12: Schrieffer-Wolff derivation jumps from 2nd-order perturbation theory to the final effective Hamiltonian without showing which virtual states are summed over. Adding 3 sentences would close this gap.
PRIORITY FIX: Q12 — incomplete SW derivation (most damaging to theoretical self-consistency).

Rules:
- Be ruthlessly strict. A section that exists but is hand-wavy counts as FAIL.
- For Q9-Q12 failures, cite the SPECIFIC line number or quote the problematic sentence.
- If everything genuinely passes all 12 criteria, write PASS: ALL.
- Do NOT suggest fixes — only diagnose problems with precision." 2>&1) && {
    echo "$REVIEW_OUTPUT"
  } || {
    if echo "$REVIEW_OUTPUT" | grep -qi "limit\|rate\|quota\|resets\|throttl\|overloaded"; then
      echo "  RATE LIMITED during review — waiting ${RETRY_WAIT}s"
      sleep $RETRY_WAIT
      continue
    fi
    echo "$REVIEW_OUTPUT"
    echo "  Review failed with non-rate-limit error. Waiting 60s and retrying..."
    sleep 60
    continue
  }

  # Check if all files pass
  if echo "$REVIEW_OUTPUT" | grep -q "PASS: ALL" && ! echo "$REVIEW_OUTPUT" | grep -q "^FAIL:"; then
    echo ""
    echo "============================================"
    echo "  ALL FILES PASS QUALITY CHECK at iteration $ITERATION"
    echo "  $(date)"
    echo "  Continuing to look for further improvements..."
    echo "============================================"
  fi

  sleep 10

  echo ""
  echo "============================================"
  echo "  PHASE 6 — IMPROVE iteration $ITERATION"
  echo "  $(date)"
  echo "============================================"

  # Step B: Improve — fix the highest priority deficiency
  run_claude "Phase 6 improve #$ITERATION" \
"You are an IMPROVER. Read ALL .qmd files in $WORKDIR/ and refs.bib.

Here is the review report from the previous step:

--- BEGIN REVIEW ---
$REVIEW_OUTPUT
--- END REVIEW ---

$QUALITY_CRITERIA

Your task:
1. Read the review report above carefully. Pay special attention to Q9-Q12 failures — these are coherence and theory issues that undermine the review's credibility.
2. Identify the single HIGHEST-IMPACT deficiency across all files. Priority order:
   (a) Q11/Q12 — physical inconsistencies or incomplete theory (most damaging to credibility)
   (b) Q9/Q10 — logical gaps or notation inconsistencies (confuse the reader)
   (c) PRIORITY FIX annotations from the reviewer
   (d) Other Q1-Q8 structural issues
3. Fix ONLY that one deficiency by editing the relevant file. When fixing theory issues (Q11/Q12):
   - Re-derive the problematic step yourself to verify correctness before writing.
   - State approximations explicitly with their validity conditions.
   - Ensure the fix is self-consistent with the rest of the file and with index.qmd notation.
   - If a derivation gap needs filling, write the missing steps concisely (key idea + result, not full algebra).
4. For existing files from the original repo (TFIM.qmd, ferm_Hubbard.qmd, Boson-Hubbard.qmd, honeycomb.qmd, puccd.qmd, Effective_ham.qmd): ONLY append, do NOT rewrite.
5. For files created during this session (XY_XXZ.qmd, topological.qmd, LGT.qmd, density_wave.qmd, dynamics.qmd, optimization.qmd): you may edit freely — including rewriting paragraphs to fix logical flow or correct physics.
6. If the fix requires new references, web-search, verify, add to refs.bib.
7. After fixing, re-read the edited section in context (5 lines before and after) to confirm the fix does not introduce NEW inconsistencies.
8. Commit with: git add <files> && git commit -m 'improve: <file> — <what was fixed>'

Focus on ONE fix per iteration. Be thorough on that one fix rather than superficial on many."

  echo ""
  echo "  Iteration $ITERATION complete at $(date)"
  echo "  Starting next iteration in 10 seconds..."
  echo "  (Press Ctrl+C to stop the loop)"
  sleep 10
done

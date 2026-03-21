# Diagnostic Report: Round 8 — f-incompatibility program primal and dual (lines 681–849)

## Issues Found

---
### ISSUE #1
**Location:** line ~702 (lemma statement) vs lines ~734, ~743 (proof)
**Quote:** Lemma: `Y_\alpha, Z \in \mathrm{Herm}(\cH^{\ox k})`; Proof: `Y_\alpha \in \mathrm{Herm}(\mathbb{C}^d)`
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The lemma statement (line 702) declares dual variables in `Herm(H^{⊗k})`, but the proof (lines 734, 743) switches to `Herm(ℂ^d)` without defining `d = dim(H)^k` in this context. The same inconsistency appears in the non-Hermitian lemma (lines 778, 804). Line 234 defines `d = 2^n` for the n-qubit case, but that definition is specific to a different section and doesn't apply here generically.
**Suggested fix:** Use `\mathrm{Herm}(\cH^{\ox k})` consistently in both the lemma statements and their proofs (lines 734, 743, 778, 804). Alternatively, add a local definition `d := \dim(\cH^{\ox k})` before the proof.

---
### ISSUE #2
**Location:** line ~679–688 (primal program, boxed)
**Quote:** The primal program has no explicit constraint `s ≥ 0` or `F_α ∈ Herm(H^{⊗k})`
**Category:** MISSING_HYPOTHESIS
**Severity:** MINOR
**Description:** (a) The constraint `s ≥ 0` is absent from the boxed primal \eqref{eq:primal-bilinear}, though it appears in the reformulated SDP (line 728). The proof divides by `s` (line 711, "s > 0"), which requires this. (b) The Hermiticity of `F_α` is a necessary condition for feasibility (since `Σ_j h_α(j) Π_j` is Hermitian for real `h_α(j)` and Hermitian `Π_j`), but is never stated. Line 748 retroactively notes this assumption.
**Suggested fix:** Add `s \geq 0` to the boxed primal constraints. Add `F_\alpha \in \mathrm{Herm}(\cH^{\ox k})` either in the primal or in the text immediately preceding it.

---
### ISSUE #3
**Location:** line ~732
**Quote:** "set $M_c = (s/2^{|\cA|})\,\1^{\ox k} + \epsilon_c$ where $\{\epsilon_c\}$ are small Hermitian perturbations chosen so that $\sum_c c_\alpha\,\epsilon_c = F_\alpha$ and $\sum_c \epsilon_c = 0$ while keeping $M_c \succ 0$"
**Category:** UNJUSTIFIED_STEP
**Severity:** MINOR
**Description:** The existence of such `ε_c` is asserted without proof. While the construction `ε_c = (1/2^{|A|}) Σ_α c_α F_α` works (one can verify `Σ_c c_α ε_c = F_α` using orthogonality of characters, and `Σ_c ε_c = 0` since `Σ_c c_α = 0`), this is not shown. For a reader checking Slater's condition, the explicit construction would be reassuring.
**Suggested fix:** Add a brief parenthetical: "e.g., $\epsilon_c = 2^{-|\cA|} \sum_\alpha c_\alpha F_\alpha$ satisfies both constraints by orthogonality of the hypercube characters."

---
### ISSUE #4
**Location:** line ~752
**Quote:** "such symmetrization will make the strategy unextendable"
**Category:** CLARITY
**Severity:** MINOR
**Description:** The term "unextendable" is non-standard in this context. The intended meaning is that a tensor-product local strategy optimized for the symmetrized single-site operators does not compose to give the global symmetrized operator. The citation [zhou2020single] is given but the terminology could confuse readers.
**Suggested fix:** Replace with: "such symmetrization prevents the strategy from being extended via tensor products to multi-site systems" or similar phrasing that explicitly states the failure mode.

---
### ISSUE #5
**Location:** line ~753
**Quote:** "$[(XI+IX)\mathrm{SWAP}]^{\ox n} \neq [(X^{\ox n}I^{\ox n}+I^{\ox n}X^{\ox n})\mathrm{SWAP}^{\ox n}]$, which indicates that locally implementing the best estimation strategy for..."
**Category:** CLARITY
**Severity:** MINOR
**Description:** The logical connection between the algebraic inequality and the conclusion about local strategies is not explicit. The reader must infer: (1) the LHS is what a tensor-product local strategy produces, (2) the RHS is the target global operator, (3) mismatch ⟹ the local strategy fails to estimate the global operator set. This inference chain should be stated.
**Suggested fix:** Add a sentence like: "Since the tensor product of locally symmetrized operators (LHS) differs from the globally symmetrized operator (RHS), a local strategy optimized for single-site symmetrized operators cannot reproduce the global estimation constraints."

---
### ISSUE #6
**Location:** line ~845
**Quote:** "it is impossible to solve the SDP for f-incompatibility for $k$ replicas of an $n$-qubit state $\rho^{\ox k}$ in polynomial time"
**Category:** OVER_CLAIMING
**Severity:** MINOR
**Description:** The claim "impossible to solve in polynomial time" is a complexity-theoretic statement that would require a formal hardness proof (e.g., NP-hardness reduction). What is actually shown is that the SDP has `2^{|A|}` (or `2^{2|A|}`) sign-vector constraints, making it exponentially large. This is a statement about the formulation size, not a computational complexity lower bound — one could conceivably exploit structure (e.g., separation oracles) to solve it more efficiently.
**Suggested fix:** Replace with: "the direct SDP formulation for f-incompatibility has exponentially many constraints (one per sign vector $c \in \{-1,1\}^{|\cA|}$), making it intractable for large $|\cA|$."

---
### ISSUE #7
**Location:** line ~762
**Quote:** `\sum_j \Pi_j = \,\1^{\ox k},\Pi_j \geq 0,`
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Missing line break or spacing between the two constraints `Σ_j Π_j = 𝟙^{⊗k}` and `Π_j ≥ 0`. They are concatenated on a single line with only a comma, inconsistent with the formatting in the Hermitian primal (lines 684–685) where they appear on separate lines. Also, `\Pi_j \geq 0` should be `\Pi_j \succeq 0` for PSD (operator inequality), consistent with the rest of the paper.
**Suggested fix:** Put `\Pi_j \succeq 0` on its own line with `\\` separator, matching the Hermitian primal format. Change `\geq` to `\succeq`.

---
### ISSUE #8
**Location:** line ~685
**Quote:** `\Pi_j \geq 0`
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** Uses `\geq` for positive semidefiniteness of operators. Throughout the rest of the section (e.g., lines 718, 728, 794, 800), the paper correctly uses `\succeq 0` for PSD constraints. The boxed primal programs (lines 685, 762) should be consistent.
**Suggested fix:** Change `\Pi_j \geq 0` to `\Pi_j \succeq 0` in both boxed primal programs.

---
### ISSUE #9
**Location:** line ~826
**Quote:** "the primal constraints $\sum_c c_\alpha\,M_c = F_\alpha$ and $\sum_c M_c = s^*\cdot\1^{\ox k}$"
**Category:** IMPLICIT_ASSUMPTION
**Severity:** MINOR
**Description:** The primal recovery paragraph (lines 819–840) switches between the Hermitian and non-Hermitian cases but uses `{Y_α^*}` in line 820 (Hermitian dual variables) even though the section header is generic. This is fine structurally but the transition at line 832 ("For the non-Hermitian SDP...") should be set off more clearly, e.g., as a separate paragraph.
**Suggested fix:** Add a paragraph break or `\medskip` before line 832 to visually separate the Hermitian and non-Hermitian recovery procedures.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| MAJOR    | 0     |
| MINOR    | 9     |

**Total issues: 9**

**Breakdown by category:**
- NOTATION_INCONSISTENCY: 2 (#1, #8)
- MISSING_HYPOTHESIS: 1 (#2)
- UNJUSTIFIED_STEP: 1 (#3)
- CLARITY: 2 (#4, #5)
- OVER_CLAIMING: 1 (#6)
- GRAMMAR: 1 (#7)
- IMPLICIT_ASSUMPTION: 1 (#9)

**Most critical issue:** Issue #1 (notation inconsistency `Herm(H^{⊗k})` vs `Herm(ℂ^d)`) — while only MINOR in severity, it is the most pervasive inconsistency, appearing in four places across both lemma proofs, and could confuse readers about the space dimensions.

**Overall assessment:** This section is mathematically sound. The SDP reformulation via hypercube convex decomposition is correct, the Lagrangian dualization is verified, and the complementary slackness recovery is valid. The non-Hermitian extension correctly generalizes to `2|A|`-dimensional sign vectors. All issues are presentational (notation, clarity, formatting) rather than logical errors.

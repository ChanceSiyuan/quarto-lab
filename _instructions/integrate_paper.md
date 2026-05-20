<!-- Originally written for the Multi-copy Shadow Tomography paper (transfer_tex.md) -->

# Prompt: Integrate f-Compatibility Framework into Multi-Copy Shadow Tomography Paper

You are helping me restructure and fill in a research paper (main.tex, revtex4-2 format, PRL-style main body + Supplemental Material appendix). The main body has placeholder sections (sec1-sec6). The appendix already contains partial results on multi-copy local estimation, 4-replica nonlocal strategy, and lower bounds.

The tex file is attached as project file: _resource/main.tex

## Source Materials

The following Quarto (.qmd) research notes contain the results to integrate. All are attached as project files in folder:

theory/Posts/Shadow_tomography
theory/Posts/compatibility


### Core Framework
- **f-compatiability.qmd**: The f-compatibility framework. Contains:
  - Classical estimation condition (polynomial functionals, falling factorial estimators)
  - Definition of k-copy f-compatibility (@def-f-compatibility): given POVMs {A_i}, functional family F, find POVM Pi_j on H^{otimes k} with scalar estimators h_alpha(j) in [-1,1]
  - Lemma: f-compatibility lower bound (k(F) <= k_compat, tight for marginals)
  - Linearization of degree-k polynomials (@def-linearization): F_alpha becomes Hermitian operator on H^{otimes k}
  - No advantage for linear functionals of binary POVMs (@thm-linearfunctional)
  - Advantage for nonlinear functionals (key: squaring makes non-commuting operators commute: [P otimes P, Q otimes Q]=0)
  - f-Compatibility SDP primal and dual (@thm-f-compatibility-SDP, @thm-f-compat-dual)
  - Bell measurement example: {X,Y,Z} squared expectations have r*=0

### Standard Compatibility Theory
- **compatiablity.qmd**: Joint measurability, unsharp Pauli threshold eta^2_x+eta^2_y+eta^2_z <= 1, sharp measurements incompatible
- **multicopy_compatiability.qmd**: k-copy compatibility, structure theorem, F-assisted 2-copy compatibility via spin-flip

### Shadow Tomography Results
- **intro.qmd**: Single-copy shadow framework, inverse channel, variance 3^w for weight-w Paulis
- **3desgin_multi_local_shadow.qmd**: Local k-copy 3-design shadow variance formula (rescaling function R(W,W'))
- **3d2c_appli1.qmd**: Application to tr(O rho^2), covariance operators, variance ~5^w for 2-copy local
- **3d2c_appli2.qmd**: OTOC nonlinear estimator, comparison figure
- **multicopy.qmd**: Entanglement-fixed shadow, shifted Bell sampling
- **multi-copy_localshadow.qmd**: Biased multi-copy local shadows, compatibility robustness conjecture (sampling complexity O(I * eps^{-2} * log(1/delta))), product hardness conjecture

### Nonlocal Strategy
- **nonlocal_multicopy.qmd**: Non-local k-copy Pauli shadow (@thm-nonlocal-pauli-shadow): commuting family A_P = sym_pi[P^{otimes 2} otimes I^{otimes 2}] * P^d_pi, eigenvalue [tr(P rho^k)]^2 on rho^{otimes 2k}. Signal estimation lemma. 4-copy circuit construction.

### Lower Bounds
- **lowerbound.qmd**: Shadow-to-discrimination reduction for nonlinear Pauli shadow

## Key Theoretical Insights from Our Discussion

### 1. The Gamma SDP is a RELAXATION
The f-compatibility SDP reformulates h_alpha(j) Pi_j as matrix variable Gamma_{alpha,j} with Pi_j +/- Gamma_{alpha,j} >= 0. This is NOT equivalent to scalar h when Pi_j has rank > 1. The SDP is exact only for rank-1 (projective) POVMs. For {X,Y,Z} on C^2, the relaxed SDP gives s*=1 while the true answer is sqrt(3).

### 2. The correct POVM-free definition
The framework should be reformulated as "Intrinsic Estimation Compatibility":
- Optimization variables: lifted operators G_alpha, POVM Pi_j, scalars h_alpha(j)
- Constraint: tr[G_alpha rho^{otimes k}] = g_alpha(rho) for all rho (pins G_alpha on symmetric subspace, free elsewhere)
- This eliminates dependence on initial POVM choice
- The free component on Sym^k(H)^perp is optimization leverage

### 3. Tensor product factorization
For product-form linearizations F_alpha = otimes_l F_{alpha_l}, the local f-compatibility robustness factorizes: s*_loc = prod_l s*_l. This transfers single-qubit hardness to n-qubit exponential cost.

### 4. Binary vs non-binary observables
- Binary (eigenvalues +/-1): estimation = compatibility, no gap
- Non-binary (eigenvalue 0 exists): estimation < compatibility. The O_P = 1/2(P otimes I + I otimes P)SWAP operators are spin-1 on the symmetric subspace.

### 5. The non-product obstruction for local strategies
The 4-copy operator A_P = 1/2(P^{otimes 2} otimes I^{otimes 2} + I^{otimes 2} otimes P^{otimes 2}) * pi is a SUM of two product operators, not a single product. The tensor product theorem doesn't apply. Local strategies face exponential cost for tr(P rho^2) at ANY copy number, while the nonlocal 4-copy strategy achieves O(1).

### 6. Copy-complexity trade-off
Total cost C(k) = k * [s*(k)]^2 * eps^{-2} * log|A|. The optimal k minimizes this. Pattern: at k=2d (twice the polynomial degree), the "squaring trick" makes linearizations commute.

## Paper Structure to Fill

### Main Body (PRL-style, ~4 pages)

**Title**: "Multi-copy shadow tomography" (or suggest better)

**Abstract**: Frame around the central question -- given nonlinear functionals of rho, what is the optimal multi-copy measurement strategy? State main results: f-compatibility framework, tensor product theorem, efficient nonlocal strategy, local no-go.

**Introduction**: Shadow tomography background -> multi-copy strategies -> the gap between local and nonlocal -> our framework bridges compatibility theory with shadow complexity.

**sec1 = "Framework"**:
- The estimation problem: given {g_alpha(rho)} polynomial functionals, find optimal k-copy POVM
- Intrinsic estimation compatibility definition (the corrected, POVM-free version)
- Linearization: degree-d polynomials become linear on H^{otimes k}
- The copy-complexity trade-off: min_k k * s*(k)^2

**sec2 = "Tensor Product Structure"**:
- Local measurements: product POVMs on k-replica space
- Factorization theorem: s*_loc = prod_l s*_l for product-form linearizations
- Per-site analysis reduces n-qubit problem to single-qubit SDP
- Recovering 3^w scaling from per-site sqrt(3) incompatibility

**sec3 = "When Nonlinearity Helps"**:
- Linear functionals of binary POVMs: no advantage (estimation = compatibility)
- Squaring trick: [P otimes P, Q otimes Q] = 0 even when [P,Q] != 0
- Bell measurement achieves s*=1 for {|tr(P rho)|^2}

**sec4 = "Nonlocal Multi-Copy Strategies"**:
- Commuting family {A_P} for [tr(P rho^k)]^2 on 2k copies
- Single projective measurement estimates all Pauli nonlinear shadows
- 4-copy circuit construction

**sec5 = "Local No-Go"**:
- The SWAP-based operators are spin-1 (non-binary) -> estimation easier than compatibility but still hard
- Non-product structure of A_P: sum of products, not a product
- Exponential local cost persists at any copy number

**sec6 = "Discussion"**:
- Summary of locality hierarchy table
- Open: general copy-complexity algorithm, local no-go proof, connections to SYK/graph theory

### Appendix (Supplemental Material)
Reorganize existing appendix content + add:
- Full proofs of tensor product theorem
- f-compatibility SDP details (primal, dual, relaxation gap discussion)
- Variance calculations for 2-copy local shadow
- 4-copy nonlocal strategy construction and signal estimation
- Lower bound proofs

## Instructions

1. **Read all project .qmd files** to extract theorems, proofs, and examples.
2. **Fill the main body** (sec1-sec6) with concise PRL-style text. Use \prlsection, theorem environments. Keep main body <= 4 pages. Reference appendix for proofs.
3. **Reorganize the appendix**: merge existing appendix content with new material from the .qmd files. Maintain the existing lower bound calculations (Section C onward). Add Sections for the f-compatibility SDP, tensor product theorem proofs, and the spin-1 analysis.
4. **Maintain notation consistency** with the existing tex file (use \tr, \ox, \1, \ket, \bra, \proj, etc.).
5. **Write the abstract** summarizing: (a) the f-compatibility framework as complexity calibrator, (b) tensor product factorization giving 3^w from per-site sqrt(3), (c) squaring trick giving Bell-measurement efficiency, (d) nonlocal 4-copy strategy for [tr(P rho^2)]^2, (e) local no-go.
6. **Add bibliography entries** for: Heinosaari-Kiukas-Reitzner 2015 (incompatibility robustness), Designolle-Farkas-Kaniewski 2019 (unified framework), McNulty et al 2024 (fermionic joint measurements, arXiv:2402.19349), graph-theoretic approach (arXiv:2511.15954), Wu-Yang 2020 (polynomial estimation), Huang-Kueng-Preskill 2020 (classical shadows), Chen-Wang-Yu-Zhang 2025 (simultaneous nonlinear estimation, arXiv:2505.16715), Ekert et al 2002 (direct estimation of functionals).

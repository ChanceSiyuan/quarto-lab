<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Monte Carlo Renormalization Group (MCRG)

Block-spin real-space renormalization group applied to MC-sampled configurations to extract critical exponents `y_t, y_h` and the critical manifold from the eigenvalues of the linearized RG map.

## Method card

### What it is

MCRG (Swendsen 1979) generates equilibrium configurations of a classical spin model at its critical point using Monte Carlo sampling, then applies an iterative block-spin transformation (e.g. majority-rule or decimation) to each configuration. The renormalized coupling constants are matched by requiring that selected spin correlations are identical before and after the transformation; the eigenvalues of the linearized RG transfer matrix give the thermal and magnetic RG exponents `y_t` and `y_h`, from which the standard critical exponents `ν = 1/y_t`, `β = (d − y_h)/y_t`, `γ = (2y_h − d)/y_t` follow. Variational MCRG (Wu–Car 2017) optimizes the block-spin rule and the operator basis to minimize the variational distance between the blocked distribution and a target form, significantly alleviating critical slowing down and improving accuracy without a large operator basis.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Critical exponents `y_t`, `y_h` (→ `ν`, `β`, `γ`, `δ`, `η`); critical coupling `K_c`; critical manifold and its tangent space; renormalized coupling constants as a function of RG scale | NOT ground-state energies, NOT thermodynamic-limit observables (e.g., magnetization or susceptibility away from criticality), NOT the full spectrum. |
| M2 regime | Finite temperature — specifically at or near the critical fixed point | MCRG is designed for the critical fixed point; away from `T_c` it gives flow information but not exponents. |
| M3 accuracy class | Controlled-bias, stochastic | Statistical error from MC sampling `∝ 1/√N_s`; systematic bias from finite block-spin operator basis (controlled by expanding the basis) and finite lattice (controlled by `L → ∞`). |
| M4 dimension fit (A1) | Any dimension (1D / 2D / 3D / ∞-D) — applicable to classical spin models in any dimension | Best applied where a critical fixed point exists (2D Ising / Potts, 3D Ising / Heisenberg, etc.). |
| M5 statistics & local dim (A3) | Classical spin models: Ising (`d=2`), Potts, O(n) continuous spins | Applies to any classical statistical model with a critical point; local dim only affects MC cost. |
| M6 entanglement regime (B5) | N/A — classical model | No entanglement restriction; thermodynamic configurations sampled. |
| M7 sign-problem dependence (C12) | Requires sign-free / classical models | MCRG operates on classical Boltzmann weights; no sign problem. For quantum models, the sign-free auxiliary-field / world-line mapping must exist first. |
| M8 symmetry exploitation (C9/C10) | Symmetry constrains the operator basis for the RG matching (fewer independent coupling constants); translation used in momentum-space matching variants | Symmetry reduces the number of couplings that must be matched, improving accuracy. |
| M9 time complexity | MC sampling cost `O(N · τ_auto · N_s)` × #RG iterations; cluster MC (§2.2) used to reduce `τ_auto`; variational MCRG (Wu–Car 2017) **significantly alleviates** critical slowing down | Larger `L` near `T_c` improves exponent accuracy (finite-size corrections `∝ L^{-ω}`); #RG steps typically 3–5 per lattice. |
| M10 memory | `O(N)` — spin configurations + blocked configurations at each RG level | Memory is dominated by storing configurations for the blocked lattice hierarchy. |
| M11 control knob | Lattice size `L` (controls finite-size corrections `~ L^{-ω}`); number of RG iterations; operator-basis size (controls truncation bias) | Accuracy of exponents improves with `L` and operator-basis completeness; convergence checked by stability of eigenvalues across RG steps. |
| M12 scale frontier | Large lattices near `T_c` (`L ~ 10²–10³` typical; `L ~ 10⁴` with cluster MC or variational MCRG); exponent accuracy `~ 10⁻³–10⁻⁴` at the frontier | Finite-size corrections to exponents scale as `L^{-ω}` (correction-to-scaling exponent); 3–4 RG levels require `L ≥ 2^4 = 16` at minimum, `L ≥ 256` for percent-level precision. |
| M13 primary approximation / bias | Finite block-spin operator basis (truncation of RG operator space) — controlled by expanding the basis; finite-size effects — controlled by increasing `L` | Both biases are systematically reducible; variational MCRG optimizes the basis to minimize truncation error. |
| M14 hard blocker / failure mode | Not applicable to non-critical systems or for computing thermodynamic-limit observables / ground-state energies — MCRG extracts only fixed-point data; requires a valid critical point (no topological phases without Landau order); frustrated / glassy systems (B8) complicate locating `T_c` | Away from criticality, MCRG returns RG-flow information but not universal exponents. |

### Cost & scaling

- Time: MC sampling `O(N · τ_auto · N_s)` + `O(N)` per RG blocking iteration; cluster MC cuts `τ_auto ~ L^{0.22}` (SW) vs `L^{2.17}` (Metropolis)
- Memory: `O(N)` — configurations at each RG level (shrink by factor 2–4 per level)
- Control knob: `L` (lattice size, controls finite-size corrections `~ L^{-ω}`); operator-basis size; #RG steps
- Scale frontier: `L ~ 10²–10³` routine; `L ~ 10⁴` with variational MCRG / cluster sampling

### Accuracy & guarantees

- Class: controlled-bias, stochastic
- Primary approximation & its control: truncated RG operator basis (expand to reduce); finite lattice (increase `L`)
- Error scaling: statistical `∝ 1/√N_s`; systematic `∝ L^{-ω}` (leading correction to scaling); convergence diagnosed by stability of eigenvalues `y_t, y_h` across RG levels

### Tasks it computes

- Thermal exponent `y_t` (→ correlation-length exponent `ν = 1/y_t`)
- Magnetic exponent `y_h` (→ order-parameter exponent `β = (d − y_h)/y_t`, susceptibility exponent `γ = (2y_h − d)/y_t`)
- Critical coupling `K_c = J/(k_B T_c)` and the critical manifold
- Tangent space of the critical manifold (Wu–Car 2017 variational extension)
- Renormalized coupling constants at each RG level (RG flow near the fixed point)

### Recommended for (models / regimes)

- **Critical-exponent extraction** for classical spin models at their continuous phase transition (B6 = gapless/critical)
- **Any dimension** where a critical fixed point exists: 2D Ising, 2D Potts, 3D Ising, 3D Heisenberg, O(n) universality classes
- **Cross-validation of exponents** from finite-size scaling (Binder cumulants) or field-theoretic calculations
- Per `method-property-map.md` (MCRG profile): applicable when B6 = critical; blocked when the goal is thermodynamic-limit observables or GS energies

### Key reference

[@wu_2017_variational] — variational MCRG that optimizes the block-spin rule to minimize a variational distance, removes critical slowing down, and extracts the critical manifold tangent space; provides benchmark exponents for 2D Ising and 3D Ising.
Rendered: `../../literature/monte-carlo-renormalization-group/1707.08683_variational-approach-to-monte-carlo-renormalization-group.md` _(reused)_.

[@swendsen_1979_montecarlo] — original MCRG method: block-spin RG on MC configurations; exponents from eigenvalues of the linearized RG map; established the framework for all MCRG variants.
Rendered: `../../literature/monte-carlo-renormalization-group/10-1103-physrevlett-42-859.md` _(reused)_.

[@swendsen_1984_montecarlo] — MCRG calculation of renormalized coupling parameters; established the matching condition for multi-coupling RG flows.
Rendered: `../../literature/monte-carlo-renormalization-group/10-1103-physrevlett-52-1165.md` _(reused)_.

[@guo_2005_montecarlo] — MCRG applied to the (ferromagnetic) triangular Ising model as a test case; demonstrates exponent extraction and finite-size analysis on a non-square-lattice geometry.
Rendered: `../../literature/monte-carlo-renormalization-group/10-1103-physreve-71-046126.md` _(reused)_.

### Benchmarks

- 2D Ising `y_t = 1.000`, `y_h = 1.875` (exact from Onsager/Kaufman/Yang): recovered to `< 0.1%` by MCRG with `L = 256` and 4 RG levels [@swendsen_1979_montecarlo].
- 3D Ising exponents from variational MCRG (Wu–Car 2017): `ν = 0.6299(4)` (cf. conformal-bootstrap `0.6299(2)`), `η = 0.0363(4)` [@wu_2017_variational].
- Triangular-lattice **ferromagnetic** Ising model: MCRG recovers the 2D Ising universality class `y_t = 1.00(1)`, `y_h = 1.875(5)` — a non-square-lattice test of the method's geometry-independence [@guo_2005_montecarlo].
- Finite-size corrections to exponents scale as `L^{-ω}` with `ω ≈ 0.83` (3D Ising) — `L ≥ 64` required for sub-percent precision [verified in `method-survey.md` §2.3].

## How it is used / Operational

**Owning skill:** none — MCRG is a reference method outside the core harness (no dedicated `/method-*` skill). The workflow below (operator-basis construction, eigenvalue extraction) is self-contained.

**Default workflow:**
1. Generate equilibrium configurations at `T ≈ T_c` using cluster MC (Swendsen–Wang or Wolff) to minimize critical slowing down; collect `N_s ≥ 10³` independent configurations at lattice size `L`.
2. Apply the block-spin rule (majority vote / decimation) repeatedly to each configuration, producing blocked lattices at scales `L, L/b, L/b², …`.
3. For each RG step, measure the expectation values of the selected operators (spin–spin, spin–spin–spin, …) on both the original and blocked lattice; solve the matching equations for the renormalized couplings.
4. Extract the RG transfer matrix by differentiating the matching equations; diagonalize to obtain `y_t` and `y_h`.
5. Check convergence: `y_t, y_h` should stabilize across RG levels; repeat for multiple `L` to extrapolate `L → ∞`.

**Variational MCRG (Wu–Car 2017) variant:**
- Parameterize the block-spin rule and operator basis; minimize the variational distance (KL divergence or similar) between the blocked distribution and a target Boltzmann form.
- Gradient-based optimization removes critical slowing down and allows a systematic basis search.

**Verification pointers:**
- For 2D Ising: exponents must converge to `y_t = 1.000`, `y_h = 1.875` (exact) within statistical errors.
- Eigenvalue stability: `y_t, y_h` must not change by more than statistical error when the operator basis is enlarged.
- Cross-check `T_c` from MCRG fixed-point coupling with Binder-cumulant location from cluster-mc.

**Cross-links:**
- Survey: `method-survey.md` §2.3 (Monte Carlo renormalization group)
- Model↔method gate: `method-property-map.md` (MCRG profile — B6 criticality)
- Complementary methods: cluster-mc (provides low-autocorrelation configurations for MCRG), metropolis-mc (slower but simpler configurations), finite-size-scaling (alternative exponent extraction from Binder cumulants)

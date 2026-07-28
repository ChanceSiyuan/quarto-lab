# Sachdev–Ye–Kitaev model — exact-solution oracle

Technique: T6 (collective / large-N / random) · Tier: D (exact in a limit) · Script: P

## Hamiltonian & conventions

$$ H = \sum_{i<j<k<l} J_{ijkl}\,\chi_i\chi_j\chi_k\chi_l, \qquad \overline{J_{ijkl}}=0,\quad \overline{J_{ijkl}^{\,2}}=\frac{3!\,J^2}{N^3}=\frac{(q-1)!\,J^2}{N^{q-1}}\;(q=4) $$

Conventions: `N` Majorana fermions `χ_i` with `\{\chi_i,\chi_j\}=2\delta_{ij}` (the oracle's Clifford/Jordan–Wigner normalisation; Maldacena–Stanford use `\{\chi_i,\chi_j\}=\delta_{ij}`, i.e. `χ_i→χ_i/\sqrt2`, which rescales the energy unit but leaves the dimensionless level statistics and `S/N` unchanged). Couplings `J_{ijkl}` are i.i.d. zero-mean Gaussians with variance `\overline{J_{ijkl}^2}=3!J^2/N^3` — the **Maldacena–Stanford convention** [@MaldacenaStanford2016] Eq. (2.3), with `q=4` and `(q-1)!=3!=6`. Physics is **disorder-averaged**. No lattice, no geometry — all-to-all 4-body randomness. This is the model-zoo entry `models/sachdev-ye-kitaev` (state-for-state the same object; that card uses citekey `[@chowdhury_2021_sachdev]` for the RMP review, this card cites the primary sources). See `.knowledge/conventions.md`.

## Solvability statement

T6 / **Tier D** (exact in the `N→∞` limit): after disorder averaging, the `1/N^3` variance makes only "melonic" diagrams survive, and the theory closes into the **Schwinger–Dyson equations** [@MaldacenaStanford2016] Eq. (2.6),
`1/G(iω) = -iω - Σ(iω)`, `Σ(τ) = J^2 G(τ)^{q-1}`,
which are *exact* at `N=∞`. Their strong-coupling (IR) solution is **conformal**, `G_c(τ)∝\mathrm{sgn}(τ)/|τ|^{2Δ}` with fermion dimension `Δ=1/q=1/4`, and the model is a **non-Fermi liquid**: maximal chaos (Lyapunov exponent saturating `λ_L=2πk_BT/ℏ`) and an **extensive zero-temperature entropy** `S_0/N≈0.2324`. **Not exact at finite `N`:** the finite-`N` model is fully chaotic (random-matrix level statistics) and requires ED. So this is a **D-tier / P-script** card — the exact content is the `N→∞` limit (tabulated conformal data + the scripted SD entropy trend) and the finite-`N` ED level statistics are exact reference numbers for whatever `N` is diagonalised, *not* a thermodynamic-limit claim.

## Two scriptable pieces (and the honest framing)

**(i) Finite-`N` ED level statistics — an identity-proof.** The random-matrix universality class of the SYK spectrum is fixed by the **Bott periodicity of the Clifford algebra**, i.e. by `N mod 8` [@GarciaGarciaVerbaarschot2016; @YouLudwigXu2017]: `N mod 8 = 0 → GOE`, `2,6 → GUE`, `4 → GSE`. The oracle builds the `2^{N/2}`-dimensional Majorana Hamiltonian (fixed seed), restricts to one fermion-parity sector, and measures the disorder-averaged adjacent-gap ratio `⟨r̃⟩`. `N=16` (`mod 8=0`) lands in **GOE** and `N=12` (`mod 8=4`) in **GSE** — the latter with the same **Kramers doubling** as a true GSE (every level exactly twice; asserted `<1e-9` before deduplication). The targets are **cross-loaded from the `random-matrix-stats` card** (`0.5307` for GOE, `0.6744` for GSE) — a genuine cross-card oracle use.

**(ii) Large-`N` Schwinger–Dyson entropy trend — observed-as-observed.** The oracle solves Eq. (2.6) in imaginary time on an antiperiodic Matsubara grid (`N_τ=2^{14}`), `β`-ramped to `βJ=40` for stability, and reconstructs the entropy by thermodynamic integration of the (robust) energy density, `\log Z/N=\tfrac12\ln2-\int_0^β (E/N)\,dβ'`, `S/N=βE/N+\log Z/N`. `S/N` falls **monotonically** from the free `\tfrac12\ln2=0.34657` toward the web-verified `S_0/N≈0.2324`; at `βJ=40` it reads `≈0.241` and is **still decreasing**. This is reported *observed-as-observed*: the finite-`β` value is **not** claimed to equal `S_0` — a subleading `-(3/2)\ln(βJ)/N` tail and the `c/(2βJ)` specific-heat term keep it above `S_0` at any finite `β` [@MaldacenaStanford2016]. The conformal amplitude `b=G(β/2)(β/π)^{1/2}` simultaneously trends to the exact `(4π)^{-1/4}=0.5311`.

## Exact / tabulated results

- Schwinger–Dyson equations (exact at `N=∞`): `1/G(iω)=-iω-Σ(iω)`, `Σ(τ)=J^2G(τ)^{q-1}` [@MaldacenaStanford2016]
- Conformal fermion dimension: `Δ=1/q=1/4` (`q=4`); IR `G_c(τ)∝\mathrm{sgn}(τ)/|τ|^{1/2}`, amplitude `J^2 b^q π=(\tfrac12-Δ)\tan πΔ ⇒ b=(4π)^{-1/4}` [@MaldacenaStanford2016]
- Zero-temperature entropy density: `S_0/N≈0.2324` (`q=4` Majorana) [@MaldacenaStanford2016]; independent ED extrapolation gives `S_0≈0.21N`, "in rough agreement" [@GarciaGarciaVerbaarschot2016]
- Maximal chaos: Lyapunov exponent saturates the bound `λ_L=2πk_BT/ℏ` [@MaldacenaStanford2016; @Kitaev2015]
- Finite-`N` level-statistics class (Bott periodicity): `N mod 8 = 0/2/4/6 → GOE/GUE/GSE/GUE` [@GarciaGarciaVerbaarschot2016; @YouLudwigXu2017]
- Origin: the `SYK_∞` random-`q`-body model of a spin liquid [@SachdevYe1993]; the Majorana `q=4` version and holographic dual [@Kitaev2015; @MaldacenaStanford2016]

## Oracle script

`python oracle.py --task levels --N 16` → finite-`N` ED: prints `class`, `rtilde`, `rtilde_target`, `in_band`, `kramers_pairgap`, `herm_residual`. `python oracle.py --task entropy` → large-`N` SD: `S_over_N_highT`, `S_over_N_lowT`, `S0_tabulated`, `E_over_N`, `conformal_b_half`, `monotone_decreasing`, `max_sd_residual`. Importable: `compute(task, N, seed, beta_max)`; helpers `syk_level_rtilde`, `sd_solve`, `entropy_trend`.
Self-test anchors: (1) **`N=16` → GOE** `⟨r̃⟩` in `0.5307±0.013`, Hermitian (`<1e-10`); (2) **`N=12` → GSE** `⟨r̃⟩` in `0.6744±0.018` with **exact Kramers doubling** (`<1e-9`, identity-proof); targets cross-loaded from `random-matrix-stats`; (3) reproducibility (fixed seed bit-identical); (4) **SD convergence** (max residual `<1e-8`); (5) entropy `S/N` **starts at** `\tfrac12\ln2` (`1e-2`), is **monotone decreasing**, and its `βJ=40` value lies in `(S_0, 0.28)` — above `S_0=0.2324`, trending down; (6) `E/N∈(-0.05,-0.03)` (ground energy per Majorana); (7) conformal amplitude `b→(4π)^{-1/4}` (`0.03`).

**Stochastic anchors.** `⟨r̃⟩` averaged over `n_real` disorder realisations (`N=16`: 30 realisations of the `2^7`-dim parity sector; `N=12`: 200 realisations of the `2^5`-dim sector, small after Kramers dedup). Run-to-run spread across 5 dev seeds: `σ=0.0020` (`N=16`), `0.0038` (`N=12`); bands `0.013/0.018` are `≥4σ` plus the finite-size centring offset; one seed fixed in the self-test.

## Benchmarks

| Quantity | Params | Value | Source |
|---|---|---|---|
| `⟨r̃⟩` (level class) | `N=16`, `mod 8=0` | `0.531` → **GOE** `0.5307` | [@GarciaGarciaVerbaarschot2016; @AtasEtAl2013] |
| `⟨r̃⟩` (level class) | `N=12`, `mod 8=4` | `0.678` → **GSE** `0.6744` | [@YouLudwigXu2017; @AtasEtAl2013] |
| Kramers pair-gap | `N=12` (GSE sector) | `<1e-9` (doubling exact) | this card (identity-proof) |
| `Δ` (fermion dimension) | `q=4` | `1/4` (tabulated) | [@MaldacenaStanford2016] |
| conformal amplitude `b` | `βJ=40` | `0.524 → (4π)^{-1/4}=0.5311` | this card / [@MaldacenaStanford2016] |
| `S/N` high-`T` | `βJ→0` | `\tfrac12\ln2=0.34657` | this card |
| `S/N` at `βJ=40` | SD, observed | `≈0.241` (decreasing → `S_0`) | this card (observed) |
| `S_0/N` (zero-`T` entropy) | `q=4`, `N→∞` | `≈0.2324` (tabulated) | [@MaldacenaStanford2016] |
| `E/N` (ground energy) | SD `βJ=40` | `≈-0.0405` | this card / [@GarciaGarciaVerbaarschot2016] |

## Verification recipes

- **To check a finite-`N` SYK ED run's spectral statistics:** average `⟨r̃⟩` over the spectrum bulk *within one fermion-parity sector*, for many disorder realisations; the value must match the `N mod 8` class (`0/2/4/6 → GOE/GUE/GSE/GUE`) against the `random-matrix-stats` constants. For `N mod 8=4` (GSE) you **must** deduplicate the exact Kramers doubling first, else `⟨r̃⟩` is biased — see the `random-matrix-stats` GSE trap.
- **To check a large-`N` Schwinger–Dyson code:** at strong coupling the IR Green's function must be conformal with `Δ=1/4` — verify `G(β/2)(β/π)^{1/2}→(4π)^{-1/4}=0.5311` and that `S/N` decreases monotonically from `\tfrac12\ln2` toward `≈0.2324` as `βJ` grows. Do **not** expect the finite-`βJ` entropy to equal `S_0` — it approaches from above.
- **Convention slips:** the variance `\overline{J^2}=3!J^2/N^3` (MS) vs a `1/N^3` without the `(q-1)!` shifts the energy scale but not `⟨r̃⟩` or `S/N`; a missing fermion-parity projection mixes the two sectors and corrupts the level statistics.
- Cross-reference `models/sachdev-ye-kitaev` (the physics card) and `random-matrix-stats` (whose constants this card cross-loads).

## Key reference

[@MaldacenaStanford2016] — J. Maldacena & D. Stanford, "Remarks on the Sachdev-Ye-Kitaev model", Phys. Rev. D **94**, 106002 (2016): the model conventions (Eq. 2.2–2.3), the Schwinger–Dyson equations (Eq. 2.6), the conformal solution `Δ=1/q`, the extensive zero-`T` entropy `S_0`, and maximal chaos. The finite-`N` random-matrix classification (`N mod 8`) and the ED entropy are [@GarciaGarciaVerbaarschot2016; @YouLudwigXu2017]; the model originates with [@SachdevYe1993] and [@Kitaev2015]. Rendered: ./10-1103-physrevd-94-106002.md.

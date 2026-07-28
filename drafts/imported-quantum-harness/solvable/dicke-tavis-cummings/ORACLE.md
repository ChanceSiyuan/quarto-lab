# Dicke / Tavis–Cummings model — exact-solution oracle

Technique: T6 (collective / large-N / random) · Tier: B (integrable / mean-field-exact) · Script: S

## Hamiltonian & conventions

$$ H_{\mathrm{TC}} = \omega\, a^\dagger a + \omega_0\, J_z + \frac{g}{\sqrt{N}}\,(a\,J_+ + a^\dagger J_-), \qquad H_{\mathrm{D}} = \omega\, a^\dagger a + \omega_0\, J_z + \frac{\lambda}{\sqrt{N}}\,(a + a^\dagger)(J_+ + J_-) $$

Conventions: `N` two-level atoms carry the collective (maximal) spin `J = N/2`; `J_{x,y,z}`, `J_±` act on the `(N+1)`-dimensional symmetric multiplet (`J_z` eigenvalues `−j…j`, `J_+` raises `J_z`); `a`, `a†` are photon operators of the single mode (frequency `ω`); `ω₀` is the atomic frequency, `δ = ω₀ − ω`. The `1/√N` is the **standard Kac scaling** (equivalently `1/√{2j}`) that keeps `H/N` finite as `N → ∞`. `H_TC` is the Tavis–Cummings (RWA) model; `H_D` is the full **Dicke** model with the counter-rotating `a J_- + a† J_+` restored (coupling `λ`). Defaults `N = 4`, `ω = ω₀ = 1`, `g = 0.5`. See `.knowledge/conventions.md`.

## Solvability statement

T6 (collective spin + single mode). **Tavis–Cummings (RWA)** conserves the excitation number `C = a†a + J_z + N/2`, so `H_TC` is exactly block-diagonal: sector `C = c` is spanned by `|n = c−k, J_z = −j+k⟩`, `k = 0…min(c,N)`, giving blocks of dimension `dim(c) = min(c,N)+1 = min(c+1, N+1)`. Each block is a small **tridiagonal** matrix in `k`, diagonalized directly — this finite-block structure **is** the exact solution (Tavis–Cummings is Richardson–Gaudin / Bethe-ansatz integrable, but at collective `j` the blocks are already finite). `H_TC` at `N = 1` reduces **exactly** to the Jaynes–Cummings model. **Not exact for `H_TC`:** nothing — the block spectra are exact; the Fock-truncated full-space ED in the script is only a cross-check.

**Dicke (`H_D`, Tier-B statement)** has no such conservation — the counter-rotating terms break `C` down to the `Z₂` parity `Π = exp[iπ(a†a + J_z + N/2)]` — so it needs a truncated-boson full-space ED (documented Fock cutoff `n_max`, convergence-checked). In the **thermodynamic limit `N → ∞`** the Holstein–Primakoff / mean-field treatment is exact and predicts a **superradiant quantum phase transition** at `λ_c = √(ω ω₀)/2` [@EmaryBrandes2003]. This `λ_c` is a closed-form, thermodynamic-limit-exact result; at **finite `N`** it is only a smooth precursor (the ground-state `⟨a†a⟩/N` rises across `λ_c`, observed-as-observed, not a sharp transition).

## The two exact structures

- **TC block dimension** `min(c+1, N+1)` is checked directly (the tridiagonal builder returns exactly that many eigenvalues for a range of `c, N`). The union of blocks reproduces the lowest truncated-boson ED levels (`1e-10`, `N = 4`, Fock-converged `n_max = 30` vs `60`), and the `N = 1` block spectrum equals the Jaynes–Cummings closed form to `1e-12` (importlib cross-load).
- **Dicke `λ_c`** derivation (Holstein–Primakoff): with `J_z = b†b − j`, `J_+ ≈ √{2j}\,b†` in the normal phase, the two coupled bosonic modes have energies `ε_±² = ½[ω² + ω₀² ± √((ω₀²−ω²)² + 16λ²ωω₀)]`; the soft mode `ε_− → 0` exactly when `4ω²ω₀² = 16λ²ωω₀`, i.e. `λ = √(ω ω₀)/2`. The finite-`N` precursor is observed at `N = 24`, `n_max = 60` (Fock-converged vs `n_max = 90`): `⟨a†a⟩/N` stays `< 0.05` in the normal phase and rises past `λ_c` into the superradiant phase.

## Exact results

- Tavis–Cummings excitation number `C = a†a + J_z + N/2` — conserved; blocks of dimension `min(c+1, N+1)` [@TavisCummings1968]
- Tavis–Cummings spectrum: eigenvalues of the finite tridiagonal `C`-blocks (exact, no truncation) [@TavisCummings1968]
- `N = 1` reduction: `H_TC = ω a†a + (ω₀/2)σ^z + g(aσ^+ + a†σ^-)` — the Jaynes–Cummings model exactly [@JaynesCummings1963]
- Dicke superradiant critical coupling (`N → ∞`, mean-field-exact): `λ_c = √(ω ω₀)/2` [@EmaryBrandes2003], [@Dicke1954]
- Dicke normal-phase excitation energies: `ε_±² = ½[ω²+ω₀² ± √((ω₀²−ω²)²+16λ²ωω₀)]`, soft mode `ε_−→0` at `λ_c` [@EmaryBrandes2003]

## Oracle script

`python oracle.py --N 4 --g 0.5` → prints `N`, `tc_e_ground`, `tc_gap`, `tc_block_dim_c3`, `dicke_lambda_c`. Importable: `compute(N=4, g=0.5, omega0=1.0, omega=1.0)`; helpers `tc_block(c,N,g,omega0,omega)`, `tc_block_dim(c,N)`, `tc_spectrum`, `tc_full_ed`, `dicke_photon_per_atom(N,n_max,lam,omega0,omega)`, `lambda_c`.
Self-test anchors: (1) **block-dimension formula** `min(c+1,N+1)` over a range of `c, N`; (2) **exact blocks == truncated full ED** (`1e-10`, `N=4`, Fock-converged `n_max = 30` vs `60`); (3) **`N=1` reduces to Jaynes–Cummings** (importlib cross-load, `1e-12`); (4) **`λ_c = √(ωω₀)/2`** closed form; (5) **finite-`N` superradiant precursor** — `⟨a†a⟩/N` rises across `λ_c` at `N = 24`, `n_max = 60`, observed-as-observed, Fock-converged vs `n_max = 90`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| TC block dimension | sector `C = c`, `N` atoms | `min(c+1, N+1)` | [@TavisCummings1968] |
| `tc_e_ground` | `N = 4`, resonant `g = 0.5` | `−N/2 = −2` (all atoms down, `C=0`) | [@TavisCummings1968] |
| Dicke `λ_c` | resonant `ω = ω₀ = 1` | `0.5` | [@EmaryBrandes2003] |
| Dicke `λ_c` | general | `√(ω ω₀)/2` | [@EmaryBrandes2003] |
| `N = 1` spectrum | any `g`, `ω₀` | Jaynes–Cummings dressed states | [@JaynesCummings1963] |

## Verification recipes

- To check a Tavis–Cummings ED/DMRG run: `tc_spectrum(N, g, ω₀)` gives the exact low-lying levels from the finite blocks (`1e-10`); a mismatch flags a broken `C` conservation or a wrong `1/√N` normalization.
- To check a Dicke superradiance study: `λ_c = √(ω ω₀)/2` is the `N → ∞` transition; at finite `N` compare `dicke_photon_per_atom(N, n_max, λ, ω₀)` for the smooth crossover and **always** re-run with a larger `n_max` to confirm Fock convergence before reading off `⟨a†a⟩/N`.
- Cross-reference `jaynes-cummings` (the `N = 1` RWA limit) and `quantum-rabi` (the `N = 1` non-RWA parent of the Dicke model); same T6 collective family as `lmg`.

## Key reference

[@TavisCummings1968] — Tavis & Cummings, "Exact Solution for an N-Molecule–Radiation-Field Hamiltonian" (Phys. Rev. **170**, 379, 1968): the exact `N`-atom RWA solution. [@Dicke1954] — Dicke, "Coherence in Spontaneous Radiation Processes" (Phys. Rev. **93**, 99, 1954): the collective superradiant model. [@EmaryBrandes2003] — Emary & Brandes (Phys. Rev. E **67**, 066203, 2003): source of the superradiant `λ_c = √(ωω₀)/2` and normal-phase spectrum. Rendered: bib stub — no PDF reachable (2026-07-14).

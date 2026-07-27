# Jaynes–Cummings model — exact-solution oracle

Technique: T6 (collective / large-N / random) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = \omega\, a^\dagger a + \tfrac{\omega_0}{2}\,\sigma^z + g\,(a\,\sigma^+ + a^\dagger \sigma^-) $$

Conventions: `a`, `a†` are single-mode photon annihilation/creation operators (cavity frequency `ω`); `σ^{x,y,z}` are Pauli matrices for a two-level atom of transition frequency `ω₀` (atomic term `(ω₀/2)σ^z`, so `|↑⟩` sits at `+ω₀/2`); `σ^± = (σ^x ± iσ^y)/2`; `g` is the atom–field coupling. Detuning `δ = ω₀ − ω`. Defaults `ω = ω₀ = 1`, `g = 0.5` (resonant). This is the **rotating-wave approximation (RWA)** of the quantum Rabi model — the counter-rotating `a σ^- + a† σ^+` is dropped. See `.knowledge/conventions.md`.

## Solvability statement

T6 (single-mode / collective): the excitation number `C = a†a + (σ^z+1)/2` (photons + atomic excitation) commutes with `H`, so the infinite-dimensional space decomposes into a one-dimensional `C = 0` sector `{|0,↓⟩}` plus **two-dimensional** blocks `{|n,↑⟩, |n+1,↓⟩}` for each `C = n+1 ≥ 1`. Diagonalizing the `2×2` block gives the **dressed-state** energies `E_±(n) = ω(n+½) ± √(g²(n+1) + δ²/4)` in closed form for every level — Tier A, the entire spectrum is exact and algebraic. The `C = 0` ground state `|0,↓⟩` is uncoupled with energy exactly `−ω₀/2` (it is the many-body ground state in the weak-coupling / near-resonant regime; at strong `g` a dressed level `E_−(0)` dips below it). **Not exact:** nothing — every eigenvalue is closed-form. The truncated-boson full-space ED in the script is only a cross-check; its low-lying levels reproduce the block spectra and are stable under doubling the Fock cutoff (a convergence check, not an approximation to the exact answer).

## The dressed-state reduction

In the manifold `C = n+1` the block, in basis `{|n,↑⟩, |n+1,↓⟩}`, has diagonal entries `ωn + ω₀/2` and `ω(n+1) − ω₀/2` and off-diagonal `g√(n+1)`. The mean of the diagonals is `ω(n+½)` and their difference is `δ = ω₀ − ω`, so the eigenvalues are `ω(n+½) ± √(g²(n+1) + δ²/4)` with generalized Rabi splitting `Ω_n = 2√(g²(n+1) + δ²/4)` (vacuum Rabi splitting `2g` at resonance, `n = 0`). The identity is proven in the script two independent ways: the closed form equals `numpy.linalg.eigvalsh` of the constructed `2×2` block (`1e-14`, `n ≤ 20`), and the lowest levels of a truncated full-space (`a`, `a†` as `(n_max+1)`-dim matrices ⊗ two-level) ED match the closed-form spectrum (`1e-12`, `n_max = 40` vs `80` stable).

## Exact results

- Dressed-state energies (every level, any `g`, `δ`): `E_±(n) = ω(n+½) ± √(g²(n+1) + δ²/4)`, `n = 0,1,2,…` [@JaynesCummings1963]
- Ground state `|0,↓⟩` (uncoupled `C = 0` sector): `E = −ω₀/2`, exact for all `g` [@JaynesCummings1963]
- Generalized Rabi splitting: `Ω_n = 2√(g²(n+1) + δ²/4)`; vacuum (`n = 0`) Rabi splitting at resonance `= 2g` [@JaynesCummings1963]
- Conserved excitation number `C = a†a + (σ^z+1)/2` — the `U(1)` symmetry that makes the model exactly solvable [@JaynesCummings1963]

## Oracle script

`python oracle.py --g 0.5 --omega0 1.0` → prints `e_ground`, `detuning`, `vacuum_rabi_splitting`, `E_lower_n0`, `E_upper_n0`, `E_lower_n1`. Importable: `compute(g=0.5, omega0=1.0, omega=1.0)`; helpers `dressed_levels(n,g,delta,omega)`, `rabi_splitting(n,g,delta)`, `spectrum(n_manifolds,g,omega0,omega)`, `block_2x2`, `full_ed`.
Self-test anchors: (1) **closed form == 2×2 block diagonalization** for `n ≤ 20` at three `(g,δ)` points (`1e-14`); (2) **exact `|0,↓⟩` eigenstate** at `−ω₀/2` present in the full ED for any coupling, and it is the GS at weak coupling (a dressed level takes over at strong `g`); (3) **truncated ED reproduces the block spectrum** (`1e-12`) and is **Fock-converged** (`n_max = 40` vs `80`); (4) **vacuum Rabi splitting** `= 2g` at resonance.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e_ground` (`\|0,↓⟩`) | any `g`, resonant `ω₀ = 1` | `−0.5` | [@JaynesCummings1963] |
| vacuum Rabi splitting | resonant `δ = 0`, `n = 0` | `2g` | [@JaynesCummings1963] |
| `E_±(0)` | resonant `δ = 0`, `ω = 1` | `½ ± g` | [@JaynesCummings1963] |
| `E_±(n)` | detuned | `ω(n+½) ± √(g²(n+1)+δ²/4)` | [@JaynesCummings1963] |

## Verification recipes

- To check a cavity-QED ED run: build `ω a†a + (ω₀/2)σ^z + g(aσ^+ + a†σ^-)` with a Fock cutoff and compare the lowest levels to `spectrum(...)` — agreement to `1e-10` (exact); a mismatch at low levels (far below the cutoff) flags a wrong coupling or a spurious counter-rotating term.
- To validate an RWA claim against the full Rabi model: compare with `quantum-rabi`'s ED at the same `(g, Δ = ω₀/2, ω)`; the two agree up to a Bloch–Siegert `O(g²/ω)` shift that vanishes as `g → 0`.
- Cross-reference `dicke-tavis-cummings`: Jaynes–Cummings is exactly its `N = 1` case (`J_z = σ^z/2`, `J_± = σ^±`), an independent cross-load check in that card's self-test.

## Key reference

[@JaynesCummings1963] — Jaynes & Cummings, "Comparison of Quantum and Semiclassical Radiation Theories with Applications to the Beam Maser" (Proc. IEEE **51**, 89, 1963): the original RWA cavity-QED model and source of the dressed-state spectrum and conserved excitation number. Rendered: bib stub — no PDF reachable (2026-07-14).

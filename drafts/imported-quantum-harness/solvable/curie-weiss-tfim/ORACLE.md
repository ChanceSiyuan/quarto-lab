# Curie–Weiss (fully connected) transverse-field Ising — exact-solution oracle

Technique: T6 (collective / large-N / random) · Tier: D (exact in a limit) · Script: S

## Hamiltonian & conventions

$$ H = -\frac{J}{N}\sum_{i<j}\sigma^z_i\sigma^z_j - h\sum_{i=1}^{N}\sigma^x_i $$

Conventions: Pauli-matrix operators (`σ^a`, parallels `tfim-chain`), all-to-all Ising coupling with the standard `1/N` Kac scaling, `h` the transverse field, both `≥ 0`, defaulting to `J = 1`, `h = 0.5`. With the collective spin `S_a = ½ Σ σ^a_i` the couplings reduce exactly to `Σ_{i<j} σ^z_iσ^z_j = 2S_z² − N/2` and `Σ σ^x_i = 2S_x`, so `H = −(2J/N)S_z² − 2h S_x + J/2`. See `.knowledge/conventions.md`.

## Solvability statement

T6 (collective / large-N): the model is the infinite-range (mean-field) TFIM — every pair couples equally, so `H` is a function of the **total** spin alone, `[S², H] = 0`, and the ground state sits in the maximal-spin sector `j = N/2` (dimension `N+1`). Quantizing along `z` makes `S_z²` diagonal and `S_x` a ladder, giving a **tridiagonal** `(N+1)`-block diagonalized to machine precision at any finite `N`. The **Tier-D** framing is deliberate: the collective diagonalization is *exact at every finite `N`*, but the *thermodynamic* results — the closed-form `e₀(h)`, the `h = J` quantum critical point, and the mean-field exponents — are exact only in the `N → ∞` limit, where spin-coherent (mean-field) minimization becomes exact for all-to-all coupling. The finite-`N` block approaches them as `O(1/N)`. **Not exact (at finite `N`):** the closed-form energies and the sharp transition; both are limit statements. What *is* exact at finite `N` is the `N+1`-dimensional collective spectrum itself.

## Relation to the TFIM chain

This is the fully-connected mean-field cousin of `tfim-chain` (`H = −J Σ σ^z σ^z − h Σ σ^x`, nearest-neighbour). The contrast is pedagogically load-bearing: **both** are critical at `h = J` in their Pauli conventions, but the 1D chain is a genuine `d = 1` quantum critical point with correlation-length exponent `ν = 1` and magnetization exponent `β = 1/8` (Onsager/Pfeuty), whereas here the infinite coordination makes **mean-field theory exact** — the order parameter onsets as `√(1−(h/J)²)` giving `β = 1/2`, and finite-size scaling follows the infinitely-coordinated exponents of Botet–Jullien rather than any short-range universality. Same `H = −(2J/N)S_z² − 2h S_x + J/2` collective form as the sibling `lmg` card, with the Ising axis (`z`) and field (`x`) swapped relative to LMG.

## Exact results

- Collective ground energy per spin (any `N`): lowest eigenvalue of the tridiagonal block `diagₖ = −(2J/N)m_z² + J/2`, `offₖ = −h√(j(j+1)−m_z(m_z+1))`, `j = N/2`, divided by `N`
- Thermodynamic energy per spin — ferromagnetic phase `h ≤ J`: `e₀ = −J/2 − h²/(2J)` (at `sin θ = h/J`) [@BotetJullien1983]
- Thermodynamic energy per spin — paramagnetic phase `h ≥ J`: `e₀ = −h` (fully `x`-polarized) [@BotetJullien1983]
- Quantum phase transition: `h = J`, second order — `e₀(h)` is `C¹` (`de₀/dh = −1` both sides) with a second-derivative kink [@BotetJullien1983]
- Ferromagnetic order parameter: `⟨σ^z⟩/N = √(1−(h/J)²)` for `h < J` (mean-field `β = 1/2`), `0` for `h ≥ J`
- Finite-size gap at criticality closes as `∼ N^{−1/3}` (shared with the LMG collective universality) [@DusuelVidal2005]

## Oracle script

`python oracle.py --N 100 --h 0.5` → prints `e0_per_spin`, `e0_thermodynamic`, `gap`, `mz_order_thermo`, `phase`. Importable: `compute(N=100, h=0.5, J=1.0)`; helpers `collective_block(N,J,h)`, `block_lowest`, `e0_thermo`, `gap_collective`.
Self-test anchors: (1) **identity-proof** — collective `(N+1)`-block energy `==` full `2^N` Pauli ED at `N=8` (`1e-12`), both phases; (2) **collective algebra** — `Σ_{i<j} σ^z_iσ^z_j == 2S_z² − N/2` as operators (`N∈{4,6}`); (3) **thermodynamic limit (D-tier)** — `N=4000` block matches the closed form `< 1e-4` both phases, deviation shrinking `2000→4000`; (4) **QPT** — `e₀(h)` `C¹` with a second-derivative kink at `h=J`; (5) **order parameter** — `√(1−(h/J)²)` onset below `h=J`, exactly `0` above.

## Benchmarks

| Quantity | Params | Exact value (N → ∞) | Source |
|---|---|---|---|
| `e0_thermodynamic` | `h = J` (critical) | `−J` | [@BotetJullien1983] |
| `e0_thermodynamic` | ferromagnetic, `h = 0.5, J = 1` | `−0.625` | [@BotetJullien1983] |
| `e0_thermodynamic` | paramagnetic, `h = 1.5, J = 1` | `−1.5` | [@BotetJullien1983] |
| `mz_order_thermo` | ferromagnetic, `h = 0.5, J = 1` | `√3/2 ≈ 0.8660` | [@BotetJullien1983] |
| critical field | any | `h = J` (mean-field, `β = 1/2`) | [@BotetJullien1983] |

## Verification recipes

- To check an ED/DMRG run at size `N`: the model is permutation-symmetric, so a correct GS energy equals `oracle.py --N <N> --h <h>`'s `e0_per_spin × N` to `1e-10` (exact at finite `N`) — a mismatch flags a broken all-to-all symmetry or wrong `1/N` scaling.
- To check a mean-field / thermodynamic claim: compare `e0_per_spin` at large `N` against `e0_thermodynamic`; they agree only to `O(1/N)` (`~1e-4` at `N=4000`). The transition sharpens to a true singularity only as `N → ∞` — do **not** expect a sharp kink at finite `N`.
- Contrast with `tfim-chain`: matching the fully-connected `e₀` to a 1D-chain run is a *category error* — different universality (mean-field `β=1/2` here vs `β=1/8` in `d=1`). Use this card only for all-to-all / infinite-range setups.

## Key reference

[@BotetJullien1983] — Botet & Jullien's finite-size scaling theory of infinitely-coordinated (mean-field-exact) quantum spin systems, including the transverse-field Ising model, source of the mean-field exponents and the exactness-in-the-limit framing; [@DusuelVidal2005] for the `N^{−1/3}` collective critical-gap scaling. Rendered: bib stub — no PDF reachable (2026-07-14).

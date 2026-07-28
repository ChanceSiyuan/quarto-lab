# Lipkin–Meshkov–Glick model — exact-solution oracle

Technique: T6 (collective / large-N / random) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ H = -\frac{J}{N}\,S_x^2 - h\,S_z, \qquad S_a = \tfrac{1}{2}\sum_{i=1}^{N}\sigma^a_i \ \ (\text{collective spin}) $$

Conventions: `S_a` are total-spin operators (`σ/2` per site, `_lib.ed.spin_ops`); `J` is the all-to-all Ising coupling (with the standard `1/N` Kac scaling), `h` the transverse field, both `≥ 0` and defaulting to `J = 1`, `h = 0.5`. This is the isotropic `γ = 0` member of the LMG family `H = −(J/N)(S_x² + γ S_y²) − h S_z`. See `.knowledge/conventions.md`.

## Solvability statement

T6 (collective / large-N): the Hamiltonian is built entirely from components of the **total** spin, so `[S², H] = 0` and `H` is block-diagonal in the total-spin sectors `j`. The ground state lives in the **maximal-spin sector `j = N/2`** (dimension `N+1`): both energy-lowering terms `−(J/N)S_x²` and `−h S_z` are minimized by the largest available spin length (ferromagnetic ordering), so the `(N+1)`-dimensional block carries the GS **exactly at any finite `N`** — an exponential `2^N → N+1` collapse. Quantizing along `x` makes `S_x` diagonal and `S_z` a ladder, so the block is **tridiagonal** and diagonalized to machine precision by `eigh_tridiagonal` for `N` up to millions. In the thermodynamic limit spin-coherent (mean-field) minimization becomes exact and gives closed-form energies in both phases, with a second-order QPT at `h = J`. **Not exact:** nothing is approximate at finite `N` (the block diagonalization is exact); the *closed-form* `e₀(h/J)` and the `N^{−1/3}` critical-gap scaling are thermodynamic-limit statements, approached as `O(1/N)` by the finite-`N` block. This is a Tier-A card: the GS sector is exactly solvable in full, and the whole `j = N/2` spectrum is available from the tridiagonal block.

## The collective-sector reduction

`S²` commutes with `H`, so eigenstates carry a good total spin `j ∈ {N/2, N/2−1, …}`. The identity-proof is numerical and exact: at `N ∈ {8, 10}` the `j = N/2` block ground energy equals the full `2^N` ED ground energy to `< 1e-12`, and the ED ground state carries `⟨S²⟩ = (N/2)(N/2+1)` — it *is* a maximal-spin state, not assumed to be one. The ferromagnetic ordering of sectors is checked directly: at `N = 8` the block minimum rises strictly as `j` drops (`j = 4 < 3 < 2` in energy) at every field, so `j = N/2` wins. The same tridiagonal formula builds any `j`, which is what makes the sector comparison a one-liner.

## Exact results

- Collective ground energy per spin (any `N`): lowest eigenvalue of the tridiagonal block `diagₖ = −(J/N)m_x²`, `offₖ = −(h/2)√(j(j+1)−m_x(m_x+1))`, `j = N/2` [@LipkinMeshkovGlick1965]
- Thermodynamic energy per spin — broken phase `h ≤ J`: `e₀ = −J/4 − h²/(4J)` (at `cos θ = h/J`) [@LipkinMeshkovGlick1965]
- Thermodynamic energy per spin — symmetric phase `h ≥ J`: `e₀ = −h/2` (fully `z`-polarized) [@LipkinMeshkovGlick1965]
- Quantum phase transition: `h = J`, second order — `e₀(h)` is `C¹` but has a second-derivative kink (`−1/(2J)` below, `0` above) [@BotetJullien1983]
- Symmetry-breaking order parameter (broken phase): `⟨S_x⟩/N = ½√(1−(h/J)²)`, vanishing at `h = J`
- Finite-size gap at criticality (`h = J`): closes as `Δ ∼ N^{−1/3}` — **observed** log-fit exponent `≈ −0.32` over `N ∈ {200,400,800,1600}` [@DusuelVidal2005]

## Oracle script

`python oracle.py --N 100 --h 0.5` → prints `e0_per_spin`, `e0_thermodynamic`, `gap`, `sx_order_thermo`, `phase`. Importable: `compute(N=100, h=0.5, J=1.0)`; helpers `collective_block(N,J,h,j)`, `block_lowest(N,J,h,k,j)`, `e0_thermo`, `gap_collective`.
Self-test anchors: (1) **identity-proof** — `j = N/2` block energy `==` full `2^N` ED at `N∈{8,10}` (`1e-12`) and `⟨S²⟩_GS = (N/2)(N/2+1)`; (2) **sector ordering** — block minimum rises with decreasing `j` at `N=8`; (3) **thermodynamic limit** — `N=4000` block matches the closed form `< 1e-4` both phases, deviation halving `2000→4000` (`O(1/N)`); (4) **QPT** — `e₀(h)` is `C¹` (`de₀/dh = −½`) with a second-derivative kink at `h=J`; (5) **critical gap** — `N^{−1/3}` log-fit within `±0.05` of `−1/3`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_thermodynamic` | `h = J` (critical) | `−J/2` | [@LipkinMeshkovGlick1965] |
| `e0_thermodynamic` | broken, `h = 0.5, J = 1` | `−0.3125` | [@LipkinMeshkovGlick1965] |
| `e0_thermodynamic` | symmetric, `h = 1.5, J = 1` | `−0.75` | [@LipkinMeshkovGlick1965] |
| `sx_order_thermo` | broken, `h = 0.5, J = 1` | `√3/4 ≈ 0.4330` | [@LipkinMeshkovGlick1965] |
| critical gap exponent | `h = J`, `N ∈ {200..1600}` | `≈ −1/3` (observed `−0.32`) | [@DusuelVidal2005] |

## Verification recipes

- To check an ED/DMRG run at size `N`: `−(J/N)S_x² − h S_z` is permutation-symmetric, so a correct GS energy equals `oracle.py --N <N> --h <h>`'s `e0_per_spin × N` to `1e-10` (exact) — a mismatch flags a broken permutation symmetry or a stray `j < N/2` projection.
- To check a mean-field / large-`N` claim: compare `e0_per_spin` at large `N` (say `N=2000`) against `e0_thermodynamic`; they must agree to `O(1/N)` (`~1e-4` at `N=2000`, symmetric phase). Do **not** expect exact agreement at finite `N`.
- Cross-reference `curie-weiss-tfim` (the sibling T6 collective card): it is the *same* machinery in Pauli conventions with the Ising axis and field swapped — an independent check of the tridiagonal collective-block method.

## Key reference

[@LipkinMeshkovGlick1965] — Lipkin, Meshkov & Glick's paper I ("Exact solutions and perturbation theory"), the original solvable collective model and source of the exact `j = N/2` reduction and its mean-field limit; [@DusuelVidal2005] for the finite-size scaling exponents (`N^{−1/3}` critical gap). Rendered: bib stub — no PDF reachable (2026-07-14).

# Kramers–Wannier duality — exact-solution oracle

Technique: T7 (dualities & solvable dynamics) · Tier: A (exact duality identity) · Script: S

## Hamiltonian & conventions

$$ \sinh(2K)\,\sinh(2K^\ast) = 1, \qquad \psi(K) - \tfrac12\ln\sinh(2K) \ \text{invariant under } K\leftrightarrow K^\ast $$

Conventions: this card verifies the Kramers–Wannier self-duality of the Ising model as a **checkable identity**, by cross-loading two sibling oracles — no new physics engine is built here. `K = βJ` is the classical reduced coupling; `ψ(K) = (1/N)\ln Z` is the reduced free energy per site (from `ising-2d-onsager`). For the quantum face, `J,h` are the Ising coupling and transverse field of the `tfim-chain` card. See `.knowledge/conventions.md`. Physics relatives: `tfim-chain` and `ising-2d-onsager` (the two sides of the duality), and the `jw-duality-dictionary` pointer card (KW row).

## Solvability statement

T7: Kramers–Wannier duality maps the ordered (low-`T`) and disordered (high-`T`) Ising descriptions onto each other, and its **self-dual fixed point locates the exact critical point**. Two exact, scripted faces:

1. **1D quantum (TFIM chain).** The dispersion `ε(k) = 2\sqrt{J^2 + h^2 − 2Jh\cos k}` is symmetric under `(J,h)↔(h,J)`, so the ground-state energy satisfies `e_0(J,h) = e_0(h,J)` **exactly**, at finite `L` and in the thermodynamic limit. This spectral symmetry is the finite-chain shadow of the KW **bond-algebra** duality — `σ^z_iσ^z_{i+1}` (bond, ordering) ↔ `σ^x` on the dual site (field, disordering), exchanging the ordered/disordered phases, i.e. `J↔h`. The self-dual point `h=J` is the chain's quantum critical point (`Δ = 2|J−h| → 0`).

2. **2D classical (square-lattice Ising).** With the dual coupling `K^\ast` fixed by `\sinh 2K\,\sinh 2K^\ast = 1`, the reduced free energy obeys the exact KW relation `ψ(K) − \tfrac12\ln\sinh 2K = ψ(K^\ast) − \tfrac12\ln\sinh 2K^\ast` (derived below). Its self-dual fixed point `\sinh 2K_c = 1 ⇒ K_c = \tfrac12\ln(1+\sqrt2)` is the exact critical coupling.

**Not exact / out of scope:** the duality relates free energies and locates the critical point but is not itself a solution — the *values* `ψ(K)`, `e_0(J,h)` come from the Onsager and Jordan–Wigner solutions on the sibling cards. Correlator-level statements of the duality (disorder operators, `μ`–`σ` exchange) are not scripted.

## Exact results

- **TFIM spectral duality:** `e_0(J,h) = e_0(h,J)` exactly (residual `< 10^{-12}` at finite `L=16` and in the thermodynamic limit); self-dual/critical point `h = J`. [@KramersWannier1941]
- **Derived KW free-energy relation.** High-`T` (polygon) and low-`T` (domain-wall) expansions of `Z` are the *same* polygon sum `P` at `\tanh K` and at `e^{-2K}`; with `\tanh K^\ast = e^{-2K}` (⇔ `\sinh 2K\,\sinh 2K^\ast = 1`) and the high-`T` form `Z(K) = (2\cosh^2 K)^N P(\tanh K)`, one gets `ψ(K) − ψ(K^\ast) = \tfrac12\ln[\sinh 2K/\sinh 2K^\ast]`. Since `\sinh 2K^\ast = 1/\sinh 2K`, the right side is `\ln\sinh 2K`, so **`g(K) ≡ ψ(K) − \tfrac12\ln\sinh 2K` is a self-dual invariant** — verified against Onsager's `ψ` at `K∈\{0.3,0.6\}` to `10^{-8}`. [@KramersWannier1941]
- **Self-dual critical point:** `\sinh 2K_c = 1 ⇒ K_c = \tfrac12\ln(1+\sqrt2) = 0.4406867935…`, identical to the Onsager card's `K_c = J/T_c` (arithmetic identity, `< 10^{-12}`).

## Oracle script

`python oracle.py --J 1.0 --h 0.7 --K 0.3` → prints `tfim_e0_duality_residual`, `dual_coupling_product`, `kw_free_energy_residual`, `Kc_selfdual`, `Kc_matches_onsager_Tc`. Importable: `compute(J=1.0, h=0.7, K=0.3)`; helpers `dual_coupling(K)`, `kw_free_energy_invariant(psi, K)`, `kc_selfdual()`.
Self-test anchors: (1) `e_0(J,h) = e_0(h,J)` (finite-`L` and thermodynamic) at three `(J,h)` pairs to `10^{-12}`, and the gap vanishes at `h=J`. (2) the derived invariant `g(K) = g(K^\ast)` to `10^{-8}` at `K∈\{0.3,0.6\}` against Onsager's `ψ` (with `\sinh 2K\,\sinh 2K^\ast = 1` to `10^{-12}`), and the invariant is non-trivial (`K≠K^\ast`, `ψ` actually changes). (3) `\sinh 2K_c = 1` and `K_c = \tfrac12\ln(1+\sqrt2) = 1/T_c` from the Onsager card to `10^{-12}`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e_0(J,h) − e_0(h,J)` (TFIM) | `L=16`, any `(J,h)` | `0` (`< 10^{-12}`) | [@KramersWannier1941] |
| self-dual invariant residual `g(K)−g(K^\ast)` | `K∈\{0.3,0.6\}` | `0` (`< 10^{-8}`) | this card (derived) |
| `\sinh 2K\,\sinh 2K^\ast` | any `K` | `1` | [@KramersWannier1941] |
| self-dual coupling `K_c` | `\sinh 2K_c=1` | `\tfrac12\ln(1+\sqrt2)=0.4406867935` | [@KramersWannier1941] |
| `K_c` vs Onsager `J/T_c` | — | equal (`< 10^{-12}`) | this card + `ising-2d-onsager` |

## Verification recipes

- To confirm a 2D-Ising free-energy code respects KW duality: compute `ψ(K)` and `ψ(K^\ast)` with `K^\ast = \tfrac12\operatorname{arcsinh}(1/\sinh 2K)`, and check `ψ(K) − \tfrac12\ln\sinh 2K` is equal at `K` and `K^\ast` to `10^{-8}`. A mismatch usually means the free energy omits the `\tfrac12\ln\sinh 2K` self-dual normalization or uses a different `K↔K^\ast` convention.
- To locate the critical point from duality alone: solve `\sinh 2K_c = 1`; compare against the `tfim-chain` self-dual point `h=J` and the Onsager `T_c`.

## Key reference

[@KramersWannier1941] — H. A. Kramers & G. H. Wannier, "Statistics of the Two-Dimensional Ferromagnet. Part I", Phys. Rev. **60**, 252 (1941): the original duality of the square-lattice Ising model, `\sinh 2K\,\sinh 2K^\ast = 1`, and the self-dual location of the critical point. The Jordan–Wigner solution behind the TFIM face is [@Pfeuty1970]; the Onsager free energy behind the classical face is on the `ising-2d-onsager` card. Rendered: bib stub — no PDF reachable (2026-07-14).

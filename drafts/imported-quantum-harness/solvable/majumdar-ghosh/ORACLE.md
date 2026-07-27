# Majumdar–Ghosh chain — exact-solution oracle

Technique: T5 (frustration-free / exact eigenstates) · Tier: C (exact ground state only) · Script: S

## Hamiltonian & conventions

$$ H = J \sum_{i=1}^{L} \left[ \mathbf{S}_i\cdot\mathbf{S}_{i+1} + \tfrac{1}{2}\,\mathbf{S}_i\cdot\mathbf{S}_{i+2} \right], \qquad \text{PBC } (\mathbf{S}_{L+1}\equiv\mathbf{S}_1) $$

Conventions: spin-½ `S`-operators (`S^a = σ^a/2`), `J=1` antiferromagnetic, `L` a multiple of 4. This is the special point `J₂/J₁ = 1/2` of the frustrated `J₁`–`J₂` chain — the Majumdar–Ghosh point. See `.knowledge/conventions.md`.

Physics card: the `J₁`–`J₂` chain lives in the model zoo as `.knowledge/models/j1-j2`; the MG point is its exactly-solvable special case. Same `S`-operator convention.

## Solvability statement

T5 (frustration-free / exact eigenstates): at `J₂/J₁ = 1/2` the two nearest-neighbour dimer coverings — the singlet product `|D_A⟩` on bonds `(1,2)(3,4)…` and `|D_B⟩` on bonds `(2,3)(4,5)…(L,1)` — are **exact** ground states with energy `E₀ = −3JL/8`. Each singlet contributes `⟨S_i·S_j⟩ = −3/4`; the frustrating next-nearest-neighbour term annihilates a dimer product because any spin sits on a triangle with the two members `a,b` of a neighbouring singlet, and `(S_a+S_b)` annihilates that singlet (total spin 0), so the extra bonds cost nothing. The ground space is **exactly 2-fold** (the two coverings, which become orthogonal and degenerate as `L→∞`), and `E₀/L = −3/8` is exact for every `L∈4ℤ`. **Not exact:** everything except the ground state. Only these two dimer states are exact eigenstates — the rest of the spectrum, the excitations (deconfined spinons / a triplet continuum), and the spin gap are **not** closed-form; the gap is positive but known only numerically (ED `≈ 0.32` at `L=12`, this convention). This is a genuine Tier-C card: the exact content is the ground state, not the spectrum.

## The exact dimer story

Write `H` as a sum over three-site groups: for consecutive sites `(i−1,i,i+1)`, group the couplings so each group contains one NN and one NNN bond. On a dimer covering, every such group acts on a spin that is paired into a singlet with one of the other two, and the combination `S_i·(S_{i-1}+S_{i+1})` sees the singlet's `S_{i-1}+S_{i+1}=0` — the group energy is a constant. Summing the constants gives exactly `−3JL/8`, independent of which of the two coverings is used, so both are degenerate exact ground states. The MG point is the canonical toy model for **spontaneous dimerization**: the two-fold ground degeneracy breaks translation by one site, and the elementary excitations are domain walls between the two coverings (spinons).

## Exact results

- Ground energy per site: `e₀ = −3J/8` (exact at the MG point); total `E₀ = −3JL/8` [@MajumdarGhosh1969]
- Ground-state degeneracy: `2` — the two nearest-neighbour dimer coverings [@MajumdarGhosh1969]
- Exact ground states: `|D_A⟩ = ∏_{k} [1,2k−1;2k]_{\rm singlet}` and its one-site translate `|D_B⟩` [@MajumdarGhosh1969]
- Spin gap: positive but **not closed form** — numerical only (ED `≈ 0.32` at `L=12`, this convention)

## Oracle script

`python oracle.py --L 12` → prints `e0_per_site` (`−3/8`), `e0_total` (`−3L/8`), `ground_degeneracy` (`2`), `gap_ed` (numerical spin gap). Importable: `compute(L=12, J=1.0)`; helpers `mg_H(L, J)`, `singlet_product_state(pairs, L)`, `dimer_coverings(L)`.

Self-test anchors: (1) **ground truth** — ED gives `E₀/L == −3/8` to `1e-12` and a 2-fold ground space at `L∈{8,12}`; (2) both dimer coverings are **operator-level** exact eigenstates — `‖H|D⟩ − E|D⟩‖ < 1e-12` with `E = −3L/8` — and the two states span the ED ground space (projector-overlap check to `1e-10`); (3) the spin gap is positive at `L=12`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_per_site` | MG point, `L∈4ℤ` | `−3/8` | [@MajumdarGhosh1969] |
| `e0_total` | `L=12` | `−9/2` | [@MajumdarGhosh1969] |
| `ground_degeneracy` | PBC, `L∈4ℤ` | `2` | [@MajumdarGhosh1969] |
| `gap_ed` | `L=12` (numerical) | `≈ 0.319` (not closed form) | ED (this card) |

## Verification recipes

- To check a DMRG/ED run at the MG point (`J₂/J₁ = 1/2`, PBC): the ground energy per site must equal `−3/8` exactly (tolerance `1e-8`), with a 2-fold ground space; a run that lands above `−3L/8` or reports a unique ground state is misconfigured (wrong `J₂`, wrong boundary, or a symmetry-restricted sector).
- To check dimerization: the exact ground states are nearest-neighbour singlet products, so `⟨S_i·S_{i+1}⟩` alternates between `−3/4` (intra-dimer) and `0` (inter-dimer) in either covering.
- Do **not** compare a measured spin gap to a closed form — there is none; use the numerical `gap_ed` at matched `L`.

## Key reference

[@MajumdarGhosh1969] — Majumdar & Ghosh, "On Next-Nearest-Neighbor Interaction in Linear Chain. I", the paper that identifies the `J₂/J₁ = 1/2` point and proves the two dimer coverings are the exact doubly-degenerate ground states (the companion Paper II, J. Math. Phys. 10, 1399, works out the degeneracy in detail). Rendered: bib stub — no PDF reachable (2026-07-14).

# Shastry–Sutherland dimer model — exact-solution oracle

Technique: T5 (frustration-free / exact eigenstates) · Tier: C (exact ground state only) · Script: S

## Hamiltonian & conventions

$$ H = J \sum_{\langle ij\rangle_{\text{square NN}}} \mathbf{S}_i\cdot\mathbf{S}_j \;+\; J' \sum_{\langle ij\rangle_{\text{dimer}}} \mathbf{S}_i\cdot\mathbf{S}_j $$

Conventions: spin-½ `S`-operators (`d=2`); **`J` is the square-lattice nearest-neighbour coupling and `J'` the dimer (diagonal) coupling**. The control ratio is `J/J'` (dimer phase at small `J/J'`). Both couplings antiferromagnetic. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/shastry-sutherland/MODEL.md`. That card uses the **same** letter convention (`J` square NN, `J'` dimer) and the same ratio `J/J'`; its exact-dimer benchmark `E/spin = −3J'/8` and boundary `J/J' ≈ 0.675` are quoted identically here. No convention translation is needed between the two cards. Corboz–Mila [@CorbozMila2013] also use this labelling (`J'` intra-dimer, transition at `J/J' = 0.675(2)`). One caveat: the *original* Shastry–Sutherland and Miyahara–Ueda papers swap the letters — their `J` is the dimer coupling and their transition reads `(J'/J)_c ≈ 0.7`.

## Solvability statement

T5 (frustration-free / exact eigenstates): the orthogonal-dimer geometry makes the dimer-singlet product `|Ψ⟩ = ∏_{\rm dimers}|{\rm singlet}⟩` an **exact** eigenstate of the *full* `H` for **all** `J/J'`, with energy `E = −(3/4)\,J'\,N_{\rm dimer}` (per spin `−3J'/8`). The proof is the orthogonality miracle: every square-lattice bond attaches an external spin to *both* members of a neighbouring singlet, so its two contributions combine into `J\,S_c·(S_a+S_b)` and vanish on the singlet (`S_a+S_b=0`) — the `J` bonds contribute exactly zero and only the `J'` dimer bonds count (`−3/4` each). This exact eigenstate is the **ground state only in the dimer phase** (small `J/J'`); above a level crossing the ground state is a *different, non-exact* state (plaquette-singlet, then Néel). **Not exact:** everything except the dimer state. The generic spectrum, the competing plaquette/Néel ground states, the triplet dispersion, and the transition point are all **numerical** — the exact-dimer→plaquette boundary is `J/J' = 0.675(2)` in the thermodynamic limit [@CorbozMila2013], quoted from the literature, not derived here. This is a genuine Tier-C card: only the dimer product state is exact, and only in part of the phase diagram.

## The cluster (documented)

The smallest cluster that faithfully realises the orthogonal-dimer connectivity under periodic boundaries is the **`4×4 = 16`-site torus** (8 dimers). Sites sit on a `4×4` square lattice whose nearest-neighbour edges are the `J` bonds; the `J'` dimer bonds are diagonals on the checkerboard of plaquettes (lower-left corner `x+y` even), oriented NE for `x` even and NW for `x` odd — an orthogonal-dimer perfect matching. Smaller tori (e.g. `4×2`) break the dimer orthogonality across the wrap, and there the dimer product is *not* an eigenstate (verified: residual `∼0.5`), so 16 sites is the minimal faithful choice. On this cluster the dimer state is the ED ground state up to a level crossing at `J/J' ≈ 0.667` — close to the thermodynamic `0.675`, a nice finite-size accident.

## Exact results

- Dimer-state energy: `E = −(3/4)\,J'\,N_{\rm dimer}`, i.e. `−3J'/8` per spin, **for all `J/J'`** [@ShastrySutherland1981]
- The dimer-singlet product is an exact eigenstate of the full `H` for arbitrary `J/J'` (orthogonality miracle) [@ShastrySutherland1981]
- It is the exact ground state in the dimer phase; on the 16-site torus the level crossing is at `J/J' ≈ 0.667` (observed), thermodynamic dimer→plaquette boundary `J/J' = 0.675(2)` [@CorbozMila2013]
- Everything else (excitations, plaquette/Néel phases, transition) is **not** closed-form — numerical

## Oracle script

`python oracle.py --J 0.5` → prints `e_dimer_exact` (`−(3/4)J'N_dimer = −6` on the 16-site cluster), `e_dimer_per_spin` (`−3J'/8`), `e0_ed` (ED ground energy at `J/J'`), `dimer_is_ground_state` (bool). Importable: `compute(J=0.5, Jp=1.0)`; helpers `ss_bonds()`, `ss_H(dimer, square, J, Jp)`, `singlet_product_state(pairs, L)`, `dimer_energy(Jp)`.

Self-test anchors: (1) the 8 dimer bonds form a perfect matching of the 16 sites; (2) the dimer product is an **operator-level** exact eigenstate for `J/J' ∈ {0.3,0.5,0.9}` — `‖H|Ψ⟩ − E|Ψ⟩‖ < 1e-12` with `E = −6` independent of `J`; (3) **ground truth** — at `J=0` (isolated dimers) the dimer product is the *unique* ground state with `E₀ = −6` (ED); (4) it *is* the ED ground state at `J/J' = 0.5` (dimer phase) but *not* at `J/J' = 0.9` (`E₀ < −6`), i.e. the level crossing is real.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e_dimer_per_spin` | any `J/J'`, `J'=1` | `−3/8` | [@ShastrySutherland1981] |
| `e_dimer_exact` | 16-site cluster, `J'=1` | `−6` (`= −¾·8`) | [@ShastrySutherland1981] |
| `dimer_is_ground_state` | `J/J' = 0.5` / `0.9` | `True` / `False` | ED (this card) |
| dimer→plaquette boundary | thermodynamic | `J/J' = 0.675(2)` | [@CorbozMila2013] |

## Verification recipes

- To check a DMRG/ED run in the dimer phase (`J/J' < 0.675`): the ground energy per spin must equal `−3J'/8` **exactly** (tolerance `1e-8`), independent of `J` — this is the sharpest possible check, since the dimer energy does not disperse with `J`. A run whose dimer-phase energy drifts with `J/J'` has the wrong bond assignment (dimer vs square swapped) or a non-faithful cluster.
- To check the exact-eigenstate property away from the ground state: build the dimer-singlet product explicitly and confirm `H|Ψ⟩ = −(3/4)J'N_dimer|Ψ⟩` at any `J/J'` (residual `< 1e-10`).
- Do **not** treat the transition point as exact — the dimer→plaquette boundary `0.675(2)` is numerical (iPEPS/series); on a finite cluster you will see a level crossing at a size-dependent value (`≈ 0.667` at 16 sites).

## Key reference

[@ShastrySutherland1981] — Shastry & Sutherland's original proof that the orthogonal-dimer antiferromagnet has an exact dimer-singlet ground state (in their paper the dimer coupling is labelled `J`; this card follows the model card's labelling, where it is `J'`); the thermodynamic dimer→plaquette boundary `0.675(2)` is the iPEPS result of Corboz & Mila [@CorbozMila2013]. Rendered: bib stub — no PDF reachable (2026-07-14).

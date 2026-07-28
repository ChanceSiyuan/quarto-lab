# Falicov–Kimball model, `d=∞` (DMFT-exact) — exact-solution oracle

Technique: T6 (collective / large-N / random) · Tier: D (exact in a limit) · Script: T

## Hamiltonian & conventions

$$ H = -t\sum_{\langle ij\rangle}\big(c^\dagger_i c_j + \text{h.c.}\big) + U\sum_i n^c_i\,n^f_i $$

Conventions: spinless itinerant `c`-electrons hopping with amplitude `t>0` (energy unit `t=1`; in DMFT the scaled `t^*=t\sqrt{Z}` is held fixed as coordination `Z→∞`), interacting via on-site repulsion `U>0` with **localized, immobile `f`-electrons** whose occupations `n^f_i∈\{0,1\}` are static classical variables (`[H,n^f_i]=0` for every `i` — an extensive set of conserved quantities). `⟨ij⟩` = nearest-neighbour bonds counted once. Half-filling means `ρ_c=ρ_f=½`. This is the model-zoo entry `models/falicov-kimball` (same object, same `H=-t\sum c^\dagger c+U\sum n^c n^f` normalisation). See `.knowledge/conventions.md`.

## Model identification (read this first)

"Falicov–Kimball" spans finite-dimensional lattices (studied by sign-free Monte Carlo over `f`-configurations) and the **infinite-dimensional limit**, where it becomes **exactly solvable by dynamical mean-field theory** (DMFT) — the first non-trivial correlated model for which DMFT is exact [@BrandtMielsch1989; @FreericksZlatic2003]. This card pins that DMFT-exact `d=∞` statement plus a small-`L` ED reference computed once for this card. It is a **T-flag** card: there is no `oracle.py`, because the exact `d=∞` results (`T_c(U)`, spectral gaps) live in the DMFT literature under several DOS/normalisation conventions and no single web-verifiable number in *this* card's bare `t` units was pinned; instead we ship exact **finite-`L` ED reference numbers** in fully specified conventions.

## Solvability statement

T6 / **Tier D** (exact in `d=∞`): because each `n^f_i` is conserved, tracing out the `f`-electrons leaves, for every frozen `f`-configuration, a **free-fermion** `c`-problem — the partition function is a *classical* sum over `f`-configurations of free-fermion determinants (manifestly positive, hence **sign-free**). In the limit `Z→∞` the `c`-electron self-energy becomes **purely local**, and the lattice problem collapses onto a single-site impurity coupled to a self-consistent bath that **closes exactly** [@BrandtMielsch1989]: the DMFT equations are not an approximation but the exact `d=∞` solution. This yields the exact `c`-spectral function, the metal–insulator transition (the DOS splits into lower/upper sub-bands separated by a gap `≈U` at large `U`), and the checkerboard charge-density-wave transition temperature `T_c(U)` [@FreericksZlatic2003]. **Not exact in finite `d`:** finite-dimensional Falicov–Kimball is not integrable (though still sign-free); the DMFT solution and the closed-form results below are `d=∞` statements. The finite-`L` numbers pinned here are exact ED references for a specific cluster, **not** thermodynamic or `d=∞` values.

## No oracle script — tabulated results and a pinned ED reference

**Exact `d=∞` (DMFT) facts** [@BrandtMielsch1989; @FreericksZlatic2003]:

- On a bipartite lattice at half-filling (`ρ_c=ρ_f=½`), the `T=0` ground state is the **checkerboard charge-density wave**: the `f`-electrons order on one sublattice for **any** `U>0`.
- A CDW ordering temperature `T_c(U)>0` separates the ordered checkerboard phase from the disordered high-`T` phase; `T_c(U)` is **non-monotonic** — it rises then falls, peaking at intermediate `U`.
- At large `U` the `c`-density of states splits into lower/upper Hubbard-like sub-bands with a **charge gap `≈U`** — a `U`-driven metal–insulator transition.
- The `f`-spectral function is a **delta function** (the `f`-electrons never hop); all `c`-dynamics is captured by the local self-energy `Σ_c(ω)`.

**Pinned finite-`L` ED reference (this card).** A short **`L=6` spinless chain**, PBC, `t=1`, on-site `c`–`f` repulsion `U`, **both species at half-filling** (`N_c=N_f=3`). Because the `f`-occupations are static, the exact ground state is obtained by **annealing**: for each of the `\binom{6}{3}=20` `f`-configurations, the `c`-electrons are free fermions in the binary on-site potential `U\,n^f_i`, so the `c`-ground energy is the sum of the `3` lowest eigenvalues of the `6×6` matrix `h_{ij}=-t(\delta_{j,i+1}+\delta_{j,i-1})_{\text{PBC}}+U\,n^f_i\,\delta_{ij}`; the reported ground energy is the **minimum over all 20 `f`-configurations**. **Identity-proof:** at `U=2` the annealing minimum is achieved by the **checkerboard** `f`-configuration `(n^f=101010)` — the finite-`L` echo of the exact `d=∞` checkerboard CDW. (Computed once for this card, scratch script not shipped — the recipe above is complete and reproducible.)

## Benchmarks

`E_0` = total `c`-electron ground energy of the annealed (optimal-`f`) state, `t=1`, `L=6`, PBC, `N_c=N_f=3`.

| Quantity | Params | Value | Source |
|---|---|---|---|
| annealed GS `E_0` | `U=0` (free) | `-4.0000000000` | finite-`L` ED reference, this card |
| annealed GS `E_0` | `U=2` | `-2.0644951022` | finite-`L` ED reference, this card |
| annealed GS `E_0` | `U=4` | `-1.3005630797` | finite-`L` ED reference, this card |
| optimal `f`-config | `U=2` | **checkerboard `101010`** | this card (identity-proof) |
| `T=0` order (bipartite, half-filling) | `d=∞`, any `U>0` | checkerboard CDW (exact) | [@BrandtMielsch1989; @FreericksZlatic2003] |
| CDW `T_c(U)` | `d=∞`, half-filling | `>0`, non-monotonic in `U` | [@FreericksZlatic2003] |
| `c`-charge gap | `d=∞`, large `U` | `≈U` (band splitting) | [@FreericksZlatic2003] |

The `U=0` value `-4` is the free `c`-band check: the `L=6` PBC hopping spectrum is `\{-2,-1,-1,1,1,2\}` and the `3` lowest sum to `-4` (every `f`-config degenerate at `U=0`). The `U=2,4` numbers are exact ED references for *this* cluster — pinned, unambiguous check values, **not** extrapolations to `d=∞` or to `L→∞`.

## Verification recipes

- **To check a finite-`L` Falicov–Kimball code (ED or Monte-Carlo-over-`f`-configs):** reproduce `E_0(U=2)=-2.0644951022` and `E_0(U=4)=-1.3005630797` on the `L=6`, PBC, `N_c=N_f=3` chain by (a) enumerating the `20` `f`-configurations, (b) diagonalising the `6×6` free-fermion `c`-matrix `-t(\text{PBC hop})+U\,\mathrm{diag}(n^f)` for each, (c) summing the `3` lowest `c`-levels, (d) taking the minimum. A mismatch usually means a convention slip — `f`-filling `≠3`, OBC vs PBC, `U` on the wrong term, or forgetting that the ground state *anneals* over `f` (the optimal `f` is the checkerboard, not the first enumerated config).
- **Sign-free check:** every `f`-configuration must give a real free-fermion determinant with positive weight — no Monte Carlo sign should ever appear; confirm before trusting `f`-config averages.
- **Symmetry check:** each `n^f_i` must be exactly conserved (`[H,n^f_i]=0`) — the defining static-`f` structure; the `c`-charge U(1) is also conserved.
- **`d=∞` limit checks:** on a bipartite lattice at half-filling the `T=0` ground state must be the checkerboard CDW for any `U>0`, and the `c`-charge gap must grow `≈U` at large `U`. Cross-reference `models/falicov-kimball` for the DMFT/Monte-Carlo method routing.

## Key reference

[@FreericksZlatic2003] — J. K. Freericks & V. Zlatić, "Exact dynamical mean-field theory of the Falicov–Kimball model", Rev. Mod. Phys. **75**, 1333 (2003): the authoritative review of the DMFT-exact `d=∞` solution — formalism, the checkerboard CDW transition `T_c(U)`, and the metal–insulator physics. The exactness of DMFT for this model is Brandt–Mielsch [@BrandtMielsch1989]; the model originates with Falicov–Kimball [@FalicovKimball1969]. Rendered: ./10-1103-revmodphys-75-1333.md.

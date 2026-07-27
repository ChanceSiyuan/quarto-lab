# Rokhsar–Kivelson quantum dimer model — exact-solution oracle

Technique: T5 (frustration-free / exact eigenstates) · Tier: C (exact ground state only) · Script: S

## Hamiltonian & conventions

$$ H_{\rm RK} = \sum_{\square}\Big[\,-t\,\big(|{=}\rangle\langle{\|}| + |{\|}\rangle\langle{=}|\big) \;+\; v\,\big(|{=}\rangle\langle{=}| + |{\|}\rangle\langle{\|}|\big)\Big], \qquad t=v=1 $$

Conventions: hard-core dimer (perfect-matching) Hilbert space on the `L×L` **square-lattice torus**; `|=⟩` is the plaquette state with its two **horizontal** edges dimerised, `|‖⟩` with its two **vertical** edges. A plaquette is *flippable* in a covering iff it is in `|=⟩` or `|‖⟩`; the kinetic term flips `= ↔ ‖`, the potential term counts flippable plaquettes. The RK point is `t = v` (energy unit `t=1`). Cluster: the `4×4` torus (16 sites, 32 edges, 272 coverings). See `.knowledge/conventions.md`.

Scope: the **RK point is a single special slice** of the QDM phase diagram. Away from `t=v` nothing on this card is exact — the square-lattice QDM columnar/plaquette/staggered phases, and the deconfined U(1) liquid of the *triangular*-lattice QDM, are cited [@RokhsarKivelson1988; @MoessnerSondhi2001], not derived here.

## Solvability statement

T5 (frustration-free / exact eigenstates): at the RK point each plaquette term factorises as `h_□ = (|=⟩−|‖⟩)(⟨=|−⟨‖|)`, a **rank-1 positive-semidefinite** operator (expand: `v(|=⟩⟨=|+|‖⟩⟨‖|) − t(|=⟩⟨‖|+|‖⟩⟨=|)` at `t=v`). Hence `H_RK = Σ_□ h_□ ≥ 0` is frustration-free with spectrum floor `E ≥ 0` (verified numerically: min eigenvalue `≈ −3e-15` on the `4×4` torus). The **equal-weight superposition** of the coverings in any flip-connected set is an **exact `E=0` ground state**: for every plaquette the local move pairs a `=`-covering with its `‖`-partner at equal amplitude, so `(⟨=|−⟨‖|)|\psi⟩ = 1−1 = 0` term by term. Winding numbers `(W_x,W_y)` — signed counts of dimers crossing a reference cut, cut-independent and preserved by every flip — block-diagonalise `H`, and the equal-weight state of **each** winding sector is a zero-energy state. **Not exact:** everything except this ground manifold at `t=v`. The gap, the excited spectrum, the columnar↔plaquette↔staggered transitions of the square-lattice QDM, and the triangular-lattice deconfined liquid are **not** closed-form — numerical / cited. This is a genuine Tier-C card: exact only at one point, and only the ground states there.

## The exact RVB / RK↔classical story

The RK ground states are the archetypal short-range **resonating valence bond** (RVB) states: an equal-amplitude superposition of dimer coverings. The **load-bearing exact statement** is that the equal-weight superposition is a zero-energy eigenstate — that is the nontrivial frustration-free physics, checked operator-level per sector. *Given* that state, the classical mapping follows as an **algebraic identity**: dimer occupations are diagonal in the covering basis, so any equal-time diagonal observable in a uniform state over a covering set equals the classical equal-weight ensemble average over the same set by construction, `⟨ψ_RK|n_b n_{b'}|ψ_RK⟩ = (1/Z)\sum_{\rm cov} n_b\,n_{b'}`. That identity — not an independent numeric cross-validation — is why the equal-time dimer correlations at the RK point are literally those of the classical dimer model (on the square lattice, the critical power-law Kasteleyn correlations in the thermodynamic limit). This card asserts the identity on the `4×4` torus (all bond pairs, `< 1e-12`) as an *implementation* check of the basis bookkeeping, with the `E=0` property carried by its own anchors.

## Ground-state degeneracy (observed)

On the `4×4` torus the exact zero-energy count is **`GSD = 17`**, decomposed by the block structure as follows — this is *not* equal to the number of winding sectors (`13`):

- **13 nonempty winding sectors** with populations `(0,0):132`, `(±1,0),(0,±1):32` each, `(±1,±1):2` each, `(±2,0),(0,±2):1` each (`132+4·32+4·2+4·1 = 272`).
- **12 fully-frozen coverings** in total (a frozen covering has no flippable plaquette, so `H|c⟩=0` trivially and it is its own zero-energy eigenstate): **8** in the four `(±1,±1)` corner sectors — 2 per sector, which is what splits those sectors into two flip-components each — plus **4** maximally-tilted staggered singletons filling the `(±2,0),(0,±2)` sectors.
- **5 resonating sectors** — `(0,0)` and `(±1,0),(0,±1)` — each a single flip-connected cluster → one equal-weight `E=0` state each.
- Total `12 + 5 = 17` zero modes (confirmed by ED and by counting flip-connected components).

The `≠` between `17` and `13` is the physically honest statement: the RK ground manifold is the resonating sectors **plus** the frozen configurations.

## Exact results

- Frustration-free at the RK point: `H_RK = Σ_□ h_□` with each `h_□ = (|=⟩−|‖⟩)(⟨=|−⟨‖|) ≥ 0`, so `E ≥ 0` [@RokhsarKivelson1988]
- Ground states: equal-weight RVB superposition per flip-connected set, all at `E = 0` [@RokhsarKivelson1988]
- `4×4` torus: `272` dimer coverings; `13` winding sectors; `GSD = 17` (observed, see above)
- RK↔classical: equal-time dimer correlators in `|ψ_RK⟩` equal classical dimer-ensemble averages — an algebraic diagonal-observable identity once the uniform state is a GS (the `E=0` property is the load-bearing exact statement) [@RokhsarKivelson1988]
- **Not exact:** the gap, excited spectrum, and QDM phase diagram (square-lattice ordered phases; triangular-lattice deconfined liquid — cited [@MoessnerSondhi2001])

## Oracle script

`python oracle.py` → prints `n_coverings` (`272`), `n_winding_sectors` (`13`), `gsd_zero_modes` (`17`, from ED), `gsd_flip_components` (`17`, from graph connectivity), `spectrum_floor` (`≈0⁻`). Only the `4×4` torus is implemented: `--L_arg` accepts `4` and raises a clear error for any other value. Importable: `compute(L_arg=4)`; helpers `dimer_coverings(order)`, `count_coverings_permanent()`, `winding(cov)`, `rk_hamiltonian(covs)`, `equal_weight_state(...)`, `sectors(covs)`, `ground_state_degeneracy(covs)`.

Self-test anchors: (1) **ground truth** — `272` coverings on the `4×4` torus by *three* independent methods (two backtracking orders + Ryser permanent of the `8×8` biadjacency), each a genuine perfect matching; (2) winding `(W_x,W_y)` is **cut-independent** (checked at every cut) and flip-preserved (→ block-diagonal `H`); (3) **projector form** — `E ≥ 0` and `H` rebuilt exactly as a sum of per-pair rank-1 PSD blocks; (4) the equal-weight state of **each** of the 13 sectors is an **operator-level** `E=0` state (`‖H|ψ⟩‖ < 1e-12`); (5) `GSD = 17` from ED equals the flip-connected-component count, with the frozen-covering census asserted exactly — `12` fully-frozen coverings total, `2` in each `(±1,±1)` sector and `1` in each `(±2,0),(0,±2)` sector, plus the `5` resonating sectors each one cluster; (6) **single-plaquette hand check** — `H=[[1,−1],[−1,1]]`, flip element `⟨=|H|‖⟩=−1`, eigenvalues `{0,2}`; (7) the full equal-weight state (all 272 coverings) is itself an `E=0` zero mode — the load-bearing part — and the RK↔classical dimer-correlator equality is then asserted to `1e-12` as an *algebraic-identity implementation check* (diagonal observables in a uniform state; uniform bond density `1/4`), not as an independent cross-validation.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `n_coverings` | `4×4` torus | `272` | this card (3 methods) |
| `n_winding_sectors` | `4×4` torus | `13` | this card |
| `gsd_zero_modes` | `4×4` torus, RK point | `17` (observed) | ED (this card) |
| `spectrum_floor` | RK point | `≥ 0` (frustration-free) | [@RokhsarKivelson1988] |
| dimer correlators | `4×4` torus, `\|ψ_RK⟩` | `=` classical dimer average (identity) | [@RokhsarKivelson1988] |

## Verification recipes

- To check a QDM code at the RK point: the equal-weight superposition of dimer coverings in any winding sector must be a zero-energy eigenstate to machine precision (`‖H|ψ⟩‖ < 1e-10`), and the spectrum floor must be `≥ 0`. A run reporting a negative ground energy at `t=v` has a sign error in the flip term.
- To check dimer coverings / sector counts on the `4×4` torus: `272` coverings, `13` winding sectors; the exact RK ground-state degeneracy is `17` (resonating sectors **plus** frozen configurations) — do **not** assume `GSD` equals the number of topological sectors.
- To check the RK↔classical mapping: measure an equal-time dimer-dimer correlator in the RK ground state and compare to a classical Monte-Carlo dimer average on the same lattice — they must agree (diagonal observable). Any discrepancy indicates the state is not the true RK point (`t≠v`) or is not equal-weight.
- Do **not** treat anything away from `t=v` as exact — the square-lattice ordered phases and the triangular-lattice deconfined liquid are numerical/cited, not closed-form.

## Key reference

[@RokhsarKivelson1988] — Rokhsar & Kivelson introduced the quantum dimer model and the exactly-solvable RK point where the ground states are the equal-weight RVB superpositions and the equal-time correlations reduce to the classical dimer ensemble; [@MoessnerSondhi2001] established the deconfined RK liquid on the triangular lattice (cited for scope, not scripted). Rendered: bib stub — no PDF reachable (2026-07-14).

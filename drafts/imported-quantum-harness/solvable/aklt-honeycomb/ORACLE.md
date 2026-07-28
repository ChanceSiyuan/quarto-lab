# Honeycomb (spin-3/2) AKLT — exact-solution oracle

Technique: T5 (frustration-free / exact ground state) · Tier: C (exact ground state only) · Script: P (partial — floor + explicit VBS on a minimal torus; correlations & gap tabulated)

## Hamiltonian & conventions

$$ H = \sum_{\langle ij\rangle} P^{(3)}_{ij}, \qquad P^{(3)}_{ij}=\frac{(\mathbf S_i\!\cdot\!\mathbf S_j+\tfrac{15}{4})(\mathbf S_i\!\cdot\!\mathbf S_j+\tfrac{11}{4})(\mathbf S_i\!\cdot\!\mathbf S_j+\tfrac{3}{4})}{90} $$

Conventions: spin-`3/2` (`d=4`, `S^z=+\tfrac32,\tfrac12,-\tfrac12,-\tfrac32`) on the **honeycomb lattice** (coordination `z=3`); on each bond `P^{(3)}` projects the pair onto its total-spin-`3` channel, built from the pair Casimir `\mathbf S_i\!\cdot\!\mathbf S_j` whose eigenvalues are `x_{S'}=\tfrac12[S'(S'{+}1)-\tfrac{15}{2}]=\{-\tfrac{15}4,-\tfrac{11}4,-\tfrac34,+\tfrac94\}` for `S'=0,1,2,3` (multiplicities `1,3,5,7`). Coupling set to the energy unit. Scriptable cluster: the smallest honeycomb **torus** feasible for spin-`3/2` ED — the `2\times2`-unit-cell cluster, `8` sites (`4^8=65536`), `12` bonds, every site degree `3`, no self-loops/multi-edges. See `.knowledge/conventions.md`. Physics card: `.knowledge/models/aklt/MODEL.md` (the 1D sibling; this card is the 2D honeycomb VBS). Cross-read `aklt-chain` (the spin-1 chain exemplar).

## Solvability statement

T5 (frustration-free / exact ground state), Tier C: since every bond projector `P^{(3)}\ge0`, `H=\sum P^{(3)}\ge0` has spectrum floor `E\ge0` (a **frustration-free** parent Hamiltonian). The honeycomb **valence-bond solid** — put three virtual spin-`\tfrac12`'s on each site (one per bond) and symmetrise to spin-`\tfrac32`, and place a singlet on every bond — caps the total spin of any bond at `2`, so it carries **zero** total-spin-`3` weight and is annihilated by every `P^{(3)}`: it is an **exact `E=0` ground state** [@AKLT1988]. This card verifies that exactly on the `8`-site torus: (i) sparse ED gives ground energy `E_0\approx6\times10^{-16}` (the frustration-free floor `0` to `1e-10`) with spectrum floor `E\ge0`, a *unique* zero-energy ground state, and a positive gap `\approx0.092` on this cluster (numerical, finite-size); and (ii) the **explicit VBS/PEPS state is constructed** (contracting the bond singlets through the on-site spin-`3/2` symmetrisers) and shown to be annihilated at operator level, `\|H|\psi\rangle\|\approx7\times10^{-16}<1e-10`, and to coincide with the ED ground state (overlap `1`). **Not exact / P-scope:** everything except the ground state at this point. The thermodynamic-limit correlation functions, the disordered (no Néel) nature of the state, and — crucially — the **nonzero spectral gap** are *not* reproduced here; the gap in particular is a hard theorem, proved only in 2020 [@PomataWei2020; @LemmSandvikWang2020], and is **tabulated with citations**, not scripted. The small torus's `0.092` gap is a finite-cluster number, not the proven thermodynamic gap.

## The exact VBS / PEPS story

The honeycomb AKLT state is the paradigmatic 2D **projected-entangled-pair state** (PEPS): a bond singlet is the "entangled pair", and the on-site map projecting `(\tfrac12)^{\otimes3}\to\tfrac32` is the "P". Each bond joins one virtual spin-`\tfrac12` from each of its two sites into a singlet; that singlet caps the two sites' *shared* spin so the bond's total spin can never reach `3`, and `P^{(3)}` annihilates the state **bond by bond** — the defining frustration-free property, checked here operator-level. This state is a gapped, disordered (no broken symmetry, exponentially decaying spin correlations) 2D analogue of the Haldane phase; it is the canonical **universal resource for measurement-based quantum computation** on the honeycomb. What the ED cluster demonstrates honestly is the exact zero-energy annihilation; the long-distance physics (finite correlation length, nonzero gap) is the content of the cited theorems.

## Exact results

- Frustration-free: `H=\sum_{\langle ij\rangle}P^{(3)}_{ij}\ge0`, spectrum floor `E\ge0` [@AKLT1988]
- Exact ground state: the honeycomb VBS is annihilated by every `P^{(3)}` → `E_0=0` (verified `1e-10`; explicit PEPS `\|H|\psi\rangle\|<1e-10`) [@AKLT1988]
- `8`-site torus (observed): `E_0=0`, unique GS, finite-cluster gap `\approx0.092` (numerical)
- **Nonzero spectral gap (thermodynamic limit): PROVEN** — a genuine theorem, tabulated not scripted [@PomataWei2020; @LemmSandvikWang2020]
- Disordered ground state with exponentially decaying spin correlations (finite correlation length); 2D Haldane/SPT analogue and MBQC resource — tabulated [@AKLT1988]

## Oracle script

`python oracle.py --L_arg 2` (only the `2\times2` torus is scripted; other values raise) → prints `n_sites` (`8`), `n_bonds` (`12`), `e0` (`\approx0`), `spectrum_floor_nonneg` (`True`), `gsd_observed` (`1`), `gap_observed` (`\approx0.092`, numerical), `vbs_energy`/`vbs_residual` (`\approx0`, the explicit PEPS check). Importable: `compute(L_arg=2)`; helpers `pair_projector_S3()`, `honeycomb_2x2_bonds()`, `honeycomb_H()`, `vbs_state()`, `spin32_ops(N)`.

Self-test anchors: (1) **geometry + projector** — `12` unique bonds, every site degree `3`, no multi-edges; `P^{(3)}` is idempotent with trace `7` (`=\dim` of the `S=3` sector), and `\mathbf S_i\!\cdot\!\mathbf S_j` has eigenvalues `\{-\tfrac{15}4,-\tfrac{11}4,-\tfrac34,+\tfrac94\}` with multiplicities `\{1,3,5,7\}`; (2) **frustration-free floor (ground truth)** — sparse ED gives `E_0=0` to `1e-10`, `E\ge0`, unique GS, positive gap; (3) **explicit VBS (operator-level)** — the constructed PEPS state satisfies `\|H|\psi\rangle\|<1e-10` and equals the ED ground state (overlap `1`).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `spectrum_floor` | honeycomb, any size | `E\ge0` (frustration-free) | [@AKLT1988] |
| `e0` | `2×2` torus (`8` sites) | `0` | [@AKLT1988] |
| `vbs_residual` `\|Hψ\|` | explicit PEPS, `8` sites | `0` (`<1e-10`) | [@AKLT1988] |
| `gsd_observed` | `2×2` torus | `1` (unique) | ED (this card) |
| `gap_observed` | `2×2` torus (numerical) | `≈0.092` (finite-size, not the theorem) | ED (this card) |
| spectral gap | thermodynamic limit | nonzero (**proven**) — tabulated | [@PomataWei2020; @LemmSandvikWang2020] |

## Verification recipes

- To check a 2D AKLT / PEPS code: build the honeycomb VBS and confirm every bond `P^{(3)}` annihilates it (`\|H|\psi\rangle\|` at machine precision) and that the parent Hamiltonian's ground energy is `0` with `E\ge0`. A negative eigenvalue means the bond term is not the pure `S=3` projector (check the Casimir normalisation `/90`).
- To check spin-`3/2` operators: `\mathbf S_i\!\cdot\!\mathbf S_j` must have the four Casimir eigenvalues `\{-15/4,-11/4,-3/4,9/4\}` with multiplicities `\{1,3,5,7\}`, and `P^{(3)}` must be idempotent with trace `7`.
- Do **not** read a spectral gap off a small cluster: the `\approx0.092` here is a finite-`8`-site number. The *existence* of a nonzero thermodynamic gap is a theorem [@PomataWei2020; @LemmSandvikWang2020], not a closed-form value — compare against the literature, not against this cluster's gap.

## Key reference

[@AKLT1988] — Affleck, Kennedy, Lieb & Tasaki's long paper constructing the valence-bond-solid ground states on general lattices, including the honeycomb spin-`3/2` model verified here. [@PomataWei2020] and [@LemmSandvikWang2020] independently proved (back-to-back, PRL 124, 2020) the nonzero spectral gap of the 2D honeycomb AKLT model — the tabulated theorem this P-scope card cites rather than scripts. Rendered: bib stub — no PDF reachable (2026-07-14).

# AKLT spin-1 chain — exact-solution oracle

Technique: T5 (frustration-free / exact eigenstates) · Tier: C (exact ground state only) · Script: S

## Hamiltonian & conventions

$$ H = \sum_{i=1}^{L} \left[ \mathbf{S}_i\cdot\mathbf{S}_{i+1} + \tfrac{1}{3}\left(\mathbf{S}_i\cdot\mathbf{S}_{i+1}\right)^2 \right], \qquad \text{PBC } (\mathbf{S}_{L+1}\equiv\mathbf{S}_1) $$

Conventions: spin-1 `S`-operators (`d=3`, `S^z = +1,0,-1`); the biquadratic coefficient is fixed at `1/3` (the AKLT point); coupling set to the energy unit `J=1`. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/aklt/MODEL.md`. That card uses the **same** spin-1 `S`-operator convention and the same `H = Σ [S_i·S_{i+1} + ⅓(S_i·S_{i+1})²]` form, and quotes the identical exact anchors (`E/N = −2/3`, string order magnitude `4/9`, correlation length `ξ = 1/ln 3`). No convention translation is needed between the two cards.

## Solvability statement

T5 (frustration-free / exact eigenstates): on each bond the local term equals `2P₂ − 2/3`, where `P₂` projects the bond onto total spin 2 (for two spin-1's the bilinear-plus-⅓-biquadratic form takes the value `4/3` in the spin-2 channel and `−2/3` in the spin-0 and spin-1 channels, i.e. `2P₂ − 2/3`). So `H = 2Σ_bond P₂ − 2N/3` with `P₂ ≥ 0` and `N = L` bonds (PBC). The valence-bond-solid (VBS) state — the exact bond-dimension-2 matrix-product state with `A^{+}=√(2/3)σ^+`, `A^{0}=−√(1/3)σ^z`, `A^{−}=−√(2/3)σ^-` — carries zero weight in every bond's spin-2 channel, so it is annihilated by every `P₂` and is the **exact** ground state with energy `E₀ = −2N/3`. It is unique on the periodic chain and 4-fold degenerate with open boundaries (two emergent spin-½ edge modes). What is exact is fully closed-form: the ground energy `−2/3` per site, the two-point function `⟨S^z_iS^z_{i+r}⟩ = (4/3)(−1/3)^r`, and the string order `O^z = −4/9`, all read off the 2×2 transfer matrix (eigenvalues `1, −1/3`). **Not exact:** everything except the ground state. The generic excited spectrum is *not* solvable in closed form, and in particular the Haldane gap above the VBS is **not** a closed-form quantity — it is only known numerically (ED `≈ 0.70` on the `L=8` PBC cluster reported here; the rigorous lower bound of AKLT/Knabe is a bound, not the gap). This is a genuine Tier-C card: only the ground state (and its exact correlators) is exact, not the spectrum.

## The exact VBS / MPS story

Put a spin-½ "Schwinger boson" pair on each site and project onto the site's `S=1` symmetric subspace; link neighbouring sites by a singlet (a valence bond). The result is the AKLT VBS, written as a periodic MPS `|ψ⟩ = Σ_{\{m\}} \mathrm{Tr}(A^{m_1}\cdots A^{m_L})\,|m_1\dots m_L⟩` with the three 2×2 matrices above. Because a valence bond caps the total spin of any bond at 1, the state has no spin-2 weight on any bond and is annihilated term-by-term by `Σ P₂` — the defining *frustration-free* property. The 2×2 transfer matrix `E = Σ_m A^m\otimes \bar A^m` has eigenvalues `{1, −1/3, −1/3, −1/3}`; the subdominant `−1/3` sets both the exponential decay of `⟨S^z_iS^z_{i+r}⟩` (correlation length `ξ = 1/\ln 3`) and, through the `e^{iπS^z}`-decorated transfer matrix, the non-vanishing string order that diagnoses the hidden `Z₂×Z₂` order of the Haldane phase.

## Exact results

- Ground energy per site: `e₀ = −2/3` (exact, VBS); total `E₀ = −2L/3` on the `L`-bond periodic chain [@AKLT1987]
- Ground-state degeneracy: `1` (PBC); `4` (OBC — two spin-½ edge modes) [@AKLT1987]
- Spin correlator: `⟨S^z_iS^z_{i+r}⟩ = (4/3)(−1/3)^r` (`r ≥ 1`); full `⟨\mathbf{S}_i·\mathbf{S}_{i+r}⟩ = 4(−1/3)^r`; correlation length `ξ = 1/\ln 3 ≈ 0.910` [@AKLT1987]
- String order parameter: `O^z = \lim_{|i-j|→∞} ⟨S^z_i\,e^{iπ\sum_{i<k<j}S^z_k}\,S^z_j⟩ = −4/9` [@AKLT1987]
- Haldane gap: **not closed form** — numerical only (ED `≈ 0.700` at `L=8` PBC, this convention; thermodynamic value `≈ 0.35 J` from DMRG in the literature)

## Oracle script

`python oracle.py --L 8` → prints `e0_per_site` (`−2/3`), `e0_total_pbc` (`−2L/3`), `szsz_r1` (`−4/9`), `szsz_r2` (`4/27`), `string_order` (`−4/9`), `gap_pbc_ed` (numerical Haldane gap at `L`). Importable: `compute(L=8)`; helpers `aklt_H(L, pbc)`, `aklt_mps_state(L)`, `szsz_correlator(r)`, `string_order()`.

Self-test anchors: (1) **ground truth** — PBC `E₀ == −2L/3` and unique GS at `L∈{6,8}` by ED; (2) OBC `L=6` gives `E₀ = −2·5/3` with 4-fold GS; (3) the explicit MPS state is an **operator-level** exact eigenstate — `‖H|ψ⟩ − E|ψ⟩‖ < 1e-10` with `E = −2L/3`, and `|⟨ψ_MPS|ψ_ED⟩| = 1`; (4) the transfer-matrix correlator equals `(4/3)(−1/3)^r` to `1e-12` for `r=1..4`, and the finite-`L=8` trace formula matches the direct MPS-state expectation to `1e-10`; (5) the string order equals `−4/9` to `1e-12`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_per_site` | AKLT point, any `L` | `−2/3` | [@AKLT1987] |
| `szsz_r1` = `⟨S^z_iS^z_{i+1}⟩` | infinite chain | `−4/9` | [@AKLT1987] |
| `szsz_r2` = `⟨S^z_iS^z_{i+2}⟩` | infinite chain | `4/27` | [@AKLT1987] |
| `string_order` `O^z` | infinite chain | `−4/9` | [@AKLT1987] |
| GS degeneracy | PBC / OBC | `1` / `4` | [@AKLT1987] |
| Haldane gap | `L=8` PBC (numerical) | `≈ 0.700` (not closed form) | ED (this card) |

## Verification recipes

- To check a DMRG/MPS run: the AKLT ground state is an exact `χ=2` MPS, so DMRG must converge to `E/L = −2/3` to machine precision at bond dimension `2` — failure flags a setup error. Compare `⟨S^z_iS^z_{i+r}⟩` against `(4/3)(−1/3)^r` and the string order against `−4/9` (tolerance `1e-8`).
- To check an ED run at size `L`, PBC: compare the ground energy against `−2L/3` (exact) and confirm the GS is unique; with OBC expect a 4-fold near-degenerate ground manifold (the spin-½ edges).
- Do **not** compare a measured Haldane gap to a closed form — there is none; use the numerical `gap_pbc_ed` at matched `L` (finite-size) or the literature thermodynamic `≈ 0.35 J`.

## Key reference

[@AKLT1987] — Affleck, Kennedy, Lieb & Tasaki's rigorous construction of the valence-bond ground state, the proof of the spectral gap, the exponentially decaying correlations, and the hidden topological (string) order used above. Rendered: bib stub — no PDF reachable (2026-07-14).

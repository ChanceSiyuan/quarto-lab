# PXP quantum many-body scars — exact-solution oracle

Technique: T5 (exact eigenstates embedded in a chaotic spectrum) · Tier: C (a few exact eigenstates only) · Script: S

## Hamiltonian & conventions

$$ H = \sum_{j} P_{j-1}\,X_j\,P_{j+1}, \qquad P=|0\rangle\langle 0|,\; X=\sigma^x,\; |0\rangle=g,\;|1\rangle=r $$

Conventions: constrained Rydberg-blockade chain, `|0\rangle=g` (ground), `|1\rangle=r` (Rydberg); `X=\sigma^x` flips (Rabi unit `\Omega=1`), `P=|0\rangle\langle0|=1-n` projects a neighbour onto its ground state, so a spin flips only if **both** neighbours are in `|0\rangle` (infinite blockade → no two adjacent excitations). **OBC** with boundary terms `X_1P_2` and `P_{N-1}X_N` (the missing-neighbour ends carry a single projector) — this matches `.knowledge/models/rydberg-pxp/MODEL.md` exactly (`\Delta=0` pure PXP point). See `.knowledge/conventions.md`. Physics card: `models/rydberg-pxp` (same projector-dressed drive, the `|Z_2\rangle`-quench scar story, Fibonacci Hilbert space).

## Solvability statement

T5 (exact eigenstates), Tier C: PXP is **non-integrable** (Wigner–Dyson bulk, ETH) yet hosts a handful of **exact eigenstates** — quantum many-body scars — that violate ETH. The kinematics are exact combinatorics: the blockade restricts the Hilbert space to bitstrings with no two adjacent `1`s, of dimension `F_{N+2}` (OBC Fibonacci) and `L_N` (PBC Lucas) — verified against a direct enumerator for `N\le 14` (e.g. `N=12`: `377=F_{14}` OBC, `322=L_{12}` PBC). Lin–Motrunich [@LinMotrunich2019] found **exact** scar eigenstates as low-bond-dimension matrix product states: block two physical sites `(2b,2b{+}1)` into one block-site with allowed states `O=(00)` and the two single-excitation states, and use the **bond-dimension-2** MPS `|\Gamma_{a,b}\rangle=\sum v_a^{\mathsf T}A^{s_1}\cdots A^{s_{N/2}}v_b|s\rangle` with `A^{O}=\bigl[\begin{smallmatrix}0&-1\\1&0\end{smallmatrix}\bigr]`, the two excitation matrices `\bigl[\begin{smallmatrix}\sqrt2&0\\0&0\end{smallmatrix}\bigr]` (for block `(1,0)`) and `\bigl[\begin{smallmatrix}0&0\\0&-\sqrt2\end{smallmatrix}\bigr]` (for `(0,1)`) — the assignment fixed by the blockade (the product vanishes on forbidden adjacencies) — and boundary vectors `v_1=(1,1)^{\mathsf T}`, `v_2=(1,-1)^{\mathsf T}`. Then `|\Gamma_{1,1}\rangle,|\Gamma_{2,2}\rangle` are exact `E=0` eigenstates and `|\Gamma_{1,2}\rangle,|\Gamma_{2,1}\rangle` are exact `E=\pm\sqrt2` eigenstates **in this `X=\sigma^x` convention** — verified at `N=8,12` OBC as operator-level eigenstates (`\|H|\Gamma\rangle-E|\Gamma\rangle\|<1e-10`). **Not exact:** everything else. These few MPS states are the only closed-form eigenstates; the rest of the spectrum is thermal. The scars are the mechanism of the `|Z_2\rangle`-quench revivals but the revival dynamics itself, the approximate `su(2)` tower, and the bulk spectrum are numerical, not closed-form.

## The scar story — weak ergodicity breaking (identity-proof)

A scar is not just "an eigenstate" — the honest claim is that it is an **ETH outlier**. The eigenstate thermalisation hypothesis predicts that all eigenstates at a given energy density look thermal, with **volume-law** half-chain entanglement entropy. The `E=+\sqrt2` scar instead has `S_{L/2}=\ln 2` **exactly** (its bond dimension is 2 → at most `\ln 2` of entanglement across any cut), whereas the mean half-chain entropy of the `52` eigenstates in the narrow window `|E-\sqrt2|<0.5` at `N=12` is `\approx 1.90` — the scar sits a factor `\approx 2.7` below the thermal mean (observed). That gap is the quantitative fingerprint of **weak ergodicity breaking**: a measure-zero set of athermal states embedded in an otherwise thermalising spectrum. A second exact structure: PXP has a chiral (sublattice) symmetry `C=\prod_j\sigma^z_j` that anticommutes with `H` (the drive changes the excitation number by one), forcing an `E\to-E` spectrum and an exponentially large `E=0` degeneracy set by the even/odd sublattice imbalance of the constrained graph — `13` exact zero modes at `N=12` OBC (observed; grows exponentially with `N`) [@LinMotrunich2019]. Both diagnostics are how one *proves* scarring rather than asserting it.

## Exact results

- Constrained dimension: `F_{N+2}` (OBC), `L_N` (PBC) — combinatorial, verified `N\le 14` [@serbyn_2020_quantum]
- Exact scars (Lin–Motrunich MPS, OBC, `N` even, bond dim 2): `E=\pm\sqrt2` (`|\Gamma_{1,2}\rangle,|\Gamma_{2,1}\rangle`) and `E=0` (`|\Gamma_{1,1}\rangle,|\Gamma_{2,2}\rangle`), operator-level `<1e-10` at `N=8,12` [@LinMotrunich2019]
- Scar entanglement: `S_{L/2}=\ln 2` exactly (bond dimension 2) — an ETH outlier vs the thermal-window mean `\approx 1.90` at `N=12` [@LinMotrunich2019]
- `E=0` zero-mode degeneracy: `13` at `N=12` OBC (observed; exponential in `N`, chiral-symmetry protected) [@LinMotrunich2019]
- **Not exact:** the bulk spectrum (chaotic/ETH), the `|Z_2\rangle`-quench revival period, and the approximate scar tower — numerical only.

## Oracle script

`python oracle.py --N 12` → prints `dim_constrained_obc` (`377=F_{14}`), `fibonacci_F_Nplus2`, `dim_constrained_pbc` (`322=L_{12}`), `lucas_L_N`, `E_scar_plus`/`E_scar_minus`/`E_scar_zero` (`\pm\sqrt2,0`), and `eth_*` (scar entropy `\ln2`, window-mean entropy, window count, `n_zero_modes`). Importable: `compute(N=12)`; helpers `pxp_H(N,pbc)`, `constrained_dim(N,pbc)`, `fibonacci/lucas`, `scar_state(N,a,b)`, `half_chain_entropy`, `eth_outlier(N)`.

Self-test anchors: (1) **combinatorial ground truth** — `constrained_dim == F_{N+2}` (OBC) and `L_N` (PBC) for `N=2..14`; (2) **exact scars, operator-level** — the Lin–Motrunich MPS states are eigenstates with `\|H|\Gamma\rangle-E|\Gamma\rangle\|<1e-10`, `E\in\{+\sqrt2,-\sqrt2,0\}`, at `N=8,12`, and `\pm\sqrt2` appear in the constrained spectrum to `1e-10`; (3) the `\pm\sqrt2` scars are mutually orthogonal and orthogonal to the `E=0` scars; (4) **identity-proof (ETH outlier)** — at `N=12` the `+\sqrt2` scar's half-chain entropy is below half the mean of the `\ge5`-state window `|E-\sqrt2|<0.5`, and `\ge10` exact `E=0` zero modes are present (chiral).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `dim_constrained_obc` | `N=12` OBC | `377` `= F_{14}` | [@serbyn_2020_quantum] |
| `dim_constrained_pbc` | `N=12` PBC | `322` `= L_{12}` | [@serbyn_2020_quantum] |
| `E_scar_plus` / `E_scar_minus` | `N=8,12` OBC, `X=σ^x` | `\pm\sqrt2` | [@LinMotrunich2019] |
| `eth_scar_entropy` | `N=12`, `+\sqrt2` scar | `\ln 2 ≈ 0.693` (vs mean `≈1.90`) | [@LinMotrunich2019] |
| `eth_n_zero_modes` | `N=12` OBC | `13` (observed) | [@LinMotrunich2019] |

## Verification recipes

- To check a PXP code: the constrained Hilbert-space dimension must equal `F_{N+2}` (OBC) or `L_N` (PBC) — the direct check that the blockade is imposed correctly. A `2^N` count means the constraint is missing.
- To check the exact scars: build the bond-dimension-2 MPS above and confirm `H|\Gamma\rangle=E|\Gamma\rangle` at machine precision with `E=\pm\sqrt2` (for `X=\sigma^x`; if your `X=\sigma^x/\sqrt2` the eigenvalues rescale to `\pm1`). A nonzero residual flags a boundary-term or basis-labelling error.
- To *prove* scarring (not just find an eigenstate): show the candidate is an entanglement/overlap **outlier** — its half-chain entropy far below the thermal mean in its energy window, and (dynamically) `|Z_2\rangle`-quench revivals absent for a generic product state (the negative control in `models/rydberg-pxp`).

## Key reference

[@LinMotrunich2019] — Lin & Motrunich construct the exact `E=\pm\sqrt2` (and `E=0`) PXP scar states as finite-bond-dimension matrix product states and analyse the chiral-symmetry zero modes — the transcription anchored above. [@serbyn_2020_quantum] is the pedagogical scar/weak-ergodicity-breaking review (used for the Fibonacci-dimension and quench context). Rendered: ./1810.00888_exact-quantum-many-body-scar-states-in-the-rydberg-blockaded.md.

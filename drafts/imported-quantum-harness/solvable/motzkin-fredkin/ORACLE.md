# Motzkin spin-1 chain (Fredkin variant) — exact-solution oracle

Technique: T5 (frustration-free / exact eigenstates) · Tier: C (exact ground state only) · Script: S

## Hamiltonian & conventions

$$ H = \sum_{j=1}^{n-1}\Pi_{j,j+1} \;+\; |d\rangle\langle d|_1 \;+\; |u\rangle\langle u|_n, \qquad \Pi_{j,j+1}=\sum_{k=1}^{3}|D_k\rangle\langle D_k| $$

with `|D_1⟩=(|u0⟩−|0u⟩)/√2`, `|D_2⟩=(|0d⟩−|d0⟩)/√2`, `|D_3⟩=(|ud⟩−|00⟩)/√2`.

Conventions: colorless **spin-1** sites with basis `{u,0,d}` mapped to walk steps `{+1,0,−1}`; a length-`n` state is a lattice walk (partial sums), and a **Motzkin walk** stays `≥ 0` and ends at height `0`. The bulk projectors enforce equal amplitude under the local moves `u0↔0u`, `0d↔d0`, `ud↔00`; the boundary terms `|d⟩⟨d|_1` and `|u⟩⟨u|_n` forbid a leading down-step / trailing up-step, pinning both ends to height `0`. Energy unit set by the projector normalisation. See `.knowledge/conventions.md`.

## Solvability statement

T5 (frustration-free / exact eigenstates): `H` is a sum of projectors (`Π_{j,j+1} ≥ 0` and boundary projectors `≥ 0`), so `H ≥ 0` and any state annihilated by every term has `E=0`. The bulk moves connect all height-`≥0` walks with the same endpoints at equal amplitude, and the boundary terms select endpoints `0→0`; the **unique** common zero of all terms is therefore the **uniform superposition of all Motzkin walks** of length `n`, `|GS⟩ ∝ Σ_{\rm Motzkin}|walk⟩`, with `E_0 = 0`. Uniqueness is genuine (verified: the second-lowest ED eigenvalue is `> 0` at `n∈{4,6,8}`; the gap closes only polynomially in `1/n` [@BravyiEtAl2012]). The number of Motzkin walks is the **Motzkin number** `M_n = 1,1,2,4,9,21,51,127,323,…`. **Not exact:** everything except the ground state. The excited spectrum and the exact gap are **not** closed-form (only the `1/\mathrm{poly}(n)` scaling is proven), and the half-chain entanglement — computed exactly here from path-counting Schmidt weights — grows like `~(1/2)\ln n + O(1)` [@BravyiEtAl2012], reported observed-as-observed, not as a fitted exponent. A genuine Tier-C card: exact ground state (and its exact Schmidt spectrum), not the spectrum.

## The exact Motzkin ground state & its entanglement

Cut the chain in half (at `n/2`). The Schmidt decomposition of `|GS⟩` is **diagonal in the height `h` at the cut**: a Schmidt block for each `h`, with weight `p_h = N(n/2,h)^2 / M_n`, where `N(L,h)` counts length-`L` height-`≥0` walks from `0` to `h` (left half), and by reflection `h→0` (right half). The identity `Σ_h N(n/2,h)^2 = M_n` makes the weights an exact probability distribution and the entropy `S = −Σ_h p_h\ln p_h` a pure-combinatorics quantity available at **any** `n` (no ED). This is the mechanism behind `S ~ (1/2)\ln n`: the cut height performs an unbiased random walk of `O(\sqrt n)` spread, so its entropy grows logarithmically — the first frustration-free translation-invariant spin-1 chain with a **critical** (log-entangled) unique ground state [@BravyiEtAl2012].

## Fredkin (spin-½ Dyck) variant

The Fredkin chain [@SalbergerKorepin2017] is the spin-½ analogue: sites `{↑,↓}` = steps `{+1,−1}`, ground state the uniform superposition of **Dyck paths** (balanced up/down walks, counted by the Catalan numbers `C_m = 1,1,2,5,14,42,…`), enforced by correlated 3-site moves plus boundary pins. It shares the `~(1/2)\ln n` half-chain entropy. Because Dyck paths have no flat step, the midpoint height is pinned to the parity of `n/2`, so the finite-size entropy **oscillates between parity classes** but is monotone within one — this card checks the Dyck Catalan counts, `Σ_h D(n/2,h)^2 = C_{n/2}`, and monotone entropy growth along `n=4,8,12,16,20` (all combinatorics, no ED). Deformations of the Fredkin/Motzkin chains reach even `√n` entanglement [@SalbergerKorepin2017].

## Exact results

- Ground energy `E_0 = 0`, frustration-free (`H = Σ` projectors); ground state = uniform Motzkin-walk superposition, **unique** [@BravyiEtAl2012]
- Motzkin numbers `M_n = 1,1,2,4,9,21,51,127,323,835,2188,…` = dimension of the (trivially 1-dim) ground space combinatorics = number of zero-energy walks [@BravyiEtAl2012]
- Half-chain entanglement entropy exact from Schmidt weights `p_h = N(n/2,h)^2/M_n`; grows monotonically, `~(1/2)\ln n + O(1)` (observed) [@BravyiEtAl2012]
- Fredkin (spin-½): Dyck-path ground state, Catalan counts, same `~(1/2)\ln n` law (tabulated + combinatorics) [@SalbergerKorepin2017]
- **Not exact:** the gap (only `1/\mathrm{poly}(n)` proven) and the excited spectrum

## Oracle script

`python oracle.py --n 8` → prints `motzkin_number` (`M_n`), `gs_residual` (`‖H|GS⟩‖`), `e0` (`≈0`), `gap` (second ED eigenvalue `>0` ⇒ unique), `half_chain_entropy`. Importable: `compute(n=8)`; helpers `motzkin_number(n)`, `motzkin_walks(n)`, `motzkin_H(n)`, `motzkin_gs(n)`, `half_chain_entropy(n)`, `catalan(m)`, `fredkin_half_entropy(n)`.

Self-test anchors: (1) `M_n` recursion values `1,1,2,4,9,21,51,127,323,835,2188` and the explicit walk enumerator produces `M_n` walks for `n≤10`; (2) **ground truth** — the uniform Motzkin state is an **operator-level** `E=0` state (`‖H|GS⟩‖ < 1e-12`) and **unique** (ED gap `>0`), overlap `1` with the ED ground vector, for `n∈{4,6,8}`; (3) Schmidt structure — `Σ_h N(n/2,h)^2 = M_n` for `n∈{4,6,8,10,12}`, and the combinatorial half-chain entropy equals the entropy of the ED ground state's reduced density matrix at `n=8` (`1e-10`); (4) entanglement grows monotonically across `n=4,6,8,10,12` (pure combinatorics), tracking `~(1/2)\ln n`; (5) Fredkin — Catalan counts `1,1,2,5,14,42,132,429`, `Σ_h D(n/2,h)^2 = C_{n/2}`, monotone Dyck entropy along `n=4,8,12,16,20`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `motzkin_number` | `n=8` | `323` | [@BravyiEtAl2012] |
| `e0` | any `n` | `0` (frustration-free) | [@BravyiEtAl2012] |
| GS uniqueness | `n∈{4,6,8}` | unique (gap `>0`) | ED (this card) |
| `half_chain_entropy` | `n=8` (Motzkin) | `≈ 1.2206` | this card (exact Schmidt) |
| entropy law | `n→∞` | `~(1/2)\ln n + O(1)` (observed) | [@BravyiEtAl2012] |
| Fredkin Dyck count | `n=8` | `C_4 = 14` | [@SalbergerKorepin2017] |

## Verification recipes

- To check a DMRG/ED code on the Motzkin chain: the uniform superposition of Motzkin walks must be a zero-energy ground state to machine precision (`‖H|GS⟩‖ < 1e-10`), unique, with `E_0 = 0`. A run whose ground energy is negative has a sign error in a projector; a degenerate ground space means a boundary term is missing (the pins `|d⟩⟨d|_1`, `|u⟩⟨u|_n` are what make it unique).
- To check entanglement growth: compute the half-chain entropy and compare to the exact Schmidt values `p_h = N(n/2,h)^2/M_n` (tolerance `1e-8`); it must **grow with `n`** (a saturating entropy signals the code found a non-critical state). Compare the trend, not a fitted coefficient, to `(1/2)\ln n`.
- For the Fredkin (spin-½) chain: use Catalan counts and the parity caveat — compare finite-size entropies only within a fixed parity of `n/2`.
- Do **not** treat the gap as closed-form — only the `1/\mathrm{poly}(n)` scaling is known.

## Key reference

[@BravyiEtAl2012] — Bravyi, Caha, Movassagh, Nagaj & Shor, "Criticality without Frustration for Quantum Spin-1 Chains", the colorless Motzkin chain with a unique, critically-entangled (`~½\ln n`) frustration-free ground state and a `1/\mathrm{poly}(n)` gap; [@SalbergerKorepin2017] introduced the spin-½ Fredkin (Dyck-path) analogue. Rendered: ./1203.5801_criticality-without-frustration-for-quantum-spin-1-chains.md.

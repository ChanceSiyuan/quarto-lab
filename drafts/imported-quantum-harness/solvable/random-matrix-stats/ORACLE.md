# Random-matrix spectral statistics — exact-solution oracle

Technique: T6 (collective / large-N / random) · Tier: A (closed-form, exact) · Script: S

## Hamiltonian & conventions

$$ \rho(e_1,\dots,e_N)=C_{\beta,N}\!\!\prod_{i<j}|e_i-e_j|^{\beta}\prod_i e^{-\beta e_i^2/2}, \qquad \beta=1\,(\text{GOE}),\;2\,(\text{GUE}),\;4\,(\text{GSE}) $$

Conventions: this card has no single Hamiltonian — it is the **random-matrix ensembles** whose eigenvalue joint distribution is written above, with Dyson index `β = 1` (real symmetric, GOE), `2` (complex Hermitian, GUE), `4` (quaternion self-dual, GSE), plus the **Poisson** (integrable) case of uncorrelated levels. The observables are the **level-spacing statistics**: the nearest-neighbour spacing `s = e_{n+1}-e_n` (unfolded to mean spacing 1) and, crucially, the **ratio of consecutive spacings** `r_n = s_n/s_{n-1}` and its folded form `r̃ = min(r,1/r)` [@OganesyanHuse2007]. `r̃` requires **no unfolding** (it is independent of the local density of states), which is why it is the workhorse chaos/MBL diagnostic. See `.knowledge/conventions.md`. No model-zoo sibling — this card is the harness's shared level-statistics oracle, used by any ED/MBL/chaos run that reports a mean adjacent-gap ratio (e.g. `mbl-disordered-heisenberg`, `pxp-scars`).

## Solvability statement

T6 (random): the classical Gaussian ensembles are exactly characterised at the level of their spectral correlation functions. Two closed-form ingredients are pinned here. **(1) Wigner spacing surmise:** the `2×2` result `P_β(s) = a_β s^{β} e^{-b_β s^2}` is, to <1% deviation, the large-`N` nearest-neighbour spacing distribution [@Wigner1951]; the two constants `a_β, b_β` are fixed uniquely by imposing unit normalisation `∫P ds = 1` and unit mean spacing `∫sP ds = 1` — the oracle **re-derives them numerically to 1e-8**. **(2) Ratio surmise:** Atas–Bogomolny–Giraud–Roux [@AtasEtAl2013] computed the exact `3×3` distribution `P(r) = Z_β^{-1}(r+r^2)^{β}/(1+r+r^2)^{1+3β/2}` and the mean `⟨r̃⟩`; the **Poisson** value `⟨r̃⟩ = 2\ln 2 - 1` is exact (integrable levels), while the three Gaussian ensembles give the numerical large-matrix values `0.5307/0.5996/0.6744`. **Tier A:** the spacing/ratio distributions are known in closed form; the sampled anchors are exact realisations of these ensembles, and the GSE construction is a genuine quaternionic self-dual matrix whose Kramers doubling is proven numerically before deduplication.

## The GSE construction and its Kramers identity-proof

The GSE requires the **quaternionic self-dual** structure, not just "complex Hermitian with some symmetry". The oracle builds a `2N×2N` complex matrix whose `2×2` blocks encode quaternions `q_0+q_1 i+q_2 j+q_3 k → [[q_0+iq_1,\,q_2+iq_3],[-q_2+iq_3,\,q_0-iq_1]]`, off-diagonal blocks random with the Hermitian-conjugate block transposed, diagonal blocks real scalars `× I_2`. **Identity-proof (asserted before use):** every eigenvalue is exactly two-fold (Kramers) degenerate — the largest within-pair gap of the sorted spectrum is `< 1e-9` — after which the pairs are deduplicated to give the `N` distinct GSE levels. **Negative control:** a naive GUE matrix of the same size does *not* exhibit the doubling (within-pair gaps `> 1e-3`), so the doubling check discriminates a true GSE from a mislabelled GUE. Diagonalising a GSE matrix with a plain `eigvalsh` and forgetting to deduplicate **halves** the effective density and biases `⟨r̃⟩` — this card handles it correctly and tests it.

## Exact results

- Wigner spacing surmise (mean spacing 1): `P_1(s)=(π/2)s\,e^{-πs^2/4}`, `P_2(s)=(32/π^2)s^2 e^{-4s^2/π}`, `P_4(s)=(2^{18}/(3^6π^3))s^4 e^{-64s^2/9π}` — constants fixed by `∫P=∫sP=1` [@Wigner1951]
- Ratio surmise `P(r)=Z_β^{-1}(r+r^2)^β/(1+r+r^2)^{1+3β/2}`, `Z_1=8/27`, `Z_2=4π/81\sqrt3`, `Z_4=4π/729\sqrt3` [@AtasEtAl2013]
- Poisson mean ratio **exact**: `⟨r̃⟩ = 2\ln 2 - 1 = 0.386294\ldots` (derived: `⟨r̃⟩=2∫_0^1 r/(1+r)^2\,dr`) [@AtasEtAl2013; @OganesyanHuse2007]
- Surmise mean ratios: `⟨r̃⟩_1 = 4-2\sqrt3`, `⟨r̃⟩_2 = 2\sqrt3/π-1/2`, `⟨r̃⟩_4 = 32\sqrt3/15π-1/2` [@AtasEtAl2013]
- Numerical large-matrix mean ratios (the band targets): GOE `0.5307`, GUE `0.5996`, GSE `0.6744` [@AtasEtAl2013]

## Oracle script

`python oracle.py --ensemble GSE` → prints `rtilde_sampled`, `rtilde_target`, `in_band`, plus the exact Poisson value and the surmise/numeric constant tables. Importable: `compute(ensemble, size, n_real, seed)`; helpers `surmise_spacing(s,β)`, `surmise_ratio(r,β)`, `sampled_rtilde(ensemble, ...)`, `_gse`, `_max_pair_gap`.
Self-test anchors: (1) **Wigner surmise constants** — `∫P=1` and `∫sP=1` to `1e-8` for `β∈{1,2,4}` (this is what fixes `a_β,b_β`); (2) **ratio surmise** normalises to 1 (Atas `Z_β`); (3) **Poisson** `⟨r̃⟩=2\ln2-1` to `1e-12`; (4) **GSE identity-proof** — quaternion construction is Kramers-doubled (`<1e-9`) while a GUE negative control is not (`>1e-3`); (5) **sampled bands** — GOE/GUE/GSE/Poisson `⟨r̃⟩` land in their `±4σ` bands at a fixed seed; (6) **reproducibility** — a fixed seed is bit-identical.

**Stochastic anchors.** Sampled `⟨r̃⟩` is averaged over the spectrum bulk (outer 15% of levels dropped for edge-density variation) across `n_real` realisations at a fixed seed. Default sizes: GOE `800×25`, GUE `600×25`, GSE `350×20` (a `700×700` complex diagonalisation after doubling), Poisson `3000×20`. The run-to-run spread was measured across 5 dev seeds: `σ =` 0.0016 (GOE), 0.0019 (GUE), 0.0031 (GSE), 0.0002 (Poisson), so `4σ =` 0.006/0.008/0.012/0.001. Bands are centred on the web-verified numeric target with half-widths `0.010/0.010/0.013/0.004` — each `≥ 4σ` plus the small finite-size centring offset — and one seed is fixed in the self-test.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `⟨r̃⟩` Poisson | integrable levels | `2\ln2-1 = 0.386294` (exact) | [@AtasEtAl2013] |
| `⟨r̃⟩` GOE | `β=1`, large matrix | `0.5307` (surmise `4-2\sqrt3=0.53590`) | [@AtasEtAl2013] |
| `⟨r̃⟩` GUE | `β=2`, large matrix | `0.5996` (surmise `0.60266`) | [@AtasEtAl2013] |
| `⟨r̃⟩` GSE | `β=4`, large matrix | `0.6744` (surmise `0.67617`) | [@AtasEtAl2013] |
| sampled `⟨r̃⟩` GSE | `n=350`, 20 real, seed 1 | `0.675` (in `0.6744±0.013`) | this card (measured) |
| Kramers pair-gap | GSE `n=350` | `<1e-9` (doubling exact) | this card (identity-proof) |
| GUE pair-gap (control) | `n=400` | `>1e-3` (no doubling) | this card (negative control) |
| Wigner surmise norm/mean | `β∈{1,2,4}` | `∫P=∫sP=1` to `1e-8` | this card [@Wigner1951] |

## Verification recipes

- **To check a level-statistics / chaos diagnostic from an ED run:** compute the mean adjacent-gap ratio `⟨r̃⟩` over the spectrum bulk *within a single symmetry sector* (resolve translation / parity / spin first — mixing sectors destroys the correlations and pulls `⟨r̃⟩` toward the Poisson `0.3863`). A chaotic (thermalising) sector gives `0.5307` (GOE, time-reversal-symmetric) or `0.5996` (GUE, broken T); an integrable or localised sector gives `2\ln2-1=0.3863`. This is the standard MBL/ETH order parameter — see `mbl-disordered-heisenberg`, `pxp-scars`.
- **To check a spacing-distribution histogram:** unfold to unit mean spacing, then compare against the Wigner surmise `P_β(s)` here; the peak position and the small-`s` level repulsion `P∼s^β` fingerprint the ensemble (`β=1,2,4`). Poisson gives `P(s)=e^{-s}` (no repulsion).
- **GSE trap:** if a code reports `⟨r̃⟩≈0.6744` **only after** you have deduplicated a Kramers-doubled spectrum, it is genuinely GSE; a spectrum that gives `0.6744` *without* any doubling is suspect (likely a mis-unfolding). Always verify the exact two-fold degeneracy first, as this card does.
- Cross-reference `syk`: the finite-`N` SYK spectrum realises GOE/GUE/GSE according to `N mod 8`, and its ED self-test cross-loads *these* `⟨r̃⟩` constants as targets — a genuine cross-card check of both cards.

## Key reference

[@AtasEtAl2013] — Y. Y. Atas, E. Bogomolny, O. Giraud & G. Roux, "Distribution of the Ratio of Consecutive Level Spacings in Random Matrix Ensembles", Phys. Rev. Lett. **110**, 084101 (2013): the closed-form ratio surmises `P(r)` and the mean values `⟨r̃⟩` (Table I) pinned above. The ratio statistic itself is Oganesyan–Huse [@OganesyanHuse2007]; the classic spacing surmise is Wigner [@Wigner1951]. Rendered: ./10-1103-physrevlett-110-084101.md.

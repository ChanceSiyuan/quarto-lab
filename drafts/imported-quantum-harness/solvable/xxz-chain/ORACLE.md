# XXZ chain — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: S

## Hamiltonian & conventions

$$ H = J \sum_{i=1}^{N}\left( S^x_i S^x_{i+1} + S^y_i S^y_{i+1} + \Delta\, S^z_i S^z_{i+1}\right), \qquad \text{PBC} $$

Conventions: spin-1/2 `S`-operators (`S^a = σ^a/2`), in-plane coupling `J = 1`, `Δ` the exchange anisotropy. `Δ = 1` is the isotropic Heisenberg point (sibling card `heisenberg-xxx`); `Δ = 0` the XX free-fermion point. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/xxz-chain/MODEL.md`. That card uses the **same** `S`-operator convention and quotes the identical anchors — `Δ=1`: `E/N = 1/4 − ln 2 ≈ −0.443147`, and `Δ=0`: `E/N = −1/π ≈ −0.318310` — which this oracle reproduces to `1e-8`. No convention translation is needed.

## Solvability statement

T3 (Bethe ansatz / Yang–Baxter): the XXZ chain is Bethe-ansatz integrable for **every** anisotropy `Δ` — Yang & Yang proved Bethe's hypothesis for the ground state and worked out the thermodynamic ground-state energy [@YangYang1966; @YangYang1966b]. The `U(1)` symmetry (`S^z_{tot}` conserved) organises the ansatz exactly as for the isotropic chain, but the two-magnon scattering phase now carries the anisotropy through `Δ = \cos γ` (`|Δ|<1`) or `Δ = \cosh η` (`Δ>1`). The ground state is again the packed all-real-root solution in the `S^z=0` sector; in the thermodynamic limit the root density solves a linear integral equation whose kernel depends on `γ`/`η`, and the ground energy per site becomes a closed-form **integral** (`|Δ|<1`) or a rapidly convergent **series** (`Δ>1`). Reported here: the thermodynamic-limit `e0(Δ)` across all three regimes, and the spin gap for `Δ>1`. **Not exact in closed form (Tier B):** the full excitation spectrum, correlation functions, and finite-`T` thermodynamics need state-by-state Bethe roots / TBA — integrable but not single closed forms; out of this card's scope.

## The Bethe-ansatz story

The magnon plane waves and the coordinate ansatz are exactly those of the isotropic chain (`heisenberg-xxx`); anisotropy enters only through the scattering phase. The ground state is the packed 1-string (all-real-root) state in `S^z=0`. As `N→∞` the roots fill a curve with density `ρ(λ)` obeying a linear integral equation — sums over roots become **integrals over `ρ`**, which is why the thermodynamic energy is an integral. The three regimes reflect the analytic structure of that kernel:

- **`−1 < Δ ≤ 1` (gapless Luttinger liquid, `Δ = \cos γ`):** the roots spread over the whole real line; the integral equation is solved by Fourier transform, giving `e0` as a Fourier integral. Central charge `c=1`; correlations are power-law (`Δ`-dependent exponent). The gap vanishes.
- **`Δ = 1` (isotropic):** `γ→0`, the kernel degenerates to `ρ = 1/(2\cosh πλ)`, and the integral collapses to `e0 = 1/4 − ln 2`.
- **`Δ > 1` (gapped Ising–Néel AFM, `Δ = \cosh η`):** the anisotropy discretises the natural variable; the Fourier integral becomes a **convergent sum**, and a finite spin gap opens with the famous Berezinskii–Kosterlitz–Thouless essential singularity as `Δ→1⁺` [@desCloizeauxGaudin1966].

## Exact results (regime table)

`Δ = \cos γ` in the critical window, `Δ = \cosh η` in the massive window. `e0 ≡ E/N` in the thermodynamic limit; `J = 1`.

| Regime | `e0` (thermodynamic ground energy per site) | Gap | Source |
|---|---|---|---|
| `Δ = 1` (isotropic) | `1/4 − ln 2 ≈ −0.4431472` (exact) | `0` (gapless) | [@Hulthen1938] |
| `−1 < Δ < 1` (gapless, `Δ=\cos γ`) | `\dfrac{\cos γ}{4} − \sin^2γ\displaystyle\int_{-\infty}^{\infty}\dfrac{dx}{2\cosh(πx)\,(\cosh 2γx − \cos γ)}` | `0` (gapless) | [@YangYang1966b] |
| `Δ > 1` (massive Néel, `Δ=\cosh η`) | `\dfrac{\cosh η}{4} − \sinh η\Big(\dfrac12 + 2\displaystyle\sum_{n\ge1}\dfrac{1}{1+e^{2nη}}\Big)` | `\sinh η\Big(1 + 2\displaystyle\sum_{n\ge1}\dfrac{(-1)^n}{\cosh nη}\Big)` | [@YangYang1966b; @desCloizeauxGaudin1966] |

Regime-of-validity discipline: **each formula holds only in its own row.** The `|Δ|<1` integral diverges/ceases to apply for `Δ≥1`; the `Δ>1` series is complex for `Δ<1`. They are pinned to agree where they meet:

- `Δ=0` (XX): the integral gives `e0 = −1/π` exactly.
- `Δ→1⁻`: the integral → `1/4 − ln 2`; `Δ→1⁺`: the series → `1/4 − ln 2` (both branches continuous across the isotropic point to `<1e-5`).
- `Δ→∞`: `e0 → −Δ/4` (classical Néel), gap `→ Δ − 2` (verified from the implemented series' own large-`η` expansion: `\sinh η → Δ`, `2\tanh η → 2`).
- Gap essential singularity: `gap(Δ→1⁺) → 0` faster than any power (`gap(1.001) ≈ 2×10⁻¹⁶`).
- Ferromagnet `Δ < −1`: ground state fully polarised, `e0 = Δ/4` (first-order crossing at `Δ=−1`; reported for completeness, outside the three integrable-formula regimes above).

## Oracle script

`python oracle.py --Delta 1.0` → prints `delta`, `e0_per_site` (three-regime dispatch), `gap` (Néel spin gap for `Δ>1`, else `0`). Importable: `compute(Delta=1.0)`; individual functions `e0(Delta)`, `gap(Delta)`.

Self-test anchors: (1) `e0` at the three exactly-known points — `e0(0)=−1/π` (`1e-8`), `e0(1)=1/4−ln 2` literal (`1e-15`), critical branch `e0(1−ε)→1/4−ln 2` (`1e-7`); (2) branch continuity `|e0(1+10⁻⁶) − e0(1−10⁻⁶)| < 1e-5` and Néel asymptote `e0(50)/(−50/4)→1` within `2%`; (3) gap pins — `gap(1.001) < 1e-3`, `gap(1)=0`, large-`Δ` ratio `gap(20)/(20−2)→1` within `1%`; (4) **ED brackets** — for `Δ∈{0.5,2.0}`, the PBC ground energy per site at `L∈{8,10,12}` rises monotonically toward `e0(Δ)` from below, with the `L=12` value within `2%`.

## ED cross-check of the spin gap (documented, not automated)

For `Δ>1` the naive "first excited state" of a **finite** PBC ring is *not* the spin gap: the two Néel configurations `|↑↓↑↓…⟩`, `|↓↑↓↑…⟩` tunnel into a quasi-degenerate doublet split only exponentially in `L` (e.g. `1.4×10⁻³` at `Δ=5, L=14`). The physical spin gap is the `S^z=0 → S^z=±1` sector gap. Sector-resolved ED (`L=14`) gives `gap ≈ 3.329` at `Δ=5` and `≈ 0.740` at `Δ=2`, versus the thermodynamic formula's `3.121` and `0.390`. Finite-`L` gaps are **upper bounds** that descend toward the formula as `L→∞` — tight (`~6%`) at `Δ=5` where the correlation length is short, loose at `Δ=2` (near the BKT point, `ξ` large). This confirms the formula's scale and identifies it as the true thermodynamic spin gap.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_per_site` | `Δ=0` (XX) | `−1/π ≈ −0.3183099` | [@YangYang1966b] |
| `e0_per_site` | `Δ=1` (isotropic) | `1/4 − ln 2 ≈ −0.4431472` | [@Hulthen1938] |
| `e0_per_site` | `Δ=2` | `−0.6172220` | [@YangYang1966b] |
| `gap` | `Δ=2` | `0.3898023` | [@desCloizeauxGaudin1966] |

## Verification recipes

- To check a DMRG/ED ground-state energy at anisotropy `Δ`: compare `e0(Δ)` from `oracle.py --Delta <Δ>` (exact thermodynamic value), tolerance set by the finite-size gap of the run. Finite PBC energies sit *below* `e0(Δ)` and rise toward it; extrapolate in `1/L²` (critical) or expect exponential convergence (`Δ>1`).
- To check a measured spin gap (`Δ>1`): compare against `gap(Δ)`, remembering finite-`L` ED overestimates it (upper bound) — see the ED cross-check above.
- Anchor any XXZ code at `Δ=0` (`−1/π`) and `Δ=1` (`1/4 − ln 2`).

## Key reference

[@YangYang1966] — Yang & Yang's proof of Bethe's hypothesis for the XXZ ground state; the companion paper [@YangYang1966b] derives the thermodynamic ground-state energy per site (both the `|Δ|<1` integral and the `Δ>1` series used above). The massive-regime spin gap is des Cloizeaux–Gaudin [@desCloizeauxGaudin1966]; the isotropic energy is Hulthén [@Hulthen1938]. Rendered: bib stub — no PDF reachable (2026-07-14).

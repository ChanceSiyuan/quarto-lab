# 1D Hubbard chain (Lieb–Wu) — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: S

## Hamiltonian & conventions

$$ H = -t \sum_{i=1}^{N}\sum_{\sigma=\uparrow,\downarrow}\left( c^\dagger_{i\sigma} c_{i+1\,\sigma} + \text{h.c.} \right) + U \sum_{i=1}^{N} n_{i\uparrow} n_{i\downarrow}, \qquad \text{PBC} $$

Conventions: `t = 1` hopping (energy unit), `U > 0` on-site repulsion, half filling (`⟨n_i⟩ = 1`, `N_↑ = N_↓ = N/2`), nearest-neighbour bonds counted once. All quantities are thermodynamic-limit (`N → ∞`) unless a finite `N`/`L` is stated. See `.knowledge/conventions.md`.

Physics card: `.knowledge/models/hubbard/MODEL.md`. That card uses the **same** `H = -t Σ(c†c+h.c.) + U Σ n↑n↓` form and quotes the identical `U/t=4` benchmark `E/N ≈ -0.5737 t` and the same large-`U` mapping `E/N → 4 ln 2 · (-t²/U)`; both are reproduced here to `1e-8`. No convention translation is needed. The strong-coupling reduction hands off to the sibling card `susy-t-j` / `models/t-j` (`J = 4t²/U`).

## Solvability statement

T3 (Bethe ansatz): the one-dimensional Hubbard model is integrable by the nested Bethe ansatz — Lieb & Wu (1968) reduced the eigenvalue problem to a coupled set of equations for charge momenta `k_j` and spin rapidities `λ_α` [@LiebWu1968]. At half filling the ground-state charge distribution fills the whole Brillouin zone and the spin rapidities condense onto the real line; the coupled equations decouple by Fourier transform into a **single closed-form integral** for the energy per site,

$$ e_0(U) = -4\int_0^\infty d\omega\,\frac{J_0(\omega)\,J_1(\omega)}{\omega\,(1 + e^{\omega U/2})}, $$

with `J_0, J_1` Bessel functions (`t=1`). The Mott charge gap is a second Bessel integral (below). **Absence of a Mott transition:** the charge gap is nonzero for **every** `U > 0` — the metal exists only at `U = 0`, and the insulator opens immediately [@LiebWu1968; @Ovchinnikov1970]. **Not exact in closed form (Tier B, not A):** away from half filling, and for the full excitation spectrum / finite-`T` thermodynamics / correlation functions, one must solve the Lieb–Wu / thermodynamic-Bethe-ansatz equations state-by-state — integrable but not single closed forms; out of this card's scope.

## The Lieb–Wu story

The Hubbard interaction is not diagonal in the free-fermion basis, so unlike the spin chains (`heisenberg-xxx`, `xxz-chain`) the ansatz is **nested**: an outer Bethe ansatz in the charge sector (momenta `k_j`, one per electron) sits over an inner ansatz in the spin sector (rapidities `λ_α`, one per down-spin). Consistency under two-body scattering plus periodicity gives the **Lieb–Wu equations**, coupling `{k_j}` and `{λ_α}` through `\arctan` kernels. At half filling the ground state is the "all-real" solution: every `k_j` real and every `λ_α` real, with no `k`-`Λ` strings (bound complexes, which raise the energy). Taking `N → ∞` turns the sums into integrals over root densities that solve linear integral equations with Bessel-function kernels — and the energy integral collapses to the closed form above. The same machinery yields the charge (Mott) gap

$$ \Delta(U) = U - 4 + 8\int_0^\infty d\omega\,\frac{J_1(\omega)}{\omega\,(1 + e^{\omega U/2})}, $$

the difference between the energies to add and to remove one electron [@Ovchinnikov1970]. Two limits pin it: as `U → ∞` the integral vanishes and `Δ → U - 4` (the atomic gap minus the two bandwidths); as `U → 0⁺` it closes as the essential singularity `Δ ≈ (8/π)\sqrt{U}\,e^{-2\pi/U}` — nonzero for any `U > 0` but exponentially small, which is why the transition is "absent". In the strong-coupling limit charge freezes and the spins map to a Heisenberg antiferromagnet with `J = 4t²/U`; the energy per site `e_0 → -4\ln 2/U` is the Heisenberg value including the `-¼ n_i n_j` density term (see `susy-t-j`).

## Exact results

- Ground-state energy per site (half filling): `e_0(U) = -4∫_0^∞ dω\, J_0(ω)J_1(ω)/(ω(1+e^{ωU/2}))` [@LiebWu1968]
- Free-fermion point: `e_0(0) = -4/π ≈ -1.2732395` (two half-filled tight-binding bands) [@LiebWu1968]
- Mott charge gap: `Δ(U) = U - 4 + 8∫_0^∞ dω\, J_1(ω)/(ω(1+e^{ωU/2}))`; `Δ > 0 ∀ U>0`, `Δ(U→∞) → U-4`, `Δ(U→0⁺) → 0` (essential singularity) [@Ovchinnikov1970]
- Strong-coupling asymptote: `e_0(U) → -4\ln 2/U` (`J = 4t²/U` Heisenberg limit) [@LiebWu1968]
- `e_0(U)` is monotone increasing in `U` (repulsion raises the energy); the ground state is a spin singlet, gapless in the spin sector, gapped in the charge sector.

## Oracle script

`python oracle.py --U 4.0` → prints `e0_thermodynamic` (Lieb–Wu integral), `mott_gap` (`Δ(U)`), `e0_strong_coupling_asymptote` (`-4 ln2/U`), `e0_ed_per_site_L6` (finite-size ED cross-check). Importable: `compute(U=4.0)`; `e0(U)`, `e0_quad(U)`, `mott_gap(U)`, `hubbard_ed_energy(L, U)`.

The Lieb–Wu integrand decays only as `1/ω²` and oscillates as `\cos 2ω` at `U=0` (the `e^{ωU/2}` damping is absent), so a plain `quad` to `∞` loses accuracy there. `e0()` integrates over whole `\cos 2ω`-periods — per-period cancellation gives a `1/N²` partial-sum tail — and Richardson-extrapolates; this reaches `e_0(0) = -4/π` to `1e-13`. For `U > 0` the exponential tail makes a direct `quad` machine-exact, which the self-test uses as the independent second strategy (they agree to `1e-8`).

Self-test anchors: (1) **ground truth** — the two-species Jordan–Wigner ED at `U=0`, `L=6`, `N_↑=N_↓=3` equals the exact free-fermion energy `-8` (two half-filled PBC rings, `2×(-2-1-1)`) to `1e-10`; (2) `e0(0) = -4/π` to `1e-8` (period-segmented + Richardson); (3) the two quadrature strategies agree to `1e-8` for `U ∈ {1,4,8}`; (4) `e0(U)` monotone increasing; (5) strong-coupling ratio `e0(64)/(-4 ln2/64) → 1` within `5%`; (6) gap pins — `Δ(1) < 0.01`, `Δ(0.5) < 1e-3`, `Δ(64)/(64-4) → 1` within `2%`, `Δ` monotone increasing; (7) **ED bracket** — the `L=6` half-filled energy per site at `U=4` lies within a documented band below the thermodynamic `e_0(4)` (see below).

## The spinful Jordan–Wigner ED (ground truth, and its finite-size sign)

The `U=0` validation is a hard `1e-10` assert built on a specific construction: the spinful chain is a `2L`-site spinless Jordan–Wigner chain ordered `(0↑…(L-1)↑, 0↓…(L-1)↓)`. Each spin lives in its own length-`L` block, so intra-species hops telescope to the standard nearest-neighbour form and the number operators are string-free (the `U`-term is a plain product). The subtlety is the boundary bond: for the **odd** particle number `N_↑=3` the Jordan–Wigner ring reproduces exactly **periodic** free fermions — verified because the `(3,3)` sector energy at `U=0` is `-8` to machine precision, matching `2×` the sum of the three lowest single-particle energies of a 6-site tight-binding ring (`-2, -1, -1`).

At `U=4` the same ED gives `e_0^{L=6}/L = -0.611451`, which sits **below** the thermodynamic `e_0(4) = -0.573729` by `0.0377` (`≈ 6.6%`): the closed-shell 6-site ring over-binds. The self-test asserts a documented band `e_0(4) - 0.06 < e_0^{L=6}/L < e_0(4) + 0.005` (finite `L`, so no exact agreement is expected — this is a bracketing sanity check, not a benchmark). The sign — ED **below** the thermodynamic value — is the physically expected finite-size effect for a half-filled PBC ring.

## Benchmarks

`e_0 ≡ E/N` at half filling, thermodynamic limit, `t = 1`.

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_thermodynamic` | `U=0` (free) | `-4/π ≈ -1.2732395` | [@LiebWu1968] |
| `e0_thermodynamic` | `U=4` | `-0.5737294` | [@LiebWu1968] |
| `e0_thermodynamic` | `U=8` | `-0.3275305` | [@LiebWu1968] |
| `mott_gap` | `U=4` | `1.2867270` | [@Ovchinnikov1970] |
| `mott_gap` | `U=8` | `4.6795171` | [@Ovchinnikov1970] |
| `e0_strong_coupling_asymptote` | `U→∞` | `-4 ln2/U` (ratio `e0/asymptote → 1`) | [@LiebWu1968] |

## Verification recipes

- To check a DMRG/ED/QMC ground-state energy at half filling: compare `e0(U)` from `oracle.py --U <U>` (exact thermodynamic value), tolerance set by the run's finite-size gap. Finite PBC energies sit **below** `e0(U)` and rise toward it as `L → ∞`; extrapolate in `1/L²`.
- To check a measured charge (Mott) gap: compare against `mott_gap(U)`. Anchor any Hubbard-chain code at `U=0` (`e0 = -4/π`) and in the strong-coupling limit (`e0 · U/(-4 ln2) → 1`, and the model should reduce to Heisenberg with `J = 4t²/U`).
- Cheap sanity checks: `e0(U)` must be monotone increasing in `U`; the charge gap must be positive for every `U > 0` (no Mott transition) and grow like `U - 4` at large `U`.

## Key reference

[@LiebWu1968] — Lieb & Wu, "Absence of Mott Transition in an Exact Solution of the Short-Range, One-Band Model in One Dimension", Phys. Rev. Lett. **20**, 1445 (1968): the nested-Bethe-ansatz solution giving the half-filling ground-state energy integral and establishing that the charge gap opens for every `U > 0`. The explicit Mott-gap integral is Ovchinnikov [@Ovchinnikov1970]. Rendered: bib stub — no PDF reachable (2026-07-14).

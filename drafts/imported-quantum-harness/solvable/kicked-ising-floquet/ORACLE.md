# Self-dual kicked Ising Floquet model — exact-solution oracle

Technique: T7 (dualities & solvable dynamics) · Tier: A (exact spectral form factor) · Script: S

## Hamiltonian & conventions

$$ U_F = e^{-iH_K}\,e^{-iH_I}, \qquad H_I = J\sum_{j}\sigma^z_j\sigma^z_{j+1} + \sum_j h_j\,\sigma^z_j, \qquad H_K = b\sum_j \sigma^x_j, \qquad \text{PBC} $$

Conventions: Pauli operators, `L` qubits, periodic boundary. `J` is the Ising coupling, `b` the transverse kick, `h_j` a site-dependent **longitudinal** field (quenched disorder). The **self-dual point** is `|J| = |b| = π/4`. This is the *kicked* gauge in which Bertini–Kos–Prosen proved an exact spectral form factor [@BertiniKosProsen2018]; it is a space-time-similarity relative of the brickwork dual-unitary gate on the `dual-unitary-circuits` card — the same physics in a different gauge, but the two Floquet operators are **not identical and not isospectral** (the brickwork `e^{iJZZ}e^{ib(X+X)}e^{iJZZ}` gate is the symmetric-split form). See `.knowledge/conventions.md`. Physics relatives: `dual-unitary-circuits` (the space-time-duality structure) and `random-matrix-stats` (the COE ensemble the SFF reproduces).

## Solvability statement

T7: at the self-dual point the model is exactly solvable *for spectral statistics*. The exact statement is the **disorder-averaged spectral form factor** [@BertiniKosProsen2018]. Define, for integer Floquet time `t > 0`,

$$ K(t) = \big\langle\, \big|\,\mathrm{tr}\,U_F^{\,t}[h]\,\big|^2 \,\big\rangle_h , $$

the average over i.i.d. longitudinal fields `h_j`. In the **thermodynamic limit** the averaged SFF equals the circular-orthogonal-ensemble RMT result. BKP prove the **odd-`t`** case rigorously and conjecture even `t`:

$$ \lim_{L\to\infty} \overline{K(t)} = \begin{cases} 2t-1, & t \le 5 \\ 2t, & t \ge 7 \end{cases}\ (t\ \text{odd}), \qquad \lim_{L\to\infty}\overline{K(t)} = 2t+1\ (t>11,\ t\ \text{even}), $$

with the RMT comparison curve `K_{COE}(t) = 2t − t\ln(1 + 2t/N)`, `N = 2^L`. The **leading ramp is `2t`** (COE); the `∓1` are exact short-time `O(1)` corrections. Averaging over the `h_j` is the essential step — it opens a gap in a transfer matrix and selects the `2t` "universal" eigenvalues; the TL result is independent of the disorder distribution and variance. **Not exact / caveat:** at finite `L` (scripted here) `K(t)` carries finite-size and finite-sample corrections, so the card **band-asserts** the odd-`t` values `2t−1` rather than claiming equality; the sharp `t=1` value is the cleanest discriminator against the non-self-dual control. The plateau `K(t)=N` (`t \gtrsim N`) and level repulsion at `t \sim 2^L` are TL-inaccessible and out of scope.

## Exact results

- **U_F two ways.** The monolithic operator exponential `e^{-iH_K}e^{-iH_I}` and a brickwork-ordered product of local factors (the 2-site gate `e^{-iJσ^zσ^z}` imported from `dual-unitary-circuits`, over even then odd bonds, dressed with field phases `e^{-ih_jσ^z}` and kicks `e^{-ibσ^x}`) coincide to `10^{-12}` at `L=8`, PBC.
- **Self-dual SFF** [@BertiniKosProsen2018]: `\overline{K(t)} → 2t−1` (`t` odd, `t≤5`) in the TL. Reproduced at finite `L=8,10` within a disorder-average band (below).
- **Negative control:** away from self-duality (`b=π/5`, `J=π/4`) the averaged SFF leaves the band — most sharply at `t=1`, where the self-dual value `≈1` while the control is `≳7` (`L=8`), `≳14` (`L=10`).

## Oracle script

`python oracle.py --L 8 --nreal 48 --tmax 5 --seed 7` → prints `twoway_UF_residual` and `sff_selfdual_t{1..tmax}`, `sff_control_t{1..tmax}`. Importable: `compute(L=8, nreal=48, tmax=5, seed=7)`; helpers `uf_expm(L,J,b,h)`, `uf_brickwork(L,J,b,h)` (cross-loads `dual-unitary-circuits`), `spectral_form_factor(L,b,nreal,tmax,seed)`.
Self-test anchors: (1) `uf_expm` and `uf_brickwork` agree to `10^{-12}` (and are unitary) at `L=8` with disorder on. (2) at self-duality (`L=8`, 24 realizations, seed 7) `K(1) < 1.8` and `K(3) ∈ (3,7)` — the BKP odd-`t` band around `2t−1 = 1, 5` — while the `b=π/5` control has `K(1) > 3` and `K(1) > 3\,K_{\text{self-dual}}(1)`; the reported disorder band is non-zero.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| BKP odd-`t` SFF (thermodynamic limit) | `t` odd, `t≤5` | `\overline{K(t)} = 2t-1` | [@BertiniKosProsen2018] |
| BKP odd-`t` SFF (thermodynamic limit) | `t` odd, `t≥7` | `\overline{K(t)} = 2t` | [@BertiniKosProsen2018] |
| RMT comparison curve | COE, `N=2^L` | `K_{COE}=2t-t\ln(1+2t/N)` | [@BertiniKosProsen2018] |
| self-dual `K(1),K(3),K(5)` (measured) | `L=8`, 400 real, seed 7 | `1.01, 5.30, 8.06` (vs `1,5,9`) | this card (measured) |
| self-dual `K(1),K(3),K(5)` (measured) | `L=10`, 80 real, seed 7 | `0.94, 4.52, 8.50` (vs `1,5,9`) | this card (measured) |
| control `K(1)` (`b=π/5`) | `L=8 / L=10`, seed 7 | `8.7 / 13.9` (off band) | this card (measured) |

Measured values are finite-`L`, finite-sample estimates of `\overline{K(t)}` (disorder average over i.i.d. `h_j ∼ U(-π,π)`); the odd-`t` entries track the BKP `2t−1` prediction, the even-`t` and control values do not. `U_F` two-way residual: `< 10^{-12}` (`L=8`).

## Verification recipes

- To check a Floquet-SFF code at the self-dual point: build `U_F = e^{-ibΣσ^x}e^{-i(J Σσ^zσ^z + Σ h_jσ^z)}` with `J=b=π/4`, average `|tr U_F^t|^2` over `≳100` i.i.d. `h_j`, and confirm the odd-`t` values sit near `2t−1` (`t≤5`) within a `~1` band at `L=8,10`; a run reproducing the `b=π/5` control (much larger, non-monotonic `K(t)`) signals the self-dual condition is not met.
- To check a Floquet-operator assembly: compare `uf_expm` against the imported-gate brickwork `uf_brickwork`, tolerance `10^{-12}` (this catches bond-wiring and PBC bugs).

## Key reference

[@BertiniKosProsen2018] — B. Bertini, P. Kos & T. Prosen, "Exact Spectral Form Factor in a Minimal Model of Many-Body Quantum Chaos", Phys. Rev. Lett. **121**, 264101 (2018): the self-dual kicked-Ising model, the Floquet SFF definition `K(t)=⟨|tr U_F^t|^2⟩_h` (Eq. 6), the transfer-matrix method, and the exact odd-`t` result `\overline{K(t)}=2t−1` (`t≤5`), `2t` (`t≥7`) with the even-`t` conjecture (Eq. 24, 26). The space-time-duality structure is developed in [@BertiniKosProsen2019]. Rendered: ./10-1103-physrevlett-121-264101.md.

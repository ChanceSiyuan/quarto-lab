# η-pairing Hubbard — exact-solution oracle

Technique: T5 (frustration-free / exact eigenstates) · Tier: C (exact eigenstates only — here **exact excited states**) · Script: S

## Hamiltonian & conventions

$$ H = -t \sum_{\langle ij\rangle,\sigma}\left(c^\dagger_{i\sigma}c_{j\sigma}+\text{h.c.}\right) + U\sum_i n_{i\uparrow}n_{i\downarrow}, \qquad \eta^\dagger = \sum_{j}(-1)^j\,c^\dagger_{j\uparrow}c^\dagger_{j\downarrow} $$

Conventions: Hubbard chain on a bipartite `L`-site **PBC ring**, `L` even; `t=1` the energy unit; `U>0` on-site repulsion. **No chemical-potential term and no `−U/2` particle-hole shift are included** — this bare form is what makes the η-pairing energy shift the clean constant `U` (see below). `n_{i\sigma}=c^\dagger_{i\sigma}c_{i\sigma}`; `|{\rm vac}\rangle` is the empty lattice, `H|{\rm vac}\rangle=0`. The staggered phase `(-1)^j` (the antiferromagnetic wavevector) is essential: it makes the hopping commute with `\eta^\dagger` on the bipartite lattice. See `.knowledge/conventions.md`. Physics card: `.knowledge/models/hubbard/MODEL.md` (same `H = -t\,\Sigma\,\text{hop} + U\,\Sigma\,n_\uparrow n_\downarrow` convention, `t=1`; that card lists the `SO(4)=` spin-SU(2)`×`η-pairing-SU(2) symmetry at half filling). Overlaps with `hubbard-1d-lieb-wu` (identical two-species Jordan–Wigner construction).

## Solvability statement

T5 (frustration-free / exact eigenstates), but the load-bearing statement is an **operator identity**, not a variational ground state. The staggered η-pairing operator obeys, on any bipartite lattice with `L` even,
`[H,\eta^\dagger]=U\eta^\dagger` — verified as a matrix identity at `L=4,6` to `< 1e-12`. The derivation splits cleanly: the kinetic term commutes with `\eta^\dagger` by itself (each bond `(i,j)` contributes `(-1)^i+(-1)^j=0` because `i,j` sit on opposite sublattices), and the interaction gives `[U\sum_i n_{i\uparrow}n_{i\downarrow},\eta^\dagger]=U\sum_i(-1)^i c^\dagger_{i\uparrow}c^\dagger_{i\downarrow}=U\eta^\dagger` since `[n_{i\uparrow}n_{i\downarrow},c^\dagger_{i\uparrow}c^\dagger_{i\downarrow}]=c^\dagger_{i\uparrow}c^\dagger_{i\downarrow}`. Consequently `\eta^{\dagger m}|{\rm vac}\rangle` is an **exact eigenstate with energy `E_m = mU`** (induction: `H\eta^{\dagger m}|{\rm vac}\rangle = mU\,\eta^{\dagger m}|{\rm vac}\rangle`), sitting in the `(N_\uparrow,N_\downarrow)=(m,m)`, `S=0`, `S^z=0` sector (each `\eta^\dagger` deposits a pair at the antiferromagnetic wavevector, so the total momentum is `m\pi`). **These are exact EXCITED states, not ground states** — for `U>0` they lie at positive energy `mU`, whereas the true ground state of the *same* `(m,m)` sector is bound (negative energy), strictly and by a wide margin below `mU` (identity-proof anchor: at `U=4`, `L=6`, `m=2` the sector ground energy is `≈ −4.70 < 8 = mU`). What is exact is only this η-pairing tower and its correlators; the generic Hubbard spectrum is *not* closed-form (it needs the Lieb–Wu Bethe ansatz — see `hubbard-1d-lieb-wu`). Convention caveat: with the particle-hole-symmetric `U\sum(n_\uparrow-\tfrac12)(n_\downarrow-\tfrac12)` the shift becomes `0` (η-states degenerate with Néel states, the `SO(4)` multiplet); with a `-\mu N` term it is `(U-2\mu)` since `[N,\eta^\dagger]=2\eta^\dagger`. This card uses the bare `H` → shift `U`.

## The exact η-pairing / ODLRO story

The `\eta^\dagger,\eta,\eta_z=\tfrac12(N-L)` operators close an `su(2)` **pseudospin** algebra (`[\eta,\eta^\dagger]=-2\eta_z`), with `|{\rm vac}\rangle` the lowest-weight state of pseudospin `L/2`. So `\eta^{\dagger m}|{\rm vac}\rangle \propto |L/2,\,-L/2+m\rangle`, and the raising-operator norm gives the closed form `\|\eta^{\dagger m}|{\rm vac}\rangle\|^2 = \prod_{k=0}^{m-1}(k+1)(L-k) = m!\,L!/(L-m)!` (`=L` at `m=1`; `=2L(L-1)` at `m=2`), pinned against direct computation for all `m\le L`. Yang's **off-diagonal long-range order (ODLRO)**: in the normalised `m`-pair state the pair correlator `\langle\eta^\dagger_i\eta_j\rangle` (with `\eta^\dagger_i=(-1)^i c^\dagger_{i\uparrow}c^\dagger_{i\downarrow}`) is `r`-**independent** for `i\ne j`, equal to `m(L-m)/(L(L-1))`, while the diagonal `\langle\eta^\dagger_i\eta_i\rangle=m/L` is the pair density. The off-diagonal element does not decay with `|i-j|` — the defining signature of ODLRO / η-superconducting order — and in the thermodynamic limit at fixed pair density `\rho=m/L` it tends to `\rho(1-\rho)\ne 0`. Both closed forms are pinned vs direct ED at `L=6`, `m\in\{2,3\}`, to `1e-10`, along with the sum rule `\sum_{i\ne j}\langle\eta^\dagger_i\eta_j\rangle=\langle\eta^\dagger\eta\rangle-m`.

## Exact results

- Operator identity: `[H,\eta^\dagger]=U\eta^\dagger` (bare `H`, bipartite, `L` even) — verified `< 1e-12` [@Yang1989]
- Exact excited tower: `\eta^{\dagger m}|{\rm vac}\rangle` eigenstate, `E_m=mU` exactly, in the `(m,m)` sector [@Yang1989]
- Norm: `\|\eta^{\dagger m}|{\rm vac}\rangle\|^2 = m!\,L!/(L-m)!` [@Yang1989]
- ODLRO: `\langle\eta^\dagger_i\eta_j\rangle=m(L-m)/(L(L-1))` (`i\ne j`, `r`-independent); `\langle\eta^\dagger_i\eta_i\rangle=m/L` [@Yang1989]
- **Not exact / not the GS:** the η-states are exact *excited* states; the sector ground state (`≈ −4.70` at `L=6,U=4,m=2`) lies far below `mU`, and the full Hubbard spectrum is closed-form only via Bethe ansatz (`hubbard-1d-lieb-wu`).

## Oracle script

`python oracle.py --L 6 --U 4 --m 2` → prints `eta_shift` (`U`), `energy_m_pair` (`mU`), `norm_sq_closed`/`norm_sq_direct` (`m!L!/(L-m)!`), `odlro_offdiag_closed` (`m(L-m)/(L(L-1))`), `pair_density_diag` (`m/L`), `sector_gs_energy` (the ED ground energy of the `(m,m)` sector — strictly below `mU`, proving the η-state is excited). Importable: `compute(L=6,U=4.0,m=2)`; helpers `eta_state(L,m)`, `eta_norm_sq(L,m)`, `odlro_offdiag(L,m)`, `sector_ground_energy(L,nup,ndn)`.

Self-test anchors: (1) **ground truth** — operator identity `\|[H,\eta^\dagger]-U\eta^\dagger\|<1e-12` at `L=4,6`, with the kinetic-only commutator separately verified to vanish (bipartite) and the `U`-term carrying the whole shift; (2) `\eta^{\dagger m}|{\rm vac}\rangle` is an **operator-level** eigenstate — `\|H|\psi\rangle-mU|\psi\rangle\|<1e-12` for `m=1,2,3`; (3) norm `m!L!/(L-m)!` vs direct for `m=1..L`; (4) ODLRO diagonal `m/L` and off-diagonal `m(L-m)/(L(L-1))` vs direct, off-diagonal verified `r`-independent, plus the sum rule, at `L=6`, `m=2,3`; (5) **identity-proof (excited, not GS)** — the `(m,m)`-sector ED ground energy is `< mU-1` and `< 0` for `m=1,2,3` at `U=4`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `eta_shift` `[H,η†]/η†` | bipartite, `L` even, bare `H` | `U` | [@Yang1989] |
| `energy_m_pair` | any `L,U`; `m` pairs | `mU` (exact excited) | [@Yang1989] |
| `norm_sq_closed` | `L=6`, `m=2` | `60` `= 2L(L−1)` | [@Yang1989] |
| `odlro_offdiag` | `L=6`, `m=2` | `4/15 ≈ 0.2667` | [@Yang1989] |
| `pair_density_diag` | `L=6`, `m=2` | `1/3` | [@Yang1989] |
| `sector_gs_energy` | `L=6`, `U=4`, `m=2` | `≈ −4.70` (`≪ mU=8`) | ED (this card) |

## Verification recipes

- To check an η-pairing / excited-eigenstate code: build `\eta^{\dagger m}|{\rm vac}\rangle` and confirm `\|H|\psi\rangle-mU|\psi\rangle\|` is at machine precision — any nonzero residual flags a wrong staggering `(-1)^j`, a wrong lattice (non-bipartite), or an unintended `-\mu N`/`-U/2` term shifting the constant off `U`.
- To check ODLRO: the pair correlator `\langle\eta^\dagger_i\eta_j\rangle` must be `|i-j|`-independent and equal `m(L-m)/(L(L-1))`; a decaying correlator means the state is not the η-condensate.
- Do **not** treat these as ground states: verify the same-sector ED ground energy sits *below* `mU`. The η-tower is a set of exact excited states (metastable η-superconducting states in Yang's language), not the Hubbard ground state.

## Key reference

[@Yang1989] — C. N. Yang's construction of the η-pairing eigenstates of the Hubbard model, the pseudospin `su(2)` algebra, and the proof that these states carry off-diagonal long-range order — the exact anchor used above. Rendered: bib stub — no PDF reachable (2026-07-14).

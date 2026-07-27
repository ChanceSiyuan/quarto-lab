# Dual-unitary brickwork circuits — exact-solution oracle

Technique: T7 (dualities & solvable dynamics) · Tier: A (closed-form dynamics) · Script: S

## Hamiltonian & conventions

$$ U_F = U_{\text{odd}}\,U_{\text{even}}, \qquad U_{\text{even}}=\!\!\prod_{j\ \text{even}}\!\! U_{j,j+1}, \quad U_{\text{odd}}=\!\!\prod_{j\ \text{odd}}\!\! U_{j,j+1}, \qquad \tilde U_{(o_1 i_1),(o_2 i_2)} = U_{(o_1 o_2),(i_1 i_2)} $$

Conventions: a brickwork Floquet circuit on `L` qubits (PBC, `L` even) built from a single two-qubit gate `U` with matrix elements `U_{(o1 o2),(i1 i2)}` (`o` = output/top legs, `i` = input/bottom legs, left site first). One period applies the gate on even bonds `(0,1),(2,3),…` then odd bonds `(1,2),…,(L-1,0)`. The **dual gate** `Ũ` is the space-time reshuffle above — pair each output leg with the input leg of the *same site*, so rows `(o1,i1)` label the left site and columns `(o2,i2)` the right. `U` is **dual-unitary** iff both `U` and `Ũ` are unitary; the circuit is then a unitary evolution in the space direction as well as time. See `.knowledge/conventions.md`. No model-zoo sibling; the physics relatives are `kicked-ising-floquet` (a self-dual-KIM Floquet in the "kicked" gauge) and `random-matrix-stats` (the RMT the SFF flows to).

## Solvability statement

T7: dual-unitarity is an exact algebraic property (a single reshuffled-gate unitarity condition), and it makes the light-cone dynamics **exactly** computable. Everything reported is exact for any `L`: (a) the dual-unitarity certificate `‖Ũ†Ũ − 1‖`; (b) infinite-temperature two-point correlators `⟨σ^z_x(t) σ^z_0(0)⟩/2^L`, which **vanish exactly off the light cone** and **on the edge equal a single-site quantum channel iterated `2t` times** [@BertiniKosProsen2019]. **Not exact / out of scope:** correlators at finite temperature or of multi-site operators, entanglement growth (exactly linear for dual-unitary but not scripted here), and the spectral form factor of a *single* dual-unitary circuit — the SFF lives on the sibling `kicked-ising-floquet` card. **Finite-size caveat (scripted):** on an `L`-ring the two light cones wrap once `2\cdot 2t \ge L`, so the exact off-cone *vanishing* is asserted only in the clean window `t \le L/4`; the on-edge value stays exact as long as the `±2t` edges do not collide (checked to `t=3` at `L=10`).

## Exact results

- **Dual-unitarity certificate.** Self-dual kicked-Ising gate `U(J,b)=e^{iJ σ^z σ^z} e^{ib(σ^x⊗1+1⊗σ^x)} e^{iJ σ^z σ^z}` is dual-unitary **exactly at** `|J|=|b|=π/4` (a Clifford point): `‖Ũ†Ũ − 1‖ < 10^{-12}`. Away from it, `b=π/6` gives `‖Ũ†Ũ − 1‖ = 3/4` — a non-dual-unitary gate must FAIL the check.
- **Canonical family.** Any gate of the form `(u_1⊗u_2)\,e^{-i(\frac\pi4 XX+\frac\pi4 YY+J_z ZZ)}\,(v_1⊗v_2)` (`u,v∈SU(2)`, any `J_z`) is dual-unitary — the `XX,YY` couplings pinned at `π/4` are what enforce it.
- **Light-cone correlators** [@BertiniKosProsen2019]. For a dual-unitary brickwork, `⟨σ^z_x(t) σ^z_0(0)⟩/2^L = 0` unless `|x| = 2t` (per Floquet period); on the edge the value is `(S^{2t})_{zz}`, where `S` is the single-site channel `S_{ab}=\tfrac12\,\mathrm{tr}[σ^a M(σ^b)]`, `M(o)=\tfrac12\,\mathrm{tr}_{\text{left}}[U(o⊗1)U^\dagger]`. Verified against direct Heisenberg evolution to machine precision.

## Oracle script

`python oracle.py --L 8 --t 2` → prints `dualunitary_defect_selfdual`, `dualunitary_defect_control_bpi6`, `lightcone_offcone_max`, `lightcone_oncone_ED`, `lightcone_oncone_channel`. Importable: `compute(L=8, t=2)`; helpers `kim_gate(J,b)`, `zz_gate(J)`, `dual_gate(U)`, `dual_unitarity_defect(U)`, `floquet(u,L)`, `zz_correlator_row(u,L,t)`, `single_site_channel(u)`.
Self-test anchors: (1) `kim_gate(π/4,π/4)` is unitary and dual-unitary (`< 10^{-12}`), while `b∈{π/6,π/5,0.5}` keeps `U` unitary but fails the dual check (`> 0.1`); the canonical family is dual-unitary for generic `J_z`. (2a) off-cone `⟨σ^z σ^z⟩ < 10^{-12}` for `t ≤ L//4` at `L=8,10` (both `±2t` edges excluded). (2b) on-edge value equals the single-site channel `S^{2t}` to `10^{-12}` for `t ≤ 2` (`L=8`) and `t ≤ 3` (`L=10`), and the channel prediction is non-trivial (`|value| < 1` at `t=1`).

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `‖Ũ†Ũ − 1‖` (self-dual KIM gate) | `J=b=π/4` | `0` (`< 10^{-15}`) | [@BertiniKosProsen2019] |
| `‖Ũ†Ũ − 1‖` (control) | `J=π/4, b=π/6` | `3/4` (fails) | this card (measured) |
| off-cone `⟨σ^z_x(t) σ^z_0⟩/2^L` | generic DU gate, `x≠±2t`, `t≤L/4` | `0` (`< 10^{-12}`) | [@BertiniKosProsen2019] |
| on-edge `⟨σ^z_{-2t}(t) σ^z_0⟩/2^L` | generic DU gate (`J_z=0.7`), `t=1` | `-0.170542` `= (S^2)_{zz}` | this card (channel) |
| on-edge `⟨σ^z_{-2t}(t) σ^z_0⟩/2^L` | same, `t=2` | `-0.457743` `= (S^4)_{zz}` | this card (channel) |
| on-edge `⟨σ^z_{-2t}(t) σ^z_0⟩/2^L` | same, `t=3` (`L=10`) | `+0.878273` `= (S^6)_{zz}` | this card (channel) |

Values are for the fixed generic dual-unitary gate `generic_du_gate(Jz=0.7)`; the self-dual KIM gate carries the dual-unitarity certificate only (being Clifford, its `σ^z` spreads into a pure operator string with zero single-site marginal, so its one-site two-point functions vanish for `t≥1` — the correlator *structure* is exhibited on the generic gate).

## Verification recipes

- To check a circuit code implements a dual-unitary gate: build `Ũ = np.transpose(U.reshape(2,2,2,2),(1,3,0,2)).reshape(4,4)` and require `‖Ũ†Ũ − 1‖ < 10^{-12}` **in addition to** `‖U†U − 1‖`. A gate passing the second but failing the first (e.g. the KIM gate at `b=π/6`) is unitary but not dual-unitary.
- To check a light-cone correlator claim: evolve `σ^z_0` for `t` Floquet periods (`t ≤ L/4`), and confirm `⟨σ^z_x σ^z_0(t)⟩` vanishes (`< 10^{-12}`) for every `x ≠ ±2t`; on the surviving edge compare against `(S^{2t})_{zz}` from `single_site_channel`, tolerance `10^{-12}`.

## Key reference

[@BertiniKosProsen2019] — B. Bertini, P. Kos & T. Prosen, "Exact Correlation Functions for Dual-Unitary Lattice Models in 1+1 Dimensions", Phys. Rev. Lett. **123**, 210601 (2019): the dual-gate reshuffling, the dual-unitarity condition, and the light-cone two-point-function result (vanishing off the cone, single-site-channel iteration on the edge) scripted above. The self-dual kicked-Ising gate and its dynamics originate with [@BertiniKosProsen2018]. Rendered: ./10-1103-physrevlett-123-210601.md.

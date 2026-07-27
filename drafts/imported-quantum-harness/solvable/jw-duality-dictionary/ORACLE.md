# Jordan–Wigner & duality dictionary — mapping oracle

Technique: T7 (dualities & solvable dynamics) · Tier: — · Script: T

## Model & conventions

$$ c_j = \Big(\textstyle\prod_{l<j}\sigma^z_l\Big)\,\sigma^-_j, \qquad \sigma^z_j = 1 - 2\,c_j^\dagger c_j, \qquad \text{(Jordan–Wigner, one prototype of the maps tabulated below)} $$

Conventions: this is the catalog's **mapping dictionary** — a pointer card. It has **no `oracle.py`** and **no pinned ED row of its own**: every exact statement below is a duality/mapping whose *values* are checked on the two cards it links. Each row gives a one-line exact statement, the parameter dictionary, and pointers to the cards where both sides live. Operator conventions (Pauli vs spin-`½`, JW string ordering) are each card's own; see `.knowledge/conventions.md`.

## Solvability statement

T7: exact model-to-model maps. A duality is not itself a solution — it transports an exact result from one card to another (free-fermionization, a critical-point location, a transfer-matrix/Hamiltonian limit, a strong-coupling projection). This card is the index of those maps; the arithmetic lives on the linked cards. It is a **T-flag pointer card** by design: nothing here is independently scripted.

## Mapping dictionary

| Duality / map | Exact one-line statement | Parameter dictionary | Cards (both sides) |
|---|---|---|---|
| **Jordan–Wigner** (spin ↔ fermion) | 1D spin-`½` chains with only `σ^z σ^z` / `σ^x` (and `σ^xσ^x+σ^yσ^y`) terms map to free/quadratic spinless fermions via `c_j=(\prod_{l<j}σ^z_l)σ^-_j`; the string makes it exact. | `σ^x_j = 1-2c_j^\dagger c_j`; hopping `σ^x_jσ^x_{j+1}+σ^y_jσ^y_{j+1} = 2(c_j^\dagger c_{j+1}+\text{h.c.})`; pairing from `σ^zσ^z`. **Boundary-sector caveat:** PBC spins ↔ *antiperiodic* fermions in the even-parity sector (and vice versa) — the `k`-grid depends on the parity sector. | `tfim-chain`, `xy-chain`, `kitaev-chain` |
| **Kramers–Wannier** (order ↔ disorder) | Square-lattice Ising is self-dual: `\sinh 2K\,\sinh 2K^\ast=1`; `ψ(K)-\tfrac12\ln\sinh 2K` is self-dual-invariant, fixing `K_c=\tfrac12\ln(1+\sqrt2)`. Quantum shadow: TFIM `J↔h`. | `K=βJ`; dual `\tanh K^\ast=e^{-2K}`; TFIM bond `σ^zσ^z` ↔ dual-site field `σ^x`. | `kramers-wannier`, `tfim-chain`, `ising-2d-onsager` |
| **Ising ↔ dimers** (Fisher) | The 2D Ising partition function maps to a dimer (perfect-matching) count on a decorated ("Fisher") lattice, solved by a Kasteleyn Pfaffian. | Each Ising site → a Fisher city of vertices; Boltzmann weights → dimer weights; `Z_{\text{Ising}} \propto \mathrm{Pf}(K)` of the Kasteleyn matrix. | `ising-2d-onsager`, `dimer-kasteleyn` |
| **Six-vertex ↔ XXZ** (Hamiltonian limit) | The six-vertex row-to-row transfer matrix and the XXZ spin-`½` chain share a family of commuting transfer matrices; `H_{XXZ}` is the logarithmic derivative `H \propto \partial_u \ln T(u)\|_{u=0}`. | Anisotropy `Δ = (a^2+b^2-c^2)/(2ab) = \cosΓ`, matching XXZ `Δ`; spectral parameter `u` → Hamiltonian limit. | `six-vertex`, `xxz-chain` |
| **RK ↔ classical dimers** | At the Rokhsar–Kivelson point the quantum-dimer ground state is the equal-weight superposition of classical dimer coverings; equal-time correlators equal classical dimer correlators. | RK point `v=t`; `\|\text{GS}⟩ = \sum_{\text{coverings}}\|c⟩ / \sqrt{\mathcal N}`; `⟨\text{GS}\|O\|\text{GS}⟩` → classical dimer average. | `rk-quantum-dimer`, `dimer-kasteleyn` |
| **Hubbard ↔ Heisenberg** (strong coupling) | At half filling and `U≫t` the Hubbard model projects to the Heisenberg antiferromagnet with `J = 4t^2/U` (second-order superexchange). | `J_{\text{eff}} = 4t^2/U`; no-double-occupancy projection; higher orders → ring exchange. | `hubbard-1d-lieb-wu`, `heisenberg-xxx` |

## No oracle script — pointer card

There is **no `oracle.py`** and **no benchmark row pinned here**: this card only routes to where each mapping is realized numerically. The Jordan–Wigner free-fermionization is exercised on `tfim-chain`/`xy-chain`/`kitaev-chain` (finite-`L` energies vs brute-force ED); Kramers–Wannier on `kramers-wannier` (the derived free-energy invariant and self-dual `K_c`); Ising↔dimers on `ising-2d-onsager` and `dimer-kasteleyn` (Kaufman `Z` vs Kasteleyn Pfaffian); six-vertex↔XXZ on `six-vertex`/`xxz-chain`; RK↔dimers on `rk-quantum-dimer`; Hubbard↔Heisenberg on `hubbard-1d-lieb-wu`/`heisenberg-xxx`.

## Verification recipes

- To use a map as a cross-check: compute a quantity on one linked card, transport it with the parameter dictionary above, and compare on the other card. E.g. JW — a TFIM `e_0(L)` from `tfim-chain` must equal a free-fermion sum; Hubbard→Heisenberg — a half-filled `U/t=∞` energy should approach `heisenberg-xxx` with `J=4t^2/U`.
- To catch a boundary-sector slip in Jordan–Wigner: match the fermion momentum grid to the spin parity sector (PBC spins ↔ antiperiodic fermions in even parity) — the commonest error in reproducing `tfim-chain`/`xy-chain` finite-`L` spectra.

## Key reference

[@JordanWigner1928] — P. Jordan & E. Wigner, "Über das Paulische Äquivalenzverbot", Z. Physik **47**, 631 (1928): the spin↔fermion transformation underlying the whole free-fermion column of the catalog. The Ising↔dimer map is [@Fisher1966] (M. E. Fisher, J. Math. Phys. **7**, 1776); Kramers–Wannier self-duality is [@KramersWannier1941]. Each row's exact values are pinned on the linked cards. Rendered: bib stub — no PDF reachable (2026-07-14).

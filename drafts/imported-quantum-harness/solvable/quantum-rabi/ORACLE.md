# Quantum Rabi model — exact-solution oracle

Technique: T6 (collective / large-N / random) · Tier: B (exact but transcendental — Braak G-function) · Script: S

## Hamiltonian & conventions

$$ H_R = \omega\, a^\dagger a + g\,\sigma^x (a + a^\dagger) + \Delta\,\sigma^z $$

Conventions: **Braak's convention transcribed verbatim** (PRL 107, 100401, 2011, Eq. 1; `ℏ = 1`) — `a`, `a†` are photon operators of the single mode (frequency `ω`); `σ^{x,z}` are Pauli matrices for a two-level system of **level splitting `2Δ`**; `g` is the coupling. Defaults `ω = 1`, `g = 0.7`, `Δ = 0.4` (Braak's own Fig. 1 point). This is the **non-RWA parent** of the Jaynes–Cummings model: writing `g σ^x(a+a†) = g(a+a†)(σ^+ + σ^-)` and dropping the counter-rotating `aσ^- + a†σ^+` gives `H_JC` with `ω₀/2 = Δ`. See `.knowledge/conventions.md`.

## Solvability statement

T6 (single-mode spin-boson). The Rabi model has only a `Z₂` parity symmetry `Π = σ^z exp(iπ a†a)` (`[H_R, Π] = 0`), yet Braak (2011) showed it is **exactly solvable**: the *regular* spectrum in each parity sector is given by the zeros of a **transcendental** `G`-function `G_±(x)`, and the corresponding energies are `E = x − g²/ω`. This is **Tier B — exact but transcendental**: there is no closed algebraic form, only the roots of `G_±`. The rare *exceptional* (doubly parity-degenerate, "baseline") eigenvalues `E = nω − g²/ω` appear only for special `(g, Δ)` tuned so `K_n(n) = 0`; they are not scanned here. **Not closed-form:** the eigenvalues themselves (they are roots of `G_±`); everything else — the recurrence, the parity structure, the `E = x − g²/ω` map — is exact and explicit.

## The Braak G-function (transcribed verbatim from [@Braak2011], Eqs. 3–5)

$$ G_\pm(x) = \sum_{n=0}^{\infty} K_n(x)\left[1 \mp \frac{\Delta}{x - n\omega}\right]\left(\frac{g}{\omega}\right)^{n}, \qquad n\,K_n = f_{n-1}(x)\,K_{n-1} - K_{n-2} $$

with `K₀ = 1`, `K₁(x) = f₀(x)`, and

$$ f_n(x) = \frac{2g}{\omega} + \frac{1}{2g}\left(n\omega - x + \frac{\Delta^2}{x - n\omega}\right). $$

`G_±(x)` has simple poles at `x = 0, ω, 2ω, …` (the uncoupled-mode levels); its zeros `x^±_n` give the parity-`±1` energies `E^±_n = x^±_n − g²/ω`. **The ED match is the gate:** the script builds `G_±`, finds its roots, and compares the lowest 8 energies in each parity to a parity-resolved truncated-boson ED to `1e-8` (Fock cutoff `n_max = 120`, convergence-checked vs `200`). A wrong transcription of the recurrence would miss the ED — so this comparison certifies the transcription. Braak's Fig. 1 (`g = 0.7`, `Δ = 0.4`, `ω = 1`) states **six** parity-`+` zeros and **five** parity-`−` zeros (including the ground state) in `x ∈ [−1, 5]`; those counts are reproduced as a literature-pinned check.

## Exact results

- Regular spectrum (each parity `±`): `E^±_n = x^±_n − g²/ω`, where `G_±(x^±_n) = 0` [@Braak2011]
- `G`-function, recurrence, `f_n`: Eqs. 3–5 above, verbatim [@Braak2011]
- Parity symmetry: `Π = σ^z exp(iπ a†a)`, `[H_R, Π] = 0`, `Π² = 1` — the `Z₂` that makes `G_+`/`G_-` decouple [@Braak2011]
- Exceptional (baseline) eigenvalues `E = nω − g²/ω`, doubly parity-degenerate, at `K_n(n) = 0` (special `g, Δ`; not scanned) [@Braak2011]
- Ground state has parity `−1` (lies in `G_-`), matching Braak's Fig. 1 [@Braak2011]

## Oracle script

`python oracle.py --g 0.7 --Delta 0.4` → prints `e_ground`, `e_first_excited`, `gap`, `n_parity_plus_below_6`, `n_parity_minus_below_6`. Importable: `compute(g=0.7, Delta=0.4, omega=1.0)`; helpers `G(x,g,Delta,omega,parity,nterms)`, `g_roots(...)`, `rabi_energies(...)`, `ed_energies_by_parity(n_max,g,Delta,omega)`.
Self-test anchors: (1) **THE GATE** — the lowest 8 `G`-roots in each parity match the parity-resolved truncated-boson ED to `1e-8` at two `(g,Δ)` points, ED **Fock-converged** `n_max = 120` vs `200` (`1e-10`); (2) **parity symmetry** `[H,Π] = 0`, `Π² = 1` operator-level; (3) **Braak Fig-1 root count** — six `G_+` and five `G_-` zeros in `x ∈ [−1,5]` at `g=0.7, Δ=0.4`; (4) **JC limit** — at small `g` the Rabi ED approaches the Jaynes–Cummings closed form within a documented `O(g²)` (Bloch–Siegert) band that shrinks as `g → 0`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e_ground` | `g=0.7, Δ=0.4, ω=1` (Braak Fig. 1) | `≈ −0.70781` (root of `G_-`) | [@Braak2011] |
| parity-`+` root count | `g=0.7, Δ=0.4`, `x ∈ [−1,5]` | `6` | [@Braak2011] |
| parity-`−` root count | `g=0.7, Δ=0.4`, `x ∈ [−1,5]` | `5` (incl. ground state) | [@Braak2011] |
| energy from root | any | `E = x − g²/ω` | [@Braak2011] |
| exceptional eigenvalues | `K_n(n)=0` | `E = nω − g²/ω` | [@Braak2011] |

## Verification recipes

- To check a Rabi ED run: build `ω a†a + g σ^x(a+a†) + Δ σ^z` with a Fock cutoff, split eigenstates by `Π = σ^z exp(iπ a†a)`, and compare the lowest levels to `rabi_energies(g, Δ, ω, parity=±1)` (`1e-8`, once the ED is Fock-converged — **always** re-run with a larger cutoff). A mismatch flags a wrong `σ^x` coupling (RWA truncation) or an unconverged cutoff.
- To validate an RWA / Jaynes–Cummings approximation: compare `quantum-rabi`'s ED with `jaynes-cummings`'s closed form at `(g, Δ = ω₀/2, ω)`; they agree up to a Bloch–Siegert `O(g²/ω)` shift that vanishes as `g → 0`.
- Cross-reference `jaynes-cummings` (RWA limit) and `dicke-tavis-cummings` (`H_Rabi` is the `N = 1` non-RWA / Dicke member); same T6 family as `lmg`.

## Key reference

[@Braak2011] — D. Braak, "Integrability of the Rabi Model" (PRL **107**, 100401, 2011): the exact `G`-function solution of the quantum Rabi model, source of the Hamiltonian convention, the `G_±(x)` series, the `K_n`/`f_n` recurrence, and the `E = x − g²/ω` map transcribed above. Rendered: ./10-1103-physrevlett-107-100401.md.

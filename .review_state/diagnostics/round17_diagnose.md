# Diagnostic Report: Round 17 — "Nonlocal strategies and local no-go" (lines 226–256)

## Summary

The section is well-written and accurately reflects the appendix proofs. Most claims are correctly stated and properly referenced. I found **no critical issues**. There are several minor issues related to clarity and precision.

---

## Issues

---
ISSUE #1
Location: line ~241 ("The expectation value factorizes (by π-invariance of ρ^{⊗2k})")
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The parenthetical "(by π-invariance of ρ^{⊗2k})" is used to explain the factorization, but in the appendix proof (lines 1352–1356), π-invariance of ρ^{⊗2k} is used to *remove the symmetrization* sym_π (first equality), while the factorization into odd×even traces is a separate step (tensor product structure). The current phrasing conflates two distinct steps.
Suggested fix: Change to something like "The expectation value simplifies (using $\pi$-invariance of $\rho^{\ox 2k}$ to remove the symmetrization, then factorizing odd and even subsystems)".
---

---
ISSUE #2
Location: line ~244 ("for $\mathbf{a} < \mathbf{b}$")
Category: MISSING_INTUITION
Severity: MINOR
Description: The main text only presents the eigenbasis for the $\mathbf{a} < \mathbf{b}$ case. The appendix (lines 1381–1383) also has the $\mathbf{a} = \mathbf{b}$ case ($\ket{\Phi_\mathbf{a}}\ket{\Phi_\mathbf{a}}$), which is a product state in the eigenbasis. For PRL brevity this is acceptable, but a reader might wonder about the full basis completeness.
Suggested fix: No change strictly needed, but could add "(and $\ket{\Phi_\mathbf{a}}^{\ox 2}$ when $\mathbf{a}=\mathbf{b}$)" after the eigenbasis expression.
---

---
ISSUE #3
Location: line ~247 ("additional $k$-replica rounds, each using $k\cdot n$ ancilla qubits")
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The appendix Lemma (line 1361) states "rounds of a $2k$-copy measurement (on $\rho^{\otimes k}\otimes\sigma^{\otimes k}$)". The main text says "$k$-replica rounds" which could be misread as using only $k$ copies total per round, when in fact each round requires $2k$ copies ($k$ of $\rho$ plus $k$ of the auxiliary $\sigma$).
Suggested fix: Replace "additional $k$-replica rounds, each using $k\cdot n$ ancilla qubits" with "additional $2k$-copy rounds (on $\rho^{\ox k}\ox\sigma^{\ox k}$ with auxiliary state $\sigma$)".
---

---
ISSUE #4
Location: line ~251 ("Since $\tilde{O}_P$ has eigenvalues $\{+1,0,-1\}$ (non-binary), Theorem~\ref{thm:linear-equiv} does not apply: estimation may be strictly easier than compatibility.")
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The logical chain is slightly loose. Theorem `thm:linear-equiv` is about linear functionals with $\|O_i\|_\infty \leq 1$, establishing equivalence between f-compatibility and joint measurability. The Õ_P operators arise from *nonlinear* functionals tr(Pρ²), so the theorem doesn't apply for that reason (nonlinearity), not primarily because the eigenvalues are non-binary. The non-binary eigenvalue structure is relevant because it means the induced POVMs have 3 outcomes rather than 2, breaking the binary equivalence.
Suggested fix: Clarify: "Since $\tilde{O}_P$ has three eigenvalues $\{+1,0,-1\}$ rather than two, it cannot be reduced to a two-outcome POVM, and Theorem~\ref{thm:linear-equiv} does not apply."
---

---
ISSUE #5
Location: line ~253 ("two-copy local 3-design shadows incur second moment $\sim (11/3)^n \cdot (5/11)^{\mathrm{wt}(P)}$ for product states, with operator norm up to $5^n$ for entangled states")
Category: MISSING_INTUITION
Severity: MINOR
Description: The connection between "second moment" and sample complexity is implicit. A reader unfamiliar with shadow tomography may not immediately see why exponential second moment implies exponential sample complexity. A brief phrase would help.
Suggested fix: Add after "for entangled states": "implying sample complexity $\Omega((11/3)^n)$ even for the identity observable".
---

---
ISSUE #6
Location: line ~253 ("exponential in $n$ for any Pauli weight")
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The phrase "for any Pauli weight" could be misread as "the exponent is the same regardless of weight." In fact, the scaling $(11/3)^n \cdot (5/11)^w$ means higher-weight Paulis are *less* costly (by a factor of $(5/11)^w$), but the base $(11/3)^n$ ensures exponential cost for *all* weights including $w=0$. The intent is clear but could be more precise.
Suggested fix: Change to "exponential in $n$ regardless of Pauli weight" or "exponential in $n$ for every Pauli weight $w \geq 0$".
---

---
ISSUE #7
Location: line ~230 (section title "Nonlocal multi-copy strategies.")
Category: STYLE
Severity: MINOR
Description: The section title uses a period ("strategies.") following \prlsection formatting convention, which is consistent with the rest of the paper. No issue—just noting for completeness.
Suggested fix: None needed.
---

## Verification Summary

| Claim in main text | Appendix reference | Verified? |
|---|---|---|
| $\{A_P\}$ commute | Lines 1339–1350 | ✓ |
| $\tr(A_P \rho^{\ox 2k}) = [\tr(P\rho^k)]^2$ | Lines 1351–1356 | ✓ |
| Eigenbasis form for $k=2$ | Lines 1376–1384 | ✓ |
| Eigenvalue formula | Line 1377 | ✓ |
| Circuit realization (transversal CNOTs + adaptive) | Lines 1386–1416, Fig at 1421 | ✓ |
| Signal estimation $\cO(\varepsilon^{-4}\log|\cO|)$ | Lines 1360–1373 | ✓ |
| $\tilde{O}_P$ eigenvalues $\{+1,0,-1\}$ | Correct by direct calculation | ✓ |
| Second moment $(11/3)^n(5/11)^w$ for products | Lemma at line 1621, proof at 1708–1710 | ✓ |
| Operator norm $5^n$ for entangled | Line 1710 | ✓ |
| Non-product structure of $\tilde{O}_P$ blocks Theorem 3 | Correct structural argument | ✓ |

## Overall Assessment

**Quality: Good.** The section accurately conveys the key results from two substantial appendix sections (app:UB_nonlin_P_shad and app:local_shadow) in compact PRL form. All quantitative claims match the appendix. The narrative arc—nonlocal strategy achieves O(1), local is exponential, therefore entanglement is a resource—is clear and compelling. The open questions (sign recovery efficiency, arbitrary-k local lower bound) are honestly flagged. The 6 minor issues above are suggestions for improved clarity, not corrections of errors.

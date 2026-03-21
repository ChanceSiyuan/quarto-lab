# Round 16 Diagnostic: "Tensor product structure and nonlinearity" (lines 194–225)

## Summary

This section covers two conceptually distinct results: (A) the tensor product factorization theorem reducing n-qubit local estimation to n single-qubit SDPs, and (B) the linear–nonlinear dichotomy showing nonlinear functionals can be exponentially easier. The writing is generally clear and the claims are correct, but there are several referencing and notation issues.

**Issue count:** 6 total (0 CRITICAL, 2 MAJOR, 4 MINOR)

---

## Issues

---
ISSUE #1
Location: line ~209 (`by Theorem~\ref{thm:linear-equiv},`)
Category: MISSING_REFERENCE (forward reference)
Severity: MAJOR
Description: Line 209 invokes "Theorem~\ref{thm:linear-equiv}" to justify the connection between the f-incompatibility SDP and joint measurability of unsharp Paulis. However, Theorem~\ref{thm:linear-equiv} is not stated until lines 215–217, six lines later. In a compressed PRL format, a forward reference to a theorem the reader hasn't seen yet disrupts the logical flow. The "Recovering 3^w" paragraph logically depends on both the tensor factorization (Theorem 1, already stated) AND the linear equivalence (Theorem 2, not yet stated), but only the latter is forward-referenced.
Suggested fix: Restructure so Theorem~\ref{thm:linear-equiv} appears BEFORE the "Recovering 3^w" paragraph. Concretely, swap the order: place the "When nonlinearity helps" subsection (lines 212–217) before "Recovering 3^w" (line 209), or at minimum move just the theorem statement. Alternatively, replace the forward reference with a brief inline justification: "since the functionals are linear with $\|P_i\|_\infty = 1$, f-compatibility reduces to joint measurability of $\{(\1 \pm P_i)/2\}$ (Lemma~\ref{thm:linear_functional_compatibility})".
---

---
ISSUE #2
Location: line ~207 (`$N = \textcolor{red}{\Theta}\!\left(k\cdot(\prod_l s^*_l)^2\cdot\varepsilon^{-2}\cdot\log(|\cA|/\delta)\right)$`)
Category: NOTATION_INCONSISTENCY
Severity: MAJOR
Description: The copy-complexity at line 191 (eq:copy-complexity) uses $\cO(\cdot)$ (upper bound only). Here at line 207 the text switches to $\Theta(\cdot)$ (tight bound) without explanation. The $\Theta$ is justified by combining the $\cO$ upper bound (line 191) with the $\Omega$ lower bound from Corollary~\ref{cor:tensor-sampling} (appendix line 928–933), but the reader of the main text has no way to know this since the corollary is never cited here. Either cite the lower bound or use $\cO$ consistently.
Suggested fix: Either (a) add a parenthetical: "$N = \Theta(\cdots)$ (matching lower bound: Corollary~\ref{cor:tensor-sampling})", or (b) revert to $\cO$ for consistency with eq:copy-complexity and note the matching lower bound separately.
---

---
ISSUE #3
Location: line ~202 (`s^*_{\mathrm{loc}}(\cF) = \prod_{l=1}^n s^*_l`)
Category: NOTATION_INCONSISTENCY
Severity: MINOR
Description: The main text writes $s^*_l$ dropping the copy-number subscript $k$, while the appendix (line 890) writes $s^*_k(\cF_l)$ and the definition at line 204 says "single-site robustness from~\eqref{eq:f-compat-prog} restricted to site $l$". Since $s^*$ depends on $k$ (this is the whole point of multi-copy strategies), suppressing $k$ here could confuse readers who want to optimize over $k$ later.
Suggested fix: Write $s^*_l(k)$ or $s^*_k(\cF_l)$ to match the appendix, or add "where $s^*_l \equiv s^*_k(\cF_l)$" after line 204.
---

---
ISSUE #4
Location: line ~213 (`f-incompatibility reduces to standard joint measurability of the induced two-outcome POVMs $\{(\1\pm O_i)/2\}$ (Lemma~\ref{thm:linear_functional_compatibility}): estimation is exactly as hard as compatibility.`)
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The phrase "estimation is exactly as hard as compatibility" is imprecise. What is meant is that the f-incompatibility robustness equals the joint measurability robustness ($s^*_\cF = s^*_\text{JM}$). The word "hard" is colloquial and could be misread as a computational complexity statement. Also, this sentence essentially states what Theorem~\ref{thm:linear-equiv} (lines 215–217) formalizes, creating mild redundancy.
Suggested fix: Replace with: "the f-incompatibility robustness equals the joint measurability robustness (Lemma~\ref{thm:linear_functional_compatibility})." This also reduces redundancy with the theorem statement that follows.
---

---
ISSUE #5
Location: line ~225 (`it is an instance of \textcolor{red}{f-compatible estimation (zero f-incompatibility robustness)}`)
Category: REDUNDANCY
Severity: MINOR
Description: "f-compatible estimation" already means $r^* = 0$ by definition. The parenthetical "(zero f-incompatibility robustness)" is redundant.
Suggested fix: Shorten to: "it is an instance of f-compatible estimation" or "it achieves $s^* = 1$ (f-compatible)."
---

---
ISSUE #6
Location: line ~197 (`a \emph{local} $k$-replica strategy uses an adaptive product POVM on $(\mathbb{C}^2)^{\ox k}$ per site`)
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The phrase "adaptive product POVM on $(\mathbb{C}^2)^{\ox k}$ per site" is slightly misleading since the adaptivity is across sites, not within a site. A reader could parse "adaptive product POVM" as a single object. The appendix (Definition at line 852) makes clear that the POVM is a product across sites with each factor potentially conditioned on earlier outcomes. Also, the appendix proof (line 911) ultimately argues that adaptivity doesn't help for product-form linearizations, which is worth mentioning.
Suggested fix: Rephrase to: "a \emph{local} $k$-replica strategy uses a product POVM across qubit sites on $(\mathbb{C}^2)^{\ox k}$ per site, where each site's measurement may adapt to outcomes at earlier sites (Definition~\ref{def:local-k-replica-f-incompatibility})."
---

## Cross-reference verification

| Main text ref | Target | Correct? |
|---|---|---|
| Definition~\ref{def:local-k-replica-f-incompatibility} (line 197) | Appendix line 852 | ✓ |
| \eqref{eq:f-compat-prog} (line 204) | Line 185 | ✓ |
| \eqref{eq:copy-complexity} (line 207) | Line 190 | ✓ |
| Theorem~\ref{thm:linear-equiv} (line 209) | Line 215 (forward ref) | ✓ but forward |
| Lemma~\ref{thm:linear_functional_compatibility} (line 213) | Appendix line 597 | ✓ |
| Appendix~\ref{app:Bell_shadow} (line 223) | Appendix line 1123 | ✓ |

## Claims vs proofs verification

| Claim | Appendix proof | Match? |
|---|---|---|
| Tensor factorization $s^*_\text{loc} = \prod_l s^*_l$ | Lines 895–924 (full proof with UB+LB) | ✓ |
| Linear equiv $s^*_\cF = s^*_\text{JM}$ | Lines 601–629 (Lemma proof) | ✓ |
| Squaring trick: $[P_i\otimes P_i, P_j\otimes P_j]=0$ | Lines 952–957 (Case 1 example) | ✓ |
| Bell measurement gives $s^*=1$ | Lines 1123–1163 | ✓ |
| $s^*_l = \sqrt{3}$ for single-qubit Paulis | Lines 960–964 (Case 2) | ✓ |

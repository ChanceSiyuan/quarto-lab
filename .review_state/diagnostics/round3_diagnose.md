# Diagnostic Report: "Tensor product structure and nonlinearity" (lines 194–225)

## Summary

6 issues found: 1 MAJOR, 5 MINOR. The section is largely accurate and well-written. The main substantive issue is a terminology error on line 225 ("f-incompatible" should be "f-compatible"). The remaining issues are minor: a condition mismatch with the appendix, a narrative ordering concern, and small clarity improvements.

---

## ISSUE #1
**Location:** line ~225 ("it is an instance of f-incompatible estimation with zero robustness penalty")
**Category:** CLAIM_MISMATCH
**Severity:** MAJOR
**Description:** Since $s^*=1$ means $r^*=0$, the squared Pauli functionals are *f-compatible* (zero f-incompatibility). Calling this "f-incompatible estimation" contradicts the paper's own Definition~\ref{def:f-incompatibility} and line 598 of the appendix, which defines $k(\cF)$ as the copy number where $r^*=0$. The sentence should say "f-compatible."
**Suggested fix:** Replace "f-incompatible estimation with zero robustness penalty" with "f-compatible estimation (zero f-incompatibility robustness)."

---

## ISSUE #2
**Location:** line ~200 ("each $F_{\alpha_l}^{(l)} \neq 0$")
**Category:** CLAIM_MISMATCH
**Severity:** MINOR
**Description:** The appendix theorem statement (line 884–893) does not include the condition $F_{\alpha_l}^{(l)} \neq 0$. The condition is used implicitly in the lower bound proof (line 909: dividing by $\tr[F_{\alpha_k}\sigma_k]$), and is WLOG since $F_{\alpha_l}^{(l)}=0$ implies $F_\alpha=0$ (trivial estimation). However, the main text and appendix theorem statements should match.
**Suggested fix:** Either add "$F_{\alpha_l}^{(l)} \neq 0$" to the appendix theorem statement, or remove it from the main text (since it's WLOG and the appendix omits it).

---

## ISSUE #3
**Location:** line ~209 ("the single-qubit optimization asks for joint measurability of unsharp Paulis...")
**Category:** MISSING_REFERENCE
**Severity:** MINOR
**Description:** This sentence invokes the equivalence between f-incompatibility and joint measurability of unsharp POVMs—which is exactly Theorem~\ref{thm:linear-equiv} (lines 215–217). But Theorem 2 appears *after* this paragraph. The reader encounters the application before the theorem that justifies it.
**Suggested fix:** Add a forward reference: "By Theorem~\ref{thm:linear-equiv} below, the single-qubit optimization..." or restructure to place Theorem 2 before the $3^w$ recovery paragraph.

---

## ISSUE #4
**Location:** line ~207 ("$N = \cO\!\left(k\cdot(\prod_l s^*_l)^2\cdot\varepsilon^{-2}\cdot\log(|\cA|/\delta)\right)$")
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** This states the sample complexity as $\cO$ (achievability/upper bound), consistent with eq. (2). However, the appendix Corollary~\ref{cor:tensor-sampling} (line 930) states the *lower bound* $\Omega(\cdot)$. Since the tensor factorization gives $s^*_{\mathrm{loc}} = \prod_l s^*_l$ exactly, both upper and lower bounds hold. The main text could be more precise by noting this is tight (matching upper and lower).
**Suggested fix:** Change to "$N = \Theta\!\left(\cdots\right)$" or add "(matching the lower bound of Corollary~\ref{cor:tensor-sampling})."

---

## ISSUE #5
**Location:** line ~213 ("Lemma~\ref{thm:linear_functional_compatibility}")
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The label `thm:linear_functional_compatibility` uses the prefix `thm:` but the environment is `\begin{lemma}` (line 604). While LaTeX doesn't enforce label-environment consistency, this is confusing for maintenance. Similarly, Theorem~\ref{thm:linear-equiv} in the main text (line 215) appears to be a main-text theorem that summarizes the appendix Lemma; the relationship could be clearer.
**Suggested fix:** No text change needed in this pass, but flag for label cleanup (rename to `lem:linear_functional_compatibility`).

---

## ISSUE #6
**Location:** line ~223 ("Since $\{X\ox X, Y\ox Y, Z\ox Z\}$ all commute, they share a common eigenbasis---the Bell basis.")
**Category:** MISSING_INTUITION
**Severity:** MINOR
**Description:** The claim that the common eigenbasis is the Bell basis is stated without justification. A reader unfamiliar with this fact has no way to verify it from the main text. The appendix (line 955–959) provides the explicit eigenvalue formula. A brief parenthetical would help.
**Suggested fix:** Add "(each $P\otimes P$ is diagonal in the Bell basis with eigenvalues $\pm 1$; see Appendix~\ref{app:Bell_shadow})" or similar.

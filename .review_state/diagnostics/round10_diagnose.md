# Diagnostic Report: Round 10 — Examples Section (lines 950–1122)

**Target:** `\section{Examples}` covering Cases 1–3 with various replica numbers.
**Scope:** Lines 950–1122 of `main.tex`.

---

## ISSUE #1
**Location:** Line ~1029
> "Since $\dim\mathrm{Sym}^3(\mathbb{C}^2) = 4$ equals the number of operators ($3$ Paulis $+$ identity), a common eigenbasis exists that diagonalizes all $F_P$ simultaneously."

**Category:** LOGICAL_GAP
**Severity:** CRITICAL

**Description:** The spin-3/2 angular momentum operators $\{J_X, J_Y, J_Z\}$ do **not** commute ($[J_X, J_Y] = iJ_Z$ etc.), so they cannot have a common eigenbasis, regardless of the dimension matching the number of operators. The claim "dim = number of operators ⟹ common eigenbasis" is a non-sequitur. Having 4 linearly independent Hermitian operators on $\mathbb{C}^4$ does not imply mutual commutativity.

The conclusion $s^* = 1$ is **numerically correct** (verified by SDP), but the stated justification is mathematically wrong. A correct argument would need to invoke the SDP result directly, or show that there exists a POVM (not necessarily a PVM) with bounded estimators. One valid approach: spin-3/2 coherent states at the vertices of a cuboctahedron (or appropriate spherical 3-design) provide a POVM whose expectation values $h_P(c) = \langle n_c | J_P/j | n_c \rangle = (n_c)_P$ satisfy $|h_P| \leq 1$.

**Suggested fix:** Replace the sentence with: "Since $\dim\mathrm{Sym}^3(\mathbb{C}^2) = 4$ and the eigenvalues of each $F_P$ lie in $[-1,1]$, the dual SDP (Lemma~\ref{lem:dual-primal-bilinear}) confirms $s^* = 1$, meaning a POVM with estimators bounded by 1 exists—despite the operators not commuting." Remove the false claim about a common eigenbasis.

---

## ISSUE #2
**Location:** Line ~1116
> "This contrasts with the $k=3$ Hermitian case, where $\dim\mathrm{Sym}^3 = 4$ matches the number of operators and a simultaneous eigenbasis exists."

**Category:** LOGICAL_GAP
**Severity:** MAJOR

**Description:** Same false claim as Issue #1, repeated. The spin-3/2 operators do not have a simultaneous eigenbasis.

**Suggested fix:** Replace with: "This contrasts with the $k=3$ Hermitian case, where the SDP yields $s^* = 1$ because the eigenvalues of $F_P$ on $\mathrm{Sym}^3(\mathbb{C}^2)$ already lie in $[-1,1]$ and the 4-dimensional space is large enough for a POVM to resolve the incompatibility."

---

## ISSUE #3
**Location:** Line ~1072
> "with estimators $h_P(c) = \frac{2}{\sqrt{3}}\,c_P$ and $h_0(c) = \frac{2}{\sqrt{3}}\,c_0$."

**Category:** NOTATION_INCONSISTENCY
**Severity:** MAJOR

**Description:** The POVM at line 1069–1071 is the **coarse-grained** 8-element POVM indexed by $c = (c_X, c_Y, c_Z) \in \{\pm 1\}^3$. The estimator $h_0(c) = \frac{2}{\sqrt{3}} c_0$ refers to a sign $c_0$ that is **not part of the coarse-grained index**. The coarse-graining (lines 1067–1068) explicitly merged the two SWAP signs $c_0 = \pm 1$, so $c_0$ is undefined for the 8-outcome POVM.

Moreover, the correct estimator for SWAP on the symmetric subspace is simply $h_0 = 1$ (constant) for all 8 symmetric outcomes, and $h_0 = -1$ for the singlet element, since $\mathrm{SWAP} = \Pi_{\mathrm{Sym}} - |\Psi^-\rangle\langle\Psi^-|$.

**Suggested fix:** Either (a) present the full 16-element POVM with all four sign indices and use $h_0(c) = (2/\sqrt{3})c_0$, or (b) state the 8-element coarse-grained POVM with $h_P(c) = (2/\sqrt{3})c_P$ for $P \in \{X,Y,Z\}$ and note separately that $h_0 = 1$ for symmetric outcomes and $h_0 = -1$ for the singlet.

---

## ISSUE #4
**Location:** Line ~968
> "Hence all $8$ sign vectors ar being active since $\Delta_c$ always contain one zero eigenvalue."

**Category:** GRAMMAR
**Severity:** MINOR

**Description:** Two errors: "ar" → "are"; "contain" → "contains". The phrasing "ar being active" is also awkward.

**Suggested fix:** "Hence all $8$ sign vectors are active, since $\Delta_c$ always has a zero eigenvalue."

---

## ISSUE #5
**Location:** Line ~972
> "the complimentary slackness condition"

**Category:** TYPO
**Severity:** MINOR

**Description:** "complimentary" → "complementary".

**Suggested fix:** Replace with "the complementary slackness condition".

---

## ISSUE #6
**Location:** Line ~982
> "the optimal joint measurement is ... which is precisely the Eq.~\eqref{eq:case2-povm}. The complementary slackness analysis confirms this POVM is also optimal in the task to simultaneously unbiasedness estimation of $\{\tr(X \rho),\tr(Y \rho),\tr(Z \rho)\}$ and gives complexity $N =\tilde{\Theta}(1/(\varepsilon^2 (s^*)^2)) = \tilde{\Theta}(3/(\varepsilon^2)) $"

**Category:** GRAMMAR
**Severity:** MINOR

**Description:** Three issues: (1) "the task to simultaneously unbiasedness estimation" is ungrammatical; (2) "the Eq." should be "Eq." (no article); (3) missing period at end of paragraph.

**Suggested fix:** "...which is precisely Eq.~\eqref{eq:case2-povm}. The complementary slackness analysis confirms this POVM is also optimal for the task of simultaneous unbiased estimation of $\{\tr(X\rho), \tr(Y\rho), \tr(Z\rho)\}$ and gives complexity $N = \tilde{\Theta}(1/(\varepsilon^2 (s^*)^2)) = \tilde{\Theta}(3/\varepsilon^2)$."

---

## ISSUE #7
**Location:** Line ~993
> "This per-site analysis gives $3^w$ scaling"

**Category:** CLARITY
**Severity:** MINOR

**Description:** The variable $w$ is not defined. From context (estimating weight-$w$ Pauli operators in $\{I,X,Y,Z\}^{\otimes n}$), $w$ is the Hamming weight (number of non-identity tensor factors). This should be stated explicitly.

**Suggested fix:** "This per-site analysis gives $3^w$ scaling for weight-$w$ Pauli strings (where $w$ is the number of non-identity tensor factors) in estimating $\{I,X,Y,Z\}^{\otimes n}$..."

---

## ISSUE #8
**Location:** Line ~1035
> "based on the Definiton~\ref{def:f-incompatibility}"

**Category:** TYPO
**Severity:** MINOR

**Description:** "Definiton" → "Definition".

**Suggested fix:** "based on Definition~\ref{def:f-incompatibility}"

---

## ISSUE #9
**Location:** Line ~1035
> "$\mathcal{\cF}$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR

**Description:** `\mathcal{\cF}` expands to `\mathcal{\mathcal{F}}` — a double application of `\mathcal`. This likely renders correctly in most engines (idempotent), but is technically wrong LaTeX.

**Suggested fix:** Replace `$\mathcal{\cF}$` with `$\cF$`.

---

## ISSUE #10
**Location:** Line ~1048
> "tensor product decompostion"

**Category:** TYPO
**Severity:** MINOR

**Description:** "decompostion" → "decomposition".

**Suggested fix:** Fix the spelling.

---

## ISSUE #11
**Location:** Line ~1021
> "among $8$ cube vertices one can find at most $2$ mutually antipodal states"

**Category:** CLARITY
**Severity:** MINOR

**Description:** The phrase "2 mutually antipodal states" is potentially confusing. There are 4 antipodal *pairs* among the 8 cube vertices. The intended meaning is: at most 2 states from $\{|\phi_c\rangle^{\otimes 2}\}$ can be mutually orthogonal (since orthogonality requires antipodality, and 3 states cannot be pairwise antipodal). The argument is correct but the phrasing could be clearer.

**Suggested fix:** "However, $|\langle\phi_a|\phi_b\rangle|^4 = 0$ requires $\vec{n}_a = -\vec{n}_b$ (antipodal), so at most 2 of the 8 states $\{|\phi_c\rangle^{\otimes 2}\}$ can be mutually orthogonal (one antipodal pair). Since we need 3 mutually orthogonal symmetric states to form a PVM basis on $\mathrm{Sym}^2(\mathbb{C}^2) \cong \mathbb{C}^3$, no PVM can be assembled from the optimal elements."

---

## ISSUE #12
**Location:** Line ~1114
> "$\sum_c \tilde{\Pi}_c = \1^{\ox 4}$"

**Category:** IMPLICIT_ASSUMPTION
**Severity:** MINOR

**Description:** For the $k=4$ POVM on $(\mathbb{C}^2)^{\otimes 4}$, the paper claims the 16-element POVM sums to $\mathbb{1}^{\otimes 4}$. However, $(\mathbb{C}^2)^{\otimes 4}$ decomposes into irreps (spin-2, spin-1, spin-0), and the operators $F_P^{(4)}$ vanish on non-symmetric subspaces. The POVM must include additional elements for the non-symmetric subspaces (analogous to the singlet element in the $k=2$ case). If the 16 elements only cover $\mathrm{Sym}^4$, additional elements are needed. This is stated implicitly but deserves a brief note.

**Suggested fix:** Add a clarifying sentence: "As in the $k=2$ case, additional POVM elements supported on the non-symmetric subspaces (with $h_\alpha = 0$) are appended to satisfy completeness on the full space."

---

## ISSUE #13
**Location:** Line ~1062
> "using $\tr(F_P^2) = 2$ for the spin-$1$ operators"

**Category:** (verification — no issue)

**Description:** Verified: eigenvalues $\{1, 0, -1\}$ give $\tr(F_P^2) = 1 + 0 + 1 = 2$. ✓

---

## Summary

| Severity | Count | Issue #s |
|----------|-------|----------|
| CRITICAL | 1     | #1       |
| MAJOR    | 2     | #2, #3   |
| MINOR    | 9     | #4–#12   |
| **Total**| **12**|          |

### Most Critical Issue

**Issue #1 (line ~1029):** The paper claims that a "common eigenbasis exists" for the spin-3/2 angular momentum operators because $\dim = 4$ equals the number of operators. This is false — the operators do not commute. The conclusion $s^* = 1$ is correct (verified by SDP), but the reasoning is a logical non-sequitur. This must be corrected to avoid invalidating the paper's argument for $k(\mathcal{F}) = 3$.

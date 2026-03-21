# Round 7 Diagnostic Report: "Definition of f-incompatibility" (Lines 421–680)

**Scope:** Lines 421–680 of `main.tex` (§ "The definition of f-incompatibility" through the end of the linearization lemma and beginning of the SDP section)

---

## ISSUE #1
**Location:** Line ~491
> "We say $f_\alpha(\rho)$ is a rank-$r$ polynomial of $\rho$ if it is a rank-$r$ multi-variant polynomial of $\rho_{j,k}$."

**Category:** TYPO
**Severity:** MINOR
**Description:** "multi-variant" should be "multivariate."
**Suggested fix:** Replace "multi-variant" with "multivariate."

---

## ISSUE #2
**Location:** Line ~491
> "rank-$r$ polynomial"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The text uses "rank-$r$" to mean "degree-$r$" polynomial. Throughout the classical statistics section (lines 421–448), "degree" is used consistently. Later (line 648), Definition 6 uses "degree-$r$." The term "rank" for polynomial degree is non-standard and conflicts with the linear-algebra meaning of "rank" (which appears elsewhere in the paper for matrices). This inconsistency appears again at lines 555, 646, 657, 670.
**Suggested fix:** Replace all instances of "rank-$r$ polynomial" / "rank-$r$ functions" / "rank-$r$ properties" with "degree-$r$ polynomial" / "degree-$r$ functions" / "degree-$r$ properties" for consistency with Definition 6 and the classical section.

---

## ISSUE #3
**Location:** Line ~490
> "$\vec{p}_i(\rho) = (\tr[A_i^{(r)}\rho])_{r \in \Omega_i}$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The superscript $(r)$ on $A_i^{(r)}$ uses $r$ as an outcome index, but $r$ is simultaneously used as the polynomial degree throughout the section (lines 491, 555, 646, 648, 657). This creates ambiguity.
**Suggested fix:** Use a different letter for the outcome index, e.g., $A_i^{(a)}$ with $a \in \Omega_i$, consistent with the POVM notation $E_{a|x}$ used earlier in the paper.

---

## ISSUE #4
**Location:** Line ~492
> "we need to impose the condition $\max_{\rho,\alpha} \|f_\alpha(\rho)\| = 1$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** $f_\alpha(\rho)$ is scalar-valued (a "state property"), so $\|f_\alpha(\rho)\|$ should be $|f_\alpha(\rho)|$ (absolute value, not operator norm).
**Suggested fix:** Replace $\|f_\alpha(\rho)\|$ with $|f_\alpha(\rho)|$.

---

## ISSUE #5
**Location:** Lines ~582–583
> "each single property can be $k$-replica unbiased estimated with scaling $s = 1$ since the maximum eigenvalue of $F_{\alpha}$, as defined in Eq~\eqref{eq:F_def}, now became $1$, thus the projective measurements on its eigenvectors form a valid estimation strategy with scaling $s = 1$."

**Category:** LOGICAL_GAP
**Severity:** MAJOR
**Description:** This argument assumes $F_\alpha$ is Hermitian (so that it has real eigenvalues and orthogonal eigenvectors supporting a projective measurement). However, Definition 6 (line 649) explicitly states "$F_\alpha$ is not necessarily Hermitian," and the discussion on line 502 explains why complex-valued $h_\alpha$ (hence non-Hermitian $F_\alpha$) are needed. For non-Hermitian $F_\alpha$, "maximum eigenvalue" is not well-defined as a real number, and projective measurement on eigenvectors is not a valid quantum measurement (eigenvectors need not be orthogonal).
**Suggested fix:** Either (a) restrict this paragraph to Hermitian $F_\alpha$ and note the non-Hermitian case requires a different argument, or (b) replace the eigenvector argument with: "since $\max_\rho |f_\alpha(\rho)| = 1$, for any informationally complete POVM $\{\Pi_j\}$ and the decomposition $F_\alpha = \sum_j h_\alpha(j)\Pi_j$, one can always find an estimation strategy for a single property with $|h_\alpha(j)| \leq 1$ by choosing a POVM adapted to $F_\alpha$." The cleanest fix is to restrict to Hermitian operators in this motivational paragraph.

---

## ISSUE #6
**Location:** Line ~583
> "For a set of normalized state properties, the scaling defined in Definition~\ref{def:k-copy-estimateability} must satisfy $s>1$"

**Category:** OVER_CLAIMING
**Severity:** MAJOR
**Description:** This claim is false as stated. For compatible properties (e.g., commuting observables), $s = 1$ is achievable even for the full set, giving $r^*_k = 0$. Indeed, line 591 defines $k(\cF)$ as the smallest $k$ with $r^*_k = 0$ (i.e., $s = 1$), directly contradicting this blanket claim. The intended meaning is that for **incompatible** sets, $s > 1$, but this qualification is missing.
**Suggested fix:** Change to: "For a set of normalized state properties that is not $k$-replica estimable with scaling $s = 1$, the minimum scaling must satisfy $s > 1$, and the increase of $s$ above $1$ reflects the hardness of simultaneous estimation."

---

## ISSUE #7
**Location:** Line ~590
> "We noted that $r^*_k(\cF) > 0$ must be satisfied since $s > 1$."

**Category:** OVER_CLAIMING
**Severity:** MAJOR
**Description:** Same issue as #6. This contradicts line 591 which defines $k(\cF)$ as the $k$ where $r^*_k = 0$. Should say $r^*_k \geq 0$, with $r^*_k > 0$ when $s^* > 1$ (i.e., when the properties are genuinely $k$-replica f-incompatible).
**Suggested fix:** Replace with: "We note that $r^*_k(\cF) \geq 0$, with $r^*_k(\cF) > 0$ if and only if the properties are genuinely $k$-replica f-incompatible (i.e., $s^*_k > 1$)."

---

## ISSUE #8
**Location:** Line ~559
> "a set of observables $\{O_1,\cdots,O_k\}$ with $\|O_i\|_{\infty} \leq 1$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** Uses $k$ for the number of observables, but $k$ is the copy number throughout this section. The number of POVMs/observables is $K$ elsewhere (e.g., line 420, 598).
**Suggested fix:** Replace $\{O_1,\cdots,O_k\}$ with $\{O_1,\cdots,O_K\}$.

---

## ISSUE #9
**Location:** Lines ~613, 620
> Proof of $r^*_k(\cF) \geq r^*_k(\cM)$ direction uses $h_i(j)$ to construct probabilities $p(\pm 1|i,j) := \frac{1 \pm (1+r)^{-1}h_i(j)}{2}$

**Category:** IMPLICIT_ASSUMPTION
**Severity:** MINOR
**Description:** Definition 4 (line 495) allows $h_\alpha: \cJ \to \mathbb{C}$. The probability construction on line 620 requires $h_i(j) \in \mathbb{R}$. This is WLOG since $O_i$ is Hermitian so $\tr[O_i\rho]$ is real, meaning the imaginary parts of $h_i(j)$ contribute nothing and can be dropped (with $|\text{Re}(h_i(j))| \leq |h_i(j)| \leq s$), but this step should be stated.
**Suggested fix:** Add after line 613: "Since $O_i$ is Hermitian, $\tr[O_i\rho]$ is real for all $\rho$. Replacing $h_i(j)$ by $\text{Re}(h_i(j))$ preserves unbiasedness and satisfies $|\text{Re}(h_i(j))| \leq |h_i(j)| \leq 1+r$, so we may assume $h_i(j) \in \mathbb{R}$ without loss of generality."

---

## ISSUE #10
**Location:** Line ~632
> "$\cF' := \{\1^{\ox (k-1)} \odot O_i\}_{i = 1}^K$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** $\cF$ is defined as a set of functionals $\{\tr(\rho O_i)\}$ but $\cF'$ is defined as a set of operators $\{\1^{\ox(k-1)} \odot O_i\}$. These are different types of objects. Based on context, $\cF'$ should be the set of functionals $\{\tr[\rho^{\ox k}(\1^{\ox(k-1)} \odot O_i)]\}$.
**Suggested fix:** Change to $\cF' := \{\tr[\sigma\,(\1^{\ox (k-1)} \odot O_i)]\}_{i=1}^K$ or, if operators are intended, rename to something like $\{F'_i\}$ and clarify.

---

## ISSUE #11
**Location:** Line ~653
> "satisfied $\tr[(O\ox\1^{m-1})S_m\,\rho^{\ox m}] = \tr(O\rho^m)$"

**Category:** TYPO + NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** (a) "satisfied" should be "satisfies" (subject-verb agreement). (b) $\1^{m-1}$ should be $\1^{\ox(m-1)}$ for consistency with notation elsewhere.
**Suggested fix:** "satisfies $\tr[(O\ox\1^{\ox(m-1)})S_m\,\rho^{\ox m}] = \tr(O\rho^m)$"

---

## ISSUE #12
**Location:** Line ~654
> "$F_\alpha = \1^{\ox (l-mp)} \ox [(O_\alpha\ox \1^{m-1}) \cdot S_{m}]^{\ox p}$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** $\1^{m-1}$ should be $\1^{\ox(m-1)}$.
**Suggested fix:** $F_\alpha = \1^{\ox (l-mp)} \ox [(O_\alpha\ox \1^{\ox(m-1)}) \cdot S_{m}]^{\ox p}$

---

## ISSUE #13
**Location:** Line ~555
> "the single-copy non-linear post-processing will require scaling $\Theta(\sqrt{2^n})$ copies of the state"

**Category:** CLARITY
**Severity:** MINOR
**Description:** Conflates "scaling factor" with "copies." The sentence mixes two quantities: the scaling factor $s$ and the number of copies.
**Suggested fix:** "...while single-copy non-linear post-processing requires a scaling factor of $\Theta(\sqrt{2^n})$" (dropping "copies of the state").

---

## ISSUE #14
**Location:** Lines ~563–576 (Pauli example)
> POVM indices $(s_x, s_z, s_y)$ and tensor product $X \ox Z \ox Y$

**Category:** CLARITY
**Severity:** MINOR
**Description:** The ordering $x, z, y$ (rather than $x, y, z$) is unconventional and may confuse readers. The tensor product in the POVM definition follows this same unusual ordering.
**Suggested fix:** Reorder to $(s_x, s_y, s_z)$ and $\ket{s_x}_X \ox \ket{s_y}_Y \ox \ket{s_z}_Z$ throughout the example. (The symmetrization makes the final result order-independent, but conventional ordering aids readability.)

---

## ISSUE #15
**Location:** Line ~661
> "Then $\sum_j h_\alpha(j)\,\tilde{\Pi}_j = F_\alpha$ holds as an operator identity (on the symmetric subspace, which suffices). This is precisely single-copy unbiased estimation of $\{F_\alpha\}$ on the state space $\cH^{\ox l}$."

**Category:** CLARITY
**Severity:** MINOR
**Description:** The parenthetical "(on the symmetric subspace, which suffices)" could mislead: single-copy estimation on $\cH^{\ox l}$ typically means the operator identity on ALL of $\cH^{\ox l}$. The proof actually works because $F_\alpha$ can be *defined* as $\sum_j h_\alpha(j)\tilde\Pi_j$ (which is an operator on all of $\cH^{\ox l}$), and this serves as a valid linearization since it matches $f_\alpha(\rho)$ on product states. But the presentation suggests $F_\alpha$ is given a priori and the identity only holds on the symmetric subspace.
**Suggested fix:** Rephrase: "Define $F_\alpha := \sum_j h_\alpha(j)\,\tilde{\Pi}_j$, which is an operator on $\cH^{\ox l}$ satisfying $\tr[F_\alpha\,\rho^{\ox l}] = f_\alpha(\rho)$ for all $\rho$ (hence a valid $l$-linearization). By construction, $\{F_\alpha\}$ admits single-copy estimation with scaling $s$ via $\{\tilde{\Pi}_j, h_\alpha(j)\}$."

---

## ISSUE #16
**Location:** Line ~643
> "\paragraph{Application on non-linear functionals}"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "Application on" is non-standard. Should be "Application to."
**Suggested fix:** "\paragraph{Application to non-linear functionals}"

---

## ISSUE #17
**Location:** Line ~571
> "$|h_P(j)| = 1 \leq 1$"

**Category:** CLARITY
**Severity:** MINOR
**Description:** $h_P$ is not defined; the estimators are $h_X, h_Y, h_Z$. Should say "for $P \in \{X,Y,Z\}$" or list all three.
**Suggested fix:** "$|h_P(j)| = 1 \leq 1$ for each $P \in \{X,Y,Z\}$" — or simply "$|h_X(j)| = |h_Y(j)| = |h_Z(j)| = 1$."

---

## ISSUE #18
**Location:** Line ~581
> "We say a set of state properties $\cF := \{f_{\alpha}(\rho)\}_{\alpha \in \cA}$ is normalized if $\forall \alpha, \max_{\rho} f_{\alpha}(\rho) = 1$."

**Category:** CLARITY
**Severity:** MINOR
**Description:** For complex-valued properties (allowed by Definition 4 via $h_\alpha: \cJ \to \mathbb{C}$), $\max_\rho f_\alpha(\rho) = 1$ is not well-defined since complex numbers are not ordered. Should use $\max_\rho |f_\alpha(\rho)| = 1$ for consistency with line 492.
**Suggested fix:** "$\forall \alpha,\; \max_{\rho} |f_{\alpha}(\rho)| = 1$."

---

---

# Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0     |
| MAJOR    | 3     |
| MINOR    | 15    |
| **Total**| **18**|

**Breakdown by category:**
- NOTATION_INCONSISTENCY: 6
- CLARITY: 5
- MINOR TYPO/GRAMMAR: 4
- OVER_CLAIMING: 2
- LOGICAL_GAP: 1
- IMPLICIT_ASSUMPTION: 1

**Most critical issue:** Issues #5, #6, #7 (collectively): The normalization paragraph (lines 581–591) contains an incorrect blanket claim that $s > 1$ (equivalently $r^* > 0$) for all normalized property sets, directly contradicted by the paper's own definition of $k(\cF)$ (the copy number where $r^* = 0$). Issue #5 compounds this by relying on a Hermitian-only argument (projective measurement on eigenvectors) for operators that the paper explicitly allows to be non-Hermitian. These issues affect the logical foundation of the f-incompatibility definition and need correction before the paper's central claims can stand.

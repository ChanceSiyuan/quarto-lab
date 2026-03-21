# Diagnostic Report: Tensor Product Extension (lines 850–949)

**File:** `_resource/Project__Compatiablity_of_properties/main.tex`
**Section:** `\subsection{Tensor product extension}` (Appendix, label `app:tensor`)
**Reviewer pass:** Round 9

---

## ISSUE #1
**Location:** line ~850
> "To utilize the f-incompatibility SDP for an $n$-qubit state $\rho^{\ox n}$"

**Category:** TYPO
**Severity:** MAJOR
**Description:** The state should be $\rho^{\otimes k}$ (k replicas of an n-qubit state), not $\rho^{\otimes n}$. The entire section concerns k-replica strategies on an n-qubit system; $\rho^{\otimes n}$ conflates the number of qubits with the number of copies.
**Suggested fix:** Replace `$\rho^{\ox n}$` with `$\rho^{\ox k}$`.

---

## ISSUE #2
**Location:** lines ~908–909
> The definition of $h'(j_n)$ and the claimed equality $\sum_{j_n} h'(j_n) \tr[\Pi^{(n)}_{j_n|j_1,\ldots,j_{n-1}} \sigma_n]$

**Category:** LOGICAL_GAP
**Severity:** CRITICAL
**Description:** The "peeling" argument breaks down for adaptive POVMs. In the adaptive case, $\Pi^{(n)}_{j_n|j_1,\ldots,j_{n-1}}$ depends on the conditioning variables $j_1,\ldots,j_{n-1}$. The inner sum on line 908 is:
$$\sum_{j_1,\ldots,j_{n-1}} h_\alpha(\vec{j}) \prod_{l=1}^{n} \tr[\sigma_l \Pi^{(l)}_{j_l|\cdot}]$$
Because $\Pi^{(n)}_{j_n|j_1,\ldots,j_{n-1}}$ varies with the conditioning, one cannot factor $\tr[\sigma_n \Pi^{(n)}_{j_n|\cdot}]$ out of the sum over $j_1,\ldots,j_{n-1}$. Therefore the `:=` definition on line 909, which claims to isolate an estimator $h'(j_n)$ multiplied by a single POVM element's trace, is ill-defined.

For non-adaptive product POVMs ($\Pi^{(l)}_{j_l|j_1,\ldots,j_{l-1}} = \Pi^{(l)}_{j_l}$), the argument works fine. But Definition 1 explicitly allows adaptive POVMs, and the theorem claims factorization over all local strategies including adaptive ones.

**Suggested fix:** Either:
(a) Restrict the lower bound proof to non-adaptive POVMs and add a separate argument that adaptivity does not help (e.g., by showing the optimal strategy is non-adaptive for product operators on product states), or
(b) Use an operator-level argument instead of the trace-based peeling. Specifically, one could partial-trace the operator constraint $\sum_{\vec{j}} h_\alpha(\vec{j}) \Pi_{\vec{j}} = F_\alpha$ against product operators on the first $n-1$ sites, avoiding the need to pass through scalar equations that mix adaptive conditioning.

---

## ISSUE #3
**Location:** line ~912
> "we can redefined the estimator function $h'(j_n)$. This forms a valid $k$-replica strategy for the operator set $\{F_{\alpha_n}^{(n)}\}_{\alpha_n}$. By the definition of $s^*_k(\cF_n)$, which is the minimum scaling factor, we have $|h'(j_n)| \geq s^*_k(\cF_n)$."

**Category:** UNJUSTIFIED_STEP / QUANTIFIER_ERROR
**Severity:** MAJOR
**Description:** The claim "$|h'(j_n)| \geq s^*_k(\cF_n)$" as stated asserts that EVERY value of $|h'(j_n)|$ is at least $s^*_k(\cF_n)$. This is not what optimality of $s^*_k$ gives. Optimality says: for any valid strategy with estimator $h'$, we have $\max_{j_n} |h'(j_n)| \geq s^*_k(\cF_n)$. The pointwise bound is false in general (e.g., $h'(j_n)$ could be 0 for some outcomes).

The weaker statement $\max_{j_n} |h'(j_n)| \geq s^*_k(\cF_n)$ is what's needed, but this then creates a problem for the recursive step: when dividing $h_\alpha(\vec{j})$ by $h'(j_n)$, the division is only valid when $h'(j_n) \neq 0$, and the bound on the quotient depends on which $j_n$ is chosen.
**Suggested fix:** Replace the pointwise bound with $\max_{j_n}|h'(j_n)| \geq s^*_k(\cF_n)$, and restructure the recursive argument to properly handle the maximization at each level. The final bound should read:
$$s = \max_{\vec{j}} |h_\alpha(\vec{j})| \geq \prod_{l=1}^n s^*_k(\cF_l)$$
with a careful argument about the existence of a $\vec{j}$ achieving this product.

---

## ISSUE #4
**Location:** line ~920
> $\left| \frac{h_{\alpha}(\vec{j})}{h'(j_n)\times \cdots \times h'(j_{2})} \right| \leq s^*_k(\cF_1)$

**Category:** SIGN_FACTOR_ERROR
**Severity:** CRITICAL
**Description:** The inequality direction appears reversed for the purpose of proving the lower bound. The paper wants to show $s \geq \prod_l s^*_k(\cF_l)$. If the quotient $|h_\alpha / (h'(j_n) \cdots h'(j_2))|$ is an estimator for site 1, then optimality gives $\max_{j_1} |h_\alpha(\vec{j}) / \prod_{m>1} h'(j_m)| \geq s^*_k(\cF_1)$, i.e., a $\geq$ bound.

With $\leq$, the chain gives $|h_\alpha(\vec{j})| \leq s^*_k(\cF_1) \cdot \prod_{m=2}^n |h'(j_m)|$, which bounds $|h_\alpha|$ from above — the wrong direction for proving $s \geq \prod s^*_l$.

Combined with Issue #3 (only $\max |h'(j_m)| \geq s^*_k(\cF_m)$), the correct conclusion should be:
$$s = \max_{\vec{j}} |h_\alpha(\vec{j})| \geq s^*_k(\cF_1) \cdot \prod_{m=2}^n s^*_k(\cF_m)$$
by choosing suitable $\vec{j}$ values, but this requires $\geq$ in line 920.
**Suggested fix:** Change $\leq$ to $\geq$ on line 920.

---

## ISSUE #5
**Location:** line ~906
> "supposed $\tr\left[F_{\alpha_k}\sigma_k\right] \neq 0$ for all $k < n$"

**Category:** GRAMMAR / IMPLICIT_ASSUMPTION
**Severity:** MAJOR
**Description:** Two issues: (a) "supposed" should be "supposing" or "assuming". (b) More importantly, this non-vanishing assumption is never discharged. The proof assumes $\tr[F_{\alpha_l} \sigma_l] \neq 0$ for the chosen $\sigma_l$ and $\alpha_l$ to perform the division, but the argument must hold for ALL $\alpha$. One must argue that suitable $\sigma_l$ can always be chosen (e.g., because $F_{\alpha_l}^{(l)} \neq 0$ implies existence of $\sigma_l$ with $\tr[F_{\alpha_l} \sigma_l] \neq 0$), and that the lower bound obtained is independent of this choice. The main theorem (line 200) includes $F_{\alpha_l}^{(l)} \neq 0$ as WLOG but the appendix proof never invokes this.
**Suggested fix:** Add a sentence: "Since each $F_{\alpha_l}^{(l)} \neq 0$ by assumption, we may choose $\sigma_l$ such that $\tr[F_{\alpha_l} \sigma_l] \neq 0$ for all $\alpha_l \in \cA_l$." (This requires $|\cA_l|$ constraints on $\sigma_l$, satisfiable generically.)

---

## ISSUE #6
**Location:** line ~912
> "can be chosen independently of the last $n-1$ sites"

**Category:** CLARITY
**Severity:** MINOR
**Description:** "the last $n-1$ sites" is ambiguous — site $n$ is the last site, and we're peeling it off. The intended meaning is "the first $n-1$ sites" or "the other $n-1$ sites."
**Suggested fix:** Replace "the last $n-1$ sites" with "the first $n-1$ sites."

---

## ISSUE #7
**Location:** line ~912
> "we can redefined the estimator function"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "redefined" should be "redefine" (infinitive after "can").
**Suggested fix:** Change "redefined" to "redefine."

---

## ISSUE #8
**Location:** line ~940
> $\cF^{(l)} = \cF = \{ \ldots \}$

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The notation $\cF^{(l)} = \cF$ reuses $\cF$ for the per-site operator set, but $\cF$ has been used throughout the paper for the global operator set $\{F_\alpha\}_{\alpha \in \cA}$. This creates confusion.
**Suggested fix:** Use a distinct symbol, e.g., $\cF^{(l)} = \cF_0$ (consistent with line 932 which already uses $\cF_0$ for the homogeneous per-site set).

---

## ISSUE #9
**Location:** line ~942
> "the sampling complexity lower bound ... is at least $[s^*_k(\cF)]^n$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** $s^*_k(\cF)$ here refers to the per-site optimal scaling factor, but $\cF$ without superscript reads as the global set. Should be $s^*_k(\cF_0)$ or $s^*_k(\cF^{(l)})$.
**Suggested fix:** Replace $[s^*_k(\cF)]^n$ with $[s^*_k(\cF_0)]^n$.

---

## ISSUE #10
**Location:** line ~948
> "In this subsection, we will show..."

**Category:** TYPO
**Severity:** MINOR
**Description:** The heading is `\section{Examples}`, not a subsection. Should say "In this section."
**Suggested fix:** Replace "subsection" with "section."

---

## ISSUE #11
**Location:** line ~938
> $F_P = (P \ox \1^{\ox(k-1)}) \cdot \mathrm{SWAP}_{1,2}^{\ox k}$

**Category:** CLARITY / NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The notation $\mathrm{SWAP}_{1,2}^{\otimes k}$ is ambiguous. If $\mathrm{SWAP}_{1,2}$ denotes the swap of copies 1 and 2 of the full $n$-qubit system, then it already acts on the correct space and $\otimes k$ is meaningless. If $\mathrm{SWAP}_{1,2}$ is the 2-qubit swap and $\mathrm{SWAP}_{1,2}^{\otimes n}$ means applying per-qubit swaps across all $n$ sites, then the exponent should be $n$, not $k$. The local decomposition on line 940 uses bare $\mathrm{SWAP}_{1,2}$ (no tensor power), which is consistent with the per-qubit interpretation — suggesting the $\otimes k$ on line 938 is incorrect.
**Suggested fix:** Clarify the SWAP notation. If it's the per-site swap between copies 1 and 2 at each qubit site, write $\mathrm{SWAP}_{1,2}^{\otimes n}$ (tensor over $n$ sites).

---

## ISSUE #12
**Location:** line ~909
> $:=\sum_{j_n} h'(j_n) \tr \left[\Pi^{(n)}_{j_n|j_1,\ldots,j_{n-1}} \sigma_n\right]$

**Category:** IMPLICIT_ASSUMPTION
**Severity:** MAJOR
**Description:** Even setting aside the adaptive issue (Issue #2), $h'(j_n)$ as defined on line 914 depends on $\alpha_1, \ldots, \alpha_{n-1}$ and $\sigma_1, \ldots, \sigma_{n-1}$. For this to constitute a valid strategy for site $n$, the estimator must work for all $\alpha_n$ with the same POVM and scaling factor. But $h'(j_n)$ implicitly depends on the choice of $\alpha_1, \ldots, \alpha_{n-1}$, meaning different $\alpha_n$ could require different estimators if the auxiliary indices are varied. The proof needs to fix $\alpha_1, \ldots, \alpha_{n-1}$ and $\sigma_1, \ldots, \sigma_{n-1}$ and show the induced estimator works for all $\alpha_n$ simultaneously.
**Suggested fix:** Make explicit that $\alpha_1, \ldots, \alpha_{n-1}$ and $\sigma_1, \ldots, \sigma_{n-1}$ are fixed, and that the constraint $\sum_{j_n} h'_{\alpha_n}(j_n) \Pi^{(n)}_{j_n} = F_{\alpha_n}^{(n)}$ holds for all $\alpha_n$ (possibly with different $h'$ for each $\alpha_n$, which is fine since only $\max |h'|$ matters).

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 2     |
| MAJOR    | 4     |
| MINOR    | 6     |
| **Total**| **12**|

### Most Critical Issue

**Issue #2 (lines 908–909):** The peeling argument for the lower bound $s^*_{k,\mathrm{loc}} \geq \prod_l s^*_k(\cF_l)$ fundamentally breaks for adaptive POVMs. When the POVM at site $n$ depends on outcomes at sites $1, \ldots, n-1$, the trace factor $\tr[\sigma_n \Pi^{(n)}_{j_n|j_1,\ldots,j_{n-1}}]$ cannot be extracted from the sum over $j_1, \ldots, j_{n-1}$, invalidating the definition of $h'(j_n)$. The proof is valid only for non-adaptive product POVMs. Since the theorem claims factorization over all local strategies (including adaptive), this is a gap in the proof that needs to be addressed — either by restricting to non-adaptive POVMs or by providing a different argument for the adaptive case.

Combined with **Issue #4** (reversed inequality on line 920), the lower bound proof has two independent critical errors that need correction before the argument is sound.

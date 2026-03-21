# Diagnostic Report: Round 12 — Multi-copy Local Shadows (lines 1436–1730)

**Date:** 2026-03-17
**Section:** Appendix — Multi-copy local shadows
**Lines reviewed:** 1436–1730

---

## ISSUE #1
**Location:** line ~1470
**Category:** OVER_CLAIMING
**Severity:** MAJOR
**Description:** The text claims "This i.i.d. unitary 3-design setting includes the Clifford randomized measurement and the randomized Pauli basis measurement proposed in [huang2020predicting]." The randomized Pauli basis measurement (measuring each qubit in a randomly chosen X/Y/Z basis) is NOT a unitary 3-design. It uses only 3 of the 24 single-qubit Cliffords (up to phases) and fails to reproduce the third moment of the Haar measure. The single-qubit Clifford group IS a 3-design (Zhu 2016), but random Pauli basis measurement is a strict subset. Since Lemma~\ref{lemma:LC_shadow_kcopy} requires the 3-design property for the variance formula, applying it to Pauli basis measurements is unjustified.
**Suggested fix:** Remove "and the randomized Pauli basis measurement proposed in~\cite{huang2020predicting}" or add a caveat: "the Clifford randomized measurement~\cite{zhu2016clifford} (note: the randomized Pauli basis measurement of~\cite{huang2020predicting} is only a 1-design and requires a separate variance analysis)."

---

## ISSUE #2
**Location:** line ~1477
**Category:** TYPO / NOTATION_INCONSISTENCY
**Severity:** MAJOR
**Description:** The channel formula uses $2^k$ in the depolarization parameter: $\cD_{1/(2^k + 1)}(\cdot) = \frac{1}{2^k +1}(\cdot) + \frac{\tr(\cdot)}{2^k + 1}{\1(d^k)}$. However, the lemma is stated for general dimension $d$ (see lines 1479–1480 which correctly use $d^k$ and $d$ respectively). The proof (line 1496) also gives $\cD_{1/(d^k+1)}$. The $2^k$ should be $d^k$ to be consistent with the general-$d$ setting of the lemma.
**Suggested fix:** Replace $2^k$ with $d^k$ in line 1477: $\cD_{1/(d^k + 1)}(\cdot) = \frac{1}{d^k +1}(\cdot) + \frac{\tr(\cdot)}{d^k + 1}{\1(d^k)}$.

---

## ISSUE #3
**Location:** line ~1520
**Category:** CIRCULARITY
**Severity:** MINOR
**Description:** "Similar to the proof in Lemma~\ref{lemma:LC_shadow_kcopy}" — but this IS the proof of Lemma~\ref{lemma:LC_shadow_kcopy}. The self-reference is meaningless.
**Suggested fix:** Either refer to a specific earlier lemma (e.g., "Following the same approach as the proof of Lemma~\ref{lemma:onsite_2design}") or simply remove the phrase and proceed directly.

---

## ISSUE #4
**Location:** line ~1554
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The RHS uses $\tilde{\rho}^{(s)}_i$ (with tilde) but the LHS and all surrounding text use ${\rho}^{(s)}_i$ (without tilde). The tilde appears nowhere else in this proof.
**Suggested fix:** Replace $\tilde{\rho}^{(s)}_i$ with ${\rho}^{(s)}_i$ on line 1554.

---

## ISSUE #5
**Location:** line ~1618
**Category:** MISSING_HYPOTHESIS
**Severity:** MAJOR
**Description:** The decomposition states "it turns out $(O \ox \1_n)\text{SWAP}^{\ox n} = \sum_{\mathbf{r} \in \mathbb{F}_2^{2n}} (\sigma_{\mathbf{r}} \ox \1_n)\text{SWAP}^{\ox n}:= \sum_{\mathbf{r}} O_{\mathbf{r}}$." This is missing the Pauli expansion coefficients of $O$. If $O = \sum_\mathbf{r} \alpha_\mathbf{r} \sigma_\mathbf{r}$, then $(O\otimes \1)\text{SWAP} = \sum_\mathbf{r} \alpha_\mathbf{r} (\sigma_\mathbf{r}\otimes\1)\text{SWAP} = \sum_\mathbf{r} \alpha_\mathbf{r} O_\mathbf{r}$. The coefficients $\alpha_\mathbf{r}$ are silently dropped.
**Suggested fix:** Write "$O = \sum_{\mathbf{r}} \alpha_{\mathbf{r}} \sigma_{\mathbf{r}}$ on the Pauli basis, giving $(O \ox \1_n)\text{SWAP}^{\ox n} = \sum_{\mathbf{r}} \alpha_{\mathbf{r}} (\sigma_{\mathbf{r}} \ox \1_n)\text{SWAP}^{\ox n} := \sum_{\mathbf{r}} \alpha_{\mathbf{r}} O_{\mathbf{r}}$."

---

## ISSUE #6
**Location:** line ~1643
**Category:** UNJUSTIFIED_STEP
**Severity:** MINOR
**Description:** The phase factor $(-1)^{[\mathbf{p},\mathbf{r}']}$ in the covariance operator expression is stated without derivation. Tracking phases through the Pauli multiplication rule (line 1573), the product $\alpha_W \alpha_{W'} W W'$ involves four phase factors from $\sigma_\mathbf{r}\sigma_\mathbf{p}$, $\sigma_{\mathbf{r}'}\sigma_{\mathbf{p}'}$, $\sigma_{\mathbf{r}+\mathbf{p}}\sigma_{\mathbf{r}'+\mathbf{p}'}$, and $\sigma_\mathbf{p}\sigma_{\mathbf{p}'}$. The claim that these combine to give only $(-1)^{[\mathbf{p},\mathbf{r}']}$ requires explicit verification.
**Suggested fix:** Add a brief derivation or footnote showing the phase cancellation, e.g., "Using the Pauli multiplication rule~\eqref{eq:...}, the four phase factors $i^{[\mathbf{p},\mathbf{r}]}$, $i^{[\mathbf{p}',\mathbf{r}']}$, $i^{[\mathbf{r}'+\mathbf{p}',\mathbf{r}+\mathbf{p}]}$, $i^{[\mathbf{p}',\mathbf{p}]}$ combine to give $(-1)^{[\mathbf{p},\mathbf{r}']}$."

---

## ISSUE #7
**Location:** line ~1640
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "foot label" is non-standard terminology.
**Suggested fix:** Replace "foot label" with "subscript".

---

## ISSUE #8
**Location:** line ~1683
**Category:** CLARITY
**Severity:** MINOR
**Description:** The correction argument "if we simply adapt the result in Eq.\eqref{eq:V_eq1}, we will get... However... we mistakenly counted..." is confusing. It presents a wrong derivation first and then patches it, rather than computing correctly from the start. The reader must understand why the $\mathbf{r}'\neq 0$ result cannot be naively extended.
**Suggested fix:** Restructure to compute directly from the four cases of $r(W,W')$ when one of $\mathbf{p}',\mathbf{p}$ equals $\mathbf{0}$, rather than presenting an incorrect intermediate and correcting it.

---

## ISSUE #9
**Location:** line ~1709
**Category:** CLARITY (redundancy)
**Severity:** MINOR
**Description:** Lines 1707–1709 in the proof repeat almost verbatim the content already stated in the lemma statement (lines 1632). This duplication adds length without new content.
**Suggested fix:** Replace with a brief closing: "This completes the proof."

---

## ISSUE #10
**Location:** line ~1715
**Category:** CLARITY / IMPLICIT_ASSUMPTION
**Severity:** MINOR
**Description:** "For the single copy local Clifford shadow" is ambiguous. This actually means: applying independent single-qubit Clifford unitaries to each of the $2n$ qubits of $\rho^{\otimes 2}$ (i.e., $k=1$ shadow tomography on a $2n$-qubit state). The $R(W_i,W'_i)$ values used ($R(XX,XX)=9$ etc.) come from products $[r_{k=1}(P,P')]^2$ over the two physical qubits at each site-pair $(j, n+j)$, NOT from $r_{k=2}$.
**Suggested fix:** Clarify: "For comparison, the single-copy local Clifford shadow applies independent single-qubit 3-design unitaries to each of the $2n$ qubits of $\rho^{\otimes 2}$. Grouping qubits $j$ and $n+j$ into site pairs, the per-pair rescaling factor becomes $R_{\text{pair}}(PP, QQ) = [r_{k=1}(P,Q)]^2$."

---

## ISSUE #11
**Location:** line ~1436
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "measurements that supports on $k$-qudits" — subject-verb disagreement and missing article.
**Suggested fix:** "measurements supported on $k$ qudits"

---

## ISSUE #12
**Location:** line ~1437
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "and try to use" — subject is "it" (singular).
**Suggested fix:** "and tries to use"

---

## ISSUE #13
**Location:** line ~1448
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "ones classically post-processing those sampled classical shadow" — multiple errors.
**Suggested fix:** "one classically post-processes the sampled classical shadows."

---

## ISSUE #14
**Location:** line ~1458
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "The explicit form of channel $\cM$ rely on" — subject-verb disagreement.
**Suggested fix:** "relies on"

---

## ISSUE #15
**Location:** line ~1484
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "the channel $\cM$ in this case became" — wrong tense.
**Suggested fix:** "becomes"

---

## ISSUE #16
**Location:** line ~1493
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "Use the fact that..." — dangling participial.
**Suggested fix:** "Using the fact that..."

---

## ISSUE #17
**Location:** line ~1498
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "its inverse $\cD_{...}^{-1}(\rho) = ...$ constitute an unbiased estimator" — "inverse" is singular.
**Suggested fix:** "constitutes"

---

## ISSUE #18
**Location:** line ~1505
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "we put $\rho^{\ox k}$ in quantum memory and then implements randomized k-qubits Clifford gate" — disagreement and wrong plural.
**Suggested fix:** "we put $\rho^{\otimes k}$ in quantum memory and then implement a randomized $k$-qubit Clifford gate"

---

## ISSUE #19
**Location:** line ~1522
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "again supposed" — wrong form.
**Suggested fix:** "suppose" or "supposing"

---

## ISSUE #20
**Location:** line ~1552
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "we first defined $\mathcal{C}(W)$" — wrong tense in a proof.
**Suggested fix:** "we first define"

---

## ISSUE #21
**Location:** line ~1568
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "Defined $[\mathbf{s}', \mathbf{s}]:=$..." — wrong form.
**Suggested fix:** "Define" or "We define"

---

## ISSUE #22
**Location:** line ~1576
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "Use this rule, we calculate" — wrong form.
**Suggested fix:** "Using this rule, we calculate"

---

## ISSUE #23
**Location:** line ~1592
**Category:** GRAMMAR / TYPO
**Severity:** MINOR
**Description:** "the we defined" — extra article.
**Suggested fix:** "we define"

---

## ISSUE #24
**Location:** line ~1598
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "The covariance operator is important due to the Lemma below" — missing period, and "Lemma" should not be capitalized mid-sentence. Also "due to" is awkward; it's important because of what the lemma states, not "due to" the lemma.
**Suggested fix:** "The covariance operator is important because of the following lemma."

---

## ISSUE #25
**Location:** line ~1606
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "Supposed the decomposition" — wrong form.
**Suggested fix:** "Suppose" or "Given"

---

## ISSUE #26
**Location:** line ~1726
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "The lower bound of many problem are find by first reduce this problem" — multiple errors.
**Suggested fix:** "The lower bounds of many problems are found by first reducing the problem"

---

## ISSUE #27
**Location:** line ~1727
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "One useful state ensembles are constructed from reducing Haar random state." — number disagreement and missing article.
**Suggested fix:** "One useful class of state ensembles is constructed by reducing a Haar random state."

---

## ISSUE #28
**Location:** line ~1576
**Category:** UNJUSTIFIED_STEP
**Severity:** MINOR
**Description:** The implication arrow "$\Rightarrow [\mathbf{s}, \mathbf{s}'] = 0$" in "$ \sigma_{\mathbf{s}}\cdot \sigma_{\mathbf{s}'}=i^{2\mathbf{s}_x'\cdot \mathbf{s}_z - 2\mathbf{s}_z'\cdot \mathbf{s}_x } (\sigma_{\mathbf{s}'} \cdot \sigma_{\mathbf{s}}) \Rightarrow [\mathbf{s}, \mathbf{s}'] = 0$" is confusing. The $\Rightarrow$ should be labeled as the condition for commutation: $\sigma_\mathbf{s}$ commutes with $\sigma_{\mathbf{s}'}$ if and only if $[\mathbf{s},\mathbf{s}'] = 0$. As written, it looks like an unconditional implication that all Paulis commute.
**Suggested fix:** Rewrite as: "so $\sigma_\mathbf{s}$ and $\sigma_{\mathbf{s}'}$ commute if and only if $[\mathbf{s},\mathbf{s}'] = 0 \pmod{2}$."

---

## ISSUE #29
**Location:** line ~1713
**Category:** CLARITY
**Severity:** MINOR
**Description:** The connection between the purity operator $O^{(2)} = \text{SWAP}^{\otimes n}$ and $O_\mathbf{0}$ from Lemma~\ref{lemma:covar_Pauli} is left implicit. Since $O_\mathbf{0} = (I \otimes I_n)\text{SWAP}^{\otimes n} = \text{SWAP}^{\otimes n} = O^{(2)}$, the sentence "the second moment operator for purity estimation is $\mathbf{V}(O_\mathbf{0},O_\mathbf{0})$" should explicitly state $O_\mathbf{0} = O^{(2)}$.
**Suggested fix:** Add: "Since $O^{(2)} = O_\mathbf{0}$ (taking $\mathbf{r} = \mathbf{0}$ in Lemma~\ref{lemma:covar_Pauli}), the second moment operator is..."

---

## ISSUE #30
**Location:** line ~1473
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The lemma is labeled "On site 3-design unitary ensemble" (\label{lemma:onsite_2design}) — the label says "2design" but the content is about 3-designs. This mismatch between label name and content can cause confusion during cross-referencing.
**Suggested fix:** Rename label to `lemma:onsite_3design` (and update all references).

---

## ISSUE #31
**Location:** line ~1577
**Category:** TYPO
**Severity:** MINOR
**Description:** $\delta_{\sigma_{\mathbf{s},\mathcal{C}(\sigma_{\mathbf{s}'} )\backslash \1_k}}$ — the subscript grouping is ambiguous/malformed. The first comma appears inside the subscript of $\sigma$, but should separate the two arguments of $\delta$.
**Suggested fix:** Use consistent notation: $\delta_{\sigma_\mathbf{s}, \mathcal{C}(\sigma_{\mathbf{s}'})\setminus \1_k}$.

---

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| MAJOR | 3 |
| MINOR | 28 |
| **Total** | **31** |

**Breakdown by category:**
- OVER_CLAIMING: 1
- TYPO / NOTATION_INCONSISTENCY: 4
- CIRCULARITY: 1
- MISSING_HYPOTHESIS: 1
- UNJUSTIFIED_STEP: 2
- CLARITY: 5
- GRAMMAR: 16
- IMPLICIT_ASSUMPTION: 1

**Most critical issue:** **Issue #1** (line 1470) — The claim that random Pauli basis measurements form a 3-design is factually incorrect. The variance formula in Lemma~\ref{lemma:LC_shadow_kcopy} requires the 3-design property (for the third moment computation), so stating that random Pauli measurements satisfy this setting is an overclaim that could mislead readers about the applicability of the results.

**Runner-up:** **Issue #2** (line 1477) — The channel formula in the general-$d$ lemma statement uses $2^k$ instead of $d^k$, making the lemma statement incorrect for $d \neq 2$.

**Mathematical soundness:** The core derivations (second moment computation, $R(W,W')$ function, covariance operator decomposition, and the explicit $v(\mathbf{r}_j, \mathbf{r}'_j)$ formula) are algebraically verified and correct. The 16-term enumeration for the $\mathbf{r}=\mathbf{r}'=0$ case (lines 1672–1679) checks out. The single-copy vs. 2-replica comparison (lines 1713–1721) is numerically correct.

# Diagnostic Report — Round 11
## Target: Section "Multi-copy local estimation" (lines 1123–1435)

---

## ISSUE #1
**Location:** line ~1124
> "Contrast to conclusion in the last section, we noted that the purity estimation strategy using Bell measurements already reach the $\cO(1)$ sampling complexity."

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Multiple grammar errors: "Contrast to" → "In contrast to the", "we noted" → "we note" (present tense for mathematical exposition), "already reach" → "already reaches" (subject–verb agreement).
**Suggested fix:** "In contrast to the conclusion in the last section, we note that the purity estimation strategy using Bell measurements already reaches the $\cO(1)$ sampling complexity."

---

## ISSUE #2
**Location:** line ~1126
> "The Bell measurement projector satisfied"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "projector" should be plural "projectors", and "satisfied" should be present tense "satisfy".
**Suggested fix:** "The Bell measurement projectors satisfy"

---

## ISSUE #3
**Location:** line ~1137
> "this channel on the two-replica space $\cH(d^2)$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The notation $\cH(d^2)$ for the two-replica Hilbert space is non-standard and used nowhere else. It should be $\cH^{\otimes 2}$ or $\mathbb{C}^{d^2}$ or $(\mathbb{C}^d)^{\otimes 2}$ consistent with the rest of the paper.
**Suggested fix:** Replace $\cH(d^2)$ with $\cH^{\otimes 2}$.

---

## ISSUE #4
**Location:** line ~1138
> "if we restrained on the operator subspace … this channel takes itself as the inverse"

**Category:** CLARITY
**Severity:** MINOR
**Description:** "restrained on" should be "restricted to". The phrase "takes itself as the inverse" is confusing—it means the channel acts as the identity on $\mathbf{S}$ (hence is trivially its own inverse), not that $\cM_I^{-1} = \cM_I$.
**Suggested fix:** "if we restrict to the operator subspace $\mathbf{S}$, this channel acts as the identity (and is therefore its own inverse)."

---

## ISSUE #5
**Location:** line ~1139
> "This estimator has variance $\tr(\rho O^2) - \tr^2(\rho O) \leq [(\lambda_{\max}(O) - \lambda_{\min}(O))/2]^2$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MAJOR
**Description:** The operator $O$ acts on the two-replica space $\cH^{\otimes 2}$, so the state in the variance expression should be $\rho^{\otimes 2}$, not $\rho$. The correct expression is $\tr(\rho^{\otimes 2} O^2) - [\tr(\rho^{\otimes 2} O)]^2$. Additionally, "Bell measurment" is a typo for "Bell measurement".
**Suggested fix:** Replace $\tr(\rho O^2) - \tr^2(\rho O)$ with $\tr(\rho^{\otimes 2} O^2) - [\tr(\rho^{\otimes 2} O)]^2$ and fix "measurment" → "measurement".

---

## ISSUE #6
**Location:** lines ~1147–1152
> "We first show that the function $f(\rho):= \text{Var}_{\rho}(O)$ is a convex function of $\rho$."
> "which shows the convexity of $f(\rho)$."
> "The maximum of a convex function over a compact convex set is attained at an extreme point."

**Category:** LOGICAL_GAP
**Severity:** CRITICAL
**Description:** The proof establishes $f((1-\theta)\rho + \theta\sigma) - (1-\theta)f(\rho) - \theta f(\sigma) \geq 0$, which by definition means $f$ is **concave**, not convex. (This is correct: $\text{Var}_\rho(O) = \langle O^2\rangle_\rho - \langle O\rangle_\rho^2$ is linear minus convex = concave in $\rho$.) The subsequent invocation "the maximum of a convex function over a compact convex set is attained at an extreme point" is therefore **inapplicable**—for concave functions the maximum may be in the interior.

The **lemma statement is correct** and the final optimization over $\{p_i\}$ (lines 1153–1160) is valid, but the logical bridge via convexity is wrong. The correct argument is simpler: $\text{Var}_\rho(O)$ depends on $\rho$ only through the diagonal elements $p_i = \langle\lambda_i|\rho|\lambda_i\rangle$ (since $\langle O^2\rangle$ and $\langle O\rangle$ both depend only on these), and the set of achievable distributions $\{p_i\}$ is the full probability simplex (realized by, e.g., $\rho = \sum_i p_i |\lambda_i\rangle\langle\lambda_i|$). One then optimizes $\text{Var}(\{p_i\}) = \sum p_i\lambda_i^2 - (\sum p_i\lambda_i)^2$ over the simplex, which is a classical calculation yielding $p = 1/2$ on the two extreme eigenvalues.

**Suggested fix:** Replace the convexity paragraph (lines 1147–1152) with:
"We observe that $f(\rho)$ depends on $\rho$ only through the probability vector $p_i = \langle\lambda_i|\rho|\lambda_i\rangle$, since $\langle O\rangle_\rho = \sum_i p_i\lambda_i$ and $\langle O^2\rangle_\rho = \sum_i p_i\lambda_i^2$. Every probability distribution $\{p_i\}$ is realizable (e.g., by the mixed state $\rho = \sum_i p_i|\lambda_i\rangle\langle\lambda_i|$, or equivalently by the pure state $|\psi\rangle = \sum_i\sqrt{p_i}|\lambda_i\rangle$), so we optimize $f = \sum_i p_i(\lambda_i - \bar\lambda)^2$ over the full simplex."

---

## ISSUE #7
**Location:** line ~1155
> "Keeping $\bar\lambda$ unchanged, we should concentrate $p_i$ on the most extreme values available"

**Category:** UNJUSTIFIED_STEP
**Severity:** MINOR
**Description:** The optimization is over $\{p_i\}$; changing $p_i$ changes $\bar\lambda = \sum p_i\lambda_i$. The sentence claims we "keep $\bar\lambda$ unchanged" while concentrating mass, but this is not what happens—both $\bar\lambda$ and the second moment change simultaneously. The subsequent two-point reduction is correct (optimizing variance over a simplex yields mass on two extreme points), but the stated justification via "keeping $\bar\lambda$ unchanged" is misleading.
**Suggested fix:** Remove "Keeping $\bar\lambda$ unchanged" and instead write: "Since $\text{Var}(\{p_i\}) = \sum_i p_i(\lambda_i - \bar\lambda)^2$ is maximized when mass concentrates on the most extreme eigenvalues, we reduce to a two-point distribution on $\lambda_{\max}$ and $\lambda_{\min}$."

---

## ISSUE #8
**Location:** line ~1163
> "This include the SWAP operator"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "include" → "includes" (subject–verb agreement).
**Suggested fix:** "This includes the SWAP operator"

---

## ISSUE #9
**Location:** line ~1209
> "We can then construct $L_\mathbf{q}:= \bigotimes_{i\in A_{\mathbf{p}}} e^{i\frac{\pi}{4} \sigma_{\mathbf{q}_i}}$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MAJOR
**Description:** The operator $L_\mathbf{q}$ is subscripted only by $\mathbf{q}$, but its definition depends on $A_\mathbf{p}$, which varies with $\mathbf{p}$ in the summation. This creates the false impression that $L_\mathbf{q}$ is a fixed unitary independent of the summation index. It should be denoted $L_{\mathbf{q},\mathbf{p}}$ or $L_{\mathbf{q}}^{(A_\mathbf{p})}$ to indicate the dependence.
**Suggested fix:** Replace $L_\mathbf{q}$ with $L_{\mathbf{q}}^{(A_{\mathbf{p}})}$ or acknowledge the $\mathbf{p}$-dependence explicitly.

---

## ISSUE #10
**Location:** line ~1225
> "the information of insymmetric Pauli operator"

**Category:** TYPO
**Severity:** MINOR
**Description:** "insymmetric" is not a word. The intended meaning is "asymmetric" or "non-symmetric".
**Suggested fix:** "the information of asymmetric Pauli operators $\1\otimes\sigma_{\mathbf{q}},\;\sigma_{\mathbf{q}}\otimes\1$"

---

## ISSUE #11
**Location:** line ~1231
> "we average all possible separation"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "average all possible separation" → "average over all possible separations".
**Suggested fix:** "we average over all possible separations."

---

## ISSUE #12
**Location:** line ~1260
> "we noted that"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Lowercase "we" at sentence start, and "noted" should be present tense.
**Suggested fix:** "We note that"

---

## ISSUE #13
**Location:** line ~1275
> "$|\mathbf{r}_i|/2$"

**Category:** CLARITY
**Severity:** MAJOR
**Description:** The notation $|\mathbf{r}_i|$ is ambiguous. In the context of Bell measurement, $\mathbf{r}_i \in \mathbb{F}_2^2$ and $|\mathbf{r}_i|$ likely denotes the Hamming weight $r_{i,x} + r_{i,z}$. But here the measurement is a single-copy Pauli measurement with outcomes $r_{i,x}, r_{i,z} \in \{0,1\}$ (or $\{+1,-1\}$?), and $|\cdot|$ could be read as absolute value. Furthermore, the projector is written as $(1 + r_{i,x}\sigma_{\mathbf{q}_i})/2$, which only makes sense if $r_{i,x} \in \{-1,+1\}$ (eigenvalues), but earlier Bell measurement outcomes use $\{0,1\}$ (binary). This mixes two conventions.
**Suggested fix:** Clarify that $r_{i,x}, r_{i,z} \in \{+1,-1\}$ are Pauli eigenvalues (not bits), and define $|\mathbf{r}_i| := r_{i,x} + r_{i,z}$ explicitly, or use Hamming weight notation $\mathrm{wt}(\mathbf{r}_i)$ if bits are intended (with the projector written as $(1 + (-1)^{r_{i,x}}\sigma)/2$).

---

## ISSUE #14
**Location:** line ~1285
> "A adaptive local strategy"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "A adaptive" → "An adaptive".
**Suggested fix:** "An adaptive local strategy"

---

## ISSUE #15
**Location:** line ~1286
> "in the case that the non-local operations is allowed"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Subject–verb disagreement: "operations is" → "operations are".
**Suggested fix:** "in the case that non-local operations are allowed"

---

## ISSUE #16
**Location:** line ~1288
> "use single anccilla qubits"

**Category:** TYPO
**Severity:** MINOR
**Description:** Two errors: "anccilla" → "ancilla" (typo), and "single … qubits" → "a single ancilla qubit" (number agreement).
**Suggested fix:** "uses a single ancilla qubit"

---

## ISSUE #17
**Location:** line ~1290
> "Since $ZIII$ contains non-identity Pauli operator only on the first qubits."

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Sentence fragment (starts with "Since" but has no main clause). Also "qubits" → "qubit" (singular).
**Suggested fix:** Merge with the next sentence: "Since $ZIII$ has a non-identity Pauli only on the first qubit, we can measure …"

---

## ISSUE #18
**Location:** line ~1302
> "we proposed a non-randomized adaptive strategy"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Tense inconsistency—paper uses present tense elsewhere. "proposed" → "propose".
**Suggested fix:** "we propose"

---

## ISSUE #19
**Location:** line ~1305
> "this observable $O_{\mathbf{r}}$ is a tensor product of local non-Hermitian operators $O_{\mathbf{r}} = [(Z \otimes \1) \cdot \mathrm{SWAP}]^{\otimes n}:= A^{\otimes n}$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MAJOR
**Description:** The subscript suddenly changes from $\mathbf{q}$ (used in line 1204 defining $O_\mathbf{q}$) to $\mathbf{r}$. This conflicts with the use of $\mathbf{r}$ for measurement outcomes throughout the section (lines 1131, 1165, etc.). Should remain $O_\mathbf{q}$ or use a different letter.
**Suggested fix:** Replace $O_\mathbf{r}$ with $O_\mathbf{q}$ throughout this paragraph for consistency.

---

## ISSUE #20
**Location:** lines ~1312–1316
> "every two-qubit projective measurements that unchanged under qubits exchange can be written in the form …"

**Category:** OVER_CLAIMING
**Severity:** MAJOR
**Description:** This claims the given 4-element basis is the **most general** exchange-symmetric rank-1 projective measurement on $(\mathbb{C}^2)^{\otimes 2}$. While any such measurement must have one element in the antisymmetric subspace ($\dim 1$) and three in the symmetric subspace ($\dim 3$), the specific form of the antisymmetric-subspace elements $|\Phi^\pm\rangle = (|\psi_0\rangle|\psi_1\rangle \pm i|\psi_1\rangle|\psi_0\rangle)/\sqrt{2}$ with the fixed $\pm i$ phase is **not** the most general choice. The general form has an arbitrary phase $e^{i\phi}$ instead of $i$. Also, grammar: "measurements that unchanged" → "measurement that is unchanged".
**Suggested fix:** Either prove this classification or weaken to "a natural family of exchange-symmetric projective measurements". Fix grammar.

---

## ISSUE #21
**Location:** line ~1367
> "using a $\cO(\varepsilon^{-4}\log(|\cO|))$ times $k$-replica strategy with $k \cdot n$ ancilla qubits"

**Category:** CLARITY
**Severity:** MAJOR
**Description:** The proof measures $\rho^{\otimes k} \otimes \sigma^{\otimes k}$ (a $2k$-copy state), so the total number of copies per round is $2k$, not $k$. Calling this a "$k$-replica strategy with $k\cdot n$ ancilla qubits" obscures the true resource cost. The "ancilla qubits" are really $k$ copies of the auxiliary state $\sigma$, which itself must be prepared.
**Suggested fix:** Rephrase as: "using $\cO(\varepsilon^{-4}\log|\cO|)$ rounds of a $2k$-copy measurement (on $\rho^{\otimes k}\otimes\sigma^{\otimes k}$), where $\sigma$ is an auxiliary state satisfying …"

---

## ISSUE #22
**Location:** line ~1370
> "Such a state $\sigma$ always exists and can be constructed given the estimates $\hat{f}_P$, but may not be found computationally efficiently."

**Category:** IMPLICIT_ASSUMPTION
**Severity:** MAJOR
**Description:** The proof requires $\sigma$ with $||\tr(P\sigma^k)| - \hat{f}_P| \leq \varepsilon$ for all $P \in \cO$. But the proof then divides by $\tr(P\sigma^k)$ (line 1377), requiring knowledge of the **sign** of $\tr(P\sigma^k)$, not just its absolute value. Since $\sigma$ is constructed (not measured), we do know $\sigma$ fully and hence $\tr(P\sigma^k)$ including sign—but this should be made explicit. Additionally, the existence claim (that such $\sigma$ exists for all $P$ simultaneously) is not proved; taking $\sigma = \rho$ works but is circular since $\rho$ is unknown.
**Suggested fix:** Add: "For existence, note that $\sigma = \rho$ satisfies the condition with margin $\varepsilon$. Since we construct $\sigma$ explicitly (even if inefficiently), we have access to $\tr(P\sigma^k)$ including its sign."

---

## ISSUE #23
**Location:** line ~1383
> "eigenvalues $\lambda_{(s,\mathbf{a},\mathbf{b})} :=(-1)^{\mathbf{r}_x\cdot\mathbf{r}_z}\cdot s \cdot 2^{-1}[(-1)^{[\mathbf{r}, \mathbf{a}]} + (-1)^{[\mathbf{r}, \mathbf{b}]}]$"

**Category:** CLARITY
**Severity:** MINOR
**Description:** The eigenvalue depends on the operator label $\mathbf{r}$ (the Pauli index for $A_\mathbf{r}$), but this dependence is only implicit through the notation. It would be clearer to write $\lambda_\mathbf{r}(s,\mathbf{a},\mathbf{b})$ to emphasize that different $A_\mathbf{r}$ have different eigenvalues on the same eigenstate.
**Suggested fix:** Write $\lambda_\mathbf{r}(s,\mathbf{a},\mathbf{b})$ and add a sentence: "where $\mathbf{r}$ labels the operator $A_\mathbf{r}$ whose eigenvalue is being computed."

---

## ISSUE #24
**Location:** line ~1410
> "the qubit on the third and the forth copy"

**Category:** TYPO
**Severity:** MINOR
**Description:** "forth" → "fourth".
**Suggested fix:** "the qubits on the third and fourth copies"

---

## ISSUE #25
**Location:** line ~1411
> "a separtiton of the $1$-st and $2$-nd copies"

**Category:** TYPO
**Severity:** MINOR
**Description:** "separtiton" → "partition" (or "separation").
**Suggested fix:** "a partition"

---

## ISSUE #26
**Location:** line ~1412
> "a GHZ state measurement $s^{I}$ formulized by circuit"

**Category:** TYPO
**Severity:** MINOR
**Description:** "formulized" is not standard; likely means "realized" or "implemented".
**Suggested fix:** "a GHZ-state measurement yielding outcome $s^I$, realized by the circuit:"

---

## ISSUE #27
**Location:** line ~1270
> "Noted that"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "Noted" → "Note" (imperative, present tense).
**Suggested fix:** "Note that"

---

## ISSUE #28
**Location:** line ~1304
> "we noted that full weight Pauli operators can be locally transformed into Pauli $Z$ strings"

**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "we noted" → "we note" (present tense).
**Suggested fix:** "we note"

---

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1     |
| MAJOR    | 7     |
| MINOR    | 20    |
| **Total**| **28**|

### Breakdown by category
- GRAMMAR: 13
- TYPO: 5
- NOTATION_INCONSISTENCY: 3
- CLARITY: 3
- LOGICAL_GAP: 1
- OVER_CLAIMING: 1
- UNJUSTIFIED_STEP: 1
- IMPLICIT_ASSUMPTION: 1

### Most critical issue

**ISSUE #6 (CRITICAL):** The proof of Lemma \ref{lemma:max_variance} (lines 1147–1152) claims variance is a **convex** function of $\rho$ and invokes "the maximum of a convex function is at an extreme point." In fact, the proof's own calculation shows variance is **concave** in $\rho$ (the inequality goes the wrong way for convexity). The invoked extremal-point theorem does not apply. The lemma's *statement* is correct, but the proof's logical structure is broken. The fix is straightforward: bypass the convexity/concavity argument entirely and instead observe that variance depends only on the diagonal distribution $\{p_i\}$ in the eigenbasis of $O$, reducing to a classical optimization over the probability simplex.

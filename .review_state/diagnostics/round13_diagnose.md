# Diagnostic Report — Round 13
## Section: "Lower bounds for nonlinear Pauli shadow" (lines 1731–2009)

---

## ISSUE #1
**Location:** line ~1733 (`$\mathcal{E}^{\mathrm{RH}}_{\varepsilon}$`)
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The ensemble is defined as $\mathcal{E}_\varepsilon$ in Definition (line 1729–1731) but referenced as $\mathcal{E}^{\mathrm{RH}}_\varepsilon$ here. The superscript "RH" appears only this once.
**Suggested fix:** Use $\mathcal{E}_\varepsilon$ consistently, or add the superscript to the definition.

---

## ISSUE #2
**Location:** line ~1733 (`separate from maximum mixed state purity`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "maximum mixed" should be "maximally mixed."
**Suggested fix:** Replace "maximum mixed state" with "maximally mixed state."

---

## ISSUE #3
**Location:** line ~1734 (`useful to proving`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Incorrect preposition.
**Suggested fix:** "useful for proving" or "useful in proving."

---

## ISSUE #4
**Location:** lines ~1737, 1741 (`writes`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "The $c$-copy average ... writes" and "its purity average and variance writes" — subject–verb agreement. Should be "can be written as" or "is given by."
**Suggested fix:** Replace "writes" with "is given by" in both locations.

---

## ISSUE #5
**Location:** line ~1751 (`can be directly calculate as`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Missing past participle.
**Suggested fix:** "can be directly calculated as."

---

## ISSUE #6
**Location:** line ~1791 (`equals each others`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Subject–verb agreement and possessive error.
**Suggested fix:** "equal each other."

---

## ISSUE #7
**Location:** line ~1797 (`Given a $T$-round ... strategy $M_s = ...$, where ...`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Sentence fragment — "Given ... strategy" has no main clause verb.
**Suggested fix:** "Consider a $T$-round 2-replica measurement strategy $M_s = \bigotimes ...$, where ..."

---

## ISSUE #8
**Location:** line ~1800 (TVD formula `$\delta_{\mathrm{tvd}} = |\tr(M_s ...)|$`)
**Category:** LOGICAL_GAP
**Severity:** MAJOR
**Description:** The total variation distance should involve a sum over measurement outcomes: $\delta_{\mathrm{tvd}} = \sum_s |\tr(M_s \cdot \Delta)|$. As written, only a single outcome $s$ appears, making the formula incorrect for TVD.
**Suggested fix:** Either add $\sum_s$ around the absolute value, or clarify that this is the contribution from a single outcome $s$ and rename accordingly.

---

## ISSUE #9
**Location:** line ~1808 (`$S_{2T}^{\mathbf{a}}$ denoting the permutation contained in position`)
**Category:** GRAMMAR / CLARITY
**Severity:** MINOR
**Description:** "denoting" should be "denotes" (or "which denotes"), and "permutation" should be "permutation group" or "group of permutations."
**Suggested fix:** "where $S_{2T}^{\mathbf{a}}$ denotes the symmetric group on positions $\{i \mid a_i = 1\}$."

---

## ISSUE #10
**Location:** line ~1841 (`$P = C^\dagger Z_1 C$`)
**Category:** SIGN_FACTOR_ERROR
**Severity:** MAJOR
**Description:** The conjugation direction is wrong. For $\rho = C\sigma C^\dagger$, we need $P = CZ_1C^\dagger$ so that $\tr(P\rho^2) = \tr(CZ_1C^\dagger \cdot C\sigma^2 C^\dagger) = \tr(Z_1\sigma^2)$. With $P = C^\dagger Z_1 C$, the trace does not simplify. Line 1848 (Lemma statement) correctly uses $P = CZ_1C^\dagger$, confirming this is a typo on line 1841.
**Suggested fix:** Change `$P = C^\dagger Z_1 C$` to `$P = CZ_1C^\dagger$`.

---

## ISSUE #11
**Location:** line ~1846 (`he can use`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Gender-specific pronoun.
**Suggested fix:** "one can use" or "they can use."

---

## ISSUE #12
**Location:** line ~1853 (`require $\Omega(2^{n})$ rounds`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Subject–verb agreement: "strategy ... require" → "requires."
**Suggested fix:** "requires $\Omega(2^n)$ rounds."

---

## ISSUE #13
**Location:** line ~1864 (`$\leq$ inequality`)
**Category:** UNJUSTIFIED_STEP
**Severity:** MAJOR
**Description:** The transition from the equality on lines 1861–1863 to the "$\leq$" bound on line 1864 is not justified. The step appears to enlarge the summation from $S_{2T}^{\mathbf{a}} \times S_{2T}^{\bar{\mathbf{a}}}$ to all of $S_{2T}$, but no argument is given for why this produces an upper bound (or in which norm/ordering sense "$\leq$" holds for these operator-valued expressions).
**Suggested fix:** Add an explicit justification (e.g., Loewner ordering argument, or trace-norm bound with a specific measurement), or replace with the correct inequality and proof.

---

## ISSUE #14
**Location:** line ~1864 (`$\1(d)^{\ox 2T}$`)
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** Elsewhere the identity is written $\1_d^{\otimes 2T}$ or $\1_{n-1}^{\otimes 2T}$. The notation $\1(d)$ is non-standard and inconsistent.
**Suggested fix:** Replace $\1(d)^{\ox 2T}$ with $\1_d^{\ox 2T}$.

---

## ISSUE #15
**Location:** line ~1867 (`$Z_1^{\ox 2T}$ is a valid 2T-fold Clifford either`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** "either" at end of sentence is incorrect.
**Suggested fix:** "as well" or "too."

---

## ISSUE #16
**Location:** line ~1870 (`Leaves likelihood`)
**Category:** CLARITY
**Severity:** MAJOR
**Description:** "Leaves likelihood" is not a standard term. This likely refers to Le Cam's method, a likelihood ratio argument, or a "leaves of a decision tree" argument. The term is undefined and appears to be garbled.
**Suggested fix:** Define the term precisely or replace with standard terminology (e.g., "Le Cam's two-point method" or "likelihood ratio bound").

---

## ISSUE #17
**Location:** line ~1870 (`$\sum_{s}|\tr(M_s \Phi[\Delta])| \leq 1 - L(s)$`)
**Category:** QUANTIFIER_ERROR
**Severity:** MAJOR
**Description:** The LHS sums over all $s$, but the RHS depends on a specific $s$ via $L(s)$. This is a scope mismatch — $L(s)$ should either be summed/minimized over $s$, or the bound should be stated per-outcome.
**Suggested fix:** Clarify the quantifier structure. Perhaps the bound should read $\sum_s |\ldots| \leq 1 - \min_s L(s)$ or be restated as a per-outcome bound.

---

## ISSUE #18
**Location:** lines ~1876–1879 (identity claimed from `Eq.\eqref{eq:t=1_Delta}`)
**Category:** UNJUSTIFIED_STEP
**Severity:** MAJOR
**Description:** The text references Eq.(eq:t=1_Delta) (which shows $\Phi_{\mathrm{Cl},2}[\Delta_2] = 0$) to justify the algebraic identity in lines 1877–1879. While the $T=1$ zero condition can be rearranged to give the needed substitution, the connection is not explicitly shown. Line 1879 replaces one term using the $\Delta_2 = 0$ relation, but the reader must reverse-engineer this; the algebraic step should be spelled out.
**Suggested fix:** Add an explicit equation showing which term is replaced using $\Delta_2 = 0$, e.g., "Since $\frac{\1^{\otimes 2} + \mathbb{P}(1-R\delta)}{d(d+1-R\delta)} = \frac{\1^{\otimes 2}}{d^2} + \frac{\1^{\otimes 2}+\mathbb{P}}{d(d+1)} - \frac{\1^{\otimes 2}+\mathbb{P}L\delta}{d(d+L\delta)}$ by Eq.(eq:t=1_Delta), we substitute..."

---

## ISSUE #19
**Location:** line ~1881 (`If we defined`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Wrong tense.
**Suggested fix:** "If we define."

---

## ISSUE #20
**Location:** line ~1891 (identity $\sum_{\pi \in S_{2T}^{\mathbf{a}}} d^{c(\pi\gamma)} = \frac{d^{\uparrow|\mathbf{a}|}}{d^{|\mathbf{a}|}}d^{c(\gamma)}$)
**Category:** IMPLICIT_ASSUMPTION
**Severity:** MINOR
**Description:** The identity is correct but relies on the convention that $c(\gamma)$ counts the total number of cycles of $\gamma$ viewed as an element of $S_{2T}$ (including the $|\mathbf{a}|$ trivial fixed-point cycles on positions in $A$). Since $\gamma \in S_{2T}^{\bar{\mathbf{a}}}$, one might naturally count only cycles on $\bar{A}$. The $d^{|\mathbf{a}|}$ denominator precisely compensates for these fixed-point cycles. This should be noted to avoid confusion.
**Suggested fix:** Add a remark: "Here $c(\gamma)$ counts all cycles of $\gamma$ in $S_{2T}$, including the $|\mathbf{a}|$ fixed-point cycles on positions in $\mathbf{a}$."

---

## ISSUE #21
**Location:** line ~1906 (`We thus Taylor expands`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Subject–verb agreement.
**Suggested fix:** "We thus Taylor expand."

---

## ISSUE #22
**Location:** line ~1908 (free variables $\pi, \nu$)
**Category:** NOTATION_INCONSISTENCY
**Severity:** MAJOR
**Description:** The expression inside the Weingarten sum has $d^{c(\pi\nu)}(1-R\delta)^{-c(\pi\beta^{-1})}(L\delta)^{-c(\nu\gamma^{-1})}$, but the summation over $\pi \in S_{|\mathbf{a}|}$ and $\nu \in S_{|\bar{\mathbf{a}}|}$ (present in line 1904) has been dropped. The variables $\pi$ and $\nu$ appear free.
**Suggested fix:** Restore the summation: $\sum_{\pi \in S_{2T}^{\mathbf{a}}, \nu \in S_{2T}^{\bar{\mathbf{a}}}} \frac{d^{c(\pi\nu)}(1-R\delta)^{-c(\pi\beta^{-1})}(L\delta)^{-c(\nu\gamma^{-1})}}{...}$

---

## ISSUE #23
**Location:** line ~1910 (`The difference of two average can then be reform into`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Multiple grammar errors.
**Suggested fix:** "The difference of the two averages can then be reformulated as."

---

## ISSUE #24
**Location:** lines ~1914–1917 (leaves likelihood factorization)
**Category:** UNJUSTIFIED_STEP
**Severity:** MAJOR
**Description:** The factorization $L(s) \geq D^{2T}\prod_{t=1}^{2T} \frac{\tr(F_{s_t}[\sum \lambda'_\rho \mathbb{P}_\rho])}{\tr(F_{s_t})}$ is stated without proof. The product runs over $2T$ terms but the measurement $M_s = \bigotimes_{t=1}^T F_{s_t}^{u_t}$ has only $T$ factors. The indexing is inconsistent, and the factorization inequality itself (which would follow from a multiplicativity property of the likelihood ratio) is not justified.
**Suggested fix:** Clarify the indexing ($T$ vs $2T$), state the multiplicativity lemma being used, and provide or cite a proof.

---

## ISSUE #25
**Location:** line ~1954 ($\mathbb{E}_{\rho \sim \mathcal{E}_1}\rho^{\otimes 2}$ formula)
**Category:** SIGN_FACTOR_ERROR
**Severity:** MAJOR
**Description:** The labels $\ket{00}\bra{00}$ and $\ket{11}\bra{11}$ are swapped. Since $\sigma = \frac{1}{2}\ket{0}\bra{0}\otimes\psi + \frac{1}{2}\ket{1}\bra{1}\otimes\1/d$, the $\ket{00}$ component (both copies choose $\ket{0}$) should be paired with $\psi\otimes\psi$ (Haar-averaged to $\frac{\1+\mathrm{SWAP}}{d(d+1)}$), and $\ket{11}$ (both choose $\ket{1}$) with $(\1/d)^{\otimes 2}$. The formula has these reversed.
**Suggested fix:** Swap the $\ket{00}\bra{00}$ and $\ket{11}\bra{11}$ assignments. The corrected formula should be:
$\frac{1}{4}[\ket{01}\bra{01}+\ket{10}\bra{10}+\ket{11}\bra{11}]\otimes(\frac{\1}{d})^{\otimes 2} + \frac{1}{4}\ket{00}\bra{00}\otimes\frac{\1\otimes\1+\mathrm{SWAP}}{d(d+1)}$

---

## ISSUE #26
**Location:** line ~1956 ($\Delta$ formula)
**Category:** SIGN_FACTOR_ERROR
**Severity:** MAJOR
**Description:** The qubit-space structure of $\Delta$ is incorrect, likely propagated from the error in line 1954. Direct calculation gives $\Delta \propto (2\ket{00}\bra{00}-\1)\otimes[\mathrm{SWAP}-\frac{\1}{d}]$, i.e., the qubit factor is $\ket{00}\bra{00}-\ket{01}\bra{01}-\ket{10}\bra{10}-\ket{11}\bra{11}$. The paper has $\ket{00}\bra{00}+\ket{01}\bra{01}+\ket{10}\bra{10}-\ket{11}\bra{11}$, which has the wrong signs on $\ket{01}$ and $\ket{10}$.
**Suggested fix:** Recompute $\Delta$ from the corrected line 1954. The correct result is:
$\Delta = \frac{2\ket{00}\bra{00}-\1}{4}\otimes\frac{1}{2}\left[\frac{\mathrm{SWAP}}{d(d+1)}-\frac{\1\otimes\1}{d^2(d+1)}\right]$

---

## ISSUE #27
**Location:** line ~1959 (`$\Phi_j$`)
**Category:** MISSING_HYPOTHESIS
**Severity:** MINOR
**Description:** The symbol $\Phi_j$ is used without definition. It appears to denote a local measurement operator at site $j$, but this is never stated.
**Suggested fix:** Define $\Phi_j$ (e.g., "where $\Phi_j$ denotes the local 2-replica POVM element at qubit site $j$").

---

## ISSUE #28
**Location:** line ~1960 (`we analysis the`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Wrong word form.
**Suggested fix:** "we analyze the."

---

## ISSUE #29
**Location:** line ~1962 (`$S^{\mathbf{a}}$`, `$d^{\uparrow \mathbf{a}}$`)
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** Two issues: (1) $S^{\mathbf{a}}$ should be $\mathbb{S}^{\mathbf{a}}$ per the definition on line 1881. (2) $d^{\uparrow \mathbf{a}}$ should be $d^{\uparrow |\mathbf{a}|}$ (rising factorial of the integer $|\mathbf{a}|$, not the vector $\mathbf{a}$).
**Suggested fix:** Replace $S^{\mathbf{a}}$ with $\mathbb{S}^{\mathbf{a}}$ and $d^{\uparrow \mathbf{a}}$ with $d^{\uparrow |\mathbf{a}|}$.

---

## ISSUE #30
**Location:** line ~1963 ($\mathbb{E}_{\rho \sim \mathcal{E}_2}\rho^{\otimes 2T}$ formula)
**Category:** LOGICAL_GAP
**Severity:** MAJOR
**Description:** The formula $\mathbb{E}_2\rho^{\otimes 2T} = 2^{-2T}\sum_\mathbf{a}\ket{\mathbf{a}}\bra{\mathbf{a}}\otimes\frac{S^{\mathbf{a}}}{d^{\uparrow|\mathbf{a}|}}$ treats the mixture state $\bar\psi = (\psi_1+\psi_2)/2$ as if it were a single Haar state across all positions. But $\bar\psi$ is a convex mixture of two independent Haar states, and its $2T$-fold moment $\mathbb{E}[\bar\psi^{\otimes 2T}]$ involves cross terms between $\psi_1$ and $\psi_2$ that produce a more complex structure than a single Haar moment. The formula appears to oversimplify.
**Suggested fix:** Derive the correct $2T$-fold moment of $\bar\psi = (\psi_1+\psi_2)/2$ by expanding the multinomial and averaging each Haar factor independently.

---

## ISSUE #31
**Location:** line ~1788 (Problem definition, `$\{\ldots\}_{\rho_\varepsilon \sim \mathcal{E}_\varepsilon}$`)
**Category:** CLARITY
**Severity:** MINOR
**Description:** The ensemble notation uses a single subscript $\rho_\varepsilon \sim \mathcal{E}_\varepsilon$ but the state involves two independent RH draws ($\rho_{1-R\delta}$ and $\rho_{L\delta}$) with different parameters. The notation obscures the independence.
**Suggested fix:** Replace with `$\{\ldots\}_{\rho_{1-R\delta} \sim \mathcal{E}_{1-R\delta},\; \rho_{L\delta} \sim \mathcal{E}_{L\delta}}$`.

---

## ISSUE #32
**Location:** line ~1831 (`Clifford gate forms a 2-design`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Subject–verb agreement.
**Suggested fix:** "Clifford gates form a 2-design" or "the Clifford group forms a 2-design."

---

## ISSUE #33
**Location:** line ~1840 (`This prevents the Lemma~\ref{lemma:hard_necess1} giving`)
**Category:** GRAMMAR
**Severity:** MINOR
**Description:** Awkward phrasing.
**Suggested fix:** "This prevents Lemma~\ref{lemma:hard_necess1} from giving."

---

## ISSUE #34
**Location:** lines ~1965–1994 (TODO block)
**Category:** INCOMPLETE_PROOF
**Severity:** CRITICAL
**Description:** The exponential lower bound $\delta_{\mathrm{loc}} = O(2^{-n})$ for the MH-ensemble, which is the main result of this section, is NOT proved. The section contains an outline (Steps 1–3) and a "Proposed resolution" but no completed argument. The errors in lines 1954–1956 also affect the starting point of this analysis. This is the most critical gap in the section.
**Suggested fix:** Complete the proof. As a first step, fix the 2-replica average (Issue #25–26), then carry out the 4th-moment Clifford commutant decomposition or the proposed Pauli-weight argument.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 1     |
| MAJOR    | 10    |
| MINOR    | 18    |
| **Total**| **29**|

### Breakdown by category:
- GRAMMAR: 14
- SIGN_FACTOR_ERROR: 3
- UNJUSTIFIED_STEP: 3
- MAJOR logical/quantifier/notation: 4
- NOTATION_INCONSISTENCY: 3
- CLARITY: 3
- INCOMPLETE_PROOF: 1
- LOGICAL_GAP: 2
- IMPLICIT_ASSUMPTION: 1
- MISSING_HYPOTHESIS: 1

### Most Critical Issue

**ISSUE #34 (INCOMPLETE_PROOF):** The main result of this section — the exponential lower bound for local 2-replica measurements on the MH-ensemble — is stated but not proved. The TODO block (lines 1981–1994) acknowledges this explicitly. Additionally, the foundational calculation that the TODO builds on (the MH 2-replica average, Issues #25–26) contains sign errors that must be fixed before the proof can proceed.

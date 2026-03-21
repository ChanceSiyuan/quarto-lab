# Round 4 Diagnostic: "Nonlocal strategies and local no-go" (lines 226–256)

## Issues

---
ISSUE #1
Location: line ~234 ("$\bP^d_\pi$ be the permutation operator on $2k$ replicas of $(\mathbb{C}^d)^{\ox 2k}$")
Category: UNCLEAR_STATEMENT
Severity: MAJOR
Description: The phrase "on $2k$ replicas of $(\mathbb{C}^d)^{\otimes 2k}$" is dimensionally redundant and confusing. It reads as if there are $2k$ copies of an already $2k$-fold tensor product space. The appendix (line 1339) says "the permutation operator on $2k$ replica of $n$-qubits ($d = 2^n$)", which is clearer. The Hilbert space is $(\mathbb{C}^d)^{\otimes 2k}$; the permutation acts on the $2k$ tensor factors.
Suggested fix: "let $\bP^d_\pi$ be the permutation operator on $(\mathbb{C}^d)^{\ox 2k}$ with $\pi = (\mathrm{odds})(\mathrm{even})$ acting as $k$-cycles on odd and even labels respectively"
---

ISSUE #2
Location: line ~241 ("The commutativity follows from $[S_P, S_Q] = 0$ since each pair of terms either acts on disjoint subsystems or involves $[P^{\ox 2}, Q^{\ox 2}] = 0$ (the squaring trick).")
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The sentence refers to "$S_P$" without defining it in the main text. The definition $S_P = \sym_\pi[P^{\ox 2} \otimes (\mathbf{1}^{\otimes 2})^{\otimes(k-1)}]$ only appears in the appendix proof (line 1348). A reader of just the main text would not know what $S_P$ is.
Suggested fix: Either define $S_P$ inline (e.g., "Writing $A_P = S_P \cdot \bP^d_\pi$ where $S_P := \sym_\pi[\cdots]$, commutativity reduces to $[S_P, S_Q] = 0$...") or simply say "The commutativity follows because each pair of symmetrized terms either acts on disjoint subsystems or involves $[P^{\otimes 2}, Q^{\otimes 2}] = 0$."
---

ISSUE #3
Location: line ~241 ("The expectation value factorizes as $\tr[(P\rho\ox\rho^{\ox(k-1)})\bP^d_{(\mathrm{odds})}] \cdot \tr[(P\rho\ox\rho^{\ox(k-1)})\bP^d_{(\mathrm{even})}]$")
Category: CLAIM_MISMATCH
Severity: MINOR
Description: The factorization step in the main text omits a key intermediate: using the symmetrization invariance $\tr[S_P \pi \rho^{\otimes 2k}] = \tr[(P^{\otimes 2} \otimes \mathbf{1}^{\otimes 2k-2}) \pi \rho^{\otimes 2k}]$ (appendix line 1361). This is not obvious and the main text jumps directly to the factored form. Additionally, each factor should have $P\rho$ in just one slot of the $k$-fold tensor, but the notation $P\rho \otimes \rho^{\otimes(k-1)}$ is slightly ambiguous about which copy $P$ acts on.
Suggested fix: Minor — this is acceptable for PRL brevity, but consider adding "(by $\pi$-invariance of $\rho^{\otimes 2k}$)" to justify the removal of $\sym_\pi$.
---

ISSUE #4
Location: line ~245 ("cf.\ Eq.~\eqref{eq:bell_eigenvalue}")
Category: WRONG_REFERENCE
Severity: MINOR
Description: `eq:bell_eigenvalue` (line 957) gives the eigenvalue of $P_i \otimes P_i$ on Bell states in the single-qubit example section. The 4-copy eigenvalue formula in line 245 is derived in the appendix at lines 1384–1385, which references `eq:bell_shadow_eig` (line 1168). While both equations express the same underlying identity $\sigma_\mathbf{q} \otimes \sigma_\mathbf{q} \ket{\Phi_\mathbf{r}} = (-1)^{[\mathbf{r},\mathbf{q}]+\mathbf{q}_x \cdot \mathbf{q}_z}\ket{\Phi_\mathbf{r}}$, the main text cross-reference points to the examples section rather than the appendix derivation where the 4-copy eigenvalue is actually computed.
Suggested fix: Consider referencing the appendix equation `eq:bell_shadow_eig` instead, or referencing both. Alternatively, since `eq:bell_eigenvalue` is in the main text and may be more accessible to the reader, this is acceptable but slightly misleading.
---

ISSUE #5
Location: line ~247 ("$\cO(\varepsilon^{-4}\log|\cO|)$ additional copies with ancilla")
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The main text says "$\cO(\varepsilon^{-4}\log|\cO|)$ additional copies" but doesn't specify what kind of copies. The appendix Lemma (line 1369) says "$\cO(\varepsilon^{-4}\log(|\cO|))$ times $k$-replica strategy with $k \cdot n$ ancilla qubits". The main text omits "$k$-replica" and the ancilla count. For a PRL reader, "copies" is ambiguous — does it mean single copies of $\rho$ or $k$-replica rounds?
Suggested fix: Clarify as "$\cO(\varepsilon^{-4}\log|\cO|)$ additional $k$-replica rounds, each requiring $k \cdot n$ ancilla qubits".
---

ISSUE #6
Location: line ~251 ("the relevant two-copy operators are $\tilde{O}_P = \tfrac{1}{2}(P\ox\1 + \1\ox P)\cdot\mathrm{SWAP}$")
Category: NOTATION_INCONSISTENCY
Severity: MINOR
Description: The operator $\tilde{O}_P$ is introduced here without connecting it to the general framework or the appendix notation. In the appendix (line 1629), the corresponding operator is $O_\mathbf{r} = (\sigma_\mathbf{r} \otimes \mathbf{1}_n) \cdot \text{SWAP}^{\otimes n}$, which is **not** the same as $\tilde{O}_P$. The $\tilde{O}_P = \tfrac{1}{2}(P \otimes \mathbf{1} + \mathbf{1} \otimes P) \cdot \mathrm{SWAP}$ form appears to be the symmetrized linearization of $\tr(P\rho^2)$. These are related but the notational disconnect should be acknowledged.
Suggested fix: Either reconcile the notation with the appendix or add a brief note like "where $\tilde{O}_P$ is the symmetrized linearization of $\tr(P\rho^2)$ on the two-copy space."
---

ISSUE #7
Location: line ~251 ("By Theorem~\ref{thm:linear-equiv}, the no-advantage result does not apply")
Category: UNCLEAR_STATEMENT
Severity: MAJOR
Description: The logic here is inverted or at least confusingly stated. Theorem 2 (linear-equiv) says that for **linear binary** operators, estimation = compatibility. The $\tilde{O}_P$ operators have eigenvalues $\{+1, 0, -1\}$ (spin-1, non-binary), so Theorem 2's precondition ($\|O_i\|_\infty \leq 1$ with binary POVMs) fails. The sentence should clarify: "Since $\tilde{O}_P$ has three distinct eigenvalues (non-binary), the hypotheses of Theorem~\ref{thm:linear-equiv} are not met, so the estimation-compatibility equivalence does not apply." Currently it says "the no-advantage result does not apply" which is vague — what "no-advantage result"?
Suggested fix: "Since $\tilde{O}_P$ has eigenvalues $\{+1,0,-1\}$ (non-binary), Theorem~\ref{thm:linear-equiv} does not apply: estimation may be strictly easier than compatibility."
---

ISSUE #8
Location: line ~253 ("Theorem~\ref{thm:tensor} does not apply, so the per-site factorization $s^*_{\mathrm{loc}} = \prod_l s^*_l$ fails.")
Category: CLAIM_MISMATCH
Severity: MAJOR
Description: The argument says Theorem 1 (tensor factorization) doesn't apply because $A_P$ is a **sum** of two product operators, not itself a product. However, Theorem 1's hypothesis (line 200) requires $F_\alpha = \bigotimes_{l=1}^n F_{\alpha_l}^{(l)}$, i.e., product form of the **linearizations** $F_\alpha$, not the lifted 4-copy operators $A_P$. The linearization $\tilde{O}_P = \tfrac{1}{2}(P \otimes \mathbf{1} + \mathbf{1} \otimes P) \cdot \mathrm{SWAP}$ is itself not a tensor product across qubit sites (SWAP couples the sites). So the correct argument is that the linearizations $\tilde{O}_P$ don't have product form $\bigotimes_l F_{P_l}^{(l)}$, not that the "four-copy operator $A_P$" lacks product form. The sentence conflates the linearization level with the lifted observable level.
Suggested fix: "The two-copy linearizations $\tilde{O}_P$ do not factorize as $\bigotimes_l F_{P_l}^{(l)}$ (unlike the linear case), so Theorem~\ref{thm:tensor} does not apply and $s^*_{\mathrm{loc}} = \prod_l s^*_l$ cannot be invoked."
---

ISSUE #9
Location: line ~253 ("second moment $\sim (11/3)^n \cdot (5/11)^{\mathrm{wt}(P)}$ for product states, with operator norm up to $5^n$ for entangled states")
Category: CLAIM_MISMATCH
Severity: MINOR
Description: The appendix (line 1640) states the $5^n$ operator norm specifically for $O_\mathbf{0}$ (identity Pauli, weight 0). For general weight-$w$ Paulis, the operator norm is $5^{n-w} \cdot (5/3)^w = 5^n \cdot (1/3)^w$. The main text's "up to $5^n$" is technically correct (achieved at $w=0$) but slightly misleading since it suggests all Pauli weights hit $5^n$.
Suggested fix: Minor — could add "up to $5^n$ (at weight 0)" or leave as is since "up to" already implies a bound.
---

ISSUE #10
Location: line ~253 ("exponential in $n$ for any Pauli weight")
Category: UNCLEAR_STATEMENT
Severity: MINOR
Description: The product-state second moment $(11/3)^n \cdot (5/11)^w$ is exponential in $n$ for fixed $w$, yes. But the phrasing "for any Pauli weight" could be read as "for every weight including $w = n$", where the bound is $(5/3)^n$ — still exponential but much smaller than $(11/3)^n$. The statement is correct but the emphasis is slightly misleading.
Suggested fix: No change needed, but could clarify "exponential in $n$ at any fixed weight $w$."
---

ISSUE #11
Location: line ~255 ("The gap quantifies nonlocality as a measurement resource for multi-copy shadow tomography.")
Category: STYLE
Severity: MINOR
Description: This closing sentence is somewhat vague for PRL. "Quantifies nonlocality as a measurement resource" — what quantity? The gap between $O(1)$ (nonlocal) and exponential (local) variance is the quantity, but the sentence doesn't quite say that.
Suggested fix: "This exponential gap between nonlocal and local strategies demonstrates that multi-copy entanglement is a genuine measurement resource for shadow tomography."
---

## Summary

**Total issues: 11** (0 CRITICAL, 3 MAJOR, 8 MINOR)

### Major issues:
1. **ISSUE #1**: Confusing description of the Hilbert space dimension in Theorem statement.
2. **ISSUE #7**: "No-advantage result" is vague; needs to clearly state why Theorem 2 doesn't apply.
3. **ISSUE #8**: Wrong level of argument — the obstruction is at the linearization level ($\tilde{O}_P$ not product), not at the 4-copy $A_P$ level.

### Overall assessment:
The section is well-structured and tells a clear story (nonlocal efficient → local exponential). The main issues are (a) a conceptual imprecision in the local no-go argument (Issue #8) where the non-factorization is attributed to the wrong object, and (b) some undefined notation ($S_P$) and vague references ("no-advantage result"). The quantitative claims all match the appendix. The sign-recovery TODO note and local no-go open question are appropriately flagged in red.

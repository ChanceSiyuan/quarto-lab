# Diagnostic Report: Introduction (lines 155–167)

## Summary

The Introduction is well-structured and reads clearly for a PRL audience. I found **1 major** and **4 minor** issues. No critical errors.

---

### ISSUE #1
**Location:** line 157, `"per-qubit depolarization factor $(d+1) = 3$"`
**Category:** UNCLEAR_STATEMENT
**Severity:** MAJOR
**Description:** The variable $d$ here silently means the single-qubit local dimension $d=2$, but $d$ is used later (line 234, Theorem 1) as the global dimension $d=2^n$. This creates a notation collision. A PRL reader encountering $d$ for the first time in line 157 and then seeing $d=2^n$ in the theorem will be confused.
**Suggested fix:** Replace `$(d+1) = 3$` with `$(d_{\mathrm{loc}}+1) = 3$` or simply write `factor of $3$` without introducing $d$, since the per-qubit dimension is not used elsewhere in the main text. Alternatively: `"the per-qubit factor $(2+1)=3$"`.

---

### ISSUE #2
**Location:** line 159, `"simultaneously estimates all squared Pauli expectations $|\tr(P\rho)|^2$ with $\cO(1)$ samples"`
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** The $\mathcal{O}(1)$ claim needs qualification. Bell sampling estimates *all* $4^n$ squared expectations simultaneously from $\mathcal{O}(1)$ samples per functional — but the total sample count to achieve $\varepsilon$-accuracy for all of them simultaneously is $\mathcal{O}(\varepsilon^{-2}\log|\mathcal{A}|)$ by median-of-means. As written, a reader might think a single measurement suffices for all Paulis at once, which is true for the variance per functional but not for uniform error control. The abstract (line 147) says the same thing; the intended meaning is clear in context, but stating "$\mathcal{O}(1)$ samples *per observable*" would be more precise.
**Suggested fix:** Change to `"with $\cO(1)$ samples per observable"` or `"with $\cO(1)$ second moment"`.

---

### ISSUE #3
**Location:** line 161, `"two-copy local 3-design strategies already incur exponential second moment $\sim (11/3)^n$--$5^n$ depending on the state (Appendix~\ref{app:local_shadow})"`
**Category:** MISSING_REFERENCE
**Severity:** MINOR
**Description:** The parenthetical cites `Appendix~\ref{app:local_shadow}` generically. The precise result is Lemma~\ref{lemma:covar_Pauli} (line 1629). For a PRL where the reader navigates a long appendix, pointing to the specific lemma would help.
**Suggested fix:** Change `(Appendix~\ref{app:local_shadow})` to `(Lemma~\ref{lemma:covar_Pauli})`.

---

### ISSUE #4
**Location:** line 161, `"individual functionals $\tr(\rho^k)$ via the ancilla-based SWAP test~\cite{ekert2002direct}"`
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** Writing "individual functionals $\tr(\rho^k)$" as a contrast to the preceding sentence about estimating *all* Pauli-weighted nonlinear functionals is slightly misleading. The SWAP test estimates one specific nonlinear functional (purity / higher moments), not parametric families. The sentence is grammatically correct but the juxtaposition with "all $|\tr(P\rho^k)|$ simultaneously" in the next clause makes it read as though the SWAP test handles one member of the same family, when it actually handles a different (simpler) quantity. Consider making the distinction sharper.
**Suggested fix:** Change to `"individual global moments $\tr(\rho^k)$ via the SWAP test~\cite{ekert2002direct}"` — the word "global" clarifies that this is not a Pauli-resolved quantity.

---

### ISSUE #5
**Location:** line 161, `"yet nonlocal multi-copy circuits can achieve $\cO(1)$ cost"`
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** The "$\cO(1)$ cost" here refers to the second moment / variance per functional (i.e., $s^*=1$), not the total sample complexity. This echoes Issue #2. Using "cost" without qualification could confuse readers about what quantity is $\mathcal{O}(1)$.
**Suggested fix:** Change to `"$\cO(1)$ second moment per functional"` or `"bounded variance"`.

---

## Overall Assessment

The Introduction effectively sets up the three-way tension (single-copy linear → multi-copy nonlinear → local vs. nonlocal) and clearly enumerates the five main results. The main actionable issue is **#1** (the $d$ notation collision), which should be fixed before submission. The remaining issues are polish-level improvements for precision.

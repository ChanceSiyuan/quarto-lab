# Diagnostic Report: Framework Section (Lines 168–193)

**Target:** `\prlsection{Framework.}` — lines 168–193 of main.tex
**Date:** 2026-03-17

---

## ISSUE #1
**Location:** line ~186–188 (eq. 3: `\sum_j \Pi_j = s\1, ... |h_\alpha(j)| \leq 1`)
**Category:** NOTATION_INCONSISTENCY
**Severity:** MAJOR
**Description:** The main text optimization eq. (3) uses the **super-normalization formulation**: $\sum_j \Pi_j = s \cdot \mathbb{1}^{\otimes k}$ with $|h_\alpha(j)| \leq 1$. The appendix primal eq. (A12) at line 685 uses the **scaling formulation**: $\sum_j \Pi_j = \mathbb{1}^{\otimes k}$ with $|h_\alpha(j)| \leq s$. These are equivalent by rescaling $\Pi_j \to \Pi_j/s$, but the reader following the "see Appendix" reference will encounter a different-looking program with no explicit reconciliation. This is the most likely source of confusion for a careful reader.
**Suggested fix:** Either (a) use the same formulation in both places, or (b) add a parenthetical in line 184: "equivalently, minimizing the estimator bound $s$ with $\sum_j \Pi_j = \mathbb{1}^{\otimes k}$ and $|h_\alpha(j)| \leq s$; see Appendix~\ref{app:f-compat}."

---

## ISSUE #2
**Location:** line ~174 (`\begin{definition}[f-incompatibility]\label{def:f-compat}`)
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** The definition is titled "f-incompatibility" but defines the condition for **f-compatibility** (the $s=1$ case where $|h_\alpha(j)| \leq 1$). The incompatibility concept is the failure of this condition, quantified by $s^* > 1$ on line 184. The title should reflect what is being defined.
**Suggested fix:** Rename to `[f-compatibility]` or `[$k$-replica $\mathcal{F}$-compatibility]` to match the body text "is \emph{$k$-replica $\cF$-compatible}".

---

## ISSUE #3
**Location:** line ~184 ("The \emph{f-incompatibility robustness} $s^*(\cF)$ is the minimum super-normalization $s \geq 1$...")
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The main text defines $s^*$ directly as the robustness. The appendix (Definition 5, line 593) defines $r^*_k(\mathcal{F})$ as the f-incompatibility with $s^* = r^* + 1$. The main text never introduces $r^*$, which is fine for brevity, but the phrase "f-incompatibility robustness" applied to $s^*$ clashes with the appendix where "f-incompatibility" is $r^* = s^* - 1$. A reader cross-referencing will see different quantities called similar names.
**Suggested fix:** Either use $r^*$ in the main text too, or add a brief note: "where $s^* = 1 + r^*$ with $r^*$ the f-incompatibility defined in Appendix~\ref{app:f-compat}."

---

## ISSUE #4
**Location:** line ~184 ("...such that the above conditions are feasible")
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** "The above conditions" refers to eq. (2) in Definition 1, but the optimization program is stated *below* on lines 186–188. The sentence tries to define $s^*$ in prose before showing the program, creating a forward reference. The phrase "the above conditions" is ambiguous — it could refer to Definition 1's conditions or the (not yet shown) optimization constraints.
**Suggested fix:** Restructure: present the optimization program first, then define $s^*$ as its optimum. Or change to: "The \emph{f-incompatibility robustness} $s^*(\mathcal{F})$ is the optimum of the following program:"

---

## ISSUE #5
**Location:** line ~170 (`$\vec{p}_i(\rho) = (\tr[A_i^{(a)}\rho])_a$`)
**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The POVM element notation $A_i^{(a)}$ (outcome $a$ of observable $i$) appears only here in the main text and is never defined. The appendix (line 497) uses $A_i^{(r)}$ with outcome label $r$, a different letter. Neither is formally introduced as a POVM.
**Suggested fix:** Add a brief clarification: "where $\{A_i^{(a)}\}_a$ are the POVM elements of the $i$-th measurement" and align the outcome label with the appendix convention.

---

## ISSUE #6
**Location:** line ~182 ("Any degree-$r$ polynomial $f_\alpha$ admits a \emph{linearization}: an operator $F_\alpha$ on $\cH^{\ox k}$ ($k \geq r$), not necessarily Hermitian")
**Category:** MISSING_REFERENCE
**Severity:** MINOR
**Description:** The sentence references `Definition~\ref{def:linearization}` and `Lemma~\ref{lem:structure_fcomp_lemma}` correctly. However, the parenthetical "(Definition~\ref{def:linearization})" appears at the end of the sentence, making it look like it qualifies the "symmetric subspace" claim rather than the "linearization" claim. The lemma reference is correctly placed.
**Suggested fix:** Move the definition reference earlier: "...admits a \emph{linearization} (Definition~\ref{def:linearization}): an operator $F_\alpha$..."

---

## ISSUE #7
**Location:** line ~191 (eq. 4: `N = \cO\!\left(k\cdot [s^*(k)]^2\cdot \varepsilon^{-2}\cdot \log(|\cA|/\delta)\right)`)
**Category:** CLAIM_MISMATCH
**Severity:** MINOR
**Description:** The appendix derivation (line 518) gives $kN = (2ks^2/\varepsilon^2) \cdot \log(2|\mathcal{A}|\delta^{-1})$, where the factor 2 appears both as a multiplicative constant and inside the log. The main text absorbs both into $\mathcal{O}(\cdot)$ and writes $\log(|\mathcal{A}|/\delta)$. This is fine asymptotically, but eq. (4) uses $N$ for total copies while the appendix uses $kN$ for total copies (with $N$ being the number of rounds). The main text's $N$ is the appendix's $kN$. This symbol overloading could confuse cross-referencing readers.
**Suggested fix:** Clarify that $N$ in eq. (4) is the total number of state copies consumed (not POVM rounds). Or rename to $N_{\mathrm{tot}}$ or use the same symbol as the appendix.

---

## ISSUE #8
**Location:** line ~193 ("Within this protocol (i.i.d.\ super-normalized POVM with bounded post-processing)")
**Category:** MISSING_INTUITION
**Severity:** MINOR
**Description:** The term "super-normalized POVM" appears for the first time with no intuition. A reader unfamiliar with this concept gets no indication of why one would allow $\sum \Pi_j = s \cdot \mathbb{1}$ rather than $\sum \Pi_j = \mathbb{1}$. The connection to "measuring with a normalized POVM but rescaling estimators" (the appendix's equivalent formulation) would provide the needed intuition.
**Suggested fix:** Add a brief parenthetical: "(equivalently, a normalized POVM whose estimators may have magnitude up to $s^*$)".

---

## ISSUE #9
**Location:** line ~170 ("By the classical estimation condition~\cite{wu2020polynomial}, unbiased estimation of degree-$r$ polynomials requires at least $r$ i.i.d.\ samples.")
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** This sentence is accurate (matching Lemma A1 in the appendix) but it conflates two roles of $r$: the degree of the polynomial and the minimum sample size. The sentence should clarify that this is the *classical* requirement — $r$ i.i.d. samples from the *distribution*. In the quantum setting introduced next, $k$ copies of $\rho$ serve as the quantum analogue, but $k$ plays a different structural role than the classical $r$ samples (one copy gives access to all outcome probabilities, not just one sample).
**Suggested fix:** Consider: "...requires at least $r$ i.i.d.\ draws from the distribution."

---

## Summary

| Severity | Count | Issues |
|----------|-------|--------|
| CRITICAL | 0 | — |
| MAJOR | 1 | #1 (primal formulation mismatch between main text and appendix) |
| MINOR | 8 | #2–#9 |

**Overall assessment:** The Framework section is logically sound — all claims are correct and properly supported by the appendix. The main issue is a presentation mismatch: the main text uses the super-normalization formulation while the appendix uses the scaling formulation. While mathematically equivalent, this will trip up readers cross-referencing. The remaining issues are minor clarity and notation improvements appropriate for a PRL polish pass.

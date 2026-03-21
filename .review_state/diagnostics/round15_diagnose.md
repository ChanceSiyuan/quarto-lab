# Diagnostic Report: Framework Section (lines 168–193)

**Date:** 2026-03-17
**Target:** `\prlsection{Framework.}` (lines 168–193 of main.tex)
**Cross-referenced:** Appendix A (lines 337–850+), especially Definitions 4–6, Lemmas 3–5, and the primal SDP (eq:primal-bilinear).

---

## ISSUE #1
**Location:** line ~170
> "polynomial functionals $\cF = \{f_\alpha\}_{\alpha \in \cA}$ of degree $\leq r$ in the outcome probability vectors $\vec{p}_i(\rho)$"

**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** The main text describes $f_\alpha$ as a polynomial "in the outcome probability vectors $\vec{p}_i(\rho)$," which is the classical framing (Appendix A.1, line 416ff). However, the appendix Definition 4 (line 494, `def:k-copy-estimateability`) and Definition 6 (`def:linearization`, line 649) work with $f_\alpha(\rho)$ as polynomials in the matrix entries of $\rho$. These are equivalent when the functionals factor through POVM outcome probabilities, but the main text never states this equivalence. A reader might wonder whether $\cF$ consists of polynomials of probabilities or of $\rho$ directly.
**Suggested fix:** Add a brief clause: "equivalently, degree-$\leq r$ polynomials in the matrix entries of $\rho$" or simply say "polynomial functionals of degree $\leq r$ in $\rho$" and note the POVM structure is used for classical post-processing.

---

## ISSUE #2
**Location:** line ~170
> "By the classical estimation condition~\cite{wu2020polynomial}, unbiased estimation of degree-$r$ polynomials requires at least $r$ i.i.d.\ draws from the distribution."

**Category:** MISSING_INTUITION
**Severity:** MINOR
**Description:** This sentence compresses the classical result (Lemma 1, `lem:classical-estimation-condition`, line 427) into an implication that may confuse: the classical result says degree-$r$ polynomials *can* be estimated from $r$ samples (sufficiency via falling factorials) and that $<r$ samples are insufficient (necessity). The main text only states the necessity direction ("requires at least $r$"). For a PRL reader, it's worth flagging that $r$ copies also *suffice* for polynomials, since this is the key motivation for multi-copy quantum strategies.
**Suggested fix:** Change to: "unbiased estimation of degree-$r$ polynomials requires *exactly* $r$ i.i.d.\ draws from each distribution (the falling-factorial estimator is optimal)~\cite{wu2020polynomial}." Or: "requires and is achievable with $r$ i.i.d.\ draws."

---

## ISSUE #3
**Location:** line ~175 (Definition 1)
> "$|h_\alpha(j)|\leq 1$"

**Category:** CLAIM_MISMATCH
**Severity:** MAJOR
**Description:** Definition 1 (main text) defines f-compatibility with estimator bound $|h_\alpha(j)| \leq 1$. This corresponds to $s = 1$ (zero f-incompatibility). However, the normalization condition $\max_\rho |f_\alpha(\rho)| = 1$ that makes this well-defined is introduced in the appendix (line 581) but is **not stated** in the main text definition. Without normalization, the bound $|h_\alpha(j)| \leq 1$ is not meaningful — a functional with $\max_\rho |f_\alpha(\rho)| = 0.01$ trivially satisfies $|h| \leq 1$, while one with max value $100$ cannot.

The appendix explicitly says (line 581–583): "We say a set of state properties $\cF$ is normalized if $\forall \alpha, \max_\rho |f_\alpha(\rho)| = 1$." This prerequisite is missing from the main text definition.

**Suggested fix:** Add "where $\cF$ is normalized ($\max_\rho |f_\alpha(\rho)| = 1$ for each $\alpha$)" either before Definition 1 or within it.

---

## ISSUE #4
**Location:** line ~182
> "After symmetrizing the POVM, condition~\eqref{eq:f-compat} becomes $\sum_j h_\alpha(j)\Pi_j = F_\alpha$ on the symmetric subspace (Lemma~\ref{lem:structure_fcomp_lemma})."

**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** The phrase "on the symmetric subspace" is imprecise. The appendix proof (Lemma 5, line 657–669) establishes that after symmetrizing the POVM, the operator equation $\sum_j h_\alpha(j)\tilde{\Pi}_j = \tilde{F}_\alpha$ holds as an operator identity on $\cH^{\otimes k}$ (not just restricted to the symmetric subspace). What is restricted to the symmetric subspace is the *validity* — the equation is derived from the fact that $\{\rho^{\otimes k}\}_\rho$ span the symmetric subspace via the polarization identity. But the resulting operator equation holds as stated without restriction.

**Suggested fix:** Change to: "After symmetrizing the POVM, condition~\eqref{eq:f-compat} reduces to the operator equation $\sum_j h_\alpha(j)\Pi_j = F_\alpha$ (Lemma~\ref{lem:structure_fcomp_lemma})." If precision is desired: "...reduces to $\sum_j h_\alpha(j)\Pi_j = F_\alpha$ as operators on $\cH^{\otimes k}$, where $\Pi_j$ is supported on the symmetric subspace."

---

## ISSUE #5
**Location:** line ~184
> "(a bilinear program in $h_\alpha(j)$ and $\Pi_j$, which is exactly equivalent to a standard SDP via coarse-graining over sign vectors; strong duality holds by Slater's condition; see Appendix~\ref{app:f-compat})"

**Category:** STYLE
**Severity:** MINOR
**Description:** This parenthetical packs three technical claims (bilinear → SDP equivalence, coarse-graining mechanism, strong duality) into a single aside. For PRL, this is acceptable but dense. More importantly, the phrase "coarse-graining over sign vectors" is jargon that will be opaque to most readers without the appendix (the technique is explained at line 786–803). Consider whether this parenthetical adds enough value to justify its density, or whether a simpler pointer suffices.

**Suggested fix:** Simplify to: "(equivalent to a standard SDP with strong duality; see Appendix~\ref{app:f-compat})". The coarse-graining mechanism is an implementation detail better left to the appendix.

---

## ISSUE #6
**Location:** line ~186
> "$\Pi_j \geq 0$"

**Category:** NOTATION_INCONSISTENCY
**Severity:** MINOR
**Description:** The main text uses $\Pi_j \geq 0$ while the appendix (line 685) uses $\Pi_j \succeq 0$ (the standard notation for positive semidefiniteness). In the PRL context where $\Pi_j$ are operators, $\geq 0$ is ambiguous (could mean element-wise). The appendix correctly uses $\succeq$.

**Suggested fix:** Change to $\Pi_j \succeq 0$ for consistency with the appendix and standard convention.

---

## ISSUE #7
**Location:** line ~191–192
> "$N = \cO\!\left(k\cdot [s^*(k)]^2\cdot \varepsilon^{-2}\cdot \log(|\cA|/\delta)\right)$"

**Category:** CLAIM_MISMATCH
**Severity:** MINOR
**Description:** The appendix (line 511) derives the total copy count as $kN = (2ks^2/\varepsilon^2)\cdot\log(2|\cA|\delta^{-1})$, where $N$ there denotes the number of measurement rounds. The main text uses $N$ for total copies and writes $\log(|\cA|/\delta)$, dropping the factor of 2 inside the log. While this is absorbed by the $\cO(\cdot)$ notation, the argument of the log differs: $\log(|\cA|/\delta)$ vs $\log(2|\cA|/\delta)$. This is fine under $\cO$, but worth noting for consistency.

No fix needed — absorbed by $\cO$ notation.

---

## ISSUE #8
**Location:** line ~193
> "Within this protocol (i.i.d.\ POVM on $k$ copies with estimators bounded by $s^*$), the optimal copy number minimizes $k\cdot [s^*(k)]^2$ over $k$."

**Category:** MISSING_INTUITION
**Severity:** MINOR
**Description:** This closing sentence introduces the key optimization problem — choosing $k$ to minimize $k \cdot [s^*(k)]^2$ — but gives no hint about when increasing $k$ helps. The reader is told to minimize but not given intuition for the trade-off: more copies ($k\uparrow$) may decrease $s^*$ (better compatibility) but increase the per-round cost ($k\uparrow$). A single clause would make this actionable.

**Suggested fix:** Add: "...minimizes $k\cdot [s^*(k)]^2$ over $k$, balancing the per-round copy cost against the improvement in measurement compatibility."

---

## Summary

| # | Category | Severity | Key Issue |
|---|----------|----------|-----------|
| 1 | UNCLEAR_STATEMENT | MINOR | Polynomial of probabilities vs. of $\rho$ ambiguity |
| 2 | MISSING_INTUITION | MINOR | Classical result: only necessity stated, not sufficiency |
| 3 | CLAIM_MISMATCH | **MAJOR** | Normalization $\max|f_\alpha|=1$ missing from Definition 1 |
| 4 | UNCLEAR_STATEMENT | MINOR | "on the symmetric subspace" imprecise |
| 5 | STYLE | MINOR | Dense parenthetical with jargon |
| 6 | NOTATION_INCONSISTENCY | MINOR | $\geq 0$ vs $\succeq 0$ for PSD |
| 7 | CLAIM_MISMATCH | MINOR | Log argument differs (absorbed by $\cO$) |
| 8 | MISSING_INTUITION | MINOR | No intuition for $k$-optimization trade-off |

**Overall Assessment:** The Framework section is well-structured and faithfully represents the appendix results. The one **major** issue is the missing normalization condition in Definition 1 — without it, the $|h_\alpha(j)| \leq 1$ bound is not well-motivated. All other issues are minor notation/clarity improvements appropriate for PRL polish.

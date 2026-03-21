# Round 18 Diagnostic: Discussion (lines 257–269)

## Summary

The Discussion section is well-structured with clear signposting of results and open problems. I found 4 issues, none critical.

---

## ISSUE #1
**Location:** line ~259 ("$s^*_l=1$ per site for squared Pauli expectations via two-copy Bell measurement")
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** The parenthetical says "$s^*_l=1$ per site … via two-copy Bell measurement" but the Bell measurement is a *nonlocal* joint measurement on qubits across copies, not a per-site local measurement. The quantity $s^*_l$ is defined as the per-site robustness under local strategies (Theorem 3, eq. (6)). Saying $s^*_l=1$ "per site" is slightly misleading — what's really happening is that the squaring trick makes the *global* $s^*=1$ because the linearizations $P\otimes P$ commute, not because each site independently has robustness 1. The tensor factorization theorem doesn't even apply here (as noted in Sec. IV for the nonlinear case).
**Suggested fix:** Clarify: replace "($s^*_l=1$ per site for squared Pauli expectations via two-copy Bell measurement" with "($s^*=1$ for squared Pauli expectations since the linearizations $P_i\otimes P_i$ commute". Or explicitly note this is the *global* robustness, not from per-site factorization.

---

## ISSUE #2
**Location:** line ~262 ("one expects $\mathrm{Var}_{\mathrm{opt}}(O;\rho) \leq \|O\|_E^2 \leq (s^*)^2$, though the second inequality awaits a formal proof")
**Category:** UNCLEAR_STATEMENT
**Severity:** MAJOR
**Description:** This inequality chain is introduced only in the Discussion with no prior setup. The quantities $\mathrm{Var}_{\mathrm{opt}}(O;\rho)$ and $\|O\|_E$ are never defined in the paper (main text or appendix). The reader has no way to evaluate this claim. The shadow norm $\|O\|_E$ presumably refers to Nguyen et al.'s shadow norm, but this is not stated. Additionally, claiming an unproven inequality in a PRL letter without even defining the terms is problematic — it reads as speculation rather than a concrete open question.
**Suggested fix:** Either (a) remove the inequality chain entirely and simply state that connecting f-incompatibility robustness to existing shadow-norm bounds is an open direction, or (b) briefly define $\|O\|_E$ (e.g., "the shadow norm of~\cite{nguyen2022optimizing}") and $\mathrm{Var}_{\mathrm{opt}}$ before stating the conjectured chain.

---

## ISSUE #3
**Location:** line ~261 ("---where commutativity graphs determine simultaneous measurability---")
**Category:** STYLE
**Severity:** MINOR
**Description:** The em-dash parenthetical explaining graph-theoretic approaches is vague and adds little. In PRL, every clause must earn its place. "Commutativity graphs determine simultaneous measurability" is almost tautological — commutativity *is* simultaneous measurability for projective measurements.
**Suggested fix:** Remove the parenthetical and tighten: "…connects to graph-theoretic approaches~\cite{graph2024nonlinear} and fermionic joint measurements~\cite{mcnulty2024fermionic}, which exploit complementary algebraic structures; their interplay…"

---

## ISSUE #4
**Location:** line ~261 ("determining the optimal copy-complexity trade-off $\min_k k\cdot[s^*(k)]^2$ for general functional families is an algorithmic challenge")
**Category:** UNCLEAR_STATEMENT
**Severity:** MINOR
**Description:** Calling this "an algorithmic challenge" is vague. Is the challenge computational (solving the SDP for large $k$)? Or is it analytical (finding closed-form expressions)? For PRL readers, specifying what makes this hard would be more useful.
**Suggested fix:** Sharpen to something like: "…is open, as the SDP dimension grows exponentially in $k$" or "…requires new analytical techniques beyond the SDP formulation."

---

## Overall Assessment

The Discussion is concise and hits the right notes for a PRL letter. The main concern is **Issue #2** (undefined quantities in the conjectured inequality chain), which should be either properly set up or removed. The other issues are minor polish.

#!/usr/bin/env python3
import re

# Read the file
with open('/Users/chance/quarto-lab/theory/Topics/Shadow_tomography/multi-copy-shadow.qmd', 'r') as f:
    content = f.read()

# Define the old text (lines 120-193)
old_text = r'''### Examples.

In the case \$k = 2\$, the commutants we choose writes
\$\\{A_{\\mathbf{r}} := {2}\^{-1}{\\(\\sigma_{\\mathbf{r}}\\sigma_{\\mathbf{r}}\\mathbb{I}_n\\mathbb{I}_n \+ \\mathbb{I}_n\\mathbb{I}_n\\sigma_{\\mathbf{r}}\\sigma_{\\mathbf{r}}\\)} \\mathrm{S}_{13}\\mathrm{S}_{24}\\}_{\\mathbf{r} \\in \\mathbb{F}_2\^{2n}}\$.
Notice that
\$\\sigma_{\\mathbf{r}} \\otimes \\sigma_{\\mathbf{r}} \\ket{\\Phi_{\\mathbf{a}}} = \\(-1\\)\^{\\[\\mathbf{r},\\mathbf{a}\\]}\\ket{\\Phi_{\\mathbf{a}}}\$,
the shared eigenbasis of \$\\mathcal{A}\$ have the form
\$\\ket{\\Psi\^{s}_{\\(\\mathbf{a}, \\mathbf{b}\\)}}\$ below with eigenvalues
\$\\lambda_{\\(s,\\mathbf{a},\\mathbf{b}\\)} :=s \\cdot 2\^{-1}\\[\\(-1\\)\^{\\[\\mathbf{r}, \\mathbf{a}\\]} \+ \\(-1\\)\^{\\[\\mathbf{r}, \\mathbf{b}\\]}\\]\$
and \$s = \\pm 1\$.
\$\$
\\begin{align}
   \\ket{\\Psi\^{s}_{\\(\\mathbf{a}, \\mathbf{b}\\)}}&=
   \\begin{cases}
    {2\^{-1/2}}\\left\\[{\\ket{\\Phi_{\\mathbf{a}_x \\mathbf{a}_z}} \\otimes \\ket{\\Phi_{\\mathbf{b}_x\\mathbf{b}_z} }\+s \\ket{\\Phi_{\\mathbf{b}_x \\mathbf{b}_z}} \\otimes \\ket{\\Phi_{\\mathbf{a}_x\\mathbf{a}_z}}}\\right\\] & \\text{if~} \\mathbf{a} < \\mathbf{b}, \\\\
    \\ket{\\Phi_{\\mathbf{a}_x \\mathbf{a}_z}}\\ket{\\Phi_{\\mathbf{a}_x \\mathbf{a}_z}}& \\text{if~} \\mathbf{a} = \\mathbf{b}.
\\end{cases}
\\end{align}
\$\$

!\\[A 4-copy strategy for non-linear shadow tomography\\]\\(4rep_strat.png\\)

After implementing the measurement
\$\\left\\{\\ket{\\Psi\^{s}_{\\(\\mathbf{a}, \\mathbf{b}\\)}} \\bra{\\Psi\^{s}_{\\(\\mathbf{a}, \\mathbf{b}\\)}}\\right\\}_{s \\in \\{\+,-\\}, \\mathbf{a},\\mathbf{b} \\in \\mathbb{F}_2\^{2n}}\$
for \$T\$ times and recording the results
\$\\{\\(s_t,\\mathbf{a}_t, \\mathbf{b}_t\\)\\}_{t = 1}\^{T}\$, the average of
\$A_{\\mathbf{r}} = \\sum \\lambda_{\\(\\pm,\\mathbf{a},\\mathbf{b}\\)} \\ket{\\Psi\^{\\pm}_{\\(\\mathbf{a}, \\mathbf{b}\\)}} \\bra{\\Psi\^{\\pm}_{\\(\\mathbf{a}, \\mathbf{b}\\)}}\$
can then be estimated by calculating the estimator
\$T\^{-1}\\sum_{t = 1}\^{T} \\lambda_{\\(s_t, \\mathbf{a}_t,\\mathbf{b}_t\\)}\$. To
realize such a measurement, we refer to construction
in \\[@liu2024auxiliary\\] and noted that
\$\$
\\begin{align\*}
    \\ket{\\Psi\^{s}_{\\mathbf{a}, \\mathbf{b}}}&= \\mathrm{CNOT}_{34}\\mathrm{CNOT}_{12}\\mathrm{H}_3\\mathrm{H}_1 \\cdot
\\begin{cases}
    2\^{-1/2} \\left\\[{\\ket{\\mathbf{a}_x \\mathbf{a}_z\\mathbf{b}_x\\mathbf{b}_z} \+s \\ket{\\mathbf{b}_x \\mathbf{b}_z\\mathbf{a}_x \\mathbf{a}_z}}\\right\\] &\\text{if~} \\mathbf{a} < \\mathbf{b}\\\\
    \\ket{\\mathbf{a}_x \\mathbf{a}_z\\mathbf{b}_x\\mathbf{b}_z}&\\text{if~} \\mathbf{a} = \\mathbf{b}
\\end{cases},\\\\
&= \\mathrm{CNOT}_{34}\\mathrm{CNOT}_{12}\\mathrm{H}_3\\mathrm{H}_1 \\mathrm{CNOT}_{13}\\mathrm{CNOT}_{24}\\cdot
\\begin{cases}
    2\^{-1/2} \\left\\[{\\ket{\\mathbf{a}_x \\mathbf{a}_z} \+s \\ket{\\mathbf{b}_x \\mathbf{b}_z}} \\right\\]\\ket{\\mathbf{a} \+ \\mathbf{b}} &\\text{if~} \\mathbf{a} < \\mathbf{b}\\\\
    \\ket{\\mathbf{a}_x \\mathbf{a}_z} \\ket{\\mathbf{0} \\mathbf{0}}&\\text{if~} \\mathbf{a} = \\mathbf{b}
\\end{cases},\\\\
&= \\mathrm{CNOT}_{34}\\mathrm{CNOT}_{12}\\mathrm{H}_3\\mathrm{H}_1 \\mathrm{CNOT}_{13}\\mathrm{CNOT}_{24}\\cdot
\\begin{cases}
    2\^{-1/2} \\left\\[{\\ket{\\mathbf{a}\^{I}} \+s \\ket{\\bar{\\mathbf{a}}\^{I}}}\\right\\] \\ket{\\mathbf{a}\^{E}}\\ket{\\mathbf{a} \+ \\mathbf{b}} &\\text{if~} \\mathbf{a} < \\mathbf{b}\\\\
    \\ket{\\mathbf{a}_x \\mathbf{a}_z} \\ket{\\mathbf{0} \\mathbf{0}}&\\text{if~} \\mathbf{a} = \\mathbf{b}
\\end{cases}.
\\end{align\*}
\$\$
This disentangled the qubit on the third and the forth
copy. Thus, we can locally implement the gate sequence
\$\\mathrm{CNOT}_{13}\\mathrm{CNOT}_{24}\\mathrm{H}_3\\mathrm{H}_1\\mathrm{CNOT}_{12}\\mathrm{CNOT}_{34}\$
and then measure the \$3\$-rd and \$4\$-th copies on the computational basis
\$\\ket{\\mathbf{s}_{3}\\mathbf{s}_4}\$. This gives the difference of vector
\$\\mathbf{a}\$ and \$\\mathbf{b}\$ through
\$\\mathbf{s}_{3} = \\mathbf{a}_x \+ \\mathbf{b}_x,\\mathbf{s}_{4} = \\mathbf{a}_z \+ \\mathbf{b}_z\$.
This information then indicates a separtiton of the \$1\$-st and \$2\$-nd
copies of qubits \$\\{1,\\cdots,2n\\} = E \\cup I\$, with
\$E := \\{i \\in \\[2n\\]\\| a_i = b_i\\}\$ and
\$I:= \\{i \\in \\[2n\\]\\| \\bar{a}_i = b_i\\} := \\{i_1<i_1<\\cdots<i_{\\|I\\|}\\}\$. We
then implement the computational basis measurement
\$\\ket{\\mathbf{s}\^{E}}\$ on the qubits in set \$E\$ and a GHZ state
measurement \$s\^{I}\$ formulized by circuit: \$\$\\begin{align}
    \\frac{1}{\\sqrt{2}} \\left\\[{\\ket{\\mathbf{a}\^{I}} \+ s\\ket{\\bar{\\mathbf{a}}\^{I}}} \\right\\] &=
    \\begin{cases}
        \\frac{1}{\\sqrt{2}} \\left\\(\\bigotimes_{i \\in I} X_i \+ Z_{i_1}\\right\\) \\ket{\\bar{\\mathbf{a}}\^{I}}  &\\text{if~} s = -1,\\\\
        \\frac{1}{\\sqrt{2}} \\left\\(\\bigotimes_{i \\in I} X_i \+ Z_{i_1}\\right\\) \\ket{{\\mathbf{a}}\^{I}}  &\\text{if~} s = \+1,
    \\end{cases}\\\\
    &=\\left\\(\\prod_{i = i_1}\^{i_{\\|I\\|-1}}\\mathrm{CNOT}_{i,i\+1}\\right\\)\^{\\dagger} H_{i_1} \\left\\(\\prod_{i = i_1}\^{i_{\\|I\\|-1}}\\mathrm{CNOT}_{i,i\+1}\\right\\) \\begin{cases}\\ket{\\bar{\\mathbf{a}}\^{I}} &\\text{if~}s = -1,\\\\\\ket{{\\mathbf{a}}\^{I}} &\\text{if~}s = 1.\\end{cases}
\\end{align}\$\$ Here we use the fact that since \$\\mathbf{a}< \\mathbf{b}\$,
we have \$a_{i_1} = 0\$. This then gives the \$\\mathbf{a}\$ vector through
\$\\mathbf{a}\^{E} = {\\mathbf{s}\^{E}}\$ and
\$s = \+1, \\mathbf{a}\^{I} = {s}\^{I}\$ if \$a_{i_1} = 0\$,
\$s = -1, \\mathbf{a}\^{I} = \\bar{s}\^{I}\$ if \$a_{i_1} = 1\$.'''

# This is too complex for regex. Let me use a simpler approach - find the section header and replace everything until the next section
# Find "### Examples." and replace until "The construction above"

pattern = r'### Examples\..*?(?=The construction above)'

new_text = '''### Examples

::: {.callout-important icon="false"}
## Lemma: 4-Copy Measurement Strategy for $k=2$

For the case $k = 2$, there exists a measurement protocol on 4 copies of the quantum state that can estimate the commutants $A_{\\mathbf{r}}$ through a shared eigenbasis measurement. The eigenbasis states $\\ket{\\Psi^{s}_{(\\mathbf{a}, \\mathbf{b})}}$ with eigenvalues $\\lambda_{(s,\\mathbf{a},\\mathbf{b})} :=s \\cdot 2^{-1}[(-1)^{[\\mathbf{r}, \\mathbf{a}]} + (-1)^{[\\mathbf{r}, \\mathbf{b}]}]$ (where $s = \\pm 1$) can be measured using a combination of local gates, computational basis measurements, and GHZ measurements.
:::

::: {.callout-note collapse="true"}
## Construction and Proof (Click to expand)

**Step 1: Define the commutants**

For $k = 2$, we choose the commutants as:
$$
\\{A_{\\mathbf{r}} := {2}^{-1}{(\\sigma_{\\mathbf{r}}\\sigma_{\\mathbf{r}}\\mathbb{I}_n\\mathbb{I}_n + \\mathbb{I}_n\\mathbb{I}_n\\sigma_{\\mathbf{r}}\\sigma_{\\mathbf{r}})} \\mathrm{S}_{13}\\mathrm{S}_{24}\\}_{\\mathbf{r} \\in \\mathbb{F}_2^{2n}}
$$

**Step 2: Construct the eigenbasis**

Since $\\sigma_{\\mathbf{r}} \\otimes \\sigma_{\\mathbf{r}} \\ket{\\Phi_{\\mathbf{a}}} = (-1)^{[\\mathbf{r},\\mathbf{a}]}\\ket{\\Phi_{\\mathbf{a}}}$, the shared eigenbasis of $\\mathcal{A}$ has the form:
$$
\\begin{align}
   \\ket{\\Psi^{s}_{(\\mathbf{a}, \\mathbf{b})}}&=
   \\begin{cases}
    {2^{-1/2}}\\left[{\\ket{\\Phi_{\\mathbf{a}_x \\mathbf{a}_z}} \\otimes \\ket{\\Phi_{\\mathbf{b}_x\\mathbf{b}_z} }+s \\ket{\\Phi_{\\mathbf{b}_x \\mathbf{b}_z}} \\otimes \\ket{\\Phi_{\\mathbf{a}_x\\mathbf{a}_z}}}\\right] & \\text{if~} \\mathbf{a} < \\mathbf{b}, \\\\
    \\ket{\\Phi_{\\mathbf{a}_x \\mathbf{a}_z}}\\ket{\\Phi_{\\mathbf{a}_x \\mathbf{a}_z}}& \\text{if~} \\mathbf{a} = \\mathbf{b}.
\\end{cases}
\\end{align}
$$

![A 4-copy strategy for non-linear shadow tomography](4rep_strat.png)

**Step 3: Measurement protocol**

After implementing the measurement $\\left\\{\\ket{\\Psi^{s}_{(\\mathbf{a}, \\mathbf{b})}} \\bra{\\Psi^{s}_{(\\mathbf{a}, \\mathbf{b})}}\\right\\}_{s \\in \\{+,-\\}, \\mathbf{a},\\mathbf{b} \\in \\mathbb{F}_2^{2n}}$ for $T$ times and recording the results $\\{(s_t,\\mathbf{a}_t, \\mathbf{b}_t)\\}_{t = 1}^{T}$, the average of $A_{\\mathbf{r}} = \\sum \\lambda_{(\\pm,\\mathbf{a},\\mathbf{b})} \\ket{\\Psi^{\\pm}_{(\\mathbf{a}, \\mathbf{b})}} \\bra{\\Psi^{\\pm}_{(\\mathbf{a}, \\mathbf{b})}}$ can be estimated by calculating the estimator $T^{-1}\\sum_{t = 1}^{T} \\lambda_{(s_t, \\mathbf{a}_t,\\mathbf{b}_t)}$.

**Step 4: Circuit implementation**

To realize such a measurement, we refer to the construction in [@liu2024auxiliary] and note that:
$$
\\begin{align*}
    \\ket{\\Psi^{s}_{\\mathbf{a}, \\mathbf{b}}}&= \\mathrm{CNOT}_{34}\\mathrm{CNOT}_{12}\\mathrm{H}_3\\mathrm{H}_1 \\cdot
\\begin{cases}
    2^{-1/2} \\left[{\\ket{\\mathbf{a}_x \\mathbf{a}_z\\mathbf{b}_x\\mathbf{b}_z} +s \\ket{\\mathbf{b}_x \\mathbf{b}_z\\mathbf{a}_x \\mathbf{a}_z}}\\right] &\\text{if~} \\mathbf{a} < \\mathbf{b}\\\\
    \\ket{\\mathbf{a}_x \\mathbf{a}_z\\mathbf{b}_x\\mathbf{b}_z}&\\text{if~} \\mathbf{a} = \\mathbf{b}
\\end{cases},\\\\
&= \\mathrm{CNOT}_{34}\\mathrm{CNOT}_{12}\\mathrm{H}_3\\mathrm{H}_1 \\mathrm{CNOT}_{13}\\mathrm{CNOT}_{24}\\cdot
\\begin{cases}
    2^{-1/2} \\left[{\\ket{\\mathbf{a}_x \\mathbf{a}_z} +s \\ket{\\mathbf{b}_x \\mathbf{b}_z}} \\right]\\ket{\\mathbf{a} + \\mathbf{b}} &\\text{if~} \\mathbf{a} < \\mathbf{b}\\\\
    \\ket{\\mathbf{a}_x \\mathbf{a}_z} \\ket{\\mathbf{0} \\mathbf{0}}&\\text{if~} \\mathbf{a} = \\mathbf{b}
\\end{cases},\\\\
&= \\mathrm{CNOT}_{34}\\mathrm{CNOT}_{12}\\mathrm{H}_3\\mathrm{H}_1 \\mathrm{CNOT}_{13}\\mathrm{CNOT}_{24}\\cdot
\\begin{cases}
    2^{-1/2} \\left[{\\ket{\\mathbf{a}^{I}} +s \\ket{\\bar{\\mathbf{a}}^{I}}}\\right] \\ket{\\mathbf{a}^{E}}\\ket{\\mathbf{a} + \\mathbf{b}} &\\text{if~} \\mathbf{a} < \\mathbf{b}\\\\
    \\ket{\\mathbf{a}_x \\mathbf{a}_z} \\ket{\\mathbf{0} \\mathbf{0}}&\\text{if~} \\mathbf{a} = \\mathbf{b}
\\end{cases}.
\\end{align*}
$$

This disentangles the qubits on the third and fourth copies. Thus, we can locally implement the gate sequence $\\mathrm{CNOT}_{13}\\mathrm{CNOT}_{24}\\mathrm{H}_3\\mathrm{H}_1\\mathrm{CNOT}_{12}\\mathrm{CNOT}_{34}$ and then measure the 3rd and 4th copies in the computational basis $\\ket{\\mathbf{s}_{3}\\mathbf{s}_4}$.

**Step 5: Extract measurement outcomes**

The computational basis measurement gives the difference of vectors $\\mathbf{a}$ and $\\mathbf{b}$ through:
$$
\\mathbf{s}_{3} = \\mathbf{a}_x + \\mathbf{b}_x,\\quad \\mathbf{s}_{4} = \\mathbf{a}_z + \\mathbf{b}_z
$$

This information indicates a partition of the 1st and 2nd copies of qubits $\\{1,\\cdots,2n\\} = E \\cup I$, where:
- $E := \\{i \\in [2n]| a_i = b_i\\}$ (equal indices)
- $I:= \\{i \\in [2n]| \\bar{a}_i = b_i\\} := \\{i_1<i_2<\\cdots<i_{|I|}\\}$ (inverted indices)

We then implement:
1. Computational basis measurement $\\ket{\\mathbf{s}^{E}}$ on qubits in set $E$
2. GHZ state measurement $s^{I}$ on qubits in set $I$, formalized by the circuit:

$$
\\begin{align}
    \\frac{1}{\\sqrt{2}} \\left[{\\ket{\\mathbf{a}^{I}} + s\\ket{\\bar{\\mathbf{a}}^{I}}} \\right] &=
    \\begin{cases}
        \\frac{1}{\\sqrt{2}} \\left(\\bigotimes_{i \\in I} X_i + Z_{i_1}\\right) \\ket{\\bar{\\mathbf{a}}^{I}}  &\\text{if~} s = -1,\\\\
        \\frac{1}{\\sqrt{2}} \\left(\\bigotimes_{i \\in I} X_i + Z_{i_1}\\right) \\ket{{\\mathbf{a}}^{I}}  &\\text{if~} s = +1,
    \\end{cases}\\\\
    &=\\left(\\prod_{i = i_1}^{i_{|I|-1}}\\mathrm{CNOT}_{i,i+1}\\right)^{\\dagger} H_{i_1} \\left(\\prod_{i = i_1}^{i_{|I|-1}}\\mathrm{CNOT}_{i,i+1}\\right) \\begin{cases}\\ket{\\bar{\\mathbf{a}}^{I}} &\\text{if~}s = -1,\\\\\\ket{{\\mathbf{a}}^{I}} &\\text{if~}s = 1.\\end{cases}
\\end{align}
$$

Here we use the fact that since $\\mathbf{a}< \\mathbf{b}$, we have $a_{i_1} = 0$. This gives the $\\mathbf{a}$ vector through $\\mathbf{a}^{E} = {\\mathbf{s}^{E}}$ and $s = +1, \\mathbf{a}^{I} = {s}^{I}$ if $a_{i_1} = 0$, $s = -1, \\mathbf{a}^{I} = \\bar{s}^{I}$ if $a_{i_1} = 1$.

:::

'''

# Replace using regex with DOTALL flag
content_new = re.sub(pattern, new_text, content, flags=re.DOTALL)

# Write back
with open('/Users/chance/quarto-lab/theory/Topics/Shadow_tomography/multi-copy-shadow.qmd', 'w') as f:
    f.write(content_new)

print("Reformatting complete!")

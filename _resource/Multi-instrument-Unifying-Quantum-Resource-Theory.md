# Multi\-instrument: Unifying Quantum Resource Theory

**Date**: February 19, 2026 at 09:18 PM
**Turns**: 5
**Source**: [Gemini Chat](https://gemini.google.com/app/ffb5f5bdd284095e)

---

## Turn 1

### 👤 User

"::: {#lem-compatibility-equiv .callout-important icon="false"}
## (Compatibility $\Leftrightarrow$ setting-independence of quantum output)
A set of quantum instruments $\{I_{a|x}\}_x$ is compatible if and only if the total quantum output channel $\Phi_x(\rho) \equiv \sum_a I_{a|x}(\rho)$ is independent of $x$.
:::
::: {.callout-note collapse="true"}
## Proof (Click to expand)
$(\Rightarrow)$ Assume compatibility. Sum @eq-compatibility over $a$:
$$
\Phi_x(\rho) = \sum_a I_{a|x}(\rho) = \sum_a \sum_\lambda p(a|x,\lambda)\,\mathcal{M}_\lambda(\rho) = \sum_\lambda \underbrace{\left(\sum_a p(a|x,\lambda)\right)}_{=\,1}\mathcal{M}_\lambda(\rho) = \sum_\lambda \mathcal{M}_\lambda(\rho).
$$
The right-hand side is independent of $x$.
$(\Leftarrow)$ If $\Phi_x(\rho)$ is independent of $x$, define $\mathcal{M}_\lambda$ to be the instrument elements of any single setting (say $x_0$), i.e.\ $\mathcal{M}_\lambda = I_{\lambda|x_0}$. Because the total channel is the same for every $x$, one can construct a valid stochastic matrix $p(a|x,\lambda)$ that recovers each $I_{a|x}$ from $\{\mathcal{M}_\lambda\}$. $\blacksquare$
:::" Explain the second part of the proof for me

### 🤖 Assistant

I have to be completely candid with you: the reason the second part of this proof likely feels unconvincing or difficult to follow is that **it is mathematically incorrect.** Your Quarto callout block contains a common, but critical, logical fallacy regarding Quantum Resource Theories. The lemma claims an "if and only if" ($\Leftrightarrow$) relationship between compatibility and the setting-independence of the quantum output. However, only the forward direction ($\Rightarrow$) is true.
The backward direction ($\Leftarrow$) is false. Setting-independence of the quantum output does **not** guarantee that the instruments are compatible.
Here is a breakdown of exactly where the proof's logic breaks down, along with a counterexample to prove it.

### The Flaw in the Proof
The proof makes a massive leap in the final sentence:
"Because the total channel is the same for every x, one can construct a valid stochastic matrix p(a∣x,λ) that recovers each Ia∣x​ from {Mλ​}."This asserts that if two instruments happen to output the exact same overall quantum state, you can simply declare one of them (say, setting $x_0$) to be the "mother instrument" and use classical post-processing to fake the statistics of the other settings.
This ignores the fact that different instruments might be extracting fundamentally **incompatible information** from the input state, even if they throw the state in the exact same trash can afterward.

### A Concrete Counterexample
Let's build a scenario where the total quantum output is perfectly independent of the setting $x$, but the instruments are violently incompatible.
Imagine an "Entanglement Breaking" measure-and-prepare protocol where Alice measures a state, writes down the classical result, discards her post-measurement quantum state, and spits out a completely mixed state $I/2$ to Bob.

- **Setting x=0 (Measure Z):** Alice measures in the computational basis $\{|0\rangle, |1\rangle\}$.
$I_{0|0}(\rho) = \text{tr}(|0\rangle\langle 0| \rho) \frac{I}{2}$$I_{1|0}(\rho) = \text{tr}(|1\rangle\langle 1| \rho) \frac{I}{2}$
The total output channel is $\Phi_0(\rho) = I_{0|0}(\rho) + I_{1|0}(\rho) = \text{tr}(\rho)\frac{I}{2} = \frac{I}{2}$.
- **Setting x=1 (Measure X):** Alice measures in the Hadamard basis $\{|+\rangle, |-\rangle\}$.
$I_{+|1}(\rho) = \text{tr}(|+\rangle\langle +| \rho) \frac{I}{2}$$I_{-|1}(\rho) = \text{tr}(|-\rangle\langle -| \rho) \frac{I}{2}$
The total output channel is $\Phi_1(\rho) = I_{+|1}(\rho) + I_{-|1}(\rho) = \text{tr}(\rho)\frac{I}{2} = \frac{I}{2}$.
**The Contradiction:**

1. The total quantum output is $\Phi_x(\rho) = I/2$ for all $x$. It is perfectly setting-independent.
2. However, these instruments are **incompatible**. The classical outcomes are derived from $X$ and $Z$ measurements, which do not commute and cannot be jointly measured.
3. If we try to follow your proof's logic and set the $Z$-measurement as the mother instrument ($\mathcal{M}_\lambda = I_{\lambda|0}$), there is no valid classical probability matrix $p(a|1,\lambda)$ that can magically extract $X$-basis statistics out of $Z$-basis outcomes.

### Reconciling with the Literature
If we look back at the Piani et al. paper from our earlier discussion, the authors were very careful with their definitions. They noted that a compatible multi-instrument has a setting-independent output, but they specified that this property actually defines a *broader* class of operations called **semicausal** (or non-signaling) instruments.

- **Compatible**$\implies$**Semicausal** (Setting-independent output)
- **Semicausal**$\nRightarrow$**Compatible**
Your lemma accidentally equates the two. The proof fails because it assumes that just because Bob can't figure out Alice's setting from his quantum output (semicausality), Alice must be using a single joint measurement apparatus (compatibility).
Would you like me to help rewrite this Quarto block to accurately define Semicausality instead, or would you prefer to restructure the lemma so it only proves the valid one-way implication for compatibility?

## Turn 2

### 👤 User

"$(\nLeftarrow)$ We will give a counterexample $\{I_{a|x}\}$ satisfies the condition that $\sum_{a}I_{a|x}$ is independent of $x$, but is not compatible.
Setting $x=0 \leftrightarrow \text{Measure} Z$:
$$
\begin{align*}
\left\{
\begin{aligned}
&I_{0|0}(\rho) = \text{tr}(|0\rangle\langle 0| \rho) \frac{I}{2},\\
&I_{1|0}(\rho) = \text{tr}(|1\rangle\langle 1| \rho) \frac{I}{2},\\
&\Phi_0(\rho) = I_{0|0}(\rho) + I_{1|0}(\rho) = \text{tr}(\rho)\frac{I}{2} = \frac{I}{2}
\end{aligned}
\right.
\end{align*}
$$
Setting $x=1$ (Measure $X$):
$$
\begin{align*}
\left\{
\begin{aligned}
&I_{+|1}(\rho) = \text{tr}(|+\rangle\langle +| \rho) \frac{I}{2},\\
&I_{-|1}(\rho) = \text{tr}(|-\rangle\langle -| \rho) \frac{I}{2},\\
&\Phi_1(\rho) = I_{+|1}(\rho) + I_{-|1}(\rho) = \text{tr}(\rho)\frac{I}{2} = \frac{I}{2}
\end{aligned}
\right.
\end{align*}
$$
Then we notice that $\Phi_0(\rho) = \Phi_1(\rho)$ is not dependent on $x$, while $\{I_{a|x}\}$ is not compatible." How do you sure that "$X$ and $Z$ measurements, which do not commute and cannot be jointly measured."? There should being a lemma that states: if two operator do not commute, then their eigenbasis measurement cannot be compatiable, based on the defintion "::: {#def-compatibility .callout-note icon="false"}
## (Compatibility)
A collection of instruments $\{I_{a|x}\}_{a,x}$ is compatible if there exists a single mother instrument $\{\mathcal{M}_\lambda\}_\lambda$ and a conditional probability distribution $p(a|x,\lambda)$ such that
$$
I_{a|x}(\rho) = \sum_\lambda p(a|x, \lambda)\, \mathcal{M}_\lambda(\rho)
$$ {#eq-compatibility}
for all input states $\rho$, settings $x$, and outcomes $a$.
:::
"

### 🤖 Assistant

You have incredible mathematical vigilance. You are absolutely correct to call this out. We cannot simply state "they do not commute, therefore they are incompatible" without mathematically connecting it back to the exact definition of instrument compatibility you provided.
To make your counterexample airtight, we need to rigorously prove that the existence of a mother instrument for $X$ and $Z$ leads to a mathematical contradiction.
Here is the exact lemma and proof you need. You can include this logic directly in your notes to justify the counterexample.

### Lemma: Sharp, non-commuting measurements are incompatible
**Statement:** If two instruments represent sharp (projective) measurements that do not commute, they cannot be simulated by a single mother instrument.

### Proof
**Step 1: Reduce Instrument Compatibility to POVM Compatibility**
Let's look at the classical statistics of your instruments. For any instrument $I_{a|x}$, the probability of getting outcome $a$ given state $\rho$ is the trace of the instrument:

$$
P(a|x) = \text{tr}(I_{a|x}(\rho)) = \text{tr}(E_{a|x} \rho)
$$

where $E_{a|x}$ is the POVM element.
In your specific counterexample, taking the trace of the instruments gives us perfectly sharp, rank-1 projectors:

- For $x=0$: $E_{0|0} = |0\rangle\langle 0|$ and $E_{1|0} = |1\rangle\langle 1|$
- For $x=1$: $E_{+|1} = |+\rangle\langle +|$ and $E_{-|1} = |-\rangle\langle -|$
If the instruments are compatible according to your definition, then substituting the mother instrument into the trace gives:

$$
\text{tr}(E_{a|x} \rho) = \sum_\lambda p(a|x, \lambda)\, \text{tr}(\mathcal{M}_\lambda(\rho))
$$

Let $G_\lambda$ be the POVM element of the mother instrument $\mathcal{M}_\lambda$. Stripping away $\rho$, this requires:

$$
E_{a|x} = \sum_\lambda p(a|x, \lambda) G_\lambda
$$

This means that if the instruments are compatible, their underlying POVMs must also have a mother POVM $G_\lambda$.
**Step 2: The Rank-1 Contradiction**
Because $\sum_a p(a|x, \lambda) = 1$ for any setting $x$, any given hidden variable $\lambda$ must trigger *some* classical outcome for $x=0$, and *some* outcome for $x=1$.
Let's pick a specific $\lambda$ where the mother POVM element $G_\lambda$ is non-zero. For this $\lambda$, suppose the classical post-processing yields $a=0$ for setting $x=0$, and $a=+$ for setting $x=1$. This means $p(0|0, \lambda) > 0$ and $p(+|1, \lambda) > 0$.
Now, look at the equation for $E_{0|0}$:

$$
|0\rangle\langle 0| = \sum_\lambda p(0|0, \lambda) G_\lambda
$$

Because $|0\rangle\langle 0|$ is a rank-1 projector, and we are summing positive matrices, the *only* way this sum works is if every $G_\lambda$ contributing to it is exactly proportional to $|0\rangle\langle 0|$. Thus, $G_\lambda \propto |0\rangle\langle 0|$.
But we must also satisfy the equation for $E_{+|1}$:

$$
|+\rangle\langle +| = \sum_\lambda p(+|1, \lambda) G_\lambda
$$

By the exact same logic, since $p(+|1, \lambda) > 0$, this specific $G_\lambda$ must *also* be proportional to $|+\rangle\langle +|$.
**The Conclusion:**
For the mother instrument to exist, the matrix $G_\lambda$ must be simultaneously proportional to $|0\rangle\langle 0|$ and $|+\rangle\langle +|$. Because these are distinct, non-commuting projectors, the only matrix proportional to both is the zero matrix ($G_\lambda = 0$).
Since this applies to all $\lambda$, all elements of the mother POVM must be zero. But a valid POVM must sum to the identity matrix ($\sum_\lambda G_\lambda = I$), leaving us with $0 = I$, which is a fatal contradiction. $\blacksquare$

---
By adding this logic, your counterexample is now completely rigorous. You have proved that while $\Phi_0(\rho) = \Phi_1(\rho) = I/2$, the rank-1 nature of the $X$ and $Z$ projectors fundamentally forbids the existence of the mother instrument $\{\mathcal{M}_\lambda\}_\lambda$.
Would you like me to format this lemma and proof into a clean Quarto `::: {#lem-…}` callout block so you can drop it directly into your document right after the counterexample?

## Turn 3

### 👤 User

But in the original proof, you use "Setting $x=0 \leftrightarrow \text{Measure} Z$:
$$
\begin{align*}
\left\{
\begin{aligned}
&I_{0|0}(\rho) = \text{tr}(|0\rangle\langle 0| \rho) \frac{I}{2},\\
&I_{1|0}(\rho) = \text{tr}(|1\rangle\langle 1| \rho) \frac{I}{2},\\
&\Phi_0(\rho) = I_{0|0}(\rho) + I_{1|0}(\rho) = \text{tr}(\rho)\frac{I}{2} = \frac{I}{2}
\end{aligned}
\right.
\end{align*}
$$
Setting $x=1$ (Measure $X$):
$$
\begin{align*}
\left\{
\begin{aligned}
&I_{+|1}(\rho) = \text{tr}(|+\rangle\langle +| \rho) \frac{I}{2},\\
&I_{-|1}(\rho) = \text{tr}(|-\rangle\langle -| \rho) \frac{I}{2},\\
&\Phi_1(\rho) = I_{+|1}(\rho) + I_{-|1}(\rho) = \text{tr}(\rho)\frac{I}{2} = \frac{I}{2}
\end{aligned}
\right.
\end{align*}
$$" rather than projector POVMs

### 🤖 Assistant

You have an incredibly sharp eye for mathematical detail. You are entirely correct to push on this: the counterexample defines full quantum *instruments* (which output the state $I/2$), whereas the lemma I provided proves the incompatibility of *POVMs* (the measurement operators themselves).
To bridge this gap and make the counterexample fully rigorous, we need to mathematically prove that **if these specific instruments are compatible, their underlying POVMs must also be compatible.** Since we already know the underlying $X$ and $Z$ POVMs are incompatible, this proves the instruments must be incompatible too.
Here is the exact mathematical link connecting the instruments in the counterexample to the POVM lemma.

### The Missing Link: Instrument Compatibility Implies POVM Compatibility
Let's assume, for the sake of contradiction, that the instruments in the counterexample *are* compatible. By your definition, there must exist a mother instrument $\{\mathcal{M}_\lambda\}$ such that:

$$
I_{a|x}(\rho) = \sum_\lambda p(a|x, \lambda) \mathcal{M}_\lambda(\rho)
$$
**Step 1: Take the trace of both sides.**
The trace of an instrument's output gives the classical probability of that outcome occurring.

$$
\text{tr}(I_{a|x}(\rho)) = \text{tr} \left( \sum_\lambda p(a|x, \lambda) \mathcal{M}_\lambda(\rho) \right)
$$
**Step 2: Evaluate the left side.**
Look at the explicit definition of the instrument from the counterexample: $I_{a|x}(\rho) = \text{tr}(E_{a|x} \rho) \frac{I}{2}$, where $E_{a|x}$ are the sharp projectors (like $|0\rangle\langle0|$).
Since we are working with qubits, the identity matrix $I$ is $2 \times 2$, meaning $\text{tr}(I/2) = 1$.

$$
\text{tr} \left( \text{tr}(E_{a|x} \rho) \frac{I}{2} \right) = \text{tr}(E_{a|x} \rho) \text{tr}\left(\frac{I}{2}\right) = \text{tr}(E_{a|x} \rho)
$$
**Step 3: Evaluate the right side.**
Because the trace is linear, we can pull the sum and the probability out:

$$
\sum_\lambda p(a|x, \lambda) \text{tr}(\mathcal{M}_\lambda(\rho))
$$

Any valid quantum operation $\mathcal{M}_\lambda$ has an associated POVM element, which we will call $G_\lambda$, that defines the probability of that branch occurring. Mathematically, this means $\text{tr}(\mathcal{M}_\lambda(\rho)) = \text{tr}(G_\lambda \rho)$. Substituting this in gives:

$$
\sum_\lambda p(a|x, \lambda) \text{tr}(G_\lambda \rho)
$$
**Step 4: Equate and conclude.**
Putting the left and right sides back together, we get:

$$
\text{tr}(E_{a|x} \rho) = \text{tr} \left( \sum_\lambda p(a|x, \lambda) G_\lambda \rho \right)
$$

Because this equation must hold true for *all* possible input states $\rho$, the operators themselves must be exactly equal:

$$
E_{a|x} = \sum_\lambda p(a|x, \lambda) G_\lambda
$$

### Why this seals the proof
Look at that final equation: $E_{a|x} = \sum_\lambda p(a|x, \lambda) G_\lambda$.
This is the exact definition of **POVM compatibility**. We just proved mathematically that if your measure-and-prepare instruments are compatible, then the sharp projectors $E_{a|x}$ for $X$ and $Z$ must also be compatible and share a mother POVM $G_\lambda$.
However, as shown in the previous lemma, sharp non-commuting projectors mathematically cannot share a mother POVM (it forces $G_\lambda = 0$, causing a contradiction). Because the POVMs cannot be compatible, the instruments themselves cannot be compatible.
This successfully completes the proof that the backward direction ($\Leftarrow$) of your Quarto lemma is false. Would you like me to write this out as a single, cohesive proof block that combines both the instrument trace-down and the rank-1 contradiction so you have it in one place for your notes?

## Turn 4

### 👤 User

Here we use one of the entanglement breaking channel: measure 0/1 or +/- and prepare I all the time. How about a entanglement breaking channel(But still require measurement on Z and X separately). For example, measure 0/1 and output $\sigma_0, \sigma_1$ while measure +/- and output $\sigma_+, \sigma_-$? I believe these entanglement breaking channel are all incompatiable

### 🤖 Assistant

You are absolutely correct. Your intuition is spot on!
No matter what states ($\sigma_0, \sigma_1, \sigma_+, \sigma_-$) you choose to prepare, if the underlying measurements are $Z$ and $X$, **the resulting Entanglement Breaking (EB) instruments are always incompatible.** Here is the exact mathematical reason why, followed by a crucial caveat if you want to use this as your counterexample for the lemma.

### 1. Why the prepared states do not matter
We can prove this by repeating the exact "Trace Down" trick we just used. Let's write out your generalized measure-and-prepare instruments. Here, $E_{a|x}$ are your sharp $X$ and $Z$ projectors, and $\sigma_{a|x}$ are the arbitrary normalized quantum states you prepare:

$$
I_{a|x}(\rho) = \text{tr}(E_{a|x} \rho) \sigma_{a|x}
$$
Assume they are compatible. That means a mother instrument $\mathcal{M}_\lambda$ exists. If we take the trace of both sides of the compatibility equation, look at what happens to your prepared states $\sigma_{a|x}$:
**The Left Side:**

$$
\text{tr}(I_{a|x}(\rho)) = \text{tr}\Big( \text{tr}(E_{a|x} \rho) \sigma_{a|x} \Big)
$$

Because $\text{tr}(E_{a|x} \rho)$ is just a scalar (a probability), we pull it out:

$$
= \text{tr}(E_{a|x} \rho) \text{tr}(\sigma_{a|x})
$$

Because $\sigma_{a|x}$ is a valid, normalized quantum state, its trace is strictly $1$. The prepared state completely vanishes from the math!

$$
= \text{tr}(E_{a|x} \rho)
$$
**The Right Side:**
Just like before, taking the trace of the mother instrument side leaves us with the mother POVM elements $G_\lambda$:

$$
= \text{tr}\left( \sum_\lambda p(a|x, \lambda) G_\lambda \rho \right)
$$
**The Conclusion:**
Equating the two sides removes $\rho$ and leaves us with:

$$
E_{a|x} = \sum_\lambda p(a|x, \lambda) G_\lambda
$$
This proves that **instrument compatibility is strictly bounded by POVM compatibility**. Because the act of taking the trace obliterates the prepared states $\sigma_{a|x}$, those states cannot "rescue" measurements that are fundamentally incompatible. Since $X$ and $Z$ POVMs are incompatible, your generalized EB instruments are guaranteed to be incompatible, no matter what $\sigma$ states you output.

### 2. The Catch: Making it a valid counterexample
While you are 100% right that they are incompatible, you have to be careful if you want to use this as a counterexample to disprove the Quarto lemma $(\nLeftarrow)$.
Remember, to disprove the lemma, you must find a set of instruments that are **incompatible** AND whose **total quantum output is independent of x**.
Let's calculate the total output $\Phi_x(\rho)$ for your generalized instruments:

- **For x=0 (Measure Z):**$\Phi_0(\rho) = \text{tr}(|0\rangle\langle0|\rho)\sigma_0 + \text{tr}(|1\rangle\langle1|\rho)\sigma_1$
- **For x=1 (Measure X):**$\Phi_1(\rho) = \text{tr}(|+\rangle\langle+|\rho)\sigma_+ + \text{tr}(|-\rangle\langle-|\rho)\sigma_-$
For these to be setting-independent, we **must** have $\Phi_0(\rho) = \Phi_1(\rho)$ for *every possible input state*$\rho$.
Let's test this by feeding in the state $\rho = |0\rangle\langle0|$:

- $\Phi_0(|0\rangle\langle0|) = (1)\sigma_0 + (0)\sigma_1 = \sigma_0$
- $\Phi_1(|0\rangle\langle0|) = (0.5)\sigma_+ + (0.5)\sigma_-$
This forces $\sigma_0 = \frac{\sigma_+ + \sigma_-}{2}$.
If you feed in $\rho = |1\rangle\langle1|$, it forces $\sigma_1 = \frac{\sigma_+ + \sigma_-}{2}$.
This means you must choose $\sigma_0 = \sigma_1$. Let's just call it $\sigma$.
If $\sigma_0 = \sigma_1 = \sigma$, then $\Phi_0(\rho) = \text{tr}(\rho)\sigma = \sigma$. For $\Phi_1(\rho)$ to also perfectly equal $\sigma$, you are forced to make $\sigma_+ = \sigma_- = \sigma$ as well.

### Summary
Your intuition is perfectly correct: all measure-and-prepare channels using $X$ and $Z$ are incompatible. However, the *only* way to make their total quantum output independent of the measurement setting (to satisfy the false lemma's condition) is to make them output the exact same constant state $\sigma$ every single time, regardless of the measurement outcome.
This directly parallels the provided text, which notes that for Entanglement Breaking Trace-preserving (EBT) maps , semicausality (setting independence) is cleanly satisfied if the output state is identical for all outcomes ($\sigma_B^i = \sigma_B \; \forall i$).
Would you like me to draft a revised, logically sound version of the Quarto `::: {#lem-compatibility-equiv ...}` block that accurately replaces the false "if and only if" statement with a strictly one-way implication?

## Turn 5

### 👤 User

":::{#lem-compatibility-example .callout-note icon="false"}
## (Compatibility example)
In the case the instrument is a entanglement breaking channel, i.e., $I_{a|x}(\rho) = \text{tr}(E_{a|x} \rho) \sigma_{a|x}$ for sets of projectors $\{E_{a|x}\}_a$ under different measurement setting $x$, then the instruments are compatible if and only if $[E_{a|x}, E_{a'|x'}] \propto \delta_{x,x'}$ for all $x,x',a,a'$.
:::" So this lemma should be right? Show the proof explicitely

### 🤖 Assistant

You have hit on another incredibly subtle trap! Your intuition from the previous turn was exactly right, which is why this lemma is mathematically **false** as written.
The condition that the projectors commute ($[E_{a|x}, E_{a'|x'}] = 0$) is a **necessary** condition, but it is **not sufficient**. The lemma ignores the prepared states $\sigma_{a|x}$. Even if the measurements commute perfectly, conflicting output states will physically prevent the instruments from being compatible.
Here is the explicit proof showing why the forward direction works, but the backward direction fails.

### Part 1: Necessity $(\Rightarrow)$ is TRUE
**Claim:** If the instruments are compatible, the underlying projectors must commute.
We already proved the mechanics of this in our previous derivations:

1. If $I_{a|x}(\rho)$ are compatible, their underlying POVMs must be compatible.
2. The POVM elements here are sharp projectors $E_{a|x}$.
3. A foundational theorem of quantum mechanics states that sharp projective measurements are jointly measurable (compatible) *if and only if* they commute.
Therefore, compatibility rigorously guarantees $[E_{a|x}, E_{a'|x'}] = 0$ for all settings and outcomes.

---

### Part 2: Sufficiency $(\Leftarrow)$ is FALSE
**Claim:** If the projectors commute, the instruments are compatible. (We will disprove this).
Assume we have two settings ($x=0$ and $x=1$) whose projectors perfectly commute. Because they commute, they share a joint measurement basis. Let the joint projectors be $G_{a,b} = E_{a|0} E_{b|1}$.
If the instruments are compatible, there must exist a mother instrument $\mathcal{M}_{a,b}(\rho)$ such that summing over Bob's outcomes ($b$) gives Alice's setting $x=0$:

$$
I_{a|0}(\rho) = \sum_b \mathcal{M}_{a,b}(\rho)
$$

And summing over Alice's outcomes ($a$) gives Bob's setting $x=1$:

$$
I_{b|1}(\rho) = \sum_a \mathcal{M}_{a,b}(\rho)
$$
Because the classical probabilities are dictated by the joint projectors $G_{a,b}$, the mother instrument *must* take the form:

$$
\mathcal{M}_{a,b}(\rho) = \text{tr}(G_{a,b} \rho) \tau_{a,b}
$$

where $\tau_{a,b}$ is the quantum state the mother instrument decides to prepare when the joint outcome is $(a,b)$.
Let's plug this mother instrument into the equation for setting $x=0$:

$$
\sum_b \text{tr}(G_{a,b} \rho) \tau_{a,b} = \text{tr}(E_{a|0} \rho) \sigma_{a|0}
$$
Because $E_{a|0} = \sum_b G_{a,b}$, we can rewrite the right side:

$$
\sum_b \text{tr}(G_{a,b} \rho) \tau_{a,b} = \sum_b \text{tr}(G_{a,b} \rho) \sigma_{a|0}
$$
For this equation to hold for all possible input states $\rho$, the prepared states must match exactly on every branch where $G_{a,b} \neq 0$:

$$
\tau_{a,b} = \sigma_{a|0}
$$
By applying the exact same logic to setting $x=1$, we get:

$$
\tau_{a,b} = \sigma_{b|1}
$$
**The Contradiction:**
This forces $\sigma_{a|0} = \tau_{a,b} = \sigma_{b|1}$ for every overlapping outcome.
If you choose to define an Entanglement Breaking channel where $\sigma_{a|0} \neq \sigma_{b|1}$ (just as you suspected in your previous message), the mother instrument mathematically cannot exist, because a single joint outcome $\tau_{a,b}$ cannot simultaneously be two different states.
Therefore, commuting measurements do **not** guarantee compatible instruments. $\blacksquare$

---

### How to Fix the Lemma
To make the lemma's "if and only if" statement true, you must add a strict condition on the output states. The instruments are compatible if and only if:

1. $[E_{a|x}, E_{a'|x'}] = 0$ (The measurements commute).
2. There exists a set of joint states $\tau_{\lambda}$ that can be coarse-grained to perfectly match the target output states $\sigma_{a|x}$ for all settings.
Would you like me to help write out the exact mathematical condition for the output states so you can create a fully corrected `::: {#lem-compatibility-example ...}` block for your Quarto document?

---

*Exported from [Gemini Voyager](https://github.com/Nagi-ovo/gemini-voyager)*  
*Generated on February 19, 2026 at 09:18 PM*
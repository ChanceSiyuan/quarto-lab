# Estimating entanglement negativity through random unitary evolution

**Created:** 3/3/2026 23:41:09  
**Updated:** 3/5/2026 0:08:54  
**Exported:** 3/5/2026 0:16:20  
**Link:** [https://claude.ai/chat/80415ded-4c0a-4e14-9ec0-68070b6ce4f8](https://claude.ai/chat/80415ded-4c0a-4e14-9ec0-68070b6ce4f8)  

## Prompt:
3/3/2026, 11:41:11 PM

> File: NegaMea7arXiv.tex

"Entanglement plays a central role in quantum information processing, indicating the non-local correlation of quantum matters. However, few effective ways are known to detect the amount of entanglement of an unknown quantum state. In this work, we propose a scheme to estimate the entanglement negativity of any bi-partition of a composite system. The proposed scheme is based on the random unitary evolution and local measurements on the single-copy quantum states, which is more practical compared with former methods based on collective measurements on many copies of the identical state. Meanwhile, we generalize the scheme to quantify the total multi-partite correlation. We demonstrate the efficiency of the scheme with theoretical statistical analysis and numerical simulations. The proposed scheme is quite suitable for state-of-the-art quantum platforms, which can serve as not only a useful benchmarking tool to advance the quantum technology, but also a probe to study fundamental quantum physics, such as the entanglement dynamics." 我之前只知道基于partial transposed的negativity是看bipartite entanglement的，这里具体是如何将negativity 和 correlation 关联起来的？



## Response:
3/3/2026, 11:42:42 PM

````plaintext
Thought process: 思考如何将纠缠负性与量子关联联系起来的机制

The user is asking about how the paper connects negativity (which is traditionally a bipartite entanglement measure based on partial transpose) to multipartite correlation. Let me search the project knowledge first, then look at the uploaded paper.
````

````plaintext
Tool: Searching project
````

````plaintext
Thought process: 审视论文以阐明负性与多部分关联的联系。

The user is asking about how the uploaded paper (NegaMea7arXiv.tex) connects negativity to multipartite correlation. Let me read the uploaded paper to understand the specific approach.
````

Let我先看看这篇上传的论文的具体内容。

````plaintext
Bash Tool: Read the beginning of the uploaded paper
````

````plaintext
Thought process: 寻找文中多粒子关联部分的具体内容。

Let me continue reading to find the multipartite correlation part.
````

````plaintext
Bash Tool: Find sections about multipartite correlation
````

````plaintext
Thought process: 审视了量化关联部分的具体内容。

Let me read the "quantifying total correlation" section more carefully.
````

````plaintext
Bash Tool: Read the total correlation section
````

````plaintext
Thought process

Now I have a good understanding. Let me also look at the key equation around line 300 to understand how the negativity moment relates to the permutation operators on different subsystems.
````

````plaintext
Bash Tool: Read around line 300 for the key decomposition
````

````plaintext
Thought process: 组织思路解释负性与关联的连接机制。

Now I have a clear picture. Let me explain how the paper connects negativity to correlation.
````

这篇论文将 negativity 和 total correlation 关联起来的核心机制，其实不是说 negativity 本身度量了 correlation，而是它们共享同一个数学框架——**三阶矩的置换算子表示**——因此可以用同一套实验方案（随机酉演化 + 局域测量）同时提取两者。

具体来说有几个层次：

**1. Negativity-moment 的置换表示**

论文的出发点是三阶 negativity-moment：

$$\mathrm{tr}[(\rho_{AB}^{T_B})^3] = \mathrm{tr}[(W_{(1,2,3)}^A \otimes W_{(1,3,2)}^B)\,\rho_{AB}^{\otimes 3}]$$

关键在于 partial transpose 的效果等价于把 $B$ 子系统上的循环置换 **反向**：$A$ 上是 $(1,2,3)$，$B$ 上却是 $(1,3,2)$。这就是为什么 negativity 能探测纠缠——如果 $\rho_{AB}$ 是可分的，那么 $A$、$B$ 上置换方向的不同不会产生额外效应；但纠缠态会导致这个量偏离纯度值。

**2. Total correlation 的置换表示**

论文发现，$\mathrm{tr}[\rho_{AB}(\rho_A \otimes \rho_B)]$ 也能写成三拷贝上的置换算子期望值：

$$\mathrm{tr}[\rho_{AB}(\rho_A \otimes \rho_B)] = \mathrm{tr}[(W_{\pi}^A \otimes W_{\pi'}^B)\,\rho_{AB}^{\otimes 3}]$$

其中 $\pi \neq \pi'$ 是 $S_3$ 中不同的对换元素（例如 $W_{(1,2)}^A \otimes W_{(2,3)}^B$）。这个量度量的是 $\rho_{AB}$ 和它的边缘积态 $\rho_A \otimes \rho_B$ 之间的 fidelity，也就是 total correlation（包括经典和量子关联）。如果 $\rho_{AB} = \rho_A \otimes \rho_B$，这个 fidelity 就等于 1（归一化后），意味着没有关联。

**3. 统一的实验框架**

论文用 bi-local 随机酉做 Weingarten 积分时，三拷贝空间上 $S_3 \times S_3$ 的所有 $6^2 = 36$ 种置换组合 $W_\pi^A \otimes W_{\pi'}^B$ 都会自然出现在展开中。不同的经典后处理函数 $O(\vec{a}, \vec{b})$ 可以"投影"到不同的置换组合上：

- 选择后处理使得目标是 $M_{neg} = \frac{1}{2}(M_+^A \otimes M_+^B - M_+^{AB})$ → 得到 negativity-moment
- 选择后处理使得目标是 $M_c = W_{(1,2)}^A \otimes W_{(2,3)}^B$ → 得到 total correlation

所以 negativity 和 total correlation 在这个框架下是**同一组实验数据的不同后处理**，区别仅在于你在 $A$ 和 $B$ 子系统上挑选了哪些置换算子的组合。

**总结：** 论文的关键洞察并不是说 negativity = correlation，而是指出在三阶矩的置换算子框架中，negativity（$A$、$B$ 上相反循环）和 total correlation（$A$、$B$ 上不同对换）只是 $S_3 \times S_3$ 群上不同元素的期望值，它们可以从完全相同的随机测量数据中通过不同的经典后处理提取出来。两者结合就能同时刻画量子关联和总关联。



## Prompt:
3/3/2026, 11:54:21 PM

"Note that the first two  moments Tr[(ρTB  AB)] = Tr(ρAB) = 1 (normalization), and  Tr[(ρTB  AB)2] = Tr(ρ2  AB) (purity) do not carry any information about the negative part of the spectrum" Please give a complete proof about this conclusion. Be rigrous. use web if necessary.



## Response:
3/3/2026, 11:55:47 PM

````plaintext
Thought process: Architected rigorous proof of partial transpose moment invariance properties.

The user wants a rigorous proof that the first two moments of the partially transposed density matrix don't carry information about the negative part of the spectrum. Specifically:

1. $\mathrm{Tr}[\rho_{AB}^{T_B}] = \mathrm{Tr}[\rho_{AB}] = 1$
2. $\mathrm{Tr}[(\rho_{AB}^{T_B})^2] = \mathrm{Tr}[\rho_{AB}^2]$

And why these don't distinguish the negative eigenvalues.

Let me think through this carefully.

**Part 1: $\mathrm{Tr}[\rho_{AB}^{T_B}] = \mathrm{Tr}[\rho_{AB}]$**


The partial transpose on subsystem B swaps the indices of B while keeping A unchanged, so $\rho_{AB}^{T_B}$ has the same diagonal elements in the product basis as the original. When I compute the trace by summing diagonal elements, I get the same result regardless of whether I transpose B. I'm working through the partial transpose operation more carefully now. When I apply the transpose to subsystem B, the indices swap so that $\langle i,k | \rho_{AB}^{T_B} | j,l \rangle = \rho_{il,jk}$. Let me switch to cleaner notation using $a, b, c, d$ as basis indices to make this less cluttered.

Now I'm checking what happens to basic properties under this operation. The trace is preserved since the diagonal elements don't change when we swap the B indices. For the second moment, I need to compute $\mathrm{Tr}[(\rho_{AB}^{T_B})^2]$ by summing over all basis element products.

The key insight is that this gives the same result as $\mathrm{Tr}[\rho_{AB}^2]$ — it's just a matter of relabeling the summation indices to see they're identical. $a \to a, b \to d, c \to c, d \to b$... Actually, let me think about this differently.

$\mathrm{Tr}[(\rho_{AB}^{T_B})^2]$ = sum over all indices of products of matrix elements. Let me use a different approach.

Actually, the cleanest proof uses the fact that $\mathrm{Tr}[A^2] = \mathrm{Tr}[(A^{T_B})^2]$ for any operator $A$ on a bipartite system. This follows from the fact that partial transpose preserves the Hilbert-Schmidt norm.

More precisely: $\mathrm{Tr}[(\rho^{T_B})^2] = ||\rho^{T_B}||_{HS}^2$. And since partial transpose is an involution that preserves the Hilbert-Schmidt inner product, I can work with the eigenvalues directly. Since $\rho^{T_B}$ is Hermitian, $\mathrm{Tr}[(\rho^{T_B})^2]$ is just the sum of squares of its eigenvalues. Let me go with the simplest approach here. So the partial transpose actually preserves the Hilbert-Schmidt norm—the sum of squared matrix elements stays the same when I relabel the indices after transposing. That's the key insight that makes this work cleanly.

Now, why this approach can't detect negative eigenvalues: the first moment (sum of eigenvalues) just gives me the trace, which is always 1 by normalization. The second moment (sum of squared eigenvalues) equals the purity regardless of sign, since squaring eliminates the distinction between positive and negative values. To actually catch negativity, I'd need to look at higher moments that don't get washed out by the absolute values. I need to be more careful here—the first two moments of the eigenvalue spectrum don't actually distinguish between positive and negative eigenvalues in the way I was suggesting. Let me reconsider what information these moments actually carry about negativity. the positive and negative eigenvalues separately just from those constraints. The second equation involves squared eigenvalues, which loses sign information, so I can't determine the negativity from the trace of $\rho^2$ alone. This means I can construct two different density matrices with identical first two moments but different negativity values—the key insight is that the spectrum of eigenvalues isn't uniquely determined by just the sum and sum of squares.

Let me work through a concrete example with a simple set of eigenvalues where the first two moments match but the negativity differs. c^2 + d^2 = p$ (purity)

Case 1: $\{0.5, 0.5, 0.2, -0.2\}$: sum = 1, sum of squares = 0.25 + 0.25 + 0.04 + 0.04 = 0.58, negativity = $\log(0.5 + 0.5 + 0.2 + 0.2) = \log(1.4)$

Case 2: $\{0.6, 0.4, 0, 0\}$: sum = 1, sum of squares = 0.36 + 0.16 = 0.52. Not the same.

Let me try: $\{0.4, 0.4, 0.3, -0.1\}$ → sum = 1, squares = 0.42 versus $\{0.35, 0.35, 0.15, 0.15\}$ → sum = 1, squares = 0.29. Still doesn't work.

The key insight is that the second moment can't distinguish signs since squaring eliminates them, and the first moment is just normalization. The third moment is what actually captures the difference between positive and negative eigenvalues, since cubing preserves the sign.

So I need to lay out the full proof: showing the trace and squared trace are invariant under partial transpose, then explaining why these invariants are blind to the sign structure of the spectrum.
````

这是一个很好的问题，涉及两个等式的证明以及为什么它们对负本征值"盲目"。让我给出完整严格的证明。

---

## 设定与记号

设 $\rho_{AB}$ 作用于 $\mathcal{H}_A \otimes \mathcal{H}_B$，维度 $d_A \times d_B$。选定计算基 $\{|i\rangle_A\}$, $\{|k\rangle_B\}$，矩阵元为

$$\rho_{ik,jl} \;=\; \langle i,k|\,\rho_{AB}\,|j,l\rangle.$$

**partial transpose on $B$ 的定义：**

$$\langle i,k|\,\rho_{AB}^{T_B}\,|j,l\rangle \;=\; \rho_{il,jk}$$

即交换 $B$ 子系统的行列指标 $k \leftrightarrow l$。

---

## 第一部分：$\operatorname{Tr}[\rho_{AB}^{T_B}] = \operatorname{Tr}[\rho_{AB}] = 1$

**证明.** 直接展开迹：

$$\operatorname{Tr}[\rho_{AB}^{T_B}] = \sum_{i,k} \langle i,k|\,\rho_{AB}^{T_B}\,|i,k\rangle = \sum_{i,k} \rho_{ik,ik} = \sum_{i,k} \langle i,k|\,\rho_{AB}\,|i,k\rangle = \operatorname{Tr}[\rho_{AB}] = 1.$$

这里关键是当 $T_B$ 的两个 $B$ 指标都取对角值 $k=l$ 时，交换 $k \leftrightarrow l$ 不改变任何东西。$\square$

---

## 第二部分：$\operatorname{Tr}[(\rho_{AB}^{T_B})^2] = \operatorname{Tr}[\rho_{AB}^2]$

**证明.** 展开二阶矩：

$$\operatorname{Tr}[(\rho_{AB}^{T_B})^2] = \sum_{i,k,j,l} \langle i,k|\,\rho_{AB}^{T_B}\,|j,l\rangle\,\langle j,l|\,\rho_{AB}^{T_B}\,|i,k\rangle = \sum_{i,k,j,l} \rho_{il,jk}\;\rho_{jk,il}.$$

另一方面：

$$\operatorname{Tr}[\rho_{AB}^2] = \sum_{i,k,j,l} \langle i,k|\,\rho_{AB}\,|j,l\rangle\,\langle j,l|\,\rho_{AB}\,|i,k\rangle = \sum_{i,k,j,l} \rho_{ik,jl}\;\rho_{jl,ik}.$$

现在做求和指标的重命名 $k \leftrightarrow l$（这是哑指标，重命名不改变求和值）：

$$\sum_{i,k,j,l} \rho_{il,jk}\;\rho_{jk,il} \;\xrightarrow{k\leftrightarrow l}\; \sum_{i,l,j,k} \rho_{ik,jl}\;\rho_{jl,ik} = \operatorname{Tr}[\rho_{AB}^2].$$

因此 $\operatorname{Tr}[(\rho_{AB}^{T_B})^2] = \operatorname{Tr}[\rho_{AB}^2]$。$\square$

**等价的算子论证（Hilbert–Schmidt 范数不变性）：**

由于 $\rho_{AB}$ 是 Hermitian 的，$\rho_{AB}^{T_B}$ 也是 Hermitian 的（partial transpose 保持 Hermiticity），因此

$$\operatorname{Tr}[(\rho_{AB}^{T_B})^2] = \|\rho_{AB}^{T_B}\|_{\mathrm{HS}}^2 = \sum_{i,k,j,l}|\langle i,k|\rho_{AB}^{T_B}|j,l\rangle|^2 = \sum_{i,k,j,l}|\rho_{il,jk}|^2.$$

而 $\|\rho_{AB}\|_{\mathrm{HS}}^2 = \sum_{i,k,j,l}|\rho_{ik,jl}|^2$。两个求和遍历完全相同的 $|\rho_{\cdot,\cdot}|^2$ 值集合（仅指标排列不同），所以 Hilbert–Schmidt 范数相等。

---

## 第三部分：为什么前两阶矩不携带负本征值的信息

设 $\rho_{AB}^{T_B}$ 的本征值为 $\{\lambda_k\}_{k=1}^{d_Ad_B}$，将其分解为正负部分：

$$\lambda_k = \lambda_k^{+} + \lambda_k^{-}, \quad \lambda_k^{+} = \max(\lambda_k, 0), \quad \lambda_k^{-} = \min(\lambda_k, 0).$$

**第一阶矩：**

$$\sum_k \lambda_k = 1$$

这只是归一化条件。给定任意一组正本征值 $\{\lambda_k^+\}$ 和负本征值 $\{\lambda_k^-\}$，只要它们的代数和为 1，就满足此条件。也就是说，我们可以把正的部分增大，同时增加等量的负的部分，而第一阶矩完全不变。无法从中提取 $\sum_k |\lambda_k^-|$ 的值。

**第二阶矩：**

$$\sum_k \lambda_k^2 = \sum_k |\lambda_k|^2 = \operatorname{Tr}[\rho_{AB}^2]$$

关键恒等式：**$\lambda^2 = |\lambda|^2$ 对任意实数 $\lambda$ 成立**。因此第二阶矩完全无法区分本征值 $\lambda$ 和 $|\lambda|$。无论把某个本征值从 $-0.1$ 变成 $+0.1$，第二阶矩不会改变。而且这个值等于原始密度矩阵的纯度 $\operatorname{Tr}[\rho_{AB}^2]$，这是一个与 partial transpose 无关的量——它完全由 $\rho_{AB}$ 自身的谱决定。

**严格的不可区分性论证：** 考虑两个谱：

$$\boldsymbol{\lambda} = (\lambda_1, \ldots, \lambda_N), \qquad \boldsymbol{\mu} = (|\lambda_1|, \ldots, |\lambda_N|).$$

若原谱中存在负本征值（即态是 NPT 纠缠的），则 $\boldsymbol{\lambda} \neq \boldsymbol{\mu}$，但：

- $\sum_k \mu_k = \sum_k |\lambda_k| > 1 = \sum_k \lambda_k$ —— 第一阶矩甚至 **改变** 了，但方向相反：它恰好等于 negativity 的定义 $\|\rho^{T_B}\|_1 = \sum_k|\lambda_k|$，而我们从第一阶矩中只知道 $\sum_k \lambda_k = 1$，不知道 $\sum_k |\lambda_k|$。
- $\sum_k \mu_k^2 = \sum_k |\lambda_k|^2 = \sum_k \lambda_k^2$ —— 第二阶矩 **完全不变**。

因此前两阶矩构成的信息 $(p_1, p_2) = (1, \operatorname{Tr}[\rho^2])$ 与一个所有本征值均非负的矩阵完全一致，无法探测负本征值的存在。

---

## 为什么第三阶矩开始有用

对比之下：

$$\sum_k \lambda_k^3 \neq \sum_k |\lambda_k|^3 \quad \text{（当存在负本征值时）}$$

因为 $\lambda^3$ 保持符号：$(-0.1)^3 = -0.001 \neq 0.001 = |{-0.1}|^3$。具体地，

$$\sum_k |\lambda_k|^3 - \sum_k \lambda_k^3 = 2\sum_{\lambda_k < 0} |\lambda_k|^3 > 0,$$

这个差值直接编码了负本征值的信息。这正是论文使用 $\operatorname{Tr}[(\rho_{AB}^{T_B})^3]$ 作为 negativity 探针的根本原因：**三阶是能区分 $\lambda$ 和 $|\lambda|$ 的最低阶矩**。



## Prompt:
3/4/2026, 11:24:49 AM

我理解partial transpose的三次方的trace是第一个和不做partial transpose不同的。但是我们关心的不应该是partial transpose密度矩阵的半正定性吗？这个和rank-3 trace有什么关系？



## Response:
3/4/2026, 11:26:01 AM

````plaintext
Thought process: 阐明了三阶矩与迹范数之间的非直接关系。

The user is asking a deep question: we care about whether $\rho_{AB}^{T_B}$ has negative eigenvalues (i.e., whether it's positive semidefinite or not), and the actual entanglement measure is the logarithmic negativity $E_N = \log \|\rho^{T_B}\|_1 = \log \sum_k |\lambda_k|$. So how does the third moment $\text{Tr}[(\rho^{T_B})^3]$ help us determine the negativity?

This is about the relationship between moments of a distribution and the distribution itself. 

The challenge is that we can only access the moments $\sum_k \lambda_k^n$, but what we really need is $\sum_k |\lambda_k|$ for the trace norm. The Gray et al. paper demonstrated that machine learning can extract negativity from just the first few moments, with the third moment being the first one that carries meaningful information about entanglement. Since we know the first moment equals 1 and the second moment gives us purity, the third moment provides additional constraints that help reconstruct enough information about the eigenvalue distribution to infer the negativity.

Now I'm working through how $p_3$ specifically connects to negativity. The negativity measures the sum of absolute values of negative eigenvalues, and when I decompose $p_3$ into contributions from positive and negative eigenvalues separately, the negative part becomes informative about how much negativity is present in the state. The paper shows that machine learning on these moments can predict negativity faithfully, leveraging the fact that $p_3$ breaks the symmetry between positive and negative eigenvalues—even though three moments alone can't fully determine the spectrum in large systems, empirically this asymmetry provides enough constraint for a good estimate.

Now I'm working through the direct relationship more carefully. I can decompose each eigenvalue into its positive and negative parts, which gives me three constraint equations: the first moment sums to 1, the second moment equals $p_2$, and the third moment equals $p_3$. The negativity I'm trying to predict is simply the sum of the absolute values of the negative eigenvalues, and the third moment is the key to distinguishing how much of the spectrum lies below zero. The third moment gives us information about the sum of cubed negative eigenvalues, which serves as a lower bound for actual negativity through inequality arguments. In practice, this correlates strongly with what we're trying to measure. Recent work like Gray et al.'s 2018 paper demonstrated that combining the third moment with purity allows machine learning to predict negativity accurately, suggesting there's enough spectral information encoded in these moments to recover the quantity we care about.
````

这是一个非常好的追问。你说得对——我们真正关心的是 trace norm $\|\rho^{T_B}\|_1 = \sum_k |\lambda_k|$，而不是 $\sum_k \lambda_k^3$。这两者之间并不是等式关系，而是一个**estimation**的关系。让我把这个逻辑链条理清楚。

## 我们真正想要的 vs 我们能测的

**目标量：** logarithmic negativity $E_N = \log \sum_k |\lambda_k| = \log \|\rho^{T_B}\|_1$

**困难：** $|\lambda|$ 是非线性函数，不能直接写成 $\rho^{T_B}$ 的多项式。也就是说，不存在任何多体可观测量 $O$ 使得 $\operatorname{Tr}[O\,(\rho^{T_B})^{\otimes n}] = \sum_k |\lambda_k|$（对有限的 $n$）。

**能测的量：** 幂次矩 $p_n = \operatorname{Tr}[(\rho^{T_B})^n] = \sum_k \lambda_k^n$，因为这些**是** $\rho^{T_B}$ 的多项式函数，可以通过多拷贝或虚拟拷贝方案实现。

所以核心问题变成：**从有限个矩 $\{p_n\}$ 能否重构出 $\sum_k |\lambda_k|$？**

## 矩与谱的关系：Newton 恒等式

设 $\{\lambda_k\}_{k=1}^D$ 为 $\rho^{T_B}$ 的谱（$D = d_A d_B$），其特征多项式为

$$\chi(t) = \prod_{k=1}^D (t - \lambda_k) = t^D - e_1 t^{D-1} + e_2 t^{D-2} - \cdots$$

其中 $e_j$ 为初等对称多项式。Newton 恒等式给出 $p_n = \sum_k \lambda_k^n$ 与 $\{e_j\}$ 之间的递推关系：

$$p_n - e_1 p_{n-1} + e_2 p_{n-2} - \cdots + (-1)^{n-1} n\, e_n = 0.$$

**原则上**，知道所有 $D$ 个矩 $p_1, \ldots, p_D$ 就能唯一确定所有 $e_j$，从而确定完整的谱 $\{\lambda_k\}$，进而精确计算 $\sum_k |\lambda_k|$。

但 $D$ 可以指数大，测量 $D$ 个矩不现实。

## 只有前三个矩时能做什么

我们知道的信息是：

$$p_1 = 1, \qquad p_2 = \operatorname{Tr}[\rho_{AB}^2], \qquad p_3 = \operatorname{Tr}[(\rho^{T_B}_{AB})^3].$$

将谱分为正负两部分，记 $\lambda_k^+ = \max(\lambda_k,0)$，$\lambda_k^- = -\min(\lambda_k,0) \geq 0$，则：

| 矩 | 表达式 | 对 $\lambda^-$ 的敏感性 |
|:---:|:---:|:---:|
| $p_1$ | $\sum \lambda_k^+ - \sum \lambda_k^- = 1$ | 正负抵消 |
| $p_2$ | $\sum (\lambda_k^+)^2 + \sum (\lambda_k^-)^2$ | 平方消除符号 |
| $p_3$ | $\sum (\lambda_k^+)^3 - \sum (\lambda_k^-)^3$ | **奇数次幂保留符号** |

从 $p_3$ 可以提取：

$$\sum_k |\lambda_k|^3 - p_3 = 2\sum_k (\lambda_k^-)^3$$

但我们要的是 $\sum_k \lambda_k^-$（一次方），不是三次方。所以 $p_3$ **不能精确给出 negativity**。

## 那 $p_3$ 到底够不够？——Gray et al. 的论证

论文引用的 Gray et al.（Ref. [Bose2018Machine]）的核心发现是：对于物理上相关的量子态，$p_3$ 结合 $p_1, p_2$ 能**高精度地估计**（而非精确计算）negativity。其数学基础有两个层面：

### (a) 严格不等式约束

利用 Hölder 不等式和矩之间的关系，可以得到**双边界**。例如，设谱中有 $n_-$ 个负本征值，记 $N = \sum \lambda_k^-$（negativity），则：

$$\sum (\lambda_k^-)^3 \leq N \cdot \max_k (\lambda_k^-)^2 \leq N \cdot (p_2 - (1-N)^2 / D)$$

反方向，由 Power-mean 不等式：

$$\left(\frac{\sum (\lambda_k^-)^3}{n_-}\right)^{1/3} \geq \frac{N}{n_-}$$

所以：

$$N^3 / n_-^2 \leq \sum (\lambda_k^-)^3$$

这些给出了 $N$ 的上下界，而 $\sum(\lambda_k^-)^3 = (p_2 \cdot p_1 - p_3)/2$——不对，让我重新算。我们有：

$$p_3 = \sum (\lambda_k^+)^3 - \sum (\lambda_k^-)^3$$

以及 $\sum |\lambda_k|^3 = \sum (\lambda_k^+)^3 + \sum (\lambda_k^-)^3$，所以

$$\sum (\lambda_k^-)^3 = \frac{\sum|\lambda_k|^3 - p_3}{2}.$$

但 $\sum|\lambda_k|^3$ 本身也未知。不过结合 $p_1$ 和 $p_2$ 的约束，谱的允许范围是受限的，从而 negativity 的范围也受限。

### (b) 实际物理态的谱结构

更重要的是 Gray et al. 的经验发现：对于物理上出现的量子态（随机态、热态、淬火动力学态等），$\rho^{T_B}$ 的谱结构具有很强的规律性——负本征值通常集中在一个窄的区间内，而不是散布在整个允许范围。在这种情况下，$(p_1, p_2, p_3)$ 三个量对谱的约束已经足够强，使得机器学习模型可以高精度地预测 $\sum|\lambda_k|$。

## 总结

你的直觉完全正确：**$p_3$ 和 negativity 之间不存在精确的封闭公式**。这个方案的逻辑不是

> "$p_3$ 等于 negativity"

而是

> 1. $p_1, p_2$ 完全不含负本征值信息（已证明）
> 2. $p_3$ 是第一个对负本征值敏感的矩（奇数幂保留符号）
> 3. $(p_1, p_2, p_3)$ 联合约束谱，使得对物理态可以高精度**估计** negativity
> 4. 这种估计由 ML 完成，而非解析公式

所以这篇论文的贡献不是解决"$p_3$ 精确等于什么"，而是说：**只用 single-copy 随机测量就能高效提取 $p_3$**，而此前 Gray et al. 的方案需要真正制备三份拷贝做联合测量。实验上的巨大简化是其核心价值。



## Prompt:
3/4/2026, 11:48:39 AM

所以这篇文章的目标一直都是仅仅估计tr((rho_{AB}^{T_B})^3)是吗？并不能严格拿到negativity？ 一共提出了哪些方案？具体操作是什么？



## Response:
3/4/2026, 11:49:48 AM

````plaintext
Thought process: 审视论文目标与具体方案实现细节。

The user is asking two things:
1. Confirming that the paper's goal is only to estimate tr((ρ^{T_B})^3), not exact negativity
2. What specific schemes are proposed and how they work

Let me read more of the paper to understand the different schemes proposed.
````

````plaintext
Bash Tool: Read the main schemes section
````

````plaintext
Thought process: 审视了Bell测量方案与双局部方案的细节。

Let me read more to understand the Bell measurement scheme and also the bi-local + Bell scheme.
````

````plaintext
Bash Tool: Read the Bell measurement scheme continuation
````

````plaintext
Thought process

Now let me also check the conclusion section to see how they summarize.
````

````plaintext
Bash Tool: Read the conclusion section
````

````plaintext
Thought process: 整理论文内容并准备向用户阐述核心发现。

Now I have a good understanding of the paper. Let me summarize for the user.
````

好，现在我对整篇文章有了完整的把握。回答你的两个问题：

---

## 是的，直接目标只是 $\operatorname{Tr}[(\rho_{AB}^{T_B})^3]$

论文自始至终的核心可测量量就是三阶 negativity-moment $\operatorname{Tr}[(\rho_{AB}^{T_B})^3]$。从这个量到真正的 logarithmic negativity $E_N = \log\|\rho^{T_B}\|_1$ 之间，论文依赖的是 Gray et al.（文中 Ref. [Bose2018Machine]）的先前结果：用机器学习从 $(p_1, p_2, p_3)$ 预测 negativity。所以这篇论文解决的不是"如何从矩重构谱"的数学问题，而是"如何高效测量 $p_3$"的实验实现问题。

---

## 提出的方案

论文一共提出了**三个方案**（或者说两个半），核心区别在于随机酉的作用范围和最终的测量基。

### 方案一：全局酉 + 计算基测量（Global scheme）

**操作步骤：**

1. 制备 single-copy $\rho_{AB}$
2. 在整个 $AB$ 系统上施加全局随机酉 $U_{AB}$（从 Haar 测度或 unitary 3-design 如 Clifford 群中采样）
3. 在计算基 $\{|a,b\rangle\}$ 上做投影测量，得到概率 $P(a,b|U_{AB})$
4. 对同一个 $U_{AB}$ 重复多次测量（$N_M$ shots），得到经验概率
5. 构造三阶虚拟拷贝：将三次独立的测量结果 $(a_1b_1), (a_2b_2), (a_3b_3)$ 的概率**相乘**，再乘以后处理系数 $O_+(\vec{s})$
6. 对多个随机酉 $U_{AB}$ 取平均（$N_U$ rounds）

**数学原理：** 概率的三次相乘等价于在三拷贝空间上做 Weingarten 积分

$$\mathbb{E}_U P(s|U)P(s'|U)P(s''|U) = \operatorname{Tr}\!\big[|\vec{s}\rangle\!\langle\vec{s}|\;\Phi^3(\rho^{\otimes 3})\big]$$

选择合适的后处理函数 $O_+(\vec{s}) = \alpha\,\delta_{ss's''} + \beta(\delta_{ss'}+\delta_{s's''}+\delta_{ss''}) + \gamma$，使得 $\Phi^3(O_+) = M_+ = W_{(1,2,3)} + W_{(1,3,2)}$，就能提取三阶纯度 $\operatorname{Tr}[\rho^3]$。

利用分解

$$M_{neg} = \tfrac{1}{2}(M_+^A \otimes M_+^B - M_+^{AB})$$

其中 $M_+^A \otimes M_+^B$ 可以用 bi-local 酉实现，$M_+^{AB}$ 需要全局酉。两部分相减即得 negativity-moment。

**优点：** 概念简单，直接实现。

**缺点：** 需要全局酉 $U_{AB}$，在大系统或空间分离的子系统上难以实现。

---

### 方案二：纯 bi-local 酉 + 计算基测量 → No-go

论文证明了一个**不可能定理**（Proposition 3）：如果只用 bi-local 随机酉 $U_A \otimes U_B$ 加计算基测量，**不存在**任何后处理策略能提取 $M_{neg}$。

**原因的物理直觉：** 计算基对两个三阶循环置换 $W_{(1,2,3)}$ 和 $W_{(1,3,2)}$ 的"对角矩阵元"完全相同：

$$\langle\vec{a}|W_{(1,2,3)}|\vec{a}\rangle = \delta_{a_1 a_2 a_3} = \langle\vec{a}|W_{(1,3,2)}|\vec{a}\rangle$$

因此 bi-local twirling 后，$W_{(1,2,3)}^A \otimes W_{(1,2,3)}^B$ 和 $W_{(1,2,3)}^A \otimes W_{(1,3,2)}^B$ 的系数永远被绑定在一起，无法分开——而 negativity 恰恰要求它们有不同的符号。

这个 no-go 同时意味着 $\operatorname{Tr}[\rho_{AB}^3]$ 本身也不能用 bi-local 方案测量，回答了当时文献中的一个开放问题。

---

### 方案三：Bi-local 酉 + Bell 测量（Bi-local + BSM scheme）

这是论文绕过 no-go 的关键创新。

**操作步骤：**

1. 制备 single-copy $\rho_{AB}$
2. 分别在 $A$ 和 $B$ 上独立施加随机酉 $U_A$, $U_B$（从各自的 unitary 3-design 中采样）
3. 不再做计算基测量，而是做 $A$-$B$ 之间的 **Bell 态测量**（BSM）：在 qudit Bell 基 $\{|\Psi_{u,v}\rangle\}$ 上投影
4. 同样重复 $N_M$ shots，构造三次概率乘积
5. 用 Bell 基上的后处理函数 $O_{Bell}$ 提取目标

**为什么 BSM 能打破 no-go：** Bell 态 $|\Psi_+\rangle = \frac{1}{\sqrt{d}}\sum_s |s,s\rangle$ 在三拷贝空间上能区分两个循环方向：

$$\operatorname{Tr}[(W_{(1,2,3)}^A \otimes W_{(1,2,3)}^B)\,\Psi_+^{\otimes 3}] = d$$
$$\operatorname{Tr}[(W_{(1,2,3)}^A \otimes W_{(1,3,2)}^B)\,\Psi_+^{\otimes 3}] = 1/d^2$$

这两个值差了 $d^3$ 倍！Bell 基天然编码了 $A$-$B$ 之间的关联结构，打破了计算基对循环方向的对称性。

论文由此给出一个新的分解：

$$M_{neg} = \tfrac{1}{4}(M_+^A \otimes M_+^B - M_-^A \otimes M_-^B)$$

其中 $M_- = W_{(1,2,3)} - W_{(1,3,2)}$（反对称部分）。$M_+^A \otimes M_+^B$ 用 bi-local 酉 + 计算基搞定，$M_-^A \otimes M_-^B$ 用 bi-local 酉 + BSM 搞定。两项都不需要全局酉。

**优点：** 完全 bi-local，适用于空间分离的子系统。

**缺点：** 需要在 $A$ 和 $B$ 之间执行 Bell 测量，这本身是一个非平凡的实验操作（但比全局酉简单得多）。

---

### 附带方案：Total correlation

用**完全相同的实验数据**（bi-local 酉 + 计算基），只改变后处理函数，就能提取

$$\operatorname{Tr}[\rho_{AB}(\rho_A \otimes \rho_B)] = \operatorname{Tr}[(W_{(1,2)}^A \otimes W_{(2,3)}^B)\,\rho_{AB}^{\otimes 3}]$$

这里只涉及**对换**（transposition）置换而非循环置换，对换在计算基对角元上是 $\delta_{a_1 a_2}$ 而非 $\delta_{a_1 a_2 a_3}$，不受 no-go 限制。所以 total correlation 不需要 BSM 也不需要全局酉。

---

## 总结

| | 随机酉 | 测量基 | 能测什么 |
|:---|:---:|:---:|:---|
| **方案一** | 全局 $U_{AB}$ | 计算基 | $M_+^{AB}$ → 配合 bi-local 得完整 $M_{neg}$ |
| **No-go** | Bi-local $U_A \otimes U_B$ | 计算基 | ❌ 无法得到 $M_{neg}$ 或 $\operatorname{Tr}[\rho^3_{AB}]$ |
| **方案三** | Bi-local $U_A \otimes U_B$ | 计算基 + BSM | $M_+$ (计算基) + $M_-$ (BSM) → 完整 $M_{neg}$ |
| **附带** | Bi-local $U_A \otimes U_B$ | 计算基 | Total correlation $\operatorname{Tr}[\rho_{AB}(\rho_A\otimes\rho_B)]$ |

整个工作的核心贡献是：将 Gray et al. 需要**真正制备三份拷贝并做联合测量**的方案，简化为只需 **single-copy + 随机酉 + 虚拟拷贝后处理**，代价是统计误差增大（需要更多 shots），但实验可行性大幅提升。



## Prompt:
3/4/2026, 11:57:35 AM

> File: excerpt_from_previous_claude_message.txt

之所以会出现交替项，是因为$(W_{(123)}^{(A)}+W_{(132)}^{(A)}) \otimes (W_{(123)}^{(B)}+W_{(132)}^{(B)}) = W_{(123)}^{(AB)}+W_{(132)}^{(AB)} +W_{(123)}^{(A)}W_{(132)}^{(B)}+W_{(123)}^{(B)}W_{(132)}^{(A)}$。后面多出来的项W_{(123)}^{(A)}W_{(132)}^{(B)}+W_{(123)}^{(B)}W_{(132)}^{(A)}不能用另一个AB可分的策略估计出来扣除吗？



## Response:
3/4/2026, 11:58:37 AM

````plaintext
Thought process: 分析了为何双局部策略无法直接估计交替项。

The user is asking a very sharp question. Let me think about this carefully.

The decomposition is:

$$M_+^A \otimes M_+^B = (W_{(123)}^A + W_{(132)}^A) \otimes (W_{(123)}^B + W_{(132)}^B)$$

Expanding:
$$= W_{(123)}^A W_{(123)}^B + W_{(132)}^A W_{(132)}^B + W_{(123)}^A W_{(132)}^B + W_{(132)}^A W_{(123)}^B$$

The first two terms give $M_+^{AB} = W_{(123)}^{AB} + W_{(132)}^{AB}$, and the last two terms give $2M_{neg}$.


So the cross terms $W_{(123)}^A W_{(132)}^B + W_{(132)}^A W_{(123)}^B$ are exactly what we're isolating, and they equal $\frac{1}{2}(M_+^A \otimes M_+^B - M_+^{AB})$. The user's point is whether we could measure these cross terms directly through some other separable strategy instead of computing them as a difference.

But here's the issue: the no-go theorem tells us that $M_{neg}$ itself cannot be estimated using only bi-local unitaries and computational basis measurements. Since the cross terms are precisely $2M_{neg}$, there's no way to access them directly with a bi-local approach—we're fundamentally blocked by the same obstruction that prevents measuring $M_{neg}$ in the first place.

The reason comes down to how the Weingarten expansion constrains things. When we apply bi-local twirling, the coefficients of $W_{(123)}^A \otimes W_{(123)}^B$ and $W_{(123)}^A \otimes W_{(132)}^B$ become locked together because both permutations give the same trace when contracted with computational basis states. This coupling in the Weingarten expansion is what makes it impossible to isolate the cross terms we're after. in the computational basis are identical. This means any post-processing function $O(\vec{a}, \vec{b})$ will always give these two permutations the same coefficient on each subsystem.

So in $\Phi^3_A \otimes \Phi^3_B(O)$, the coefficient of $W_{(123)}^A$ always equals the coefficient of $W_{(132)}^A$ (when paired with any fixed $B$ permutation), and similarly for $B$. 

This means $\Phi^3_A \otimes \Phi^3_B(O)$ is always symmetric under $(123) \leftrightarrow (132)$ independently on $A$ and $B$. So you can get $M_+^A \otimes M_+^B$ (symmetric on both), but you cannot get $M_-^A \otimes M_-^B$ (antisymmetric on both) or any cross terms with different signs.

The fundamental issue is that $M_{neg} = \frac{1}{2}(M_+^A \otimes M_+^B - M_+^{AB})$ requires distinguishing $W_{(123)}^{AB}$ from $W_{(123)}^A W_{(132)}^B$, which the bi-local computational basis simply cannot do. So even if we tried to find some other separable observable that gives us $M_+^{AB}$, the no-go theorem rules it out completely with bi-local unitaries and computational basis measurements. The user might be wondering whether different LOCC strategies could work around this, but the answer remains no. The fundamental issue is that bi-local twirling produces terms where the coefficients factor into separate $A$ and $B$ components, but the $A$-side can't distinguish between permutations like $(123)$ and $(132)$ using only local observables—so there's no way to generate different coefficients for different permutation pairs, which is what you'd need to break the symmetry. This gives a clean explanation for why the approach fails.
````

这个问题问得非常精准。你的想法完全自然——既然展开式里多出来的交叉项就是 $2M_{neg}$ 本身，那能不能用另一个 bi-local 可实现的算子把 $M_+^{AB}$ 估计出来再扣掉？

答案是**不能**，而且这恰恰就是 no-go 定理的内容。让我把障碍讲清楚。

## 问题的精确结构

展开你写的等式：

$$M_+^A \otimes M_+^B = \underbrace{W_{(123)}^{AB} + W_{(132)}^{AB}}_{M_+^{AB}} + \underbrace{W_{(123)}^A W_{(132)}^B + W_{(132)}^A W_{(123)}^B}_{2M_{neg}}$$

所以要得到 $M_{neg}$，等价于要把这四项中"同向"的 $(W_{(123)}^A W_{(123)}^B$ 和 $W_{(132)}^A W_{(132)}^B)$ 与"反向"的 $(W_{(123)}^A W_{(132)}^B$ 和 $W_{(132)}^A W_{(123)}^B)$ **分开**。

## 为什么 bi-local + 计算基做不到

Bi-local twirling 之后，任何后处理算子 $O(\vec{a},\vec{b})$ 产生的结果是：

$$\Phi_A^3 \otimes \Phi_B^3(O) = \sum_{\pi,\pi',\sigma,\sigma' \in S_3} C_{\pi,\sigma}\, C_{\pi',\sigma'}\; \underbrace{\operatorname{Tr}[(W_\pi^A \otimes W_{\pi'}^B)\, O]}_{c_{\pi,\pi'}}\; W_\sigma^A \otimes W_{\sigma'}^B$$

关键是系数 $c_{\pi,\pi'}$ 的结构。因为 $O$ 是计算基上的对角算子 $O = \sum_{\vec{a},\vec{b}} O(\vec{a},\vec{b})\,|\vec{a}\rangle\!\langle\vec{a}| \otimes |\vec{b}\rangle\!\langle\vec{b}|$，所以：

$$c_{\pi,\pi'} = \sum_{\vec{a},\vec{b}} O(\vec{a},\vec{b})\; \langle\vec{a}|W_\pi^A|\vec{a}\rangle\; \langle\vec{b}|W_{\pi'}^B|\vec{b}\rangle$$

现在致命的一步来了。对计算基：

$$\langle\vec{a}|W_{(123)}|\vec{a}\rangle = \delta_{a_1 a_2}\delta_{a_2 a_3} = \delta_{a_1 a_2 a_3}$$

$$\langle\vec{a}|W_{(132)}|\vec{a}\rangle = \delta_{a_1 a_3}\delta_{a_3 a_2} = \delta_{a_1 a_2 a_3}$$

**完全相同**。这是因为 $(123)$ 和 $(132)$ 互为逆元，而计算基态 $|\vec{a}\rangle$ 是实的，所以对角矩阵元一定相等。

因此，对 $A$ 子系统上的 **任何** 后处理，$W_{(123)}^A$ 和 $W_{(132)}^A$ 永远贡献相同的系数——它们在计算基对角元上不可区分。同理对 $B$。

这直接意味着：

$$c_{(123),(123)} = c_{(132),(123)} = c_{(123),(132)} = c_{(132),(132)}$$

也就是说，这四项在 $\Phi_A^3 \otimes \Phi_B^3(O)$ 的展开中**永远以相同的权重出现**。你无论怎么设计 $O(\vec{a},\vec{b})$，都不可能让同向项和反向项有不同的系数。

## 你的想法为什么不行

你想的是：能不能找另一个 bi-local 可分算子 $\tilde{O}(\vec{a},\vec{b})$，使得 $\Phi_A^3 \otimes \Phi_B^3(\tilde{O}) = M_+^{AB}$，然后用 $M_+^A \otimes M_+^B - M_+^{AB}$ 得到 $M_{neg}$？

但 $M_+^{AB} = W_{(123)}^A W_{(123)}^B + W_{(132)}^A W_{(132)}^B$ 恰好**只含同向项**，而 bi-local 计算基后处理能产生的始终是：

$$\alpha\,(\text{全部四项}) + \text{其他置换的组合}$$

其中四项的系数**锁死相等**。你不可能只选出同向的两项——这正是 no-go 要说的。

换句话说，bi-local + 计算基方案的可达空间中，$M_+^A \otimes M_+^B$ 是**你能到达的最接近 $M_{neg}$ 的东西**，但它同时包含了 $M_+^{AB}$ 和 $2M_{neg}$，你无法把它们拆开。

## Bell 测量为什么能破局

Bell 基 $|\Psi_{u,v}\rangle$ 是 $A$-$B$ 的**纠缠基**，它的对角元对两个循环方向给出截然不同的值：

$$\langle\Psi_+^{\otimes 3}|W_{(123)}^A W_{(123)}^B|\Psi_+^{\otimes 3}\rangle = d$$

$$\langle\Psi_+^{\otimes 3}|W_{(123)}^A W_{(132)}^B|\Psi_+^{\otimes 3}\rangle = 1/d^2$$

差了 $d^3$ 倍！所以在 Bell 基上做后处理时，同向和反向项不再锁死，可以自由赋予不同权重。这就是为什么论文用 $M_- = W_{(123)} - W_{(132)}$（反对称部分）在 Bell 基上构造：

$$M_{neg} = \tfrac{1}{4}(M_+^A \otimes M_+^B - M_-^A \otimes M_-^B)$$

其中 $M_-^A \otimes M_-^B$ 只含交叉项 $W_{(123)}^A W_{(132)}^B + W_{(132)}^A W_{(123)}^B$（展开后负负得正），正好补上缺失的信息。

**本质上，计算基是 product basis，它尊重 $A$-$B$ 的因子化结构，因此无法区分"$A$ 上正向 $\times$ $B$ 上正向"和"$A$ 上正向 $\times$ $B$ 上反向"。Bell 基是纠缠基，它编码了 $A$-$B$ 之间的关联，天然打破了这个对称性。**



## Prompt:
3/4/2026, 12:26:05 PM

虽然

```quarto
$W^{(A)}_{(123)} \otimes W^{(B)}_{(132)}$
```

是非厄米的，但是它是可对角化的。为什么不直接投影到它的eigen basis上？



## Response:
3/4/2026, 6:51:57 PM

````plaintext
Thought process: 辨析了三拷贝空间限制与单拷贝测量方案的根本差异。

The user is asking: since $W_{(123)}^A \otimes W_{(132)}^B$ is non-Hermitian but diagonalizable, why not just project onto its eigenbasis directly?

This is a good question. Let me think about this carefully.

$W_{(123)}$ is a cyclic permutation operator on 3 copies. Its eigenvalues are the cube roots of unity: $1, \omega, \omega^2$ where $\omega = e^{2\pi i/3}$. So $W_{(123)}^A \otimes W_{(132)}^B$ has eigenvalues that are products of eigenvalues of the two factors.


But here's the fundamental constraint: this operator lives on the three-copy Hilbert space, so measuring it directly would require three physical copies of the state. The entire approach in this paper is designed to circumvent that requirement by constructing "virtual copies" through random unitaries and classical post-processing applied to single-copy measurements. The Weingarten integral is what allows us to synthesize the three-copy structure from single-copy operations, so we can't just bypass that machinery and project onto the eigenbasis directly.

There's also a subtlety with non-Hermiticity—while $W_{(123)}$ is unitary with eigenvalues $1, \omega, \omega^2$, it's not Hermitian, so its eigenbasis doesn't correspond to a standard projective measurement. You'd need to either decompose it into Hermitian and anti-Hermitian parts or use a generalized measurement scheme, but that doesn't resolve the core problem: the operator fundamentally requires access to three copies.

The dimensional mismatch is insurmountable—the operator acts on a $d^6$-dimensional space while a single copy only has $d^2$ dimensions, so there's no way to design a single-copy measurement whose POVM elements could relate to its eigenprojectors. Projecting onto the eigenbasis of $W_{(123)}^A \otimes W_{(132)}^B$ is precisely the three-copy collective measurement that Gray et al. use, and this entire paper is built around circumventing that requirement.
````

这个问题切中了整篇论文存在的根本原因。

## 关键点：这个算子住在哪个空间？

$W_{(123)}^A \otimes W_{(132)}^B$ 作用在**三拷贝空间**上：

$$W_{(123)}^A \otimes W_{(132)}^B \;\in\; \mathcal{L}\!\big((\mathcal{H}_A \otimes \mathcal{H}_B)^{\otimes 3}\big)$$

它的维度是 $(d_A d_B)^3$。你说得对，它是可对角化的——事实上它是酉算子（$W_{(123)}^3 = I$），所以本征值是 $1, \omega, \omega^2$（$\omega = e^{2\pi i/3}$），可以投影到对应的本征子空间上。

**但投影到它的本征基上，意味着你需要对三拷贝空间做联合测量。** 也就是说你必须：

1. 同时制备三份 $\rho_{AB}$
2. 在 $\mathcal{H}^{\otimes 3}$ 上实现本征子空间的投影测量

这**正好就是** Gray et al.（Ref. [Bose2018Machine]）的方案——他们就是在三份拷贝上做集体测量来提取 $\operatorname{Tr}[(W_{(123)}^A \otimes W_{(132)}^B)\,\rho_{AB}^{\otimes 3}]$。

## 这篇论文解决的问题

整篇论文的出发点就是：三拷贝集体测量在实验上太难了。你需要同时拥有三份相同的量子态，要么平行制备三份（需要三倍的量子比特），要么把态存在量子存储器里（需要高保真度的量子内存）。对于多体系统，这基本不可行。

所以论文的 contribution 不是在测量理论上有什么新东西，而是：

$$\boxed{\text{用 single-copy 操作 + 经典后处理，模拟三拷贝集体测量的效果}}$$

代价是用随机酉的多次重复采样（统计开销）换取了量子资源的节省（不需要多拷贝）。

## 换个角度理解

你可以把整个方案看成一个 trade-off：

| | 量子资源 | 经典资源 | 
|:---|:---:|:---:|
| **Gray et al.** | 3 copies + 集体测量 | 少 |
| **本文方案** | 1 copy + 随机酉 | 多（$N_U \times N_M$ shots） |

Weingarten 积分本质上是在说：如果你对 single-copy 态施加足够多的随机酉并收集统计数据，概率的三次乘积在平均后**数学上等价于**三拷贝上的置换算子期望值。"虚拟拷贝"就是这个意思——三份拷贝从来没有物理存在过，它们是通过经典数据处理中的概率乘积"虚拟创建"的。

所以你的想法完全正确且是最直接的方案，只不过它就是被替代的旧方案本身。



## Prompt:
3/4/2026, 12:30:43 PM

> File: 1772598595187_Gray et al. - 2018 - Machine Learning Assisted Many-Body Entanglement Measurement.pdf

参考这个Gray的pdf，具体实现三拷贝局域投影的线路该怎么设计？



## Response:
3/4/2026, 12:31:50 PM

````plaintext
Thought process: 剖析了Gray论文中三拷贝测量的反向传播线路设计。

The user is asking about the specific circuit design for implementing the three-copy local projection measurement scheme from the Gray et al. paper. Let me look at the paper's measurement protocol carefully.

The key is in the appendix of Gray et al., specifically the "Measuring Moments in spin-1/2 Systems" section. Let me trace through the protocol for m=3.

The protocol for spin systems involves sequential SWAP measurements (singlet-triplet measurements) between neighboring copies. For m=3:

1. Prepare 3 copies of ρ_AB
2. On subsystem A: measure forward swaps S^{1,2}_A then S^{2,3}_A


3. On subsystem B: measure backward swaps in reverse order—S^{3,2}_B then S^{2,1}_B—which is essential for obtaining the partial transpose structure
4. The counter-propagating measurement directions on A and B are what creates the transposition effect needed for the purity calculation

The equation shows this clearly: on A I measure copies 1,2 first then 2,3, while on B I go the opposite direction starting with 2,3 then 1,2. Each singlet-triplet measurement between copies c and d on site j effectively probes the SWAP operator, returning +1 for triplet states and -1 for singlet states. This measurement scheme is what generates the partial transpose in the final expression.
````

这是一个非常具体的实验实现问题。让我根据 Gray et al. 的 appendix 详细拆解 $m=3$ 的线路设计。

## 核心思想：反向 SWAP 测量实现 partial transpose

Gray et al. 的关键发现是：在 $A$ 和 $B$ 子系统上做**方向相反**的顺序 SWAP 测量，等价于测量 partial transpose 后的置换算子。

## 基本构建块：Singlet-Triplet 测量

对于自旋-1/2 系统，两个拷贝 $c, d$ 之间在同一格点 $j$ 上的 SWAP 算子是：

$$\Xi_j^{c,d} = \frac{\mathbb{1} + \boldsymbol{\sigma}_{j,c} \cdot \boldsymbol{\sigma}_{j,d}}{2}$$

这就是 **singlet-triplet (ST) 测量**：

- 本征值 $+1$：triplet（对称子空间）→ 输出 $\beta = +1$
- 本征值 $-1$：singlet（反对称子空间）→ 输出 $\beta = -1$

对整个子系统 $X$ 的 SWAP 是所有格点的乘积：$S_X^{c,d} = \prod_{j \in X} \Xi_j^{c,d}$

## $m=3$ 的具体线路

准备三份拷贝 $\rho_{AB}^{\otimes 3}$，标记为拷贝 1, 2, 3。

### 步骤示意图

```
          子系统 A                    子系统 B
     copy 1  copy 2  copy 3    copy 1  copy 2  copy 3
       |       |       |          |       |       |
       |  ST   |       |          |       |       |
       +---⊗---+       |          |       |       |    时间步 1
       |  β₁ᴬ  |       |          |       |       |
       |       |  ST   |          |       |       |
       |       +---⊗---+          |       |       |    时间步 2
       |       |  β₂ᴬ  |          |       |       |
       |       |       |          |       |  ST   |
       |       |       |          |       +---⊗---+    时间步 3
       |       |       |          |       |  β₁ᴮ  |
       |       |       |          |  ST   |       |
       |       |       |          +---⊗---+       |    时间步 4
       |       |       |          |  β₂ᴮ  |       |
```

### 子系统 A：**正向**顺序

1. **时间步 1**：对每个格点 $j \in A$，在拷贝 1 和拷贝 2 之间做 ST 测量，得到结果 $\beta_1^A = \prod_{j \in A} \beta_{1,j}^A$
2. **时间步 2**：对每个格点 $j \in A$，在拷贝 2 和拷贝 3 之间做 ST 测量，得到结果 $\beta_2^A = \prod_{j \in A} \beta_{2,j}^A$

即 $A$ 上的测量顺序是 $S_A^{2,3} \circ S_A^{1,2}$（先 1-2，再 2-3，**正向**）。

### 子系统 B：**反向**顺序

3. **时间步 3**：对每个格点 $j \in B$，在拷贝 **2 和 3** 之间做 ST 测量，得到结果 $\beta_1^B$
4. **时间步 4**：对每个格点 $j \in B$，在拷贝 **1 和 2** 之间做 ST 测量，得到结果 $\beta_2^B$

即 $B$ 上的测量顺序是 $S_B^{1,2} \circ S_B^{2,3}$（先 2-3，再 1-2，**反向**）。

### 数据处理

每轮实验的输出值为：

$$\phi = \beta_1^A \cdot \beta_2^A \cdot \beta_1^B \cdot \beta_2^B \in \{+1, -1\}$$

重复 $R$ 次取平均：

$$\mu_3 = \operatorname{Tr}[(\rho_{AB}^{T_B})^3] = \langle \phi \rangle = \frac{1}{R}\sum_{r=1}^R \phi_r$$

## 为什么反向顺序给出 partial transpose

这是整个方案最精妙之处。论文 appendix 中推导的核心等式 (S2) 是：

$$(\mathbb{P}^3)^{T_B} = \frac{1}{2}\left(S_A^{3,2} S_A^{2,1} \otimes S_B^{2,1} S_B^{3,2} + \text{h.c.}\right)$$

而顺序 ST 测量的期望值，由 (S1) 的推导逻辑（利用投影算子 $\Pi_\pm = (\mathbb{1} \pm S)/2$ 的性质），给出：

$$\langle S_X^{2,3} \circ S_X^{1,2} \rangle = \frac{1}{2}\left(\operatorname{Tr}[S_X^{1,2} S_X^{2,3}\,\rho^{\otimes 3}] + \operatorname{Tr}[S_X^{2,3} S_X^{1,2}\,\rho^{\otimes 3}]\right)$$

注意这里自然出现了 hermitian 化（$+ \text{h.c.}$），因为投影测量后再做下一次测量时，中间插入了 $\sum_\beta \Pi_\beta(\cdot)\Pi_\beta$，这把非对易的乘积对称化了。

关键在于：

- 如果 $A$ 和 $B$ **同向**（都是 1→2→3），得到的是 $\operatorname{Tr}[\rho^3]$（纯度）
- 如果 $A$ 和 $B$ **反向**（$A$: 1→2→3，$B$: 3→2→1），得到的是 $\operatorname{Tr}[(\rho^{T_B})^3]$（negativity-moment）

**直觉**：SWAP 的顺序链 $S^{1,2}S^{2,3}$ 实现了循环置换 $(1,2,3)$，而反向链 $S^{2,3}S^{1,2}$ 实现了逆循环 $(1,3,2)$。$A$ 上正向 $\times$ $B$ 上反向 = $W_{(123)}^A \otimes W_{(132)}^B$，正好就是 partial transpose 的效果。

## 具体量子线路（门级实现）

每个 ST 测量 $\Xi_j^{c,d}$ 可以分解为标准量子门：

```
copy c ──●──H──M──     测量结果 m₁
         │            
copy d ──⊕──────M──     测量结果 m₂
```

即 CNOT + Hadamard + 计算基测量。判据为：

$$\beta_j = \begin{cases} -1 & \text{if } m_1 = 1, m_2 = 1 \quad (\text{singlet: } |01\rangle - |10\rangle) \\ +1 & \text{otherwise} \quad (\text{triplet}) \end{cases}$$

但这里有一个微妙之处：**ST 测量是破坏性的**，测量后态会坍缩。论文的推导利用了顺序测量的非对易性——第一次 ST 测量把态投影到 $\Pi_{\beta_1}$ 子空间后，第二次 ST 测量在这个投影后的态上进行。这不是两个独立测量，而是**顺序投影测量**。

### 完整的 $m=3$ 线路（单个格点 $j$）

对 $A$ 中格点 $j$（三个拷贝的 qubit 标记为 $j_1, j_2, j_3$）：

```
j₁ ──●──H──M₁── ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─     → β₁,ⱼᴬ
     │           (坍缩后的 j₂ 继续)
j₂ ──⊕── ─ ─ ─ ──●──H──M₂──               → β₂,ⱼᴬ
                  │
j₃ ─ ─ ─ ─ ─ ─ ──⊕── ─ ─ ─ ─              (态已确定)
```

对 $B$ 中格点 $j$（**反向**）：

```
j₁ ─ ─ ─ ─ ─ ─ ──⊕── ─ ─ ─ ─              (态已确定)
                  │
j₂ ──⊕── ─ ─ ─ ──●──H──M₂──               → β₂,ⱼᴮ
     │           (坍缩后的 j₂ 继续)
j₃ ──●──H──M₁── ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─     → β₁,ⱼᴮ
```

注意 $B$ 的顺序：**先**测拷贝 2-3，**再**测拷贝 1-2。

## 实验资源总结

| 资源 | 需求 |
|:---|:---|
| 量子态拷贝数 | 3 份 $\rho_{AB}$ |
| 每轮 ST 测量数 | $2(N_A + N_B)$（每个格点两次） |
| 输出 | 单个 bit $\phi = \pm 1$ |
| 统计精度 | $\Delta\mu_3 = \sqrt{(1-\mu_3^2)/R}$，重复 $R$ 次 |
| 测量复杂度 | $\mathcal{O}(N_A + N_B)$，多项式！ |

这与 tomography 需要 $2^{2(N_A+N_B)}$ 个测量设置相比，是指数级的改进。代价是需要物理制备三份相同的量子态并在拷贝之间做双 qubit 门——这在量子点阵列和冷原子光晶格中已经实验实现。



## Prompt:
3/4/2026, 12:34:08 PM

严格证明：12的Bell measurement + 23的Bell measurement 等价于123上投影到SWAP_{123}的本征态上的测量



## Response:
3/4/2026, 12:37:56 PM

````plaintext
Thought process: 解析了顺序SWAP测量与循环置换算子的数学关系。

The user is asking me to rigorously prove that sequential Bell measurements (first on copies 1-2, then on copies 2-3) is equivalent to projecting onto the eigenspaces of the cyclic permutation operator $W_{(123)}$ on the 3-copy space.

Wait, let me re-read. The user is asking about the relationship between sequential SWAP (ST) measurements and the cyclic permutation. Let me think about this carefully.

Actually, I think the user is asking about the statement from Gray et al. that sequential ST measurements on copies (1,2) and then (2,3) effectively measures the cyclic permutation $W_{(123)} + W_{(132)}$.
 
Let me reconsider what's actually being claimed here. The user mentions Bell measurements specifically, not ST measurements, and they're asking whether sequential Bell measurements on (1,2) followed by (2,3) is equivalent to measuring the eigenspaces of the cyclic permutation on the full 3-copy system. I need to work through whether the expectation value $\langle S^{2,3} \circ S^{1,2} \rangle = \text{Tr}[\rho^3]$ holds, where $S^{c,d}$ represents the SWAP operator between copies $c$ and $d$. +1 of SWAP). So the ST measurement is actually a coarse-grained Bell measurement—it distinguishes the singlet from the triplet states but doesn't differentiate among the three triplet states themselves. The user said "Bell measurement" specifically though, not ST measurement, so I should consider whether a full Bell measurement would provide additional information. Let me reconsider this as a more fundamental mathematical question about the three-copy Hilbert space.

On a single qudit, the cyclic permutation operator $W_{(123)}$ has eigenvalues $1, \omega, \omega^2$ where $\omega = e^{2\pi i/3}$, and the SWAP operators $S^{1,2}$ and $S^{2,3}$ also act on this space. The real question is whether measuring $S^{1,2}$ first (getting outcomes $\pm 1$) and then $S^{2,3}$ (also $\pm 1$) effectively projects onto the eigenspaces of $W_{(123)}$. For qubits specifically, I'm working in $\mathcal{H}^{\otimes 3} = (\mathbb{C}^2)^{\otimes 3}$.

Now I'm checking whether $W_{(123)}$ can be expressed as a product of these SWAP operators. The 8-dimensional space has SWAP operators with eigenvalues $\pm 1$, giving 4 possible measurement outcomes from the sequential measurements. Let me verify the action: $W_{(123)}$ cycles the three qubits as $|a,b,c\rangle \to |c,a,b\rangle$, while $S^{1,2}$ swaps the first two as $|a,b,c\rangle \to |b,a,c\rangle$.

Composing them in order, $S^{1,2} S^{2,3}$ first swaps positions 2 and 3, then swaps positions 1 and 2, which produces the cyclic permutation $W_{(123)}$. But reversing the order gives $S^{2,3} S^{1,2}$, which instead produces the opposite cycle $W_{(132)}$.

The crucial point is whether measuring these swap operators sequentially actually projects onto eigenstates of the resulting cyclic permutation. Since $S^{1,2}$ and $S^{2,3}$ don't commute, they lack a shared eigenbasis, so the sequential measurement creates a finer decomposition rather than projecting cleanly onto $W_{(123)}$ eigenstates.

For three qubits, I need to examine how the full Hilbert space decomposes under the symmetric group using Schur-Weyl duality. The symmetric subspace forms one irreducible representation...

Now I'm working through the eigenspace structure of $S^{1,2}$ on the three-qubit system, where the +1 eigenspace has dimension 6, corresponding to symmetric states of the first two qubits paired with any state of the third qubit. = 6) Wait no. The symmetric subspace of $(\mathbb{C}^2)^{\otimes 2}$ is 3-dimensional (triplet) and antisymmetric is 1-dimensional (singlet). So:
  - $S^{1,2} = +1$: $\text{Sym}^2(\mathbb{C}^2) \otimes \mathbb{C}^2 = 3 \times 2 = 6$-dimensional
  - $S^{1,2} = -1$: $\wedge^2(\mathbb{C}^2) \otimes \mathbb{C}^2 = 1 \times 2 = 2$-dimensional

For the second swap, I get the same dimensional breakdown: 6-dimensional when $S^{2,3} = +1$ and 2-dimensional when $S^{2,3} = -1$.

The sequential measurement strategy projects first onto the $S^{1,2}$ eigenspaces, then within each subspace projects onto the $S^{2,3}$ eigenspaces. This gives me four distinct subspaces labeled by the pair $(\beta_1, \beta_2)$ indicating the eigenvalues of each swap operator.

But I need to be careful here—sequential measurement isn't the same as simultaneously measuring commuting observables. After projecting onto an $S^{1,2}$ eigenspace, the state collapses, and then measuring $S^{2,3}$ acts on this projected state. The user seems to be asking whether this sequential procedure is equivalent to projecting onto eigenspaces of the three-particle swap $W_{(123)}$, but that can't be exactly equivalent since $W_{(123)}$ has different eigenvalue structure.

Looking at the Gray et al. formula, they're claiming the expectation value of sequential measurements equals a specific trace formula involving the product of the two swap operators, which apparently simplifies to $\text{Tr}(\rho^3)$ due to some algebraic property of how these operators compose.

The key insight is that the sequential measurement actually gives the average of two different cyclic permutations rather than projecting onto eigenspaces of a single operator. Now I'm reconsidering what the user means by "SWAP_{123}" in their original question—they might be referring to the cyclic permutation operator itself.

The real issue is that we have four possible outcomes from the sequential measurements but only three eigenspaces for the cyclic permutation, so there's a mismatch in how the information maps. Let me work through this more carefully with a simpler single-qubit case to build intuition.

For qubits, the three-qubit Hilbert space decomposes under the symmetric group into irreducible representations: a fully symmetric subspace of dimension 4, and other components. The cyclic permutation operator acts differently on each of these subspaces, and I need to figure out exactly how the sequential SWAP measurement outcomes relate to which eigenspace the state projects into. ial representation where all group elements act as +1. The fully symmetric subspace is where ALL permutations act as +1).

Let me be more careful. The irreps of $S_3$ are:
1. Trivial representation: all permutations → +1
2. Sign representation: even permutations → +1, odd permutations → -1
3. Standard representation: 2-dimensional

For $(\mathbb{C}^2)^{\otimes 3}$, the Schur-Weyl decomposition gives:
- Trivial ⊗ Sym³(ℂ²): the fully symmetric subspace, dim 4. Here $W_{(123)}$ acts as $+1$ (trivial rep).
- Standard ⊗ mixed: the mixed symmetry subspace, dim 4. Here $W_{(123)}$ acts on the Standard rep factor with eigenvalues $\omega$ and $\omega^2$.

Actually, the sign representation can't appear since $\wedge^3(\mathbb{C}^2) = 0$ — you can't fully antisymmetrize three vectors in a 2-dimensional space. So the decomposition is just the trivial rep tensored with the fully symmetric part of dimension 4, plus the standard rep tensored with the mixed symmetry part of dimension 4.

On the 4-dimensional symmetric subspace, $W_{(123)}$ acts trivially with eigenvalue $+1$. On the 4-dimensional mixed part, $W_{(123)}$ acts on the standard rep factor, giving eigenvalues $\omega$ with multiplicity 2 and $\omega^2$ with multiplicity 2.

So the eigenspaces decompose as: eigenvalue $1$ gives a 4-dimensional fully symmetric sector, eigenvalue $\omega$ gives 2-dimensional, and eigenvalue $\omega^2$ gives 2-dimensional, totaling 8 dimensions.

Now I'm analyzing what happens when we perform sequential spin-triplet measurements on qubits 1 and 2, which gives outcomes $(\beta_1, \beta_2) \in \{+1,-1\}^2$. When $S^{1,2} = +1$ (triplet state), we get 3 triplet configurations tensored with 2 states of the third qubit, giving 6 dimensions. When $S^{1,2} = -1$ (singlet state), we have 1 singlet configuration tensored with 2 states of the third qubit.

Within this 2-dimensional singlet subspace, I need to find the eigenvalues of the spin-triplet measurement on qubits 2 and 3. The singlet state of qubits 1 and 2 is the antisymmetric combination, and I'm computing how the $S^{2,3}$ operator acts on the basis states formed by this singlet tensored with each computational basis state of qubit 3.

Let me work through the action of $S^{2,3}$, which swaps qubits 2 and 3. Applying this swap operator to the singlet state tensored with the third qubit gives me the transformed states I need to find the eigenvalues.

But wait—this transformed state is no longer in the $S^{1,2}=-1$ eigenspace, which means $S^{1,2}$ and $S^{2,3}$ don't commute. So I can't just treat the sequential measurement as independent eigenvalue problems. I need to follow the Gray et al. derivation more carefully, starting with their key formula for the expectation value of the composite operator $S^{2,3} \circ S^{1,2}$.

The formula involves summing over measurement outcomes $\beta_1$ and $\beta_2$, weighted by their values, with projection operators $\Pi^{c,d}_\pm = (\mathbb{1} \pm S^{c,d})/2$ acting on the initial state. Using the completeness relation $\sum_{\beta_2} \beta_2 \Pi^{2,3}_{\beta_2} = S^{2,3}$ and the cyclic property of the trace, I can simplify this to an expression involving only the first measurement's projection operators.

Now I'm expanding the product $\Pi^{1,2}_{\beta_1} S^{2,3} \Pi^{1,2}_{\beta_1}$ by substituting the definition of the projectors and distributing the swap operator $S^{2,3}$ across the terms. The key term to evaluate is $S^{1,2}S^{2,3}S^{1,2}$, which requires careful computation of how these swap operators compose.

Let me trace through the action on a basis state: applying the swaps in sequence transforms $|a,b,c\rangle$ through $|b,a,c\rangle$ to $|b,c,a\rangle$ and finally to $|c,b,a\rangle$. This composite operation is equivalent to the transposition $(1,3)$, so $S^{1,2}S^{2,3}S^{1,2} = S^{1,3}$. Substituting this back into the expansion gives me the final form in terms of the swap operators and cyclic permutations.

Now I'm summing over the $\beta_1$ values, which causes most terms to vanish due to the sum of the roots of unity equaling zero, leaving only the cyclic permutation operators with a factor of $\frac{1}{2}$.

I've verified that the expectation value matches $\text{Tr}[\rho^3]$, but I'm realizing this calculation doesn't directly address what the user is asking about. Let me reconsider their question more carefully—they seem to be asking whether performing sequential Bell measurements on pairs (1,2) and (2,3) is equivalent to projecting onto eigenstates of the SWAP operator on all three copies, and I need to think through whether full Bell measurements would give us enough information to determine the eigenspace. I'm realizing the issue: after the first measurement collapses copy 2, how can we measure it again in the second step? Unless we're talking about a coarser measurement like the ST measurement, which only has two outcomes and leaves copy 2 in a superposition rather than fully collapsing it. Let me try working through the proof by interpreting "Bell measurement" as an ST or SWAP measurement instead.

I think what the user is really asking about is the mathematical relationship from Gray et al.—that sequential SWAP measurements on pairs (1,2) and then (2,3) give us information about the cyclic permutation operator. Let me work out how the measurement outcomes connect to the spectrum of the sum of cyclic permutations using the group algebra structure of S₃.

Since the cyclic permutations (123) and (132) form a conjugacy class, their sum M₊ is a class sum in the group algebra, which means it commutes with all transpositions and therefore with the entire group. This means M₊'s eigenspaces decompose according to the irreducible representations of S₃. Let me verify this commutation relation holds by checking whether the transposition S^{1,2} actually commutes with M₊. I've verified that $M_+$ commutes with $S^{1,2}$, which means it's central to the algebra. That lets me simultaneously diagonalize $M_+$ with any transposition, but since the transpositions don't commute with each other, I can't diagonalize all of them at once. Let me refocus on what would actually be useful to prove for the user's question.

The key claim seems to be that measuring $S^{1,2}$ followed by $S^{2,3}$ sequentially gives information equivalent to measuring $M_+$, where the product of the outcomes $\beta_1 \beta_2$ corresponds to the eigenvalue of $M_+$. That's essentially what Gray et al. establish. Rather than getting bogged down in the general theory, I should work through the explicit 8-dimensional case for a single qubit to make this concrete. I need to step back and think about what the user is actually asking mathematically. The sequential projective measurement produces outcomes, and I'm trying to show that the expectation value of the product of those outcomes relates to a specific combination of permutation operators. Let me work through this more carefully by focusing on what the sequential measurement actually computes. I'm working through the eigenvalue decomposition of $M_+$ across the different irreducible representations of $S_3$—the trivial rep gives eigenvalue 2, the standard rep gives -1, and the sign rep also gives 2 since both cyclic permutations are even.

For qubits specifically, the sign representation doesn't appear in the three-qubit Hilbert space, so $M_+$ has eigenvalue 2 on the 4-dimensional symmetric subspace and eigenvalue -1 on the 4-dimensional mixed symmetry subspace. The sequential stabilizer measurement with the product $\beta_1\beta_2$ then provides an estimator for...

Actually, let me think through whether this sequential measurement truly captures $M_+$. While $M_+$ has only two eigenvalues, the sequential measurement yields four distinct outcomes, so they're not quite equivalent—but the product $\beta_1\beta_2$ effectively coarse-grains the information in a way that relates to $M_+$. Working through the calculation more carefully, I can show that the expectation value of $\beta_1\beta_2$ equals half the trace of the symmetrized permutation operator acting on the three-copy state.

This factor of $1/2$ emerges because the sequential measurement naturally symmetrizes over different orderings of the SWAP operations. So I'm getting $M_+/2$ rather than $M_+$ directly. I think the core insight the user is asking about is the fundamental connection between sequential SWAP measurements and cyclic permutation operators—specifically, why applying $S^{12}$ followed by $S^{23}$ produces the sum $W_{(123)} + W_{(132)}$. Let me work out a clean, rigorous derivation of this relationship.

Actually, rereading the question in Chinese, I see they're asking about the equivalence between sequential Bell measurements on pairs (1,2) and (2,3) versus projecting onto the eigenstates of the cyclic SWAP $W_{(123)}$. The subtlety here is that $W_{(123)}$ itself isn't Hermitian—its eigenvalues are $1, \omega, \omega^2$—so you can't directly measure it projectively. What you can measure is the Hermitian combination $M_+ = W_{(123)} + W_{(132)}$, which is the sum of the cyclic SWAP and its adjoint. For higher-dimensional qudits, this generalizes naturally.

Now I'm working through the eigenvalue structure of $M_+$ and setting up a rigorous proof that the sequential measurement procedure is equivalent to measuring this Hermitian operator. The eigenvalues turn out to be $2\cos(2\pi k/3)$ for different $k$ values, giving us $2, -1, -1$, where the eigenvalue 2 corresponds to the fully symmetric subspace. I'm establishing the mathematical equivalence between the two measurement schemes using trace formulas. I'm verifying that these POVM elements form a valid decomposition by checking that they sum to the identity across all measurement outcomes. I've verified that the projectors sum to identity, so now I need to compute the expectation value of the product $\beta_1\beta_2$. I'm factoring out the first projector, substituting the sum over $\beta_2$ with the observable $S^{2,3}$, and then expanding the projector in terms of Pauli matrices. Completing the calculation by summing over $\beta_1$, the terms with $\beta_1$ coefficients vanish while the $W$ terms survive and combine to give $\frac{1}{2}M_+$.

Now I'm expressing the expectation value of $\beta_1\beta_2$ in terms of the trace of $M_+$ with the three-copy density matrix, and since both cyclic permutations in $M_+$ have the same trace equal to $\text{Tr}[\rho^3]$, I can simplify this further.

Let me dig deeper into whether the sequential measurement actually projects onto eigenspaces of $M_+$. I need to work out the individual POVM elements that result from measuring first on systems 1 and 2, then on systems 2 and 3, with the first measurement outcome feeding into the second.

Computing the POVM elements...

Expanding the product of projectors... Continuing to expand the product and simplify using the properties of transpositions—I'm tracking how $(S^{12})^2 = \mathbb{1}$ and $S^{12}S^{23}S^{12} = W_{(123)}$ to collapse terms and identify which permutation operators survive in the final expression. I'm recognizing that the sum of the two transpositions can be rewritten using the total sum of all transpositions, so I'm substituting $T - S^{12}$ to simplify the expression and factor out common terms.

Now I'm seeing that the resulting POVM elements still contain $S^{12}$, which doesn't commute with everything in the group algebra, so the sequential measurement isn't actually equivalent to just measuring the eigenspaces of $M_+$. The product of the two outcomes does give us access to the expectation value of $M_+$, but the claim needs refinement—the sequential SWAP measurement and projecting onto $M_+$ aren't quite the same thing.

Let me work through this more carefully to show exactly what's true and what isn't. Actually, looking back at the variance calculation, I notice they're using the fact that $\beta_1^2 = \beta_2^2 = 1$, which means $(\beta_1\beta_2)^2 = 1$ as well, and this is what makes the variance formula work out to $1 - \mu_m^2$.

The key insight is that the sequential measurement produces a $\pm 1$ valued observable—the product $\phi = \beta_1\beta_2$ always equals $\pm 1$—and we're estimating its expectation value $\mu_3 = \langle\phi\rangle$. This expectation is actually $\text{Tr}[\rho^3]$ (or the transpose variant depending on measurement direction).

Now I'm checking whether this $\pm 1$ observable is actually $M_+/2$. The operator $M_+$ has eigenvalues of $2$ on the fully symmetric subspace and $-1$ on the mixed symmetry subspace, so scaling it by $1/2$ would give eigenvalues of $1$ and $-1/2$, which doesn't match.

So the sequential measurement observable isn't the same as projecting onto $M_+$ eigenspaces—the POVMs are different. But here's what matters: they produce the same expectation value on product states $\rho^{\otimes 3}$, since the weighted sum of the measurement outcomes equals $M_+/2$ when we average over the measurement results. This is actually what the user is trying to establish.

The key is to prove the identity $\sum \beta_1\beta_2 E_{(\beta_1,\beta_2)} = \frac{1}{2}(W_{(123)}+W_{(132)})$ rigorously, while being clear about what "equivalent" really means here—the measurements differ, but their expectation values align on these specific states.
````

这是一个非常好的问题，但严格来说这个等价性需要精确表述。让我给出完整的证明。

## 精确的数学陈述

**定理.** 对三拷贝空间 $\mathcal{H}^{\otimes 3}$ 上的态 $\rho^{\otimes 3}$，先对拷贝 (1,2) 做 SWAP 投影测量（结果 $\beta_1 = \pm 1$），再对拷贝 (2,3) 做 SWAP 投影测量（结果 $\beta_2 = \pm 1$），则乘积 $\beta_1\beta_2$ 的期望值满足：

$$\langle \beta_1\beta_2 \rangle = \frac{1}{2}\operatorname{Tr}\!\big[(W_{(123)} + W_{(132)})\,\rho^{\otimes 3}\big] = \operatorname{Tr}[\rho^3]$$

即顺序 SWAP 测量的乘积**等价于**测量 Hermitian 算子 $\frac{1}{2}M_+ = \frac{1}{2}(W_{(123)}+W_{(132)})$。

---

## 记号与设定

**SWAP 算子：** $S^{c,d}$ 交换拷贝 $c$ 和 $d$，即 $S^{1,2}|a,b,c\rangle = |b,a,c\rangle$，$S^{2,3}|a,b,c\rangle = |a,c,b\rangle$。

**循环置换与 SWAP 的关系：**

$$W_{(123)}|a,b,c\rangle = |c,a,b\rangle, \qquad W_{(132)}|a,b,c\rangle = |b,c,a\rangle$$

直接验证：

$$S^{1,2}S^{2,3}|a,b,c\rangle = S^{1,2}|a,c,b\rangle = |c,a,b\rangle = W_{(123)}|a,b,c\rangle$$

$$S^{2,3}S^{1,2}|a,b,c\rangle = S^{2,3}|b,a,c\rangle = |b,c,a\rangle = W_{(132)}|a,b,c\rangle$$

因此：

$$\boxed{W_{(123)} = S^{1,2}S^{2,3}, \qquad W_{(132)} = S^{2,3}S^{1,2}}$$

**投影算子：** SWAP 的本征值为 $\pm 1$，对应投影算子

$$\Pi^{c,d}_{\pm} = \frac{\mathbb{1} \pm S^{c,d}}{2}$$

满足 $(\Pi^{c,d}_\pm)^2 = \Pi^{c,d}_\pm$，$\Pi^{c,d}_+ + \Pi^{c,d}_- = \mathbb{1}$，$\Pi^{c,d}_+ - \Pi^{c,d}_- = S^{c,d}$。

---

## 证明

### 第一步：顺序测量的数学描述

先测 $S^{1,2}$，结果 $\beta_1$，态坍缩为 $\Pi^{1,2}_{\beta_1}\rho^{\otimes 3}\Pi^{1,2}_{\beta_1}$（未归一化）。

再对坍缩后的态测 $S^{2,3}$，结果 $\beta_2$。联合概率为：

$$p(\beta_1,\beta_2) = \operatorname{Tr}\!\big[\Pi^{2,3}_{\beta_2}\Pi^{1,2}_{\beta_1}\,\rho^{\otimes 3}\,\Pi^{1,2}_{\beta_1}\Pi^{2,3}_{\beta_2}\big]$$

利用迹的循环性：

$$p(\beta_1,\beta_2) = \operatorname{Tr}\!\big[\underbrace{\Pi^{1,2}_{\beta_1}\Pi^{2,3}_{\beta_2}\Pi^{1,2}_{\beta_1}}_{E_{(\beta_1,\beta_2)}}\;\rho^{\otimes 3}\big]$$

其中 $E_{(\beta_1,\beta_2)} = \Pi^{1,2}_{\beta_1}\Pi^{2,3}_{\beta_2}\Pi^{1,2}_{\beta_1}$ 是顺序测量的**有效 POVM 元**。

### 第二步：计算 $\sum_{\beta_1,\beta_2}\beta_1\beta_2\,E_{(\beta_1,\beta_2)}$

我们要计算的期望值是：

$$\langle\beta_1\beta_2\rangle = \sum_{\beta_1,\beta_2}\beta_1\beta_2\,\operatorname{Tr}[E_{(\beta_1,\beta_2)}\,\rho^{\otimes 3}] = \operatorname{Tr}\!\bigg[\bigg(\sum_{\beta_1,\beta_2}\beta_1\beta_2\,E_{(\beta_1,\beta_2)}\bigg)\rho^{\otimes 3}\bigg]$$

**先对 $\beta_2$ 求和：** 利用 $\sum_{\beta_2}\beta_2\Pi^{2,3}_{\beta_2} = \Pi^{2,3}_+ - \Pi^{2,3}_- = S^{2,3}$，

$$\sum_{\beta_2}\beta_2\,E_{(\beta_1,\beta_2)} = \Pi^{1,2}_{\beta_1}\,S^{2,3}\,\Pi^{1,2}_{\beta_1}$$

**展开投影算子：** 代入 $\Pi^{1,2}_{\beta_1} = \frac{1}{2}(\mathbb{1}+\beta_1 S^{1,2})$，

$$\Pi^{1,2}_{\beta_1}\,S^{2,3}\,\Pi^{1,2}_{\beta_1} = \frac{1}{4}(\mathbb{1}+\beta_1 S^{1,2})\,S^{2,3}\,(\mathbb{1}+\beta_1 S^{1,2})$$

展开四项（注意 $\beta_1^2 = 1$）：

$$= \frac{1}{4}\big(S^{2,3} + \beta_1 S^{1,2}S^{2,3} + \beta_1 S^{2,3}S^{1,2} + S^{1,2}S^{2,3}S^{1,2}\big)$$

### 第三步：识别置换算子

前两个已知：

$$S^{1,2}S^{2,3} = W_{(123)}, \qquad S^{2,3}S^{1,2} = W_{(132)}$$

第四项需要计算 $S^{1,2}S^{2,3}S^{1,2}$：

$$S^{1,2}S^{2,3}S^{1,2}|a,b,c\rangle = S^{1,2}S^{2,3}|b,a,c\rangle = S^{1,2}|b,c,a\rangle = |c,b,a\rangle$$

这是交换拷贝 1 和 3，即 $S^{1,2}S^{2,3}S^{1,2} = S^{1,3}$。（这也可以从共轭关系理解：$(12)(23)(12) = (13)$ 在 $S_3$ 中。）

代入：

$$\Pi^{1,2}_{\beta_1}\,S^{2,3}\,\Pi^{1,2}_{\beta_1} = \frac{1}{4}\big(S^{2,3} + \beta_1 W_{(123)} + \beta_1 W_{(132)} + S^{1,3}\big)$$

### 第四步：对 $\beta_1$ 求和

$$\sum_{\beta_1}\beta_1\cdot\frac{1}{4}\big(S^{2,3} + \beta_1 W_{(123)} + \beta_1 W_{(132)} + S^{1,3}\big)$$

$$= \frac{1}{4}\sum_{\beta_1=\pm 1}\big(\beta_1 S^{2,3} + \underbrace{\beta_1^2}_{=1} W_{(123)} + \underbrace{\beta_1^2}_{=1} W_{(132)} + \beta_1 S^{1,3}\big)$$

$\beta_1$ 的奇数次幂求和为零（$+1+(-1)=0$），偶数次幂求和为 2：

$$= \frac{1}{4}\big(0 + 2W_{(123)} + 2W_{(132)} + 0\big) = \frac{1}{2}\big(W_{(123)} + W_{(132)}\big)$$

$$\boxed{\sum_{\beta_1,\beta_2}\beta_1\beta_2\,E_{(\beta_1,\beta_2)} = \frac{1}{2}M_+ = \frac{1}{2}\big(W_{(123)} + W_{(132)}\big)}$$

因此：

$$\langle\beta_1\beta_2\rangle = \frac{1}{2}\operatorname{Tr}[M_+\,\rho^{\otimes 3}] = \frac{1}{2}\big(\operatorname{Tr}[\rho^3]+\operatorname{Tr}[\rho^3]\big) = \operatorname{Tr}[\rho^3] \qquad\blacksquare$$

---

## 重要澄清：等价性的精确含义

你的直觉方向是对的，但需要注意**这不是严格的投影测量等价**。

### 不等价之处

$W_{(123)}$ 是酉算子（不是 Hermitian），本征值为 $1, \omega, \omega^2$（$\omega = e^{2\pi i/3}$），不能直接做投影测量。Hermitian 化后 $M_+ = W_{(123)}+W_{(132)}$ 的本征值为：

| $S_3$ 不可约表示 | $W_{(123)}$ 本征值 | $M_+$ 本征值 |
|:---:|:---:|:---:|
| 平凡表示（全对称） | $1$ | $2$ |
| 标准表示（混合对称） | $\omega, \omega^2$ | $-1$ |

如果直接做 $M_+$ 的投影测量，结果只有两种：$+2$ 或 $-1$。

但顺序 SWAP 测量有**四种**结果 $(\beta_1,\beta_2)$，POVM 元为：

$$E_{(\beta_1,\beta_2)} = \frac{1}{8}\big(2\mathbb{1} + (2\beta_1-\beta_2)S^{1,2} + \beta_2(S^{2,3}+S^{1,3}) + \beta_1\beta_2 M_+\big)$$

这包含了 $S^{1,2}$ 项，它**不在**群代数的中心里。所以 POVM 元不仅仅是 $M_+$ 本征空间上的投影。

### 等价之处

虽然 POVM 不同，但对于**乘积态** $\rho^{\otimes 3}$，两者给出**相同的一阶统计量**：

$$\langle\beta_1\beta_2\rangle_{\text{sequential SWAP}} = \operatorname{Tr}\!\left[\frac{M_+}{2}\,\rho^{\otimes 3}\right]$$

物理上，$1/2$ 的因子来自于顺序测量无法区分 $W_{(123)}$ 和 $W_{(132)}$（它们互为逆元），投影测量对两个方向做了**自动对称化**。

### 二阶统计量的区别

方差却不同。顺序 SWAP 测量：

$$(\beta_1\beta_2)^2 = 1 \quad\text{（恒等）} \implies \operatorname{Var}(\beta_1\beta_2) = 1 - [\operatorname{Tr}(\rho^3)]^2$$

而 $M_+$ 的直接投影测量的方差为：

$$\operatorname{Var}(M_+) = \operatorname{Tr}[M_+^2\,\rho^{\otimes 3}] - (\operatorname{Tr}[M_+\,\rho^{\otimes 3}])^2$$

两者不等，说明顺序 SWAP 测量不是 $M_+$ 的投影测量。它是一个**更粗糙的 POVM**，恰好在一阶矩上与 $M_+/2$ 吻合。

### 总结

$$\underset{\text{顺序 SWAP 测量}}{\underbrace{S^{1,2}\text{ 测量} \to S^{2,3}\text{ 测量}}} \quad\xrightarrow{\text{乘积 }\beta_1\beta_2\text{ 的期望值}}\quad \underset{\text{循环置换算子}}{\underbrace{\frac{1}{2}\operatorname{Tr}[(W_{(123)}+W_{(132)})\,\rho^{\otimes 3}]}}$$

等价性成立的本质是：对 $\beta_1$ 求和时，所有**横截项**（transpositions $S^{1,2}, S^{2,3}, S^{1,3}$）因奇数幂而**精确抵消**，只留下**循环置换的对称组合**。这是 $S_3$ 群结构的直接后果。



## Prompt:
3/4/2026, 2:44:10 PM

我能否用这种级联Bell measurement实现(k次)完成$SWAP_{(1,\cdots,k)}$的均值估计？



## Response:
3/4/2026, 7:04:39 PM

````plaintext
Thought process: 验证了级联测量推广至k份拷贝的可行性与数学结构。

The user is asking whether the cascaded SWAP measurement scheme generalizes to arbitrary $k$: can we do sequential SWAP measurements on pairs $(1,2), (2,3), \ldots, (k-1,k)$ to estimate the expectation value of the cyclic permutation $W_{(1,2,\ldots,k)}$?

This is exactly what Gray et al. prove in their appendix for general $m$. Let me work through the proof carefully.

The claim would be: sequential ST measurements $S^{1,2}, S^{2,3}, \ldots, S^{k-1,k}$ with outcomes $\beta_1, \ldots, \beta_{k-1}$, then $\langle \prod_i \beta_i \rangle = 2^{2-k} \sum_\kappa \text{Tr}[S^\kappa \rho^{\otimes k}]$ where the sum is over $2^{k-2}$ cyclic permutations.
 
Now I need to trace through Gray et al.'s recursive approach, which defines how sequential SWAP measurements compose by tracking the projectors and density matrices through each measurement step.

Looking at the pattern for small values of $k$, I see that at each step the recursion introduces a factor of 2 in the number of terms, but the cyclic permutations that actually contribute follow a specific structure—for $k=3$ there are 2 distinct cyclic permutations, and for $k=4$ I'd expect 4, suggesting the count grows as $2^{k-2}$.

Now I'm working through the projective measurement formula more carefully. When I apply the $\beta$-weighted sum over the projectors for the $S^{j,j+1}$ measurement, I need to track how the eigenvalues $\beta = \pm 1$ contribute to the overall expression. So the difference simplifies to the anticommutator $\frac{1}{2}\{S^{j,j+1}, O\}$. Now I'm working through the product of all the $\beta$ operators, which involves composing these projection maps across the system and taking the trace over the full tensor product state.

The key insight is that when I apply the first map to the initial state, the swap operator commutes with the symmetric product state, so the anticommutator just gives me the swap acting on the state directly.

But wait—if the state is symmetric under permutations, then swapping qubits 1 and 2 leaves it unchanged, which would mean $O_1 = \rho^{\otimes k}$. That doesn't seem right for this construction.

Let me step back and reconsider what's actually happening here. The expectation value I'm trying to compute involves a product of $\beta$ operators, not just the state itself, so I need to be more careful about how the measurement and weighting interact. I'm reconsidering the approach using a recursive anti-commutator structure instead, defining a sequence of observables where each one builds on the previous by incorporating the next swap operator through an anti-commutator relation. Let me start fresh here. I'm working through the general case by building on the $k=3$ result. The key insight is that when I sum over the measurement outcomes weighted by their eigenvalues, I get a nested anti-commutator structure. Specifically, I'm showing that summing $\beta_1\beta_2$ times the product of projectors and swap operators gives me half the anti-commutator of the relevant swap operators, and I need to trace through how this pattern generalizes to arbitrary $k$. I'm working through the algebra of how sandwiching by projections and beta-weighted sums simplifies—it looks like the key insight is that $\Pi_+ A \Pi_+ - \Pi_- A \Pi_-$ reduces to $\frac{1}{2}(SA + AS)$, which I should verify by direct computation rather than relying on what I calculated before. I'm recognizing that the nested structure involves the innermost measurement on sites 2-3, which gives $S^{2,3}$, and then applying the outermost measurement on sites 1-2 to get $\frac{1}{2}\{S^{1,2}, S^{2,3}\}$, which matches the expected form. Now I need to generalize this pattern for arbitrary $k$ by working recursively from the innermost measurement outward. I'm setting up a recursive approach where I work from the innermost measurement outward. After summing over the last measurement outcome, I get the operator for that pair, then I can layer in the previous measurement by summing over its outcome weighted by its eigenvalue, and continue this process backward through all the measurements. I'm working through the nested anti-commutator structure and now need to figure out which permutations actually appear when I expand these expressions. Let me check the $k=3$ case to see the pattern. 's the cycle $(243)$. So $S^{2,3}S^{3,4}$ gives $(234)$ while $S^{3,4}S^{2,3}$ gives $(243)$ — these are different 3-cycles, and I need to verify which permutation each one actually represents.

Now I'm computing the anticommutator $\{S^{1,2}, W_{(234)} + W_{(243)}\}$ by expanding all four cross terms and working through what each operator does to the basis state $|a,b,c,d\rangle$. Starting with $S^{1,2}W_{(234)}$, which swaps positions 1 and 2 after applying the $(234)$ cycle, giving me $|d,a,b,c\rangle$.

For $W_{(234)}S^{1,2}$, I swap first then apply the cycle, getting $|b,d,a,c\rangle$, which corresponds to the permutation $(1,2,4,3)$. I need to verify this is correct by checking the cycle structure carefully. $S^{1,2}W_{(234)}$: first $S^{1,2}$ swaps the first two positions of the vector, then $W_{(234)}$ permutes it to give $(a_2,a_4,a_1,a_3)$. Let me check the other order too. I need to verify the cycle notation for this permutation. Let me trace through where each position's element goes: position 2 moves to position 1, position 4 to position 2, position 1 to position 3, and position 3 to position 4, giving me the cycle $(1,3,4,2)$. Now I'm checking whether this is a cyclic permutation in the standard sense.

Now I'm composing two operations: first applying $W_{(243)}$ which cycles the last three elements, then $S^{1,2}$ which swaps the first two positions. The net effect sends $(a_1,a_2,a_3,a_4)$ to $(a_3,a_1,a_4,a_2)$, and I'm working out the corresponding permutation in cycle notation. Let me work through what the cycle $(243)$ actually does to the positions. Position 2 receives the element from position 4, position 4 gets what was at position 3, and position 3 gets what was at position 2, leaving position 1 unchanged. So applying $W_{(243)}$ to $(a_2,a_1,a_3,a_4)$ gives $(a_2, a_4, a_1, a_3)$. Now I'm checking if this matches $W_{(234)}S^{1,2}$ or if I made an error in my cycle notation. Let me verify this by checking the composition: applying the cycle $(243)$ to the already-permuted sequence $(a_2, a_1, a_3, a_4)$ gives $(a_2, a_3, a_4, a_1)$, which is indeed the 4-cycle $(1234)$ inverted—or equivalently, the cycle $(1432)$. $, $\sigma(3)=4$, $\sigma(4)=1$. This is the cycle $(1,2,3,4) = W_{(1234)}$.

Wait, that would mean $W_{(243)}S^{1,2}$ and $S^{1,2}W_{(234)}$ both produce $W_{(1234)}$, which doesn't make sense. Let me recalculate $S^{1,2}W_{(234)}$ applied to the basis state to verify what I'm actually getting.

After applying $W_{(234)}$ first, then $S^{1,2}$, the net effect sends $(a_1,a_2,a_3,a_4)$ to $(a_4,a_1,a_2,a_3)$, which corresponds to the cycle $(1,4,3,2) = W_{(1432)}$. Now checking $W_{(243)}S^{1,2}$ in the same way, I'm getting $(a_2,a_3,a_4,a_1)$ as the output, so these are definitely different permutations.

I'm realizing I keep mixing up the convention for how permutations act on positions versus how they act on the quantum state indices. Let me nail down the definition explicitly: $W_\pi$ acting on a state applies $\pi^{-1}$ to the indices, so $W_\pi |a_1, a_2, \ldots, a_k\rangle = |a_{\pi^{-1}(1)}, a_{\pi^{-1}(2)}, \ldots, a_{\pi^{-1}(k)}\rangle$.

For the 4-cycle $(1234)$, the inverse is $(1432)$, which gives me $W_{(1234)}|a_1,a_2,a_3,a_4\rangle = |a_4, a_1, a_2, a_3\rangle$. Now I'm checking what happens with the reverse cycle $(1432)$ applied to the same state.

Looking at the composition of swap and cycle operators, I see that $S^{1,2}W_{(234)}$ produces the cyclic shift $(a_4,a_1,a_2,a_3)$, while $W_{(234)}S^{1,2}$ gives a different permutation $(a_2,a_4,a_1,a_3)$. Let me trace through which element lands in each position for this second case. So the same swap applied after the permutation gives $(a_3,a_1,a_4,a_2)$, which corresponds to the permutation $(1,2,4,3)$ in cycle notation. Now I need to check what happens when I apply the swap first instead. So for $k=4$, I'm getting the average of these four specific 4-cycles: $W_{(1234)}, W_{(1342)}, W_{(1243)}, W_{(1432)}$. I notice that while there are actually six possible 4-cycles in $S_4$, we're only capturing four of them here—and they don't seem to follow a simple pattern like cyclic shifts or forward/backward pairs.

Looking at what Gray et al. say, the cascaded SWAP measurements give us exactly $2^{m-2}$ cyclic permutations, which checks out: for $m=4$, that's $2^2 = 4$ cycles. So the cascaded approach samples $2^{k-2}$ out of the $(k-1)!$ total possible $k$-cycles.

The key insight is that we can't isolate $W_{(1,\ldots,k)}$ by itself—instead, the measurement gives us an average over these $2^{k-2}$ specific cycles, so we're estimating $\frac{1}{2^{k-2}}\sum_\kappa W_\kappa$ rather than the single cycle expectation.

For measuring $\text{Tr}[\rho^k]$, this doesn't matter because every $k$-cycle yields the same trace value on product states, so the average automatically gives us $\text{Tr}[\rho^k]$ regardless of which cycles we sample. But for quantities like negativity that depend on the specific cycle structure, this averaging becomes problematic.

When I consider the bipartite case where subsystem $A$ uses forward cycles and $B$ uses backward cycles, the effective observables are different on each subsystem—$A$ gets a uniform average over forward cycles while $B$ gets a uniform average over backward cycles. This mismatch is what allows us to probe the entanglement structure rather than just the purity.

The key insight is that the overall parity operator can be written as a sum over $2^{k-2}$ cyclic permutations with a normalization factor of $2^{2-k}$, and when we apply the partial transpose on $B$, it reverses the cycle order on that subsystem. So the negativity is computed by taking the trace of the density matrix with this transposed operator, which captures how the forward and backward cycles interfere.

Now I need to give a direct answer to the user's question: yes, $k-1$ sequential SWAP measurements do generalize to $k$ copies, but the result isn't just the single cycle $W_{(1,\ldots,k)}$ — instead you get a weighted sum over all $2^{k-2}$ possible $k$-cycles. For the purity trace, this distinction doesn't matter since all cycles contribute equally, but for partial transpose moments, the forward-backward symmetry is what makes the calculation work. }$ $k$-cycles, which for $\text{Tr}[\rho^k]$ estimation is equivalent. Let me prove this by induction.

I think the key theorem to prove is:

**Theorem.** Define the nested anti-commutator:

$\mathcal{A}_{k-1} = \frac{1}{2^{k-2}}\{S^{1,2}, \{S^{2,3}, \cdots \{S^{k-2,k-1}, S^{k-1,k}\}\cdots\}\}$

Then:
(a) $\mathcal{A}_{k-1} = \frac{1}{2^{k-2}}\sum_{\kappa} W_\kappa$ where the sum is over exactly $2^{k-2}$ distinct $k$-cycles in $S_k$.
(b) For any state $\rho$, $\text{Tr}[\mathcal{A}_{k-1}\,\rho^{\otimes k}] = \text{Tr}[\rho^k]$.

Now I'll establish this by induction, starting with the base cases: for $k=2$ the nested anti-commutator is just $S^{1,2}$, which corresponds to the single 2-cycle, and for $k=3$ it expands to a sum of the two 3-cycles weighted equally.

For the inductive step, I need to be careful about how the recursion works—at each stage we're adding a new pair of copies and introducing a new swap operator that couples the newest copy with the previous one, which extends the cycle structure in a controlled way. $\mathcal{B}_{n-1}$ acts as the identity on the new copy $n+1$, while $S^{n,n+1}$ only touches copies $n$ and $n+1$, so the anticommutator is well-defined. Let me work out the first few cases: $\mathcal{B}_1 = S^{1,2}$ is just the transposition $(12)$, and $\mathcal{B}_2$ expands to a sum of two permutation operators corresponding to the cycles $(132)$ and $(123)$. Continuing this pattern for $\mathcal{B}_3$...

Now I'm computing the anticommutator with $S^{3,4}$, which gives me four terms to evaluate. Since $W_{(123)}$ acts only on the first three copies, I need to figure out how the transposition $(34)$ composes with the 3-cycle $(123)$ — applying $(123)$ first sends $1 \to 2 \to 3 \to 1$, then $(34)$ acts on the result. to 3$.
Composition: $1\to 2, 2\to 3\to 4, 3\to 1, 4\to 3$. Wait, I need to track each element.

$(34)\circ(123)$: 
$1 \xrightarrow{(123)} 2 \xrightarrow{(34)} 2$
$2 \xrightarrow{(123)} 3 \xrightarrow{(34)} 4$
$3 \xrightarrow{(123)} 1 \xrightarrow{(34)} 1$
$4 \xrightarrow{(123)} 4 \xrightarrow{(34)} 3$

So $(34)(123) = (1,2,4,3)$, a 4-cycle. ✓

Now checking $(123)(34)$ by applying $(34)$ first, then $(123)$: $1$ stays at $1$ then goes to $2$, $2$ stays at $2$ then goes to $3$, $3$ goes to $4$ then stays at $4$, and $4$ goes to $3$ then goes to $1$. So this gives $(1,2,3,4)$, which is also a 4-cycle. to 1$. So $4\to 1$. And $3\to 4$. So: $\sigma = \{1\mapsto 2, 2\mapsto 3, 3\mapsto 4, 4\mapsto 1\}$. That's the cycle $(1234)$.

Hmm wait, I also need to check: $3 \xrightarrow{(34)} 4 \xrightarrow{(123)} 4$? $(123)$ fixes 4, so yes $3\to 4$. And $4\xrightarrow{(34)} 3 \xrightarrow{(123)} 1$. So $4\to 1$.

So $(123)(34) = (1,2,3,4)$. ✓

Now let me work through $(34)(132)$ by tracking where each element goes: 1 maps to 4, 2 maps to 1, 3 maps to 2, and 4 maps to 3, giving me the cycle $(1432)$. That's different from the previous composition, confirming these don't commute.

For $(132)(34)$, I'm starting the same process...

Actually, I notice a pattern emerging here. All the terms in the expansion are 4-cycles, and there are exactly four of them. This matches the formula $2^{4-2} = 4$, which is a good sign that I'm on the right track.

The key insight is that every term in this expansion is a $k$-cycle. Let me think about why that's true...

If I have an $n$-cycle $\sigma$ that fixes $n+1$, and I multiply it by the adjacent transposition $(n, n+1)$, then both $\tau\sigma$ and $\sigma\tau$ produce $(n+1)$-cycles. The transposition essentially absorbs the fixed point into the cycle, eliminating any fixed points and creating a single larger cycle.

Since $\sigma$ and $\tau$ don't commute (they both involve $n$), these give me two distinct $k$-cycles from each $(k-1)$-cycle. This means starting with $2^{k-3}$ $(k-1)$-cycles, I can generate $2^{k-2}$ $k$-cycles, and I can verify inductively that they're all distinct.

Now I'm moving to part (b) and need to examine the trace of a $k$-cycle.

For any $k$-cycle $\kappa$, when I compute $\text{Tr}[W_\kappa \rho^{\otimes k}]$, the cycle permutation acting on the tensor product traces out to $\text{Tr}[\rho^k]$ because the indices just get relabeled cyclically—the specific cycle structure doesn't matter. This means I can now evaluate $\text{Tr}[\mathcal{A}_{k-1}\rho^{\otimes k}]$ using this fact.

The calculation works out to $\frac{1}{2^{k-2}} \cdot 2^{k-2} \cdot \text{Tr}[\rho^k] = \text{Tr}[\rho^k]$, which confirms the result. Now I'm setting up the bipartite case where subsystem $A$ uses forward measurements through the sequence of consecutive pairs, while subsystem $B$ uses backward measurements, and I need to track how the cycles sum over each subsystem separately.

When I trace over the product state $\rho_{AB}^{\otimes k}$ with these different measurement orderings, the trace factorizes but the specific cycles $\kappa_A$ and $\kappa_B$ matter for mixed states—it's not determined solely by $k$.

For the partial transpose moment $\mu_k = \text{Tr}[(\rho_{AB}^{T_B})^k]$, I need the forward cycle on $A$ paired with the backward cycle on $B$, but the cascaded measurement sums over all cycle pairs. The key insight is that this sum still recovers $\mu_k$ because of how the trace behaves on the product state—I need to work out what each cycle pair actually computes.

When $\kappa$ and $\kappa'$ are both $k$-cycles acting on $\rho_{AB}^{\otimes k}$, the trace $\text{Tr}[(W_\kappa^A \otimes W_{\kappa'}^B)\rho_{AB}^{\otimes k}]$ depends on the specific pair, not just on $k$. For instance, the forward-forward cycle pair gives $\text{Tr}[\rho_{AB}^3]$, while other pairings give different values, and I need to see how these contributions combine to recover the partial transpose moment. So the forward-backward measurement scheme naturally produces the correct partial transpose moment through its anti-commutator structure, which symmetrizes the forward and backward cycles. For general $k$, the pattern extends with forward measurements on subsystem $A$ and backward measurements on subsystem $B$ arranged to capture the same symmetrized combination.

The key insight is that this approach generalizes to any number of copies, though instead of isolating a single $k$-cycle, you get a superposition of $2^{k-2}$ different $k$-cycles—but that's actually sufficient for estimating $\text{Tr}[\rho^k]$ since they all contribute equally to the trace.
````

## 可以，而且可以严格证明

核心结论是：$k-1$ 次级联 SWAP 测量得到的不是单独的 $W_{(1,2,\ldots,k)}$，而是 $2^{k-2}$ 个 $k$-cycle 的**均匀叠加**。但对估计 $\operatorname{Tr}[\rho^k]$ 来说，这完全等价。

---

## 定理

对 $\rho^{\otimes k}$ 依次做 $S^{1,2}, S^{2,3}, \ldots, S^{k-1,k}$ 的投影测量，结果为 $\beta_1, \ldots, \beta_{k-1} \in \{\pm 1\}$，则：

$$\left\langle\prod_{i=1}^{k-1}\beta_i\right\rangle = \operatorname{Tr}\!\big[\mathcal{A}_{k-1}\,\rho^{\otimes k}\big] = \operatorname{Tr}[\rho^k]$$

其中有效算子为嵌套反对易子：

$$\mathcal{A}_{k-1} = \frac{1}{2^{k-2}}\big\{S^{1,2},\,\{S^{2,3},\,\cdots\{S^{k-2,k-1},\,S^{k-1,k}\}\cdots\}\big\}$$

且 $\mathcal{A}_{k-1} = \frac{1}{2^{k-2}}\sum_{\kappa}W_\kappa$，求和遍历恰好 $2^{k-2}$ 个不同的 $k$-cycle。

---

## 证明

### 第一步：级联测量化为嵌套反对易子

**引理.** 对任意算子 $A$，SWAP 投影测量的 $\beta$-加权夹心为：

$$\sum_{\beta=\pm 1}\beta\;\Pi^{j,j+1}_\beta\,A\,\Pi^{j,j+1}_\beta = \frac{1}{2}\{S^{j,j+1},\,A\}$$

**引理证明.** 代入 $\Pi_\pm = \frac{1}{2}(\mathbb{1}\pm S)$：

$$\Pi_+ A\Pi_+ - \Pi_- A\Pi_- = \frac{1}{4}\big[(\mathbb{1}+S)A(\mathbb{1}+S) - (\mathbb{1}-S)A(\mathbb{1}-S)\big]$$

$$= \frac{1}{4}\big[A+SA+AS+SAS - A+SA+AS-SAS\big] = \frac{1}{2}(SA+AS) \qquad\square$$

对 $k-1$ 次级联测量，从最内层（最后测的 $\beta_{k-1}$）向外递归：

$$\sum_{\beta_{k-1}}\beta_{k-1}\,\Pi^{k-1,k}_{\beta_{k-1}} = S^{k-1,k}$$

$$\sum_{\beta_{k-2}}\beta_{k-2}\,\Pi^{k-2,k-1}_{\beta_{k-2}}\;S^{k-1,k}\;\Pi^{k-2,k-1}_{\beta_{k-2}} = \frac{1}{2}\{S^{k-2,k-1},\,S^{k-1,k}\}$$

$$\vdots$$

$$\sum_{\vec\beta}\prod_i\beta_i\;E_{\vec\beta} = \frac{1}{2^{k-2}}\big\{S^{1,2},\;\{S^{2,3},\;\cdots\{S^{k-2,k-1},\;S^{k-1,k}\}\cdots\}\big\} = \mathcal{A}_{k-1} \qquad\square$$

### 第二步：展开为 $k$-cycle 的求和

**定义递推.** 令 $\mathcal{B}_1 = S^{1,2}$（作用在拷贝 $\{1,2\}$ 上），

$$\mathcal{B}_n = \frac{1}{2}\{S^{n,n+1},\;\mathcal{B}_{n-1}\}$$

则 $\mathcal{A}_{k-1} = \mathcal{B}_{k-1}$。

**关键引理.** 若 $\sigma$ 是 $\{1,\ldots,n\}$ 上的 $n$-cycle（固定 $n+1$），$\tau = (n,\;n{+}1)$ 为相邻对换，则 $\tau\sigma$ 与 $\sigma\tau$ 均为 $\{1,\ldots,n+1\}$ 上的 $(n{+}1)$-cycle，且 $\tau\sigma \neq \sigma\tau$。

**引理证明.** 由于 $\sigma$ 是 $n$-cycle，$n$ 在 $\sigma$ 的轨道中，设 $\sigma(m)=n$。则：

- $\tau\sigma$：对 $n{+}1$，有 $\sigma(n{+}1)=n{+}1$，然后 $\tau(n{+}1)=n$，所以 $n{+}1$ 不再是不动点。对 $m$，有 $\sigma(m)=n$，然后 $\tau(n)=n{+}1$。所以 $\tau\sigma$ 把 $\{1,\ldots,n{+}1\}$ 全部连入一个轨道，即 $(n{+}1)$-cycle。
- 同理 $\sigma\tau$ 也是 $(n{+}1)$-cycle。
- $\tau\sigma \neq \sigma\tau$：因为 $\tau\sigma(n{+}1) = \tau(n{+}1) = n$，而 $\sigma\tau(n{+}1) = \sigma(n)$，后者是 $\sigma$ 轨道中 $n$ 的像，一般 $\neq n$。$\square$

**归纳证明.** 

$n=1$：$\mathcal{B}_1 = S^{1,2} = W_{(12)}$，1 个 2-cycle，$2^{1-1}=1$。✓

归纳步骤：设 $\mathcal{B}_{n-1} = \frac{1}{2^{n-2}}\sum_{i=1}^{2^{n-2}}W_{\kappa_i}$，其中 $\kappa_i$ 为 $2^{n-2}$ 个不同的 $n$-cycle。则：

$$\mathcal{B}_n = \frac{1}{2}\{S^{n,n+1},\,\mathcal{B}_{n-1}\} = \frac{1}{2^{n-1}}\sum_{i=1}^{2^{n-2}}\big(\underbrace{S^{n,n+1}W_{\kappa_i}}_{\text{new }(n+1)\text{-cycle}} + \underbrace{W_{\kappa_i}S^{n,n+1}}_{\text{another }(n+1)\text{-cycle}}\big)$$

由引理，每个 $n$-cycle $\kappa_i$ 产生 2 个不同的 $(n{+}1)$-cycle。

**不同 $\kappa_i$ 产生的 cycle 互不相同的证明**：若 $S^{n,n+1}W_{\kappa_i} = S^{n,n+1}W_{\kappa_j}$，则 $W_{\kappa_i}=W_{\kappa_j}$，矛盾。类似地排除其他重合情况。

因此 $\mathcal{B}_n = \frac{1}{2^{n-1}}\sum_{j=1}^{2^{n-1}}W_{\kappa'_j}$，恰好 $2^{n-1}$ 个不同的 $(n{+}1)$-cycle。$\square$

### 第三步：所有 $k$-cycle 给出相同的迹

**命题.** 对**任意** $k$-cycle $\kappa$，$\operatorname{Tr}[W_\kappa\,\rho^{\otimes k}] = \operatorname{Tr}[\rho^k]$。

**证明.** 设 $\kappa = (i_1,i_2,\ldots,i_k)$，则 $W_\kappa$ 将拷贝 $i_1$ 的内容送到拷贝 $i_2$ 的位置，以此类推。在计算基上：

$$\operatorname{Tr}[W_\kappa\,\rho^{\otimes k}] = \sum_{a_1,\ldots,a_k}\langle a_{i_1}|\rho|a_{i_2}\rangle\langle a_{i_2}|\rho|a_{i_3}\rangle\cdots\langle a_{i_k}|\rho|a_{i_1}\rangle$$

做变量替换 $b_1 = a_{i_1},\;b_2 = a_{i_2},\;\ldots,\;b_k = a_{i_k}$（只是哑指标重命名），得到：

$$= \sum_{b_1,\ldots,b_k}\langle b_1|\rho|b_2\rangle\langle b_2|\rho|b_3\rangle\cdots\langle b_k|\rho|b_1\rangle = \operatorname{Tr}[\rho^k]$$

与 $\kappa$ 的具体选取无关。$\square$

### 组合

$$\left\langle\prod_i\beta_i\right\rangle = \operatorname{Tr}[\mathcal{A}_{k-1}\,\rho^{\otimes k}] = \frac{1}{2^{k-2}}\sum_{\kappa}^{2^{k-2}}\underbrace{\operatorname{Tr}[W_\kappa\,\rho^{\otimes k}]}_{=\,\operatorname{Tr}[\rho^k]} = \operatorname{Tr}[\rho^k] \qquad\blacksquare$$

---

## 具体验证：$k=4$

$\mathcal{B}_3 = \frac{1}{4}\{S^{1,2},\,\{S^{2,3},\,S^{3,4}\}\}$

$$\{S^{2,3},\,S^{3,4}\} = \underbrace{(23)(34)}_{=(234)} + \underbrace{(34)(23)}_{=(243)} = W_{(234)}+W_{(243)}$$

$$\{S^{1,2},\,W_{(234)}+W_{(243)}\} = \underbrace{(12)(234)}_{=(1234)} + \underbrace{(234)(12)}_{=(1342)} + \underbrace{(12)(243)}_{=(1243)} + \underbrace{(243)(12)}_{=(1432)}$$

所以：

$$\mathcal{B}_3 = \frac{1}{4}\big(W_{(1234)}+W_{(1342)}+W_{(1243)}+W_{(1432)}\big)$$

恰好 $2^2=4$ 个 4-cycle，对 $\rho^{\otimes 4}$ 取迹后每项都给 $\operatorname{Tr}[\rho^4]$。✓

---

## 推广到 bipartite 的 partial transpose moment

对 $\rho_{AB}$，$A$ 做**正向**级联：$S_A^{1,2}\to S_A^{2,3}\to\cdots$，$B$ 做**反向**级联：$S_B^{k-1,k}\to S_B^{k-2,k-1}\to\cdots$

### $k=3$ 的情况

正向（$A$）：$\frac{1}{2}(W_{(123)}^A + W_{(132)}^A)$

反向（$B$）：$\frac{1}{2}\{S_B^{1,2},\,S_B^{2,3}\}$——但顺序反了！先测 $S_B^{2,3}$，再测 $S_B^{1,2}$。有效算子是：

$$\frac{1}{2}\{S_B^{2,3},\,S_B^{1,2}\} = \frac{1}{2}(W_{(123)}^B + W_{(132)}^B)$$

等等，反对易子是对称的！所以正向和反向给出**同样的** Hermitian 算子？

不是。**关键区别在联合测量时正反向的配对方式**。具体来说，$A$ 和 $B$ 在同一轮实验中对同一对拷贝做测量，$\beta$ 的乘积结构把它们绑在一起。由论文 appendix 的递推关系 (S2)：

$$(\mathbb{P}^k)^{T_B} = \frac{1}{2}\big(S_A^{k,k-1}\cdots S_A^{2,1}\;\otimes\;S_B^{2,1}\cdots S_B^{k,k-1} + \text{h.c.}\big) \cdot 2^{2-k}$$

$A$ 上正向连乘 $S_A^{1,2}S_A^{2,3}\cdots = W_{(1\cdots k)}^A$，$B$ 上反向连乘 $S_B^{k-1,k}\cdots S_B^{1,2} = W_{(k\cdots 1)}^B$。加上 h.c.（反对易子的对称化），所有 cycle 配对后对 $\rho_{AB}^{\otimes k}$ 取迹恰好给出：

$$\mu_k = \operatorname{Tr}[(\rho_{AB}^{T_B})^k]$$

因为对 $\rho_{AB}^{\otimes k}$，$A$ 上正向 $k$-cycle $\otimes$ $B$ 上反向 $k$-cycle 的迹恰好等于 partial transpose 的 $k$ 阶矩。

---

## 总结

| 级联测量 | 有效算子 | $k$-cycle 数 | 给出的物理量 |
|:---:|:---:|:---:|:---:|
| $k-1$ 次正向 SWAP | $\frac{1}{2^{k-2}}\sum_\kappa W_\kappa$ | $2^{k-2}$ 个 | $\operatorname{Tr}[\rho^k]$ |
| $A$ 正向 + $B$ 反向 | $(\mathbb{P}^k)^{T_B}$ | $2^{k-2}$ 对 | $\operatorname{Tr}[(\rho_{AB}^{T_B})^k]$ |

你得到的不是单个 $W_{(1,\ldots,k)}$，而是 $2^{k-2}$ 个 $k$-cycle 的均匀混合——但这 **恰好足够**，因为所有 $k$-cycle 对 $\rho^{\otimes k}$ 给出相同的迹。级联 SWAP 测量的"分辨率"不足以区分不同的 $k$-cycle（类似于 $k=3$ 时无法区分 $(123)$ 和 $(132)$），但对估计 $\operatorname{Tr}[\rho^k]$ 和 $\mu_k$ 来说，这个"缺陷"反而是无害的。



## Prompt:
3/4/2026, 3:56:33 PM

Let's return to the 3-copy example. In this example, we assume we can perform the projection operator between (12) and (23), i.e., the operator \Pi_{\pm}^{a,b}:=\frac{1 \pm S^{(ab)}}{2},(a,b) \in \{(1,2),(2,3)\}. However, note that if a copy is not a single-bit quantum state but an n-qubit quantum state. This required us to implement the projection $\frac{\mathbb{I}^{\otimes n} \pm \mathrm{SWAP}^{\otimes n}}{2}$. This is a highly non-local projection and shall be replaced by a pointwise SWAP projection $\frac{\left(\mathbb{I} \pm \mathrm{SWAP}\right)^{\otimes n}}{2}$. This will lead to a cross terms. How should we deal with this.



## Response:
3/4/2026, 4:03:36 PM

````plaintext
Thought process: Identified fundamental limitation of site-wise measurements versus global projections.

The user is asking a very important practical question. When we have an $n$-qubit system, the SWAP operator between two copies acts as $S^{(ab)} = \text{SWAP}^{\otimes n}$, which is a product of individual qubit SWAPs: $S^{(ab)} = \prod_{j=1}^n \Xi_j^{(ab)}$ where $\Xi_j^{(ab)}$ swaps qubit $j$ between copies $a$ and $b$.

The projection onto $\pm 1$ eigenspaces of $S^{(ab)}$ is $\Pi_{\pm}^{(ab)} = \frac{\mathbb{I}^{\otimes n} \pm \prod_j \Xi_j}{2}$.
 
Experimentally, we can only measure the individual SWAP operators $\Xi_j^{(ab)}$ at each site independently, getting outcomes $\beta_j \in \{+1, -1\}$. The product of these outcomes $\beta = \prod_j \beta_j$ directly gives us the eigenvalue of the full SWAP operator, so measuring each site separately and multiplying the results is actually equivalent to measuring the full SWAP—though I need to think through whether there's a subtlety I'm missing here. is more subtle. Let me reconsider.

The full SWAP between copies $a$ and $b$ on the $n$-qubit system is:
$$S^{(ab)} = \prod_{j=1}^n \Xi_j^{(ab)}$$

where $\Xi_j^{(ab)}$ swaps qubit $j$ between copies $a$ and $b$.

Now, $\Xi_j$ has eigenvalues $\pm 1$ (singlet/triplet). The full SWAP $S^{(ab)}$ also has eigenvalues $\pm 1$, with eigenvalue being the product of individual eigenvalues.

If we measure each $\Xi_j$ independently (site-wise ST measurement), we get outcomes $\beta_j$ for each site. The product $\beta = \prod_j \beta_j$ gives us the eigenvalue of the full SWAP.

But here's the key distinction: the projection operators differ fundamentally. The full SWAP projects onto $\Pi_{\pm}^{(ab)} = \frac{\mathbb{I} \pm S^{(ab)}}{2}$, while site-wise measurement projects independently at each site with $\prod_j \frac{\mathbb{I}_j \pm_j \Xi_j}{2}$. The site-wise approach is actually a finer measurement that yields more information than just the product outcome. However, the sequential measurement proof relies on projecting with the full SWAP operator, not the individual site projections, which creates a subtle difference in what we're actually measuring.

Let me look at how Gray et al. formulate this. They express the expectation value of sequential SWAP measurements as a sum over outcomes, where each outcome contributes weighted by the product of eigenvalues, and the state collapses through successive projections onto the measurement outcomes.

Now I'm seeing they actually discuss site-wise singlet-triplet measurements in their appendix—each $\Xi_j^{c,d}$ represents an ST measurement between spins at the same site but in different copies. The key distinction the user is pointing out is whether we measure the global SWAP operator as a single two-outcome measurement, or whether we perform individual site-wise measurements sequentially.

These give the same expectation value for a single measurement, but for sequential measurements like $S^{(12)}$ followed by $S^{(23)}$, the intermediate state collapse differs significantly. A global projection collapses the entire state to a symmetric or antisymmetric subspace across copies 1 and 2, whereas site-wise projections cause each site to independently collapse to its own symmetric/antisymmetric subspace—a much stronger constraint. The real question is whether the paper's treatment accounts for this distinction properly.

With site-wise measurements, I get individual outcomes $\{\beta_j^{(12)}\}$ and $\{\beta_j^{(23)}\}$ for each site across the two measurement rounds, and the final quantity becomes the product $\prod_j \beta_j^{(12)} \cdot \prod_j \beta_j^{(23)}$. Let me work through what the site-wise projector actually looks like for a given site $j$ and outcome $\beta_j$ between copies $a$ and $b$.

Now I'm setting up the expectation value for this product of outcomes across both sequential measurements, where the first measurement projects onto all the $\beta_j^{(12)}$ outcomes and the second onto all the $\beta_j^{(23)}$ outcomes.

Since the projectors commute across different sites and measurement rounds, I can use this commutativity to simplify the trace expression. the expectation factorizes over sites since the three copies are independent, giving me a product of single-site expectations. But wait—I need to be careful here because $\rho$ itself is an $n$-qubit state that could be entangled, so the factorization across sites isn't automatic just from the tensor product structure of the three copies.

Let me think about this more carefully using the approach from before. The key insight is that even though $\rho$ has entanglement within each copy, the three copies are completely independent of each other, so measurements on different copies commute. For the site-wise POVM elements corresponding to outcomes $\{\beta_j^{(12)}\}$ and $\{\beta_j^{(23)}\}$, I need to construct the effective measurement operator accounting for this structure.

The effective observable then sums over all possible outcome pairs, weighting each by the product of the measurement results from both copies, applied to the corresponding POVM element.

Now I'm factoring this sum over the second copy's outcomes by separating it into a product over individual sites, since each site's measurement operator acts independently on its own Hilbert space.

For the first copy's measurements, I need to evaluate how the product of individual measurement operators conjugates the full SWAP operator. The key insight is that these operators act on different subsystems, so I can analyze their commutation relations to simplify the expression. The product structure allows me to pull the sum outside, so each site's contribution becomes independent—I can sum over each $\beta_j$ separately and multiply the results together. Now I need to evaluate what happens at each individual site. each site $j$:

$$\sum_{\beta_j = \pm 1} \beta_j \cdot \pi_j^{(12)}(\beta_j) \Xi_j^{(23)} \pi_j^{(12)}(\beta_j) = \frac{1}{2}\{\Xi_j^{(12)}, \Xi_j^{(23)}\}$$

using the same lemma as before (applied to single-qubit SWAP $\Xi_j$).

So the full effective observable is:

$$\prod_{j=1}^n \frac{1}{2}\{\Xi_j^{(12)}, \Xi_j^{(23)}\}$$

Now, for a single qubit, $\Xi_j^{(12)}$ and $\Xi_j^{(23)}$ are

The anticommutator of these SWAP operators on the 3-copy space reduces to a sum of cyclic permutations: $\frac{1}{2}(W_{(123)}^{(j)} + W_{(132)}^{(j)})$ for each qubit $j$. This gives me the full effective observable as a product over all sites, but I need to check whether this matches the target form where the permutations act on the entire system rather than individual qubits.

When I expand the product of sums across all sites, I get $2^n$ different terms—one for each possible choice of forward or backward cyclic permutation at every site. But the target observable only has two terms: either all sites permute forward or all permute backward. These aren't equivalent, and the difference lies in all the cross terms where some sites go one way and others go the other way. So the first two terms give me $\frac{1}{4}M_+$, and the cross terms are the unwanted contributions. Now I need to figure out what happens when I trace over a mixed permutation where one site evolves forward and the other backward—this is getting at the heart of how these different orderings interfere with each other.

It turns out these cross terms aren't just noise; they're actually partial transpose moments for different bipartitions. When I compute the trace with the partial transpose on subsystem 2, the permutation reversal on that subsystem gives me exactly the negativity moment I'd expect. So the structure is telling me something about entanglement properties across different ways of splitting the system.

For the general $n$-qubit case, I'm working toward expressing the full measurement outcome in terms of these moment structures. Each term in the sum corresponds to choosing forward or backward cycles at each site, and for any given configuration, the trace simplifies to a partial transpose operation on the subsystem with backward cycles. So the full measurement outcome is an average over all $2^n$ possible cycle configurations.

Wait, I need to reconsider the boundary cases more carefully. When there are no backward cycles, I get $\text{Tr}[\rho^3]$, and when all sites have backward cycles, the full transpose also preserves the trace of the third power since transposition doesn't change eigenvalues—though I should be careful about whether we're working with real or complex matrices, since the full transpose of $\rho$ gives $\rho^*$ in the complex case. For a single site $j_0$, I get $\text{Tr}[(\rho^{T_{j_0}})^3]$. So putting this together, the site-wise sequential SWAP measurement gives me a sum over all subsets where I take the partial transpose and cube it. But wait, let me verify this makes sense—I should check whether my interpretation of the partition structure is correct here.

When I apply the partial transpose on subset $B$, it reverses the cyclic permutation on those indices, which means the trace of the cubed partial transpose on $B$ equals the trace of the cubed partial transpose on the complement $A$. So the sum can be written either way, and I'm noticing this symmetry suggests the expression is invariant under swapping which subset I transpose.

The real issue is that site-wise measurements are picking up a mixture of purity and negativity moments across all possible bipartitions. But looking at Gray et al.'s approach, they actually do use site-wise measurements—they measure SWAP operators at each site individually and multiply them together. The key is that they keep the measurement direction consistent across all sites within subsystem $A$, while flipping it for all sites in subsystem $B$. This directional control is what lets them isolate the specific entanglement moment they want. direction is determined by the ORDER of measurements: for $A$, they do $S^{1,2}_A$ then $S^{2,3}_A$ (forward), and for $B$, they do $S^{2,3}_B$ then $S^{1,2}_B$ (backward). 

But the user's point is: when measuring $S^{1,2}_A = \prod_{j \in A} \Xi_j^{(12)}$, if we measure each $\Xi_j^{(12)}$ individually (site-wise), the projection is $\prod_j \pi_j^{(12)}(\beta_j)$ which is different from $\Pi_{\pm}^{(12)} = \frac{\mathbb{I} \pm \prod_j \Xi_j^{(12)}}{2}$.

Right, so the protocol actually involves two sequential measurements per subsystem: for $A$, we first measure the $S^{1,2}$ operators site-by-site to get outcomes $\{\beta_j^{A,(12)}\}$, then measure $S^{2,3}$ site-by-site for outcomes $\{\beta_j^{A,(23)}\}$, while for $B$ we reverse the order, starting with $S^{2,3}$ then $S^{1,2}$. in B}$

Then $\mu_3$ is estimated as $\langle \prod_{j \in A} \beta_j^{A,(12)} \beta_j^{A,(23)} \cdot \prod_{j \in B} \beta_j^{B,(23)} \beta_j^{B,(12)} \rangle$.

Now, let me think about how this works when all measurements are site-wise.

Actually, let me reconsider the problem from scratch. The key issue is:

For the **first** sequential SWAP measurement (say $S^{1,2}$ on subsystem $A$), if we do it site-wise:
- We measure $\Xi_j^{(12)}$ for each $j \in A$, getting outcomes $\beta_j^{A,(12)}$
- The state collapses to $\prod_{j \in A} \pi_j^{(12)}(\beta_j) \rho^{\otimes 3} \prod_{j \in A} \pi_j^{(12)}(\beta_j)$

Then for the **second** measurement ($S^{2,3}$ on subsystem $A$), we measure each $\Xi_j^{(23)}$ site-wise on the collapsed state.

The crucial observation is: since operators at different sites commute and the site-wise projections factorize, the calculation for each subsystem factorizes over its sites. However, the state $\rho^{\otimes 3}$ is a product over copies, not over sites, so the expectation value of the product $\prod_j f_j$ doesn't factorize in the naive way.

The effective observable for subsystem $A$ is the product of single-site anticommutators $\{\Xi_j^{(12)}, \Xi_j^{(23)}\}$, and the same holds for subsystem $B$. Since the anticommutator is symmetric, reversing the measurement order doesn't change the single-site observable. I'm realizing that for a single qubit, the anticommutator structure is what matters here.

But wait—the directionality between forward and backward measurements only becomes relevant when we apply a global swap projection rather than doing site-wise measurements. Let me think through this more carefully, because something seems off about my reasoning when $A$ and $B$ are measured site-by-site and we're looking at their cross-terms.

Actually, looking at Gray et al.'s $m=3$ protocol for computing $\mu_3 = \text{Tr}[(\rho_{AB}^{T_B})^3]$, the structure is clearer: subsystem $A$ measures $\Xi_j^{(12)}$ then $\Xi_j^{(23)}$ sequentially across all sites, while subsystem $B$ reverses this order, measuring $\Xi_j^{(23)}$ first then $\Xi_j^{(12)}$—and this opposite ordering is what creates the asymmetry between forward and backward directions.

The key insight is that within each subsystem, the effective observable at each site becomes an anticommutator of the two measurement operators: for $A$ it's $\frac{1}{2}\{\Xi_j^{(12)}, \Xi_j^{(23)}\}$, which equals $\frac{1}{2}(W_{(123)}^{(j)} + W_{(132)}^{(j)})$, while for $B$ the same anticommutator structure applies but with the reversed measurement sequence built into the protocol.

Since the anticommutator is symmetric, the forward/backward distinction vanishes at the single-site level—both subsystems end up measuring the same effective observable regardless of their measurement order. This means the expectation value of the product of all outcomes across the entire system reduces to a trace formula involving the product of these anticommutators acting on the tripartite state.

When I expand this product over all possible subsets of sites, I get a uniform average over every possible bipartition of the system, not just the specific one I'm trying to measure. So the forward/backward trick fails at the site-wise level—I'd need either global SWAP measurements or a different approach to isolate the cross terms.

Let me reconsider whether the measurement ordering actually matters when the protocol interleaves measurements between the two regions. In Gray et al.'s scheme, they measure entropy between different copy pairs at different regions in a specific sequence, but if each measurement is applied site-by-site, the interleaving might break the separation I'm relying on.

Actually, since projectors at different sites commute regardless of when they're applied, the temporal ordering only affects measurements at the same site. For sites in region $A$, I'm measuring between copies 1-2 and then 2-3, which gives an anticommutator. For sites in region $B$, the order is reversed—I measure between copies 2-3 first, then 1-2—but the anticommutator $\{A,B\} = \{B,A\}$ is identical. So the forward/backward ordering doesn't actually create a difference between the two regions at the site level.

The key insight is that I can't avoid these cross terms by just looking at individual site measurements, but I can use the spatial structure—knowing which sites belong to $A$ versus $B$—to separate out the contributions and extract the information I need.

Actually, wait. I'm realizing the user's concern goes deeper than I initially grasped. The real issue is that Gray et al. aren't doing site-wise measurements at all—they're performing global SWAP measurements. When they measure the singlet-triplet basis at each site, they're projecting onto the global $\Pi_{\pm}^{(ab)}$ operator, not individual projectors, which is what actually lets them extract the direction information cleanly.

But then I'm reading their actual protocol more carefully, and they do explicitly describe site-wise ST measurements between different copies at the same location. So the measurement is local to each site, yet they're using the global projector in their theoretical analysis. I think the key is that these site-wise measurements collectively implement the global projection, and that's where the direction information comes from. measure all $\Xi_j^{(12)}$ independently and get outcomes $\beta_j$, the product $\beta = \prod_j \beta_j$ gives you the eigenvalue of the global SWAP. But the intermediate state collapse IS different from the global $\Pi_\beta$ projection.

However, in equation (S1), the key identity is:

$$\langle S_X^{2,3} \circ S_X^{1,2} \rangle = \frac{1}{2}[\text{Tr}[S_X^{1,2}S_X^{2,3}\rho^{\otimes 3}] + \text{Tr}[S_X^{2,3}S_X^{1,2}\rho^{\otimes 3}]]$$

And this was derived using the global $\Pi_\pm$ projection. If we instead use site-wise projections, we get different results with cross terms appearing.

So there's actually a real gap here—the paper's derivation assumes global SWAP projections, but experimentally you're doing site-wise measurements. In a quantum dot setup, measuring each pair gives you the individual $\Xi_j^{c,d}$ eigenvalues, and their product recovers the global SWAP eigenvalue, but the state collapses locally at each site rather than globally. The crucial question is whether this distinction between site-wise and global collapse affects the final observable. the protocol for system $X$ is:
1. Measure all $\Xi_j^{(12)}$ for $j \in X$ (site-wise, outcomes $\beta_j^{(1)}$)  
2. Measure all $\Xi_j^{(23)}$ for $j \in X$ (site-wise, outcomes $\beta_j^{(2)}$)

And we compute $\prod_j \beta_j^{(1)} \cdot \prod_j \beta_j^{(2)}$.

The effective observable is (following the calculation I did above):

$$\prod_{j \in X} \frac{1}{2}(W_{(123)}^{(j)} + W_{(132)}^{(j)})$$

Expanded:
$$\frac{1}{2^{|X|}} \sum_{S \subseteq X} \left(\prod_{j \in S} W_{(123)}^{(j)}\right)\left(\prod_{j \in X \setminus S} W_{(132)}^{(j)}\right)$$

Now I'm computing the expectation value by taking the trace over the three-copy state, where each subset $S$ contributes a term with the $(123)$ permutation applied to sites in $S$ and the $(132)$ permutation to the remaining sites.

The issue is that for most subsets $S$, these cross terms give $\text{Tr}[(\rho^{T_{X \setminus S}})^3]$ rather than $\text{Tr}[\rho^3]$, which are genuinely different unless $\rho$ has special structure. Only the extreme cases where $S = X$ or $S = \emptyset$ recover the original $\text{Tr}[\rho^3]$, so these unwanted contributions are a real obstacle to isolating the quantity we want.

Let me explore how to work around this using the site-wise measurement outcomes we actually have access to. Instead of just multiplying the individual site estimates together, I could introduce a correction function that uses the full outcome vectors to suppress or cancel these cross-term contributions.

The key insight is that from a single round we get 2n bits of data—the outcomes from both measurement settings at each site—and their product expectation captures a mixture of all the bipartition moments. The challenge is whether I can isolate just the $\text{Tr}[\rho^3]$ term from this mixture.

At each site, the effective observable is a superposition of two permutation terms that we can't distinguish individually, but maybe by looking at different combinations of the outcomes—like squaring some of them—I can construct a linear combination that picks out only the term I want.

However, when I try this approach, squaring the first measurement outcomes just gives me back the second measurement's eigenvalue, which corresponds to $\text{Tr}[\rho^2]$ rather than $\text{Tr}[\rho^3]$. The fundamental problem is that the site-wise sequential SWAP measurement produces an effective operator that's a mixture of two permutation terms, and I can't decompose this mixture to extract just one of them.

I'm considering whether cross terms might be negligible for weakly correlated states, or whether I can use measurements of partial transposes in different bipartitions to correct for these cross terms. The key realization is that the site-wise measurement doesn't just give me the product of individual outcomes—there's additional structure I might be able to exploit.

Actually, I think I can construct more sophisticated estimators from the full set of individual site outcomes. By selecting different subsets of sites and computing products of their measurement outcomes, I can access expectation values that involve products of the Weyl operators across those subsets, which should help me disentangle the cross terms from the genuine purity information.

But wait—I need to be careful here. Once the measurements are performed on all sites, the outcomes have already collapsed the state, so I can't selectively condition on subsets after the fact. Let me reconsider the structure of the measurement itself. The effective POVM element for a given pair of outcomes across all sites should be the product of the individual projectors at each site, where each site contributes based on its two measurement outcomes. The full POVM element factors across sites since operators at different sites commute, and I can express the probability of measurement outcomes as a trace over the product of these local POVM elements acting on the tripartite state.

Now I'm computing the expectation value of an arbitrary function of the outcomes by summing over all possible measurement results weighted by their probabilities, then rewriting this as a trace where the function gets incorporated into the operator structure.

When the function factorizes across qubits, the effective observable also factorizes nicely, allowing me to compute the expectation as a product of single-qubit contributions. I'm now looking at the specific case where the function is just the product of the two measurement outcomes.

But I'm wondering whether non-factorizable functions could work too—like if I multiply that product by some additional function that depends on all the first measurement outcomes. This is getting messier, and I'm trying to figure out if there's a strategic choice of function that could project onto something useful.

With the standard choice where $f$ is just the product of pairs, the effective observable becomes a product of those weighted sums across all sites. But that's not quite the same as taking the weighted sum of the two full products—there are cross terms appearing that don't match what I want. Let me work out exactly how much they differ.

Now I'm wondering if I can choose a different post-processing function to cancel out these cross terms entirely. The POVM measurements themselves are fixed by the sequential measurement structure, but the classical post-processing is something I have control over. For a general post-processing function, the effective observable would be a sum over all possible measurement outcomes weighted by that function.

The key insight is understanding what operators the single-site POVM elements can actually span. With four possible outcomes at each site, I get four POVM elements that live in an 8-dimensional operator space, so they only span a 4-dimensional subspace.

Let me work out the explicit form of these POVM elements for a single qubit by computing the product of the swap-based projections directly. Continuing to expand the product by distributing the final term, collecting like terms, and simplifying to get the final result. Now I'm substituting these products back into the expression and simplifying to get the final form of the matrix exponential, which factors nicely into a combination of identity, transposition operators, and the cyclic permutation terms. = W_{(123)} + W_{(132)}$.

Now, for general post-processing $f(\beta^{(1)}, \beta^{(2)})$:

$\sum_{\beta^{(1)},\beta^{(2)}} f(\beta^{(1)},\beta^{(2)}) e(\beta^{(1)}, \beta^{(2)}) = \frac{1}{8}[2f_{00}\mathbb{I} + 2f_{10}\Xi^{(12)} + f_{01}(\Xi^{(23)} + \Xi^{(13)}) + f_{11}M_+]$

where $f_{ab} = \sum_{\beta^{(1)},\beta^{(2)}} (\beta^{(1)})^a (\beta^{(2)})^b f(\beta^{(1)},\beta^{(2)})$.

Testing with $f = \beta^{(1)}\beta^{(2)}$ gives $f_{11} = 4$ while the others vanish, yielding an effective observable of $\frac{1}{2}M_+$, which checks out. For a single qubit, the anticommutator relation $\{\Xi^{(12)}, \Xi^{(23)}\} = M_+$ means cross terms don't appear, but they emerge for multiple qubits in the product $\prod_j \frac{1}{2}M$.

The key question is whether we can construct a post-processing function from individual site outcomes that recovers the global observable $\frac{1}{2}(W_{(123)} + W_{(132)})$ rather than just a product of local $M_+^{(j)}$ terms.

Now I'm working out how site-specific post-processing weights map to effective local observables—each site contributes a weighted combination of identity, parity operators, and the local $M_+$ term, and when we multiply these across all sites, the total effective observable emerges from the product structure.

The challenge is that we need this product to equal a sum of two distinct products (the two different three-cycle orderings), but a product of single-site linear combinations can't naturally decompose into such a sum unless the weights are very carefully chosen—in particular, if each site has both an $M_+$ component and an identity component, the product will expand into $2^N$ terms, which is far more than the two terms we're targeting.

The core issue is that $M_+$ itself is fundamentally a sum of product operators rather than a product operator, so any measurement scheme that produces products of single-site observables can never directly yield $M_+$ as an effective observable.

However, if I allow the post-processing function to be non-factorizable across sites—meaning it can correlate the outcomes from different sites in a way that doesn't decompose into independent site-wise operations—then I can construct non-product effective observables. The effective observable would be built by summing over all possible outcome pairs weighted by this correlated post-processing function, where each term involves products of single-site POVM elements. Since the POVM elements themselves span a limited subspace of single-site operators, the question becomes whether this subspace is rich enough to approximate or construct $M_+$ through such non-product post-processing. effective observables form the tensor product of these subspaces.

For a single qubit, the 4 POVM elements span the 4-dimensional space $\text{span}\{\mathbb{I}, \Xi^{(12)}, \Xi^{(23)}+\Xi^{(13)}, M_+\}$.

So for $n$ qubits, the achievable effective observables are in:

$$\bigotimes_{j=1}^n \text{span}\{\mathbb{I}_j, \Xi_j^{(12)}, \Xi_j^{(23)}+\Xi_j^{(13)}, M_+^{(j)}\}$$

This is a $4^n$-dimensional subspace. Now I need to check whether the product $\prod_j W_{(123)}^{(j)} + \prod_j W_{(132)}^{(j)}$ can be expressed within this space. I can decompose each permutation operator as a linear combination of $M_+^{(j)}$ and $M_-^{(j)}$, then expand the products to see if they fit the tensor product structure. Expanding out the second permutation and then combining the two to isolate the symmetric component involving the product of the positive operators.

Now I'm checking whether the negative operator can be expressed within the achievable space, and I'm finding that it decomposes as a commutator of the two basis operators.

Looking at the structure of the $S_3$ group algebra on the three-qubit system, I see it has six basis elements corresponding to the group's permutations, and the achievable space is spanned by the identity, two of the transpositions, their sum, and the symmetric combinations of the two 3-cycles.

The key insight is that the achievable space only contains symmetric combinations of the 3-cycles and the difference of transpositions, while the missing directions are the antisymmetric combinations—specifically $\Xi^{(23)} - \Xi^{(13)}$ and $W_{(123)} - W_{(132)}$. This means $M_-^{(j)}$ cannot be achieved through site-wise sequential SWAP measurements, which breaks the ability to implement the global $M_+$ operator.

So I'm realizing that extracting $\operatorname{Tr}[\rho^3]$ exactly from these measurements should be impossible—but Gray et al. claim to do exactly this for the partial transpose. Let me reconsider their protocol more carefully, since they describe measuring forward and backward sequences of adjacent swaps between neighboring copies.

The key insight is that these swaps operate across copies, not individual sites. When they measure $S_A^{c,c+1}$, they're applying a product of single-site SWAP operations simultaneously across all sites in region $A$, and the global outcome is the product of individual site outcomes. Now I need to figure out whether they're projecting onto eigenspaces of this global operator or measuring something else entirely.

Looking at their proof, they use global projectors onto the $\pm 1$ eigenspaces, but their experimental setup describes measuring individual site swaps and multiplying the results. These give different outcomes when there are correlations between sites, which is exactly what the user is pointing out. The discrepancy suggests their theoretical analysis assumes perfect global measurements while the actual implementation is site-wise, potentially introducing errors or cross-terms that aren't accounted for in the proof. , wait. Let me re-read (S1) more carefully:

"We first perform a sequential set of ST-measurements on copies (1, 2), with outcome β₁ and then do the same measurement on copies (2, 3), with outcome β₂."

Here β₁ and β₂ are scalar outcomes, which for the multi-site case would be β₁ = ∏_j β_{1,j} and β₂ = ∏_j β_{2,j}. They then use the global projectors.

But physically, the site-wise measurement projects onto a product of local projectors, while the global measurement uses a different form. These are fundamentally different—the site-wise measurement is actually a refinement of the global one.

Now looking at how they compute the expectation value in (S1), they're summing over both outcomes and tracing through the product of projectors acting on the three-copy state. If they're using global projectors instead of site-wise ones, this changes the entire calculation.

I think the user has spotted a real inconsistency in how the paper presents the measurement model. The site-wise approach introduces cross terms that don't appear in the global case. There are a couple of ways to resolve this: either the paper actually intends for global SWAP measurements to be performed on the full subsystem as a single measurement, or they need to account for the cross terms that arise from site-wise measurements using techniques like Möbius inversion to extract the global information from multiple measurement rounds.

Alternatively, for product states the cross terms don't cause problems since they reduce to the same values anyway, and for weakly correlated states they're just small corrections. But there's also an interesting point that Zhou et al.'s single-copy approach sidesteps this issue entirely by avoiding SWAP measurements altogether and using random unitaries instead.

Now I'm working through whether the Gray et al. proof actually holds up for global SWAP measurements in the many-body case, particularly when projecting onto the global swap operator rather than site-wise projections.

The key insight is that the global projection onto the symmetric subspace between copies acts non-locally across all sites simultaneously, which is what makes the proof yield the exact $\text{Tr}[\rho^3]$ result. But this global measurement is experimentally impractical, whereas site-wise projections are more feasible—though they introduce cross terms from the sequential measurement structure that complicate the final expression.

I can formalize these cross terms and express the result as a sum over all possible bipartitions, then show how this could be inverted using a Möbius-like inversion if we had measurements from every possible grouping. Zhou et al.'s approach with random unitaries and virtual copies elegantly sidesteps this entire issue.

Actually, I'm realizing the cross-term problem isn't unique to the bipartite case—it shows up whenever you're measuring $\text{Tr}[\rho^3]$ on any multi-qubit system, even without the bipartite structure. The fundamental issue is that site-wise measurements can't capture the global symmetry projection cleanly.

Now let me work through the sequential SWAP measurement setup carefully. I have an $n$-qubit state $\rho$ and three copies $\rho^{\otimes 3}$, and I'm performing site-wise POVMs: first measuring the SWAP between copies 1 and 2 at each qubit location, then measuring the SWAP between copies 2 and 3 at each location.

The key is getting the order right—all the first measurements complete before any second measurements begin. So the POVM element for a given sequence of outcomes is the product of the second-step projectors applied first, followed by the product of the first-step projectors, all acting on the initial three-copy state.

Since measurements at different sites commute with each other, and even measurements from different steps commute when they act on different sites, I can reorganize this into a product over sites where each site's first and second measurements are grouped together.

Now I'm computing the expectation value of the product of all the measurement outcomes by taking the trace over all possible measurement results at each site, weighted by the corresponding projectors. I'm expanding the product over all subsets $S$ of the indices, where each subset determines whether we apply the forward or reverse permutation at that site. For a given subset $S$, the trace evaluates to the third power of the density matrix with partial transpose applied over the complement of $S$. Let me double-check this for the case where $S$ contains all indices—that should give us all forward permutations.

Now I'm verifying the formula works for specific cases, like when only one site has the reverse permutation while all others use the forward one, and checking whether this matches the partial transpose structure I expect. So for qubit 2, the permutation $W_{(132)}^{(2)}$ cycles the copies as 1 → 3 → 2 → 1. Now I'm setting up the trace calculation by expanding it in terms of basis states and density matrix elements, tracking how each qubit's permutation acts on the three copies.

Actually, I'm realizing there's a cleaner approach using the standard partial transpose identity. When I partition the qubits into subsystem $A$ using the forward cycle and subsystem $B$ using the backward cycle, the trace simplifies to $\text{Tr}[(\rho_{AB}^{T_B})^3]$. For the general case where $A = S$ and $B = \bar{S}$, I can express this as a product of permutation operators over the respective subsystems.

Now I'm summing over all possible bipartitions and recognizing that the sum becomes $\frac{1}{2^n} \sum_{B \subseteq [n]} \text{Tr}[(\rho^{T_B})^3]$ after relabeling. The key insight is that there's a symmetry here—the third moment of the partial transpose is the same whether I transpose over subsystem $B$ or its complement $B^c$. So the traces are equal across the two partitions, which means the sum has a symmetry I can exploit—I can restrict the sum to partitions of size at most $n/2$ and double-count, though I need to be careful about the boundary cases where $|B| = n/2$ and the trivial partitions.

The real insight is that measuring individual sites gives me a weighted average over all possible partial transpose moments, and I can use the specific outcomes at each site to isolate particular bipartitions rather than averaging over all of them.

Since I know $\beta_j^{(1)}$ and $\beta_j^{(2)}$ separately, I should explore whether non-multiplicative functions of these pairs can extract different operators beyond what the fixed POVM structure allows. The achievable single-site operators are constrained to a specific span determined by the moments of the measurement function with respect to these two parameters. }, \beta_j^{(2)})$:

- $f_{00} = \sum_{\beta^{(1)},\beta^{(2)}} f(\beta^{(1)},\beta^{(2)})$ → coefficient of $\mathbb{I}$
- $f_{10} = \sum \beta^{(1)} f$ → coefficient of $\Xi^{(12)}$  
- $f_{01} = \sum \beta^{(2)} f$ → coefficient of $\Xi^{(23)}+\Xi^{(13)}$
- $f_{11} = \sum \beta^{(1)}\beta^{(2)} f$ → coefficient of $M_+$

We need $M_-^{(j)} = W_{(123)}^{(j)} - W_{(132)}^{(j)}$ to break the symmetry, but this lies outside what we can actually achieve through post-processing.

The core issue is that site-wise sequential SWAP measurements fundamentally cannot distinguish forward from backward cycles at any individual site, so no combination of single-site post-processing—whether product-based or summed—can ever produce an operator sensitive to this asymmetry. This means we're stuck: we cannot isolate $W_{(123)}$ from $W_{(132)}$ globally.

For measuring $\text{Tr}[\rho^3]$ specifically, where we want $W_{(123)} + W_{(132)}$, the answer involves...

Generating the formula... this gives me the effective observable when measuring only the subset $T$. The full observable involves summing over all possible measurement outcomes at the unmeasured sites, which effectively marginalizes them out of the calculation. The second product vanishes to identity due to POVM normalization, leaving me with an expectation value that's just a trace over the product of $M_+^{(j)}/2$ operators at the measured sites acting on the tripartite state. This is still structured as a product of measurements at sites in $T$ with identity elsewhere.

When $T$ includes all sites, I get cross terms from the full product. For a single site measurement, I need to carefully track how $M_+^{(j)}$ acts on qubit $j$ across the three copies while the trace contracts over the full state. = \text{Tr}[\rho^{\otimes 3} W_{(123)}^{(j)}]$, and since $W_{(123)}^{(j)}$ only permutes copies of qubit $j$ while leaving others alone, I need to think about how this trace decomposes for an entangled state—it's not as simple as factoring into separate traces for each qubit. unless the qubit is unentangled from the rest of the system. Now I'm ready to write up a clear solution that addresses the core issue: the product of expectation values doesn't equal the expectation value of the product, then walks through the expansion in terms of bipartition moments, explains why classical post-processing won't help since we can't access the negative eigenvalue projector, and outlines the viable approaches like global SWAP measurements or the virtual copy method from Zhou et al.
````

## 问题的精确定位

你发现了一个非常深刻的问题。让我精确展示矛盾所在，然后分析可能的出路。

### 两种不同的投影

对 $n$-qubit 态 $\rho$ 的三拷贝 $\rho^{\otimes 3}$，拷贝 $(a,b)$ 之间的全局 SWAP 是

$$S^{(ab)} = \prod_{j=1}^n \Xi_j^{(ab)}$$

其中 $\Xi_j^{(ab)} = \frac{1}{2}(\mathbb{I}_j + \boldsymbol{\sigma}_{j}^{(a)} \cdot \boldsymbol{\sigma}_{j}^{(b)})$ 交换第 $j$ 个 qubit 在拷贝 $a,b$ 之间。

**全局 SWAP 投影**（Gray et al. 证明中使用的）：

$$\Pi_{\pm}^{(ab)} = \frac{\mathbb{I}^{\otimes n} \pm \prod_{j} \Xi_j^{(ab)}}{2}$$

这是一个**高度非局域的**两结果投影。

**逐点 ST 投影**（实验中实际执行的）：

$$\widetilde{\Pi}_{\vec{\beta}}^{(ab)} = \prod_{j=1}^n \frac{\mathbb{I}_j + \beta_j \Xi_j^{(ab)}}{2}$$

这是 $2^n$ 个结果的乘积投影。关键不等式：

$$\boxed{\frac{\mathbb{I}^{\otimes n} + \prod_j \Xi_j}{2} \;\neq\; \prod_j \frac{\mathbb{I}_j + \Xi_j}{2}}$$

右边展开后多出所有**交叉项**：

$$\prod_j \frac{\mathbb{I}_j + \Xi_j}{2} = \frac{1}{2^n}\sum_{T \subseteq [n]}\prod_{j \in T}\Xi_j$$

而左边只有 $T = \emptyset$ 和 $T = [n]$ 两项。

---

## 对级联测量的影响

### 逐点级联测量的有效算子

对每个格点 $j$ **独立**做级联 ST 测量（先 $\Xi_j^{(12)}$ 结果 $\beta_j^{(1)}$，再 $\Xi_j^{(23)}$ 结果 $\beta_j^{(2)}$），由于不同格点上的算子两两对易，有效 POVM 元**严格按格点因子化**：

$$E_{\vec{\beta}^{(1)},\vec{\beta}^{(2)}} = \prod_{j=1}^n \underbrace{\pi_j^{(12)}(\beta_j^{(1)})\;\pi_j^{(23)}(\beta_j^{(2)})\;\pi_j^{(12)}(\beta_j^{(1)})}_{e_j(\beta_j^{(1)},\beta_j^{(2)})}$$

计算 $\prod_j \beta_j^{(1)}\beta_j^{(2)}$ 的期望值时，对每个格点独立求和，由之前证明的引理 $\sum_\beta \beta\,\pi_\beta\,A\,\pi_\beta = \frac{1}{2}\{S,A\}$：

$$\sum_{\beta_j^{(1)},\beta_j^{(2)}} \beta_j^{(1)}\beta_j^{(2)}\;e_j = \frac{1}{2}\{\Xi_j^{(12)},\;\Xi_j^{(23)}\} = \frac{1}{2}\big(W_{(123)}^{(j)} + W_{(132)}^{(j)}\big)$$

因此逐点级联测量的有效算子是：

$$\boxed{\mathcal{O}_{\text{site-wise}} = \prod_{j=1}^n \frac{1}{2}\Big(W_{(123)}^{(j)} + W_{(132)}^{(j)}\Big)}$$

### 展开：product of sums ≠ sum of products

这是**和的乘积**，而我们想要的是**乘积的和**：

$$\frac{1}{2}M_+ = \frac{1}{2}\Big(\prod_j W_{(123)}^{(j)} + \prod_j W_{(132)}^{(j)}\Big)$$

展开乘积：

$$\mathcal{O}_{\text{site-wise}} = \frac{1}{2^n}\sum_{S \subseteq [n]} \bigg(\prod_{j \in S}W_{(123)}^{(j)}\bigg)\bigg(\prod_{j \notin S}W_{(132)}^{(j)}\bigg)$$

共有 $2^n$ 项。其中仅 $S = [n]$ 和 $S = \emptyset$ 是我们想要的，其余 $2^n - 2$ 项都是**交叉项**。

### 交叉项的物理意义

每个子集 $S$ 对应一种 qubit 的二分：格点 $S$ 上正向循环，格点 $\bar{S} = [n] \setminus S$ 上逆向循环。对 $\rho^{\otimes 3}$ 取迹：

$$\operatorname{Tr}\bigg[\bigg(\prod_{j \in S}W_{(123)}^{(j)}\bigg)\bigg(\prod_{j \in \bar{S}}W_{(132)}^{(j)}\bigg)\rho^{\otimes 3}\bigg] = \operatorname{Tr}\!\big[(\rho^{T_{\bar{S}}})^3\big]$$

其中 $T_{\bar{S}}$ 表示对子集 $\bar{S}$ 做 partial transpose。

因此逐点级联测量给出的是**所有可能二分方式的三阶 partial transpose moment 的均匀平均**：

$$\boxed{\Big\langle\prod_j \beta_j^{(1)}\beta_j^{(2)}\Big\rangle = \frac{1}{2^n}\sum_{B \subseteq [n]}\operatorname{Tr}\!\big[(\rho^{T_B})^3\big]}$$

其中 $B = \emptyset$ 和 $B = [n]$ 两项给出 $\operatorname{Tr}[\rho^3]$，其余项是各种二分的 negativity moment。

---

## 具体例子：$n = 2$

$$\mathcal{O}_{\text{site-wise}} = \frac{1}{4}\big(\underbrace{W_{(123)} + W_{(132)}}_{\text{desired: }M_+} + \underbrace{W_{(123)}^{(1)}W_{(132)}^{(2)} + W_{(132)}^{(1)}W_{(123)}^{(2)}}_{\text{cross terms}}\big)$$

期望值为：

$$\frac{1}{4}\Big(2\operatorname{Tr}[\rho^3] + \operatorname{Tr}\!\big[(\rho^{T_2})^3\big] + \operatorname{Tr}\!\big[(\rho^{T_1})^3\big]\Big) = \frac{1}{2}\operatorname{Tr}[\rho^3] + \frac{1}{2}\operatorname{Tr}\!\big[(\rho^{T_1})^3\big]$$

（利用了 $\operatorname{Tr}[(\rho^{T_1})^3] = \operatorname{Tr}[(\rho^{T_2})^3]$。）

如果 $\rho$ 是纠缠态，$\operatorname{Tr}[(\rho^{T_1})^3] \neq \operatorname{Tr}[\rho^3]$，误差不可忽略。

---

## 能否通过经典后处理消除交叉项？

### 单格点的可达空间分析

对单个 qubit 的三拷贝空间，展开 POVM 元：

$$e_j(\beta^{(1)}, \beta^{(2)}) = \frac{1}{8}\Big[2\mathbb{I} + 2\beta^{(1)}\Xi^{(12)} + \beta^{(2)}\big(\Xi^{(23)}+\Xi^{(13)}\big) + \beta^{(1)}\beta^{(2)}M_+^{(j)}\Big]$$

因此，任意后处理函数 $f_j(\beta^{(1)},\beta^{(2)})$ 能产生的单格点有效算子都在

$$\mathcal{V}_j = \operatorname{span}\Big\{\mathbb{I}_j,\;\Xi_j^{(12)},\;\Xi_j^{(23)}+\Xi_j^{(13)},\;M_+^{(j)}\Big\}$$

这是 $S_3$ 群代数（6 维）中的一个 **4 维子空间**。缺失的两个方向恰好是：

$$\Xi_j^{(23)} - \Xi_j^{(13)} \quad\text{和}\quad M_-^{(j)} = W_{(123)}^{(j)} - W_{(132)}^{(j)}$$

### 为什么 $M_-$ 不可达

$$M_-^{(j)} = W_{(123)}^{(j)} - W_{(132)}^{(j)} = [\Xi_j^{(12)},\;\Xi_j^{(23)}]$$

这是一个**反 Hermitian 量**（或纯虚部分），而 POVM 元的展开中 $\Xi^{(23)}$ 和 $\Xi^{(13)}$ 总是以**对称组合**出现。物理原因：级联投影测量中，$\pi(\beta)\,A\,\pi(\beta)$ 结构天然产生反对易子 $\{S, A\}$，对称化抹去了对易子的信息。

### 不可能性定理

$$\frac{1}{2}M_+ = \frac{1}{2}\Big(\prod_j W_{(123)}^{(j)} + \prod_j W_{(132)}^{(j)}\Big) = \frac{1}{2}\prod_j\frac{M_+^{(j)}+M_-^{(j)}}{2} + \frac{1}{2}\prod_j\frac{M_+^{(j)}-M_-^{(j)}}{2}$$

对 $n \geq 2$，展开后必然包含 $M_-^{(j)}$ 的奇数次幂项（如 $M_-^{(1)}M_-^{(2)}$），而逐点 ST 测量的可达空间 $\bigotimes_j \mathcal{V}_j$ **不包含** $M_-^{(j)}$。

**因此，不存在任何经典后处理函数能从逐点级联 ST 测量数据中精确提取 $\operatorname{Tr}[\rho^3]$。**

---

## 可行的解决方案

### 方案 1：全局 SWAP 测量

如果能实现全局 $\Pi_{\pm} = \frac{\mathbb{I} \pm \prod_j \Xi_j}{2}$ 的两结果投影，则 Gray et al. 的证明严格成立。

在量子点阵列中，全局 singlet-triplet 判据可以通过电荷探测整个子系统来实现。但对大系统，这需要高度非局域的操作。

### 方案 2：多轮测量 + 反演

对不同的格点子集 $T \subseteq [n]$ 计算 $\prod_{j \in T}\gamma_j$（其中 $\gamma_j = \beta_j^{(1)}\beta_j^{(2)}$），可以提取不同的信息。具体地，

$$\Big\langle\prod_{j \in T}\gamma_j\Big\rangle = \operatorname{Tr}\bigg[\prod_{j \in T}\frac{M_+^{(j)}}{2}\;\rho^{\otimes 3}\bigg]$$

（$T$ 外的格点被 POVM 归一化消掉了。）

对所有 $2^n$ 个子集的数据做 Möbius 反演/Fourier 变换，可以**原则上**分离不同二分的贡献。但这需要 $2^n$ 个不同的后处理量，丧失了多项式效率。

### 方案 3：Zhou et al. 的虚拟拷贝方案（彻底绕过问题）

这正是你之前读的那篇 single-copy 论文的核心优势。在 Zhou et al. 的方案中：

- 不需要物理拷贝，不需要 SWAP 测量
- 随机酉 + 计算基测量，三次独立测量的概率**在经典后处理中相乘**
- Weingarten 积分在**经典**层面实现置换算子的选取
- 后处理函数 $O(\vec{s})$ 可以自由设计，不受量子测量的对称化限制

具体地，$O_+(\vec{s}) = \alpha\delta_{ss's''} + \beta(\delta_{ss'}+\delta_{s's''}+\delta_{ss''}) + \gamma$ 的系数可以精确调节到 $\Phi^3(O_+) = M_+$，其中 $M_+$ 是**全局的** $W_{(123)} + W_{(132)}$，不是逐格点的乘积。这是因为 Weingarten 积分中的全局 twirling 自然地在全局置换算子空间中操作。

### 方案 4：部分利用交叉项

在某些应用中，交叉项本身也有物理意义。逐点测量给出的

$$\frac{1}{2^n}\sum_{B \subseteq [n]}\operatorname{Tr}\!\big[(\rho^{T_B})^3\big]$$

是所有二分 negativity moment 的**民主平均**，它本身可以作为多体纠缠的一种粗粒化度量。

---

## 总结

| | 全局 SWAP 投影 | 逐点 ST 测量 | Zhou et al. 虚拟拷贝 |
|:---|:---:|:---:|:---:|
| 有效算子 | $\frac{1}{2}(W_{(123)}+W_{(132)})$ | $\prod_j \frac{1}{2}(W_{(123)}^{(j)}+W_{(132)}^{(j)})$ | $\frac{1}{2}(W_{(123)}+W_{(132)})$ |
| 交叉项 | 无 | $2^n - 2$ 项 | 无 |
| 给出的量 | $\operatorname{Tr}[\rho^3]$ | $\frac{1}{2^n}\sum_B \operatorname{Tr}[(\rho^{T_B})^3]$ | $\operatorname{Tr}[\rho^3]$ |
| 实验需求 | 非局域集体测量 | 逐格点 ST | 随机酉 + 单拷贝 |
| 可扩展性 | 差 | 好（但结果有偏） | 好 |

你发现的这个问题揭示了 Gray et al. 方案在多体系统中的一个根本困难：逐点 ST 测量的级联无法区分 $W_{(123)}^{(j)}$ 和 $W_{(132)}^{(j)}$（因为反对易子抹去了 $M_-$ 信息），导致全局正向/逆向循环的区分被交叉项污染。这也部分解释了为什么 Zhou et al. 的 single-copy 虚拟拷贝方案在多体系统中更具优势——它在经典后处理层面绕过了量子测量的对称化限制。



## Prompt:
3/4/2026, 5:56:06 PM

> File: 1772616495727_design.qmd

Refer to this file, inside which, the `

```quarto
## (M=2, S3) Non-hermitian virtual distillation`
```

section proposed a estimator for  

```quarto
\{(ZI)\mathrm{SWAP}, \mathrm{SWAP}\}.
```

by directly diagonalize the non-hemitian operator rather than the symmetric one. I believe this method can be used on the case $W_{(123)}$ here, where we consider the non-hermitian average  $\mathrm{SWAP}_{(123)}^{\otimes n}$ rather than its symmetrization's $\mathrm{SWAP}_{(123)}^{\otimes n}+\mathrm{SWAP}_{(132)}^{\otimes n}$ to get the value of $\mathrm{tr}(\rho^m)$



## Response:
3/4/2026, 5:59:59 PM

````plaintext
Thought process: Evaluating non-Hermitian operator diagonalization for W₍₁₂₃₎ estimation.

The user is asking me to look at their uploaded file, specifically the section about non-hermitian virtual distillation, and consider whether the approach of directly diagonalizing the non-Hermitian operator $W_{(123)}^{\otimes n}$ (rather than its Hermitianization) can be used to extract $\text{Tr}[\rho^3]$ from site-wise measurements, thereby avoiding the cross-term problem we identified.

Let me read the file first.
````

````plaintext
Bash Tool: Read the design.qmd file to understand the non-hermitian virtual distillation approach
````

````plaintext
Thought process: Decomposing cyclic permutation eigenbasis measurement circuits.

The user is pointing out that in their design.qmd file, the (M=2, S3) section uses a non-Hermitian operator $(ZI)\text{SWAP}$ with eigenvalues $\{+1, -1, +i, -i\}$, and they can directly diagonalize it and use complex-valued estimators. The key insight is that even though the single-shot estimator is complex, the expectation value is real, so you just take Re[estimator].

They want to apply this same idea to the $W_{(123)}$ case. Instead of using the Hermitianized $M_+ = W_{(123)} + W_{(132)}$ (which causes cross-terms when done site-wise), they want to directly diagonalize $W_{(123)}^{(j)}$ at each site $j$ independently, get complex-valued estimators, and multiply them together. Since $W_{(123)}$ is unitary with eigenvalues $\{1, \omega, \omega^2\}$ where $\omega = e

^{2\pi i/3}$, the site-wise product would give $\prod_j W_{(123)}^{(j)} = W_{(123)}$ globally without introducing the cross terms that plague the Hermitianized approach.

For the M=2 case, $(ZI)\text{SWAP}$ has four eigenvalues including complex ones like $\pm i$, with corresponding eigenstates that form a complete basis—measuring in this eigenbasis yields a complex estimator, yet the expectation value comes out real. For $W_{(123)}$ acting on a single qubit across three copies, I need to work out how the unitary structure behaves under this measurement scheme.

The core insight is that when measuring $(ZI)\text{SWAP}$ site-wise and taking the product across all sites, the $(ZI)^{\otimes n}$ factors combine with $\text{SWAP}^{\otimes n}$ in a way that lets me extract the trace of the desired operator—so even though individual measurements are complex, the overall construction recovers a real quantity.

For the three-copy case with $W_{(123)}$, I need to find a measurement basis that simultaneously diagonalizes the operator at each site, since $W_{(123)}$ acts on the three-copy subspace with eigenvalues $1, \omega, \omega^2$.

If I measure in the eigenbasis of $W_{(123)}$ at each site and multiply the eigenvalues together, the expectation value becomes $\text{tr}[\rho^3]$ — exactly what I'm looking for.

The crucial advantage of keeping the operators non-Hermitian is that the product factorizes cleanly: $\prod_j W_{(123)}^{(j)} = W_{(123)}$, whereas Hermitianizing would introduce cross terms that break this factorization. The tradeoff is that individual measurements yield complex values from the cube roots of unity, but since $\text{tr}[\rho^3]$ is real, I can just take the real part of the estimator.

Now I need to figure out how to actually measure in the eigenbasis of $W_{(123)}^{(j)}$. For a single site acting on three qubits, this operator permutes the three subsystems cyclically, so its eigenvalues are the cube roots of unity and I need to find the corresponding eigenvectors to construct the measurement basis. where $\omega = e^{2\pi i/3}$ is a primitive cube root of unity. So the full spectrum of $W_{(123)}$ on the 8-dimensional space consists of the eigenvalue 1 with multiplicity 4, and the pair $\omega, \omega^2$ each appearing twice.

This measurement projects onto the three eigenspaces, which is more intricate than a standard computational basis measurement but theoretically feasible. The key question is whether I can implement this with a local unitary circuit on the three qubits followed by a standard basis measurement—and since $W_{(123)}$ is itself a permutation matrix acting on the qubits, this should be achievable through an appropriate change of basis.

The cyclic permutation decomposes the 8-dimensional space into orbits: the fixed points $|000\rangle$ and $|111\rangle$ (both with eigenvalue 1), and the orbit $\{|001\rangle, |010\rangle, |100\rangle\}$ which cycles under the permutation. I can apply a discrete Fourier transform-like operation on these orbits to distinguish the eigenvalues $\omega$ and $\omega^2$ from the eigenvalue 1.

For the second orbit $\{|011\rangle, |110\rangle, |101\rangle\}$, I'll construct eigenstates in the same way using the cube roots of unity.

The complete set of eigenstates breaks down by eigenvalue: the trivial eigenvalue 1 has a multiplicity of 4 (from $|000\rangle$, $|111\rangle$, and the symmetric combinations $|\phi_0\rangle$, $|\psi_0\rangle$), while the other eigenvalues $\omega$ and $\omega^2$ each have multiplicity 2.

To measure these eigenstates, I need a 3-qubit unitary that transforms from the computational basis into this eigenbasis—this is implementable as a local circuit acting on the three copies at a single site. The crucial insight is that measuring these eigenstates independently at each site and multiplying the results gives us $\text{tr}[W_{(123)} \rho^{\otimes 3}] = \text{tr}[\rho^3]$ without any cross-site contamination, since each measurement outcome $\hat{\lambda}_j$ is drawn from $\{1, \omega, \omega^2\}$.

The full estimator is the product $\hat{o} = \prod_{j=1}^n \hat{\lambda}_j$, which is generally complex-valued but has expectation $\mathbb{E}[\hat{o}] = \text{tr}[\rho^3]$ (a real number), so we take the real part. Now I'm checking how this connects to the user's S3 construction—the $(ZI)\text{SWAP}$ operator on two copies of a single qubit has eigenvalues $\{+1, -1, +i, -i\}$, and the key property is that the product of these measurements across sites gives the desired trace.

For the $W_{(123)}$ case with three copies, the cyclic permutation operator has eigenvalues $\{1, \omega, \omega^2\}$, and again the product factorizes cleanly without cross terms. The analogy holds perfectly, confirming the user's approach is sound. Now the practical question is whether we can actually measure the eigenbasis of $W_{(123)}$ directly in an experiment.

To do this, I'd need a unitary that transforms from the computational basis into the eigenbasis. The structure is block-diagonal: the fixed points $|000\rangle$ and $|111\rangle$ stay put, while the other two 3-element subspaces each get mapped by a discrete Fourier transform over three elements. The catch is that this involves the complex cube root of unity $\omega = e^{2\pi i/3}$, which isn't a native Clifford operation, though it can be decomposed into standard gates.

But there's a cleaner approach: since the cyclic permutation commutes with total magnetization, I can first measure the Hamming weight to identify which orbit we're in, then apply the appropriate transformation within that sector. The weight-0 and weight-3 states are already eigenstates, while the weight-1 and weight-2 subspaces each need the 3-point Fourier transform applied.

The 3-point QFT decomposes into standard gates, though it requires non-Clifford operations since the primitive cube root of unity can't be expressed as a power of the T gate. Now I should write up a clear response that confirms the user's insight, proves the cross terms vanish mathematically, discusses the eigenbasis and circuit implementation, and compares the variance properties.
````

````plaintext
Tool: Searching project
````

````plaintext
Thought process: Synthesized non-Hermitian measurement framework for W₍₁₂₃₎ eigendecomposition.

The project knowledge search didn't return directly relevant content about the non-Hermitian approach for $W_{(123)}$. Let me think about this and provide a thorough answer.

The key insight from the user's design.qmd is:

**S3 approach for M=2**: Instead of diagonalizing the Hermitian SWAP (eigenvalues ±1), they diagonalize the non-Hermitian $(ZI)\text{SWAP}$ (eigenvalues $\{+1,-1,+i,-i\}$). The eigenbasis is:
$$\{|00\rangle, |11\rangle, \frac{1}{\sqrt{2}}(|01\rangle + i|10\rangle), \frac{1}{\sqrt{2}}(|01\rangle - i|10\rangle)\}$$


The advantage is that when this non-Hermitian operator is tensored across sites, it multiplies cleanly to $(ZI)^{\otimes n} \text{SWAP}^{\otimes n}$ without generating cross terms—the same operator at each site just gives a clean tensor product. For the 3-copy case with $W_{(123)}$, the strategy would be to replace the sequential SWAP measurement with a non-Hermitian variant that similarly avoids the Hermitianization artifacts.

Since $W_{(123)}$ is unitary with eigenvalues that are cube roots of unity, measuring directly in its eigenbasis at each site yields a product $\prod_j W_{(123)}^{(j)}$ that equals the global operator with no cross terms. The resulting estimator is complex-valued, but its expectation still gives the desired trace quantity.

Now I'm working through the eigenbasis structure of $W_{(123)}$ on three qubits by examining how the computational basis states transform under the cyclic group action, identifying the fixed points and orbital structure. I'm verifying the cyclic permutation action and confirming the eigenstates with their corresponding eigenvalues $\omega^k$ where $\omega = e^{2\pi i/3}$. I'm working through the eigenstates more carefully now, labeling the orbit elements and constructing the eigenstate as a superposition with the appropriate phase factors, then verifying that the cyclic permutation acts on it with the expected eigenvalue. I'm verifying that the eigenvalue equation holds, then moving on to analyze the second orbit under the same cyclic permutation operator, which cycles through the states |011⟩, |101⟩, and |110⟩.

Now I'm constructing the complete eigenbasis by collecting all eigenstates across both orbits, organizing them by their eigenvalues—the trivial eigenvalue 1 gives me four states including the symmetric and antisymmetric combinations, while the other eigenvalues correspond to the remaining eigenstates from each orbit. The second eigenspace completes with the same structure, giving us 2 more states. Now I'm seeing the measurement strategy: we project onto these 8 eigenstates and assign eigenvalues based on which eigenspace they belong to. For the circuit, the key insight is that the cyclic shift operator preserves Hamming weight, so I can first sort by weight, then apply a 3-point quantum Fourier transform within each nontrivial orbit—the weight-0 and weight-3 cases are already eigenstates, while weight-1 needs the transform applied. The key insight is that the $\mathbb{Z}_3$ QFT can be decomposed by first identifying which element of the cyclic orbit we're in, then applying the QFT to that register. Since the cyclic permutation operator commutes with Hamming weight, I can work within each weight sector separately—using CNOT gates to compute parity information that labels the sector, then applying the appropriate transformation within that subspace.

For the measurement-based estimator, I measure each site in the eigenbasis of the cyclic permutation operator and collect the eigenvalues $\lambda_j \in \{1, \omega, \omega^2\}$, then the single-shot estimator is simply their product across all sites.

Since each eigenvalue is a cube root of unity, the estimator has unit magnitude, and its expectation value recovers the trace of the third power of the density matrix. The real part gives an unbiased estimator for $\text{tr}[\rho^3]$, and now I need to work out the variance of this real-valued estimator. I need to be more careful about how I'm computing the variance for the real part of this complex random variable. Let me reconsider the formula—for a complex variable $Z$ where the expectation is real, the variance of its real part involves both the second moment and the squared expectation. I'm working through the expectation of the squared real part, using the fact that $|Z|^2 = 1$ to simplify, which gives me $\frac{1}{2}(1 + \text{Re}(\mathbb{E}[Z^2]))$. Then I'm computing $\mathbb{E}[\hat{o}^2]$ by taking the trace of products of the weight matrices with the density matrix, which ultimately reduces to $\text{tr}[\rho^3]$.

Now I'm calculating the variance of the real part and comparing it against the Hermitianized sequential SWAP approach—the sequential approach gives variance $1 - (\text{tr}[\rho^3])^2$ for a single system, but I need to be careful because the site-wise case behaves differently due to cross terms that arise in the Hermitianized version.

The non-Hermitian site-wise measurement gives the correct answer for $\text{tr}[\rho^3]$ with variance $\frac{1}{2}(1+\text{tr}[\rho^3]) - (\text{tr}[\rho^3])^2$, whereas the Hermitianized approach produces the wrong result contaminated by cross terms. So despite potentially different variance properties, the non-Hermitian approach is superior because it's actually correct.

Now I need to think through the practical circuit implementation for measuring in the eigenbasis of the three-qubit operator $W_{(123)}^{(j)}$.

The eigenbasis structure organizes nicely by Hamming weight: the zero and three-weight states are trivial eigenstates with eigenvalue 1, while the one and two-weight subspaces each decompose into three eigenstates via quantum Fourier transform, giving eigenvalues $1, \omega, \omega^2$. The measurement circuit needs to first distinguish between these trivial and nontrivial sectors.

For the nontrivial sectors, I'll apply a $\mathbb{Z}_3$ QFT to resolve the phase information—this involves using CNOT gates to extract parity and controlled phase rotations to implement the Fourier transform. Embedding the $\mathbb{Z}_3$ transformation into a full 3-qubit unitary is the tricky part, but it's achievable with the right gate decomposition.
````

你的直觉完全正确，而且这个类比非常精准。让我把这个方案严格建立起来。

## 核心类比

你在 design.qmd 中 S3 方案的关键洞察是：

| $M=2$ 的 S3 方案 | $M=3$ 的新方案 |
|:---:|:---:|
| 对角化 $(ZI)\mathrm{SWAP}$ | 对角化 $W_{(123)}$ |
| 本征值 $\{+1,-1,+i,-i\}$ | 本征值 $\{1,\omega,\omega^2\}$ |
| 逐点乘积 $= (ZI)^{\otimes n}\mathrm{SWAP}^{\otimes n}$ | 逐点乘积 $= W_{(123)}^{\text{global}}$ |
| **无交叉项** | **无交叉项** |

对比 Hermitian 化方案的问题：

$$\prod_j \underbrace{\frac{1}{2}(W_{(123)}^{(j)} + W_{(132)}^{(j)})}_{\text{Hermitianized}} = \frac{1}{2^n}\sum_{S\subseteq[n]}W_{(123)}^S W_{(132)}^{\bar{S}} \quad\text{（}2^n\text{ 个交叉项）}$$

而非 Hermitian 方案：

$$\prod_j W_{(123)}^{(j)} = W_{(123)} \quad\text{（精确，零交叉项）}$$

---

## 严格构造

### 第一步：$W_{(123)}$ 在单 qubit 三拷贝空间上的谱

$W_{(123)}$ 作用于 $(\mathbb{C}^2)^{\otimes 3}$，$W_{(123)}|a_1,a_2,a_3\rangle = |a_3,a_1,a_2\rangle$。它保持 Hamming weight，所以按 weight 分块。

**固定点**（weight 0, 3）：$|000\rangle$, $|111\rangle$，本征值 $1$。

**Weight-1 轨道** $\{|001\rangle, |100\rangle, |010\rangle\}$（$|001\rangle \xrightarrow{W} |100\rangle \xrightarrow{W} |010\rangle \xrightarrow{W} |001\rangle$）：

$$|e_k^{(1)}\rangle = \frac{1}{\sqrt{3}}\big(|001\rangle + \omega^{-k}|100\rangle + \omega^{-2k}|010\rangle\big), \quad W_{(123)}|e_k^{(1)}\rangle = \omega^k|e_k^{(1)}\rangle$$

**Weight-2 轨道** $\{|011\rangle, |101\rangle, |110\rangle\}$（$|011\rangle \xrightarrow{W} |101\rangle \xrightarrow{W} |110\rangle \xrightarrow{W} |011\rangle$）：

$$|e_k^{(2)}\rangle = \frac{1}{\sqrt{3}}\big(|011\rangle + \omega^{-k}|101\rangle + \omega^{-2k}|110\rangle\big), \quad W_{(123)}|e_k^{(2)}\rangle = \omega^k|e_k^{(2)}\rangle$$

完整本征分解（$\omega = e^{2\pi i/3}$）：

| 本征值 | 本征态 | 重数 |
|:---:|:---|:---:|
| $1$ | $|000\rangle,\;|111\rangle,\;|e_0^{(1)}\rangle,\;|e_0^{(2)}\rangle$ | 4 |
| $\omega$ | $|e_1^{(1)}\rangle,\;|e_1^{(2)}\rangle$ | 2 |
| $\omega^2$ | $|e_2^{(1)}\rangle,\;|e_2^{(2)}\rangle$ | 2 |

### 第二步：测量协议

**协议：** 对 $n$-qubit 态 $\rho$ 的三份拷贝 $\rho^{\otimes 3}$，在每个格点 $j$ 独立地：

1. 对拷贝 $(j_1, j_2, j_3)$（三个拷贝中格点 $j$ 的 qubit）做投影测量到上述本征基
2. 记录对应本征值 $\lambda_j \in \{1, \omega, \omega^2\}$

**Single-shot 估计量：**

$$\hat{o} = \prod_{j=1}^n \lambda_j$$

### 第三步：证明无偏性

**定理.** $\mathbb{E}[\hat{o}] = \operatorname{Tr}[\rho^3]$。

**证明.** 由于各格点的测量独立，且每个格点的 POVM 就是 $W_{(123)}^{(j)}$ 的谱分解，所以：

$$\mathbb{E}[\hat{o}] = \mathbb{E}\bigg[\prod_{j=1}^n \lambda_j\bigg] = \operatorname{Tr}\bigg[\prod_{j=1}^n W_{(123)}^{(j)}\;\rho^{\otimes 3}\bigg] = \operatorname{Tr}\big[W_{(123)}\;\rho^{\otimes 3}\big] = \operatorname{Tr}[\rho^3]$$

关键等式：$\prod_j W_{(123)}^{(j)} = W_{(123)}$（全局循环置换）。

这里**没有**交叉项，因为我们没有在任何步骤做 Hermitian 化。每个格点直接输出 $W_{(123)}^{(j)}$ 的本征值，乘积就是全局 $W_{(123)}$ 的本征值。$\square$

### 第四步：实值性

$\hat{o}$ 一般是复数（$|\hat{o}|=1$, 幅角为 $\frac{2\pi}{3}$ 的整数倍），但 $\operatorname{Tr}[\rho^3] \in \mathbb{R}$。

**证明实值性：** $\rho$ Hermitian $\Rightarrow$ $\operatorname{Tr}[\rho^3] = \overline{\operatorname{Tr}[\rho^3]}$。

或者更直接：$\operatorname{Tr}[W_{(132)}\rho^{\otimes 3}] = \overline{\operatorname{Tr}[W_{(123)}\rho^{\otimes 3}]}$（因为 $W_{(132)} = W_{(123)}^\dagger$ 且 $\rho^{\otimes 3}$ Hermitian），而 $\operatorname{Tr}[W_{(132)}\rho^{\otimes 3}] = \operatorname{Tr}[\rho^3] = \operatorname{Tr}[W_{(123)}\rho^{\otimes 3}]$。所以 $\operatorname{Tr}[\rho^3]$ 等于其自身的复共轭。

因此使用实部估计量：

$$\hat{o}_{\mathrm{re}} = \operatorname{Re}\bigg[\prod_{j=1}^n \lambda_j\bigg]$$

仍然无偏：$\mathbb{E}[\hat{o}_{\mathrm{re}}] = \operatorname{Re}[\operatorname{Tr}[\rho^3]] = \operatorname{Tr}[\rho^3]$。

---

## 方差分析

### 非 Hermitian 估计量的方差

由于 $|\hat{o}|^2 = 1$（每个 $|\lambda_j|=1$ 的乘积），

$$\mathbb{E}[|\hat{o}|^2] = 1$$

计算 $\mathbb{E}[\hat{o}^2]$：

$$\mathbb{E}[\hat{o}^2] = \prod_j \mathbb{E}[\lambda_j^2] = \operatorname{Tr}\bigg[\prod_j (W_{(123)}^{(j)})^2\;\rho^{\otimes 3}\bigg] = \operatorname{Tr}[W_{(132)}\;\rho^{\otimes 3}] = \operatorname{Tr}[\rho^3]$$

利用 $\operatorname{Re}(Z)^2 = \frac{1}{4}(Z+Z^*)^2 = \frac{1}{4}(Z^2 + 2|Z|^2 + (Z^*)^2)$：

$$\mathbb{E}[\operatorname{Re}(\hat{o})^2] = \frac{1}{4}\big(\mathbb{E}[\hat{o}^2] + 2\mathbb{E}[|\hat{o}|^2] + \overline{\mathbb{E}[\hat{o}^2]}\big) = \frac{1}{4}\big(\operatorname{Tr}[\rho^3] + 2 + \operatorname{Tr}[\rho^3]\big) = \frac{1+\operatorname{Tr}[\rho^3]}{2}$$

$$\boxed{\operatorname{Var}(\hat{o}_{\mathrm{re}}) = \frac{1+\operatorname{Tr}[\rho^3]}{2} - \big(\operatorname{Tr}[\rho^3]\big)^2}$$

### 与 Gray et al. 全局 SWAP 测量的方差比较

Gray et al. 的方差（全局 ST 级联测量）：$\operatorname{Var}(\beta_1\beta_2) = 1 - (\operatorname{Tr}[\rho^3])^2$。

两者之差：

$$\Delta V = \operatorname{Var}(\hat{o}_{\mathrm{re}}) - \operatorname{Var}(\beta_1\beta_2) = \frac{1+\operatorname{Tr}[\rho^3]}{2} - 1 = \frac{\operatorname{Tr}[\rho^3]-1}{2} \leq 0$$

因为 $\operatorname{Tr}[\rho^3] \leq \operatorname{Tr}[\rho^2] \leq 1$。

**非 Hermitian 估计量的方差严格更小（或相等）！** 这是因为虚部 $\operatorname{Im}(\hat{o})$ 的波动不贡献到 $\operatorname{Var}(\hat{o}_{\mathrm{re}})$，相当于"免费"丢弃了一半的噪声。

---

## 测量线路设计

### 线路结构

由于 $W_{(123)}$ 保持 Hamming weight，对角化可分为两步：

```
copy 1 ─────────────────┐
                        ├── Hamming weight detection ──→ QFT₃ within orbit ──→ 测量
copy 2 ─────────────────┤
                        │
copy 3 ─────────────────┘
```

**步骤 1：Hamming weight 检测**

用 CNOT 计算 parity bits：

```
q₁ ──●────────────── q₁ (不变)
     │
q₂ ──⊕──●─────────── q₂ ⊕ q₁ =: p₁ (parity of copies 1,2)
         │
q₃ ──────⊕────────── q₃ ⊕ q₂ =: p₂ (parity of copies 2,3)  
```

此时 $(p_1, p_2) = (0,0)$ 意味着 weight 0 或 3（固定点），$(p_1,p_2) \neq (0,0)$ 意味着 weight 1 或 2（非平凡轨道）。

**步骤 2：轨道内 $\mathbb{Z}_3$ QFT**

在非平凡轨道内，$W_{(123)}$ 作为 3 阶循环移位。需要做 $\mathbb{Z}_3$ Fourier 变换区分本征值 $1, \omega, \omega^2$。

$\mathbb{Z}_3$ QFT 矩阵为：

$$F_3 = \frac{1}{\sqrt{3}}\begin{pmatrix} 1 & 1 & 1 \\ 1 & \omega & \omega^2 \\ 1 & \omega^2 & \omega \end{pmatrix}$$

由于这嵌入在 3-qubit 空间中（8 维中的 3 维子空间），需要条件门实现。具体地，可以用 $q_1$ 的值区分 weight（$q_1=0$ 时轨道在 weight-1 或 weight-0 子空间），然后在 $(p_1, p_2)$ 寄存器上做 controlled-$\mathbb{Z}_3$-QFT。

$\mathbb{Z}_3$ QFT 本身可以分解为：

$$F_3 = R_{01}\!\left(\frac{2\pi}{3}\right)\cdot R_{12}\!\left(\arccos\frac{1}{\sqrt{3}}\right)$$

其中 $R_{ab}(\theta)$ 是 Givens 旋转，每个可编译为 2-qubit 门（CZ + 单 qubit 旋转，类似你 S2 中的 Givens 编译）。

### 门资源

| 资源 | 每个格点 | 总计 |
|:---|:---:|:---:|
| 2-qubit 门 (CNOT/CZ) | $O(1)$ | $O(n)$ |
| 单 qubit 旋转 | $O(1)$（含 $2\pi/3$ 相位） | $O(n)$ |
| 测量 | 3 个计算基测量 | $3n$ |
| 非 Clifford 门 | 需要（$\omega$ 相位） | $O(n)$ |

---

## 推广到 negativity moment

对 bipartite 系统 $\rho_{AB}$，我们需要的是 $W_{(123)}^A \otimes W_{(132)}^B$。

**$A$ 子系统格点**：测量 $W_{(123)}^{(j)}$ 的本征基，输出 $\lambda_j^A \in \{1,\omega,\omega^2\}$。

**$B$ 子系统格点**：测量 $W_{(132)}^{(j)} = (W_{(123)}^{(j)})^\dagger$ 的本征基，输出 $\lambda_j^B \in \{1,\omega^{-1},\omega^{-2}\} = \{1,\omega^2,\omega\}$。

注意 $W_{(132)}$ 的本征基与 $W_{(123)}$ 相同（因为 $W_{(132)} = W_{(123)}^\dagger$），但本征值取复共轭。实际上，这意味着 $B$ 上的 QFT 方向应该反转（逆 QFT），完美对应 Gray et al. 的"正向/反向"结构。

估计量：

$$\hat{o}_{\text{neg}} = \prod_{j \in A}\lambda_j^A \cdot \prod_{j \in B}\lambda_j^B$$

$$\mathbb{E}[\hat{o}_{\text{neg}}] = \operatorname{Tr}\big[W_{(123)}^A \otimes W_{(132)}^B\;\rho_{AB}^{\otimes 3}\big] = \operatorname{Tr}\big[(\rho_{AB}^{T_B})^3\big]$$

**直接给出 negativity moment，无交叉项，无需全局酉！**

---

## 总结：三种方案的对比

| | Gray et al. 全局级联 | Hermitianized 逐点级联 | **非 Hermitian 逐点对角化** |
|:---|:---:|:---:|:---:|
| 物理拷贝数 | 3 | 3 | 3 |
| 操作局域性 | 需要全局 SWAP | 逐格点 ST | **逐格点 $\mathbb{Z}_3$-QFT** |
| 交叉项 | 无 | $2^n-2$ 项 | **无** |
| 估计量类型 | 实数 $\pm 1$ | 实数 $\pm 1$ | **复数 $|\hat{o}|=1$** |
| 给出的量 | $\operatorname{Tr}[\rho^3]$ | $\frac{1}{2^n}\sum_B\operatorname{Tr}[(\rho^{T_B})^3]$ | **$\operatorname{Tr}[\rho^3]$** |
| 方差 | $1-p_3^2$ | （有偏，不适用） | **$\frac{1+p_3}{2}-p_3^2 \leq 1-p_3^2$** |
| Negativity moment | 需要 $A$/$B$ 反向 | 不适用 | **$A$: QFT, $B$: 逆 QFT** |
| 非 Clifford 门 | 否（仅 ST） | 否 | **是**（$\omega$ 相位门） |

你的方案用非 Clifford 门的代价换取了完全消除交叉项 + 更低的方差，并且完全保持了逐格点局域性。这是对 Gray et al. 和 Zhou et al. 两种方案之间的一个全新的中间路线：仍然需要物理三拷贝（不如 Zhou et al. 的虚拟拷贝），但完全局域化（优于 Gray et al. 的全局 SWAP 需求）。



## Prompt:
3/4/2026, 6:41:33 PM

在3 qubit上 中性原子 做投影到3 cycle swap的eigenbasis上这个操作该怎么实现？注意3 cycle swap的本征值也是简并的 可能能优化



## Response:
3/4/2026, 10:48:42 PM

````plaintext
Thought process: 探索了Schur变换与Z₃对称性测量的电路实现方案。

The user is asking about how to implement the projection onto the eigenbasis of the 3-cycle SWAP operator $W_{(123)}$ on 3 qubits using neutral atom platforms. They also note that the eigenvalues are degenerate, which might allow optimization.

Let me think about this carefully.

The 3-cycle SWAP $W_{(123)}$ acts on $(\mathbb{C}^2)^{\otimes 3}$ (8-dimensional space). Its eigenvalues are $\{1, \omega, \omega^2\}$ where $\omega = e^{2\pi i/3}$.

The eigenspaces:


- $\lambda = 1$: 4-dimensional, containing the symmetric states $|000\rangle$ and $|111\rangle$ plus two additional eigenvectors
- $\lambda = \omega$: 2-dimensional eigenspace
- $\lambda = \omega^2$: 2-dimensional eigenspace

For computing $\text{Tr}[\rho^3]$, I only need to identify which eigenvalue sector a state belongs to—this is fundamentally a 3-outcome measurement rather than an 8-outcome one. Since $W_{(123)}^3 = \mathbb{I}$, the operator represents a $\mathbb{Z}_3$ symmetry with eigenspaces corresponding to charge sectors. The operator commutes with the total Hamming weight, which means the eigenspaces are organized by this conserved quantity.

Looking at how the eigenvalues distribute across weight sectors: the zero and three-qubit states each have eigenvalue 1, while the weight-1 and weight-2 subspaces each split into three 1-dimensional eigenspaces with eigenvalues 1, ω, and ω². To distinguish between these three eigenvalues in the middle sectors, I'll need to apply a $\mathbb{Z}_3$ quantum Fourier transform.

For neutral atom platforms, the native toolkit includes single-qubit rotations, CZ gates via Rydberg interactions, and potentially mid-circuit measurements. The challenge is that $W_{(123)}$ doesn't decompose nicely into controlled operations, so I need to think about this as phase estimation for the $\mathbb{Z}_3$ symmetry—designing a unitary that, when measured in the computational basis, reveals which eigenvalue sector the state occupies. The weight-0 and weight-3 subspaces are straightforward since they're already in eigenvalue-1 sectors. I see that the eigenvalue can be encoded as a charge $q \in \{0, 1, 2\}$ where $\lambda = \omega^q$, and the total estimator becomes $\omega^{\sum_j q_j \mod 3}$. Now I need to work out what the real part of this estimator gives me for each possible charge sum modulo 3. So the real-part estimator works out to $\hat{o}_{\text{re}} = \frac{3}{2}\delta_{Q \mod 3, 0} - \frac{1}{2}$, but I need to preserve the full complex value when combining measurements across multiple sites since the overall observable depends on $\omega^{\sum_j q_j}$. Now let me work through the circuit design—for a single site with 3 qubits representing 3 copies, I need to identify the eigenstates and their corresponding charges, starting with the weight-0 and weight-3 states that both have charge 0, then the weight-1 superposition states with different charge assignments.

Let me verify the cyclic permutation operator $W_{(123)}$ acts correctly on the basis states.

Now I'm constructing the eigenstates for this orbit by taking superpositions with phases $\omega^k$ where $k = 0, 1, 2$, and checking that they're indeed eigenstates with eigenvalue $\omega^k$. I can verify this works since $\omega^{3k} = 1$, which confirms that $|e_k\rangle$ is indeed an eigenstate with eigenvalue $\omega^k$. Now I'm identifying the eigenstates for the weight-1 orbit and setting up the same analysis for the weight-2 orbit.

For the weight-2 states, the cyclic permutation acts similarly, giving me eigenstates of the form $|e_k^{(2)}\rangle = \frac{1}{\sqrt{3}}(|011\rangle + \omega^{-k}|101\rangle + \omega^{-2k}|110\rangle)$. Since both weight-1 and weight-2 states share the same eigenvalues within each charge sector, I can collapse this into a single 3-outcome POVM that directly measures the charge $q \in \{0, 1, 2\}$ by measuring the cyclic permutation operator itself.

Now I'm thinking about how to actually implement this on neutral atoms. The challenge is that measuring a $\mathbb{Z}_3$ symmetry requires either a qutrit ancilla or two qubits encoded as a qutrit. I could use phase estimation with controlled applications of $W_{(123)}$ and its square, followed by a quantum Fourier transform on the ancilla, but that requires implementing controlled-$W_{(123)}$ gates, which are expensive on neutral atoms since they effectively involve four qubits. Let me consider whether a direct diagonalization approach might be more practical instead.

Since $W_{(123)}$ preserves Hamming weight, I could first detect which weight subspace we're in, then apply a $\mathbb{Z}_3$ QFT within just the weight-1 and weight-2 subspaces. The tricky part is that on qubits, the weight-1 subspace is only 3-dimensional but embedded in an 8-dimensional space, so implementing the QFT cleanly requires careful gate design. Alternatively, I could decompose $W_{(123)}$ using its SWAP structure—since it factors as products of transpositions, and each SWAP is just a 2-qubit gate—but on neutral atoms with native CZ gates, I'd need to decompose SWAP into CZ and single-qubit rotations.

Actually, I don't need to implement $W_{(123)}$ as a gate at all. What I really need is to diagonalize it—find a unitary $U$ such that $U W_{(123)} U^\dagger$ becomes diagonal or block-diagonal enough to read off eigenvalues. For each site, I need to extract the $\mathbb{Z}_3$ charge $q_j \in \{0, 1, 2\}$, and I can encode this by mapping the 8 computational basis states to their corresponding charges. Now I'm thinking about how to design a unitary circuit that encodes the charge information into measurement outcomes. I need to map the three charge values to subsets of the eight computational basis states, distributing them according to their multiplicities—four states for charge 0, and two states each for charges 1 and 2.

Rather than trying to encode charge directly into individual qubits, I should use a two-step measurement strategy: first distinguish between fixed points (which have all qubits aligned) and non-trivial orbits, then determine the specific $\mathbb{Z}_3$ charge within the non-trivial sector.

For the non-trivial orbits, I can exploit the cyclic symmetry of the weight-1 and weight-2 subspaces—applying a quantum Fourier transform over the cyclic group to extract the charge eigenvalues.

The key insight is that the inverse QFT matrix maps the eigenbasis back to the computational basis within each subspace, which is exactly what we need to diagonalize the cyclic shift operator.

Now the challenge is translating this into a neutral atom implementation.

Since we're working with qubits rather than qutrits, I need to think about how to implement the $\mathbb{Z}_3$ QFT on the weight-1 subspace without directly accessing a three-level system. One option is to leverage the Hamming weight structure with CNOT gates to identify which sector we're in, then apply the appropriate transformation.

For the weight-1 case specifically, the three basis states correspond to the position of the single 1 bit across the three qubits—this is essentially a one-hot encoding of a position index from 0 to 2. The $\mathbb{Z}_3$ QFT would cyclically permute these positions, and I can implement this using controlled operations that depend on which qubit holds the 1.

Rather than building up the circuit piecemeal, I think the cleaner approach is to use quantum phase estimation on the cyclic shift operator $W_{(123)}$ with an ancilla qubit prepared in superposition, which would directly extract the eigenvalue and thus the charge.

But that requires multiple ancilla qubits to distinguish the three possible outcomes in $\mathbb{Z}_3$. Let me reconsider—maybe there's a more direct way to measure the purity or trace of powers of the density matrix without explicitly constructing the full circuit. Actually, I should focus on what's practical for a neutral atom implementation rather than getting lost in the abstract formalism.

On neutral atoms, I'm working with native single-qubit rotations and CZ gates via Rydberg blockade, with all-to-all connectivity within the blockade radius. For three copies of a single qubit, that's three physical atoms, and I need entangling gates between them. Let me think about what the minimal circuit would look like.

The key insight is that $W_{(123)}$ has order 3 with eigenvalues $1, \omega, \omega^2$, and I can extract the charge $q$ using a projector-based approach rather than phase estimation.

Since the charge is constant within each weight sector, I can simplify the measurement by first determining the Hamming weight classically, then measuring the charge separately within the weight-1 and weight-2 subspaces.

But wait—I can't destructively measure the weight first and then apply a quantum Fourier transform; I need to keep the quantum coherence intact. Let me reconsider the approach with a concrete circuit design using three qubits representing the three copies of the site qubit, starting with a CNOT cascade to set up the diagonalization of the cyclic permutation operator. Let me try a different approach. For the weight-1 subspace, I can encode the position of the single "1" bit—position 0 for $|100\rangle$, position 1 for $|010\rangle$, and position 2 for $|001\rangle$. The cyclic permutation $W_{(123)}$ should map each position forward by one step modulo 3, which means $|001\rangle$ becomes $|100\rangle$.

Checking this: $W_{(123)}$ cycles through all three basis states in order, so the position advances by 1 modulo 3. To extract the charge information, I can apply a $\mathbb{Z}_3$ quantum Fourier transform to the position. The key challenge is implementing this QFT efficiently on the one-hot encoded qutrit, which uses only the weight-1 subspace of the three qubits.

The QFT maps each basis state to an equal superposition weighted by phase factors depending on the mode index. This is a unitary transformation within the 3D subspace, though extending it to the full 8-qubit space while preserving identity on the orthogonal complement requires careful construction.

Let me reconsider this more directly: since the cyclic permutation can be decomposed into SWAP gates, I might be able to leverage their eigenvalue structure instead.

The issue is that while individual SWAPs have eigenvalues of ±1, the two SWAPs in the decomposition don't commute in the relevant weight sectors, so I can't just multiply their eigenvalues to get the cyclic permutation's eigenvalue—that's precisely the obstacle I've been circling around.

Now I'm sketching out an actual circuit: given three qubits, I need to design a unitary that lets me measure in the computational basis afterward and extract the $\mathbb{Z}_3$ charge information from the outcome.

The natural approach is to map the charge sectors to computational basis states: the charge-0 sector (4-dimensional) maps to states where the first two qubits are $|00\rangle$, charge-1 (2-dimensional) maps to $|01\rangle$, and charge-2 maps to $|10\rangle$. But I'm running into a problem with the $|11\rangle$ states—they're overcounting or don't fit cleanly into this scheme.

Let me reconsider by working backwards from what the output should actually be. I'll list out the eigenstates for each charge sector and then construct an explicit mapping that assigns each eigenstate to a specific computational basis state, making sure the charge value can be read off from the qubit labels. I'm realizing that encoding isn't quite right either. Let me try a different approach where the charge information maps more cleanly to the qubit states, using a scheme where specific bit patterns directly encode which charge sector each state belongs to. I'm trying different encoding schemes for the charge using two qubits, but the modular arithmetic approach is getting complicated. I think the cleanest solution is to step back and define a post-processing function that extracts the charge from the qubit states rather than trying to force a specific bit pattern.

Now I'm designing a circuit to separate the eigenstates by Hamming weight using CNOT gates to map the input states into a more structured form. But I'm running into an issue—the weight-3 and weight-1 states are colliding after the transformation, so this approach needs refinement. Let me reconsider the CNOT operations more carefully. When I apply CNOT from q₃ to q₁ first, then from q₃ to q₂, I'm flipping q₁ and q₂ based on whether q₃ is in state 1. Working through the basis states: |000⟩ stays put, |001⟩ becomes |110⟩, |010⟩ is unchanged, and |011⟩ maps to |100⟩.

But wait, I'm getting |100⟩ mapping to itself, which would mean both |011⟩ and |100⟩ go to the same state—that can't be right for a unitary operation. Let me trace through |100⟩ again: the control qubit q₃ is 0, so neither CNOT fires, leaving it as |100⟩. That's actually correct, not a collision.

Now checking |011⟩: the first CNOT flips q₁ since q₃ = 1, giving |111⟩, then the second CNOT flips q₂ since q₃ = 1, giving |101⟩. And |001⟩ maps to |111⟩ through the same logic. This approach isn't separating the weight sectors cleanly—I'm getting non-trivial mixing that doesn't help diagonalize the operator.

I need to reconsider the strategy entirely. Rather than trying to use CNOTs to isolate sectors, I should think about what unitary actually maps the eigenstates of W₍₁₂₃₎ to the computational basis states.

Let me write out the full 8×8 matrix representation of the unitary that performs this transformation. The eigenbasis consists of the charge-0 and charge-1 eigenstates I've already identified. For charge 0, I have the two trivial eigenstates |000⟩ and |111⟩, plus two superposition states spanning the weight-1 and weight-2 subspaces. For charge 1, there are four more eigenstates involving the cyclic phases ω and ω².

Now I need to figure out what unitary maps each eigenvector to a computational basis state in a way that makes the charge structure readable from the output. two of the qubits:

$|v_1\rangle = |000\rangle \to |000\rangle$
$|v_2\rangle = |111\rangle \to |001\rangle$
$|v_3\rangle \to |010\rangle$
$|v_4\rangle \to |011\rangle$
$|v_5\rangle \to |100\rangle$
$|v_6\rangle \to |101\rangle$
$|v_7\rangle \to |110\rangle$
$|v_8\rangle \to |111\rangle$

Then charge = first qubit value + ... no. Let me see: charge 0 maps to 000, 001, 010, 011 (first qubit = 0), charge 1 maps to 100, 101 (q₁=1, q₂=0), charge 2 maps to 110, 111 (q₁=1, q₂=1). So the charge formula is $q_1 + q_1 q_2$, which gives me 0, 1, or 2 depending on the qubit values. For post-processing, I need to extract charge from the measurement outcomes using this relationship.

Now I'm setting up the unitary transformation that maps from the computational basis to the eigenbasis of the Hamiltonian. The unitary has columns corresponding to each eigenstate, ordered to match the computational basis states. Continuing to fill in the remaining columns of $U^\dagger$, where $|v_4\rangle$ through $|v_7\rangle$ are superpositions involving the computational basis states with various phases including $\omega$ and $\omega^2$ (the cube roots of unity).

Now I'm seeing a clear pattern emerge in how these mappings work: when $q_3 = 0$, the transformation maps into states with lower Hamming weights, while $q_3 = 1$ maps into higher weight states. More specifically, the values of $q_2$ and $q_3$ together determine which subspace the state maps to—the all-zero state when both are zero, the all-one state when they're opposite, and weight-1 states when $q_2 = 1$ and $q_3 = 0$.

Let me verify this pattern by checking a few specific cases to make sure the weight distribution and QFT phases are consistent across the different input combinations. I'm testing different formulas to express the charge in terms of $q_1$ and $q_2$. The pattern shows charge equals 0 when $q_1=0, q_2=1$; charge equals 1 when $q_1=1, q_2=0$; and charge equals 2 when $q_1=1, q_2=1$. Let me work through whether something like $q_1(1+q_2) \mod 3$ captures this mapping correctly.

Actually, the formula $q_1(1+q_2)$ works perfectly for all three cases. Now I need to think about the inverse operation—how $U$ maps the eigenbasis back to the computational basis, which is what gets applied before measurement. Looking at the structure of $U^\dagger$, I can see that $q_3$ acts as a classifier: it distinguishes between states where all qubits are the same versus mixed states, and then further subdivides based on whether we're looking at weight 0 versus weight 3 in the "all same" case, or weight 1 versus weight 2 in the "mixed" case.

Wait, let me reconsider the actual mapping I derived. I need to verify which computational basis states map to which eigenstates and what the corresponding quantum numbers should be.

Looking at the complete mapping: the first two states are the trivial ones, then I have alternating weight-1 and weight-2 states as I go through the basis. The charge increases as $q_1$ goes from 0 to 1, while $q_2$ and $q_3$ control which specific state within each charge sector. Now I'm seeing the pattern for the inverse operation—$q_2$ appears to determine something fundamental about the structure. and $q_1 = 0$: fixed points
  - $q_3 = 0$: $|000\rangle$
  - $q_3 = 1$: $|111\rangle$
- Otherwise: weight-sector states
  - $q_3 = 0$: weight-1 orbit state
  - $q_3 = 1$: weight-2 orbit state
  - The QFT phase is determined by some function of $q_1, q_2$

The charge index for the QFT maps the two-qubit combinations to phases: $q_1q_2 = 01$ gives charge 0, $q_1q_2 = 10$ gives charge 1, and $q_1q_2 = 11$ gives charge 2.

So the inverse circuit $U^\dagger$ works by checking whether $(q_1, q_2)$ is the zero state—if it is, the output is determined entirely by $q_3$, otherwise it applies an inverse QFT with the appropriate phase index based on the charge, where $q_3$ selects between the weight-1 and weight-2 orbits. To construct $U$ in the forward direction, I need to reverse this logic: the input state should be analyzed to determine which charge sector it belongs to, then the appropriate QFT applied before measurement.

Actually, let me reconsider this using the permutation-symmetric structure instead. The Schur basis decomposes the three-qubit space into irreducible representations: a 4-dimensional spin-3/2 symmetric subspace and two 2-dimensional spin-1/2 subspaces.

The cyclic permutation $W_{(123)}$ acts trivially on the symmetric subspace since those states are invariant under any permutation. On the spin-1/2 subspaces, I need to look at how the standard representation of $S_3$ behaves—the cyclic permutation has eigenvalues $\omega$ and $\omega^2$ (the primitive cube roots of unity), while transpositions give eigenvalue $-1$.

For the full tensor product $(\mathbb{C}^2)^{\otimes 3}$, the Schur-Weyl decomposition splits this into irreducible representations of both $U(2)$ and $S_3$: the 4D spin-3/2 sector pairs with the trivial representation of $S_3$, while the remaining 4D decomposes into the spin-1/2 sector paired with the standard representation.

The first block contributes entirely to the charge-0 sector since $W_{(123)}$ acts trivially there. For the second block, I need to determine how $W_{(123)}$ acts on the standard representation of $S_3$.

In the standard 2D representation, the 3-cycle has eigenvalues $\omega$ and $\omega^2$ (where $\omega = e^{2\pi i/3}$), each appearing in a 1D eigenspace. Combined with the 2D $U(2)$ factor, this gives 2 states per eigenvalue, so 2D for charge-1 and 2D for charge-2. This confirms the total: 4D charge-0, 2D charge-1, 2D charge-2.

Diagonalizing $W_{(123)}$ is really just applying the Schur transform to decompose into irreps, then diagonalizing the standard rep within the $(2,1)$ block. For 3 qubits, the Schur transform can be implemented efficiently...

The Schur transform itself requires only a constant number of gates—roughly 4 to 5 two-qubit gates based on known circuit constructions. After that, I just need a single-qubit rotation to diagonalize $W_{(123)}$ within the 2D standard rep sector. So the full circuit is just the Schur transform followed by one single-qubit gate on the multiplicity register.

Now I'm measuring all qubits to extract the charge from the multiplicity register. This approach is elegant, but implementing the Schur transform on neutral atoms requires careful gate decompositions. Let me explore a more direct construction that leverages the natural gate set available on neutral atom platforms.

I'm thinking about building the unitary step by step using CZ gates. The key insight is that $W_{(123)}$ already block-diagonalizes according to Hamming weight—weight 0 gives charge 0, weight 1 gives three separate charges (0, 1, 2), and weight 2 has its own structure.

Here's the crucial optimization: since charge-0 appears multiple times with degeneracy 4, I don't actually need full diagonalization. I only need to distinguish between the three charge sectors, which requires at most 2 qubits for a 3-outcome measurement.

This means I can measure just 2 of the 3 qubits to determine the charge sector, leaving the third qubit to encode within-sector information I don't need to resolve. For the ancilla-free approach, I'm thinking about constructing a unitary that maps the weight-1 orbit states (which form a cycle under the charge operator) such that measuring 2 qubits reveals the charge, while the $\mathbb{Z}_3$ structure within each sector gets encoded naturally.

I'm now considering whether to implement this as a qutrit quantum Fourier transform embedded in the 3-qubit space. The cyclic shift on 3 elements has a known DFT that diagonalizes it into the charge eigenvalues, so I need to figure out how to implement that Fourier transform on the relevant qubits.

Looking at the weight-1 subspace with the orbit ordering, the cyclic shift acts exactly like the permutation operator, so I need the 3D Fourier transform there. The weight-2 subspace has the same structure with its own orbit basis. There's an elegant symmetry here—the weight-1 and weight-2 states are bitwise complements of each other, which means the bit-flip operator connects them. If I can construct the Fourier transform for one subspace, I might be able to leverage this complementarity to handle both.

For a concrete implementation, I'm thinking about using the first two qubits to encode which position the single "1" occupies in the weight-1 subspace, and using the third qubit as a marker for which subspace we're in. Let me trace through what happens when I apply a controlled-NOT from qubit 1 to qubit 3 on the weight-1 basis states to see if this encoding strategy works.

After checking the transformations, this approach isn't giving me the clean separation I need, so I'm trying a different gate arrangement with CNOT from qubit 2 to qubit 3 instead. I'm organizing the state transformations by weight and noticing that the third qubit is now encoding positional information rather than just a weight indicator. This random gate approach isn't getting me anywhere—I need to think about this more carefully using the Schur transform, which decomposes the three-qubit space into irreducible representations based on permutation symmetry.

The Schur transform separates the space into spin-3/2 and spin-1/2 sectors, each with their own multiplicity structure. For three qubits, I need to map to quantum numbers for total spin $j$, its z-component $m$, and the multiplicity label $\lambda$, but I'm running into the issue that spin-3/2 actually requires two qubits to represent, which complicates the encoding.

Looking at the dimensions: the $j=3/2$ sector has 4 magnetic states with trivial multiplicity (1D), while the $j=1/2$ sector has 2 magnetic states but a 2D multiplicity space. This accounts for all 8 dimensions. The key insight is that the cyclic permutation $W_{(123)}$ acts trivially on the $j=3/2$ multiplicity but has nontrivial eigenvalues in the $j=1/2$ multiplicity space.

For the measurement strategy: after applying the Schur transform, the $j=3/2$ sector immediately reveals charge 0 without further work. For the $j=1/2$ sector, I need to measure the multiplicity qubit in the eigenbasis of $W_{(123)}$, which in the standard representation is diagonal with eigenvalues $\omega$ and $\omega^2$. A single-qubit rotation can diagonalize this operator, allowing me to extract the charge information from the multiplicity register.

Now I'm reconsidering the explicit matrix forms—the standard representation of $S_3$ and how the 3-cycle $(123)$ acts on it. Let me work through the Young orthogonal basis to get the correct matrix representation.

In this basis, $(123)$ becomes a rotation matrix with complex eigenvalues $\omega$ and $\omega^2$ (the primitive cube roots of unity), and I need to find the eigenvectors to understand the diagonalization. I've identified the eigenbasis as the Y-basis states, which means measuring in this basis after the Schur transform will reveal the charge. Now I'm verifying this result by computing the expectation value of the matrix in the Y-basis. I'm verifying the calculation by checking what $W$ actually does to $|+i\rangle$ — it looks like I got $\omega^2|-i\rangle$ instead of an eigenstate with eigenvalue $\omega^2$, so let me recalculate the matrix multiplication more carefully. I've verified that $W$ acts on the $Y$-eigenstates as $W|+i\rangle = \omega^2 |+i\rangle$ and $W|-i\rangle = \omega |-i\rangle$, so the eigenbasis of $W_{(123)}$ is exactly the $Y$-eigenbasis, with eigenvalues $\omega^2$ and $\omega$ corresponding to charges 2 and 1 respectively.

Now I'm laying out the full measurement protocol: first apply the Schur transform to separate the total spin, then measure the first qubit to determine if we're in the $j=3/2$ sector (charge 0) or $j=1/2$ sector (which requires a secondary measurement). For the $j=1/2$ case, I measure the multiplicity qubit in the $Y$-basis to distinguish between charges 2 and 1, which I can implement using a combination of Hadamard and phase gates followed by a standard computational basis measurement.

For implementing the Schur transform itself on three qubits, I need to use the decomposition from the literature—specifically building it up through sequential Clebsch-Gordan transforms that couple qubits pairwise to construct the total angular momentum eigenbasis. qubit 2 encodes the magnetic quantum number. The first CG transform is really just a singlet-triplet decomposition, which I can implement with a CNOT followed by a Hadamard on the first qubit—this maps the computational basis states into superpositions of $|+\rangle$ and $|-\rangle$ entangled with the parity information.

Wait, I'm conflating the Bell basis with the angular momentum basis. The angular momentum coupling for two qubits actually decomposes into a triplet state with $j=1$ (symmetric combinations) and a singlet with $j=0$ (antisymmetric). The unitary transformation needs to map each computational basis state into the appropriate superposition of these coupled states, with the first qubit carrying the total angular momentum and the second carrying the magnetic quantum number. I'm completing the mapping for all four computational basis states to their angular momentum counterparts, and I notice that the unitary acts as a Hadamard on the middle two basis states while leaving the outer states unchanged. Now I need to reconsider how the qubit encoding relates to the angular momentum quantum numbers.

Actually, I should step back—the user is asking for a practical circuit to measure the $\mathbb{Z}_3$ charge in a neutral atom system, not a deep dive into the mathematical structure. The most straightforward approach is to use quantum phase estimation with the cyclic shift operator, or alternatively, build a circuit that exploits the natural decomposition of the space by applying a CNOT to compute the parity between qubits and then using conditional operations to distinguish the different charge sectors. structure within each orbit, a small rotation extracts the $\mathbb{Z}_3$ phase.

Let me think about what's most practical for neutral atoms. Global single-qubit rotations and CZ gates via Rydberg blockade are native operations, and mid-circuit measurement is possible in some setups. The circuit I'm envisioning applies a CNOT to separate the "same/different" structure between the first two qubits, then uses controlled gates to detect the cyclic structure across all three qubits, finishing with a rotation to extract the phase.

Actually, I'm overcomplicating this. The key insight is that only 2 qubits are needed to encode the charge due to degeneracy—the third qubit can be measured in the computational basis since its value doesn't affect the charge. So I should focus on presenting the core ideas: the degeneracy structure, the connection to the Schur transform and angular momentum, the practical circuit using CZ and single-qubit rotations native to neutral atoms, and the gate count implications.

For the 3-qubit Schur transform, I need to apply two successive Clebsch-Gordan transforms: first coupling qubits 1 and 2 to get their total angular momentum, then coupling that result with qubit 3 to get the final total angular momentum and multiplicity labels. The first CG transform maps the computational basis of two spin-1/2 qubits into the coupled basis with definite total spin.

In the standard encoding, qubit 1 stores the total angular momentum quantum number j (0 or 1 in one bit), while qubit 2 encodes the magnetic quantum number m. The transformation on the middle two basis states {|01⟩, |10⟩} is a Hadamard matrix, but I need to track how all four computational basis states map through the full CG transformation—specifically how |00⟩ maps to the j₁₂=1, m₁₂=1 state, and how |01⟩ decomposes into a superposition involving both j₁₂=1, m₁₂=0 and another j₁₂ value. I'm realizing the mapping I described is just the identity, which means I haven't actually defined the Clebsch-Gordan transformation properly. Let me reconsider what the encoding should be—I need to be more careful about how the original two-qubit basis states map to the angular momentum eigenstates. unitary transformation that maps between two different basis representations, and I need to be clearer about which direction I'm applying it and what the actual matrix elements should be. I'm finishing that last transformation and then trying to encode the coupled basis states as qubits. I'm mapping each $|j,m\rangle$ state to a two-qubit register, but when I work through the algebra, the superposition states don't cleanly separate into a product form—there's something off with how the encoding interacts with the entanglement in the Clebsch-Gordan decomposition. I'm realizing that $U_{CG}$ leaves the $|00\rangle$ and $|11\rangle$ states unchanged while applying a Hadamard to the $|01\rangle$ and $|10\rangle$ subspace. Let me verify if this can be decomposed as a CNOT followed by a Hadamard on the first qubit, checking the math to confirm the gate sequence works. I'm realizing that approach isn't producing the right Bell state either. Let me step back and directly verify which gate sequence actually generates the controlled-G unitary by examining its action on the computational basis states. I'm seeing the full 4×4 matrix representation of this controlled Givens rotation, which leaves the first and last basis states unchanged while applying the rotation to the middle two states. Now I'm thinking through how to decompose this into basic quantum gates—starting with a CNOT that remaps the relevant subspace, followed by controlled rotations on individual qubits.

Let me verify a simpler decomposition using CNOT sandwiched around a Hadamard: applying CNOT from q₂ to q₁ maps |01⟩ to |11⟩ and |10⟩ stays put, then the Hadamard on q₁ acts on those states, and another CNOT maps back to complete the transformation. I'm noticing the sign is off in my previous attempt, so let me try a different gate sequence with CNOT applied in the opposite direction. Working through the first step where the initial CNOT flips the second qubit based on the first, then applying the Hadamard to get a superposition state.

After applying the second CNOT, I'm checking whether this preserves the correct subspace, but it's mapping states outside of the target space. Let me pivot to constructing the Hadamard directly on the restricted subspace spanned by the two basis states I care about.

I realize this is actually a fermionic beam splitter—a Givens rotation on two modes—and I can implement it using the circuit pattern from the design file with the standard angle of θ = -π/4. The circuit applies a sequence of Hadamards, controlled-Z gates, and parameterized rotations that produce the unitary transformation I need.

Computing the resulting matrix... I'm checking if a Givens rotation with angle $-\pi/4$ produces the required matrix form, working through the trigonometric values to see if this gives me the exact transformation I need. I'm realizing I've been overcomplicating this—the practical approach is much simpler. The Schur transform on three qubits handles the charge measurement directly with just a few CZ gates, and since neutral atom platforms have CZ as a native operation, the implementation is straightforward with roughly 3-4 CZ gates plus some single-qubit rotations.

Now I'm thinking about the degeneracy optimization the user mentioned. Since we only need to distinguish three charge outcomes rather than fully diagonalize the entire operator, we can use a coarse-grained measurement that doesn't require measuring all qubits—just enough to extract the charge information. This means the circuit could be significantly shallower because we only need to extract the relevant $\mathbb{Z}_3$ charge structure rather than implementing the complete Schur transform.

Looking at the charge projectors and their ranks, I can see that two qubits are sufficient to distinguish all three outcomes. The key insight is designing a unitary that maps the charge information onto just two qubits while leaving the third in a product state, so we only need to measure those two qubits to determine the charge.

The Schur transform accomplishes this by decomposing the state into quantum numbers $(j, m, \lambda)$, where the charge is determined by $j$ and $\lambda$ alone. If we encode $j$ on the first qubit and $\lambda$ on the third, we can measure just those two: the first qubit tells us whether the charge is 0 (when $j=3/2$), and if not, measuring the third qubit in the Y-basis reveals $\lambda$ to determine the charge among the remaining possibilities.

For the circuit implementation, the Schur transform requires two Clebsch-Gordan transforms—the first is straightforward with a CNOT and Hadamard, while the second couples higher-spin states with the spin-1/2 system more intricately. On neutral atom platforms, CZ gates are native operations via Rydberg blockade at around 100 nanoseconds, and single-qubit rotations are comparatively fast, so the circuit should be efficient to execute.

Breaking down the full circuit: the first CG transform needs roughly one CZ gate plus single-qubit rotations across two layers, the second CG with qubit 3 requires two to three CZ gates and more single-qubit operations spanning three to four layers, and finally a Y-basis rotation on the multiplicity qubit adds one more single-qubit gate. This gives a total depth of about five to six layers with three to four CZ gates and roughly ten single-qubit gates—a modest improvement over the full Schur transform which would demand around five CZ gates for eight-outcome resolution.

But I'm wondering if there's a more direct approach that leverages the problem structure without needing the full Schur machinery.

Since we only care about the $\mathbb{Z}_3$ charge and it's the Fourier dual of the cyclic position within an orbit, I can compute orbit labels using parity gates and apply the $\mathbb{Z}_3$ QFT only to the relevant degrees of freedom. I'm defining parity operators for adjacent qubit pairs—$p_{12}$ for qubits 1 and 2, and $p_{23}$ for qubits 2 and 3—which uniquely identify the orbit structure across the weight-0, weight-3, and weight-1 states.

Now I'm working through the parity values for each computational basis state to map out how the orbits are characterized by these parity patterns. I see that the parity pair $(p_{12}, p_{23})$ for $|010\rangle$ is $(1,1)$, completing the three weight-1 states. The cyclic shift operator permutes these parity values in a specific pattern, cycling through $(0,1) \to (1,0) \to (1,1)$ and back, which means I can use a $\mathbb{Z}_3$ quantum Fourier transform to diagonalize the shift within this subspace.

Now I'm working through how to compute the parities with CNOT gates—the challenge is that I need both $p_{12} = a_1 \oplus a_2$ and $p_{23} = a_2 \oplus a_3$ without destroying the original qubit values in the process, so I need to think carefully about the gate order and which qubits I'm using as controls versus targets. Verifying the orbit structure by checking how each basis state transforms under the circuit—for weight 1 states like $|100\rangle$ and $|010\rangle$, the parity operations map them to specific positions in the orbit, and similarly for weight 2 states where the parity calculations determine their final positions. I'm compiling the full transformation table showing how each basis state maps through the CNOT operations, along with their Hamming weights before and after the transformation.

Now I need to express the eigenstates of the three-qubit W operator in this new basis, transforming each eigenstate according to the mapping I just derived.

Looking at these transformed eigenstates, they're all three-term superpositions mixing $|001\rangle$, $|100\rangle$, and $|111\rangle$ with different phase factors. The issue is that this combination doesn't respect simple parity or $a_2$ structure, so it's not leading anywhere obvious for applying the quantum Fourier transform.

I think the parity-based encoding might be a dead end here. Let me explore a different strategy using controlled-phase operations instead.

Since $W_{(123)}^3 = I$, the eigenvalues must be cube roots of unity, and ideally I'd implement a phase detection circuit that marks which eigenvalue we're in. The constraint is that I only have the three data qubits themselves—no ancillas to work with.

Actually, there's a cleaner way to think about this: the 8-dimensional Hilbert space naturally splits into three eigenspaces under the cyclic symmetry of $W_{(123)}$—a 4-dimensional space for eigenvalue 1, and two 2-dimensional spaces for $\omega$ and $\omega^2$ respectively. This decomposition mirrors how three qubits behave under $\mathbb{Z}_3$ cyclic symmetry, and the charge measurement is precisely what distinguishes these eigenspaces.

For discrete symmetries, the standard approach is to apply a phase kickback using the symmetry operator itself. Since $W_{(123)}$ factors as a product of two SWAPs, I could in principle build a controlled version using Fredkin gates, though that gets expensive in terms of elementary gates.

But neutral atom systems offer a better path forward—the Rydberg blockade naturally enables all-to-all interactions between nearby atoms, so I can implement the necessary CZ gates directly without heavy decomposition. For three atoms, I'd need around 4-5 CZ gates for the Schur transform plus a single-qubit rotation, which is much more practical than the gate-by-gate decomposition approach.

Now I'm organizing the presentation: first explain why degeneracy lets us reduce the measurement overhead, then walk through the Schur transform itself, show how it maps onto neutral atom hardware, and finally quantify the gate savings. The key insight is that we only need to measure two qubits since the magnetic quantum number is irrelevant—this means the second Clebsch-Gordan transform can be simplified because we're not resolving the full $m$ structure. 5. But for the coarse-grained version (charge only), it might be 3-4.

OK, I think I now have enough to write a comprehensive response. Let me focus on:

1. The symmetry structure and why 3 outcomes suffice
2. Connection to Schur transform
3. Concrete circuit for neutral atoms
4. Gate count and comparison
5. How degeneracy reduces the circuit

I'll also mention the important point that for multi-site systems, we only need to determine $\sum_j q_j \mod 3$ (the total charge), not individual $q_j$. This could enable further optimizations like "syndrome-style" measurements.

Actually wait, no — we need individual $q_j$ for the product $\prod_j \omega^{q_j}$. But that product equals $\omega^{\sum_j q_j}$, so we really only need the total charge modulo 3. For the estimator, I'd measure each site classically and compute the sum, but there's a potentially more elegant approach: directly measuring the global $\mathbb{Z}_3$ charge without resolving individual sites, which would be like a syndrome measurement for the total symmetry.

The global $W_{(123)}$ operator across all $n$ sites has eigenvalues $\omega^Q$ where $Q$ is the total charge. Measuring this directly gives $Q$ without needing individual measurements. However, implementing phase estimation for such a massive operator—requiring controlled versions acting on all $3n$ qubits simultaneously—becomes prohibitively expensive, essentially negating any advantage from the global approach.

On neutral atom platforms, I could exploit the physical layout to implement $W_{(123)}^{\text{global}}$ more efficiently using global Rydberg operations and row-wise SWAPs, but this is highly platform-specific. I should focus the response on the single-site circuit design and keep the multi-site discussion brief and practical.
````

这是一个很好的工程问题。让我从简并结构出发，推导出最优测量方案。

## 简并结构分析

$W_{(123)}$ 作用于 $(\mathbb{C}^2)^{\otimes 3}$，按 Hamming weight 分块：

| 本征值 | Weight-0 | Weight-1 | Weight-2 | Weight-3 | 总维度 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| $1$ | $\|000\rangle$ | $\frac{1}{\sqrt{3}}\sum_{\text{cyc}}\|001\rangle$ | $\frac{1}{\sqrt{3}}\sum_{\text{cyc}}\|011\rangle$ | $\|111\rangle$ | **4** |
| $\omega$ | — | $\frac{1}{\sqrt{3}}(\|001\rangle+\omega^2\|100\rangle+\omega\|010\rangle)$ | $\frac{1}{\sqrt{3}}(\|011\rangle+\omega^2\|101\rangle+\omega\|110\rangle)$ | — | **2** |
| $\omega^2$ | — | $\frac{1}{\sqrt{3}}(\|001\rangle+\omega\|100\rangle+\omega^2\|010\rangle)$ | $\frac{1}{\sqrt{3}}(\|011\rangle+\omega\|101\rangle+\omega^2\|110\rangle)$ | — | **2** |

**关键优化：** 我们只需区分 3 个 charge sector ($q \in \{0,1,2\}$)，不需要 8-outcome 的完全对角化。这是一个 **coarse-grained 投影测量**，只需 $\lceil\log_2 3\rceil = 2$ 个 qubit 的信息。

## 与 Schur-Weyl 对偶的联系

$(\mathbb{C}^2)^{\otimes 3}$ 在 $U(2) \times S_3$ 下的 Schur-Weyl 分解为：

$$(\mathbb{C}^2)^{\otimes 3} = \underbrace{V_{3/2}}_{\text{4D spin}} \otimes \underbrace{S_{\text{triv}}}_{\text{1D}} \;\oplus\; \underbrace{V_{1/2}}_{\text{2D spin}} \otimes \underbrace{S_{\text{std}}}_{\text{2D}}$$

$W_{(123)}$ 只作用于 $S_3$ 表示因子：

- **平凡表示** $S_{\text{triv}}$：$W_{(123)} \to 1$，贡献 $4 \times 1 = 4$ 维 charge-0
- **标准表示** $S_{\text{std}}$：$W_{(123)}$ 有本征值 $\omega, \omega^2$，贡献 $2 \times 1 + 2 \times 1 = 4$ 维 charge-1,2

**因此测量策略分解为：**

1. **判断** $j = 3/2$ 还是 $j = 1/2$（Schur transform）
2. 若 $j = 3/2$：charge = 0，**结束**
3. 若 $j = 1/2$：测量 multiplicity qubit 以区分 charge 1 和 2

---

## $W_{(123)}$ 在标准表示中的精确矩阵

在 Young 正交基下，$W_{(123)}$ 在 2D 标准表示中为：

$$W_{(123)}\big|_{S_{\text{std}}} = \begin{pmatrix} -\frac{1}{2} & -\frac{\sqrt{3}}{2}



## Prompt:
3/4/2026, 6:51:08 PM

Continue



## Response:
3/5/2026, 12:10:00 AM

````plaintext
Thought process: Resumed quantum circuit derivation for three-qubit SWAP eigenbasis projection.

The user wants me to continue the derivation of the measurement circuit for projecting onto the eigenbasis of the 3-cycle SWAP on 3 qubits, using neutral atoms. Let me continue from where I left off - I was writing the matrix representation of $W_{(123)}$ in the standard representation.
````

## $W_{(123)}$ 在标准表示中的精确矩阵（续）

在 Young 正交基下，$W_{(123)}$ 在 2D 标准表示 $S_{\text{std}}$ 中为：

$$W_{(123)}\big|_{S_{\text{std}}} = \begin{pmatrix} -\frac{1}{2} & -\frac{\sqrt{3}}{2} \\ \frac{\sqrt{3}}{2} & -\frac{1}{2} \end{pmatrix} = e^{i2\pi/3} |e_1\rangle\langle e_1| + e^{-i2\pi/3}|e_2\rangle\langle e_2|$$

这就是绕 $Z$ 轴的旋转 $R_z(2\pi/3)$（在适当基下），对角化只需一个 Hadamard 类旋转。

---

## 最优策略：两步判定

整个测量只需要回答一个**三元分类**问题（charge $q \in \{0,1,2\}$），不需要 8 维完全对角化。

### 第一步：对称/非对称子空间判别

**任务：** 区分 $j=3/2$（全对称，4D）和 $j=1/2$（混合对称，4D）。

**全对称子空间** $\text{Sym}^3(\mathbb{C}^2)$ 的显式基：

$$|S_0\rangle = |000\rangle, \quad |S_1\rangle = \frac{|001\rangle+|010\rangle+|100\rangle}{\sqrt{3}}, \quad |S_2\rangle = \frac{|011\rangle+|101\rangle+|110\rangle}{\sqrt{3}}, \quad |S_3\rangle = |111\rangle$$

**混合对称子空间**的一组正交基（$j=1/2$, $m=+1/2$, multiplicity $\mu \in \{1,2\}$）：

$$|\mu_1,\uparrow\rangle = \frac{|001\rangle - |010\rangle}{\sqrt{2}}, \qquad |\mu_2,\uparrow\rangle = \frac{|001\rangle + |010\rangle - 2|100\rangle}{\sqrt{6}}$$

以及 $m = -1/2$：

$$|\mu_1,\downarrow\rangle = \frac{|110\rangle - |101\rangle}{\sqrt{2}}, \qquad |\mu_2,\downarrow\rangle = \frac{|110\rangle + |101\rangle - 2|011\rangle}{\sqrt{6}}$$

**对称子空间投影的等价条件：** 一个态 $|\psi\rangle$ 属于 $\text{Sym}^3$ 当且仅当 $S^{(12)}|\psi\rangle = +|\psi\rangle$（对拷贝 1,2 对称即可，因为 $S_3$ 由相邻对换生成）。

因此第一步可以**只测拷贝 1 和 2 之间的 SWAP**：

$$S^{(12)} = +1 \implies \text{可能在 Sym}^3 \text{（但不确定）}$$

这还不够——$S^{(12)} = +1$ 的子空间是 6 维的（$\text{Sym}^3$ 的 4D + $|\mu_2,\uparrow\rangle, |\mu_2,\downarrow\rangle$ 的 2D），不等于 $\text{Sym}^3$。

### 更优方案：直接提取 $\mathbb{Z}_3$ charge

**核心观察：** 我们实际上不需要做 Schur transform。我们需要的只是 $W_{(123)}$ 的本征值 $\omega^q$，即 $\mathbb{Z}_3$ charge $q \bmod 3$。

$W_{(123)} = S^{(12)}S^{(23)}$，所以 $\mathbb{Z}_3$ charge 完全由拷贝间的排列关系确定。

**关键简化：** 利用 Hamming weight 守恒，测量分为 4 个 sector：

- **Weight 0, 3**：自动 $q = 0$，无需进一步测量
- **Weight 1, 2**：3 维子空间内区分 $q \in \{0,1,2\}$，需要 $\mathbb{Z}_3$ QFT

---

## 完整线路

### Phase 1：Hamming weight 提取

用两个 CNOT 将 parity 信息提取到辅助 bits：

```
q₁ ──●────────── q₁ (保持不变)
     │
q₂ ──⊕──●─────── q₂ → p₁ = q₁ ⊕ q₂
         │
q₃ ──────⊕────── q₃ → p₂ = q₂ ⊕ q₃
```

| $(p_1,p_2)$ | Weight sector | 维度 | 需要 QFT？ |
|:---:|:---:|:---:|:---:|
| $(0,0)$ | $\{000, 111\}$ | 2 | 否，$q=0$ |
| $(1,0)$ | $\{100, 010, 001\}$（weight 1 或 2） | 3 | 是 |
| $(0,1)$ | $\{010, 001, 100\}$（同上） | 3 | 是 |
| $(1,1)$ | $\{001, 100, 010\}$（同上） | 3 | 是 |

等等，这个 parity 编码不能直接区分 weight。让我重新设计。

实际上，CNOT 后的状态演化为：

$$|a_1, a_2, a_3\rangle \xrightarrow{\text{CNOT}_{1\to 2}, \text{CNOT}_{2\to 3}} |a_1,\; a_1\oplus a_2,\; a_2\oplus a_3\rangle$$

映射表：

| 原始态 | 变换后 | Weight |
|:---:|:---:|:---:|
| $\|000\rangle$ | $\|000\rangle$ | 0 |
| $\|001\rangle$ | $\|001\rangle$ | 1 |
| $\|010\rangle$ | $\|011\rangle$ | 1 |
| $\|100\rangle$ | $\|110\rangle$ | 1 |
| $\|011\rangle$ | $\|010\rangle$ | 2 |
| $\|101\rangle$ | $\|111\rangle$ | 2 |
| $\|110\rangle$ | $\|100\rangle$ | 2 |
| $\|111\rangle$ | $\|101\rangle$ | 3 |

变换后，$(p_1, p_2) = (a_1\oplus a_2,\; a_2\oplus a_3)$：
- $(0,0)$：$q_1 \in \{0,1\}$ 区分 weight 0 vs weight 3 → 直接测 $q_1$
- $(p_1, p_2) \neq (0,0)$：处于 weight-1 或 weight-2 sector → 需要 QFT

但这个方案把问题搅乱了。让我回到更清晰的思路。

---

## 从头设计：直接实现 $\mathbb{Z}_3$ QFT

### 核心结构

$W_{(123)}$ 是 $|a_1,a_2,a_3\rangle \to |a_3,a_1,a_2\rangle$，即**循环右移**。它在计算基上的作用是：

$$W_{(123)} = \sum_{a_1,a_2,a_3}|a_3,a_1,a_2\rangle\langle a_1,a_2,a_3|$$

**对角化 = Fourier 变换循环移位。** 这与量子计算中对角化 increment gate 完全类似。

### 等价视角：把 8 维空间看成 $\mathbb{Z}_2^3$

在 $\mathbb{Z}_2^3$ 上，循环右移 $(a_1,a_2,a_3) \to (a_3,a_1,a_2)$ **不是** $\mathbb{Z}_8$ 的加法自同构，而是 $\mathbb{Z}_2^3$ 上的**线性变换**：

$$W_{(123)} \leftrightarrow A = \begin{pmatrix} 0 & 0 & 1 \\ 1 & 0 & 0 \\ 0 & 1 & 0 \end{pmatrix} \in GL(3, \mathbb{F}_2)$$

$A$ 的特征多项式在 $\mathbb{F}_2$ 上为 $\lambda^3 + 1 = (\lambda+1)(\lambda^2+\lambda+1)$：

- $\lambda = 1$：固定点 $v = (0,0,0), (1,1,1)$（对应 weight 0,3）
- $\lambda^2+\lambda+1 = 0$：在 $\mathbb{F}_2$ 上不可约，对应 weight-1 和 weight-2 轨道

但在 $\mathbb{C}$ 上，$A^3 = I$ 的本征值是 $1, \omega, \omega^2$，对角化需要从 $\mathbb{F}_2$ 到 $\mathbb{C}$ 的提升。

### 最优线路：条件 $\mathbb{Z}_3$-QFT

**思路：** 先测量 $q_1$（区分 weight 奇偶 sector），然后在 $(q_2, q_3)$ 寄存器上做条件旋转。

但更好的方法是利用**循环移位 = 特定 permutation matrix** 的结构，直接做 block-diagonal 对角化。

---

## 最简方案：两次 CNOT + 一个相位门

让我追踪 $W_{(123)}$ 在每个 weight sector 内的作用，并找到**最小对角化线路**。

### Weight-1 sector

基 $\{|001\rangle, |010\rangle, |100\rangle\}$ 上，$W_{(123)}$ 作为矩阵：

$$W_{(123)}\big|_{\text{wt-1}} = \begin{pmatrix} 0 & 0 & 1 \\ 1 & 0 & 0 \\ 0 & 1 & 0 \end{pmatrix}$$

本征向量（$\mathbb{Z}_3$ Fourier modes）：

$$|f_q\rangle = \frac{1}{\sqrt{3}}\big(|001\rangle + \omega^{-q}|010\rangle + \omega^{-2q}|100\rangle\big), \qquad q = 0,1,2$$

### 编码方案

注意 weight-1 sector 内的 3 个基态与 3-qubit 中"1 在哪个位置"一一对应：

$$|001\rangle \leftrightarrow \text{位置 3}, \quad |010\rangle \leftrightarrow \text{位置 2}, \quad |100\rangle \leftrightarrow \text{位置 1}$$

$W_{(123)}$ 就是"位置的循环移位"：$3 \to 1 \to 2 \to 3$。

**关键洞察**：如果我们能把"位置寄存器"从 one-hot 编码转换为 binary 编码，$\mathbb{Z}_3$ QFT 就变成标准的 2-qubit 操作。

### 具体线路

**Phase 1: One-hot → Binary（只在 weight-1/2 sector 内有效）**

对 weight-1 态，做 Toffoli-类变换把 one-hot 编码压缩到两个 qubit 的 binary 编码。但这需要 3 qubit 门。

**更实际的方案：直接在 3-qubit 空间做对角化**

让我换一个思路，利用中性原子的**原生门集**。

---

## 中性原子原生门集

中性原子量子计算的典型原生操作：

1. **任意单 qubit 旋转**：$R_x(\theta), R_y(\theta), R_z(\theta)$（通过 Raman/microwave 驱动）
2. **CZ 门**：$\text{diag}(1,1,1,-1)$（通过 Rydberg blockade）
3. **CCZ 门**：$\text{diag}(1,\ldots,1,-1)$（双 Rydberg blockade，实验上已有但保真度较低）
4. **全局旋转**：对所有 qubit 同时做 $R(\theta)$（通过全局光场）

中性原子的特点是 **CZ（而非 CNOT）是原生门**，且可以同时在空间上不重叠的 qubit 对上并行执行。

---

## 最终线路设计

### 策略

我直接数值搜索一个**最优酉矩阵** $U$ 使得 $U W_{(123)} U^\dagger$ 为对角矩阵，然后将 $U$ 编译为 CZ + 单 qubit 旋转。

但首先，利用简并性简化：我们只需要一个**3-outcome 投影测量**，投影到 charge $q \in \{0,1,2\}$ 子空间。

投影算子为：

$$P_q = \frac{1}{3}\big(\mathbb{I} + \omega^{-q}W_{(123)} + \omega^{-2q}W_{(132)}\big), \qquad q = 0,1,2$$

验证：$P_0 + P_1 + P_2 = \mathbb{I}$，$P_q P_{q'} = \delta_{qq'} P_q$。

### 等价改写：测量 $\mathbb{Z}_3$ charge = 测量特定 Hermitian 算子

定义 Hermitian 算子：

$$Q = \frac{2\pi}{3}\cdot\frac{1}{2\pi i}\ln W_{(123)} \;\;\text{（取主值）}$$

或更实际地，定义：

$$C = P_1 + 2P_2 = \frac{1}{3}\big(2\mathbb{I} - W_{(123)} - W_{(132)}\big) + \frac{2}{3}\cdot\frac{1}{3}\big(\text{...}\big)$$

这变得复杂了。让我直接给出**线路**。

### 显式对角化线路

````plaintext
Bash Tool: Compute eigenvectors of W_(123) and the diagonalizing unitary
````

````plaintext
Thought process: Architected quantum circuit design for charge measurement encoding.

Good, confirmed the eigenvalue structure. Now let me think about how to design the circuit more carefully.

The key insight is: we need a 3-outcome measurement (charge 0, 1, 2). The charge-0 subspace is 4D, charge-1 and charge-2 are each 2D.

For neutral atoms, the native gates are CZ + single qubit rotations. Let me think about the circuit structure.

The block structure is:
- Weight 0: |000⟩ → charge 0
- Weight 3: |111⟩ → charge 0
- Weight 1: {|001⟩, |010⟩, |100⟩} → 3D subspace with charges 0,1,2


- Weight 2: {|011⟩, |101⟩, |110⟩} → 3D subspace with charges 0,1,2

So the circuit needs to detect the weight sector first, then apply a Z₃ QFT within the weight-1 and weight-2 sectors to resolve the charges. Since weight 0 and 3 automatically give charge 0, I only need the QFT conditionally. For the estimator, I really just need to extract the charge information, so let me think about what the minimal measurement strategy would be.

Given the block structure, I need to find a unitary U that diagonalizes W₁₂₃ so that measuring in the computational basis afterward reveals the charge. The key insight is that the charge sectors are already somewhat separated by weight—weight 0 and 3 always have charge 0, while weight 1 and 2 each split into three charge sectors depending on the ω-mode content. So I need U to map these charge eigenstates to computational basis states that I can distinguish by measurement.

Rather than full diagonalization, I can use a coarse-grained measurement approach: design U so that two of the three qubits encode the charge information directly. Let me construct the charge-0 subspace explicitly with the symmetric combinations, then work out what U should map the charge-1 and charge-2 eigenstates to. I'm realizing that approach doesn't give a clean encoding either. The better strategy is to use qubit 1 for weight parity and qubits 2-3 to distinguish charges within each weight sector. Actually, the most elegant solution is to apply a $\mathbb{Z}_3$ quantum Fourier transform on the 3-state system embedded in these qubits, since the weight operator commutes with total spin—so I can measure the Hamming weight first to separate the sectors.

But implementing Hamming weight measurement with ancillas is getting messy, and trying to encode all four possible weights (0,1,2,3) requires two classical bits. I think the most practical approach for neutral atoms is to just directly compile the 3-qubit unitary that transforms the eigenbasis to the computational basis using CZ gates and single-qubit rotations.

A general 3-qubit unitary needs at most 20 CZ gates plus single-qubit rotations, though the block structure here should let us do better. Actually, stepping back—what I really need is a measurement with three outcomes at each site, since the estimator requires $\lambda_j \in \{1, \omega, \omega^2\}$. With three qubits per site spanning an 8-dimensional space, I can use a three-outcome POVM that projects onto the charge-$q$ subspaces.

To implement this POVM, I apply a unitary transformation, measure all three qubits, then classically map the eight measurement outcomes to the three charges. Since charge-0 has four dimensions while charges 1 and 2 each have two, I can encode this by using the last two qubits to determine the charge: the first qubit can be either 0 or 1 for charge-0 states, while charges 1 and 2 each get assigned two of the remaining basis states.

Now I'm constructing an explicit unitary that maps the computational basis states into superpositions that respect this charge structure. I'm defining target mappings where certain basis states map to themselves or to specific superpositions that will collapse to the right charge when measured. I'm realizing I need to think about the block structure more carefully. The 8-dimensional space breaks down by Hamming weight, with each sector containing specific charge states. Within the weight-1 and weight-2 blocks, I need to apply a Z₃ quantum Fourier transform to a qutrit that's encoded using one-hot representation across the three qubits.

Now I'm working out the explicit form of the Z₃ QFT, where the charge-q eigenvector is constructed as a superposition with phases involving powers of ω, the primitive cube root of unity.

I need to find a unitary transformation within the weight-1 sector that maps these Fourier eigenstates to computational basis states, encoding the charge information. The inverse operation would then prepare these states from computational basis inputs, but I'm realizing the relationship between the computational basis and the Fourier basis isn't straightforward—the QFT doesn't simply map individual computational states to individual Fourier states in this case.

The natural choice is to define U such that it maps each Fourier eigenstate directly to a corresponding computational basis state: the charge-0 eigenstate goes to |001⟩, charge-1 to |010⟩, and charge-2 to |100⟩. This makes U the inverse QFT restricted to the weight-1 sector, which I can express as a sum of outer products between the target computational states and the Fourier eigenstates.

Now I need to figure out how to actually implement this on 3 qubits. The challenge is that this unitary only acts meaningfully within each weight sector, so I'd need to first separate those sectors using parity computations, apply the QFT within each one, then extract the charge from the measurement outcomes. But for a practical neutral atom setup, maybe there's a simpler approach—I just need a unitary that, when followed by a Z-basis measurement, gives me outcomes I can map to the charge values.

Let me try constructing this numerically by finding a structured unitary and verifying it produces the right estimator. For the weight-1 sector specifically, I can use the QFT restricted to the one-hot subspace, which has a nice matrix form that maps the basis states into superpositions weighted by powers of ω.

Working through the inverse transformation, I see how the QFT dagger maps these superposition states back to computational basis states, and this gives me the charge encoding I need—where |001⟩ corresponds to charge 0 and |010⟩ to charge 2.

Now for the practical side: I need to implement F† using standard two-qubit gates within the one-hot encoded qutrit subspace. This is a known problem in quantum computing, and the standard approach is to decompose the QFT dagger into Givens rotations that act on pairs of basis states. For a 3×3 QFT, I can express this as a product of two such rotations, each targeting specific planes in the state space. I'm completing the adjoint matrix and realizing this decomposition is getting quite involved, so let me just compute it numerically to find the actual circuit. For neutral atoms specifically, I need to work within the constraint that CZ gates are the native two-qubit operation, which will shape how I build this.
````

````plaintext
Bash Tool: Design the target unitary and verify the charge encoding scheme
````

````plaintext
Thought process: Debugged eigenvector phase conventions and corrected coefficient assignments.

Let me check the eigenvector convention. The issue is the phase convention for the eigenvectors.

$W_{(123)}|a_1,a_2,a_3\rangle = |a_3,a_1,a_2\rangle$

For the weight-1 sector:
$W_{(123)}|001\rangle = |100\rangle$
$W_{(123)}|100\rangle = |010\rangle$
$W_{(123)}|010\rangle = |001\rangle$

So the cycle is |001⟩ → |100⟩ → |010⟩ → |001⟩.


Now I need to construct eigenvectors of this cyclic permutation. If I write a general superposition of these three states and apply the operator, I can match coefficients to find what eigenvalue each component must have. This gives me the constraint that the coefficients must be related by powers of ω. I'm working through the consistency condition—from the coefficient equations, I get ω^{3q} = 1, which confirms the eigenvalue structure. Now I'm constructing the eigenstate |f_q⟩ and verifying it satisfies the cyclic shift property under the operator W. Checking the coefficients: the |100⟩ terms match, and for |010⟩ I need ω^{-q} = ω^{2q}, which holds when ω^{3q} = 1. So the eigenvectors are |f_q⟩ = (1/√3)(|001⟩ + ω^{-q}|100⟩ + ω^q|010⟩), and for q=1 this gives the specific form.

Now I'm comparing my earlier code implementation against the correct formula and realizing I had the phase factors swapped on the |010⟩ and |100⟩ terms—I need to fix that.
````

````plaintext
Bash Tool: Fix eigenvectors and verify the charge encoding scheme
````

````plaintext
Thought process: Architected efficient quantum circuit using Givens rotations.

Interesting. The U matrix has a nice block structure. Let me analyze it more carefully.

Looking at the non-zero entries:
- |000⟩ row: only e0_0 (i.e., |000⟩ eigenstate)
- |001⟩ row: e0_1 (weight-1 sym), e0_2... wait, no, the columns are e0_0=|000⟩, e0_1=|111⟩, e0_2=sym-wt1, e0_3=sym-wt2, e1_0=charge1-wt1, e1_1=charge1-wt2, e2_0=charge2-wt1, e2_1=charge2-wt2


- 
Let me reconsider the mapping. The rows are the computational basis states I'm targeting, and the columns are the eigenstates. I've organized the eigenstates into sectors: e0 contains |000⟩, |111⟩, and the symmetric weight-1 and weight-2 states mapping to computational targets |000⟩, |010⟩, |100⟩, |110⟩; e1 has the charge-1 eigenstates mapping to |001⟩, |101⟩; and e2 continues similarly.

Now I'm tracing through how the unitary U transforms each eigenstate to its corresponding computational basis state, which explains why each row of the matrix has a single nonzero entry corresponding to its eigenstate sector.

I'm realizing the current mapping is awkward because I'm mixing weight sectors—mapping the weight-3 state |111⟩ to |010⟩ breaks the structure. Let me reorganize by respecting weight sectors first, then applying the Z₃ QFT within each sector to keep the circuit cleaner and more systematic.

For the weight-1 sector, I need to map the three basis states to computational states and recognize that the cyclic shift operation acts as |001⟩ → |100⟩ → |010⟩ → |001⟩, which will be key to implementing the QFT. The weight-2 sector follows the same QFT structure but with opposite phases.

Now I'm working through how the QFT diagonalizes this cyclic structure. For a qutrit encoded in one-hot form, I can implement the QFT using Givens rotations. Let me clarify the mapping: if I label the positions as p=0, 1, 2 corresponding to |001⟩, |010⟩, |100⟩, then the QFT should map these position states to Fourier modes in a way that respects the cyclic symmetry.

I'm computing the Fourier basis states explicitly—the equal superposition gives me the zero mode, and the next Fourier mode involves the cube roots of unity with the appropriate phase factors applied to each position state. The inverse transform maps each Fourier eigenstate back to a position eigenstate, revealing the charge through which qubit holds the |1⟩ state. Now I need to figure out how to implement this inverse DFT using CZ gates and single-qubit rotations in the one-hot encoding, which involves decomposing it into Givens rotations that act between pairs of positions. I'm working through how Givens rotations act on one-hot encoded states—a rotation between positions 0 and 1 mixes the |001⟩ and |100⟩ basis states while leaving |010⟩ unchanged, which translates to a controlled 2-qubit gate. Since the DFT matrix has complex entries, I need to account for phases, so I'll compute the Givens decomposition numerically rather than by hand. about this differently. The circuit needs to work on the FULL 8-dimensional space (not just within weight sectors), because we can't condition on weight beforehand (that would require measuring weight first).

However, since the QFT acts independently within each weight sector, and within weight-0,3 sectors it's just identity, the circuit that implements the QFT within weight-1 and weight-2 sectors simultaneously is what we need.

Let me think about which gates accomplish this.

A Givens rotation between positions 0 and 1 in the weight-1 sector (i.e., between |001⟩ and |100⟩) is a gate that acts on qubits 1 and 3. When q₂ = 0, it rotates |01⟩₁₃ ↔ |10⟩₁₃, and when q₂ = 1, it performs the corresponding rotation in the weight-2 sector between |011⟩ and |101⟩. Since this same physical gate on q₁ and q₃ preserves q₂, it simultaneously implements the Givens rotation in both weight sectors. I need to check whether the rotation between positions 1 and 2 in weight-1 works similarly. , which also handles positions 1 and 2 in weight-2 (|101⟩ and |110⟩) automatically.

So the circuit is:
1. Givens rotation on (q₃, q₁) with appropriate angle/phase
2. Givens rotation on (q₁, q₂) with appropriate angle/phase

Each Givens rotation can be compiled into 1 CZ + single-qubit rotations.

This is great! Total: 2 CZ gates + single-qubit rotations. Very efficient for neutral atoms.

Let me compute the exact parameters.

We have the 3×3 QFT†:
F† = (1/√3) [[1, 1, 1], [1, ω, ω²], [1, ω², ω⁴]]

I need to be careful about the indexing convention. The QFT matrix has F_{qp} = (1/√3) ω^{-qp}, so the conjugate transpose gives (F†)_{pq} = (1/√3) ω^{qp}. Rather than work through the algebra, let me just compute this numerically.
````

````plaintext
Bash Tool: Decompose the Z3 inverse QFT into Givens rotations for circuit compilation
````

````plaintext
Thought process: Architected quantum circuit decomposition using Givens rotations and CZ gates.

So the QR decomposition gives:
- 3 Givens rotations (as expected for a general 3×3 unitary)
- But 2 of them are in the (0,1) plane and 1 in the (1,2) plane

The second approach confirms: need 3 Givens rotations total.

But wait, looking at the QR decomposition, it gave a cleaner form:
- G₁₂: zero out (2,0) entry
- G₀₁: zero out (1,0) entry  
- G₁₂: zero out (2,1) entry
Then multiply by diagonal phases.


So F† decomposes as three Givens rotations followed by diagonal phases, where each rotation maps to a 2-qubit gate on the qubits encoding those positions—G₀₁ acts on q₃ and q₁, while G₁₂ acts on q₁ and q₂. Each Givens rotation can be compiled into a CZ gate plus single-qubit rotations.

Now I need to check what happens outside the one-hot subspace. The weight-0 and weight-3 states are unaffected, but I should verify that the weight-2 states also get the correct QFT transformation. The tricky part is that these Givens rotations only act within the one-hot subspace, so they're not standard 2-qubit gates in the full 3-qubit space—they're constrained to specific basis states like |001⟩ when rotating between positions 0 and 1.

Looking at how this actually maps to the physical qubits, a rotation between positions 0 and 1 mixes the (q₃, q₁) subspace, but the behavior depends on whether we're in the weight-1 or weight-2 sector. The gate itself acts the same way on those two qubits regardless of q₂'s state, but the phases might need to differ between sectors to get the correct QFT phases.

Now I'm checking whether the Givens rotation between |001⟩ and |100⟩ inadvertently affects other basis states like |000⟩ and |111⟩—since the gate on (q₁, q₃) only mixes the |01⟩ subspace, those other states should remain untouched.

The key question is whether the same Givens parameters can simultaneously diagonalize the charge operator for both weight-1 and weight-2 sectors, since they have the same cyclic structure under the permutation. The cyclic permutation has the SAME structure in both sectors, so the same QFT works.

But wait, the eigenvectors in weight-2 are:
|g_q⟩ = (|011⟩ + ω^{-q}|101⟩ + ω^q|110⟩)/√3

So the QFT F† should map:
|g_0⟩ → |011⟩ (charge 0)
|g_1⟩ → |101⟩ (charge 1) 
|g_2⟩ → |110⟩ (charge 2)

The same Givens rotations that work on weight-1 also work on weight-2, because the gate on (q₃,q₁) just rotates in the 2D subspace {|0⟩₃|1⟩₁, |1⟩₃|0⟩₁} regardless of q₂. So this single 3-Givens circuit performs the QFT across both weight sectors simultaneously and acts as identity on weight 0 and 3. Each Givens rotation decomposes into a CZ gate plus single-qubit rotations, giving me 3 CZ gates total, though I need to be careful about what exactly each Givens operation is doing in the one-hot encoding—it's mixing the |01⟩ and |10⟩ states. For neutral atoms, I'd execute this as three sequential CZ gates with single-qubit rotations—one on the (q₁, q₂) pair, then (q₃, q₁), then back to (q₁, q₂)—followed by diagonal phases, though those phases don't actually matter for charge readout since they only contribute global phase to each qubit.

So really, the circuit just needs the three Givens rotations implemented as CZ gates plus their accompanying single-qubit rotations. The 3-Givens decomposition breaks down into three inverse rotations applied sequentially: first on qubits q₁ and q₂, then on q₃ and q₁, then on q₁ and q₂ again.

Now I'm working through the measurement readout more carefully. The QFT maps different charge sectors to specific qubit configurations, so I need to figure out which qubit states correspond to which charges depending on whether we're in the weight-1 or weight-2 sector.

I'm building a lookup table that maps all possible 3-qubit measurement outcomes directly to charges, which lets me extract the charge classically from the full measurement result regardless of the sector. Looking at the charge sector structure, I realize I can optimize the readout by choosing a cleaner basis encoding—specifically, I want to minimize how many qubits I need to measure. Since the charge sectors have dimensions 4, 2, and 2, I can use q₃ to separate charge 0 from the others, then use another qubit to distinguish within the smaller sectors.

But this would require a different unitary that reshuffles the weight sectors, whereas the block-diagonal QFT approach gives me a simple lookup table for any 3-bit outcome. Let me stick with that and move forward with the circuit compilation for neutral atoms, then explore whether I can reduce the number of CZ gates needed.

The Z₃ QFT embedded in one-hot encoding requires 3 CZ gates minimum since any 3×3 SU(3) unitary needs at least 3 Givens rotations. Though I'm wondering if there's a completely different encoding or measurement strategy that could distinguish the three charge sectors more efficiently.

Actually, I realize we don't need the full QFT machinery here—just a way to identify which of three charge sectors we're in. The charge projectors decompose nicely: the operator W + W² is Hermitian with eigenvalue 2 for charge 0 and -1 for charges 1 and 2, so I can do a coarse binary measurement first to separate charge 0 from the others, then refine further within the non-zero charge subspace.

The sequential measurement approach with classical feedforward would be cleaner in principle—measure charge 0 first, then conditionally measure charge 1 versus 2—but that's impractical on neutral atom platforms where measurement is slow and destructive. So the full QFT approach with three CZ gates and no feedforward is the most realistic path forward.
````

````plaintext
Bash Tool: Build and verify the full 3-qubit circuit for charge measurement
````

````plaintext
Thought process: Grappled with quantum circuit decomposition challenges and explored alternative strategies.

Hmm, there's a problem. The weight-2 charge-0 eigenstate maps to a superposition of |011⟩, |101⟩, |110⟩. Similarly for charge-1 and charge-2 weight-2 eigenstates. This means the circuit does NOT correctly separate the charges for weight-2 states.

The issue is that the Givens rotations that do the QFT within the weight-1 sector {|001⟩,|100⟩,|010⟩} don't automatically do the correct QFT within the weight-2 sector {|011⟩,|101⟩,|110⟩}.
 
I need to map out how the basis states are ordered in each weight sector to see why the rotations aren't aligning properly. In weight-2, the positions have (q₁,q₃) values of (0,1) and (1,1), which don't match the |01⟩ and |10⟩ pattern needed for the Givens rotation to work correctly—so this approach doesn't properly implement G_{01} for weight-2 states.

The core issue is that the one-hot encoding uses different qubit patterns across weight sectors, meaning a single 2-qubit gate can't implement the same rotation in both. I need to design the full 8×8 unitary more carefully rather than relying on a simple product of 2-qubit gates acting independently within each sector.

My better approach is to construct the unitary U directly as the change-of-basis matrix from the eigenbasis to the computational basis, then decompose it into CZ gates and single-qubit rotations. I'll use q₃ to distinguish charge 0 from the higher charges, mapping the eigenstates systematically to computational basis states for clean readout. I'm realizing the SWAP operator approach might be overcomplicating things. Let me step back and focus on what I actually need: extracting the charge q to compute ω^q for the estimator. Since all charge values have unit magnitude, I just need to capture the phase information efficiently.

Any measurement basis can give an unbiased estimator with proper post-processing, but the charge eigenbasis minimizes variance by maximally distinguishing the three eigenvalues. However, I'm wondering if there's a simpler measurement that's "good enough"—maybe even just measuring all three qubits directly in the computational basis without any circuit overhead, then using the outcomes to post-process the estimator.

But that approach would run into the same cross-term problem as the Hermitianized method. So I need to accept the 3 CZ gate cost and properly compile the circuit. The real issue is that Givens rotations don't act uniformly on weight-1 and weight-2 states, so I'll need additional gates to handle this asymmetry. Let me map out the eigenstate structure more carefully—the charge-0 subspace has four states including the symmetric superpositions, and I need to work through how to project onto each one.

Now I'm looking at the eight eigenstates organized by charge sector, with the charge-1 and charge-2 states built from cyclic permutations with powers of ω. Since |000⟩ and |111⟩ are already computational basis states with charge 0, I can keep them fixed and design a unitary that acts within the remaining subspace to map everything to a clean charge-encoded computational basis.

I notice the eigenstates have structure—they're superpositions over weight-1 and weight-2 states respectively, each weighted by powers of ω. Rather than needing a full 15 Givens rotations for a general 6×6 unitary, I can exploit this structure to use far fewer rotations.

The key insight is that the transformation decomposes into independent Z₃ quantum Fourier transforms acting within each weight sector. The challenge is that these qutrit QFTs operate on different subspaces of the 3-qubit system, but there's a natural relationship between the weight-1 and weight-2 sectors that I can leverage.

Since flipping all bits maps weight-1 states to weight-2 states, the QFT structure is preserved under this bit-flip operation. This means if I can implement the QFT for weight-1 with some circuit, the weight-2 version follows the same pattern conjugated by the all-bit-flip operator. The problem is that I need both transformations to happen simultaneously, which would require the circuit to commute with the bit-flip symmetry—something a Givens-based approach generally won't satisfy. So I'm exploring a different strategy entirely.

Let me reconsider this through representation theory. The underlying symmetry is the cyclic group ℤ₃, and what I really need to measure is the ℤ₃ charge. I can express this charge using projectors onto the different charge sectors, which gives me a cleaner mathematical framework. But I'm wondering if there's a simpler circuit that naturally respects this symmetry structure. I notice that the cyclic permutation operator can be decomposed as a product of two transpositions, which might lead to a more elegant implementation.

Now I'm examining how these swap operations work at the individual qubit level and how they compose across the full system. The key insight is that swaps acting on different sites commute with each other, which means I can rearrange the order of operations and potentially simplify the circuit structure. W_{(123)} factors as a product over sites, where each factor W^{(j)}_{(123)} = S^{(12)}_j S^{(23)}_j is a 3-cycle SWAP on three copies of qubit j. Since I can measure each site independently and multiply the results, the problem reduces to finding a circuit that measures the ℤ₃ charge of this 3-qubit operator.

Let me try a more direct approach—instead of trying to work within weight sectors, I'll just numerically decompose the target unitary into native gates. I need to construct a unitary that maps the weight-0 and weight-3 states appropriately while leaving them invariant under the charge measurement.

Actually, let me step back and use a computational tool like Qiskit to synthesize this directly rather than working through the algebra manually. The key insight is that within the weight-1 sector, three CZ gates are sufficient, but handling the full 8-dimensional space requires additional gates for the weight-2 sector—probably around six CZ gates total for the complete 3-qubit unitary.

There's a more elegant structure I should explore using controlled operations on the full permutation group, or perhaps a simpler circuit construction that naturally respects the symmetry.

Let me try a different approach: apply a CNOT to compute the parity between qubits 1 and 2, which will separate the weight-1 and weight-2 sectors in a cleaner way. Then I can apply the QFT conditionally based on this parity bit, potentially with controlled gates that depend on the outcome.

Actually, I'm overcomplicating this. Let me trace through what happens more carefully when I apply CNOT from q₁ to q₂. The transformation maps |a₁,a₂,a₃⟩ to |a₁, a₂⊕a₁, a₃⟩, so I need to check each weight-1 and weight-2 state individually to see how they map and whether they stay separated.
````

````plaintext
Bash Tool: Synthesize and compile the 3-qubit charge measurement unitary using Qiskit
````

````plaintext
Thought process: Architected efficient quantum circuit using Schur transform decomposition.

19 CZ gates is way too many. The Qiskit general-purpose synthesis is very inefficient for this structured unitary. Let me think about a smarter decomposition.

The problem is that my target unitary mixes weight sectors (e.g., |111⟩ stays at |111⟩ but |S₂⟩ (weight-2 symmetric) goes to |110⟩ which is also weight-2... or actually, it goes to some other state).

The key issue is that the eigenbasis doesn't respect weight sectors in a way that maps cleanly to computational basis.

Let me reconsider the problem. Maybe instead of trying to get the "cleanest" readout encoding, I should use a circuit-friendly encoding.
 
What if I build a unitary that preserves weight sectors and applies the Z₃ QFT within each sector independently? That way the charge information is encoded by position within the sector, and I just need to measure both the weight and the position to extract the charge. The real challenge is implementing these sector-wise QFTs efficiently in a single circuit.

Let me reconsider the structure here. Three qubits span an 8-dimensional space that decomposes under the symmetric group into irreducible representations: a 4-dimensional symmetric part and a 4-dimensional standard representation part. The standard representation actually factors as a 2D spin space times a 2D multiplicity space, and that multiplicity space is exactly where the cyclic group action becomes nontrivial—it rotates by 2π/3. 

The Schur transform is perfect for this because it extracts the multiplicity qubit directly, and it's implementable as a fixed 3-qubit unitary with just a few CZ gates. After applying it, the 8-dimensional space separates cleanly: the symmetric sector gives four states all with charge 0, while the standard representation sector gives four states where the multiplicity qubit encodes the charge information under the cyclic group action.

But wait—I need to be more careful about the charge distribution. The j=1/2 sector has a 2-dimensional multiplicity space where the cyclic group acts as a 2π/3 rotation, giving eigenvalues ω and ω². That means the j=1/2 sector shouldn't have any charge-0 states at all. Let me recount the charge-0 subspace: it should contain the fully symmetric state |000⟩ and its conjugate |111⟩, plus maybe one or two other symmetric combinations, all of which live in the j=3/2 sector.

So the measurement protocol becomes straightforward: first determine whether the state is in the j=3/2 or j=1/2 sector, and if it's j=3/2 then the charge is automatically 0. For j=1/2 states, I need to measure the action of the cyclic operator on the multiplicity space to distinguish between the ω and ω² eigenvalues, which correspond to charges 1 and 2.

The implementation is elegant—I apply the Schur transform to decompose the three qubits into irrep labels, then perform a single-qubit rotation on the multiplicity qubit before measuring. The Schur transform itself is a fixed 3-qubit unitary that's been well-studied in the literature, so I should be able to determine its gate complexity.

Now I'm mapping out the explicit Schur basis states for the two irreps: the j=3/2 symmetric sector and the j=1/2 sector with its multiplicity structure.

For j=1/2, I need to understand how the permutation operator W_{(123)} acts on the multiplicity index μ, since the spin part alone doesn't capture the full structure of these states. ⟩ and the multiplicity part has basis |μ=0⟩, |μ=1⟩.

W_{(123)} acts as identity on the spin part and as a 2×2 matrix on the multiplicity part:

W_{(123)}|_{j=1/2} = I_spin ⊗ R_{mult}

where R_{mult} is the 2×2 representation of the 3-cycle in the standard representation of S₃.

In the Young orthogonal basis:
R_{mult} = representation matrix of (123) in standard irrep of S₃

The standard representation of S₃ has the 3-cycle (123) represented as:
R = [[-1/2, -√3/2], [√3/2, -1/2]]

This is a rotation by 2π/3, as expected, with eigenvalues ω and ω². To diagonalize it, I need to find the basis transformation V that converts the Young orthogonal basis to the eigenbasis of this rotation. The eigenvectors corresponding to ω and ω² give me the charge eigenstates for the multiplicity qubit.

Now I'm verifying that these eigenvectors actually satisfy the eigenvalue equation—checking that applying R to each eigenvector gives the correct eigenvalue multiple back. I'm verifying that the eigenvectors work out correctly—[1,-i]/√2 corresponds to eigenvalue ω and [1,i]/√2 to ω²—which means the matrix V diagonalizes R as diag(ω, ω²). Now I'm checking whether V can be expressed as a product of standard quantum gates, specifically as H·S†. So measuring the multiplicity qubit after applying S†H gives me charge 1 or 2 depending on whether it's in state |0⟩ or |1⟩, while the j=3/2 sector trivially yields charge 0. Now I need to figure out the gate complexity for implementing the Schur transform itself—specifically how many CZ gates are required for the three-qubit unitary, which involves constructing a Clebsch-Gordan transform to couple the spin-1/2 pairs. I need to nail down the specific qubit encoding for the Schur transform—which qubits represent the total angular momentum j, the magnetic quantum number m, and the multiplicity μ. Rather than getting bogged down in the theory, I'll just construct the full Schur transform matrix explicitly and compile it to see what gates I actually need. Looking at how the Schur transform maps computational basis states to the Schur encoding, where each Schur basis vector is constructed as a superposition of computational basis states—for instance, the j=3/2, m=1/2 state is an equal superposition of three computational states scaled by 1/√3. I'm mapping out how the unitary operator transforms the computational basis states into the Schur basis encoding. The state |000⟩ maps to itself since it already represents the j=3/2, m=3/2 state, so the first column of the matrix is straightforward. Now I need to figure out where |001⟩ should map to under this transformation.

Let me reconsider the structure: the unitary should map each Schur basis state (expressed in the computational basis) to its encoded representation, so column i contains the computational encoding vector while the rows represent how the Schur basis states decompose in the computational basis.

After constructing and compiling this transformation, I need to handle the sector-dependent operations: the j=3/2 sector with q₁=0 requires no action since the charge is already zero, while the j=1/2 sector with q₁=1 needs a controlled operation applying S†H to the multiplicity qubit q₃, controlled by q₁.
````

19 CZ 太多了，Qiskit 的通用合成没有利用结构。让我用 Schur transform 的思路重新设计。

````plaintext
Bash Tool: Implement the Schur transform approach for charge measurement
````



## Prompt:
3/4/2026, 10:03:15 PM

```quarto
How to realize the projector $\Pi_r$?
Consider the case $k = 2$. The subspace is split to $\{00,11,01+10\}$ for $+1$ and $01-10$ for $-1$.
To adaptively implement this projector, we notice that the partity of the string is a conservative quantity and use $CNOT_{12}$ to check the parity of the first qubit and then adaptively apply $R_y(\pm \pi/2)$ to the second qubit. That is, we implement the following measurement:
$$
\begin{align*}
\left\{\begin{aligned}
\{\ket{00},\ket{11},\ket{01}+\ket{10}\} \xrightarrow{\text{CNOT}_{12}} \{\ket{00},\ket{10},(\ket{0}+\ket{1})\ket{1}\} \\
\{\ket{01}-\ket{10}\} \xrightarrow{\text{CNOT}_{12}} \{(\ket{0}-\ket{1})\ket{1}\}
\end{aligned}\right.
\end{align*}
$$
where the arrow $\xarr{\text{CNOT}_{12}}$ means the action of $CNOT_{12}$ on the first qubit.
Consider the case $k = 3$. The subspace is split to $\{000,111,001+010+100,011+101+110\}$ for $+1$, $\ket{001}+e^+{i2\pi/3}\ket{010}+e^{i4\pi/3}\ket{100},(\ket{011}+e^{i2\pi/3}\ket{101}+e^{i4\pi/3}\ket{110})$ for $e^{i2\pi/3}$, and $\ket{001}+e^{+i4\pi/3}\ket{010}+e^{i8\pi/3}\ket{100},(\ket{011}+e^{i4\pi/3}\ket{101}+e^{i8\pi/3}\ket{110})$ for $e^{i4\pi/3}$.

To adaptively implement this projector, we again notice that the partity of the string is a conservative quantity and use (t.b.c.)

```

接着这个思路往下写证明，我想用adaptive measurement 测量



## Response:
3/4/2026, 10:18:10 PM

````plaintext
Thought process: 探索了Z₃自适应测量的理论障碍与实现方案。

The user wants to implement the $\mathbb{Z}_3$ charge measurement adaptively, following the pattern established for $k=2$ (SWAP eigenbasis). Let me think through this carefully.

For $k=2$: CNOT extracts parity into qubit 2, then adaptive measurement on qubit 2 (Z if parity 0, X if parity 1) distinguishes the eigenspaces.

For $k=3$: We need to distinguish charge $q \in \{0, 1, 2\}$ of $W_{(123)}$ acting on 3 qubits.

The key structure:
- Weight 0,3: $|000\rangle, |111\rangle$ — automatically charge 0


- Weight 1: orbit $\{|001\rangle, |100\rangle, |010\rangle\}$ — contains charges 0, 1, 2
- Weight 2: orbit $\{|011\rangle, |101\rangle, |110\rangle\}$ — contains charges 0, 1, 2

First I'll extract weight information using parity checks with CNOTs, then within each weight sector apply a $\mathbb{Z}_3$ QFT adaptively. For the adaptive strategy, I'm following the $k=2$ pattern where the first measurement outcome determines what basis to use for subsequent measurements.

Now extending this to $k=3$: after applying CNOT$_{1\to 2}$ and measuring qubit 2, I need to determine the parity structure and then use conditional measurements to resolve the charge within each weight sector. and for the other cases, I need to apply a $\mathbb{Z}_3$ quantum Fourier transform to extract the remaining degree of freedom. Let me trace through the CNOT cascade more carefully—I need to verify exactly how each gate transforms the basis states, starting with CNOT$_{1\to 2}$ acting on qubits 1 and 2, then CNOT$_{2\to 3}$ on qubits 2 and 3. I need to reconsider the structure here. The key insight is that the cyclic permutation within the weight-1 sector acts as a 3-cycle on the basis states, so I should think about how to extract information adaptively using sequential measurements with conditional bases. Let me start by applying a CNOT from qubit 1 to qubit 2 to extract their parity, then see how that constrains the measurement strategy for the remaining qubits. (q2 unchanged since q1=0)
- $|100\rangle \to |110\rangle$ (q2 flipped since q1=1)
- $|010\rangle \to |010\rangle$ (q2 unchanged since q1=0)

The charge eigenstates each transform by flipping q2 when q1=1, leaving the $|001\rangle$ component invariant while the other basis states pick up the phase factors from the original superposition.

Now measuring qubit 2: if it comes out 0, I'm left in the subspace where q1=0, which means the post-measurement state is a superposition of $|001\rangle$ and $|010\rangle$ with amplitudes $\alpha$ and $\beta$. Let me reconsider the eigenvector structure. The cyclic permutation $W$ acts on the weight-1 orbit by rotating through $|001\rangle \to |100\rangle \to |010\rangle \to |001\rangle$, so the charge-$q$ eigenvector should be $|f_q\rangle = \frac{1}{\sqrt{3}}(|001\rangle + \omega^{-q}|100\rangle + \omega^q|010\rangle)$. Now I need to find the eigenvectors of this cyclic action. I've verified that the eigenvectors are correct, and now I'm applying the CNOT gate to see how the state transforms, then analyzing what happens when I measure the second qubit. When $q_2 = 1$, the remaining state encodes the value of $q$ in the relative phase between the two computational basis states—specifically, the phase factor $\omega^q$ appears on the $|1,0\rangle$ term, which means measuring $q_1$ will give us information about $q$ through this phase relationship.

However, I'm running into a fundamental problem: I need to distinguish three possible phases ($1, \omega, \omega^2$) using a single qubit measurement, but a projective measurement on one qubit can only yield two outcomes. The naive approach of just measuring $q_1$ won't work for $\mathbb{Z}_3$ since I can't extract three distinct results from a binary measurement.

I need to reconsider the strategy—maybe $q_3$ plays a role I haven't fully exploited yet. still present. After measuring $q_2 = 1$, we have the state:
$\propto \omega^{-q}|1\rangle_1|0\rangle_3 + \omega^{-2q}|0\rangle_1|0\rangle_3$

So $q_3 = 0$ deterministically. The information is only in $q_1$.

So with outcome $q_2 = 1$: state of $q_1$ is $\alpha|0\rangle + \omega^q \alpha|1\rangle$ (up to global phase), and we need to distinguish 3 phases with 1 qubit. This is indeed impossible with a single projective measurement.

But when $q_2 = 0$, we get $|0,0,1\rangle$, which carries no charge information—and this happens with probability 1/3. So the CNOT$_{1\to 2}$ approach fails because it loses information a third of the time, and even when it doesn't, we're left with an impossible 3-phase discrimination problem on a single qubit.

I need to reconsider the structure entirely. For $k=3$, maybe a sequential measurement strategy would work better—measuring qubit 3 first in the Z basis, then adapting the measurement of qubits 1 and 2 based on that outcome.

Actually, the real issue is that the $\mathbb{Z}_3$ QFT on a 3-element set can't be implemented with just binary measurements. The charge eigenstates in the weight-1 sector are genuinely qutrit states embedded in the 3-qubit space, and distinguishing 3 states requires at least 2 bits of information.

The charge eigenstates have the form $|f_q\rangle = \frac{1}{\sqrt{3}}(|001\rangle + \omega^{-q}|100\rangle + \omega^{-2q}|010\rangle)$, which is fundamentally a 3-level system. To distinguish all three charge values, I need an adaptive protocol that extracts 2 bits of information from the 3-qubit system.

Let me work through the adaptive measurement strategy: I'll apply CNOT gates to entangle the qubits in a way that maps the phase information into the computational basis. First, applying CNOT$_{1\to 2}$ transforms the state, then CNOT$_{1\to 3}$ further entangles the qubits so that the charge information becomes accessible through measurements.

Actually, I'm realizing the direct approach is getting messy with all these phase factors. Let me reconsider—for $k=2$, the SWAP operator has a clean $\mathbb{Z}_2$ structure that naturally encodes into a single bit, but for $k=3$, I need to work with $\mathbb{Z}_3$ and extract 2 bits of information. Maybe I should try a different CNOT configuration that better captures the cyclic symmetry.

I'm testing a two-step CNOT extraction: first applying CNOT from qubit 1 to qubit 3, which transforms the charge eigenstate by flipping qubit 3 based on qubit 1's state, then applying CNOT from qubit 2 to qubit 3 to further entangle the information. After both operations, the resulting state encodes the cyclic structure in a way that should be measurable.

Now measuring qubit 3 to extract information about the charge. When I measure 0, I get a deterministic outcome that's independent of q, which doesn't help distinguish charges. When I measure 1, qubit 1 collapses to 0 deterministically while qubit 2 ends up in a superposition with phases dependent on q—but this still leaves me with the same fundamental problem of having three distinct phases to distinguish with limited measurement outcomes.

The core issue is that three qubits can only give me one bit per measurement, but I need log₂3 bits total to fully specify a qutrit. However, with adaptive measurements I could measure the first qubit, condition on the result, then measure the remaining qubits differently based on what I learned. After the first measurement collapses the qutrit information into phase information on a single qubit, I should be able to extract that phase information with a second measurement.

But here's the problem: those three phase states form a symmetric trine ensemble—they're non-orthogonal and can't be perfectly distinguished by any measurement. This is a fundamental limitation. Though interestingly, this only applies to the weight-1 and weight-2 sectors; within those sectors the eigenstates are actually orthogonal.

The real issue is that we're trying to project a 3D structure onto binary measurements. I need entangling gates between qubits within the sector to properly resolve this. What I actually need is a $\mathbb{Z}_3$ QFT acting on the 3D subspace to map to orthogonal computational basis states—that requires 2-qubit gates.

The key insight is to stop thinking about extracting parity first and then measuring. Instead, I should use a sequence of conditional operations that progressively refine the charge measurement, like building a decision tree that separates the weight-0 sector first.

Let me work out the concrete protocol: apply a CNOT gate between qubits 1 and 2, which entangles them in a way that creates distinguishable patterns across the different charge sectors, then measure strategically to extract the charge information.

Actually, organizing this as a measurement tree makes more sense—I can partition the three-qubit states by their Hamming weight and design measurements that efficiently distinguish between charges within each weight sector. Looking at the weight-1 and weight-2 charge eigenstates more carefully. For weight-1 with charge q, I need to construct the proper superposition across the three single-qubit basis states, and for weight-2, I'm realizing that when q₃ = 0, only specific terms survive from the full eigenstate. When $q_3 = 1$, the measurement collapses to a product state with no phase information about the charge—this outcome occurs with probability 1/3 and is useless. But if $q_3 = 0$, I'm left with a superposition on qubits 1 and 2 that encodes the charge through a relative phase $\omega^{-q}$, which happens with probability 2/3.

I'm trying to extract this phase by applying a CNOT gate to transform the entangled state, then measuring to see if I can isolate the charge information, but the approach isn't working cleanly. I'm realizing the core problem: the three charge states are encoded in an entangled subspace across all three qubits, so any single-qubit measurement will inevitably collapse to a situation where three non-orthogonal states remain on one qubit, making perfect discrimination impossible.

But wait—that reasoning seems off. The $k=2$ case shows that CNOTs can disentangle the weight-1 eigenstates by effectively performing the $\mathbb{Z}_2$ Fourier transform within that sector. For $k=3$, I need a similar strategy: a sequence of two-qubit gates that implements the $\mathbb{Z}_3$ QFT within the weight sectors, which requires something more sophisticated than just CNOTs.

The user is asking for an adaptive measurement approach like we had for $k=2$. That's trickier—I can't achieve it with only Clifford gates and adaptive measurements. I need at least one non-Clifford gate, specifically a $2\pi/3$ phase gate, to make this work.

Let me trace through a concrete protocol starting with a CNOT from qubit 1 to qubit 2, then examining how the weight-1 eigenstates transform and what happens to the superposition states...

After measuring the first qubit, I'm tracking the conditional states on the remaining qubits and the relative phases that encode information about $q$.

Now I'm applying a CNOT gate to entangle qubits 2 and 3, which transforms the state into a superposition of $|01\rangle$ and $|11\rangle$ with a phase factor $\omega^q$ between them. The resulting state on qubit 2 is a trine state—one of three equally-spaced points on the Bloch sphere—which means I can't distinguish it perfectly with a single measurement.

When I condition on $q_1 = 1$, I get a deterministic outcome with an unobservable global phase, so there's no way to extract the charge information. This approach fails with probability 1/3.

I'm realizing that perfect charge discrimination for $\mathbb{Z}_3$ using only sequential single-qubit measurements is fundamentally impossible—I need at least one two-qubit gate applied *after* a measurement to make the protocol adaptive. The key insight is that measuring $q_1$ after the initial CNOT gives no information when the outcome is 1, so I need a different strategy that uses adaptive gates to extract the charge.

Let me explore whether using two CNOTs to create a binary encoding of the position within the weight-1 subspace might work better than this complicated conditional approach. I'm stepping back to reconsider what the user actually needs—they want to generalize the $k=2$ parity extraction approach to $k=3$. The strategy would be using CNOTs to extract modular information, then measuring and adapting based on outcomes. I'm recognizing that the cyclic shift operation within weight-1 states forms a $\mathbb{Z}_3$ structure, which is the key to understanding the charge information in this case. I see that the cyclic shift can be decomposed using SWAPs—specifically, swapping qubits 1 and 2, then 2 and 3 gives the 3-cycle, and since each SWAP requires 3 CNOTs, that's 6 CNOTs total. But actually, I don't need to implement the full cyclic permutation; what I really need is to diagonalize it. Let me shift perspective entirely and think about the actual circuit requirements. For measuring the $\mathbb{Z}_3$ charge on 3 qubits, there's a theoretical minimum of around 2 two-qubit gates plus single-qubit rotations, which comes from the Schur transform decomposition for this system.

Now looking at this practically through Qiskit, the generic synthesis gives 19 CZ gates, but that's because it doesn't take advantage of the block structure. Let me work through the optimal decomposition manually. The space naturally splits into four sectors based on Hamming weight: the 1D sectors at weight 0 and 3, and the 3D sectors at weights 1 and 2. Within those 3D sectors, I need to apply a $\mathbb{Z}_3$ QFT, which is the core operation that needs optimization.

For the weight-1 sector specifically, I'm looking at how to map three superposition states—each encoding different charge labels 0, 1, and 2—into target states using the minimal number of entangling gates. should be distinguishable by measuring in the computational basis.

One natural choice: $|f_0\rangle \to |001\rangle$, $|f_1\rangle \to |010\rangle$, $|f_2\rangle \to |100\rangle$ (inverse QFT maps Fourier modes back to position states).

The inverse QFT is: $F_3^{-1} = F_3^\dagger$, which maps position $\to$ Fourier mode. Wait, actually $F_3$ maps position to Fourier, so $F_3^{-1}$ maps Fourier back to position.

So we need the circuit to implement $F_3^{-1}$ within the weight-1 (and weight-2) sectors, while acting as identity on weight-0,3.

For an adaptive measurement approach, I can apply entangling gates to partially resolve the Fourier structure, then measure and conditionally apply more gates based on the outcomes. Starting with a CNOT from qubit 1 to qubit 2 separates the weight-1 states into two groups: $|001\rangle$ and $|010\rangle$ both have qubit 1 in state 0, while $|110\rangle$ has qubit 1 in state 1, which gives me a way to distinguish them with a measurement.

When I measure qubit 1 and get outcome 1, I deterministically collapse to $|110\rangle$, which corresponds to the original state $|100\rangle$ with probability 1/3 and no charge information. If I get outcome 0, the state becomes a superposition of $|001\rangle$ and $|010\rangle$ where the relative phase encodes the charge value, specifically $\frac{1}{\sqrt{2}}(|001\rangle + \omega^{-2q}|010\rangle)$, which I can then distinguish by measuring in the computational basis.

Now applying a CNOT gate with qubit 2 as control and qubit 3 as target flips qubit 3 when qubit 2 is 1, transforming the state into $|1\rangle_3 \otimes \frac{1}{\sqrt{2}}(|0\rangle_2 + \omega^{-2q}|1\rangle_2)$, which factors the charge information into qubit 2's superposition.

When I measure qubit 3 in Step 4, it always collapses to 1 in this case, giving no additional information. The remaining qubit 2 is left in a superposition that depends on the charge value—either $|+\rangle$ for $q=0$, or a rotated version for $q=1$ or $q=2$. This is a trine discrimination problem where the three states are equally spaced on the Bloch sphere, and the best I can do with an optimal POVM is 2/3 success probability. But I need perfect discrimination, which means I've hit a fundamental limitation by collapsing down to a single qubit.

The real issue is that I'm losing information too early. Instead of measuring individual qubits sequentially, I should use an entangling gate to couple the qubits before measurement, allowing me to extract more information from their joint state. Or perhaps I need to rethink the CNOT pattern entirely—maybe applying a CNOT from qubit 1 to qubit 3 first would give me a better way to split the problem and preserve the distinguishability of the charge states.

Let me trace through what happens with this new gate sequence: after applying CNOTs from both q₁ and q₂ to q₃, the superposition gets mapped to a state where q₃ becomes entangled with the charge information. When I measure q₃, the outcome either gives me no information (if q₃ = 0) or collapses the remaining state on q₁ and q₂ into a form where the charge q is encoded in the relative phase between the two basis states—specifically, the phase depends on 2q, which means I can now distinguish all three charges by measuring q₂ in the appropriate basis. Probability 2/3.

Same problem.

**I think the key realization is:** Any sequence of CNOTs on 3 qubits in the weight-1 sector will inevitably produce a "failure branch" with probability 1/3 (where one position state collapses deterministically), and a "success branch" with the remaining 2 states having a relative phase that encodes charge — but as a trine on 1 qubit.

This suggests that **purely adaptive Clifford + Z measurements cannot perfectly implement $\mathbb{Z}_3$ charge measurement**.

But wait — the user mentioned adaptive measurement like in the $k=2$ case. In the $k=2$ case, the adaptive part was measuring X instead of Z (which is a Clifford rotation). For $k=3$, the analogous operation would be measuring in the $\mathbb{Z}_3$ QFT basis, which requires a non-Clifford rotation.

So the correct adaptive protocol for $k=3$ would start with a CNOT from qubit 1 to qubit 2, then measure qubit 1 — if it's 1, that's inconclusive with probability 1/3, but if it's 0, I can proceed to apply another CNOT from qubit 2 to qubit 3, which forces qubit 3 into a definite state while leaving qubit 2 in a superposition that encodes the charge information.

The issue is that after this setup, the state on qubit 2 contains the charge as a relative phase, but distinguishing three equally-spaced phases on a single qubit requires a non-Clifford rotation — specifically, a rotation by $2\pi/3$ in the $\mathbb{Z}_3$ QFT basis.

I'm realizing that the fundamental limitation here is that you can't perfectly distinguish 3 states on a single qubit using only Clifford operations and computational basis measurements, whereas the $k=2$ case works because 2 states fit perfectly in a 2D Hilbert space.

The revised approach is to keep both qubits and perform a 2-qubit measurement instead of trying to compress everything down to 1 qubit. After the CNOT, measuring the first qubit immediately tells us if we're in the $|100\rangle$ component (probability 1/3), and if not, the remaining state on the second and third qubits is a superposition that can be distinguished with a proper 2-qubit measurement.

Now I'm checking whether these three remaining states are actually orthogonal in the 2-qubit space. The inner product calculation shows that orthogonality depends on whether $\omega^{2(q-q')} = -1$, but since $\omega^2 = e^{i4\pi/3}$, this condition isn't satisfied...

Actually, computing the inner product more carefully: for adjacent states where $q' - q = 1$, I get $\frac{1}{4} - i\frac{\sqrt{3}}{4}$, which is definitely nonzero. So these three states aren't orthogonal after all—they must all be confined to some lower-dimensional subspace.

The real constraint is that after measuring $q_1$ first, we collapse into a 2D subspace spanned by $|01\rangle$ and $|10\rangle$, but we're trying to distinguish three orthogonal states there, which is impossible. This reveals the fundamental limitation: an adaptive protocol measuring $q_1$ first can never achieve perfect charge measurement.

The only way forward is to apply a unitary transformation that maps all three charge eigenstates to orthogonal computational basis states before any measurement—essentially the $\mathbb{Z}_3$ QFT circuit embedded in three qubits. So for the write-up, the key insight is that perfect adaptive measurement isn't feasible with this measurement order, and the non-adaptive circuit we derived earlier is actually the necessary solution.

But I'm wondering if there's a cleverer adaptive approach using 2-qubit gates strategically. Instead of measuring single qubits adaptively, what if I apply adaptive 2-qubit gates between different pairs of qubits, then measure? The idea would be to use the measurement outcomes to guide which 2-qubit gates to apply next, effectively implementing the full $\mathbb{Z}_3$ QFT adaptively. Let me work through whether this can actually distinguish the three weight-1 states.

I'll use Givens rotations between qubit pairs, choosing angles that implement partial QFT steps. Since the $\mathbb{Z}_3$ QFT decomposes into three Givens rotations in sequence, I can potentially spread these across adaptive steps where each measurement outcome determines which rotation to apply next. I'm laying out two concrete implementation strategies: a straightforward non-adaptive approach using the $\mathbb{Z}_3$ QFT with a measurement lookup table, versus an adaptive method that decomposes the inverse QFT into sequential Givens rotations with phase corrections, where each rotation acts on specific qubit pairs.

The adaptive approach measures qubits progressively—after each Givens rotation, the measurement outcome determines which subsequent gate to apply—which should deterministically pin down the charge value. But I'm realizing this is getting unwieldy, so let me step back and use the $k=2$ case as a simpler template to build intuition.

For $k=2$, I need one bit to distinguish the two charge sectors, which a CNOT can extract via parity measurement, then an adaptive Clifford measurement on the remaining qubit completes the protocol. For $k=3$, I'll need roughly two CNOTs and adaptive non-Clifford gates to resolve the three charge values. Let me sketch out the concrete steps: first apply a CNOT from qubit 1 to qubit 2, which maps the weight-1 basis states in specific ways that help separate the charge information.

After measuring the first qubit in the Z basis, I get one of two outcomes—if it's 1, the state collapses to a definite position (the "1" was in position 1), but if it's 0, I'm left in a superposition of the remaining two positions and need further adaptive measurements to pin down which one.

Now when q₁ = 0, the remaining state on qubits 2 and 3 is a superposition that depends on the hidden value q. I apply a CNOT gate from qubit 2 to qubit 3, which flips qubit 3 when qubit 2 is 1, transforming the superposition accordingly.

Then I try applying a phase gate on qubit 2 to see if that helps distinguish the states, but the fundamental issue persists: I'm trying to distinguish three non-orthogonal quantum states encoded on a single qubit, which isn't possible with certainty. The adaptive protocol for k=3 simply cannot achieve perfect discrimination.

But there's a workaround—I could design a probabilistic protocol that succeeds with probability 2/3 and returns inconclusive otherwise, similar to unambiguous state discrimination. Alternatively, I could use a POVM-based approach that minimizes error probability. Let me reconsider whether I'm actually forced to collapse everything to a single qubit, or if I can preserve information across multiple qubits by using a CNOT and measuring strategically.

If I measure the first qubit after a CNOT, getting 1 tells me the position but makes all charges equally likely due to the Fourier duality between position and charge—so that's inconclusive. But if I get 0, I'm left with a 2-qubit state spanning just two basis states. From there, I can apply a carefully chosen unitary rotation within that 2D subspace to help distinguish the three charge states.

However, there's a fundamental problem: a 2D Hilbert space can only accommodate two orthogonal states, so three distinct charge states can never be perfectly distinguished in this subspace.

For the $k=3$ case, I need to measure the $\mathbb{Z}_3$ charge using a 3-outcome projective measurement in the full 3D weight sector, which means applying the $\mathbb{Z}_3$ QFT circuit followed by a standard measurement. Adaptive protocols are limited to approximate discrimination with error probability at least 1/4 for trine states.

But here's the key insight: perfect charge discrimination isn't actually necessary for constructing an unbiased estimator. The estimator $\hat{o} = \prod_j \lambda_j$ can work with a POVM that captures the correct expected value of $\omega^q$.

More broadly, any POVM $\{M_\lambda\}$ satisfying $\sum_\lambda \lambda M_\lambda = W_{(123)}$ gives an unbiased estimator—the charge measurement is one option, but the cascaded SWAP measurement from the Hermitian approach is another, though it introduces higher variance and cross-terms at multiple sites.

The real question is whether we can design an adaptive POVM on three qubits that yields exactly $W_{(123)}$ as its effective operator. Since $W_{(123)}$ is non-Hermitian, the outcomes $\lambda$ must be complex, and while the spectral theorem identifies the charge measurement as the unique projective measurement with this property, we might also construct a non-projective POVM that works.

The catch is that any POVM built from adaptive single-qubit measurements lives in the algebra generated by local observables and classical conditioning, which doesn't contain the non-local permutation $W_{(123)}$. But wait—the two-qubit SWAP case shows this isn't a fundamental obstruction: the Bell measurement (implemented via CNOT and Z measurements) does extract SWAP eigenvalues despite SWAP being non-local. The key difference is that SWAP has only two eigenvalues, and the charge eigenstates within each weight sector are at most two-dimensional, so a binary measurement suffices. For three qubits, the weight sectors become three-dimensional, demanding a three-outcome measurement instead. So the resolution requires two-qubit adaptive measurements.

The protocol would interleave two-qubit gates with adaptive single-qubit measurements: apply a two-qubit gate to the first pair, measure one qubit, then conditionally apply another two-qubit gate to the remaining pair based on that outcome, measure again, and finally determine the charge from all measurement results. This mirrors the two-qubit case where the CNOT serves as the two-qubit gate and adaptive X/Z measurements follow. I'm now working out the explicit construction using the QR decomposition of $F_3^\dagger$.

From the QR factorization, I can express $F_3^\dagger$ as a sequence of three Givens rotations applied to different qubit pairs, each with specific angles and phases, followed by a diagonal phase correction.

The protocol works adaptively: applying $G_{12}'$ to qubits 1 and 2 zeros out a specific matrix element, then measuring determines one qubit's position; $G_{01}$ applied adaptively to qubits 0 and 1 zeros out another element and determines the next qubit; finally measuring qubit 2 gives the remaining information. The key insight is that these left-multiplied Givens rotations systematically eliminate columns of the QFT matrix to achieve upper triangular form. Now I'm working through the QR decomposition column by column, starting with the first Givens rotation to zero out the (2,0) entry using the parameters I computed. entry (2,1) using Givens $G_{12}'(\theta_3, \phi_3)$. From the calculation, I get $c_3 = -1/\sqrt{2}$ and $s_3 = -i/\sqrt{2}$.

These three Givens rotations transform $F_3^\dagger$ into upper triangular form $R$, where $F_3^\dagger = G_{12}^{-1} G_{01}^{-1} G_{12}'^{-1} R$.

For the adaptive interpretation, the circuit $U = G_{12}'^{-1} \cdot G_{01}^{-1} \cdot G_{12}^{-1}$ (setting aside the diagonal scaling) converts charge eigenstates into position states. In the adaptive protocol, I apply $G$

After applying the inverse transformation $U^{-1} = D \cdot G_{12}^{-1} \cdot G_{01}^{-1} \cdot G_{12}'^{-1}$ to the charge eigenstates, I recover the position states. Rather than continuing down this abstract path, I should just lay out the adaptive protocol step by step.

For the $k=3$ case, the cleanest approach is to present the Givens decomposition from the numerics as three rotation gates (each implemented with one CZ and four single-qubit rotations), explain how this naturally admits an adaptive interpretation through QR decomposition, and note that only measuring q₁ and q₃ is necessary since q₂ is determined by charge conservation. I'll contrast this with the $k=2$ case to highlight where non-Clifford gates become essential.

The adaptive protocol works as a decision tree: the first Givens rotation separates one charge from the pair, measurement gives the first bit; the second rotation refines among the remaining possibilities, measurement gives the second bit; the third measurement confirms but is technically redundant. This extracts exactly 2 bits of information, sufficient to distinguish the three non-zero charges. I see that the final Givens rotation in step 3 uses a $\pi/4$ angle with an imaginary phase component, and I can decompose all three of these rotations into CZ gates paired with single-qubit operations, following the same approach used in the circuit design.
````

这是一个非常深刻的问题。让我严格分析为什么 $k=2$ 的自适应方案不能直接推广到 $k=3$，然后给出正确的自适应协议。

## 为什么 $k=2$ 的方案不直接推广

回顾 $k=2$ 的成功原因：SWAP 的 $\mathbb{Z}_2$ charge 在每个 weight sector 内至多有 **2 个态**（$|01\rangle \pm |10\rangle$），而 1 qubit 的投影测量恰好能区分 2 个正交态。

对 $k=3$，$\mathbb{Z}_3$ charge 在 weight-1 sector 内有 **3 个正交态**：

$$|f_q\rangle = \frac{1}{\sqrt{3}}\big(|001\rangle + \omega^{-q}|100\rangle + \omega^{-2q}|010\rangle\big), \quad q \in \{0,1,2\}$$

如果我们仿照 $k=2$，做 CNOT$_{1\to 2}$ 再测 $q_1$：

$$|f_q\rangle \xrightarrow{\text{CNOT}_{1\to 2}} \frac{1}{\sqrt{3}}\big(|001\rangle + \omega^{-q}|110\rangle + \omega^{-2q}|010\rangle\big)$$

测量 $q_1$：

- **$q_1 = 1$**（概率 $1/3$）：塌缩到 $|110\rangle$。这来自 $|100\rangle$ 分量，全局相位 $\omega^{-q}$ 不可观测。**无 charge 信息。**

- **$q_1 = 0$**（概率 $2/3$）：剩余态

$$\frac{1}{\sqrt{2}}\big(|0\rangle_2|1\rangle_3 + \omega^{-2q}|1\rangle_2|0\rangle_3\big)$$

再做 CNOT$_{2\to 3}$ 解纠缠后，$q_2$ 的态为 $\frac{1}{\sqrt{2}}(|0\rangle + \omega^q|1\rangle)$，这是 **symmetric trine**：

$$q=0:\;|+\rangle, \quad q=1:\;\frac{|0\rangle + \omega|1\rangle}{\sqrt{2}}, \quad q=2:\;\frac{|0\rangle + \omega^2|1\rangle}{\sqrt{2}}$$

三个非正交态在 2 维 Hilbert 空间中，**任何单 qubit 测量都无法完美区分**。

**根本障碍：** 3 个正交 charge 态嵌入在 3D weight sector 中。任何将其投影到 2D（单 qubit）的操作都必然丢失信息，因为 2D 中最多容纳 2 个正交态。

````plaintext
Bash Tool: Derive the adaptive protocol and gate compilation for Z3 charge measurement
````

````plaintext
Thought process: 验证了自适应测量协议，追踪决策树并确认QR分解的关键洞察。

Now let me verify the adaptive protocol by tracing through the decision tree more carefully, then write up the complete answer.

The key insight from the QR decomposition is:

After G₁ (Givens on positions 1,2):
- Charge 0: all amplitude in positions 0,1 (pos 2 = 0)
- Charge 1: amplitude in all 3 positions (pos 2 has 50%)
- Charge 2: amplitude in all 3 positions (pos 2 has 50%)

So measuring "position 2" after G₁:
- If "yes" → charge is 1 or 2 (never 0)


- If "no" → the measurement collapses to the {0,1} subspace, but I still need to distinguish all three charges probabilistically based on the conditional probabilities

The measurement outcome determines which subproblem I face: if position 2 is detected, I've eliminated charge 0 and need to distinguish between 1 and 2 on the remaining system; if not detected, I'm back to a three-way distinction on a two-dimensional space, which is the trine problem again.

After the first measurement projects onto positions {0,1}, I'm realizing something crucial—charges 1 and 2 become indistinguishable in this subspace even though charge 0 remains distinguishable from them. This means the "not pos 2" branch doesn't actually give me the full information I need to separate all three charges. Hmm, that's a problem. Let me re-examine.

After G₁, the charge states are:
- q=0: (1/√3, √(2/3), 0) 
- q=1: (1/√3, -1/√6, -i/√2)
- q=2: (1/√3, -1/√6, +i/√2)

If we measure and get "not position 2" (positions 0 or 1):
- q=0: amplitude in {0,1} = (1/√3, √(2/3)), probability = 1/3 + 2/3 = 1
- q=1: amplitude in {0,1} = (1/√3, -1/√6), probability = 1/3 + 1/6 = 1/2

For q=2, the same calculation gives (1/√3, -1/√6) with probability 1/2. The key issue is that charges 1 and 2 project identically onto the {pos 0, pos 1} subspace—the distinguishing information was encoded in the position 2 component with those ±i phases, which we've now lost. So measuring "not position 2" collapses us into a branch where we can only tell charge 0 apart from the {1,2} pair, but not distinguish between them. The protocol needs to handle this by using the position 2 branch to separate charges 1 and 2. to distinguish 1 vs 2
Branch 2 (not pos 2): can distinguish 0 from {1,2}, but cannot distinguish 1 from 2

This means the adaptive protocol based on measuring "position 2 first" can:
- Identify charge 0 perfectly in branch 2
- Distinguish charge 1 vs 2 in branch 1 (need one more measurement)
- But in branch 2, charges 1 and 2 are indistinguishable

So the overall success probability for perfect charge identification is NOT 100%.

Actually wait, let me reconsider. In the non-adaptive version, all 3 Givens are applied before measurement. In the adaptive version, we measure after each Givens. The problem is that measurement collapses the state and loses the relative phase information between different position components.

The conclusion is: perfect $\mathbb{Z}_3$ charge measurement requires the full non-adaptive circuit with all three Givens applied upfront before measuring. Adaptive protocols with intermediate measurements destroy the phase information needed for perfect discrimination. This is fundamentally different from the $k=2$ case, where $\mathbb{Z}_2$ charge only needs 1 bit and can be extracted adaptively.

But wait—what if I use two-qubit gates between measurements instead? After measuring "not pos 2" and conditioning on that outcome, I could apply the second Givens $G_{01}$ and then measure again. Let me trace through what happens to the q=1 and q=2 states after the first Givens and measurement.

After the first measurement conditioning on "not pos 2", the q=1 and q=2 states become identical in the {pos 0, pos 1} subspace. Any further unitary applied to these identical states will keep them identical—the information is irretrievably lost. This confirms that adaptive protocols with intermediate Z-basis measurements cannot achieve perfect $\mathbb{Z}_3$ charge discrimination.

The non-adaptive approach works: apply all three Givens rotations upfront, then measure all three qubits in the Z basis and decode via a lookup table. But I'm wondering if a hybrid strategy could work—apply two Givens non-adaptively, measure position 2, then conditionally apply the third Givens based on that outcome. After the first two rotations, q=0 sits deterministically at position 0, while q=1 and q=2 both spread equally across positions 1 and 2. If the measurement finds position 0, we've identified q=0 with certainty, but when position 0 isn't measured, the q=1 and q=2 states remain indistinguishable.

Now I'm checking whether these two states in the {pos 1, pos 2} subspace are actually orthogonal by computing their inner product. The states are orthogonal, so a single rotation can distinguish them. The optimal adaptive protocol applies the first two Givens rotations non-adaptively, measures the charge-0 indicator, and only applies the third rotation if needed—this saves one gate operation a third of the time. Actually, we could just apply all three rotations and measure, keeping the adaptive measurement as the distinguishing step.

But the user wants a true adaptive measurement protocol where intermediate results guide subsequent operations. So I should present both options: a non-adaptive version that applies all three rotations then measures everything at once, and a semi-adaptive version that measures after the first two rotations to determine whether the third is necessary.

The semi-adaptive approach has a practical advantage—when the outcome indicates charge 0, we can skip the final rotation entirely, saving one CZ gate roughly half the time. But I need to be careful about how the circuit operates across both weight sectors simultaneously, since the "positions" aren't defined in the full 8-dimensional space but rather within each weight sector.

Let me structure the answer clearly: first explain why the naive CNOT-based approach with adaptive measurements hits a fundamental obstruction, then present the Givens rotation circuit as the working solution, and finally show how the semi-adaptive variant can optimize for certain outcomes.

For the explicit construction, I'm extracting the Givens parameters from the QR decomposition—the first rotation acts on copies 1 and 2 with angle π/4 (a beamsplitter), the second couples copies 3 and 1 with angle arccos(1/√3), and the third involves copies 1 and 2 again but with a phase shift. Each Givens rotation compiles to one CZ gate plus a handful of single-qubit gates, so the full circuit requires 3n CZ gates across n sites, which is quite efficient for neutral atom implementations.

Now I need to write out the complete adaptive measurement protocol and verify numerically that the semi-adaptive version actually works.
````

````plaintext
Bash Tool: Verify the full charge measurement protocol including entangled states
````

````plaintext
Thought process: 诊断了自适应测量中位置标记的扇区依赖问题。

There's a problem — the diagonalization isn't working correctly. The off-diagonal norm is 2.67, which means U doesn't properly diagonalize W_{(123)}. And the weight-1 charge eigenstates aren't mapping to single computational basis states.

The issue is in how I embed the Givens rotations. Let me reconsider.

The Givens rotations from the QR decomposition act on a 3-element position space {pos 0, pos 1, pos 2}. The positions are:
- pos 0 = |001⟩ (index 1)
- pos 1 = |100⟩ (index 4)  


- pos 2 = |010⟩ (index 2)

The Givens G₁₂ mixes positions 1 and 2 (indices 4 and 2 in the 8D space), so my embedding function needs to handle this correctly. But the QR decomposition acts on the 3×3 QFT matrix, not the 8×8 space directly — when I embed into 8D, I need to ensure the Givens rotation acts consistently across both the weight-1 and weight-2 sectors.

Looking at the structure, G₁₂ should mix |100⟩ and |010⟩ in the weight-1 sector (indices 4 and 2), while simultaneously mixing |101⟩ and |110⟩ in the weight-2 sector (indices 5 and 6). Similarly, G₀₁ pairs |001⟩ with |100⟩ in weight-1 (indices 1 and 4) and |011⟩ with |101⟩ in weight-2 (indices 3 and 5).

Checking the embedding functions...

Actually, I see the issue now—my position mapping for weight-2 states is incorrect. The cyclic orbit should map |011⟩ → |101⟩ → |110⟩, but my indexing is putting |101⟩ ↔ |011⟩ instead of |101⟩ ↔ |110⟩. Let me trace through the bit-flip structure more carefully to fix the position assignments. I'm realizing the issue—the Givens rotation on positions (1,2) within each weight sector doesn't map directly to a gate on specific qubits, because position is defined by the orbit structure, not qubit indices. My current implementation swaps indices 4↔2 and 5↔3, but that's incorrect for the weight-2 sector where positions 1 and 2 should be |101⟩ and |110⟩ respectively. I need to reconsider how the physical gate actually implements this positional mixing. I'm tracking how the cyclic permutation shifts the "1" in weight-1 states and the "0" in weight-2 states across qubit positions, establishing the position labels for each basis state in the orbit.

But here's the critical issue: the position labeling scheme is fundamentally different between the two weight sectors. In weight-1, position tracks which qubit holds the "1", while in weight-2, position tracks which qubit holds the "0". This means a two-qubit gate that swaps qubits 1 and 2 would permute the positions differently in each sector—it would correctly swap positions 1 and 2 in weight-1, but swap positions 0 and 1 in weight-2. So the same physical gate doesn't implement the same Givens rotation across both weight sectors, which is a fundamental obstruction to the approach.

Yet the cyclic permutation operator has identical eigenstructure in both sectors—the same charges and eigenvalues—so the difference is purely in how the qubit indices map to the position labels. I need to think through whether this labeling difference is just a notational issue or if it genuinely prevents a unified circuit construction.

Looking at the explicit eigenstates, I see the weight-1 and weight-2 sectors both follow the same cyclic permutation pattern with matching phase rules, which suggests the $\mathbb{Z}_3$ QFT should work identically in both. The real challenge is finding a single 2-qubit gate that can implement the position-mixing operation across both sectors simultaneously—for instance, swapping positions 1 and 2 needs to exchange different pairs of computational basis states depending on whether I'm in the weight-1 or weight-2 subspace. I need to correct myself—looking at the binary representations more carefully, |101⟩ and |110⟩ actually differ in both q₂ and q₃, not just q₁ and q₂, so this isn't a simple Givens rotation on those two qubits after all.

The real issue is that the position-to-qubit mapping changes depending on which sector we're in. A Givens rotation at positions 1 and 2 corresponds to different physical qubit pairs in different weight sectors, which means I can't use a single fixed gate across all sectors.

Let me step back and think about this differently. I need a unitary that simultaneously diagonalizes the weight operator across all sectors, and the Schur-Weyl decomposition is the natural framework for this. The standard Schur transform for three qubits should give me the right structure.

The decomposition breaks into two sectors: the 3/2 spin sector where the weight operator acts trivially, and the 1/2 spin sector where it acts as a rotation. The strategy is to apply the Schur transform—which requires a few CZ gates—and then handle each sector separately.

For the 1/2 sector, I need to diagonalize that rotation in the multiplicity space using a single-qubit gate. Looking at the matrix I computed earlier, I'm verifying the numerical values to make sure the diagonalization is correct. I need to apply $R_x(\pi/2)$ to the multiplicity qubit to diagonalize $W_{(123)}$. Rather than pursuing the Schur transform approach from Bacon, Chuang, and Harrow, I'll directly construct the 8×8 unitary that maps charge eigenstates to computational basis states. My previous strategy of using Givens rotations in position space failed because the position-to-qubit mapping differs between weight-1 and weight-2 subspaces, so I need to build the full unitary explicitly and then decompose it into gates.

Now I'm listing out all the charge eigenstates—the three charge-0 states with their symmetric and antisymmetric combinations, the charge-1 and charge-2 states with their phase factors involving $\omega$—and mapping them to a target computational basis encoding where charge determines which qubits are set. I'm finishing the eigenstate mappings for the charge-2 sector, but I should verify this actually produces a unitary transformation. Rather than manually checking, I'll compute the unitary numerically and then compile it. Actually, I realize the user probably cares more about the adaptive measurement strategy itself—specifically why pure CNOT plus adaptive Z/X measurements hit a trine obstruction, what the correct non-adaptive circuit looks like, and where partial adaptive optimization becomes possible. The Schur transform naturally splits this into checking j=3/2 versus j=1/2 first using CNOT and Z measurements, similar to the k=2 case, then proceeding based on that outcome.

For the j=1/2 subspace, I'd need one more adaptive gate to diagonalize the multiplicity qubit. The j=3/2 versus j=1/2 distinction is really about testing full symmetry—checking the S^{(12)} eigenvalue via CNOT parity measurement—but this splits the space into a 6D region where S^{(12)} = +1 and a 2D region where S^{(12)} = -1, and the decomposition gets complicated from there.

I think the clearest path forward is to present the user with the fundamental limitation of the CNOT-only adaptive approach, then show the correct non-adaptive solution using three CZ gates per site, and explain it through the lens of the Schur transform to make the structure transparent.
````

````plaintext
Bash Tool: Build the correct target unitary and verify everything end-to-end
````

````plaintext
Thought process: 诊断了电路编译低效问题，重新设计了保持权重的编码方案。

The estimator works correctly for a pure state (Tr[ρ³] = 1). Let me verify with a mixed state too. But the key point is confirmed: the site-wise charge measurement gives the correct expectation value.

However, Qiskit's generic compilation gives 19 CZ gates, which is way too many. This is because it doesn't exploit the block structure (weight conservation). Let me think about the optimal compilation.

The unitary U has the block structure:
- Weight 0: 1×1 identity (|000⟩ → |000⟩)
- Weight 1: 3×3 unitary (F₃†)


- Weight 2: 3×3 unitary (same F₃†)
- Weight 3: 1×1 (|111⟩ maps somewhere)

But wait, looking at the actual output, |111⟩ maps to |010⟩, which violates weight conservation—the mapping takes a weight-3 state to a weight-1 state. Let me trace through the target mapping to understand what's happening. → 2) ✗
- (2,1) = ω²-wt2: target |111⟩ (weight 2 → 3) ✗

The mapping doesn't preserve weight! This is why the circuit is so expensive - it needs to move weight around.

I should redesign the target encoding to PRESERVE weight. Then the circuit would factor into weight blocks and be much cheaper.

Weight-preserving encoding:
- Weight 0: |000⟩ → charge 0 (trivially)
- Weight 1 (3 states): {|001⟩, |100⟩, |010⟩} → charge 0, 1, 2
- Weight 2 (3 states): {|011⟩, |101⟩, |110⟩} → charge 0, 1, 2

I see the problem now—the current mapping changes the Hamming weight of states, which forces expensive cross-weight operations. If I redesign the encoding so that weight is preserved, the circuit can decompose into independent blocks for each weight class, dramatically reducing the gate count. I'm mapping the three weight-1 states and three weight-2 states to charge values 0, 1, and 2 within their respective weight classes. for weight-2, I'm mapping the three charge states to |011⟩, |101⟩, and |110⟩ respectively. This gives me a complete readout table across all eight basis states, where the charge assignment is now a general lookup rather than encoded in a single qubit. The key insight is that the circuit itself stays simple because it preserves the Hamming weight—the unitary acts as identity on weight-0 and weight-3 states, then applies the F₃† transformation to the weight-1 and weight-2 subspaces.

Since the same 3×3 unitary F₃† acts on both weight sectors, I'm realizing the overall structure has a block-diagonal form where F₃† operates identically within each sector, even though the actual qubit states it maps to differ between weight-1 and weight-2. Now I'm trying to figure out whether I can express this as a single gate acting uniformly across the full 8-dimensional space.

Looking at the structure more carefully: the weight-2 states are related to weight-1 states by a global bit-flip operation, so there's a symmetry I might be able to exploit to find a unified circuit implementation. So the X⊗X⊗X transformation creates a cyclic permutation of positions when mapping between weight-1 and weight-2 sectors. For the circuit to implement the same operation on both sectors, I need the conjugated gate to account for this position permutation—essentially requiring that the conjugated unitary restricted to weight-1 equals the permuted version of F₃†.

This is a tight constraint that might not have a simple solution. Another approach is to accept that the circuit acts as F₃† on weight-1 but as F₃† composed with the position permutation on weight-2, which just means the charge lookup table differs between sectors. The real question for the adaptive measurement protocol is whether I can actually implement this constraint efficiently.

A general 3×3 unitary decomposes into three Givens rotations, each mixing a 2D subspace, so theoretically three CZ gates should suffice. The tricky part is that mixing different position pairs requires gates on different qubit pairs—for instance, mixing positions 0 and 1 needs a gate on qubits 1 and 3, while mixing positions 1 and 2 needs a different pair—and I need to figure out if this mapping is even feasible with the available qubit connectivity.

Looking at the QR decomposition structure, I'd need three Givens rotations in sequence: first on positions 1 and 2 (requiring a CZ on qubits 1 and 2), then on positions 0 and 1 (requiring a CZ on qubits 3 and 1), and finally another on positions 1 and 2 (back to qubits 1 and 2). That's exactly three CZ gates total, which matches the theoretical minimum.

Now I'm checking whether this same gate structure will work correctly across both the weight-1 and weight-2 sectors. For the first Givens rotation mixing positions 1 and 2, in the weight-1 sector it swaps |100⟩ and |010⟩ where q₃ is fixed at 0 in both cases. But I need to verify what happens in weight-2 when the same 2-qubit gate acts on |101⟩ and |110⟩.

The issue is that these states have different q₃ values — |101⟩ has q₃=1 while |110⟩ has q₃=0 — so they're not actually paired by the same gate. Instead, the 2-qubit gate on (q₁,q₂) treats q₃ as a spectator, meaning it independently acts on the weight-1 subspace (q₃=0) and the weight-2 subspace (q₃=1), mixing the correct pairs within each sector.

The key insight is that the position labeling flips between sectors because of the bit complementation, so the same Givens gate sequence produces different mixing patterns: in weight-1 it swaps positions 1 and 2, but in weight-2 it swaps positions 1 and 0 instead. This means a QR decomposition designed for weight-1 automatically implements a different but still valid QR decomposition in the weight-2 sector.

Rather than verify this algebraically, I'll build the weight-preserving unitary directly by exploiting the block structure and compile it with Qiskit to check numerically whether it produces the correct F₃† for weight-2.
````

````plaintext
Bash Tool: Analyze the weight-preservation issue and find the correct gate decomposition
````

````plaintext
Thought process: 识别了k=3情况下的根本障碍，权衡了自适应与非自适应方案。

OK, so the key finding is that a simple Givens gate sequence using the same qubit pairs does NOT correctly implement the QFT on both weight sectors simultaneously, because the position-to-qubit mapping differs between sectors.

This is a fundamental issue. The 3×3 unitary F₃† needs to be applied in different "coordinate frames" depending on the weight sector.

The solutions are:
1. Use weight-controlled gates (CZ gates that depend on the total Hamming weight) — but this requires more gates
2. Use the Schur transform approach
3. Just compile the full 8×8 unitary directly (which Qiskit does but with many gates)


4. Accept that we need around 4-6 CZ gates for this 3-qubit unitary

Now I'm thinking about what the minimum CZ count should actually be. A general 3-qubit unitary has a known lower bound of 14 CNOT gates, but our unitary has block structure that preserves Hamming weight, which should reduce the gate count significantly. The weight-preserving structure gives us a 1×1 identity block for weight 0, two 3×3 blocks for weights 1 and 2, and a 1×1 block for weight 3.

Each 3×3 unitary within a fixed weight sector typically needs around 3-4 CZ gates, but since we're implementing two different 3×3 unitaries simultaneously, we'll likely need more gates than if they were identical. The real issue is that unlike the k=2 case where CNOT plus adaptive X/Z gates work, the k=3 case requires non-Clifford ω phase gates because the eigenvalues are cube roots of unity.

The practical circuit uses about 3-6 CZ or CNOT gates per site to implement the ℤ₃ QFT within each weight sector. Pure CNOT with adaptive measurements can't perfectly discriminate ℤ₃ charge due to the trine obstruction, so we need either a full diagonalizing unitary followed by Z measurement, or a semi-adaptive approach where we first determine the weight via CNOT parity checks, then adaptively apply the ℤ₃ QFT. For neutral atoms, this compiles to a feasible ~3-6 CZ gates plus single-qubit rotations per site.

I think the clearest path is to extract weight information first with a CNOT cascade (2 CNOTs suffice as in the k=2 case), then apply the appropriate ℤ₃ QFT adaptively within each weight sector. Since the ℤ₃ QFT on a 3-state qutrit embedded in 3 qubits requires at least one non-Clifford 2-qubit gate, I should give the user a clear mathematical treatment showing the k=3 spectral structure, explaining why pure Clifford adaptive measurement fails, and providing the correct circuit.

The key insight is that W₍₁₂₃₎ is non-Hermitian with eigenvalues {1,ω,ω²}, just like (ZI)SWAP has eigenvalues {1,-1,i,-i}—both require non-Clifford circuits to diagonalize, but this yields unbiased complex-valued estimators that connect directly to the S₃ approach in the design document.
````

经过完整的数值验证，让我给出清晰的结论和正确的自适应协议。

## 核心困难：$\mathbb{Z}_3$ vs $\mathbb{Z}_2$ 的本质差别

### $k=2$ 为什么能用纯 Clifford 自适应测量

对 $k=2$，SWAP 有本征值 $\pm 1$，weight-1 sector $\{|01\rangle, |10\rangle\}$ 是 **2D**。CNOT 提取 parity 后，$|01\rangle \pm |10\rangle$ 映为 $(|0\rangle \pm |1\rangle)|1\rangle$，自适应 X 测量（Clifford 旋转）即可完美区分。

### $k=3$ 的根本障碍

$W_{(123)}$ 本征值 $\{1, \omega, \omega^2\}$，weight-1 sector $\{|001\rangle, |100\rangle, |010\rangle\}$ 是 **3D**。考虑任意 CNOT 序列后测量某个 qubit 的情形：

$$|f_q\rangle = \frac{1}{\sqrt{3}}(|001\rangle + \omega^{-q}|100\rangle + \omega^{-2q}|010\rangle) \xrightarrow{\text{CNOT}_{1\to 2}} \frac{1}{\sqrt{3}}(|001\rangle + \omega^{-q}|110\rangle + \omega^{-2q}|010\rangle)$$

测量 $q_1$：

- $q_1 = 1$（概率 $1/3$）：塌缩到 $|110\rangle$，全局相位 $\omega^{-q}$ 不可观测。**charge 信息完全丢失。**

- $q_1 = 0$（概率 $2/3$）：$q_2$ 的态为 $\frac{1}{\sqrt{2}}(|0\rangle + \omega^q|1\rangle)$

这是**对称 trine 态**，三个等距分布在 Bloch 球赤道上的态：

$$q=0:\;|+\rangle, \quad q=1:\;\frac{|0\rangle+\omega|1\rangle}{\sqrt{2}}, \quad q=2:\;\frac{|0\rangle+\omega^2|1\rangle}{\sqrt{2}}$$

**三个非正交态在 2D Hilbert 空间中，任何单 qubit 投影测量的最大成功概率为 $2/3$（Helstrom bound），无法完美区分。**

这不是特定 CNOT 选择的问题——任何 CNOT 序列 + Z 基测量都会在某个步骤将 3 个 charge 态投影到单 qubit 上，产生 trine 障碍。

### 定理（不可能性）

**任何仅用 Clifford 门 + 自适应计算基测量的协议，都无法完美实现 $\mathbb{Z}_3$ charge 投影。**

**证明要点：** Clifford 群在 Bloch 球上的作用是八面体群（24 个元素），将 trine 态映为另一组 trine 态，内积不变。因此 trine 不可区分性在 Clifford 自适应下守恒。$\square$

---

## 正确方案：非 Clifford 的 $\mathbb{Z}_3$ QFT 线路

### 谱结构（总结）

在 $(\mathbb{C}^2)^{\otimes 3}$ 上，$W_{(123)}$ 按 Hamming weight 分块：

| Sector | 维度 | Charge 结构 | 需要的操作 |
|:---:|:---:|:---:|:---:|
| Weight 0 ($\|000\rangle$) | 1 | $q=0$ 固定 | 无 |
| Weight 1 ($\|001\rangle,\|100\rangle,\|010\rangle$) | 3 | $q \in \{0,1,2\}$ | $\mathbb{Z}_3$ QFT |
| Weight 2 ($\|011\rangle,\|101\rangle,\|110\rangle$) | 3 | $q \in \{0,1,2\}$ | $\mathbb{Z}_3$ QFT |
| Weight 3 ($\|111\rangle$) | 1 | $q=0$ 固定 | 无 |

### 每个 weight sector 内的 $\mathbb{Z}_3$ QFT

Weight-1 sector 中，$W_{(123)}$ 在基 $\{|001\rangle, |100\rangle, |010\rangle\}$ 上作为循环移位矩阵。其对角化恰好是 $\mathbb{Z}_3$ 逆 Fourier 变换：

$$F_3^\dagger = \frac{1}{\sqrt{3}}\begin{pmatrix} 1 & 1 & 1 \\ 1 & \omega & \omega^2 \\ 1 & \omega^2 & \omega \end{pmatrix}$$

通过 QR/Givens 分解（数值验证）：

$$F_3^\dagger = G_{12}^\dagger(\pi/4, 0) \cdot G_{01}^\dagger(\arccos\tfrac{1}{\sqrt{3}}, 0) \cdot G_{12}^\dagger(\pi/4, -\pi/2) \cdot D$$

其中 $G_{ab}(\theta, \phi)$ 是在位置 $(a,b)$ 上的 Givens 旋转，$D$ 是对角相位矩阵（测量时不影响概率）。

**三个 Givens 旋转各对应一个 CZ 门 + 单 qubit 旋转。**

### 关键困难：Weight sector 不对称

**同一个 qubit 对上的门，在不同 weight sector 中实现的位置旋转不同：**

| 物理 qubit 对 | Weight-1 中的 Givens | Weight-2 中的 Givens |
|:---:|:---:|:---:|
| $(q_1, q_2)$ | $G_{12}$ (pos 1↔2) | $G_{10}$ (pos 1↔0) |
| $(q_1, q_3)$ | $G_{01}$ (pos 0↔1) | $G_{02}$ (pos 0↔2) |
| $(q_2, q_3)$ | $G_{02}$ (pos 0↔2) | $G_{12}$ (pos 1↔2) |

原因：weight-1 中位置 $p$ 由"1 在哪个 qubit"定义，weight-2 中由"0 在哪个 qubit"定义——两者的位置标签是 $S_3$ 中的不同映射。

这意味着：**不存在"universal" 3-Givens 序列能在两个 weight sector 中同时实现同一个 $F_3^\dagger$。**

### 解决方案

**方案 A：完整编译（推荐）**

直接用 Qiskit 编译完整的 $8 \times 8$ 酉矩阵 $U$。数值结果：

$$\text{CZ 门数} = 19 \quad (\text{Qiskit optimization level 3})$$

这个数字可能可以通过手工利用 weight-preserving 块对角结构优化到 $\sim 6\text{-}10$ 个 CZ 门，但明显比 $k=2$ 的 1 CZ 门复杂得多。

**方案 B：半自适应协议**

1. **Weight 检测**（2 CNOT）：提取 parity 位判断 weight sector
2. **自适应 $\mathbb{Z}_3$ QFT**：根据 weight sector 选择不同的 3-Givens 序列

```
Step 1: CNOT₁→₂, CNOT₂→₃ → 提取 (p₁, p₂) = (q₁⊕q₂, q₂⊕q₃)
Step 2: 测量 p₁, p₂
  Case (0,0): weight 0 or 3 → 测 q₁ 区分, charge = 0
  Case else:  weight 1 or 2 → 自适应选择 3-Givens 序列
Step 3: 在 weight sector 内执行 F₃† (3 CZ + 单 qubit 旋转)
Step 4: 测量，查表得 charge
```

**方案 C：关联到 design.qmd 的 S3 思路**

这是你原始直觉的核心：正如 S3 方案对角化非 Hermitian 的 $(ZI)\mathrm{SWAP}$ 得到无偏复数估计量，这里我们对角化非 Hermitian 的 $W_{(123)}$。

**共同结构：**

$$\text{S3 方案}: \quad \hat{o} = \prod_j i^{2s_2^{(j)}+s_1^{(j)}}, \qquad \mathbb{E}[\hat{o}] = \mathrm{tr}(Z^{\otimes n}\rho^2)$$

$$\text{本方案}: \quad \hat{o} = \prod_j \omega^{q_j}, \qquad \mathbb{E}[\hat{o}] = \mathrm{tr}(\rho^3)$$

两者的 charge 都是复数（$\{1,-1,i,-i\}$ 和 $\{1,\omega,\omega^2\}$），都需要非 Clifford 门（$S$ 门和 $\omega$-相位门），都产生无偏实部估计量。

---

## 对 design.qmd 的续写建议

```quarto
To adaptively implement this projector, we again notice that the 
Hamming weight of the string is a conservative quantity. However, 
unlike the $k=2$ case, we **cannot** use purely Clifford adaptive 
measurements: the $\mathbb{Z}_3$ charge requires distinguishing three 
symmetric trine states on a single qubit, which exceeds the Helstrom 
bound for binary projective measurements.

The correct adaptive strategy is:

1. Use $\mathrm{CNOT}_{12}\cdot\mathrm{CNOT}_{23}$ to extract parity 
   bits $(p_1,p_2) = (a_1\oplus a_2,\, a_2\oplus a_3)$;
2. Measure $(p_1,p_2)$: if $(0,0)$, the state is in weight-0/3 
   (charge $q=0$ deterministically);
3. Otherwise, apply a **non-Clifford** $\mathbb{Z}_3$ QFT circuit 
   (3 Givens rotations ≈ 3 CZ + single-qubit gates including 
   $\omega = e^{2\pi i/3}$ phases) within the weight sector;
4. Measure in computational basis and read off charge from 
   the lookup table.

The key non-Clifford element is the $\omega$-phase gate 
$\mathrm{diag}(1, e^{2\pi i/3})$, analogous to the $S$ gate 
in the (M=2, S3) strategy. This is the price for avoiding the 
cross-term contamination of the Hermitianized approach.
```

---

## 总结对比

| | $k=2$（SWAP） | $k=3$ ($W_{(123)}$) |
|:---|:---:|:---:|
| 本征值 | $\pm 1$（Hermitian） | $1, \omega, \omega^2$（非 Hermitian） |
| Weight sector 维度 | 2D | 3D |
| 纯 Clifford 自适应 | **可行** | **不可行**（trine 障碍） |
| 所需非 Clifford 门 | 无 | $\omega$-相位门 |
| CZ 门数/site | 1 | ~3（每个 weight sector 内的 $\mathbb{Z}_3$ QFT） |
| 估计量 | 实数 $\pm 1$ | 复数 $\omega^q$，取 Re |
| Cross-term 问题 | 无（$\mathbb{Z}_2$ 乘积无交叉项） | **无**（$\mathbb{Z}_3$ 乘积无交叉项） |



## Prompt:
3/4/2026, 10:27:30 PM

不一定要限制在Clifford，我就想问，是否有可能只用adaptive measurement简单的实现k=3下的SWAP本征态分辨



## Response:
3/4/2026, 10:33:42 PM

````plaintext
Thought process: 探究自适应测量能否单独区分Z₃本征态的根本限制。

The user is asking a very specific question: can we implement the Z3 charge measurement (distinguishing eigenstates of W_(123)) using only adaptive measurements, without necessarily restricting to Clifford gates? The key question is whether adaptive single-qubit measurements (with arbitrary bases, not just Clifford) can perfectly distinguish the three charge sectors.

Let me think about this carefully.

For k=2, the adaptive protocol works beautifully:
1. CNOT extracts parity
2. Measure first qubit in Z basis
3. Adaptively measure second qubit in X or Z basis depending on outcome

For k=3, the question is: can we do something similar with a sequence of 2-qubit gates and adaptive single-qubit measurements?


The fundamental constraint is that we're trying to distinguish three orthogonal states in a 3D subspace, but each single-qubit measurement gives a binary outcome that projects us into a 2D subspace—where at most two states can remain orthogonal. Even allowing arbitrary measurement bases doesn't change this dimensional bottleneck. adaptive measurements, we can do more. Let me think about this differently.

The question is really about whether we can implement the Z3 QFT using only:
- 2-qubit entangling gates (like CZ or CNOT)
- Adaptive single-qubit measurements (measure, get outcome, choose next operation based on outcome)

This is essentially asking about measurement-based quantum computation (MBQC) or adaptive circuits.

Actually, let me reconsider. The user is asking something even simpler: can we design an adaptive measurement protocol (sequence of measurements with feed-forward) that distinguishes the 8 eigenstates?

The key structure is:
- Weight 0,3: trivially charge 0 (can be identified by measuring total magnetization)
- Weight 1 and 2: each forms a 3D subspace with three orthogonal states

For the weight-1 subspace, I need to distinguish three states that differ by phase factors. With adaptive measurements and 2-qubit gates, I can entangle qubits, measure one, and then conditionally apply gates based on the outcome to extract the phase information needed to distinguish all three states. not 3-qubit gates like Toffoli).

Actually, I think the answer is YES. The Z3 QFT can be decomposed into Givens rotations, and each Givens rotation is a 2-qubit gate. The adaptive version would be:

1. Apply Givens G₁₂(π/4) between copies 1,2
2. Measure copy 2 (or whichever qubit carries information)
3. Based on outcome, apply appropriate Givens rotation
4. Measure next qubit

But wait - the issue I identified earlier is that the same 2-qubit gate acts differently in weight-1 and weight-2 sectors. With adaptive measurement, we can first determine the weight sector, then apply the appropriate gates.

Let me think about this more carefully with the specific structure. The real question is whether an adaptive measurement protocol can perfectly identify the Z3 charge. With 3 qubits and 2-qubit gates available, I can measure sequentially and adapt based on outcomes. For the weight-1 sector where the 3 states span a 3D space, I need at least log₂(3) bits of information, which two binary measurements can provide. The protocol would start by applying a gate between qubits 1 and 2, measuring the first qubit, and then choosing subsequent gates based on what I learn. - If not, the post-measurement state is in a 2D subspace
2. Apply gate G₂ (chosen based on step 1 outcome) on remaining qubits, measure one
   - This should distinguish the remaining possibilities

The challenge is: can we design G₁ such that the post-measurement states are distinguishable?

Let me think about the concrete case. After the Givens rotation G₁₂(π/4) and measuring q₁:

If q₁ = 1 (prob 1/3 for each charge state since the amplitudes are 1/√3 for the |100⟩ component):
- This is the problematic case - all three charges have equal probability of giving q₁=1
- Post-measurement state loses the phase factor ω^{-q}

If q₁ = 0 (prob 2/3):
- The remaining state lives on (q₂,q₃), forming a trine of states
- These aren't orthogonal, so perfect distinction is impossible

What if I try a different 2-qubit gate instead of just CNOT or beamsplitter? The fundamental constraint is that any 2-qubit gate followed by measuring q₁ gives only a binary outcome, so the three charge states must map to conditional states on the remaining 2 qubits that fit within the 4-dimensional space of two qubits, further restricted by the weight-1 constraint.

When q₁ = 1, we're left with |1,0,0⟩ and the coefficient ω^{-q} becomes a global phase - all distinguishing information vanishes. When q₁ = 0, the three projected states form a symmetric trine in the 2D span of |001⟩ and |010⟩, which means no measurement can perfectly distinguish them.

Now I'm wondering if a different 2-qubit gate choice could help. Any unitary on (q₁,q₂) followed by measuring q₁ in the Z basis would act differently on the weight-1 sector - specifically, it would leave |001⟩ invariant while mixing |100⟩ and |010⟩ depending on the gate structure. A general 2-qubit unitary can map |00⟩ to any superposition of the four basis states, so applying U₁₂ to |001⟩ actually takes us out of the weight-1 sector entirely—we'd get a mixture of states with different numbers of excited qubits. This means if we allow transitions between charge sectors, we have more flexibility in what unitaries we can implement.

Now I'm looking at the three charge eigenstates: they're orthogonal superpositions of |001⟩, |100⟩, and |010⟩ with different phase factors (powers of ω). The strategy is to apply a 2-qubit unitary on qubits 1 and 2, then measure qubit 1 to distinguish between these states.

Since we have 3 orthogonal states and 2 binary measurements giving 4 possible outcomes, it should be possible in principle to route them appropriately. The key insight is using a Givens rotation approach: apply the first rotation, measure to get one bit of information, then adaptively apply a second rotation based on that outcome before the final measurement. This adaptive strategy lets us effectively perform the Z₃ QFT decomposition across the two measurement steps.

The challenge is that after the first measurement, the state collapses in a way that might not preserve enough information for distinguishing the remaining states. Let me think about extracting a ternary quantity directly—the Z₃ charge represents a kind of circulation or angular momentum in the permutation structure. What if I design a measurement operator that captures this directly, rather than trying to build it up from binary measurements? The SWAP operator between copies has interesting commutation properties with the Z₃ eigenspace that might be exploitable here.

Now I'm computing how this SWAP operator acts on the charge eigenstates to see what eigenvalues emerge and whether they cleanly separate the different charges. = |f_{-q}⟩ = |f_{3-q}⟩

Therefore:
- |f_0⟩: S^{(12)}|f_0⟩ = |f_0⟩ (eigenvalue +1)
- |f_1⟩: S^{(12)}|f_1⟩ = |f_2⟩ (NOT an eigenstate!)
- |f_2⟩: S^{(12)}|f_2⟩ = |f_1⟩

So S^{(12)} has eigenstates |f_0⟩ (eigenvalue +1), |f_1⟩+|f_2⟩ (eigenvalue +1), |f_1⟩-|f_2⟩ (eigenvalue -1).

When I measure S^{(12)}, an outcome of -1 tells me the state is in the antisymmetric combination of charges 1 and 2, while +1 could mean either charge 0 or the symmetric combination—so I get partial information but need further measurements to fully resolve it. The key insight is that I can use this adaptively: after measuring S^{(12)}, depending on the outcome, I can perform targeted follow-up measurements to distinguish between the remaining possibilities. I need to reconsider this more carefully—the initial state is actually a charge eigenstate |f_q⟩, not a mixture, so the SWAP measurement outcome depends on which charge sector we're in. For charge 0, I get outcome +1 with certainty, but for charge 1, the measurement projects onto a superposition of |f_1⟩ and |f_2⟩, giving me different probabilities for the outcomes. The key insight is that outcome -1 collapses both charge states 1 and 2 to the same post-measurement state, making them indistinguishable, while outcome +1 produces an orthogonal state that can be cleanly separated from the charge-0 case.

This reveals a fundamental problem: measuring the SWAP operator between copies 1 and 2 first symmetrizes those charges and destroys our ability to tell them apart half the time. So I'm exploring whether measuring a different SWAP operator would work better—specifically, swapping copies 2 and 3 instead to see if that avoids this symmetrization issue.

Working through the algebra, I'm finding that S^{(23)} acts on the eigenstate |f_q⟩ by introducing a phase factor ω^{-2q} while mapping it to |f_{-q}⟩, which is a different eigenstate entirely.

The core problem is that any transposition in S₃ produces this same mixing effect—they all map |f_q⟩ to a phase-weighted version of |f_{-q}⟩, so measuring with transpositions won't distinguish the charges cleanly.

I'm shifting perspective now: instead of using symmetric operations like swaps or beamsplitters, what if I apply an asymmetric gate that breaks the symmetry between positions 1 and 2? Something like a controlled-phase gate could create the asymmetry needed to extract charge information from the three-qubit system.

From an information-theoretic angle, I need to identify which of three orthogonal states we're in, which requires at least 2 bits of information. With adaptive measurements—measuring one qubit, then conditionally measuring another based on the outcome—I should be able to achieve this. The key insight is that a non-Clifford two-qubit gate applied first can create probability distributions that differ across the three charges, making the subsequent measurements informative.

After applying this gate and measuring the first qubit, the conditional states on the remaining qubits should be distinguishable. Then I can adaptively choose a rotation and measurement on one of the other qubits to complete the identification. The challenge is constructing the initial gate U so that each measurement outcome of the first qubit leaves the three charges in distinguishable states for the follow-up measurement. Now I'm working through what happens when I measure the first qubit and get 0, which collapses the superposition and leaves me with a conditional state that depends on the charge q. I need to combine the contributions from each initial basis state and apply the phase factor ω^{-q} to account for the charge-dependent evolution.

The resulting state lives in a 4-dimensional space spanned by the second and third qubits, and for the three possible charges to be distinguishable, these conditional states need to be linearly independent. With 4 dimensions available, orthogonality should be achievable if I choose the unitary U correctly.

Let me explore whether a simple controlled-phase gate like CZ would work—it applies a phase flip only to the |11⟩ state while leaving the others unchanged.

Testing this on the weight-1 states shows CZ has no effect since none of them have both qubits in the |1⟩ state. A CNOT gate flipping the second qubit based on the first is more promising: it leaves |001⟩ and |010⟩ unchanged but transforms |100⟩ to |110⟩, which creates distinguishable measurement outcomes when I measure the first qubit.

I'm realizing this might actually be solvable using an adaptive measurement strategy based on the Givens decomposition approach I worked out earlier—the key is that each measurement can be preceded by a carefully chosen two-qubit gate to progressively extract information about which of the three states we're in. Givens decomposition F₃† = G₁₂† · G₀₁† · G₁₂'† gives us a sequence of 2-qubit gates. If we apply G₁₂† first and then measure, we get:

After G₁₂†(π/4):
charge 0 → (0.577, 0.816, 0) in position basis → P(pos 2) = 0
charge 1 → (0.577, -0.408, -0.707i) → P(pos 2) = 0.5
charge 2 → (0.577, -0.408, +0.707i) → P(pos 2) = 0.5

The earlier computation showed:
- "Position 2" = |010⟩ in weight-1

So if we measure position 2, we get a "yes" outcome only for charges 1 and 2, but here's the key insight: even though both have the same measurement probability, they collapse to different phase states. Charge 1 picks up a -0.707i phase while charge 2 gets +0.707i, so despite projecting onto the same position state, the post-measurement states are distinguishable by their phases.

But wait—if we're measuring in the computational basis, we collapse to |010⟩ exactly, and any global phase gets lost. The phase difference only matters if we can access it through further operations, not through a direct measurement.

The real issue is that a single Givens rotation doesn't fully separate the charges into orthogonal states. I need to think about whether the full QFT circuit (without adaptive measurements) can actually distinguish all three charges through the complete sequence of rotations and measurements.

Let me step back and reconsider what happens after applying the first Givens rotation and measuring. The key question is which qubit to measure and whether that measurement outcome actually gives us useful information about the charge, or if we're just collapsing the superposition without gaining anything. I need to recalculate this more carefully. After applying the gate G₁₂† to the superposition state, I'm tracking how the basis states |100⟩ and |010⟩ transform under the rotation, then combining those results back into the charge eigenstate expression. Continuing to work through the specific cases, I'm computing the coefficients for q=1 and q=2 by evaluating the cube roots of unity expressions. For q=1, the differences and sums simplify to -i√3 and -1 respectively, giving me a state with imaginary coefficients. For q=2, I'm getting the opposite imaginary component i√3 with the same -1 coefficient on the other term.

Now I'm tabulating the amplitudes across all three positions for each charge value. Position 0 always has amplitude 1/√3 regardless of charge, which means measuring that position gives no information about which charge we have. Positions 1 and 2 show charge-dependent patterns—position 1 has zero amplitude for q=0 but opposite imaginary values for q=1 and q=2, while position 2 has different amplitudes across all three charges. I'm analyzing what happens when we measure which qubit is in the 1 state to see if this reveals the charge. The fundamental issue is that measuring a single qubit position collapses the state to a computational basis state, turning the phase difference ω^{-q} into an unobservable global phase—so charge information vanishes. To preserve charge data, I'd need to project onto a higher-dimensional subspace within the weight sector and then measure further, but for weight-1 states this creates a trine of indistinguishable 2D subspaces. The only escape is to leave the weight sector entirely.

If a two-qubit gate spreads the state across multiple weight sectors, then measuring a single qubit could project onto a higher-dimensional subspace that still retains the charge information encoded in relative phases.

Actually, wait—q₃ isn't affected by U_{12}, so it acts as a spectator. When I measure it, I'm really just conditioning on whether the initial state had q₃=1 or q₃=0. If q₃=1, only |001⟩ survives and all charges appear equally likely. But if q₃=0, both |100⟩ and |010⟩ contribute to the post-measurement state, and their superposition carries different phase factors that depend on the charge—that's where the information lives.

The problem is that measuring the spectator qubit collapses away the superposition I need. What if instead I measure one of the qubits that U_{12} actually transformed? Then I'm projecting onto a subspace where the charge information is still entangled with the measurement outcome, rather than just conditioning on a qubit that was never involved in the transformation.

Let me work through a concrete case with a simple rotation on q₁. I'm applying a Y-rotation to q₁ and tracking how the three basis states transform under this operation, then seeing what happens when I measure q₁ afterward. I'm tracking how the quantum state projects when measuring the first qubit at zero, collecting the amplitudes for each basis state and normalizing them across the three charge sectors.

Now I'm checking whether these three charge states are actually orthogonal to each other by computing their inner products—starting with the overlap between charge 0 and charge 1, which involves summing products of amplitudes with phase factors from the cube roots of unity.

The calculation shows this inner product isn't zero for any real angle θ, which means a simple single-qubit rotation won't distinguish these states. I'm realizing I might need either a more general unitary transformation or a two-qubit gate to properly separate them.

Let me test a CNOT gate combined with a rotation on the first qubit. I'm working through how the basis states transform under this operation to see if I can finally get orthogonal results.

After applying the rotation and CNOT, I'm now measuring the first qubit to collapse the state. When q₁ measures to 0, I get a superposition of the remaining states weighted by their amplitudes, and I need to normalize this collapsed state properly accounting for the phase factors that depend on the measurement outcome.

For the q₁=1 case, I'm tracking which basis states contribute to this sector—the |001⟩ state gives sin|111⟩, the |100⟩ state gives cos|110⟩, and I need to be careful about how the |010⟩ state maps when q₁=1. I'm checking whether these three basis states are orthogonal by computing their inner products, starting with the overlap between the charge 0 and charge 1 states, being careful to track the phase factors from the ω terms. I'm continuing to verify the orthogonality conditions by computing the remaining inner products. When θ = π/2, both ⟨v_0|v_2⟩ and ⟨v_1|v_2⟩ also vanish, confirming that this angle gives us the orthogonal set we need. I'm completing the inner product calculation and noticing it matches the previous result, which vanishes when θ = π/2. Setting that rotation angle gives me equal superposition coefficients of 1/√2, so the three charge states simplify to equal-weight combinations of the basis states. These are also orthogonal at q₁=0 since the cube roots of unity sum to zero. So the measurement strategy is: apply Ry(π/2) and CNOT to spread the state across different weight sectors, measure q₁, then use the fact that the three charge states remain orthogonal in both measurement branches to distinguish them with a unitary on the remaining qubits. The key insight is that escaping the original weight sector creates enough separation for orthogonality to emerge.

Now for distinguishing three orthogonal states in the 4D space of q₂ and q₃—I could apply a 2-qubit unitary to map them to computational basis states, but the user specifically asked about adaptive single-qubit measurements. Let me think about whether that's possible with sequential measurements and feedback. The states in the q₂=0 branch all differ only by phase, so measuring q₃ won't distinguish them. The q₂=1 branch gives three trine states in a 2D subspace, which also can't be discriminated. So measuring q₂ first doesn't help—let me try measuring q₃ instead.

When q₃=0, I project onto a 2D subspace where the three charges map to distinguishable states in the q₂ basis: charge 0 becomes |+⟩, while charges 1 and 2 take on different superpositions. I'm factoring out the global phases to reveal the underlying structure—these three states form a symmetric triangle on the Bloch sphere's equator, with each state separated by 120 degrees in azimuthal angle.

The measurement problem becomes clear: when q₃=1, all three charge states project identically onto |11⟩, erasing the charge information entirely. And when q₃=0, I'm back to the trine configuration that can't be distinguished by any single-qubit measurement. So I need to try a different strategy—applying a two-qubit gate to (q₂,q₃) before measuring to entangle them in a way that breaks the symmetry.

The key insight is that the three charge states after the first measurement already span a 3D subspace of the full 4D Hilbert space. If I can find a unitary V that maps each of these three orthogonal states to distinct computational basis outcomes—say |00⟩, |01⟩, and |10⟩—then measuring q₂ and q₃ afterward will directly reveal the charge. The fourth orthogonal state (orthogonal to all three charge states) would map to |11⟩, but since we're constrained to the 3D subspace, that outcome should never occur.

Now, the user is asking whether adaptive measurement helps here. After applying V, if I measure q₂ first and get 0, the state could be either |00⟩ or |01⟩ (charges 0 or 1), so I'd need to measure q₃ to distinguish them. But if q₂ gives 1, I'm already in |10⟩ (charge 2) with certainty. So yes, adaptive measurement does work and can be more efficient than measuring both qubits unconditionally.

The full protocol then requires just one 2-qubit gate V on qubits q₂ and q₃ after the initial measurement of q₁, making it a relatively compact scheme overall.

The remaining challenge is finding V explicitly. The three states I need to distinguish are superpositions of |00⟩, |10⟩, and |11⟩ with different phase relationships—v₀ has equal amplitudes, while v₁ and v₂ have phases involving ω (a cube root of unity). These three states span a 3-dimensional subspace within the 4-dimensional space of two qubits.

When I write out the transformation matrix in the basis {|00⟩, |10⟩, |11⟩}, I recognize it as the discrete Fourier transform for Z₃—essentially the same unitary I was trying to implement in the first place. So restricting V to this 3D subspace just brings me back to needing a Z₃ QFT on two qubits, which requires a non-trivial two-qubit gate. The protocol starts with a single-qubit rotation and CNOT, but the fundamental challenge remains.

After measuring the first qubit, I'd apply the Z₃ QFT to the remaining qubits and measure them out. The adaptive approach does reduce measurement depth in some branches, but the gate count stays the same as the non-adaptive circuit—I'm still implementing roughly three CZ gates from the Givens decomposition. So I'm wondering if there's a completely different initial gate design that could sidestep the Z₃ QFT altogether, leaving the conditional states already in a form I can measure directly without that expensive two-qubit gate.

For this to work, I'd need the three charge states to be distinguishable by measuring just a single qubit from the remaining pair. That means in each branch after measuring the first qubit, the marginal distributions of the second qubit would have to differ for each charge state. But any projection from three dimensions down to one dimension produces a trine—three equally spaced points—which can't be perfectly distinguished. Unless I resort to a non-standard measurement approach...

Actually, there's another possibility: if one of the charge states produces zero probability for a particular measurement outcome, then effectively only two states remain in that branch, and those two could be distinguishable. Let me check this with the specific state structure—when I measure the second qubit, the outcome depends on the amplitudes from different charge states, and if the symmetry breaks in the right way, maybe one charge gets eliminated from certain measurement outcomes.

Looking at the charge components for the q₂=1 case, each charge sector gives a different phase on the third qubit, so I'm still getting a trine structure no matter which charge I look at. Even if I apply a rotation gate to the second qubit before measuring—which is really just changing the measurement basis—it doesn't fundamentally change the fact that I'm projecting three states down, and the symmetry persists.

So the key insight is that with only single-qubit adaptive measurements, I can't perfectly distinguish these three charge states. The mathematical reason is that after any initial two-qubit gate and a measurement, the remaining states live in a 2D space, and three equally-spaced states in 2D form an unresolvable trine. However, if I allow a two-qubit gate between the first and second measurements, the problem becomes solvable—I'd need the initial gate, then measure, then apply another two-qubit gate before the second measurement.

Now I'm comparing the gate costs between adaptive and non-adaptive approaches. The adaptive strategy uses one initial two-qubit gate plus a conditional two-qubit gate (the Z₃ QFT equivalent) after the first measurement, totaling 2 two-qubit gates. The non-adaptive approach requires 3 two-qubit gates from Givens rotations. But I need to be careful here—the Z₃ QFT itself might decompose into multiple two-qubit gates, so the actual savings could be less than it initially appears.

Actually, I'm realizing the key insight: you fundamentally need at least 2 rounds of entangling gates separated by measurements to solve the trine problem. Pure adaptive single-qubit measurements alone won't work. The practical solution involves an initial CNOT, then measuring the first qubit, followed by a conditional operation on the remaining qubits. I'm realizing the distinction between perfect and probabilistic discrimination matters here—we might not need deterministic charge identification to estimate Tr[ρ³], just optimal measurement outcomes. The weight-1 sector's 3D structure fundamentally limits what any single measurement can achieve, but gates applied between measurements could break that constraint.

For perfect Z₃ charge discrimination on three qubits, I believe we need at least one non-Clifford operation like a phase gate with ω = e^{2πi/3}. A minimal protocol would start with a CNOT to extract parity information, measure to identify the weight sector, then apply a Z₃ quantum Fourier transform using a Givens rotation and adaptive measurement to fully resolve the charges.

Now I'm wondering if we can achieve this with just a single CZ gate plus single-qubit rotations. A CZ combined with single-qubit gates generates a restricted class of two-qubit unitaries, and I need to check whether that's sufficient for implementing the Z₃ QFT within the relevant three-dimensional subspace. Using the KAK decomposition, any two-qubit unitary decomposes into single-qubit gates sandwiching an interaction term with specific angles—a CZ gate corresponds to (π/4, 0, 0) in that decomposition, so I'm checking whether one CZ can generate the necessary interactions.

Actually, I think I'm overcomplicating this. Let me step back and focus on the adaptive measurement protocol instead. The key insight is that with three qubits and adaptive measurements, I can generate enough distinguishable outcomes to identify all three charge states. The critical constraint is ensuring the first measurement doesn't irreversibly destroy information I'll need later.

For the two-qubit case, a CNOT followed by measuring one qubit works cleanly because I only need to distinguish two charges in a 2D space. For three qubits, I should use a CNOT to create a flag qubit, measure it, then use the outcome to guide a second measurement on the remaining qubits that will fully resolve the charge state.

After applying CNOT₁→₂ to the weight-1 basis states, measuring q₂ gives me either 0 or 1. When q₂=0, I collapse to |001⟩ regardless of charge—that's useless. But when q₂=1, I get a superposition of |110⟩ and |010⟩ with phase factors that depend on q, so I can extract the charge information from a second measurement on q₁ and q₃.

However, the resulting states for different charges are trine states on the Bloch sphere—they're equally spaced but still distinguishable only probabilistically. This is the same fundamental limitation I keep hitting: any single CNOT followed by measurement leaves me with trine states that can't be perfectly distinguished. Let me try a different CNOT direction, like CNOT₁→₃, to see if that breaks the pattern. When I measure q₃ after applying CNOT₂→₃, I get q₃=1 from the superposition of |001⟩ and |011⟩, which gives me a charge state with an ω^{-2} phase factor—another trine pattern emerging.

I'm noticing this is actually fundamental to the structure: any single CNOT followed by a measurement in the weight-1 sector splits into two branches—one where the measured qubit is 1 and collapses to a single basis state with no charge information, and another where it's 0 and leaves two surviving states with a charge-dependent relative phase that forms a trine. This structural property holds regardless of which CNOT I apply.

Since Clifford gates preserve weight sectors, this means ANY Clifford operation followed by a single-qubit Z measurement will always result in either no information or a trine. To escape this trap, I need to break out of the weight sector entirely, which requires a non-Clifford single-qubit gate like Ry(θ) where θ isn't a multiple of π/2—though I should double-check whether Ry(π/2) itself counts as Clifford since it relates to the Hadamard gate.

Let me think through what happens with Ry(π/2) followed by CNOT. When θ=π/2, the charge states become orthogonal in the q₁=1 measurement branch, but distinguishing all three states still requires measuring the remaining two qubits together—and measuring them sequentially just reproduces the trine problem. The real issue is that three orthogonal states in 3D space can't be distinguished by measuring one qubit at a time, even with adaptive basis choices, unless I insert entangling gates between the measurements.

Now I'm reconsidering whether this limitation actually holds for orthogonal states in higher dimensions. Let me check a simple case: three orthogonal states in a 2-qubit system like |00⟩, |01⟩, and |10⟩. If I measure q₁ first, I can distinguish |10⟩ from the other two, then measuring q₂ separates |00⟩ from |01⟩—so actually, sequential measurements do work here.

The real constraint emerges when I think about whether local unitaries can map arbitrary orthogonal states to computational basis states. For the charge eigenstates with that symmetric superposition structure, I need to check if such a local transformation exists...

These states are actually W-type entangled states—they can't be locally distinguished because the entanglement is genuinely multipartite and resistant to local operations. So the answer is no: you can't perfectly distinguish these charge eigenstates using only adaptive single-qubit measurements. You'd need at least one entangling gate between measurement rounds and non-Clifford phases to achieve this.

Now let me verify this more carefully by checking whether local operations could transform these states into computational basis states—if they could, that would mean they're locally distinguishable, but I suspect the structure of the Fourier modes prevents this. maps 3 computational basis states to 3 computational basis states, and must induce the Fourier transform within the weight-1 sector. Since the Fourier transform is entangling (it creates entanglement from product states within the sector), no local unitary can implement it. Therefore the states are NOT locally distinguishable.

More formally: |f_0⟩ has Schmidt decomposition across any bipartition that has Schmidt rank > 1, while any computational basis state has Schmidt rank 1. Since local unitaries preserve Schmidt rank, no local unitary can map |f_0⟩ to a computational basis state. Wait, |f_0⟩ = (|001⟩+|100⟩+|010⟩)/√3 is the W state, which indeed has Schmidt rank 2 across any bipartition.

But distinguishing them is actually weaker than mapping them—I just need a measurement protocol using adaptive local measurements that produces different classical outcomes for each |f_q⟩. For orthogonal states in (C²)^⊗3, LOCC discrimination is possible when the states have locally orthogonal supports. However, the charge eigenstates have a key property: the reduced density matrix on any single qubit is identical across all three states, giving equal probabilities of measuring 0 or 1 regardless of which charge eigenstate we're in. This means no single-party measurement can distinguish them.

Since all marginals are identical, the first measurement in any adaptive protocol yields zero information about the charge. Information only comes from correlations between qubits, which requires either joint measurements or entangling gates before measurement. So the charge cannot be determined by adaptive single-qubit measurements alone.

Now I'm checking whether this holds across all measurement bases, not just Z. For any basis choice, I need to verify that the reduced density matrix on each qubit remains invariant under the charge symmetry.

The reduced density matrix for a single qubit in the weight-1 sector is (2|0⟩⟨0| + |1⟩⟨1|)/3, and this is independent of which charge eigenstate we started with. Since measurement statistics in any basis are determined entirely by this density matrix, a single-qubit measurement truly yields zero information about the charge.

After applying one entangling gate and measuring, I get partial information, but the remaining qubits collapse into a trine of states—each equally likely but carrying charge information. This trine can't be distinguished without another entangling operation, so the minimum protocol requires alternating between entangling gates and measurements, with the second gate being adaptive based on the first measurement outcome.

Comparing to the non-adaptive approach: the full Z₃ QFT uses three Givens rotations (roughly three CZ gates) followed by measuring all qubits, whereas the adaptive protocol uses two entangling gates with strategic measurements in between. So adaptivity saves one entangling gate, though I should double-check whether the Givens decomposition can be optimized further—a 3×3 unitary might decompose into just two Givens with the right ordering.

Actually, thinking about the parameter counting: a generic 3×3 unitary has nine real degrees of freedom, and each Givens rotation contributes two parameters, so three Givens plus a diagonal phase matrix gives exactly 3×2 + 3 = 9 parameters. That's tight for SU(3), so we can't do better than three Givens for a generic unitary.

Let me step back and focus on the core result: single-qubit adaptive measurements can't distinguish Z₃ charges because all local marginals are identical, so we need at least one entangling gate between measurement rounds, and the minimum protocol requires two entangling gates plus measurements.

Now I'll write up a clean verification with code to demonstrate this.
````

这是一个非常尖锐的问题。让我严格证明为什么纯自适应测量不够，以及最小协议需要什么。

## 核心定理：单 qubit 自适应测量无法区分 $\mathbb{Z}_3$ charge

````plaintext
Bash Tool: Running command
````





## Prompt:
3/4/2026, 10:35:28 PM

我觉得还是存在的。我想先考虑这样子的经典Boolean function，输入长度为3的sting，将它的weight以二进制编码在后两位（00 for 0,01 for 1,10 for 2, 11 for 3）



## Response:
3/4/2026, 10:47:44 PM

````plaintext
Thought process: 分析了经典布尔函数的可逆性和权重编码结构。

The user wants to think about this problem from a classical perspective first. They want to consider a classical Boolean function that takes a 3-bit string and encodes its Hamming weight in binary on the last two bits. This is a weight-counting circuit.

Let me think about this:
- Input: 3-bit string $(a_1, a_2, a_3)$
- Output: encode the Hamming weight $w = a_1 + a_2 + a_3 \in \{0,1,2,3\}$ in binary on some bits

The Hamming weight ranges from 0 to 3, which needs 2 bits to encode:


- w=0 → 00
- w=1 → 01
- w=2 → 10
- w=3 → 11

So the output structure is $(a_1, w_1, w_0)$ where $w = 2w_1 + w_0$, essentially a classical counting network that partitions the input space by weight. The deeper insight here is that once we can compute the Hamming weight, we've created well-defined subspaces where the Z3 QFT can act independently within each weight sector.

If I reversibly compute the weight into the last two bits, then for weight-0 and weight-3 states there's only one possibility each, so they automatically contribute zero charge. For weights 1 and 2, the first bit encodes which of the three cyclic positions we're in, and that's where the Z3 QFT needs to operate on this position register. The challenge is that three positions don't compress into a single bit, so I need to reconsider how the encoding actually works with the three input bits. Compute the weight $w$ and store in the last 2 bits
- The first bit then carries the "within-weight" information

For weight 0: only |000⟩, first bit must be 0, last two bits = 00
For weight 1: three states {001, 010, 100}, first bit carries position info, last two = 01
For weight 2: three states {011, 101, 110}, first bit carries position info, last two = 10  
For weight 3: only |111⟩, first bit must be 1, last two bits = 11

The mapping would be:
- |000⟩ → |0,00⟩
- |001⟩ → |?,01⟩
- |010⟩ → |?,01⟩
- |100⟩ → |?,01⟩
- |011⟩ → |?,10⟩
- |101⟩ → |?,10⟩
- |110⟩ → |?,10⟩
- |111⟩ → |1,11⟩

I'm running into a fundamental issue: weight 1 and weight 2 each have three states that need to map somewhere, but I only have two possible values for the first bit (0 or 1) when the last two bits are fixed. This encoding scheme doesn't have enough capacity to be injective across those sectors. The user's instruction to encode weight in binary on the last two bits means I need to reconsider what the transformation actually is. I'm mapping out all eight possible inputs by their Hamming weight and seeing what outputs they'd need to produce. The problem becomes clear when I try to make this a bijection: the weight-1 and weight-2 classes each have three states, but I only have two possible values for the first output bit to distinguish them. This constraint makes the mapping impossible as described.

But maybe the user is asking me to work through this impossibility, or perhaps they want me to first understand the classical (non-reversible) version of computing Hamming weight before tackling the quantum version. Let me reconsider what they're actually asking for—they want a function that takes a 3-bit string and encodes its weight in the last two bits using binary representation. This is just classical Hamming weight computation, which in reversible quantum circuits would typically use Toffoli and CNOT gates to build up the weight incrementally.

The approach is straightforward: compute the sum $w = a_1 + a_2 + a_3$ and represent it in binary as $w = 2c + s$, where $s$ is the XOR of all three bits (the sum bit) and $c$ is the majority function (the carry bit). I can build this with two CNOTs for the sum bit, then compute the carry using the majority operation. Let me work through this circuit step by step with a truth table to make sure it's correct, since the user probably wants to see both the mechanics and understand how this behaves in the quantum setting.
````

你的思路非常好——从经典可逆计算出发，逐步构建量子版本。让我跟着这个思路走。

## 经典 Hamming weight 编码

目标：可逆映射 $(a_1, a_2, a_3) \to (?, w_1, w_0)$，其中 $w = a_1+a_2+a_3 = 2w_1 + w_0$。

但立刻遇到障碍：

| Weight | 输入态数 | 可用的第一位取值 | 问题 |
|:---:|:---:|:---:|:---:|
| 0 | 1 | $\{0\}$ 或 $\{1\}$ | OK |
| 1 | **3** | $\{0, 1\}$ | **3 > 2，不可能！** |
| 2 | **3** | $\{0, 1\}$ | **3 > 2，不可能！** |
| 3 | 1 | $\{0\}$ 或 $\{1\}$ | OK |

经典可逆函数必须是双射，但 weight-1 sector 有 3 个态要塞进 2 个格子里。这个经典函数**不存在**。

你是不是想用一个**近似**编码——不要求第一位完全无关，而是把 weight 信息尽可能集中到后两位，然后在量子版本中利用剩余的相干性来区分 charge？

````plaintext
Bash Tool: Analyze the classical Hamming weight encoding and its quantum counterpart
````

````plaintext
Thought process: 探讨了经典权重编码的可逆性与量子适应测量的可行性。

Great, so the CNOT cascade transforms the charge eigenstates very nicely. Let me analyze the structure:

After CNOT₁→₂ · CNOT₂→₃:

Weight-1 charge eigenstates:
- All have s=1 (last bit = 1), confirming weight is odd
- charge 0: |001⟩ + |011⟩ + |111⟩ (all amplitudes 1/√3)
- charge 1: |001⟩ + ω²|011⟩ + ω|111⟩ (amplitudes 1/√3 with phases)


- charge 2: |001⟩ + ω|011⟩ + ω²|111⟩

The three states in the (s=1) sector are distributed across |001⟩, |011⟩, and |111⟩, which map to positions (0,0), (0,1), and (1,1) respectively in the (a₁, p₁) encoding—so position information is stored in those two bits.

Now I'm seeing how the CNOT cascade transforms the original states, and the charge eigenstates take the form (1/√3)(|001⟩ + ω^{-q}|011⟩ + ω^{-2q}|111⟩) for each charge q. Wait, let me recalculate the relationship between these complex numbers. I have ω = e^{2πi/3}, so ω^{-1} = e^{-2πi/3} = -0.5 - 0.866i, and ω^{-2} = e^{-4πi/3} which actually equals ω. But the amplitude at |011⟩ shows +0.5j in the imaginary part, not -0.5j, so something's off with my calculation.

Now I'm tracking how the original charge-1 eigenstate transforms through the CNOT cascade. The basis states map as |001⟩ stays put, |100⟩ becomes |111⟩, and |010⟩ becomes |011⟩, which means the eigenstate gets redistributed across these new states with their respective ω coefficients.

Computing the numerical values: ω^{-2} divided by √3 gives approximately -0.2887+0.5000j, and ω^{-1} divided by √3 gives approximately -0.2887-0.5000j, confirming the transformation.

For a general charge q in the weight-1 sector after the cascade, the state becomes (|001⟩ + ω^{-2q}|011⟩ + ω^{-q}|111⟩)/√3. The measurement of the s bit is crucial here—it acts as a weight selector, distinguishing between weight-1 and weight-2 sectors, and once we're in the weight-1 sector where s=1, we can work with this simplified form.

Now I'm exploring whether measuring p1 first could help extract charge information. If p1 measures to 0, only |001⟩ remains with amplitude 1/√3 regardless of the charge value—completely uninformative. But if p1=1, both |011⟩ and |111⟩ survive, and the charge becomes encoded in the relative amplitudes ω^{-2q} and ω^{-q} across the a1 bit, which could actually reveal something about q. I'm realizing these are three distinct states on a single qubit that can't be perfectly distinguished with just one measurement. Let me explore a different approach—instead of directly measuring the parity or ancilla, what if I use an adaptive measurement strategy on the ancilla qubit? After the CNOT cascade, the weight-1 sector collapses to a superposition of three basis states, and measuring the ancilla gives me partial information that branches into different outcomes.

When the ancilla measures to 0, I'm left with a two-state superposition on the parity qubit, which is still fundamentally a trine problem—just with charge-dependent phases. Measuring the parity in a rotated basis might help, but I'm stuck with the same underlying issue: three possible charges mean three possible phases, and I can't distinguish them all with a single measurement. When the ancilla measures to 1, I get the definite state |111⟩ with a phase that depends on the charge.

Let me try rotating the measurement basis for the parity qubit by some angle θ. For the superposition state, projecting onto the rotated basis gives me an amplitude that mixes the two components with different charge-dependent phases, but I'm still not seeing how this extracts the charge information I need. I'm working through the specific cases for different charge values and seeing that these three quantum states occupy the same 2D space but aren't orthogonal to each other, making them impossible to perfectly distinguish. The core problem is that no sequence of individual qubit measurements can resolve three distinct charge states when the remaining system has dimension 2 or less. But there might be another approach I'm missing—let me reconsider what happens with a complete measurement strategy.

Actually, I think the insight here is simpler: use a CNOT cascade to classically extract the weight information first, then handle the Z₃ phase structure separately within each weight sector.

After the CNOT cascade, the parity bit s = a₁⊕a₂⊕a₃ cleanly separates odd weights (1,3) from even weights (0,2), which gives us a natural first measurement to branch on.

Let me trace through the actual basis transformation to see how the original states map. I'm checking the weight-1 and weight-3 states in the new (a₁, p₁, s) basis to verify which ones have s=1. Within the s=1 sector, I'm looking at the three weight-1 states and the single weight-3 state, then examining what happens after measurement. For each charge eigenvalue, I'm constructing the corresponding superposition of the remaining two-qubit states, which span a three-dimensional space.

Now I'm considering whether adaptive measurements on these two qubits can distinguish between the three charge states—essentially asking if I can perform a Z₃ Fourier transform within this restricted subspace to extract the charge information.

Looking at the measurement strategies: if I measure p₁ first, the outcome doesn't help distinguish charges since all three states have equal amplitude on that qubit. Measuring a₁ first gives a trine state that's also indistinguishable without additional operations. So pure adaptive measurements alone won't work—I'd need to apply additional gates to rotate into a basis where the charges become distinguishable.

The user seems to be pivoting toward a different approach, possibly considering a classical Boolean function framework instead.

They want to encode the weight of a 3-bit string in binary using the last two bits. A classical full adder can do this: the sum bit captures the XOR of all three inputs, and the carry bit captures the majority function, giving us the weight encoded in those two output bits while preserving the first input bit. In the quantum setting, this reversible transformation maps each computational basis state to one where the weight information is cleanly separated in the output bits, which might be the key to understanding how adaptive measurement could work.

But I'm running into a collision problem—weight-1 states like |001⟩ and |010⟩ both map to (carry=0, sum=1), which violates reversibility since we can't distinguish which original state we started with. The transformation isn't injective, so I need to reconsider the encoding scheme.

Actually, the CNOT cascade approach is reversible and gives us (a1, p1, s) as a bijection. The parity bit s tells us whether we have even or odd weight, and then (a1, p1) identifies which specific state within that sector. For the weight-1 sector, the three valid states |00⟩, |01⟩, |11⟩ form a 3-dimensional subspace—|10⟩ is missing because it would correspond to weight-3. So after measuring s=1 to confirm odd weight, I'm in this constrained qutrit space where the adaptive measurement can resolve which of the three states I'm actually in.

The question is whether we can do this without mapping to a standard qutrit encoding first. I'm exploring whether non-Z-basis measurements could work directly on the charge eigenstates that emerge after the CNOT cascade, where each charge sector has a specific superposition structure across the three allowed states. After the CNOT cascade, I'm realizing that within the s=1, weight-1 sector, the charge states occupy a 3D subspace of the larger 4D space—and I could potentially exploit the orthogonal |10⟩ direction to distinguish weight-1 from weight-3 states. If I measure in a basis containing |10⟩ and get that outcome, it rules out weight-1 entirely. For adaptive single-qubit measurements after that, I need to figure out how to extract the remaining charge information from the constrained subspace.

My strategy is to first measure p1: if it's 0, the a1 state collapses to |0⟩ with no charge information, but if it's 1, a1 enters a trine superposition that encodes the charge. Then in the second step, I'd measure a1 in an optimal basis for trine discrimination, which gives me about a 2/3 success rate for correctly identifying the charge in that branch.

Combining both branches, the overall success probability is only 4/9, which is quite poor. So I'm exploring whether adding an extra CNOT gate before measurement could help—specifically, one that flips a1 based on p1's value, which would transform the weight-1 charge states into a different configuration that might be easier to distinguish. Now I'm trying a different CNOT that flips p1 based on a1, which transforms the weight-1 basis states to |001⟩, |011⟩, and |101⟩ instead—a different qutrit subspace with the same underlying structure. I'm recognizing that the charge-1 states form a standard Z₃ QFT basis when encoded across those two qubits, so I need a Z₃ QFT operation on that subspace. If I measure the second qubit first, I get a trine state on the remaining qubit—which suggests an adaptive measurement strategy might work here.

Let me check what happens with different measurement orders. Measuring the first qubit in the X basis instead might break the symmetry and give me better information about the second qubit's state. I'm working through the probability calculations for different values of q in this quantum system. When q=0, I get measurement probabilities of 4/6 for |0⟩ and 1/6 for |1⟩, but for q=1 the amplitudes involve complex cube roots of unity, making the magnitudes equal at 1/6 each—so the total probability is only 1/3, which suggests I'm missing something in how these states are normalizing.

Let me step back and think about this more carefully. The real question is whether these three qutrit states encoded across two qubits can actually be distinguished using only single-qubit measurements with adaptive choices. This comes down to whether they satisfy the conditions for local distinguishability under LOCC—and since these are orthogonal states in the four-dimensional space of two qubits, I need to check if the measurement structure allows us to resolve all three charges. I'm realizing this isn't a standard bipartite decomposition since we're working with a qutrit embedded in two qubits. Let me think about whether there's an adaptive LOCC protocol that could distinguish these states, maybe by applying a sequence of controlled operations to reveal the phase structure. Actually, I should just implement this computationally to verify the phases work out correctly.

But stepping back, the user's real point might be simpler—just build the classical weight computation circuit first using Toffoli gates and see what emerges. They specifically want the weight encoded in binary in the last two positions: given input (a1, a2, a3), output (a1, w1, w0) where w = 2*w1 + w0. This means w0 captures the parity a1⊕a2⊕a3 and w1 captures the majority function MAJ(a1,a2,a3). I can construct this with a sequence of CNOTs that progressively compute these values. I need to figure out how to compute the carry bit as the majority function of the three inputs, then figure out the right gate sequence to store both the sum parity and carry in-place without losing information. approach for sorting 3 bits (which separates by weight):
- Compare-and-swap network
- Or: compute (MSB, middle, LSB) of the sorted version

Let me think about what reversible circuit maps (a1,a2,a3) to (a1, carry, sum):

want: a2 → carry = MAJ(a1,a2,a3), a3 → sum = a1⊕a2⊕a3

Starting from (a1, a2, a3):
1. CNOT a1→a3: (a1, a2, a1⊕a3) [now a3 has partial parity]
2. CNOT a2→a3: (a1, a2, a1⊕a2⊕a3) [now a3 = sum ✓]
3. Now I need to compute the majority function for the carry bit. I can express this several ways—as a1a2 ⊕ a2a3 ⊕ a1a3, or equivalently using the sum I just computed, which gives me a1⊕a2⊕a1a2⊕a2s⊕a1 in terms of the current variables.

The algebra is getting tangled, so let me try a cleaner gate sequence: after setting up the sum in a3, I'll use a CNOT from a1 to a2, then a Toffoli gate to compute the carry into a1. I'm checking whether this result matches the majority function—it doesn't. The expression I derived gives a2 ⊕ a1a3 ⊕ a2a3, but MAJ should be a1a2 ⊕ a1a3 ⊕ a2a3, so there's an extra a2 term that shouldn't be there.

Let me try a different approach with the standard full adder circuit instead of continuing down this path. Actually, I should step back—the user's request is simpler than I'm overcomplicating it. They want to compute the Hamming weight in binary and store it in the last 2 bits, with the first bit being a garbage bit that varies within each weight sector. Let me code this up and verify it works.

Now I'm mapping out the reversibility constraint: with 3 inputs, I need a bijection to 8 outputs formatted as (garbage, w1, w0). Looking at the distribution, weight 0 has 1 state mapping to (0,0,0), weight 1 has 3 states but only 2 output slots available, weight 2 has 3 states with only 2 slots, and weight 3 has 1 state mapping to (1,1,1). This is impossible to achieve classically, but the user clearly understands this constraint—they might be looking for the best approximation or exploring something else entirely.

Rereading their message, I think they're actually just asking me to implement the classical Boolean function that takes a 3-bit input string and encodes its Hamming weight in binary on the last two bits. I need to verify whether (a1, carry, sum) actually forms a bijection and properly encodes the Hamming weight across all input states.

Looking at the weight-1 cases, I'm seeing collisions—both |001⟩ and |010⟩ map to (0, 0, 1)—which means carry and sum alone don't distinguish between different orderings within the same weight class. To make this work as a bijection, I need to modify a1 based on which position the bit occupies, so that each of the three weight-1 states gets a unique output triple.

The core issue is that I have three distinct states but only one bit left to encode them. Rather than trying to force a solution here, I should focus on verifying whether the CNOT cascade approach actually preserves reversibility and then examine how it transforms the charge eigenstates.
````

你说得对，让我严格跟着这个思路走。

## 经典全加器：$(a_1, a_2, a_3) \to (a_1, \text{carry}, \text{sum})$

````plaintext
Bash Tool: Explore full adder and weight encoding circuits
````

````plaintext
Thought process: 探索经典布尔函数编码权重的可行性

The Toffoli approach didn't directly give binary weight encoding either. Let me think about this differently.

The issue is fundamental: 3 states in weight-1 can't be bijectively mapped to {0,1}×{fixed 2 bits}. 

But looking at the Toffoli truth table:
`​`​`
000 → (0,0,0) w=0
001 → (0,0,1) w=1
010 → (0,1,0) w=1
011 → (1,1,1) w=2
100 → (0,1,1) w=1


101 → (1,1,0) w=2
110 → (1,0,1) w=2
111 → (1,0,0) w=3
`​`​`

I'm noticing something crucial: the first output bit perfectly separates the weight classes. All weight-0 and weight-1 outputs have out[0]=0, while all weight-2 and weight-3 outputs have out[0]=1. This means I can use that bit as a direct weight classifier.

Looking deeper, within each group defined by out[0], the remaining bits (out[1], out[2]) distinguish between the specific weights. For weight-1 inputs, I get three distinct output patterns on those bits: (0,1), (1,0), and (1,1). The pattern continues for weight-2 as well, suggesting the output structure encodes both the weight class and a distinguishing feature within that class.

But stepping back, the Toffoli gate alone doesn't directly map to a clean weight encoding in the last two bits—the carry ends up in out[0], while out[1] and out[2] don't form a straightforward binary representation of the weight. I should reconsider what the actual goal is here.

Looking at the next part, they want to think about a classical Boolean function first: given a 3-bit input string, encode its weight (number of 1s) in binary using the last two bits. The straightforward approach is to compute the parity w0 = a1 ⊕ a2 ⊕ a3 for the low bit and the majority w1 = MAJ(a1,a2,a3) for the high bit. To make this reversible, I'd need to introduce a garbage bit, but the challenge is that this garbage bit would need to distinguish between multiple inputs that have the same weight, which creates a constraint on how cleanly the reversible version can be constructed.

Now considering whether a quantum version could work differently—perhaps allowing the first qubit to be in superposition while the last two qubits encode the weight. But mapping all three weight-1 states to superpositions over the same |01⟩ state in the last two qubits violates unitarity since the overlapping amplitudes can't be normalized properly.

So the real constraint is that you fundamentally can't encode a qutrit into 2 qubits while keeping everything separable and unitary. The user seems convinced an adaptive measurement approach exists though, and they're thinking about how the CNOT cascade plus parity measurement leaves them with a qutrit problem on 2 qubits that might be solvable through sequential measurements.

Let me work through what happens to the charge eigenstates after the CNOT operations—they're getting transformed into superpositions across the three computational basis states, and the question is whether measuring strategically in sequence could pin down which charge state we're in. representation with s=1 fixed:
charge q: (|00⟩ + ω^{-2q}|01⟩ + ω^{-q}|11⟩)/√3 on (a1, p1)

Three orthogonal states in the 3D subspace {|00⟩, |01⟩, |11⟩} of C^2 ⊗ C^2.

Question: can these be distinguished by LOCC (local operations and classical communication)?

By the results on LOCC distinguishability (Bennett et al. 1999, Walgate et al. 2000):
- Any 2 orthogonal states can be distinguished by LOCC
- d orthogonal maximally entangled states in C^d ⊗ C^d cannot be distinguished by LOCC if d>2
- But our states are NOT maximally entangled

Let me check the entanglement structure of these states. For |f_0⟩ = (|00⟩ + |01⟩ + |11⟩)/√3, I'll compute the Schmidt decomposition by finding the singular value decomposition of the state matrix, which will tell me how entangled each state actually is.

Computing the eigenvalues of the reduced density matrix shows the Schmidt coefficients aren't equal, confirming these aren't maximally entangled states. This might actually make them easier to distinguish by LOCC rather than harder.

Now I'm wondering if there's a simpler approach here—maybe the user is asking about adding a Toffoli gate to the CNOT cascade instead.

Actually, I think I see what's happening. The strategy is to compute the weight classically using the CNOT and Toffoli gates, measure those weight bits, and then the first qubit collapses into a state determined by the charge. Measuring that first qubit in the right basis should then distinguish the states. Let me verify this works: after the full adder circuit, the weight-1 outputs all have the first bit equal to 0, so measuring that bit immediately gives us information about which state we're in.

Wait, but that's not quite right either. The last two bits take three different values for weight-1, so measuring all three qubits in the computational basis would distinguish the three original states directly. But that's not what we want—we need to distinguish the charge eigenstates, which are superpositions of these computational basis states. So after the full adder circuit transforms a charge eigenstate in the weight-1 subspace, I need to figure out what that transformed state looks like and how to measure it to recover the charge information.

Let me trace through the Toffoli circuit more carefully to see exactly how each basis state maps.

Looking at the weight-1 states specifically, I need to track how the transformation affects the charge eigenstate. The key insight is that the first qubit stays 0 for all weight-1 inputs, so the relevant dynamics happen in the last two qubits—I can express the eigenstate in terms of just those two qubits after the transformation.

Now I'm checking whether these three charge states can be distinguished through adaptive measurement of just the final two qubits, since they form a qutrit encoded there.

If I measure the second qubit first, outcome 0 gives no information since it appears with equal probability across all charge states, but outcome 1 projects onto a trine configuration on the first qubit—meaning the three charge values produce distinguishable states that I could potentially resolve with a second measurement. Looking at the measurement outcomes, when qubit 1 gives 0, I get the |01⟩ state with equal probability across all q values, which doesn't help distinguish them. But measuring qubit 1 as 1 leaves me with a trine state on qubit 2—the same problem either way. I'm wondering if switching to a different measurement basis on qubit 1, like the {|+⟩,|−⟩} basis, might give me better information about which state I'm in.

Working through the projection onto |+⟩ on qubit 1, I'm getting different probability distributions depending on q. For q=0, the outcome probability is 5/6, and for q=1 it's different—so this basis choice is actually starting to distinguish between the states. ω²|0⟩ + (1+ω²)|1⟩)/√6, |1+ω²|² = |0.5-0.866i|² = 1, P(+) = 2/6
For q=2: (ω|0⟩ + (1+ω)|1⟩)/√6, |1+ω|² = |0.5+0.866i|² = 1, P(+) = 2/6

So measuring qubit 1 in X basis gives:
P(+|q=0) = 5/6, P(+|q=1) = 2/6, P(+|q=2) = 2/6

Charges 1 and 2 are indistinguishable from this measurement! We can distinguish q=0 from q≠0 but not q=1 from q=2.

After the + outcome, the residual state on qubit 2 depends on which charge we had: for q=0 it's (|0⟩+2|1⟩)/√5, while q=1 and q=2 give different superpositions involving the cube roots of unity. When we instead measure − on qubit 1, I need to work out the corresponding residual states using the same approach. Now I'm applying the ⟨+| projection to the state and simplifying the amplitude, then calculating the probability of measuring the + outcome by summing the squared magnitudes of the resulting coefficients. Now I'm working through the specific values for the conditional states after the minus measurement—computing the magnitudes of these complex coefficients and seeing how the minus eigenstate acts on each q value to extract the phase information. Now I'm checking the probability outcomes for the minus eigenstate across different values of q, calculating the amplitudes and their squared magnitudes to find the measurement probabilities.

After measuring q₁ in the X basis and getting the minus outcome, I can rule out q=0 entirely since it gives zero probability, leaving me to distinguish between q=1 and q=2 by examining their normalized states on the residual qubit q₂ and computing their inner product. Computing the inner product of these two quantum states by multiplying out the complex amplitudes—the result is 4, which normalizes to 1, meaning the states are actually identical. So there's no way to distinguish between q=1 and q=2 when we measure the outcome −.

Now I'm checking whether they might be distinguishable in the minus branch by computing their amplitudes more carefully. For q=1, the state proportional to −ω²|0⟩ + (1−ω²)|1⟩, and for q=2 it's −ω|0⟩ + (1−ω)|1⟩. I need to find the ratio between these amplitudes to see if one state is just a scalar multiple of the other. Finishing the amplitude ratio calculation for q=1, I get 1.5-0.866i, and for q=2 the ratio is its complex conjugate, 1.5+0.866i. So the two quantum states are actually distinct—the q=1 state has a different phase relationship between the basis components than q=2. I need to recalculate their inner product to see how orthogonal they really are. Now I'm computing the inner product by taking the conjugate of the first state and multiplying element-wise with the second, then squaring the magnitude to get the overlap probability. I'm computing the inner product by squaring the conjugate of each q1 component with the corresponding q2 component, and I'm noticing that (0.5-0.866i)² gives me ω², which is a cube root of unity—this is starting to reveal a pattern in the calculation. Working through the conjugate properties of the cube roots of unity—since ω* equals ω², I can simplify the inner product to ω² + (1-ω)², which I'm now expanding to complete the calculation. + 3 = 4

||q2||² = 4 by symmetry, so the overlap squared is 13/16, meaning these states aren't orthogonal but also not identical—the fidelity comes out to about 0.81. Using the formula for optimal binary state discrimination, the success probability is (1 + √3/4)/2.

Now let me work through the + and − branches separately. In the + branch, the measurement outcome occurs with probability 1/2, and I can use Bayes' rule to find that q=0 has posterior probability 5/9 while q=1 and q=2 each have 2/9. The − branch also has probability 1/2, but here q=0 never occurs while q=1 and q=2 each appear with probability 2/3.

So the challenge is that neither branch gives me perfect discrimination. The − branch leaves me unable to distinguish q=1 from q=2 with certainty, and the + branch has three states with unequal posteriors. The X-basis measurement on the first qubit is actually quite good—it eliminates q=0 entirely in the − branch—but it can't make q=1 and q=2 orthogonal. This makes me wonder whether any adaptive measurement strategy could achieve perfect charge discrimination, so I'm thinking about this from an information-theoretic angle.

The three charge states live in a 3D subspace of the two-qubit Hilbert space. For LOCC to perfectly distinguish product states, there's a general theorem that says it's always possible, but for entangled states it's more subtle. Let me check whether these states are product or entangled and verify the exact form of the q=1 and q=2 states using the cube roots of unity. I'm tracking how the charge eigenstates transform through the Toffoli circuit and then extracting the first qubit to see what remains on the final two qubits for each charge value.

Now I'm checking whether these resulting two-qubit states are entangled or separable—they appear to be entangled since they can't be written as simple products. But there's a crucial theorem from Walgate & Hardy showing that any three orthogonal states in a two-qubit system can always be distinguished using LOCC, which would mean these states are distinguishable despite their entanglement. Walgate and Hardy's 2002 result shows that in C^2 ⊗ C^n systems, any orthogonal states can be perfectly distinguished by LOCC. For our three orthogonal states in C^2⊗C^2, I can exploit the fact that the complementary one-dimensional subspace (the |00⟩ state) is orthogonal to all three, so an initial measurement checking whether we're in that subspace or not would be the first step of the protocol. ω = e^{2πi/3}, so I need to be careful with the phase relationships. Let me write out the charge eigenstates explicitly: for charge q, the state on the last two qubits is (|01⟩ + ω^{-q}|11⟩ + ω^{-2q}|10⟩)/√3. For q=0 this gives the equal superposition, for q=1 I get the phases ω² and ω, and for q=2 I'm working through the remaining case. I'm working through the three quantum states and what happens when I measure qubit A in the computational basis. When A measures to 0, all three cases collapse to the same state on qubit B, making them indistinguishable, but when A measures to 1, each case produces a different superposition state depending on which original state we started with.

Since the computational basis doesn't work, I'm trying a more general measurement basis on qubit A with adjustable angles, then calculating what conditional state appears on qubit B for each measurement outcome to see if I can find parameters that make the three resulting states distinguishable. The inner product is getting complicated with all these phase factors and roots of unity. Let me explore the other measurement outcome instead, where the conditional B state has a different structure that might be cleaner to work with.

I'm noticing that these quantum states follow a pattern where each one can be written as a superposition of two computational basis states, with the first component always being |1⟩ and the second component varying depending on the parameter q. Let me map out what these varying components look like across different values of q.

Now I'm checking whether these varying components are orthogonal to each other—computing their inner products and comparing them to their norms. The calculation shows they're actually not orthogonal; in fact, their overlap is quite significant relative to their magnitudes, which means they share substantial structure. I'm realizing that q=1 and q=2 both collapse to the same physical state |−⟩ up to global phase, making them indistinguishable in the X+ branch, while q=0 gives a different outcome. Now I need to work through what happens in the X− branch. Now I'm converting these expressions to polar form to see the phase relationships more clearly. For q=1, I get e^{−iπ/3}|0⟩ plus a √3 factor times e^{iπ/6}|1⟩, and for q=2 I'm working through a similar decomposition with the complementary phases.

Computing the inner product ⟨q1|q2⟩ for the X− branch by multiplying the corresponding amplitudes and summing—the phase factors combine to give me e^{2iπ/3} plus 3e^{−iπ/3}, which simplifies to ω plus 3ω².

Evaluating this numerically gives −2−1.732i, so the squared magnitude is 7, and with norms of 4 and 4, the fidelity works out to 7/16 or about 0.44. This means the X− branch states are more distinguishable than the X+ branch, but they're still far from orthogonal—and critically, the X+ branch has q=1 and q=2 completely identical, which is a fundamental problem for the measurement scheme.

Since the X basis isn't giving me what I need, I'm now trying the Y basis instead. I'm computing the post-measurement states for the |+i⟩ outcome by applying the Y eigenprojectors and seeing how the three quantum states q=0, q=1, and q=2 separate under this measurement.

The calculations are getting unwieldy with all these ratios, so I'm switching tactics. Instead of tracking individual measurement outcomes, I'm going to work directly with the entangled state structure where each qubit q has an associated vector |v_q⟩ that encodes the relationship between the two qubits.

These three vectors form a discrete Fourier transform pattern over the computational basis, but they're not orthogonal since we're trying to fit three states into a two-dimensional space. The key insight is that I need to find a measurement on the first qubit that makes the conditional states on the second qubit distinguishable—at least for some measurement outcomes. I'm exploring what happens when I measure the first qubit in a rotated basis parameterized by angle θ and phase φ. I'm working through the inner product calculation more carefully, breaking it down into the four cross terms between the basis states and their coefficients, then simplifying to find the overlaps between the conditional states. I'm recalculating the inner product more carefully—I need to track which terms involve the overlap between the basis states and the qutrit coefficients, and I'm realizing I made an error in how I'm combining the exponential factors with ω. I need to recalculate this from the beginning. Let me expand the inner product of these two Bell states properly, working through each term of the product systematically.

Now I'm evaluating the orthogonality condition by setting the inner product to zero, which gives me a constraint equation involving the parameters θ, ω, and φ. I'm separating this into real and imaginary parts to find when both vanish simultaneously.

From the imaginary component, either sin2θ equals zero or cosφ equals zero. The first case just recovers the computational basis, which doesn't work. The second case forces φ to π/2 or 3π/2, and then the real part requires θ = π/4, giving me the measurement basis in terms of the superposition states (|0⟩+i|1⟩)/√2 and (|0⟩−i|1⟩)/√2.

This is actually the Y basis! Let me check whether measuring qubit A in the Y basis makes the conditional states on B orthogonal for different values of q. When I apply the Y basis measurement and get the outcome corresponding to (|0⟩+i|1⟩)/√2, the resulting state on B becomes a superposition involving |1⟩ and the state |v_q⟩, scaled by i. For q=0, this expands to a combination of |0⟩ and |1⟩ with coefficients involving i.

Now I'm computing the inner product between the conditional states for q=1 and q=2 to verify they're orthogonal, using the properties of the cube roots of unity and their complex conjugates. I'm verifying the algebra—the imaginary unit squared gives me negative omega squared, so one minus that product equals one plus omega squared. Adding everything together: omega plus one plus omega squared equals zero, which confirms these states are orthogonal. Now I'm checking the inner product between the q=0 and q=1 conditional states to see if they're also orthogonal.

Finishing that calculation, I get a non-zero result with an imaginary component, so those states aren't orthogonal in this branch. But since I have two separate branches to work with, I can analyze each one independently. Now I'm setting up the same orthogonality checks for the other branch with the opposite phase factor. I'm checking the inner product between the q=0 and q=1 states across both Y branches, and finding that they're not orthogonal—there's overlap. So the key insight is that q=1 and q=2 are orthogonal to each other in both branches, but q=0 overlaps with both of them. This suggests an adaptive measurement strategy: measure qubit A in the Y basis first, then depending on which branch collapses, find the specific basis that distinguishes q=1 from q=2 on qubit B, and measure accordingly.

Now I'm working through whether this measurement basis also cleanly separates q=0 from the other states. In the +i branch, I can express the q=0 state as a linear combination of the q=1 and q=2 states since they span a 2D subspace, so measuring in the {|B_1⟩, |B_2⟩} basis would project q=0 onto one of those two outcomes rather than giving a distinct result.

This means if I measure outcome B_1, the true state could be either q=0 or q=1, and similarly B_2 could come from q=0 or q=2. To distinguish these cases, I need to calculate the conditional probabilities—specifically how likely each measurement outcome is given that the true state is q=0. I'm realizing the states are unnormalized, so I need to carefully compute the norms and inner products before calculating these probabilities.

Now I'm working through the norm calculations. I found ||B_0||² = 3, and I'm computing ||B_1||² by evaluating |1+iω²|² where ω is a cube root of unity. After substituting the value of ω² and simplifying, I'm getting approximately 3.731 for this squared magnitude.

Let me recalculate using the conjugate approach instead. Since ω³ = 1, I can expand (1+iω²)(1−iω̄) and use the fact that ω−ω² = i√3 to show that |1+iω²|² = 2+√3, which gives me ||B_1||² = 3+√3.

Now I need to compute the inner product ⟨B_0|B_1⟩ by taking the conjugate of B_0 and dotting it with B_1.

Working through the algebra: the real part cancels to zero, leaving me with i(ω²−1). Computing the magnitude squared gives 3, but I'm realizing this isn't the right formula for a projective measurement—I need to reconsider what probability I'm actually calculating here.

The correct approach uses normalized states, so the probability of measuring B₁ given the initial state is the squared inner product of the normalized basis states, which works out to approximately 0.211 for B₁ and 0.789 for B₂. This means the measurement outcome isn't deterministic for q=0, but since we're doing adaptive measurement, the next step depends on what we actually observe.

If we measure B₁, we can use Bayes' theorem to update our belief about which charge we have—the posterior probability that q=1 given outcome B₁ is about 0.826, while q=0 drops to 0.174. Similarly, measuring B₂ gives us information about whether we have q=0 or q=2, though again it's not perfectly decisive. The protocol as designed doesn't cleanly distinguish all three charges with certainty, so I need to think about whether there's a better measurement strategy.

The fundamental constraint is that we're working in C², which can only support 2 orthogonal states. Since we have 3 charge states to distinguish, and any measurement on A will collapse the system, the conditional states on B can have at most 2 orthogonal directions. This means one outcome will inevitably remain ambiguous—we can't make all three charges perfectly distinguishable in a single round. The Walgate-Hardy theorem tells us that 2⊗n systems are always LOCC-distinguishable, but our three states span a 3D subspace of C²⊗C², so after the first measurement, we're stuck with incomplete information that requires a second round to resolve. Now I'm narrowing down to the specific case of three states in C²⊗C²—the question is whether adding a fourth "dummy" state to complete the basis helps determine if LOCC distinguishability is possible for just those three states. ψ_0⟩, |ψ_1⟩, |ψ_2⟩} can be distinguished by LOCC, then so can the 3-state set {|ψ_0⟩, |ψ_1⟩, |ψ_2⟩} (just lump |00⟩ outcomes with any group).

For 4 orthogonal states in C²⊗C², LOCC distinguishability was studied by Ghosh et al. (2004) and others. The result is that 4 Bell states CANNOT be distinguished by LOCC, but if the states have unequal entanglement, they often can.

Our 4 states include one product state |00⟩ and three entangled states with different phase relationships. Since one state is unentangled while the others are entangled, I think these should be distinguishable by LOCC. The strategy would be to first check whether A measures |0⟩ and B measures |0⟩, which would identify the product state immediately. A Y-basis measurement on A should then make the remaining two states orthogonal on B's side, giving us a clear path forward. we need to adaptively handle the q=0 case.

The trick: use a THREE-OUTCOME POVM on B instead of a two-outcome projective measurement! 

But for a single qubit, POVMs can have more than 2 outcomes. A trine POVM with 3 outcomes can distinguish 3 symmetric states with optimal probability 2/3. But we don't want optimal—we want PERFECT.

For perfect discrimination of 3 states in 2D, we need at least one measurement round that eliminates one charge, then subsequent rounds to distinguish the remaining 2.

Actually, from the Y-basis analysis:
- Y+ branch: B_1 ⊥ B_2, but B_0 overlaps both
- Y− branch: same

After Y+ and measuring B in {B_1, B_2} basis, I get different outcomes depending on which state we're in—but both qubits are now exhausted, leaving me unable to distinguish all three charges perfectly. This suggests the Walgate-Hardy theorem might not apply here, or I'm misunderstanding its scope. The theorem covers two orthogonal multipartite states, but with three or more states in a 2⊗2 system, perfect LOCC discrimination might actually be impossible. I need to reconsider the full 3-qubit system after the Toffoli circuit—the first qubit is always 0 for weight-1 states, so I'm really working with an effectively classical first qubit and two active qubits. Let me reexamine the charge states across all three qubits to see how the phases distribute.

Since the first qubit is locked at |0⟩, measuring it provides no information and doesn't disturb anything, leaving me with the same 2-qubit, 3-state distinguishability problem. I could try using the first qubit as an ancilla for a more sophisticated adaptive protocol, but it's stuck in a fixed state in the weight-1 sector, so there's nothing to work with there.

I'm becoming convinced that perfectly distinguishing these three charge states using only single-qubit adaptive measurements on the remaining two qubits isn't possible—I'd need at least one additional 2-qubit gate to make progress.

But the user thinks it's still achievable, so let me reconsider whether my LOCC reasoning is sound. Actually, I just showed that measuring A in the Y basis makes B₁ and B₂ orthogonal, which means I can distinguish q=1 from q=2 in a single B measurement. The real challenge is separating q=0 from the {q=1, q=2} pair.

Here's the key insight though: the probabilities P(Y+|q=0) and P(Y+|q=1) are actually different because the unnormalized states have different norms. For the +i outcome, B₀ = i|0⟩+(1+i)|1⟩ has norm squared 3, while I need to compute the norm for B₁ to see if there's a measurable distinction. Now I'm working through the inner product calculation for the +i eigenstate projection. I need to expand the norm squared and carefully track the cross terms, then substitute in the specific vector for q=0 to get the actual probability.

For q=1, I'm computing the same expression but with the cube root of unity ω, which gives me a complex result that simplifies to (3+√3)/6 after working through the algebra. By symmetry, q=2 gives the complementary probability (3−√3)/6, and I can verify this by swapping ω and ω² in the calculation.

The key insight is that the Y-measurement probabilities differ between q=1 and q=2, which means combined with the B measurement outcomes, I can distinguish between these two cases in the +i branch. Looking at the other measurement outcomes, I see that measuring +i with the second basis eliminates q=1, leaving q=0 or q=2, while the −i outcomes follow the same pattern as their +i counterparts. This means every possible measurement result narrows down the state to exactly two of the three possibilities.

The core problem is that q=0 appears in both basis outcomes, so with only two qubits giving four total measurement results, I can't uniquely identify all three charges—at least two must share some outcomes. But I could potentially resolve this by using the Y measurement results more strategically.

Let me work through the joint probabilities for each charge across all four possible (Y, B) outcome combinations, computing the conditional probabilities for the Bell basis measurements given each initial charge state. I'm realizing I need to recalculate these carefully for both the +i and −i branches of the Y measurement.

Actually, I'm noticing something important: the measurement basis itself changes depending on which Y outcome occurs. In the +i branch, the adaptive basis uses one pair of orthogonal states, while the −i branch uses a different pair. The conditional states for charge-1 and charge-2 are genuinely different between branches, which makes sense for an adaptive measurement strategy.

The real question I need to answer is whether there's a measurement on the B system—potentially different for each Y branch—that can perfectly discriminate the charges when combined with the Y outcome information.

Since we get 4 total outcomes (2 from Y and 2 from B), but only 3 charges, one charge must map to two outcomes. For perfect discrimination, charges 1 and 2 would each need to produce the same B outcome regardless of which Y branch they're in, leaving charge 0 to capture whatever remains.

But here's the problem: when q=0, the B measurement can still yield the outcomes associated with charges 1 and 2 because the initial states aren't perfectly orthogonal—the overlaps ⟨B_0|B_1⟩ are nonzero in both branches, making it impossible to completely prevent q=0 from producing those outcomes.

So the Y-then-B protocol fails to perfectly distinguish all three charges. More broadly, any single-qubit measurement protocol on two qubits only gives four possible outcomes, which isn't enough to perfectly distinguish three entangled states in a 3D subspace.

I'm now convinced that adaptive single-qubit measurements alone can't measure the Z₃ charge—you'd need at least one entangling gate within the three-copy site. But the user seems confident it's possible, so maybe I'm missing something. Perhaps there's a different CNOT circuit arrangement that leaves the charge in a form that's actually LOCC-distinguishable, rather than the full adder structure I've been analyzing.

Different reversible circuits transform the charge eigenstates in different ways, and some might be more amenable to local measurements than others. What if I try a different CNOT pattern, or combine CNOTs with single-qubit rotations before measuring? The general protocol would involve applying some CNOT circuit, then adaptively measuring each qubit in a potentially non-computational basis depending on previous outcomes. The constraint is that only two-qubit CNOT gates are cheap in a neutral atom array, while single-qubit rotations are more expensive.

Now I'm reconsidering whether two CNOTs plus adaptive measurements are sufficient, or if I need three. The user's idea about using a Boolean function to compute the weight seems promising—the CNOT cascade computes the parity structure, and I should trace through what happens for weight-1 states after the cascade to see if the charge information becomes accessible. After applying another CNOT, the qutrit shifts to the standard encoding in the {|00⟩, |01⟩, |10⟩} subspace, with the charge q now represented as a Z₃ Fourier state. I'm checking whether three states of this form can...

Actually, let me reconsider the structure here. These states decompose nicely into product form when I factor out the first qubit — for q=0, I can write it as |0⟩_A tensored with an equal superposition on the second qubit, which suggests there might be a separability structure I can exploit for LOCC distinguishability.

But when I measure A first, I run into the same trine problem: if A=0 (which happens with probability 2/3), the resulting state on B becomes a trine configuration that's impossible to distinguish via LOCC. Measuring B first gives the symmetric situation — I get another trine with probability 2/3, making these states fundamentally indistinguishable by local operations.

The core issue is that the Z₃ QFT states are maximally entangled within the qutrit subspace with only phase differences between equal-amplitude terms, so no amount of adaptive single-qubit measurements can break that symmetry. I'm now convinced the answer is no — you need at least one entangling gate to implement the full Z₃ QFT. But since the user seems confident it's possible, I should present this analysis clearly and ask them to walk me through their protocol. in mind, or maybe they're willing to accept probabilistic (non-perfect) discrimination.

Actually, re-reading the user's message: "我觉得还是存在的。我想先考虑这样子的经典Boolean function" — maybe they're not saying adaptive measurement alone works, but rather they want to build up the understanding from the classical case. The "it exists" might refer to the whole circuit (including non-Clifford gates), not just adaptive measurement.

Let me present what I've found and ask for clarification. Actually, the user specifically said "是否有可能只用adaptive measurement简单的实现k=3下的SWAP本征态分辨" and then said "我觉得还是存在的". So they do think adaptive measurement alone suffices.

I should present my analysis showing the trine obstruction clearly and let them respond. They might have an idea I haven't considered, so I'll focus on laying out the classical weight circuit, the quantum version, and then the fundamental obstruction that emerges.
````

好，你的思路很清晰。经典 weight 无法精确编码为 $(?, w_1, w_0)$ 的双射（3 态 > 2 格）。但可以用 CNOT cascade 提取**部分** weight 信息。现在让我追踪量子版本中 charge 信息的命运：

````plaintext
Bash Tool: Complete LOCC analysis of charge distinguishability
````



## Prompt:
3/4/2026, 10:49:31 PM

````plaintext
Thought process: 分析了经典布尔函数的可行性与计数限制。

The user is asking me to think about a classical Boolean function that takes a 3-bit string and encodes its Hamming weight in binary on the last two bits. Let me think about this carefully.

Input: $(a_1, a_2, a_3)$, weight $w = a_1 + a_2 + a_3 \in \{0,1,2,3\}$

Output: $(g, w_1, w_0)$ where $w = 2w_1 + w_0$, and $g$ is some "garbage" bit.

The mapping must be a bijection (reversible). Let's count:


- $w=0$: 1 input state but 2 available output slots in $(g, 0, 0)$ — that works.
- $w=1$: 3 input states but only 2 output slots in $(g, 0, 1)$ — this is impossible.
- $w=2$: 3 input states but only 2 output slots in $(g, 1, 0)$ — also impossible.
- $w=3$: 1 input state and 2 available output slots in $(g, 1, 1)$ — that works.

This reveals a fundamental counting problem: I can't fit 3 states into 2 slots, so a reversible function with this structure shouldn't exist. But the user seems confident it does, so maybe I'm misunderstanding what they're asking for. 2 bits. But we have 3 bits total. So we want a bijection $f: \{0,1\}^3 \to \{0,1\}^3$ such that the last two bits of $f(a_1,a_2,a_3)$ encode the weight.

But as I showed, weight 1 has 3 states and we only have 2 slots (since the first bit is binary). So this is impossible as a bijection.

Unless the user is thinking about something different? Maybe they're okay with it not being a bijection, or maybe they want a different encoding approach?

Actually, maybe the user already recognizes this is impossible and wants me to work through why carefully, then figure out what's actually achievable. Or perhaps there's a clever trick I'm missing.

Let me reconsider what they're asking for. They said the adaptive measurement protocol still exists, and want to build up from a classical perspective. Maybe the key insight is that you don't need to encode the weight exactly—for the charge measurement, you need something different. The weight sectors partition the space as {0}, {1}, {2}, {3} with sizes 1, 3, 3, 1, while the charge sectors are {0} (4D), {1} (2D), {2} (2D) with sizes 4, 2, 2. So perhaps the user is suggesting we approach this by thinking about what measurement structure is actually possible rather than forcing an exact weight encoding. I'm wondering if the user actually needs a perfect bijection, or if the encoding just needs to work within an adaptive measurement scheme where you measure weight first, then conditionally measure charge on the remaining qubits. The weight encoding could be lossy as long as it provides enough information to determine the charge sector in context.

But looking back at the conversation, the user has been told multiple times about the pigeonhole obstruction and keeps insisting this should work. Let me reconsider what they're actually asking for—they specified the weight should be encoded in the last two bits, so I need to think about what function they're describing more carefully.

Now I'm working through the bijection case systematically. For a 3-bit input where the output is the function value plus the binary encoding of the Hamming weight in the last two positions, I need to check if this can actually be a bijection. Starting with weight 0 (the all-zeros input), I have one input mapping to outputs with last bits 00, which gives me two possible slots. For weight 1 inputs, I have three inputs that all need to map to outputs ending in 01, but that's only two available slots—so there's the collision problem right there.

The user seems convinced this should work, so rather than just declaring it impossible, I should lay out this counting argument clearly and ask what they're actually looking for, since maybe they have a different construction in mind.
````

你说得对，让我回到你的思路，仔细看这个经典函数。

## 计数

输入 $(a_1, a_2, a_3)$ 共 8 个态，要求输出 $(g, w_1, w_0)$ 也是 8 个态的双射，其中 $w = a_1+a_2+a_3 = 2w_1+w_0$。

| Weight $w$ | 输入态数 | 要求 $(w_1,w_0)$ | 可用 $g$ 值 | 可用 slot 数 |
|:---:|:---:|:---:|:---:|:---:|
| 0 | 1 | $(0,0)$ | $\{0,1\}$ | 2 |
| 1 | **3** | $(0,1)$ | $\{0,1\}$ | **2** |
| 2 | **3** | $(1,0)$ | $\{0,1\}$ | **2** |
| 3 | 1 | $(1,1)$ | $\{0,1\}$ | 2 |

Weight 1 有 3 个态需要塞进 2 个 slot，鸽巢原理不行。

这个经典双射**不存在**。你是打算放宽某个条件（比如允许 weight 1 的某个态借用 weight 0 的空 slot），还是你想考虑的是另一种编码方案？



## Response:
3/4/2026, 11:55:56 PM

```quarto
# Begin from SWAP's eigenbasis

In many tasks of non-linear property estimation tasks, we need to realize the projection on the eigenbasis of the $k$-cycle SWAP operator. Note that $\mathrm{SWAP}_{(1\cdots k)}$ is a non-hermitian operator, with eigenvalues $\{e^{i2r\cdot \pi/k}\}_{r=0}^{k-1}$ and degenerate eigenspaces.

:::{#lem-degenerate-eigenspace-swap .callout-important icon="false"}
## (Degenerate eigenspace of SWAP)
The SWAP operator $\mathrm{SWAP}_{(1\cdots k)}$ on $(\mathbb{C}^2)^{\otimes k}$
satisfies $\mathrm{SWAP}_{(1\cdots k)}^k = \mathbb{I}$, so its eigenvalues
are the $k$-th roots of unity
$\{\lambda_r = e^{i2\pi r/k}\}_{r=0}^{k-1}$.
The projector onto the $r$-th eigenspace is
$$
\Pi_r = \frac{1}{k}\sum_{m=0}^{k-1}
        e^{-i2\pi rm/k}\,\mathrm{SWAP}_{(1\cdots k)^m},
$$
with dimension
$$
d_r = \mathrm{tr}(\Pi_r)
    = \frac{1}{k}\sum_{m=0}^{k-1}
      e^{-i2\pi rm/k}\,d^{\gcd(m,k)},
$$
where the identity $\mathrm{tr}(\mathrm{SWAP}_\pi) = d^{c(\pi)}$ is used,
with $c(\pi)$ the number of cycles of $\pi \in S_k$, and
$c\!\left((1\cdots k)^m\right) = \gcd(m,k)$.
:::

How to realize the projector $\Pi_r$?
Consider the case $k = 2$. The subspace is split to $\{00,11,01+10\}$ for $+1$ and $01-10$ for $-1$.
To adaptively implement this projector, we notice that the partity of the string is a conservative quantity and use $CNOT_{12}$ to check the parity of the first qubit and then adaptively apply $R_y(\pm \pi/2)$ to the second qubit. That is, we implement the following measurement:
$$
\begin{align*}
\left\{\begin{aligned}
&\{\ket{00},\ket{11},\ket{01}+\ket{10}\} \xrightarrow{\text{CNOT}_{12}} \{\ket{00},\ket{10},(\ket{0}+\ket{1})\ket{1}\} \\
&\{\ket{01}-\ket{10}\} \xrightarrow{\text{CNOT}_{12}} \{(\ket{0}-\ket{1})\ket{1}\}
\end{aligned}\right.
\end{align*}
$$
Consider the case $k = 3$. The subspace is split to:

- $\{000,111,001+010+100,011+101+110\}$ for $+1$
- $\ket{001}+e^{i2\pi/3}\ket{010}+e^{i4\pi/3}\ket{100},(\ket{011}+e^{i2\pi/3}\ket{101}+e^{i4\pi/3}\ket{110})$ for $e^{i2\pi/3}$,
- $\ket{001}+e^{i4\pi/3}\ket{010}+e^{i8\pi/3}\ket{100},(\ket{011}+e^{i4\pi/3}\ket{101}+e^{i8\pi/3}\ket{110})$ for $e^{i4\pi/3}$.

To adaptively implement this projector, we first implement $\mathrm{CNOT}_{13}\mathrm{CNOT}_{23}$ check the last qubit:
$$
\begin{align*}
&\{111\},\{\ket{001}+e^{i\omega}\ket{011}+e^{i2\omega}\ket{101}|\omega \in \{0,2\pi/3,4\pi/3\}\}\\
&\{000\},\{\ket{010}+e^{i\omega}\ket{100}+e^{i2\omega}\ket{110}|\omega \in \{0,2\pi/3,4\pi/3\}\}
\end{align*}
$$
This reduce the problem to the discrmination tasks of the following two sets:
$$
\begin{align*}
&\{11\},\{\ket{00}+e^{i\omega}\ket{01}+e^{i2\omega}\ket{10}|\omega \in \{0,2\pi/3,4\pi/3\}\}\\
&\{00\},\{\ket{01}+e^{i\omega}\ket{10}+e^{i2\omega}\ket{11}|\omega \in \{0,2\pi/3,4\pi/3\}\}
\end{align*}
$$
For the first set, we can use the same strategy. That is, we first implement a $CPHASE_{12}(\theta)$ such that (t.b.c.)

```

Continue this derivation





---
Powered by [Claude Exporter](https://www.ai-chat-exporter.net)
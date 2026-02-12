# **神经动力学的相变：Lazy与Rich机制交汇处的Grokking现象深度解析**

## **摘要**

"Grokking"（顿悟）现象——即神经网络在训练误差降至零并长期停滞后，突然表现出泛化能力的延迟相变——构成了现代深度学习理论中最令人费解的谜题之一。这一现象不仅挑战了传统的统计学习理论，更暗示了神经网络内部存在着某种热力学性质的相变机制。本报告旨在通过统计物理学和平均场理论（Mean Field Theory, MFT）的视角，对Grokking现象进行详尽的剖析。我们将论证，Grokking并非优化过程中的偶然，而是系统从受神经正切核（NTK）主导的“Lazy机制”（惰性机制）向特征学习主导的“Rich机制”（丰富机制）跃迁的一阶或二阶相变。

本报告综合了大量前沿文献，建立了一个统一的有效理论框架。我们将定义并分析一系列物理序参量，包括表示质量指数（RQI）、有效秩（Effective Rank）、参与率（Participation Ratio）以及核对齐度（Kernel Alignment），以量化网络在损失函数能量景观中的轨迹。分析表明，这种转变是由信号学习率与噪声学习率之间的竞争驱动的，并受到初始化尺度（![][image1]）、样本量和正则化强度的精细调节。当网络处于超参数的“金发姑娘区”（Goldilocks zone）时，它被迫压缩其内部表示，从高熵的“无序”状态（记忆）坍缩为低熵的“有序”状态（特征学习）。此外，报告还探讨了有限宽度效应下的费曼图修正，以及新型优化器（如Muon）如何通过谱动力学加速这一相变过程。

## ---

**1\. 神经动力学的基石：机制的二分法**

要理解Grokking，首先必须解构神经网络行为的两个基本极限：Lazy机制（Lazy Regime）和Rich机制（Rich Regime）。这不仅仅是描述性的标签，而是代表了学习动力学中数学上截然不同的普适类（Universality Classes），它们的区别在于参数随宽度的缩放方式以及在梯度下降过程中的演化轨迹。

### **1.1 Lazy机制：神经正切核（NTK）的微扰视角**

Lazy机制，通常通过神经正切核（Neural Tangent Kernel, NTK）理论形式化，描述了一种神经网络表现为线性化模型的学习模式 1。在无限宽度的极限下，如果权重按照特定的缩放（通常是 ![][image2]）进行初始化，网络参数在训练过程中仅会从初始化位置移动无穷小的距离。尽管这些微观变化极其微小，但由于参数数量巨大，累积效应足以使网络在初始化周围的一个小球内找到解，从而完美拟合训练数据 3。

在这种机制下，网络函数 ![][image3] 可以通过其在初始参数 ![][image4] 处的泰勒展开来近似：

![][image5]  
这种线性化意味着训练动力学由一个固定的核——NTK——主导，其定义为：

![][image6]  
至关重要的是，在Lazy机制中，这个核在整个训练过程中保持恒定 2。网络本质上充当了一个核机器，使用初始化时存在的随机特征来解决岭回归问题。在这种情境下，不存在深度学习意义上的“表示学习”；内部特征不会适应目标函数的结构。网络只是简单地重新加权它“与生俱来”的随机特征。

虽然NTK机制解释了大规模网络优化至零训练损失的能力（通过过参数化保证核的正定性），但它无法解释现代深度学习在算法任务上观察到的泛化能力，因为这些任务要求网络发现底层的结构 1。当目标函数与初始随机特征不对齐时，Lazy机制表现出典型的“死记硬背”（memorization）行为。

### **1.2 Rich机制：特征学习与平均场理论**

与之形成鲜明对比的是，“Rich”机制（或称特征学习机制）是深度学习“魔力”的源泉。这种机制通常通过不同的缩放极限（如输出层的 ![][image7] 缩放或最大更新参数化 ![][image8]P）来访问 6。在这种机制下，权重从初始化位置发生显著迁移（量级为 ![][image9]），允许网络演化其内部表示。

描述这一机制的最佳理论框架是动力学平均场理论（Dynamical Mean Field Theory, DMFT） 1。DMFT 不将高维权重矩阵视为分布的固定样本，而是将其视为随时间演化的动态变量，其统计分布服从麦基恩-弗拉索夫（McKean-Vlasov）过程。

在Rich机制中，核不是静态的。它会演化并适应数据。这种适应性在核的特征函数与目标函数的对齐中清晰可见 9。“Rich”网络不仅仅是拟合数据；它在压缩数据，寻找能够捕捉任务潜在结构的低秩表示。这正是“Grokking”的栖息地——它是网络挣脱Lazy/NTK吸引盆地，寻找更高效、更“丰富”解的过程 5。

### **1.3 缩放参数 ![][image1] 的控制作用**

近期研究的一个核心洞见是，这两种机制之间的转换是连续的，并且可以通过一个标量超参数（通常表示为 ![][image1]，或初始化尺度的倒数）来控制 5。

* **大 ![][image1]（Lazy态）**：网络输出被放大，或者权重初始化较大。误差信号很大，但为了最小化损失所需的权重变化很小。权重不需要移动很远就能满足方程，因此停留在初始化附近。核保持静态。  
* **小 ![][image1]（Rich态）**：网络输出较小。权重必须在损失景观中移动显著距离才能建立拟合标签所需的信号。这种长距离的轨迹允许网络的非线性特性使特征空间发生变形，从而与数据结构对齐 12。

Grokking 本质上是一种动力学现象，当网络处于这两种机制的临界点，或者受到正则化项的推动时，它最初表现出Lazy行为（记忆），但最终在梯度下降和权重衰减的压力下，跌入Rich机制 5。

## ---

**2\. Grokking的唯象学：从记忆到理解的时空跨越**

“Grokking”一词最初由Power等人（2022）在神经网络语境下提出，借用了罗伯特·海因莱因小说《异乡异客》中的概念，意指一种深层的、直觉性的理解。在机器学习中，它指的是一种特定的、反直觉的训练曲线形态 14。

### **2.1 典型的Grokking曲线形态**

在常规机器学习任务中，训练精度和验证精度通常同步上升。如果模型过拟合，训练精度达到100%，而验证精度停滞或下降。但在Grokking场景中，时间线被拉长且呈现出独特的阶段性：

1. **第一阶段：记忆期（The Lazy Phase）** 网络迅速最小化训练误差。训练精度飙升至100%（或损失降至0）。在此阶段，验证精度保持在随机猜测水平（例如，二分类为50%，模 ![][image10] 运算为 ![][image11]）。网络利用其随机初始化的高维容量（NTK行为）“死记硬背”了训练数据 16。此时，网络并未学习到数据的生成规则，而是将噪声和信号一视同仁地编码。  
2. **第二阶段：平台期（The Silent Phase）** 在一段漫长的时间内——通常比初始拟合阶段长几个数量级——训练精度保持完美，而验证精度在随机水平上纹丝不动。对外部观察者来说，学习似乎已经停滞。然而，在网络内部，权重正在缓慢漂移。尽管梯度很小（因为训练损失接近零），但并非为零。正则化（权重衰减）和优化器的隐式偏差正在施加恒定而微弱的压力，推动权重构型在零损失流形上游走 15。  
3. **第三阶段：泛化期（The Rich Phase Transition）** 突然之间，验证精度急剧飙升。在极短的训练步数窗口内，模型“悟”出了底层规则。验证精度上升至与训练精度匹配的水平（通常接近100%）。网络从记忆解（高复杂度，本质上是查找表）跃迁至泛化解（低复杂度，真实的算法逻辑） 18。

### **2.2 算法任务与数据稀疏性的催化作用**

Grokking 最常在算法数据集上被观察到，例如模加法（![][image12]）或稀疏奇偶校验任务 19。这些任务具有严格的低维结构（例如，模运算中的傅里叶特征），如果将其视为通用输入，这些结构是完全模糊的。

数据稀疏性加剧了这一现象。当训练集大小较小（相对于总可能输入空间）时，Lazy解（记忆）很容易找到。Rich解（通用规则）虽然在任何地方都有效，但更难被梯度下降发现。寻找简单解与寻找通用解之间的难度差距造成了延迟。如果数据集足够密集（占总空间的很大比例），网络被迫更早地进行泛化，Grokking（即延迟）现象就会消失 14。

## ---

**3\. Grokking作为相变：统计物理学的理论框架**

从平台期到泛化的转变在数学上等价于统计物理中的相变。本节将利用平均场理论，探讨将Grokking映射到一阶和二阶相变的具体理论框架。

### **3.1 能量景观与熵的博弈**

在物理学中，系统演化以最小化自由能 ![][image13]，其中 ![][image14] 是能量，![][image15] 是熵。在神经网络中，“能量”对应于损失函数（加上正则化项），而“熵”与对应于特定解的权重空间的体积相关 22。

* **记忆解（Memorization Solution）**：对应于“玻璃态”（glassy state）。它具有零训练能量（损失为零），但是高度无序的。权重本质上是初始化的随机扰动。这类配置的数量极多（高熵），使得网络在训练初期统计上极易落入这个盆地 24。  
* **泛化解（Generalizing Solution）**：对应于“晶体态”（crystal state）。它同样具有零训练能量（以及零测试能量）。然而，它是高度有序的（低熵）。权重必须与目标特征（如傅里叶模式）精确对齐。

Grokking 本质上是系统逃离高熵、亚稳态的非晶态（记忆），寻找低熵、稳定的晶体态（泛化）的动力学过程。“延迟”是系统穿越熵垒所需的时间，或者是“Rich”特征的缓慢动力学增长至足以主导输出所需的时间 17。

### **3.2 Liu等人的有效理论**

Liu等人（2022/2023）提出了一种有效理论，将学习动力学分解为两个竞争的时间尺度：“信号”的学习（结构化表示）和“噪声”的学习（记忆） 15。

他们定义了超参数的“金发姑娘区”（Goldilocks zone）：

* **困惑区（Confusion）**：正则化过高；什么都学不到。  
* **记忆区（Memorization）**：正则化过低；网络瞬间拟合噪声且不再离开。  
* **Grokking区**：正则化适中。网络首先拟合噪声（快速动力学），但正则化项（权重衰减）使得高范数的记忆解变得不稳定。网络缓慢地向低范数的泛化解“漂移”。

信号强度 (![][image16]) 与噪声强度 (![][image17]) 的有效更新方程可以建模为：

![][image18]  
![][image19]  
当信号增长缓慢（核中的小特征值）而噪声受到权重衰减 ![][image20] 的抑制时，Grokking就会发生。最终，信号分量跨越阈值，并在Softmax输出中抑制噪声分量 25。

### **3.3 映射到一阶相变**

Kumar等人（2024）和Rubin等人（2024）的研究明确将Grokking映射为一阶相变 5。

在一阶相变（如水结冰）中，序参量（如密度）发生不连续变化。在Grokking中，“序参量”（测试精度或特征重叠度）发生跳变。系统在转变过程中处于“混合相”（Mixed Phase）。

* **前Grokking（亚稳态）**：系统处于DMFT“作用量”（Action）的局部极小值，对应于Lazy机制。与教师特征的重叠度接近零（![][image21]）。  
* **转变点**：随着样本量或训练时间的增加，作用量的全局极小值发生转移。一个新的极小值出现在 ![][image22]（完美重叠）处。  
* **后Grokking（稳态）**：系统沉降到Rich机制中。

DMFT描述的“混合相”涉及预激活分布变为**高斯混合**（Gaussian Mixture Feature Learning, GMFL）。在Grokking之前，预激活是高斯的（GFL）。在转变过程中，特征学习神经元的“液滴”（droplets）形成，打破了高斯对称性 17。

## ---

**4\. 物理序参量：量化相变**

为了严格表征这一相变，我们必须定义“序参量”——能够区分无序（Lazy）相和有序（Rich）相的可测量量。文献中确定了几个关键指标。

### **4.1 表示质量指数（Representation Quality Index, RQI）**

由Liu等人 15 提出，RQI 测量嵌入空间的几何结构。对于像模加法（![][image23]）这样的任务，真实的嵌入应该形成规则的网格或晶格结构（例如，环面）。

![][image24]  
其中 ![][image25] 是学习到的嵌入空间中“平行四边形”（满足 ![][image26] 的四个点集）的数量，并通过总的可能平行四边形数量 ![][image27] 进行归一化。

* **Lazy相**：嵌入是随机的。RQI ![][image28]。  
* **Rich相**：嵌入是结构化的。RQI ![][image29]。  
  相变表现为RQI的急剧S形上升，与测试精度的上升同步。

### **4.2 有效秩与参与率**

这些参数测量学习到的表示的维数。在Lazy机制中，网络使用所有可用的维度（随机特征）来拟合噪声。在Rich机制中，网络将数据压缩到与任务对齐的低维流形上 27。

#### **4.2.1 有效秩（Effective Rank, erank）**

有效秩利用表示矩阵（激活的协方差矩阵）的奇异值（![][image30]）的香农熵来定义 29。

设 ![][image31] 为归一化的奇异值分布。

![][image32]  
![][image33]

* **观察**：在记忆阶段，有效秩很高（高熵，需要许多奇异值来解释方差）。在Grokking转变处，有效秩急剧坍缩，表明网络找到了低秩解（例如，模加法所需的少数傅里叶模式） 27。

#### **4.2.2 参与率（Participation Ratio, PR）**

参与率是凝聚态物理中用于描述局域化理论的常用指标 31。对于协方差矩阵 ![][image34] 的一组特征值 ![][image35]：

![][image36]

* **物理诠释**：如果方差均匀分布在 ![][image37] 个神经元上，PR ![][image38]（离域/Lazy）。如果方差集中在单个模式上，PR ![][image29]（局域/Rich）。  
* **Grokking信号**：PR的急剧下降是Grokking相变的一个稳健序参量 27。

### **4.3 核对齐度（Kernel Alignment）**

神经正切核（NTK）与目标函数 ![][image39] 之间的对齐度是特征学习的直接度量 9。

![][image40]

* **Lazy机制**：核 ![][image41] 在初始化时固定。对齐度低且恒定。  
* **Rich机制**：核演化。![][image42] 旋转，使其主要特征向量与目标标签 ![][image39] 对齐。  
* **相变**：Grokking 对应于核对齐度的突然增加。网络“学习”到了适合任务的核 6。

### **4.4 信号与噪声子空间投影**

更微观的视角涉及将权重向量 ![][image43] 投影到由信号（真实特征）和噪声（正交补）定义的子空间上 33。 设 ![][image44] 为真实特征（如基真傅里叶模式）张成的子空间。 设 ![][image45] 为正交子空间。

序参量定义为：

![][image46]  
![][image47]

* **第一阶段**：![][image48] 迅速增长以拟合训练数据。![][image49] 增长缓慢。  
* **第二阶段**：![][image48] 衰减（由于权重衰减）或饱和。![][image49] 继续呈指数增长，但基数很小。  
* **第三阶段（Grokking）**：![][image49] 超过 ![][image48]。信噪比（SNR）跨越临界阈值，Softmax非线性放大了信号，导致完美泛化 33。

### **4.5 磁化率（Susceptibility）**

借鉴自统计力学，磁化率测量序参量对外部扰动的响应。在Grokking语境下，它描述了网络对数据分布微小变化的敏感性 35。在相变点附近，磁化率通常会发散，这标志着系统处于临界状态，微小的信号增强足以引发宏观状态的改变。

## ---

**5\. 平均场理论与相变机制**

动力学平均场理论（DMFT）提供了在无限宽极限下这些序参量的运动方程。与NTK极限（同样是无限宽但特定缩放）不同，平均场极限允许特征演化 1。

### **5.1 DMFT方程与作用量**

在平均场极限下，权重的分布由概率密度流描述。单个神经元 ![][image50] 的动力学由随机微分方程控制，其中与其他神经元的相互作用被“平均场”（极限下的高斯过程）所替代 1。

Grokking在DMFT中的核心对象是**作用量**（Action, ![][image15]）或有效势能。系统轨迹旨在最小化这一作用量。 Kumar等人 17 将这种转变描述为作用量景观中两个极小值之间的竞争：

1. **无特征极小值（Featureless Minimum）**：权重未对齐。“磁化强度”（与目标的重叠）为零。这是Lazy解。  
2. **特征学习极小值（Feature-Learning Minimum）**：权重已对齐。磁化强度非零。这是Rich解。

“作用量”取决于样本大小 ![][image10] 和初始化尺度 ![][image1]。

* 对于小 ![][image10]，无特征极小值是全局的。无Grokking。  
* 对于大 ![][image10]，特征学习极小值变为全局的。  
* **Grokking即磁滞回线**：系统从无特征盆地（亚稳态）开始。它需要时间波动出来，或者等待“盆地”在正则化的影响下变得不稳定。

### **5.2 混合相（GMFL）与高斯混合**

DMFT分析的一个重要洞见是“混合相”（Gaussian Mixture Feature Learning, GMFL）的存在 17。 在纯Lazy机制中，预激活服从高斯分布。 在Rich机制中，它们是非高斯的。 在转变过程中，分布是**混合的**。一些神经元已经“专门化”（锁定特征），成为谱分布中的离群值，而大多数神经元仍停留在“Lazy”的高斯云中。

这与随机矩阵理论中的\*\*“尖峰”模型（Spike model）\*\*一致。权重的协方差矩阵产生了一个从Marchenko-Pastur体谱中分离出来的“尖峰”特征值 32。Grokking事件就是这个尖峰从体谱中浮现的过程。

## ---

**6\. 初始化与缩放参数 ![][image1] 的调控作用**

参数 ![][image1]，控制网络输出的尺度（或反过来，权重初始化的尺度），是调节系统在Lazy和Rich行为之间转换的“旋钮” 5。

考虑模型输出 ![][image51]。

* **大 ![][image1]**：为了产生量级为1的输出，权重 ![][image52] 必须很小。小权重意味着系统停留在激活函数的线性（泰勒展开）区域。![][image53] **Lazy**。  
* **小 ![][image1]**：为了产生量级为1的输出，权重 ![][image52] 必须很大。大权重将神经元推向激活函数的非线性饱和区。![][image53] **Rich**。

Kumar等人 5 表明，当 ![][image1] 足够大以允许初始记忆（Lazy），但又没有大到完全禁止特征学习时，Grokking最为普遍。它需要一个“甜蜜点”（sweet spot），在这里特征学习率非零但很慢。

**时间尺度分离**：

Grokking的核心机械原因是输出层（线性，快速）和隐藏层（非线性，慢速）动力学之间的时间尺度分离。

![][image54]  
网络利用读出权重（记忆）迅速解决问题。特征权重在时间尺度 ![][image55] 上演化。Grokking发生在 ![][image56] 时。

## ---

**7\. 有限宽度修正与费曼图**

虽然DMFT在无限宽极限下工作，但真实的Grokking发生在有限宽度的网络中。Guillen等人（2025） 38 引入了费曼图形式主义来计算NTK的 ![][image7] 修正。

在无限宽下，NTK是常数。代表权重之间“相互作用”的费曼图会自我闭合。 对于有限宽度，这些闭环贡献了非平凡的修正。NTK的“漂移”（允许特征学习）在标准参数化下是一个 ![][image7] 效应。 这证实了为什么在未进行特定调优（如 ![][image8]P 缩放）的大规模网络中，Grokking往往难以观察到——除非通过学习率或初始化的缩放来补偿，否则“Richness”会被宽度抑制 39。

费曼展开表明，“四点顶点”（权重间的相互作用强度）负责特征演化。如果这个顶点强度为零（高斯极限），则不会发生Grokking。

## ---

**8\. 算法启示：Muon优化器与谱动力学**

对Lazy到Rich转变的理论理解对优化器设计具有实际意义。Jordan等人提出的“Muon”优化器（Momentum Orthogonalized） 40 旨在迫使网络进入Rich机制。

标准的SGD或Adam是逐元素作用的。它们不尊重权重矩阵的谱结构。

Muon作用于权重矩阵的奇异值，有效地对更新进行正交化。这防止了“主导模式”（通常是噪声模式或领先的Hessian特征向量）掩盖“信号模式”。

通过在特征模式之间均衡学习率（或在谱域中创建各向同性更新），Muon加速了“特征学习”阶段。它有效地降低了Lazy和Rich盆地之间的势垒，消除了Grokking的“平台期”或将其显著压缩。

Muon迫使权重更新最初是满秩的（或高有效秩），但允许特定的“尖峰”结构比SGD更清晰地浮现，而SGD往往卡在由顶部Hessian特征值主导的“Lazy”子空间中 41。

## ---

**9\. 结论**

Grokking 不是一个谜；它是一个相变。它是神经网络跨越Lazy（NTK）普适类和Rich（特征学习）普适类边界的可观测结果。

本报告详细阐述了这一转变的物理机制：

1. **状态变量**：网络从高熵、无序状态（高有效秩，低RQI，低核对齐度）移动到低熵、有序状态（低有效秩，高RQI，高核对齐度）。  
2. **机制**：转变是由信号学习与噪声记忆之间的竞争驱动的，并受到正则化和初始化尺度（![][image1]）的调节。  
3. **动力学**：这是一个涉及混合相的一阶或二阶相变，其中特征的“液滴”从高斯体中浮现。

这一结论具有深远的意义。“过拟合”并不是学习的终点；它通常只是通往真正理解（相变）之前的亚稳态。“稳定性边缘”（Edge of Stability）和“金发姑娘区”是利用原始数据孵化智能所需的热力学条件。

随着我们迈向更大的模型，理解这些相变使我们能够通过工具（如Muon优化器或特定的缩放定律）来工程化这些过程——绕过浪费的“记忆”平台期，直接跳入广义特征学习的“Rich”机制。

## ---

**附录：核心概念深度分析**

### **表 1：Lazy机制与Rich机制的对比分析**

| 特征 | Lazy机制 (NTK) | Rich机制 (Mean Field) |
| :---- | :---- | :---- |
| **缩放极限** | 无限宽，标准参数化 | 无限宽，平均场/![][image8]P参数化 |
| **权重移动** | $ | \\Delta W |
| **核行为** | 静态（初始化时冻结） | 动态（随数据演化） |
| **特征学习** | 无（固定基函数） | 活跃（基函数对齐） |
| **序参量** | 线性化精度 | 特征重叠度 / 磁化强度 |
| **Grokking?** | 无（除非使用正则化） | 有（内在属性） |
| **有效秩** | 高（保持随机） | 坍缩（变为低秩） |

### **表 2：Grokking的物理序参量**

| 序参量 | 符号 | 物理类比 | 转变时的行为 |
| :---- | :---- | :---- | :---- |
| **表示质量指数** | RQI | 晶体有序度 / 对称性 | ![][image57] 急剧上升 |
| **有效秩** | **![][image58]** | 本征态熵 | 急剧下降（坍缩） |
| **参与率** | PR | 局域化长度 | 急剧下降（局域化） |
| **核对齐度** | **![][image59]** | 场对齐 | S形增加 |
| **信噪子空间投影** | **![][image60]** | 信噪比 | 交叉点 (![][image61]) |

### **深度剖析：信噪交叉机制**

解释Grokking“延迟”最直观的方法是信号与噪声的谱差异。

* **噪声**：训练集中的“噪声”（随机标签或特定实例细节）是高维且满秩的。在NTK机制中，网络与Hessian的顶部特征向量对齐。如果噪声强烈投影到这些“硬”模式（大特征值）上，误差下降很快。  
* **信号**：“信号”（例如，模运算规则）通常对应于特定的、低维的子空间。如果网络初始化是随机的，根据大数定律，权重在信号子空间上的投影很小。  
* **赛跑**：  
  * ![][image62] 下降很快，因为很容易找到一个随机子网络来拟合它（彩票假设）。  
  * ![][image63] 下降很慢，因为它需要许多权重的协同旋转（特征学习）。  
  * **损失谷**：网络利用噪声达到 ![][image64]。梯度变小。  
  * **漂移**：然而，权重衰减 ![][image65] 惩罚“噪声”解，因为拟合噪声通常需要更大的权重范数（拟合 ![][image37] 个随机点需要高复杂度）。“信号”解在结构上更简单（低秩），因此具有更低的范数。  
  * **切换**：动力学沿着零训练损失流形缓慢漂向最小范数解。一旦权重漂移得足够接近信号流形，特征学习的正反馈循环启动（Rich动力学），“信号”模式呈指数增长，从而“Grok”任务。

这证实了Grokking是**熵可用性（记忆容易找到）与能量稳定性（泛化是低能态）之间竞争**的观点。

#### **Works cited**

1. arxiv.org, accessed February 12, 2026, [https://arxiv.org/html/2403.14917v1](https://arxiv.org/html/2403.14917v1)  
2. Neural tangent kernel \- Wikipedia, accessed February 12, 2026, [https://en.wikipedia.org/wiki/Neural\_tangent\_kernel](https://en.wikipedia.org/wiki/Neural_tangent_kernel)  
3. Finding Features in Neural Networks with the Empirical NTK \- LessWrong, accessed February 12, 2026, [https://www.lesswrong.com/posts/cpFqDDjhvhbaoyHnd/finding-features-in-neural-networks-with-the-empirical-ntk-1](https://www.lesswrong.com/posts/cpFqDDjhvhbaoyHnd/finding-features-in-neural-networks-with-the-empirical-ntk-1)  
4. Neural Tangent Kernel (NTK) Regime \- Emergent Mind, accessed February 12, 2026, [https://www.emergentmind.com/topics/neural-tangent-kernel-ntk-regime](https://www.emergentmind.com/topics/neural-tangent-kernel-ntk-regime)  
5. Publication: Grokking as the transition from lazy to rich training dynamics \- Harvard DASH, accessed February 12, 2026, [https://dash.harvard.edu/entities/publication/aab4355b-ca98-4cb4-89de-8fc886f766d1](https://dash.harvard.edu/entities/publication/aab4355b-ca98-4cb4-89de-8fc886f766d1)  
6. On infinitely wide neural networks that exhibit feature learning \- Microsoft Research, accessed February 12, 2026, [https://www.microsoft.com/en-us/research/blog/on-infinitely-wide-neural-networks-that-exhibit-feature-learning/](https://www.microsoft.com/en-us/research/blog/on-infinitely-wide-neural-networks-that-exhibit-feature-learning/)  
7. \[R\] Feature Learning in Infinite-Width Neural Networks (Talk at Physics ∩ ML) \- Reddit, accessed February 12, 2026, [https://www.reddit.com/r/MachineLearning/comments/kg83cn/r\_feature\_learning\_in\_infinitewidth\_neural/](https://www.reddit.com/r/MachineLearning/comments/kg83cn/r_feature_learning_in_infinitewidth_neural/)  
8. The Optimization Landscape of SGD Across the Feature Learning Strength \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2410.04642v3](https://arxiv.org/html/2410.04642v3)  
9. A Kernel Analysis of Feature Learning in Deep Neural Networks \- Allerton Conference, accessed February 12, 2026, [https://allerton.csl.illinois.edu/files/2022/12/2022-166-paper\_158.pdf](https://allerton.csl.illinois.edu/files/2022/12/2022-166-paper_158.pdf)  
10. \[PDF\] Grokking as the Transition from Lazy to Rich Training Dynamics | Semantic Scholar, accessed February 12, 2026, [https://www.semanticscholar.org/paper/Grokking-as-the-Transition-from-Lazy-to-Rich-Kumar-Bordelon/287839feb1e302fe513c2b03754ca44ad428634a](https://www.semanticscholar.org/paper/Grokking-as-the-Transition-from-Lazy-to-Rich-Kumar-Bordelon/287839feb1e302fe513c2b03754ca44ad428634a)  
11. \[D\] Is grokking "solved"? : r/MachineLearning \- Reddit, accessed February 12, 2026, [https://www.reddit.com/r/MachineLearning/comments/1defvmv/d\_is\_grokking\_solved/](https://www.reddit.com/r/MachineLearning/comments/1defvmv/d_is_grokking_solved/)  
12. Grokking as the transition from lazy to rich training dynamics \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2310.06110v3](https://arxiv.org/html/2310.06110v3)  
13. Grokking as the Transition from Lazy to Rich Training Dynamics \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2310.06110v1](https://arxiv.org/html/2310.06110v1)  
14. Grokking Explained: A Statistical Phenomenon \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2502.01774v1](https://arxiv.org/html/2502.01774v1)  
15. Towards Understanding Grokking: An Effective Theory of ... \- NeurIPS, accessed February 12, 2026, [https://papers.neurips.cc/paper\_files/paper/2022/file/dfc310e81992d2e4cedc09ac47eff13e-Paper-Conference.pdf](https://papers.neurips.cc/paper_files/paper/2022/file/dfc310e81992d2e4cedc09ac47eff13e-Paper-Conference.pdf)  
16. Grokking Phenomenon in Neural Networks \- Emergent Mind, accessed February 12, 2026, [https://www.emergentmind.com/topics/grokking-phenomenon](https://www.emergentmind.com/topics/grokking-phenomenon)  
17. GROKKING AS A FIRST ORDER PHASE TRANSITION IN TWO ..., accessed February 12, 2026, [https://proceedings.iclr.cc/paper\_files/paper/2024/file/682f87a8c306098ec8be29019bd76aa4-Paper-Conference.pdf](https://proceedings.iclr.cc/paper_files/paper/2024/file/682f87a8c306098ec8be29019bd76aa4-Paper-Conference.pdf)  
18. Grokking as a First Order Phase Transition in Two Layer Networks \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2310.03789v3](https://arxiv.org/html/2310.03789v3)  
19. Beyond Memorization: Exploring the Dynamics of Grokking in Sparse Neural Networks \- DSpace@MIT, accessed February 12, 2026, [https://dspace.mit.edu/bitstream/handle/1721.1/156751/fuangkawinsombut-taisf-meng-eecs-2024-thesis.pdf?sequence=1\&isAllowed=y](https://dspace.mit.edu/bitstream/handle/1721.1/156751/fuangkawinsombut-taisf-meng-eecs-2024-thesis.pdf?sequence=1&isAllowed=y)  
20. ICML Poster Emergence in non-neural models: grokking modular arithmetic via average gradient outer product, accessed February 12, 2026, [https://icml.cc/virtual/2025/poster/46553](https://icml.cc/virtual/2025/poster/46553)  
21. Paper page \- Grokking as the Transition from Lazy to Rich Training Dynamics, accessed February 12, 2026, [https://huggingface.co/papers/2310.06110](https://huggingface.co/papers/2310.06110)  
22. Mitigating the Curse of Detail: Scaling Arguments for Feature Learning and Sample Complexity \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2512.04165v2](https://arxiv.org/html/2512.04165v2)  
23. (PDF) Critical Phase Transition in a Large Language Model \- ResearchGate, accessed February 12, 2026, [https://www.researchgate.net/publication/381307122\_Critical\_Phase\_Transition\_in\_a\_Large\_Language\_Model](https://www.researchgate.net/publication/381307122_Critical_Phase_Transition_in_a_Large_Language_Model)  
24. On the descriptive power of Neural-Networks as constrained Tensor Networks with exponentially large bond dimension \- R Discovery, accessed February 12, 2026, [https://discovery.researcher.life/article/on-the-descriptive-power-of-neural-networks-as-constrained-tensor-networks-with-exponentially-large-bond-dimension/2427e4ed59143fcd8346c27c42307f80](https://discovery.researcher.life/article/on-the-descriptive-power-of-neural-networks-as-constrained-tensor-networks-with-exponentially-large-bond-dimension/2427e4ed59143fcd8346c27c42307f80)  
25. The Complexity Dynamics of Grokking \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2412.09810v2](https://arxiv.org/html/2412.09810v2)  
26. Journal of High School Science, 9(4), 2025 346 Investigating the impact of low to moderate level label noise on Neural Netwo, accessed February 12, 2026, [https://jhss.scholasticahq.com/article/154269.pdf](https://jhss.scholasticahq.com/article/154269.pdf)  
27. Phase transitions and structure formation in learning local rules, accessed February 12, 2026, [https://ml4physicalsciences.github.io/2022/files/NeurIPS\_ML4PS\_2022\_135.pdf](https://ml4physicalsciences.github.io/2022/files/NeurIPS_ML4PS_2022_135.pdf)  
28. Phase Transitions or Continuous Evolution? Methodological Sensitivity in Neural Network Training Dynamics \- OpenReview, accessed February 12, 2026, [https://openreview.net/pdf?id=MkZIew531l](https://openreview.net/pdf?id=MkZIew531l)  
29. NEAR: A Training-Free Pre- Estimator of Machine Learning Model Performance, accessed February 12, 2026, [https://www.research-collection.ethz.ch/bitstreams/2c0cc6e2-e048-4341-b5f7-567097130e9e/download](https://www.research-collection.ethz.ch/bitstreams/2c0cc6e2-e048-4341-b5f7-567097130e9e/download)  
30. (PDF) The Effective Rank: A Measure of Effective Dimensionality \- ResearchGate, accessed February 12, 2026, [https://www.researchgate.net/publication/37450697\_The\_Effective\_Rank\_A\_Measure\_of\_Effective\_Dimensionality](https://www.researchgate.net/publication/37450697_The_Effective_Rank_A_Measure_of_Effective_Dimensionality)  
31. Facets of Interpolation in Modern Machine Learning \- UC San Diego, accessed February 12, 2026, [https://escholarship.org/content/qt1hz6b714/qt1hz6b714.pdf](https://escholarship.org/content/qt1hz6b714/qt1hz6b714.pdf)  
32. Rarely categorical, always high-dimensional: how the neural code changes along the cortical hierarchy \- PMC, accessed February 12, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11601379/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11601379/)  
33. UCLA Electronic Theses and Dissertations \- eScholarship, accessed February 12, 2026, [https://escholarship.org/content/qt1qb8k234/qt1qb8k234.pdf](https://escholarship.org/content/qt1qb8k234/qt1qb8k234.pdf)  
34. Benign overfitting in leaky ReLU networks with moderate input dimension \- NeurIPS, accessed February 12, 2026, [https://proceedings.neurips.cc/paper\_files/paper/2024/file/4054556fcaa934b0bf76da52cf4f92cb-Paper-Conference.pdf](https://proceedings.neurips.cc/paper_files/paper/2024/file/4054556fcaa934b0bf76da52cf4f92cb-Paper-Conference.pdf)  
35. Towards Worst-Case Guarantees with Scale-Aware Interpretability \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2602.05184v1](https://arxiv.org/html/2602.05184v1)  
36. Mean Field Approaches to Learning Dynamics in Deep Networks | Blake Bordelon, Harvard University \- YouTube, accessed February 12, 2026, [https://www.youtube.com/watch?v=XZyFwz5\_vro](https://www.youtube.com/watch?v=XZyFwz5_vro)  
37. Feature Learning vs Lazy Regimes \- Emergent Mind, accessed February 12, 2026, [https://www.emergentmind.com/topics/feature-learning-vs-lazy-regimes](https://www.emergentmind.com/topics/feature-learning-vs-lazy-regimes)  
38. \[2508.11522\] Finite-Width Neural Tangent Kernels from Feynman Diagrams \- arXiv, accessed February 12, 2026, [https://arxiv.org/abs/2508.11522](https://arxiv.org/abs/2508.11522)  
39. Neural Tangent Kernel Analysis \- Emergent Mind, accessed February 12, 2026, [https://www.emergentmind.com/topics/neural-tangent-kernel-ntk-analysis](https://www.emergentmind.com/topics/neural-tangent-kernel-ntk-analysis)  
40. $\\mathbf{Li\_2}$: A Framework on Dynamics of Feature Emergence and Delayed Generalization | OpenReview, accessed February 12, 2026, [https://openreview.net/forum?id=ceIBRhJpUr](https://openreview.net/forum?id=ceIBRhJpUr)  
41. Muon Outperforms Adam in Tail-End Associative Memory Learning \- arXiv, accessed February 12, 2026, [https://arxiv.org/html/2509.26030v1](https://arxiv.org/html/2509.26030v1)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAZCAYAAAAFbs/PAAAAl0lEQVR4XmNgGAXDBqQC8RcgvgTEvGhyKEAaiP8DcTmUbwzlq0D53EA8E8pm4IBKVsMEoAAkBsIgsBOIWbBJIIPDDAhxuHwklNMDE0ACsxggcn+QBadDBRWQBaFgAgNEzg1Z0BEqyI4sCAVrGSByTOgSIEGQJDL4DMR5UDkTIDYEYg9kBY+gkiD8Fkl8EVTsCZLYKKAuAACuViTEl3OYcAAAAABJRU5ErkJggg==>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADUAAAAYCAYAAABa1LWYAAACMUlEQVR4Xu2XT0gWQRjGXyLFRAQPKaQHFYsgQQgkErxKHTx4CkQRFDx0CgIhKBEjwmtEB1E7hIciCMSLpxTBiwcvapBeEj0FKSX0D9TndWfd+R5n/4x+0Sf4g4fd/b2zszuz47erSOFQjIzmKQXDONLO8ixTgmywPOvcQ/pY/m9+sPDgEvKF5b+gnEUCj5E2lh50I8MsQTXyE/ll0ptbPmQW2ULWJFi+X+1iD7KK7Js8sYspaPvTsMKCeIcsSfx17iMfWCp1SJHZ9x3UAAsPmpBWlkQ4GN2+tAuGZaSCJeMzqCoWniywcGAPyvW0XO4YPoPSZXFSbkr6+Y3IhNn/K8G93Y3KRz4Vn0ElzdIjSX6ZvkGaWRLvkRqz3yLB9fai8iHP6diJnjjI0sEdZISlYUqCfuKexFVkkaUDnrRwCZZZrtTaj0VPGmLpgC8YcsVsdQa1zZhVU/S99JGciwvIZ3Ladzgw5ZVVS0RPcL03bGqRaZaE/rJpX7tIpeVvS7Yl8xDpZCnRoOrNNhPa8ClLQmdQv9fS0HcMT9Icctk6juM7C0OXBH3umG0mtOEzlkTWzm5I0PaTOdZ30ouonEjSNcKnNcOFOLRx0vLokGx/cyGTEvSpn0PzyLXcspPryDZLi7DPW1yw0RvVb6g/Es2CPn7XvwO/WaSgP9vany7Z2dySk28S3YOmP7d8RNKT9KIBecsyA68ljzeRb9aRiywzoJOxybJQKNjZPg0PWJxzzsk5AHzWh8wJrbgUAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADgAAAAYCAYAAACvKj4oAAACX0lEQVR4Xu2Xz4tOURjHHz+SXwuxUZrNyEaWQlL8AbKY0pQpG0pKIcWGMSuxsaDs2FGaWJCSbFhYiWRqLGTGr2RBKVE0zPN1znGf9/s+5577Du8spvdT395zvs9zft177r3nFenRY87zSLWJzVlkveoFm02ZUD1X/eRA5LjqJptdYpfqt+q+aopil1Q3yCtyQUKH++KvR87/35yS1rHemnKi47mgwW02DedUy9nsEjz5a6rD5M1XPSUvyxoJnQ5wwMCDdovHqjvkjauukgcaz4m3BLNK6uNgMdWXUL0pGGeR410kD8DvZ9OSJs7Cgi11FwALQey86puEbf5LdVL1XbW2Sv3bfw7sIC8ObzObEvzrbHqUBh6TfByLSaTFLlMdimUsPFEa57NUOSwP+BNseiDxGZuGr5IfxN6h7VLlDcbyvCr858WwwNQZbzFXHC/xQ/KxFpC0jU0D4uisBLZkowEzoO1dx8v1OSn5WAulpDdSzgHIec9mB6D9AVPfGr3cyQmPR3Fe2DalpHuSz0EMrJT2Cb4y5SagvX2ZoP7S1BnE37HJDEn7UYjBR9Zb4G6p/FuxjDczWKH6EMsJxL1+Eojtj+X0DNeB+DCbzEPVZTYdvME2qPaqDqqeSLhjOF3A8y5aWmDuG7lRQvx0/F3YGm7DXtAsSFrNpoO3QLBDtcXU+1TrTJ05JuHu5sBWr2tvyc1JPkoVzCYRS8U/LnVK0/FKnJWaszEGwV+io6ovFKvjXye3UzXC5gypncuohIRJ8kvgGfnEZgc8YGOGvJYwl66wR3WGzVnkhOoImz3mCtNwAqU93YemoQAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAYCAYAAAAcYhYyAAAA9klEQVR4Xu2SwQoBURSGfwsl2ZBsbKwlsWRn4wm8gKwpS2+AspWyk+xlaclSydZaeQZJnDN3ZjpzZib3Aearv+b/zzl35p4GSLChSPqSnqSDqllRgTkg7Xp+zvpVC8owQxmRsT8L/xceYOnspbJY2jADA5V7u7HijvBXNN1sofJYvKtEqS76YinBNN9UHrWjMcJXdhjBNNdUztlUeQ9edl54TBB+IyOzhvJ70lZ4tBA+5ErqCj9DsGdNeguPFIINBeWZjcqWyjscSSdSD6ZYDZYxd3OPlfI+/F90dOjSR3BoR3oIb4085EPKCW8ND/FCL6ShqiUofluuQOK2b74YAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,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>

[image6]: <data:image/png;base64,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>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACUAAAAYCAYAAAB9ejRwAAABc0lEQVR4Xu2VPS8FQRSGjyDRiUQ0ClErVH4DURGJVqLU6UQkciNCotLyD3Qkav4AvWjER6MivhU4x8xm5z5m5+4mF80+yZudec98nJ2dmRWpqZFHGr9BL40Ey6oJmsqM6kX16jXaHP7mTnWtOlddqS6bw44R1b1qlYEEnzTAnrg2lliMB3HxMQaGVd2+bA2qJLVEA9h4/f45i5jxQSNGlaQGaETIPomNG1vVmPeDKkmd0gALqjlfzpKyVQs5QT1KlaRaveVtULbPbO25mSdRj1I2qXHVFk3ApPkJ+4JyEuvUoBnhmQboEHfUQ47Fjb/r69t5KI11WqMJhlSHNMGBapCm5KvV6Z+lsIbrNMGZqocmKJpwR1zsSNzlWgrrsEETFE0YkmqTrdYKA0VY402aAVPSes/Nq/ZpBlyImye7sKNMq25U75K/hV3/PL7GG40A2ydPko9hiv3z7NSlVrIypffBX2FHvIvmf9PWJW8XizRqasAXbHZbLOiZBp0AAAAASUVORK5CYII=>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAXCAYAAAA/ZK6/AAAAnUlEQVR4XmNgGAWDERQC8UM0MS4gbkMTg4P/QPwTTewjVBwrAEm0YxE7hSYGBuEMEEkeJDEOqFgAkhgcgCTQrT6ERQwOQBJnsIjBNGgiS8hAJWYgiTFDxZZA+Sg23YEKgLApELszQDwP4h8A4s0MEEPhACTxC4i5gTgRiJWR5FyAWBKJDwYgDTgjBx1EMkA0gEwnCvwA4n/ogkMIAAA6BSYK975OnwAAAABJRU5ErkJggg==>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACgAAAAYCAYAAACIhL/AAAABsElEQVR4Xu2WPS+EQRSFL4mEBCFClKsREgqFRkkoSMQPIBQKtcQPEBqFho5CT6H2F9REIqHwEaLQiAji457MTPbd4867sxvb7ZOc7L7nnDsz+5F9V6ROnYr5ZCOBF1U3m+U4Uv2oHlVn/vlWSeMvq6oGNjMMspEB6yeD8iZ5Xd6/Ij/QL/FNBlTPEs/BqGqKTeZY8hdpEZefcyDOb2dTGfKPyPPWBsgb2QzMiSucckBYGy0bHmPNMcgP2AykLACsHq5jH33AmmNOJNLZERc8cWBgbYTrFfIYa46ZlEgnDC+Rz8yIvRGux8hjrDmmVyKdlGFwIa53TT48LJ5H6h7otFpmueEOsXvN3sv7/QPWrAU6w5ZZbvhDXGecA3F+gU0iZQ+8SHTaOMDtCUEPBxmQ77LpQTbBJpFywIJEOk3iggcOxL2qb9U6Bxkwu8EmkXLARcnp4DaD8N5f49B73tsOpQh3qlc2PTeqdykeELotaRTBHSp6wMCC6lK1r5qmLMa8JCycANaYZfO/wDt/yGaF4G9XzQjf42pZE/eTVVNGVH1sJtCpemOzVlSz0Rcbdf6LX9GYf8HoFD1XAAAAAElFTkSuQmCC>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAYCAYAAAAlBadpAAAAsklEQVR4XmNgGAUg8B6IvwHxDyj+CsQfgfg5EG8CYnGEUuzgPxQrIIlJAPE9qPgiJHEMANOMDcDkDNAlYAAkuRNdEApgmpXQJWAAJGmOLsgA8QY+VzG4MuCW/MUAkRNGl4CB4wwQBSxAzATEnECsBRX7DsSMCKWYAKToBRCvAeLVQLwMiOeiqMABBBkgmvnQJYgBUxhw+5cgwBuShADJmt2A+DUDQiMIPwViOWRFo2BIAwAwdS8e+04QmQAAAABJRU5ErkJggg==>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACIAAAAYCAYAAACfpi8JAAABRElEQVR4Xu2VzypFURTGF10DAxkwEKNroChMDLyGgUcQZWDqLZSJMpEBk2vgBTyEJ1AikhL30i2Kb7X36ez7da21T+GU7q9+k2+ts846p/NHZMA/55iDn2KZA4cGB5E2fIPd6Ct8gnfwHE6Wrb0swQ785ILBHgfEh4R5i0k2Ba9ivp/kMivlVWmxyiJerzWvqM1wQbEOZDbgJocJTQmzLrkQKc41zgWlyiJe35GEnjUugDlxzmUWiUcOCGvWu4TaGBcKrINTDuAqh0QxawQOw1G4EzN9m0xyF8nteYFnsAVP4W5Ph0HOItsSHlQPnTPPYS45i3h1ZUvy+r7FW2QIPnDYB+2x5rh4ixzCFQ77oDNOOPRYh7dSvlLqM7xOmyLWkvrpvpdyhqr/lZzFKzEBLzisA+tu/Ck3HNTFAgd1MM3BgN/kCzRtWvC/AL08AAAAAElFTkSuQmCC>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHwAAAAYCAYAAAA4e5nyAAAD1UlEQVR4Xu2ZaahOQRjHH7tCFCEiWT9ZkhL5cMuaomQrikuSUJLyUVlK+CARWVKk7CTxQXJv1kgoIooQUrLvS3j+Zua+z33uvGeZe9/ee73nV/965z/nmTPLOTNz5iXKyMjIyMhoMPzSxn/ObtZibdZXlrD+WE1TeSE8ZQ3WZhFwbYLS8pb1mfXN6ivrPesV6xFrXu7SKj6whmqzvnKFwjpGs4t1S5tFohGZmSa0XYPIxL5T/krr+8r1eQWjNjfL14A0dKDal1HXHKLwOt0gEztQZzATyeR1Uv4c1gTlFYzQhgHEbtdmSp6xrmuzyByk8H6Jegl2kMlrrTMof0ydU5sbyae1rcxIAcqYrk1Be/G7lfjtaKcND2nfnkINeFxeJJVkNgSnWBWsn6xF8oKExN4oAsTeJFOXrTadhubkj1lOuc6BsOnZybpt02Wss6yTrKPW8+0BTrO+sIaxjrF+sJpWuyK3pDxk7Sezfp+xXlrwYCEOS4KmjPLXEyCvjzYd38lU3uHWjXHCS0pIw8BMMrHdhPeJ1UOk45hK0fd3Ay7BAMLrLLxN1pPc8XirldfCprcID6BvdWwS3DgMYDUm80Dj90Xrz81dWgPko09rcI5Mppze9lgvhNC4B6xtyntJZp1KinuT8+Eb8Gsez22GHF1tGgOsgX/B/sasqMsCV8nvx+Hqe8QKSwO+QHrJi/LgrW8Xm4HvOwm8uEMLbBTwJGshVnvQMhOWF1+HwNuozQg2kL8ch+tAyXmPN0Z5mMqRHi48hyzTVz4IGfCOZGLw/R0CYvdpc73NWKF8eOuUl5S0DXPouGbWS7N5w0GELkfiG5AKjzdSeXtterLwHLJMX/kgZMDdDlyPTVIQu0abMJCBtcExy3quo5+IvCSkbRhoSTXjMHVpL44RFB3jG5BKjzdKeUNs2vcSwL8nfuuyQMiAu7Lw4IeA2HJt9iWT0V14stI4l/VNY1GkbZhDxjWx6RPCSwI2NoiTD7DENyBYf7U31uNhY/tbeW5zh/oCtxRMqbrC4LtvHCExEsTqL4h/3CVzWIHd8SXKPd04h9YNTEJoJQ+wVrFGkykj9AAGsXq/sIDMWug6Ee0Fb4SHTzXwXHjY28y3PnhN5qwaXy/H7TVYayWbrb+QtZRMH963XpK+weZV1vUjpZ9lQeS92lD1g3h8XswQ6TRE3igGTMmTtJmSx2R294UCs0g5q6fyNXjbsSkGOAgaz+qXyy44l7VRKPprowjgoeutzRICZwslxWwyfyuWIjgaDlmKGzyHWWu1WQLUZklt8GATWkq8IHMqmJGRUXL8BUFoNP6u1vHmAAAAAElFTkSuQmCC>

[image13]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGgAAAAYCAYAAAAWPrhgAAACi0lEQVR4Xu2YuYsVQRDGS1kQdRVPEBTEA0E8AiNRPEDMVkQDRSONBBMDDfYPEEFB2MDEI1OMBAMDwV0QNDUwWFERVHSDBRWDZT3xqG+r26lXr3sOcXue0D/4eNNVXTPfTE/P9BuiTCaTyWR6h+c1NdMXJGYBdXuJaa+rScG9GrrDusk66moAzucn65fTJxd/xprlO2nmUtF5M2s+azZrMWs/FTtrk3msayQ+Vrg2POJkt7FeuNwWXzDN7CE53mnWDpLjYiAQ28laz9rOuupiJ6SMDrr2StcGq1ys9BpXdSjLpQIeJmxQkdJj6Fixa/jZ/Q5QOA8esB7aoAaFt2xQEdtxSuDhjImtU9upPPaxntggxQfIx76qbct1kpkXZAZJ4QYTx3T0PFbbbbCJxKN9D+oT/qC2p5PzJI9WzVYSL29NHHiPfgCPq5zHXvsOTlH3yO4y7ba5Td0ez7JGTawtRkj8HTNxzV0qBglC295wQT6SFLwkuQO+u3YTflDnwav0eqqqPrbeS8/yNvF+qghdp3MdPQKgE+5QPFuxgtvnYr1E6ALYdpuE/MXoZw1R51I7in92WlDcKwySeLxh4l/U9iOSpXcZlxqoCZgB8HfZJhR4h4a4QFLrl+FdDFN4gJqykLW0gTBT6zJJ4nGtTSj+xTn8Lf6VsMwmFDF/+A+HHP7bBamcYjXByuZiA52UslpUeRxjHbDBhFT5A7G8X1xEqbPzNplD5R7XUDyXgiVU7g8cpnge8dU2eIj1noodQ+9Yr3SnHsCvLrVHzJZx1jcVv+ILEvKGxIf2h29qof9BT1n3SfocYS1ibST5KrK76JZpC/8JB98O8SrAR1G8+5f/6ZHJZDKZTCaT+c/5DQy74HcHY0npAAAAAElFTkSuQmCC>

[image14]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAYCAYAAAAlBadpAAAAq0lEQVR4XmNgGAUgcJNIPAWmARlwAfF/KDYHYj4g5gRiUSA2BOKtULk+mAZ0ANOMC5xjgBiEFYA0HkQTU0Bin0diYwCQZjs0sdVI7IdIbBSQzoDpZGsg1kQTwwpeMCD8jIyJAiCFm7GIEQSgEAQpZEQTR9ZcDMTRSHw4gMUhPoBTnpD/ZgPxKnRBGMCnuZUBi1woEL+BSsAwKMQfA/FzIP6GJP4SqmcUDC0AAClnOAMEEf35AAAAAElFTkSuQmCC>

[image15]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA0AAAAYCAYAAAAh8HdUAAAAz0lEQVR4XmNgGDmACYg/AfFPIP4PxH+h4meBmBemCBnIMUAUOiCJiUDFQBgDsDFAJATQJYBgORBfQhcEgbkMOEwDgg4gDkAXBIFjDBBNi9ElgEAZXQAGohgQbgfhJgaIkwmCRwyoGkF4BYoKHIAZiOsYUDXyoKiAAmd0ASiIY4BoakSXAIFn6AJQAAp+kCZTdIl0IP6MLggF/Qw4ouEpA0QClHyQAchvIHFbNHEwAElUQukyIJYGYkkoPxFJHQoAeRYGaoD4DBCfRBIbBVQDAFVLLfdCoH8hAAAAAElFTkSuQmCC>

[image16]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAZCAYAAADjRwSLAAAAbElEQVR4XmNgGAVUB3FA/BOIM6D8OiD+D8RLYQqYgfgylAZJPANiRyDWgPJ5QYo2AjEHEMtABbtAglA2CIPBHCjdiywIBSDNKACkAOQuvACkqBVdEBlYMyA5EhfYxIDpHgzwCoivoQuOAjgAAG+8FtX3+SXDAAAAAElFTkSuQmCC>

[image17]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC8AAAAYCAYAAABqWKS5AAABoElEQVR4Xu2UPShGYRTHj6TIIAkZSErJx2LXuyiykI+ElDIxG8wmg4XdYjEZlGwGH4t8heRjUko+ophIPv7nfc7Te+7hna5yy/OrX53/eZ5733Pvfe8lCgQCgUAg4czDFfgKN1S/AX6qzLXOf04lucGZN4oOt2Ny4oa/UTUPtm+yHrbc5DiU2UYclig6WLHkftXjv9GsynFotY042Ls8YzKzBvNNLxHwoKsq30pPo3MdPJD6Au7BzcxyGn5693ALdkuvFF7CXcmeZnLv3KPpp6T/YvoReLAHlT+k5xmCXSrzULkUPUbv52H46+Xxa3yczh6fh2Ge1AtwXepCOCj1N6bInaATHsM+yYuwFp5ktqYpghOmpwfiuspkfmcK4DS5J6Xh9UPYIjlHem1wFG5LPyt8xT3kDvTUwzGVNc+q7iD3eJkmyn5nfV2iMjNO7nx+H99Ee45fxQ7En9LlH9bayV0Qw3+/O7XWSNG9/tPNT0j3U3BE5Vjwi3em8hy5F7daci+5H7+Gk9LzvMMjlc/hKbyCNao/QG7vE6xQ/UDgX/IFz+VoX+dFtx8AAAAASUVORK5CYII=>

[image18]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAABGCAYAAABxPchcAAAEoUlEQVR4Xu3dW6hnUxwH8OWSkUgGIWYSCeOFF/Fg8iD3JkKhNEXKpYZIklu8uOWB3ApzcimlvPAil1IkDwYjl5GHQWMkuSWRy7B+7bWdddbsM3M08/+f/8x8PvVrr/Xd//P//8/br7X3f6+UAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA2BGszPVPKQAAJpSGDQBgwkWztroNAQCYDJelrmHbrz0BAMD8eS51TdpDudaVce/UMn+vzGPlLear/nsFAAAjszB1zdfZZf5WmdcN2+/l2OcLcl1RxgAAjFg0XesHsofL+Lpcy6p8UTXWsAEAjNg5aeOma2ogCxel4RwAgBF6M23chM22crYmDecAAIxQNGCvDWSflvGZTb6hmgMAMAZf5VrRZNGYXVjGdYMW+QPVHACAMYlG7Jhcj+X6sszvTV0zt3N5zd0lBwBgnlySZj4k94Jce1TzvXKdVM0BAAAAAAAAAAAAAAAm1sG5FjfZ0lyHNBkAAHN0wv+o48vfbMozub7P9V2ufXOtSt0G9n/l+rF6HQAA8+DFcvwmdc+Hq3dkuLlkm3NbG2xlf6a5fQ8AgFn1e4ZujZpK43VDOfafX/tsIBsyl9dsiQVp9J8BADDxoiF6dCCbhEYpVvDWtiEAwKSKXRPaVbnN1ebEfqfxuoOaPLLYZqu3W66rc+1SZUdV41rcP3dWk11VjktyXVqfqFzeBtlvuZa3IQDAjmSosYvVtjq7I9e1ZdznX5RjNFS1t6tx3H8Wrsx1a67bq3P1+7+e684yjn1Yn63Otd9tNu+k6fcYcn2uD9uwcmjqfmSxT5MDAMy7aIhWD2R1o/R0mb9aZfun7lel9Q8VXk4zV+Duq8a/VOMj0/T7x8pd/VkxPqKM4/Eic23Y2u/c6s+f3OS9P1J3/uP2BADAfIsmpb20OdS4PJ5rQ657qiweAVKrG6Zlufau5vW5WIV7pIzjsSJtw9aLlbcnqvmmvJC6VbzZXJNmNpytw3Kty7WwPQEAbP/6lZ1Nrf5Mklg5i+96XplP5fpp+nS6sRr3/9PFzTx8Uo13TRs3ZTul7hLpS7meKvlx5VyIX7DGeFGuN0oGADAy0ZC832Q/p8ls4j5IM7/Xnqm7F+2jXK9Uefg6101N9muu89PM93gw14pqHs3ct9X889Q9RiSauPi7/hLtXan73APKHABgZKIJOXcgixvsJ018r9jlYEv0q3QAANuMoeYlstkebzGf4t619p62uYiVubVlHKts7WM9AAAmzhnleHiavWHbnsR9aitLxS8/AQAmVlxO7O/1Oj11jVnfnMUjL3ZP0w+rjXEUAABjEs1au3JWN2y9d3M92WQAAIzYaalrzG5p8sj6Z47V2eImAwBgxPqVtPr+reUlax9L0a64AQAwBkOXPuvsxHK8v8rCsdUYAIARiibsh4FsTRn3Wyz9XfJebPcEAMAYPJ9mNmL96tpU6n4d2m+K3m8yHtbnOrCMAQAYk1NyLa3mcSn06GoeYrunJU0GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwLbjX3ZPFHjxU+yhAAAAAElFTkSuQmCC>

[image19]: <data:image/png;base64,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>

[image20]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAYCAYAAAAs7gcTAAAAhUlEQVR4XmNgGPrgCxD/B+J16BK4wFIGiAaiAUhxIbogLrCJgQTTORggihnRJXABkOK56IK4AEgx0U6BKRZFl0AGIEmYiXhNl2eASDpC+bBIwvCoNlSiCknMGSo2E0mMwQQquA1ZEAownALiPEAWQALHGSDyUjCBNIQcVlAMxIHogiMbAACjSyDQo4lHOQAAAABJRU5ErkJggg==>

[image21]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC4AAAAXCAYAAAB0zH1SAAABn0lEQVR4Xu2VvytGURjHH79lsDBgpCz8A1J+pJTBarFYbMrPpCyUUhaDmWx+jMRgIKWUwUCRyMAqYSLC87zPc1/nfO99vSbvpfupb+85n/Oczn3PvedeooSEhFyRzznhfHDOOXn+cDwpIb3gbus3WL8sXRFTHjnP4C457+Bih+zuCrgR898yTFp0w6mEMaSAtPaas2Bt2a1St8gh2+J9pDWT4DvNz4BPs8lpt3YdZX+27ij855pI522Qf6j2OENOP4o50rmj4FvNr4FPsUvhHZH+BTgXOfGZkEVkfpADfziSRdLaQfDN5o/BU68NFIMX9wYuE40oIihHAQyQrjkGvs38sq+JXim8213m1sEj++Tv7Kw/7IFrIB2kNdPg5dUofgJ8St6CuzJfBN5lizPl9As5R6Tzah0vtHCWwEUhc1fByTMvvsKVcrhE9rvS3CE45AWFUUVfd0Au9snaP0Hq7sHtmPc4M/lA+qwHr7Vqt+iXkfW3rT1v/dBnP9gZQQ5YvTOWS8Y5p/YbSXA7/xQ9pBdegwNxRz7PoYc+IeGf8AmEFmsn0AKq+gAAAABJRU5ErkJggg==>

[image22]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC4AAAAXCAYAAAB0zH1SAAABX0lEQVR4Xu2VTysGURTGj/xJFlYWyIqykr2NspJEVjbW9nwDOx/A3p4l2ZJSygcgJQvKSpIVIc7Tubc584y3mbFgpu6vnrr3Oee8c+7cufcVSSQS/82Yap7NprKtulV9BbWm8WlVVxi3qnFPrcY3xQruVEMUY7rFcrG1O2H8qur3SQ7E61C58UPVXBhPiBUOZOECj1Jc3IxY3YFkWw5OVBtuXoVKjR9L8Y1gfk2e54oNx55kBww6y4crgboFNj1rYkl95MP7IK8TU2z8wCAbJeD5i2x63qX4trFSePvkM6eSf7O4zjrBzygD+UtsepBwT95N8HvJ9xyptty8R3UhVjfufDCr2iWvDPzOMpsRHC4krJMP75w85o2NwLBkO4BmX8K4LqhZYTNyKZbwLPatx2ttxCf9IfjUHlSfki3+Sex6zhGDAAds0sUaTdzOVrEq1vgoB5oO/p5/c2gSiTbwDSd6Vm/VrZ5FAAAAAElFTkSuQmCC>

[image23]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEwAAAAYCAYAAABQiBvKAAABwklEQVR4Xu2WzytFQRTHj4WsrLCg5EcpC6XEHyALaxZ+bVnYScnaAgulKCtKKWtZKBvZKDbWTykbP0qWNvIjnNOZybnHve7cee57eeZT396d75lv82bevJkLEAgEAoHf4hX1YbSlaoEEloEXrE0XKhmasC92h/0ripkwZa+0Wen4LlgTcHbCtOtErZzUasNyjHpEHaBOUC+ouUgPN3wXjA56yu4B77Il0y4Xh8Djb5rnN1l8Br6lLGfAnYeE54rvJO35NSi8fdSkaGtm4CvnKhdmIXo0FEBkj0xDbj37a/tQTO5SeTuoa+XlTTt8n8M96pYeGoGLtMMk5L0rTzOP2ogRZbVHWudYIpSjc0x7F8rLmx934gpwcUH55K0pz5XEwVKIy5E3rE1FQ0alQWM+aNOyCNyhRnhjxqs37cRwAnETd0HnRmI8TSdqNaPSoDG3tWnpAO7QKjy5JenAHRA1F9ImmYTOUftGeaWAxr3TJohbkm4A6tAM/DrRDxzqNZ9Z8ckQlNtF9QGfn6fRcsnoAf4uLahu1DnqCVUtO9ENOSXa9Be1L5BZ8V0wogs1jqrShTIwjRrVZh7QpAOBQCAQ+Nt8At0Zg3mb8yAAAAAAAElFTkSuQmCC>

[image24]: <data:image/png;base64,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>

[image25]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADgAAAAYCAYAAACvKj4oAAACaUlEQVR4Xu2XP0hXURTHT0VEUVAQJQ1G5NDU1FAUTkFCro2NQpNDi1uK0RBBS2tUBFFDS4GtumhqaaRODYEagvhnSayh0PPl3uc7v6/n3ac/H4rw+8DB3+9zzr3vnvd7776nSIMG+4Y1FhVS1dwTGtdYGgZZWFKLWNRY1fgbA59/a8xrjGu05qWbuKFxkmUEc/yR2nmXNeY0XmqcyUs3wDpPs4wMsbCkGgTvJdQ8Ne6gxofocRKYo1I+7yEJNbYOJ+RTdD+NB8ei9/jMwlI0KIMXYcGlgdxr8nD4BVM8kVB3nxPKW/GP+ULjHEtlhIXFm8iSajDLPTPuUnRl/JNQh6uBWRF/DtT+YKmMsrB4E1mQx+Xo4TU/6TgPb2xGWY75wsLiDbAgf5ml5PdKB3m4N+SYExLqsFkx2ICQu8CJiLferyws3oCM2xLyRyRcHvh7VsLGAt+cl24A38WSyO6/WY1+jWGN/9H1mjoP1JwnN0bfa0g1iEcB8thJEe80XknYJYtA/R2WRNaM5WN0V8gzqLlFDusshA9kQe4RyxIw5jpLAjXecYu8Bfl75L7R9xqKJmySkEv9Wh4Yc5clgRrvPt1qg23k6mrwuRTnUmBMN0sCNRfJ3Yy+7JjIt5Crq8GtHMwDYwZYGrDrevM+lM3HfGA+Z3hjt9XgL8k3AQR2zMc1FWmK3kK+S/4AR+D9c8bkj5sc6DQ5izf3thrcKXh01Dsn3jd7NKbEv4/xruqd7F1tEODNZ5plBRStddcbBFXPe1VjiWVkTxo8pdHOsk4OSHqdyQYXWFQINiwsbqfgP4/DLA19LBrsd9YBK/S7/u1XGXsAAAAASUVORK5CYII=>

[image26]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAG4AAAAYCAYAAAAbIMgnAAACb0lEQVR4Xu2XO2gVQRSGj1GMUTEWCgY0hQ8sEhBEW3stRVAUIWAEG1sRS7XQQgkSBRtFwSdoI9hoo4FgZWdjTEghYiWCFiq+zu+cTc6eu/fuzOzem4fzwc9l/tkzszv/PuYSJRKJRCKR6AQ/WH9EN0zf/84Wml0baN5xntyJbbMdCVpGbQ6uysC/qVr9fAJvjS5rVmAtubU5bjvqosrCo3bamguU21RvcCNUbW1LiR18A7nao9Jep/rmkm5reHKH6g2u6dvoOesL6wlrnPWNdSZ3hB+Fg3twnVztI9YUue/dtD6gw1wmdz73WQ9Yj/PdpdxjLbFmAC/I5YG5J8idy/vcEcx31k/VHiN34EHl+RIbHOqgvcY7odqWnTRb56NPrqwULBh2uRlXKPy6qgT3lfJ5vCY3/zHl0TMx1yjvmngxVKl7V+B9NF67yXZvS5X3kHVBtX2IDe4WNeYxKt4MfWLouwtkd2grTpEb0Ap11oNw17YCdRsLvEnjtRvMiaB8GaDGa4Xesq4W+FAzeskzj4tinNWmeHjqYigLvBlFdfDKXtfrA4QtdRmYc9CaEcQ8cSepeR43tXFOzBXKOyAenkbwWfX5UBSAD7Zuf4Fn6WFdCtBpV9aSsjl9iQmuKI9D4vVL+18eW8XcLCZAOzt5bM33qT4fYi/c1qGNvwidBvNutyblNws+xAQXlMcb1gfWJtZL1h5yB+6W31BiagDq7rJ2sX6xXuW7O0b2ndlBbiGfSjuUmOBAlgfCK81jNWtYtZezjqh2CA2DB4Bvy2GKu+A6WcUaEsUSGxyoMw9v6viwLwZWWiORSCQSiURiUfIXApW5/TfU6iEAAAAASUVORK5CYII=>

[image27]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB8AAAAYCAYAAAACqyaBAAABY0lEQVR4Xu2UPUoEQRSEWwW9gIE/yYJgYGYoegIDL2DiDYw8gIHBnkAwUBPBQMRAzMwE/xXvYCDoJiIiimgV3c/pLaZ7doLBQD8omFf1Zmq3Gca5f36ZLzUa4FQNI1f+BL1Cb0G8foY60BU0W6xmOVPDyJWTA+d32uIfBv9B/DLO1TCqypmndm6cz9Y1EC7UMFIPNnLllumpKJdqGKkHG8z31AzkflgM349Sqm5mPqUmOHY+W9SghGs1jFz5gvP5INQPDUEj0Ebwx4vVLHw3SsmV37ni2KldaBuaj3bIALQMtcQ3btUwcuXMVtUUlqCdcD0MvRTRD/wTpaTKx5zPeNQ5uDMns1K7fNOlsxjuTMrME4ipXU4/lcVwpyXzTDSTnsvvoc/gU/y+r3VtdMOdCZnjkyA9l9eF90/L3BfNpLHyFWg/XI9C71FmNFZOTqAt6MP5j5HSaHkVyfJHNRrgSI2/yTeb+2Q/RTjWUAAAAABJRU5ErkJggg==>

[image28]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAAAXCAYAAAAcP/9qAAABGUlEQVR4XmNgGAWjgHKgBMQa6IK0BCxA/B+INwJxIpSdhKKCRgBkkT8WsR40MaqCLgaIJegAJIYhDnIJTOIvEEugSqOA3+gCaOAXAxYLGLBYvB+IVyHx4xggCs4jicGAIhCvRxdEAxgWQMFPBjTxp8gcJNDBAFF4BYg9gHgblE8I4LL4CwNEnB0mEIiQwwrmMEA0rECXwAEIWSyMLMiDJFGFLIEFvEUXQAO4LAalHRTxMKgAKG4VgPgjlG+OpAYZnEYXQANPGLBbjOGgf8gcKOBmgKROUCjAHCDLANEoAFOEA7gyQNRxoomDxH4gC+AL2igGhEtB2ApVGicAqZ2BxIeVZKDQpSlwZ4BYZArlg0LuHkJ6FIyC4QYAFcJMxnq6OgcAAAAASUVORK5CYII=>

[image29]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAAAXCAYAAAAcP/9qAAAA40lEQVR4XmNgGAWjgDrAFl2A1oAXiBcC8X90CVoCKSitwkBni2GAoMU9DBAFIPwXiCVQpVHAb3QBPACvxfuBeBUSP44Bovg8khgMKALxenRBPACvxU/RBaCggwGi6QoQewDxNiifFIDX4kB0ATQwhwGieQW6BBEAr8UgwAPEXxggiqrQ5NDBW3QBPACvxWEMEElQ3CoA8Uco3xxJDTI4jS6AB+C1+B+6ABBwA/EvBkgowBwgywAxRACmiAiA12J8QRvFANEIw1ao0gQBXotpAR4D8WsGVEc/AeI1yIpGwSgYPgAA5TY1Hvw9DxAAAAAASUVORK5CYII=>

[image30]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABQAAAAXCAYAAAALHW+jAAAA0ElEQVR4XmNgGAWjYHACDSBeDMTL0LAJsiJiACsQ/8eDcxBKiQMgTXeR+KuhYuiAG4itgTgaXQIZPGXA1MwGFZNEE5cG4ptAvB1NHA6iGCAa5dHE86Hi7GjiIAASZ0EXhIHlDJiuA4F/DNjFGRlQxc2Q2GBQzICpEeQtkJgtmjgIFADxJyjbEogfIKQQ4D4UKzBANDxGkUUFIItAYY7TyzAgCMTpQKyLLoEGQAaCIuw7ugQ5wIgBETzuQMzJAHEE2WANEK+Csnmg9D0oPQqoBAClzC3Fh0TImgAAAABJRU5ErkJggg==>

[image31]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFIAAAAcCAYAAADyfuiHAAABS0lEQVR4Xu3YTytEYRQG8CMLLCU2ko2SJImysCI7Sys+wSgbK0s2fAHlG1gJO3uRb8EeKSnlz4LndM5tzpyYmZvV7T6/epp7zvveqfs29847I0JERERE9D8TqZ5GelKPOnhHdpBvZMDrTeQTOQ/zqI05ZM+PdSE1hSGvh0OvrEVpvm83ebbTqufAX1fELmQmjE1578jr4mK1T3+4Eluk6Nh7S6GX51BSfNra9eZT3a3xEhnxcypLF+j0l959qC+Ri1DrF1Mn/chhiTTstGpaFVu0k9C7816k9SyygKx5TcGt2KJ8IRtiz8uPlhlG56wjo17rFokCXaCH3Ex2xeYU25m+1mEaFFuY7TyQvCJbfqzzl5GX5jCdiS1Mbx5I4vPwRuz2ngy92ntEnpA35DqNRXpLR7oVIiIiIqoZ/dNC95NjHv0jWO1LzX6H/wDpeFH/VwGdIwAAAABJRU5ErkJggg==>

[image32]: <data:image/png;base64,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>

[image33]: <data:image/png;base64,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>

[image34]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAYCAYAAAAlBadpAAAAsElEQVR4XmNgGAXIoBmI/6PhIKjcXCBOgLIxAEyxEJr4LSA+CJXDABsYIBKM6BJIAGYwCvCDCn5El0AD/4B4HrogzERWdAk08BuIpZAFKhkgGn8gC+IA6OEAtzUBTZwoANPMjC5BDMAagljAS3QBECBW81N0ARA4wwDRrIMugQS+MeDwFihR4LNdnwG/wQzCDAgDQhkgtiQA8XMgnoJQhh+AUtoJIN4HxOlocqNgwAAA6iYtjWdMzl0AAAAASUVORK5CYII=>

[image35]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAYCAYAAAAcYhYyAAAAv0lEQVR4XmNgGAWEwDcg/g/Eq9AlSAWrGSAGUQxAhmSgC5IKdjBQwTXcDFQwBARAhkxGFyQVgAyh2DUwQ/jQJYCAEYht0QWRgTgDwgUg+h+SHAxIADEruiAMKDJANNpA+T+gfKKBLgNEQymSmA9UrBdJ7BMQf0biw4EpA0TxJnQJBtQAvo4khgFAgvfQBaHgEgNEXhCI1YBYBMrHAKnoAmigGIi9oezzQNyMJEcWgLniCIooieAFEL9BFxwFqAAAWNQq6+Qx6XUAAAAASUVORK5CYII=>

[image36]: <data:image/png;base64,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>

[image37]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAYCAYAAAD3Va0xAAAA2klEQVR4XmNgGAWkAlYg/gbEP4D4OxCXokqDwRcgfgrEt4H4ERC/QJVGBZ5A/B+K0QEnA8QQkJwNmhwG+AXEGxkgipeiyYHAPSDmQBfEBkAGMEJpbK7CJoYBuID4AJT9kQGiKRQuCwGgcCQIWoHYAcpWY8B0VRgQ1yDxcQJQ+CADmEECUP51BkjsEgTo/i+Eit2B8tHlsQJ3IG5CF2RAuEoViHegyWEFJxkggY0OAhkgBn0AYnM0OawAn7PRAx0nEGLAr3AeA355hhQGhG0wDEoC2ABeg0bBiAUAGYM24Z/XDOYAAAAASUVORK5CYII=>

[image38]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACYAAAAYCAYAAACWTY9zAAABYUlEQVR4Xu2UvytGURjHnxSDGFmklB+DRRmYLDKbpQwWg+GdGLHY7JSBDZsii2LzHyiLKJOQXylC+B7POe8953vvfa+3vEqdT33qnu9zz+mc59yuSCTy/7mHL9YHqjlu4Dk8g5dwMCzXlk/rCBfAkGhtEzZTrab0wTVJNpfFMwd/wTZsg7eiG5sKyzIB5ykrsyjJiZ5gY1gOOOKgANelDvvMXTuFDZR9cyB6Kses6OQdL3MMwDkOC/A34jbWTlkmFxxYNkQn7Yt+J4d2XA39cNkbm2s0a1x72aP3HDDKgUedaDfNYutU+wm7sJUyvk5zQ7k0if5nzIRpqjF7HFQgq8PDovkr7KZawJjoi5OwR/RnaMZd/kseKxzkUA9POLS4rvnfdop3DkAL/IBXkpyqV7I7kMcCHOfQsiTpK00xw4FHSZIFjJ1huSJvHBCFG/ttViU8zF1YLnMMtziMRCKRKvgCqdVWcRsNdO8AAAAASUVORK5CYII=>

[image39]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAYCAYAAADDLGwtAAAAoElEQVR4XmNgGAW0AIzoAuhgJhBvB+JvQHwaTe4/EHeBGBJAvAMq+AMqAQNaUL4piPMMSQIkeA+JvxkqhgJWYREE8UHOwRBEVsgO5dcgiYEBSHAtEr8OKsaKJAYGIME9SPxfUDEMcJgBIqHHgFD0DkUFEpAD4iwgFmCAKExBlcb0CIj9AIkPBjwMEAkzKN8GiG8hpFHBdAaEqUfQ5AYaAADDjiuVHsZpmgAAAABJRU5ErkJggg==>

[image40]: <data:image/png;base64,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>

[image41]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADMAAAAXCAYAAACmnHcKAAABvUlEQVR4Xu2WSyhEYRTHjySvKArZSIoNeztlYcFWkYVHWSgLwlZRYmdlqRAbbOwspCTKQllYsPMuKY+yF+ff/U5z5txv7kxNo5m6v/p3v/M/594557uPhigmJiYbSlivrF+lT9awqjky+UWVy0ukUR81FOS6bSJfSTXMGOvRmvkOBjk33iVrwXh5TxMFw5S6uNbFBckmJZqfcOuCHQaNf7OuWTOsW+dlQr2TptKpzPjpqGBVuWO18otZ5ZR4ciJB4yse79l4qUDtrvGG3PGHkofVm9TA2lAxGKfwRvazlo3nZZLCJ4ND8vuWUdY8hWuv3BE5oZl1oGLQZ+I7Cp4S4YRVp+JIPijcCCiiwN8yvkU+26jFYAIa6lIx2GF1qLhRrQVcZ9at33QiE3CybxgQlRNu3PGMkmvn1FpIdy2AGtnIfZPzMsB6p0Sz0AsFL5nwYPK+XWql8PuwxFpTniANRoE7hxq8/C1ujb9b/8Keidcp9d2cIr+vQX7bxBcqzim+5uDZIcEX68maBpyLOyJMOy+ntFOwg/ihQZO7Z7WpuJc1QkHtMatH5QR4qxTU4BWQr5cMc8rqdF5MTEwW/AFWRXHOUZtfyAAAAABJRU5ErkJggg==>

[image42]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAYCAYAAAD+vg1LAAAA/klEQVR4XmNgGAX0BoxA/BWIXwLxEyB+DsRvgDgbSc0xqPg9IL4DxK+R5AiCUCD+D8Qa6BIMEMtBcr+BOBxNjiD4wADRjA6agPgkuiApAGToajQxIyCORRMjCcC8ihwMs4B4IxKfLJDPgBoMoMjDFiwkg3cMEIMEoTQMSyIrIgfADLoJ5XdD+U/hKsgApgwQQ66iicMswwdA8jLogjCwkwGiIAxNPBcqDgoeXACvxfhcBhJ/gC7IAHEEclyAkiUGwGcwKGPgktsOxDPQBSMYEEkKhj+iqGBgeIYkB8IgPjIAiUmgiVEF4PIJxeA+lAaVdlQFoJIOZCioOBgFdAIArrdIgrVSBKQAAAAASUVORK5CYII=>

[image43]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAYCAYAAAAVibZIAAABDUlEQVR4Xu2TvWoCQRSFL4gpJJa+g20U8hbWprC3tkrwCaxFyzxDwCYPkCKQCPamCQkqKAr+oJVJzs3ssteT2c02dvvBgZ3zMZddZlYk41zskRnyhnwgO+PWyDsyRj6RpXEXyByZIFNka9wvD8g3MmQB7sW5KgvQFecaLJS6OPnKAtyIcz6+uLBcidu4YiGu1+RZgCYXlqJEmy095Droy+TuaO3FN1QPStG+ZgU40NoLD9UTDz9Z+5ZxT8ilWcdih5aQR3L94LmAvBiXiB26sEJcH94MvdepCYfqT5DzOL34I3Fvmppw6ICFRO6ZxX8c5fSgLBuJd4noZ8dt1INpc5mGDlLhMuCWi4yMv/wAbk5I2/5HTiEAAAAASUVORK5CYII=>

[image44]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAYCAYAAAC4CK7hAAAB5klEQVR4Xu2XSytFURTHFyUlSkpmPoDnQAYMDM0YKBNCDCgZKcqQGd/AwARlQiGZmRBRogh5DCjyVh7Jm/9q78M66957zg11z637q1937bX2eexz9tnnXKIECRJEwwM8hHtwH166qoZHeANP4CmZvoGkHn5aw5FOpvYEi1QtcHgNpBlO6WRQ8RpIpHwgiTSQVFiik0Em0kCedSLoHFPoQFrghMoFnjEKHYhu+5GtE/9MpFnjoorcnXw3iBHjOqHJJHPyBXAZVrrLgYAXnXydDAcPpB9e64KgGL6Reds7rNicph0uwQYyU5fhZ24R5sAzMosJv5AlI3ABlpJ5Th1mROxJNHPQqfNvGqyFGWQGI+EpMGjjObgGk8lcVd62ztZ4eZfH3CazT4bzHaLmd27fcMdunVRwn03Rdm61PEiKar/AGphl27LWBO9tXKhqHCepdlTw1fCjDd6Se6f8PL2Kdi+FnpBkVMT80dpo4wMyH64Ocrsy1f41fOXljnZFzHm+C850KaefZ2gVvtuY6RIxTzW5z3nYY+NcOAsryNyVI9gKh2z9T+xY+eUpGYZbKsd3hb+W1+GAyG+ImDmHF6J9R+akq+EHnLb5PHjldIoFfMV5UYg7eFmV04X/jMUtnXAS9ulCAg++AKoDe203wXAGAAAAAElFTkSuQmCC>

[image45]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAYCAYAAACBbx+6AAABsklEQVR4Xu2Wuy8FQRTGD6ITjdIjUSgQKhEUWhKFRKJUKahE6VHRUaJQSCT+BQmJhGg0uKUCEYKCiEdCofD6vsyZm5lx90ZyN+6S/SVfds45k91vZnZmVyQl5X/wAl1AJ9ApdOVVDUvQPXQN3UDLfvn3GYE+VaVBzcLaLVQfFoqFNRzFZJgoNvkMZ8JEEogyXA3dhckkYA2X58gnkmcx5rqd3Dw048SJYlOM4SmNeVrEPbsNYaIQhsQYPNI4brOxw/PVvsfnUKNfTibWML96IZXQIbQN1Yr56r15PQzT0K6YPWFZgx6c2HIMPUFtQX4P2pcfnP1RRxu51CvrfdrmqtC85Qwa1vagGNM1UDu0aDspO1ArNCpm8KREzP3LNI7ykiWfYT64U/z6hNPuEb9GM4ztgML7csY/oA4nx5XloPvF/Nc0ObWcsJM7YyFb4v/4vDttGuCsWTagV21XyXfDnE32Z75Fc2z3ZnvEgPvQCo1nNV6F1rVdJ/77zX7cxHNOPKbtR70S/lwNOHHBX9hw4/BhXU58IGaVFpwcGde8pVnMgLj8fNVcuAm5uVeCfErKn+cLXz5r2urqSBMAAAAASUVORK5CYII=>

[image46]: <data:image/png;base64,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>

[image47]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA2CAYAAAB6H8WdAAAF80lEQVR4Xu3daai22xgH8GU8hJN5Hl4cc5FM+UAnhBQnIlM+mDKPSQjnFPJB4YOIOB0yFck3R50iJZRPZOqg10zmeR7Wv/u529de7/3s/bw9++z9HOf3q6u91rXuvfcz1X217nutpzUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP5/vbe0Ly9tDvbf0r5Nj1eUPgDAkbq4tE+X9igFykHxlr1Dd8pn25mPdX7Ob18Yqw4bm53q8frSBwA4UpeU9o9Ke52l4uXlq9xfhvwuWXrc8cI25b83DnR3bdPYLceBtv9v3bnHG0sfAODIXK3Hh0r/x6W95BltKlQ+Og50/27T2PlDflesK9ge2Kb8b8eB7uM9zhuTK/Vv5ZgLSx8A4MhcvceHS/+npb1kXdET89jjxoEdse6xz/mlseeMiaIen5m4i0ofANjAo3tcs/TTTiFx7ZJLsfLYHjcruauavAYfKf2flfaSdYXNOW392K74T1t+fHdvy4/9dUN/VI+/W1OwAcBZyf1Ej2nTCfWCHm/t8bIeb1rlntLj9z0+2eOJq1wKjquia7TNC7YUtnmtli6b/rFNY7ceB3bI99uZRdmXVz+XCra/Df2Rgg0AtjCfSJdOwku5S9v++7h21bN7vGQhXtymG+df0ON5PZ7bDr6UV40F289Le/SNtvf61fhXj9uV43ZV7ker7/0bejxs1R4/F+NnZEk9JrN0F5U+AHCIzJplVV9OqE8axpL7zkLu8UNuG/cbEzssBVtdQHBQwTYWNUuySnQ+LoXjrBZ4JyXbjtT///fSro/ttT0eXsbWUbABwJbe084sDm6xyj1tyI/HbeNWbVp1eGVx1AVb/LJN98ZVT2hTUXOSntn2Hv8Xepxbxupz+0fJH0TBBgBbWiou3r2Qe/pCbldlJeK9zyI2cTaXRPM6fW5MLsi9gQ8act8e+ifhIW16Drlf8evD2Px5uV6PGw5j6yjYAGBLOZlmlm3MjcVZ+tk/bG5Hiou0M0v0mx5/6vGo1dgshcvn2zSbNEux8+fSnyX/lR7PKrkUD7n365s9blzyx20s2NYtOrhTm16Tusp2ncymvbP0c+/dNm7aNrtEeZjrtOk5/HMcaNP7vPT5OEg9NosOLix9AGADOZneZCH3rjW557dpU9hIoZYVgvNqyBRrKa5mKfDuWPq/aNNN/kszN7n0FpnJS1EQ2RG/7nf2gdI+bptu65GCcy5iD3PzHl8t/S+W9knLc1gqkL/UprF7jAMHULABwJbGmZJsN5FcZlmqrBRMPissq/r7H+vx6dKfZ+RmOTb3x83t6oc9ftXjqSWXY7Ky81U9vlbyJ+GwjXOz+//vevx69fOvbbOvn5pfh2/ty7b2ytXPLAZ5aB1YSeHz5tJPEfyi0o9ctsz3dt5nyKd/WNE0vj+zFM15n85G/Vu5XJ3PEgBwTB7c9p+M53byj2j7d/K/Z49Xr9qf6vGJNu0BF5nhy4k8Mrv20lV7XdFwEsavpvpJaW8jz/GyIZctRy7p8YNV/zVt738/oO0vmPL7t+1x+zbNflUpdGN+HfO6Zo+12R1K+4pU38e7tMM32gUAjtBnery/9OcT89tWP+tMyljY5RsVsq3I3J9nlHJ59VolP0tBkhm8k/TB0t7ky983keeYWcRR8jdYtXMp+fySr3u5ja9rlX5iXliRdu4FTLGZPfWOS31c2ax5LtwBgGOQrzC6UennMuDlpZ+iJpcys+Dg3JJP4VNXQ+byXi6fpljLDMwshUZO9lmMsAtbgFxc2qdLexvrtsZYV4iNRVneg8iMZi0iU/Ret8c72t7vjL97XOr/PdX2inMAgCP3vtL+bmkftcygzSs079vjD226pzCXlWvx8+Qe11+1c79ctsyos5az0wu5eOTQv6LU/5vLt+N9kAAAVzpZLFDl2yhyD93sVNu/+nZ2/6F/r6Ef+Z7TbD0CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADskv8Bh5dfNSiZsdUAAAAASUVORK5CYII=>

[image48]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAYCAYAAAC4CK7hAAABzUlEQVR4Xu2VO0gcURSGj9FAFA0WBhG00yiksDUggdjYqKAEFAsLC20sBNugCIJNSCV2iRaWFoqtWGplIogEEV+gnWIkBJ9B/9854549O4W4G9jifvAz93x3djz3zkORQCAQCARyQ6kXoMQLUO5FPnGFTCJ3EjV6g0whm+oqkGNkFZlRN/zwyzziAzKiYzbIWFifIS+Nu1CfV/zRI+8Em/tm5ggdG/culwvhHX/j5XP5IZnNtamrc55u2rlsaPEiG5J2eT3BfVX3wvm8gc19T3B+IdbFx3ZkB+lGTnW8oHMxDchf5CeypY6P1AGyoXVMI3KLnDjfjFwjl84/0ilRU1XO0yW9M190HC98CWnSuRg7HkT2TL2iRy6aJG0W+SSpfwGzEn01CT88AzpOY00yL8ZdpuOuWejGJbpwTBGyiMwZ5xdVYOr4/SpGJiT6zFt4Pt1HrflbulakX6JHPpEa5K2XoMsLpRd57Rz/UK2Ox5BdN2fxi6w0NeEdPNc50mHG/5VCyWyO7LuajCLbOu6R1OPFzXkn6ece6vGV8++RIVPnDN65eVMvS9RsmdafJXpJfyN98UnKP0m9/OSX5gipN54fEp7La1QbHwgEnsA93H90XpfyXTgAAAAASUVORK5CYII=>

[image49]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADgAAAAXCAYAAABefIz9AAACAUlEQVR4Xu2WzUtVURTFd0FCUCLSFyoaDspAQ2uiiNhAJBw5aCAWSH9AEzERwVFTRQQnUTNBSHAgiCAINQka6MBGDhyITUIJQcUc9OFenH1wvf0uIfTC9+L8YHH3Xvvdc89593xckUQikUgkEt2q36pZy9tUq+ZNmndV9cm89+aVDLt2RedfqcaoBm9UcgcF74jyogZvrcZidBxisrwfGd55c1/V5U0GU9F3+pp5T50Pb815f8K3+y94qLrnTeaX5HdkOsN7ZB4aLCYWveFBpzczPD/APfKwGXk6XV7tcgYzhGmhuF11kfLIZVWHNyW/nzlcl/CDPufD28jwPlt8QD4e/NXin3adUlWo3loeWVANqh5LaK9M1SqhjY8SZg74Lrnr6oPqicV+QD7PIW7/DBqCV+58eC9Vc85/Z7V+8m5JOIJukLejWrIYbcfnNkp4Y88tB6g9sBj3vXG1yIhqi/I8alV3vKn0esPApnPFm8q8hAfzMYO3wKBeb/GEhPM2gj+O4UEgrqI8ntngUDVAecF5rfpm8QvVMNXQsUpVHeURbGw9lO9TPKTappzva1Y1SPhDuXbXrgVnWXXb4mPyL0l4+BfyMLXHVc+sxnCOdYtBrliO9Y4336RaV12Q050T92EdFx0l8zV0VvAFFDcKrNObVPsvwK6JI2BGwqdV4m85AQBScr74ZVHbAAAAAElFTkSuQmCC>

[image50]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABQAAAAXCAYAAAALHW+jAAAAzElEQVR4XmNgGAWjYHCBK0D8HojF0cQnI7FXAfF6JD5O8B9K30Big0AJGh/ERuZjBe1AbAhlo2v4jsYvR+NjBROgNBsDRHEDQgrMf4PEh4nh48PBVwZUSXsoXxNJLAqIk5H4eAFI8yck/g6oGDJ4hca3Q+OjAJDmTUj851AxZPAYiQ0Kqmwgno8khgJqGCAGBAHxWQaI92CWKAHxI4RSMJBggMiDaJyAhQFiIBOSmBoDxCXYALoPKAYgbwswQHxAMQD5RpABNVxHARUAAMBzL6T8OsJQAAAAAElFTkSuQmCC>

[image51]: <data:image/png;base64,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>

[image52]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAZCAYAAAABmx/yAAAAnklEQVR4XmNgGAWjAAoeAfFzIGZDEmMB4i4kfiUQ30TiM/xHor8hiT9GkgMBEBvOnwjEckgSIFthAMR/g8TXgYqBwRQoDdIMEnSESUD5eUh8mBiGALogOp8HiFejiYEV7UfiS0DFkAHIdQJoYmBFdUh8V6gYMkDngwFI8A8S/x9UDAZmALEWEh8OOID4HQPCr6JAfAWJ74NQOgoGGQAAyfoqW0PwlQAAAAAASUVORK5CYII=>

[image53]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABMAAAAYCAYAAAAYl8YPAAAAVUlEQVR4XmNgGAWjYPCC/+gClIBLQMyELkguYAPip+iClIAyIF6OLggCoDCgBH9hoAI4A8T16ILkgANArIcuSA6QBuIZ6ILkgrfoApSA9+gCo2C4AQBIKhmIEfrpwQAAAABJRU5ErkJggg==>

[image54]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA2CAYAAAB6H8WdAAAFO0lEQVR4Xu3dW6htVRkH8KGmaRJqSVpGEeGFLEsMMX3ZZOlrL0UpCuWDLyaoFSpCZCX40KMVEh7RhxCVSu2iPoRSiBjdxGvWOaVmmArZVVNz/J1zcMYZe53O3ueyPZffDz72mN+ca+655n7YH98Yc61SAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYBf2xTExu3BMAACwtn5R4y9Dbr8a/6tx8pAHAGANXVvjpRpvH/Ip4P465AAAXhd3lamLtLnYXaV79myNpSG/rsbLNd455FfilbL8/u0J9xIA2IFSRLxp2N7d3Vbj3zUOHvKP1dgw5Fbjv8P2nnAvAYA10Bdr8bNhe0e5tax9QZOO2vM1PjTkv1vjPzUOGfKr9bZunDVvYwE3eq7Gv8YkAMD/kzVcnxuTO9C2Fmz7lNWd48gyHX/AkP9jjQeH3LZ6qMZ1Y7Lz1jJdyz/GHauU4nM19wAA2MX9sExdqLXy1JhYpUtr/GFMrsDTNX475A4r04MH6bZtDymilsZkZ12NH4/JrXBHjWvGJACw+1rUqXm8xt9rvKfG1TV+0O37Xo2Hy/TQwke6fIqeG8rUrbu9y6eD988yTYdeVeOYbt93avy6TOe7Zc7dV+PuGh+bt0+t8ZN5vD0W87+/TK9dtJYtXbe9hvxK5X1v7poy7dpf99c23f3ax4pkjV1+9r//yRrfqnFBjdPnXH+e3Nd4Zt5ucp43zOPcuxdqXFbj+hr7t4OqK+dcO0+Tp2RTEK5l5xUA2IylsrzIeHOND9S4p8ajZSqeUhBEiqgT53H8fv750xpfmccpelIENP35U4A0h9f4VLed444t0+9PIXfjnE9n7Ox2UFl+vVtrfZmuvy+QDirT+rIfdbmVyuu2dG2L9vfFbaZtz5rH6fxlCjXyuvfO4xRi/Xn+PP9Mrr2X8fe0e3t5jePn3J9qfGEef7zGu+Zx/t5tvV/W2wEAr7MryvJ/7q0Dk/wR/Y45d06Nb5SNU5vtQ2abjLNuLN5d45vDvkXjtp2CqY0zXdnGzUnD9rZKly1PjvYdxEjBmq5TiseVynXdNCYH47W39XjnlmntW7ps8aU53/Tji8vUDWwOLdP7aMfk2vvjx79PHDXnPlum997/jVLIZd/NXQ4A2AntW5b/k49FuUxh9ov32zHpCP28y+8978s069glSmeobZ/Qjd/Xjd9SpsX6rduWqdLt6ftjokzFzqL81kh36/4h9+my+J4m13cfW2eyFXitG3bK/PNvZSr6Ih3J88rGDwTOerdvz+Mm2zlukRRzsVTj/C4PAOxk0sV5ZEyWTYuLTN9tqPHlGnd2uXyExoFl6q5lX5OPDskUW1sv1Z8r+bZe6rQaL87je8vUdfrwvN1ek87XZ+bxruKJGp8fcm8sm96HpTIVXlk/2IqxT9S4qEwFX7TjP1im4jfyUSIfncfZn+K4FWTZfsc8bvLa/vemMDuuTOv72nenpjhM4Q4A7KTyNOWi79HM9FvWTKVAOKPL/65MBd4lZSoEftPty7cHpAPUumgp5CJTdxvKtCC+FR5NunY5XwrAvKY9xfnVGg/U+Pq8vSvJ+1j0NO4na/yqTEVrK6xScOUep3A7ukzTtnloINIx+2WNM+ftSIGcY/INDim215eN09m5/4ukAEzxnAdM+gcRcnyewt3S9C4AwG6n72gBALATyXqxTO2mawYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOxJXgUIVBJFQALOpgAAAABJRU5ErkJggg==>

[image55]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD4AAAAYCAYAAACiNE5vAAACD0lEQVR4Xu2WTUhVQRTHjxFoawk0SBAxUnFRuzZtXNhGhRYakW7SjS4EV24kECJ0IypECzduBEEqDJJatoooEaTIheAX2CYxRfIr9f9nZvC8854vvJt6z/nBj5lzZt69M/edO++JRCKRSCQSieQol+EBPM5iXsKNvYUPYAt87vvN8D4sPp2aP/yA11RcAS+pOBNbcBR22IFc5o9NGFgNk/CGHUjAf/UK/W0xHK+3yYSs2cS/gu/zWRtvlOwHXjs8hN9NvhUuwUfwtc9xnr3OdbgIC31Mfvm2Fn6Bg3AGfhC31gDjBbircuQpXIXTJp/GhqRvyJJpfB4+UzE3QTrhrO+/giu+T3pUn3z2bbdva+T0XpuwyMcF8Dd84/vM8VeJXPEtuSPuwCaZ1pwCJ8zZpOKWpF+kzOfuwS5xh2VAz+VDfazi8G0GuOh+Fb+E475fAnvFVYSG1bUsrhoH4Cc1xofO+4cqy0p42mcxIq6sNEOS/jBIm6Tm7RwbEzu/UsXb8KGKCec0mJxmTNyc93bgvPAiN03uNjwyuWpYJ+5nLxA2xf8H5Sp+4VsScnxVQn/YjGlYXbxe4K5vp+C6yus5ich0c8JDhN/IHnyi8u/gN3Eluy/uAArwoUyomLBKvopbKEuYkquS+lkNXyGeDz9hqcrviDsQP6pcIniA8DS+ULCU+2CVHch3+De2ySYjOcgJWNqBsZ9YubUAAAAASUVORK5CYII=>

[image56]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAF8AAAAYCAYAAACcESEhAAAC80lEQVR4Xu2YW4hOURTHl2uklAehaIrccn2hJJFIUi4PoiQll8gkUfJi5o0XSSjlQfHgktuDkXEphCeiFEkp9yITolGu699a27fO6nzf/maYwzftX/07e//XPmdfzj577+8jSiQSiUQi8U/Y7Y1EMXxk/fRmohgw8O+9meh4upMM/nofKMMAkvJBG7PhDJe9kRDsAFpVoh9lywxlvWL9MJ5lszfK4NtgdcKU63S0UnzQA9e9oYwgecYZ1gTWOs1XwzfWFtYS1k7WDdZS1mLWAlOuU4JBeu3NMjzyhqEn6xzJ856TfBUxLrBmmPxj1nST94xiXaTqX+x/zSySjoz0gQhfSO5rJtkzynHSGxFigxriwzJu+4jV1eHcorY3AuWxROCFNWn+SKZEiV3eqMAGirclFq+WLvT3ntVu0ADbiFiD9rEGe5PkJTxlDTEelqC28JVkucpjLpXaCiFvuUayZOGLtGByXWEdYE1Wzz4HdYJNrLus1ZrvzXqmadBCMtnesp6wuqnfh/WSdZXk4GG5z7rJmuP836ABZ00em2Ul3nnDsJ2yHTudDUfBPQ3edOzxBsl9PTSN6xpNf2LVaXota6ymAfqxStP4ChayFlHpt85h1lFNY2I1UulEh/qmsSZqOmDbfp41VdOfjZ8Bb+0NyaZnH1Q080jqH+gDhjGs8c7DwL1gzSc5Kd1Rv56y/Tlu0sDG+uoVL2u5phFHfWASyT8AKzUfQJkdJKcyvCi7xOIAg/he4+WCSmZ7s2DwGa/wpiNv/8CgY9Z6MEsPmrwdbNSVN9Gs5+M+D/I8yyWSMjN9oBbJ62wv1jKTn0KycWMWIw3CfoFlERxiHdP0cL1i7Q7PxxeE+7GE1amXV7f39usV/lZNdyU5gtc8vrMBrN+3STbFcBhAp7GZfmCNJtnIGzSGo/F3kg3RgnUah4ZBJPF7Jpb3F0p/kjY9ZD0wPn6L4IcjDgCnjF+TYGPDYGJAEgUSZtc21jgXSxRAI8kxMJH4c34B0ai4uoZq1bMAAAAASUVORK5CYII=>

[image57]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADEAAAAXCAYAAACiaac3AAABO0lEQVR4Xu2WsUrDUBSGj0NBxKUdRDp18gUUK1RKKUgfQLAP4N7NvQ/g4q4429YOPkBfwMXFrU4O7eSsCNX7kxNMf281yb2lHe4HB8L354ZzEnITkUAg8B8tUxss14hNLSsDU1+mTk2NTU3n47WgLVGPhxyAJ4nCJH2LWxWVxPHCIRC8kDtRv03elVsWGbEOUdBgRH5P/RV5V1yfrnWIpgZD8jvqeThXrk0dsMyAdYj4ZbkjX1T/St4HLk8Da6sszzRYNMQbeR9gC8e1SxykAOuOWJY1eEjpmcuc1ZPo+heSDaypsQQIHsntq++S98Gu5P8OoadjlgDBO7lz9cvgk0UG0FOdJbiR3w1PTM3I+eBe/vhtSAH6bLCM+TD1rMcdiU7e+om9kefG4B2Kbyr6QmHDWcbOGQgEAp74Bi/3USq+SgM6AAAAAElFTkSuQmCC>

[image58]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAE0AAAAYCAYAAAC/SnD0AAADJUlEQVR4Xu2YS6iNURTHlzd5J5EoQpLyKHnLAJGBECUTA5QQeQ2MPAYIKTIg5BYRiYHCxGtmwAAliboJGXiWVx6x/vZazjrrrO/cc+69OE7nV//ut////e3zffvus/a+l6hGjRo1/gpnvdFI7rHGebOS+WFUDk+8ETCX8seHjkk2RTsJyHo4r6J5RuVN2mHWHW8aelJukma4bD/rlmSWjoFX0Wyk0h8Yq6FY34+U8pE+MDyieIw6Vm9vViprKX6JiKes294U2lEaZ58PHIdY37zJtGQ98GYEvvdZdJWfLfLcHINZU73psHWii7m2rKHSJw39FnpTeEOljbOXtd2bQtH7X4jw0uh42mRaDy6xvrKOS1vBb+M7awxrpWRzTA50DAg700PWXWkvM/2AnzR7r/XbuLYFvxBkO30Q0MEbhqzx6T3lh/qBI4ynD9yHNUuufaZckHZr4wHtZ1/kg3gWP2n4+r2kwvEWUOG9yg3KzsoBY/T15igJtjkf3mPXznqIXqz+pj2QUt+lxgPRGDcDz05ae9Y5k1mKbRjRZzUGjDHNm9ckOMHa5WRXBPpgJ8oCWzf6fKFUeHGNr6olepHrgaeTpkePrK/Ybiq8V4k+K2ILa7Q3DRjDl49fOweC+T5woM9bbwr6gKgxoJu0V/3ukYhe5Erg6aSNZXWS6855PRJLqPBeBbU3K7M01Af5dG8OkuCUD5h55hp9UFc8BylldtdEDdBJwwRobYwm7WrgrXdedB+YSLEPZlN2ppyn4qsMYIwB3gSvKIW20E6mtAoV5CjanpOUMtQx5Yh461hbWUPFj14+KtibnDdc2peNB3COgt/W+QrKCU77EXWsPd4M8M+WRz2lDqhtmymdcZTnkkHvWPdNBjSbwJrEOkCpttlJ+mTan1mrWa+NB2HjsZ8F4W9K3d1VRykH2htM24McxyGs3lasmZRKAjbAUtDnzwSH1kWsfj4ogWGsFZS/4oaY6z9FPaXzZTGWsy5SOrpkbSoR3Vk7vFktYDXgr5HmpsFV9j+zmOJ62xTGU7zxVRVnvNEEUKaqepVZmmtl4D8eeuasUeMf8RO/rvnaR1YRfgAAAABJRU5ErkJggg==>

[image59]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEIAAAAYCAYAAABOQSt5AAACuklEQVR4Xu2YS6hNURjHP6+8i4soZWTgFaWulEcmzCgpRiSPUJJMXJLHTJKZzNwZAyUzY6RkIERJcU9CHmHgUZTH979rrbO//b9r7XvO2fvoDvav/t29/t+3Hnvtvb+9zxWpqakpyQY2IpxnYwSxUPWMzXaZp/rLJrFKNcCm54fqg+qt6o3qnep+LsPFX6uei8uZmg9XwkXVdTbbAZtQtBETpTgOxks2zjiKgWXiYkdUkyhWJcOtM8lX1VUpHgCxNWwS/eLyznFAaah2s9klRqsesjkca1V3VdskvRELJB2zhLthsvEmeG+a8f4Hraw3R+iw2BwzjyUds4SNCGxUvTftsrTzOGEd89lMcVm1yx+PEdd5ThZuAv8Km0QotiiaYJZvV8Vv1RnVF/I3qe6QBzD3NTZj4DnC4BZ0Xk8egN/HJtEvLu+46pDqiW+fsEkdgjtyhj/mzf0sbj4GeQ02Y3xSTScPnVHRGfhb2SSQA71Q7SevLL/83+0Sv3i4m5mf0sLcoyRbJOumyQvAX80mETvpl967RH6nYKwe00ah5zkDA5KONfnIhgcd8aHDwN/BJoEcfiZxx8U2qBPw8cXj3I54gT+Sjg2yQvWITU9q0fBOs2lAvUHOIg5INuYWDrTJQRm6ttR6AfzYRR0kvNNTpAaGd4tNwzGJ9wM7JT2uBXEU2hQHJD/GbN++YTwLYqfYXCfZYmKLuiCuCIUYihM+sgJ4dXIf8FT1XbJ+eHW+MnGMwfM2TDwQaha+cItAzkpxGxbGw/dPDMRmslmWVn6QVUErc+wTd/IPpDi/KFYK3IL2alfNEtVeNj0nxZ1YiO/x7eXNjDxnpTu/bJtg8rFsVkTRFbyn+uaP54rL3ZyFh1A0ViXgdYjXUjdA8SsC9QcniP9lTKGYpaHqZbMbLBVX3EYiR1WH2aypifMPLCPEp/EJnyAAAAAASUVORK5CYII=>

[image60]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEMAAAAYCAYAAAChg0BHAAACe0lEQVR4Xu2WOYgVQRCGCwVBPGG9QDDSSMRMEAMDBY9E8cALA2FTUSMFE0UQzZRVPCJFPIJdj0xBPEIFRV3wWhRMDEQEL8R769+u9tX8rwaE2cfu8uaDYrq/6pnp6emeHpGampoRxDsW7cxPFu3KTo1NLNuVvyzalZUaB1kONeNZKGNZKJNZVOQbC2McC2USC4ldJb5rHJI0XSdo/NI4qvHM3ERJX/tbGhfMbR44szo/WCivNQ5Ius88jQ8a5zVum5uv8UTjpaR+wp0eOLMiizV2WRkX5fWL+nuNUc79MV+V/RpryOFlXLNyWX9w/ynO9ZqvzBc7dki64AmXA3AfA1d282Ua3Ro9Gpc1XhXTBaJr3JA0EwHyD10uOz7vTeDATYnbZ8f+H4+lObnB3AznRpvb51wGb2ihq6PtfVdn9rJw5OnvQT/g0C8P3B1ymTOS8l3kF1C9QDRSzwN3NnAZ+LnkllA94wc4IlqKJwO3zdx08hnkjtjxv0HjU4Hji3jHufwAneQjHrEgcJ0XgeN7/nYu2hGP2xFtVlgZn4RS1kpqPJV8HlV2e6zM/wdYFvitzp1eVEwX4Ify4OOI/DrycDyIcNet/MAnlNnSeKankl4WOGbHkHvS3Ln8veD9Hm6HxhXyzGdJW3TEco3DLB3IcX+wDOCWkoe7JGkr3k25i66M50Bb7FZ87QKzNOawVFaxMLZI8yCdo/pGjT5yma8sCHQ4mlVbWRjrpXlWgzwTMlhSWHoYvJaxWhpbdKZs9GdqXGXZAjA4+LgyZf0aNLCO87Z3V9L6HFNo0QB/jmW5wQK/+J8kvSD883jeUn1IafmbGSlM09jOsqZmeNMPOommc4js0DIAAAAASUVORK5CYII=>

[image61]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFMAAAAYCAYAAACGLcGvAAACPElEQVR4Xu2XPWgVQRSFbzAW0YhNIBZiftDCKk3QdLG0CkQCQkyXKp1EUGysI1iIIELSBARF1FTpBMFCC4sQCMEEAjYmjYEQEUWDP/c4Mzp7dnbf29338D2YDw47c+7m7tzZNzMbkUgkEolEIpFIi3FEta96w4F2pZsNpYsN5TgbDeSo6pfqBgdK8l9q+q66LaYQDOCH6q5q03rHVLuqF6on1pv485fNAbnxjAUOFMCvqVPSNQGuqTKjqqu2jYScFH08tIM8vq8ZDIuZhJccqAHX9M2LOe+npGsa8vql+GyvPWIS3vdiAN5ewMuazIuqp6rn9vo+GS7FSTHPm+ZABlwTA68v4J0nD7haX2f4ofyyJunAFethUI7D1rvpeY51SQ4Iy6tRhwr20w+qjxzIIa8mH1dTFgNi4r2eN++1U4RmeSvgPQ54DvhnyRulfhmw170TU3QRGlGTA3vwjtfPvR/BBwEPe0uWhyXtAx/xepdjLZbE5LtAfr2UqYkn6bS9npNk7JnXTuBOT385A3h3At6sbX/1A8oh1YGYe6CRZLgukGNFTO5BihWhTE39qlvJkDzy2rhv0bZ5Bf7lraTfyKT1+LsM3oxqWfKXMA4BTGwRrqm2xXyKVaVMTXzQAv9XjInmnClOqc6wqYyxYZkS81+Lz0PqY6PfIC8LvGUM8hIHKlCmphD3qI9xXievoYzLv88RR8032AbMsaFclibXtqo6IeYhr8R8IhU9eVuNL6pP9spgT49EIpFIBX4DKROjGmPxS6oAAAAASUVORK5CYII=>

[image62]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC4AAAAYCAYAAACFms+HAAABjElEQVR4Xu2WTStFURSGFxJCJvwAJVIUP8KUkQEDmSgzAwyklIGJkj+gTAyZKDExpshAkUwuJfIRko+Jr3fZa+e1j2ty3Dqne556Onu9+9x9V3fve+4VycgoPp7hGTyGJ/ACPvINSebD7Aknko5vPHVo02thmAa08c4wTDqDktJjciopbVybXg7DAtAVBnFoFdd4SThh/NdONMCKMIzDiuRvrgWuhmFS+Ov5rTl/SofidmgObsJLmvNswy34RtkDfKJaKYevcAeWUV4Dz8X9ejdSHiFf45PyM1+yK2d7cIxqPnLVsA8e0Jw26+F1Juyqj2POczT+ohveyHfTqv5XuYLvlE37F4A2WCru0enRezps/AIXaU7RY9YM6yT64Wh9D0eCbAb2wlvKYzMe1NyMjquoHoIDNtbjM09zShM8kugaBYEX3oAL4nbCz1XaWI/Lbw3tU11r42G7+tyja+WojoV+mTzt4rZzyup6cW+8C9f9TYZ+2a6pnoV34o7rKOX6yNQ1dCf6Kc/IKAo+AdA5Y2VB7f2RAAAAAElFTkSuQmCC>

[image63]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADQAAAAYCAYAAAC1Ft6mAAAB1klEQVR4Xu2WzysFURTHT36s2Ek2Fo9Y+VE2bCgLGymJhaWFspCUIhELlhZKWfgDSLJRoixsZCGJovwKUUpJKb9SFN/T3OMdx5vX03uP5vU+9Wnu/d47zZyZO7chSpMmTaJ5gdfwFF7CG/isJwSRD2eTHQgqUlDKwMUs2TDIcEEVNgwqnZRiy413uJQqiIuZt+EvyYd5NkwwMW1cZRR9UrQxTYMNkkAW7LKhhXc2v5uuhAs2/EcGbRCJaK+Rc34qmiq4CZ9Utg13VF+4J+/vow72uWwPTsIaeAjfXa7ZguuwmbyHKjyqti9+BY1R5FwyPmbDdpircuFKtV/hOCyFmeTNLXFjrTLJwb9cha7N84rUmL3GF1z5HYWLYXmnuzXZkJyg4HxK9cvdcVdl/Bb1xbmdA0OwH16oMb2ke+nneQI/PN+C4qGbwgULjfR9h9sg7ydX0HMfYIfq2wJmTF8YhueqHzf8JuQC/F0dqDHJ29xxBK65Nn9H/M0J+iZrXV9+uXi5Vbt2C+yBE67P84rJW+IJ4xgewUWTz8F9k83CafJupF7lJ6rN8PcVcu0M+EbeW+TvjTeeATfGhZy59r+SlHX/l/CykyJW4KoaCyyjcBkW2IE0MfAJvll1O4ccuOoAAAAASUVORK5CYII=>

[image64]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADEAAAAYCAYAAABTPxXiAAABmklEQVR4Xu2UvS8GQRDGRzQSnfiKQiESQSOhURJ/gL+AQq2jU1KoRHQiEQo9jUYUEioJNVEIIkQIicb3jJ11d8/t7nuRyHuS/SVP3nefmZvdudtdokgkEqKG9cy6YJ2wzlnX6pWBHjRCfKqGMVAlJsisZ4p1yHrMht3YJsrAPOXXIs2gl0MS1tCsEq4XWqeed6fIuZCEdgwUpI2SiUVj2XCGDTQcSI13NMn4R2haJinfeVEaWR+sJh13s+5Yr6x6m5Si0jy1ZHLuMUDGf0PTIpNWKu7jAA1lgEzNVVYfa1rHg+kkB81k8m4wQMmXdiKBZTQLcoYGsEOm/imrAWIuWugXTfSTJ6CEYmk2yeTKr5wxH3NoOJA6T2iS36dtCi90AQ0H8vw6q4u1q+PFTEZCaC6L742Lt4em4HtAmEHDgWzDVjTJnBWpm95Cx6zZ1NjHC+XX1KFeJ/jf+JpYIrePOD+vIjeXrR/6Osg4mfz0ttxS74dRSm4kq0vWLXhFmvgrrlgP+n+IzFp6k/D/YYS1z1qh8GURiUQiJeELuHlzJPL6M6kAAAAASUVORK5CYII=>

[image65]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADsAAAAYCAYAAABEHYUrAAACf0lEQVR4Xu2XP4xNQRTGjyDREHb9X1aDRKhUhEqjUajoJbZARaWTEH8rlehsRCSEgkSwKwqS9afcll2xiwSLbLENwfkyZ5Lzvjdz3+y67yXYX/Ll3XO+uXPnvDv3zlyRWf5qlqkuqHrY+NfYo9prx79Ul503Y06qFroYHXeCJxTfphjjuGfHKLpyXJMSGvhCUpxRdbmYOx1WfVa9Vo2qPqimzHuseq96Zfqo2m0ewHnIvVNNuDwYovguxddUh+14izSPq4kr0rrRWQnPRiTVfpGEPLSKvAXOm0PefNVL1aBqCXnPKI53MQX+iNS4mkCj45x0nFOtdHGu01hQilZeiucUP6DYc5ETOaoGAs5L493Ktc31gzuS866q1nHSeEHxQ4oj3+13cUM2A54bDGQeGwaKXe3i1KBBqiBM0zeWZw9TepxyHi52gGLwyR0X3d1tEgZynQ0D69hMi/1ivylvTJqfYQ+eZQ8Xi/Njv6n+s1Q15kU71y72sdzizapLdvzTvMhaCVO4Ci4WL7E/xr8t15AHSouN//QOi327EYpzfXhqL7ZbwhoHcne3tNhbEryjqqXk3TAPYN0todZiMZX8wL9aPNflQGmxWKLgYer+IO+0eRskrO0l1FbsJgkXP+Fy2y2HnYmntNiDErxvqiPkHTAvd26KWordKuGiqXUrNaDSt/EuSZ8PdkrI72OjAi6W38ZF4KJvOWk8kuCvd7nSdbZXgreRDQnPcO68HCXrbEv6OEEcU+13cekOCtzkhGO6g+ViUzOxdvDiWeHiqmLrhPfG9yluCyVfPe1gOl89tXFKGj+/OlXsU4rvUNwWDknYZUWw9esE2Ih4+ime5b/kN4leugsrknm0AAAAAElFTkSuQmCC>
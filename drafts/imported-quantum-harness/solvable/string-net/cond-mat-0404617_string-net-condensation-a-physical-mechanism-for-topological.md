---
source: "https://arxiv.org/abs/cond-mat/0404617"
type: "arxiv"
canonical_id: "cond-mat/0404617"
title: "String-net condensation: A physical mechanism for topological phases"
authors: "Michael Levin, X. Wen"
year: "2004"
venue: "Physical Review B"
arxiv_id: "cond-mat/0404617"
doi: "10.1103/PhysRevB.71.045110"
full_text: yes
---

# String-net condensation: A physical mechanism for topological phases

**Authors:** Michael Levin, X. Wen

**Citation:** Physical Review B, vol. 71, pp. 045110, 2004

**arXiv:** [cond-mat/0404617](https://arxiv.org/abs/cond-mat/0404617)

**DOI:** [10.1103/PhysRevB.71.045110](https://doi.org/10.1103/PhysRevB.71.045110)

## Abstract

We show that quantum systems of extended objects naturally give rise to a large class of exotic phases---namely topological phases. These phases occur when extended objects, called ``string-nets,'' become highly fluctuating and condense. We construct a large class of exactly soluble 2D spin Hamiltonians whose ground states are string-net condensed. Each ground state corresponds to a different parity invariant topological phase. The models reveal the mathematical framework underlying topological phases: tensor category theory. One of the Hamiltonians---a spin-$1∕2$ system on the honeycomb lattice---is a simple theoretical realization of a universal fault tolerant quantum computer. The higher dimensional case also yields an interesting result: we find that 3D string-net condensation naturally gives rise to both emergent gauge bosons and emergent fermions. Thus, string-net condensation provides a mechanism for unifying gauge bosons and fermions in 3 and higher dimensions.

## Full Text

# String-net condensation: A physical mechanism for topological phases 

Michael A. Levin and Xiao-Gang Wen[∗] 

Department of Physics, Massachusetts Institute of Technology, Cambridge, Massachusetts 02139 

(Dated: April 2004) 

We show that quantum systems of extended objects naturally give rise to a large class of exotic phases - namely topological phases. These phases occur when the extended objects, called “string-nets”, become highly fluctuating and condense. We derive exactly soluble Hamiltonians for 2D local bosonic models whose ground states are string-net condensed states. Those ground states correspond to 2D parity invariant topological phases. These models reveal the mathematical framework underlying topological phases: tensor category theory. One of the Hamiltonians - a spin-1/2 system on the honeycomb lattice - is a simple theoretical realization of a fault tolerant quantum computer. The higher dimensional case also yields an interesting result: we find that 3D string-net condensation naturally gives rise to both emergent gauge bosons and emergent fermions. Thus, string-net condensation provides a mechanism for unifying gauge bosons and fermions in 3 and higher dimensions. 

PACS numbers: 11.15.-q, 71.10.-w 

## I. INTRODUCTION 

For many years, it was thought that Landau’s theory of symmetry breaking [1] could describe essentially all phases and phase transitions. It appeared that all continuous phase transitions were associated with a broken symmetry. However, after the discovery of the fractional quantum Hall (FQH) effect, it was realized that FQH states contain a new type of order - topological order - that is beyond the scope of Landau theory (for a review, see Ref. [2]). Since then the study of topological phases in condensed matter systems has been an active area of research. Topological phases have been investigated in a variety of theoretical and experimental systems, ranging from FQH systems [3–6], quantum dimer models [7–10] , quantum spin models [11–19], to quantum computing [20, 21], or even superconducting states [22, 23]. This work has revealed a host of interesting theoretical phenomena and applications, including fractionalization, anyonic quasiparticles, and fault tolerant quantum computation. Yet, a general theory of topological phases is lacking. 

One way to reveal the gaps in our understanding is to compare with Landau’s theory of symmetry breaking phases. Landau theory is based on (a) the physical concepts of long range order, symmetry breaking, and order parameters, and (b) the mathematical framework of group theory. These tools allow us to solve three important problems in the study of ordered phases. First, they provide low energy effective theories for general ordered phases: Ginzburg-Landau field theories [24]. Second, they lead to a classification of symmetry-breaking states. For example, we know that there are only 230 different crystal phases in three dimensions. Finally, they allow us to determine the universal properties of the quasiparticle excitations (e.g. whether they are gapped or gapless). In addition, Landau theory provides a physical picture for the emergence of ordered phases - namely particle con- 

densation. 

Several components of Landau theory have been successfully reproduced in the theory of topological phases. For example, the low energy behavior of topological phases is relatively well understood on a formal level: topological phases are gapped and are described by topological quantum field theories (TQFT’s).[25] The problem of physically characterizing topological phases has also been addressed. Ref. [2] investigated the “topological order” (analogous to long range order) that occurs in topological phases. The author showed that topological order is characterized by robust ground state degeneracy, nontrivial particle statistics, and gapless edge excitations.[3, 13, 26] These properties can be used to partially classify topological phases. Finally, the quasiparticle excitations of topological phases have been analyzed in particular cases. Unlike the symmetry breaking case, the emergent particles in topologically ordered (or more generally, quantum ordered) states include (deconfined) gauge bosons[27, 28] as well as fermions (in three dimensions) [29, 30] or anyons (in two dimensions) [31]. Fermions and anyons can emerge as collective excitations of purely bosonic models. 

Yet, the theory of topological phases is still incomplete. The theory lacks two important components: a physical picture (analogous to particle condensation) that clarifies how topological phases emerge from microscopic degrees of freedom, and a mathematical framework (analogous to group theory) for characterizing and classifying these phases. 

In this paper, we address these two issues for a large class of topological phases which we call “doubled” topological phases. On a formal level, “doubled” topological phases are phases that are described by a sum of two TQFT’s with opposite chiralities. Physically, they are characterized by parity and time reversal invariance. Examples include all discrete lattice gauge theories, and all doubled Chern-Simons theories. It is unclear to what extent our results generalize to chiral topological phases - such as in the FQH effect. 

We first address the problem of the physical picture for doubled topological phases. We argue that in these 

> ∗URL: http://dao.mit.edu/~wen 

2 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0002-01.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0002-02.png)


**----- Start of picture text -----**<br>
Normal String-net condensed<br>t/U << 1 t/U >> 1<br>**----- End of picture text -----**<br>


FIG. 1: A schematic phase diagram for the generic string-net Hamiltonian (3). When t/U (the ratio of the kinetic energy to the string tension) is small the system is in the normal phase. The ground state is essentially the vacuum with a few small string-nets. When t/U is large the string-nets condense and large fluctuating string-nets fill all of space. We expect a phase transition between the two states at some t/U of order unity. We have omitted string labels and orientations for the sake of clarity. 

phases, local energetic constraints cause the microscopic degrees of freedom to organize into effective extended objects called “string-nets”. At low energies, the microscopic Hamiltonian effectively describes the dynamics of these extended objects. If the kinetic energy of the string-nets dominates the string-net tension, the stringnets “condense”: large string-nets with a typical size on the same order as the system size fill all of space (see Fig. 1). The result is a doubled topological phase. Thus, just as traditional ordered phases arise via particle condensation, topological phases originate from “string-net condensation.” 

This physical picture naturally leads to a solution to the second problem - that of finding a mathematical framework for classifying and characterizing doubled topological phases. We show that each topological phase is associated with a mathematical object known as a “tensor category.” [32] Here, we think of a tensor category as a 6 index object Flmn[ijk][which][satisfies][certain] algebraic equations (8). The mathematical object Flmn[ijk] characterizes different topological phases and determines the universal properties of the quasiparticle excitations (e.g. statistics) just as the symmetry group does in Landau theory. We feel that the mathematical framework of tensor categories, together with the physical picture of string-net condensation provides a general theory of (doubled) topological phases. 

Our approach has the additional advantage of providing exactly soluble Hamiltonians and ground state wave functions for each of these phases. Those exactly soluble Hamiltonians describe local bosonic models (or spin models). They realize all discrete gauge theories (in any dimension) and all doubled Chern-Simons theories (in (2 + 1) dimensions). One of the Hamiltonians - a spin1/2 model on the honeycomb lattice - is a simple theoretical realization of a fault tolerant quantum computer [33]. The higher dimensional models also yield an interesting result: we find that (3 + 1)D string-net con- 

densation naturally gives rise to both emerging gauge bosons and emerging fermions. Thus, string-net condensation provides a mechanism for unifying gauge bosons and fermions in (3 + 1) and higher dimensions. 

We feel that this constructive approach is one of the most important features of this paper. Indeed, in the mathematical community it is well known that topological field theory, tensor category theory and knot theory are all intimately related [34–36]. Thus it is not surprising that topological phases are closely connected to tensor categories and string-nets. The contribution of this paper is our demonstration that these elegant mathematical relations have a concrete realization in condensed matter systems. 

The paper is organized as follows. In sections II and III, we introduce the string-net picture, first in the case of deconfined gauge theories, and then in the general case. We argue that all doubled topological phases are described by string-net condensation. 

The rest of the paper is devoted to developing a theory of string-net condensation. In section IV, we consider the case of (2 + 1) dimensions. In parts A and B, we construct string-net wave functions and Hamiltonians for each (2 + 1)D string-net condensed phase. Then, in part C, we use this mathematical framework to calculate the universal properties of the quasiparticle excitations in each phase. In section V, we discuss the generalization to 3 and higher dimensions. In the last section, we present several examples of string-net condensed states - including a spin-1/2 model theoretically capable of fault tolerant quantum computation. The main mathematical calculations can be found in the appendix. 

## II. STRING-NETS AND GAUGE THEORIES 

In this section, we introduce the string-net picture in the context of gauge theory [27, 37, 38]. We point out that all deconfined gauge theories can be understood as string-net condensates where the strings are essentially electric flux lines. We hope that this result provides intuition for (and motivates) the string-net picture in the general case. 

We begin with the simplest gauge theory - Z2 lattice gauge theory [39]. The Hamiltonian is 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0002-14.png)


where σ[x,y,z] are the Pauli matrices, and I, i, p label the sites, links, and plaquettes of the lattice. The Hilbert space is formed by states satisfying 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0002-16.png)


for every site I. For simplicity we will restrict our discussion to trivalent lattices such as the honeycomb lattice (see Fig. 2). 

It is well known that Z2 lattice gauge theory is dual to the Ising model in (2 + 1) dimensions [40]. What 

3 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0003-01.png)


**----- Start of picture text -----**<br>
σ [x] I σ [x]<br>σ   =−1 x<br>σ [x] σ   =−1 x σ   =−1 x<br>σ   =−1 x σ   =−1 x<br>σ [z] σ   =−1 x<br>σ [z] σ [z]<br>p<br>σ [z] σ [z]<br>σ [z]<br>**----- End of picture text -----**<br>


FIG. 2: The constraint term[�] legs of I[σ] i[x][and][magnetic][term] �edges of p[σ] j[z][in][Z][2][lattice][gauge][theory.][In][the][dual][picture,] we regard the links with σ[x] = −1 as being occupied by a string, and the links with σ[x] = +1 as being unoccupied. The constraint term then requires the strings to be closed - as shown on the right. 

is less well known is that there is a more general dual description of Z2 gauge theory that exists in any number of dimensions [41]. To obtain this dual picture, we view links with σ[x] = −1 as being occupied by a string and links with σ[x] = +1 as being unoccupied. The constraint (2) then implies that only closed strings are allowed in the Hilbert space (Fig. 2). 

In this way, Z2 gauge theory can be reformulated as a closed string theory, and the Hamiltonian can be viewed as a closed string Hamiltonian. The electric and magnetic energy terms have a simple interpretation in this dual picture: the “electric energy” −U[�] i[σ] i[x][is][a][string] tension while the “magnetic energy” t[�] p �edges of p[σ] j[z] is a string kinetic energy. The physical picture for the confining and deconfined phases is also clear. The confining phase corresponds to a large electric energy and hence a large string tension U ≫ t. The ground state is therefore the vacuum configuration with a few small strings. The deconfined phase corresponds to a large magnetic energy and hence a large kinetic energy. The ground state is thus a superposition of many large string configurations. In other words, the deconfined phase of Z2 gauge theory is a quantum liquid of large strings - a “string condensate.” (Fig. 3a). 

A similar, but more complicated, picture exists for other deconfined gauge theories. The next layer of complexity is revealed when we consider other Abelian theories, such as U (1) gauge theory. As in the case of Z2, U (1) lattice gauge theory can be reformulated as a theory of electric flux lines. However, unlike Z2, there is more then one type of flux line. The electric flux on a link can take any integral value in U (1) lattice gauge theory. Therefore, the electric flux lines need to be labeled with integers to indicate the amount of flux carried by the line. In addition, the flux lines need to be oriented to indicate the direction of the flux. The final point is that the flux lines don’t necessarily form closed loops. It is possible for three flux lines E1, E2, E3 to meet at a point, as long as Gauss’ law is obeyed: E1 + E2 + E3 = 0. Thus, the dual formulation of U (1) gauge theory involves not strings, but more general objects: networks of strings 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0003-06.png)


**----- Start of picture text -----**<br>
5 2<br>1<br>-3<br>-1 1/2<br>2<br>5<br>-4 3/2<br>2 7/2<br>3<br>1 5<br>(a) (b) (c)<br>**----- End of picture text -----**<br>


FIG. 3: Typical string-net configurations in the dual formulation of (a) Z2, (b) U (1), and (c) SU (2) gauge theory. In the case of (a) Z2 gauge theory, the string-net configurations consist of closed (non-intersecting) loops. In (b) U (1) gauge theory, the string-nets are oriented graphs with edges labeled by integers. The string-nets obey the branching rules E1 + E2 + E3 = 0 for any three edges meeting at a point. In the case of (c) SU (2) gauge theory, the string-nets consist of (unoriented) graphs with edges labeled by half-integers 1/2, 1, 3/2, .... The branching rules are given by the triangle inequality: {E1, E2, E3} are allowed to meet at a point if and only if E1 ≤ E2 + E3, E2 ≤ E3 + E1, E3 ≤ E1 + E2, and E1 + E2 + E3 is an integer. 

(or “string-nets”). The strings in a string-net are labeled, oriented, and obey branching rules, given by Gauss’ law (Fig. 3b). 

This “string-net” picture exists for general gauge theories. In the general case, the strings (electric flux lines) are labeled by representations of the gauge group. The branching rules (Gauss’ law) require that if three strings E1, E2, E3 meet at a point, then the product of the representations E1 ⊗ E2 ⊗ E3 must contain the trivial representation. (For example, in the case of SU (2), the strings are labeled by half-integers E = 1/2, 1, 3/2, ..., and the branching rules are given by the triangle inequality: {E1, E2, E3} are allowed to meet at a point if and only if E1 ≤ E2 + E3, E2 ≤ E3 + E1, E3 ≤ E1 + E2 and E1 + E2 + E3 is an integer (Fig. 3c)) [37]. These stringnets provide a general dual formulation of gauge theory. As in the case of Z2, the deconfined phase of the gauge theory always corresponds to highly fluctuating stringnets – a string-net condensate. 

## III. GENERAL STRING-NET PICTURE 

Given the large scope of gauge theory, it is natural to wonder if string-nets can describe more general topological phases. In this section we will discuss this more general string-net picture. (Actually, we will not discuss the most general string-net picture. We will focus on a special case for the sake of simplicity. See Appendix A for a discussion of the most general picture). 

We begin with a more detailed definition of “stringnets.” As the name suggests, string-nets are networks of strings. We will focus on trivalent networks where each node or branch point is attached to exactly 3 strings. The strings in a string-net are oriented and come in various “types.” Only certain combinations of string types are allowed to meet at a node or branch point. To specify a particular string-net model, one needs to provide the 

4 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0004-01.png)


**----- Start of picture text -----**<br>
k<br>i j<br>**----- End of picture text -----**<br>


FIG. 4: The orientation convention for the branching rules. 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0004-03.png)


**----- Start of picture text -----**<br>
=<br>i i*<br>**----- End of picture text -----**<br>


FIG. 5: i and i[∗] label strings with opposite orientations. 

following data: 

1. String types: The number of different string types N . For simplicity, we will label the different string types with the integers i = 1, ..., N . 

2. Branching rules: The set of all triplets of stringtypes {{i, j, k}...} that are allowed to meet at a point. (See Fig. 4). 

3. String orientations: The dual string type i[∗] associated with each string type i. The duality must satisfy (i[∗] )[∗] = i. The type-i[∗] string corresponds to the type-i string with the opposite orientation. If i = i[∗] , then the string is unoriented (See Fig. 5). 

This data describes the detailed structure of the stringnets. The Hilbert space of the string-net model is then defined in the natural way. The states in the Hilbert space are simply linear superpositions of different spatial configurations of string-nets. 

Once the Hilbert space has been specified, we can imagine writing down a string-net Hamiltonian. The string-net Hamiltonian can be any local operator which acts on quantum string-net states. A typical Hamiltonian is a sum of potential and kinetic energy pieces: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0004-11.png)


The kinetic energy Ht gives dynamics to the string-nets, while the potential energy HU is typically some kind of string tension. When U >> t, the string tension dominates and we expect the ground state to be the vacuum state with a few small string-nets. On the other hand, when t >> U , the kinetic energy dominates, and we expect the ground state to consist of many large fluctuating string-nets. We expect that there is a quantum phase transition between the two states at some t/U on the order of unity. (See Fig. 1). Because of the analogy with particle condensation, we say that the large t, highly fluctuating string-net phase is “string-net condensed.” 

This notion of string-net condensation provides a natural physical mechanism for the emergence of topological phases in real condensed matter systems. Local energetic constraints can cause the microscopic degrees of freedom to organize into effective extended objects or string-nets. If the kinetic energy of these string-nets is large, then they can condense giving rise to a topological phase. The type of topological phase is determined by the structure of the string-nets, and the form of string-net condensation. 

But how general is this picture? In the previous section, we pointed out that all deconfined gauge theories can be viewed as string-net condensates. In fact, mathematical results suggest that the string-net picture is even more general. In (2 + 1) dimensions, all so-called “doubled” topological phases can be described by string-net condensation (provided that we generalize the string-net picture as in Appendix A). [34] Physically, this means that the string-net picture can be applied to essentially all parity and time reversal invariant topological phases in (2+1) dimensions. Examples include all discrete gauge theories, and all doubled Chern-Simons theories. The situation for dimension d > 2 is less well understood. However, we know that string-net condensation quite generally describes all lattice gauge theories with or without emergent Fermi statistics. 

## IV. STRING-NET CONDENSATION IN (2 + 1) DIMENSIONS 

## A. Fixed-point wave functions 

In this section, we attempt to capture the universal features of string-net condensed phases in (2 + 1) dimensions. Our approach, inspired by Ref. [35–37, 42–44], is based on the string-net wave function. We construct a special “fixed-point” wave function for each string-net condensed phase. We believe that these “fixed-point” wave functions capture the universal properties of the corresponding phases. Each “fixed-point” wave function is associated with a six index object Flmn[ijk][that][satisfies] certain algebraic equations (8). In this way, we derive a one-to-one correspondence between doubled topological phases and tensor categories Flmn[ijk][.] We would like to mention that a related result on the classification of (2+1)D topological quantum field theories was obtained independently in the mathematical community. [34] 

Let us try to visualize the wave function of a string-net condensed state. Though we haven’t defined string-net condensation rigorously, we expect that a string-net condensed state is a superposition of many different stringnet configurations. Each string-net configuration has a size typically on the same order as the system size. The large size of the string-nets implies that a string-net condensed wave function has a non-trivial long distance structure. It is this long distance structure that distinguishes the condensed state from the “normal” state. 

In general, we expect that the universal features of a string-net condensed phase are contained in the long distance character of the wave functions. Imagine comparing two different string-net condensed states that belong to the same quantum phase. The two states will have different wave functions. However, by the standard RG reasoning, we expect that the two wave functions will look the same at long distances. That is, the two wave functions will only differ in short distance details - like those shown in Fig. 6. 

Continuing with this line of thought, we imagine performing an RG analysis on ground state functions. All 

5 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0005-01.png)


FIG. 6: Three pairs of string-net configurations that differ only in their short distance structure. We expect string-net wave functions in the same quantum phase to only differ by these short distance details. 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0005-03.png)


**----- Start of picture text -----**<br>
Φ a<br>Φ d<br>Φ b<br>Φ c<br>**----- End of picture text -----**<br>


FIG. 7: A schematic RG flow diagram for a string-net model with 4 string-net condensed phases a, b, c, and d. All the states in each phase flow to fixed-points in the long distance limit. The corresponding fixed-point wave functions Φa, Φb, Φc, and Φd capture the universal long distance features of the associated quantum phases. Our ansatz is that the fixedpoint wave functions Φ are described by local constraints of the form (4-7). 

the states in a string-net condensed phase should flow to some special “fixed-point” state. We expect that the wave function of this state captures the universal long distance features of the whole quantum phase. (See Fig. 7). 

In the following, we will construct these special fixedpoint wave functions. Suppose Φ is some fixed-point wave function. We know that Φ is the ground state of some fixed-point Hamiltonian H. Based on our experience with gauge theories, we expect that H is free. That is, H is a sum of local string kinetic energy terms with no string tension terms: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0005-07.png)


In particular, H is unfrustrated, and the ground state wave function minimizes the expectation values of all the kinetic energy terms {Hti} simultaneously. Minimizing the expectation value of an individual kinetic energy term Ht,i is equivalent to imposing a local constraint on the ground state wave function, namely Ht,i|Φ⟩ = Ei|Φ⟩ (where Ei is the smallest eigenvalue of Ht,i). We conclude that the wave function Φ can be specified uniquely by local constraint equations. The local constraints are linear relations between several string-net amplitudes Φ(X1), Φ(X2), Φ(X3)... where the configurations X1, X2, X3... only differ by local transformations. 

To derive these local constraints from first principles is difficult, so we will use a more heuristic approach. We will first guess the form of the local constraints (ie guess the form of the fixed-point wave function). Then, in the 

next section, we will construct the fixed-point Hamiltonian and show that its ground state wave function does indeed satisfy these local relations. Our ansatz is that the local constraints can be put in the following graphical form: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0005-11.png)


Here, i, j, k etc. are arbitrary string types and the shaded regions represent arbitrary string-net configurations. The di are complex numbers. The 6 index symbol Fkln[ijm][is][a][complex][numerical][constant][that][depends] on 6 string types i, j, m, k, l, and n. If one or more of the branchings {i, j, m}, {k, l, m[∗] }, {i, n, l}, {j, k, n[∗] } is illegal, the value of the symbol Fkln[ijm][is][unphysical.][How-] ever, for simplicity, we will set Fkln[ijm][= 0][in][this][case.] 

The local rules (4-7) are written using a new notational convention. According to this convention, the indices i, j, k etc., can take on the value i = 0 in addition to the N physical string types i = 1, ...N . We think of the i = 0 string as the “empty string” or “null string.” It represents empty space - the vacuum. Thus, we can convert labeled string-nets to our old convention by simply erasing all the i = 0 strings. The branching rules and dualities associated with i = 0 are defined in the obvious way: 0[∗] = 0, and {i, j, 0} is allowed if and only if i = j[∗] . Our convention serves two purposes: it simplifies notation (each equation in (4- 7) represents several equations with the old convention), and it reveals the mathematical framework underlying string-net condensation. 

We now briefly motivate these rules. The first rule (4) constrains the wave function Φ to be topologically invariant. It requires the quantum mechanical amplitude for a string-net configuration to only depend on the topology of the configuration: two configurations that can be continuously deformed into one another must have the same amplitude. The motivation for this constraint is our expectation that topological string-net phases have topologically invariant fixed-points. 

The second rule (5) is motivated by the fundamental property of RG fixed-points: scale invariance. The wave function Φ should look the same at all distance scales. Since a closed string disappears at length scales larger then the string size, the amplitude of an arbitrary stringnet configuration with a closed string should be proportional to the amplitude of the string-net configuration alone. 

The third rule (6) is similar. Since a “bubble” is irrelevant at long length scales, we expect 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0005-17.png)


6 

But if i ̸= j, the configuration i j is not allowed: Φ i j = 0. We conclude that the amplitude � � for the bubble configuration vanishes when i ̸= j (6). 

The last rule is less well-motivated. The main point is that the first three rules are not complete: another constraint is needed to specify the ground state wave function uniquely. The last rule (7) is the simplest local constraint with this property. An alternative motivation for this rule is the fusion algebra in conformal field theory.[45] 

The local rules (4-7) uniquely specify the fixed-point wave function Φ. The universal features of the string-net condensed state are captured by these rules. Equivalently, they are captured by the six index object Fkln[ijm][,] and the numbers di. 

However, not every choice of (Fkln[ijm][,][d][i][) corresponds to] a string-net condensed phase. In fact, a generic choice of (Fkln[ijm][,][d][i][)][will][lead][to][constraints][(4-7)][that][are][not] self-consistent. The only (Fkln[ijm][,][d][i][) that give rise][to][self-] consistent rules and a well-defined wave function Φ are (up to a trivial rescaling) those that satisfy 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0006-05.png)


where vi = vi∗ =[√] di (and v0 = 1). (See appendix B). Here, we have introduced a new object δijk defined by the branching rules: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0006-07.png)


There is a one-to-one correspondence between (2+1)D string-net condensed phases and solutions of (8). These solutions correspond to mathematical objects known as tensor categories. [32] Tensor category theory is the fundamental mathematical framework for string-net condensation, just as group theory is for particle condensation. We have just shown that it gives a complete classification of (2 + 1)D string-net condensed phases (or equivalently doubled topological phases): each phase is associated with a different solution to (8). We will show later that it also provides a convenient framework for deriving the physical properties of quasiparticles. 

It is highly non-trivial to find solutions of (8). However, it turns out each group G provides a solution. The solution is obtained by (a) letting the string-type index i run over the irreducible representations of the group, (b) letting the numbers di be the dimensions of the representations and (c) letting the 6 index object Fkln[ijm][be][the][6][j] symbol of the group. The low energy effective theory of the corresponding string-net condensed state turns out to be a deconfined gauge theory with gauge group G. Another class of solutions can be obtained from 6j symbols 

of quantum groups. It turns out that in these cases, the low energy effective theories of the corresponding stringnet condensed states are doubled Chern-Simons gauge theories. These two classes of solutions are not necessarily exhaustive: Eq. (8) may have solutions other then gauge theories or Chern-Simons theories. Nevertheless, it is clear that gauge bosons and gauge groups emerge from string-net condensation in a very natural way. 

In fact, string-net condensation provides a new perspective on gauge theory. Traditionally, we think of gauge theories geometrically. The gauge field Aµ is analogous to an affine connection, and the field strength Fµν is essentially a curvature tensor. From this point of view, gauge theory describes the dynamics of certain geometric objects (e.g. fiber bundles). The gauge group determines the structure of these objects and is introduced by hand as part of the basic definition of the theory. In contrast, according to the string-net condensation picture, the geometrical character of gauge theory is not fundamental. Gauge theories are fundamentally theories of extended objects. The gauge group and the geometrical gauge structure emerge dynamically at low energies and long distances. A string-net system “chooses” a particular gauge group, depending on the coupling constants in the underlying Hamiltonian: these parameters determine a string-net condensed phase which in turn determines a solution to (8). The nature of this solution determines the gauge group. 

One advantage of this alternative picture is that it unifies two seemingly unrelated phenomena: gauge interactions and Fermi statistics. Indeed, as we will show in section V, string-net condensation naturally gives rise to both gauge interactions and Fermi statistics (or fractional statistics in (2 + 1)D). In addition, these structures always appear together. [29] 

## B. Fixed-point Hamiltonians 

In this section, we construct exactly soluble lattice spin Hamiltonians with the fixed-point wave functions Φ as ground states. These Hamiltonians provide an explicit realization of all (2 + 1)D string-net condensates and therefore all (2 + 1)D doubled topological phases (provided that we generalize these models as discussed in Appendix A). In the next section, we will use them to calculate the physical properties of the quasiparticle excitations. 

For every (Fkln[ijm][, d][i][) satisfying the self-consistency con-] ditions (8) and the unitarity condition (14), we can construct an exactly soluble Hamiltonian. Let us first describe the Hilbert space of the exactly soluble model. The model is a spin system on a (2D) honeycomb lattice, with a spin located on each link of the lattice. Each “spin” can be in N + 1 different states labeled by i = 0, 1, ..., N . We assign each link an arbitrary orientation. When a spin is in state i, we think of the link as being occupied by a type-i string oriented in the appropriate direction. We think of the type-0 string or null string as the vacuum (ie no string on the link). 

7 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0007-01.png)


**----- Start of picture text -----**<br>
i<br>I i* i<br>i*<br>i* i k i*<br>k k<br>i k* k* i<br>j j<br>j<br>p j* j j*<br>j* j* j [j]<br>j*<br>**----- End of picture text -----**<br>


FIG. 8: A picture of the lattice spin model (10). The electric charge operator QI acts on the three spins adjacent to the vertex I, while the magnetic energy operator Bp acts on the 12 spins adjacent to the hexagonal plaquette p. The term QI constrains the string-nets to obey the branching rules, while Bp provides dynamics. A typical state satisfying the lowenergy constraints is shown on the right. The empty links have spins in the i = 0 state. 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0007-03.png)


Then the operators Bp[s][are][defined][by] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0007-05.png)


(See appendix C for a graphical representation of Bp[s][).] One can check that the Hamiltonian (10) is Hermitian if F 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0007-07.png)


The exactly soluble Hamiltonian for our model is given by 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0007-09.png)


where the sums run over vertices I and plaquettes p of the honeycomb lattice. The coefficients as satisfy as∗ = a[∗] s[but][are][otherwise][arbitrary.] 

Let us explain the terms in (10). We think of the first term QI as an electric charge operator. It measures the “electric charge” at site I, and favors states with no charge. It acts on the 3 spins adjacent to the site I: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0007-12.png)


where δijk is the branching rule symbol (9). Clearly, this term constrains the strings to obey the branching rules described by δijk. With this constraint the low energy Hilbert space is essentially the set of all allowed stringnet configurations on a honeycomb lattice. (See Fig. 8). 

We think of the second term Bp as a magnetic flux operator. It measures the “magnetic flux” though the plaquette p (or more precisely, the cosine of the magnetic flux) and favors states with no flux. This term provides dynamics for the string-net configurations. 

The magnetic flux operator Bp is a linear combination of (N +1) terms Bp[s][,][ s][ = 0][,][ 1][, ..., N][.][Each][ B] p[s][is an opera-] tor that acts on the 12 links that are adjacent to vertices of the hexagon p. (See Fig. 8). Thus, the Bp[s][are][essen-] tially (N +1)[12] ×(N +1)[12] matrices. However, the action of Bp[s][does not change the spin states on the 6 outer links] of p. Therefore the Bp[s][can][be][block][diagonalized][into] (N + 1)[6] blocks, each of dimension (N + 1)[6] × (N + 1)[6] . Let Bp[s,g] ,ghijkl[′][h][′][i][′][j][′][k][′][l][′] (abcdef ), with a, b, c... = 0, 1, ..., N , denote the matrix elements of these (N + 1)[6] matrices: 

in addition to (8). Our model is only applicable to topological phases satisfying this additional constraint. We believe that this is true much more generally: only topological phases satisfying the unitarity condition (14) are physically realizable. 

The Hamiltonian (10) has a number of interesting properties, provided that (Fkln[ijm][,][d][i][)][satisfy][the][self-] consistency conditions (8). It turns out that: 

1. The Bp[s][and][Q][I][’s][all][commute][with][each][other.] Thus the Hamiltonian (10) is exactly soluble. 

2. Depending on the choice of the coefficients as, the system can be in N + 1 different quantum phases. 

3. The choice as = � Nid=0s[d][2] i[corresponds][to][a][topolog-] ical phase with a smooth continuum limit. The ground state wave function for this parameter choice is topologically invariant, and obeys the local rules (4-7). It is precisely the wave function Φ, defined on a honeycomb lattice. Furthermore, QI , Bp are projection operators in this case. Thus, the ground state satisfies QI = Bp = 1 for all I, p, while the excited states violate these constraints. 

The Hamiltonian (10) with the above choice of as provides an exactly soluble realization of the doubled topological phase described by Fkln[ijm][.][We][can obtain some in-] tuition for the Hamiltonian (10) by considering the case where Fkln[ijm][is][the][6][j][symbol][of][some][group][G][.][In][this] case, it turns out that QI and Bp are precisely the electric charge and magnetic flux operators in the standard lattice gauge theory with group G. Thus, (10) is the usual Hamiltonian of lattice gauge theory, except with no electric field term. This is nothing more than the well-known exactly soluble Hamiltonian of lattice gauge theory. [20, 39] In this way, our construction can be viewed as a natural generalization of lattice gauge theory. 

8 

In this paper, we will focus on the smooth topological phase corresponding to the parameter choice as = Nds[appendix][C).] However, we would like to � i=0[d][2] i[(see] mention that the other N quantum phases also have nontrivial topological (or quantum) order. However, in these phases, the ground state wave function does not have a smooth continuum limit. Thus, these are new topological phases beyond those described by continuum theories. 

## C. Quasiparticle excitations 

In this section, we find the quasiparticle excitations of the string-net Hamiltonian (10), and calculate their statistics (e.g. the twists θα and the S matrix sαβ). We will only consider the topological phase with smooth continuum limit. That is, we will choose as = Nds � i=0[d][2] i[in our] lattice model. 

Recall that the ground state satisfies QI = Bp = 1 for all vertices I, and all plaquettes p. The quasiparticle excitations correspond to violations of these constraints for some local collection of vertices and plaquettes. We are interested in the topological properties (e.g. statistics) of these excitations. 

We will focus on topologically nontrivial quasiparticles - that is, particles with nontrivial statistics or mutual statistics. By the analysis in Ref. [29], we know that these types of particles are always created in pairs, and that their pair creation operator has a string-like structure, with the newly created particles appearing at the ends. (See Fig. 9). The position of this string operator is unobservable in the string-net condensed state - only the endpoints of the string are observable. Thus the two ends of the string behave like independent particles. 

If the two endpoints of the string coincide so that the string forms a loop, then the associated closed string operator commutes with the Hamiltonian. This follows from the fact that the string is truly unobservable; the action of an open string operator on the ground state depends only on its endpoints. 

Thus, each topologically nontrivial quasiparticle is associated with a (closed) string operator that commutes with the Hamiltonian. To find the quasiparticles, we need to find these closed string operators. 

An important class of string operators are what we will call “simple” string operators. The defining property of simple string operators is their action on the vacuum state. If we apply a type-s simple string operator W (P ) to the vacuum state, it creates a type-s string along the path of the string, P . We already have some examples of these operators, namely the magnetic flux operators Bp[s][.] When Bp[s][acts on the vacuum configuration][ |][0][⟩][, it creates] a type-s string along the boundary of the plaquette p. Thus, we can think of Bp[s][as][a][short type-][s][simple][string] operator, W (∂p). 

We would like to construct simple string operators W (P ) for arbitrary paths P = I1, ..., IN on the honeycomb lattice. Using the definition of Bp[s][as a guide,][we] make the following ansatz. The string operator W (P ) only changes the spin states along the path P . The ma- 

trix element of a general type-s simple string operator W (P ) between an initial spin state i1, ...iN and final spin state i[′] 1[, ...i][′] N[is][of][the][form] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0008-11.png)


where e1, ..., eN are the spin states of the N “legs” of P (see Fig. 9) and 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0008-13.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0008-14.png)


Here, ωj[i][,][ω][¯] j[i][are][two][(complex)][two][index][objects][that] characterize the string W . 

Note the similarity to the definition of Bp[s][.][The][major] difference is the additional factor[�][N] k=1[ω][k][.][We][conjec-] ture that |ωi[j] vvivj s[|][=][1][for][a][type-][s][string,][so][�][N] k=1[ω][k] is simply a phase factor that depends on the initial and final spin states i1, i2, ..., iN , i[′] 1[,][i][′] 2[,][...,][i][′] N[.][This][phase] vanishes for paths P that make only left or only right turns, such as plaquette boundaries ∂p. In that case, the definition of W (P ) coincides with Bp[s][.] 

A straightforward calculation shows that the operator W (P ) defined above commutes with the Hamiltonian (10) if ωj[i][,][ ¯][ω] j[i][satisfy] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0008-18.png)


The solutions to these equations give all the type-s simple string operators. 

For example, consider the case of Abelian gauge theory. In this case, the solutions to (18) can be divided into three classes. The first class is given by s = 0, ωi[j] vvivj s = ω¯i[j] vvivj s = 1. These string operators create electric flux lines and the associated quasiparticles are electric charges. In more traditional nomenclature, these are known as (Wegner-)Wilson loop operators [39, 46]. The second class of solutions is given by s = 0, and ωi[j] vvivj s = (¯ωi[j] vvivj s[)][∗][=][1.] These string operators create magnetic flux lines and the associated quasiparticles are magnetic fluxes. The third class has s = 0 and ωi[j] vvivj s = (¯ωi[j] vvivj s[)][∗][=][1.][These][strings][create][both][elec-] tric and magnetic flux and the associated quasiparticles are electric charge/magnetic flux bound states. This accounts for all the quasiparticles in (2+1)D Abelian gauge theory. Therefore, all the string operators are simple in this case. 

9 

However, this is not true for non-Abelian gauge theory or other (2 + 1)D topological phases. To compute the quasiparticle spectrum of these more general theories, we need to generalize the expression (15) for W (P ) to include string operators that are not simple. 

One way to guess the more general expression for W (P ) is to consider products of simple string operators. Clearly, if W1(P ) and W2(P ) commute with the Hamiltonian, then W (P ) = W1(P )·W2(P ) also commutes with the Hamiltonian. Thus, we can obtain other string operators by taking products of simple string operators. In general, the resulting operators are not simple. If W1 and W2 are type-s1 and type-s2 simple string operators, then the action of the product string on the vacuum state is: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0009-03.png)


where |s⟩ denotes the string state with a type-s string along the path P and the vacuum everywhere else. If we take products of more then two simple string operators then the action of the product string on the vacuum is of the form W (P )|0⟩ =[�] s[n][s][|][s][⟩][where][ n][s][are some non-] negative integers. 

We now generalize the expression for W (P ) so that it includes arbitrary products of simple strings. Let W be a product of simple string operators, and let ns be the non-negative integers characterizing the action of W on the vacuum: W (P )|0⟩ =[�] s[n][s][|][s][⟩][.][Then,][one][can][show] that the matrix elements of W (P ) are always of the form 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0009-06.png)


where 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0009-08.png)


and Ω[i] stj[,¯Ω][i] stj[are][two][4][index][objects][that][characterize] the string operator W . For any quadruple of string types i, j, s, t, (Ω[i] stj[,][¯Ω][i] stj[)][are][(complex)][rectangular][matrices] of dimension ns × nt. Note that type-s0 simple string operators correspond to the special case where ns = δs0s. In this case, the matrices Ω[i] stj[,][ ¯Ω][i] stj[reduce][to][complex] numbers, and we can identify 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0009-10.png)


As we mentioned above, products of simple string operators are always of the form (19). In fact, we believe that all string operators are of this form. Thus, we will use (19) as an ansatz for general string operators in (2 + 1)D topological phases. This ansatz is complicated algebraically, but like the definition of Bp[s][,][it][has][a] simple graphical interpretation (see appendix D). 

A straightforward calculation shows that the closed string W (P ) commutes with the Hamiltonian (10) if Ω 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0009-13.png)


**----- Start of picture text -----**<br>
e 3 i 2 e 2<br>i 3 I 3 I 2 i 1<br>I 4 I 1 W(P)<br>e 4 e 1<br>**----- End of picture text -----**<br>



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0009-14.png)


FIG. 9: Open and closed string operators for the lattice spin model (10). Open string operators create quasiparticles at the two ends, as shown on the left. Closed string operators, as shown on the right, commute with the Hamiltonian. The closed string operator W (P ) only acts nontrivially on the spins along the path P = I1, I2... (thick line), but its action depends on the spin states on the legs (thin lines). The matrix element between an initial state i1, i2, ... and a final state i[′] 1[, i][′] 2[, ...][is][W] ii1[′] 1i[i] 2[′] 2...[...][(][e][1][e][2][...][)][=] (Fse[∗] 2ii[′] 1[∗] 2[i][i][′∗] 2[1][F] se[∗] 3ii[′] 2[∗] 3[i][i][′∗] 3[2][...][)][·][ (] viv1i v′1s1 ωii1[′] 1 viv3i v′3s3 ω¯ii3[′] 3[...][)][for][a][type-][s][sim-] i[′] 1[i][′] 2[...] e2i[∗] 2[i][1] e3i[∗] 3[i][2] ple string and Wi1i2...[(][e][1][e][2][...][)][=][�] {sk }[(][F] s[∗] 2[i][′] 1[i][′∗] 2[F] s[∗] 3[i] 2[′][i][′∗] 3[...][)][·] Tr( viv1i v′1s1 Ωis[′] 11s2i1[δ][s] 2[s] 3[Id] viv3i v′3s3 ¯Ωis[′] 33s4i3[...][)][for][a][general][string.] 

and Ωsatisfy[¯] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0009-17.png)


The solutions (Ωm, Ω[¯] m) to these equations give all the different closed string operators Wm. However, not all of these solutions are really distinct. Notice that two solutions (Ω1, Ω[¯] 1), (Ω2, Ω[¯] 2) can be combined to form a new solution (Ω[′] , Ω[¯][′] ): 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0009-19.png)


This is not surprising: the string operator W[′] corresponding to (Ω[′] , Ω[¯][′] ) is simply the sum of the two operators corresponding to (Ω1,2, Ω[¯] 1,2): W[′] = W1 + W2. Given this additivity property, it is natural to consider the “irreducible” solutions (Ωα, Ω[¯] α) that cannot be written as a sum of two other solutions. Only the “irreducible” string operators Wα create quasiparticle-pairs in the usual sense. Reducible string operators W create superpositions of different strings - which correspond to superpositions of different quasiparticles. [51] 

To analyze a topological phase, one only needs to find the irreducible solutions (Ωα, Ω[¯] α) to (22). The number M of such solutions is always finite. In general, each solution corresponds to an irreducible representation of an algebraic object. In the case of lattice gauge theory, there 

10 

is one solution for every irreducible representation of the quantum double D(G) of the gauge group G. Similarly, in the case of doubled Chern-Simons theories there is one solution for each irreducible representation of a doubled quantum group. 

The structure of these irreducible string operators Wα determines all the universal features of the topological phase. The number M of irreducible string operators is the number of different kinds of quasiparticles. The fusion rules WαWβ =[�][M] γ=1[h][γ] αβ[W][γ][determine][how][bound] states of type-α and type-β quasiparticles can be viewed as a superposition of other types of quasiparticles. 

The topological properties of the quasiparticles are also easy to compute. As an example, we now derive two particularly fundamental objects that characterize the spins and statistics of quasiparticles: the M twists θα and the M × M S-matrix, sαβ [13, 25, 35, 47]. 

The twists θα are defined to be statistical angles of the type-α quasiparticles. By the spin-statistics theorem they are closely connected to the quasiparticle spins sα: e[iθ][α] = e[2][πis][α] . We can calculate θα by comparing the quantum mechanical amplitude for the following two processes. In the first process, we create a pair of quasiparticles α, ¯α (from the ground state), exchange them, and then annihilate the pair. In the second process, we create and then annihilate the pair without any exchange. The ratio of the amplitudes for these two processes is precisely e[iθ][α] . 

The amplitude for each process is given by the expectation value of the closed string operator Wα for a particular path P : 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0010-06.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0010-07.png)


Here, |Φ⟩ denotes the ground state of the Hamiltonian (10). 

Let (Ωα, Ω[¯] α, nα) be the irreducible solution corresponding to the string operator Wα. The above two amplitudes can be then be expressed in terms of (Ωα, Ω[¯] α, nα) (see appendix D): 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0010-10.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0010-11.png)


Combining these results, we find that the twists are given by 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0010-13.png)


Just as the twists θα are related to the spin and statistics of individual particle types α, the elements of the S-matrix, sαβ describe the mutual statistics of two particle types α, β. Consider the following process: We create two pairs of quasiparticles α, ¯α, β, β[¯] , braid α around β, and then annihilate the two pairs. The element sαβ is 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0010-15.png)


FIG. 10: A three dimensional trivalent lattice, obtained by splitting the sites of the cubic lattice. We replace each vertex of the cubic lattice with 4 other vertices as shown above. 

defined to be the quantum mechanical amplitude A of this process, divided by a proportionality factor D where D[2] =[�] α[(][�] s[n][α,s][d][s][)][2][.] The amplitude A can be calculated from the expectation value of Wα, Wβ for two “linked” paths P : 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0010-18.png)


Expressing A in terms of (Ωα, Ω[¯] α, nα), we find 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0010-20.png)


## V. STRING-NET CONDENSATION IN (3 + 1) AND HIGHER DIMENSIONS 

In this section, we generalize our results to (3 + 1) and higher dimensions. We find that there is a one-to-one correspondence between (3+1) (and higher) dimensional string-net condensates and mathematical objects known as “symmetric tensor categories.” [32] The low energy effective theories for these states are gauge theories coupled to bosonic or fermionic charges. 

Our approach is based on the exactly soluble lattice spin Hamiltonian (10). In that model, the spins live on the links of the honeycomb lattice. However, the choice of lattice was somewhat arbitrary: we could equally well have chosen any trivalent lattice in two dimensions. 

Trivalent lattices can also be constructed in three and higher dimensions. For example, we can create a spacefilling trivalent lattice in three dimensions, by “splitting” the sites of the cubic lattice (see Fig. 10). Consider the spin Hamiltonian (10) for this lattice, where I runs over all the vertices of the lattice, and p runs over all the “plaquettes” (that is, the closed loops that correspond to plaquettes in the original cubic lattice). 

This model is a natural candidate for string-net condensation in three dimensions. Unfortunately, it turns out that the Hamiltonian (10) is not exactly soluble on this lattice. The magnetic flux operators Bp[s][do not com-] mute in general. 

This lack of commutativity originates from two differences between the plaquettes in the honeycomb lattice and in higher dimensional trivalent lattices. The first 

11 

difference is that in the honeycomb lattice, neighboring plaquettes always share precisely two vertices, while in higher dimensions the boundary between plaquettes can contain three or more vertices (see Fig. 11). The existence of these interior vertices has the following consequence. Imagine we choose orientation conventions for each vertex, so that we have a notion of “left turns” and “right turns” for oriented paths on our lattice (such an orientation convention can be obtained by projecting the 3D lattice onto a 2D plane - as in Fig. 11). Then, no matter how we assign these orientations the plaquette boundaries will always make both left and right turns. Thus, we cannot regard the boundaries of the 3D plaquettes as small closed strings the way we did in two dimensions (since small closed strings always make all left turns, or all right turns). But the magnetic flux operators Bp[s][only][commute][if][their][boundaries][are][small] closed strings. It is this inconsistency between the algebraic definition of Bp[s][and the][topology of][the][plaquettes] that leads to the lack of commutativity. 

To resolve this problem, we need to define a Hamiltonian using the general simple string operators W (∂p) rather then the small closed strings Bp[s][.] Suppose (ωsj[i][,][ ¯][ω] sj[i][),][s][=][0][,][ 1][, ...N][are][type-][s][solutions][of][(18).][Af-] ter picking some “left turn”, “right turn” orientation convention at each vertex, we can define the corresponding type-s simple string operators Ws(P ) as in (15). Suppose, in addition, that we choose (ωsj[i][,][ ¯][ω] sj[i][)][so][that][the] string operators satisfy Wr · Ws =[�] t[δ][rst][W][t][(this][prop-] erty ensures that Ws(∂p) are analogous to Bp[s][).][Then,][a] natural higher dimensional generalization of the Hamiltonian (10) is 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0011-03.png)


For a two dimensional lattice, the conditions (18) are sufficient to guarantee that the Hamiltonian (31) is an exactly soluble realization of a doubled topological phase. (This is because the plaquette boundaries ∂p are not linked and hence the Ws(∂p) all commute). However, in higher dimensions, one additional constraint is necessary. 

This constraint stems from the second, and perhaps more fundamental, difference between 2D and higher dimensional lattices. In two dimensions, two closed curves always intersect an even number of times. For higher dimensional lattices, this is not the case. Small closed curves, in particular plaquette boundaries, can (in a sense) intersect exactly once (see Fig. 11). Because of this, the objects ωjk[i][must satisfy][the][additional relation:] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0011-06.png)


One can show that if this additional constraint is satisfied, then (a) the higher dimensional Hamiltonian (31) is exactly soluble, and (b) the ground state wave function Φ is defined by local topological rules analogous to (4-7). This means that (31) provides an exactly soluble realization of topological phases in (3 + 1) and higher dimensions. 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0011-08.png)


**----- Start of picture text -----**<br>
I 4 I 3<br>p 3<br>p 2<br>p 1<br>I 2<br>z<br>I 1<br>y<br>x<br>**----- End of picture text -----**<br>


FIG. 11: Three plaquettes demonstrating the two fundamental differences between higher dimensional trivalent lattices and the honeycomb lattice. The plaquettes p1, p2 lie in the xz plane, while p3 is oriented in the xy direction. Notice that p1 and p2 share three vertices, I1, I2, I3. Also, notice that the plaquette boundaries ∂p1 and ∂p3 intersect only at the line segment I3I4. The boundary ∂p1 makes a left turn at I3, and a right turn at I4. Thus, viewed from far away, these two plaquette boundaries intersect exactly once (unlike the pair ∂p1 and ∂p2). 

Each exactly soluble Hamiltonian is associated with a solution (Fkln[ijm][, ω] jk[i][,][ ¯][ω] jk[i][)][of][(8),][(18),][(32).][By][analogy] with the two dimensional case, we conjecture that there is a one-to-one correspondence between topological stringnet condensed phases in (3 + 1) or higher dimensions, and these solutions. The solutions (Fkln[ijm][, ω] jk[i][,][ ¯][ω] jk[i][)][cor-] respond to a special class of tensor categories - symmetric tensor categories. [32] Thus, just as tensor categories are the mathematical objects underlying string condensation in (2+1) dimensions, symmetric tensor categories are fundamental to string condensation in higher dimensions. There are relatively few solutions to (8), (18), (32). Physically, this is a consequence of the restrictions on quasiparticle statistics in 3 or higher dimensions. Unlike in two dimensions, higher dimensional quasiparticles necessarily have trivial mutual statistics, and must be either bosonic or fermionic. From a more mathematical point of view, the scarcity of solutions is a result of the symmetry condition (32). Doubled topological phases, such as Chern-Simons theories, typically fail to satisfy this condition. 

However, gauge theories do satisfy the symmetry condition (32) and therefore do correspond to higher dimensional string-net condensates. Recall that the gauge theory solution to (8) is obtained by (a) letting the stringtype index i run over the irreducible representations of the gauge group, (b) letting the numbers di be the dimensions of the representations, and (c) letting the 6 index object Fkln[ijm] be the 6j symbol of the group. One can check that this also provides a solution to (18), (32), if we set ωjk[i] vjvvi k = −1 when j = k and the invariant tensor in k ⊗ k ⊗ i[∗] is antisymmetric in the first two indices, and ωjk[i] vjvvi k = 1 otherwise. This result is to be expected, since the string-net picture of gauge theory (section II) 

12 

is valid in any number of dimensions. Thus, it is not surprising that gauge theories can emerge from higher dimensional string-net condensation. 

There is another class of higher dimensional stringnet condensed phases that is more interesting. The low energy effective theories for these phases are variants of gauge theories. Mathematically, they are obtained by twisting the usual gauge theory solution by 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0012-03.png)


Here P (i) is some assignment of parity (“even”, or “odd”) to each representation i. The assignment must be selfconsistent in the sense that the tensor product of two representations with the same (different) parity, decomposes into purely even (odd) representations. If all the representations are assigned an even parity - that is P (i) is trivial - then the twisted gauge theory reduces to standard gauge theory. 

The major physical distinction between twisted gauge theories and standard gauge theories is the quasiparticle spectrum. In standard gauge theory, the fundamental quasiparticles are the electric charges created by the N + 1 string operators Wi. These quasiparticles are all bosonic. In contrast, in twisted gauge theories, all the quasiparticles corresponding to “odd” representations i are fermionic. 

In this way, higher dimensional string-net condensation naturally gives rise to both emerging gauge bosons and emerging fermions. This feature suggests that gauge interactions and Fermi statistics may be intimately connected. The string-net picture may be the bridge between these two seemingly unrelated phenomena. [29] 

In fact, it appears that gauge theories coupled to fermionic or bosonic charged particles are the only possibilities for higher dimensional string-net condensates: mathematical work on symmetric tensor categories suggests that the only solutions to (8), (18), (32) are those corresponding to gauge theories and twisted gauge theories. [48] 

We would like to point out that (3 + 1) dimensional string-net condensed states also exhibit membrane condensation. These membrane operators are entirely analogous to the string operators. Just as open string operators create charges at their two ends, open membrane operators create magnetic flux loops along their boundaries. Furthermore, just as string condensation makes the string unobservable, membrane condensation leads to the unobservability of the membrane. Only the boundary of the membrane - the magnetic flux loop - is observable. 

## VI. EXAMPLES 

## A. N = 1 string model 

We begin with the simplest string-net model. In the notation from section III, this model is given by 

1. Number of string types: N = 1 

2. Branching rules: ∅ (no branching) 

## 3. String orientations: 1[∗] = 1. 

In other words, the string-nets in this model contain one unoriented string type and have no branching. Thus, they are simply closed loops. (See Fig. 3a). 

We would like to find the different topological phases that can emerge from these closed loops. According to the discussion in section IV, each phase is captured by a fixed-point wave function, and each fixed-point wave function is specified by local rules (4-7) that satisfy the self-consistency relations (8). It turns out that (8) have only two solutions in this case (up to rescaling): 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0012-17.png)


where the other elements of F all vanish. The corresponding local rules (4-7) are: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0012-19.png)


We have omitted those rules that can be derived from topological invariance (4). 

The fixed-point wave functions Φ± satisfying these rules are given by 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0012-22.png)


where Xc is the number of disconnected components in the string configuration X. 

The two fixed-point wave functions Φ± correspond to two simple topological phases. As we will see, Φ+ corresponds to Z2 gauge theory, while Φ− is a U (1) × U (1) Chern-Simons theory. (Actually, other topological phases can emerge from closed loops - such as in Ref. [42– 44]. However, we regard these phases as emerging from more complicated string-nets. The closed loops organize into these effective string-nets in the infrared limit). 

The exactly soluble models (10) realizing these two phases can be written as spin 1/2 systems with one spin on each link of the honeycomb lattice (see Fig. 12). We regard a link with σ[x] = −1 as being occupied by a type-1 string, and the state σ[x] = +1 as being unoccupied (or equivalently, occupied by a type-0 or null string). The Hamiltonians for the two phases are of the form 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0012-26.png)


The electric charge term is the same for both phases (since it only depends on the branching rules): 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0012-28.png)


13 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0013-01.png)


**----- Start of picture text -----**<br>
R-leg<br>σ [x] I σ [x]<br>σ   =−1 x<br>σ [x] σ   =−1 x σ   =−1 x L-vertex<br>i<br>f(    ) σ [x] σ   =−1 x σ   =−1 x j I<br>f(    ) σ [x] σ [z] σ   =−1 x<br>σ [z] σ [z] f(    ) σ [x] P<br>p<br>f(    ) σ [x] σ [z]<br>σ [z] σ [z] f(    ) σ [x]<br>f(    ) σ [x]<br>**----- End of picture text -----**<br>


FIG. 12: The Hamiltonians (39), (40), realizing the two N = 1 string-condensed phases. Each circle denotes a spin-1/2 spin. The links with σ[x] = −1 are thought of as being occupied by a type-1 string, while the links with σ[x] = +1 are regarded as empty. The electric charge term acts on the three legs of the vertex I with σ[x] . The magnetic energy term acts on the 6 edges of the plaquette p with σ[z] , and acts on the 6 legs of p with an operator of the form f (σ[x] ). For the Z2 phase, f = 1, while for the Chern-Simons phase, f (x) = i[(1][−][x][)][/][2] . 

FIG. 13: A closed string operator W (P ) for the two models (39),(40). The path P is drawn with a thick line, while the legs are drawn with thin lines. The action of the string operators (41),(44) on the legs is different for legs that branch to the right of P , “R-legs”, and legs that branch to the left of P , “Llegs.” Similarly, we distinguish between “R-vertices” and “Lvertices” which are ends of “R-leg” and “L-leg” respectively. 

The other elements of Ωvanish. In all cases Ω=[¯] Ω. The corresponding string operators for a path P are 

The magnetic terms for the two phases are 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0013-06.png)


where Pp is the projection operator Pp =[�] I∈p[Q][I][.][The] projection operator Pp can be omitted without affecting the physics (or the exact solubility of the Hamiltonian). We have included it only to be consistent with (10). If we omit this term, the Hamiltonian for the first phase (Φ+) reduces to the usual exactly soluble Hamiltonian of Z2 lattice gauge theory (neglecting numerical factors): 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0013-08.png)


The Hamiltonian for the second phase, 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0013-10.png)


is less familiar. However, one can check that in both cases, the Hamiltonians are exactly soluble and the two ground state wave functions are precisely Φ± (in the σ[x] basis). 

Next we find the quasiparticle excitations for the two phases, and the corresponding S-matrix and twists θα. In both cases, equation (22) has 4 irreducible solutions (nα,s, Ω[ij] α,st[,][ ¯Ω][ij] α,st[),][α][ = 1][,][ 2][,][ 3][,][ 4][-][corresponding][to] 4 quasiparticle types. For the first phase (Φ+) these solutions are given by: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0013-13.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0013-14.png)


where the “R-legs” k are the legs that are to the right of P . (See Fig. 13). Technically, we should multiply these string operators by an additional projection operator[�] I∈P[Q][I][,][in][order][to][be][consistent][with][the][general] result (19). However, we will neglect this factor since it doesn’t affect the physics. 

Once we have the string operators, we can easily calculate the twists and the S-matrix. We 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0013-17.png)


This is in agreement with the twists and S-matrix for Z2 gauge theory: W1 creates trivial quasiparticles, W2 creates magnetic fluxes, W3 creates electric charges, W4 creates electric/magnetic bound states. 

In the second phase (Φ−), we find 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0013-20.png)


Once again, the other elements of Ωvanish. Also, in all cases, Ω= Ω[¯][∗] . The corresponding string operators for a 

14 

The string-nets are unoriented trivalent graphs. To find the topological phases that can emerge from these objects, we solve the self-consistency relations (8). We find two sets of self-consistent rules: 

path P are 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0014-03.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0014-04.png)


where the “L-vertices” I are the vertices of P adjacent to legs that are to the left of P . The exponent sI is defined by sI = 4[1][(1][ −][σ] i[x][)(1 +][ σ] j[x][),][where][i][,][j][are][the][links][just] before and just after the vertex I, along the path P . (See Fig. 13). 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0014-06.png)


We the twists and S-matrix are 

We see that W1 creates trivial quasiparticles, W2, W3 create semions with opposite chiralities and trivial mutual statistics, and W4 creates bosonic bound states of the semions. These results agree with the U (1) × U (1) Chern-Simons theory 

As before, the exactly soluble realization of this phase (10) is a spin-1/2 model with spins on the links of the honeycomb lattice. We regard a link with σ[x] = −1 as being occupied by a type-1 string, and a link with σ[x] = 1 as being unoccupied (or equivalently occupied by a type0 string). However, in this case we will not explicitly rewrite (10) in terms of Pauli matrices, since the resulting expression is quite complicated. 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0014-10.png)


with K-matrix 

We now find the quasiparticles. These correspond to irreducible solutions of (22). For this model, there are 4 such solutions, corresponding to 4 quasiparticles: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0014-13.png)


Thus the above U (1) × U (1) Chern-Simons theory is the low energy effective theory of the second exactly soluble model (with d1 = −1). 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0014-15.png)


Note that the Z2 gauge theory from the first exactly soluble model (with d1 = 1) can also be viewed as a U (1) × U (1) Chern-Simons theory with K-matrix [23] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0014-17.png)


## B. N = 1 string-net model 

In all cases, Ω= Ω[¯][∗] . 

The next simplest string-net model also contains only one oriented string type - but with branching. Simple as it is, we will see that this model contains non-Abelian anyons and is theoretically capable of universal fault tolerant quantum computation [33]. Formally, the model is defined by 

We can calculate the twists and the S-matrix. 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0014-22.png)


1. Number of string types: N = 1 

We conclude that W1 creates trivial quasiparticles, W2, W3 create (non-Abelian) anyons with opposite chiralities, and W4 creates bosonic bound states of the anyons. 

2. Branching rules: {{1, 1, 1}} 

3. String orientations: 1[∗] = 1. 

15 

These results agree with SO3(3) × SO3(3) Chern-Simons theory, the so-called doubled “Yang-Lee” theory. 

Researchers in the field of quantum computing have shown that the Yang-Lee theory can function as a universal quantum computer - via manipulation of non-Abelian anyons. [33] Therefore, the spin-1/2 Hamiltonian (10) associated with (50) is a theoretical realization of a universal quantum computer. While this Hamiltonian may be too complicated to be realized experimentally, the stringnet picture suggests that this problem can be overcome. Indeed, the string-net picture suggests that generic spin Hamiltonians with a trivalent graph structure will exhibit a Yang-Lee phase. Thus, much simpler spin-1/2 Hamiltonians may be capable of universal fault tolerant quantum computation. 

## C. N = 2 string-net models 

In this section, we discuss two N = 2 string-net models. The first model contains one oriented string and its dual. In the notation from section III, it is given by 

1. Number of string types: N = 2 

2. Branching rules: {{1, 1, 1}, {2, 2, 2}} 

3. String orientations: 1[∗] = 2, 2[∗] = 1. 

The string-nets are therefore oriented trivalent graphs with Z3 branching rules. The string-net condensed phases correspond to solutions of (8). Solving these equations, we find two sets of self-consistent local rules: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0015-09.png)


The corresponding fixed-point wave functions Φ± are given by 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0015-11.png)


where Xc, Xv, are the number of connected components, and vertices, respectively in the string-net configuration X. As before, we can construct an exactly soluble Hamiltonians, find the quasiparticles for the two theories and compute the twists and S-matrices. We find that the first theory Φ+ is described by a Z3 gauge theory, while the second theory Φ− is described by a U (1) × U (1) ChernSimons theory with K-matrix 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0015-13.png)


Both theories have 3[2] = 9 elementary quasiparticles. In the case of Z3, these quasiparticles are electric charge/magnetic flux bound states formed from the 3 types of electric charges and 3 types of magnetic fluxes. 

In the case of the Chern-Simons theory, the quasiparticles are bound states of the two fundamental anyons with statistical angles ±π/3. 

The final example we will discuss contains two unoriented strings. Formally it is given by 

1. Number of string types: N = 2 

2. Branching rules: {{1, 2, 2}, {2, 2, 2}} 

3. String orientations: 1[∗] = 1, 2[∗] = 2. 

The string-nets are unoriented trivalent graphs, with edges labeled with 1 or 2. We find that there is only one set of self-consistent local rules: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0015-21.png)


where d0 = d1 = 1, d2 = 2, and F22[22] n[m][is][the][matrix] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0015-23.png)


If we construct the Hamiltonian (10), we find that it is equivalent to the standard exactly lattice gauge theory Hamiltonian [20] with gauge group S3 - the permutation group on 3 objects. One can show that this theory contains 8 elementary quasiparticles (corresponding to the 8 irreducible representations of the quantum double D(S3)). These quasiparticles are combinations of the 3 electric charges and 3 magnetic fluxes. 

## VII. CONCLUSION 

In this paper, we have shown that quantum systems of extended objects naturally give rise to topological phases. These phases occur when the extended objects (e.g. string-nets) become highly fluctuating and condense. This physical picture provides a natural mechanism for the emergence of parity invariant topological phases. Microscopic degrees of freedoms (such as spins or dimers) can organize into effective extended objects which can then condense. We hope that this physical picture may help direct the search for topological phases in real condensed matter systems. It would be interesting to develop an analogous picture for chiral topological phases. 

16 

We have also found the fundamental mathematical framework for topological phases. We have shown that each (2 + 1) dimensional doubled topological phase is associated with a 6 index object Fkln[ijm] and a set of real numbers di satisfying the algebraic relations (8). All the universal properties of the topological phase are contained in these mathematical objects (known as tensor categories). In particular, the tensor category directly determines the quasiparticle statistics of the associated topological phase (28, 30). This mathematical framework may also have applications to phase transitions and critical phenomena. Tensor categories may characterize transitions between topological phases just as symmetry groups characterize transitions between ordered phases. 

We have constructed exactly soluble (2 + 1)D lattice spin Hamiltonians (10) realizing each of these doubled topological phases. These models unify (2 + 1)D lattice gauge theory and doubled Chern-Simons theory. One particular Hamiltonian - a realization of the doubled Yang-Lee theory - is a spin 1/2 model capable of fault tolerant quantum computation. 

In higher dimensions, string-nets can also give rise to topological phases. However, the physical and mathematical structure of these phases is more restricted. On a mathematical level, each higher dimensional string-net condensate is associated with a special kind of tensor category - a symmetric tensor category (18), (32). More physically, we have shown that higher dimensional stringnet condensation naturally gives rise to both gauge interactions and Fermi statistics. Viewed from this perspective, string-net condensation provides a mechanism for unifying gauge interactions and Fermi statistics. It may have applications to high energy physics [30]. 

From a more general point of view, all of the phases described by Landau’s symmetry breaking theory can be understood in terms of particle condensation. These phases are classified using group theory and lead to emergent gapless scalar bosons [49, 50], such as phonons, spin waves, etc . In this paper, we have shown that there is a much richer class of phase - arising from the condensation of extended objects. These phases are classified using tensor category theory and lead to emergence of Fermi statistics and gauge excitations. Clearly, there is whole new world beyond the paradigm of symmetry breaking and long range order. It is a virgin land waiting to be explored. 

We would like to thank Pavel Etingof and Michael Freedman for useful discussions of the mathematical aspects of topological field theory. This research is supported by NSF Grant No. DMR–01–23156 and by NSFMRSEC Grant No. DMR–02–13282. 

## APPENDIX A: GENERAL STRING-NET MODELS 

In this section, we discuss the most general string-net models. These models can describe all doubled topological phases, including all discrete gauge theories and doubled Chern-Simons theories. 

In these models, there is a “spin” degree of freedom at each branch point or node of a string-net, in addition to the usual string-net degrees of freedom. The dimension of this “spin” Hilbert space depends on the string types of the 3 strings incident on the node. 

To specify a particular model one needs to provide a 3 index tensor δijk which gives the dimension of the spin Hilbert space associated with {i, j, k} (in addition to the usual information). The string-net models discussed above correspond to the special case where δijk = 0, 1 for all i, j, k. In the case of gauge theory, δijk is the number of copies of the trivial representation that appear in the tensor product i ⊗ j ⊗ k. Thus we need the more general string-net picture to describe gauge theories where the trivial representation appears multiple times in i ⊗ j ⊗ k. 

The Hilbert space of the string-net model is defined in the natural way: the states in the string-net Hilbert space are linear superpositions of different spatial configurations of string-nets with different spin states at the nodes. 

One can analyze string-net condensed phases as before. The universal properties of each phase are captured by a fixed-point ground state wave function Φ. The wave function Φ is specified by the local rules (4), (5) and simple modifications of (6), (7): 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0016-12.png)


The complex numerical constant Fkln[ijm][is][now][a][complex] tensor (Fkln[ijm][)][στ] µν[of dimension][ δ][ijm][×][ δ][klm][∗][×][ δ][inl][×][ δ][jkn][∗][.] 

One can proceed as before, with self-consistency conditions, fixed-point Hamiltonians, string operators, and the generalization to (3+1) dimensions. The exactly soluble models are similar to (10). The main difference is the existence of an additional spin degree of freedom at each site of the honeycomb lattice. These spins account for the degrees of freedom at the nodes of the string-nets. 

## APPENDIX B: SELF-CONSISTENCY CONDITIONS 

In this section, we derive the self-consistency conditions (8). We begin with the last relation, the so-called “pentagon identity”, since it is the most fundamental. To derive this condition, we use the fusion rule (7) j k l to relate the amplitude Φ p q to the amplitude � i m � j k l Φ r s in two distinct ways (see Fig. 14). On the � i m � one hand, we can apply the fusion rule (7) twice to obtain 

17 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-01.png)


**----- Start of picture text -----**<br>
k k k<br>j l j l j l<br>p q q<br>r r s<br>i m i m i m<br>(a) (b) (c)<br>k k<br>j l j n l<br>n s<br>p<br>i m i m<br>(d) (e)<br>**----- End of picture text -----**<br>


FIG. 14: The fusion rule (7) can be used to relate the amplitude of (a) to the amplitude of (c) in two different ways. On the one hand, we can apply the fusion rule (7) twice - along the links denoted by solid arrows - to relate (a) → (b) → (c). But we can also apply (7) three times - along the links denoted by dashed arrows - to relate (a) → (d) → (e) → (c). Self-consistency requires that the two sequences of the operation lead to the same linear relations between the amplitudes of (a) and (c). 

the relation 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-04.png)


(Here, we neglected to draw a shaded region surrounding the whole diagram. Just as in the local rules (4-7) the ends of the strings i, j, k, l, m are connected to some arbitrary string-net configuration). But we can also apply the fusion rule (7) three times to obtain a different relation: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-06.png)


If the rules are self-consistent, then these two relations must agree with each other. Thus, the two coefficients j k l of Φ r s must be the same. This equality implies � i m � the pentagon identity (8). 

The first two relations in (8) are less fundamental. In fact, the first relation is not required by self-consistency at all; it is simply a useful convention. To see this, consider the following rescaling transformation on wave functions Φ → Φ.[˜] Given a string-net wave function Φ, we can obtain a new wave function Φ[˜] by multiplying the amplitude Φ(X) for a string-net configuration X by an arbitrary factor f (i, j, k) for each vertex {i, j, k} in X. As long as f (i, j, k) is symmetric in i, j, k and f (0, i, i[∗] ) = 1, 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-09.png)


**----- Start of picture text -----**<br>
i l j i<br>n l n i n k l n<br>j m k m i m m j<br>k j l k<br>(a) (b) (c) (d)<br>**----- End of picture text -----**<br>


FIG. 15: Four string-net configurations related by tetrahedral symmetry. In diagram (a), we show the tetrahedron corresponding to G[ijm] kln[.][In][diagrams][(b),][(c),(d),][we][show][the] tetrahedrons G[lkm] jin[∗][,][G][jim] lkn[∗][,][G][imj] k[∗] nl[,][obtained][by][reflecting][(a)] in 3 different planes: the plane joining n to the center of m, the plane joining m to the center of n, and the plane joining i to the center of k. The four tetrahedrons correspond to the four terms in the second relation of (8). 

this operation preserves the topological invariance of Φ. The rescaled wave function Φ[˜] satisfies the same set of local rules with rescaled Fkln[ijm][:] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-12.png)


Since Φ and Φ[˜] describe the same quantum phase, we regard F and F[˜] as equivalent local rules. Thus the first relation in (8) is simply a normalization convention for F or Φ (except when i, j or k vanishes; these cases require an argument similar to the derivation of the pentagon identity). 

The second relation in (8) has more content. This relation can be derived by computing the amplitude for a tetrahedral string-net configuration. We have: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-15.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-16.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-17.png)


We define the above combination in the front of Φ(∅) as: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0017-19.png)


Imagine that the above string-net configuration lies on a sphere. In that case, topological invariance (together with parity invariance) requires that G[ijm] kln[be][invariant] under all 24 symmetries of a regular tetrahedron. The second relation in (8) is simply a statement of this tetrahedral symmetry requirement - written in terms of Fkln[ijm][.] (See Fig. 15). 

In this section, we have shown that the relations (8) are necessary for self-consistency. It turns out that these relations are also sufficient. One way of proving this is to use the lattice model (10). A straightforward algebraic calculation shows that the ground state of 10 obeys the local rules (4-7), as long as (8) is satisfied. This establishes that the local rules are self-consistent. 

18 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0018-01.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0018-02.png)


**----- Start of picture text -----**<br>
(a) (b)<br>**----- End of picture text -----**<br>


FIG. 16: The fattened honeycomb lattice. The strings are forbidden in the shaded region. A string state in the fattened honeycomb lattice (a) can be viewed as a superposition of string states on the links (b). 

and those in the unfattened lattice: |X⟩ =[�] ai|Xi⟩. This linear relation is independent of the particular way in which the local rules (4-7) are applied, as long as the rules are self-consistent. 

In this way, the fattened honeycomb lattice provides an alternative notation for representing the states in the Hilbert space of (10). This notation is useful because the magnetic energy operators Bp[s][are simple][in][this][rep-] resentation. Indeed, the action of the operator Bp[s][on] 

b h c g i the string-net state a d is equivalent to simply ��� l j � f k e 

adding a loop of type-s string: 

## APPENDIX C: GRAPHICAL REPRESENTATION OF THE HAMILTONIAN 

In this section, we provide an alternative, graphical, representation of the lattice model (10). This graphical representation provides a simple visual technique for understanding properties (a)-(c) of the Hamiltonian (10). 

We begin with the 2D honeycomb lattice. Imagine we fatten the links of the lattice into stripes of finite width (see Fig. 16). Then, any string-net state in the fattened honeycomb lattice (Fig. 16a) can be viewed as a superposition of string-net states in the original, unfattened lattice (Fig. 16b). This mapping is obtained via the local rules (4-7). Using these rules, we can relate the amplitude Φ(X) for a string-net in the fattened lattice to a linear combination of string-net amplitudes in the original lattice: Φ(X) =[�] aiΦ(Xi). This provides a natural linear relation between the states in the fattened lattice 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0018-11.png)


As we described above, we can use the local rules (4-7) b h c g i to rewrite a s d as a linear combination of the ��� l j � f k e 

physical string-net states with strings only on the links, that is to reduce Fig. 17a to Fig. 17b. This allows us to obtain the matrix elements of B[s] p[.] 

The following is a particular way to implement the above procedure: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0018-15.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0018-16.png)


Notice that (C1) is exactly (13). Thus, the graphical representation of Bp[s][agrees][with][the][original][algebraic] 

Using the graphical representation of Bp[s][we][can][eas-] ily show that Bp[s][1] 1[and][B] p[s][2] 2[commute.] The derivation 

is much simpler then the more straightforward algebraic calculation. First note that these operators will commute if p1, p2 are well-separated. Thus, we only have to consider the case where p1 and p2 are adjacent, or the case where p1, p2 coincide. We begin with the nearest neigh- 

19 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-01.png)


**----- Start of picture text -----**<br>
b c b c<br>h h’<br>g i g’ i’<br>a s d a d<br>l j l’ j’<br>k k’<br>(a) f e (b) f e<br>**----- End of picture text -----**<br>


FIG. 17: The action of Bp[s][is][equivalent][to][adding][a][loop][of] type-s string. The resulting string-net state (a) is actually a linear combination of the string-net states (b). The coefficients in this linear relation can be obtained by using the local rules (4-7) to reduce (a) to (b). 

bor case. The action of B[s][1][the][string-net][state] p1[B] p[s][2] 2[on] Fig. 18a can be represented as Fig. 18b. Fig. 18b can then be related to a linear combination of the string-net states shown in Fig. 18c. The coefficients in this relation are the matrix elements of B[s][1][But][by][the][same][ar-] p1[B] p[s][2] 2[.] gument, the action of Bp[s][2] 2[B] p[s][1] 1[can also be represented by] Fig. 18b. We conclude that Bp[s][2] 2[B] p[s][1] 1[,][B] p[s][1] 1[B] p[s][2] 2[have][the] same matrix elements. Thus, the two operators commute in this case. 

On the other hand, when p1 = p2, we have 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-05.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-06.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-07.png)


Thus, 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-09.png)


Since δk∗s2s1 is symmetric in s2, s1, we conclude that Bp[s][1][B] p[s][2][=][ B] p[s][2][B] p[s][1][, so the operators commute in this case] as well. This establishes property (a) of the Hamiltonian (10). Equation (C3) also sheds light on the spectrum of the Bp[s][operators.][Let][the][simultaneous][eigenvalues][of][B] p[s] (with p fixed) be {b[s] q[}][.][Then,][by][(C3)][these][eigenvalues] satisfy 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-11.png)


**----- Start of picture text -----**<br>
b c b c b c<br>a i j k l d a i j k l d a i’ j’ k’ l’ d<br>r t m r s1 t s 2 m r’ t’ m’<br>h q p o n e h q p o n e h q’ p’ o’ n’ e<br>g f g f g f<br>(a) (b) (c)<br>**----- End of picture text -----**<br>


FIG. 18: The action of Bp[s][1] 1[B] p[s][2] 2[on][the][string-net][state][(a)] can be represented by adding two loops of type-s1 and types2 strings as shown in (b). The string-net state (b) is a linear combination of the string-net states (c). The coefficients are obtained by using (4 -7) to reduce (b) to (c). 

simultaneous eigenvalues b[s] q[2][are simply the simultaneous] eigenvalues of the matrices Ms2 . In particular, this means that the index q ranges over a set of size N + 1. 

Each value of q corresponds to a different possible state for the plaquette p. The magnetic energies of these N +1 different states are given by: Eq = −[�] s[a][s][b][s] q[.][Depend-] ing on the parameter choice as, all on the plaquettes p will be in one of these states q. In this way, the Hamiltonian (10) can be in N + 1 different quantum phase. This establishes property (b) of the Hamiltonian (10). 

One particular state q is particularly interesting. This state corresponds to the simultaneous eigenvalues b[s] = ds. It is not hard to show that the parameter choice as = �dks[d][2] k[makes][this][state][energetically][favorable.][In] fact, using (C3) one can show that Bp is a projector for this parameter choice, and that Bp = 1 for this state. 

Furthermore, the ground state wave function for this parameter choice obeys the local rules (4-7). One way to see this is to compare Bp i i with Bp i i . ��� � ��� � For the first state, we find 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-17.png)


For the second state, we find the same result: 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-19.png)


It follows that 

so 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-22.png)


We can view this as an eigenvalue equation for the (N + 1) × (N + 1) matrix Ms2 , defined by Ms[i] 2,j[=][ δ][j][∗][s] 2[i][.][The] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0019-24.png)


This result means that the strings can be moved through the forbidden regions at the center of the hexagons. 

20 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0020-01.png)


**----- Start of picture text -----**<br>
α<br>**----- End of picture text -----**<br>


FIG. 19: The action of the string operator Wα(P ) is equivalent to adding a type-α string along the path P . The resulting string-net state can be reduced to a linear combination of states on the honeycomb lattice, using the local rules (4-7), (D1). 

Thus, the local rules which were originally restricted to the fattened honeycomb lattice can be extended throughout the entire 2D plane. The wave function Φ obeys these continuum local rules and has a smooth continuum limit. We call such a state smooth topological state. This establishes property (c) of the Hamiltonian (10). 

The wave functions of some smooth topological states are positive definite. So those wave functions can be viewed as the statistical weights of certain statistical models in the same spatial dimensions. What is interesting is that those statistical models are local models with short-ranged interactions [10, 35, 36]. 

## APPENDIX D: GRAPHICAL REPRESENTATION OF THE STRING OPERATORS 

In this section, we describe a graphical representation of the long string operators Wα(P ). Just as in the previous section, this representation involves the fattened honeycomb lattice. The action of the string operator Wα(P ) on a general string state X, is simply to create a string labeled α along the path P . The resulting stringnet state can then be reduced to a linear combination of string-net states on the unfattened lattice. The coefficients in this linear combination are the matrix elements of Wα(P ). 

However, none of the rules (4-7) involve strings labeled 

- [1] L. D. Landau, Phys. Z. Sowjetunion 11, 26 (1937). 

- [2] X.-G. Wen, Advances in Physics 44, 405 (1995). 

- [3] X.-G. Wen and Q. Niu, Phys. Rev. B 41, 9377 (1990). 

- [4] B. Blok and X.-G. Wen, Phys. Rev. B 42, 8145 (1990). 

- [5] N. Read, Phys. Rev. Lett. 65, 1502 (1990). 

- [6] J. Fr¨ohlich and T. Kerler, Nucl. Phys. B 354, 369 (1991). 

- [7] D. S. Rokhsar and S. A. Kivelson, Phys. Rev. Lett. 61, 2376 (1988). 

- [8] N. Read and B. Chakraborty, Phys. Rev. B 40, 7133 (1989). 

- [9] R. Moessner and S. L. Sondhi, Phys. Rev. Lett. 86, 1881 (2001). 

- [10] E. Ardonne, P. Fendley, and E. Fradkin, Annals Phys. 310, 493 (2004). 

α, nor do they allow for crossings. Thus, the reduction to string-net states on the unfattened lattice requires new local rules. These new local rules are defined by the 4 index objects Ω[j] α,sti[,][¯Ω][j] α,sti[,][and][the][integers][n][α,i][:] 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0020-19.png)


Here, σ, τ are the two indices of the matrix Ω[ij] st[.][(Until] now, we’ve neglected to write out these indices explicitly). 

After applying these rules, we then need to join together the resulting string-nets. The “joining rule” for two string types s1, s2 is as follows. If s1 = s2, we don’t join the two strings: we simply throw away the diagram. If s1 = s2, then we join the two strings and contract the two corresponding indices σ1, σ2. That is, we multiply the two Ωmatrices together in the usual way. Using the same approach as (C1), one can show that the graphical definition of Wα(P ) agrees with the algebraic definition (19). 

In the previous section, we used the graphical representation of Bp[s][to][show][that][these][operators][commute.] The string operators Wα(P ) can be analyzed in the same way. With a simple graphical argument one can show that the string operators Wα(P ) commute with the magnetic operators Bp[s][provided][that][(4-7),(D1)][satisfy][the] conditions 


![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0020-23.png)



![](.figures/arxiv__cond-mat-0404617/cond-mat-0404617.pdf-0020-24.png)


These relations are precisely the commutativity conditions (22), written in graphical form. 

- [11] V. Kalmeyer and R. B. Laughlin, Phys. Rev. Lett. 59, 2095 (1987). 

- [12] X.-G. Wen, F. Wilczek, and A. Zee, Phys. Rev. B 39, 11413 (1989). 

- [13] X.-G. Wen, Int. J. Mod. Phys. B 4, 239 (1990). 

- [14] N. Read and S. Sachdev, Phys. Rev. Lett. 66, 1773 (1991). 

- [15] X.-G. Wen, Phys. Rev. B 44, 2664 (1991). 

- [16] T. Senthil and M. P. A. Fisher, Phys. Rev. B 62, 7850 (2000). 

- [17] X.-G. Wen, Phys. Rev. B 65, 165113 (2002). 

- [18] S. Sachdev and K. Park, Annals of Physics (N.Y.) 298, 58 (2002). 

- [19] L. Balents, M. P. A. Fisher, and S. M. Girvin, Phys. Rev. 

21 

B 65, 224412 (2002). 

- [20] A. Y. Kitaev, Ann. Phys. (N.Y.) 303, 2 (2003). 

- [21] L. B. Ioffe, M. V. Feigel’man, A. Ioselevich, D. Ivanov, M. Troyer, and G. Blatter, Nature 415, 503 (2002). 

- [22] X.-G. Wen, Int. J. Mod. Phys. B 5, 1641 (1991). 

- [23] T. H. Hansson, V. Oganesyan, and S. L. Sondhi, condmat/0404327 (2004). 

- [24] V. L. Ginzburg and L. D. Landau, Zh. Ekaper. Teoret. Fiz. 20, 1064 (1950). 

- [25] E. Witten, Comm. Math. Phys. 121, 351 (1989). 

- [26] X.-G. Wen, Int. J. Mod. Phys. B 6, 1711 (1992). 

- [27] T. Banks, R. Myerson, and J. B. Kogut, Nucl. Phys. B 129, 493 (1977). 

- [28] D. Foerster, H. B. Nielsen, and M. Ninomiya, Phys. Lett. B 94, 135 (1980). 

- [29] M. Levin and X.-G. Wen, Phys. Rev. B 67, 245316 (2003). 

- [30] X.-G. Wen, Phys. Rev. D 68, 065003 (2003). 

- [31] D. Arovas, J. R. Schrieffer, and F. Wilczek, Phys. Rev. Lett. 53, 722 (1984). 

- [32] C. Kassel, Quantum Groups (Springer-Verlag, New York, 1995). 

- [33] M. Freedman, M. Larsen, and Z. Wang, Commun. Math. Phys. 227, 605 (2002). 

- [34] V. G. Turaev, Quantum invariants of knots and 3- manifolds (W. de Gruyter, Berlin-New York, 1994). 

   - [36] E. Witten, Nuclear Physics B 330, 285 (1990). 

   - [37] J. Kogut and L. Susskind, Phys. Rev. D 11, 395 (1975). 

   - [38] X.-G. Wen, Phys. Rev. B 68, 115413 (2003). 

   - [39] F. Wegner, J. Math. Phys. 12, 2259 (1971). 

   - [40] J. B. Kogut, Rev. Mod. Phys. 51, 659 (1979). 

   - [41] C. Itzykson, H. Saleur, and J. Zuber, Conformal Invariance and Applications to Statistical Mechanics, (World Scientific) (1988). 

   - [42] M. H. Freedman, quant-ph/0110060 (2001). 

   - [43] M. Freedman, C. Nayak, K. Shtengel, K. Walker, and Z. Wang, cond-mat p. 0307511 (2003). 

   - [44] M. Freedman, C. Nayak, and K. Shtengel, cond-mat p. 0309120 (2003). 

   - [45] G. Moore and N. Seiberg, Comm. Math. Phys. 123, 177 (1989). 

   - [46] K. G. Wilson, Phys. Rev. D 10, 2445 (1974). 

   - [47] E. Verlinde, Nuclear Physics B 300, 360 (1988). 

   - [48] P. Etingof and S. Gelaki, Moscow Mathematical Journal 3, 37 (2003). 

   - [49] Y. Nambu, Phys. Rev. Lett. 4, 380 (1960). 

   - [50] J. Goldstone, Nuovo Cimento 19, 154 (1961). 

   - [51] Note that reducible quasiparticles should not be confused with bound states. Indeed, in the case of Abelian gauge theory, most of the irreducible quasiparticles are bound states of electric charges and magnetic fluxes. 

- [35] E. Witten, Nuclear Physics B 322, 629 (1989).

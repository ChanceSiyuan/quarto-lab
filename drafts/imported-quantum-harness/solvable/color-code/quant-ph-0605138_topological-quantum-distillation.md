---
source: "https://arxiv.org/abs/quant-ph/0605138"
type: "arxiv"
canonical_id: "quant-ph/0605138"
title: "Topological quantum distillation."
authors: "H. Bombin, M. Martin-Delgado"
year: "2006"
venue: "Physical Review Letters"
arxiv_id: "quant-ph/0605138"
doi: "10.1103/PhysRevLett.97.180501"
full_text: yes
---

# Topological quantum distillation.

**Authors:** H. Bombin, M. Martin-Delgado

**Citation:** Physical Review Letters, vol. 97 18, pp. 
          180501
        , 2006

**arXiv:** [quant-ph/0605138](https://arxiv.org/abs/quant-ph/0605138)

**DOI:** [10.1103/PhysRevLett.97.180501](https://doi.org/10.1103/PhysRevLett.97.180501)

## Abstract

We construct a class of topological quantum codes to perform quantum entanglement distillation. These codes implement the whole Clifford group of unitary operations in a fully topological manner and without selective addressing of qubits. This allows us to extend their application also to quantum teleportation, dense coding, and computation with magic states.

## Full Text

## Topological Quantum Distillation 

H. Bombin and M.A. Martin-Delgado 

Departamento de F´ısica Te´orica I, Universidad Complutense, 28040. Madrid, Spain. 

We construct a class of topological quantum codes to perform quantum entanglement distillation. These codes implement the whole Clifford group of unitary operations in a fully topological manner and without selective addressing of qubits. This allows us to extend their application also to quantum teleportation, dense coding and computation with magic states. 

PACS numbers: 03.67.-a, 03.67.Lx 

One of the main motivations for introducing topological error correction codes [1], [2], [3] in quantum information theory is to realize a naturally protected quantum system: one that is protected from local errors in such a way that there is no need to explicitly perform an error syndrome measurement and a fixing procedure. Physically, this is achieved by realizing the code space in a topologically ordered quantum system. In such a system we have a gap to system excitations and topological degeneracy, which cannot be lifted by any local perturbations to the Hamiltonian. Only topologically non-trivial errors are capable of mapping degenerate ground states one onto another. Thus, a natural question is how to implement quantum information protocols in a topological manner, thereby getting the benefits provided by quantum topology. 

Quantum distillation of entanglement is one of those very important protocols in quantum information [4]. It allows us to purify initially mixed states with low degree of entanglement towards maximally entangled states, which are needed in many quantum information tasks. The most general description of entanglement distillation protocols [4], [5], [6] relies on the implementation of unitary operations from the Clifford group. This is the group of unitary operators acting on a system of n qubits that map the group of Pauli operators onto itself under conjugation. 

In this paper we have been able to construct quantum topological codes that allows us to implement the Clifford group in a fully topological manner. The Clifford group also underlies other quantum protocols besides distillation. Thus, as a bonus, we obtain complete topological implementations of quantum teleportation and superdense coding. We call these topological codes triangular codes. In addition, they have two virtues: 1/ there is no need for selective addressing and 2/ there is no need for braiding quasiparticles. The first property means that we do not have to address any particular qubit or set of qubits in order to implement a gate. The second one means that all we use are ground state operators, not quasiparticle excitations. 

In order to achieve these goals, we shall proceed in several stages. First, we introduce a new class of topological quantum error correcting codes that we call color codes. Unlike the original topological codes in [1], these are not based in a homology-cohomology setting. Instead, there 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0001-10.png)


FIG. 1: (a) A color code in a torus. Each site is a qubit and each plaquette a generator of the stabilizer S. The dashed red line corresponds to the shrunk red lattice. The thick red and blue lines are string operators. They act on the sites lying on their links. The dotted green line is the string operator that results from the product of the red and the blue one. (b) There are two ways in which we can change the shape of a red string operator. We can either consider homologous strings only or also use the operator equivalence (5). 

is an interplay between homology and a property that we call color for visualization purposes. This color is not a degree of freedom but a property emerging from the geometry of the codes. After color codes have been presented for closed surfaces, we show how colored borders can be introduced by doing holes in a surface. In particular we define triangular codes, so called because they consist of a planar layer with three borders, one of each color. These codes completely remove the need of selective addressing. If the lattice of a triangular code is suitably chosen, we show that the whole Clifford group can be performed on it. Finally, we give the Hamiltonian that implements the desired self-correcting capabilities. It is an exactly solvable local Hamiltonian defined on spin-1/2 systems placed at the sites of a 2-dimensional lattice. 

A quantum error correcting code of length n is a subspace C of H2[⊗][n][,][with][H][2][the][Hilbert][space][of][one][qubit.] Let the length of an operator on H2[⊗][n] be the number of qubits on which it acts nontrivially. We say that the code C corrects t errors when it is possible to recover any of its (unknown) states after any (unknown) error of length at most t has occurred. Let ΠC be the projector onto C. We say that C detects an operator O if ΠCOΠC ∝ ΠC. The distance of a code is the smallest length of a non- 

2 

detectable error. A code of distance 2t + 1 corrects t errors. We talk about [[n, k, d]] codes when referring to quantum codes of length n, dimension 2[k] and distance d. Such a code is said to encode k logical qubits in n physical qubits. 

Now let X, Y and Z denote the usual Pauli matrices. A Pauli operator is any tensor product of the form[�][n] i=1[σ][i] with σi ∈{1, X, Y, Z}. The closure of such operators as a group is the Pauli group Pn. Given an abelian subgroup S ⊂ Pn not containing −I, an stabilizer code of length n is the subspace C ⊂H2[⊗][n] formed by those vectors with eigenvalue 1 for any element of S [7], [8]. If its length is n and S has s generators, it will encode k = n − s qubits. Let Z be the centralizer of S in Pn, i.e., the set of operators in Pn that commute with the elements of S. The distance of the code C is the minimal length among the elements of Z not contained in S up to a sign. 

Suppose that we have a 2-dimensional lattice embedded in a torus of arbitrary genus such that three links meet at each site and plaquettes can be 3-colored, see Fig. 1 for a example in a torus of genus one. We will take red, green and blue as colors (RGB). Notice that we can attach a color to the links in the lattice according to the plaquettes they connect: a link that connects two red plaquettes is red, and so on. With such an embedding at hand we can obtain a color code by choosing as generators for S suitable plaquette operators. For each plaquette p there is a pair of operators: Bp[X][and][ B] p[Z][.][Let] I be an index set for the qubits in p’s border, then 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0002-04.png)


Color codes are local because [1] each generator acts on a limited number of qubits and each qubit appears in a limited number of generators, whereas there is no limit in the code distance, as we shall see. 

We will find very useful to introduce the notion of shrunk lattices, one for each color. The red shrunk lattice, for example, is obtained by placing a site at each red plaquette and connecting them through red links, see Fig. 1. Note that each link of a shrunk lattice corresponds to two sites in the colored one. Note also that green and blue plaquettes correspond to the plaquettes of the red shrunk lattice. 

We classify the plaquettes according to their color into three sets, R, G and B. Observe that for σ = X, Z 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0002-08.png)


hold because these products equal σˆ := σ[⊗][n] . We shall be using this hat notation for operators acting bitwise on the physical qubits of the code. Equations (2) implies that four of the generators are superfluous. We can now calculate the number of encoded qubits using the Euler characteristic of a surface χ = f + v − e. Here f , v and e are the number of plaquettes, sites and links of 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0002-10.png)


FIG. 2: A honeycomb lattice with a green border. Notice the two possible points of view for the operators of the plaquette p as boundary paths. The green string S is homologous to part of the border, and thus is equivalent to the identity. There is also a pair of equivalent 3-string operators, A and B. 

any lattice on the surface. Applying the definition to a shrunk lattice we get 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0002-13.png)


Observe that the number of encoded qubits depends only upon the surface, not the lattice. When the code is rephrased in terms of a ground state in a quantum system(13), this will be an indication of the existence of topological quantum order [9]. 

So far we have described the Hilbert space of the logical qubits in terms of the stabilizer. Now we want to specify the action of logical operators on those qubits. To this end we introduce an equivalence relation among the operators in Z, which we shall use repeatedly. We say that A ∼ B if A and B represent the same quotient in Z/S. Notice that two equivalent operators will have the same effect in C. Now we introduce the key idea of string operators. They can be red, green or blue, depending on the shrunk lattice we are considering. Let P be any closed path in a shrunk lattice. We attach to it two operators: if P is a path and the qubits it contains are indexed by I, we define 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0002-16.png)


The point is that string operators commute with the generators of the stabilizer. Also observe that, let us say, a red plaquette operator can be identified both with a green string or with a blue string, see Fig. 2. In both cases the paths are boundaries, but in the first case it is a boundary for the green shrunk lattice and in the second for the blue one. 

We can now relate Z2 homology theory [10] and string operators. We recall that a closed path is a boundary iff it is a combination of boundaries of plaquettes. For the, say, red shrunk lattice, green and blue plaquettes make up the set of its plaquettes. Thus, two string operators of the same color are equivalent iff their corresponding paths are homologous, that is, if they differ by a boundary. Then it 

3 

makes sense to label the string operators as Sµ[Cσ][,][where] C is a color, σ is a Pauli matrix and µ is a label related to the homology class. But what about the equivalence of strings of different colors? Fig. 1 shows how the product of a pair of homologous red and blue strings related to the same Pauli matrix produces a green string. Note that at those qubits in which both strings cross they cancel each other. In general we have 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0003-02.png)


This property gives the interplay between homology and color, as we will see later. 

The commutation properties of strings are essential to their study as operators on C. It turns out that: 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0003-05.png)


FIG. 3: (a) The grey area is the support of an operator O in Z. It must be trivial since it commutes with the colored string operators shown, which are enough to construct all X and Z operators for logical qubits. (b) The color structure of a planar triangular code. A 3-string operator T and a deformation of it are displayed, showing why {T[X] , T[Z] } = 0. 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0003-07.png)


The first commutator is trivially null; for the second, note that two homologous strings must cross an even number of times; the third is zero because two strings of the same color always share an even number of qubits. Other commutators will depend on the homology, they will be nonzero iff the labels of the strings are completely different and closed paths in the respective homology classes cross an odd number of times. For example, consider the torus with the labels 1 and 2 for its two fundamental cycles. If we make the 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0003-09.png)



![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0003-10.png)


then we recover the usual commutation relations for Pauli operators in H2[4][.] 

We now determine the distance of color codes. Recall that in order to calculate the distance we must find the smallest length among those operators in Z which act nontrivially on C. Let the support of an operator in Z be the set of qubits in which it acts nontrivially. We can identify this support with a set of sites in the lattice. The point is that any operator in Z such that its support does not contain a closed path which is not a boundary, must be in S. The idea behind this assertion is illustrated in Fig. 3 . For such an operator O, we can construct a set of string operators with two properties: their support does not intersect the support of O and any operator in S commuting with all of them must be trivial. The distance thus is the minimal length among paths with nontrivial homology. 

Strings are all we need to handle tori of arbitrary genus. Things get more interesting if we consider oriented surfaces with border, which can be obtained by opening holes in a closed surface. In particular, we will introduce holes by removing plaquettes. If we remove, for example, a green plaquette, green strings can have an endpoint on it, but not blue or red ones. Then borders have a color, and only a green string can end at a green border, see Fig. 2. The most important case of such bordered codes are triangular codes. They are constructed starting with a color code in a sphere from which a site and its 

neighboring three links and three plaquettes are removed. From constraints (2) we observe that two generators of the stabilizer are removed in the process. Since a color code in the sphere encodes zero qubits, a triangular code will encode a single qubit. Examples of triangular codes are displayed in Fig 4. 

So let us show why new features are introduced through triangular codes. Observe that equation (5) suggests the construction displayed in Fig. 2: three strings, one of each color, can be combined at a point and obtain an operator that commutes with plaquette operators. Fig. 3(b) shows the color structure of the borders in a triangular code. Let T[σ] , σ ∈{X, Z}, be the 3-string operators depicted in the figure. By deforming T a little it becomes clear that {T[X] , T[Z] } = 0, because T and its deformation cross each other once at strings of different colors. Such an anticommutation property is impossible with strings because of (6). 

Although 3-string operators can be used to construct an operator basis for the encoded qubit in a triangular code, this can equivalently be done with the operators X[ˆ] and Z[ˆ] . They commute with the stabilizer operators and {X,[ˆ] Z[ˆ] } = 0 because the total number of qubits is odd. The generators of the Clifford group are the Hadamard gate H and the phase-shift gate K applied to any qubit and the controlled-not gate Λ(X) applied to any pair of qubits: 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0003-17.png)


The action of these gates is completely determined up to a global phase by their action on the operators X and Z of individual qubits, for example 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0003-19.png)


Now consider H[ˆ] , K[ˆ] and Λ([ˆ] X). Of course, Λ([ˆ] X) acts pairwise on two code layers that must be placed one on top of the other so that the operation is locally performed. The fact is that in the triangular codes both H[ˆ] and Λ([ˆ] X) act as the local ones at the logical level, for example: 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0003-21.png)


4 

mit faulty measurements, since the faulty measurement of a qubit is equivalent to an X error previous to it. In this sense, the measuring process is as robust as the code itself. 

Now let us return to the general case of an arbitrary color code in a surface with border. We can give a Hamiltonian such that its ground state is C: 

FIG. 4: (a) The simplest example of a triangular code. The original lattice in the sphere can be recovered by adding a site and linking it to the sites at vertices of the triangle. (b) Triangular codes of any size can be constructed with the special property that any plaquette has v = 4m sites, with m an integer. This extra requirement is needed in order to implement the phase-shift gate K. 

Unfortunately, K[ˆ] is more tricky because in general it does not take ground states to ground states. This is so because KB[ˆ] p[X][K][ˆ][†][=][(][−][1)][v/][2][B] p[X][B] p[Z][if][the][plaquette] p has v sites. However, this difficulty can be overcome by choosing a suitable lattice, as shown in Fig. 4. For such a suitable code, if the number of sites is congruent with 3 mod 4, then K[ˆ] acts like K[†] , but this is a minor detail. As a result, any operation in the Clifford group can be performed on certain triangular codes in a fault tolerant way and without selective addressing. As for the distance of triangular codes, it can be arbitrarily large: notice that an operator in Z acting nontrivially on C must have a support connecting the red, green and blue borders. 

We can give an expression for the states of the logical qubit {|0[¯] ⟩, |1[¯] ⟩}: 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0004-06.png)


and |1[¯] ⟩ := X[ˆ] |0[¯] ⟩, so that Z[ˆ] |[¯] l⟩ = (−1)[l] |[¯] l⟩, l = 0, 1. Observe that if we have a state in C and we measure each physical qubit in the Z basis we are also performing a destructive measurement in the Z[ˆ] basis. This is so because the two sets of outputs do not have common elements. In fact, the classical distance between any output of |0[¯] ⟩ and any of |1[¯] ⟩ is at least 2t + 1. Moreover, we can ad- 

- [1] A. Yu. Kitaev, Annals of Physics 303 no. 1, 2–30 (2003), quant-ph/9707021. 

- [2] Dennis et al. J. Math. Phys. 43, 4452-4505 (2002). 

- [3] S. B. Bravyi, A. Yu. Kitaev, quant-ph/9811052. 

- [4] Bennett et al. Phys. Rev. Lett. 76, 722-725 (1996). 

- [5] Deutsch et al. Phys. Rev. Lett. 77, 2818-2821 (1996). 

- [6] H. Bombin, M.A. Martin-Delgado Phys. Rev. A 72, 032313 (2005). 

- [7] D. Gottesman, Phys. Rev. A 54, 1862 (1996). 

- [8] A.R. Calderbank et al. Phys. Rev. Lett. 78,405 (1997). 

- [9] X.-G. Wen. Quantum Field Theory of Many-body Systems, Oxford University Press, (2004). 


![](.figures/arxiv__quant-ph-0605138/quant-ph-0605138.pdf-0004-17.png)


Observe that color plays no role in the Hamiltonian, rather, it is just a tool we introduce to analyze it. Any eigenstate |ψ⟩ of H for which any of the conditions Bp[σ][|][ψ][⟩][=][|][ψ][⟩][is][not][fulfilled][will][be][an][excited][state.] Then we can say, for example, that an state |ψ⟩ for which Bp[X][|][ψ][⟩][=][ −|][ψ][⟩][has an][ X][-type excitation or quasi-particle] at plaquette p. These excitations have the color of the plaquette where they live. In a quantum system with this hamiltonian and the geometry of the corresponding surface, any local error will either leave the ground state untouched or produce some quasiparticles that will decay. This family of quantum systems shows topological quantum order: they become self-protected from local errors by the gap [12], [13]. 

As a final remark, we want to point out that the ability to perform fault tolerantly any operation in the Clifford group is enough for universal quantum computation as long as a reservoir of certain states is available [14]. These states need not be pure, and so they could be obtained, for example, by faulty methods, perhaps semi-topological ones. Namely, one can distill these imperfect states until certain magic states are obtained [14]. These magic states are enough to perform universal quantum computation with the Clifford group, which is different from topological computation based on braiding quasiparticles [1], [15], [16]. 

Acknowledgements H.B. acknowledges useful discussions with L. Tarruell. We acknowledge financial support from a PFI fellowship of the EJ-GV (H.B.), DGS grant under contract BFM 2003-05316-C02-01 (M.A.MD.), and CAM-UCM grant under ref. 910758. 

- [10] H. Bombin, M.A. Martin-Delgado, Phys. Rev. A 73, 062303 (2006) 

- [11] A. Kitaev, cond-mat/0506438. 

- [12] A. Kitaev, J. Preskill, Phys. Rev. Lett. 96, 110404 (2006) 

- [13] M. Levin,X.-G. Wen, Phys. Rev. Lett. 96, 110405 (2006). 

- [14] S. Bravyi, A. Kitaev. Phys. Rev. A 71, 022316 (2005) 

- [15] M. H. Freedman, A. Kitaev, M. J. Larsen, Z. Wang. Bull. Amer. Math. Soc. 40 31-38, (2003). 

- [16] J. Preskill, Lecture notes on Topological Quantum Computation, http://www.theory.caltech.edu/preskill/ ph219/topological.ps.

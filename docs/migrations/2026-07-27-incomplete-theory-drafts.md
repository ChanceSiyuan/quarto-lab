# Incomplete theory pages moved to drafts

At source commit `ab1ef63ca39e5514d732e23f4d2e7137a0f97dd4`, all 184 pages under `theory/` were reviewed for visible incompleteness. A page was moved only when it was empty or frontmatter-only, ended in an unfinished sentence/formula/core section, contained an explicit unresolved TODO/TBC in its substantive argument, or was plainly an abandoned outline.

The 41 visibly incomplete pages were moved byte-for-byte from `theory/<relative-path>` to `drafts/<relative-path>`. A subsequent trust-closure audit moved seven additional pages whose arguments substantively depended on those drafts. Every destination was verified with `cmp` against its source blob at the source commit; the final boundary contains 136 trusted QMD pages and 48 draft QMD pages.

## Moved

```text
Condensed_matter/LGT/Intro.qmd
Condensed_matter/LGT/U1_sim.qmd
Condensed_matter/LGT/digital_based.qmd
Condensed_matter/LGT/exp_CFT.qmd
Condensed_matter/TFIM/Square-lattice.qmd
Condensed_matter/TFIM/kagome-lattice.qmd
Condensed_matter/topo_matter/2dHH.qmd
Dynamics/Effective_ham.qmd
Dynamics/Floquet.qmd
Dynamics/Stoq.qmd
Dynamics/examples.qmd
Entanglement/measures.qmd
Factoring/grahiso.qmd
Factoring/non-abelian.qmd
Fingerprint/DNA.qmd
OSF/Feynman_based.qmd
OSF/nonPauli_stab.qmd
SLM_engineer/realizaiton.qmd
compatibility/f-compatiability.qmd
compatibility/local-optimal_shadow.qmd
compatibility/nonparametric.qmd
compatibility/projective_sim.qmd
learning_theo/NTK.qmd
learning_theo/Virtual_Distillation/design.qmd
learning_theo/approx_dataload.qmd
learning_theo/framework.qmd
learning_theo/ham_learning.qmd
learning_theo/weak_schur/Clifford-Weingarten.qmd
learning_theo/weak_schur/approx_design.qmd
learning_theo/weak_schur/symmetric_strategies.qmd
optimization/MIS/Heristic.qmd
optimization/MIS/MIS.qmd
optimization/MIS/approx.qmd
optimization/MIS/encoding.qmd
quantum_complexity/Boolean_ana/Influence.qmd
quantum_complexity/supermacy/Bellsamp.qmd
quantum_complexity/supermacy/IQPs/iqp_supremacy.qmd
quantum_complexity/supermacy/IQPs/mbqc_iqp.qmd
quantum_complexity/supermacy/QNC0.qmd
quantum_complexity/supermacy/hardness_proofs.qmd
stab_simulation/graph_combine.qmd
```

## Trust-closure demotions

```text
Condensed_matter/LGT/QuantumLink.qmd
Condensed_matter/LGT/Z2_floquet.qmd
Condensed_matter/topo_matter/honeycomb.qmd
Factoring/learning_barriers.qmd
compatibility/Algebraic_estimation_framework.qmd
compatibility/multi-copy_localshadow.qmd
learning_theo/grokking_phase_transition.qmd
```

## Conservatively retained

These 17 pages were reviewed but not moved automatically. They contain a short but potentially self-contained definition or derivation, a research-question TODO, a missing-image comment, or a local formatting defect rather than decisive evidence that the whole page is incomplete.

```text
Condensed_matter/Fermi-Hubbard/intro.qmd
Condensed_matter/LGT/MCMC.qmd
Condensed_matter/TFIM/TFIM_super.qmd
Dynamics/Adiabatic_comp.qmd
Dynamics/geometric_phase.qmd
Factoring/shor.qmd
Fingerprint/Pattern.qmd
Fingerprint/fingerprint.qmd
TN_sim/MPS_AKLT.qmd
TN_sim/PEPS.qmd
TN_sim/TDVP.qmd
learning_theo/phasegate_learn.qmd
quantum_complexity/Ham_complexity.qmd
quantum_complexity/supermacy/IQPs/ft_iqp.qmd
quantum_complexity/supermacy/IQPs/reduct_deg3gap.qmd
quantum_complexity/supermacy/Peak.qmd
stab_simulation/clifford_T.qmd
```

## Follow-up

The trust-closure audit removed navigational references to moved drafts, fixed historical paths, and verified that the trusted tree no longer links to `drafts/` or `conference/`. Generated tables and sidebars were then replaced by explicit Reading maps so future membership is curated rather than inferred from filesystem enumeration.

The legacy Noisy Complexity auto-generation shell script was also moved
byte-for-byte out of `theory/` to
`drafts/automation/generate_and_polish_noisy_complexity.sh`. It is untrusted,
not published, and not part of the implemented knowledge-reading phase.

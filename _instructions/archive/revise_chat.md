# Role
You are a Senior Academic Researcher and Expert Technical Writer specializing in Quantum Computing. You have access to web search and external academic databases.

# Task
I am providing a chat history (between me and an AI assistant) and a rough draft of my academic reading notes in Quarto (`.qmd`) format. Your task is to complete the missing mathematical proofs marked as "(t.b.c.)", rigorously review the logic, fill in any mathematical gaps using external sources if necessary, and output a complete, professional Quarto document along with an accompanying BibTeX (`.bib`) file.

# Core Directives

1. **Targeted Completion & Gap-Filling:** Locate every instance of `(t.b.c.)` and `(todo:*)` in my draft. Replace these placeholders with rigorous, step-by-step mathematical proofs. 
   * **Crucial:** If the provided chat history lacks sufficient mathematical detail, skips steps, or is too vague to form a complete proof, **you must use your web search capabilities or external domain knowledge** to fill in these logical gaps. Ensure every proof is highly detailed and self-consistent.

2. **Identifying & Adding Missing Theorems:** As you review the logic linking the `(t.b.c.)` and `(todo:*)` proofs and the surrounding text, watch for implicit dependencies. 
   * If the chat history or the derivation relies on an important theorem, transformation, or identity (e.g., specific fermionic commutation relations, Pauli algebra tricks) that is not explicitly stated in my draft, **create a new formal block** for it (`::: {#thm-new-name .callout-important icon="false"}`).
   * If the proof for this new theorem is brief, provide it within a `collapse="true"` callout.
   * If the proof is overly lengthy or standard textbook knowledge, state the theorem clearly, omit the full proof, and provide a precise academic citation (adding it to the `.bib` file).

3. **Structure Preservation:** Do NOT heavily alter my existing draft's structure, headings, or core narrative. Your modifications should be surgical: fill in the proofs, add missing supporting theorems, and insert necessary bridging sentences to ensure contextual coherence.

4. **Deep Analysis of Chat History:** * The "### 👤 User" sections represent my core intent and should guide your focus.
   * Critically evaluate the "### 🤖 Assistant" sections. Extract the correct derivations, discard redundancies, and upgrade the mathematical rigor.
   * Skip basic overviews. Focus strictly on advanced theoretical depth (e.g., many-body physics, qubit mappings).

# Formatting & Quarto Standards
* Retain all existing Quarto Div syntax (`:::`) for definitions, lemmas, and theorems. 
* When inserting proofs, ensure they are properly enclosed within the expandable callout blocks (`::: {.callout-note collapse="true"}`).
* Ensure all LaTeX math formulas are perfectly formatted and notationally consistent with the equations I have already written.

# Grounding & Citation Constraint
* **Traceable Extension:** While you are authorized to use external knowledge to bridge logical gaps, every new concept, mathematical step, or theorem you introduce *must* be standard, verifiable quantum computing literature. 
* **Strict Citation:** Any external theorem or significant mathematical trick you bring in to complete the `(t.b.c.)` and `(todo:*)` sections must be properly cited inline and included in the final `.bib` output.

# Workflow Execution
Before generating the final `.qmd` and `.bib` text, please provide a brief outline detailing:
1. The specific mathematical steps and logical flow you intend to use to fill each `(t.b.c.)` and `(todo:*)` gap.
2. Any logical gaps you identified in the chat history that require external knowledge/web search to bridge.
3. Any **new theorems/lemmas** you plan to add as Quarto blocks, including whether you will prove them or just cite them.
4. The key papers/textbooks you will include in the `.bib` file.

Wait for my confirmation on this outline before generating the full files.

---
**[Here is my draft]**
Experiments/posts/Digital-analog/digital-analog.qmd
**[Here is the chat history]**
_resource/chat copy.md
_resource/main.tex
# QEC Problem Portfolio Assessments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register twenty approved quantum-error-correction problems as `Prob-002` through `Prob-021`, evaluate all twenty-one QEC problems with frozen citation/economic evidence and the V/A/S policy, and expose the completed comparison and reports on a local English-only web page.

**Architecture:** A canonical, validated catalog owns the approved problem copy and technical anchors. A staging/publishing layer uses the existing `make problem-publish` trust boundary, an approved-evidence valuation adapter feeds the existing immutable snapshot manager, and a restartable sequential batch runner drives valuation and assessment managers without starting autoresearch. A read-only portfolio projection joins the generated problem index with the latest completed assessment summaries and is served by the loopback sidecar to a new client page.

**Tech Stack:** Node.js 22 ESM, `node:test`, existing problem publisher and schemas, existing OpenAlex/valuation/assessment managers, Next.js/React/TypeScript, CSS Modules, local loopback HTTP sidecar, Playwright/in-app browser verification.

## Global Constraints

- Keep the existing `Prob-001`; add exactly twenty new records with contiguous IDs `Prob-002` through `Prob-021`; final total is exactly twenty-one.
- Preserve the user-approved titles, summaries, candidate questions, gates, technical anchors, `sourceCount: 3`, and registration timestamps specified below.
- Every new manifest uses `schemaVersion: 1`, `status: "draft"`, `domain: "quantum-computing"`, `quantumArea: "error-correction-and-fault-tolerance"`, and gate readiness `"specified"`.
- Every new problem directory is published only through `make problem-publish STAGE=<path> ID=<id>` and initially contains exactly `problem.json`, `problem.md`, `generation/initial-prompt.md`, `generation/transcript.md`, and `generation/decision.md`.
- Never overwrite a conflicting problem, valuation snapshot, assessment run, or report. A restart may skip an artifact only after validating its identity, content contract, and hash.
- Keep portfolio-visible problem text, UI copy, assessment summaries, and report HTML English-only. Generation audit files are excluded from rendering and from the visible-content CJK check.
- External papers, citation metadata, company announcements, and market reports remain external evidence. Never write them into `knowledge/` or represent them as trusted knowledge.
- OpenAlex is the frozen citation provider. Raw citation totals may inform Scientific Attention but never Gap/Novelty and are never added directly to V, A, or S.
- Treat the McKinsey market range and IBM investment as broad enabling/investment proxies, never as problem-specific revenue. Keep Capturable Value unknown without pricing, licensing, contract, product-margin, or willingness-to-pay evidence.
- Keep Research Value (V) and Autoresearch Fit (A) on their existing 0–100 weighted policies. Combined Priority (S) remains their harmonic mean. Do not change A weights.
- Do not start an autoresearch campaign. All new records remain drafts and every assessment recommendation remains advisory.
- Do not modify `app/page.tsx`, `app/globals.css`, `app/layout.tsx`, or any file under `public/knowledge/`.
- Preserve pre-existing worktree changes and stage only the files or exact hunks owned by the current task; do not absorb unrelated dirty files into a feature commit.
- Before changing tests during execution, read `superpowers:test-driven-development/writing-good-tests.md` completely and follow test-first RED/GREEN commits.
- Before claiming completion, use `superpowers:verification-before-completion`; for local UI verification, use `browser:control-in-app-browser` and inspect the rendered page rather than relying only on source assertions.

---

## File and Interface Map

| File | Responsibility |
|---|---|
| `lib/qec-portfolio/catalog.mjs` | Immutable approved catalog, common evidence source metadata, catalog validation and lookup. |
| `lib/qec-portfolio/registration.mjs` | Render the five-file draft shape, stage it, verify exact existing records, and invoke an injected publisher. |
| `scripts/register-qec-portfolio.mjs` | CLI that stages and publishes `Prob-002`–`Prob-021` through `make problem-publish`. |
| `lib/qec-portfolio/valuation-researcher.mjs` | Deterministic adapter that converts approved catalog/economic evidence into the existing strict valuation-candidate contract. |
| `lib/qec-portfolio/openalex-retry.mjs` | Bounded retry wrapper for transient OpenAlex provider failures; never retries missing credentials. |
| `lib/qec-portfolio/batch-runner.mjs` | Restartable phase orchestration for registration, snapshots, assessments, and final verification. |
| `scripts/run-qec-portfolio.mjs` | Production composition root for repository, OpenAlex, resolver, Codex assessment, stores, and batch runner. |
| `scripts/verify-qec-portfolio.mjs` | Read-only artifact, hash, count, English-only, and route-data verifier. |
| `lib/qec-portfolio/reader.mjs` | Join problem records with latest completed assessment summaries and produce safe portfolio rows. |
| `lib/qec-portfolio/view-model.mjs` | Pure sorting and display-value helpers shared by tests and the client panel. |
| `lib/assessments/local-service.mjs` | Add authenticated read-only `GET /__local/assessments/portfolio`. |
| `scripts/local-assessment-service.mjs` | Construct and inject the portfolio reader into the loopback service. |
| `app/qec-portfolio/page.tsx` | Static-safe route shell for the local comparison page. |
| `app/qec-portfolio/portfolio-panel.tsx` | Fetch, status, sorting controls, desktop table, and responsive cards. |
| `app/qec-portfolio/portfolio-panel.module.css` | Route-scoped layout and responsive styles without touching preserved global CSS. |

## Canonical Approved Catalog

The implementation splits each approved two-sentence preview entry at the sentence boundary: the first sentence is `summary`; the second sentence is `candidateQuestion`. For arXiv sources, `sourceUrl` remains the approved arXiv URL while `persistentId` uses the standard DataCite form accepted by the existing OpenAlex client. `Prob-011` keeps the approved qecsim documentation URL and uses the DOI that qecsim's official Citing page asks users to cite, `10.25910/x8xw-9077`, as its citation identifier.

| ID | Title | Summary | Candidate question | Gate type | Technical source URL | OpenAlex persistent ID | Created/updated |
|---|---|---|---|---|---|---|---|
| `Prob-002` | Finite-Length qLDPC Code Search Under Hardware Constraints | Search for finite-length qLDPC codes that improve the rate–distance–check-weight–decoder-performance frontier. | Can automated search outperform declared finite-length baselines on sealed instances? | `finite-length-code-pareto` | `https://arxiv.org/abs/2510.14090` | `doi:10.48550/arXiv.2510.14090` | `2026-07-29T12:33:33.000Z` |
| `Prob-003` | Circuit-Level qLDPC Decoder Optimization | Optimize qLDPC decoders under circuit-level noise and bounded runtime. | Can search improve logical error rate without exceeding latency and memory budgets? | `circuit-level-decoder-benchmark` | `https://arxiv.org/abs/2206.06557` | `doi:10.48550/arXiv.2206.06557` | `2026-07-29T12:33:33.000Z` |
| `Prob-004` | Real-Time Decoder Tail-Latency Minimization | Minimize decoder tail latency while preserving logical accuracy. | Can implementation search improve p95/p99 latency and avoid syndrome backlog? | `tail-latency-decoder-benchmark` | `https://arxiv.org/abs/2410.05202` | `doi:10.48550/arXiv.2410.05202` | `2026-07-29T12:33:33.000Z` |
| `Prob-005` | Bounded-Memory Streaming QEC Decoder | Design a streaming decoder with bounded state and stable throughput. | Can it match batch-decoder accuracy without unbounded memory or backlog? | `bounded-memory-streaming-benchmark` | `https://arxiv.org/abs/2605.30765` | `doi:10.48550/arXiv.2605.30765` | `2026-07-29T12:33:33.000Z` |
| `Prob-006` | Adaptive Decoding Under Correlated and Drifting Noise | Adapt decoder parameters to correlated, nonstationary noise. | Does online adaptation improve held-out logical error rates without leakage from final evaluation? | `noise-drift-holdout` | `https://arxiv.org/abs/1809.10704` | `doi:10.48550/arXiv.1809.10704` | `2026-07-29T12:33:33.000Z` |
| `Prob-007` | Leakage-Aware Decoder and Reset-Policy Co-Design | Jointly optimize leakage inference, decoder behavior, and reset placement. | Can the policy reduce logical failures and cycle cost on held-out leakage traces? | `leakage-reset-policy-benchmark` | `https://arxiv.org/abs/2308.02079` | `doi:10.48550/arXiv.2308.02079` | `2026-07-29T12:33:33.000Z` |
| `Prob-008` | Erasure-Biased Code–Decoder Co-Design | Co-design finite codes and decoders for erasure-dominated hardware. | Can search improve logical error and physical-resource Pareto performance? | `erasure-code-decoder-pareto` | `https://arxiv.org/abs/2307.08737` | `doi:10.48550/arXiv.2307.08737` | `2026-07-29T12:33:33.000Z` |
| `Prob-009` | Generalizable Neural Decoder with Calibrated Uncertainty | Train a decoder that transfers across codes and noise shifts while reporting calibrated confidence. | Can it beat classical baselines on unseen domains? | `cross-domain-neural-decoder` | `https://arxiv.org/abs/2510.06257` | `doi:10.48550/arXiv.2510.06257` | `2026-07-29T12:33:33.000Z` |
| `Prob-010` | Rare-Event Logical Failure Estimation | Estimate very low logical failure probabilities with auditable uncertainty. | Can the estimator reduce simulation cost while maintaining calibrated coverage? | `rare-event-estimator-calibration` | `https://arxiv.org/abs/2511.15177` | `doi:10.48550/arXiv.2511.15177` | `2026-07-29T12:33:33.000Z` |
| `Prob-011` | Reproducible Cross-Code QEC Benchmark Suite | Build a reproducible benchmark spanning codes, decoders, and noise models. | Can it produce implementation-independent rankings with complete audit records? | `cross-code-benchmark-reproducibility` | `https://qecsim.github.io/overview.html` | `doi:10.25910/x8xw-9077` | `2026-07-29T12:33:33.000Z` |
| `Prob-012` | Syndrome-Extraction Schedule Search | Search valid stabilizer-measurement schedules that control error propagation. | Can automated scheduling reduce logical error and circuit depth on sealed codes? | `syndrome-schedule-benchmark` | `https://arxiv.org/abs/2601.12509` | `doi:10.48550/arXiv.2601.12509` | `2026-07-29T12:33:33.000Z` |
| `Prob-013` | Flag-Sharing Ancilla Circuit Synthesis | Synthesize fault-tolerant flag-sharing syndrome circuits. | Can search reduce ancilla count and circuit area while passing exhaustive bounded-fault checks? | `flag-circuit-fault-enumeration` | `https://arxiv.org/abs/2407.00607` | `doi:10.48550/arXiv.2407.00607` | `2026-07-29T12:33:33.000Z` |
| `Prob-014` | Noise-Aware Stabilizer Measurement Scheduling | Allocate measurement cadence using heterogeneous and drifting error rates. | Can adaptive scheduling reduce logical error per unit cycle cost? | `measurement-cadence-benchmark` | `https://arxiv.org/abs/2308.02079` | `doi:10.48550/arXiv.2308.02079` | `2026-07-29T12:33:33.000Z` |
| `Prob-015` | Lattice-Surgery Routing and Scheduling | Optimize logical-patch placement, routing, and operation timing. | Can search reduce spacetime volume while respecting dependencies and factory supply? | `lattice-surgery-scheduling-benchmark` | `https://arxiv.org/abs/2512.06484` | `doi:10.48550/arXiv.2512.06484` | `2026-07-29T12:33:33.000Z` |
| `Prob-016` | Multi-Level Magic-State Factory Optimization | Optimize factory topology, level count, allocation, and buffering. | Can search improve the physical-qubit/runtime/error Pareto frontier? | `magic-state-factory-pareto` | `https://arxiv.org/abs/2411.04270` | `doi:10.48550/arXiv.2411.04270` | `2026-07-29T12:33:33.000Z` |
| `Prob-017` | Fault-Tolerant Code-Switching Protocol Synthesis | Search verified protocols for switching between complementary codes. | Can synthesis reduce qubit and gate overhead while satisfying bounded-fault correctness? | `code-switching-fault-enumeration` | `https://arxiv.org/abs/2403.13732` | `doi:10.48550/arXiv.2403.13732` | `2026-07-29T12:33:33.000Z` |
| `Prob-018` | Bias-Preserving Logical Operation Co-Optimization | Co-optimize biased-noise codes, logical operations, and decoding. | Can search preserve noise bias and reduce logical error across a universal workload? | `bias-preserving-logical-benchmark` | `https://arxiv.org/abs/2009.07851` | `doi:10.48550/arXiv.2009.07851` | `2026-07-29T12:33:33.000Z` |
| `Prob-019` | Bosonic–Outer-Code Concatenation Co-Design | Co-design bosonic inner encodings and discrete outer codes. | Can search reduce hardware and cycle overhead at a fixed logical-error target? | `bosonic-outer-code-pareto` | `https://arxiv.org/abs/2010.08699` | `doi:10.48550/arXiv.2010.08699` | `2026-07-29T12:33:33.000Z` |
| `Prob-020` | End-to-End Fault-Tolerant Resource Allocation Under Uncertainty | Jointly allocate code distances, factories, routing capacity, and error budgets. | Can robust optimization reduce total cost across uncertain hardware parameters? | `end-to-end-resource-estimation-benchmark` | `https://arxiv.org/abs/2411.04270` | `doi:10.48550/arXiv.2411.04270` | `2026-07-29T12:33:33.000Z` |
| `Prob-021` | Automated Fault-Tolerance Verification for QEC Circuits | Develop scalable formal verification for stabilizer-code circuits and fault-tolerant logical protocols. | Can an automated verifier prove bounded-fault correctness or produce minimal counterexamples across a sealed corpus of syndrome-extraction, logical-gate, and code-switching circuits? | `fault-tolerance-formal-verification` | `https://arxiv.org/abs/2504.07732` | `doi:10.48550/arXiv.2504.07732` | `2026-07-29T12:36:58.000Z` |

The `technicalAnchor.title` values are exact and are shown verbatim in the problem evidence section and valuation confirmation:

| ID | Technical anchor title |
|---|---|
| `Prob-002` | Quantum Low-Density Parity-Check Codes |
| `Prob-003` | An efficient decoder for a linear distance quantum LDPC code |
| `Prob-004` | Demonstrating real-time and low-latency quantum error correction with superconducting qubits |
| `Prob-005` | Real-Time Quantum Error Correction System Stack: Architecture, Algorithms, and Engineering Practice |
| `Prob-006` | Statistical mechanical models for quantum codes with correlated noise |
| `Prob-007` | Model-based Optimization of Superconducting Qubit Readout |
| `Prob-008` | Demonstrating a long-coherence dual-rail erasure qubit using tunable transmons |
| `Prob-009` | Toward Uncertainty-Aware and Generalizable Neural Decoding for Quantum LDPC Codes |
| `Prob-010` | Fail fast: techniques to probe rare events in quantum error correction |
| `Prob-011` | qecsim — Quantum Error Correction Simulator; citing work: Tailoring surface codes: Improvements in quantum error correction with biased noise |
| `Prob-012` | AlphaSyndrome: Tackling the Syndrome Measurement Circuit Scheduling Problem for QEC Codes |
| `Prob-013` | Reducing Quantum Error Correction Overhead with Versatile Flag-Sharing Syndrome Extraction Circuits |
| `Prob-014` | Model-based Optimization of Superconducting Qubit Readout |
| `Prob-015` | PureMagic: A Dynamic Scheduler for Lattice Surgery |
| `Prob-016` | Optimizing Multi-level Magic State Factories for Fault-Tolerant Quantum Architectures |
| `Prob-017` | Experimental fault-tolerant code switching |
| `Prob-018` | The XZZX Surface Code |
| `Prob-019` | Bosonic quantum error correction codes in superconducting quantum circuits |
| `Prob-020` | Optimizing Multi-level Magic State Factories for Fault-Tolerant Quantum Architectures |
| `Prob-021` | Efficient Formal Verification of Quantum Error Correcting Programs |

The common evidence records are exact:

- `source-mckinsey-quantum-monitor-2026`: `https://www.mckinsey.com/capabilities/mckinsey-technology/our-insights/mckinsey-quantum-technology-monitor-2026-a-commercial-tipping-point`; locator states that the 2035 internal quantum-computing market range is USD 43–71 billion, represented as low/base/high USD 43/57/71 billion in 2035 dollars.
- `source-ibm-quantum-investment-2026`: `https://newsroom.ibm.com/2026-06-02-ibm-commits-more-than-10-billion-to-quantum-computing%2C-funding-its-roadmap-from-todays-leading-systems-to-the-worlds-first-fault-tolerant-quantum-computers`; locator states that IBM announced more than USD 10 billion over five years, represented only as a USD 10 billion lower-bound investment signal in 2026 dollars.

### Task 1: Canonical Catalog and Contract

**Files:**
- Create: `lib/qec-portfolio/catalog.mjs`
- Create: `tests/qec-portfolio-catalog.test.mjs`

**Interfaces:**
- Consumes: no task-local interfaces; imports `PROBLEM_ID_PATTERN` from `lib/problems/schema.mjs`.
- Produces: `QEC_PORTFOLIO_PROBLEMS: ReadonlyArray<QecCatalogRecord>`, `QEC_PORTFOLIO_IDS: ReadonlyArray<string>`, `COMMON_ECONOMIC_EVIDENCE: ReadonlyArray<AtomicEvidence>`, `getQecPortfolioProblem(id: string): QecCatalogRecord | null`, and `validateQecPortfolioCatalog(records?): { ok: boolean, errors: string[] }`.
- `QecCatalogRecord` fields are exactly `id`, `title`, `summary`, `candidateQuestion`, `gateType`, `technicalAnchor`, `createdAt`, and `updatedAt`; `technicalAnchor` fields are `id`, `title`, `sourceUrl`, `persistentId`, and `relevanceRationale`.

- [ ] **Step 1: Read the good-test guidance and write the failing catalog tests**

Read `superpowers/test-driven-development/writing-good-tests.md` completely. Then add tests that assert the complete table above, not only its length:

```js
const EXPECTED_IDENTITIES = [
  ["Prob-002", "Finite-Length qLDPC Code Search Under Hardware Constraints", "finite-length-code-pareto"],
  ["Prob-003", "Circuit-Level qLDPC Decoder Optimization", "circuit-level-decoder-benchmark"],
  ["Prob-004", "Real-Time Decoder Tail-Latency Minimization", "tail-latency-decoder-benchmark"],
  ["Prob-005", "Bounded-Memory Streaming QEC Decoder", "bounded-memory-streaming-benchmark"],
  ["Prob-006", "Adaptive Decoding Under Correlated and Drifting Noise", "noise-drift-holdout"],
  ["Prob-007", "Leakage-Aware Decoder and Reset-Policy Co-Design", "leakage-reset-policy-benchmark"],
  ["Prob-008", "Erasure-Biased Code–Decoder Co-Design", "erasure-code-decoder-pareto"],
  ["Prob-009", "Generalizable Neural Decoder with Calibrated Uncertainty", "cross-domain-neural-decoder"],
  ["Prob-010", "Rare-Event Logical Failure Estimation", "rare-event-estimator-calibration"],
  ["Prob-011", "Reproducible Cross-Code QEC Benchmark Suite", "cross-code-benchmark-reproducibility"],
  ["Prob-012", "Syndrome-Extraction Schedule Search", "syndrome-schedule-benchmark"],
  ["Prob-013", "Flag-Sharing Ancilla Circuit Synthesis", "flag-circuit-fault-enumeration"],
  ["Prob-014", "Noise-Aware Stabilizer Measurement Scheduling", "measurement-cadence-benchmark"],
  ["Prob-015", "Lattice-Surgery Routing and Scheduling", "lattice-surgery-scheduling-benchmark"],
  ["Prob-016", "Multi-Level Magic-State Factory Optimization", "magic-state-factory-pareto"],
  ["Prob-017", "Fault-Tolerant Code-Switching Protocol Synthesis", "code-switching-fault-enumeration"],
  ["Prob-018", "Bias-Preserving Logical Operation Co-Optimization", "bias-preserving-logical-benchmark"],
  ["Prob-019", "Bosonic–Outer-Code Concatenation Co-Design", "bosonic-outer-code-pareto"],
  ["Prob-020", "End-to-End Fault-Tolerant Resource Allocation Under Uncertainty", "end-to-end-resource-estimation-benchmark"],
  ["Prob-021", "Automated Fault-Tolerance Verification for QEC Circuits", "fault-tolerance-formal-verification"],
].map(([id, title, gateType]) => ({ id, title, gateType }));

test("catalog preserves the approved twenty-problem identity and copy", () => {
  assert.deepEqual(QEC_PORTFOLIO_PROBLEMS.map(({ id, title, gateType }) => ({ id, title, gateType })), EXPECTED_IDENTITIES);
  assert.equal(QEC_PORTFOLIO_PROBLEMS[0].summary, "Search for finite-length qLDPC codes that improve the rate–distance–check-weight–decoder-performance frontier.");
  assert.equal(QEC_PORTFOLIO_PROBLEMS.at(-1).candidateQuestion, "Can an automated verifier prove bounded-fault correctness or produce minimal counterexamples across a sealed corpus of syndrome-extraction, logical-gate, and code-switching circuits?");
});

test("catalog IDs, visible copy, source URLs, and OpenAlex identifiers are safe", () => {
  assert.deepEqual(QEC_PORTFOLIO_IDS, Array.from({ length: 20 }, (_, index) => `Prob-${String(index + 2).padStart(3, "0")}`));
  assert.equal(validateQecPortfolioCatalog().ok, true);
  for (const record of QEC_PORTFOLIO_PROBLEMS) {
    assert.doesNotMatch([record.title, record.summary, record.candidateQuestion, record.gateType].join(" "), /\p{Script=Han}/u);
    assert.match(record.technicalAnchor.sourceUrl, /^https:\/\//);
    assert.match(record.technicalAnchor.persistentId, /^doi:10\./i);
  }
});
```

- [ ] **Step 2: Run the catalog test and confirm RED**

Run: `node --test tests/qec-portfolio-catalog.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `lib/qec-portfolio/catalog.mjs`.

- [ ] **Step 3: Implement the frozen catalog and strict validation**

Encode every row from **Canonical Approved Catalog** as a deeply frozen object. Use these invariants in `validateQecPortfolioCatalog`:

```js
const VISIBLE_FIELDS = ["title", "summary", "candidateQuestion", "gateType"];
const CJK = /\p{Script=Han}/u;
const EXPECTED_IDS = Array.from({ length: 20 }, (_, index) => `Prob-${String(index + 2).padStart(3, "0")}`);

export function validateQecPortfolioCatalog(records = QEC_PORTFOLIO_PROBLEMS) {
  const errors = [];
  if (!Array.isArray(records) || records.length !== 20) errors.push("Catalog must contain exactly twenty new problems.");
  if (JSON.stringify(records.map((record) => record.id)) !== JSON.stringify(EXPECTED_IDS)) errors.push("Catalog IDs must be contiguous from Prob-002 through Prob-021.");
  for (const record of records) {
    if (!PROBLEM_ID_PATTERN.test(record.id)) errors.push(`Invalid problem ID: ${record.id}`);
    if (VISIBLE_FIELDS.some((field) => typeof record[field] !== "string" || record[field].trim() === "")) errors.push(`Visible copy is incomplete for ${record.id}.`);
    if (VISIBLE_FIELDS.some((field) => CJK.test(record[field]))) errors.push(`Visible copy must be English-only for ${record.id}.`);
    if (!/^https:\/\//.test(record.technicalAnchor.sourceUrl)) errors.push(`Technical source URL is invalid for ${record.id}.`);
    if (!/^doi:10\./i.test(record.technicalAnchor.persistentId)) errors.push(`OpenAlex persistent ID is invalid for ${record.id}.`);
  }
  return { ok: errors.length === 0, errors };
}
```

For every catalog row, set `technicalAnchor.id` to the template literal `` `anchor-${record.id}` ``, for example `anchor-Prob-002`. Set `technicalAnchor.title` from the exact title table. Set `technicalAnchor.relevanceRationale` to the template literal `` `This source directly motivates the declared gate for ${record.title}.` ``; for `Prob-011`, append ` The official qecsim Citing page maps the software documentation to the persistent thesis DOI.`

Define the McKinsey market evidence as `state: "known"`, interval `{ low: 43_000_000_000, base: 57_000_000_000, high: 71_000_000_000 }`, unit `USD_2035`, `currency: "USD"`, `priceBaseYear: 2035`, evidence tier `authoritative-secondary`, and kind `broad-enabling-market-proxy`. Define the IBM evidence as a lower-bound signal with interval values all `10_000_000_000`, unit `USD_2026`, evidence tier `vendor-or-news`, and kind `investment-floor`; its locator must explicitly say the encoded value is a floor, not a point estimate or capturable value.

- [ ] **Step 4: Run the catalog and existing valuation-contract tests and confirm GREEN**

Run: `node --test tests/qec-portfolio-catalog.test.mjs tests/valuation-contract.test.mjs tests/valuation-codex-adapter.test.mjs`

Expected: all tests PASS.

- [ ] **Step 5: Commit the catalog contract**

```bash
git add lib/qec-portfolio/catalog.mjs tests/qec-portfolio-catalog.test.mjs
git commit -m "feat: add approved QEC portfolio catalog"
```

### Task 2: Safe Draft Staging and Publication

**Files:**
- Create: `lib/qec-portfolio/registration.mjs`
- Create: `scripts/register-qec-portfolio.mjs`
- Create: `tests/qec-portfolio-registration.test.mjs`
- Modify: `package.json`
- Modify: `Makefile`

**Interfaces:**
- Consumes: `QEC_PORTFOLIO_PROBLEMS` and `validateQecPortfolioCatalog()` from Task 1; existing `validateDraftDirectory` and `make problem-publish` behavior.
- Produces: `renderProblemManifest(record): object`, `renderProblemMarkdown(record): string`, `renderGenerationAudit(record): Map<string,string>`, `stageQecProblem({ rootDir, runId, record }): Promise<{ stageDir, digest }>`, `verifyPublishedProblem({ rootDir, record, digest }): Promise<boolean>`, and `registerQecPortfolio({ rootDir, records, publish }): Promise<RegistrationSummary>`.
- `RegistrationSummary` is `{ published: string[], skipped: string[], failed: Array<{ id: string, code: string, message: string }> }`.

- [ ] **Step 1: Write failing rendering, collision, and restart tests**

Use a temporary repository fixture with a valid `Prob-001`. Assert exact five-file staging, exact headings, no visible CJK, chronological timestamps, `sourceCount: 3`, publisher order, collision stop, and verified restart:

```js
async function relativeFiles(directory, prefix = "") {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relativePath = `${prefix}${entry.name}`;
    if (entry.isDirectory()) files.push(...await relativeFiles(join(directory, entry.name), `${relativePath}/`));
    else files.push(relativePath);
  }
  return files.sort();
}

test("stages exactly the approved five-file draft", async () => {
  const { rootDir } = await createRegistrationFixture();
  const result = await stageQecProblem({ rootDir, runId: "20260729T130000Z-catalog", record: QEC_PORTFOLIO_PROBLEMS[0] });
  assert.deepEqual(await relativeFiles(result.stageDir), [
    "generation/decision.md",
    "generation/initial-prompt.md",
    "generation/transcript.md",
    "problem.json",
    "problem.md",
  ]);
  const manifest = JSON.parse(await readFile(join(result.stageDir, "problem.json"), "utf8"));
  assert.deepEqual(manifest.gate, { type: "finite-length-code-pareto", readiness: "specified" });
  assert.equal(manifest.provenance.sourceCount, 3);
  assert.match(await readFile(join(result.stageDir, "problem.md"), "utf8"), /^# Candidate Question\n/m);
});

test("stops at a non-identical collision without publishing later IDs", async () => {
  const { rootDir } = await createRegistrationFixture();
  const calls = [];
  const summary = await registerQecPortfolio({ rootDir, records: QEC_PORTFOLIO_PROBLEMS.slice(0, 3), publish: async ({ id }) => {
    calls.push(id);
    if (id === "Prob-003") return { status: "collision", id, nextProblemId: "Prob-004" };
    return { status: "published", id };
  }});
  assert.deepEqual(calls, ["Prob-002", "Prob-003"]);
  assert.equal(summary.failed[0].code, "PROBLEM_COLLISION");
});
```

- [ ] **Step 2: Run the registration test and confirm RED**

Run: `node --test tests/qec-portfolio-registration.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `lib/qec-portfolio/registration.mjs`.

- [ ] **Step 3: Implement deterministic rendering and hash-verified restart behavior**

Render the manifest with this exact shape:

```js
{
  schemaVersion: 1,
  id: record.id,
  title: record.title,
  summary: record.summary,
  domain: "quantum-computing",
  quantumArea: "error-correction-and-fault-tolerance",
  status: "draft",
  gate: { type: record.gateType, readiness: "specified" },
  provenance: { sourceCount: 3 },
  lastActivity: { summary: "Draft registered from QEC portfolio brainstorming.", at: record.updatedAt },
  createdAt: record.createdAt,
  updatedAt: record.updatedAt,
}
```

Render `problem.md` with exactly these H1 headings and content rules:

```md
# Candidate Question

{candidateQuestion}

# Motivation and Context

{summary}

# Discussion Summary

This user-approved draft is part of a twenty-problem QEC portfolio. It will be evaluated with frozen external citation and economic evidence, Research Value, Autoresearch Fit, and Combined Priority. Registration does not start an autoresearch campaign.

# Evidence Mentioned

- Technical anchor: {technicalAnchor.title} — {technicalAnchor.sourceUrl} ({technicalAnchor.persistentId}).
- Market proxy: McKinsey Quantum Technology Monitor 2026; the quantum-computing internal-market range is enabling context, not problem-specific revenue.
- Investment signal: IBM's 2026 five-year quantum investment announcement; investment is not capturable value.

# Open Qualification Questions

- Which baseline implementation and sealed benchmark instances will be frozen before optimization?
- Which primary metric, resource constraints, and no-regression checks define success for the declared gate?
- Which evidence would establish novelty beyond the technical anchor rather than attention alone?
```

Generation audit content is never rendered. Use an English audit summary in `initial-prompt.md`, record scope B and exact approval in `transcript.md`, and state `Approved after exact preview on 2026-07-29; publish as draft only.` in `decision.md`. Compute the SHA-256 digest from sorted relative paths plus exact bytes. When `problems/<id>` exists, compare all five files against freshly rendered bytes; skip only an exact match and otherwise return `PROBLEM_COLLISION` before invoking the publisher for that ID or any later ID.

- [ ] **Step 4: Implement the CLI and trust-boundary invocation**

The CLI validates the catalog, creates a unique staging run, and injects this publisher without a shell:

```js
async function publish({ id, stageDir }) {
  const relativeStage = relative(rootDir, stageDir);
  const { stdout } = await execFile("make", ["problem-publish", `STAGE=${relativeStage}`, `ID=${id}`], { cwd: rootDir });
  return JSON.parse(stdout);
}
```

Add package script `"qec-portfolio:register": "node scripts/register-qec-portfolio.mjs"` and Make target:

```make
qec-portfolio-register: node_modules/.package-lock.json
	@npm run --silent qec-portfolio:register
```

- [ ] **Step 5: Run targeted publisher tests and confirm GREEN**

Run: `node --test tests/qec-portfolio-catalog.test.mjs tests/qec-portfolio-registration.test.mjs tests/problem-draft-contract.test.mjs tests/problem-draft-publisher.test.mjs tests/problem-indexer.test.mjs`

Expected: all tests PASS and no real `problems/Prob-002` directory is created by tests.

- [ ] **Step 6: Commit registration support**

```bash
git add lib/qec-portfolio/registration.mjs scripts/register-qec-portfolio.mjs tests/qec-portfolio-registration.test.mjs package.json Makefile
git commit -m "feat: register approved QEC problem drafts"
```

### Task 3: Approved-Evidence Valuation Researcher

**Files:**
- Create: `lib/qec-portfolio/valuation-researcher.mjs`
- Create: `tests/qec-portfolio-valuation.test.mjs`

**Interfaces:**
- Consumes: `getQecPortfolioProblem(id)` and `COMMON_ECONOMIC_EVIDENCE` from Task 1; the existing `researcher.run(options)` contract used by `createValuationJobManager`.
- Produces: `PROB_001_VALUATION_PROFILE`, `createQecPortfolioValuationResearcher({ catalog? }): { run(options): Promise<{ ok: true, candidate, stderr: "", eventsText: "" } | { ok: false, code: string, message: string }> }`, and `buildApprovedValuationCandidate({ problem, quantumScope }): object`.
- The returned candidate has exactly the existing required fields: `schemaVersion`, `problemId`, `scope`, `anchorCandidates`, `paperInclusionRules`, `technicalStages`, `classicalBaseline`, `marketEvidence`, `atomicInputs`, `materialAssumptions`, and `warnings`.
- The researcher supports all twenty catalog records plus an explicit `Prob-001` valuation profile; it rejects every other ID with `{ ok: false, code: "UNAPPROVED_PORTFOLIO_PROBLEM", message }`.

- [ ] **Step 1: Write failing strict-candidate tests**

Exercise all twenty-one records and assert identity, anchor mapping, common market evidence, conservative unknowns, public visibility, and compatibility with the existing candidate validator through a valuation-manager fixture:

```js
test("builds one strict approved-evidence candidate for every portfolio problem", async () => {
  const researcher = createQecPortfolioValuationResearcher();
  const records = [
    PROB_001_VALUATION_PROFILE,
    ...QEC_PORTFOLIO_PROBLEMS.map((record) => ({ ...record, technicalAnchors: [record.technicalAnchor] })),
  ];
  for (const record of records) {
    const result = await researcher.run({
      problem: { id: record.id, title: record.title, summary: record.summary },
      quantumScope: { status: "supported", domain: "quantum-computing", quantumArea: "error-correction-and-fault-tolerance" },
    });
    assert.equal(result.ok, true);
    assert.deepEqual(result.candidate.anchorCandidates.map((item) => item.persistentId), record.technicalAnchors.map((item) => item.persistentId));
    assert.deepEqual(result.candidate.marketEvidence.map((item) => item.id), ["mckinsey-qc-internal-market-2035", "ibm-quantum-investment-floor-2026"]);
    assert.equal(result.candidate.materialAssumptions.find((item) => item.id === "capturable-value")?.proposedValue.state, "unknown");
  }
});
```

- [ ] **Step 2: Run the valuation-researcher test and confirm RED**

Run: `node --test tests/qec-portfolio-valuation.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `lib/qec-portfolio/valuation-researcher.mjs`.

- [ ] **Step 3: Implement exact candidate construction**

For each new problem, produce one `anchorCandidates` entry from its approved `technicalAnchor`. Expose a module-level `PROB_001_VALUATION_PROFILE` for the existing problem with these two exact anchors:

```js
{
  id: "Prob-001",
  title: "AutoQEC CSS Distance Campaign",
  summary: "Imported AutoQEC CSS-distance experimental audit record.",
  technicalAnchors: [{
    id: "anchor-fast-quantum-distance-2026",
    persistentId: "doi:10.1145/3795877",
    title: "Fast Algorithms and Implementations for Computing the Minimum Distance of Quantum Codes",
    sourceUrl: "https://doi.org/10.1145/3795877",
    relevanceRationale: "Direct published baseline for fast quantum-code minimum-distance computation.",
  }, {
    id: "anchor-qdistrnd-2022",
    persistentId: "doi:10.21105/joss.04120",
    title: "QDistRnd: A GAP package for computing the distance of quantum error-correcting codes",
    sourceUrl: "https://doi.org/10.21105/joss.04120",
    relevanceRationale: "Published open-software baseline for randomized quantum-code distance computation.",
  }],
}
```

Normalize a catalog record internally to `technicalAnchors: [record.technicalAnchor]`. Use these exact paper rules and warnings:

```js
paperInclusionRules: {
  include: ["Directly evaluates the declared QEC problem, baseline, gate metric, or implementation constraint."],
  exclude: ["General quantum-computing work without a direct QEC connection.", "Market forecasts used as technical or novelty evidence."],
},
warnings: [
  "External valuation evidence is not trusted knowledge; it is frozen for local advisory assessment only.",
  "Citation counts measure scientific attention, not novelty or solution quality.",
  "The McKinsey range and IBM investment are broad enabling signals, not problem-specific capturable value.",
  "Technical success remains uncertain until the declared gate is run on a sealed benchmark.",
],
```

Use three technical stages: freeze baseline/benchmark/metric; run at most 200 attempts or eight wall-clock hours; evaluate once on a sealed holdout and report regressions. Use a classical baseline description of `The declared implementation and metric reported by the approved technical anchor, frozen before optimization.` and its approved source URL.

Use `atomicInputs` for four explicitly typed facts: attempt budget `200 count`, wall-clock budget `8 hours`, allowed secondary-metric regression `0.05 fraction`, and technical success unknown because the sealed gate has not run. The three known assumptions cite one `operator-assumption` source whose URL is `https://research-loop.local/qec-portfolio` and locator is `User-approved QEC portfolio evaluation policy, 2026-07-29.` Use `evidenceTier: "assumption"` and `evidenceState: "reported"`.

Use these `materialAssumptions`:

1. `sealed-evaluation`: exact sealed benchmark composition is unknown; sensitivity rank 1; `confirmationRequired: false` because the user approved the policy but the benchmark must still be frozen before a campaign.
2. `capturable-value`: unknown with reason `No problem-specific pricing, licensing, contract, product-margin, or willingness-to-pay source has been identified.`; sensitivity rank 2; `confirmationRequired: false`.
3. `fixed-budget`: known eight-hour budget backed by the operator-assumption source; sensitivity rank 3; `confirmationRequired: false`.

Do not synthesize a feasibility probability, revenue share, or problem-specific market allocation.

- [ ] **Step 4: Run candidate, valuation manager, privacy, and snapshot tests and confirm GREEN**

Run: `node --test tests/qec-portfolio-valuation.test.mjs tests/valuation-codex-adapter.test.mjs tests/valuation-job-manager.test.mjs tests/valuation-privacy.test.mjs tests/valuation-snapshot.test.mjs`

Expected: all tests PASS; the manager reaches `needs_confirmation`, accepts the exact anchor, freezes three files, and never turns Capturable Value into zero.

- [ ] **Step 5: Commit the deterministic researcher**

```bash
git add lib/qec-portfolio/valuation-researcher.mjs tests/qec-portfolio-valuation.test.mjs
git commit -m "feat: build approved QEC valuation candidates"
```

### Task 4: Restartable Twenty-One-Problem Batch Runner

**Files:**
- Create: `lib/qec-portfolio/batch-runner.mjs`
- Create: `lib/qec-portfolio/openalex-retry.mjs`
- Create: `scripts/run-qec-portfolio.mjs`
- Create: `scripts/verify-qec-portfolio.mjs`
- Create: `tests/qec-portfolio-batch.test.mjs`
- Create: `tests/qec-portfolio-openalex-retry.test.mjs`
- Modify: `package.json`
- Modify: `Makefile`

**Interfaces:**
- Consumes: `registerQecPortfolio`, `createQecPortfolioValuationResearcher`, `createValuationJobManager`, `createAssessmentJobManager`, `createOpenAlexClient`, `createValuationSnapshotStore`, `createArtifactStore`, and the existing problem repository/index/resolver adapters.
- Produces: `createRetryingOpenAlexClient({ client, delay?, maxAttempts?, baseDelayMs? }): { expand(options): Promise<object[]> }`, `createQecPortfolioBatchRunner(dependencies): { run(): Promise<BatchSummary> }`, `waitForTerminalState(read, options): Promise<object>`, and `verifyQecPortfolio({ rootDir }): Promise<VerificationSummary>`.
- `BatchSummary` is `{ status: "complete" | "incomplete", phases: object, problems: Array<{ id, registration, valuation, assessment, error }> }` and is printed as one JSON object by the CLI.

- [ ] **Step 1: Write failing orchestration tests with fake managers**

Cover first run, ambiguity selection, manager failure, and restart. Assert the exact external alternative and no duplicate work:

```js
const EXTERNAL_ALTERNATIVE = {
  page: "__external__/valuation-snapshot",
  topic: "external-valuation",
  title: "Continue with external valuation evidence only",
  matchKind: "external-valuation",
};

test("confirms approved anchors and selects only the external valuation alternative", async () => {
  const { runner, calls } = fixtureRunner();
  const summary = await runner.run();
  assert.equal(summary.status, "complete");
  assert.deepEqual(calls.confirm[0], {
    candidateHash: "a".repeat(64),
    acceptedAnchorIds: ["anchor-Prob-002"],
    assumptionDecisions: [],
  });
  assert.deepEqual(calls.select[0].alternative, EXTERNAL_ALTERNATIVE);
});

test("restart skips only verified snapshots and completed version-two assessments", async () => {
  const { runner, calls } = fixtureRunner({ verifiedSnapshot: true, completedAssessment: true });
  const summary = await runner.run();
  assert.equal(summary.problems[0].valuation, "verified-existing");
  assert.equal(summary.problems[0].assessment, "verified-existing");
  assert.equal(calls.valuationStart.length, 0);
  assert.equal(calls.assessmentStart.length, 0);
});
```

- [ ] **Step 2: Run the batch tests and confirm RED**

Run: `node --test tests/qec-portfolio-batch.test.mjs tests/qec-portfolio-openalex-retry.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for the batch-runner and OpenAlex-retry modules.

- [ ] **Step 3: Implement bounded OpenAlex retry behavior**

Wrap the existing client rather than changing its evidence semantics. Use `maxAttempts: 3`, `baseDelayMs: 2_000`, and delays of 2,000 then 4,000 milliseconds. Retry only `OPENALEX_PROVIDER_ERROR`; immediately rethrow `OPENALEX_KEY_REQUIRED`, validation errors, and the third transient failure. The test injects a zero-cost delay, verifies success on the third call, and verifies that a missing key is attempted exactly once.

```js
const defaultDelay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export function createRetryingOpenAlexClient({ client, delay = defaultDelay, maxAttempts = 3, baseDelayMs = 2_000 }) {
  return Object.freeze({
    async expand(options) {
      for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
          return await client.expand(options);
        } catch (error) {
          if (error?.code !== "OPENALEX_PROVIDER_ERROR" || attempt === maxAttempts) throw error;
          await delay(baseDelayMs * (2 ** (attempt - 1)));
        }
      }
      throw new Error("OpenAlex retry loop ended without a result.");
    },
  });
}
```

- [ ] **Step 4: Implement phase orchestration and terminal-state polling**

The runner executes these phases in order and processes problem IDs ascending:

```text
catalog validation
registration of Prob-002 through Prob-021
problem-index rebuild and exact 21-QEC-record verification
valuation snapshot verification or start -> needs_confirmation -> exact confirmation -> ready -> snapshot verify
assessment verification or start -> needs-input -> select exact external alternative -> completed
final portfolio artifact verification
```

Use bounded polling with an injected delay, 2.5-second production interval, and explicit 30-minute per-valuation/30-minute per-assessment deadlines. A terminal `research_failed` or `failed` state records the problem error and continues to collect diagnostics, but the final process exits non-zero. After valuation reports `ready`, call `store.verify(problemId, snapshotId)` and require `manifest.complete === true`; an immutable incomplete provider-failure snapshot is retained but does not satisfy the batch. This causes the existing incomplete `Prob-001` snapshot to be preserved and superseded by a new complete snapshot built from the explicit profile in Task 3.

An existing assessment is reusable only when `run.status === "completed"`, `run.summary` exists, `input.schemaVersion === 2`, its valuation snapshot/content hashes match a verified current snapshot, and its report contains no CJK code points. Otherwise start a fresh run; never modify the old run.

- [ ] **Step 5: Compose the production CLI with explicit preflights**

Before any new valuation starts, require a non-empty `OPENALEX_API_KEY`; print `OPENALEX_KEY_REQUIRED` without printing the secret. Load `.generated/problem-index.json`, create a repository with `getProblem`, `listProblems`, and `readProblemMarkdown`, and instantiate:

```js
const valuationStore = createValuationSnapshotStore({ rootDir });
const valuationManager = createValuationJobManager({
  rootDir,
  repository,
  researcher: createQecPortfolioValuationResearcher(),
  openAlex: createRetryingOpenAlexClient({
    client: createOpenAlexClient({ apiKey: process.env.OPENALEX_API_KEY }),
  }),
  store: valuationStore,
});
const assessmentStore = createArtifactStore({ rootDir });
const assessmentManager = createAssessmentJobManager({
  rootDir,
  repository,
  store: assessmentStore,
  valuationStore,
  resolveKnowledge: createKnowledgeResolver(rootDir),
});
```

Always shut down both managers in `finally`. Print the complete JSON summary to stdout and set `process.exitCode = 1` when any phase is incomplete.

- [ ] **Step 6: Implement the independent verifier**

`verifyQecPortfolio` must read from disk rather than trusting runner memory. Require:

- exact IDs `Prob-001` through `Prob-021` in the QEC area;
- exact catalog manifests for `Prob-002` through `Prob-021`;
- at least one hash-valid, complete frozen snapshot per problem;
- at least one completed schema-v2 assessment bound to the selected valid snapshot per problem;
- a present `report.html` for every selected run;
- `assessment.json` envelope language equal to `en` for every selected run;
- no `\p{Script=Han}` in new `problem.json`, new `problem.md`, selected `assessment.json`, selected `run.json` summary, or selected `report.html`;
- exactly twenty-one rows from the portfolio reader once Task 5 is present.

Return `{ ok, problemIds, snapshotIds, assessmentRunIds, errors }`; never delete or rewrite a failing artifact.

- [ ] **Step 7: Add package and Make commands**

Add scripts:

```json
"qec-portfolio:run": "node scripts/run-qec-portfolio.mjs",
"qec-portfolio:verify": "node scripts/verify-qec-portfolio.mjs"
```

Add Make targets:

```make
qec-portfolio-run: node_modules/.package-lock.json
	@npm run --silent qec-portfolio:run

qec-portfolio-verify: node_modules/.package-lock.json
	@npm run --silent qec-portfolio:verify
```

- [ ] **Step 8: Run batch unit tests and confirm GREEN**

Run: `node --test tests/qec-portfolio-openalex-retry.test.mjs tests/qec-portfolio-batch.test.mjs tests/valuation-job-manager.test.mjs tests/assessment-job-manager.test.mjs tests/assessment-artifacts.test.mjs`

Expected: all tests PASS with fake OpenAlex/Codex dependencies; no live network or Codex process is invoked.

- [ ] **Step 9: Commit the batch runner**

```bash
git add lib/qec-portfolio/batch-runner.mjs lib/qec-portfolio/openalex-retry.mjs scripts/run-qec-portfolio.mjs scripts/verify-qec-portfolio.mjs tests/qec-portfolio-batch.test.mjs tests/qec-portfolio-openalex-retry.test.mjs package.json Makefile
git commit -m "feat: orchestrate QEC portfolio assessments"
```

### Task 5: Read-Only Portfolio Projection and Local Endpoint

**Files:**
- Create: `lib/qec-portfolio/reader.mjs`
- Create: `lib/qec-portfolio/view-model.mjs`
- Create: `tests/qec-portfolio-reader.test.mjs`
- Modify: `lib/assessments/local-service.mjs`
- Modify: `scripts/local-assessment-service.mjs`
- Modify: `tests/assessment-local-service.test.mjs`

**Interfaces:**
- Consumes: repository `listProblems`, artifact-store `listRuns`, and completed `run.summary` returned by `summarizeCompletedAssessment`.
- Produces: `createQecPortfolioReader({ repository, assessmentStore }): { read(): Promise<PortfolioResponse> }`, `sortPortfolioRows(rows, sort): PortfolioRow[]`, and authenticated `GET /__local/assessments/portfolio`.
- `PortfolioResponse` is `{ schemaVersion: 1, generatedAt: string, evidenceLabel: "External-evidence-backed advisory comparison", count: number, rows: PortfolioRow[] }`.
- `PortfolioRow` fields are `problemId`, `title`, `status`, `verdict`, `confidence`, `researchValue`, `autoresearchFit`, `combinedPriority`, `scientificAttention`, `technicalSuccess`, `socialValue`, `capturableValue`, `largestBottleneck`, `snapshotId`, `problemHref`, and `reportHref`. Missing assessment fields are `null`, never fabricated zeroes.

- [ ] **Step 1: Write failing join, sorting, redaction, and route tests**

```js
test("returns all QEC rows sorted by Combined Priority descending and ID as tie-break", async () => {
  const response = await fixtureReader().read();
  assert.equal(response.count, 21);
  assert.deepEqual(response.rows.slice(0, 3).map((row) => row.problemId), ["Prob-003", "Prob-002", "Prob-001"]);
  assert.equal(response.rows[0].problemHref, "/problems/Prob-003");
  assert.equal(response.rows[0].reportHref, "/__local/assessments/reports/Prob-003/run-3");
});

test("serves the portfolio only with the local capability token", async () => {
  const unauthorized = await request(createAssessmentService({ token: "secret", manager: {}, portfolioReader }), "/__local/assessments/portfolio");
  assert.equal(unauthorized.status, 401);
  const response = await request(createAssessmentService({ token: "secret", manager: {}, portfolioReader }), "/__local/assessments/portfolio", { headers: tokenHeaders });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).count, 21);
});
```

- [ ] **Step 2: Run reader and local-service tests and confirm RED**

Run: `node --test tests/qec-portfolio-reader.test.mjs tests/assessment-local-service.test.mjs`

Expected: FAIL because the reader module and route do not exist.

- [ ] **Step 3: Implement safe projection and stable sorting**

Filter on both `domain === "quantum-computing"` and `quantumArea === "error-correction-and-fault-tolerance"`. For each problem, select the newest completed run with a summary using `updatedAt` then `runId` descending. Map summary fields as follows:

| Portfolio field | Summary source |
|---|---|
| `researchValue` | `summary.scores.researchValue` |
| `autoresearchFit` | `summary.scores.autoresearchSuitability` |
| `combinedPriority` | `summary.scores.combined` |
| `scientificAttention` | `summary.quantitative.scientificAttention` |
| `technicalSuccess` | `summary.quantitative.technicalSuccess` |
| `socialValue` | `summary.quantitative.socialValue` |
| `capturableValue` | `summary.quantitative.capturableValue` |
| `snapshotId` | `summary.quantitative.snapshotId` |

Default sort is combined estimate descending with nulls last and problem ID ascending as tie-break. `sortPortfolioRows` supports exact keys `combined`, `research-value`, `autoresearch-fit`, `verdict`, and `scientific-attention`; never mutate the input array. Return only the public summary projection—no event logs, prompts, tokens, private valuation inputs, or filesystem paths.

- [ ] **Step 4: Add and wire the authenticated GET route**

Extend the constructor to `createAssessmentService({ rootDir, token, manager, valuationManager = null, portfolioReader = null })`. Before the parameterized problem route, add:

```js
if (request.method === "GET" && pathname === "/__local/assessments/portfolio") {
  if (!portfolioReader?.read) return send(response, 404, { error: "NOT_FOUND" });
  return send(response, 200, await portfolioReader.read());
}
```

In `scripts/local-assessment-service.mjs`, add `portfolioReader = null` to `startAssessmentService` options. Instantiate `localAssessmentStore = createArtifactStore({ rootDir: workspaceRoot })`, pass it to the default assessment manager as `store`, construct the default portfolio reader with the same repository and `localAssessmentStore`, and pass the reader to `createAssessmentService`. Keep the server bound to `127.0.0.1` and retain token enforcement. Tests that inject both managers also inject a fixture reader so repository loading remains unnecessary.

- [ ] **Step 5: Run reader, service, and privacy tests and confirm GREEN**

Run: `node --test tests/qec-portfolio-reader.test.mjs tests/assessment-local-service.test.mjs tests/valuation-privacy.test.mjs`

Expected: all tests PASS; serialized portfolio JSON contains neither the token nor private inputs.

- [ ] **Step 6: Commit the projection and endpoint**

```bash
git add lib/qec-portfolio/reader.mjs lib/qec-portfolio/view-model.mjs tests/qec-portfolio-reader.test.mjs lib/assessments/local-service.mjs scripts/local-assessment-service.mjs tests/assessment-local-service.test.mjs
git commit -m "feat: serve local QEC portfolio data"
```

### Task 6: English-Only Local Comparison Page

**Files:**
- Create: `app/qec-portfolio/page.tsx`
- Create: `app/qec-portfolio/portfolio-panel.tsx`
- Create: `app/qec-portfolio/portfolio-panel.module.css`
- Create: `tests/qec-portfolio-page.test.mjs`

**Interfaces:**
- Consumes: `GET /__local/assessments/portfolio`, `sortPortfolioRows`, and the `PortfolioResponse`/`PortfolioRow` shape from Task 5.
- Produces: local route `/qec-portfolio`; no new deployed mutation or execution route.

- [ ] **Step 1: Write failing source-contract tests for copy and preserved surfaces**

```js
test("QEC portfolio page spells out V, A, and S and contains no visible Chinese", async () => {
  const source = await readFile("app/qec-portfolio/portfolio-panel.tsx", "utf8");
  assert.match(source, /Research Value \(V\)/);
  assert.match(source, /Autoresearch Fit \(A\)/);
  assert.match(source, /Combined Priority \(S\)/);
  assert.match(source, /External-evidence-backed advisory comparison/);
  assert.doesNotMatch(source, /\p{Script=Han}/u);
});

test("QEC portfolio route owns its styles without importing preserved global surfaces", async () => {
  const page = await readFile("app/qec-portfolio/page.tsx", "utf8");
  const panel = await readFile("app/qec-portfolio/portfolio-panel.tsx", "utf8");
  assert.match(panel, /portfolio-panel\.module\.css/);
  assert.doesNotMatch(`${page}\n${panel}`, /app\/globals\.css|app\/page\.tsx|app\/layout\.tsx/);
});
```

- [ ] **Step 2: Run the page test and confirm RED**

Run: `node --test tests/qec-portfolio-page.test.mjs`

Expected: FAIL with `ENOENT` for `app/qec-portfolio/portfolio-panel.tsx`.

- [ ] **Step 3: Implement the static-safe page shell and client states**

`page.tsx` renders a semantic `<main>` with a back link to `/`, title `QEC Problem Portfolio`, and `<PortfolioPanel />`. The client panel starts with `Loading the local QEC portfolio…`, fetches with `{ cache: "no-store" }`, and displays `This comparison is available when the local assessment service is running.` on 404/network unavailability. It must not expose a control that starts valuation, assessment, or autoresearch.

- [ ] **Step 4: Implement sortable table and responsive cards**

Provide sort controls for exactly:

```ts
const SORT_OPTIONS = [
  ["combined", "Combined Priority (S)"],
  ["research-value", "Research Value (V)"],
  ["autoresearch-fit", "Autoresearch Fit (A)"],
  ["verdict", "Verdict"],
  ["scientific-attention", "Scientific Attention"],
] as const;
```

Every desktop row and mobile card shows ID/title, verdict/confidence, V/A/S estimate and interval, Scientific Attention, Technical Success, Industry/Social Enabling-Value Proxy, Capturable Value, largest bottleneck, `Open problem`, and `Open detailed report`. Render an unknown quantitative value as `Unknown — <reason>`; never show a bare `unknown` or replace an unknown with zero. Default to Combined Priority descending.

Use only the CSS module for route styling. Provide visible focus states, table overflow at narrow widths, card fallback under 760 px, and `aria-sort` on the active table header.

- [ ] **Step 5: Run page, build, and rendered-content tests and confirm GREEN**

Run: `node --test tests/qec-portfolio-page.test.mjs`

Run: `npm run build`

Run: `npm run test:rendered`

Expected: all commands PASS; the static build includes `/qec-portfolio` but contains no assessment artifacts or local execution endpoint implementation.

- [ ] **Step 6: Commit the local portfolio UI**

```bash
git add app/qec-portfolio/page.tsx app/qec-portfolio/portfolio-panel.tsx app/qec-portfolio/portfolio-panel.module.css tests/qec-portfolio-page.test.mjs
git commit -m "feat: add local QEC portfolio comparison page"
```

### Task 7: Full Regression Verification Before Real Data Generation

**Files:**
- Modify only if a failing test exposes a defect in files owned by Tasks 1–6; do not repair unrelated dirty worktree state.

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: a green codebase suitable for the authorized local batch run.

- [ ] **Step 1: Run the focused QEC portfolio suite**

Run:

```bash
node --test tests/qec-portfolio-catalog.test.mjs tests/qec-portfolio-registration.test.mjs tests/qec-portfolio-valuation.test.mjs tests/qec-portfolio-openalex-retry.test.mjs tests/qec-portfolio-batch.test.mjs tests/qec-portfolio-reader.test.mjs tests/qec-portfolio-page.test.mjs
```

Expected: all tests PASS.

- [ ] **Step 2: Run the complete problem/valuation/assessment unit suite**

Run: `npm run test:unit:problems`

Expected: all tests PASS.

- [ ] **Step 3: Run lint, build, and the full repository suite**

Run: `npm run lint`

Run: `npm run build`

Run: `npm test`

Expected: all commands PASS. If the full suite exposes a pre-existing unrelated failure, record the exact command and evidence separately; do not mask it or combine an unrelated fix with this feature.

- [ ] **Step 4: Review the cumulative implementation diff**

Run:

```bash
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; preserved dashboard files and `public/knowledge/` are absent from this feature's diff.

### Task 8: Generate, Verify, and Visually Inspect the Local Twenty-One-Report Portfolio

**Files:**
- Runtime writes: `problems/Prob-002` through `problems/Prob-021` via the publisher.
- Runtime writes: immutable `problems/Prob-*/valuation/snapshots/<snapshot-id>/` and `problems/Prob-*/assessments/<run-id>/` artifacts; these trees remain local/ignored under the repository policy.
- Runtime writes: `.generated/problem-index.json` and bounded staging directories owned by existing services.

**Interfaces:**
- Consumes: `make qec-portfolio-run`, `make qec-portfolio-verify`, local development server, and `/qec-portfolio`.
- Produces: exactly twenty-one locally viewable completed reports and one verified comparison page.

- [ ] **Step 1: Confirm the live evidence-provider preflight without exposing credentials**

Run: `test -n "$OPENALEX_API_KEY"`

Expected: exit status 0 and no output. If absent, stop before publication/valuation and request the credential through the existing local environment mechanism; never print or persist it.

- [ ] **Step 2: Run the authorized restartable portfolio batch**

Run: `make qec-portfolio-run`

Expected: one final JSON object with `status: "complete"`; `published` contains `Prob-002` through `Prob-021` on the first run, all twenty-one valuation states reference complete hash-valid snapshots, and all twenty-one assessment states are completed. Provider retries and Codex execution may take substantial time; continue polling through the runner rather than starting duplicate jobs.

- [ ] **Step 3: Run the independent on-disk verifier**

Run: `make qec-portfolio-verify`

Expected: a JSON object whose `ok` field is `true`, with exactly twenty-one problem IDs, twenty-one snapshot IDs, twenty-one assessment run IDs, and an empty errors array.

- [ ] **Step 4: Re-run the batch to prove restart safety**

Run: `make qec-portfolio-run`

Expected: `status: "complete"`; registration, valuation, and assessment fields report verified-existing/skipped states and no new immutable artifact is created.

- [ ] **Step 5: Start or refresh the local development server on port 5174**

Run: `npm run dev -- --host 127.0.0.1 --port 5174`

Expected: the app listens at `http://127.0.0.1:5174`, `/__local/assessments/portfolio` is reachable through the app proxy, and the assessment sidecar remains loopback-only.

- [ ] **Step 6: Inspect the portfolio with the in-app browser skill**

Read `browser:control-in-app-browser/SKILL.md` completely, navigate to `http://localhost:5174/qec-portfolio`, and verify from rendered state:

- heading and advisory evidence label are English;
- exactly twenty-one rows/cards appear;
- default order is descending Combined Priority (S);
- changing each sort option updates order without losing rows;
- the table spells out Research Value (V), Autoresearch Fit (A), and Combined Priority (S);
- unknown values include explanatory reasons;
- `Open problem` works for `Prob-001`, one middle record, and `Prob-021`;
- `Open detailed report` works for the same three records;
- no visible CJK text appears on the portfolio or those three reports.

- [ ] **Step 7: Capture final proof and run completion verification**

Record the verified local URL, twenty-one count, three sampled report URLs, final `make qec-portfolio-verify` output, and final test command results in the handoff. Use `superpowers:verification-before-completion` before stating that generation, assessment, or deployment is complete.

import { formatKnownInterval, formatMoneyInterval } from "./view-model.mjs";
import { redactPrivate } from "../valuations/privacy.mjs";

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function scoreText(interval) {
  return `${interval.estimate} (${interval.min}-${interval.max})`;
}

function dimensionRows(dimensions) {
  return dimensions.map((item) => `
    <tr>
      <th scope="row">${escapeHtml(item.label)}</th>
      <td>${escapeHtml(item.id)}</td>
      <td>${escapeHtml(item.weight)}</td>
      <td>${escapeHtml(scoreText(item.score))}</td>
      <td>${escapeHtml(item.evidenceState)}</td>
      <td>${escapeHtml(item.rationale)}</td>
      <td>${escapeHtml(item.evidenceRefs.join(", "))}</td>
    </tr>`).join("");
}

function safeExternalHref(value) {
  if (typeof value !== "string" || value.length === 0) return null;
  if (/^10\.\S+\/\S+$/i.test(value)) return `https://doi.org/${encodeURIComponent(value).replaceAll("%2F", "/")}`;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function externalLink(value, label = value) {
  const href = safeExternalHref(value);
  return href ? `<a href="${escapeHtml(href)}" rel="noreferrer">${escapeHtml(label)}</a>` : escapeHtml(label ?? "—");
}

function listItems(items, fallback = "None recorded.") {
  const values = Array.isArray(items) ? items : [];
  return values.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || `<li>${escapeHtml(fallback)}</li>`;
}

function formatQuantitativeValue(value) {
  if (!value) return "—";
  if (value.currency || /^[A-Z]{3}_\d{4}$/.test(value.unit ?? "")) return formatMoneyInterval(value);
  return formatKnownInterval(value);
}

function evidenceMetricRows(quantitative) {
  const scientific = quantitative?.scientificAttention ?? {};
  const rows = [
    ["Scientific attention", scientific.value],
    ["Citation momentum", scientific.momentum],
    ["Technical success", quantitative?.technicalFeasibility],
    ["Social value", quantitative?.socialValue],
    ["Capturable value", quantitative?.capturableValue],
    ["Information value", quantitative?.informationValue],
  ];
  return rows.map(([label, value]) => `
    <tr><th scope="row">${escapeHtml(label)}</th><td>${escapeHtml(formatQuantitativeValue(value))}</td></tr>`).join("");
}

function paperRows(papers) {
  const values = Array.isArray(papers) ? papers : [];
  return values.map((paper) => `
    <tr>
      <th scope="row">${escapeHtml(paper.id ?? "paper")}</th>
      <td>${escapeHtml(paper.title ?? "Untitled")}</td>
      <td>${externalLink(paper.sourceUrl, paper.sourceUrl ? "source" : "—")}</td>
      <td>${paper.doi ? externalLink(paper.doi, paper.doi) : "—"}</td>
      <td>${escapeHtml(paper.citedByCount ?? "—")}</td>
    </tr>`).join("") || "<tr><td colspan=\"5\">No anchor papers recorded.</td></tr>";
}

function stageRows(stages) {
  const values = Array.isArray(stages) ? stages : [];
  return values.map((stage) => `
    <tr>
      <th scope="row">${escapeHtml(stage.id ?? "stage")}</th>
      <td>${escapeHtml(stage.description ?? stage.label ?? "—")}</td>
      <td>${escapeHtml(formatQuantitativeValue(stage.success))}</td>
      <td>${escapeHtml(formatQuantitativeValue(stage.cost))}</td>
    </tr>`).join("") || "<tr><td colspan=\"4\">No stage tree recorded.</td></tr>";
}

function atomicRows(inputs) {
  const values = Array.isArray(inputs) ? inputs : [];
  return values.map((input) => `
    <tr>
      <th scope="row">${escapeHtml(input.id ?? "input")}</th>
      <td>${escapeHtml(formatQuantitativeValue(input))}</td>
      <td>${escapeHtml(input.reason ?? input.question ?? "—")}</td>
    </tr>`).join("") || "<tr><td colspan=\"3\">No atomic inputs recorded.</td></tr>";
}

function assumptionRows(assumptions) {
  const values = Array.isArray(assumptions) ? assumptions : [];
  return values.map((assumption) => `
    <tr>
      <th scope="row">${escapeHtml(assumption.id ?? "assumption")}</th>
      <td>${escapeHtml(assumption.question ?? assumption)}</td>
      <td>${escapeHtml(assumption.confirmationRequired === true ? "required" : "automatic")}</td>
    </tr>`).join("") || "<tr><td colspan=\"3\">No material assumptions recorded.</td></tr>";
}

function scoreAnchorRows(anchors) {
  const values = Array.isArray(anchors) ? anchors : [];
  return values.map((anchor) => `
    <tr>
      <th scope="row">${escapeHtml(anchor.dimensionId)}</th>
      <td>${escapeHtml(scoreText(anchor.recommended))}</td>
      <td>${escapeHtml((anchor.evidenceIds ?? []).join(", "))}</td>
      <td>${escapeHtml(anchor.override ?? "none")}</td>
    </tr>`).join("") || "<tr><td colspan=\"4\">No score anchors recorded.</td></tr>";
}

function sensitivityRows(sensitivity) {
  const values = Array.isArray(sensitivity) ? sensitivity : [];
  return values.map((item) => `
    <tr>
      <th scope="row">${escapeHtml(item.label ?? item.id)}</th>
      <td>${escapeHtml(item.id ?? "—")}</td>
      <td>${escapeHtml(item.swing ?? "—")}</td>
    </tr>`).join("") || "<tr><td colspan=\"3\">No sensitivity analysis recorded.</td></tr>";
}

function renderValuationAudit({ input, assessment }) {
  if (!input?.valuation && !assessment?.quantitativeEvidence) return "";
  const valuation = input.valuation ?? {};
  const recalculation = redactPrivate(valuation.recalculationInputs ?? {});
  const quantitative = redactPrivate(assessment.quantitativeEvidence ?? {});
  const candidate = recalculation.manifest?.confirmedCandidate ?? {};
  const freshness = valuation.freshness ?? {};
  const warnings = [
    ...(Array.isArray(quantitative.warnings) ? quantitative.warnings : []),
    ...((freshness.staleClasses ?? []).map((name) => `${name} evidence may be stale`)),
  ];
  return `
  <h2>External valuation evidence</h2>
  <p class="muted">External evidence is frozen for audit and is not trusted knowledge.</p>
  <table><tbody>
    <tr><th scope="row">Snapshot ID</th><td><code>${escapeHtml(valuation.snapshotId ?? quantitative.snapshot?.snapshotId ?? "—")}</code></td></tr>
    <tr><th scope="row">Content hash</th><td><code>${escapeHtml(valuation.contentHash ?? quantitative.snapshot?.contentHash ?? "—")}</code></td></tr>
    <tr><th scope="row">Snapshot hash</th><td><code>${escapeHtml(valuation.snapshotHash ?? "—")}</code></td></tr>
    <tr><th scope="row">Visibility</th><td>${escapeHtml(valuation.visibility ?? quantitative.snapshot?.visibility ?? "public")}</td></tr>
  </tbody></table>
  <h2>Formula audit</h2>
  <h2>Scenario intervals</h2>
  <table><tbody>${evidenceMetricRows(quantitative)}</tbody></table>
  <h2>Anchor papers</h2>
  <table><thead><tr><th>ID</th><th>Title</th><th>Source</th><th>DOI</th><th>Citations</th></tr></thead><tbody>${paperRows(recalculation.papers)}</tbody></table>
  <h2>Stage tree</h2>
  <table><thead><tr><th>ID</th><th>Description</th><th>Success</th><th>Cost</th></tr></thead><tbody>${stageRows(candidate.technicalStages)}</tbody></table>
  <h2>Classical baseline</h2>
  <p>${escapeHtml(candidate.classicalBaseline?.description ?? "No classical baseline recorded.")} ${candidate.classicalBaseline?.sourceUrl ? externalLink(candidate.classicalBaseline.sourceUrl, "source") : ""}</p>
  <h2>Atomic assumptions</h2>
  <table><thead><tr><th>ID</th><th>Question</th><th>Confirmation</th></tr></thead><tbody>${assumptionRows(candidate.materialAssumptions)}</tbody></table>
  <table><thead><tr><th>ID</th><th>Value</th><th>Note</th></tr></thead><tbody>${atomicRows([...(candidate.atomicInputs ?? []), ...(recalculation.marketEvidence ?? [])])}</tbody></table>
  <h2>Score anchors</h2>
  <table><thead><tr><th>Dimension</th><th>Recommended</th><th>Evidence outputs</th><th>Override</th></tr></thead><tbody>${scoreAnchorRows(quantitative.scoreAnchors)}</tbody></table>
  <h2>Sensitivity</h2>
  <table><thead><tr><th>Label</th><th>ID</th><th>Swing</th></tr></thead><tbody>${sensitivityRows(quantitative.sensitivity)}</tbody></table>
  <h2>Stale valuation warnings</h2>
  <ul>${listItems(warnings, "No stale valuation warnings.")}</ul>`;
}

export function renderAssessmentReport({ run, input, envelope, computed }) {
  const assessment = envelope.assessment;
  const valuationAudit = renderValuationAudit({ input, assessment });
  return `<!doctype html>
<html lang="${escapeHtml(envelope.language)}">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(input.problemId)} Assessment Report</title>
  <style>
    body { margin: 0; background: #f3f0e8; color: #17211d; font: 14px/1.55 system-ui, sans-serif; }
    main { width: min(1040px, calc(100% - 48px)); margin: 0 auto; padding: 42px 0 72px; }
    h1 { margin: 0 0 8px; font-size: 32px; line-height: 1.1; }
    h2 { margin: 28px 0 10px; font-size: 18px; }
    table { width: 100%; border-collapse: collapse; background: #fbfaf6; }
    th, td { border: 1px solid #d9d7ce; padding: 8px 10px; text-align: left; vertical-align: top; }
    th { background: #e9e6dc; }
    code { overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .summary { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin: 18px 0; }
    .summary div { border: 1px solid #d9d7ce; background: #fbfaf6; padding: 12px; }
    .muted { color: #65716c; }
    @media print { main { width: auto; padding: 0; } }
  </style>
</head>
<body>
<main>
  <p class="muted">${escapeHtml(run.runId)} · policy ${escapeHtml(input.policyVersion)}</p>
  <h1>${escapeHtml(input.problemId)} Research Problem Assessment</h1>
  <p>${escapeHtml(input.problemTitle)}</p>
  <p>${escapeHtml(assessment.normalizedProblem)}</p>
  <section class="summary" aria-label="Assessment summary">
    <div><strong>Verdict</strong><br>${escapeHtml(assessment.verdict.label)}</div>
    <div><strong>Recommendation</strong><br>${escapeHtml(assessment.recommendation)}</div>
    <div><strong>Confidence</strong><br>${escapeHtml(assessment.confidence.level)}</div>
    <div><strong>Research Value</strong><br>${escapeHtml(scoreText(computed.scores.researchValue))}</div>
    <div><strong>Autoresearch Suitability</strong><br>${escapeHtml(scoreText(computed.scores.autoresearchSuitability))}</div>
    <div><strong>Combined</strong><br>${escapeHtml(scoreText(computed.scores.combined))}</div>
  </section>
  <h2>Input Digest</h2>
  <table><tbody>
    <tr><th scope="row">problem.json</th><td><code>${escapeHtml(input.problemJsonHash)}</code></td></tr>
    <tr><th scope="row">problem.md</th><td><code>${escapeHtml(input.problemMdHash)}</code></td></tr>
    <tr><th scope="row">skill</th><td><code>${escapeHtml(input.skillHash)}</code></td></tr>
    <tr><th scope="row">schema</th><td><code>${escapeHtml(input.schemaHash)}</code></td></tr>
  </tbody></table>
  <h2>Bottleneck and Reframe</h2>
  <p><strong>Largest bottleneck:</strong> ${escapeHtml(assessment.largestBottleneck)}</p>
  <p><strong>Recommended reframe:</strong> ${escapeHtml(assessment.recommendedReframe.text)}</p>
  <h2>Research Value Audit</h2>
  <table><thead><tr><th>Dimension</th><th>ID</th><th>Weight</th><th>Score</th><th>Evidence</th><th>Rationale</th><th>Refs</th></tr></thead><tbody>${dimensionRows(assessment.dimensions.researchValue)}</tbody></table>
  <h2>Autoresearch Fit Audit</h2>
  <table><thead><tr><th>Dimension</th><th>ID</th><th>Weight</th><th>Score</th><th>Evidence</th><th>Rationale</th><th>Refs</th></tr></thead><tbody>${dimensionRows(assessment.dimensions.autoresearchSuitability)}</tbody></table>
  <h2>Information Gaps</h2>
  <ul>${assessment.informationGaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join("") || "<li>None recorded.</li>"}</ul>
  <h2>Evidence Appendix</h2>
  <table><thead><tr><th>ID</th><th>Kind</th><th>Path</th><th>Locator</th><th>Summary</th></tr></thead><tbody>${assessment.evidence.map((item) => `<tr><th scope="row">${escapeHtml(item.id)}</th><td>${escapeHtml(item.kind)}</td><td><code>${escapeHtml(item.path)}</code></td><td>${escapeHtml(item.locator)}</td><td>${escapeHtml(item.summary)}</td></tr>`).join("")}</tbody></table>
  ${valuationAudit}
</main>
</body>
</html>`;
}

"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  assessmentScoreMetrics,
  assessmentStatusCopy,
  assessmentServiceFailure,
  assessmentStateFromProblemResponse,
  formatCommercialInvestmentProxy,
  formatIndustrySocialProxy,
  formatScientificAttention,
  formatScoreInterval,
  formatTechnicalSuccessEstimate,
  isLocalAssessmentUnavailable,
  latestAssessmentSummary,
  valuationStatusCopy,
} from "@/lib/assessments/view-model.mjs";
import styles from "./assessment-panel.module.css";

type ClarificationAlternative = {
  page: string;
  topic: string;
  title: string;
  matchKind: string;
};

type ScoreInterval = {
  min: number;
  estimate: number;
  max: number;
};

type AssessmentSummary = {
  verdict?: string;
  recommendation?: string;
  confidence?: string;
  scores?: {
    researchValue?: ScoreInterval;
    autoresearchSuitability?: ScoreInterval;
    combined?: ScoreInterval;
  };
  largestBottleneck?: string;
  reportHref?: string;
  quantitative?: {
    scientificAttention?: QuantitativeValue;
    technicalSuccess?: QuantitativeValue;
    socialValue?: QuantitativeValue;
    capturableValue?: QuantitativeValue;
    largestSensitivity?: { id?: string; label?: string; swing?: number };
    snapshotId?: string;
    freshness?: string;
  };
};

type QuantitativeValue = {
  state?: string;
  interval?: { low: number; base: number; high: number };
  unit?: string;
  visibility?: string;
  redacted?: boolean;
  currency?: string;
  priceBaseYear?: number;
  reason?: string;
  estimateKind?: string;
  evidenceConfidence?: string;
};

type AssessmentRun = {
  runId?: string;
  problemId?: string;
  status?: string;
  summary?: AssessmentSummary | null;
  error?: { message?: string } | null;
};

type AssessmentState = {
  kind: string;
  runId?: string;
  reason?: string;
  latest?: AssessmentSummary | null;
  runs?: AssessmentRun[];
  clarification?: {
    query?: string;
    reason?: string;
    alternatives?: ClarificationAlternative[];
  };
  queuePosition?: number;
  elapsedSeconds?: number;
};

type ProblemAssessmentResponse = {
  activeJob?: AssessmentState | null;
  stale?: boolean;
  latest?: AssessmentSummary | null;
  runs?: AssessmentRun[];
};

type AnchorCandidate = {
  id: string;
  title?: string;
  persistentId?: string;
  sourceUrl?: string;
  relevanceRationale?: string;
};

type MaterialAssumption = {
  id: string;
  question?: string;
  confirmationRequired?: boolean;
};

type ValuationCandidate = {
  contentHash: string;
  anchorCandidates?: AnchorCandidate[];
  materialAssumptions?: MaterialAssumption[];
};

type ValuationJob = {
  runId?: string;
  status?: string;
  snapshotId?: string | null;
  error?: { message?: string } | null;
  candidate?: ValuationCandidate | null;
};

type ValuationProblemResponse = {
  activeJob?: ValuationJob | null;
  readySnapshotId?: string | null;
  jobs?: ValuationJob[];
};

type Props = { problemId: string };
const EMPTY_ALTERNATIVES: ClarificationAlternative[] = [];
const DEFAULT_SELECTION = { runId: null, index: "0" };

export function AssessmentPanel({ problemId }: Props) {
  const [state, setState] = useState<AssessmentState>({ kind: "unavailable" });
  const [valuation, setValuation] = useState<ValuationProblemResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [selection, setSelection] = useState<{ runId: string | null; index: string }>(DEFAULT_SELECTION);
  const [scopeAreas, setScopeAreas] = useState<string[]>([]);
  const [scopeOverride, setScopeOverride] = useState("");
  const [anchorSelection, setAnchorSelection] = useState<{ candidateHash: string; ids: Set<string> } | null>(null);
  const [assumptionDecisions, setAssumptionDecisions] = useState<Record<string, "accept" | "reject">>({});

  const refresh = useCallback(async () => {
    try {
      const [response, valuationResponse] = await Promise.all([
        fetch(`/__local/assessments/problems/${encodeURIComponent(problemId)}`, { cache: "no-store" }),
        fetch(`/__local/assessments/problems/${encodeURIComponent(problemId)}/valuation`, { cache: "no-store" }),
      ]);
      if (valuationResponse.ok) {
        setValuation(await valuationResponse.json() as ValuationProblemResponse);
      } else if (valuationResponse.status === 404) {
        setValuation(null);
      }
      if (!response.ok) {
        setState(isLocalAssessmentUnavailable(response)
          ? { kind: "unavailable" }
          : await assessmentServiceFailure(response));
        return;
      }
      setState(assessmentStateFromProblemResponse(await response.json() as ProblemAssessmentResponse) as AssessmentState);
    } catch (error) {
      setState(isLocalAssessmentUnavailable(error) ? { kind: "unavailable" } : {
        kind: "failed",
        reason: error instanceof Error ? error.message : String(error),
      });
    }
  }, [problemId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  useEffect(() => {
    const valuationStatus = valuation?.activeJob?.status;
    const shouldPollValuation = valuationStatus && ["queued", "researching", "confirming"].includes(valuationStatus);
    if (!["queued", "running"].includes(state.kind) && !shouldPollValuation) return undefined;
    const timer = window.setInterval(() => {
      void refresh();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [refresh, state.kind, valuation?.activeJob?.status]);

  async function start() {
    setBusy(true);
    try {
      const response = await fetch("/__local/assessments/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ problemId }),
      });
      if (response.ok) await refresh();
      else setState(await assessmentServiceFailure(response));
    } catch (error) {
      setState(isLocalAssessmentUnavailable(error) ? { kind: "unavailable" } : {
        kind: "failed",
        reason: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  }

  async function startValuation() {
    setBusy(true);
    try {
      const response = await fetch(`/__local/assessments/problems/${encodeURIComponent(problemId)}/valuation/jobs`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(scopeOverride ? { scopeOverride } : {}),
      });
      const payload = await response.json().catch(() => null);
      if (response.ok) {
        setScopeAreas([]);
        await refresh();
      } else if (payload?.status === "needs_input" && Array.isArray(payload.supportedAreas)) {
        setScopeAreas(payload.supportedAreas);
        setScopeOverride(payload.supportedAreas[0] ?? "");
      } else {
        setState({ kind: "failed", reason: payload?.message ?? payload?.code ?? payload?.error ?? "Valuation research failed." });
      }
    } catch (error) {
      setState(isLocalAssessmentUnavailable(error) ? { kind: "unavailable" } : {
        kind: "failed",
        reason: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  }

  const alternatives = state.clarification?.alternatives ?? EMPTY_ALTERNATIVES;
  const selectionRunId = state.runId ?? null;
  const selectedAlternativeIndex = selection.runId === selectionRunId ? selection.index : "0";
  const selectedAlternative = useMemo(
    () => alternatives[Number.parseInt(selectedAlternativeIndex, 10)] ?? alternatives[0],
    [alternatives, selectedAlternativeIndex],
  );

  const candidate = valuation?.activeJob?.candidate ?? null;
  const defaultAnchorIds = useMemo(
    () => new Set((candidate?.anchorCandidates ?? []).map((item) => item.id)),
    [candidate?.anchorCandidates],
  );
  const selectedAnchorIds = candidate && anchorSelection?.candidateHash === candidate.contentHash
    ? anchorSelection.ids
    : defaultAnchorIds;

  async function confirmValuation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const runId = valuation?.activeJob?.runId;
    if (!runId || !candidate) return;
    setBusy(true);
    try {
      const response = await fetch(`/__local/assessments/valuation/jobs/${encodeURIComponent(runId)}/confirmation`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          candidateHash: candidate.contentHash,
          acceptedAnchorIds: [...selectedAnchorIds],
          assumptionDecisions: (candidate.materialAssumptions ?? [])
            .filter((item) => item.confirmationRequired)
            .map((item) => ({ id: item.id, decision: assumptionDecisions[item.id] ?? "accept" })),
        }),
      });
      if (response.ok) await refresh();
      else setState(await assessmentServiceFailure(response));
    } catch (error) {
      setState(isLocalAssessmentUnavailable(error) ? { kind: "unavailable" } : {
        kind: "failed",
        reason: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  }

  function setAnchorChecked(id: string, checked: boolean) {
    setAnchorSelection((current) => {
      const candidateHash = candidate?.contentHash ?? "";
      const currentIds = current?.candidateHash === candidateHash ? current.ids : selectedAnchorIds;
      const next = new Set(currentIds);
      if (checked) next.add(id);
      else next.delete(id);
      return { candidateHash, ids: next };
    });
  }

  async function submitSelection() {
    if (!state.runId || !selectedAlternative) return;
    setBusy(true);
    try {
      const response = await fetch(
        `/__local/assessments/jobs/${encodeURIComponent(state.runId)}/selection`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ alternative: selectedAlternative }),
        },
      );
      if (response.ok) await refresh();
      else setState(await assessmentServiceFailure(response));
    } catch (error) {
      setState(isLocalAssessmentUnavailable(error) ? { kind: "unavailable" } : {
        kind: "failed",
        reason: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  }

  const copy = assessmentStatusCopy(state);
  const latest = state.latest ?? (latestAssessmentSummary(state) as AssessmentSummary | null);
  const latestValuationJob = [...(valuation?.jobs ?? [])]
    .reverse()
    .find((job) => job.status === "ready" || job.status === "research_failed");
  const readySnapshotId = valuation?.readySnapshotId ?? (latestValuationJob?.status === "ready" ? latestValuationJob.snapshotId : null);
  const valuationKind = (() => {
    const status = valuation?.activeJob?.status;
    if (status === "research_failed") return "research_failed";
    if (!status && latestValuationJob?.status === "research_failed") return "research_failed";
    if (status === "needs_confirmation") return "needs_confirmation";
    if (status && ["queued", "researching", "confirming"].includes(status)) return "researching";
    if (readySnapshotId && state.kind === "stale") return "stale";
    if (readySnapshotId) return "ready";
    return "no_evidence";
  })();
  const valuationCopy = valuationStatusCopy({ kind: valuationKind, error: valuation?.activeJob?.error ?? latestValuationJob?.error });
  const valuationAction = valuationKind === "ready" ? start : startValuation;
  const metricCards = latest?.quantitative ? [
    ["Scientific Demand Score", formatScientificAttention(latest.quantitative.scientificAttention)],
    ["Technical Success Estimate", formatTechnicalSuccessEstimate(latest.quantitative.technicalSuccess)],
    ["Industry / social proxy", formatIndustrySocialProxy(latest.quantitative.socialValue)],
    ["Commercial investment proxy", formatCommercialInvestmentProxy(latest.quantitative.capturableValue)],
    ["Largest sensitivity", latest.quantitative.largestSensitivity?.label
      ? `${latest.quantitative.largestSensitivity.label} (${latest.quantitative.largestSensitivity.swing ?? "—"})`
      : "—"],
  ] : [];

  return (
    <section className={`assessment-panel assessment-${state.kind}`} aria-labelledby="assessment-heading">
      {valuation && (
        <div className={styles.valuationStrip} aria-live="polite">
          <div>
            <p className={styles.eyebrow}>QUANTUM VALUATION</p>
            <h3>{valuationCopy.heading}</h3>
            <p>{valuationCopy.body}</p>
            {readySnapshotId && <small>Snapshot {readySnapshotId}</small>}
          </div>
          {valuationCopy.actionLabel && valuationKind !== "needs_confirmation" && valuationKind !== "ready" && (
            <button className={styles.primary} type="button" onClick={valuationAction} disabled={busy}>
              {busy ? "Working…" : valuationCopy.actionLabel}
            </button>
          )}
        </div>
      )}

      {scopeAreas.length > 0 && (
        <div className={styles.scopeChooser}>
          <label htmlFor={`quantum-area-${problemId}`}>Quantum area</label>
          <select id={`quantum-area-${problemId}`} value={scopeOverride} onChange={(event) => setScopeOverride(event.target.value)}>
            {scopeAreas.map((area) => <option key={area} value={area}>{area}</option>)}
          </select>
          <button className={styles.primary} type="button" onClick={startValuation} disabled={busy || !scopeOverride}>
            Research evidence
          </button>
        </div>
      )}

      {valuationKind === "needs_confirmation" && candidate && (
        <form className={styles.confirmation} onSubmit={confirmValuation}>
          <h3>Confirm valuation snapshot</h3>
          <fieldset>
            <legend>Selected Reference Papers</legend>
            {(candidate.anchorCandidates ?? []).map((anchor) => (
              <label key={anchor.id} className={styles.choice}>
                <input
                  type="checkbox"
                  checked={selectedAnchorIds.has(anchor.id)}
                  onChange={(event) => setAnchorChecked(anchor.id, event.target.checked)}
                />
                <span>
                  <strong>Selected reference paper: {anchor.title ?? anchor.id}</strong>
                  <small>{anchor.persistentId ?? anchor.sourceUrl ?? anchor.id}</small>
                </span>
              </label>
            ))}
          </fieldset>
          <fieldset>
            <legend>Material assumptions</legend>
            {(candidate.materialAssumptions ?? []).filter((item) => item.confirmationRequired).map((assumption) => (
              <label key={assumption.id} className={styles.choice}>
                <span>{assumption.question ?? assumption.id}</span>
                <select
                  value={assumptionDecisions[assumption.id] ?? "accept"}
                  onChange={(event) => setAssumptionDecisions((current) => ({ ...current, [assumption.id]: event.target.value as "accept" | "reject" }))}
                >
                  <option value="accept">Accept</option>
                  <option value="reject">Reject</option>
                </select>
              </label>
            ))}
          </fieldset>
          <button className={styles.primary} type="submit" disabled={busy || selectedAnchorIds.size === 0}>
            {busy ? "Freezing…" : "Confirm and freeze snapshot"}
          </button>
        </form>
      )}

      <div className="assessment-panel-head">
        <div>
          <p className="eyebrow">QUALIFICATION</p>
          <h2 id="assessment-heading">{copy.heading}</h2>
          <p>{copy.body}</p>
        </div>
        {copy.actionLabel && (
          <button className="state-action" type="button" onClick={start} disabled={busy}>
            {busy ? "Starting…" : copy.actionLabel}
          </button>
        )}
      </div>

      {state.kind === "needs-input" && alternatives.length > 0 && (
        <div className="assessment-clarification">
          {state.clarification?.reason && <p>{state.clarification.reason}</p>}
          <fieldset className="assessment-options">
            <legend>Trusted knowledge match</legend>
            {alternatives.map((alternative, index) => (
              <label className="assessment-option" key={`${index}:${alternative.page}:${alternative.matchKind}`}>
                <input
                  type="radio"
                  name={`assessment-alternative-${state.runId}`}
                  value={String(index)}
                  checked={selectedAlternativeIndex === String(index)}
                  onChange={() => setSelection({ runId: selectionRunId, index: String(index) })}
                />
                <span>
                  <strong>{alternative.title}</strong>
                  <small>{alternative.page} · {alternative.topic} · {alternative.matchKind}</small>
                </span>
              </label>
            ))}
          </fieldset>
          <button className="state-action" type="button" onClick={submitSelection} disabled={busy}>
            {busy ? "Submitting…" : "Continue assessment"}
          </button>
        </div>
      )}

      {latest?.verdict && (
        <dl className="assessment-summary-grid">
          <div><dt>Verdict</dt><dd>{latest.verdict}</dd></div>
          <div><dt>Recommendation</dt><dd>{latest.recommendation}</dd></div>
          <div><dt>Confidence</dt><dd>{latest.confidence}</dd></div>
          {assessmentScoreMetrics.map((metric) => (
            <div key={metric.key}>
              <dt title={`${metric.shortLabel}: ${metric.description}`}>{metric.label}</dt>
              <dd>{formatScoreInterval(latest.scores?.[metric.key as keyof NonNullable<AssessmentSummary["scores"]>])}</dd>
            </div>
          ))}
        </dl>
      )}
      {metricCards.length > 0 && (
        <dl className={styles.metricGrid}>
          {metricCards.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      {latest?.largestBottleneck && <p className="assessment-bottleneck">{latest.largestBottleneck}</p>}
      {latest?.reportHref && (
        <a className="open-affordance" href={latest.reportHref}>
          Open detailed report <span aria-hidden="true">→</span>
        </a>
      )}
    </section>
  );
}

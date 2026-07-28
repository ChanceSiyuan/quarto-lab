"use client";

import { useEffect, useMemo, useState } from "react";
import {
  assessmentStatusCopy,
  formatScoreInterval,
  isLocalAssessmentUnavailable,
  latestAssessmentSummary,
} from "@/lib/assessments/view-model.mjs";

type ClarificationAlternative = {
  page: string;
  topic: string;
  title: string;
  matchKind: string;
};

type AssessmentState = {
  kind: string;
  runId?: string;
  reason?: string;
  latest?: any;
  runs?: any[];
  clarification?: {
    query?: string;
    reason?: string;
    alternatives?: ClarificationAlternative[];
  };
  [key: string]: any;
};

type Props = { problemId: string };

function stateFromProblemResponse(body: any): AssessmentState {
  const runs = body?.runs ?? [];
  if (body?.activeJob) {
    const status = body.activeJob.status;
    return {
      kind: status === "queued" ? "queued" : status,
      ...body.activeJob,
      runs,
    };
  }
  if (body?.stale) return { kind: "stale", latest: body.latest, runs };
  if (body?.latest) return { kind: "completed", latest: body.latest, runs };
  const latest = latestAssessmentSummary(body);
  if (latest) return { kind: "completed", latest, runs };
  const latestRun = runs[0];
  if (latestRun?.status === "failed") {
    return {
      kind: "failed",
      reason: latestRun.error?.message ?? "Open diagnostics for details.",
      runs,
    };
  }
  if (latestRun?.status === "completed") {
    return {
      kind: "completed",
      latest: {
        reportHref: `/__local/assessments/reports/${encodeURIComponent(latestRun.problemId)}/${encodeURIComponent(latestRun.runId)}`,
      },
      runs,
    };
  }
  return { kind: "never", runs };
}

function serviceFailure(response: Response) {
  return { kind: "failed", reason: `Local service returned ${response.status}.` };
}

export function AssessmentPanel({ problemId }: Props) {
  const [state, setState] = useState<AssessmentState>({ kind: "unavailable" });
  const [busy, setBusy] = useState(false);
  const [selectedAlternativeIndex, setSelectedAlternativeIndex] = useState("0");

  async function refresh() {
    try {
      const response = await fetch(
        `/__local/assessments/problems/${encodeURIComponent(problemId)}`,
        { cache: "no-store" },
      );
      if (!response.ok) {
        setState(isLocalAssessmentUnavailable(response) ? { kind: "unavailable" } : serviceFailure(response));
        return;
      }
      setState(stateFromProblemResponse(await response.json()));
    } catch (error) {
      setState(isLocalAssessmentUnavailable(error) ? { kind: "unavailable" } : {
        kind: "failed",
        reason: error instanceof Error ? error.message : String(error),
      });
    }
  }

  useEffect(() => {
    void refresh();
  }, [problemId]);

  useEffect(() => {
    if (!["queued", "running"].includes(state.kind)) return undefined;
    const timer = window.setInterval(() => {
      void refresh();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [state.kind, problemId]);

  useEffect(() => {
    setSelectedAlternativeIndex("0");
  }, [state.runId]);

  async function start() {
    setBusy(true);
    try {
      const response = await fetch("/__local/assessments/jobs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ problemId }),
      });
      if (response.ok) await refresh();
      else setState(serviceFailure(response));
    } catch (error) {
      setState(isLocalAssessmentUnavailable(error) ? { kind: "unavailable" } : {
        kind: "failed",
        reason: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  }

  const alternatives = state.clarification?.alternatives ?? [];
  const selectedAlternative = useMemo(
    () => alternatives[Number.parseInt(selectedAlternativeIndex, 10)] ?? alternatives[0],
    [alternatives, selectedAlternativeIndex],
  );

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
      else setState(serviceFailure(response));
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
  const latest = state.latest ?? latestAssessmentSummary(state);

  return (
    <section className={`assessment-panel assessment-${state.kind}`} aria-labelledby="assessment-heading">
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
                  onChange={() => setSelectedAlternativeIndex(String(index))}
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
          <div><dt>V</dt><dd>{formatScoreInterval(latest.scores?.researchValue)}</dd></div>
          <div><dt>A</dt><dd>{formatScoreInterval(latest.scores?.autoresearchSuitability)}</dd></div>
          <div><dt>S</dt><dd>{formatScoreInterval(latest.scores?.combined)}</dd></div>
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

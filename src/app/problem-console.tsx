"use client";

import { useMemo } from "react";
import {
  buildProblemPresentation,
  formatProblemTimestamp,
  judgmentStatusCopy,
} from "@/lib/problems/presentation.mjs";

type Problem = {
  id: string;
  title: string;
  summary: string;
  status: string;
  gate: {
    type: string;
    readiness: string;
  };
  provenance: {
    sourceCount: number;
  };
  lastActivity: {
    summary: string;
    at: string;
  };
  updatedAt: string;
};

type Summary = {
  total: number;
  accepted: number;
  solved: number;
  published: number;
  rejected: number;
  archived: number;
};

type Diagnostic = {
  relativePath: string;
  field: string;
  message: string;
};

type Launch = {
  href: string;
  fallbackText: string;
};

type ProblemConsoleProps = {
  initialProblems: Problem[];
  summary: Summary;
  diagnostics: Diagnostic[];
  generatedAt: string;
  workspacePath: string;
  launch: Launch;
};

function ProblemStatus({ status }: { status: string }) {
  return (
    <span className={`status-badge status-${status}`}>
      {judgmentStatusCopy(status)}
    </span>
  );
}

export function ProblemConsole({
  initialProblems,
  diagnostics,
  generatedAt,
  workspacePath,
  launch,
}: ProblemConsoleProps) {
  const visiblePresentations = useMemo(
    () => initialProblems.map(buildProblemPresentation),
    [initialProblems],
  );

  return (
    <main className="console-shell">
      <header className="console-topbar">
        <div className="console-brand">
          <span className="brand-mark" aria-hidden="true">RL</span>
          <div>
            <strong>Research Loop</strong>
            <span>Problem Console</span>
          </div>
          <nav className="console-nav" aria-label="Primary">
            <a className="topbar-link" href="/knowledge/">Knowledge <span aria-hidden="true">→</span></a>
          </nav>
        </div>
        <div className="mode-indicator">
          <span>Local mode</span>
          <code title={workspacePath}>{workspacePath}</code>
        </div>
        <div className={`index-health ${diagnostics.length ? "has-errors" : ""}`}>
          <span className="health-dot" aria-hidden="true" />
          <div>
            <strong>{diagnostics.length ? `${diagnostics.length} index errors` : "Index healthy"}</strong>
            <span>Generated {formatProblemTimestamp(generatedAt)}</span>
          </div>
        </div>
      </header>

      <section className="console-content" aria-labelledby="problem-heading">
        <div className="console-heading">
          <div>
            <p className="eyebrow">LOCAL REPOSITORY INDEX</p>
            <h1 id="problem-heading">Problems</h1>
          </div>
          <p>
            Read-only lifecycle view · local repository index
          </p>
          <a className="primary-action" href={launch.href}>+ Add problem</a>
        </div>

        <div className="problem-results">
          <table className="problem-table">
            <caption>{initialProblems.length} indexed problems</caption>
            <thead>
              <tr>
                <th scope="col">Problem</th>
                <th scope="col">Status</th>
                <th scope="col">Executable gate</th>
                <th scope="col">Scientific Demand Score</th>
                <th scope="col">Expected Attributable Net Social Value (EANSV)</th>
                <th scope="col">Autoresearch Fit</th>
              </tr>
            </thead>
            <tbody>
              {initialProblems.length === 0 ? (
                <tr className="result-state-row">
                  <td colSpan={6}>
                    <section className="empty-state">
                      <span aria-hidden="true">Prob—</span>
                      <div>
                        <h2>No problems indexed yet</h2>
                        <p>Create a candidate in Codex, confirm its files, then rebuild the local index.</p>
                        <a className="state-action" href={launch.href}>+ Add first problem</a>
                      </div>
                    </section>
                  </td>
                </tr>
              ) : visiblePresentations.map((row) => (
                <tr className="problem-table-row" key={row.problem.id}>
                  <th scope="row">
                    <a className="problem-row-link" href={row.open.href}>
                      <span>{row.problem.id}</span>
                      <strong>{row.problem.title}</strong>
                      <small>{row.problem.summary}</small>
                    </a>
                  </th>
                  <td><ProblemStatus status={row.status.value} /></td>
                  <td>
                    <div className="cell-stack">
                      <strong>{row.gate.primary}</strong>
                      <small>{row.gate.secondary}</small>
                    </div>
                  </td>
                  <td>{row.scientificDemand.value}</td>
                  <td>{row.eansv.value}</td>
                  <td>{row.autoresearchFit.value}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="problem-list" aria-label="Problems">
            {initialProblems.length === 0 ? (
              <section className="empty-state">
                <span aria-hidden="true">Prob—</span>
                <div>
                  <h2>No problems indexed yet</h2>
                  <p>Create a candidate in Codex, confirm its files, then rebuild the local index.</p>
                  <a className="state-action" href={launch.href}>+ Add first problem</a>
                </div>
              </section>
            ) : visiblePresentations.map((row) => (
              <a
                className="problem-list-item"
                href={row.open.href}
                aria-label={`Open ${row.problem.id}: ${row.problem.title}`}
                key={row.problem.id}
              >
                <div className="mobile-problem-field">
                  <span className="mobile-field-label">{row.problem.label}</span>
                  <span className="problem-id">{row.problem.id}</span>
                  <h2>{row.problem.title}</h2>
                  <p>{row.problem.summary}</p>
                </div>
                <dl>
                  <div><dt>{row.status.label}</dt><dd><ProblemStatus status={row.status.value} /></dd></div>
                  <div><dt>{row.gate.label}</dt><dd>{row.gate.primary} · {row.gate.secondary}</dd></div>
                  <div><dt>{row.scientificDemand.label}</dt><dd>{row.scientificDemand.value}</dd></div>
                  <div><dt>{row.eansv.label}</dt><dd>{row.eansv.value}</dd></div>
                  <div><dt>{row.autoresearchFit.label}</dt><dd>{row.autoresearchFit.value}</dd></div>
                </dl>
              </a>
            ))}
          </div>
        </div>

        <details className="codex-fallback">
          <summary>Cannot open Codex?</summary>
          <p>Copy this complete prompt into a new Codex task.</p>
          <textarea readOnly value={launch.fallbackText} aria-label="Add problem fallback prompt" />
        </details>
      </section>
    </main>
  );
}

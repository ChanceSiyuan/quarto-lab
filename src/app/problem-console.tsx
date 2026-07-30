"use client";

import { useMemo } from "react";
import {
  buildProblemPresentation,
  formatProblemTimestamp,
} from "@/lib/problems/presentation.mjs";

const statusLabels: Record<string, string> = {
  draft: "Draft",
  qualifying: "Qualifying",
  accepted: "Accepted",
  solving: "Solving",
  solved: "Solved",
  publishing: "Publishing",
  published: "Published",
  rejected: "Rejected",
  archived: "Archived",
};

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
  // Kept for the locked page.tsx contract; filtering was removed, so the
  // listing always shows every indexed problem regardless of this flag.
  initialShowArchived?: boolean;
};

function ProblemStatus({ status }: { status: string }) {
  return (
    <span className={`status-badge status-${status}`}>
      {statusLabels[status] ?? status}
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
                <th scope="col">Provenance</th>
                <th scope="col">Recent activity</th>
                <th scope="col">Updated</th>
                <th scope="col">Open</th>
              </tr>
            </thead>
            <tbody>
              {initialProblems.length === 0 ? (
                <tr className="result-state-row">
                  <td colSpan={7}>
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
                  <td>{row.provenance.value}</td>
                  <td>
                    <div className="cell-stack">
                      <strong>{row.activity.primary}</strong>
                      <small>{row.activity.secondary}</small>
                    </div>
                  </td>
                  <td>{row.updated.value}</td>
                  <td>
                    <a className="open-affordance" href={row.open.href}>
                      Open <span aria-hidden="true">→</span>
                    </a>
                  </td>
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
                  <div><dt>{row.provenance.label}</dt><dd>{row.provenance.value}</dd></div>
                  <div><dt>{row.activity.label}</dt><dd>{row.activity.primary} · {row.activity.secondary}</dd></div>
                  <div><dt>{row.updated.label}</dt><dd>{row.updated.value}</dd></div>
                  <div>
                    <dt>{row.open.label}</dt>
                    <dd><span className="open-affordance">{row.open.value} <span aria-hidden="true">→</span></span></dd>
                  </div>
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

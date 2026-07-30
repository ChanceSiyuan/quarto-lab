"use client";

import { useMemo, useState } from "react";
import {
  buildProblemPresentation,
  buildTierMetrics,
  formatProblemTimestamp,
} from "@/lib/problems/presentation.mjs";
import {
  ACTIVE_PROBLEM_STATUSES,
  clearProblemFilters,
  createDefaultProblemFilters,
  filterProblems,
} from "@/lib/problems/view-state.mjs";

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
  summary,
  diagnostics,
  generatedAt,
  workspacePath,
  launch,
  initialShowArchived = false,
}: ProblemConsoleProps) {
  const defaults = createDefaultProblemFilters();
  const [query, setQuery] = useState(defaults.query);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>(defaults.selectedStatuses);
  const [showRejected, setShowRejected] = useState(defaults.showRejected);
  const [showArchived, setShowArchived] = useState(defaults.showArchived || initialShowArchived);

  const visibleProblems = useMemo(() => filterProblems(initialProblems, {
    query,
    selectedStatuses,
    showRejected,
    showArchived,
  }), [initialProblems, query, selectedStatuses, showArchived, showRejected]);

  const visiblePresentations = useMemo(
    () => visibleProblems.map(buildProblemPresentation),
    [visibleProblems],
  );

  function toggleStatus(status: string) {
    setSelectedStatuses((current) =>
      current.includes(status)
        ? current.filter((item) => item !== status)
        : [...current, status],
    );
  }

  function clearFilters() {
    const cleared = clearProblemFilters();
    setQuery(cleared.query);
    setSelectedStatuses(cleared.selectedStatuses);
    setShowRejected(cleared.showRejected);
    setShowArchived(cleared.showArchived);
  }

  const metrics = buildTierMetrics(summary);

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
        </div>

        <dl className="metric-strip" aria-label="Problem metrics">
          {metrics.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>

        <section className="console-toolbar" aria-label="Problem filters">
          <label className="search-field">
            <span>Search problems</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="ID, title, or summary"
            />
          </label>

          <fieldset className="status-filters">
            <legend>Lifecycle status</legend>
            <div className="filter-chips">
              {ACTIVE_PROBLEM_STATUSES.map((status) => (
                <label className="filter-chip" key={status}>
                  <input
                    type="checkbox"
                    checked={selectedStatuses.includes(status)}
                    onChange={() => toggleStatus(status)}
                  />
                  <span>{statusLabels[status]}</span>
                </label>
              ))}
              <label className="filter-chip filter-chip-muted">
                <input
                  type="checkbox"
                  checked={showRejected}
                  onChange={(event) => setShowRejected(event.target.checked)}
                />
                <span>{statusLabels.rejected}</span>
              </label>
              <label className="filter-chip filter-chip-muted">
                <input
                  type="checkbox"
                  checked={showArchived}
                  onChange={(event) => setShowArchived(event.target.checked)}
                />
                <span>{statusLabels.archived}</span>
              </label>
            </div>
          </fieldset>

          <a className="primary-action" href={launch.href}>+ Add problem</a>
        </section>

        <section
          className={`diagnostics ${diagnostics.length ? "has-errors" : ""}`}
          aria-labelledby="diagnostics-heading"
        >
          <div>
            <h2 id="diagnostics-heading">Index diagnostics</h2>
            <p>
              {diagnostics.length
                ? "Invalid manifests are excluded until these errors are fixed."
                : "No manifest errors detected in the generated index."}
            </p>
          </div>
          {diagnostics.length > 0 && (
            <ul>
              {diagnostics.map((item, index) => (
                <li key={`${item.relativePath}-${item.field}-${index}`}>
                  <code>{item.relativePath}</code>
                  <strong>{item.field}</strong>
                  <span>{item.message}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="problem-results">
          <table className="problem-table">
            <caption>{visibleProblems.length} visible problems</caption>
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
              ) : visibleProblems.length === 0 ? (
                <tr className="result-state-row">
                  <td colSpan={7}>
                    <section className="no-results">
                      <h2>No matching problems</h2>
                      <p>Adjust the search text or lifecycle filters.</p>
                      <button className="state-action" type="button" onClick={clearFilters}>Clear all filters</button>
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
                  <td className="cell-stack">
                    <strong>{row.gate.primary}</strong>
                    <small>{row.gate.secondary}</small>
                  </td>
                  <td>{row.provenance.value}</td>
                  <td className="cell-stack">
                    <strong>{row.activity.primary}</strong>
                    <small>{row.activity.secondary}</small>
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
            ) : visibleProblems.length === 0 ? (
              <section className="no-results">
                <h2>No matching problems</h2>
                <p>Adjust the search text or lifecycle filters.</p>
                <button className="state-action" type="button" onClick={clearFilters}>Clear all filters</button>
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

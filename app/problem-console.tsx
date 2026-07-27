"use client";

import { useMemo, useState } from "react";

const statusLabels: Record<string, string> = {
  draft: "草稿",
  qualifying: "资格验证中",
  accepted: "已接受",
  solving: "求解中",
  solved: "已解决",
  publishing: "投稿中",
  published: "已发表",
  rejected: "已拒绝",
  archived: "已归档",
};

const activeStatuses = [
  "draft",
  "qualifying",
  "accepted",
  "solving",
  "solved",
  "publishing",
  "published",
];

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
  target: number;
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

function formatTimestamp(value: string) {
  return value.replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}

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
}: ProblemConsoleProps) {
  const [query, setQuery] = useState("");
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>(activeStatuses);
  const [showRejected, setShowRejected] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  const visibleProblems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return initialProblems.filter((problem) => {
      if (problem.status === "rejected") {
        if (!showRejected) return false;
      } else if (problem.status === "archived") {
        if (!showArchived) return false;
      } else if (!selectedStatuses.includes(problem.status)) {
        return false;
      }

      return (
        !normalizedQuery ||
        [problem.id, problem.title, problem.summary]
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery)
      );
    });
  }, [initialProblems, query, selectedStatuses, showArchived, showRejected]);

  function toggleStatus(status: string) {
    setSelectedStatuses((current) =>
      current.includes(status)
        ? current.filter((item) => item !== status)
        : [...current, status],
    );
  }

  const metrics: Array<[string, number | string]> = [
    ["Total", summary.total],
    ["Accepted", `${summary.accepted} / ${summary.target}`],
    ["Solved", `${summary.solved} / ${summary.target}`],
    ["Published", `${summary.published} / ${summary.target}`],
    ["Rejected", summary.rejected],
  ];

  return (
    <main className="console-shell">
      <header className="console-topbar">
        <div className="console-brand">
          <span className="brand-mark" aria-hidden="true">RL</span>
          <div>
            <strong>Research Loop</strong>
            <span>问题控制台</span>
          </div>
        </div>
        <div className="mode-indicator">
          <span>Local mode</span>
          <code title={workspacePath}>{workspacePath}</code>
        </div>
        <div className={`index-health ${diagnostics.length ? "has-errors" : ""}`}>
          <span className="health-dot" aria-hidden="true" />
          <div>
            <strong>{diagnostics.length ? `${diagnostics.length} index errors` : "Index healthy"}</strong>
            <span>Generated {formatTimestamp(generatedAt)}</span>
          </div>
        </div>
      </header>

      <section className="console-content" aria-labelledby="problem-heading">
        <div className="console-heading">
          <div>
            <p className="eyebrow">LOCAL REPOSITORY INDEX</p>
            <h1 id="problem-heading">问题</h1>
          </div>
          <p>
            Read-only lifecycle view · publication target {summary.target}
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
              {activeStatuses.map((status) => (
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

          <a className="primary-action" href={launch.href}>+ 增加问题</a>
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
                      <span aria-hidden="true">QMB—</span>
                      <div>
                        <h2>No problems indexed yet</h2>
                        <p>Create a candidate in Codex, confirm its files, then rebuild the local index.</p>
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
                    </section>
                  </td>
                </tr>
              ) : visibleProblems.map((problem) => (
                <tr key={problem.id}>
                  <th scope="row">
                    <a href={`/problems/${problem.id}`}>
                      <span>{problem.id}</span>
                      <strong>{problem.title}</strong>
                      <small>{problem.summary}</small>
                    </a>
                  </th>
                  <td><ProblemStatus status={problem.status} /></td>
                  <td className="cell-stack">
                    <strong>{problem.gate.type}</strong>
                    <small>{problem.gate.readiness}</small>
                  </td>
                  <td>{problem.provenance.sourceCount} sources</td>
                  <td className="cell-stack">
                    <strong>{problem.lastActivity.summary}</strong>
                    <small>{formatTimestamp(problem.lastActivity.at)}</small>
                  </td>
                  <td>{formatTimestamp(problem.updatedAt)}</td>
                  <td>
                    <a className="open-affordance" href={`/problems/${problem.id}`}>
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
                <span aria-hidden="true">QMB—</span>
                <div>
                  <h2>No problems indexed yet</h2>
                  <p>Create a candidate in Codex, confirm its files, then rebuild the local index.</p>
                </div>
              </section>
            ) : visibleProblems.length === 0 ? (
              <section className="no-results">
                <h2>No matching problems</h2>
                <p>Adjust the search text or lifecycle filters.</p>
              </section>
            ) : visibleProblems.map((problem) => (
              <article className="problem-list-item" key={problem.id}>
                <div className="mobile-problem-field">
                  <span className="mobile-field-label">Problem</span>
                  <span className="problem-id">{problem.id}</span>
                  <h2>{problem.title}</h2>
                  <p>{problem.summary}</p>
                </div>
                <dl>
                  <div><dt>Status</dt><dd><ProblemStatus status={problem.status} /></dd></div>
                  <div><dt>Executable gate</dt><dd>{problem.gate.type} · {problem.gate.readiness}</dd></div>
                  <div><dt>Provenance</dt><dd>{problem.provenance.sourceCount} sources</dd></div>
                  <div><dt>Recent activity</dt><dd>{problem.lastActivity.summary} · {formatTimestamp(problem.lastActivity.at)}</dd></div>
                  <div><dt>Updated</dt><dd>{formatTimestamp(problem.updatedAt)}</dd></div>
                  <div>
                    <dt>Open</dt>
                    <dd><a className="open-affordance" href={`/problems/${problem.id}`}>Open problem <span aria-hidden="true">→</span></a></dd>
                  </div>
                </dl>
              </article>
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

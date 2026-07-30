"use client";

import { useEffect, useMemo, useState } from "react";

import { sortPortfolioRows } from "@/lib/qec-portfolio/view-model.mjs";
import styles from "./portfolio-panel.module.css";

type ScoreInterval = { min?: number; estimate?: number; max?: number };
type QuantitativeValue = {
  state?: string;
  label?: string;
  reason?: string;
  interval?: { low?: number; base?: number; high?: number };
  unit?: string;
  currency?: string;
  priceBaseYear?: number;
  estimateKind?: string;
  evidenceConfidence?: string;
};
type PortfolioRow = {
  problemId: string;
  title: string | null;
  status: string | null;
  verdict: string | null;
  confidence: string | null;
  researchValue: ScoreInterval | null;
  autoresearchFit: ScoreInterval | null;
  combinedPriority: ScoreInterval | null;
  scientificAttention: QuantitativeValue | null;
  technicalSuccess: QuantitativeValue | null;
  socialValue: QuantitativeValue | null;
  capturableValue: QuantitativeValue | null;
  largestBottleneck: string | null;
  problemHref: string;
  reportHref: string | null;
};
type PortfolioResponse = {
  schemaVersion: number;
  generatedAt: string;
  evidenceLabel: string;
  count: number;
  rows: PortfolioRow[];
};

const EVIDENCE_LABEL = "External-evidence-backed advisory comparison";

const SORT_OPTIONS = [
  ["combined", "Combined Priority (S)"],
  ["research-value", "Research Value (V)"],
  ["autoresearch-fit", "Autoresearch Fit (A)"],
  ["verdict", "Verdict"],
  ["scientific-attention", "Scientific Demand Score"],
] as const;

type SortKey = typeof SORT_OPTIONS[number][0];

function numberText(value: number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

function moneyText(value: number | undefined, currency = "USD") {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const symbol = currency === "USD" ? "$" : `${currency} `;
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${symbol}${numberText(value / 1_000_000_000)}B`;
  if (abs >= 1_000_000) return `${symbol}${numberText(value / 1_000_000)}M`;
  if (abs >= 1_000) return `${symbol}${numberText(value / 1_000)}K`;
  return `${symbol}${numberText(value)}`;
}

function scoreText(score: ScoreInterval | null) {
  if (!score || typeof score.estimate !== "number") return "Not assessed";
  return numberText(score.estimate);
}

function quantitativeText(value: QuantitativeValue | null) {
  if (!value) return "Not reported";
  if (value.state === "unknown") return `Evidence gap — ${value.reason ?? "No supporting evidence was recorded."}`;
  if (value.interval) {
    if (value.currency || /^[A-Z]{3}_\d{4}$/.test(value.unit ?? "")) {
      const match = /^([A-Z]{3})_(\d{4})$/.exec(value.unit ?? "");
      const currency = value.currency ?? match?.[1] ?? "USD";
      const year = value.priceBaseYear ?? (match?.[2] ? Number(match[2]) : null);
      return `${moneyText(value.interval.base, currency)}${year ? ` · ${currency} ${year}` : ""}`;
    }
    if (value.unit === "score-100") {
      const confidence = value.evidenceConfidence
        ? `${value.evidenceConfidence[0].toUpperCase()}${value.evidenceConfidence.slice(1).toLowerCase()} evidence confidence`
        : "Evidence confidence unavailable";
      return `${numberText(value.interval.base)} / 100 · ${confidence}`;
    }
    if (value.unit === "count") {
      const count = numberText(value.interval.base);
      if (count === "0") return "No matched citations";
      return count === "1" ? "1 matched citation" : `${count} matched citations`;
    }
    if (value.unit === "fraction") return `${numberText((value.interval.base ?? 0) * 100)}%`;
    if (value.unit === "percent") return `${numberText(value.interval.base)}%`;
    const suffix = value.unit ? ` ${value.unit}` : "";
    return `${numberText(value.interval.base)}${suffix}`;
  }
  return value.reason ? `${value.label ?? "Evidence gap"} — ${value.reason}` : value.label ?? "Not reported";
}

function technicalSuccessText(value: QuantitativeValue | null) {
  const point = quantitativeText(value);
  if (value?.state !== "known") return point;
  return value.estimateKind === "model" ? `${point} · Model estimate` : `${point} · Measured`;
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className={styles.metric}><dt>{label}</dt><dd>{children}</dd></div>;
}

function Links({ row }: { row: PortfolioRow }) {
  return (
    <span className={styles.links}>
      <a href={row.problemHref}>Open problem</a>
      {row.reportHref ? <a href={row.reportHref}>Open detailed report</a> : <span>Detailed report unavailable</span>}
    </span>
  );
}

function rowAriaSort(sort: SortKey, key: SortKey) {
  return sort === key ? key === "verdict" ? "ascending" : "descending" : "none";
}

export function PortfolioPanel() {
  const [response, setResponse] = useState<PortfolioResponse | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [sort, setSort] = useState<SortKey>("combined");

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const result = await fetch("/__local/assessments/portfolio", { cache: "no-store" });
        if (!result.ok) throw new Error(`Local portfolio response: ${result.status}`);
        const payload = await result.json() as PortfolioResponse;
        if (active) setResponse(payload);
      } catch {
        if (active) setUnavailable(true);
      }
    })();
    return () => { active = false; };
  }, []);

  const rows = useMemo(() => response ? sortPortfolioRows(response.rows, sort) : [], [response, sort]);

  if (unavailable) return <section className={styles.notice}>This comparison is available when the local assessment service is running.</section>;
  if (!response) return <section className={styles.notice}>Loading the local QEC portfolio…</section>;

  return (
    <section className={styles.panel} aria-label="QEC portfolio comparison">
      <div className={styles.toolbar}>
        <div>
          <p className={styles.eyebrow}>{response.evidenceLabel || EVIDENCE_LABEL}</p>
          <p className={styles.count}>{response.count} QEC problems · updated {new Date(response.generatedAt).toLocaleString()}</p>
        </div>
        <label className={styles.sortLabel}>
          Sort comparison
          <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
            {SORT_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      </div>

      <div className={styles.tableWrap}>
        <table>
          <thead>
            <tr>
              <th scope="col">Problem</th>
              <th scope="col" aria-sort={rowAriaSort(sort, "verdict")}>Verdict and confidence</th>
              <th scope="col" aria-sort={rowAriaSort(sort, "research-value")}>Research Value (V)</th>
              <th scope="col" aria-sort={rowAriaSort(sort, "autoresearch-fit")}>Autoresearch Fit (A)</th>
              <th scope="col" aria-sort={rowAriaSort(sort, "combined")}>Combined Priority (S)</th>
              <th scope="col" aria-sort={rowAriaSort(sort, "scientific-attention")}>Scientific Demand Score</th>
              <th scope="col">Technical Success Estimate</th>
              <th scope="col">Industry/Social Enabling-Value Proxy</th>
              <th scope="col">Commercial Investment Proxy</th>
              <th scope="col">Largest bottleneck</th>
              <th scope="col">Links</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.problemId}>
                <th scope="row"><a href={row.problemHref}>{row.problemId}</a><span>{row.title ?? "Untitled QEC problem"}</span></th>
                <td>{row.verdict ?? "Not assessed"}<small>{row.confidence ?? "Confidence unavailable"}</small></td>
                <td>{scoreText(row.researchValue)}</td>
                <td>{scoreText(row.autoresearchFit)}</td>
                <td>{scoreText(row.combinedPriority)}</td>
                <td>{quantitativeText(row.scientificAttention)}</td>
                <td>{technicalSuccessText(row.technicalSuccess)}</td>
                <td>{quantitativeText(row.socialValue)}</td>
                <td>{quantitativeText(row.capturableValue)}</td>
                <td>{row.largestBottleneck ?? "No completed assessment."}</td>
                <td><Links row={row} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.cards}>
        {rows.map((row) => (
          <article key={row.problemId} className={styles.card}>
            <header><a href={row.problemHref}>{row.problemId}</a><h2>{row.title ?? "Untitled QEC problem"}</h2></header>
            <dl>
              <Metric label="Verdict and confidence">{row.verdict ?? "Not assessed"} · {row.confidence ?? "Confidence unavailable"}</Metric>
              <Metric label="Research Value (V)">{scoreText(row.researchValue)}</Metric>
              <Metric label="Autoresearch Fit (A)">{scoreText(row.autoresearchFit)}</Metric>
              <Metric label="Combined Priority (S)">{scoreText(row.combinedPriority)}</Metric>
              <Metric label="Scientific Demand Score">{quantitativeText(row.scientificAttention)}</Metric>
              <Metric label="Technical Success Estimate">{technicalSuccessText(row.technicalSuccess)}</Metric>
              <Metric label="Industry/Social Enabling-Value Proxy">{quantitativeText(row.socialValue)}</Metric>
              <Metric label="Commercial Investment Proxy">{quantitativeText(row.capturableValue)}</Metric>
              <Metric label="Largest bottleneck">{row.largestBottleneck ?? "No completed assessment."}</Metric>
            </dl>
            <Links row={row} />
          </article>
        ))}
      </div>
    </section>
  );
}

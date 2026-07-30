import styles from "./static-assessment-panel.module.css";

const METRIC_CARDS = [
  {
    label: "Scientific Demand Score",
    value: "33.4 / 100",
    note: "Citation-derived attention proxy, not a raw citation count.",
    formula: [
      "2 confirmed-anchor papers; evidence weight each",
      "  = max(0.25 anchor floor, relevance) x match_confidence x independence_discount",
      "  = 0.25 x 1 x 1 = 0.25",
      "",
      "influence (w 0.45) = weighted_median( 0.8423 [QDistRnd, w .25],",
      "                                      0.0041 [FastAlg, w .25] ) = 0.0041",
      "momentum (w 0.30) = logistic( ln((9 + 1) / (2 + 1)) )",
      "                  = logistic(1.204) = 0.7692   (QDistRnd: 2 cites 2024 -> 9 in 2025)",
      "breadth  (w 0.15) = 0.6 x log1p(2 papers) / log1p(20)",
      "                  + 0.4 x log1p(5 institutions) / log1p(20)",
      "                  = 0.6 x 0.3608 + 0.4 x 0.5885 = 0.4519",
      "network  (w 0.10) = reserved -> active weights renormalize to 0.90",
      "",
      "score = round_1dp( 100 x (0.45 x 0.0041 + 0.30 x 0.7692 + 0.15 x 0.4519) / 0.90 )",
      "      = round_1dp( 100 x 0.3004 / 0.90 ) = 33.4",
    ],
    reasons: [
      "Only QDistRnd (JOSS 2022, 16 citations) has complete-year counts (2 in 2024, 9 in 2025); the 2026 anchor paper has no year data, so momentum rests on a single paper.",
      "Influence sits near the 0.4th citation percentile because the newer anchor paper has zero citations so far, and equal 0.25 anchor weights put the weighted median on it.",
      "Evidence confidence is low (fewer than 3 comparable papers): 33.4 is a sparse-evidence attention proxy, not proof of novelty.",
    ],
  },
  {
    label: "Industry / social proxy",
    value: "$57.0B USD 2035",
    note: "Broad quantum-computing market proxy, not problem-specific welfare.",
    formula: [
      "source = McKinsey Quantum Technology Monitor 2026",
      "reported 2035 internal quantum-computing market = USD 43B - 71B (2035 dollars)",
      "encoded as low / base / high = 43 / 57 / 71 USD B",
      "",
      "displayed value = base of the interval = $57.0B USD 2035",
    ],
    reasons: [
      "Proxy mckinsey-qc-internal-market-2035 fills the economic column because no problem-specific market model exists for this candidate.",
      "It states the enabling quantum-computing market reaches tens of billions by 2035; it says nothing about this problem's capturable revenue, pricing power, adoption, or welfare.",
    ],
  },
  {
    label: "Autoresearch Fit",
    value: "38.5 / 100",
    note: "Suitability for a bounded autonomous search loop.",
    formula: [
      "A = 100 x weighted_average(0-5 dimension estimates) / 5",
      "",
      "modifiable search object       20 x 1.5 =  30.0",
      "executable objective           20 x 1.5 =  30.0",
      "correctness and anti-gaming    15 x 2.0 =  30.0",
      "incremental feedback           15 x 1.5 =  22.5",
      "fresh evaluation               10 x 2.0 =  20.0",
      "reproducibility, auditability  10 x 3.0 =  30.0",
      "attempt runtime                10 x 3.0 =  30.0",
      "                              weighted sum = 192.5 / 100 = 1.925",
      "",
      "A = 100 x 1.925 / 5 = 38.5",
      "S = 2 x V x A / (V + A) = 2 x 71.0 x 38.5 / 109.5 = 49.9",
    ],
    reasons: [
      "Weakest dimensions are modifiable search object, executable objective, and incremental feedback (all 1.5 / 5): the sealed benchmark, baseline, and primary success metric are not frozen yet.",
      "A = 38.5 falls in the weak band (< 40), so the harmonic mean holds combined priority at S = 49.9 despite strong research value V = 71.0.",
      "That arithmetic is exactly why the demo verdict is REFRAME rather than DO_NOW.",
    ],
  },
];

export function StaticAssessmentPanel() {
  return (
    <section className={`assessment-panel ${styles.panel}`} aria-labelledby="assessment-heading">
      <div className="assessment-panel-head">
        <div>
          <p className="eyebrow">QUALIFICATION</p>
          <h2 id="assessment-heading">Assessment methodology demo</h2>
          <p>
            Three headline metrics for this demo problem. Expand any card to see
            the formula worked through with the actual input data.
          </p>
        </div>
        <span className={styles.pill}>Static example</span>
      </div>

      <div className={styles.metrics}>
        {METRIC_CARDS.map((card) => (
          <details className={styles.metric} key={card.label}>
            <summary>
              <span className={styles.metricLabel}>{card.label}</span>
              <span className={styles.metricValue}>{card.value}</span>
              <span className={styles.metricNote}>{card.note}</span>
              <span className={styles.metricToggle}>Formula &amp; reasoning</span>
            </summary>
            <div className={styles.metricDetail}>
              <pre className={styles.formula}>{card.formula.join("\n")}</pre>
              <ul>
                {card.reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

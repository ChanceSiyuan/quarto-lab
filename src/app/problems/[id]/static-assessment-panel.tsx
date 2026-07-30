import styles from "./static-assessment-panel.module.css";

const SCORE_CARDS = [
  { label: "Verdict", value: "REFRAME" },
  { label: "Recommendation", value: "reframe" },
  { label: "Confidence", value: "low" },
  { label: "Research Value (V)", value: "71.0" },
  { label: "Autoresearch Fit (A)", value: "38.5" },
  { label: "Combined Priority (S)", value: "49.9" },
];

const QUANTITATIVE_CARDS = [
  {
    label: "Scientific Demand Score",
    value: "33.4 / 100",
    note: "Citation-derived attention proxy using influence, momentum, and breadth.",
  },
  {
    label: "Technical Success Estimate",
    value: "49.0%",
    note: "Model estimate from plausibility, executable objective, anti-gaming, feedback, and runtime.",
  },
  {
    label: "Industry / social proxy",
    value: "$57.0B USD 2035",
    note: "Broad quantum-computing market proxy, not problem-specific welfare.",
  },
  {
    label: "Commercial investment proxy",
    value: "$10.0B USD 2026",
    note: "Public investment-floor proxy, not single-problem capturable revenue.",
  },
];

const METHOD_STEPS = [
  "V scores research importance, novelty gap, plausibility, learning value, generality, and cost-adjusted value.",
  "A scores whether a bounded autonomous loop has a modifiable object, executable objective, anti-gaming checks, feedback, fresh evaluation, auditability, and tractable runtime.",
  "S is the harmonic mean of V and A, so a weak automation fit suppresses priority even when research value is high.",
  "Scientific Demand uses a weighted bibliometric model; raw citation counts are audit evidence, not direct score additions.",
];

export function StaticAssessmentPanel() {
  return (
    <section className={`assessment-panel ${styles.panel}`} aria-labelledby="assessment-heading">
      <div className="assessment-panel-head">
        <div>
          <p className="eyebrow">QUALIFICATION</p>
          <h2 id="assessment-heading">Assessment methodology demo</h2>
          <p>
            Static example assessment for the demo page. It shows the current
            point-valued scoring model without requiring the local assessment
            service or publishing local run artifacts.
          </p>
        </div>
        <span className={styles.pill}>Static example</span>
      </div>

      <dl className="assessment-summary-grid">
        {SCORE_CARDS.map((card) => (
          <div key={card.label}>
            <dt>{card.label}</dt>
            <dd>{card.value}</dd>
          </div>
        ))}
      </dl>

      <dl className={styles.metrics}>
        {QUANTITATIVE_CARDS.map((card) => (
          <div key={card.label}>
            <dt>{card.label}</dt>
            <dd>{card.value}</dd>
            <p>{card.note}</p>
          </div>
        ))}
      </dl>

      <div className={styles.method}>
        <h3>How this evaluation is read</h3>
        <ul>
          {METHOD_STEPS.map((step) => <li key={step}>{step}</li>)}
        </ul>
      </div>

      <p className="assessment-bottleneck">
        Largest bottleneck: the sealed benchmark, baseline, and primary success
        metric must be frozen before this code-distance search can be treated as
        a high-confidence autonomous research campaign.
      </p>
    </section>
  );
}

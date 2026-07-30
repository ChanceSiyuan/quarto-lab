import { getStaticEvaluation } from "@/lib/pages-showcase/evaluation-scenarios.mjs";
import styles from "./static-assessment-panel.module.css";

const METHODOLOGY_HREF =
  "https://github.com/nzy1997/research-loop/blob/main/.research-loop/docs/project/assessment-methodology.md";

type MetricCard = {
  label: string;
  value: string;
  formula: string[];
  reason: string;
};

const SCIENTIFIC_DEMAND_CARD: MetricCard = {
  label: "Scientific Demand Score",
  value: "33.4 / 100",
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
  reason:
    "Both anchor papers carry equal 0.25 weights, so the zero-citation 2026 paper pulls influence down and momentum rests on one paper — sparse evidence, low confidence.",
};

const AUTORESEARCH_FIT_CARD: MetricCard = {
  label: "Autoresearch Fit",
  value: "88.5 / 100",
  formula: [
    "A = 100 x weighted_average(0-5 dimension estimates) / 5",
    "",
    "modifiable search object       20 x 5.0 = 100.0",
    "executable objective           20 x 4.5 =  90.0",
    "correctness and anti-gaming    15 x 4.5 =  67.5",
    "incremental feedback           15 x 5.0 =  75.0",
    "fresh evaluation               10 x 2.5 =  25.0",
    "reproducibility, auditability  10 x 3.5 =  35.0",
    "attempt runtime                10 x 5.0 =  50.0",
    "                              weighted sum = 442.5 / 100 = 4.425",
    "",
    "A = 100 x 4.425 / 5 = 88.5",
  ],
  reason:
    "The explicit algorithm search object, executable benchmark, verified witnesses, directional attempt metrics, and five-minute loop make this a strong autoresearch fit. Fresh evaluation and reproducibility remain lower because the current results are synthetic and a real frozen holdout and executable environment are not yet present.",
};

export function StaticAssessmentPanel({
  problemId,
  eansvCard,
}: {
  problemId?: string;
  eansvCard?: MetricCard;
}) {
  const evaluation = problemId ? getStaticEvaluation(problemId) : null;
  const metricCards = eansvCard
    ? [SCIENTIFIC_DEMAND_CARD, eansvCard, AUTORESEARCH_FIT_CARD]
    : evaluation?.cards;
  if (!metricCards) return null;

  return (
    <section className={`assessment-panel ${styles.panel}`} aria-label="Assessment">
      {evaluation ? <p className={styles.disclosure}>{evaluation.disclosure}</p> : null}
      <div className={styles.metrics}>
        {metricCards.map((card) => (
          <details className={styles.metric} key={card.label}>
            <summary>
              <span className={styles.metricLabel}>{card.label}</span>
              <span className={styles.metricValue}>{card.value}</span>
              <span className={styles.metricToggle}>Formula &amp; reasoning</span>
            </summary>
            <div className={styles.metricDetail}>
              <pre className={styles.formula}>{card.formula.join("\n")}</pre>
              <p className={styles.reason}>{card.reason}</p>
            </div>
          </details>
        ))}
      </div>

      <a className={`open-affordance ${styles.methodologyLink}`} href={METHODOLOGY_HREF}>
        Methodology documentation <span aria-hidden="true">→</span>
      </a>
    </section>
  );
}

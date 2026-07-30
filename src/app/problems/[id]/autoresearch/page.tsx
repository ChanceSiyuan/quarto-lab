import generatedIndex from "../../../../../.generated/problem-index.json";
import {
  getStaticResearchExample,
  getStaticResearchExampleProblem,
  isStaticResearchExampleProblem,
} from "@/lib/problems/example-research.mjs";
import { buildExampleResearchLedger } from "@/lib/problems/example-presentation.mjs";
import { createProblemRepository } from "@/lib/problems/repository.mjs";
import Link from "next/link";
import { notFound } from "next/navigation";
import detailStyles from "../research-detail.module.css";

export default async function ProblemAutoresearchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const repository = createProblemRepository(generatedIndex);
  const problem = repository.getProblem(id) ?? getStaticResearchExampleProblem(id);

  if (!problem || !isStaticResearchExampleProblem(problem.id)) {
    notFound();
  }

  const example = getStaticResearchExample(problem.id);
  if (!example) {
    notFound();
  }
  const ledger = buildExampleResearchLedger(example);

  return (
    <main className="detail-shell research-shell">
      <div className="breadcrumb-row">
        <Link className="back-link" href={`/problems/${problem.id}`}>← Back to problem</Link>
        <Link className="back-link muted-back-link" href="/">Problem library</Link>
      </div>

      <header className="research-header">
        <div>
          <p className="eyebrow">{`${problem.id} / Autoresearch`}</p>
          <h1 className={detailStyles.title}>Autoresearch results</h1>
          <p className="detail-summary">{problem.title}</p>
        </div>
        <div className="research-badges" aria-label="Research metadata">
          <span>Example data</span>
          <span>Blind evaluation</span>
          <span>{ledger.rows.length} synthetic attempts</span>
        </div>
      </header>

      <p className="example-disclaimer">{example.manifest.disclaimer}</p>

      <dl className="research-metric-strip" aria-label="Research metrics">
        {ledger.cards.map((card) => (
          <div key={card.label}>
            <dt>{card.label}</dt>
            <dd>{card.value}</dd>
          </div>
        ))}
      </dl>

      <section className="attempt-ledger" aria-labelledby="attempt-ledger-heading">
        <div className="section-heading-row">
          <h2 id="attempt-ledger-heading">Attempts</h2>
          <p>{ledger.rows.length} synthetic attempts</p>
        </div>
        <div className="attempt-table-wrap">
          <table className="attempt-table">
            <thead>
              <tr>
                <th scope="col">Attempt</th><th scope="col">Method</th><th scope="col">Stage</th><th scope="col">Decision</th><th scope="col">Gate</th><th scope="col">Verified</th><th scope="col">Hits</th><th scope="col">Quality</th><th scope="col">Runtime</th><th scope="col">P95</th><th scope="col">Speedup</th><th scope="col">Open</th>
              </tr>
            </thead>
            <tbody>
              {ledger.rows.map((row) => (
                <tr key={row.id}>
                  <th scope="row"><Link href={row.href}>{row.id}</Link></th>
                  <td><strong>{row.method}</strong><span>{row.summary}</span></td>
                  <td>{row.stage}</td>
                  <td>{row.decision}</td>
                  <td>{row.gate.map((item) => <span key={item.label}>{item.label}: {item.value}</span>)}</td>
                  <td>{row.verified}</td>
                  <td>{row.hits}</td>
                  <td>{row.quality}</td>
                  <td>{row.runtime}</td>
                  <td>{row.p95}</td>
                  <td>{row.speedup}</td>
                  <td><Link href={row.href}>Open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="attempt-card-list" aria-label="Attempt cards">
          {ledger.rows.map((row) => (
            <Link className="attempt-card" href={row.href} key={row.id}>
              <span>{row.id}</span>
              <strong>{row.method}</strong>
              <small>{row.decision} · {row.verified} verified · {row.speedup}</small>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}

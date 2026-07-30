import generatedIndex from "../../../../../../.generated/problem-index.json";
import generatedResearchIndex from "../../../../../../.generated/research-index.json";
import { buildAttemptDossier } from "@/lib/problems/example-presentation.mjs";
import {
  getStaticResearchAttempt,
  getStaticResearchExample,
  getStaticResearchExampleProblem,
  isStaticResearchExampleProblem,
} from "@/lib/problems/example-research.mjs";
import { createProblemRepository } from "@/lib/problems/repository.mjs";
import { createResearchRepository } from "@/lib/problems/research-repository.mjs";
import { buildAttemptDetailResearchState } from "@/lib/problems/research-route-data.mjs";
import Link from "next/link";
import { notFound } from "next/navigation";
import detailStyles from "../../research-detail.module.css";

export default async function AttemptDetailPage({
  params,
}: {
  params: Promise<{ id: string; attemptId: string }>;
}) {
  const { id, attemptId } = await params;
  const repository = createProblemRepository(generatedIndex);
  const problem = repository.getProblem(id) ?? getStaticResearchExampleProblem(id);

  if (!problem) {
    notFound();
  }

  if (isStaticResearchExampleProblem(problem.id)) {
    const example = getStaticResearchExample(problem.id);
    const attempt = getStaticResearchAttempt(problem.id, attemptId);

    if (!example || !attempt) {
      notFound();
    }

    const dossier = buildAttemptDossier(attempt, example.manifest);

    return (
      <main className={`detail-shell attempt-shell ${detailStyles.shellZoom}`}>
        <div className="breadcrumb-row">
          <Link className="back-link" href={`/problems/${problem.id}/autoresearch`}>← Back to autoresearch results</Link>
          <Link className="back-link muted-back-link" href="/">Problem library</Link>
        </div>

        <header className="attempt-header">
          <div>
            <p className="eyebrow">{`${problem.id} / ${dossier.id}`}</p>
            <h1>{dossier.title}</h1>
            <p className="detail-summary">{dossier.summary}</p>
          </div>
          <div className="research-badges" aria-label="Attempt metadata">
            <span>{dossier.stage}</span>
            <span>{dossier.decision}</span>
            <span>Example data</span>
          </div>
        </header>

        <p className="example-disclaimer">{dossier.disclaimer}</p>

        <dl className="attempt-metric-strip" aria-label="Attempt metrics">
          {dossier.metrics.map((metric) => (
            <div key={metric.label}>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
            </div>
          ))}
        </dl>

        <div className="attempt-layout">
          <section className="attempt-main" aria-label="Attempt research record">
            <article>
              <h2>Hypothesis</h2>
              <p>{dossier.method.hypothesis}</p>
              <h3>Method changes</h3>
              <ul>{dossier.method.changes.map((item) => <li key={item}>{item}</li>)}</ul>
            </article>
            <article>
              <h2>Evaluation path</h2>
              <ol className="evaluation-path">
                {dossier.evaluationPath.map((item) => (
                  <li key={item.label}><span>{item.label}</span><strong>{item.value}</strong></li>
                ))}
              </ol>
            </article>
            <article>
              <h2>Result interpretation</h2>
              <p>{dossier.interpretation}</p>
            </article>
            <article>
              <h2>Learning carried forward</h2>
              <ul>{dossier.learnings.map((item) => <li key={item}>{item}</li>)}</ul>
            </article>
          </section>

          <aside className="attempt-audit" aria-label="Attempt audit metadata">
            <section>
              <h2>Provenance</h2>
              <dl>
                <div><dt>Branch</dt><dd>{dossier.provenance.branch}</dd></div>
                <div><dt>Commit</dt><dd>{dossier.provenance.commit}</dd></div>
                <div><dt>Worktree</dt><dd>{dossier.provenance.worktreeState}</dd></div>
                <div><dt>Model</dt><dd>{dossier.provenance.model}</dd></div>
                <div><dt>Created</dt><dd>{dossier.createdAt}</dd></div>
              </dl>
            </section>
            <section>
              <h2>Artifacts</h2>
              <ul>{dossier.artifacts.map((artifact) => <li key={artifact}><code>{artifact}</code></li>)}</ul>
            </section>
          </aside>
        </div>
      </main>
    );
  }

  const researchRepository = createResearchRepository(generatedResearchIndex);
  const researchRecord = researchRepository.getResearchRecord(problem.id);
  const researchState = buildAttemptDetailResearchState({ problem, researchRecord, attemptId });

  if (researchState.kind === "research-attempt") {
    const dossier = researchState.dossier;
    return (
      <main className="detail-shell attempt-shell">
        <div className="breadcrumb-row">
          <Link className="back-link" href={`/problems/${problem.id}`}>← Back to research ledger</Link>
          <Link className="back-link muted-back-link" href="/">Problem library</Link>
        </div>
        <header className="attempt-header">
          <div>
            <p className="eyebrow">{`${problem.id} / ${dossier.id}`}</p>
            <h1>{dossier.title}</h1>
            <p className="detail-summary">{dossier.summary}</p>
          </div>
          <div className="research-badges" aria-label="Attempt metadata">
            <span>{dossier.stage}</span>
            <span>{dossier.decision}</span>
            <span>{dossier.candidate.label}</span>
          </div>
        </header>
        <p className="example-disclaimer">{dossier.disclaimer}</p>
        {dossier.candidate.message ? <p className="example-disclaimer">{dossier.candidate.message}</p> : null}
        <dl className="attempt-metric-strip" aria-label="Attempt metrics">
          {dossier.metrics.map((metric) => (
            <div key={metric.label}><dt>{metric.label}</dt><dd>{metric.value}</dd></div>
          ))}
        </dl>
        <div className="attempt-layout">
          <section className="attempt-main" aria-label="Attempt research record">
            <article><h2>Method</h2><p>{dossier.method.description}</p></article>
            <article>
              <h2>Evaluation path</h2>
              <ol className="evaluation-path">
                {dossier.evaluationPath.map((item) => (
                  <li key={item.label}><span>{item.label}</span><strong>{item.value}</strong></li>
                ))}
              </ol>
            </article>
          </section>
          <aside className="attempt-audit" aria-label="Attempt audit metadata">
            <section>
              <h2>Provenance</h2>
              <dl>
                <div><dt>Branch</dt><dd>{dossier.provenance.sourceBranch}</dd></div>
                <div><dt>Commit</dt><dd>{dossier.provenance.sourceCommit}</dd></div>
                <div><dt>Infrastructure</dt><dd>{dossier.provenance.sourceInfrastructureCommit}</dd></div>
                <div><dt>Cohort</dt><dd>{dossier.provenance.sourceCohort}</dd></div>
                <div><dt>Model</dt><dd>{dossier.provenance.model ?? "not recorded"}</dd></div>
              </dl>
            </section>
            <section>
              <h2>Artifacts</h2>
              <ul>{dossier.artifacts.map((artifact) => <li key={artifact.path}><code>{artifact.path}</code><span>{artifact.sha256}</span></li>)}</ul>
            </section>
          </aside>
        </div>
      </main>
    );
  }

  notFound();
}

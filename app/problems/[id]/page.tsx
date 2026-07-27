import generatedIndex from "../../../.generated/problem-index.json";
import { createProblemRepository } from "@/lib/problems/repository.mjs";
import Link from "next/link";
import { notFound } from "next/navigation";

export default async function ProblemDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const repository = createProblemRepository(generatedIndex);
  const problem = repository.getProblem(id);

  if (!problem) {
    notFound();
  }

  return (
    <main className="detail-shell">
      <Link className="back-link" href="/">← Back to problems</Link>
      <p className="eyebrow">{problem.id}</p>
      <h1>{problem.title}</h1>
      <p className="detail-summary">{problem.summary}</p>
      <section className="detail-panel" aria-labelledby="detail-status-heading">
        <h2 id="detail-status-heading">Problem detail</h2>
        <p>详情界面将在后续设计；本页先固定路由、身份和返回路径。</p>
      </section>
    </main>
  );
}

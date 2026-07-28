import generatedIndex from "../.generated/problem-index.json";
import { buildCodexLaunch } from "@/lib/problems/codex-launch.mjs";
import { createProblemRepository } from "@/lib/problems/repository.mjs";
import { ProblemConsole } from "./problem-console";

export default function Home() {
  const repository = createProblemRepository(generatedIndex);
  const launch = buildCodexLaunch({
    workspacePath: generatedIndex.workspacePath,
    nextProblemId: generatedIndex.nextProblemId,
  });

  return (
    <ProblemConsole
      generatedAt={generatedIndex.generatedAt}
      workspacePath={generatedIndex.workspacePath}
      initialProblems={repository.listProblems({ includeRejected: true, includeArchived: true })}
      summary={repository.getSummary()}
      diagnostics={repository.getIndexDiagnostics()}
      launch={launch}
    />
  );
}

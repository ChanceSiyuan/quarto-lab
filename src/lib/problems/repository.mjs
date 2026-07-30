function normalizeQuery(query) {
  return String(query ?? "").trim().toLowerCase();
}

function matchesQuery(problem, query) {
  if (!query) return true;
  return [problem.id, problem.title, problem.summary]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

function cloneProblem(problem) {
  return structuredClone(problem);
}

export function createProblemRepository(index) {
  const problems = Array.isArray(index.problems) ? index.problems.map(cloneProblem) : [];
  return {
    listProblems(filters = {}) {
      const query = normalizeQuery(filters.query);
      const statuses = Array.isArray(filters.statuses) ? new Set(filters.statuses) : null;
      return problems.filter((problem) => {
        if (!filters.includeRejected && problem.status === "rejected") return false;
        if (!filters.includeArchived && problem.status === "archived") return false;
        if (statuses && !statuses.has(problem.status)) return false;
        return matchesQuery(problem, query);
      }).map(cloneProblem);
    },
    getSummary() {
      return { ...index.summary };
    },
    getIndexDiagnostics() {
      return Array.isArray(index.diagnostics) ? index.diagnostics.map((item) => ({ ...item })) : [];
    },
    getProblem(id) {
      const problem = problems.find((item) => item.id === id);
      return problem ? cloneProblem(problem) : null;
    },
  };
}

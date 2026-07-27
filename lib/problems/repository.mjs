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

export function createProblemRepository(index) {
  const problems = Array.isArray(index.problems) ? [...index.problems] : [];
  return {
    listProblems(filters = {}) {
      const query = normalizeQuery(filters.query);
      const statuses = Array.isArray(filters.statuses) ? new Set(filters.statuses) : null;
      return problems.filter((problem) => {
        if (!filters.includeRejected && problem.status === "rejected") return false;
        if (!filters.includeArchived && problem.status === "archived") return false;
        if (statuses && !statuses.has(problem.status)) return false;
        return matchesQuery(problem, query);
      });
    },
    getSummary() {
      return { ...index.summary };
    },
    getIndexDiagnostics() {
      return Array.isArray(index.diagnostics) ? index.diagnostics.map((item) => ({ ...item })) : [];
    },
    getProblem(id) {
      return problems.find((problem) => problem.id === id) ?? null;
    },
  };
}

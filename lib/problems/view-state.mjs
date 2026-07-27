export const ACTIVE_PROBLEM_STATUSES = [
  "draft",
  "qualifying",
  "accepted",
  "solving",
  "solved",
  "publishing",
  "published",
];

export function createDefaultProblemFilters() {
  return {
    query: "",
    selectedStatuses: [...ACTIVE_PROBLEM_STATUSES],
    showRejected: false,
    showArchived: false,
  };
}

export function clearProblemFilters() {
  return {
    query: "",
    selectedStatuses: [...ACTIVE_PROBLEM_STATUSES],
    showRejected: true,
    showArchived: true,
  };
}

export function filterProblems(problems, filters) {
  const query = String(filters.query ?? "").trim().toLowerCase();
  const selectedStatuses = new Set(filters.selectedStatuses ?? []);

  return problems.filter((problem) => {
    if (problem.status === "rejected") {
      if (!filters.showRejected) return false;
    } else if (problem.status === "archived") {
      if (!filters.showArchived) return false;
    } else if (!selectedStatuses.has(problem.status)) {
      return false;
    }

    return !query || [problem.id, problem.title, problem.summary]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
}

export function buildProblemHref(id) {
  return `/problems/${id}`;
}

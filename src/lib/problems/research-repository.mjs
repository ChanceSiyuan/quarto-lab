function clone(value) {
  return structuredClone(value);
}

export function createResearchRepository(index) {
  const records = Array.isArray(index.records) ? index.records.map(clone) : [];
  const diagnostics = Array.isArray(index.diagnostics) ? index.diagnostics.map(clone) : [];
  return {
    getResearchRecord(problemId) {
      const record = records.find((item) => item.problemId === problemId);
      return record ? clone(record) : null;
    },
    getAttempt(problemId, attemptId) {
      const record = records.find((item) => item.problemId === problemId);
      const attempt = record?.attempts.find((item) => item.id === attemptId);
      return attempt ? clone(attempt) : null;
    },
    getDiagnostics(problemId = null) {
      return diagnostics
        .filter((item) => !problemId || item.relativePath.includes(`/${problemId}/`) || item.relativePath.startsWith(`problems/${problemId}/`))
        .map(clone);
    },
  };
}

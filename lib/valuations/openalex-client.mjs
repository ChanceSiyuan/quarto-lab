import { createHash } from "node:crypto";

const DEFAULT_BASE_URL = "https://api.openalex.org";
const REQUEST_TIMEOUT_MS = 20_000;
const DEFAULT_MAX_WORKS = 100;

function providerError(code, message, details = {}) {
  const error = new Error(message);
  error.code = code;
  Object.assign(error, details);
  return error;
}

function stableId(value) {
  const text = String(value ?? "").trim();
  const openAlex = text.match(/(?:https?:\/\/openalex\.org\/)?(W\d+)$/i);
  return openAlex ? openAlex[1].toUpperCase() : null;
}

function normalizeDoi(value) {
  const text = String(value ?? "").trim();
  if (!text) return null;
  const doi = text.replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, "").replace(/^doi:/i, "");
  return /^10\.\S+\/\S+$/i.test(doi) ? doi.toLowerCase() : null;
}

function normalizedTopicId(value) {
  return String(value ?? "").trim().replace(/^https?:\/\/openalex\.org\//i, "").toUpperCase() || null;
}

function tokens(value) {
  return [...new Set(String(value ?? "").toLowerCase().match(/[\p{L}\p{N}]+/gu)?.filter((token) => token.length >= 3) ?? [])].sort();
}

function overlap(left, right) {
  const rightSet = new Set(right);
  return left.filter((item) => rightSet.has(item));
}

function jaccard(left, right) {
  const intersection = overlap(left, right).length;
  const union = new Set([...left, ...right]).size;
  return union === 0 ? 0 : intersection / union;
}

function reconstructAbstract(index) {
  if (!index || typeof index !== "object") return "";
  const entries = Object.entries(index).flatMap(([word, positions]) => Array.isArray(positions)
    ? positions.map((position) => [position, word]) : []);
  return entries.sort(([left], [right]) => left - right).map(([, word]) => word).join(" ");
}

export function calculatePaperRelevance({ normalizedProblem, anchorTopicIds = [], paper }) {
  const problemTokens = tokens(normalizedProblem);
  const titleTokens = tokens(paper?.title);
  const abstractTokens = tokens(paper?.abstract);
  const paperTopics = (paper?.topicIds ?? []).map(normalizedTopicId).filter(Boolean);
  const anchorTopics = anchorTopicIds.map(normalizedTopicId).filter(Boolean);
  const titleJaccard = jaccard(problemTokens, titleTokens);
  const abstractJaccard = jaccard(problemTokens, abstractTokens);
  const anchorTopicOverlap = jaccard(anchorTopics, paperTopics);
  const matchedProblemTokens = [...new Set([
    ...overlap(problemTokens, titleTokens),
    ...overlap(problemTokens, abstractTokens),
  ])].sort();
  return {
    relevance: 0.6 * titleJaccard + 0.3 * abstractJaccard + 0.1 * anchorTopicOverlap,
    matchedProblemTokens,
  };
}

function normalizeWork(work, { normalizedProblem, anchorTopicIds, inclusionReason, accessedAt }) {
  const abstract = reconstructAbstract(work.abstract_inverted_index);
  const topicIds = (work.topics ?? []).map((topic) => normalizedTopicId(topic?.id)).filter(Boolean).sort();
  const { relevance, matchedProblemTokens } = calculatePaperRelevance({
    normalizedProblem,
    anchorTopicIds,
    paper: { title: work.title, abstract, topicIds },
  });
  return {
    id: stableId(work.id),
    doi: normalizeDoi(work.doi),
    title: String(work.title ?? ""),
    publicationYear: Number.isInteger(work.publication_year) ? work.publication_year : null,
    topicIds,
    citedByCount: Number.isFinite(work.cited_by_count) ? work.cited_by_count : null,
    citationNormalizedPercentile: Number.isFinite(work.citation_normalized_percentile?.value) ? work.citation_normalized_percentile.value : null,
    countsByYear: Array.isArray(work.counts_by_year)
      ? work.counts_by_year.filter((count) => Number.isInteger(count?.year) && Number.isFinite(count?.cited_by_count)).map((count) => ({ year: count.year, citedByCount: count.cited_by_count })).sort((left, right) => left.year - right.year)
      : [],
    referencedWorkIds: (work.referenced_works ?? []).map(stableId).filter(Boolean).sort(),
    abstractHash: abstract ? createHash("sha256").update(abstract).digest("hex") : null,
    matchedProblemTokens,
    relevance,
    inclusionReason,
    accessedAt,
  };
}

export function createOpenAlexClient({ fetchFn = globalThis.fetch, apiKey, baseUrl = DEFAULT_BASE_URL, maxWorks = DEFAULT_MAX_WORKS, now = () => new Date() } = {}) {
  if (typeof fetchFn !== "function") throw new TypeError("fetchFn must be a function.");
  const isLiveClient = fetchFn === globalThis.fetch;
  const limit = Math.min(DEFAULT_MAX_WORKS, Math.max(1, Number.isInteger(maxWorks) ? maxWorks : DEFAULT_MAX_WORKS));

  async function request(path, params = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const url = new URL(path, baseUrl);
      Object.entries({ ...params, api_key: apiKey }).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
      });
      const response = await fetchFn(url.toString(), { signal: controller.signal });
      if (!response?.ok) throw providerError("OPENALEX_PROVIDER_ERROR", `OpenAlex request failed with status ${response?.status ?? "unknown"}.`, { status: response?.status });
      return response.json();
    } catch (error) {
      if (error?.code) throw error;
      throw providerError("OPENALEX_PROVIDER_ERROR", "OpenAlex request failed.", { cause: error });
    } finally {
      clearTimeout(timeout);
    }
  }

  return Object.freeze({
    async expand({ anchors = [], topicIds = [], normalizedProblem = "" } = {}) {
      if (isLiveClient && !apiKey) throw providerError("OPENALEX_KEY_REQUIRED", "An OpenAlex API key is required to collect citation evidence.");
      const accessTime = new Date(now()).toISOString();
      const anchorIds = new Set(anchors.map(stableId).filter(Boolean));
      const anchorDois = anchors.map(normalizeDoi).filter(Boolean);
      const seedResponses = await Promise.all([
        ...[...anchorIds].map((id) => request(`/works/${id}`)),
        ...anchorDois.map((doi) => request(`/works/${encodeURIComponent(`https://doi.org/${doi}`)}`)),
      ]);
      const seeds = seedResponses.filter((value) => value?.id);
      seeds.forEach((work) => anchorIds.add(stableId(work.id)));
      const anchorTopicIds = [...new Set([
        ...topicIds.map(normalizedTopicId).filter(Boolean),
        ...seeds.flatMap((work) => (work.topics ?? []).map((topic) => normalizedTopicId(topic?.id)).filter(Boolean)),
      ])].sort();
      const citedResponses = await Promise.all([...anchorIds].map((id) => request("/works", { filter: `cites:${id}`, "per-page": limit })));
      const referencedIds = [...new Set(seeds.flatMap((work) => (work.referenced_works ?? []).map(stableId).filter(Boolean)))];
      const referencedResponses = await Promise.all(referencedIds.map((id) => request(`/works/${id}`)));
      const topicResponses = await Promise.all(anchorTopicIds.map((id) => request("/works", { filter: `topics.id:${id}`, "per-page": limit })));
      const works = [
        ...seeds,
        ...citedResponses.flatMap((response) => response?.results ?? []),
        ...referencedResponses.filter((value) => value?.id),
        ...topicResponses.flatMap((response) => response?.results ?? []),
      ];
      const normalized = new Map();
      for (const work of works) {
        const id = stableId(work?.id);
        if (!id || normalized.has(id)) continue;
        const isAnchor = anchorIds.has(id);
        const paper = normalizeWork(work, {
          normalizedProblem,
          anchorTopicIds,
          inclusionReason: isAnchor ? "confirmed-anchor" : "relevance-threshold",
          accessedAt: accessTime,
        });
        if (isAnchor || paper.relevance >= 0.15) normalized.set(id, paper);
      }
      return [...normalized.values()].sort((left, right) => left.id.localeCompare(right.id)).slice(0, limit);
    },
  });
}

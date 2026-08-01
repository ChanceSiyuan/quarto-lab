import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, realpath, stat } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import {
  KnowledgeQueryError,
  resolveKnowledge,
  type ReadingBundle,
  type ResolveCandidate,
  type ResolveResult,
} from "../knowledge/index.js";
import { loadBibliography, type LiteratureEntry } from "../literature/index.js";
import { buildProblemIndex } from "../problems/indexer.mjs";
import { createProblemRepository } from "../problems/repository.mjs";
import {
  CompanionIdError,
  assertCompanionQuery,
  decodeCompanionId,
  encodeKnowledgeId,
  encodeLiteratureId,
  encodeProblemId,
} from "./ids.js";

const run = promisify(execFile);
const SHA256_HEX = /^[a-f0-9]{64}$/u;
const DEFAULT_MAX_RESULTS = 20;
const MAX_RESULTS = 50;
const MAX_PUBLIC_BASE_URL_CHARS = 2_048;

export type CompanionNamespace = "knowledge" | "problem" | "literature";
export type CompanionAuthority =
  | "reviewed_knowledge"
  | "open_problem"
  | "external_evidence";

export interface CompanionSearchResult {
  id: string;
  namespace: CompanionNamespace;
  authority: CompanionAuthority;
  title: string;
  summary: string;
  url: string;
}

export interface CompanionKnowledgeFile {
  path: string;
  content: string;
  sha256: string;
}

export interface CompanionDocument {
  id: string;
  namespace: CompanionNamespace;
  authority: CompanionAuthority;
  title: string;
  url: string;
  text: string;
  metadata: Record<string, unknown>;
  files?: readonly CompanionKnowledgeFile[];
  provenance?: {
    repositoryRevision: string;
    files: readonly { path: string; sha256: string }[];
  };
}

export interface CompanionContext {
  search(query: string): Promise<readonly CompanionSearchResult[]>;
  fetch(id: string): Promise<CompanionDocument>;
}

interface ProblemManifest {
  schemaVersion: number;
  id: string;
  title: string;
  summary: string;
  status: string;
  gate: { type: string; readiness: string };
  provenance: { sourceCount: number };
  lastActivity: { summary: string; at: string };
  createdAt: string;
  updatedAt: string;
  domain?: string;
  quantumArea?: string;
}

interface ProblemRepository {
  listProblems(filters?: { query?: string }): ProblemManifest[];
  getProblem(id: string): ProblemManifest | null;
}

export interface CompanionContextDependencies {
  resolveKnowledge: typeof resolveKnowledge;
  loadBibliography: typeof loadBibliography;
  buildProblemIndex: (options: { rootDir: string }) => Promise<unknown>;
  createProblemRepository: (index: unknown) => ProblemRepository;
  readFile: typeof readFile;
  realpath: typeof realpath;
  getRepositoryRevision: (repoRoot: string) => Promise<string>;
  sha256: (value: string) => Promise<string>;
}

export interface CreateCompanionContextOptions {
  repoRoot: string;
  bibliographyPath?: string;
  publicBaseUrl: string;
  accessToken?: string;
  maxResults?: number;
  dependencies?: Partial<CompanionContextDependencies>;
}

export class CompanionInputError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CompanionInputError";
  }
}

export class CompanionNotFoundError extends Error {
  constructor() {
    super("document not found");
    this.name = "CompanionNotFoundError";
  }
}

export class CompanionIntegrityError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CompanionIntegrityError";
  }
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function isWithin(parent: string, candidate: string): boolean {
  const relative = path.relative(parent, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== "..");
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

async function defaultSha256(value: string): Promise<string> {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

async function defaultRepositoryRevision(repoRoot: string): Promise<string> {
  try {
    const { stdout } = await run("git", ["rev-parse", "--verify", "HEAD"], {
      cwd: repoRoot,
      encoding: "utf8",
    });
    const revision = stdout.trim();
    if (!/^[a-f0-9]{40,64}$/u.test(revision)) throw new Error("invalid Git revision");
    return revision;
  } catch (error) {
    throw new CompanionIntegrityError(
      `could not read the repository revision: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

const DEFAULT_DEPENDENCIES: CompanionContextDependencies = {
  resolveKnowledge,
  loadBibliography,
  buildProblemIndex: (options) => buildProblemIndex(options),
  createProblemRepository: (index) => createProblemRepository(index) as ProblemRepository,
  readFile,
  realpath,
  getRepositoryRevision: defaultRepositoryRevision,
  sha256: defaultSha256,
};

function validatePublicBaseUrl(raw: string, accessToken?: string): URL {
  if (typeof raw !== "string" || raw.length === 0 || raw.length > MAX_PUBLIC_BASE_URL_CHARS) {
    throw new CompanionInputError("public content base URL is invalid");
  }
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new CompanionInputError("public content base URL is invalid");
  }
  if (
    url.protocol !== "https:" ||
    url.username !== "" ||
    url.password !== "" ||
    url.search !== "" ||
    url.hash !== "" ||
    url.pathname !== "/"
  ) {
    throw new CompanionInputError(
      "public content base URL must be a credential-free HTTPS origin",
    );
  }
  if (
    accessToken !== undefined &&
    accessToken !== "" &&
    (url.href.includes(accessToken) || url.href.includes(encodeURIComponent(accessToken)))
  ) {
    throw new CompanionInputError("public content base URL must not contain access-token text");
  }
  return url;
}

function validateMaxResults(value: number | undefined): number {
  const result = value ?? DEFAULT_MAX_RESULTS;
  if (!Number.isInteger(result) || result < 1 || result > MAX_RESULTS) {
    throw new CompanionInputError(`maxResults must be an integer from 1 to ${MAX_RESULTS}`);
  }
  return result;
}

function publicUrl(base: URL, relativePath: string): string {
  const encoded = relativePath
    .split("/")
    .filter(Boolean)
    .map(encodeURIComponent)
    .join("/");
  return new URL(encoded, base).href;
}

function knowledgeUrlPath(page: string): string {
  const withoutPrefix = page.replace(/^knowledge\//u, "");
  if (withoutPrefix === "index.qmd") return "knowledge/";
  if (withoutPrefix.endsWith("/index.qmd")) {
    return `knowledge/${withoutPrefix.slice(0, -"index.qmd".length)}`;
  }
  return `knowledge/${withoutPrefix.replace(/\.qmd$/u, ".html")}`;
}

function topicLabel(topic: string): string {
  const segments = topic.split("/");
  const slug = segments.at(-2) ?? "Knowledge";
  return slug.charAt(0).toUpperCase() + slug.slice(1);
}

type KnowledgeSelection =
  | { kind: "bundle"; bundle: ReadingBundle }
  | { kind: "candidate"; candidate: ResolveCandidate };

function selectionsFromResolution(result: ResolveResult): readonly KnowledgeSelection[] {
  if (result.status === "match") return [{ kind: "bundle", bundle: result.bundle }];
  if (result.status === "ambiguous") {
    return result.alternatives.map((candidate) => ({ kind: "candidate", candidate }));
  }
  return [];
}

function selectionIdentity(selection: KnowledgeSelection): unknown {
  if (selection.kind === "candidate") {
    const { page, topic, title, matchKind, tier, matchedTerms } = selection.candidate;
    return { kind: "candidate", page, topic, title, matchKind, tier, matchedTerms };
  }
  const { topic, ancestorIndexes, contentPages, orderedFiles } = selection.bundle;
  return { kind: "bundle", topic, ancestorIndexes, contentPages, orderedFiles };
}

async function digestSelections(
  selections: readonly KnowledgeSelection[],
  sha256: (value: string) => Promise<string>,
): Promise<readonly { selection: KnowledgeSelection; digest: string }[]> {
  const digested = await Promise.all(
    selections.map(async (selection) => ({
      selection,
      digest: await sha256(canonicalJson(selectionIdentity(selection))),
    })),
  );
  if (digested.some(({ digest }) => !SHA256_HEX.test(digest))) {
    throw new CompanionIntegrityError("the selection digest provider returned an invalid SHA-256");
  }
  if (new Set(digested.map(({ digest }) => digest)).size !== digested.length) {
    throw new CompanionIntegrityError("knowledge selection digest collision");
  }
  return digested;
}

function knowledgeSearchResult(
  query: string,
  selection: KnowledgeSelection,
  digest: string,
  base: URL,
): CompanionSearchResult {
  const page =
    selection.kind === "candidate" ? selection.candidate.page : selection.bundle.topic;
  const title =
    selection.kind === "candidate"
      ? `${selection.candidate.title} · ${topicLabel(selection.candidate.topic)}`
      : query;
  return {
    id: encodeKnowledgeId({ query, selectionDigest: digest }),
    namespace: "knowledge",
    authority: "reviewed_knowledge",
    title,
    summary:
      selection.kind === "candidate"
        ? "Reviewed Knowledge candidate; fetch this candidate before relying on it."
        : "Reviewed Knowledge match; fetch the full ordered reading bundle before relying on it.",
    url: publicUrl(base, knowledgeUrlPath(page)),
  };
}

export function isCompanionVisibleProblem(
  problem: ProblemManifest | null | undefined,
): problem is ProblemManifest {
  return (
    problem !== null &&
    problem !== undefined &&
    problem.status !== "rejected" &&
    problem.status !== "archived"
  );
}

function publicProblem(problem: ProblemManifest): Record<string, unknown> {
  const result: Record<string, unknown> = {
    schemaVersion: problem.schemaVersion,
    id: problem.id,
    title: problem.title,
    summary: problem.summary,
    status: problem.status,
    gate: clone(problem.gate),
    provenance: clone(problem.provenance),
    lastActivity: clone(problem.lastActivity),
    createdAt: problem.createdAt,
    updatedAt: problem.updatedAt,
  };
  if (problem.domain !== undefined) result.domain = problem.domain;
  if (problem.quantumArea !== undefined) result.quantumArea = problem.quantumArea;
  return result;
}

function literatureMatches(entry: LiteratureEntry, query: string): boolean {
  const terms =
    query
      .normalize("NFKC")
      .toLocaleLowerCase("en-US")
      .match(/[\p{L}\p{N}]+/gu) ?? [];
  if (terms.length === 0) return false;
  const searchable = [
    entry.citekey,
    entry.title,
    ...entry.authors,
    entry.year ?? "",
    entry.doi ?? "",
    entry.arxiv ?? "",
    ...entry.methods,
  ]
    .join(" ")
    .normalize("NFKC")
    .toLocaleLowerCase("en-US");
  return terms.every((term) => searchable.includes(term));
}

function publicLiterature(entry: LiteratureEntry): Record<string, unknown> {
  const metadata: Record<string, unknown> = {
    citekey: entry.citekey,
    type: entry.type,
    title: entry.title,
    authors: [...entry.authors],
  };
  if (entry.year !== undefined) metadata.year = entry.year;
  if (entry.doi !== undefined) metadata.doi = entry.doi;
  if (entry.arxiv !== undefined) metadata.arxiv = entry.arxiv;
  metadata.methods = [...entry.methods];
  return metadata;
}

function notFound(): never {
  throw new CompanionNotFoundError();
}

async function readKnowledgeBundle(input: {
  id: string;
  title: string;
  bundle: ReadingBundle;
  repoRoot: string;
  knowledgeRoot: string;
  base: URL;
  dependencies: CompanionContextDependencies;
}): Promise<CompanionDocument> {
  const files: CompanionKnowledgeFile[] = [];
  for (const relativePath of input.bundle.orderedFiles) {
    if (
      path.posix.isAbsolute(relativePath) ||
      !relativePath.startsWith("knowledge/") ||
      relativePath.includes("\\")
    ) {
      throw new CompanionIntegrityError("resolver returned a path outside knowledge/");
    }
    const absolute = path.resolve(input.repoRoot, ...relativePath.split("/"));
    if (!isWithin(input.knowledgeRoot, absolute)) {
      throw new CompanionIntegrityError("resolver returned a path outside knowledge/");
    }
    let physical: string;
    try {
      physical = await input.dependencies.realpath(absolute);
    } catch {
      throw new CompanionIntegrityError("a resolved Knowledge file is unavailable");
    }
    if (!isWithin(input.knowledgeRoot, physical)) {
      throw new CompanionIntegrityError("a resolved Knowledge file escapes knowledge/");
    }
    const content = await input.dependencies.readFile(physical, "utf8");
    const sha256 = await input.dependencies.sha256(content);
    if (!SHA256_HEX.test(sha256)) {
      throw new CompanionIntegrityError("the content digest provider returned an invalid SHA-256");
    }
    files.push({ path: relativePath, content, sha256 });
  }
  const repositoryRevision = await input.dependencies.getRepositoryRevision(input.repoRoot);
  if (typeof repositoryRevision !== "string" || repositoryRevision.trim() === "") {
    throw new CompanionIntegrityError("repository revision is unavailable");
  }
  return {
    id: input.id,
    namespace: "knowledge",
    authority: "reviewed_knowledge",
    title: input.title,
    url: publicUrl(input.base, knowledgeUrlPath(input.bundle.topic)),
    text: files.map((file) => `<!-- ${file.path} -->\n${file.content}`).join("\n\n"),
    metadata: { reviewStatus: "reviewed" },
    files,
    provenance: {
      repositoryRevision,
      files: files.map((file) => ({ path: file.path, sha256: file.sha256 })),
    },
  };
}

export async function createCompanionContext(
  options: CreateCompanionContextOptions,
): Promise<CompanionContext> {
  if (!path.isAbsolute(options.repoRoot)) {
    throw new CompanionInputError("repoRoot must be an absolute path");
  }
  const dependencies: CompanionContextDependencies = {
    ...DEFAULT_DEPENDENCIES,
    ...options.dependencies,
  };
  let repoRoot: string;
  try {
    repoRoot = await dependencies.realpath(options.repoRoot);
    if (!(await stat(repoRoot)).isDirectory()) throw new Error("not a directory");
  } catch (error) {
    throw new CompanionInputError(
      `repoRoot is unavailable: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  const base = validatePublicBaseUrl(options.publicBaseUrl, options.accessToken);
  const maxResults = validateMaxResults(options.maxResults);
  const literatureRoot = path.join(repoRoot, "literature");
  const requestedBibliography = path.resolve(
    repoRoot,
    options.bibliographyPath ?? path.join("literature", "ref.bib"),
  );
  if (!isWithin(literatureRoot, requestedBibliography)) {
    throw new CompanionInputError("bibliography must remain below literature/");
  }
  let bibliographyPath: string;
  let physicalLiteratureRoot: string;
  let knowledgeRoot: string;
  try {
    [bibliographyPath, physicalLiteratureRoot, knowledgeRoot] = await Promise.all([
      dependencies.realpath(requestedBibliography),
      dependencies.realpath(literatureRoot),
      dependencies.realpath(path.join(repoRoot, "knowledge")),
    ]);
  } catch (error) {
    throw new CompanionInputError(
      `repository content roots are unavailable: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  if (!isWithin(physicalLiteratureRoot, bibliographyPath)) {
    throw new CompanionInputError("bibliography must remain below literature/");
  }

  async function resolve(query: string): Promise<ResolveResult> {
    try {
      return await dependencies.resolveKnowledge(query, { repoRoot, bibliographyPath });
    } catch (error) {
      if (error instanceof KnowledgeQueryError) {
        throw new CompanionInputError(error.message);
      }
      throw error;
    }
  }

  async function problemRepository(): Promise<ProblemRepository> {
    const index = await dependencies.buildProblemIndex({ rootDir: repoRoot });
    return dependencies.createProblemRepository(index);
  }

  return {
    async search(query: string): Promise<readonly CompanionSearchResult[]> {
      try {
        assertCompanionQuery(query);
      } catch (error) {
        if (error instanceof CompanionIdError) {
          throw new CompanionInputError("query is blank, unsafe, or over the size limit");
        }
        throw error;
      }

      const results: CompanionSearchResult[] = [];
      const knowledge = await resolve(query);
      const selections = await digestSelections(
        selectionsFromResolution(knowledge),
        dependencies.sha256,
      );
      for (const { selection, digest } of selections) {
        results.push(knowledgeSearchResult(query, selection, digest, base));
      }

      if (results.length < maxResults) {
        const repository = await problemRepository();
        for (const problem of repository.listProblems({ query })) {
          if (!isCompanionVisibleProblem(problem)) continue;
          results.push({
            id: encodeProblemId(problem.id),
            namespace: "problem",
            authority: "open_problem",
            title: problem.title,
            summary: problem.summary,
            url: publicUrl(base, `problems/${problem.id}`),
          });
          if (results.length === maxResults) break;
        }
      }

      if (results.length < maxResults) {
        const entries = await dependencies.loadBibliography(bibliographyPath);
        for (const entry of entries) {
          if (!literatureMatches(entry, query)) continue;
          results.push({
            id: encodeLiteratureId(entry.citekey),
            namespace: "literature",
            authority: "external_evidence",
            title: entry.title,
            summary: [entry.authors.join(", "), entry.year].filter(Boolean).join(" · "),
            url: publicUrl(base, `literature/${entry.citekey}`),
          });
          if (results.length === maxResults) break;
        }
      }
      return results.map(clone);
    },

    async fetch(id: string): Promise<CompanionDocument> {
      const decoded = decodeCompanionId(id);
      if (decoded.namespace === "knowledge") {
        const resolution = await resolve(decoded.query);
        const digested = await digestSelections(
          selectionsFromResolution(resolution),
          dependencies.sha256,
        );
        const matches = digested.filter(({ digest }) => digest === decoded.selectionDigest);
        if (matches.length !== 1) return notFound();
        const [matched] = matches;
        let bundle: ReadingBundle;
        let title = decoded.query;
        if (matched.selection.kind === "bundle") {
          bundle = matched.selection.bundle;
        } else {
          title = `${matched.selection.candidate.title} · ${topicLabel(matched.selection.candidate.topic)}`;
          let selected: ResolveResult;
          try {
            selected = await dependencies.resolveKnowledge(decoded.query, {
              repoRoot,
              bibliographyPath,
              selectedPage: matched.selection.candidate.page,
            });
          } catch {
            return notFound();
          }
          if (selected.status !== "match") return notFound();
          bundle = selected.bundle;
        }
        return clone(
          await readKnowledgeBundle({
            id,
            title,
            bundle,
            repoRoot,
            knowledgeRoot,
            base,
            dependencies,
          }),
        );
      }

      if (decoded.namespace === "problem") {
        const problem = (await problemRepository()).getProblem(decoded.problemId);
        if (!isCompanionVisibleProblem(problem)) return notFound();
        const metadata = publicProblem(problem);
        return clone({
          id,
          namespace: "problem",
          authority: "open_problem",
          title: problem.title,
          url: publicUrl(base, `problems/${problem.id}`),
          text: problem.summary,
          metadata,
        });
      }

      const entry = (await dependencies.loadBibliography(bibliographyPath)).find(
        (candidate) => candidate.citekey === decoded.citekey,
      );
      if (entry === undefined) return notFound();
      const metadata = publicLiterature(entry);
      return clone({
        id,
        namespace: "literature",
        authority: "external_evidence",
        title: entry.title,
        url: publicUrl(base, `literature/${entry.citekey}`),
        text: [
          entry.title,
          entry.authors.join(", "),
          entry.year,
          entry.doi === undefined ? undefined : `DOI: ${entry.doi}`,
          entry.arxiv === undefined ? undefined : `arXiv: ${entry.arxiv}`,
          entry.methods.length === 0 ? undefined : `Methods: ${entry.methods.join(", ")}`,
        ]
          .filter((line): line is string => line !== undefined && line !== "")
          .join("\n"),
        metadata,
      });
    },
  };
}

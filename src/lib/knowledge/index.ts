/**
 * Public interface of the knowledge module.
 *
 * The CLI, the Make targets, and the agent skills are thin adapters over these
 * entry points; nothing outside `src/lib/knowledge` may re-implement parsing,
 * containment, validation, or ranking, because two implementations of "what
 * does the knowledge tree say?" is exactly the drift this module exists to
 * prevent.
 *
 * The three error classes are exported with the functions that throw them: a
 * caller cannot honour "never act on an invalid tree" without being able to
 * catch the refusal.
 */

export { loadKnowledge } from "./graph.js";
export { KnowledgeValidationError, validateKnowledge } from "./validate.js";
export { compileTree, extractTreeBlock } from "./tree.js";
export type { CompiledTree, CompiledTreeNode, TreeDiagnostic } from "./tree.js";
export { KnowledgeQueryError, resolveKnowledge } from "./resolve.js";
export { KnowledgeSiteError, buildKnowledgeSite, previewKnowledgeSite } from "./site.js";

export type { KnowledgeGraph, LoadKnowledgeOptions } from "./graph.js";
export type { ValidationReport } from "./validate.js";
export type {
  AtomicDirectoryOps,
  BuildKnowledgeSiteOptions,
  BuildKnowledgeSiteResult,
  ProcessRunner,
} from "./site.js";
export type {
  MatchKind,
  ReadingBundle,
  ResolveCandidate,
  ResolveResult,
} from "./resolve.js";
export type { Diagnostic, ParsedKnowledgePage } from "./types.js";

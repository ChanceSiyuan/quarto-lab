/**
 * Public interface of the knowledge module.
 *
 * The CLI, the Make targets, and the agent skills are thin adapters over these
 * entry points; nothing outside `lib/knowledge` may re-implement parsing,
 * containment, validation, or ranking, because two implementations of "what
 * does the knowledge tree say?" is exactly the drift this module exists to
 * prevent.
 *
 * The two error classes are exported with the functions that throw them: a
 * caller cannot honour "never act on an invalid tree" without being able to
 * catch the refusal. The site build lands in a later task.
 */

export { loadKnowledge } from "./graph.js";
export { KnowledgeValidationError, validateKnowledge } from "./validate.js";
export { KnowledgeQueryError, resolveKnowledge } from "./resolve.js";

export type { KnowledgeGraph, LoadKnowledgeOptions } from "./graph.js";
export type { ValidationReport } from "./validate.js";
export type {
  MatchKind,
  ReadingBundle,
  ResolveCandidate,
  ResolveResult,
} from "./resolve.js";
export type { Diagnostic, ParsedKnowledgePage } from "./types.js";

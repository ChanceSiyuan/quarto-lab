/**
 * Public interface of the literature module.
 *
 * CLIs, Make targets, and skills use these entry points; they must not
 * re-implement bibliography, index, or fetch semantics.
 */

export { loadBibliography } from "./bibliography.js";
export { writeMethodIndexes } from "./indexes.js";
// The error is exported with the functions that throw it: a caller cannot tell
// "no such citekey" from "arXiv was unreachable" — and a CLI cannot pick the
// right exit code — without being able to catch the refusal.
export {
  LiteratureFetchError,
  fetchLiteratureEntry,
  syncLiterature,
} from "./fetch.js";

export type { LiteratureEntry } from "./bibliography.js";
export type { LiteratureManifest } from "./fetch.js";

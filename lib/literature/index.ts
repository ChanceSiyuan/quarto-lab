/**
 * Public interface of the literature module.
 *
 * CLIs, Make targets, and skills use these entry points; they must not
 * re-implement bibliography or index semantics.
 */

export { loadBibliography } from "./bibliography.js";
export { writeMethodIndexes } from "./indexes.js";

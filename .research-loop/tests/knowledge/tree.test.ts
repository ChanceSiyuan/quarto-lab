import assert from "node:assert/strict";
import test from "node:test";

import { compileTree, extractTreeBlock } from "../../../src/lib/knowledge/tree.js";

const SITE_PATH = "/knowledge/";
const PAGES = new Set([
  "index.qmd",
  "TN_sim/index.qmd",
  "TN_sim/MPS_DMRG.qmd",
  "Magic/index.qmd",
]);

const VALID_BLOCK = [
  "root: Research Knowledge",
  "nodes:",
  "  - label: Tensor Networks",
  "    note: TN_sim/index.qmd",
  "    zotero: zotero://select/library/collections/ABCD1234",
  "    x: 120",
  "    y: 80",
  "    children:",
  "      - label: MPS & DMRG",
  "        note: TN_sim/MPS_DMRG.qmd",
  "        zotero: zotero://open-pdf/library/items/KEY?page=4",
  "  - label: Planned Topic",
].join("\n");

function page(blockBody: string): string {
  return [
    "---",
    "title: Research Knowledge",
    "description: Root.",
    "---",
    "",
    "# Research Knowledge",
    "",
    "```qlab-tree",
    blockBody,
    "```",
    "",
  ].join("\n");
}

function compile(blockBody: string) {
  const extracted = extractTreeBlock(page(blockBody));
  assert.ok(extracted, "block should extract");
  return compileTree({
    yamlText: extracted.yamlText,
    startLine: extracted.startLine,
    pages: PAGES,
    sitePath: SITE_PATH,
  });
}

test("extracts the qlab-tree block with its opening-fence line", () => {
  const extracted = extractTreeBlock(page(VALID_BLOCK));
  assert.ok(extracted);
  assert.equal(extracted.startLine, 8);
  assert.equal(extracted.yamlText.split("\n")[0], "root: Research Knowledge");
});

test("returns null for a page without a tree block", () => {
  assert.equal(extractTreeBlock("---\ntitle: T\ndescription: D\n---\n\nBody.\n"), null);
});

test("ignores an ordinary fenced block and an unclosed qlab-tree fence", () => {
  assert.equal(extractTreeBlock("```python\nroot: nope\n```\n"), null);
  assert.equal(extractTreeBlock("```qlab-tree\nroot: never closed\n"), null);
});

test("compiles a valid block deterministically", () => {
  const first = compile(VALID_BLOCK);
  const second = compile(VALID_BLOCK);
  assert.deepEqual(first.diagnostics, []);
  assert.deepEqual(first, second);
  const tree = first.tree;
  assert.ok(tree);
  assert.equal(tree.root, "Research Knowledge");
  assert.equal(tree.nodes.length, 2);
  const tn = tree.nodes[0];
  assert.equal(tn.id, "tensor-networks");
  assert.equal(tn.noteUrl, "/knowledge/TN_sim/index.html");
  assert.equal(tn.zotero, "zotero://select/library/collections/ABCD1234");
  assert.equal(tn.x, 120);
  assert.equal(tn.y, 80);
  const child = tn.children[0];
  assert.equal(child.id, "tensor-networks/mps-dmrg");
  assert.equal(child.noteUrl, "/knowledge/TN_sim/MPS_DMRG.html");
  const planned = tree.nodes[1];
  assert.equal(planned.noteUrl, null);
  assert.equal(planned.zotero, null);
  assert.equal(planned.x, null);
});

test("defaults the root title", () => {
  const { tree, diagnostics } = compile("nodes:\n  - label: Solo");
  assert.deepEqual(diagnostics, []);
  assert.equal(tree?.root, "Research Knowledge");
});

test("reports unparseable YAML with the fence line", () => {
  const { tree, diagnostics } = compile("nodes: [unclosed");
  assert.equal(tree, null);
  assert.equal(diagnostics[0]?.code, "TREE_YAML_INVALID");
  assert.equal(diagnostics[0]?.line, 8);
});

test("reports a non-mapping document and a non-list nodes field", () => {
  assert.equal(compile("just a string").diagnostics[0]?.code, "TREE_YAML_INVALID");
  assert.equal(compile("nodes: 7").diagnostics[0]?.code, "TREE_YAML_INVALID");
});

test("reports missing and duplicate labels", () => {
  const missing = compile("nodes:\n  - note: TN_sim/index.qmd");
  assert.equal(missing.diagnostics[0]?.code, "TREE_LABEL_INVALID");
  const duplicate = compile("nodes:\n  - label: Twin\n  - label: Twin");
  assert.equal(duplicate.diagnostics[0]?.code, "TREE_LABEL_INVALID");
  assert.equal(duplicate.tree, null);
});

test("reports a note that is not a knowledge page", () => {
  const { diagnostics } = compile("nodes:\n  - label: Ghost\n    note: Missing/index.qmd");
  assert.equal(diagnostics[0]?.code, "TREE_NOTE_MISSING");
  assert.match(diagnostics[0]!.message, /Missing\/index\.qmd/);
});

test("reports a non-zotero scheme on the zotero field", () => {
  const { diagnostics } = compile("nodes:\n  - label: Bad\n    zotero: https://example.com");
  assert.equal(diagnostics[0]?.code, "TREE_LINK_SCHEME");
});

test("reports non-numeric coordinates", () => {
  const { diagnostics } = compile("nodes:\n  - label: Bad\n    x: wide");
  assert.equal(diagnostics[0]?.code, "TREE_COORD_INVALID");
});

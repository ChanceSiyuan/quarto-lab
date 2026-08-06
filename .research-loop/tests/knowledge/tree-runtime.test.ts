import assert from "node:assert/strict";
import test from "node:test";

import { parse as parseYaml } from "yaml";

// The runtime is the browser module the projection embeds; importing it here
// must stay side-effect free (no DOM, data placeholder still null).
import {
  autoLayout,
  effectivePositions,
  serializeTreeYaml,
} from "../../../src/lib/knowledge/tree-runtime.js";

const NODES = [
  {
    id: "a",
    label: "A",
    noteUrl: "/knowledge/A/index.html",
    zotero: null,
    x: null,
    y: null,
    children: [
      { id: "a/b", label: "B", noteUrl: null, zotero: null, x: null, y: null, children: [] },
      { id: "a/c", label: "C", noteUrl: null, zotero: null, x: null, y: null, children: [] },
    ],
  },
  { id: "d", label: "D", noteUrl: null, zotero: "zotero://select/library/items/K", x: 10, y: 20, children: [] },
];

test("autoLayout places a parent left of its children and centres it on them", () => {
  const positions = autoLayout(NODES, { xGap: 100, yGap: 50 });
  const a = positions.get("a");
  const b = positions.get("a/b");
  const c = positions.get("a/c");
  assert.ok(a && b && c);
  assert.equal(b.x, a.x + 100);
  assert.equal(c.x, a.x + 100);
  assert.equal(a.y, (b.y + c.y) / 2);
  assert.notEqual(b.y, c.y);
});

test("effectivePositions prefers stored, then authored, then automatic", () => {
  const stored = { d: { x: 900, y: 901 } };
  const positions = effectivePositions(NODES, stored, { xGap: 100, yGap: 50 });
  assert.deepEqual(positions.get("d"), { x: 900, y: 901 });       // stored wins
  const withoutStore = effectivePositions(NODES, {}, { xGap: 100, yGap: 50 });
  assert.deepEqual(withoutStore.get("d"), { x: 10, y: 20 });      // authored wins
  assert.ok(withoutStore.get("a/b"));                             // auto fills the rest
});

test("serializeTreeYaml freezes positions into a parseable authored block", () => {
  const positions = new Map([
    ["a", { x: 1, y: 2 }],
    ["a/b", { x: 3, y: 4 }],
    ["a/c", { x: 5, y: 6 }],
    ["d", { x: 7, y: 8 }],
  ]);
  const text = serializeTreeYaml(
    { root: "Research Knowledge", nodes: NODES },
    positions,
    "/knowledge/",
  );
  const parsed = parseYaml(text) as {
    root: string;
    nodes: Array<Record<string, unknown>>;
  };
  assert.equal(parsed.root, "Research Knowledge");
  assert.equal(parsed.nodes[0]?.label, "A");
  assert.equal(parsed.nodes[0]?.note, "A/index.qmd");     // noteUrl inverted
  assert.equal(parsed.nodes[0]?.x, 1);
  assert.equal(parsed.nodes[0]?.y, 2);
  const children = parsed.nodes[0]?.children as Array<Record<string, unknown>>;
  assert.equal(children[0]?.label, "B");
  assert.equal(children[0]?.note, undefined);             // grey stays absent
  assert.equal(children[0]?.x, 3);
  const d = parsed.nodes[1];
  assert.equal(d?.zotero, "zotero://select/library/items/K");
  assert.equal(d?.x, 7);                                  // frozen position wins
});

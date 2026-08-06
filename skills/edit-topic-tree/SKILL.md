---
name: edit-topic-tree
description: Use when editing the topic tree on the knowledge index — adding or moving nodes, changing a node's QMD note or Zotero link, or freezing a canvas layout the user dragged into shape.
---

# Edit Topic Tree

The topic tree is the draggable canvas rendered on the knowledge site's front
page. Its single source of truth is the ```` ```qlab-tree ```` YAML block in
`knowledge/index.qmd`; the build validates and compiles that block, and the
site renders it. Edit the block, never the generated site.

## Block schema

````markdown
```qlab-tree
root: Research Knowledge
nodes:
  - label: Tensor Networks          # required; unique among siblings; English
    note: TN_sim/index.qmd          # optional; must be an existing knowledge page
    zotero: zotero://select/library/collections/ABCD1234  # optional zotero:// link
    x: 120                          # optional canvas coordinates
    y: 80
    children:
      - label: MPS & DMRG
        note: TN_sim/MPS_DMRG.qmd
        zotero: zotero://open-pdf/library/items/ITEMKEY?page=4
```
````

A node without `note` renders with a grey "Open note" link; without `zotero`,
a grey "Open PDF in Zotero" link. Zotero link forms:

- Open a PDF at a page: `zotero://open-pdf/library/items/ITEMKEY?page=12`
- Group library: `zotero://open-pdf/groups/<groupID>/items/ITEMKEY?page=12`
- Select an item or collection: `zotero://select/library/items/ITEMKEY`,
  `zotero://select/library/collections/COLLECTIONKEY`

Collection keys for topics live in `literature/zotero.yml` (`collection_map`).

## Commands

| Task | Command |
|---|---|
| Validate the edited block | `make knowledge-check` |
| Preview the rendered tree | `make knowledge-preview` |

## Workflow

1. Read the current block in `knowledge/index.qmd`.
2. Apply the requested change: labels stay in English; `note` either points at
   an existing `knowledge/**/*.qmd` page or is omitted; `zotero` either starts
   with `zotero://` or is omitted.
3. To freeze a layout the user arranged on the canvas, replace the block body
   with the text from the canvas's "Copy layout YAML" button — it is the same
   schema with `x`/`y` filled in.
4. Run `make knowledge-check` after every edit. Diagnostics name the fence
   line: `TREE_NOTE_MISSING` (page does not exist), `TREE_LINK_SCHEME` (not a
   zotero:// link), `TREE_LABEL_INVALID`, `TREE_COORD_INVALID`,
   `TREE_YAML_INVALID`, `TREE_BLOCK_MISPLACED` (the block belongs on
   `knowledge/index.qmd` only).
5. Preview with `make knowledge-preview` when the user wants to see the tree.

The tree is a presentation layer. The `## Reading map` list remains the
navigation authority for the site and the graph; adding a tree node neither
publishes a page nor changes containment.

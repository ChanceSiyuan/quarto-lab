const TREE_DATA = /*__QLAB_TREE_DATA__*/ null;

/**
 * Topic tree canvas runtime.
 *
 * This file is served verbatim as `research-loop-tree.js`: the projection
 * replaces the placeholder above with the compiled tree JSON. It must stay
 * dependency-free and side-effect free without a DOM, because the node:test
 * suite imports the pure functions below straight from this module.
 */

const STORE_KEY = "qlab-tree-layout";
const DEFAULT_GAPS = { xGap: 200, yGap: 64 };

/** Depth-first walk over the compiled node forest. */
function walk(nodes, visit, depth = 0, parent = null) {
  for (const node of nodes) {
    visit(node, depth, parent);
    walk(node.children || [], visit, depth + 1, node);
  }
}

/**
 * Tidy tree layout: x from depth, leaves on a fixed vertical rhythm, every
 * parent centred on its children. Returns Map<id, {x, y}>.
 */
export function autoLayout(nodes, gaps = DEFAULT_GAPS) {
  const positions = new Map();
  let nextLeafSlot = 0;
  const place = (node, depth) => {
    const x = depth * gaps.xGap;
    const children = node.children || [];
    if (!children.length) {
      const y = nextLeafSlot * gaps.yGap;
      nextLeafSlot += 1;
      positions.set(node.id, { x, y });
      return y;
    }
    const centres = children.map((child) => place(child, depth + 1));
    const y = centres.reduce((sum, value) => sum + value, 0) / centres.length;
    positions.set(node.id, { x, y });
    return y;
  };
  for (const node of nodes) place(node, 0);
  return positions;
}

/**
 * Effective node positions: stored (a plain {id: {x, y}} object, typically
 * parsed from localStorage) beats authored x/y, which beats the automatic
 * layout. Returns Map<id, {x, y}>.
 */
export function effectivePositions(nodes, stored, gaps = DEFAULT_GAPS) {
  const positions = autoLayout(nodes, gaps);
  walk(nodes, (node) => {
    if (typeof node.x === "number" && typeof node.y === "number") {
      positions.set(node.id, { x: node.x, y: node.y });
    }
    const saved = stored ? stored[node.id] : undefined;
    if (saved && typeof saved.x === "number" && typeof saved.y === "number") {
      positions.set(node.id, { x: saved.x, y: saved.y });
    }
  });
  return positions;
}

/**
 * Regenerates the authored ```qlab-tree block body from the compiled tree,
 * freezing the given positions as x/y. noteUrl is inverted back to the
 * authored page path; absent links stay absent.
 */
export function serializeTreeYaml(tree, positions, sitePath) {
  const lines = [`root: ${quote(tree.root)}`, "nodes:"];
  const emit = (node, indent) => {
    const pad = " ".repeat(indent);
    lines.push(`${pad}- label: ${quote(node.label)}`);
    if (node.noteUrl) {
      const note = node.noteUrl.startsWith(sitePath)
        ? node.noteUrl.slice(sitePath.length).replace(/\.html$/u, ".qmd")
        : node.noteUrl;
      lines.push(`${pad}  note: ${note}`);
    }
    if (node.zotero) lines.push(`${pad}  zotero: ${node.zotero}`);
    const position = positions.get(node.id)
      || (typeof node.x === "number" && typeof node.y === "number"
        ? { x: node.x, y: node.y }
        : null);
    if (position) {
      lines.push(`${pad}  x: ${round(position.x)}`);
      lines.push(`${pad}  y: ${round(position.y)}`);
    }
    if (node.children && node.children.length) {
      lines.push(`${pad}  children:`);
      for (const child of node.children) emit(child, indent + 4);
    }
  };
  for (const node of tree.nodes) emit(node, 2);
  return `${lines.join("\n")}\n`;
}

function quote(text) {
  return JSON.stringify(String(text));
}

function round(value) {
  return Math.round(value * 100) / 100;
}

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * Builds the canvas in place of the hidden source block. `store` follows the
 * localStorage contract (getItem/setItem/removeItem); pass null to keep
 * positions in memory only.
 */
export function mountTopicTree(doc, data, store) {
  const anchor = findSourceBlock(doc);
  if (!anchor || !data || !Array.isArray(data.nodes) || !data.nodes.length) return null;

  const readStore = () => {
    try {
      const raw = store ? store.getItem(STORE_KEY) : null;
      return raw ? JSON.parse(raw) : {};
    }
    catch {
      return {};
    }
  };
  const writeStore = (value) => {
    try {
      if (store) store.setItem(STORE_KEY, JSON.stringify(value));
    }
    catch {
      /* storage may be unavailable; dragging still works for the session */
    }
  };

  const container = doc.createElement("div");
  container.className = "qlab-tree-canvas";
  anchor.insertAdjacentElement("beforebegin", container);

  const svg = doc.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "qlab-tree-svg");
  const world = doc.createElementNS(SVG_NS, "g");
  svg.appendChild(world);
  container.appendChild(svg);

  const card = doc.createElement("div");
  card.className = "qlab-tree-card";
  card.hidden = true;
  container.appendChild(card);

  const tools = doc.createElement("div");
  tools.className = "qlab-tree-tools";
  const copyButton = doc.createElement("button");
  copyButton.type = "button";
  copyButton.textContent = "Copy layout YAML";
  const resetButton = doc.createElement("button");
  resetButton.type = "button";
  resetButton.textContent = "Reset layout";
  tools.append(copyButton, resetButton);
  container.appendChild(tools);

  const overrides = readStore();
  let positions = effectivePositions(data.nodes, overrides);
  const view = { x: -40, y: -40, scale: 1 };
  let cardPinned = null;

  const applyView = () => {
    world.setAttribute(
      "transform",
      `translate(${-view.x * view.scale}, ${-view.y * view.scale}) scale(${view.scale})`,
    );
  };

  const flat = [];
  walk(data.nodes, (node, depth, parent) => flat.push({ node, parent }));

  const edges = new Map();
  const dots = new Map();
  const render = () => {
    while (world.firstChild) world.removeChild(world.firstChild);
    edges.clear();
    dots.clear();
    for (const { node, parent } of flat) {
      if (!parent) continue;
      const edge = doc.createElementNS(SVG_NS, "path");
      edge.setAttribute("class", "qlab-tree-edge");
      world.appendChild(edge);
      edges.set(node.id, { edge, parent });
    }
    for (const { node } of flat) {
      const group = doc.createElementNS(SVG_NS, "g");
      group.setAttribute("class", "qlab-tree-node");
      group.setAttribute("data-node-id", node.id);
      const dot = doc.createElementNS(SVG_NS, "circle");
      dot.setAttribute("r", "7");
      dot.setAttribute("class", node.noteUrl ? "qlab-tree-dot" : "qlab-tree-dot is-bare");
      const text = doc.createElementNS(SVG_NS, "text");
      text.setAttribute("dx", "12");
      text.setAttribute("dy", "4");
      text.textContent = node.label;
      group.append(dot, text);
      world.appendChild(group);
      dots.set(node.id, group);
      wireNode(group, node);
    }
    reposition();
  };

  const reposition = () => {
    for (const [id, group] of dots) {
      const position = positions.get(id);
      if (!position) continue;
      group.setAttribute("transform", `translate(${position.x}, ${position.y})`);
    }
    for (const [id, { edge, parent }] of edges) {
      const from = positions.get(parent.id);
      const to = positions.get(id);
      if (!from || !to) continue;
      const middle = (from.x + to.x) / 2;
      edge.setAttribute(
        "d",
        `M ${from.x} ${from.y} C ${middle} ${from.y}, ${middle} ${to.y}, ${to.x} ${to.y}`,
      );
    }
  };

  const showCard = (node) => {
    card.textContent = "";
    const title = doc.createElement("strong");
    title.textContent = node.label;
    const links = doc.createElement("div");
    links.append(
      cardLink(doc, "Open PDF in Zotero", node.zotero),
      cardLink(doc, "Open note", node.noteUrl),
    );
    card.append(title, links);
    const position = positions.get(node.id) || { x: 0, y: 0 };
    card.style.left = `${(position.x - view.x) * view.scale + 16}px`;
    card.style.top = `${(position.y - view.y) * view.scale + 16}px`;
    card.hidden = false;
  };

  const wireNode = (group, node) => {
    group.addEventListener("pointerenter", () => {
      if (!cardPinned) showCard(node);
    });
    group.addEventListener("pointerleave", () => {
      if (!cardPinned) card.hidden = true;
    });
    group.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
      const start = positions.get(node.id) || { x: 0, y: 0 };
      const origin = { x: event.clientX, y: event.clientY };
      let moved = false;
      const onMove = (moveEvent) => {
        const dx = (moveEvent.clientX - origin.x) / view.scale;
        const dy = (moveEvent.clientY - origin.y) / view.scale;
        if (!moved && Math.hypot(dx, dy) < 3) return;
        moved = true;
        positions.set(node.id, { x: start.x + dx, y: start.y + dy });
        reposition();
      };
      const onUp = () => {
        doc.removeEventListener("pointermove", onMove, true);
        doc.removeEventListener("pointerup", onUp, true);
        if (!moved) {
          // A plain tap toggles the pinned card (touch has no hover).
          cardPinned = cardPinned === node.id ? null : node.id;
          if (cardPinned) showCard(node);
          else card.hidden = true;
          return;
        }
        const next = readStore();
        next[node.id] = positions.get(node.id);
        writeStore(next);
      };
      doc.addEventListener("pointermove", onMove, true);
      doc.addEventListener("pointerup", onUp, true);
    });
  };

  svg.addEventListener("pointerdown", (event) => {
    const origin = { x: event.clientX, y: event.clientY };
    const startView = { x: view.x, y: view.y };
    const onMove = (moveEvent) => {
      view.x = startView.x - (moveEvent.clientX - origin.x) / view.scale;
      view.y = startView.y - (moveEvent.clientY - origin.y) / view.scale;
      applyView();
    };
    const onUp = () => {
      doc.removeEventListener("pointermove", onMove, true);
      doc.removeEventListener("pointerup", onUp, true);
    };
    doc.addEventListener("pointermove", onMove, true);
    doc.addEventListener("pointerup", onUp, true);
  });

  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
    view.scale = Math.min(2.5, Math.max(0.4, view.scale * factor));
    applyView();
  }, { passive: false });

  copyButton.addEventListener("click", () => {
    const yamlText = serializeTreeYaml(data, positions, data.sitePath || "/knowledge/");
    const clipboard = doc.defaultView && doc.defaultView.navigator
      ? doc.defaultView.navigator.clipboard
      : null;
    if (clipboard && clipboard.writeText) {
      clipboard.writeText(yamlText).then(
        () => flashLabel(copyButton, "Copied"),
        () => showFallback(doc, tools, yamlText),
      );
    }
    else {
      showFallback(doc, tools, yamlText);
    }
  });

  resetButton.addEventListener("click", () => {
    try {
      if (store) store.removeItem(STORE_KEY);
    }
    catch {
      /* nothing to clear */
    }
    positions = effectivePositions(data.nodes, {});
    reposition();
  });

  render();
  applyView();
  return container;
}

function cardLink(doc, label, href) {
  const link = doc.createElement("a");
  link.textContent = label;
  if (href) {
    link.href = href;
  }
  else {
    link.className = "is-disabled";
    link.setAttribute("aria-disabled", "true");
  }
  return link;
}

function flashLabel(button, text) {
  const original = button.textContent;
  button.textContent = text;
  setTimeout(() => {
    button.textContent = original;
  }, 1500);
}

function showFallback(doc, tools, yamlText) {
  let area = tools.parentElement.querySelector(".qlab-tree-fallback");
  if (!area) {
    area = doc.createElement("textarea");
    area.className = "qlab-tree-fallback";
    area.rows = 8;
    area.readOnly = true;
    tools.parentElement.appendChild(area);
  }
  area.value = yamlText;
  area.hidden = false;
  area.select();
}

function findSourceBlock(doc) {
  return (
    doc.querySelector("pre.qlab-tree")
    || doc.querySelector('pre[class*="qlab-tree"]')
    || doc.querySelector("code.qlab-tree")?.closest("pre")
    || null
  );
}

if (typeof document !== "undefined" && TREE_DATA) {
  const ready = () => {
    try {
      mountTopicTree(document, TREE_DATA, window.localStorage);
    }
    catch (error) {
      console.error("qlab-tree: failed to mount", error);
    }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready);
  else ready();
}

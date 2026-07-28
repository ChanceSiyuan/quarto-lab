from __future__ import annotations

import json


def render_eczoo_site(codes_doc: dict, relations_doc: dict) -> tuple[str, str, str]:
    state = {"codes": codes_doc["items"], "relations": relations_doc["items"],
             "generated_at": codes_doc["generated_at"]}
    state_json = json.dumps(state, sort_keys=True).replace("</", "<\\/")

    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>eczoo mirror</title>
    <link rel="stylesheet" href="assets/styles.css">
  </head>
  <body>
    <div class="layout">
      <aside class="sidebar">
        <h1>eczoo mirror</h1>
        <input id="search" class="filter" placeholder="filter codes...">
        <div id="code-list" class="code-list"></div>
      </aside>
      <main class="detail">
        <section class="panel">
          <h2 id="code-title">Select a code</h2>
          <p id="code-meta" class="summary"></p>
          <p id="code-desc"></p>
        </section>
        <section class="panel">
          <h3>Relations</h3>
          <div id="relations"></div>
        </section>
      </main>
    </div>
    <script src="assets/app.js"></script>
  </body>
</html>
"""

    js = "const EMBEDDED_STATE = " + state_json + """;
(function () {
  const state = EMBEDDED_STATE;
  const byId = {};
  state.codes.forEach(c => { byId[c.code_id] = c; });
  const list = document.getElementById("code-list");
  const search = document.getElementById("search");

  function rels(id) {
    return state.relations.filter(e => e.source === id);
  }
  function show(id) {
    const c = byId[id];
    if (!c) return;
    document.getElementById("code-title").textContent = c.name + " (" + c.code_id + ")";
    document.getElementById("code-meta").textContent = c.family_path.join(" / ");
    document.getElementById("code-desc").textContent = c.description_excerpt || "";
    const r = document.getElementById("relations");
    r.innerHTML = "";
    rels(id).forEach(e => {
      const div = document.createElement("div");
      const a = document.createElement("a");
      a.href = "#" + e.target;
      a.textContent = e.target;
      a.onclick = () => show(e.target);
      div.appendChild(document.createTextNode(e.type + ": "));
      div.appendChild(a);
      r.appendChild(div);
    });
  }
  function render(filter) {
    list.innerHTML = "";
    state.codes
      .filter(c => !filter || (c.code_id + " " + c.name).toLowerCase().includes(filter))
      .forEach(c => {
        const item = document.createElement("button");
        item.className = "code-list-item";
        item.textContent = c.code_id;
        item.onclick = () => show(c.code_id);
        list.appendChild(item);
      });
  }
  search.addEventListener("input", e => render(e.target.value.toLowerCase()));
  render("");
})();
"""

    css = """body { font-family: system-ui, sans-serif; margin: 0; }
.layout { display: flex; min-height: 100vh; }
.sidebar { width: 280px; border-right: 1px solid #ddd; padding: 1rem; overflow-y: auto; }
.detail { flex: 1; padding: 1rem 2rem; }
.filter { width: 100%; margin-bottom: 1rem; padding: 0.4rem; }
.code-list { display: flex; flex-direction: column; gap: 2px; }
.code-list-item { text-align: left; border: none; background: none; padding: 4px 6px; cursor: pointer; }
.code-list-item:hover { background: #f0f0f0; }
.panel { margin-bottom: 1.5rem; }
.summary { color: #666; }
"""
    return html, js, css

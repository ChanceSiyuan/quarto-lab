from __future__ import annotations

import json


def render_site_assets(app_state: dict) -> tuple[str, str, str]:
    app_state_json = json.dumps(app_state, sort_keys=True).replace("</", "<\\/")

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AutoQEC Zoo Browser</title>
    <link rel="stylesheet" href="assets/styles.css">
  </head>
  <body>
    <div class="layout">
      <aside class="sidebar">
        <h1>AutoQEC Zoo</h1>
        <label class="filter">
          <span>Family</span>
          <select id="family-filter"></select>
        </label>
        <div id="code-list" class="code-list"></div>
      </aside>
      <main class="detail">
        <section class="panel">
          <h2 id="code-title">Select a code</h2>
          <p id="code-summary" class="summary"></p>
        </section>
        <section class="panel">
          <h3>Canonical Facts</h3>
          <div id="canonical-facts"></div>
        </section>
        <section class="panel">
          <h3>Generated Instances</h3>
          <div id="generated-instances"></div>
        </section>
        <section class="panel">
          <h3>Paper-Specific Evidence</h3>
          <div id="paper-evidence"></div>
        </section>
      </main>
    </div>
    <script id="app-state" type="application/json">{app_state_json}</script>
    <script src="assets/app.js"></script>
  </body>
</html>
"""

    js = """const appState = JSON.parse(
  document.getElementById("app-state").textContent
);

const familyFilter = document.getElementById("family-filter");
const codeList = document.getElementById("code-list");
const codeTitle = document.getElementById("code-title");
const codeSummary = document.getElementById("code-summary");
const canonicalFacts = document.getElementById("canonical-facts");
const generatedInstances = document.getElementById("generated-instances");
const paperEvidence = document.getElementById("paper-evidence");

let selectedCodeId = appState.codes.length ? appState.codes[0].id : null;

function familyLabel(code) {
  return code.family_title || "Standalone";
}

function renderCanonicalFacts(code) {
  const sections = [
    ["Kind", code.kind],
    ["Family", familyLabel(code)],
    ["Aliases", code.aliases.length ? code.aliases.join(", ") : "None"],
    ["Construction", code.construction.description],
    [
      "Parameters",
      Object.entries(code.parameters)
        .map(([key, value]) => `${key}: ${value}`)
        .join("; "),
    ],
    [
      "Assumptions",
      code.assumptions.length ? code.assumptions.join("; ") : "None",
    ],
    [
      "Known Decoders",
      code.known_decoders.length ? code.known_decoders.join(", ") : "None",
    ],
    [
      "Distance Methods",
      code.distance_methods.length ? code.distance_methods.join(", ") : "None",
    ],
  ];

  canonicalFacts.innerHTML = "";
  const list = document.createElement("dl");
  list.className = "fact-list";
  sections.forEach(([label, value]) => {
    const term = document.createElement("dt");
    term.textContent = label;
    const desc = document.createElement("dd");
    desc.textContent = value;
    list.append(term, desc);
  });
  canonicalFacts.appendChild(list);
}

function renderEvidence(code) {
  paperEvidence.innerHTML = "";
  if (!code.evidence.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No evidence statements recorded.";
    paperEvidence.appendChild(empty);
    return;
  }

  code.evidence.forEach((item) => {
    const article = document.createElement("article");
    article.className = "evidence-item";

    const title = document.createElement("h4");
    title.textContent = item.title;
    article.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "evidence-meta";
    meta.textContent = `${item.paper_id} | ${item.claim_type}`;
    article.appendChild(meta);

    const statement = document.createElement("p");
    statement.textContent = item.statement;
    article.appendChild(statement);

    const context = [];
    if (item.decoder) context.push(`decoder: ${item.decoder}`);
    if (item.noise_model) context.push(`noise: ${item.noise_model}`);
    if (item.distance_method) context.push(`distance: ${item.distance_method}`);
    if (item.quote_ref) context.push(`quote: ${item.quote_ref}`);
    if (item.uncertainty_flags.length) {
      context.push(`flags: ${item.uncertainty_flags.join(", ")}`);
    }
    if (context.length) {
      const detail = document.createElement("p");
      detail.className = "evidence-context";
      detail.textContent = context.join(" | ");
      article.appendChild(detail);
    }

    paperEvidence.appendChild(article);
  });
}

function renderInstances(code) {
  generatedInstances.innerHTML = "";
  if (!code.instances.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No generated instances recorded.";
    generatedInstances.appendChild(empty);
    return;
  }

  const list = document.createElement("ul");
  list.className = "instance-list";
  code.instances.forEach((item) => {
    const row = document.createElement("li");

    const title = document.createElement("strong");
    title.textContent = item.id;
    row.appendChild(title);

    const meta = document.createElement("span");
    meta.className = "instance-meta";
    meta.textContent = `distance ${item.distance}, n=${item.n}, mx=${item.mx}, mz=${item.mz}`;
    row.appendChild(meta);

    list.appendChild(row);
  });
  generatedInstances.appendChild(list);
}

function renderDetail(code) {
  codeTitle.textContent = code.title;
  codeSummary.textContent = code.summary;
  renderCanonicalFacts(code);
  renderInstances(code);
  renderEvidence(code);
}

function filteredCodes() {
  const selectedFamily = familyFilter.value;
  if (!selectedFamily || selectedFamily === "all") {
    return appState.codes;
  }
  return appState.codes.filter((code) => code.family_id === selectedFamily);
}

function renderCodeList() {
  const visibleCodes = filteredCodes();
  if (!visibleCodes.some((code) => code.id === selectedCodeId)) {
    selectedCodeId = visibleCodes.length ? visibleCodes[0].id : null;
  }

  codeList.innerHTML = "";
  visibleCodes.forEach((code) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = code.id === selectedCodeId ? "code-item selected" : "code-item";
    button.addEventListener("click", () => {
      selectedCodeId = code.id;
      renderCodeList();
      renderDetail(code);
    });

    const title = document.createElement("strong");
    title.textContent = code.title;
    button.appendChild(title);

    const meta = document.createElement("span");
    meta.className = "code-meta";
    meta.textContent = `${familyLabel(code)} | ${code.evidence_count} evidence | ${code.instance_count} instances`;
    button.appendChild(meta);

    const summary = document.createElement("span");
    summary.className = "code-blurb";
    summary.textContent = code.summary;
    button.appendChild(summary);

    codeList.appendChild(button);
  });

  if (!visibleCodes.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No codes match this family filter.";
    codeList.appendChild(empty);
    codeTitle.textContent = "No matching code";
    codeSummary.textContent = "";
    canonicalFacts.innerHTML = "";
    generatedInstances.innerHTML = "";
    paperEvidence.innerHTML = "";
    return;
  }

  renderDetail(visibleCodes.find((code) => code.id === selectedCodeId) || visibleCodes[0]);
}

function renderFamilyOptions() {
  familyFilter.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = "All families";
  familyFilter.appendChild(allOption);

  appState.families.forEach((family) => {
    const option = document.createElement("option");
    option.value = family.id;
    option.textContent = family.title;
    familyFilter.appendChild(option);
  });
}

familyFilter.addEventListener("change", () => {
  renderCodeList();
});

renderFamilyOptions();
renderCodeList();
"""

    css = """:root {
  color-scheme: light;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: #f4f6fb;
  color: #162033;
}

.layout {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  min-height: 100vh;
}

.sidebar {
  padding: 1.5rem;
  border-right: 1px solid #d8dfeb;
  background: #ffffff;
}

.filter {
  display: grid;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.filter select {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid #bcc8dc;
  border-radius: 6px;
  background: #fff;
}

.code-list {
  display: grid;
  gap: 0.75rem;
}

.code-item {
  display: grid;
  gap: 0.3rem;
  width: 100%;
  padding: 0.9rem;
  text-align: left;
  border: 1px solid #d8dfeb;
  border-radius: 6px;
  background: #f9fbff;
  cursor: pointer;
}

.code-item.selected {
  border-color: #3657c8;
  background: #eef3ff;
}

.code-meta,
.code-blurb,
.summary,
.evidence-meta,
.evidence-context,
.instance-meta,
.empty {
  color: #4d5b78;
}

.detail {
  padding: 1.5rem;
  display: grid;
  gap: 1rem;
}

.panel {
  padding: 1rem 1.25rem;
  border: 1px solid #d8dfeb;
  border-radius: 6px;
  background: #ffffff;
}

.fact-list {
  display: grid;
  grid-template-columns: minmax(140px, 180px) minmax(0, 1fr);
  gap: 0.5rem 1rem;
  margin: 0;
}

.instance-list {
  display: grid;
  gap: 0.6rem;
  margin: 0;
  padding-left: 1.25rem;
}

.instance-list li {
  padding-left: 0.25rem;
}

.instance-list strong {
  margin-right: 0.5rem;
}

.fact-list dt {
  font-weight: 600;
}

.fact-list dd {
  margin: 0;
}

.evidence-item + .evidence-item {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e3e8f2;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #d8dfeb;
  }

  .fact-list {
    grid-template-columns: 1fr;
  }
}
"""

    return html, js, css

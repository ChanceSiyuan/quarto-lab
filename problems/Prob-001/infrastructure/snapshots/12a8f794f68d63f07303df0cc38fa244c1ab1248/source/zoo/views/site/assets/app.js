const appState = JSON.parse(
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

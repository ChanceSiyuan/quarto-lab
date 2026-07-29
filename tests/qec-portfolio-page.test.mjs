import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const pagePath = new URL("../app/qec-portfolio/page.tsx", import.meta.url);
const panelPath = new URL("../app/qec-portfolio/portfolio-panel.tsx", import.meta.url);
const cssPath = new URL("../app/qec-portfolio/portfolio-panel.module.css", import.meta.url);

test("QEC portfolio page spells out V, A, and S and contains no visible Chinese", async () => {
  const source = await readFile(panelPath, "utf8");
  assert.match(source, /Research Value \(V\)/);
  assert.match(source, /Autoresearch Fit \(A\)/);
  assert.match(source, /Combined Priority \(S\)/);
  assert.match(source, /External-evidence-backed advisory comparison/);
  assert.doesNotMatch(source, /\p{Script=Han}/u);
});

test("QEC portfolio route owns its styles without importing preserved global surfaces", async () => {
  const [page, panel, css] = await Promise.all([
    readFile(pagePath, "utf8"),
    readFile(panelPath, "utf8"),
    readFile(cssPath, "utf8"),
  ]);
  assert.match(page, /QEC Problem Portfolio/);
  assert.match(panel, /portfolio-panel\.module\.css/);
  assert.match(css, /@media \(max-width: 760px\)/);
  assert.doesNotMatch(`${page}\n${panel}`, /app\/globals\.css|app\/page\.tsx|app\/layout\.tsx/);
});

test("portfolio panel fetches only the read-only endpoint and renders unknown reasons", async () => {
  const source = await readFile(panelPath, "utf8");
  assert.match(source, /\/__local\/assessments\/portfolio/);
  assert.match(source, /cache: "no-store"/);
  assert.match(source, /Unknown —/);
  assert.match(source, /Open problem/);
  assert.match(source, /Open detailed report/);
  assert.doesNotMatch(source, /\/valuation\/jobs|\/assessment\/jobs/);
});

test("portfolio panel reports Verdict's ascending order to assistive technology", async () => {
  const source = await readFile(panelPath, "utf8");
  assert.match(source, /key === "verdict" \? "ascending" : "descending"/);
});

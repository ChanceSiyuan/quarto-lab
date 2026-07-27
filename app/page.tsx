"use client";

import { useEffect, useMemo, useState } from "react";

const stages = [
  {
    key: "discover",
    number: "01",
    name: "Discover",
    detail: "Mine gaps in the literature",
  },
  {
    key: "verify",
    number: "02",
    name: "Verify",
    detail: "Freeze an executable gate",
  },
  {
    key: "solve",
    number: "03",
    name: "Solve",
    detail: "Run agents and learn",
  },
  {
    key: "publish",
    number: "04",
    name: "Publish",
    detail: "Prepare external review",
  },
];

const actions = [
  "Run novelty check",
  "Launch solver run",
  "Prepare review packet",
  "Archive completed run",
];

const activityByStage = [
  "Candidate generated from 18 source papers",
  "Novelty check passed against the challenge catalog",
  "Solver run started with the current heuristics library",
  "Review packet assembled for external submission",
];

const initialActivity = [
  { time: "12:42", text: "Executable interval-arithmetic gate created" },
  { time: "12:31", text: "Candidate accepted by automatic quality rubric" },
  { time: "12:18", text: "Literature mining completed across 18 papers" },
];

export default function Home() {
  const [stage, setStage] = useState(1);
  const [activity, setActivity] = useState(initialActivity);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const saved = window.localStorage.getItem("research-loop-demo");
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as {
          stage?: number;
          activity?: typeof initialActivity;
        };
        if (typeof parsed.stage === "number") setStage(parsed.stage);
        if (Array.isArray(parsed.activity)) setActivity(parsed.activity);
      } catch {
        window.localStorage.removeItem("research-loop-demo");
      }
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    window.localStorage.setItem(
      "research-loop-demo",
      JSON.stringify({ stage, activity }),
    );
  }, [stage, activity, ready]);

  const progress = useMemo(() => ((stage + 1) / stages.length) * 100, [stage]);

  function advanceRun() {
    const now = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    setActivity((items) => [
      { time: now, text: activityByStage[stage] },
      ...items,
    ]);
    setStage((current) => (current + 1) % stages.length);
  }

  function resetDemo() {
    setStage(1);
    setActivity(initialActivity);
  }

  return (
    <main>
      <nav className="topbar" aria-label="Primary navigation">
        <a className="brand" href="#top" aria-label="Research Loop home">
          <span className="brand-mark">RL</span>
          <span>Research Loop</span>
        </a>
        <div className="team-label">by Automata</div>
        <div className="top-actions">
          <a href="#activity" className="text-link">Activity</a>
          <span className="system-status"><i /> System ready</span>
        </div>
      </nav>

      <section className="hero" id="top">
        <div>
          <p className="eyebrow">AUTONOMOUS RESEARCH CONTROL</p>
          <h1>Turn open literature into<br />verifiable research.</h1>
          <p className="hero-copy">
            One auditable loop to discover meaningful problems, freeze their
            success criteria, solve them, and prepare the results for review.
          </p>
        </div>
        <div className="run-score" aria-label="Challenge progress">
          <span className="score-number">1<span>/5</span></span>
          <p>problems in the<br />publication pipeline</p>
        </div>
      </section>

      <section className="pipeline" aria-labelledby="pipeline-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ACTIVE RUN · RL-001</p>
            <h2 id="pipeline-heading">Research pipeline</h2>
          </div>
          <div className="progress-label">{Math.round(progress)}% complete</div>
        </div>
        <div className="progress-track" aria-hidden="true">
          <span style={{ width: `${progress}%` }} />
        </div>

        <div className="stage-grid">
          {stages.map((item, index) => {
            const status = index < stage ? "complete" : index === stage ? "active" : "pending";
            return (
              <article className={`stage-card ${status}`} key={item.key}>
                <div className="stage-topline">
                  <span>{item.number}</span>
                  <span className="stage-state">
                    {status === "complete" ? "Complete" : status === "active" ? "In progress" : "Queued"}
                  </span>
                </div>
                <h3>{item.name}</h3>
                <p>{item.detail}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="workbench">
        <article className="candidate-card">
          <div className="card-label-row">
            <p className="eyebrow">CURRENT CANDIDATE</p>
            <span className="candidate-id">QMB-001</span>
          </div>
          <h2>Certified timestep bounds for 1D lattice dynamics</h2>
          <p className="candidate-summary">
            Find a tighter, machine-checkable error bound for product-formula
            simulation of local Hamiltonians on fresh benchmark instances.
          </p>
          <div className="checks" aria-label="Candidate checks">
            <div><span className="check done">✓</span><p><b>Provenance traced</b><small>18 papers and 3 benchmark tables</small></p></div>
            <div><span className="check done">✓</span><p><b>Gate executable</b><small>Interval arithmetic · deterministic</small></p></div>
            <div><span className={`check ${stage > 1 ? "done" : "waiting"}`}>{stage > 1 ? "✓" : "·"}</span><p><b>Novelty confirmed</b><small>{stage > 1 ? "Catalog comparison passed" : "Awaiting catalog comparison"}</small></p></div>
          </div>
        </article>

        <aside className="command-card">
          <p className="eyebrow">NEXT ACTION</p>
          <div className="command-index">{String(stage + 1).padStart(2, "0")}</div>
          <h2>{actions[stage]}</h2>
          <p>
            Advance this candidate to the next checkpoint. The action and its
            result will be added to the audit log.
          </p>
          <button type="button" onClick={advanceRun}>
            {actions[stage]} <span aria-hidden="true">→</span>
          </button>
          <button type="button" className="reset-button" onClick={resetDemo}>
            Reset demo
          </button>
        </aside>
      </section>

      <section className="activity-section" id="activity">
        <div className="section-heading">
          <div>
            <p className="eyebrow">AUDIT TRAIL</p>
            <h2>Recent activity</h2>
          </div>
          <span className="local-note">Saved on this device</span>
        </div>
        <div className="activity-list">
          {activity.slice(0, 5).map((item, index) => (
            <div className="activity-item" key={`${item.time}-${item.text}-${index}`}>
              <span>{item.time}</span>
              <p>{item.text}</p>
              <span className="activity-run">RL-001</span>
            </div>
          ))}
        </div>
      </section>

      <footer>
        <span>Research Loop · Automata</span>
        <span>Prototype 0.1</span>
      </footer>
    </main>
  );
}

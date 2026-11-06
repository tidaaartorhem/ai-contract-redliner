import { useState } from "react";
import { useRedlineDeskData } from "./data";
import QueueView from "./views/QueueView";
import PlaybookView from "./views/PlaybookView";
import PasteView from "./views/PasteView";
import MethodologyView from "./views/MethodologyView";
import "./styles.css";

const REPO_URL = "https://github.com/tidaaartorhem/ai-contract-redliner";
const LIVE_URL = "https://ai-contract-redliner.web.app";

type Tab = "queue" | "playbook" | "paste" | "methodology";

const TABS: { id: Tab; label: string }[] = [
  { id: "queue", label: "Review queue" },
  { id: "playbook", label: "Playbook" },
  { id: "paste", label: "Paste a clause" },
  { id: "methodology", label: "Methodology" },
];

export default function App() {
  const { data, error } = useRedlineDeskData();
  const [tab, setTab] = useState<Tab>("queue");

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>
            <span className="mark">Rd</span>RedlineDesk
          </h1>
          <p className="sub">
            The contract first-pass desk: 50 real CUAD contracts, each clause scored against
            Harbourline Analytics&rsquo; 12-rule playbook with disclosed thresholds — and a human
            gate on every redline draft. Nothing is sent or signed without approval.
          </p>
          <div className="badges">
            <span className="badge neutral">
              <a href={REPO_URL} target="_blank" rel="noreferrer">
                GitHub repo
              </a>
            </span>
            <span className="badge neutral">
              <a href={LIVE_URL} target="_blank" rel="noreferrer">
                Live site
              </a>
            </span>
          </div>
        </div>
      </header>

      <div className="disclosure banner">
        <b>Deterministic, no LLM.</b> Each clause: tier ACCEPT / FLAG / REJECT from a 0–100 risk
        score (base + adjustment, capped at 100). Contract route: any REJECT clause or score ≥80
        ESCALATE · any FLAG clause or score ≥40 SEND_TO_LEGAL · otherwise APPROVE. The in-browser
        assessor mirrors the Python pipeline exactly.
      </div>

      {error && <div className="card error">Failed to load data: {error}</div>}
      {!data && !error && <div className="card">Loading…</div>}

      {data && (
        <>
          <div className="stat-row">
            {(
              [
                ["APPROVE", "ok", data.summary.findings.routes.APPROVE ?? 0],
                ["SEND_TO_LEGAL", "warn", data.summary.findings.routes.SEND_TO_LEGAL ?? 0],
                ["ESCALATE", "bad", data.summary.findings.routes.ESCALATE ?? 0],
              ] as const
            ).map(([label, cls, n]) => (
              <div className="card stat" key={label}>
                <div className="stat-num">{n}</div>
                <div className={`pill ${cls}`}>{label.replace("_", " ")}</div>
              </div>
            ))}
            <div className="card stat">
              <div className="stat-num">{data.summary.findings.uncapped_liability_pct}%</div>
              <div className="muted small">
                contracts with an uncapped-liability clause ({data.summary.findings.uncapped_liability_contracts} of{" "}
                {data.summary.findings.contract_count})
              </div>
            </div>
            <div className="card stat">
              <div className="stat-num">{data.summary.findings.effort_hours}h</div>
              <div className="muted small">estimated review effort</div>
            </div>
            <div className="card stat">
              <div className="stat-num">{Math.round(data.summary.eval.tier_accuracy * 100)}%</div>
              <div className="muted small">
                tier accuracy ({data.summary.eval.n}-pair golden set, calibration)
              </div>
            </div>
          </div>

          <div className="tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={tab === t.id ? "active" : ""}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === "queue" && <QueueView data={data} />}
          {tab === "playbook" && <PlaybookView data={data} />}
          {tab === "paste" && <PasteView data={data} />}
          {tab === "methodology" && <MethodologyView data={data} />}

          <footer className="footer muted small">
            {data.summary.data_note} Built{" "}
            {data.stamp ? `from ${data.stamp.git_sha} at ${data.stamp.built_utc}` : "locally"} ·
            no LLMs were used.
          </footer>
        </>
      )}
    </div>
  );
}

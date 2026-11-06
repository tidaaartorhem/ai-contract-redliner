import { useState } from "react";
import type { ClauseAssessment, ContractRow, Route, Tier } from "../types";

const ROUTE_CLASS: Record<Route, string> = {
  APPROVE: "ok",
  SEND_TO_LEGAL: "warn",
  ESCALATE: "bad",
};

const TIER_CLASS: Record<Tier, string> = {
  ACCEPT: "ok",
  FLAG: "warn",
  REJECT: "bad",
};

export function RouteBadge({ route }: { route: Route }) {
  return <span className={`pill ${ROUTE_CLASS[route]}`}>{route.replace("_", " ")}</span>;
}

export function TierBadge({ tier }: { tier: Tier }) {
  return <span className={`pill ${TIER_CLASS[tier]}`}>{tier}</span>;
}

export function ScoreBar({ value }: { value: number }) {
  const cls = value >= 85 ? "bad" : value >= 40 ? "warn" : "ok";
  return (
    <span className="confbar" title={`${value}`}>
      <span className="confbar-track">
        <span className={`confbar-fill ${cls}`} style={{ width: `${Math.min(100, value)}%` }} />
      </span>
      <span className="confbar-num">{value}</span>
    </span>
  );
}

function ClauseSpan({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const shown = open || text.length <= 400 ? text : text.slice(0, 400) + "…";
  return (
    <div className="clause-span">
      <span className="mono small">{shown}</span>
      {text.length > 400 && (
        <button className="linklike" onClick={() => setOpen(!open)}>
          {open ? "show less" : "show full clause"}
        </button>
      )}
    </div>
  );
}

function ClauseRow({ c }: { c: ClauseAssessment }) {
  return (
    <div className="clause-row">
      <div className="clause-head">
        <b>{c.title}</b>
        <TierBadge tier={c.tier} />
        <ScoreBar value={c.score} />
        {!c.present && <span className="pill neutral">not in contract</span>}
      </div>
      <div className="muted small">
        Score {c.score} = base {c.score_parts.base} + adjustment {c.score_parts.adjustment}.{" "}
        {c.evidence.join(" ")}
      </div>
      {c.spans.map((s, i) => (
        <ClauseSpan key={i} text={s} />
      ))}
      {c.tier !== "ACCEPT" && (
        <div className="redline-box">
          <div>
            <b>Suggested redline:</b> {c.redline}
          </div>
          <div className="muted">
            <b>Fallback:</b> {c.fallback}
          </div>
        </div>
      )}
    </div>
  );
}

export function ContractCard({ c }: { c: ContractRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="card match-card">
      <div className="match-head">
        <span className="req-id">{c.contract_id}</span>
        <RouteBadge route={c.route} />
        <ScoreBar value={c.overall_score} />
        <span className="pill neutral">
          {c.flag_count} flag{c.flag_count === 1 ? "" : "s"}
          {c.reject_count > 0 ? ` · ${c.reject_count} reject` : ""}
        </span>
        <span className="pill gate">human gate required</span>
      </div>
      <p className="req-text">
        <b>{c.document_name ?? c.title}</b>
      </p>
      <div className="muted small" style={{ marginBottom: 8 }}>
        {c.parties ?? c.title}
        {c.agreement_date ? ` · dated ${c.agreement_date}` : ""}
      </div>
      <div className="action-line">
        <b>Recommended action:</b> {c.action}
      </div>
      <button className="btn" style={{ marginTop: 10 }} onClick={() => setOpen(!open)}>
        {open ? "Hide clause review" : `Show clause review (${c.clauses.length} rules)`}
      </button>
      {open && (
        <div style={{ marginTop: 12 }}>
          {c.clauses.map((cl) => (
            <ClauseRow key={cl.rule_id} c={cl} />
          ))}
          {c.redline_draft.length > 0 && (
            <div className="card" style={{ marginTop: 12, background: "#fbfcfe" }}>
              <h3 style={{ marginTop: 0 }}>Redline draft — pending human approval</h3>
              <p className="muted small">
                Nothing here is sent or final. A person reviews each redline, edits as needed, and
                approves before anything goes to the counterparty or Legal.
              </p>
              <ol className="answer-text" style={{ paddingLeft: 20 }}>
                {c.redline_draft.map((d) => (
                  <li key={d.rule_id} style={{ marginBottom: 8 }}>
                    <b>{d.title}</b> — {d.redline}
                    <div className="muted">Fallback: {d.fallback}</div>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

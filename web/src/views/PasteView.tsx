import { useMemo, useState } from "react";
import { assessClause, routeForClause } from "../rules";
import type { RedlineDeskData } from "../types";
import { RouteBadge, ScoreBar, TierBadge } from "./shared";

/** Paste-a-clause: runs the same assess + route in the browser (TS mirror). */
export default function PasteView({ data }: { data: RedlineDeskData }) {
  const [ruleId, setRuleId] = useState("LIABILITY_CAP");
  const [text, setText] = useState("");
  const [noticeText, setNoticeText] = useState("");
  const [hasException, setHasException] = useState(false);
  const [ran, setRan] = useState(false);

  const cfg = data.summary.config;
  const rule = data.playbook.rules.find((r) => r.id === ruleId)!;

  const assessment = useMemo(() => {
    if (!ran || !text.trim()) return null;
    const spans = [text.trim()];
    const notice = ruleId === "AUTO_RENEWAL" && noticeText.trim() ? [noticeText.trim()] : [];
    return assessClause(ruleId, spans, cfg.thresholds, hasException, notice);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ran, ruleId, text, noticeText, hasException]);
  const route = assessment ? routeForClause(assessment) : null;

  const runAssess = () => {
    if (!text.trim()) return;
    setRan(true);
  };

  return (
    <div>
      <div className="card">
        <h2>Paste a clause</h2>
        <p className="muted">
          Pick the clause category, paste the clause text, and the in-browser engine — the exact
          TypeScript mirror of the Python pipeline, verified against {data.vectors.vectors.length}{" "}
          shared test vectors — scores it against Harbourline&rsquo;s playbook and predicts the
          route. For auto-renewal, paste the renewal term below and the opt-out notice period in
          the second box; for non-compete, tick the box if the contract states carve-outs.
        </p>
        <div className="paste-form">
          <label>
            Clause category
            <select value={ruleId} onChange={(e) => { setRuleId(e.target.value); setRan(false); }}>
              {data.playbook.rules.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title} — {r.stance}
                </option>
              ))}
            </select>
          </label>
          <label>
            Clause text
            <textarea
              className="paste"
              rows={5}
              placeholder="e.g. Either party's total liability shall be limited to the amounts paid or payable during the twelve-month period preceding the claim."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          {ruleId === "AUTO_RENEWAL" && (
            <label>
              Opt-out notice period (the Notice Period To Terminate Renewal clause, if any)
              <textarea
                className="paste"
                rows={2}
                placeholder="e.g. …unless one party provides prior written notice of non-renewal at least sixty (60) days prior to expiration."
                value={noticeText}
                onChange={(e) => setNoticeText(e.target.value)}
              />
            </label>
          )}
          {ruleId === "NON_COMPETE" && (
            <label className="check">
              <input type="checkbox" checked={hasException} onChange={(e) => setHasException(e.target.checked)} />
              This contract states non-compete carve-outs / exceptions
            </label>
          )}
          <div>
            <button className="btn primary" onClick={runAssess}>
              Assess it
            </button>
          </div>
        </div>
      </div>

      {ran && assessment && route && (
        <div className="card match-card">
          <div className="match-head">
            <RouteBadge route={route} />
            <TierBadge tier={assessment.tier} />
            <span className="pill neutral">{rule.title}</span>
            <span className="pill gate">human gate required</span>
          </div>
          <div className="match-body">
            <ScoreBar value={assessment.score} />
            <div className="match-detail">
              <div>
                Score {assessment.score} = base {assessment.score_parts.base} + adjustment{" "}
                {assessment.score_parts.adjustment}. {assessment.evidence.join(" ")}
              </div>
              {assessment.tier !== "ACCEPT" ? (
                <div className="redline-box">
                  <div>
                    <b>Suggested redline:</b> {rule.redline}
                  </div>
                  <div className="muted">
                    <b>Fallback:</b> {rule.fallback}
                  </div>
                </div>
              ) : (
                <p className="answer-text">
                  This clause passes the playbook as written. A full contract route still needs
                  all 12 rules checked — one clean clause does not clear a contract.
                </p>
              )}
              <div className="action-line">
                <b>Recommended action:</b>{" "}
                {route === "ESCALATE"
                  ? "Escalate to Legal immediately — a REJECT-tier clause means this draft must not be signed."
                  : route === "SEND_TO_LEGAL"
                    ? "Send the redline draft to Legal with this clause; do not sign until Legal clears it."
                    : "No redline needed for this clause."}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import type { RedlineDeskData } from "../types";

/** The playbook: Harbourline's 12 seeded rules, with per-rule flag rates from the run. */
export default function PlaybookView({ data }: { data: RedlineDeskData }) {
  const table = data.summary.findings.rule_table;
  return (
    <div>
      <div className="card">
        <h2>The playbook</h2>
        <p className="muted">
          Harbourline Analytics Inc.&rsquo;s contract positions — seeded demo data, disclosed as
          such. Each rule reads one CUAD clause category (two for auto-renewal) and scores it
          against a concrete threshold: a 12-month liability cap, 30 days&rsquo; termination
          notice, Ontario governing law, and so on. Flag rate is measured on this 50-contract
          run.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Stance</th>
              <th>Present</th>
              <th>Accept</th>
              <th>Flag</th>
              <th>Reject</th>
              <th>Flag rate</th>
            </tr>
          </thead>
          <tbody>
            {data.playbook.rules.map((r) => {
              const row = table[r.id];
              return (
                <tr key={r.id}>
                  <td>
                    <b>{r.title}</b>
                    <div className="muted small">CUAD: {r.cuad_category}</div>
                  </td>
                  <td>{r.stance}</td>
                  <td>
                    {row.present} ({row.present_pct}%)
                  </td>
                  <td>{row.accept}</td>
                  <td>{row.flag}</td>
                  <td>{row.reject}</td>
                  <td>{row.flag_rate}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {data.playbook.rules.map((r) => (
        <div className="card" key={r.id}>
          <div className="match-head">
            <b>{r.title}</b>
            <span className="pill neutral">{r.cuad_category}</span>
          </div>
          <p>
            <b>Suggested redline:</b> {r.redline}
          </p>
          <p className="muted">
            <b>Fallback:</b> {r.fallback}
          </p>
        </div>
      ))}
    </div>
  );
}

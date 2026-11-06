import type { RedlineDeskData } from "../types";

/** Methodology: disclosed weights, thresholds, data provenance, caveats. */
export default function MethodologyView({ data }: { data: RedlineDeskData }) {
  const f = data.summary.findings;
  const cfg = data.summary.config;
  const ev = data.summary.eval;
  return (
    <div>
      <div className="card">
        <h2>Methodology</h2>
        <p className="muted">
          Everything on this page is disclosed: how each clause is scored, where the contracts
          came from, and what the numbers do and do not prove.
        </p>
        <h3>How a clause is scored</h3>
        <p>
          Each of the 12 playbook rules reads the CUAD expert-labeled spans for its clause
          category and applies threshold tests with disclosed numbers. Score = base + adjustment,
          capped at 100. Tier: score ≥ {cfg.thresholds.reject_bar} REJECT · ≥{" "}
          {cfg.thresholds.flag_bar} FLAG · otherwise ACCEPT.
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Rule</th>
              <th>What the parser looks for</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Liability cap</td><td>months of fees (number words normalized: &ldquo;twelve-month&rdquo; → 12)</td><td>≥12mo → 10 · &lt;12mo → 55 + (12 − months) × 3 · amount-only → 60 · no number → 65</td></tr>
            <tr><td>Uncapped liability</td><td>carve-out from a stated cap vs exclusion vs &ldquo;unlimited&rdquo;</td><td>carve-out → 55 · exclusion → 45 · unlimited → 90</td></tr>
            <tr><td>Termination for convenience</td><td>notice days (months × 30)</td><td>≥30d → 10 · &lt;30d → 55 + (30 − days) · no period → 60</td></tr>
            <tr><td>Governing law</td><td>jurisdiction named in the clause</td><td>Ontario → 10 · other Canada → 55 · US state / other country → 80</td></tr>
            <tr><td>IP assignment</td><td>&ldquo;assign&rdquo; / &ldquo;become property&rdquo; vs licence-back only</td><td>assignment → 65 · licence-back → 45</td></tr>
            <tr><td>Audit rights</td><td>presence / absence</td><td>present → 10 · absent → 55</td></tr>
            <tr><td>Non-compete</td><td>presence; mitigated by stated carve-outs</td><td>no carve-out → 70 · carve-outs → 15</td></tr>
            <tr><td>No-solicit (employees)</td><td>presence</td><td>present → 60</td></tr>
            <tr><td>Most-favoured-nation</td><td>presence</td><td>present → 90</td></tr>
            <tr><td>Change of control</td><td>&ldquo;terminate&rdquo; vs consent / notice rights</td><td>termination → 70 · consent → 60</td></tr>
            <tr><td>Auto-renewal</td><td>renewal term (months) and opt-out notice (days), parsed separately</td><td>term &gt;12mo → 55 + (term − 12) × 2 · notice &gt;60d → 55 + (notice − 60) ÷ 5 · within limits → 10</td></tr>
            <tr><td>Anti-assignment</td><td>&ldquo;freely assign&rdquo; / &ldquo;may assign … without consent&rdquo; vs consent required</td><td>free → 15 · consent required → 60</td></tr>
          </tbody>
        </table>
        <h3>How a contract is routed</h3>
        <p>
          Overall score = 0.7 × worst clause + 0.3 × mean clause. Route: any REJECT clause or
          score ≥ {cfg.route_bars.escalate_score} → ESCALATE · any FLAG clause or score ≥{" "}
          {cfg.route_bars.legal_score} → SEND_TO_LEGAL · otherwise APPROVE. Review effort:{" "}
          {cfg.effort_minutes.APPROVE} min (APPROVE) · {cfg.effort_minutes.SEND_TO_LEGAL} min
          (SEND_TO_LEGAL) · {cfg.effort_minutes.ESCALATE} min (ESCALATE).
        </p>
        <h3>Golden-set evaluation</h3>
        <p>
          {ev.n} hand-labeled (contract, rule) pairs, read from the actual CUAD spans: tier
          accuracy {Math.round(ev.tier_accuracy * 100)}%, precision{" "}
          {Math.round(ev.precision * 100)}%, recall {Math.round(ev.recall * 100)}%. Thresholds
          were grid-searched on this same set, so these are calibration numbers, not held-out
          test results — the README says so. {data.summary.eval_misses.length === 0
            ? "No misses on the golden set."
            : `${data.summary.eval_misses.length} misses, listed in the repo README.`}
        </p>
        <h3>Data provenance</h3>
        <p>
          Contracts: {data.summary.queue_meta.source}, {data.summary.queue_meta.license}.{" "}
          {data.summary.queue_meta.citation} Slice: {data.summary.queue_meta.slice}.{" "}
          {data.summary.queue_meta.clause_note} The playbook is seeded demo data for the
          fictional {data.summary.company.name}; the company profile is fictional.
        </p>
        <h3>Caveats, kept honest</h3>
        <ul className="answer-text">
          <li>
            CUAD contracts are US SEC filings, so the Ontario-law playbook flags governing law on{" "}
            {f.non_ontario_governing_law_contracts} of {f.contract_count} contracts and APPROVE
            is 0. That is the corpus, not a bug — it is also why the queue is a redline desk, not
            an approval desk.
          </li>
          <li>
            CUAD labels are noisy: some &ldquo;Uncapped Liability&rdquo; spans are actually
            consequential-damages exclusions, and some spans are redacted ([**]). The assessor
            scores what the text says, and the evidence line shows what it found.
          </li>
          <li>
            The parser reads the first number it finds per unit. A clause that states two
            different periods (e.g. a 1-year term &ldquo;for up to another ten years&rdquo;) is
            scored on the first — the evidence line shows the number used.
          </li>
          <li>
            Presence-based rules (MFN, non-compete, no-solicit) cannot tell which party the
            restriction binds; the redline draft assumes Harbourline is the restricted party and
            Legal should confirm direction before sending.
          </li>
          <li>
            Zero LLM calls. The Python pipeline and the in-browser TypeScript mirror agree on all{" "}
            {data.vectors.vectors.length} shared test vectors.
          </li>
        </ul>
      </div>
    </div>
  );
}

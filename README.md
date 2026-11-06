# RedlineDesk — the contract first-pass redliner

Every company signs contracts it has not really read. A vendor's draft
arrives, someone skims it, Legal sees it only when something has already
gone wrong — and the risky clauses are the quiet ones: an uncapped
liability carve-out, a liability cap of three months' fees, a governing-law
clause pointing at Delaware when the company sits in Ontario, an
auto-renewal that rolls for ten years unless someone remembers to opt out.

RedlineDesk is the first-pass desk for that workflow. It takes a morning's
inbox of contracts — 50 real commercial agreements from CUAD, each with
expert-labeled clause spans — scores every clause against the company's
12-rule playbook with disclosed deterministic thresholds, and routes each
contract to exactly one action:

- **APPROVE** — every playbook rule passed: file it as-is
- **SEND_TO_LEGAL** — at least one clause needs a redline: the draft goes to Legal with the flagged clauses
- **ESCALATE** — a REJECT-tier clause (or an 80+ risk score): do not sign

Every redline is a human-gated draft. Nothing is sent or marked final
automatically, and nothing is ever invented: below the bar, the product says
so and hands the contract to a person.

## The queue (real data)

50 real commercial contracts from CUAD (Contract Understanding Atticus
Dataset, Hendrycks et al., NeurIPS 2021; CC BY 4.0), a deterministic strided
sample — every 10th of the 510 contracts in the dataset. Each contract
carries expert-labeled clause spans in 41 categories; RedlineDesk keeps the
488 spans in the 14 categories its playbook covers (470 assessed against the
12 rules, 18 Competitive Restriction Exception spans used as mitigation
context for Non-Compete). Citation: Hendrycks, Burns, Chen, Ball. *CUAD: An
Expert-Annotated NLP Dataset for Legal Contract Review*. NeurIPS 2021.
arXiv:2103.06268.

Queue truth, measured from the data itself:

| | |
|---|---|
| Contracts | 50 |
| Clause spans kept | 488 (470 assessed + 18 exception context) |
| Most-flagged rule | Governing law — 44 of 50 (88.0%) |
| Mean overall risk score | 61.9 / 100 |
| Contracts with an uncapped-liability clause | 9 (18.0%) |
| Contracts with no audit rights | 23 |
| Contracts with a low or unquantified liability cap | 28 |

## How it runs

A deterministic LangGraph `StateGraph` — `intake → extract_clauses →
match_playbook → score_risk → draft_redline → gate` — over the queue, with
zero LLM calls:

1. **intake** loads the 50 contracts and the 12-rule playbook.
2. **extract_clauses** groups each contract's expert-labeled spans by
   playbook rule (Renewal Term + Notice Period feed one auto-renewal rule;
   Competitive Restriction Exception is kept as mitigation context).
3. **match_playbook** assesses every rule against its spans: tier, 0–100
   risk score with disclosed parts, evidence, suggested redline, fallback.
4. **score_risk** computes the per-contract overall score (0.7 × worst
   clause + 0.3 × mean clause) and routes it per the decision table below.
5. **draft_redline** writes one recommended action per contract plus the
   redline draft for every FLAG/REJECT clause.
6. **gate** marks every item `pending_approval` — the export pack is a
   draft until a human approves it.

If `langgraph` is not installed the same nodes run sequentially with
identical state — the pipeline does not depend on it.

## The scoring (disclosed, no LLM)

Per clause, 0–100 (base + adjustment, capped at 100). Number words are
normalized to digits first ("twelve-month" → "12-month", "sixty (60) days"
→ "60 days"), so written-out and numeric periods parse the same way.
Parenthetical restatements ("three (3) months") are collapsed before
parsing. Tier: score ≥ 85 REJECT · ≥ 40 FLAG · otherwise ACCEPT.

| Rule | What the parser looks for | Score |
|---|---|---|
| Liability cap | months of fees | ≥12mo → 10 · <12mo → 55 + (12 − months) × 3 · amount-only → 60 · no number → 65 |
| Uncapped liability | carve-out from a stated cap vs exclusion vs "unlimited" | carve-out → 55 · exclusion → 45 · unlimited → 90 |
| Termination for convenience | notice days (months × 30) | ≥30d → 10 · <30d → 55 + (30 − days) · no period → 60 |
| Governing law | jurisdiction named | Ontario → 10 · other Canada → 55 · US state / other country → 80 |
| IP assignment | "assign" / "become property" vs licence-back only | assignment → 65 · licence-back → 45 |
| Audit rights | presence / absence | present → 10 · absent → 55 |
| Non-compete | presence; mitigated by stated carve-outs | no carve-out → 70 · carve-outs → 15 |
| No-solicit (employees) | presence | present → 60 |
| Most-favoured-nation | presence | present → 90 |
| Change of control | "terminate" vs consent / notice rights | termination → 70 · consent → 60 |
| Auto-renewal | renewal term (months) and opt-out notice (days), parsed separately | term >12mo → 55 + (term − 12) × 2 · notice >60d → 55 + (notice − 60) ÷ 5 · within limits → 10 |
| Anti-assignment | "freely assign" / "may assign … without consent" vs consent required | free → 15 · consent required → 60 |

Two parser traps, found while building and fixed in the code: a renewal
term of "two years" must never be misread as a 730-day notice period
(term and notice spans are parsed separately), and "shall not assign
without consent" is consent-*required* — the word "without" alone must
never trigger the free-assignment branch.

Thresholds were grid-searched on a 36-pair hand-labeled golden set:
**reject_bar 85, flag_bar 40** → tier accuracy 1.000, precision 1.000,
recall 1.000. The rules were also tuned against the golden set, so that
1.000 is a calibration result, not a held-out claim — the golden set and
its labels ship in `data/raw/golden_set.json` for anyone to re-check.

Route decision table (in order):

1. Any REJECT clause → ESCALATE
2. Overall score ≥ 80 → ESCALATE
3. Any FLAG clause → SEND_TO_LEGAL
4. Overall score ≥ 40 → SEND_TO_LEGAL
5. Otherwise → APPROVE

## What the run found (Fri Nov 6, 2026 replay)

| Route | Contracts |
|---|---|
| APPROVE | 0 |
| SEND_TO_LEGAL | 48 |
| ESCALATE | 2 |

- **Governing law is the story of this queue: 44 of 50 contracts (88.0%)
  are governed by a US state or another non-Ontario jurisdiction**, and
  APPROVE is 0. That is the corpus, not a bug: CUAD contracts are US SEC
  filings, and the playbook is an Ontario company's. It is also why the
  product is a redline desk, not an approval desk.
- **Uncapped liability in 9 contracts (18.0%)** — in this slice every one
  is a carve-out from a stated cap (confidentiality / IP / indemnity) or a
  consequential-damages exclusion, not a free-standing "unlimited"
  clause; all 9 flag rather than reject, and the evidence line says which.
- **23 contracts have no audit-rights clause at all** — the playbook
  requires one, so absence flags.
- **28 contracts carry a low or unquantified liability cap** — the most
  common pattern is a cap stated with no amount or period the parser can
  verify against 12 months' fees.
- **The only 2 escalations are the two most-favoured-nation contracts**
  (CUAD-150, CUAD-390). Everything else routes to Legal with a redline
  draft.
- **Estimated review effort 39.0h** for the queue at the disclosed
  per-route rates (APPROVE 10m, SEND_TO_LEGAL 45m, ESCALATE 90m).

## The playbook (seeded, disclosed)

The 12-rule playbook states the positions of **Harbourline Analytics
Inc.**, a fictional Toronto analytics firm. It is seeded demo data, not a
real company's playbook — each rule carries its CUAD category, a suggested
redline, and a fallback position in `data/raw/playbook.json`. The queue is
real; the playbook is the desk's own.

## Try it

- **Live demo:** https://ai-contract-redliner.web.app
- **Paste a clause tab:** pick the clause category, paste the clause text;
  the in-browser TypeScript mirror of the Python engine assesses it
  against the playbook and predicts the route. The mirror is verified
  against 12 shared test vectors in `data/test-vectors.json` (also shipped
  as `web/public/data/test-vectors.json`).
- **Repo:** https://github.com/tidaaartorhem/ai-contract-redliner

## Run it yourself

```bash
python3 scripts/fetch_cuad.py    # re-fetch CUAD (public GitHub zip, no auth)
python3 scripts/seed_playbook.py # regenerate the playbook + golden set
python3 -m pytest tests/ -q       # 32 tests
python3 scripts/build_web.py     # regenerate web/public/data/*.json
cd web && npm install && npm test && npm run build
```

## Project layout

```
scripts/fetch_cuad.py      fetch CUAD, slice 50 contracts, keep playbook spans
scripts/seed_playbook.py   the 12-rule playbook, scoring config, golden set
src/redlinedesk/text.py    tokenization, bigrams, Jaccard (+ light stemming)
src/redlinedesk/assess.py  deterministic clause -> playbook-rule assessment
src/redlinedesk/data.py    loaders for data/raw/*.json
src/redlinedesk/graph.py   LangGraph StateGraph: intake -> ... -> gate
src/redlinedesk/report.py  headline findings from a run
src/redlinedesk/eval.py    golden-set eval + threshold grid search
tests/test_redlinedesk.py  32 deterministic tests
web/                       React + Vite UI (light mode) + TS mirror
```

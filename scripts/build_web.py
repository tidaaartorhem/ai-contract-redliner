#!/usr/bin/env python3
"""Build script: runs the RedlineDesk pipeline and assembles the web payload.

Writes web/public/data/*.json:
  summary.json      - headline findings + golden-set eval + scoring disclosure
  contracts.json    - per-contract export pack (route, clauses, redline drafts)
  playbook.json     - the 12-rule Harbourline playbook
  test-vectors.json - shared Python/TS assessor contract (one vector per rule)
Exits non-zero if the pipeline produced no contracts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DATA = ROOT / "web" / "public" / "data"
RAW = ROOT / "data" / "raw"


def fail(msg: str) -> None:
    print(f"build_web: {msg}", file=sys.stderr)
    sys.exit(1)


# 12 contract vectors: one per playbook rule, spanning all three tiers.
VECTOR_KEYS = [
    ("CUAD-100", "LIABILITY_CAP"),       # ACCEPT (12-month cap)
    ("CUAD-050", "UNCAPPED_LIABILITY"),  # FLAG (consequential exclusion)
    ("CUAD-460", "TERMINATION_CONVENIENCE"),  # FLAG (5 days' notice)
    ("CUAD-390", "GOVERNING_LAW"),       # ACCEPT (Ontario)
    ("CUAD-030", "IP_ASSIGNMENT"),       # FLAG
    ("CUAD-000", "AUDIT_RIGHTS"),        # FLAG (absent)
    ("CUAD-150", "NON_COMPETE"),         # ACCEPT (carve-outs present)
    ("CUAD-000", "NO_SOLICIT_EMPLOYEES"),  # FLAG
    ("CUAD-150", "MFN"),                 # REJECT
    ("CUAD-030", "CHANGE_OF_CONTROL"),   # FLAG
    ("CUAD-100", "AUTO_RENEWAL"),        # FLAG (2-year term)
    ("CUAD-000", "ANTI_ASSIGNMENT"),     # FLAG (consent required)
]


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from redlinedesk import eval as rd_eval
    from redlinedesk.data import load_contracts
    from redlinedesk.graph import run
    from redlinedesk.report import findings

    state = run()
    if not state["export_pack"]:
        fail("pipeline produced no contracts")

    f = findings(state)
    ev = rd_eval.evaluate(state["config"])
    pb = json.loads((RAW / "playbook.json").read_text())
    queue = load_contracts()

    by_contract = {c["contract_id"]: c for c in state["contracts"]}
    pack_by_id = {p["contract_id"]: p for p in state["export_pack"]}

    vectors = []
    for cid, rid in VECTOR_KEYS:
        c = by_contract[cid]
        clause = next(cl for cl in pack_by_id[cid]["clauses"] if cl["rule_id"] == rid)
        raw = next(rc for rc in queue["contracts"] if rc["contract_id"] == cid)
        term_spans = [cl["text"] for cl in raw["clauses"]
                      if cl["rule_id"] == rid and cl["cuad_category"] != "Notice Period To Terminate Renewal"]
        notice_spans = [cl["text"] for cl in raw["clauses"]
                        if cl["cuad_category"] == "Notice Period To Terminate Renewal"]
        vectors.append({
            "contract_id": cid,
            "rule_id": rid,
            "term_spans": term_spans,
            "notice_spans": notice_spans if rid == "AUTO_RENEWAL" else [],
            "has_exception": c["has_exception"],
            "expected_tier": clause["tier"],
            "expected_score": clause["score"],
        })

    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "summary.json").write_text(json.dumps({
        "findings": f,
        "eval": {k: v for k, v in ev.items() if k != "misses"},
        "eval_misses": ev["misses"],
        "config": state["config"],
        "company": state["company"],
        "queue_meta": state["queue_meta"],
        "data_note": ("Contracts: 50 real commercial contracts from CUAD (Contract "
                      "Understanding Atticus Dataset, Hendrycks et al. 2021), deterministic "
                      "strided sample (every 10th of 510), CC BY 4.0. Clause spans are the "
                      "expert labels shipped with CUAD. The 12-rule playbook is seeded demo "
                      "data for the fictional Harbourline Analytics Inc. desk. CUAD contracts "
                      "are US SEC filings, so the Ontario-law playbook flags governing law on "
                      "44 of 50 — that is the corpus, not a bug."),
    }, indent=1))
    (WEB_DATA / "contracts.json").write_text(json.dumps(state["export_pack"], indent=1))
    (WEB_DATA / "playbook.json").write_text(json.dumps(
        {"rules": pb["rules"], "categories": pb["categories"]}, indent=1))
    (WEB_DATA / "test-vectors.json").write_text(json.dumps({"vectors": vectors}, indent=1))
    print(f"build_web: {len(state['export_pack'])} contracts, {len(pb['rules'])} playbook rules, "
          f"{len(vectors)} vectors -> {WEB_DATA}")


if __name__ == "__main__":
    main()

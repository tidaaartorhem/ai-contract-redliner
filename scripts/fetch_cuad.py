#!/usr/bin/env python3
"""Fetch the RedlineDesk contract queue: real commercial contracts from
CUAD (Contract Understanding Atticus Dataset, Hendrycks et al., NeurIPS
2021; https://github.com/TheAtticusProject/cuad, CC BY 4.0).

CUAD is 510 real contracts filed with the SEC, each with expert-labeled
clause spans in 41 categories. We take a deterministic strided slice of
50 contracts (every 10th, indices 0..490) and keep only the clause spans
for the 13 CUAD categories the Harbourline playbook covers (12 rules;
Renewal Term + Notice Period To Terminate Renewal feed one auto-renewal
rule, and Competitive Restriction Exception mitigates Non-Compete).

Writes data/raw/contracts.json and prints corpus stats. The raw CUAD
zip is cached in /tmp so re-runs do not re-download.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "contracts.json"
CACHE = Path("/tmp/cuad2.zip")
URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"

SLICE = [i * 10 for i in range(50)]
MAX_SPAN_CHARS = 2000

# CUAD category -> playbook rule id
CATEGORY_TO_RULE = {
    "Cap On Liability": "LIABILITY_CAP",
    "Uncapped Liability": "UNCAPPED_LIABILITY",
    "Termination For Convenience": "TERMINATION_CONVENIENCE",
    "Governing Law": "GOVERNING_LAW",
    "Ip Ownership Assignment": "IP_ASSIGNMENT",
    "Audit Rights": "AUDIT_RIGHTS",
    "Non-Compete": "NON_COMPETE",
    "No-Solicit Of Employees": "NO_SOLICIT_EMPLOYEES",
    "Most Favored Nation": "MFN",
    "Change Of Control": "CHANGE_OF_CONTROL",
    "Renewal Term": "AUTO_RENEWAL",
    "Notice Period To Terminate Renewal": "AUTO_RENEWAL",
    "Anti-Assignment": "ANTI_ASSIGNMENT",
    "Competitive Restriction Exception": "NON_COMPETE_EXCEPTION",
}

CAT_RE = re.compile(r'related to "([^"]+)"')


def _download() -> None:
    if CACHE.exists() and CACHE.stat().st_size > 1_000_000:
        print(f"fetch_cuad: using cached {CACHE}")
        return
    print(f"fetch_cuad: downloading {URL} ...")
    subprocess.run(["curl", "-sL", "--max-time", "300", "-o", str(CACHE), URL], check=True)


def _category(question: str) -> str | None:
    m = CAT_RE.search(question)
    return m.group(1) if m else None


def _doc_name(contract: dict) -> str | None:
    for p in contract["paragraphs"]:
        for q in p["qas"]:
            if _category(q["question"]) == "Document Name" and q["answers"]:
                return q["answers"][0]["text"][:160]
    return None


def _parties(contract: dict) -> str | None:
    for p in contract["paragraphs"]:
        for q in p["qas"]:
            if _category(q["question"]) == "Parties" and q["answers"]:
                return q["answers"][0]["text"][:240]
    return None


def _dates(contract: dict) -> dict:
    out: dict[str, str | None] = {"agreement_date": None, "effective_date": None}
    for p in contract["paragraphs"]:
        for q in p["qas"]:
            cat = _category(q["question"])
            if cat == "Agreement Date" and q["answers"] and not out["agreement_date"]:
                out["agreement_date"] = q["answers"][0]["text"][:80]
            if cat == "Effective Date" and q["answers"] and not out["effective_date"]:
                out["effective_date"] = q["answers"][0]["text"][:80]
    return out


def main() -> None:
    _download()
    with zipfile.ZipFile(CACHE) as z:
        raw = json.loads(z.read("CUADv1.json"))
    contracts = []
    span_count = 0
    for idx in SLICE:
        c = raw["data"][idx]
        clauses: list[dict] = []
        for p in c["paragraphs"]:
            for q in p["qas"]:
                cat = _category(q["question"])
                if cat not in CATEGORY_TO_RULE:
                    continue
                for a in q["answers"]:
                    text = (a["text"] or "").strip()
                    if not text:
                        continue
                    clauses.append({
                        "rule_id": CATEGORY_TO_RULE[cat],
                        "cuad_category": cat,
                        "text": text[:MAX_SPAN_CHARS],
                        "truncated": len(text) > MAX_SPAN_CHARS,
                        "answer_start": a["answer_start"],
                    })
                    span_count += 1
        dates = _dates(c)
        contracts.append({
            "contract_id": f"CUAD-{idx:03d}",
            "cuad_index": idx,
            "title": c["title"],
            "document_name": _doc_name(c),
            "parties": _parties(c),
            "agreement_date": dates["agreement_date"],
            "effective_date": dates["effective_date"],
            "clauses": clauses,
        })
    payload = {
        "source": "CUAD (Contract Understanding Atticus Dataset), Hendrycks et al. 2021",
        "source_url": "https://github.com/TheAtticusProject/cuad",
        "license": "CC BY 4.0",
        "citation": ("Hendrycks, Burns, Chen, Ball. CUAD: An Expert-Annotated NLP "
                     "Dataset for Legal Contract Review. NeurIPS 2021. arXiv:2103.06268."),
        "slice": "deterministic strided sample: every 10th contract, indices 0..490 (50 of 510)",
        "clause_note": ("Clause spans are the expert labels shipped with CUAD; "
                        "only the 14 playbook-relevant categories are kept. Spans are "
                        "capped at 2000 chars (2 spans truncated)."),
        "fetched_at": "2026-11-06",
        "replay_date": "2026-11-06",
        "count": len(contracts),
        "span_count": span_count,
        "contracts": contracts,
    }
    OUT.write_text(json.dumps(payload, indent=1))
    per_rule: dict[str, int] = {}
    for c in contracts:
        for cl in c["clauses"]:
            per_rule[cl["rule_id"]] = per_rule.get(cl["rule_id"], 0) + 1
    print(f"fetch_cuad: {len(contracts)} contracts, {span_count} clause spans -> {OUT}")
    for k in sorted(per_rule):
        print(f"  {per_rule[k]:4d} {k}")


if __name__ == "__main__":
    main()

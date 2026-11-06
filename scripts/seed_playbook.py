#!/usr/bin/env python3
"""Seed the RedlineDesk playbook, scoring config, and golden set.

The playbook is SEEDED demo data: 12 rules stating Harbourline Analytics
Inc.'s (fictional) contract positions, each with the CUAD category it
reads, a suggested redline, and a fallback position. The contract queue
itself is real (CUAD expert-labeled spans); the playbook is the company's
own positions, disclosed as seeded.

Golden set: 36 hand-labeled (contract, rule) -> expected tier pairs, read
from the actual CUAD spans (see README for the labeling notes). Absent
rules are labeled too: AUDIT_RIGHTS absent is FLAG (the playbook requires
audit rights), while an absent MFN / non-compete / change-of-control is
ACCEPT (nothing to flag).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# id, cuad category, title, stance, redline, fallback
RULES = [
    ("LIABILITY_CAP", "Cap On Liability",
     "Liability cap must be at least 12 months' fees",
     "Cap each party's aggregate liability at the fees paid or payable in the "
     "12 months before the claim; carve out only wilful misconduct and IP infringement.",
     "Accept a 6-month cap if the counterparty carries $2M+ E&O cover."),
    ("UNCAPPED_LIABILITY", "Uncapped Liability",
     "No uncapped liability except a capped carve-out",
     "Delete the uncapped-liability carve-out; liability for confidentiality and "
     "IP breaches stays inside the cap.",
     "Cap carve-out exposure at 24 months' fees."),
    ("TERMINATION_CONVENIENCE", "Termination For Convenience",
     "Termination for convenience needs at least 30 days' notice",
     "Either party may terminate for convenience on 30 days' written notice.",
     "Accept 60 days if the counterparty funds wind-down."),
    ("GOVERNING_LAW", "Governing Law",
     "Governing law must be Ontario",
     "Governing law: Ontario; the courts of Toronto have exclusive jurisdiction.",
     "Accept the federal law of Canada with Toronto arbitration."),
    ("IP_ASSIGNMENT", "Ip Ownership Assignment",
     "IP in deliverables stays with Harbourline",
     "IP in deliverables created for Harbourline is owned by Harbourline; "
     "counterparty IP stays with the counterparty; any licence-back is non-exclusive.",
     "Accept joint ownership only for jointly created background IP."),
    ("AUDIT_RIGHTS", "Audit Rights",
     "Harbourline must hold audit rights",
     "Harbourline may audit the counterparty's relevant books once per year on "
     "30 days' notice.",
     "Accept an independent-auditor certificate in place of direct audit."),
    ("NON_COMPETE", "Non-Compete",
     "No non-compete unless stated carve-outs exist",
     "Delete the non-compete; replace with a 12-month non-solicit of Harbourline customers.",
     "Accept a 12-month, Ontario-only non-compete with a carve-out for pre-existing business."),
    ("NO_SOLICIT_EMPLOYEES", "No-Solicit Of Employees",
     "No employee non-solicit, or 12 months at most",
     "Delete the employee non-solicit; replace with a 12-month non-solicit limited "
     "to employees the counterparty introduced.",
     "Accept 12 months, employees only, no contractors."),
    ("MFN", "Most Favored Nation",
     "No most-favoured-nation clause, ever",
     "Delete the most-favoured-nation clause in full.",
     "No fallback. Escalate to legal."),
    ("CHANGE_OF_CONTROL", "Change Of Control",
     "Change of control must not trigger termination or consent",
     "Change of control does not trigger termination or consent; Harbourline may "
     "assign on a change of control.",
     "Accept notice-only on change of control, no consent."),
    ("AUTO_RENEWAL", "Renewal Term / Notice Period To Terminate Renewal",
     "Auto-renewal: 12-month term max, 60-day opt-out max",
     "Renewal is by written agreement only; no automatic renewal. If auto-renewal "
     "is retained, term 12 months and opt-out notice 30 days.",
     "Accept a 12-month auto-renewal with a 60-day opt-out notice."),
    ("ANTI_ASSIGNMENT", "Anti-Assignment",
     "Harbourline must be free to assign on change of control or to an affiliate",
     "Either party may assign on a change of control or to an affiliate without "
     "consent; other assignments need consent not to be unreasonably withheld.",
     "Accept consent not to be unreasonably withheld or delayed."),
]

CATEGORIES = {
    "LIABILITY_CAP": "Liability cap",
    "UNCAPPED_LIABILITY": "Uncapped liability",
    "TERMINATION_CONVENIENCE": "Termination for convenience",
    "GOVERNING_LAW": "Governing law",
    "IP_ASSIGNMENT": "IP ownership / assignment",
    "AUDIT_RIGHTS": "Audit rights",
    "NON_COMPETE": "Non-compete",
    "NO_SOLICIT_EMPLOYEES": "No-solicit of employees",
    "MFN": "Most-favoured-nation",
    "CHANGE_OF_CONTROL": "Change of control",
    "AUTO_RENEWAL": "Auto-renewal",
    "ANTI_ASSIGNMENT": "Anti-assignment",
}

# Hand-labeled golden set: (contract_id, rule_id) -> expected tier.
# Labels read from the actual CUAD spans; see README "Golden set" notes.
GOLDEN = [
    # LIABILITY_CAP: 12-month cap accepts; unquantified / amount-only flags
    {"contract_id": "CUAD-100", "rule_id": "LIABILITY_CAP", "expected": "ACCEPT"},
    {"contract_id": "CUAD-010", "rule_id": "LIABILITY_CAP", "expected": "FLAG"},
    {"contract_id": "CUAD-390", "rule_id": "LIABILITY_CAP", "expected": "FLAG"},
    # UNCAPPED_LIABILITY: slice has only carve-outs / exclusions, all FLAG
    {"contract_id": "CUAD-050", "rule_id": "UNCAPPED_LIABILITY", "expected": "FLAG"},
    {"contract_id": "CUAD-100", "rule_id": "UNCAPPED_LIABILITY", "expected": "FLAG"},
    {"contract_id": "CUAD-180", "rule_id": "UNCAPPED_LIABILITY", "expected": "FLAG"},
    # TERMINATION_CONVENIENCE: 3 months / 30 days accept; 5 days flags
    {"contract_id": "CUAD-020", "rule_id": "TERMINATION_CONVENIENCE", "expected": "ACCEPT"},
    {"contract_id": "CUAD-260", "rule_id": "TERMINATION_CONVENIENCE", "expected": "ACCEPT"},
    {"contract_id": "CUAD-460", "rule_id": "TERMINATION_CONVENIENCE", "expected": "FLAG"},
    # GOVERNING_LAW: Ontario accepts; Illinois / California flag
    {"contract_id": "CUAD-390", "rule_id": "GOVERNING_LAW", "expected": "ACCEPT"},
    {"contract_id": "CUAD-000", "rule_id": "GOVERNING_LAW", "expected": "FLAG"},
    {"contract_id": "CUAD-260", "rule_id": "GOVERNING_LAW", "expected": "FLAG"},
    # IP_ASSIGNMENT: assignment to counterparty flags (incl. broad licence-back)
    {"contract_id": "CUAD-030", "rule_id": "IP_ASSIGNMENT", "expected": "FLAG"},
    {"contract_id": "CUAD-310", "rule_id": "IP_ASSIGNMENT", "expected": "FLAG"},
    {"contract_id": "CUAD-470", "rule_id": "IP_ASSIGNMENT", "expected": "FLAG"},
    # AUDIT_RIGHTS: present accepts; absent flags
    {"contract_id": "CUAD-020", "rule_id": "AUDIT_RIGHTS", "expected": "ACCEPT"},
    {"contract_id": "CUAD-230", "rule_id": "AUDIT_RIGHTS", "expected": "ACCEPT"},
    {"contract_id": "CUAD-000", "rule_id": "AUDIT_RIGHTS", "expected": "FLAG"},
    # NON_COMPETE: no carve-out flags; stated carve-outs accept; absent accepts
    {"contract_id": "CUAD-030", "rule_id": "NON_COMPETE", "expected": "FLAG"},
    {"contract_id": "CUAD-150", "rule_id": "NON_COMPETE", "expected": "ACCEPT"},
    {"contract_id": "CUAD-000", "rule_id": "NON_COMPETE", "expected": "ACCEPT"},
    # NO_SOLICIT_EMPLOYEES: present flags; absent accepts
    {"contract_id": "CUAD-000", "rule_id": "NO_SOLICIT_EMPLOYEES", "expected": "FLAG"},
    {"contract_id": "CUAD-030", "rule_id": "NO_SOLICIT_EMPLOYEES", "expected": "FLAG"},
    {"contract_id": "CUAD-100", "rule_id": "NO_SOLICIT_EMPLOYEES", "expected": "ACCEPT"},
    # MFN: present rejects; absent accepts
    {"contract_id": "CUAD-150", "rule_id": "MFN", "expected": "REJECT"},
    {"contract_id": "CUAD-390", "rule_id": "MFN", "expected": "REJECT"},
    {"contract_id": "CUAD-000", "rule_id": "MFN", "expected": "ACCEPT"},
    # CHANGE_OF_CONTROL: consent/termination rights flag; absent accepts
    {"contract_id": "CUAD-030", "rule_id": "CHANGE_OF_CONTROL", "expected": "FLAG"},
    {"contract_id": "CUAD-050", "rule_id": "CHANGE_OF_CONTROL", "expected": "FLAG"},
    {"contract_id": "CUAD-000", "rule_id": "CHANGE_OF_CONTROL", "expected": "ACCEPT"},
    # AUTO_RENEWAL: 1-year term accepts; 2-year / 10-year terms flag
    {"contract_id": "CUAD-000", "rule_id": "AUTO_RENEWAL", "expected": "ACCEPT"},
    {"contract_id": "CUAD-100", "rule_id": "AUTO_RENEWAL", "expected": "FLAG"},
    {"contract_id": "CUAD-030", "rule_id": "AUTO_RENEWAL", "expected": "FLAG"},
    # ANTI_ASSIGNMENT: consent-required flags (incl. "not unreasonably withheld")
    {"contract_id": "CUAD-000", "rule_id": "ANTI_ASSIGNMENT", "expected": "FLAG"},
    {"contract_id": "CUAD-020", "rule_id": "ANTI_ASSIGNMENT", "expected": "FLAG"},
    {"contract_id": "CUAD-090", "rule_id": "ANTI_ASSIGNMENT", "expected": "FLAG"},
]

CONFIG = {
    "thresholds": {"reject_bar": 85, "flag_bar": 40},
    "route_bars": {"escalate_score": 80, "legal_score": 40},
    "contract_score_weights": {"max_clause": 0.7, "mean_clause": 0.3},
    "effort_minutes": {"APPROVE": 10, "SEND_TO_LEGAL": 45, "ESCALATE": 90},
    "replay_date": "2026-11-06",
}


def main() -> None:
    playbook = {
        "company": {
            "name": "Harbourline Analytics Inc.",
            "profile": ("Fictional Toronto analytics firm. The contract queue is real "
                        "(CUAD expert-labeled spans); the playbook is the company's own "
                        "seeded positions."),
            "fictional": True,
        },
        "categories": CATEGORIES,
        "rules": [
            {
                "id": rid, "cuad_category": cat, "title": title,
                "stance": title, "redline": redline, "fallback": fallback,
                "seeded": True,
            }
            for rid, cat, title, redline, fallback in RULES
        ],
    }
    (RAW / "playbook.json").write_text(json.dumps(playbook, indent=1))
    (RAW / "scoring-config.json").write_text(json.dumps(CONFIG, indent=1))
    (RAW / "golden_set.json").write_text(json.dumps({"pairs": GOLDEN}, indent=1))
    print(f"seed_playbook: {len(RULES)} playbook rules, {len(GOLDEN)} golden pairs -> {RAW}")


if __name__ == "__main__":
    main()

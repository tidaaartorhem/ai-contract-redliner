"""Headline findings computed from a pipeline run. Numbers are measured,
not invented."""
import json
from collections import Counter
from pathlib import Path

from .data import DATA_DIR


def findings(state: dict) -> dict:
    pack = state["export_pack"]
    cfg = state["config"]
    routes = Counter(p["route"] for p in pack)
    n = len(pack)

    per_rule: dict[str, dict] = {}
    for p in pack:
        for cl in p["clauses"]:
            cell = per_rule.setdefault(cl["rule_id"], {"present": 0, "accept": 0, "flag": 0, "reject": 0})
            if cl["present"]:
                cell["present"] += 1
            cell[cl["tier"].lower()] += 1
    rule_table = {
        rid: {
            "present": v["present"],
            "present_pct": round(100 * v["present"] / n, 1),
            "accept": v["accept"],
            "flag": v["flag"],
            "reject": v["reject"],
            "flag_rate": round(100 * (v["flag"] + v["reject"]) / n, 1),
        }
        for rid, v in sorted(per_rule.items())
    }
    most_flagged = max(rule_table.items(), key=lambda kv: kv[1]["flag"] + kv[1]["reject"])

    uncapped = sum(1 for p in pack if any(
        cl["rule_id"] == "UNCAPPED_LIABILITY" and cl["present"] for cl in p["clauses"]))
    no_audit = sum(1 for p in pack if any(
        cl["rule_id"] == "AUDIT_RIGHTS" and cl["tier"] == "FLAG" for cl in p["clauses"]))
    non_ontario = sum(1 for p in pack if any(
        cl["rule_id"] == "GOVERNING_LAW" and cl["tier"] == "FLAG" for cl in p["clauses"]))
    low_caps = sum(1 for p in pack if any(
        cl["rule_id"] == "LIABILITY_CAP" and cl["tier"] == "FLAG" for cl in p["clauses"]))

    effort = cfg["effort_minutes"]
    total_minutes = sum(effort[p["route"]] for p in pack)
    scores = [p["overall_score"] for p in pack]
    mean_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    total_spans = sum(len(cl["spans"]) for p in pack for cl in p["clauses"])
    corpus_spans = state["queue_meta"]["span_count"]  # 488: incl. 18 exception spans used as context

    return {
        "contract_count": n,
        "routes": dict(routes),
        "approve_pct": round(100 * routes.get("APPROVE", 0) / n, 1),
        "needs_legal_pct": round(100 * (routes.get("SEND_TO_LEGAL", 0) + routes.get("ESCALATE", 0)) / n, 1),
        "rule_table": rule_table,
        "most_flagged_rule": most_flagged[0],
        "most_flagged_count": most_flagged[1]["flag"] + most_flagged[1]["reject"],
        "uncapped_liability_contracts": uncapped,
        "uncapped_liability_pct": round(100 * uncapped / n, 1),
        "no_audit_rights_contracts": no_audit,
        "non_ontario_governing_law_contracts": non_ontario,
        "low_or_unquantified_cap_contracts": low_caps,
        "total_clause_spans": corpus_spans,
        "assessed_playbook_spans": total_spans,
        "exception_spans": corpus_spans - total_spans,
        "mean_overall_score": mean_score,
        "effort_minutes": total_minutes,
        "effort_hours": round(total_minutes / 60, 1),
    }


def main() -> None:
    from .graph import run

    state = run()
    f = findings(state)
    out = DATA_DIR.parent / "outputs" / "findings.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"findings": f, "export_pack": state["export_pack"]}, indent=1))
    r = f["routes"]
    print(
        f"{f['contract_count']} contracts -> APPROVE {r.get('APPROVE',0)} | "
        f"SEND_TO_LEGAL {r.get('SEND_TO_LEGAL',0)} | ESCALATE {r.get('ESCALATE',0)} | "
        f"effort {f['effort_hours']}h | mean score {f['mean_overall_score']}"
    )
    print(f"most-flagged rule: {f['most_flagged_rule']} ({f['most_flagged_count']} contracts)")
    print(f"uncapped liability: {f['uncapped_liability_contracts']} contracts "
          f"({f['uncapped_liability_pct']}%), no audit rights: {f['no_audit_rights_contracts']}, "
          f"non-Ontario governing law: {f['non_ontario_governing_law_contracts']}")


if __name__ == "__main__":
    main()

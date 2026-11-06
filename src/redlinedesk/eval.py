"""Golden-set evaluation + threshold calibration for the clause assessor.

Metrics (all on the 36 hand-labeled (contract, rule) pairs in
data/raw/golden_set.json):
  - tier accuracy: fraction where the assessor's tier matches the label.
  - precision: correct FLAG/REJECT calls / all FLAG/REJECT calls.
  - recall:    correct FLAG/REJECT calls / all FLAG/REJECT labels.

The reject_bar / flag_bar cutoffs are grid-searched on the golden set and
written back to scoring-config.json (documented as tuned on the golden
set — a calibration result, not a held-out test).
"""
import itertools
import json
from pathlib import Path

from .assess import assess_clause
from .data import DATA_DIR, load_config, load_contracts, load_golden, load_playbook


def evaluate(cfg: dict) -> dict:
    contracts = {c["contract_id"]: c for c in load_contracts()["contracts"]}
    rules = {r["id"]: r for r in load_playbook()["rules"]}
    golden = load_golden()
    correct = tp = fp = 0
    fn_labels = sum(1 for p in golden if p["expected"] in ("FLAG", "REJECT"))
    misses = []
    for p in golden:
        c = contracts[p["contract_id"]]
        spans = [cl["text"] for cl in c["clauses"] if cl["rule_id"] == p["rule_id"]]
        notice_spans = [cl["text"] for cl in c["clauses"]
                        if cl["cuad_category"] == "Notice Period To Terminate Renewal"]
        has_exception = any(cl["rule_id"] == "NON_COMPETE_EXCEPTION" for cl in c["clauses"])
        if p["rule_id"] == "AUTO_RENEWAL":
            term_spans = [cl["text"] for cl in c["clauses"]
                          if cl["cuad_category"] == "Renewal Term"]
            got = assess_clause(p["rule_id"], term_spans, rules[p["rule_id"]], cfg,
                                notice_spans=notice_spans)["tier"]
        else:
            got = assess_clause(p["rule_id"], spans, rules[p["rule_id"]], cfg,
                                has_exception=has_exception)["tier"]
        if got == p["expected"]:
            correct += 1
            if got in ("FLAG", "REJECT"):
                tp += 1
        else:
            misses.append({"contract_id": p["contract_id"], "rule_id": p["rule_id"],
                           "expected": p["expected"], "got": got})
            if got in ("FLAG", "REJECT"):
                fp += 1
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / fn_labels if fn_labels else 1.0
    return {
        "n": len(golden),
        "tier_accuracy": round(correct / len(golden), 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "misses": misses,
    }


def calibrate() -> dict:
    cfg = load_config()
    best = None
    for reject_bar, flag_bar in itertools.product(range(75, 96, 5), range(30, 56, 5)):
        if reject_bar <= flag_bar:
            continue
        trial = {**cfg, "thresholds": {"reject_bar": reject_bar, "flag_bar": flag_bar}}
        ev = evaluate(trial)
        key = (ev["tier_accuracy"], ev["precision"])
        # Prefer the shipped defaults on a tie (stability over churn).
        tiebreak = -abs(reject_bar - 85) - abs(flag_bar - 40)
        if best is None or (key, tiebreak) > (best[0], best[1]):
            best = (key, tiebreak, reject_bar, flag_bar, ev)
    _, _, reject_bar, flag_bar, ev = best
    cfg["thresholds"] = {"reject_bar": reject_bar, "flag_bar": flag_bar}
    cfg["tuning_note"] = (f"Thresholds grid-searched on the {ev['n']}-pair golden set "
                          f"(reject_bar={reject_bar}, flag_bar={flag_bar}); "
                          f"tier_accuracy={ev['tier_accuracy']}, precision={ev['precision']}, "
                          f"recall={ev['recall']}. Calibration only — the golden set is "
                          f"also the tuning set, so these are not held-out numbers.")
    (DATA_DIR / "scoring-config.json").write_text(json.dumps(cfg, indent=1))
    return {"thresholds": cfg["thresholds"], **ev}


def main() -> None:
    res = calibrate()
    print(f"thresholds: {res['thresholds']}")
    print(f"tier_accuracy={res['tier_accuracy']} precision={res['precision']} recall={res['recall']}")
    print(f"misses ({len(res['misses'])}):")
    for m in res["misses"]:
        print(f"  {m['contract_id']} {m['rule_id']}: expected {m['expected']}, got {m['got']}")


if __name__ == "__main__":
    main()

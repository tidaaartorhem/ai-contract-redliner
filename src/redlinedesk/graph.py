"""RedlineDesk LangGraph pipeline.

StateGraph: intake -> extract_clauses -> match_playbook -> score_risk
             -> draft_redline -> gate

- intake:          load the 50-contract CUAD queue + the seeded playbook.
- extract_clauses: group each contract's expert-labeled spans by playbook
                   rule (Renewal Term + Notice Period feed one auto-renewal
                   rule; Competitive Restriction Exception is kept as
                   mitigation context for Non-Compete).
- match_playbook:  assess every rule against its spans (assess.py): each
                   clause gets a tier (ACCEPT / FLAG / REJECT), a 0-100
                   risk score with disclosed parts, evidence, a suggested
                   redline, and a fallback position.
- score_risk:      per-contract overall score (0.7 * worst clause +
                   0.3 * mean clause) and route:
                     ESCALATE      any REJECT clause, or score >= 80
                     SEND_TO_LEGAL any FLAG clause, or score >= 40
                     APPROVE       otherwise
- draft_redline:   one recommended action per contract + the redline draft
                   (suggested redlines for every FLAG/REJECT clause).
- gate:            every redline is a human-gated draft; nothing is sent
                   or marked final automatically.
"""
from __future__ import annotations

from typing import Any

from .assess import assess_clause
from .data import load_config, load_contracts, load_playbook

RULE_ORDER = [
    "LIABILITY_CAP", "UNCAPPED_LIABILITY", "TERMINATION_CONVENIENCE",
    "GOVERNING_LAW", "IP_ASSIGNMENT", "AUDIT_RIGHTS", "NON_COMPETE",
    "NO_SOLICIT_EMPLOYEES", "MFN", "CHANGE_OF_CONTROL", "AUTO_RENEWAL",
    "ANTI_ASSIGNMENT",
]


def node_intake(state: dict) -> dict:
    queue = load_contracts()
    pb = load_playbook()
    return {
        **state,
        "contracts": queue["contracts"],
        "queue_meta": {k: v for k, v in queue.items() if k != "contracts"},
        "rules": {r["id"]: r for r in pb["rules"]},
        "rule_list": pb["rules"],
        "company": pb["company"],
        "categories": pb["categories"],
        "config": load_config(),
    }


def node_extract_clauses(state: dict) -> dict:
    grouped = []
    for c in state["contracts"]:
        by_rule: dict[str, list[str]] = {r: [] for r in RULE_ORDER}
        auto_term: list[str] = []
        auto_notice: list[str] = []
        has_exception = False
        for cl in c["clauses"]:
            if cl["rule_id"] == "NON_COMPETE_EXCEPTION":
                has_exception = True
            elif cl["rule_id"] in by_rule:
                by_rule[cl["rule_id"]].append(cl["text"])
                if cl["rule_id"] == "AUTO_RENEWAL":
                    if cl["cuad_category"] == "Notice Period To Terminate Renewal":
                        auto_notice.append(cl["text"])
                    else:
                        auto_term.append(cl["text"])
        grouped.append({**c, "spans_by_rule": by_rule,
                        "auto_term_spans": auto_term,
                        "auto_notice_spans": auto_notice,
                        "has_exception": has_exception})
    return {**state, "contracts": grouped}


def node_match_playbook(state: dict) -> dict:
    cfg = state["config"]
    assessed = []
    for c in state["contracts"]:
        clauses = []
        for rid in RULE_ORDER:
            rule = state["rules"][rid]
            if rid == "AUTO_RENEWAL":
                a = assess_clause(rid, c["auto_term_spans"], rule, cfg,
                                  notice_spans=c["auto_notice_spans"])
            else:
                a = assess_clause(rid, c["spans_by_rule"][rid], rule, cfg,
                                  has_exception=c["has_exception"])
            clauses.append({**a, "spans": c["spans_by_rule"][rid]})
        assessed.append({**c, "clauses": clauses})
    return {**state, "contracts": assessed}


def _route(clauses: list[dict], overall: int, cfg: dict) -> str:
    if any(c["tier"] == "REJECT" for c in clauses):
        return "ESCALATE"
    if overall >= cfg["route_bars"]["escalate_score"]:
        return "ESCALATE"
    if any(c["tier"] == "FLAG" for c in clauses):
        return "SEND_TO_LEGAL"
    if overall >= cfg["route_bars"]["legal_score"]:
        return "SEND_TO_LEGAL"
    return "APPROVE"


def _overall(clauses: list[dict], cfg: dict) -> int:
    w = cfg["contract_score_weights"]
    scores = [c["score"] for c in clauses]
    return round(w["max_clause"] * max(scores) + w["mean_clause"] * (sum(scores) / len(scores)))


def node_score_risk(state: dict) -> dict:
    cfg = state["config"]
    scored = []
    for c in state["contracts"]:
        overall = _overall(c["clauses"], cfg)
        scored.append({**c, "overall_score": overall, "route": _route(c["clauses"], overall, cfg)})
    return {**state, "contracts": scored}


_ROUTE_ACTION = {
    "APPROVE": "No redlines needed. File the contract as-is; the desk's audit-rights check is the only open item if it flagged.",
    "SEND_TO_LEGAL": "Send the redline draft below to Legal with the flagged clauses; do not sign until Legal clears the draft.",
    "ESCALATE": "Escalate to Legal immediately — a REJECT-tier clause (or an 80+ risk score) means this draft must not be signed.",
}


def node_draft_redline(state: dict) -> dict:
    drafted = []
    for c in state["contracts"]:
        flagged = [cl for cl in c["clauses"] if cl["tier"] in ("FLAG", "REJECT")]
        redlines = [
            {
                "rule_id": cl["rule_id"],
                "title": state["rules"][cl["rule_id"]]["title"],
                "tier": cl["tier"],
                "score": cl["score"],
                "evidence": cl["evidence"],
                "redline": cl["redline"],
                "fallback": cl["fallback"],
            }
            for cl in flagged
        ]
        drafted.append({
            **c,
            "action": _ROUTE_ACTION[c["route"]],
            "redline_draft": redlines,
            "flag_count": len([cl for cl in c["clauses"] if cl["tier"] == "FLAG"]),
            "reject_count": len([cl for cl in c["clauses"] if cl["tier"] == "REJECT"]),
        })
    return {**state, "contracts": drafted}


def node_gate(state: dict) -> dict:
    pack = [
        {
            "contract_id": c["contract_id"],
            "title": c["title"],
            "document_name": c["document_name"],
            "parties": c["parties"],
            "agreement_date": c["agreement_date"],
            "effective_date": c["effective_date"],
            "overall_score": c["overall_score"],
            "route": c["route"],
            "flag_count": c["flag_count"],
            "reject_count": c["reject_count"],
            "clauses": [
                {
                    "rule_id": cl["rule_id"],
                    "title": state["rules"][cl["rule_id"]]["title"],
                    "tier": cl["tier"],
                    "score": cl["score"],
                    "score_parts": cl["score_parts"],
                    "evidence": cl["evidence"],
                    "present": cl["present"],
                    "spans": cl["spans"],
                    "redline": cl["redline"],
                    "fallback": cl["fallback"],
                }
                for cl in c["clauses"]
            ],
            "action": c["action"],
            "redline_draft": c["redline_draft"],
            "pending_approval": True,
        }
        for c in state["contracts"]
    ]
    return {**state, "export_pack": pack}


NODES = [node_intake, node_extract_clauses, node_match_playbook,
         node_score_risk, node_draft_redline, node_gate]


def build_graph():
    """Return a compiled LangGraph StateGraph; fall back to a sequential
    runner when langgraph is not installed (same node order, same state)."""
    try:
        from langgraph.graph import StateGraph  # type: ignore

        g: Any = StateGraph(dict)
        prev = None
        for fn in NODES:
            name = fn.__name__.replace("node_", "")
            g.add_node(name, fn)
            if prev:
                g.add_edge(prev, name)
            else:
                g.set_entry_point(name)
            prev = name
        g.add_edge(prev, "__end__")
        return g.compile()
    except ImportError:
        return None


def run() -> dict:
    graph = build_graph()
    if graph is not None:
        return graph.invoke({})
    state: dict = {}
    for fn in NODES:
        state = fn(state)
    return state

"""RedlineDesk pipeline tests. All deterministic; no network, no LLM."""
import json
from pathlib import Path

import pytest

from redlinedesk import assess, eval as rd_eval, graph, report
from redlinedesk.assess import (
    assess_clause, normalize_numbers, parse_days, parse_months,
)
from redlinedesk.data import load_config, load_contracts, load_playbook
from redlinedesk.text import tokens

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"

RULE = {"redline": "REDLINE", "fallback": "FALLBACK"}


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def rules():
    return {r["id"]: r for r in load_playbook()["rules"]}


@pytest.fixture(scope="module")
def full_state():
    return graph.run()


# ------------------------------------------------------------- text / parse

def test_normalize_numbers_words_and_parentheticals():
    assert normalize_numbers("three (3) months written notice") == "3 months written notice"
    assert normalize_numbers("sixty (60) days prior") == "60 days prior"
    assert normalize_numbers("twelve-month period") == "12-month period"
    assert normalize_numbers("twenty four (24) months") == "24 months"


def test_parse_months_and_days():
    assert parse_months(normalize_numbers("limited to twelve-month fees")) == 12
    assert parse_months(normalize_numbers("for one (1) year terms")) == 12
    assert parse_months(normalize_numbers("renew for two (2) years")) == 24
    assert parse_days(normalize_numbers("thirty days written notice")) == 30
    assert parse_days(normalize_numbers("five days prior written notice")) == 5
    assert parse_days(normalize_numbers("three (3) months notice")) == 90
    assert parse_days(normalize_numbers("no period stated")) is None


def test_tokens_still_work():
    assert tokens("Are biometrics and passkeys enabled?") == ["biometric", "passkey", "enabled"]


# ------------------------------------------------------------- assess rules

def test_liability_cap_twelve_months_accepts(cfg):
    a = assess_clause("LIABILITY_CAP",
                      ["limited to the amounts paid or payable during the twelve-month period"],
                      RULE, cfg)
    assert (a["tier"], a["score"]) == ("ACCEPT", 10)


def test_liability_cap_six_months_flags(cfg):
    a = assess_clause("LIABILITY_CAP",
                      ["liability capped at six months fees"], RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 73


def test_liability_cap_amount_only_flags(cfg):
    a = assess_clause("LIABILITY_CAP",
                      ["liability shall not exceed U.S.$5,000,000"], RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 60


def test_liability_cap_unquantified_flags(cfg):
    a = assess_clause("LIABILITY_CAP",
                      ["It is the cumulative maximum for which IBM is responsible."],
                      RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 65


def test_uncapped_carveout_flags_not_rejects(cfg):
    a = assess_clause("UNCAPPED_LIABILITY",
                      ["Except for breach of confidentiality, liability shall be limited "
                       "to the amounts paid during the twelve-month period"], RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 55


def test_uncapped_exclusion_flags(cfg):
    a = assess_clause("UNCAPPED_LIABILITY",
                      ["In no event will either party be liable for special, incidental, "
                       "or consequential damages"], RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 45


def test_termination_thirty_days_accepts(cfg):
    a = assess_clause("TERMINATION_CONVENIENCE",
                      ["may terminate for any reason with thirty days written notice"],
                      RULE, cfg)
    assert (a["tier"], a["score"]) == ("ACCEPT", 10)


def test_termination_five_days_flags(cfg):
    a = assess_clause("TERMINATION_CONVENIENCE",
                      ["terminate at any time upon five days prior written notice"],
                      RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 80


def test_termination_no_period_flags(cfg):
    a = assess_clause("TERMINATION_CONVENIENCE",
                      ["Customer may terminate at any time by destroying all copies."],
                      RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 60


def test_governing_law_ontario_accepts(cfg):
    a = assess_clause("GOVERNING_LAW",
                      ["governed by the laws of the Province of Ontario, Canada"],
                      RULE, cfg)
    assert (a["tier"], a["score"]) == ("ACCEPT", 10)


def test_governing_law_us_state_flags_high(cfg):
    a = assess_clause("GOVERNING_LAW",
                      ["governed by the laws of the State of New York"], RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 80


def test_governing_law_other_canada_flags_mid(cfg):
    a = assess_clause("GOVERNING_LAW",
                      ["governed by the laws of British Columbia"], RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 55


def test_ip_assignment_flags(cfg):
    a = assess_clause("IP_ASSIGNMENT",
                      ["Distributor shall assign all intellectual property rights in any "
                       "modification to Erchonia"], RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 65


def test_audit_rights_absent_flags_present_accepts(cfg):
    absent = assess_clause("AUDIT_RIGHTS", [], RULE, cfg)
    present = assess_clause("AUDIT_RIGHTS", ["may audit the other party's books"], RULE, cfg)
    assert (absent["tier"], absent["score"]) == ("FLAG", 55)
    assert (present["tier"], present["score"]) == ("ACCEPT", 10)


def test_non_compete_exception_mitigates(cfg):
    flagged = assess_clause("NON_COMPETE", ["you will not compete"], RULE, cfg)
    mitigated = assess_clause("NON_COMPETE", ["you will not compete"], RULE, cfg,
                              has_exception=True)
    assert (flagged["tier"], flagged["score"]) == ("FLAG", 70)
    assert (mitigated["tier"], mitigated["score"]) == ("ACCEPT", 15)


def test_mfn_rejects(cfg):
    a = assess_clause("MFN",
                      ["terms shall be no less favourable than terms given to any reseller"],
                      RULE, cfg)
    assert (a["tier"], a["score"]) == ("REJECT", 90)


def test_change_of_control_flags(cfg):
    a = assess_clause("CHANGE_OF_CONTROL",
                      ["consent required if a party undergoes a change of control"],
                      RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 60
    b = assess_clause("CHANGE_OF_CONTROL",
                      ["the other party may terminate on a change of control"],
                      RULE, cfg)
    assert b["score"] == 70


def test_auto_renewal_term_and_notice_split(cfg):
    # A 2-year term must not be misread as a 730-day notice period.
    ok = assess_clause("AUTO_RENEWAL", ["renew for one (1) year terms"],
                       RULE, cfg, notice_spans=["sixty (60) days prior notice"])
    assert (ok["tier"], ok["score"]) == ("ACCEPT", 10)
    long_term = assess_clause("AUTO_RENEWAL", ["renew for an additional two (2) years"],
                              RULE, cfg, notice_spans=["sixty (60) days prior notice"])
    assert long_term["tier"] == "FLAG" and long_term["score"] == 79
    long_notice = assess_clause("AUTO_RENEWAL", ["renew for one (1) year"],
                                RULE, cfg, notice_spans=["ninety (90) days prior notice"])
    assert long_notice["tier"] == "FLAG"
    absent = assess_clause("AUTO_RENEWAL", [], RULE, cfg, notice_spans=[])
    assert (absent["tier"], absent["score"]) == ("ACCEPT", 0)


def test_anti_assignment_consent_flags(cfg):
    a = assess_clause("ANTI_ASSIGNMENT",
                      ["No assignment shall be made without the prior written consent "
                       "of the Company"], RULE, cfg)
    assert a["tier"] == "FLAG" and a["score"] == 60
    b = assess_clause("ANTI_ASSIGNMENT",
                      ["Either party may freely assign this Agreement to an affiliate"],
                      RULE, cfg)
    assert (b["tier"], b["score"]) == ("ACCEPT", 15)


def test_absent_clause_accepts_except_audit(cfg):
    for rid in ["LIABILITY_CAP", "MFN", "NON_COMPETE", "GOVERNING_LAW"]:
        a = assess_clause(rid, [], RULE, cfg)
        assert (a["tier"], a["score"]) == ("ACCEPT", 0), rid


# ------------------------------------------------------------- graph / routes

def test_graph_produces_fifty_contracts(full_state):
    assert len(full_state["export_pack"]) == 50
    routes = {p["route"] for p in full_state["export_pack"]}
    assert routes <= {"APPROVE", "SEND_TO_LEGAL", "ESCALATE"}


def test_routes_match_measured_counts(full_state):
    routes = [p["route"] for p in full_state["export_pack"]]
    assert routes.count("ESCALATE") == 2  # the two MFN contracts
    assert routes.count("SEND_TO_LEGAL") == 48
    assert routes.count("APPROVE") == 0


def test_every_contract_has_twelve_clauses(full_state):
    for p in full_state["export_pack"]:
        assert len(p["clauses"]) == 12
        assert 0 <= p["overall_score"] <= 100
        assert p["pending_approval"] is True


def test_mfn_contracts_escalate(full_state):
    by_id = {p["contract_id"]: p for p in full_state["export_pack"]}
    for cid in ("CUAD-150", "CUAD-390"):
        assert by_id[cid]["route"] == "ESCALATE"
        mfn = [c for c in by_id[cid]["clauses"] if c["rule_id"] == "MFN"][0]
        assert mfn["tier"] == "REJECT"


def test_redline_draft_only_for_flagged(full_state):
    for p in full_state["export_pack"]:
        flagged = {c["rule_id"] for c in p["clauses"] if c["tier"] in ("FLAG", "REJECT")}
        drafted = {d["rule_id"] for d in p["redline_draft"]}
        assert drafted == flagged
        for d in p["redline_draft"]:
            assert d["redline"] and d["fallback"]


def test_overall_score_is_max_weighted(full_state):
    p = full_state["export_pack"][0]
    scores = [c["score"] for c in p["clauses"]]
    expected = round(0.7 * max(scores) + 0.3 * (sum(scores) / len(scores)))
    assert p["overall_score"] == expected


# ------------------------------------------------------------- eval / report

def test_golden_set_accuracy(cfg):
    ev = rd_eval.evaluate(cfg)
    assert ev["n"] == 36
    assert ev["tier_accuracy"] == 1.0
    assert ev["misses"] == []


def test_findings_match_pipeline(full_state):
    f = report.findings(full_state)
    assert f["contract_count"] == 50
    assert f["total_clause_spans"] == 488
    assert f["assessed_playbook_spans"] == 470
    assert f["exception_spans"] == 18
    assert f["uncapped_liability_contracts"] == 9
    assert f["uncapped_liability_pct"] == 18.0
    assert f["most_flagged_rule"] == "GOVERNING_LAW"
    assert f["routes"]["SEND_TO_LEGAL"] == 48
    assert f["effort_hours"] == 39.0
    assert f["rule_table"]["MFN"]["reject"] == 2


def test_raw_files_shape():
    queue = load_contracts()
    assert queue["license"] == "CC BY 4.0"
    assert queue["count"] == 50
    golden = json.loads((DATA / "golden_set.json").read_text())["pairs"]
    assert len(golden) == 36
    assert len({(p["contract_id"], p["rule_id"]) for p in golden}) == 36

"""Deterministic clause assessment against the Harbourline playbook.

Every rule reads the CUAD expert-labeled clause span(s) for its category
and applies disclosed, threshold-based tests — no LLM calls. Number words
are normalized to digits first ("twelve-month" -> "12-month", "sixty (60)
days" -> "60 days"), so the same parser works on written-out and numeric
periods. The TypeScript mirror in web/src/rules.ts implements these exact
functions; data/test-vectors.json keeps both in agreement.

Score: base + adjustment, capped at 100. Tier from score:
  score >= reject_bar (85) -> REJECT
  score >= flag_bar   (40) -> FLAG
  otherwise               -> ACCEPT
Thresholds are grid-searched on the golden set in eval.py.
"""
from __future__ import annotations

import re

NUMBER_WORDS = [
    ("ninety", "90"), ("eighty", "80"), ("seventy", "70"), ("sixty", "60"),
    ("fifty", "50"), ("forty", "40"), ("thirty", "30"), ("twenty four", "24"),
    ("twenty-four", "24"), ("twenty", "20"), ("fifteen", "15"),
    ("fourteen", "14"), ("thirteen", "13"), ("twelve", "12"),
    ("eleven", "11"), ("ten", "10"), ("nine", "9"), ("eight", "8"),
    ("seven", "7"), ("six", "6"), ("five", "5"), ("four", "4"),
    ("three", "3"), ("two", "2"), ("one", "1"),
]

US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "district of columbia",
}

CANADA_PROVINCES = {
    "british columbia", "alberta", "saskatchewan", "manitoba", "quebec",
    "new brunswick", "nova scotia", "prince edward island",
    "newfoundland", "newfoundland and labrador", "yukon",
    "northwest territories", "nunavut",
}

OTHER_JURISDICTIONS = {
    "australia", "england", "united kingdom", "scotland", "wales",
    "ireland", "germany", "france", "netherlands", "switzerland",
    "singapore", "japan", "india", "victoria", "new south wales",
    "queensland", "ontario",
}


def normalize_numbers(text: str) -> str:
    """Lowercase, rewrite number words as digits (longest first), and drop
    redundant parenthetical restatements ("three (3) months" -> "3 months")."""
    t = text.lower()
    for word, digit in NUMBER_WORDS:
        t = re.sub(rf"\b{re.escape(word)}\b", digit, t)
    t = re.sub(r"\(\d+\)", "", t)
    return re.sub(r"\s+", " ", t)


def _first_int(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def parse_months(text: str) -> int | None:
    """First '<n> month(s)' in normalized text, or years converted to months."""
    n = _first_int(r"(\d+)[\s-]*(?:months?|mos?)\b", text)
    if n is not None:
        return n
    y = _first_int(r"(\d+)[\s-]*(?:years?|yrs?)\b", text)
    return y * 12 if y is not None else None


def parse_days(text: str) -> int | None:
    """First '<n> day(s)' (business days included); months/years converted."""
    n = _first_int(r"(\d+)[\s-]*(?:business\s+days?|days?)\b", text)
    if n is not None:
        return n
    m = _first_int(r"(\d+)[\s-]*(?:months?|mos?)\b", text)
    if m is not None:
        return m * 30
    y = _first_int(r"(\d+)[\s-]*(?:years?|yrs?)\b", text)
    return y * 365 if y is not None else None


def parse_money(text: str) -> str | None:
    m = re.search(r"\$[\d,]+(?:\.\d+)?", text)
    return m.group(0) if m else None


def _result(rule_id: str, base: int, adjustment: int, evidence: list[str],
            redline: str, fallback: str) -> dict:
    score = min(100, base + adjustment)
    return {
        "rule_id": rule_id,
        "score": score,
        "score_parts": {"base": base, "adjustment": adjustment},
        "evidence": evidence,
        "redline": redline,
        "fallback": fallback,
    }


def _tier(score: int, cfg: dict) -> str:
    if score >= cfg["thresholds"]["reject_bar"]:
        return "REJECT"
    if score >= cfg["thresholds"]["flag_bar"]:
        return "FLAG"
    return "ACCEPT"


# ------------------------------------------------------------------ rules

def assess_liability_cap(spans: list[str], rule: dict) -> dict:
    text = " ".join(spans)
    norm = normalize_numbers(text)
    months = None
    if re.search(r"\b(fee|fees|paid|payable|consideration)\b", norm):
        months = parse_months(norm)
    if months is not None:
        if months >= 12:
            return _result("LIABILITY_CAP", 10, 0,
                           [f"cap of {months} months' fees (playbook minimum: 12)"],
                           rule["redline"], rule["fallback"])
        return _result("LIABILITY_CAP", 55, min(29, (12 - months) * 3),
                       [f"cap of only {months} months' fees (playbook minimum: 12)"],
                       rule["redline"], rule["fallback"])
    money = parse_money(text)
    if money:
        return _result("LIABILITY_CAP", 60, 0,
                       [f"fixed-amount cap ({money}) — cannot verify against 12 months' fees"],
                       rule["redline"], rule["fallback"])
    return _result("LIABILITY_CAP", 65, 0,
                   ["cap language present but no amount or period stated"],
                   rule["redline"], rule["fallback"])


def assess_uncapped_liability(spans: list[str], rule: dict) -> dict:
    text = " ".join(spans)
    low = text.lower()
    if re.search(r"\b(limited to|shall not exceed|maximum aggregate|capped at|cap of)\b", low):
        return _result("UNCAPPED_LIABILITY", 55, 0,
                       ["carve-out from a stated cap (confidentiality / IP / indemnity)"],
                       rule["redline"], rule["fallback"])
    if "in no event" in low and re.search(r"\b(consequential|incidental|indirect|special|punitive)\b", low):
        return _result("UNCAPPED_LIABILITY", 45, 0,
                       ["consequential-damages exclusion, not a general cap"],
                       rule["redline"], rule["fallback"])
    if re.search(r"\b(unlimited|uncapped|not be limited|without limit)\b", low):
        return _result("UNCAPPED_LIABILITY", 90, 0,
                       ["liability stated as unlimited / uncapped"],
                       rule["redline"], rule["fallback"])
    return _result("UNCAPPED_LIABILITY", 60, 0,
                   ["uncapped-liability language, scope unclear"],
                   rule["redline"], rule["fallback"])


def assess_termination(spans: list[str], rule: dict) -> dict:
    text = " ".join(spans)
    days = parse_days(normalize_numbers(text))
    if days is not None:
        if days >= 30:
            return _result("TERMINATION_CONVENIENCE", 10, 0,
                           [f"{days} days' notice (playbook minimum: 30)"],
                           rule["redline"], rule["fallback"])
        return _result("TERMINATION_CONVENIENCE", 55, min(29, 30 - days),
                       [f"only {days} days' notice (playbook minimum: 30)"],
                       rule["redline"], rule["fallback"])
    return _result("TERMINATION_CONVENIENCE", 60, 0,
                   ["termination-for-convenience clause states no notice period"],
                   rule["redline"], rule["fallback"])


def assess_governing_law(spans: list[str], rule: dict) -> dict:
    text = " ".join(spans)
    low = text.lower()
    if "ontario" in low:
        return _result("GOVERNING_LAW", 10, 0,
                       ["governing law is Ontario, as the playbook requires"],
                       rule["redline"], rule["fallback"])
    for prov in CANADA_PROVINCES:
        if prov in low:
            return _result("GOVERNING_LAW", 55, 0,
                           [f"governing law is {prov.title()} (Canada, but not Ontario)"],
                           rule["redline"], rule["fallback"])
    if "canada" in low:
        return _result("GOVERNING_LAW", 55, 0,
                       ["governing law is Canada (not Ontario specifically)"],
                       rule["redline"], rule["fallback"])
    for st in US_STATES:
        if st in low:
            return _result("GOVERNING_LAW", 80, 0,
                           [f"governing law is {st.title()} (US state, not Ontario)"],
                           rule["redline"], rule["fallback"])
    if re.search(r"\blaws of the state\b", low) or "state of" in low:
        return _result("GOVERNING_LAW", 80, 0,
                       ["governing law is a US state (not Ontario)"],
                       rule["redline"], rule["fallback"])
    for j in OTHER_JURISDICTIONS:
        if j in low:
            return _result("GOVERNING_LAW", 80, 0,
                           [f"governing law is {j.title()} (not Ontario)"],
                           rule["redline"], rule["fallback"])
    return _result("GOVERNING_LAW", 60, 0,
                   ["governing-law clause found but jurisdiction not identified"],
                   rule["redline"], rule["fallback"])


def assess_ip_assignment(spans: list[str], rule: dict) -> dict:
    text = " ".join(spans)
    low = text.lower()
    if re.search(r"\b(assign|become .* property|owned exclusively|hereby assigns)\b", low):
        return _result("IP_ASSIGNMENT", 65, 0,
                       ["IP created under the agreement is assigned to the counterparty"],
                       rule["redline"], rule["fallback"])
    return _result("IP_ASSIGNMENT", 45, 0,
                   ["broad licence-back to the counterparty, not a full assignment"],
                   rule["redline"], rule["fallback"])


def assess_non_compete(spans: list[str], rule: dict, has_exception: bool) -> dict:
    if has_exception:
        return _result("NON_COMPETE", 15, 0,
                       ["non-compete present but the contract carries stated carve-outs/exceptions"],
                       rule["redline"], rule["fallback"])
    return _result("NON_COMPETE", 70, 0,
                   ["non-compete with no stated carve-out or exception"],
                   rule["redline"], rule["fallback"])


def assess_no_solicit_employees(spans: list[str], rule: dict) -> dict:
    return _result("NO_SOLICIT_EMPLOYEES", 60, 0,
                   ["employee non-solicit present (playbook: delete or cap at 12 months)"],
                   rule["redline"], rule["fallback"])


def assess_mfn(spans: list[str], rule: dict) -> dict:
    return _result("MFN", 90, 0,
                   ["most-favoured-nation clause present (playbook: delete in full)"],
                   rule["redline"], rule["fallback"])


def assess_change_of_control(spans: list[str], rule: dict) -> dict:
    text = " ".join(spans)
    low = text.lower()
    if "terminat" in low:
        return _result("CHANGE_OF_CONTROL", 70, 0,
                       ["counterparty may terminate on a change of control"],
                       rule["redline"], rule["fallback"])
    return _result("CHANGE_OF_CONTROL", 60, 0,
                   ["change-of-control clause gives the counterparty consent or notice rights"],
                   rule["redline"], rule["fallback"])


def assess_auto_renewal(term_spans: list[str], notice_spans: list[str], rule: dict) -> dict:
    """term_spans: Renewal Term spans; notice_spans: Notice Period To
    Terminate Renewal spans. Kept separate on purpose: a renewal term of
    "two years" must never be misread as a 730-day notice period."""
    if not term_spans and not notice_spans:
        return _result("AUTO_RENEWAL", 5, 0,
                       ["no auto-renewal term found in the contract"],
                       rule["redline"], rule["fallback"])
    term = parse_months(normalize_numbers(" ".join(term_spans))) if term_spans else None
    notice = parse_days(normalize_numbers(" ".join(notice_spans))) if notice_spans else None
    if term is not None and term > 12:
        return _result("AUTO_RENEWAL", 55, min(29, (term - 12) * 2),
                       [f"auto-renewal term of {term} months (playbook maximum: 12)"],
                       rule["redline"], rule["fallback"])
    if notice is not None and notice > 60:
        return _result("AUTO_RENEWAL", 55, min(29, (notice - 60) // 5),
                       [f"opt-out notice of {notice} days (playbook maximum: 60)"],
                       rule["redline"], rule["fallback"])
    if term is None and notice is None:
        return _result("AUTO_RENEWAL", 60, 0,
                       ["auto-renewal present but term and notice period not stated"],
                       rule["redline"], rule["fallback"])
    bits = []
    if term is not None:
        bits.append(f"renewal term {term} months")
    if notice is not None:
        bits.append(f"opt-out notice {notice} days")
    return _result("AUTO_RENEWAL", 10, 0,
                   ["; ".join(bits) + " (within playbook limits)"],
                   rule["redline"], rule["fallback"])


def assess_anti_assignment(spans: list[str], rule: dict) -> dict:
    text = " ".join(spans)
    low = text.lower()
    # "Freely assignable" or "may assign ... without consent" is a pass.
    # NOTE: "shall not assign without consent" is consent-REQUIRED — the
    # word "without" alone must never trigger the free-assignment branch.
    free = ("freely assign" in low
            or re.search(r"may assign[^.]{0,120}without (the )?(prior )?(written )?consent", low))
    if free:
        return _result("ANTI_ASSIGNMENT", 15, 0,
                       ["assignment permitted without counterparty consent"],
                       rule["redline"], rule["fallback"])
    if "consent" in low:
        return _result("ANTI_ASSIGNMENT", 60, 0,
                       ["assignment requires the counterparty's consent"],
                       rule["redline"], rule["fallback"])
    return _result("ANTI_ASSIGNMENT", 55, 0,
                   ["anti-assignment clause present; consent position unclear"],
                   rule["redline"], rule["fallback"])


ASSESSORS = {
    "LIABILITY_CAP": assess_liability_cap,
    "UNCAPPED_LIABILITY": assess_uncapped_liability,
    "TERMINATION_CONVENIENCE": assess_termination,
    "GOVERNING_LAW": assess_governing_law,
    "IP_ASSIGNMENT": assess_ip_assignment,
    "NON_COMPETE": assess_non_compete,
    "NO_SOLICIT_EMPLOYEES": assess_no_solicit_employees,
    "MFN": assess_mfn,
    "CHANGE_OF_CONTROL": assess_change_of_control,
    "ANTI_ASSIGNMENT": assess_anti_assignment,
}


def assess_clause(rule_id: str, spans: list[str], rule: dict, cfg: dict,
                  has_exception: bool = False,
                  notice_spans: list[str] | None = None) -> dict:
    """Assess one playbook rule against its spans (empty spans = absent).
    AUTO_RENEWAL takes term spans in `spans` and notice spans separately."""
    if rule_id == "AUDIT_RIGHTS":
        if spans:
            r = _result("AUDIT_RIGHTS", 10, 0, ["audit rights present"],
                        rule["redline"], rule["fallback"])
        else:
            r = _result("AUDIT_RIGHTS", 55, 0,
                        ["no audit-rights clause found (playbook requires one)"],
                        rule["redline"], rule["fallback"])
        r["tier"] = _tier(r["score"], cfg)
        r["present"] = bool(spans)
        return r
    if rule_id == "AUTO_RENEWAL":
        if not spans and not notice_spans:
            r = _result(rule_id, 0, 0, ["clause category not present in this contract"],
                        rule["redline"], rule["fallback"])
            r["tier"] = "ACCEPT"
            r["present"] = False
            return r
        r = assess_auto_renewal(spans, notice_spans or [], rule)
        r["tier"] = _tier(r["score"], cfg)
        r["present"] = True
        return r
    if not spans:
        r = _result(rule_id, 0, 0, ["clause category not present in this contract"],
                    rule["redline"], rule["fallback"])
        r["tier"] = "ACCEPT"
        r["present"] = False
        return r
    if rule_id == "NON_COMPETE":
        r = assess_non_compete(spans, rule, has_exception)
    else:
        r = ASSESSORS[rule_id](spans, rule)
    r["tier"] = _tier(r["score"], cfg)
    r["present"] = True
    return r

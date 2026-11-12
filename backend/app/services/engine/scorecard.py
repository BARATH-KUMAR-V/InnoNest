LABEL = "Demonstration scorecard with illustrative weights. It has not been validated against portfolio outcomes and the score is not a probability of default."
SCORECARD_VERSION = "scorecard-demo-1.0"


def banded(value: float, table: list[tuple[float, int]], default: int = 0) -> int:
    for threshold, points in table:
        if value >= threshold:
            return points
    return default


def score(snapshot: dict, financial: dict) -> dict:
    bureau = snapshot["bureau"]
    primary = snapshot["applicants"][0]
    components = []

    def add(code: str, label: str, points: int, maximum: int, detail: str) -> None:
        components.append({"code": code, "label": label, "points": points, "max": maximum, "detail": detail})

    credit = bureau["score"] or 0
    add("CREDIT_SCORE", "Credit score", banded(credit, [(800, 30), (750, 26), (700, 20), (650, 12), (600, 6)]), 30, f"Bureau score {credit}")
    repayment = 0
    repayment += 8 if bureau["max_dpd_12m"] == 0 else (3 if bureau["max_dpd_12m"] <= 30 else 0)
    repayment += 4 if bureau["enquiries_6m"] <= 2 else (2 if bureau["enquiries_6m"] <= 4 else 0)
    repayment += 3 if bureau["utilization"] < 0.4 else (1 if bureau["utilization"] < 0.7 else 0)
    add("REPAYMENT", "Repayment indicators", repayment, 15, f"Max delinquency {bureau['max_dpd_12m']} days, {bureau['enquiries_6m']} enquiries, utilisation {bureau['utilization']:.0%}")
    years = primary["years_in_job"]
    stability = banded(years, [(5, 10), (3, 8), (2, 6), (1, 4)], 1) + {"GOVT": 5, "SALARIED": 3, "SELF_EMPLOYED": 3 if snapshot.get("gst_regular") else 1}[primary["employment_type"]]
    add("INCOME_STABILITY", "Income stability", min(stability, 15), 15, f"{years:g} years in current job or business, {primary['employment_type'].replace('_', ' ').lower()}")
    foir = financial["foir"]
    obligations = 15 if foir <= 0.30 else 12 if foir <= 0.40 else 8 if foir <= 0.50 else 4 if foir <= 0.60 else 0
    add("OBLIGATIONS", "Obligations after the new EMI", obligations, 15, f"FOIR {foir:.1%}")
    ltv = financial["ltv"]
    exposure = 15 if ltv <= 0.5 else 12 if ltv <= 0.6 else 9 if ltv <= 0.7 else 5 if ltv <= 0.8 else 1
    add("COLLATERAL", "Loan to value exposure", exposure, 15, f"LTV {ltv:.1%}")
    penalty = sum(5 if c["status"] == "REFER" else 3 for c in snapshot["checks"] if c["status"] in ("FLAG", "REFER"))
    penalty += 2 * sum(1 for c in snapshot["property"]["checks"] if c["status"] in ("REFER", "FAIL"))
    add("EVIDENCE", "Evidence completeness and consistency", max(0, 10 - penalty), 10, f"{len([c for c in snapshot['checks'] if c['status'] in ('FLAG', 'REFER')])} flagged verification checks")
    total = sum(c["points"] for c in components)
    band = "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 50 else "D" if total >= 35 else "E"
    reasons = [{"code": c["code"], "effect": "POSITIVE" if c["points"] >= c["max"] * 0.7 else "NEGATIVE" if c["points"] <= c["max"] * 0.4 else "NEUTRAL", "detail": c["detail"]} for c in components]
    return {"score": total, "max_score": 100, "band": band, "components": components, "reason_codes": reasons, "scorecard_version": SCORECARD_VERSION, "disclosure": LABEL}

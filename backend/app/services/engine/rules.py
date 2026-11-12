def rule(code: str, passed: bool, outcome_if_failed: str, message_ok: str, message_failed: str, values: dict | None = None) -> dict:
    return {"code": code, "outcome": "PASS" if passed else outcome_if_failed, "message": message_ok if passed else message_failed, "values": values or {}}


def evaluate(snapshot: dict, financial: dict, risk: dict, params: dict) -> list[dict]:
    product = snapshot["product"]
    applicants = snapshot["applicants"]
    primary = applicants[0]
    bureau = snapshot["bureau"]
    results = []
    youngest = min(a["age_years"] for a in applicants)
    results.append(rule("AGE_MINIMUM", youngest >= params["min_age"], "REJECT", "All applicants meet the minimum age.", f"An applicant is younger than {params['min_age']}.", {"youngest": round(youngest, 1)}))
    low, high = financial["loan_amount_range"]
    results.append(rule("LOAN_AMOUNT_RANGE", low <= financial["inputs"]["loan_amount"] <= high, "REJECT", "The loan amount is within the product range.",
                        f"The loan amount is outside the range of {low:,.0f} to {high:,.0f} for this product.", {"loan_amount": financial["inputs"]["loan_amount"], "range": [low, high]}))
    t_low, t_high = financial["tenure_range_months"]
    tenure = financial["inputs"]["tenure_months"]
    results.append(rule("TENURE_RANGE", t_low <= tenure <= t_high, "REJECT", "The tenure is within the product range.", f"The tenure must be between {t_low} and {t_high} months.", {"tenure_months": tenure}))
    results.append(rule("AGE_AT_MATURITY", tenure <= financial["tenure_cap_by_age_months"], "REJECT", "The loan matures before the maximum age.",
                        f"The tenure runs past the maximum age at maturity. The longest permitted tenure is {max(financial['tenure_cap_by_age_months'], 0)} months.", {"cap_months": financial["tenure_cap_by_age_months"]}))
    results.append(rule("MINIMUM_INCOME", financial["inputs"]["eligible_monthly_income"] >= financial["min_income_required"], "REJECT", "Eligible income meets the product minimum.",
                        f"Eligible income {financial['inputs']['eligible_monthly_income']:,.0f} is below the minimum of {financial['min_income_required']:,.0f}.", {"eligible_income": financial["inputs"]["eligible_monthly_income"]}))
    results.append(rule("FOIR_LIMIT", financial["foir"] <= financial["foir_limit"], "REJECT", f"FOIR {financial['foir']:.1%} is within the limit of {financial['foir_limit']:.0%}.",
                        f"FOIR {financial['foir']:.1%} is above the limit of {financial['foir_limit']:.0%}.", {"foir": financial["foir"], "limit": financial["foir_limit"]}))
    results.append(rule("LTV_LIMIT", financial["ltv"] <= financial["ltv_limit"], "REJECT", f"LTV {financial['ltv']:.1%} is within the limit of {financial['ltv_limit']:.0%}.",
                        f"LTV {financial['ltv']:.1%} is above the limit of {financial['ltv_limit']:.0%}.", {"ltv": financial["ltv"], "limit": financial["ltv_limit"]}))
    results.append(rule("EXPOSURE_CAP", financial["total_exposure"] <= params["max_exposure_per_applicant"], "REJECT", "Total exposure is within the policy cap.", "Total exposure is above the policy cap.", {"exposure": financial["total_exposure"]}))
    score = bureau["score"] or 0
    cs = params["credit_score"]
    results.append(rule("CREDIT_SCORE_FLOOR", score >= cs["reject_below"], "REJECT", f"Credit score {score} is above the floor of {cs['reject_below']}.", f"Credit score {score} is below the floor of {cs['reject_below']}.", {"score": score}))
    if score >= cs["reject_below"]:
        results.append(rule("CREDIT_SCORE_REVIEW", score >= cs["refer_below"], "REFER", f"Credit score {score} clears the review band.", f"Credit score {score} is in the review band below {cs['refer_below']}.", {"score": score}))
    results.append(rule("DELINQUENCY", bureau["max_dpd_12m"] <= params["max_dpd_12m"], "REJECT", "Delinquency in the last 12 months is within the limit.",
                        f"Delinquency of {bureau['max_dpd_12m']} days in the last 12 months is above the limit of {params['max_dpd_12m']} days.", {"max_dpd": bureau["max_dpd_12m"]}))
    bad_use = snapshot.get("end_use") in params["disallowed_end_uses"]
    results.append(rule("END_USE", not bad_use, "REJECT", "The stated end use is acceptable.", "The stated end use is not permitted by this policy.", {"end_use": snapshot.get("end_use")}))
    prop_type = next((c for c in snapshot["property"]["checks"] if c["code"] == "PROP-TYPE"), None)
    results.append(rule("PROPERTY_TYPE", not prop_type or prop_type["status"] != "FAIL", "REJECT", "The property type is acceptable.", "The property type is not accepted for this product.", {"property_type": snapshot["property_type"]}))
    results.append(rule("RISK_SCORE_FLOOR", risk["score"] >= params["risk_score"]["reject_below"], "REJECT", f"Risk score {risk['score']} is above the floor of {params['risk_score']['reject_below']}.",
                        f"Risk score {risk['score']} is below the floor of {params['risk_score']['reject_below']}.", {"score": risk["score"]}))
    if risk["score"] >= params["risk_score"]["reject_below"]:
        results.append(rule("RISK_SCORE_REVIEW", risk["score"] >= params["risk_score"]["refer_below"], "REFER", f"Risk score {risk['score']} clears the review band.",
                            f"Risk score {risk['score']} is in the review band below {params['risk_score']['refer_below']}.", {"score": risk["score"]}))
    kyc_fail = [c for c in snapshot["checks"] if c["status"] == "FAIL"]
    results.append(rule("KYC_FAILURE", not kyc_fail, "REJECT", "No verification check failed.", "A verification check failed: " + ", ".join(c["code"] for c in kyc_fail), {"codes": [c["code"] for c in kyc_fail]}))
    for category, code, label in (("AML", "AML_REVIEW", "A potential sanctions or PEP match needs authorised review."), ("KYC", "KYC_REVIEW", "An identity verification point needs review."),
                                  ("FRAUD", "FRAUD_INDICATORS_REVIEW", "Document or consistency indicators need review.")):
        hits = [c for c in snapshot["checks"] if c["category"] == category and c["status"] == "REFER"]
        results.append(rule(code, not hits, "REFER", "No check in this category needs review.", label, {"codes": [c["code"] for c in hits]}))
    variance_limit = params["income_variance_refer_pct"]
    worst = max(applicants, key=lambda a: a["variance_pct"])
    results.append(rule("INCOME_VARIANCE", worst["variance_pct"] <= variance_limit, "REFER", "Declared income agrees with the evidence.",
                        f"Declared income is {worst['variance_pct']:.0%} above the documented income. The documented figure was used.", {"variance_pct": worst["variance_pct"], "limit": variance_limit}))
    property_flags = [c for c in snapshot["property"]["checks"] if c["status"] == "REFER"]
    results.append(rule("PROPERTY_REVIEW", not property_flags, "REFER", "No property point needs review.", "Property points need review: " + ", ".join(c["code"] for c in property_flags), {"codes": [c["code"] for c in property_flags]}))
    explained = snapshot.get("explained_conflicts", [])
    results.append(rule("EXPLAINED_CONFLICTS", not explained, "REFER", "No unresolved information conflict.", "The applicant explained a conflict in the information. A reviewer must confirm it.", {"keys": explained}))
    return results

from app.services import finance


def ltv_limit_for(bands: list, loan_amount: float) -> float:
    for ceiling, limit in bands:
        if ceiling is None or loan_amount <= ceiling:
            return limit
    return bands[-1][1]


def compute(snapshot: dict, params: dict) -> dict:
    product = snapshot["product"]
    applicants = snapshot["applicants"]
    primary = applicants[0]
    loan = float(snapshot["loan_amount"])
    rate = float(snapshot["interest_rate"])
    months = int(snapshot["tenure_months"])
    eligible_income = round(sum(a["eligible_income"] for a in applicants), 2)
    existing_emi = round(sum(a["existing_emi_used"] for a in applicants), 2)
    proposed_emi = finance.emi(loan, rate, months)
    foir_limit = params["foir_limit"][primary["employment_type"]]
    foir_value = finance.foir(existing_emi, proposed_emi, eligible_income)
    property_data = snapshot["property"]
    accepted_value = float(property_data["accepted_value"])
    existing_mortgage = float(property_data["existing_mortgage_amount"])
    exposure = loan + existing_mortgage
    ltv_cap = ltv_limit_for(params["ltv_limit"][product], loan)
    ltv_value = finance.ltv(exposure, accepted_value)
    max_emi = finance.max_eligible_emi(eligible_income, existing_emi, foir_limit)
    loan_by_foir = finance.max_principal(max_emi, rate, months)
    loan_by_ltv = max(0.0, accepted_value * ltv_cap - existing_mortgage)
    low, high = params["loan_amount_limits"][product]
    indicative = max(0.0, min(loan_by_foir, loan_by_ltv, high))
    tenure_low, tenure_high = params["tenure_limits_months"][product]
    age_caps = [int((params["max_age_at_maturity"][a["employment_type"]] - a["age_years"]) * 12) for a in applicants]
    return {
        "inputs": {"loan_amount": loan, "interest_rate": rate, "tenure_months": months, "eligible_monthly_income": eligible_income, "existing_monthly_emi": existing_emi,
                   "accepted_property_value": accepted_value, "existing_mortgage_amount": existing_mortgage},
        "formulas": {"emi": "P x r x (1+r)^n / ((1+r)^n - 1), r = annual rate / 12 / 100", "foir": "(existing EMI + proposed EMI) / eligible monthly income",
                     "ltv": "total loan exposure / accepted property value"},
        "proposed_emi": round(proposed_emi, 2), "foir": round(foir_value, 4), "foir_limit": foir_limit, "total_exposure": round(exposure, 2),
        "ltv": round(ltv_value, 4), "ltv_limit": ltv_cap, "max_eligible_emi": round(max_emi, 2), "loan_by_foir": round(loan_by_foir, 2), "loan_by_ltv": round(loan_by_ltv, 2),
        "indicative_eligible_loan": round(indicative, 2), "min_income_required": params["min_monthly_income"][product],
        "tenure_range_months": [tenure_low, tenure_high], "tenure_cap_by_age_months": min(age_caps), "loan_amount_range": [low, high],
    }

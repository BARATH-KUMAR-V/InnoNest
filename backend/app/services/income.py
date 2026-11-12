from app.models import Applicant, Document, ProviderCall
from app.services import documents as docs
from app.services.verification import call_for, doc_numbers


def assess(applicant: Applicant, calls: list[ProviderCall], documents: list[Document], params: dict) -> dict:
    declared = float(applicant.monthly_income)
    candidates = {"declared": declared}
    notes = []
    bank = call_for(calls, "account_aggregator", applicant.id)
    bank_credit = bank.response["average_monthly_credit"] if bank and bank.response_status == "OK" else None
    if applicant.employment_type == "SELF_EMPLOYED":
        itr_doc = doc_numbers(documents, "ITR", applicant.id, "gross_total_income")
        profit = doc_numbers(documents, "BUSINESS_FINANCIALS", applicant.id, "net_profit")
        itr_call = call_for(calls, "itr", applicant.id)
        if itr_doc:
            candidates["itr_document"] = itr_doc / 12
        if profit:
            candidates["business_profit"] = profit / 12
        if itr_call and itr_call.response_status == "OK":
            candidates["itr_provider"] = itr_call.response["gross_total_income"] / 12
        turnover = applicant.annual_turnover
        gst = call_for(calls, "gst", applicant.id)
        if turnover and gst and gst.response_status == "OK" and gst.response.get("applicable"):
            gst_total = sum(gst.response["monthly_turnover"])
            ratio = gst_total / turnover
            if abs(ratio - 1) > 0.15:
                notes.append(f"GST turnover ({gst_total:,.0f}) differs from declared turnover ({turnover:,.0f}) by more than 15 percent.")
        if turnover and bank_credit is not None and bank_credit * 12 < turnover * 0.6:
            notes.append("Bank credits are well below the declared turnover.")
    else:
        slip = doc_numbers(documents, "SALARY_SLIP", applicant.id, "net_pay")
        if slip:
            candidates["salary_slip"] = slip
        if bank_credit is not None:
            candidates["bank_credits"] = bank_credit
    basis = min(candidates, key=candidates.get)
    base = candidates[basis]
    recognised_other = float(applicant.other_income) * params["other_income_recognition"]
    variance = (declared - base) / declared if declared > 0 else 0.0
    bureau = call_for(calls, "bureau", applicant.id)
    reported = bureau.response["reported_monthly_obligation"] if bureau and bureau.response_status == "OK" else 0.0
    existing = max(float(applicant.existing_emi), float(reported))
    return {"applicant_id": applicant.id, "name": applicant.full_name, "employment_type": applicant.employment_type, "candidates": {k: round(v, 2) for k, v in candidates.items()},
            "basis": basis, "base_income": round(base, 2), "other_income_declared": float(applicant.other_income), "other_income_recognised": round(recognised_other, 2),
            "eligible_income": round(base + recognised_other, 2), "declared_income": declared, "variance_pct": round(variance, 4),
            "existing_emi_declared": float(applicant.existing_emi), "existing_emi_bureau": float(reported), "existing_emi_used": existing, "notes": notes}

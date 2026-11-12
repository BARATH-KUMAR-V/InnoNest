import hashlib
import json

from app.services.engine import financials, rules, scorecard
from app.services.finance import inr

REASON_NAMES = {
    "AGE_MINIMUM": "Applicant below minimum age", "LOAN_AMOUNT_RANGE": "Loan amount outside product range", "TENURE_RANGE": "Tenure outside product range",
    "AGE_AT_MATURITY": "Age at maturity above limit", "MINIMUM_INCOME": "Income below product minimum", "FOIR_LIMIT": "FOIR above limit", "LTV_LIMIT": "LTV above limit",
    "EXPOSURE_CAP": "Exposure above cap", "CREDIT_SCORE_FLOOR": "Credit score below floor", "CREDIT_SCORE_REVIEW": "Credit score in review band", "DELINQUENCY": "Recent delinquency above limit",
    "END_USE": "End use not permitted", "PROPERTY_TYPE": "Property type not accepted", "RISK_SCORE_FLOOR": "Risk score below floor", "RISK_SCORE_REVIEW": "Risk score in review band",
    "KYC_FAILURE": "Verification check failed", "AML_REVIEW": "Potential AML match", "KYC_REVIEW": "Identity verification needs review", "FRAUD_INDICATORS_REVIEW": "Fraud indicators need review",
    "INCOME_VARIANCE": "Declared income above documented income", "PROPERTY_REVIEW": "Property points need review", "EXPLAINED_CONFLICTS": "Information conflict explained by applicant",
}


def explain(outcome: str, policy_name: str, version: int, results: list[dict], financial: dict, risk: dict) -> str:
    figures = (f"Proposed EMI {inr(financial['proposed_emi'])}, FOIR {financial['foir']:.1%} against a limit of {financial['foir_limit']:.0%}, "
               f"LTV {financial['ltv']:.1%} against a limit of {financial['ltv_limit']:.0%}, risk score {risk['score']} (band {risk['band']}).")
    failed = [r for r in results if r["outcome"] != "PASS"]
    head = f"Outcome {outcome} under the {policy_name} policy, version {version}."
    if outcome == "APPROVE":
        return f"{head} All {len(results)} policy rules passed. {figures}"
    label = "Rejected because" if outcome == "REJECT" else "Referred for review because"
    reasons = " ".join(r["message"] for r in failed if r["outcome"] == outcome)
    return f"{head} {label}: {reasons} {figures}"


def evaluate(snapshot: dict, policy_name: str, policy_version: int, params: dict, ruleset_version: str) -> dict:
    financial = financials.compute(snapshot, params)
    risk = scorecard.score(snapshot, financial)
    results = rules.evaluate(snapshot, financial, risk, params)
    outcome = "REJECT" if any(r["outcome"] == "REJECT" for r in results) else "REFER" if any(r["outcome"] == "REFER" for r in results) else "APPROVE"
    reason_codes = [{"code": r["code"], "name": REASON_NAMES[r["code"]], "outcome": r["outcome"], "message": r["message"], "values": r["values"]} for r in results if r["outcome"] != "PASS"]
    content = {"outcome": outcome, "reason_codes": [(r["code"], r["outcome"]) for r in reason_codes], "financial": financial, "risk_score": risk["score"], "rules": [(r["code"], r["outcome"]) for r in results]}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()
    return {"outcome": outcome, "financial": financial, "risk": risk, "rules": results, "reason_codes": reason_codes, "ruleset_version": ruleset_version,
            "explanation": explain(outcome, policy_name, policy_version, results, financial, risk), "result_hash": digest}

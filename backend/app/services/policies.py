from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import invalid, not_found
from app.models import Policy
from app.services import audit

RULESET_VERSION = "ruleset-2026.11"

BASE_PARAMS = {
    "foir_limit": {"SALARIED": 0.55, "GOVT": 0.60, "SELF_EMPLOYED": 0.50},
    "ltv_limit": {"HOME_LOAN": [[3000000, 0.90], [7500000, 0.80], [None, 0.75]], "LAP": [[None, 0.60]]},
    "min_monthly_income": {"HOME_LOAN": 25000, "LAP": 40000},
    "loan_amount_limits": {"HOME_LOAN": [300000, 50000000], "LAP": [500000, 30000000]},
    "tenure_limits_months": {"HOME_LOAN": [12, 360], "LAP": [12, 180]},
    "max_age_at_maturity": {"SALARIED": 60, "GOVT": 60, "SELF_EMPLOYED": 65},
    "min_age": 21,
    "min_experience_years": {"SALARIED": 1, "GOVT": 1, "SELF_EMPLOYED": 2},
    "credit_score": {"reject_below": 650, "refer_below": 700},
    "max_dpd_12m": 30,
    "other_income_recognition": 0.5,
    "income_variance_refer_pct": 0.15,
    "valuation_deviation_refer_pct": 0.10,
    "risk_score": {"reject_below": 40, "refer_below": 55},
    "extra_reports_required_above": {"HOME_LOAN": 5000000, "LAP": 0},
    "disallowed_property_types": {"HOME_LOAN": ["AGRICULTURAL"], "LAP": ["AGRICULTURAL"]},
    "disallowed_end_uses": ["SPECULATIVE_INVESTMENT"],
    "fraud_refer_score": 0.35,
    "max_exposure_per_applicant": 60000000,
}

DEFAULTS = {
    "balanced": {"name": "Balanced", "description": "Illustrative mid-market lender policy. Not a Hero Housing policy.", "overrides": {}},
    "conservative": {
        "name": "Conservative",
        "description": "Illustrative low-risk-appetite lender policy with tighter ratios and stronger credit requirements. Not a Hero Housing policy.",
        "overrides": {
            "foir_limit": {"SALARIED": 0.45, "GOVT": 0.50, "SELF_EMPLOYED": 0.40},
            "ltv_limit": {"HOME_LOAN": [[3000000, 0.85], [7500000, 0.75], [None, 0.70]], "LAP": [[None, 0.50]]},
            "min_monthly_income": {"HOME_LOAN": 35000, "LAP": 60000},
            "credit_score": {"reject_below": 700, "refer_below": 750},
            "max_dpd_12m": 0,
            "risk_score": {"reject_below": 50, "refer_below": 65},
            "valuation_deviation_refer_pct": 0.05,
            "income_variance_refer_pct": 0.10,
        },
    },
    "flexible": {
        "name": "Flexible",
        "description": "Illustrative higher-risk-appetite lender policy with wider ratios and recognition of more income. Not a Hero Housing policy.",
        "overrides": {
            "foir_limit": {"SALARIED": 0.65, "GOVT": 0.70, "SELF_EMPLOYED": 0.60},
            "ltv_limit": {"HOME_LOAN": [[3000000, 0.90], [7500000, 0.85], [None, 0.80]], "LAP": [[None, 0.70]]},
            "min_monthly_income": {"HOME_LOAN": 18000, "LAP": 30000},
            "credit_score": {"reject_below": 600, "refer_below": 650},
            "max_dpd_12m": 60,
            "other_income_recognition": 0.75,
            "risk_score": {"reject_below": 35, "refer_below": 48},
            "valuation_deviation_refer_pct": 0.15,
            "income_variance_refer_pct": 0.20,
        },
    },
}

POLICY_KEYS = tuple(DEFAULTS)


def params_for(key: str) -> dict:
    merged = {**BASE_PARAMS}
    merged.update(DEFAULTS[key]["overrides"])
    return merged


def seed_policies(db: Session) -> None:
    for key, spec in DEFAULTS.items():
        exists = db.execute(select(Policy).where(Policy.key == key)).first()
        if exists:
            continue
        db.add(Policy(key=key, name=spec["name"], version=1, status="ACTIVE", description=spec["description"], params=params_for(key),
                      change_note="Initial illustrative policy"))
    db.flush()


def active_policy(db: Session, key: str) -> Policy:
    policy = db.execute(select(Policy).where(Policy.key == key, Policy.status == "ACTIVE")).scalar_one_or_none()
    if not policy:
        raise not_found(f"Policy '{key}'")
    return policy


def list_active(db: Session) -> list[Policy]:
    return list(db.execute(select(Policy).where(Policy.status == "ACTIVE").order_by(Policy.key)).scalars())


def history(db: Session, key: str) -> list[Policy]:
    return list(db.execute(select(Policy).where(Policy.key == key).order_by(Policy.version.desc())).scalars())


def validate_params(params: dict) -> None:
    problems = []
    for group, limit in params.get("foir_limit", {}).items():
        if not 0.1 <= limit <= 0.9:
            problems.append({"field": f"foir_limit.{group}", "message": "FOIR limit must be between 0.10 and 0.90"})
    for product, bands in params.get("ltv_limit", {}).items():
        for band in bands:
            if not 0.2 <= band[1] <= 0.95:
                problems.append({"field": f"ltv_limit.{product}", "message": "LTV limit must be between 0.20 and 0.95"})
    score = params.get("credit_score", {})
    if score and score["reject_below"] > score["refer_below"]:
        problems.append({"field": "credit_score", "message": "Reject threshold cannot be above the refer threshold"})
    risk = params.get("risk_score", {})
    if risk and risk["reject_below"] > risk["refer_below"]:
        problems.append({"field": "risk_score", "message": "Reject threshold cannot be above the refer threshold"})
    for product, (low, high) in params.get("tenure_limits_months", {}).items():
        if low <= 0 or high < low:
            problems.append({"field": f"tenure_limits_months.{product}", "message": "Tenure range is not valid"})
    if problems:
        raise invalid("The policy parameters are not valid", problems)


def publish_version(db: Session, key: str, params: dict, change_note: str, actor: str, actor_role: str) -> Policy:
    current = active_policy(db, key)
    merged = {**current.params, **params}
    validate_params(merged)
    current.status = "ARCHIVED"
    new = Policy(key=key, name=current.name, version=current.version + 1, status="ACTIVE", description=current.description, params=merged,
                 change_note=change_note, created_by=actor)
    db.add(new)
    db.flush()
    audit.record(db, "policy.version_published", actor=actor, actor_role=actor_role, entity="policy", entity_id=new.id,
                 details={"key": key, "version": new.version, "change_note": change_note, "changed": sorted(params)})
    return new

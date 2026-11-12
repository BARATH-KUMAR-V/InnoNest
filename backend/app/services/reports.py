import csv
import io
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Applicant, Application, AuditEvent, Decision
from app.models.mixins import utcnow
from app.services.catalog import STATUSES


def dashboard(db: Session) -> dict:
    by_status = dict(db.execute(select(Application.status, func.count()).group_by(Application.status)).all())
    by_product = dict(db.execute(select(Application.product, func.count()).group_by(Application.product)).all())
    outcome_by_product = {}
    for product, status, count in db.execute(select(Application.product, Application.status, func.count()).where(Application.status.in_(("APPROVED", "REJECTED", "REFERRED"))).group_by(Application.product, Application.status)):
        outcome_by_product.setdefault(product, {})[status] = count
    total = sum(by_status.values())
    since = utcnow() - timedelta(days=30)
    daily = dict(db.execute(select(func.date(Application.created_at), func.count()).where(Application.created_at >= since).group_by(func.date(Application.created_at))).all())
    recent = db.execute(select(AuditEvent).where(AuditEvent.application_id.is_not(None)).order_by(AuditEvent.id.desc()).limit(12)).scalars().all()
    references = {a.id: a.reference for a in db.execute(select(Application).where(Application.id.in_({e.application_id for e in recent}))).scalars()} if recent else {}
    decided = db.execute(select(func.avg(func.julianday(Application.decided_at) - func.julianday(Application.submitted_at))).where(Application.decided_at.is_not(None))).scalar() if db.bind.dialect.name == "sqlite" else None
    return {
        "total": total, "approved": by_status.get("APPROVED", 0), "rejected": by_status.get("REJECTED", 0), "referred": by_status.get("REFERRED", 0),
        "action_required": by_status.get("ACTION_REQUIRED", 0), "verification_pending": by_status.get("VERIFICATION_PENDING", 0), "draft": by_status.get("DRAFT", 0),
        "status_breakdown": [{"status": s, "count": by_status.get(s, 0)} for s in STATUSES], "product_distribution": [{"product": p, "count": c} for p, c in sorted(by_product.items())],
        "outcomes_by_product": [{"product": p, **{k: v.get(k, 0) for k in ("APPROVED", "REJECTED", "REFERRED")}} for p, v in sorted(outcome_by_product.items())],
        "applications_per_day": [{"date": str(day), "count": count} for day, count in sorted(daily.items())],
        "approval_rate": round(by_status.get("APPROVED", 0) / max(1, by_status.get("APPROVED", 0) + by_status.get("REJECTED", 0)), 4),
        "recent_activity": [{"id": e.id, "action": e.action, "application_id": e.application_id, "reference": references.get(e.application_id), "actor": e.actor, "at": e.created_at.isoformat()} for e in recent],
        "avg_days_to_decision": round(decided, 2) if decided else None,
    }


def to_csv(headers: list[str], rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def register_csv(db: Session, applications: list[Application]) -> str:
    rows = []
    for a in applications:
        primary = a.applicants[0] if a.applicants else None
        rows.append([a.reference, a.product, a.status, primary.full_name if primary else "", primary.employment_type if primary else "", a.loan_amount, a.interest_rate, a.tenure_months,
                     a.property_city, a.policy_key, a.submitted_at.isoformat() if a.submitted_at else "", a.decided_at.isoformat() if a.decided_at else ""])
    return to_csv(["reference", "product", "status", "applicant", "employment_type", "loan_amount", "interest_rate", "tenure_months", "property_city", "policy", "submitted_at", "decided_at"], rows)


def decisions_csv(db: Session) -> str:
    rows = []
    for decision, reference in db.execute(select(Decision, Application.reference).join(Application, Application.id == Decision.application_id).order_by(Decision.id)):
        rows.append([reference, decision.id, decision.outcome, decision.kind, decision.policy_name, decision.policy_version, decision.ruleset_version,
                     ";".join(r["code"] for r in decision.reason_codes), decision.result_hash, decision.created_at.isoformat()])
    return to_csv(["reference", "decision_id", "outcome", "kind", "policy", "policy_version", "ruleset_version", "reason_codes", "result_hash", "created_at"], rows)


def audit_csv(events: list[AuditEvent]) -> str:
    return to_csv(["id", "application_id", "actor", "actor_role", "action", "entity", "entity_id", "created_at", "hash"],
                  [[e.id, e.application_id, e.actor, e.actor_role, e.action, e.entity, e.entity_id, e.created_at.isoformat(), e.hash] for e in events])

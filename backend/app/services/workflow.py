from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, forbidden, invalid
from app.models import Application, Assessment, Decision, User, VerificationCheck
from app.models.mixins import utcnow
from app.providers import service as providers
from app.services import audit, checklist, followup, policies, snapshot, verification
from app.services.catalog import EDITABLE_STATUSES, OPEN_STATUSES
from app.services.engine import core as engine

RERUNNABLE = ("ACTION_REQUIRED", "DOCUMENTS_RECEIVED", "VERIFICATION_PENDING", "SUBMITTED", "PROCESSING", "REFERRED")


def set_status(db: Session, application: Application, status: str, actor: str = "system", role: str = "system", reason: str | None = None) -> None:
    previous = application.status
    application.status = status
    audit.record(db, "application.status_changed", application.id, actor, role, "application", application.id, {"from": previous, "to": status, "reason": reason})


def next_run(db: Session, application: Application) -> int:
    latest = db.execute(select(func.max(VerificationCheck.run)).where(VerificationCheck.application_id == application.id)).scalar()
    return (latest or 0) + 1


def carry_dispositions(db: Session, application: Application, rows: list[VerificationCheck], run: int) -> None:
    previous = db.execute(select(VerificationCheck).where(VerificationCheck.application_id == application.id, VerificationCheck.run < run,
                                                           VerificationCheck.disposition.is_not(None)).order_by(VerificationCheck.id)).scalars()
    latest = {(p.code, p.applicant_id): p for p in previous}
    for row in rows:
        old = latest.get((row.code, row.applicant_id))
        if old and old.status == row.status:
            row.disposition, row.disposition_note, row.disposition_by = old.disposition, old.disposition_note, old.disposition_by


def submit(db: Session, application: Application, user: User) -> Application:
    if application.status != "DRAFT":
        raise conflict("Only a draft application can be submitted")
    application.submitted_at = utcnow()
    set_status(db, application, "SUBMITTED", user.email, user.role, "Applicant submitted the application")
    audit.record(db, "application.submitted", application.id, user.email, user.role, "application", application.id, {"product": application.product})
    return run_pipeline(db, application, "submission")


def hold_for_applicant(db: Session, application: Application, evaluation: dict) -> Application:
    config = followup.follow_up_config(db)
    due = utcnow() + timedelta(days=config["expiry_days"])
    first_entry = application.status != "ACTION_REQUIRED"
    sync = followup.sync_requests(db, application, evaluation["items"], due)
    if first_entry or sync["created"]:
        application.expires_at = due
    application.pending_stage = "COMPLETENESS"
    if application.status != "ACTION_REQUIRED":
        set_status(db, application, "ACTION_REQUIRED", reason=f"{evaluation['open_count']} item(s) needed before underwriting can continue")
    if sync["created"]:
        name = application.applicants[0].full_name.split()[0].title()
        body = (f"{name}, to continue with application {application.reference} we need the following:\n{followup.request_message([{'message': r.message} for r in sync['created']])}\n"
                f"Please respond before {application.expires_at:%d %b %Y}. Your application is saved and will resume as soon as everything is received.")
        followup.notify(db, application, "ACTION_REQUIRED", f"Action needed on application {application.reference}", body)
    return application


def hold_for_providers(db: Session, application: Application, failed: list) -> Application:
    application.pending_stage = "VERIFICATION"
    set_status(db, application, "VERIFICATION_PENDING", reason="Verification providers unavailable: " + ", ".join(sorted({c.provider for c in failed})))
    return application


def decide(db: Session, application: Application, checks: list[VerificationCheck], policy_key: str | None = None) -> Decision:
    policy = policies.active_policy(db, policy_key or application.policy_key)
    data = snapshot.build(db, application, policy.params, checks)
    result = engine.evaluate(data, policy.name, policy.version, policy.params, policies.RULESET_VERSION)
    run = checks[0].run if checks else 1
    db.add(Assessment(application_id=application.id, run=run, financial=result["financial"], risk=result["risk"], property_assessment=data["property"],
                      verification_summary={"checks": [{"code": c.code, "status": c.status, "category": c.category} for c in checks]}))
    refs = [{"type": "document", "id": d.id, "sha256": d.sha256} for d in application.documents if d.status == "ACTIVE"]
    refs += [{"type": "provider_call", "id": c.id, "provider": c.provider} for c in providers.latest_calls(db, application.id)]
    refs += [{"type": "verification_check", "id": c.id, "code": c.code} for c in checks]
    decision = Decision(application_id=application.id, outcome=result["outcome"], kind="SYSTEM", policy_key=policy.key, policy_name=policy.name, policy_version=policy.version,
                        ruleset_version=result["ruleset_version"], inputs=data, outputs={"financial": result["financial"], "risk": result["risk"], "rules": result["rules"]},
                        reason_codes=result["reason_codes"], explanation=result["explanation"], evidence_refs=refs, policy_snapshot=policy.params, result_hash=result["result_hash"])
    db.add(decision)
    db.flush()
    audit.record(db, "decision.recorded", application.id, "decision-engine", "system", "decision", decision.id,
                 {"outcome": decision.outcome, "policy": policy.key, "policy_version": policy.version, "result_hash": decision.result_hash,
                  "reason_codes": [r["code"] for r in decision.reason_codes]})
    return decision


OUTCOME_STATUS = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REFER": "REFERRED"}
OUTCOME_COPY = {
    "APPROVE": "Your application has been approved subject to the lender's sanction terms and final documentation.",
    "REJECT": "We are unable to approve this application under the current policy. The reasons are available on your application page.",
    "REFER": "Your application needs a closer look from an underwriter. We will contact you if we need anything more.",
}


def run_pipeline(db: Session, application: Application, trigger: str) -> Application:
    resumed_from = application.pending_stage
    set_status(db, application, "PROCESSING", reason=f"Underwriting run triggered by {trigger}" + (f", resuming from {resumed_from}" if resumed_from else ""))
    evaluation = checklist.evaluate(db, application)
    if not evaluation["complete"]:
        return hold_for_applicant(db, application, evaluation)
    followup.sync_requests(db, application, evaluation["items"])
    application.pending_stage = None
    run = providers.next_run(db, application.id)
    calls = providers.collect(db, application, run)
    audit.record(db, "provider.calls_completed", application.id, details={"run": run, "calls": [{"provider": c.provider, "mode": c.mode, "status": c.response_status, "result": c.verification_result} for c in calls]})
    failed = providers.unavailable_critical(calls)
    if failed:
        return hold_for_providers(db, application, failed)
    policy = policies.active_policy(db, application.policy_key)
    results = verification.run_checks(db, application, policy.params)
    check_run = next_run(db, application)
    rows = verification.persist(db, application, results, check_run)
    carry_dispositions(db, application, rows, check_run)
    audit.record(db, "verification.completed", application.id, details={"run": check_run, "statuses": {r.code + (f":{r.applicant_id}" if r.applicant_id else ""): r.status for r in rows}})
    decision = decide(db, application, rows)
    application.decided_at = utcnow()
    set_status(db, application, OUTCOME_STATUS[decision.outcome], reason=decision.explanation[:200])
    followup.notify(db, application, "DECISION", f"Update on application {application.reference}", OUTCOME_COPY[decision.outcome])
    return application


def revalidate(db: Session, application: Application, user: User, reason: str) -> Application:
    if application.status not in ("ACTION_REQUIRED", "VERIFICATION_PENDING"):
        return application
    evaluation = checklist.evaluate(db, application)
    if application.status == "ACTION_REQUIRED":
        if not evaluation["complete"]:
            sync = followup.sync_requests(db, application, evaluation["items"], application.expires_at)
            if sync["created"]:
                followup.notify(db, application, "ACTION_REQUIRED", f"More information needed on application {application.reference}", followup.request_message(sync["created"]))
            elif sync["fulfilled"]:
                left = [i for i in evaluation["items"] if i["status"] == "OPEN"]
                followup.notify(db, application, "PROGRESS", f"Thank you. Application {application.reference} is still waiting on {len(left)} item(s)", followup.request_message(left))
            return application
        set_status(db, application, "DOCUMENTS_RECEIVED", user.email, user.role, reason)
    return run_pipeline(db, application, reason)


def retry_verification(db: Session, application: Application, user: User) -> Application:
    if application.status != "VERIFICATION_PENDING":
        raise conflict("Only an application waiting on verification can be retried")
    return run_pipeline(db, application, "verification retry")


def manual_review(db: Session, application: Application, user: User, outcome: str, note: str) -> Decision:
    if application.status != "REFERRED":
        raise conflict("Only a referred application can be reviewed")
    if outcome not in ("APPROVE", "REJECT"):
        raise invalid("The review outcome must be APPROVE or REJECT")
    if len(note.strip()) < 10:
        raise invalid("A review note of at least 10 characters is required")
    last = db.execute(select(Decision).where(Decision.application_id == application.id).order_by(Decision.id.desc()).limit(1)).scalar_one()
    decision = Decision(application_id=application.id, outcome=outcome, kind="REVIEW", decided_by=user.email, policy_key=last.policy_key, policy_name=last.policy_name,
                        policy_version=last.policy_version, ruleset_version=last.ruleset_version, inputs=last.inputs, outputs=last.outputs, reason_codes=last.reason_codes,
                        explanation=f"Referral reviewed by {user.full_name}: {outcome}. {note.strip()}", evidence_refs=last.evidence_refs, policy_snapshot=last.policy_snapshot,
                        result_hash=last.result_hash, review_note=note.strip())
    db.add(decision)
    db.flush()
    application.decided_at = utcnow()
    set_status(db, application, OUTCOME_STATUS[outcome], user.email, user.role, "Referral reviewed")
    audit.record(db, "decision.reviewed", application.id, user.email, user.role, "decision", decision.id, {"outcome": outcome, "note": note.strip(), "system_decision": last.id})
    followup.notify(db, application, "DECISION", f"Update on application {application.reference}", OUTCOME_COPY[outcome])
    return decision


def withdraw(db: Session, application: Application, user: User) -> None:
    if application.status not in OPEN_STATUSES + ("DRAFT",):
        raise conflict("This application can no longer be withdrawn")
    for request in followup.open_requests(application):
        request.status = "WITHDRAWN"
    set_status(db, application, "WITHDRAWN", user.email, user.role, "Withdrawn by applicant")


def ensure_editable(application: Application) -> None:
    if application.status not in EDITABLE_STATUSES:
        raise forbidden("This application can no longer be edited")

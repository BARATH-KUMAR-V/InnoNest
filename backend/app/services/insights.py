from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.models import Application, Decision, VerificationCheck
from app.providers.service import latest_calls
from app.services import documents as docs, policies, snapshot
from app.services.catalog import DOC_LABELS
from app.services.engine import core as engine


def latest_checks(db: Session, application_id: int) -> list[VerificationCheck]:
    run = db.execute(select(func.max(VerificationCheck.run)).where(VerificationCheck.application_id == application_id)).scalar()
    if run is None:
        return []
    return list(db.execute(select(VerificationCheck).where(VerificationCheck.application_id == application_id, VerificationCheck.run == run).order_by(VerificationCheck.id)).scalars())


def latest_decision(db: Session, application_id: int) -> Decision | None:
    return db.execute(select(Decision).where(Decision.application_id == application_id).order_by(Decision.id.desc()).limit(1)).scalar_one_or_none()


def evidence_graph(db: Session, application: Application, include_fields: bool = True) -> dict:
    nodes, edges = [], []

    def node(node_id: str, kind: str, label: str, data: dict | None = None) -> None:
        nodes.append({"id": node_id, "type": kind, "label": label, "data": data or {}})

    def edge(source: str, target: str, label: str) -> None:
        edges.append({"source": source, "target": target, "label": label})

    root = f"application:{application.id}"
    node(root, "APPLICATION", f"{application.reference} ({application.product.replace('_', ' ').title()})", {"status": application.status, "loan_amount": application.loan_amount})
    for applicant in application.applicants:
        node(f"applicant:{applicant.id}", "APPLICANT", applicant.full_name, {"role": applicant.role, "employment_type": applicant.employment_type})
        edge(f"applicant:{applicant.id}", root, "applicant on")
    documents = docs.active_documents(db, application.id)
    for document in documents:
        node(f"document:{document.id}", "DOCUMENT", DOC_LABELS.get(document.doc_type, document.doc_type), {"sha256": document.sha256, "extraction_status": document.extraction_status, "confidence": document.confidence})
        edge(f"document:{document.id}", f"applicant:{document.applicant_id}" if document.applicant_id else root, "supports")
        if include_fields:
            for field in document.fields:
                node(f"field:{field.id}", "FIELD", f"{field.name}: {field.effective_value}", {"confidence": field.confidence, "corrected": field.corrected_value is not None})
                edge(f"field:{field.id}", f"document:{document.id}", "extracted from")
    for call in latest_calls(db, application.id):
        node(f"provider:{call.id}", "PROVIDER_RESPONSE", f"{call.provider_name} [{call.mode}]", {"response_status": call.response_status, "verification_result": call.verification_result, "source_ref": call.source_ref, "consent_ref": call.consent_ref})
        edge(f"provider:{call.id}", f"applicant:{call.applicant_id}" if call.applicant_id and call.provider not in ("cersai", "property_registration") else root, "responded for")
    checks = latest_checks(db, application.id)
    for check in checks:
        node(f"check:{check.id}", "VERIFICATION", f"{check.code}: {check.status}", {"detail": check.detail, "disposition": check.disposition})
        edge(f"check:{check.id}", f"applicant:{check.applicant_id}" if check.applicant_id else root, "assesses")
    decision = latest_decision(db, application.id)
    if decision:
        for key, label in (("financial", "Financial assessment"), ("risk", "Risk scorecard")):
            node(f"calc:{key}", "CALCULATION", label, {k: v for k, v in decision.outputs[key].items() if isinstance(v, (int, float, str))})
            edge(root, f"calc:{key}", "calculated")
        for document in documents:
            if document.doc_type in ("SALARY_SLIP", "ITR", "BANK_STATEMENT", "FORM16", "BUSINESS_FINANCIALS"):
                edge(f"document:{document.id}", "calc:financial", "income evidence")
            if document.doc_type == "VALUATION_REPORT":
                edge(f"document:{document.id}", "calc:financial", "accepted value")
        for check in checks:
            edge(f"check:{check.id}", "calc:risk", "scored")
        policy_id = f"policy:{decision.policy_key}:{decision.policy_version}"
        node(policy_id, "POLICY", f"{decision.policy_name} policy v{decision.policy_version}", {"ruleset_version": decision.ruleset_version})
        decision_id = f"decision:{decision.id}"
        node(decision_id, "DECISION", f"{decision.outcome} ({decision.kind.lower()})", {"result_hash": decision.result_hash, "decided_by": decision.decided_by})
        edge("calc:financial", decision_id, "input to")
        edge("calc:risk", decision_id, "input to")
        edge(policy_id, decision_id, "applied")
        for reason in decision.reason_codes:
            reason_id = f"reason:{decision.id}:{reason['code']}"
            node(reason_id, "REASON", reason["name"], {"outcome": reason["outcome"], "message": reason["message"]})
            edge(reason_id, decision_id, "reason")
            edge(policy_id, reason_id, "rule")
    return {"nodes": nodes, "edges": edges}


def replay(decision: Decision) -> dict:
    policy_name, version = decision.policy_name, decision.policy_version
    result = engine.evaluate(decision.inputs, policy_name, version, decision.policy_snapshot, decision.ruleset_version)
    matches = result["result_hash"] == decision.result_hash
    steps = [
        {"step": "Load stored snapshot", "detail": f"{len(decision.inputs['applicants'])} applicant(s), {decision.inputs['product'].replace('_', ' ').title()}, loan {decision.inputs['loan_amount']:,.0f}"},
        {"step": "Load policy as it stood", "detail": f"{policy_name} policy version {version}, {decision.ruleset_version}"},
        {"step": "Recompute financials", "detail": f"EMI {result['financial']['proposed_emi']:,.2f}, FOIR {result['financial']['foir']:.1%}, LTV {result['financial']['ltv']:.1%}"},
        {"step": "Recompute risk scorecard", "detail": f"Score {result['risk']['score']}, band {result['risk']['band']}"},
        {"step": "Evaluate policy rules", "detail": f"{sum(1 for r in result['rules'] if r['outcome'] == 'PASS')} passed, {sum(1 for r in result['rules'] if r['outcome'] != 'PASS')} raised"},
        {"step": "Compare with stored result", "detail": "The recomputed result is identical to the stored result" if matches else "The recomputed result differs from the stored result"},
    ]
    return {"decision_id": decision.id, "stored_outcome": decision.outcome, "recomputed_outcome": result["outcome"], "identical": matches, "stored_hash": decision.result_hash,
            "recomputed_hash": result["result_hash"], "steps": steps, "rules": result["rules"]}


def compare_policies(db: Session, application: Application) -> dict:
    checks = latest_checks(db, application.id)
    if not checks:
        raise not_found("Verification results for this application")
    outcomes, matrix = [], {}
    for policy in policies.list_active(db):
        data = snapshot.build(db, application, policy.params, checks)
        result = engine.evaluate(data, policy.name, policy.version, policy.params, policies.RULESET_VERSION)
        outcomes.append({"policy_key": policy.key, "policy_name": policy.name, "policy_version": policy.version, "outcome": result["outcome"], "foir": result["financial"]["foir"],
                         "foir_limit": result["financial"]["foir_limit"], "ltv": result["financial"]["ltv"], "ltv_limit": result["financial"]["ltv_limit"],
                         "risk_score": result["risk"]["score"], "risk_band": result["risk"]["band"], "indicative_eligible_loan": result["financial"]["indicative_eligible_loan"],
                         "explanation": result["explanation"]})
        for rule in result["rules"]:
            matrix.setdefault(rule["code"], {})[policy.key] = {"outcome": rule["outcome"], "message": rule["message"]}
    differing = [{"code": code, "name": engine.REASON_NAMES[code], "by_policy": cells} for code, cells in matrix.items() if len({c["outcome"] for c in cells.values()}) > 1]
    return {"application_id": application.id, "outcomes": outcomes, "differences": differing, "rule_matrix": matrix}

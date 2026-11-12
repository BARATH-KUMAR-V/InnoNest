import os
import tempfile
from functools import lru_cache
from pathlib import Path

WORK_DIR = Path(tempfile.mkdtemp(prefix="innonest-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{WORK_DIR / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(WORK_DIR / "uploads")
os.environ["ENABLE_SCHEDULER"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.demo import runner, scenarios
from app.main import app
from app.models import (Applicant, Application, Assessment, AuditEvent, Decision, Document, DocumentRequest, ExtractedField, Notification, Policy, ProviderCall,
                        Setting, VerificationCheck)
from app.providers.base import OUTAGES
from app.services import policies

CLEAN_ORDER = (ExtractedField, Document, DocumentRequest, VerificationCheck, Assessment, Decision, ProviderCall, Notification, Applicant, Application, AuditEvent, Setting, Policy)

USERS = {
    "applicant": ("applicant@example.com", "Applicant@123"),
    "other_applicant": ("applicant2@example.com", "Applicant@123"),
    "underwriter": ("underwriter@example.com", "Underwriter@123"),
    "policy_admin": ("policy@example.com", "PolicyAdmin@123"),
    "auditor": ("auditor@example.com", "Auditor@123"),
}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_state(client):
    db = SessionLocal()
    try:
        for model in CLEAN_ORDER:
            db.execute(delete(model))
        policies.seed_policies(db)
        db.commit()
    finally:
        db.close()
    OUTAGES.clear()
    yield
    OUTAGES.clear()


@pytest.fixture(scope="session")
def auth(client):
    return {role: runner.login(client, email, password) for role, (email, password) in USERS.items()}


@pytest.fixture
def applicant(auth):
    return auth["applicant"]


@pytest.fixture
def underwriter(auth):
    return auth["underwriter"]


@pytest.fixture
def run(client, auth):
    def execute(key: str, submit: bool = True) -> dict:
        return runner.run_scenario(client, auth["applicant"], key, submit)
    return execute


@lru_cache(maxsize=None)
def cached_documents(key: str, only: tuple | None = None):
    return scenarios.generate_documents(scenarios.SCENARIOS[key], list(only) if only else None)


@pytest.fixture
def docs_for():
    def get(key: str, only: list[str] | None = None):
        return cached_documents(key, tuple(only) if only else None)
    return get


def get_json(client, url: str, headers: dict, **params):
    response = client.get(url, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def fetch(client):
    return lambda url, headers, **params: get_json(client, url, headers, **params)

from fastapi import APIRouter

from app.api.v1 import applications, assessments, auth, documents, followup, integrations, reports

api_router = APIRouter(prefix="/api/v1")
for module in (auth, applications, documents, followup, integrations, assessments, reports):
    api_router.include_router(module.router)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core import branding
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import install_handlers
from app.core.migrations import upgrade_to_head
from app.services import seed
from app.services.scheduler import FollowUpScheduler

scheduler = FollowUpScheduler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    upgrade_to_head()
    db = SessionLocal()
    try:
        seed.seed_reference_data(db)
        if settings.seed_demo_data:
            seed.seed_users(db)
    finally:
        db.close()
    scheduler.start()
    yield
    scheduler.stop()


def create_app() -> FastAPI:
    app = FastAPI(title=f"{branding.NAME} API", version="1.0.0", lifespan=lifespan,
                  description=f"{branding.IDENTITY}. {branding.TAGLINE} Home Loan and Loan Against Property underwriting with connected evidence, automated applicant follow-up and explainable decisions.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    install_handlers(app)
    app.include_router(api_router)

    @app.get("/api/health", tags=["system"])
    def health():
        return {"status": "ok", "service": branding.NAME}

    dist = settings.frontend_dist
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            candidate = dist / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()

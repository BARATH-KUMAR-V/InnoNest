import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra="ignore")

    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'innonest.db'}"
    upload_dir: Path = PROJECT_ROOT / "uploads"
    sample_dir: Path = PROJECT_ROOT / "data" / "samples"
    jwt_secret: str = "change-this-secret-before-any-real-use-0123456789"
    jwt_algorithm: str = "HS256"
    token_expire_minutes: int = 480
    max_upload_mb: int = 8
    allowed_extensions: list[str] = Field(default_factory=lambda: ["pdf", "png", "jpg", "jpeg"])
    reminder_intervals_hours: list[int] = Field(default_factory=lambda: [24, 72, 120])
    expiry_days: int = 14
    enable_scheduler: bool = True
    scheduler_interval_seconds: int = 300
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:8000"])
    provider_modes: str = "{}"
    sandbox_registry_path: Path = PROJECT_ROOT / "data" / "sandbox_registry.json"
    seed_demo_data: bool = True
    smtp_host: str = ""
    smtp_port: int = 25
    smtp_sender: str = "noreply@example.com"
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"

    def provider_mode_map(self) -> dict[str, str]:
        try:
            return json.loads(self.provider_modes)
        except json.JSONDecodeError:
            return {}


settings = Settings()

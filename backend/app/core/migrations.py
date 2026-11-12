from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    return config


def upgrade_to_head() -> None:
    if settings.database_url.startswith("sqlite"):
        path = settings.database_url.replace("sqlite:///", "", 1)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(), "head")

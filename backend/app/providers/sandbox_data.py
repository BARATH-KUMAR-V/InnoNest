import csv
import json
from datetime import date, timedelta
from functools import lru_cache

from app.core.config import PROJECT_ROOT, settings
from app.providers.base import stable_random


@lru_cache(maxsize=1)
def registry() -> dict:
    path = settings.sandbox_registry_path
    if not path.exists():
        return {}
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def watchlist() -> list[dict]:
    path = PROJECT_ROOT / "data" / "synthetic_watchlist.csv"
    if not path.exists():
        return []
    with path.open() as handle:
        return list(csv.DictReader(handle))


def profile_for(pan: str) -> dict:
    return registry().get((pan or "").upper(), {})


def bureau_profile(applicant: dict) -> dict:
    entry = profile_for(applicant["pan"]).get("bureau")
    if entry:
        return entry
    rng = stable_random("bureau", applicant["pan"])
    return {"score": 660 + rng.randint(0, 150), "max_dpd_12m": 0, "enquiries_6m": rng.randint(0, 3), "utilization": round(rng.uniform(0.1, 0.5), 2)}


def bank_profile(applicant: dict) -> dict:
    entry = profile_for(applicant["pan"]).get("bank", {})
    return {"income_factor": entry.get("income_factor", round(stable_random("bank", applicant["pan"]).uniform(0.96, 1.02), 3)),
            "income_cv": entry.get("income_cv", 0.08), "bounces": entry.get("bounces", 0)}


def month_starts(count: int, end: date) -> list[date]:
    months = []
    cursor = end.replace(day=1)
    for _ in range(count):
        cursor = (cursor - timedelta(days=1)).replace(day=1)
        months.append(cursor)
    return list(reversed(months))

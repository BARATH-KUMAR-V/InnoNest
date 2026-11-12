import logging
import threading

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import followup

log = logging.getLogger("scheduler")


class FollowUpScheduler:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def sweep(self) -> None:
        db = SessionLocal()
        try:
            followup.send_due_reminders(db)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("Follow-up sweep failed")
        finally:
            db.close()

    def loop(self) -> None:
        while not self.stop_event.wait(settings.scheduler_interval_seconds):
            self.sweep()

    def start(self) -> None:
        if settings.enable_scheduler and self.thread is None:
            self.thread = threading.Thread(target=self.loop, name="follow-up-scheduler", daemon=True)
            self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

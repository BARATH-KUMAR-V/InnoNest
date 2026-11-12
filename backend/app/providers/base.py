import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import settings

MODES = ("MOCK", "SANDBOX", "LIVE_PARTNER")
OUTAGES: set[str] = set()


def stable_random(*parts) -> random.Random:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def content_hash(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ProviderRequest:
    application: dict
    applicant: dict
    consent_ref: str | None = None
    extra: dict = field(default_factory=dict)


class ProviderError(Exception):
    pass


class Adapter:
    key = ""
    name = ""
    default_mode = "MOCK"
    needs_consent = True
    live_route = ""
    consent_scope = ""

    def mode(self) -> str:
        configured = settings.provider_mode_map().get(self.key, self.default_mode)
        return configured if configured in MODES else self.default_mode

    def fetch(self, request: ProviderRequest) -> dict:
        raise NotImplementedError

    def verify(self, payload: dict, request: ProviderRequest) -> str:
        return "VERIFIED"

    def source_reference(self, request: ProviderRequest) -> str:
        return f"{self.key.upper()}-{content_hash([request.applicant.get('pan'), request.application.get('reference')])[:10].upper()}"

    def call(self, request: ProviderRequest) -> dict:
        mode = self.mode()
        envelope = {
            "provider": self.key,
            "provider_name": self.name,
            "mode": mode,
            "integration_status": "ACTIVE",
            "consent_ref": request.consent_ref if self.needs_consent else None,
            "requested_at": now_iso(),
            "response_status": "OK",
            "source_ref": None,
            "verification_result": "NOT_CHECKED",
            "payload": {},
            "live_route": self.live_route,
        }
        if self.needs_consent and not request.consent_ref:
            envelope.update(response_status="CONSENT_MISSING", integration_status="BLOCKED", verification_result="NOT_CHECKED")
            return envelope
        if mode == "LIVE_PARTNER":
            envelope.update(response_status="UNAVAILABLE", integration_status="NOT_CONFIGURED", verification_result="NOT_CHECKED")
            envelope["payload"] = {"message": "No partner credentials are configured for this provider"}
            return envelope
        if self.key in OUTAGES:
            envelope.update(response_status="UNAVAILABLE", integration_status="DEGRADED", verification_result="NOT_CHECKED")
            envelope["payload"] = {"message": "The provider did not respond. The check was not performed"}
            return envelope
        try:
            payload = self.fetch(request)
        except ProviderError as exc:
            envelope.update(response_status="FAILED", verification_result="NOT_CHECKED")
            envelope["payload"] = {"message": str(exc)}
            return envelope
        envelope["payload"] = payload
        envelope["source_ref"] = self.source_reference(request)
        envelope["verification_result"] = self.verify(payload, request)
        return envelope

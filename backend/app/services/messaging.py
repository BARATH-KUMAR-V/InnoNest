import smtplib
from email.message import EmailMessage

from app.core.config import settings


class Channel:
    name = ""
    simulated = True

    def send(self, recipient: str, subject: str, body: str) -> str:
        raise NotImplementedError


class SimulatedEmail(Channel):
    name = "EMAIL"

    def send(self, recipient, subject, body):
        return "SIMULATED_NOT_SENT"


class SimulatedSms(Channel):
    name = "SMS"

    def send(self, recipient, subject, body):
        return "SIMULATED_NOT_SENT"


class SmtpEmail(Channel):
    name = "EMAIL"
    simulated = False

    def send(self, recipient, subject, body):
        message = EmailMessage()
        message["From"] = settings.smtp_sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.send_message(message)
            return "SENT"
        except OSError:
            return "FAILED"


def email_channel() -> Channel:
    return SmtpEmail() if settings.smtp_host else SimulatedEmail()


def sms_channel() -> Channel:
    return SimulatedSms()
